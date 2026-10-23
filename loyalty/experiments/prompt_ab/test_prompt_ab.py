import copy, hashlib, importlib, json, tempfile, unittest
from pathlib import Path
from PIL import Image

class PromptOnlyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try: cls.m=importlib.import_module('prompt_ab')
        except ModuleNotFoundError: cls.m=None

    def module(self):
        self.assertIsNotNone(self.m,'prompt-only runner is missing')
        return self.m

    def template(self):
        return {'model':'unchanged','format':{'required':['x']},'options':{'seed':1},
                'messages':[{'role':'system','content':'old'}, {'role':'user','content':'whole source','images':['abc','def']}], 'think':False}

    def test_old_payload_is_byte_equivalent_without_mutation(self):
        m=self.module(); source=self.template(); before=copy.deepcopy(source)
        out=m.with_prompt(source,'old')
        self.assertEqual(out,before);out['options']['seed']=9
        self.assertEqual(source,before)

    def test_defined_changes_only_system_content(self):
        m=self.module(); source=self.template();out=m.with_prompt(source,'defined')
        self.assertNotEqual(out['messages'][0]['content'],'old')
        out['messages'][0]['content']='old';self.assertEqual(out,source)

    def test_unknown_variant_is_rejected_not_silently_old(self):
        m=self.module()
        with self.assertRaises(ValueError):m.with_prompt(self.template(),'typo')

    def test_text_must_be_actual_request_suffix(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'request.json').write_text(json.dumps(self.template()))
            (root/'text.txt').write_text('other source')
            Image.new('RGB',(16,8)).save(root/'page.png')
            names=['request.json','text.txt','page.png']
            spec={'request':names[0],'text':names[1],'images':[names[2]],'sha256':{x:hashlib.sha256((root/x).read_bytes()).hexdigest() for x in names}}
            with self.assertRaisesRegex(ValueError,'text'):m.load_request(root,spec)

    def test_corrupted_input_rejected(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'x').write_text('changed')
            with self.assertRaisesRegex(ValueError,'hash'):m.checked_bytes(root,'x','0'*64)

    def test_source_path_cannot_escape_root(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaisesRegex(ValueError,'path'):m.checked_bytes(Path(t),'../outside','0'*64)

    def test_cpu_anomaly_not_reported_as_verified(self):
        m=self.module()
        self.assertEqual(m.runtime_status({'returned_model':'qwen3.5:4b','vram_bytes':[2681355632]}),'needs_log_review')
        self.assertEqual(m.runtime_status({'returned_model':'qwen3.5:4b','vram_bytes':[0]}),'cpu_verified')

if __name__=='__main__':unittest.main()
