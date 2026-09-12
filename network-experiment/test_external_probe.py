import unittest
try: import external_probe as e
except ImportError: e=None
class Tests(unittest.TestCase):
 def setUp(self): self.assertIsNotNone(e)
 def test_nodes_must_be_actual_ru_nl_nodes(self):
  nodes={'nodes':{'ru1.node.check-host.net':{'location':['ru','Russia','Moscow']},'nl1.node.check-host.net':{'location':['nl','Netherlands','Amsterdam']}}}
  self.assertEqual(e.choose_nodes(nodes), ['ru1.node.check-host.net','nl1.node.check-host.net'])
  nodes['nodes']['ru1.node.check-host.net']['location'][0]='us'
  with self.assertRaises(ValueError): e.choose_nodes(nodes)
 def test_job_identity_must_be_same_service_and_requested_nodes(self):
  self.assertEqual(e.validate_job({'ok':1,'request_id':'a123','nodes':{'n1':[],'n2':[]}},['n1','n2']), 'a123')
  with self.assertRaises(ValueError):e.validate_job({'ok':1,'request_id':'../../private','nodes':{'n1':[]}},['n1'])
  with self.assertRaises(ValueError):e.validate_job({'ok':1,'request_id':'a123','nodes':{'evil':[]}},['n1'])
if __name__=='__main__':unittest.main()
