"""Protect the prompt-only boundary and explicit single-candidate plan mode."""
import copy, hashlib, json, subprocess, sys, tempfile, unittest
from pathlib import Path
from PIL import Image
import prompt_ab as m

class PromptOptions(unittest.TestCase):
    def source(self):
        return {'model':'fixed','format':{'type':'object'},'options':{'seed':1},
                'messages':[{'role':'system','content':'baseline'},
                            {'role':'user','content':'exact source','images':['one','two']}],
                'think':False}

    def test_custom_candidate_changes_only_system_and_does_not_mutate(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'candidate.txt';p.write_text('new grounded instructions',encoding='utf-8')
            src=self.source();before=copy.deepcopy(src)
            got=m.with_prompt(src,'defined',p)
            self.assertEqual(got['messages'][0]['content'],'new grounded instructions')
            got['messages'][0]['content']='baseline'
            self.assertEqual(got,before);self.assertEqual(src,before)

    def test_baseline_does_not_read_or_require_candidate_file(self):
        got=m.with_prompt(self.source(),'old',Path('/missing/candidate.txt'))
        self.assertEqual(got,self.source())

    def test_plan_single_candidate_has_one_record_and_keeps_all_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);src=self.source();src['messages'][-1].pop('images')
            (root/'request.json').write_text(json.dumps(src));(root/'text.txt').write_text('exact source')
            for n in (1,2):Image.new('RGB',(12,8)).save(root/f'page-{n}.png')
            names=['request.json','text.txt','page-1.png','page-2.png']
            spec={'id':'fixture','request':names[0],'text':names[1],'images':names[2:],
                  'order':['old','defined'],'sha256':{n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in names}}
            plan=root/'plan.json';plan.write_text(json.dumps({'cases':[spec]}))
            prompt=root/'candidate.txt';prompt.write_text('new grounded instructions')
            out=root/'out'
            run=subprocess.run([sys.executable,str(Path(m.__file__)), '--source',str(root),
              '--out',str(out),'--cases','fixture','--plan',str(plan),'--candidate-prompt',str(prompt),
              '--variants','defined'],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr)
            rows=json.loads((out/'summary.json').read_text())['attempts']
            self.assertEqual([(r['variant'],r['status']) for r in rows],[('defined','prepared')])
            self.assertEqual(len(list((out/'fixture').glob('page-*.png'))),2)
            q=json.loads((out/'fixture/defined/request-without-image-bytes.json').read_text())
            self.assertEqual(q['messages'][0]['content'],'new grounded instructions')
            self.assertEqual(q['messages'][1]['content'],'exact source')
            self.assertFalse((out/'fixture/old').exists())
            self.assertFalse(rows[0]['publication_allowed'])

if __name__=='__main__':unittest.main()
