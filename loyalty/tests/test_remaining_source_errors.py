"""Regressions from the final PR93 acceptance and same-runner live captures."""
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from playwright.async_api import Error as BrowserError

sys.path[:0]=[str(Path(__file__).parents[1]),str(Path(__file__).parent)]
import collect_normalized as collector
from test_html_hydration import HydratingPage, ReplaySource
from source_diagnostics import ParseError, ReadError, error_record
from expansion_common import add_error
from normalized import validate_offer

NOW='2026-10-23T09:00:00+00:00'

class RemainingFailures(unittest.IsolatedAsyncioTestCase):
    async def test_registered_article_waits_for_real_dom_and_parses(self):
        cfg=next(c for c in json.loads((Path(__file__).parents[1]/'sources_normalized.json').read_text()) if c['id']=='t2_registration_rules')
        raw=(Path(__file__).parent/'fixtures_live/t2-registration-20261023.html').read_text()
        page=HydratingPage(initial='<html><title>T2</title></html>',hydrated=raw,final_url=cfg['url'])
        with patch.object(collector,'PublicSource',ReplaySource),contextlib.redirect_stdout(io.StringIO()):
            report,rows=await collector.one(page,cfg,NOW,500)
        self.assertEqual(report['status'],'ok',report['errors'])
        self.assertEqual(len(rows),1)
        self.assertEqual(len(page.ready_calls),1)
        validate_offer(rows[0])
        self.assertIn('90',rows[0]['conditions_text'])

    def test_nested_catalog_error_retains_safe_transport_diagnostics(self):
        report={'errors':[]}
        add_error(report,BrowserError('Page.goto: net::ERR_CONNECTION_RESET at https://a.test/?token=SECRET'),'199')
        row=report['errors'][0]
        self.assertEqual(row['reason'],'ERR_CONNECTION_RESET')
        self.assertEqual(row['category'],'transport')
        self.assertEqual(row['native'],'199')
        self.assertNotIn('SECRET',json.dumps(row))

    def test_nested_catalog_error_never_publishes_free_form_exception(self):
        report={'errors':[]}
        add_error(report,RuntimeError('Bearer SECRET https://a.test/?token=SECRET'),'new-id')
        self.assertNotIn('SECRET',json.dumps(report))

    def test_nested_parse_error_keeps_selector_and_match_count(self):
        report={'errors':[]}
        add_error(report,ParseError('missing_section',selector='article',matches=0),'new-id')
        row=report['errors'][0]
        self.assertEqual(row['selector'],'article');self.assertEqual(row['matches'],0)

    def test_connection_error_marker_not_classified_as_extraction(self):
        for code in ('ERR_CONNECTION_RESET','ERR_CONNECTION_CLOSED','ERR_CONNECTION_REFUSED','ERR_NETWORK_CHANGED','ERR_TIMED_OUT','ERR_CONNECTION_TIMED_OUT','ERR_NAME_NOT_RESOLVED'):
            with self.subTest(code=code):
                row=error_record(BrowserError('net::'+code+' at https://a.test/?token=SECRET'),'read')
                self.assertIn(row['category'],('transport','timeout'))
                self.assertNotIn('SECRET',json.dumps(row))

    def test_nested_http_error_keeps_fingerprint_not_body(self):
        report={'errors':[]}
        add_error(report,ReadError('http_503',status=503,body='PRIVATE CONTENT'),'199')
        row=report['errors'][0]
        self.assertEqual(row['http_status'],503)
        self.assertEqual(len(row['response_sha256']),64)
        self.assertNotIn('PRIVATE',json.dumps(row))

if __name__=='__main__':unittest.main()
