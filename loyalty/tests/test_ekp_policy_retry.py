"""A single policy-route retry must not generalize into an access bypass."""
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).parents[1]))
import ekp_api_collect as c
from free_access_probe import ProbeError
from test_ekp_api import FakeReader,NOW

RULES='User-agent: *\nAllow: /'

class PolicyRetryTests(unittest.TestCase):
    def reader(self,values,halted=False):
        return SimpleNamespace(read=Mock(side_effect=values),sleep=Mock(),http=SimpleNamespace(halted=halted))

    def test_success_has_one_request_without_retry_delay(self):
        r=self.reader([RULES]);a={}
        self.assertEqual(c.read_policy(r,a),RULES)
        r.read.assert_called_once_with(c.POLICY);r.sleep.assert_not_called()
        self.assertEqual(len(a['policy_attempts']),1)

    def test_one_documented_unreachable_route_retry(self):
        r=self.reader([ProbeError('provider_http_404'),RULES]);a={}
        self.assertEqual(c.read_policy(r,a),RULES)
        self.assertEqual(r.read.call_count,2);r.sleep.assert_called_once_with(10)
        self.assertEqual(a['policy_attempts'][0]['error'],'provider_http_404')
        self.assertEqual(a['policy_attempts'][1]['result'],'source_document_received')

    def test_second_unreachable_route_is_terminal(self):
        r=self.reader([ProbeError('provider_http_404'),ProbeError('provider_http_404'),RULES]);a={}
        with self.assertRaises(ProbeError):c.read_policy(r,a)
        self.assertEqual(r.read.call_count,2);r.sleep.assert_called_once_with(10)
        self.assertEqual(len(a['policy_attempts']),2)

    def test_refusals_challenges_quota_and_unknown_errors_never_retry(self):
        for error in ('provider_http_403','provider_http_423','provider_http_429','provider_http_500',
                      'provider_auth_quota_or_rate_limit','ekp_origin_http_refusal','ekp_source_rate_limit',
                      'ekp_cost_contract_changed','ekp_weekly_budget_bound'):
            r=self.reader([ProbeError(error),RULES])
            with self.subTest(error=error),self.assertRaises(ProbeError):c.read_policy(r,{})
            self.assertEqual(r.read.call_count,1);r.sleep.assert_not_called()

    def test_already_halted_reader_cannot_restart(self):
        r=self.reader([ProbeError('provider_http_404'),RULES],halted=True)
        with self.assertRaises(ProbeError):c.read_policy(r,{})
        self.assertEqual(r.read.call_count,1);r.sleep.assert_not_called()

    def test_source_policy_parse_error_is_not_a_provider_retry(self):
        r=self.reader([RuntimeError('robots_not_readable'),RULES])
        with self.assertRaises(RuntimeError):c.read_policy(r,{})
        self.assertEqual(r.read.call_count,1);r.sleep.assert_not_called()

    def test_actual_transport_counts_both_attempts_in_same_budget(self):
        from test_free_access_probe import Response,page,USAGE
        get=Mock(side_effect=[Response(USAGE),Response('{}',status=404),page(RULES,cost='25')])
        r=c.Reader('fixture-key',get=get,post=Mock(),sleep=Mock());r.preflight()
        self.assertEqual(c.read_policy(r,{}),RULES)
        self.assertEqual(r.calls,2);self.assertEqual(r.reserved,50);self.assertEqual(r.charged,25)
        r.sleep.assert_any_call(10)

    def test_actual_collector_keeps_total_budget_with_policy_retry(self):
        class Once(FakeReader):
            def __init__(self):super().__init__(total=1046);self.fail=True;self.sleep=Mock()
            def read(self,url,body=None):
                if url==c.POLICY and self.fail:
                    self.fail=False;self.calls+=1;self.reserved+=25
                    raise ProbeError('provider_http_404')
                return super().read(url,body)
        r=Once()
        with tempfile.TemporaryDirectory() as tmp:
            b=c.collect(r,tmp,run_id='fixture:1',observed_at=NOW,commit='test')
            self.assertEqual(len(b['records']),1046);self.assertEqual(b['sources'][0]['status'],'ok')
            self.assertEqual(r.calls,11);self.assertEqual(r.reserved,275)
            r.sleep.assert_called_once_with(10)

    def test_catalogue404_has_separate_bounded_query_retry(self):
        class ApiFailure(FakeReader):
            def __init__(self):super().__init__(total=1);self.sleep=Mock()
            def read(self,url,body=None):
                if url==c.API:
                    self.queries.append(body);self.calls+=1;self.reserved+=25
                    raise ProbeError('provider_http_404')
                return super().read(url,body)
        r=ApiFailure()
        with tempfile.TemporaryDirectory() as tmp:
            b=c.collect(r,tmp,run_id='fixture:1',observed_at=NOW,commit='test')
            self.assertFalse(b['records']);self.assertEqual(len(r.queries),2);r.sleep.assert_called_once_with(10)

if __name__=='__main__':unittest.main()
