"""Preserve the real regional 403 diagnostics from workflow run 43594061340."""
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))
import collect_normalized as production
import mir_regions
from source_diagnostics import ReadError


class ObservedMirFailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_observed_catalog_403_keeps_access_diagnostics_in_source_report(self):
        fixture = Path(__file__).parent / 'fixtures_live/mir-catalog-regions-403-20261114.json'
        observed = json.loads(fixture.read_text())['source_report']
        cfg = {'id': 'mir', 'mode': 'mir', 'name': observed['name'], 'url': observed['root']}

        class Source:
            def __init__(self, *args):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        async def read_region(client, cfg, key, now, limit):
            failure = next(error for error in observed['errors'] if error['region'] == key)
            # PublicSource.check_response raises this typed error for the recorded
            # HTTP response. The dropped response body was not retained in the
            # artifact, so no body or fingerprint is invented for this replay.
            raise ReadError(failure['reason'], status=403)

        with patch.object(production, 'PublicSource', Source), \
                patch.object(mir_regions, 'read_region', read_region), \
                contextlib.redirect_stdout(io.StringIO()):
            report, rows = await production.one(None, cfg, observed['observed_at'], 500)

        self.assertEqual(rows, [])
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['normalized'], 0)
        self.assertEqual(report['failed'], 2)
        self.assertEqual([error['region'] for error in report['errors']], ['msk', 'spb'])
        for error in report['errors']:
            with self.subTest(region=error['region']):
                self.assertEqual(error['reason'], 'http_403')
                self.assertEqual(error.get('category'), 'access_denied')
                self.assertEqual(error.get('error_type'), 'ReadError')
                self.assertEqual(error.get('http_status'), 403)
                self.assertEqual(error.get('path'), '/promo/')


if __name__ == '__main__':
    unittest.main()
