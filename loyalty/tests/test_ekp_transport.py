"""Exercise the real EKP walk, policy guard and dispatcher without network access."""
import asyncio
import json
import sys
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ekp_catalog as ekp
from public_transport import PublicSource
from protego import Protego
from test_ekp_catalog import card, page as html_page, NOW


class Page:
    def __init__(self, pages):
        self.pages = list(pages)
        self.index = 0
        self.url = ekp.ROOT
        self.main_frame = object()
        self.listener = None
        self.goto_count = 0
        self.click_count = 0
        self.on_content = None
        self.on_control = None
        self.status = 200
        self.headers = {}
        self.control_count = 1
        self.next_page_error = None
        self.api_on_content = None
        self.delays = []
        self.click_delays = []
    def on(self, event, callback):
        self.listener = callback
    def remove_listener(self, event, callback):
        self.listener = None
    def emit(self, status=200, url=None, headers=None, is_navigation=True):
        self.listener(SimpleNamespace(status=status, url=url or self.url, headers=headers or {},
            request=SimpleNamespace(frame=self.main_frame, is_navigation_request=lambda: is_navigation)))
    async def goto(self, url, **kwargs):
        self.goto_count += 1
        self.emit(self.status, self.url, self.headers)
    async def content(self):
        result = self.pages[self.index]
        if self.on_content:
            cb, self.on_content = self.on_content, None
            cb(self)
        if self.api_on_content:
            opts, self.api_on_content = self.api_on_content, None
            self.emit(url='https://ekp.spb.ru/api/portal/loyalty/partners', is_navigation=False, **opts)
        return result
    def get_by_role(self, *args, **kwargs):
        return self
    async def count(self):
        if self.on_control:
            cb, self.on_control = self.on_control, None
            cb(self)
        return self.control_count
    async def is_visible(self):
        return self.index + 1 < len(self.pages)
    async def is_enabled(self):
        return self.index + 1 < len(self.pages)
    async def click(self, **kwargs):
        self.click_count += 1
        self.click_delays.append(list(self.delays))
        self.delays.clear()
        if self.next_page_error:
            raise self.next_page_error
        self.index += 1


