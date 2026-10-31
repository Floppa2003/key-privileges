"""Confirmed routes: real extraction/queue code, HTTP is the only external double."""
import base64
import copy
from datetime import datetime, timezone
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

SCHEMA = {'type':'object','properties':{'has_offer':{'type':'boolean'},'offers':{'type':'array'},'unknowns':{'type':'array'}},'required':['has_offer','offers','unknowns']}
EMPTY = {'has_offer':False,'offers':[],'unknowns':[]}
MODELS = {'experiential':'deepseek-v4.1-flash:free','kilo':'nvidia/nemotron-3.5-super-vl:free','openrouter':'nvidia/nemotron-3.5-super-vl:free','vercel':'nvidia/nemotron-3.5-super-vl','gemini':'gemini-3.8-flash'}

class Response:
    def __init__(self, data, status=200, headers=None):
        self.content=json.dumps(data).encode(); self.status_code=status; self.headers=headers or {}
    def json(self): return json.loads(self.content)


def answer(model, cost=0, usage=None):
    return Response({'model':model,'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(EMPTY)}}], 'usage':usage or {'cost':cost,'prompt_tokens':100,'completion_tokens':200,'total_tokens':300}})


def native():
    return Response({'modelVersion':'gemini-3.8-flash','candidates':[{'finishReason':'STOP','content':{'role':'model','parts':[{'text':'private thought','thought':True},{'text':json.dumps(EMPTY)}]}}], 'usageMetadata':{'promptTokenCount':100,'candidatesTokenCount':20,'thoughtsTokenCount':30,'totalTokenCount':150}})

class HTTP:
    def __init__(self, responses, balance='5', pricing=True):
        self.responses=list(responses); self.calls=[]; self.reads=[]; self.balance=balance; self.pricing=pricing
    def post(self,url,**kwargs):
        self.calls.append((url,kwargs))
        value=self.responses.pop(0)
        if isinstance(value,Exception): raise value
        return value
    def get(self,url,**kwargs):
        self.reads.append((url,kwargs))
        if url.endswith('/credits'): return Response({'balance':self.balance,'total_used':'0'})
        if url.endswith('/models'):
            return Response({'data':[{'id':'nvidia/nemotron-3.5-super-vl','context_window':1048576,'pricing':{'input':'0.0000002','output':'0.0000005'}}] if self.pricing else []})
        raise AssertionError('Unexpected GET '+url)

class Clock:
    def __init__(self):self.t=1793448000.;self.waits=[]
    def now(self):return self.t
    def sleep(self,s):self.waits.append(s);self.t+=s

class ChannelTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.state_path=self.root/'state.json';self.clock=Clock();self.state=q.new_state()
        b=io.BytesIO();Image.new('RGB',(2,2)).save(b,format='PNG');self.png=b.getvalue()
    def require(self,provider):self.assertIn(provider,m.PROVIDERS,'approved channel is not registered')
    def doc(self,ident='a'):
        return {'id':ident,'target':{'partner':ident,'program':'P','as_of':'2026-10-31'},'text':'Полный исходный текст','images':[self.png,self.png],'source':{'source_url':'https://example.org/'+ident}}
    def call(self,provider,http,ident='a'):
        self.require(provider)
        payload=m.build_request(self.doc()['target'],self.doc()['text'],self.doc()['images'],SCHEMA,'prompt',provider=provider)
        result=m.infer(payload,SCHEMA,self.root/ident,'TEST_SECRET',session=http,sleep=self.clock.sleep,monotonic=self.clock.now,max_attempts=1,provider=provider)
        return result
    def batch(self,provider,http,ids=('a',),state=None,out='batch'):
        self.require(provider)
        return q.process_documents([self.doc(i) for i in ids],self.state if state is None else state,self.state_path,self.root/out,'TEST_SECRET',SCHEMA,'prompt',provider=provider,session=http,now=self.clock.now,sleep=self.clock.sleep,max_requests=10)

    def test_approved_routes_send_full_text_all_images_and_no_tools(self):
        for provider,model in MODELS.items():
            with self.subTest(provider=provider):
                self.require(provider)
                http=HTTP([native() if provider=='gemini' else answer(model)])
                result=self.call(provider,http,provider)
                self.assertEqual(result['status'],'completed')
                url,kw=http.calls[0];body=json.loads(kw['data'])
                self.assertNotIn('TEST_SECRET',url);self.assertNotIn('TEST_SECRET',kw['data'].decode())
                self.assertNotIn('tools',body);self.assertNotIn('plugins',body)
                if provider=='gemini':
                    self.assertEqual(kw['headers']['x-goog-api-key'],'TEST_SECRET')
                    self.assertNotIn('Authorization',kw['headers'])
                    parts=body['contents'][0]['parts']
                    self.assertEqual([x['inlineData']['data'] for x in parts if 'inlineData' in x],[base64.b64encode(self.png).decode()]*2)
                    self.assertIn('Полный исходный текст',parts[0]['text'])
                else:
                    self.assertEqual(body['model'],model)
                    parts=body['messages'][1]['content'];self.assertEqual(len(parts),3)
                    self.assertIn('Полный исходный текст',parts[0]['text'])
                    self.assertEqual(base64.b64decode(parts[1]['image_url']['url'].split(',')[1]),self.png)
                self.assertEqual(json.loads((self.root/provider/'extracted.json').read_text()),EMPTY)

    def test_route_mismatch_rejects_nano_and_wrong_family(self):
        for provider,wrong in [('kilo','nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free'),('experiential','glm-5.3'),('vercel','deepseek-v4.1-flash')]:
            with self.subTest(provider=provider):
                result=self.call(provider,HTTP([answer(wrong)]),provider)
                self.assertEqual(result['status'],'failed_validation')
                self.assertEqual(result['error'],'returned_model_mismatch')

    def test_gemini_keeps_only_final_text_and_accounts_thoughts_once(self):
        result=self.call('gemini',HTTP([native()]))
        self.assertEqual(result['usage']['total_tokens'],150)
        self.assertEqual(result['usage']['completion_tokens'],50)
        self.assertEqual(json.loads((self.root/'a/extracted.json').read_text()),EMPTY)

    def test_gemini_function_call_is_not_accepted_as_an_answer(self):
        data=native().json();data['candidates'][0]['content']['parts'].append({'functionCall':{'name':'search','args':{}}})
        result=self.call('gemini',HTTP([Response(data)]))
        self.assertEqual(result['status'],'failed_validation')

    def test_free_route_billing_anomaly_stops_without_losing_valid_json(self):
        result=self.call('openrouter',HTTP([answer(MODELS['openrouter'],cost=0.1)]))
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['stop_batch_reason'],'nonzero_reported_cost')

    def test_vercel_nonzero_cost_is_allowed_only_under_free_credit_guard(self):
        http=HTTP([answer(MODELS['vercel'],cost=0.0013669)])
        result=self.call('vercel',http)
        self.assertEqual(result['status'],'completed')
        self.assertNotIn('stop_batch_reason',result)
        self.assertTrue(any(url.endswith('/credits') for url,_ in http.reads))
        self.assertEqual(result['usage']['cost'],0.0013669)

    def test_vercel_insufficient_balance_does_not_send_generation(self):
        http=HTTP([],balance='0.10');result=self.call('vercel',http)
        self.assertEqual(result['http_attempts'],0);self.assertEqual(http.calls,[])
        self.assertEqual(result['stop_batch_reason'],'free_credit_budget_unavailable')

    def test_vercel_unknown_pricing_does_not_send_generation(self):
        http=HTTP([],pricing=False);result=self.call('vercel',http)
        self.assertEqual(http.calls,[]);self.assertEqual(result['http_attempts'],0)
        self.assertEqual(result['stop_batch_reason'],'free_credit_budget_unavailable')

    def test_vercel_monthly_reservation_survives_timeout_and_restart(self):
        import requests
        self.require('vercel')
        result=self.batch('vercel',HTTP([requests.ReadTimeout()]))
        stored=q.read_state(self.state_path);ledger=q.provider_state(stored,'vercel')
        self.assertGreaterEqual(ledger['credit_usage']['reserved_usd'],0.25)
        ledger['credit_usage']['reserved_usd']=4.50
        next_result=self.batch('vercel',HTTP([]),ids=('b',),state=stored,out='again')
        self.assertEqual(next_result['http_attempts'],0)
        self.assertIn('b',next_result['not_attempted'])

    def test_completed_credit_response_settles_only_its_reservation(self):
        self.require('vercel')
        result=self.batch('vercel',HTTP([answer(MODELS['vercel'],cost=0.0013669)]))
        ledger=q.provider_state(q.read_state(self.state_path),'vercel')
        self.assertEqual(result['completed'],1)
        self.assertAlmostEqual(ledger['credit_usage']['reserved_usd'],0.0013669)

    def test_one_provider_quota_does_not_stop_independent_channel(self):
        self.require('experiential');self.require('kilo')
        denied=Response({'error':{'code':'rate_limited','metadata':{'retry_after_seconds':86400}}},429,{'Retry-After':'86400'})
        result=q.process_pool([self.doc()],self.state,self.state_path,self.root/'pool',{'experiential':'TEST_SECRET','kilo':'TEST_SECRET'},SCHEMA,'prompt',providers=('experiential','kilo'),sessions={'experiential':HTTP([denied]),'kilo':HTTP([answer(MODELS['kilo'])])},now=self.clock.now,sleep=self.clock.sleep,max_requests=10)
        self.assertEqual(result['completed'],1)
        stored=q.read_state(self.state_path)
        self.assertEqual(stored['items']['a']['inferred_provider'],'kilo')
        self.assertGreater(q.provider_state(stored,'experiential')['provider_not_before'],self.clock.now())

    def test_same_evidence_cache_survives_provider_pool_expansion(self):
        self.require('experiential');self.require('kilo')
        self.batch('experiential',HTTP([answer('deepseek-v4.1-flash')]))
        result=self.batch('kilo',HTTP([]),out='cached')
        self.assertEqual(result['cached'],1);self.assertEqual(result['http_attempts'],0)
        self.assertEqual(q.read_state(self.state_path)['items']['a']['inferred_provider'],'experiential')

    def test_experiential_token_ceiling_blocks_only_its_own_account(self):
        self.require('experiential')
        ledger=q.provider_state(self.state,'experiential')
        ledger['usage']={'date':datetime.fromtimestamp(self.clock.now(),timezone.utc).date().isoformat(),'attempts':1,'tokens':1000000}
        result=self.batch('experiential',HTTP([]))
        self.assertEqual(result['http_attempts'],0)
        self.assertEqual(result['not_attempted'],['a'])
        self.assertTrue(q.provider_eligible(self.state,'orcarouter',self.clock.now()))

    def test_weekly_reset_in_body_takes_precedence_over_short_retry_header(self):
        data={'error':{'code':'free_tier_limit_reached','message':"Your free allowance is used up. It comes back on 31 Oct 2026 at 08:01 UTC."}}
        delay=m.retry_delay({'Retry-After':'3600'},data,now=datetime(2026,10,30,10,0,tzinfo=timezone.utc).timestamp())
        self.assertEqual(delay,79260)

    def test_kilo_fast_responses_respect_hourly_rate_without_ip_rotation(self):
        self.require('kilo')
        result=self.batch('kilo',HTTP([answer(MODELS['kilo']),answer(MODELS['kilo'])]),ids=('a','b'))
        self.assertEqual(result['completed'],2)
        self.assertGreaterEqual(sum(self.clock.waits),20)

if __name__=='__main__':unittest.main()
