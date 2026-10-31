"""Boundary regressions for malformed vendor replies and the manual pool cap."""
import copy
import unittest
import test_merchant_channels as f


class ChannelBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.context = f.ChannelTests()
        self.context.setUp()
        self.addCleanup(self.context.doCleanups)

    def test_malformed_google_envelope_is_a_document_failure_not_queue_crash(self):
        for index, change in enumerate((
            {'candidates': [17]},
            {'candidates': [{'finishReason': 'STOP', 'content': None}]},
            {'candidates': [{'finishReason': 'STOP', 'content': {'parts': 'bad'}}]},
            {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': 17}]}}]},
            {'usageMetadata': ['wrong shape']},
        )):
            with self.subTest(change=change):
                data=f.native().json();data.update(change)
                result=self.context.call('gemini',f.HTTP([f.Response(data)]),str(index))
                self.assertEqual(result['status'],'failed_validation')
                self.assertEqual(result['http_attempts'],1)

    def test_manual_cap_processes_different_documents_on_each_channel(self):
        c=self.context
        result=f.q.process_pool([c.doc('a'),c.doc('b')],c.state,c.state_path,c.root/'pool',
            {'experiential':'TEST_SECRET','kilo':'TEST_SECRET'},f.SCHEMA,'prompt',
            providers=('experiential','kilo'),per_provider_requests=1,max_requests=2,
            sessions={'experiential':f.HTTP([f.answer('deepseek-v4.1-flash')]),
                      'kilo':f.HTTP([f.answer(f.MODELS['kilo'])])},now=c.clock.now,sleep=c.clock.sleep)
        self.assertEqual(result['completed'],2)
        self.assertEqual(result['http_attempts'],2)
        self.assertEqual([p['http_attempts'] for p in result['providers']],[1,1])
        saved=f.q.read_state(c.state_path)
        self.assertEqual(saved['items']['a']['inferred_provider'],'experiential')
        self.assertEqual(saved['items']['b']['inferred_provider'],'kilo')

    def test_price_exceeding_reservation_cannot_start_a_credit_call(self):
        class InflatedPrice(f.HTTP):
            def get(self,url,**kwargs):
                response=super().get(url,**kwargs)
                if url.endswith('/models'):
                    data=response.json();data['data'][0]['pricing']['input']='1'
                    return f.Response(data)
                return response
        http=InflatedPrice([])
        result=self.context.call('vercel',http)
        self.assertEqual(result['http_attempts'],0)
        self.assertEqual(result['stop_batch_reason'],'free_credit_budget_unavailable')
        self.assertEqual(http.calls,[])


if __name__=='__main__':unittest.main()
