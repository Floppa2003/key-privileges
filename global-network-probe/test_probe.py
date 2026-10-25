import unittest
try: import probe
except ImportError: probe=None
class ProbeTests(unittest.TestCase):
 def setUp(self):self.assertIsNotNone(probe,'global comparison not implemented')
 def test_http_keeps_real_path_and_query(self):
  self.assertEqual(probe.options('http','https://www.rzd-bonus.ru/?accessible=true'),('www.rzd-bonus.ru',{'protocol':'HTTPS','port':443,'ipVersion':4,'request':{'method':'GET','path':'/','query':'accessible=true'}}))
 def test_tcp_is_bounded_not_port_scan(self):
  self.assertEqual(probe.options('ping','ekp.spb.ru'),('ekp.spb.ru',{'protocol':'TCP','port':443,'packets':1,'ipVersion':4}))
 def test_external_results_require_both_requested_countries(self):
  good={'results':[{'probe':{'country':'RU'}},{'probe':{'country':'NL'}}]}
  self.assertTrue(probe.country_pair(good))
  self.assertFalse(probe.country_pair({'results':[{'probe':{'country':'RU'}}]}))
 def test_public_evidence_does_not_include_response_cookies_or_body(self):
  r={'status':'finished','statusCode':403,'rawOutput':'Set-Cookie: secret','headers':{'set-cookie':'secret'},'tls':{'valid':True}}
  self.assertEqual(probe.evidence(r),{'status':'finished','statusCode':403,'tls':{'valid':True}})
if __name__=='__main__':unittest.main()

class ApiContractTests(unittest.TestCase):
 def test_absent_query_is_omitted_not_sent_as_empty_string(self):
  host,opts=probe.options('http','https://ekp.spb.ru/capabilities/loyalty/')
  self.assertEqual(opts['request'],{'method':'GET','path':'/capabilities/loyalty/'})
 def test_created_measurements_are_read_even_if_a_later_creation_fails(self):
  import os,tempfile,json
  from unittest.mock import patch
  class Response:
   def __init__(self,code,obj):self.status_code=code;self.obj=obj;self.text=json.dumps(obj)
   def json(self):return self.obj
  class Session:
   headers={}
   def __init__(self):self.created=0
   def request(self,method,url,**kwargs):
    if method=='POST':
     self.created+=1
     if self.created==4:return Response(400,{'error':{'message':'bad optional field'}})
     return Response(202,{'id':'m'+str(self.created),'probesCount':2})
    return Response(200,{'status':'finished','results':[{'probe':{'country':'RU'},'result':{'status':'finished'}},{'probe':{'country':'NL'},'result':{'status':'finished'}}]})
  old=os.getcwd()
  try:
   with tempfile.TemporaryDirectory() as tmp:
    os.chdir(tmp)
    with patch.object(probe.requests,'Session',Session),patch.object(probe.time,'sleep'):
     probe.main()
    result=json.loads(probe.Path('global-output/globalping.json').read_text())
    self.assertEqual([x['status'] for x in result['checks']],['completed']*3)
    self.assertIn('400',result['experiment_error'])
  finally:os.chdir(old)
