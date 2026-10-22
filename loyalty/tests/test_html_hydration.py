"""Replay the actual T2 HTTP-200 shell -> offer hydration at the collector seam."""
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup
from protego import Protego
from playwright.async_api import TimeoutError as BrowserTimeout

sys.path[:0] = [str(Path(__file__).parents[1]), str(Path(__file__).parent)]
import collect_normalized as collector
import public_transport as transport
from source_diagnostics import ParseError, ReadError
from test_final_navigation import Response

URL = 'https://msk.t2.ru/tariff/premium'
SELECTOR = '.tariff-detail-t2-subscription-premium-card'
NOW = '2026-10-23T00:00:00+00:00'
# Minimal DOM from run 39864088087: successful initial document had no body.
SHELL = '<html><head><title>Тариф Premium</title></head></html>'
READY = '''<html><body>
<div class="tariff-detail-t2-subscription-premium-card"><h5>МЕЖДУНАРОДНЫЙ РОУМИНГ</h5><p class="card-kit-t2__text">Интернет за границей</p></div>
<div class="tariff-detail-t2-subscription-premium-card"><h5>УЧАСТИЕ В ПРОГРАММЕ T2 SELECTION</h5><p class="card-kit-t2__text">Скидки в сервисах Яндекса, приоритетное обслуживание в салонах T2 и по выделенной линии 711, а также другие преимущества программы</p></div>
</body></html>'''


class HydratingPage:
    def __init__(self, initial=SHELL, hydrated=READY, status=200, final_status=None, final_url=URL):
        self.url = URL
        self.main_frame = object()
        self.listeners = {}
        self.initial = initial
        self.hydrated = hydrated
        self.status = status
        self.final_status = final_status
        self.final_url = final_url
        self.body = initial
        self.gotos = 0
        self.ready_calls = []

    def on(self, event, callback):
        self.listeners[event] = callback

    def remove_listener(self, event, callback):
        self.listeners.pop(event, None)

    def emit(self, status, url):
        r = Response(self, status, url)
        if 'response' in self.listeners:
            self.listeners['response'](r)
        return r

    async def goto(self, url, **kwargs):
        self.gotos += 1
        self.url = url
        self.body = self.initial
        return self.emit(self.status, url)

    async def wait_for_timeout(self, milliseconds):
        pass

    async def wait_for_function(self, expression, *, arg, timeout):
        self.ready_calls.append((expression, arg, timeout))
        if self.hydrated is None:
            raise BrowserTimeout('fixture content never hydrated')
        self.body = self.hydrated
        self.url = self.final_url
        if self.final_status is not None:
            self.emit(self.final_status, self.url)
        selectors = arg if isinstance(arg, list) else [arg]
        for selector in selectors:
            if not any(n.get_text(strip=True) for n in BeautifulSoup(self.body, 'html.parser').select(selector)):
                raise BrowserTimeout('fixture lacks nonempty selected content')

    async def content(self):
        return self.body


class ReplaySource(transport.PublicSource):
    async def __aenter__(self):
        self.page = self.browser
        self.request_interval = 0
        return self

    async def robots(self):
        self.policy = Protego.parse('User-agent: *\nAllow: /')


