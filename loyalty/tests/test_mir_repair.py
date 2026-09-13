import json,sys,time,unittest
from pathlib import Path
from unittest.mock import AsyncMock,patch
sys.path.insert(0,str(Path(__file__).parents[1]))
from fixtures import fixture
import mir_ui
URL='https://vamprivet.ru/promo/transport/ekspress-v-aeroport-s-vygodoy-i-komfortom-1/'
NOW='2026-09-13T00:00:00+00:00'
class Page:
    def __init__(self):self.listeners={}
    def on(self,event,callback):self.listeners[event]=callback
    def remove_listener(self,event,callback):self.listeners.pop(event,None)
class Client:
    request_interval=0
    def __init__(self,responses,captured):self.responses=list(responses);self.captured=captured;self.calls=[]
    async def read(self,url,**kwargs):
        self.calls.append(url);entry=self.responses.pop(0)
        if entry is None:return ''
        if isinstance(entry,Exception):raise entry
        status,payload=entry
        class Response:
            url='https://vamprivet.ru/api/configs/client/?code=promoDetail'
            async def text(self):return json.dumps(payload)
        r=Response();r.status=status
        await self.captured.capture(r)
        return '<main>Public page</main>'
class MirRepairTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fn=getattr(mir_ui,'read_matching_detail',None)
        self.assertTrue(callable(self.fn),'Missing bounded Mir detail recovery')
        self.data=json.loads(fixture('mir_detail.json'))
        self.capture=mir_ui.BrowserResponses(Page(),'vamprivet.ru')
    async def test_missing_response_recovers_once_and_never_reuses_old_details(self):
        self.capture.details.append(self.data) # Must not satisfy this new observation.
        c=Client([None,(200,self.data)],self.capture)
        with patch('mir_ui.asyncio.sleep',new_callable=AsyncMock):
            record=await self.fn(c,self.capture,URL,NOW,wait_timeout=.01)
        self.assertEqual(c.calls,[URL,URL]);self.assertEqual(record['source_url'],URL)
        self.assertEqual(record['details']['retrieval_attempts'],2)
    async def test_api_denial_is_not_retried_as_missing_response(self):
        for status in (401,403,429):
            capture=mir_ui.BrowserResponses(Page(),'vamprivet.ru');c=Client([(status,{})],capture)
            with self.assertRaisesRegex(RuntimeError,'http_'+str(status)):
                await self.fn(c,capture,URL,NOW,wait_timeout=.01)
            self.assertEqual(len(c.calls),1)
    async def test_wrong_native_id_is_not_accepted_or_retried(self):
        c=Client([(200,self.data)],self.capture)
        with self.assertRaisesRegex(RuntimeError,'identity_mismatch'):
            await self.fn(c,self.capture,URL,NOW,expected_id='not-the-real-id',wait_timeout=.01)
        self.assertEqual(len(c.calls),1)
    async def test_exhausted_deadline_does_not_start_another_request(self):
        c=Client([],self.capture)
        with self.assertRaisesRegex(RuntimeError,'budget'):
            await self.fn(c,self.capture,URL,NOW,deadline=time.monotonic()-1,wait_timeout=.01)
        self.assertEqual(c.calls,[])
    async def test_two_missing_responses_report_failure_not_empty_success(self):
        c=Client([None,None],self.capture)
        with patch('mir_ui.asyncio.sleep',new_callable=AsyncMock):
            with self.assertRaisesRegex(RuntimeError,'expected_public_response_not_observed'):
                await self.fn(c,self.capture,URL,NOW,wait_timeout=.01)
        self.assertEqual(len(c.calls),2)

    async def test_in_flight_navigation_is_stopped_at_source_deadline(self):
        import asyncio
        stopped=asyncio.Event()
        class StalledClient:
            request_interval=0
            async def read(self,*args,**kwargs):
                try:await asyncio.Event().wait()
                finally:stopped.set()
        try:
            await asyncio.wait_for(self.fn(StalledClient(),self.capture,URL,NOW,
                deadline=time.monotonic()+.01),.1)
        except RuntimeError as exc:self.assertIn('budget',str(exc))
        except asyncio.TimeoutError:self.fail('In-flight read ignored its source deadline')
        else:self.fail('Stalled read returned success')
        self.assertTrue(stopped.is_set())

class MirCatalogIdentityTests(unittest.TestCase):
    def test_dom_validation_keeps_native_id_observed_in_same_catalogue(self):
        html='<main><div class="x__promos__y"><a class="promo-card-v2__link" href="/promo/test/a/"><div class="promo-card-v2-owner__name">A</div></a></div></main>'
        profile={'expected':1,'page_title':'Москва','items':[{'xml_id':'native-123','url':'/promo/test/a/','name':'A'}]}
        result=mir_ui.dom_snapshot(html,profile,'mir',1)
        self.assertEqual(result['items'][0]['xml_id'],'native-123')
