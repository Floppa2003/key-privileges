"""Regression for the actual Orca free_rate_limited response; no network."""
import json
import unittest
from unittest.mock import patch
import test_merchant_extract as fixtures

m=fixtures.m
Transport=fixtures.Transport
Response=fixtures.Response
Clock=fixtures.Clock
EMPTY=fixtures.EMPTY

class WorkspaceLimitTests(unittest.TestCase):
    setUp=fixtures.ManifestTests.setUp
    write=fixtures.ManifestTests.write
    def test_workspace_limit_preserves_success_and_defers_remaining_documents(self):
        import os
        self.write([self.spec, {**self.spec,'id':'b'}, {**self.spec,'id':'c'}])
        denied={'error':{'code':'free_rate_limited','metadata':{'reason':'err_free_rate','retry_after_seconds':25163},'type':'rate_limit_error'}}
        transport=Transport([Response(),Response(429,denied,{'Retry-After':'25163'}),Response()])
        transport.close=lambda:None
        out=self.root/'limited'
        with patch.dict(os.environ,{'ORCAROUTER_API_KEY':'TEST_API_SECRET'}), patch('merchant_extract.requests.Session',return_value=transport), patch('merchant_extract.time.sleep'):
            code=m.main(['--manifest',str(self.manifest),'--out',str(out),'--execute'])
        self.assertEqual(code,2)
        status=json.loads((out/'summary.json').read_text())
        self.assertEqual(status['completed'],1)
        self.assertEqual(status['not_attempted'],['c'])
        self.assertEqual(status['stop_reason'],'provider_rate_limited')
        self.assertEqual(len(transport.calls),2)
        self.assertEqual(json.loads((out/'a/direct/extracted.json').read_text()),EMPTY)


class RetryHintTests(unittest.TestCase):
    setUp=fixtures.DeepSeekTests.setUp
    infer=fixtures.DeepSeekTests.infer
    def test_orca_json_retry_hint_is_respected_without_a_header(self):
        denied={'error':{'code':'free_rate_limited','metadata':{'reason':'err_free_rate','retry_after_seconds':25163},'type':'rate_limit_error'}}
        clock=Clock();transport=Transport([Response(429,denied),Response()])
        result=self.infer(transport,clock)
        self.assertEqual(result['status'],'deferred')
        self.assertEqual(result.get('stop_batch_reason'),'provider_rate_limited')
        self.assertEqual(result.get('retry_after_seconds'),25163)
        self.assertEqual(len(transport.calls),1)
        self.assertEqual(clock.waits,[])

    def test_largest_retry_hint_wins_and_malformed_metadata_is_ignored(self):
        self.assertEqual(m.retry_delay({'Retry-After':'5'}, {'error':{'metadata':{'retry_after_seconds':25163}}}),25163)
        for value in (None, {}, 'nonsense', 'NaN', '-7'):
            self.assertEqual(m.retry_delay({'Retry-After':'5'},{'error':{'metadata':{'retry_after_seconds':value}}}),5)


if __name__=='__main__':unittest.main()
