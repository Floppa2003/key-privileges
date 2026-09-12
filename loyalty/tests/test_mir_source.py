import asyncio,copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from mir_source import page_body,walk_catalog
BODY={'filters':[{'id':'category_link','values':[]}],'page':1,'customFilter':None,'idCompilation':None,'sort':None,'paymentType':'sbp'}
def payload(n):
 return {'success':True,'data':{'items':[{'xml_id':str(n),'url':'/promo/test/'+str(n)+'/'}], 'counter':{'qt':2},'pagination':[{'page':1},{'page':2}], 'pageTitle':'Москва и МО','query':f'/promo/?page_catalog_list={n}&payment_type=sbp'}}
class Client:
 def __init__(self,fail=False):self.calls=[];self.fail=fail
 async def json(self,url,**kw):
  self.calls.append((url,kw))
  if self.fail:raise RuntimeError('http_500')
  d=json.loads(kw['data'])
  return payload(d['page'])
class MirTransportTests(unittest.TestCase):
 def test_page_is_changed_in_json_body_not_only_query(self):
  changed=page_body(BODY,2)
  self.assertEqual(changed['page'],2);self.assertEqual(changed['paymentType'],'sbp');self.assertEqual(BODY['page'],1)
 def test_private_fields_are_not_replayed(self):
  with self.assertRaises(ValueError):page_body({**BODY,'accessToken':'not-for-replay'},2)
 def test_pagination_uses_observed_post_and_collects_new_ids(self):
  c=Client();items,report=asyncio.run(walk_catalog(c,'https://vamprivet.ru/api/moskva-i-mo/promo/filter-json',BODY,payload(1)))
  self.assertEqual(set(items),{'1','2'});self.assertEqual(report['observed'],2);self.assertEqual(report['errors'],[])
  self.assertEqual(c.calls[0][1]['method'],'POST');self.assertEqual(json.loads(c.calls[0][1]['data'])['page'],2)
 def test_later_page_failure_preserves_first_page_evidence(self):
  items,report=asyncio.run(walk_catalog(Client(True),'https://vamprivet.ru/api/moskva-i-mo/promo/filter-json',BODY,payload(1)))
  self.assertEqual(set(items),{'1'});self.assertTrue(report['errors']);self.assertEqual(report['expected'],2)
