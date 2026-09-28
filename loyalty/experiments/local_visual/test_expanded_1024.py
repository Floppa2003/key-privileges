"""Real document preparation regressions; no model responses are fabricated."""
import base64, hashlib, importlib.util, io, json, sys, tempfile, unittest
from pathlib import Path
import fitz
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parent))
try:
    import expanded_1024 as m
except ModuleNotFoundError:
    m = None

class ExpandedPreparation(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(m, 'expanded_1024 preparation not implemented')
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.case=self.root/'captures'/'synthetic';self.case.mkdir(parents=True)
        doc=fitz.open()
        for width,height in [(960,1200),(480,240)]:
            page=doc.new_page(width=width,height=height);page.insert_text((30,30),'Source evidence')
        doc.save(self.case/'reading.pdf');doc.close()
        (self.case/'visible-text.txt').write_bytes('Exact source\r\nsecond line'.encode())
        capture={'final_url':'https://example.test/offer','observed_at':'2026-09-27T00:00:00Z','warnings':['collapsed_controls_not_opened']}
        (self.case/'capture.json').write_text(json.dumps(capture))
        self.spec={'id':'synthetic','merchant':'Synthetic','program':'Example Club','files':{n:hashlib.sha256((self.case/n).read_bytes()).hexdigest() for n in ('reading.pdf','visible-text.txt','capture.json')}}
        self.out=self.root/'out';self.out.mkdir()

    def test_default_preserves_all_pages_and_limits_long_edge(self):
        request,info=m.prepare_case(self.root,self.spec,self.out)
        self.assertEqual(info['max_image_edge'],1024)
        self.assertEqual([p['size'] for p in info['images']],[[819,1024],[640,320]])
        self.assertEqual(len(request['messages'][-1]['images']),2)
        self.assertTrue(info['all_pdf_pages_sent']);self.assertFalse(info['publication_allowed'])

    def test_text_and_warnings_preserved(self):
        request,info=m.prepare_case(self.root,self.spec,self.out)
        self.assertTrue(request['messages'][-1]['content'].endswith('Exact source\r\nsecond line'))
        self.assertEqual(info['source_warnings'],['collapsed_controls_not_opened'])
        self.assertEqual((self.out/'visible-text.txt').read_bytes(),(self.case/'visible-text.txt').read_bytes())

    def test_source_mismatch_fails_before_any_request(self):
        (self.case/'visible-text.txt').write_text('changed')
        with self.assertRaisesRegex(ValueError,'source_hash_mismatch'):
            m.prepare_case(self.root,self.spec,self.out)
        self.assertFalse((self.out/'input.json').exists())

    def test_page_budget_rejects_whole_document_not_truncation(self):
        doc=fitz.open()
        for _ in range(9):doc.new_page(width=60,height=60)
        doc.save(self.case/'reading.pdf');doc.close()
        self.spec['files']['reading.pdf']=hashlib.sha256((self.case/'reading.pdf').read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError,'page_budget:9>8'):
            m.prepare_case(self.root,self.spec,self.out)
        self.assertFalse(list(self.out.glob('page-*.png')))

    def test_encoded_images_are_exact_saved_images(self):
        request,info=m.prepare_case(self.root,self.spec,self.out)
        for i,encoded in enumerate(request['messages'][-1]['images'],1):
            raw=(self.out/f'page-{i}.png').read_bytes()
            self.assertEqual(base64.b64decode(encoded),raw)
            self.assertEqual(hashlib.sha256(raw).hexdigest(),info['images'][i-1]['sha256'])

    def test_source_files_not_modified(self):
        before={n:(self.case/n).read_bytes() for n in self.spec['files']}
        m.prepare_case(self.root,self.spec,self.out)
        self.assertEqual(before,{n:(self.case/n).read_bytes() for n in before})

    def test_error_status_does_not_become_success(self):
        self.assertEqual(m.classify({'schema_valid':True,'returned_model':'qwen3.5:4b','vram_bytes':[0]}),'completed')
        self.assertEqual(m.classify({'schema_valid':False,'error_type':'ReadTimeout'}),'timeout')
        self.assertEqual(m.classify({'schema_valid':True,'returned_model':'other','vram_bytes':[0]}),'runtime_unverified')
        self.assertEqual(m.classify({'schema_valid':True,'returned_model':'qwen3.5:4b','vram_bytes':[1]}),'runtime_unverified')

    def test_case_path_traversal_rejected(self):
        self.spec['id']='../synthetic'
        with self.assertRaisesRegex(ValueError,'case_id'):
            m.prepare_case(self.root,self.spec,self.out)

if __name__=='__main__':unittest.main()
