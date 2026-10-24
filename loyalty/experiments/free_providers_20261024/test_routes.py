import unittest
from unittest.mock import Mock
import routes as m

class Routes(unittest.TestCase):
    def test_secret_scrubbing(self):
        self.assertEqual(m.scrub('prefix secret-key suffix', ['secret-key']), 'prefix [REDACTED] suffix')
    def test_models_have_no_paid_substitution(self):
        for p in ('orca','harbor','opencode','openrouter'):
            self.assertTrue(all(x.endswith(('-free', ':free')) for x in m.ROUTES[p]['models']))
    def test_payload_all_images_preserved(self):
        x=m.payload('orca','x-free','sys','hello',['AAA','BBB'], {})
        self.assertEqual([p['image_url']['url'] for p in x['messages'][1]['content'][1:]], ['data:image/png;base64,AAA','data:image/png;base64,BBB'])
        self.assertNotIn('tools',x)
    def test_gemini_images_preserved(self):
        x=m.payload('gemini','gemini-3.8-flash','sys','hello',['AAA','BBB'], {})
        self.assertEqual([p['inlineData']['data'] for p in x['contents'][0]['parts'][1:]], ['AAA','BBB'])
        self.assertFalse(x['generationConfig']['thinkingConfig']['includeThoughts'])
    def test_final_json(self):
        self.assertEqual(m.final_text('orca',{'choices':[{'finish_reason':'stop','message':{'content':'{"code":"7429"}'}}]}),'{"code":"7429"}')
    def test_truncation_rejected(self):
        with self.assertRaisesRegex(ValueError,'unfinished'):
            m.final_text('orca',{'choices':[{'finish_reason':'length','message':{'content':'{}'}}]})
    def test_reasoning_not_answer(self):
        with self.assertRaisesRegex(ValueError,'empty'):
            m.final_text('orca',{'choices':[{'finish_reason':'stop','message':{'content':None,'reasoning':'{}'}}]})
    def test_tools_rejected(self):
        with self.assertRaisesRegex(ValueError,'tool'):
            m.final_text('orca',{'choices':[{'finish_reason':'stop','message':{'content':'{}','tool_calls':[{}]}}]})
    def test_unknown_price_is_not_zero(self):
        self.assertFalse(m.is_zero_priced({'id':'some'}))
        self.assertFalse(m.is_zero_priced({'pricing':{'input':'0','output':'0.2'}}))
        self.assertTrue(m.is_zero_priced({'pricing':{'input':'0','output':'0'}}))
    def test_invalid_json_not_repaired(self):
        with self.assertRaises(ValueError):m.validate('```json\n{"code":"7429"}\n```',m.SMOKE_SCHEMA)
    def test_json_schema_not_just_json(self):
        with self.assertRaises(ValueError):m.validate('{"other":1}',m.SMOKE_SCHEMA)
    def test_redirects_disabled(self):
        session=Mock();response=Mock(status_code=302,content=b'');session.request.return_value=response
        m.http(session,'GET','https://example.com',{},None,[])
        self.assertFalse(session.request.call_args.kwargs['allow_redirects'])

if __name__=='__main__':unittest.main()
