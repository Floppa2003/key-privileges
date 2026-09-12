import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from public_transport import PublicSource
RULES='User-agent: *\nDisallow: /*?*\nDisallow: /private/\nAllow: /private/public/\nCrawl-delay: 2\n'
class RobotsTests(unittest.IsolatedAsyncioTestCase):
 async def client(self):
  class Response:
   status=200
   async def text(self):return RULES
  class Requests:
   async def get(self,*a,**kw):return Response()
  c=PublicSource(None,'https://msk.t2.ru/bolshe/offers')
  c.context=type('Context',(),{'request':Requests()})()
  await c.robots();return c
 async def test_wildcard_query_rule_is_enforced(self):
  c=await self.client()
  with self.assertRaisesRegex(RuntimeError,'robots_disallow'):c.check_url('https://msk.t2.ru/bolshe/offer?id=abc')
  c.check_url('https://msk.t2.ru/bolshe/offers')
 async def test_longer_allow_overrides_shorter_disallow(self):
  c=await self.client();c.check_url('https://msk.t2.ru/private/public/offer')
 async def test_crawl_delay_is_not_replaced_by_default_rate(self):
  c=await self.client();self.assertGreaterEqual(getattr(c,'request_interval',0.25),2)
