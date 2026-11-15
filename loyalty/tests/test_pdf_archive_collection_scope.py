"""Previously skipped public PDF observations reach the real capture pipeline.

Discovery metadata is copied from retained public CI observations. The bank
and Utair transports reuse an archived UniCredit PDF only as opaque bytes;
an injected parser failure prevents its text being attributed to another
source. EKP uses the actual current price.pdf and an observed clinic refusal.
No source wording or discount terms are manufactured by these tests.
"""
import asyncio
import copy
from datetime import datetime
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))
import ekp_linked_rules as ekp
import ekp_catalog
import recovered_sources as banks
import utair_documents as utair
from recovered_contract import SOURCES

FIXTURE = json.loads((Path(__file__).with_name('fixtures_live') /
    'pdf-archive-collection-scope-20261115.json').read_text())
ARCHIVE = Path(__file__).parents[2] / 'source-documents'
OPAQUE_SHA = 'c9db3bc59fea0645579888f4d1a453c1b5089a7accf601878c66ebfc155f2610'
PRICE_SHA = 'e79939871dcf6a7ffd9785889a56b43b203a4f4585bb1b9d98eb10424fe0a2db'
CLINIC = 'https://mpclinic.ru/upload/1689252399.pdf'
PRICE = 'https://xn--b1abfnwkklk1gdn5a.xn--p1ai/img/dogovori/price.pdf'
NOW = '2026-11-15T12:00:00+00:00'
VTB_ROOT = 'https://www.vtb.ru/media-files/vtb.ru/sitepages/'
BANK_PDFS = {
    'af_vtb_rules': [
        VTB_ROOT + 'privilegia/karty/debetovye/privilegiya-aeroflot/usloviya_akcii_ko_dnyu_rozhdeniya.pdf',
        VTB_ROOT + 'privilegia/karty/debetovye/privilegiya-aeroflot/VTB_AERO_tariffs.pdf',
        VTB_ROOT + 'tarify/chastnim-licam/t-priv_pbu.pdf',
        VTB_ROOT + 'privilegia/mir-pass/site_usloviya_nspk_11032026.pdf',
    ],
    'uralsib_rzd_rules': [
        'https://uralsib.ru/api/directory-engine/files/rates/usloviya_privetstvennye-bally-rzhd_ewzxcygl.pdf',
    ],
}


class Response:
    def __init__(self, data=b'', status=200, headers=None):
        self.data = data
        self.status_code = status
        self.headers = headers or {'Content-Type':'application/pdf'}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def iter_content(self, size):
        yield self.data


class FrozenClock(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime.fromisoformat(NOW)


class BankArchiveScopeTests(unittest.TestCase):
    def check_scope(self, capture):
        data = (ARCHIVE / (OPAQUE_SHA + '.pdf')).read_bytes()
        for observed in FIXTURE['bank_parents']:
            sid = observed['source_id']
            requested = []

            class Reader(banks.ScopedReader):
                def __enter__(self):
                    # Replace network/CA setup; retain real URL binding and
                    # read_document validation below that boundary.
                    return self

                def read(self, url):
                    self.allowed(url)
                    return {}, '\n'.join(observed['details']['sections']).encode()

                def _get(self, url, *, ca_download=False):
                    self.allowed(url)
                    requested.append(url)
                    return 200, {'Content-Type':'application/pdf'}, data

            spec = SOURCES[sid]
            cfg = {'id':sid, 'name':sid, 'url':spec['url'],
                   'mode':'recovered', 'access_profile':spec['profile']}
            report = {'errors':[]}
            with self.subTest(source=sid), tempfile.TemporaryDirectory() as directory:
                with patch.dict(os.environ, {'PDF_CAPTURE_DIR':directory if capture else ''}):
                    with patch.object(banks, 'ScopedReader', Reader), \
                            patch.object(banks, 'parse_bank_page', return_value=copy.deepcopy(observed)), \
                            patch('pypdf.PdfReader', side_effect=ValueError('parser_failure')):
                        rows = asyncio.run(banks.collect_recovered(cfg, report, NOW, 100))
                self.assertEqual(sorted(requested), sorted(BANK_PDFS[sid]) if capture else [])
                self.assertEqual(rows[0]['benefit_text'], observed['benefit_text'])
                if capture:
                    self.assertEqual((Path(directory) / (OPAQUE_SHA + '.pdf')).read_bytes(), data)
                    self.assertEqual({r['source_url'] for r in rows[1:]}, set(BANK_PDFS[sid]))
                    self.assertTrue(all(r['record_kind'] == 'source_observation' for r in rows[1:]))
                    self.assertTrue(all(not r['benefit_text'] for r in rows[1:]))
                else:
                    self.assertEqual(len(rows), 1)
                    self.assertEqual(list(Path(directory).iterdir()), [])

    def test_capture_mode_retains_pdf_links_from_real_bank_observations(self):
        self.check_scope(True)

    def test_default_bank_scope_keeps_parent_without_fetching_pdf(self):
        self.check_scope(False)


class UtairArchiveScopeTests(unittest.IsolatedAsyncioTestCase):
    async def check_scope(self, capture):
        observed = FIXTURE['utair_omitted']
        entry = {'key':'cstcnc', 'kind':'shortlink', 'url':observed['url'],
                 'labels':observed['labels'], 'contexts':[]}
        # Current public redirect observed on 2026-11-15, with its query omitted.
        target = ('https://eu-s3.beelinecloud.ru/utair-log/'
                  '%D0%9F%D1%80%D0%B0%D0%B2%D0%B8%D0%BB%D0%B0%20Status%20'
                  '%D0%BD%D0%B0%20%D1%81%D0%B0%D0%B9%D1%82%2001.05.2026%2B.pdf')
        data = (ARCHIVE / (OPAQUE_SHA + '.pdf')).read_bytes()
        requested = []

        class Client:
            async def read(self, url, **kwargs):
                return '\n'.join(observed['labels'])

        def get(url, **kwargs):
            requested.append(url)
            if url == 'https://ut0.ru/cstcnc':
                return Response(status=302, headers={'Location':target})
            self.assertEqual(url, target)
            return Response(data)

        report = {'errors':[]}
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {'PDF_CAPTURE_DIR':directory if capture else ''}):
                with patch.object(utair, 'discover_documents', return_value=[entry]), \
                        patch.object(utair.requests, 'get', side_effect=get), \
                        patch('pypdf.PdfReader', side_effect=ValueError('parser_failure')):
                    rows = await utair.collect_documents(Client(),
                        {'id':'utair_rule_documents', 'url':utair.ROOT}, report, NOW, 100)
            self.assertEqual(requested, ['https://ut0.ru/cstcnc', target] if capture else [])
            if capture:
                self.assertEqual((Path(directory) / (OPAQUE_SHA + '.pdf')).read_bytes(), data)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]['source_url'], 'https://ut0.ru/cstcnc')
                self.assertEqual(rows[0]['record_kind'], 'source_observation')
                self.assertEqual(rows[0]['benefit_text'], '')
            else:
                self.assertEqual(rows, [])
                self.assertEqual(list(Path(directory).iterdir()), [])

    async def test_capture_mode_reaches_observed_general_rules_before_parse(self):
        await self.check_scope(True)

    async def test_default_utair_scope_still_excludes_general_rules(self):
        await self.check_scope(False)


