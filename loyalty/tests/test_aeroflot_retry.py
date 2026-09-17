"""Transient import recovery must not turn identity/auth failures into retries."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from datetime import datetime
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import aeroflot_import_collect as c
import aeroflot_import_catalog as m
from test_aeroflot_import import Clock, SourceReader, NOW


class RecoveryTests(unittest.TestCase):
    def reader(self, outcomes, *, cleanup=True, calls=1, elapsed=0):
        clock = Clock(); clock.value = elapsed
        reader = object.__new__(c.ImportReader)
        reader.clock = clock.now; reader.sleep = clock.sleep
        reader.started = 0; reader.calls = calls
        reader.cleanup_verified = cleanup; reader.retry_events = []
        reader._read_once = Mock(side_effect=outcomes)
        return reader, clock

    def test_transient_failure_retries_exact_target_once(self):
        expected = {'source': 'new response, not a cached row'}
        reader, clock = self.reader([ValueError('af_import_error_cell'), expected])
        self.assertEqual(reader.read(m.detail_url(71), 'detail'), expected)
        self.assertEqual(reader._read_once.call_count, 2)
        self.assertEqual(reader._read_once.call_args_list[0], reader._read_once.call_args_list[1])
        self.assertEqual(clock.value, 30)
        self.assertEqual(reader.retry_events[0]['result'], 'recovered')

    def test_timeout_can_recover_but_second_failure_stays_failure(self):
        reader, clock = self.reader([ValueError('af_import_calculation_timeout'), ValueError('af_import_error_cell')])
        with self.assertRaisesRegex(ValueError, 'af_import_error_cell'):
            reader.read(m.detail_url(71), 'detail')
        self.assertEqual(reader._read_once.call_count, 2)
        self.assertEqual(reader.retry_events[0]['result'], 'failed')

    def test_identity_policy_and_quota_failures_are_not_retried(self):
        for error in (ValueError('af_formula_readback'), ValueError('af_workspace_generation'),
                      ValueError('af_collection_bound'), RuntimeError('Google Sheets HTTP 429')):
            reader, clock = self.reader([error, {'wrong': 'must not be read'}])
            with self.assertRaises(type(error)): reader.read(m.detail_url(71), 'detail')
            self.assertEqual(reader._read_once.call_count, 1)
            self.assertEqual(clock.value, 0)
            self.assertFalse(reader.retry_events)

    def test_uncleared_staging_or_exhausted_budgets_stop(self):
        for params in ({'cleanup': False}, {'calls': c.MAX_READS}, {'elapsed': c.MAX_SECONDS - 100}):
            reader, _ = self.reader([ValueError('af_import_error_cell'), {}], **params)
            with self.assertRaises(ValueError): reader.read(m.detail_url(71), 'detail')
            self.assertEqual(reader._read_once.call_count, 1)
            self.assertFalse(reader.retry_events)

    def test_catalogue_and_policy_errors_do_not_trigger_detail_retries(self):
        for url, kind in ((m.ROBOTS, 'robots'), (m.CATALOG, 'catalog'), (m.ROOT, 'discovery')):
            reader, _ = self.reader([ValueError('af_import_error_cell'), {}])
            with self.assertRaises(ValueError): reader.read(url, kind)
            self.assertEqual(reader._read_once.call_count, 1)

    def test_global_retry_ceiling(self):
        reader, _ = self.reader([ValueError('af_import_error_cell'), {}])
        reader.retry_events = [{}] * 12
        with self.assertRaises(ValueError): reader.read(m.detail_url(71), 'detail')
        self.assertEqual(reader._read_once.call_count, 1)

    def test_airline_retry_preserves_endpoint_and_type(self):
        import aeroflot_airlines as airlines
        reader, _ = self.reader([ValueError('af_import_error_cell'), {'fresh': True}])
        self.assertEqual(reader.read(airlines.detail_url(901), 'airline_detail'), {'fresh': True})
        self.assertEqual(reader.retry_events[0]['url'], airlines.detail_url(901))
        self.assertEqual(reader.retry_events[0]['kind'], 'airline_detail')

    def test_success_does_not_retry_or_change_response(self):
        response = {'unchanged': [1, 2, 3]}
        reader, clock = self.reader([response])
        self.assertIs(reader.read(m.detail_url(71), 'detail'), response)
        self.assertEqual(reader._read_once.call_count, 1)
        self.assertEqual(clock.value, 0)
        self.assertFalse(reader.retry_events)

    def test_retry_audit_cannot_claim_foreign_or_unobserved_recovery(self):
        reader = SourceReader(); bundle = c.walk(reader, '123:1', NOW)
        audit = {'run_id':'123:1','commit':'a'*40,'cleanup_verified':True,'started_at':NOW,'finished_at':NOW,
                 'source_accounts_used':False,'scrapingant_credits':0,'permission_basis':m.PERMISSION,
                 'permission_email_independently_read':False,'observations':reader.observations}
        bad = {'url':m.detail_url(999),'kind':'detail','first_error':'af_import_error_cell',
               'wait_seconds':30,'result':'recovered','started_at':NOW,'finished_at':NOW}
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder); (p/'normalized.json').write_text(json.dumps(bundle))
            for event in (bad, {**bad,'url':m.detail_url(71),'first_error':'af_formula_readback'}):
                (p/'evidence.json').write_text(json.dumps({**audit,'detail_retries':[event]}))
                with self.assertRaises(ValueError):
                    c.validate_bundle(p,run_id='123:1',commit='a'*40,clock=datetime.fromisoformat(NOW))

class RetryAuditTests(unittest.TestCase):
    def test_valid_recovery_and_failure_receipts(self):
        start=datetime.fromisoformat(NOW)
        obs={'url':m.detail_url(71),'kind':'detail','requested_at':NOW,'calculated_at':NOW}
        event={'url':obs['url'],'kind':'detail','first_error':'af_import_error_cell',
               'wait_seconds':30,'result':'recovered','started_at':NOW,'finished_at':NOW}
        c.validate_retries({'detail_retries':[event],'import_requests':2},[obs],{71:{}},{},start,start)
        failed={**event,'result':'failed','final_error':'af_import_error_cell'}
        c.validate_retries({'detail_retries':[failed],'import_requests':2},[],{71:{}},{},start,start)

    def test_repeated_receipts_and_false_request_counts_are_rejected(self):
        start=datetime.fromisoformat(NOW)
        obs={'url':m.detail_url(71),'kind':'detail','requested_at':NOW,'calculated_at':NOW}
        event={'url':obs['url'],'kind':'detail','first_error':'af_import_error_cell',
               'wait_seconds':30,'result':'recovered','started_at':NOW,'finished_at':NOW}
        for audit in ({'detail_retries':[event,event]}, {'detail_retries':[event],'import_requests':1},
                      {'detail_retries':[event],'import_requests':c.MAX_READS+1},
                      {'detail_retries':[{**event,'result':'failed','final_error':'af_import_error_cell'}]}):
            with self.assertRaises(ValueError): c.validate_retries(audit,[obs],{71:{}},{},start,start)

    def test_one_target_cannot_be_retried_twice(self):
        reader, _ = RecoveryTests().reader([ValueError('af_import_error_cell'), {}])
        reader.retry_events=[{'url':m.detail_url(71)}]
        with self.assertRaises(ValueError): reader.read(m.detail_url(71),'detail')
        self.assertEqual(reader._read_once.call_count,1)

if __name__ == '__main__': unittest.main()
