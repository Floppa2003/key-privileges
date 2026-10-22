"""Error telemetry is actionable without publishing request secrets."""
import asyncio
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]))
from source_diagnostics import ParseError, ReadError, category, error_record, final_status
from test_recovered_sources import cfg, Response
from recovered_sources import ScopedReader
import requests
import time

class DiagnosticsTests(unittest.TestCase):
    def test_parse_code_and_selector_survive_without_response_text(self):
        row=error_record(ParseError('partner_content_selector_missing',selector='article.pf-post',matches=0),'parse','https://site.test/a?token=SECRET')
        self.assertEqual(row['reason'],'partner_content_selector_missing')
        self.assertEqual(row['selector'],'article.pf-post');self.assertEqual(row['matches'],0)
        self.assertEqual(row['path'],'/a');self.assertNotIn('SECRET',json.dumps(row))
    def test_arbitrary_exception_details_never_become_public_diagnostics(self):
        for exc in (RuntimeError('Bearer SECRET https://site.test/?token=SECRET'),ValueError('SECRET escaped value')):
            self.assertNotIn('SECRET',json.dumps(error_record(exc,'read')))
        self.assertEqual(error_record(ValueError('smartavia_plan_price_missing'),'parse')['reason'],'smartavia_plan_price_missing')
    def test_http_fingerprint_is_not_response_body(self):
        row=error_record(ReadError('http_403',status=403,body='PRIVATE TOKEN'),'read')
        self.assertEqual(row['http_status'],403);self.assertEqual(row['response_bytes'],13)
        self.assertEqual(len(row['response_sha256']),64);self.assertNotIn('PRIVATE',json.dumps(row))
    def test_network_and_tls_are_not_parser_errors(self):
        for reason,expected in [('source_connection_failed','transport'),('source_timeout','timeout'),('ERR_CERT_AUTHORITY_INVALID','tls_verification'),('http_403','access_denied'),('robots_not_readable','robots_unavailable'),('authentication_redirect','authentication_required')]:
            with self.subTest(reason=reason):self.assertEqual(category(reason),expected)
    def test_status_reflects_actual_successful_results(self):
        self.assertEqual(final_status([],['error']),'failed')
        self.assertEqual(final_status([{}],['error']),'partial')
        self.assertEqual(final_status([{}],[]),'ok')

class ScopedRetryTests(unittest.TestCase):
    def reader(self):return ScopedReader(cfg('loyals'),{},time.monotonic()+90)
    def test_transient_connection_uses_same_url_session_and_tls(self):
        r=self.reader()
        with patch('recovered_sources.time.sleep'),patch.object(r.session,'get',side_effect=[requests.ConnectionError('SECRET'),Response()]) as get:
            self.assertEqual(r._get(cfg('loyals')['url'])[0],200)
            self.assertEqual(get.call_count,2)
            self.assertEqual(get.call_args_list[0],get.call_args_list[1])
        r.__exit__()
    def test_exhausted_timeout_keeps_type_not_secret(self):
        r=self.reader()
        with patch('recovered_sources.time.sleep'),patch.object(r.session,'get',side_effect=requests.ReadTimeout('SECRET')) as get:
            with self.assertRaises(ReadError) as caught:r._get(cfg('loyals')['url'])
            self.assertEqual(get.call_count,3)
            row=error_record(caught.exception,'read');self.assertEqual(row['upstream_error_type'],'ReadTimeout')
            self.assertNotIn('SECRET',json.dumps(row))
        r.__exit__()
    def test_access_refusal_is_not_retried(self):
        r=self.reader()
        with patch('recovered_sources.time.sleep'),patch.object(r.session,'get',return_value=Response(403)) as get:
            self.assertEqual(r._get(cfg('loyals')['url'])[0],403);self.assertEqual(get.call_count,1)
        r.__exit__()

class CollectorStatusTests(unittest.IsolatedAsyncioTestCase):
    async def test_caught_region_errors_with_zero_rows_is_failed(self):
        import collect_normalized as collect
        class Client:
            policy=True;robots_info={}
            def __init__(self,*args):pass
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
        async def region_fail(client,cfg,report,now,limit):
            report['errors'].extend([{'reason':'http_403','phase':'region'}]*2)
            return []
        config={'id':'mir','name':'Mir','url':'https://vamprivet.ru/','mode':'mir'}
        with patch.object(collect,'PublicSource',Client),patch.object(collect,'collect_mir',region_fail),contextlib.redirect_stdout(io.StringIO()):
            report,rows=await collect.one(None,config,'2026-10-22T12:00:00+00:00',500)
        self.assertEqual(rows,[]);self.assertEqual(report['status'],'failed');self.assertEqual(report['failed'],2)
