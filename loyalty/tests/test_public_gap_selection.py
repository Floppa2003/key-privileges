"""A targeted refresh cannot silently become a complete catalogue crawl."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from source_selection import select_sources,request_spec
import test_request

class SelectionTests(unittest.TestCase):
    def test_default_keeps_normal_scope_and_targeted_order_is_registered_order(self):
        cfg=[{'id':'alpha'},{'id':'beta'},{'id':'gamma'}];before=copy.deepcopy(cfg)
        self.assertEqual(select_sources(cfg),cfg)
        self.assertEqual(select_sources(cfg,'gamma,alpha'),[cfg[0],cfg[2]])
        self.assertEqual(cfg,before)

    def test_bad_selection_never_falls_back_to_all_sources(self):
        for value in ('unknown','alpha,','alpha,alpha',' alpha','https://example.test','alpha;echo x',None,','):
            with self.subTest(value=value),self.assertRaises(ValueError):select_sources([{'id':'alpha'}],value)

    def test_request_file_is_typed_and_legacy_request_means_full_scope(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'request.json'
            for value,wanted in [({},''),({'source_ids':['alpha','beta']},'alpha,beta')]:
                p.write_text(json.dumps(value));self.assertEqual(request_spec(p),wanted)
            for value in ('alpha',[1],None,[''],['alpha,beta']):
                p.write_text(json.dumps({'source_ids':value}))
                with self.assertRaises(ValueError):request_spec(p)

    def test_real_dispatcher_passes_only_registered_targeted_sources(self):
        result,args=test_request.RequestTests().run_script({'LOYALTY_SOURCE_IDS':'ekp_artflora,ekp_litres'})
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(args[-2:],['-f','sources=ekp_artflora,ekp_litres'])
        for value in ('not_registered','ekp_artflora,','ekp_artflora,ekp_artflora','ekp_artflora;echo fail'):
            result,args=test_request.RequestTests().run_script({'LOYALTY_SOURCE_IDS':value})
            self.assertNotEqual(result.returncode,0);self.assertIsNone(args)

if __name__=='__main__':unittest.main()
