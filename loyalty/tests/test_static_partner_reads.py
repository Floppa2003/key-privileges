"""Replay original static partner responses through the production collector."""
import contextlib
import hashlib
import io
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from bs4 import BeautifulSoup

sys.path[:0] = [str(Path(__file__).parents[1]), str(Path(__file__).parent)]
import collect_normalized as collector
from public_transport import CONTENT_READY_JS
from test_html_hydration import HydratingPage

NOW = '2026-11-05T10:34:27+00:00'
FIXTURES = {
    'af_istochnik': 'istochnik-aeroflot-20261105',
    'ural_gloria_rules': 'gloria-krylya-20261105',
}


def source_config(source_id):
    configs = json.loads((Path(__file__).parents[1] / 'sources_normalized.json').read_text())
    return next(cfg for cfg in configs if cfg['id'] == source_id)


def original_html(source_id):
    root = Path(__file__).with_name('fixtures_live')
    stem = FIXTURES[source_id]
    provenance = json.loads((root / (stem + '.provenance.json')).read_text())
    raw = (root / (stem + '.html')).read_bytes()
    if (hashlib.sha256(raw).hexdigest() != provenance['fixture_sha256']
            or len(raw) != provenance['bytes']
            or provenance['url'] != source_config(source_id)['url']):
        raise AssertionError('Original source fixture identity changed')
    return raw.decode('utf-8')


class BrowserFixture:
    """Only browser/network I/O is replaced; PublicSource and parsers stay real."""
    def __init__(self, url, body, *, status=200, response_url=None, page=None):
        self.page = page if page is not None else SimpleNamespace(
            goto=AsyncMock(side_effect=AssertionError('Unexpected rendered navigation')),
            on=Mock(), remove_listener=Mock(), main_frame=object())
        response = SimpleNamespace(status=status, url=response_url or url, headers={},
                                   text=AsyncMock(return_value=body))
        self.request = SimpleNamespace(fetch=AsyncMock(return_value=response))
        self.context = SimpleNamespace(request=self.request,
                                       new_page=AsyncMock(return_value=self.page),
                                       close=AsyncMock())
        self.new_context = AsyncMock(return_value=self.context)


