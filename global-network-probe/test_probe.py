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