class WalkTests(unittest.IsolatedAsyncioTestCase):
    def client(self, page, policy=''):
        client = PublicSource(None, ekp.ROOT)
        client.page = page
        client.policy = Protego.parse(policy)
        return client

    async def walk(self, pages, *, limit=100, configure=None, policy='', interval=.25):
        page = Page(pages)
        if configure:
            configure(page)
        client = self.client(page, policy)
        client.request_interval = interval
        report = {'discovered': 0, 'errors': []}
        # Patch only the adapter's sleep; leave event-loop and deadline clocks real.
        real_sleep = asyncio.sleep
        clock = [0.0]
        async def sleep(delay):
            page.delays.append(delay)
            clock[0] += max(1,delay)
            await real_sleep(0)
        with patch.object(ekp, 'asyncio', SimpleNamespace(sleep=sleep, wait_for=asyncio.wait_for,
                                                        TimeoutError=asyncio.TimeoutError)), \
             patch.object(ekp, 'time', SimpleNamespace(monotonic=lambda:clock[0])):
            rows = await ekp.walk_catalog(client, report, NOW, limit)
        self.assertIsNone(page.listener)
        return rows, report, page

    async def test_shell_waits_for_actual_cards_without_second_navigation(self):
        def configure(p):
            p.on_content = lambda p:p.pages.__setitem__(0,html_page(card()))
        rows,report,browser = await self.walk([html_page('Загрузка')],configure=configure)
        self.assertEqual(len(rows),1)
        self.assertEqual(browser.goto_count,1)

    async def test_persistent_shell_is_bounded_not_an_empty_catalog(self):
        rows,report,browser = await self.walk([html_page('Загрузка')])
        self.assertEqual(rows,[])
        self.assertIn('ekp_catalog_not_ready',str(report['errors']))
        self.assertEqual(browser.goto_count,1)
        self.assertLessEqual(len(browser.delays),32)

    async def test_load_more_no_growth_keeps_rows_and_reports_failure(self):
        body=html_page(card())
        rows,report,browser=await self.walk([body,body])
        self.assertEqual(len(rows),1)
        self.assertEqual(browser.click_count,1)
        self.assertIn('ekp_load_more_no_growth',str(report['errors']))

    async def test_200_challenge_never_yields_a_record(self):
        rows,report,browser=await self.walk(['<html><title>Access denied</title><body>Blocked</body></html>'])
        self.assertEqual(rows,[])
        self.assertIn('access_challenge',str(report['errors']))
        self.assertEqual(browser.click_count,0)

    async def test_real_walk_reconciles_growth_and_keeps_preview_scope(self):
        a = card('1', 'Первый', 'Скидка 11%')
        b = card('2', 'Второй', 'Скидка 22%', gated=True)
        rows, report, browser = await self.walk([html_page(a), html_page(a+b)])
        self.assertEqual(len(rows), 2)
        self.assertEqual(browser.click_count, 1)
        self.assertEqual([r['native_id'] for r in rows], ['card:1','card:2'])
        self.assertEqual(report['discovered'], 2)
        coverage = json.loads(report['coverage'])
        self.assertFalse(coverage['full_catalog_complete'])
        self.assertFalse(coverage['details_fetched'])
        self.assertTrue(report['errors'])

    async def test_late_card_failure_retains_previous_page(self):
        a = card('1')
        rows, report, browser = await self.walk([html_page(a), html_page(a+card('2')+card('2'))])
        self.assertEqual([r['native_id'] for r in rows], ['card:1'])
        self.assertEqual(browser.click_count, 1)
        self.assertTrue(report['errors'])

    async def test_old_card_terms_cannot_change_during_pagination(self):
        rows, report, _ = await self.walk([html_page(card('1')), html_page(card('1',benefit='Скидка 99%')+card('2'))])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['benefit_text'], 'Скидка 17%')
        self.assertIn('ekp_catalog_changed_during_pagination', str(report['errors']))

    async def test_replacement_page_is_not_load_more(self):
        rows, report, _ = await self.walk([html_page(card('1')), html_page(card('2'))])
        self.assertEqual(len(rows), 1)
        self.assertIn('ekp_load_more_lost_previous_cards', str(report['errors']))

    async def test_cap_never_clicks_next_page_or_claims_complete(self):
        rows, report, browser = await self.walk([html_page(card('1')+card('2')),html_page(card('3'))],limit=1)
        self.assertEqual(len(rows),1)
        self.assertEqual(report['discovered'],2)
        self.assertEqual(browser.click_count,0)
        self.assertEqual(json.loads(report['coverage'])['stop_reason'],'record_limit')

    async def test_initial_http_refusals_do_not_parse_or_click(self):
        for status in (401,403,429,503):
            with self.subTest(status=status):
                rows, report, browser = await self.walk([html_page(card())],configure=lambda p:setattr(p,'status',status))
                self.assertEqual(rows,[])
                self.assertEqual(browser.click_count,0)
                self.assertIn('http_'+str(status),str(report['errors']))

    async def test_retry_after_on_200_is_terminal(self):
        rows, report, browser = await self.walk([html_page(card())],configure=lambda p:setattr(p,'headers',{'retry-after':'60'}))
        self.assertEqual(rows,[])
        self.assertEqual(browser.click_count,0)
        self.assertIn('ekp_retry_after',str(report['errors']))

    async def test_api_refusal_cannot_certify_displayed_cards(self):
        rows, report, browser = await self.walk([html_page(card())],configure=lambda p:setattr(p,'api_on_content',{'status':403}))
        self.assertEqual(rows,[])
        self.assertEqual(browser.click_count,0)
        self.assertIn('http_403',str(report['errors']))

    async def test_foreign_navigation_during_dom_capture_is_terminal(self):
        rows, report, browser = await self.walk([html_page(card())],configure=lambda p:setattr(p,'on_content',lambda p:setattr(p,'url','https://foreign.example/')))
        self.assertEqual(rows,[])
        self.assertEqual(browser.click_count,0)
        self.assertIn('ekp_unexpected_redirect',str(report['errors']))

    async def test_final_catalog_alias_obeys_its_robots_rule(self):
        rows, report, browser = await self.walk([html_page(card())],
            configure=lambda p:setattr(p,'url',ekp.CATALOG_URLS[1]),
            policy='User-agent: *\nDisallow: /capabilities/loyalty/tiles\n')
        self.assertEqual(rows,[])
        self.assertIn('robots_disallow',str(report['errors']))
        self.assertEqual(browser.click_count,0)

    async def test_robots_interval_applies_before_every_ui_request(self):
        a,b,c = card('1'),card('2'),card('3')
        _,_,browser = await self.walk([html_page(a),html_page(a+b),html_page(a+b+c)],interval=7)
        self.assertEqual(browser.click_count,2)
        self.assertTrue(all(sum(delays)>=7 for delays in browser.click_delays))

    async def test_foreign_redirect_while_inspecting_controls_never_clicks(self):
        rows,report,browser = await self.walk([html_page(card('1')),html_page(card('1')+card('2'))],
            configure=lambda p:setattr(p,'on_control',lambda p:setattr(p,'url','https://foreign.example/')))
        self.assertEqual(len(rows),1)
        self.assertEqual(browser.click_count,0)
        self.assertIn('ekp_unexpected_redirect',str(report['errors']))

    async def test_api_error_while_inspecting_controls_never_clicks(self):
        rows,report,browser = await self.walk([html_page(card('1')),html_page(card('1')+card('2'))],
            configure=lambda p:setattr(p,'on_control',lambda p:p.emit(status=429,url='https://ekp.spb.ru/api/portal/loyalty/partners',is_navigation=False)))
        self.assertEqual(len(rows),1)
        self.assertEqual(browser.click_count,0)
        self.assertIn('http_429',str(report['errors']))

    async def test_source_deadline_preserves_read_rows(self):
        rows,report,browser = await self.walk([html_page(card('1')),html_page(card('1')+card('2'))],
            configure=lambda p:setattr(p,'next_page_error',RuntimeError('source_time_budget_reached')))
        self.assertEqual(len(rows),1)
        self.assertIn('source_time_budget_reached',str(report['errors']))

    async def test_ambiguous_load_more_does_not_guess_a_button(self):
        rows,report,browser = await self.walk([html_page(card('1')),html_page(card('1')+card('2'))],
            configure=lambda p:setattr(p,'control_count',2))
        self.assertEqual(len(rows),1)
        self.assertEqual(browser.click_count,0)
        self.assertFalse(json.loads(report['coverage'])['full_catalog_complete'])


class RoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_dispatcher_uses_real_ekp_entrypoint_not_generic_probe(self):
        import collect_normalized as collect
        cfg = {'id':'ekp','name':'ЕКП — каталог','url':ekp.ROOT,'mode':'probe'}
        async def entry(cfg, report, now, limit):
            parsed=ekp.parse_catalog(html_page(card()),ekp.ROOT)
            rows=[ekp.preview_record(parsed['cards'][0],now,parsed['page_sha256'])]
            report['discovered']=len(rows)
            report['coverage']='synthetic'
            report['errors'].append({'phase':'coverage','reason':'preview_only'})
            return rows
        with patch.object(collect,'collect_ekp',side_effect=entry) as call:
            report,rows=await collect.one(None,cfg,NOW,5)
        call.assert_awaited_once()
        self.assertEqual(report['status'],'partial')
        self.assertEqual(report['normalized'],1)
        self.assertEqual(rows[0]['record_kind'],'source_observation')

    async def test_robots_failure_never_enters_catalog(self):
        @asynccontextmanager
        async def session():
            yield object(),object()
        with patch('installed_browser.installed_chrome',session),\
             patch.object(PublicSource,'robots',new=AsyncMock(side_effect=RuntimeError('robots_disallow'))),\
             patch.object(ekp,'walk_catalog',new=AsyncMock()) as walk:
            with self.assertRaisesRegex(RuntimeError,'robots_disallow'):
                await ekp.collect_ekp({'id':'ekp','url':ekp.ROOT},{'errors':[]},NOW,10)
            walk.assert_not_awaited()

if __name__=='__main__':unittest.main()