class StaticPartnerReadTests(unittest.IsolatedAsyncioTestCase):
    async def collect(self, source_id, *, body=None, status=200, response_url=None,
                      page=None, cfg=None):
        cfg = source_config(source_id) if cfg is None else cfg
        body = original_html(source_id) if body is None else body
        browser = BrowserFixture(cfg['url'], body, status=status,
                                 response_url=response_url, page=page)
        with contextlib.redirect_stdout(io.StringIO()):
            report, rows = await collector.one(browser, cfg, NOW, 500)
        browser.context.close.assert_awaited_once()
        return report, rows, browser

    def assert_http_read(self, browser, source_id):
        browser.request.fetch.assert_awaited_once_with(
            source_config(source_id)['url'], timeout=20000, method='GET')
        browser.page.goto.assert_not_awaited()

    async def test_istochnik_original_http_html_yields_owned_miles_rule(self):
        report, rows, browser = await self.collect('af_istochnik')
        self.assertEqual(report['status'], 'ok', report['errors'])
        self.assertEqual((report['normalized'], len(rows)), (1, 1))
        self.assertEqual(report['errors'], [])
        row, = rows
        self.assertEqual(row['source_id'], 'af_istochnik')
        self.assertEqual(row['partner_name'], 'Источник Кисловодск')
        self.assertEqual(row['source_url'], source_config('af_istochnik')['url'])
        self.assertEqual([(r['kind'], r['value'], r['unit'], r['basis_amount'], r['basis_unit'])
                          for r in row['rates']], [('miles', '1', 'miles', '80', 'RUB')])
        self.assert_http_read(browser, 'af_istochnik')

    async def test_gloria_original_http_html_keeps_card_scoped_table(self):
        report, rows, browser = await self.collect('ural_gloria_rules')
        self.assertEqual(report['status'], 'ok', report['errors'])
        self.assertEqual((report['normalized'], len(rows)), (1, 1))
        self.assertEqual(report['errors'], [])
        row, = rows
        self.assertEqual(row['source_id'], 'ural_gloria_rules')
        self.assertEqual(row['partner_name'], 'GLORIA')
        self.assertEqual(row['record_kind'], 'program_rules')
        self.assertEqual(row['source_url'], source_config('ural_gloria_rules')['url'])
        table = row['details']['table_benefits']
        self.assertEqual(table['issues'], [])
        self.assertEqual([(c['scope']['kind'], c['scope']['value'], c['rate']['value'])
                          for c in table['components']],
                         [('card_type', '«Синяя»', '5'), ('card_type', '«Серебряная»', '7'),
                          ('card_type', '«Золотая»', '10')])
        self.assertEqual([(r['kind'], r['value'], r['qualifier']) for r in row['rates']],
                         [('discount', '10', 'up_to')])
        self.assert_http_read(browser, 'ural_gloria_rules')

    async def test_http_refusal_does_not_turn_original_offer_html_into_success(self):
        for source_id in FIXTURES:
            with self.subTest(source_id=source_id):
                report, rows, browser = await self.collect(source_id, status=403)
                self.assertEqual(rows, [])
                self.assertEqual(report['status'], 'failed')
                self.assertEqual(report['errors'][0]['reason'], 'http_403')
                self.assertEqual(report['errors'][0]['category'], 'access_denied')
                self.assert_http_read(browser, source_id)

    async def test_challenge_remains_failed_without_browser_fallback(self):
        for source_id in FIXTURES:
            with self.subTest(source_id=source_id):
                report, rows, browser = await self.collect(
                    source_id, body='<html><title>Access denied</title></html>')
                self.assertEqual(rows, [])
                self.assertEqual(report['status'], 'failed')
                self.assertEqual(report['errors'][0]['reason'], 'access_challenge')
                self.assert_http_read(browser, source_id)

    async def test_foreign_redirect_remains_failed_without_browser_fallback(self):
        for source_id in FIXTURES:
            with self.subTest(source_id=source_id):
                report, rows, browser = await self.collect(
                    source_id, response_url='https://other.example/offer')
                self.assertEqual(rows, [])
                self.assertEqual(report['status'], 'failed')
                self.assertEqual(report['errors'][0]['reason'], 'unexpected_redirect')
                self.assert_http_read(browser, source_id)

    async def test_source_owned_scope_is_still_required_in_raw_responses(self):
        cases = [('af_istochnik', '.block_image_text .block--content',
                  'partner_content_selector_missing'),
                 ('ural_gloria_rules', '.spb-asset-content:has(table)',
                  'known_rule_scope_missing_or_ambiguous')]
        for source_id, selector, reason in cases:
            with self.subTest(source_id=source_id):
                soup = BeautifulSoup(original_html(source_id), 'html.parser')
                for node in soup.select(selector):
                    node.decompose()
                report, rows, browser = await self.collect(source_id, body=str(soup))
                self.assertEqual(rows, [])
                self.assertEqual(report['status'], 'failed')
                error, = report['errors']
                self.assertEqual((error['reason'], error.get('selector'), error.get('matches')),
                                 (reason, selector, 0))
                self.assert_http_read(browser, source_id)

    async def test_html_without_override_still_renders(self):
        cfg = source_config('af_istochnik')
        cfg.pop('render', None)
        raw = original_html('af_istochnik')
        page = HydratingPage(initial=raw, hydrated=raw, final_url=cfg['url'])
        report, rows, browser = await self.collect('af_istochnik', cfg=cfg, page=page)
        self.assertEqual(report['status'], 'ok', report['errors'])
        self.assertEqual(len(rows), 1)
        self.assertEqual(page.gotos, 1)
        self.assertEqual(page.ready_calls, [])
        browser.request.fetch.assert_not_awaited()

    async def test_other_html_source_keeps_real_structural_readiness(self):
        cfg = source_config('t2_selection')
        page = HydratingPage()
        report, rows, browser = await self.collect('t2_selection', body='', page=page)
        self.assertEqual(report['status'], 'ok', report['errors'])
        self.assertEqual([r['source_id'] for r in rows], ['t2_selection'])
        self.assertEqual(page.gotos, 1)
        self.assertEqual(page.ready_calls, [(CONTENT_READY_JS, cfg['ready_selector'], 10000)])
        browser.request.fetch.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
