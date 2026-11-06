"""Real Chromium replay of source parsing with fully controlled HTTP responses.

Every browser request is fulfilled locally or aborted. No original-source
network, accounts, model calls, or publication are used by these tests.
"""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

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



RGO_CFG=next(c for c in json.loads((ROOT/'loyalty/sources_normalized.json').read_text())
             if c['id']=='rgo')
RGO_URL=RGO_CFG['url']
RGO_DETAIL=(ROOT/'loyalty/tests/fixtures_live/rgo-etnomir.html').read_text()


def rgo_catalog(initial,mode):
    return """<!doctype html><html><body>
      <div id="cards"></div>
      <div class="pagination-more"><span class="btn" role="button" tabindex="0">More</span></div>
      <script>
      const cards=document.querySelector('#cards');
      const more=document.querySelector('.pagination-more .btn');
      const mode=__MODE__;
      let next=1;
      window.rgoClicks=0;
      window.rgoGrowthDelay=null;
      function appendCard() {
        const card=document.createElement('div'); card.className='loyalty-card';
        const link=document.createElement('a'); link.className='loyalty-card__link';
        link.href=__URL__+'browser-test-'+next+++'/'; link.textContent='Partner';
        card.append(link); cards.append(card);
      }
      for(let n=0;n<__INITIAL__;n++) appendCard();
      if(mode==='terminal') more.hidden=true;
      more.addEventListener('click',()=>{
        window.rgoClicks++;
        if(mode==='delayed') {
          const started=performance.now();
          setTimeout(()=>{
            for(let n=0;n<8;n++) appendCard();
            window.rgoGrowthDelay=performance.now()-started;
            more.hidden=true;
          },3000);
        } else if(mode==='cycle') {
          cards.append(cards.firstElementChild.cloneNode(true));
        } else if(mode==='limit-visible' || mode==='limit-terminal') {
          appendCard();
          if(mode==='limit-terminal' && window.rgoClicks===30) more.hidden=true;
        }
      });
      </script></body></html>""".replace('__INITIAL__',str(initial)).replace(
          '__MODE__',json.dumps(mode)).replace('__URL__',json.dumps(RGO_URL))


class RgoReplaySource:
    """Only transport is replaced; DOM clicks and both parsers stay real."""
    def __init__(self,browser,html):
        self.browser=browser;self.html=html;self.detail_reads=[];self.aborted=[]
        self.catalog_reads=0;self.clicks=0;self.growth_delay=None

    async def __aenter__(self):
        self.context=await self.browser.new_context()
        async def abort(route):
            self.aborted.append(route.request.url)
            await route.abort()
        await self.context.route('**/*',abort)
        self.page=await self.context.new_page()
        return self

    async def __aexit__(self,*_):
        try:
            state=await self.page.evaluate('({clicks: window.rgoClicks, delay: window.rgoGrowthDelay})')
            self.clicks=state['clicks'];self.growth_delay=state['delay']
        finally:
            await self.context.close()

    async def read(self,url,*,render=False):
        if url==RGO_URL and render:
            self.catalog_reads+=1
            await self.page.set_content(self.html,wait_until='domcontentloaded')
            return await self.page.content()
        if render or not url.startswith(RGO_URL+'browser-test-'):
            raise AssertionError('unexpected_replay_source_request')
        self.detail_reads.append(url)
        return RGO_DETAIL


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



    async def collect_rgo_replay(self,initial,mode):
        source=RgoReplaySource(self.browser,rgo_catalog(initial,mode))
        with patch.object(collector,'PublicSource',return_value=source):
            report,rows=await collector.one(self.browser,RGO_CFG,NOW,500)
        self.assertEqual(source.catalog_reads,1)
        self.assertEqual(source.aborted,[])
        self.assertEqual(len(set(source.detail_reads)),len(rows))
        return source,report,rows

    async def test_rgo_waits_for_native_growth_after_one_and_a_half_seconds(self):
        source,report,rows=await self.collect_rgo_replay(12,'delayed')
        self.assertEqual(report['status'],'ok',report['errors'])
        self.assertEqual(report['coverage'],'load_more_exhausted')
        self.assertEqual(report['discovered'],20)
        self.assertEqual(len(rows),20)
        self.assertEqual(source.clicks,1)
        self.assertGreaterEqual(source.growth_delay,2000)

    async def test_rgo_terminal_stalled_and_cyclic_catalogues_remain_distinct(self):
        for mode in ('terminal','stalled','cycle'):
            with self.subTest(mode=mode):
                source,report,rows=await self.collect_rgo_replay(12,mode)
                self.assertEqual(len(rows),12)
                if mode=='terminal':
                    self.assertEqual(report['status'],'ok',report['errors'])
                    self.assertEqual(report['coverage'],'load_more_exhausted')
                    self.assertEqual(report['errors'],[])
                    self.assertEqual(source.clicks,0)
                else:
                    self.assertEqual(report['status'],'partial')
                    self.assertEqual(report['coverage'],'pagination_not_exhausted')
                    self.assertEqual(report['errors'],[
                        {'phase':'catalog','reason':'load_more_did_not_grow'}])
                    self.assertEqual(source.clicks,1)

    async def test_rgo_thirtieth_click_requires_observed_exhaustion(self):
        for mode in ('limit-visible','limit-terminal'):
            with self.subTest(mode=mode):
                source,report,rows=await self.collect_rgo_replay(1,mode)
                self.assertEqual(source.clicks,30)
                self.assertEqual(report['discovered'],31)
                self.assertEqual(len(rows),31)
                if mode=='limit-visible':
                    self.assertEqual(report['status'],'partial')
                    self.assertEqual(report['coverage'],'pagination_not_exhausted')
                    self.assertEqual(report['errors'],[
                        {'phase':'catalog','reason':'pagination_iteration_limit_reached'}])
                else:
                    self.assertEqual(report['status'],'ok',report['errors'])
                    self.assertEqual(report['coverage'],'load_more_exhausted')
                    self.assertEqual(report['errors'],[])


if __name__=='__main__':unittest.main(verbosity=2)
