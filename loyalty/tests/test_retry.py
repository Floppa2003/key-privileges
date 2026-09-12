import json,sys,unittest
from pathlib import Path
from protego import Protego
sys.path.insert(0,str(Path(__file__).parents[1]))
from public_transport import PublicSource
URL='https://vamprivet.ru/api/configs/client/?code=promoDetail'

class Response:
 def __init__(self,status,body,headers=None):self.status=status;self.body=body;self.url=URL;self.headers=headers or {}
 async def text(self):return self.body
 async def json(self):return json.loads(self.body)
class Requests:
 def __init__(self,responses):self.responses=list(responses);self.calls=[]
 async def fetch(self,url,**kwargs):
  self.calls.append((url,kwargs))
  if not self.responses:raise AssertionError('Unexpected extra HTTP request')
  return self.responses.pop(0)
class Context:
 def __init__(self,responses):self.request=Requests(responses)

class RetryTests(unittest.IsolatedAsyncioTestCase):
 def client(self,responses):
  c=PublicSource(None,URL);c.context=Context(responses);c.policy=Protego.parse('');return c
 async def test_transient_503_is_retried_without_changing_read_request(self):
  c=self.client([Response(503,'temporary'),Response(200,'{"offer_id":42}')])
  try:r=await c.json(URL)
  except RuntimeError as e:self.fail('Transient read was not retried: '+str(e))
  self.assertEqual(r,{'offer_id':42})
  self.assertEqual([x[0] for x in c.context.request.calls],[URL,URL])
 async def test_persistent_server_failure_stops_after_three_attempts(self):
  c=self.client([Response(503,'temporary') for _ in range(3)])
  with self.assertRaises(RuntimeError):await c.json(URL)
  self.assertEqual(len(c.context.request.calls),3)
 async def test_access_denial_and_rate_limit_are_not_retried(self):
  for status in [401,403,429]:
   c=self.client([Response(status,'denied')])
   with self.assertRaises(RuntimeError):await c.json(URL)
   self.assertEqual(len(c.context.request.calls),1)
 async def test_retry_after_response_is_not_immediately_retried(self):
  c=self.client([Response(503,'busy',{'retry-after':'120'})])
  with self.assertRaises(RuntimeError):await c.json(URL)
  self.assertEqual(len(c.context.request.calls),1)
 async def test_successful_captcha_is_not_data_and_not_retried(self):
  c=self.client([Response(200,'<html><title>Just a moment</title></html>')])
  with self.assertRaises(RuntimeError):await c.json(URL)
  self.assertEqual(len(c.context.request.calls),1)
if __name__=='__main__':unittest.main()
