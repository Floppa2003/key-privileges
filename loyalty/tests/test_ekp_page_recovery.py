"""Bounded read-only page recovery never hides a gap or target restriction."""
import json
import sys
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).parents[1]))
import ekp_api_collect as c
import ekp_catalog as e
from free_access_probe import ProbeError
from test_ekp_api import FakeReader,NOW

class FlakyReader(FakeReader):
    def __init__(self,failures,total=245):
        super().__init__(total=total);self.failures=dict(failures);self.sleep=Mock()
    def read(self,url,body=None):
        offset=body['pagination']['offset'] if body else None
        if url==c.API and self.failures.get(offset,0):
            self.failures[offset]-=1;self.queries.append(body);self.calls+=1;self.reserved+=25
            raise ProbeError('provider_http_404')
        return super().read(url,body)

class PageRecoveryTests(unittest.TestCase):
    def test_transient_second_page_reaches_actual_end(self):
        r=FlakyReader({120:1})
        with tempfile.TemporaryDirectory() as tmp:
            b=c.collect(r,tmp,run_id='fixture:1',observed_at=NOW,commit='test')
            self.assertEqual(len(b['records']),245);self.assertEqual(b['sources'][0]['status'],'ok')
            self.assertEqual([q['pagination']['offset'] for q in r.queries],[0,120,120,240])
            self.assertEqual(r.reserved,125);r.sleep.assert_called_once_with(10)
            a=json.loads(Path(tmp,'report.json').read_text());self.assertEqual(a['page_retries'],1)

    def test_missing_middle_page_does_not_erase_or_block_later_page(self):
        r=FlakyReader({120:2})
        with tempfile.TemporaryDirectory() as tmp:
            stamp=datetime.now(timezone.utc).isoformat()
            b=c.collect(r,tmp,run_id='fixture:1',observed_at=stamp,commit='test')
            self.assertEqual(len(b['records']),125);self.assertEqual(b['sources'][0]['status'],'partial')
            self.assertEqual({x['details']['request']['pagination']['offset'] for x in b['records']},{0,240})
            self.assertEqual(b['sources'][0]['errors'],[{'phase':'page','offset':120,'reason':'provider_http_404'}])
            self.assertFalse(json.loads(b['sources'][0]['coverage'])['catalogue_pagination_complete'])
            self.assertEqual(e.validate_bundle(tmp,run_id='fixture:1',commit='test',clock=datetime.now(timezone.utc)),b)

    def test_first_page_still_requires_a_known_total_before_skipping(self):
        r=FlakyReader({0:3})
        with tempfile.TemporaryDirectory() as tmp:
            b=c.collect(r,tmp,run_id='fixture:1',observed_at=NOW,commit='test')
            self.assertFalse(b['records']);self.assertEqual(len(r.queries),2)
            self.assertEqual([q['pagination']['offset'] for q in r.queries],[0,0])

    def test_at_most_two_extra_query_attempts_in_entire_scan(self):
        r=FlakyReader({0:1,120:1,240:1},total=365)
        with tempfile.TemporaryDirectory() as tmp:
            b=c.collect(r,tmp,run_id='fixture:1',observed_at=NOW,commit='test')
            self.assertEqual(len(b['records']),245);self.assertEqual(r.sleep.call_count,2)
            self.assertEqual([q['pagination']['offset'] for q in r.queries],[0,0,120,120,240,360])
            self.assertEqual(json.loads(Path(tmp,'report.json').read_text())['missing_page_offsets'],[240])

    def test_two_extra_attempts_remain_within_original_credit_cap(self):
        r=FlakyReader({120:1,240:1},total=1046)
        with tempfile.TemporaryDirectory() as tmp:
            b=c.collect(r,tmp,run_id='fixture:1',observed_at=NOW,commit='test')
            self.assertEqual(len(b['records']),1046);self.assertEqual(r.calls,12);self.assertEqual(r.reserved,300)
            self.assertEqual(b['sources'][0]['status'],'ok')

    def test_source_refusal_challenge_or_quota_cannot_retry_or_advance(self):
        for code in ('provider_http_423','provider_auth_quota_or_rate_limit','ekp_origin_http_refusal',
                     'ekp_source_rate_limit','ekp_cost_contract_changed','ekp_weekly_budget_bound'):
            r=SimpleNamespace(read=Mock(side_effect=ProbeError(code)),sleep=Mock(),http=SimpleNamespace(halted=False))
            with self.subTest(code=code),self.assertRaises(ProbeError):c.read_page(r,e.query(120),{})
            r.read.assert_called_once_with(c.API,e.query(120));r.sleep.assert_not_called()

    def test_halted_reader_is_not_restarted_by_page_helper(self):
        r=SimpleNamespace(read=Mock(side_effect=ProbeError('provider_http_404')),sleep=Mock(),http=SimpleNamespace(halted=True))
        with self.assertRaises(ProbeError):c.read_page(r,e.query(0),{})
        self.assertEqual(r.read.call_count,1);r.sleep.assert_not_called()

    def test_successful_page_does_not_replay_or_delay(self):
        r=SimpleNamespace(read=Mock(return_value='public'),sleep=Mock())
        a={};self.assertEqual(c.read_page(r,e.query(120),a),'public')
        self.assertEqual(r.read.call_count,1);r.sleep.assert_not_called();self.assertNotIn('page_retries',a)

if __name__=='__main__':unittest.main()