class EkpArchiveScopeTests(unittest.TestCase):
    def check_scope(self, capture):
        base = copy.deepcopy(FIXTURE['ekp_parents'])
        # Replay the retained public responses through today's adapter without
        # changing the actual source observation or request timestamps.
        base['records'] = [ekp_catalog.make_record(r['details']['public_partner'], r['observed_at'],
            request=r['details']['request'], response_sha=r['details']['source_response_sha256'],
            observed_total=r['details']['source_reported_total'],
            completed_at=r['details']['request_completed_at']) for r in base['records']]
        base['sources'][0]['normalized'] = len(base['records'])
        data = (ARCHIVE / (PRICE_SHA + '.pdf')).read_bytes()
        requested = []

        class Network:
            def get(self, url, **kwargs):
                requested.append(url)
                if url == CLINIC:
                    return Response(status=503)
                self_case.assertEqual(url, PRICE)
                return Response(data)

        self_case = self
        reader = ekp.Reader(session=Network(), sleep=lambda _:None)
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / 'parents.json'
            source.write_text(json.dumps(base, ensure_ascii=False))
            out = folder / 'output'
            archive = folder / 'archive'
            env = {'PDF_CAPTURE_DIR':str(archive) if capture else '',
                   'GITHUB_RUN_ID':'archive-scope-test', 'GITHUB_RUN_ATTEMPT':'1',
                   'GITHUB_SHA':'0' * 40, 'SCRAPINGANT_API_KEY':''}
            args = ['ekp_linked_rules.py', '--input', str(source), '--out', str(out)]
            with patch.dict(os.environ, env), patch.object(sys, 'argv', args), \
                    patch.object(ekp, 'datetime', FrozenClock), \
                    patch.object(ekp, 'Reader', return_value=reader), \
                    patch('pypdf.PdfReader', side_effect=ValueError('parser_failure')), \
                    redirect_stdout(io.StringIO()):
                ekp.main()
            self.assertEqual(sorted(requested), sorted([CLINIC, PRICE]) if capture else [])
            audit = json.loads((out / 'audit.json').read_text())
            self.assertEqual(audit['practical_only'], not capture)
            rows = json.loads((out / 'normalized.json').read_text())['records']
            if capture:
                self.assertEqual((archive / (PRICE_SHA + '.pdf')).read_bytes(), data)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]['source_url'], PRICE)
                self.assertEqual(rows[0]['details']['document_sha256'], PRICE_SHA)
                self.assertEqual(rows[0]['record_kind'], 'source_observation')
                self.assertEqual(rows[0]['benefit_text'], '')
                failed = next(r for r in audit['results'] if r['url'] == CLINIC)
                self.assertEqual(failed['error'], 'el_http_503')
            else:
                self.assertEqual(rows, [])
                self.assertFalse(archive.exists())

    def test_capture_mode_downloads_observed_appendices_and_replays_same_scope(self):
        self.check_scope(True)

    def test_default_ekp_scope_still_skips_pdf_appendices(self):
        self.check_scope(False)


if __name__ == '__main__':
    unittest.main()
