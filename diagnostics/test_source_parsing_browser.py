"""Real Chromium replay of source parsing with fully controlled HTTP responses.

Every browser request is fulfilled locally or aborted. No original-source
network, accounts, model calls, or publication are used by these tests.
"""
import json
from pathlib import Path
import sys
import unittest

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'loyalty'))
import collect_normalized as collector

URL='https://msk.t2.ru/help/article/magnit-plus-premium'
NOW='2026-11-04T23:14:12.440964+00:00'
CFG=next(c for c in json.loads((ROOT/'loyalty/sources_normalized.json').read_text())
         if c['id']=='t2_magnit_rules')
FIXTURE=(ROOT/'loyalty/tests/fixtures_live/t2-magnit-20261104.html').read_text()
ARTICLE=BeautifulSoup(FIXTURE,'html.parser').body.decode_contents()
SHELL='<html><head><title>Магнит Плюс Премиум - служба поддержки T2</title></head><body><div>Загрузка…</div>'
DELAYED=SHELL+'<script>setTimeout(() => { document.body.innerHTML = '+json.dumps(ARTICLE)+'; }, 2800);</script></body></html>'


class RoutedBrowser:
    def __init__(self,real,html):
        self.real=real;self.html=html;self.documents=[];self.aborted=[]

    async def new_context(self,**kwargs):
        context=await self.real.new_context(**kwargs)
        async def route(request):
            if request.request.url==URL and request.request.resource_type=='document':
                self.documents.append(request.request.url)
                await request.fulfill(status=200,content_type='text/html; charset=utf-8',body=self.html)
            else:
                self.aborted.append(request.request.url)
                await request.abort()
        await context.route('**/*',route)
        return context


class SourceParsingBrowserTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.playwright=await async_playwright().start()
        self.browser=await self.playwright.chromium.launch(headless=True)

    async def asyncTearDown(self):
        await self.browser.close()
        await self.playwright.stop()

    async def test_actual_collector_waits_for_delayed_source_owned_article(self):
        # The old configuration reproduces the historical missing-heading error:
        # ordinary navigation returns after 1.2s, before our 2.8s hydration.
        before=dict(CFG);before.pop('ready_selector',None)
        old_browser=RoutedBrowser(self.browser,DELAYED)
        old_report,old_rows=await collector.one(old_browser,before,NOW,500)
        self.assertEqual(old_report['status'],'failed')
        self.assertEqual(old_rows,[])
        self.assertEqual(old_report['errors'][0]['reason'],'known_rule_scope_missing_or_ambiguous')
        self.assertEqual(old_report['errors'][0]['selector'],'.support-article__article-title')
        self.assertEqual(old_report['errors'][0]['matches'],0)
        self.assertEqual(old_browser.documents,[URL])

        current_browser=RoutedBrowser(self.browser,DELAYED)
        report,rows=await collector.one(current_browser,CFG,NOW,500)
        self.assertEqual(report['status'],'ok',report['errors'])
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['record_kind'],'program_rules')
        self.assertTrue(rows[0]['details']['activation']['same_phone_required'])
        for text in ('MiXX S','MiXX M','MiXX Max','Воспользоваться'):
            self.assertIn(text,rows[0]['conditions_text'])
        self.assertNotIn('Загрузка',rows[0]['conditions_text'])
        self.assertEqual(current_browser.documents,[URL])

    async def test_permanent_http_200_shell_remains_failed(self):
        browser=RoutedBrowser(self.browser,SHELL+'</body></html>')
        report,rows=await collector.one(browser,CFG,NOW,500)
        self.assertEqual(report['status'],'failed')
        self.assertEqual(rows,[])
        self.assertEqual(report['errors'][0]['reason'],'page_content_not_ready')
        self.assertEqual(browser.documents,[URL])


if __name__=='__main__':unittest.main(verbosity=2)
