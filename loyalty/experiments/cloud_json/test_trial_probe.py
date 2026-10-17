import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

import jsonschema
import requests
import trial_probe as probe


class TrialProbeTests(unittest.TestCase):
    def setUp(self):
        self.schema = probe.common.strict_json((probe.common.HERE / 'merchant_offer.schema.json').read_text())
        self.base = probe.common.build_request({'partner':'test','program':'A','as_of':'2026-09-27'}, 'Full text A\nB foreign', [b'png1',b'png2'], self.schema, 'unchanged system')
        self.obj = {'has_offer':False, 'offers':[], 'unknowns':[]}
        self.key = 'unittest-secret-not-a-real-key'

    def response(self, provider, obj=None, finish=None):
        content = json.dumps(self.obj if obj is None else obj)
        if provider == 'cohere':
            return {'finish_reason':finish or 'COMPLETE','message':{'role':'assistant','content':[{'type':'thinking','thinking':'not a final answer'},{'type':'text','text':content}]}, 'usage':{'tokens':{'input_tokens':10,'output_tokens':20}}}
        return {'model':probe.MODELS[provider], 'choices':[{'finish_reason':finish or 'stop','message':{'role':'assistant','content':content}}], 'usage':{'prompt_tokens':10,'completion_tokens':20}}

    def test_payload_preserves_all_messages_images_and_source_schema(self):
        before=copy.deepcopy(self.base)
        for provider in probe.MODELS:
            payload=probe.build_payload(provider,self.base)
            self.assertEqual(payload['messages'],before['messages'])
            self.assertEqual(payload['model'],probe.MODELS[provider])
            self.assertEqual(payload['max_tokens'],8192)
            self.assertFalse(payload['stream'])
        self.assertEqual(self.base,before)

    def test_native_reasoning_and_schema_settings(self):
        co=probe.build_payload('cohere',self.base)
        sc=probe.build_payload('scaleway',self.base)
        self.assertEqual(co['thinking'],{'type':'enabled','token_budget':7168})
        self.assertEqual(sc['reasoning_effort'],'high')
        self.assertEqual(sc['response_format'],self.base['response_format'])
        self.assertEqual(co['response_format']['type'],'json_object')
        self.assertNotIn('reasoning',co)
        self.assertNotIn('reasoning',sc)

    def test_nonempty_pattern_equivalent_and_original_immutable(self):
        source={'type':'string','minLength':1}
        result=probe.cohere_schema(source)
        self.assertEqual(source,{'type':'string','minLength':1})
        for value in ('','a','\n','я','\x00','  '):
            self.assertEqual(jsonschema.Draft202012Validator(source).is_valid(value),jsonschema.Draft202012Validator(result).is_valid(value))
        with self.assertRaises(ValueError): probe.cohere_schema({'type':'string','minLength':2})
        with self.assertRaises(ValueError): probe.cohere_schema({'type':'string','minLength':1,'pattern':'x'})

    def test_completed_native_responses(self):
        for provider in probe.MODELS:
            self.assertEqual(probe.parse_final(provider,self.response(provider),self.schema),self.obj)

    def test_unfinished_or_wrong_model_not_accepted(self):
        for provider in probe.MODELS:
            with self.assertRaises(ValueError): probe.parse_final(provider,self.response(provider,finish='MAX_TOKENS'),self.schema)
            raw=self.response(provider);raw['model']='other-model'
            with self.assertRaises(ValueError): probe.parse_final(provider,raw,self.schema)

    def test_thinking_is_never_final(self):
        raw=self.response('cohere');raw['message']['content']=raw['message']['content'][:1]
        with self.assertRaises(ValueError):probe.parse_final('cohere',raw,self.schema)

    def test_original_schema_and_offer_state_still_enforced(self):
        for obj in ({'has_offer':True,'offers':[],'unknowns':[]}, {'has_offer':False,'offers':[],'unknowns':[],'extra':1}):
            for provider in probe.MODELS:
                with self.assertRaises((ValueError,jsonschema.ValidationError)): probe.parse_final(provider,self.response(provider,obj),self.schema)

    def test_duplicate_keys_and_refusal_rejected(self):
        for provider in probe.MODELS:
            raw=self.response(provider)
            message=raw['message'] if provider=='cohere' else raw['choices'][0]['message']
            message['refusal']='declined'
            with self.assertRaises(ValueError): probe.parse_final(provider,raw,self.schema)
        raw=self.response('scaleway');raw['choices'][0]['message']['content']='{"has_offer":false,"has_offer":false,"offers":[],"unknowns":[]}'
        with self.assertRaises(ValueError): probe.parse_final('scaleway',raw,self.schema)

    def test_model_preflight_is_exact(self):
        co={'name':probe.MODELS['cohere'],'endpoints':['chat'],'is_deprecated':False}
        sc={'data':[{'id':probe.MODELS['scaleway']}]}
        probe.select_model('cohere',co);probe.select_model('scaleway',sc)
        for provider in probe.MODELS:
            with self.assertRaises(ValueError):probe.select_model(provider,{})
        co['is_deprecated']=True
        with self.assertRaises(ValueError):probe.select_model('cohere',co)
        sc['data']*=2
        with self.assertRaises(ValueError):probe.select_model('scaleway',sc)

    def http(self,status,data,headers=None):
        return Mock(status_code=status,content=json.dumps(data).encode(),headers=headers or {})

    def test_transient_retry_same_bytes_and_redacted_logs(self):
        for provider in probe.MODELS:
            session=Mock();session.post.side_effect=[self.http(429,{'message':'busy'}, {'Retry-After':'20'}),self.http(200,self.response(provider))]
            with tempfile.TemporaryDirectory() as tmp:
                waits=[]
                result=probe.infer(provider,probe.build_payload(provider,self.base),self.schema,Path(tmp),self.key,session,waits.append)
                self.assertEqual(result['status'],'completed')
                self.assertEqual(result['http_attempts'],2)
                self.assertEqual(waits,[20])
                calls=session.post.call_args_list
                self.assertEqual(calls[0].kwargs['data'],calls[1].kwargs['data'])
                self.assertFalse(calls[0].kwargs['allow_redirects'])
                self.assertEqual(calls[0].kwargs['headers']['Authorization'],'Bearer '+self.key)
                for p in Path(tmp).rglob('*'):
                    if p.is_file():self.assertNotIn(self.key.encode(),p.read_bytes())

    def test_no_retry_on_permanent_validation_timeout_or_echo(self):
        bad=self.response('scaleway',finish='length')
        cases=[self.http(400,{'error':'invalid'}), self.http(200,bad), requests.Timeout('timeout'),self.http(503,{'error':self.key})]
        for response in cases:
            session=Mock();session.post.side_effect=[response]
            with tempfile.TemporaryDirectory() as tmp:
                result=probe.infer('scaleway',probe.build_payload('scaleway',self.base),self.schema,Path(tmp),self.key,session,lambda _:self.fail('unexpected retry'))
                self.assertEqual(result['http_attempts'],1)
                self.assertNotEqual(result['status'],'completed')
                for p in Path(tmp).rglob('*'):
                    if p.is_file():self.assertNotIn(self.key.encode(),p.read_bytes())

    def test_long_retry_after_not_shortened(self):
        session=Mock();session.post.return_value=self.http(429,{}, {'Retry-After':'120'})
        with tempfile.TemporaryDirectory() as tmp:
            result=probe.infer('scaleway',probe.build_payload('scaleway',self.base),self.schema,Path(tmp),self.key,session,lambda _:self.fail('wait not admitted'))
            self.assertEqual(result['http_attempts'],1)

    def test_fixed_provider_and_model_guard(self):
        with self.assertRaises(ValueError):probe.build_payload('other',self.base)
        session=Mock();payload=probe.build_payload('scaleway',self.base);payload['model']='other'
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):probe.infer('scaleway',payload,self.schema,Path(tmp),self.key,session)
        session.post.assert_not_called()


if __name__=='__main__':unittest.main()
