"""Persistent queue contracts. External capture and HTTP are the only test doubles."""
import asyncio
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import merchant_extract as m
try:
    import merchant_queue as q
except ImportError:
    q = None

SCHEMA = {'type': 'object', 'properties': {'has_offer': {'type':'boolean'}, 'offers': {'type':'array'}, 'unknowns': {'type':'array'}}, 'required':['has_offer','offers','unknowns']}
EMPTY = {'has_offer': False, 'offers': [], 'unknowns': []}

class Response:
    def __init__(self, status=200, data=None, headers=None):
        self.status_code=status
        if data is None:
            data={'model':'deepseek-v4-1-flash-261017', 'choices':[{'finish_reason':'stop', 'message':{'role':'assistant','content':json.dumps(EMPTY)}}], 'usage':{'cost':0}}
        self.content=json.dumps(data).encode()
        self.headers=headers or {}

class HTTP:
    def __init__(self, responses): self.responses=list(responses); self.calls=[]
    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        value=self.responses.pop(0)
        if isinstance(value,Exception): raise value
        return value

class Clock:
    def __init__(self,t=1792886700): self.t=t; self.waits=[]
    def now(self): return self.t
    def sleep(self,s): self.waits.append(s); self.t+=s

class QueueTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(q,'persistent daily queue is not implemented')
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.state_path=self.root/'state.json'
        self.clock=Clock();self.state=q.new_state()
        b=io.BytesIO();Image.new('RGB',(2,2)).save(b,format='PNG');self.png=b.getvalue()

    def doc(self, ident='a', text='10%', day='2026-10-25'):
        return {'id':ident,'target':{'partner':ident,'program':'P','as_of':day},'text':text,'images':[self.png], 'source':{'source_url':'https://example.org/'+ident}}

    def run_batch(self, documents, responses, limit=50):
        client=HTTP(responses)
        out=self.root/('run-'+str(len(list(self.root.glob('run-*')))))
        result=q.process_documents(documents,self.state,self.state_path,out,'TEST_SECRET',SCHEMA,'prompt',
            session=client,now=self.clock.now,sleep=self.clock.sleep,max_requests=limit)
        self.state=json.loads(self.state_path.read_text())
        return result,client

    def test_restart_reuses_success_even_when_capture_date_changes(self):
        first,client=self.run_batch([self.doc()],[Response()]);self.assertEqual(first['completed'],1)
        second,client=self.run_batch([self.doc(day='2026-10-26')],[])
        self.assertEqual(second['cached'],1);self.assertEqual(len(client.calls),0)
        self.assertEqual(self.state['items']['a']['extracted'],EMPTY)
        self.assertEqual(self.state['items']['a']['inferred_as_of'],'2026-10-25')

    def test_text_image_target_and_contract_changes_invalidate_cache(self):
        d=self.doc();old=q.fingerprint(d,SCHEMA,'prompt')
        for change in ('text','images','target'):
            c=copy.deepcopy(d)
            if change=='text':c['text']='20%'
            if change=='images':c['images']=[b'new image']
            if change=='target':c['target']['program']='Other'
            self.assertNotEqual(q.fingerprint(c,SCHEMA,'prompt'),old)
        self.assertNotEqual(q.fingerprint(d,SCHEMA,'new prompt'),old)
        self.assertNotEqual(q.fingerprint(d,{**SCHEMA,'description':'different'},'prompt'),old)

    def test_hard_daily_budget_survives_repeated_runs_and_resets_utc(self):
        self.state['usage']={'date':'2026-10-25','attempts':49}
        result,client=self.run_batch([self.doc('a'),self.doc('b')],[Response()])
        self.assertEqual(len(client.calls),1);self.assertEqual(result['not_attempted'],['b'])
        again,client=self.run_batch([self.doc('b')],[])
        self.assertEqual(len(client.calls),0);self.assertEqual(again['status'],'deferred')
        self.clock.t=1792973100
        tomorrow,client=self.run_batch([self.doc('b')],[Response()])
        self.assertEqual(tomorrow['completed'],1);self.assertEqual(self.state['usage']['attempts'],1)

    def test_429_keeps_queue_and_respects_provider_pause_across_runs(self):
        error={'error':{'code':'free_rate_limited','metadata':{'reason':'err_free_rate','retry_after_seconds':3600}}}
        result,client=self.run_batch([self.doc('a'),self.doc('b')],[Response(429,error,{'Retry-After':'3600'})])
        self.assertEqual(len(client.calls),1);self.assertEqual(result['not_attempted'],['b'])
        self.assertGreaterEqual(self.state['provider_not_before'],self.clock.now()+3600)
        again,client=self.run_batch([self.doc('a'),self.doc('b')],[])
        self.assertEqual(len(client.calls),0);self.assertEqual(again['status'],'deferred')
        self.clock.t+=3601
        resumed,client=self.run_batch([self.doc('a'),self.doc('b')],[Response(),Response()])
        self.assertEqual(resumed['completed'],2)

    def test_bad_answer_does_not_erase_previous_success_or_stop_next_document(self):
        self.run_batch([self.doc()],[Response()])
        invalid={'model':m.MODEL,'choices':[{'finish_reason':'length','message':{'content':'{'}}]}
        result,client=self.run_batch([self.doc(text='changed'),self.doc('b')],[Response(data=invalid),Response()])
        self.assertEqual(len(client.calls),2);self.assertEqual(result['completed'],1)
        self.assertEqual(self.state['items']['a']['extracted'],EMPTY)
        self.assertEqual(self.state['items']['a']['status'],'failed_validation')
        self.assertEqual(self.state['items']['b']['status'],'completed')

    def test_no_model_calls_without_execute_is_cli_default(self):
        state=self.root/'missing.json';out=self.root/'prepared'
        with patch.dict('os.environ',{},clear=True):
            rc=q.main(['extract','--manifest',str(self.root/'absent-manifest.json'),'--state',str(state),'--out',str(out)])
        self.assertEqual(rc,0)
        self.assertEqual(json.loads((out/'summary.json').read_text())['status'],'prepared_not_inferred')

    def test_spacing_is_applied_to_fast_responses(self):
        result,client=self.run_batch([self.doc('a'),self.doc('b'),self.doc('c')],[Response(),Response(),Response()])
        self.assertEqual(len(client.calls),3)
        self.assertGreaterEqual(sum(self.clock.waits),14)

    def test_nonretryable_prompt_cap_does_not_stop_other_documents(self):
        error={'error':{'code':'free_rate_limited','metadata':{'reason':'err_free_prompt_cap','retryable':False}}}
        result,client=self.run_batch([self.doc('a'),self.doc('b')],[Response(400,error),Response()])
        self.assertEqual(len(client.calls),2);self.assertEqual(result['completed'],1)

    def test_free_access_denial_stops_batch_without_retry(self):
        error={'error':{'code':'free_rate_limited','metadata':{'reason':'err_free_access_denied','retryable':False}}}
        result,client=self.run_batch([self.doc('a'),self.doc('b')],[Response(429,error)])
        self.assertEqual(len(client.calls),1);self.assertEqual(result['not_attempted'],['b'])
        self.assertEqual(result['status'],'incomplete')

    def test_targets_are_deduplicated_by_url_program_partner_not_offer_row(self):
        records=[{'source_id':'a','partner_name':'New merchant','program':'P','source_url':'https://example.org/a','record_kind':'partner_offer'}]*2
        records+=[{**records[0],'program':'Q'}]
        targets=q.discover_targets({'records':records}, {'x':{'partner':'New merchant','program':'P','url':'https://example.org/a'}}, {})
        self.assertEqual(len(targets),2)
        self.assertEqual({t['program'] for t in targets}, {'P','Q'})
        self.assertTrue(all(len(t['id'])<60 for t in targets))

    def test_missing_catalog_does_not_empty_registered_sources_or_previous_queue(self):
        targets=q.discover_targets(None,{'x':{'partner':'New merchant','program':'P','url':'https://example.org/a'}},{})
        self.state['items']['old']={'target':{'id':'old','url':'https://example.org/old','partner':'Old','program':'P'},'last_checked':1}
        q.merge_targets(self.state,targets)
        self.assertIn('old',self.state['items']);self.assertEqual(len(self.state['items']),2)

    def test_rotation_puts_unseen_targets_first_then_least_recently_checked(self):
        targets=[{'id':c,'url':'https://example.org/'+c,'partner':c,'program':'P'} for c in 'abc']
        q.merge_targets(self.state,targets)
        self.state['items']['a']['last_checked']=100
        self.state['items']['b']['last_checked']=50
        self.assertEqual([t['id'] for t in q.pending_targets(self.state)],['c','b','a'])

    def test_persistence_roundtrip_is_atomic_json_and_versioned(self):
        q.write_state(self.state_path,self.state)
        self.assertEqual(q.read_state(self.state_path),self.state)
        self.state_path.write_text('{"version":99,"items":{}}')
        with self.assertRaises(ValueError):q.read_state(self.state_path)

    def test_time_budget_defers_work_instead_of_dropping_it(self):
        out=self.root/'time-budget'
        client=HTTP([Response(),Response()])
        # A caller can deliberately provide a zero processing window (dry pause).
        result=q.process_documents([self.doc()],self.state,self.state_path,out,'TEST_SECRET',SCHEMA,'prompt',
            session=client,now=self.clock.now,sleep=self.clock.sleep,time_budget=0)
        self.assertEqual(len(client.calls),0)
        self.assertEqual(result['not_attempted'],['a'])
        self.assertEqual(result['status'],'deferred')

    def test_empty_manifest_reports_quota_deferral_not_completed_extraction(self):
        day=q.datetime.now(q.timezone.utc).date().isoformat()
        self.state['usage']={'date':day,'attempts':50}
        q.write_state(self.state_path,self.state)
        manifest=self.root/'empty.json';manifest.write_text('{"documents":[]}')
        out=self.root/'empty-result'
        self.assertEqual(q.main(['extract','--manifest',str(manifest),'--state',str(self.state_path),
            '--out',str(out),'--execute']),0)
        result=json.loads((out/'summary.json').read_text())
        self.assertEqual(result['status'],'deferred');self.assertEqual(result['http_attempts'],0)

    def test_infer_one_attempt_mode_never_uses_hidden_extra_quota(self):
        client=HTTP([Response(503,{'error':{}}),Response()])
        result=m.infer({'model':m.MODEL,'messages':[]},SCHEMA,self.root/'one','TEST_SECRET',session=client,
            max_attempts=1,sleep=self.clock.sleep,monotonic=self.clock.now)
        self.assertEqual(result['http_attempts'],1);self.assertEqual(len(client.calls),1)

if __name__=='__main__':unittest.main()
