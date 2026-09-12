"""Regression: the first HTTP status need not describe the final browser document."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from public_transport import PublicSource

class Response:
    def __init__(self,page,status,url):
        self.status=status;self.url=url;self.headers={}
        self.request=type('Request',(),{'frame':page.main_frame,'is_navigation_request':lambda _:True})()
class Page:
    def __init__(self,sequence,url):
        self.sequence=list(sequence);self.url=url;self.main_frame=object();self.listeners={};self.body='';self.waits=0
    def on(self,event,callback):self.listeners[event]=callback
    def remove_listener(self,event,callback):self.listeners.pop(event,None)
    def emit(self):
        status,self.body=self.sequence.pop(0);r=Response(self,status,self.url)
        if 'response' in self.listeners:self.listeners['response'](r)
        return r
    async def goto(self,url,**kwargs):self.url=url;return self.emit()
    async def wait_for_timeout(self,_):
        self.waits+=1
        if self.sequence:self.emit()
    async def content(self):return self.body

class NavigationTests(unittest.IsolatedAsyncioTestCase):
    async def test_t2_natural_reload_uses_final_200_not_initial_503(self):
        client=PublicSource(None,'https://msk.t2.ru/bolshe/offers')
        client.page=Page([(503,'<title>Loading</title>'),(200,'<title>Больше</title><main>Скидка 10%</main>')], 'https://msk.t2.ru/bolshe/offers')
        self.assertTrue(hasattr(client,'navigate'), 'Missing final-document-aware browser transport')
        status,body=await client.navigate(client.page.url)
        self.assertEqual(status,200);self.assertIn('Скидка 10%',body)
        self.assertEqual(client.page.listeners,{})
    async def test_denial_without_navigation_stays_denial(self):
        client=PublicSource(None,'https://coralbonus.ru/klub-privilegii/')
        client.page=Page([(403,'<title>Access denied</title>')], 'https://coralbonus.ru/klub-privilegii/')
        self.assertTrue(hasattr(client,'navigate'))
        status,body=await client.navigate(client.page.url)
        self.assertEqual(status,403);self.assertIn('Access denied',body)
        self.assertLessEqual(client.page.waits,1)
    async def test_t2_without_final_success_does_not_fabricate_success(self):
        client=PublicSource(None,'https://msk.t2.ru/robots.txt')
        client.page=Page([(503,'<title>Loading</title>')], 'https://msk.t2.ru/robots.txt')
        self.assertTrue(hasattr(client,'navigate'))
        status,_=await client.navigate(client.page.url)
        self.assertEqual(status,503);self.assertLessEqual(client.page.waits,14)
