import hashlib
import json
import unittest
try:
    import run_cpu as cpu
except ImportError:
    cpu = None

class CPUProbeTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(cpu, 'CPU-only batch client is not implemented')

    def test_all_images_text_schema_are_sent_without_gold_or_cloud_tools(self):
        p=cpu.payload({'partner':'Example','program':'Club','as_of':'2026-09-27'},'source text',[b'a',b'b'])
        self.assertEqual(p['messages'][-1]['images'],['YQ==','Yg=='])
        self.assertIn('source text',p['messages'][-1]['content'])
        self.assertEqual(p['options']['num_gpu'],0)
        self.assertFalse(p['think'])
        self.assertNotIn('tools',p)
        self.assertNotIn('expected',str(p))

    def test_empty_and_too_many_images_are_rejected(self):
        for images in ([],[b'a']*9):
            with self.assertRaises(ValueError):cpu.payload({},'text',images)

    def test_rejects_incomplete_invalid_or_extra_json(self):
        obj={'has_offer':False,'offers':[],'unknowns':[]}
        base={'done':True,'done_reason':'stop','message':{'content':json.dumps(obj)}}
        self.assertEqual(cpu.parse_response(base),obj)
        for changed in ({**base,'done_reason':'length'},
                        {**base,'message':{'content':'```json\n{}\n```'}},
                        {**base,'message':{'content':json.dumps({**obj,'extra':1})}},
                        {**base,'message':{'content':json.dumps({**obj,'has_offer':True})}}):
            with self.assertRaises(ValueError):cpu.parse_response(changed)

    def test_remote_and_missing_weights_are_rejected(self):
        for tags in ({'models':[]},{'models':[{'name':cpu.MODEL,'remote_host':'cloud'}]}):
            with self.assertRaises(ValueError):cpu.local_model(tags)

    def test_changed_source_never_reaches_model(self):
        with self.assertRaises(ValueError):cpu.verify(b'bad',hashlib.sha256(b'good').hexdigest())

if __name__=='__main__':unittest.main()