class HydrationTests(unittest.IsolatedAsyncioTestCase):
    def client(self, page):
        c = transport.PublicSource(None, URL)
        c.page = page
        c.request_interval = 0
        c.policy = Protego.parse('User-agent: *\nAllow: /')
        return c

    async def test_real_collector_waits_for_t2_offer_not_just_http_200(self):
        cfg = next(c for c in json.loads((Path(__file__).parents[1]/'sources_normalized.json').read_text())
                   if c['id'] == 't2_selection')
        # Set the proposed configuration explicitly so the old call site really
        # goes red on the missing-card error, not on a missing config key.
        cfg['ready_selector'] = SELECTOR
        page = HydratingPage()
        with patch.object(collector, 'PublicSource', ReplaySource):
            report, rows = await collector.one(page, cfg, NOW, 500)
        self.assertEqual(report['status'], 'ok', report['errors'])
        self.assertEqual(len(rows), 1)
        self.assertIn('711', rows[0]['conditions_text'] + rows[0]['benefit_text'])
        self.assertNotIn('Интернет за границей', rows[0]['benefit_text'])
        self.assertEqual(len(page.ready_calls), 1)
        self.assertEqual(page.gotos, 1)
        self.assertEqual(page.listeners, {})

    async def test_timeout_is_bounded_and_does_not_replay_navigation(self):
        page = HydratingPage(hydrated=None)
        with self.assertRaisesRegex(ParseError, 'page_content_not_ready'):
            await self.client(page).read(URL, render=True, ready_selector=SELECTOR)
        self.assertEqual(page.gotos, 1)
        self.assertEqual(page.ready_calls[0][2], 10000)
        self.assertEqual(page.listeners, {})

    async def test_http_refusal_does_not_wait_for_hydration(self):
        for status in (401, 403, 429):
            with self.subTest(status=status):
                page = HydratingPage(status=status)
                with self.assertRaises(ReadError):
                    await self.client(page).read(URL, render=True, ready_selector=SELECTOR)
                self.assertEqual(page.ready_calls, [])
                self.assertEqual(page.gotos, 1)

    async def test_challenge_does_not_wait_for_hydration(self):
        page = HydratingPage(initial='<title>Access denied</title>')
        with self.assertRaises(ReadError):
            await self.client(page).read(URL, render=True, ready_selector=SELECTOR)
        self.assertEqual(page.ready_calls, [])

    async def test_redirect_during_hydration_stays_rejected(self):
        for url in ('https://other.test/', 'https://msk.t2.ru/login/'):
            with self.subTest(url=url):
                page = HydratingPage(final_status=200, final_url=url)
                with self.assertRaisesRegex(RuntimeError, 'unexpected_redirect'):
                    await self.client(page).read(URL, render=True, ready_selector=SELECTOR)
                self.assertEqual(page.gotos, 1)

    async def test_new_failed_status_cannot_be_masked_by_offer_dom(self):
        page = HydratingPage(final_status=503)
        with self.assertRaisesRegex(ReadError, 'http_503'):
            await self.client(page).read(URL, render=True, ready_selector=SELECTOR)
        self.assertEqual(page.gotos, 1)

    async def test_multiple_required_blocks_must_all_be_ready(self):
        page = HydratingPage(hydrated='<main>ready</main><section></section>')
        with self.assertRaisesRegex(ParseError, 'page_content_not_ready'):
            await self.client(page).read(URL, render=True, ready_selector=['main', 'section'])
        self.assertEqual(page.gotos, 1)

    async def test_ready_selector_configuration_reaches_rule_reader(self):
        from unittest.mock import AsyncMock
        from known_rules import collect_known_rules, CONFIG
        cfg = next(c for c in json.loads((Path(__file__).parents[1]/'sources_normalized.json').read_text())
                   if c['id'] == 't2_mixx_rules')
        client = self.client(HydratingPage())
        client.read = AsyncMock(return_value='fixture')
        with patch('known_rules.parse_known_rule', return_value=[{}]):
            await collect_known_rules(client, cfg, {}, NOW, 500)
        client.read.assert_awaited_once_with(cfg['url'], render=True, ready_selector=CONFIG[cfg['id']]['selectors'])

    def test_missing_rule_scope_retains_selector_and_match_count(self):
        from known_rules import scoped, CONFIG
        from source_diagnostics import error_record
        with self.assertRaises(ParseError) as caught:
            scoped('t2_mixx_rules', SHELL, CONFIG['t2_mixx_rules']['url'])
        error = error_record(caught.exception, 'parse')
        self.assertEqual(error['reason'], 'known_rule_scope_missing_or_ambiguous')
        self.assertEqual(error['matches'], 0)
        self.assertEqual(error['selector'], '.option-detail-t2-header-card')

    async def test_plain_navigation_does_not_wait_for_offer_selector(self):
        page = HydratingPage()
        await self.client(page).navigate(URL)
        self.assertEqual(page.ready_calls, [])

    async def test_ready_selector_requires_rendering(self):
        with self.assertRaisesRegex(ValueError, 'readiness_requires_render'):
            await self.client(HydratingPage()).read(URL, ready_selector=SELECTOR)

    def test_ready_predicate_waits_for_nonempty_text_without_specific_offer_values(self):
        expression = getattr(transport, 'CONTENT_READY_JS', None)
        self.assertIsNotNone(expression)
        script = '''const fn=eval('('+process.argv[1]+')');
for (const texts of [[],['   '],['Новый произвольный текст']]) {
  global.document={querySelectorAll:()=>texts.map(textContent=>({textContent}))};
  console.log(fn('.arbitrary'));
}
global.document={querySelectorAll:(s)=>s==='main' ? [{textContent:'ready'}] : []};
console.log(fn(['main','section']));'''
        result = subprocess.run(['node', '-e', script, expression], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.splitlines(), ['false', 'false', 'true', 'false'])


if __name__ == '__main__':
    unittest.main()
