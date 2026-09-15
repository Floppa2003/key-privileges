"""Control source timing without external requests or browser process launches."""
import asyncio
import sys
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
sys.path.insert(0,str(Path(__file__).parents[1]))
import utair_support as support
from public_transport import PublicSource
from protego import Protego
from test_utair_support import fixture,NOW

class Page:
    def __init__(self,sequence):
        self.sequence=list(sequence);self.url=support.ROOT;self.main_frame=object()
        self.listener=None;self.body='';self.on_content=None;self.goto_count=0
    def on(self,event,callback):self.listener=callback
    def remove_listener(self,event,callback):self.listener=None
    def emit(self):
        if not self.sequence:return
        status,self.body,opts=self.sequence.pop(0)
        self.url=opts.get('url',support.ROOT)
        req=SimpleNamespace(frame=self.main_frame,is_navigation_request=lambda:True)
        self.listener(SimpleNamespace(status=status,url=self.url,headers=opts.get('headers',{}),request=req))
    async def goto(self,*args,**kwargs):self.goto_count+=1;self.emit()
    async def content(self):
        if self.on_content:
            callback=self.on_content;self.on_content=None;callback()
        return self.body

class ReadTests(unittest.IsolatedAsyncioTestCase):
    async def read(self,sequence,on_content=None):
        page=Page(sequence);page.on_content=(lambda:on_content(page)) if on_content else None
        client=PublicSource(None,support.ROOT);client.page=page;client.policy=Protego.parse('')
        clock=[0]
        async def sleep(_):
            clock[0]+=6
            if page.goto_count and page.sequence:page.emit()
        try:
            with patch.object(support,'time',SimpleNamespace(monotonic=lambda:clock[0])),patch.object(support,'asyncio',SimpleNamespace(sleep=sleep,wait_for=asyncio.wait_for)):
                return await support.read_article(client)
        finally:
            self.assertIsNone(page.listener)
            self.assertEqual(page.goto_count,1)
    async def test_natural_reload_401_to_200(self):
        raw,statuses=await self.read([(401,'',{}),(200,fixture(),{})])
        self.assertEqual(statuses,[401,200]);self.assertIn('Новый партнер',raw)
    async def test_persistent_401_is_not_success(self):
        with self.assertRaisesRegex(RuntimeError,'http_401'):await self.read([(401,'',{})])
    async def test_actual_refusals_are_terminal(self):
        for status in (403,429,503):
            with self.subTest(status=status),self.assertRaisesRegex(RuntimeError,'http_'+str(status)):
                await self.read([(status,'',{})])
    async def test_retry_after_is_terminal(self):
        with self.assertRaisesRegex(RuntimeError,'utair_retry_after'):
            await self.read([(401,'',{'headers':{'retry-after':'60'}})])
    async def test_200_restriction_is_not_article(self):
        with self.assertRaisesRegex(RuntimeError,'access_challenge'):
            await self.read([(200,'<title>Access denied</title>',{})])
    async def test_shell_is_not_article(self):
        with self.assertRaisesRegex(RuntimeError,'utair_support_article_not_ready'):
            await self.read([(200,'<h1>Utair Status</h1>',{})])
    async def test_foreign_redirect_is_refused(self):
        with self.assertRaisesRegex(RuntimeError,'utair_unexpected_redirect'):
            await self.read([(200,fixture(),{'url':'https://foreign.example/'})])
    async def test_navigation_during_dom_read_must_not_certify_old_status(self):
        with self.assertRaisesRegex(RuntimeError,'utair_unexpected_redirect'):
            await self.read([(200,fixture(),{})],lambda page:setattr(page,'url','https://foreign.example/'))
    async def test_context_timeout_removes_listener(self):
        def fail(page):raise asyncio.TimeoutError()
        raw,statuses=await self.read([(200,fixture(),{})],fail)
        self.assertTrue(raw);self.assertEqual(statuses,[200])

class RoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_dispatcher_calls_real_source_entrypoint(self):
        import collect_normalized as collect
        cfg={'id':'utair','name':'Utair Status','url':support.ROOT,'mode':'access'}
        async def reader(cfg,report,now,limit):
            rows=support.parse_article(fixture(),now);report['discovered']=len(rows);report['coverage']='synthetic'
            return rows
        with patch.object(collect,'collect_utair',side_effect=reader) as call:
            report,rows=await collect.one(None,cfg,NOW,10)
        self.assertEqual(report['status'],'ok');self.assertEqual(len(rows),1);call.assert_awaited_once()
    async def test_robots_denial_never_navigates_article(self):
        @asynccontextmanager
        async def session():yield object(),object()
        with patch('installed_browser.installed_chrome',session),patch.object(PublicSource,'robots',new=AsyncMock(side_effect=RuntimeError('robots_disallow'))),patch.object(support,'read_article',new=AsyncMock()) as read:
            with self.assertRaisesRegex(RuntimeError,'robots_disallow'):
                await support.collect_utair({'id':'utair','url':support.ROOT},{'errors':[]},NOW,10)
            read.assert_not_awaited()

if __name__=='__main__':unittest.main()
