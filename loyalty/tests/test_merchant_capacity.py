"""Independent free-provider capacity, shared evidence cache and durable accounting."""
import base64
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import merchant_extract as m
import merchant_queue as q

SCHEMA = {'type': 'object', 'properties': {'has_offer': {'type':'boolean'}, 'offers': {'type':'array'}, 'unknowns': {'type':'array'}}, 'required':['has_offer','offers','unknowns']}
EMPTY = {'has_offer': False, 'offers': [], 'unknowns': []}

class Response:
    def __init__(self, status=200, data=None, headers=None):
        self.status_code = status
        if data is None:
            data = {'model':'deepseek-v4.1-flash', 'choices':[{'finish_reason':'stop', 'message':{'content':json.dumps(EMPTY)}}], 'usage':{'cost':0}}
        self.content = json.dumps(data).encode()
        self.headers = headers or {}

class HTTP:
    def __init__(self, responses): self.responses=list(responses); self.calls=[]
    def post(self, url, **kwargs):
        self.calls.append((url,kwargs))
        value=self.responses.pop(0)
        if isinstance(value, Exception): raise value
        return value

class Clock:
    def __init__(self): self.t=1792886700
    def now(self): return self.t
    def sleep(self,t): self.t+=t

class CapacityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.state=q.new_state(); self.clock=Clock()
        self.path=self.root/'state.json'
        b=io.BytesIO(); Image.new('RGB',(2,2)).save(b,format='PNG'); self.png=b.getvalue()

    def doc(self,ident='a'):
        return {'id':ident, 'target':{'partner':ident,'program':'P','as_of':'2026-10-25'}, 'text':'10%', 'images':[self.png], 'source':{'source_url':'https://example.org/'+ident}}

    def pool(self,docs,orca,harbor,**kwargs):
        sessions={'orcarouter':HTTP(orca),'tokenharbor':HTTP(harbor)}
        out=self.root/('run-'+str(len(list(self.root.glob('run-*')))))
        keys=kwargs.pop('keys',{'orcarouter':'ORCA_TEST_KEY','tokenharbor':'HARBOR_TEST_KEY'})
        result=q.process_pool(docs,self.state,self.path,out,keys,SCHEMA,'prompt',
            sessions=sessions,now=self.clock.now,sleep=self.clock.sleep,**kwargs)
        self.state=q.read_state(self.path)
        return result,sessions

    def test_harbor_uses_its_own_free_id_endpoint_and_complete_input(self):
        d=self.doc()
        p=m.build_request(d['target'],d['text'],d['images'],SCHEMA,'prompt',provider='tokenharbor')
        self.assertEqual(p['model'],'deepseek-v4.1-flash:free')
        self.assertEqual(p['max_tokens'], 16384)
        self.assertNotIn('reasoning',p) # Mirror the previously live-tested Harbor request.
        self.assertNotIn('tools',p); self.assertNotIn('web_search_options',p)
        self.assertIn('10%',p['messages'][1]['content'][0]['text'])
        self.assertEqual(p['messages'][1]['content'][1]['image_url']['url'], 'data:image/png;base64,'+base64.b64encode(self.png).decode())
        http=HTTP([Response()])
        r=m.infer(p,SCHEMA,self.root/'harbor','HARBOR_TEST_KEY',provider='tokenharbor',session=http)
        self.assertEqual(r['status'],'completed')
        self.assertGreater(http.calls[0][1]['timeout'][1], 90)
        self.assertEqual(http.calls[0][0],'https://tokenharbor.ai/v1/chat/completions')
        self.assertEqual(http.calls[0][1]['headers']['Authorization'],'Bearer HARBOR_TEST_KEY')

    def test_paid_id_cannot_be_sent_to_harbor(self):
        with self.assertRaises(ValueError):
            m.infer({'model':'deepseek-v4.1-flash','messages':[]},SCHEMA,self.root/'bad','K',provider='tokenharbor',session=HTTP([]))

    def test_existing_orca_daily_cap_and_cooldown_do_not_block_harbor(self):
        self.state['usage']={'date':'2026-10-25','attempts':50}
        self.state['provider_not_before']=self.clock.now()+10000
        r,s=self.pool([self.doc()],[],[Response()])
        self.assertEqual(r['completed'],1)
        self.assertEqual(len(s['orcarouter'].calls),0)
        self.assertEqual(self.state['usage']['attempts'],50)
        self.assertEqual(self.state['providers']['tokenharbor']['usage']['attempts'],1)

    def test_real_429_defers_only_that_provider_and_routes_unfinished_documents(self):
        error={'error':{'code':'free_rate_limited','metadata':{'reason':'err_free_rate','retry_after_seconds':3600}}}
        r,s=self.pool([self.doc('a'),self.doc('b')],[Response(429,error)],[Response(),Response()])
        self.assertEqual(r['completed'],2); self.assertEqual(r['http_attempts'],3)
        self.assertEqual(len(s['orcarouter'].calls),1)
        self.assertGreater(self.state['provider_not_before'],self.clock.now())
        self.assertEqual(self.state['providers']['tokenharbor']['provider_not_before'],0)
        self.assertEqual(self.state['items']['a']['inferred_provider'],'tokenharbor')

    def test_successful_orca_document_is_not_repeated_on_harbor(self):
        r,s=self.pool([self.doc()],[Response()],[])
        self.assertEqual(r['completed'],1); self.assertEqual(len(s['tokenharbor'].calls),0)

    def test_harbor_output_is_reused_next_run_even_when_orca_is_available(self):
        self.state['provider_not_before']=self.clock.now()+10000
        self.pool([self.doc()],[],[Response()])
        self.clock.t+=10001
        r,s=self.pool([self.doc()],[],[])
        self.assertEqual(r['cached'],1)
        self.assertEqual(r['http_attempts'],0)

    def test_harbor_quota_respects_retry_after_without_inventing_midnight_reset(self):
        self.state['provider_not_before']=self.clock.now()+1000000
        error={'error':{'code':'free_allowance_exhausted'}}
        r,s=self.pool([self.doc('a'),self.doc('b')],[],[Response(429,error,{'Retry-After':'604800'})])
        self.assertEqual(len(s['tokenharbor'].calls),1)
        self.assertGreaterEqual(self.state['providers']['tokenharbor']['provider_not_before'],self.clock.now()+604800)
        r,s=self.pool([self.doc('a')],[],[])
        self.assertEqual(r['http_attempts'],0)

    def test_total_run_limit_is_shared_not_reset_per_provider(self):
        error={'error':{'code':'free_rate_limited','metadata':{'retry_after_seconds':3600}}}
        r,s=self.pool([self.doc()],[Response(429,error)],[],max_requests=1)
        self.assertEqual(r['http_attempts'],1); self.assertEqual(len(s['tokenharbor'].calls),0)

    def test_missing_optional_key_does_not_block_existing_provider(self):
        r,s=self.pool([self.doc()],[Response()],[],keys={'orcarouter':'ORCA_TEST_KEY'})
        self.assertEqual(r['completed'],1)

    def test_missing_primary_key_still_allows_harbor(self):
        r,s=self.pool([self.doc()],[],[Response()],keys={'tokenharbor':'HARBOR_TEST_KEY'})
        self.assertEqual(r['completed'],1)

    def test_no_credentials_has_explicit_result_without_provider_call(self):
        r,s=self.pool([self.doc()],[],[],keys={})
        self.assertEqual(r['status'],'unavailable'); self.assertEqual(r['http_attempts'],0)

    def test_cost_anomaly_halts_pool_but_preserves_valid_result(self):
        data=json.loads(Response().content);data['usage']={'cost_usd':0.1}
        r,s=self.pool([self.doc('a'),self.doc('b')],[Response(data=data)],[])
        self.assertEqual(r['completed'],1)
        self.assertEqual(r['stop_reason'],'nonzero_reported_cost')
        self.assertEqual(len(s['tokenharbor'].calls),0)
        self.assertEqual(self.state['items']['a']['extracted'],EMPTY)

    def test_invalid_model_answer_is_not_regenerated_on_second_provider(self):
        data=json.loads(Response().content);data['choices'][0]['finish_reason']='length'
        r,s=self.pool([self.doc('a')],[Response(data=data)],[])
        self.assertEqual(r['completed'],0)
        self.assertEqual(len(s['tokenharbor'].calls),0)
        self.assertIn('a',r['pending'])

    def test_input_size_rejection_can_use_other_provider_without_truncation(self):
        error={'error':{'code':'free_rate_limited','metadata':{'reason':'err_free_prompt_cap','retryable':False}}}
        r,s=self.pool([self.doc()],[Response(400,error)],[Response()])
        self.assertEqual(r['completed'],1)
        p1=json.loads(s['orcarouter'].calls[0][1]['data'])
        p2=json.loads(s['tokenharbor'].calls[0][1]['data'])
        self.assertEqual(p1['messages'],p2['messages'])

    def test_capture_can_continue_when_only_harbor_is_eligible(self):
        self.state['provider_not_before']=self.clock.now()+100000
        self.assertFalse(q.provider_eligible(self.state,'orcarouter',self.clock.now()))
        self.assertTrue(q.provider_eligible(self.state,'tokenharbor',self.clock.now()))

    def test_original_state_roundtrip_preserves_history(self):
        self.state['items']['old']={'extracted':EMPTY,'fingerprint':'old','target':{'id':'old'}}
        self.state['usage']={'date':'2026-10-25','attempts':50}
        self.pool([self.doc()],[],[Response()])
        self.assertEqual(self.state['items']['old']['fingerprint'],'old')
        self.assertEqual(self.state['usage']['attempts'],50)

if __name__=='__main__': unittest.main()
