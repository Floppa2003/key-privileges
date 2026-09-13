"""A real captured 503 in the 2.3.2 branch run needs bounded, evidence-kept recovery."""
import json,sys,unittest
from pathlib import Path
from unittest.mock import AsyncMock,patch
sys.path.insert(0,str(Path(__file__).parents[1]))
from fixtures import fixture
from mir_ui import BrowserResponses,read_matching_detail
from test_mir_repair import Page,URL,NOW

class ResponseClient:
    request_interval=0
    def __init__(self,captured,responses):
        self.captured=captured;self.responses=list(responses);self.calls=[]
    async def read(self,url,**kwargs):
        self.calls.append(url);status,headers,data=self.responses.pop(0)
        class Response:
            url='https://vamprivet.ru/api/configs/client/?code=promoDetail'
            async def text(self):return json.dumps(data)
        response=Response();response.status=status;response.headers=headers
        await self.captured.capture(response)
        return '<main>Public detail page</main>'

class TemporaryDetailTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.data=json.loads(fixture('mir_detail.json'))
    async def test_temporary_public_api_errors_retry_once_and_keep_evidence(self):
        for status in (502,503,504):
            with self.subTest(status=status):
                captured=BrowserResponses(Page(),'vamprivet.ru')
                client=ResponseClient(captured,[(status,{},{}),(200,{},self.data)])
                with patch('mir_ui.asyncio.sleep',new_callable=AsyncMock):
                    record=await read_matching_detail(client,captured,URL,NOW,wait_timeout=.01)
                self.assertEqual(client.calls,[URL,URL])
                self.assertEqual(record['details']['retrieval_attempts'],2)
                self.assertEqual(record['details']['retrieval_recovered_errors'][0]['reason'],'http_'+str(status))
                self.assertEqual(captured.errors[0]['reason'],'http_'+str(status))

    async def test_retry_after_is_terminal_even_for_503(self):
        captured=BrowserResponses(Page(),'vamprivet.ru')
        client=ResponseClient(captured,[(503,{'retry-after':'60'},{}),(200,{},self.data)])
        with self.assertRaisesRegex(RuntimeError,'http_503'):
            await read_matching_detail(client,captured,URL,NOW,wait_timeout=.01)
        self.assertEqual(len(client.calls),1)
        self.assertTrue(captured.errors[0]['retry_after'])

    async def test_repeated_503_fails_after_two_reads_without_empty_success(self):
        captured=BrowserResponses(Page(),'vamprivet.ru')
        client=ResponseClient(captured,[(503,{},{}),(503,{},{})])
        with patch('mir_ui.asyncio.sleep',new_callable=AsyncMock):
            with self.assertRaisesRegex(RuntimeError,'http_503'):
                await read_matching_detail(client,captured,URL,NOW,wait_timeout=.01)
        self.assertEqual(len(client.calls),2)
        self.assertEqual(len(captured.errors),2)

    async def test_access_refusals_never_take_transient_branch(self):
        for status in (401,403,429):
            captured=BrowserResponses(Page(),'vamprivet.ru')
            client=ResponseClient(captured,[(status,{},{}),(200,{},self.data)])
            with self.assertRaisesRegex(RuntimeError,'http_'+str(status)):
                await read_matching_detail(client,captured,URL,NOW,wait_timeout=.01)
            self.assertEqual(len(client.calls),1)
