"""Target reads do not depend on auxiliary crawl policies; real boundaries remain."""
import asyncio
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).parents[1]))
from public_transport import PublicSource, check_response
from recovered_sources import ScopedReader
from source_lifecycle import health_summary, health_passes

URL = 'https://example.com/catalog'

class DirectReadTests(unittest.IsolatedAsyncioTestCase):
    def client(self, status=200, body='<main>Скидка 10%</main>'):
        response = SimpleNamespace(status=status, url=URL, headers={}, text=AsyncMock(return_value=body))
        request = SimpleNamespace(fetch=AsyncMock(return_value=response),
                                  get=AsyncMock(side_effect=AssertionError('auxiliary GET')))
        c = PublicSource(None, URL)
        c.context = SimpleNamespace(request=request)
        c.request_interval = 0
        return c

    async def test_first_http_read_is_the_target_without_any_setup_document(self):
        c = self.client()
        self.assertIn('10%', await c.read(URL))
        c.context.request.get.assert_not_awaited()
        self.assertEqual(c.context.request.fetch.await_args.args, (URL,))
        self.assertFalse(hasattr(c, 'robots'))

    async def test_first_rendered_read_is_the_target(self):
        c = self.client()
        c.navigate = AsyncMock(return_value=(200, '<main>Условия</main>'))
        self.assertIn('Условия', await c.read(URL, render=True))
        c.navigate.assert_awaited_once_with(URL)
        c.context.request.get.assert_not_awaited()
        c.context.request.fetch.assert_not_awaited()

    async def test_target_refusal_is_not_reclassified_as_success(self):
        for status in (401,403,404,429,500):
            c = self.client(status)
            with self.subTest(status=status), self.assertRaisesRegex(RuntimeError, 'http_'+str(status)):
                await c.read(URL)
            c.context.request.get.assert_not_awaited()

    async def test_authenticated_or_foreign_urls_still_do_not_get_requested(self):
        c = self.client()
        for url in ('https://example.com/login', 'https://foreign.example/catalog'):
            with self.subTest(url=url), self.assertRaisesRegex(RuntimeError, 'outside_public_source'):
                await c.read(url)
        c.context.request.fetch.assert_not_awaited()

    async def test_browser_context_setup_shares_pacing_not_auxiliary_requests(self):
        contexts = [SimpleNamespace(new_page=AsyncMock(return_value=object()), close=AsyncMock()) for _ in range(3)]
        browser = SimpleNamespace(_loyalty_read_locks={}, new_context=AsyncMock(side_effect=contexts))
        async with PublicSource(browser, URL) as first, PublicSource(browser, URL) as second, PublicSource(browser, 'https://other.example/catalog') as third:
            self.assertIs(first.lock, second.lock)
            self.assertIsNot(first.lock, third.lock)
            self.assertGreaterEqual(first.request_interval, .25)
        for context in contexts: context.close.assert_awaited_once()

    def test_challenge_page_is_not_offer_content(self):
        with self.assertRaisesRegex(RuntimeError, 'access_challenge'):
            check_response(200, '<html><title>Access denied</title></html>')

    def test_scoped_http_reader_enters_without_auxiliary_request(self):
        import json
        cfg = next(x for x in json.loads((Path(__file__).parents[1]/'sources_normalized.json').read_text()) if x['id']=='loyals')
        reader = ScopedReader(cfg, {}, time.monotonic()+30)
        with patch.object(reader, '_get', side_effect=AssertionError('unexpected preflight read')) as get:
            with reader: pass
            get.assert_not_called()


class NonblockingDiagnosticsTests(unittest.TestCase):
    def bundle(self, sid='smartavia_rules', count=1, errors=None, status='ok'):
        return {'observed_at':'2026-10-23T12:00:00+00:00',
                'sources':[{'source_id':sid,'normalized':count,'status':status,'errors':errors or []}],
                'records':[{'source_id':sid} for _ in range(count)]}

    def test_access_probe_is_visible_but_not_an_extraction_blocker(self):
        health = health_summary(self.bundle('nordwind',0,[{'reason':'http_403'}],'failed'))
        self.assertFalse(health[0]['healthy'])
        self.assertEqual(health[0]['route_kind'],'access_probe')
        self.assertFalse(health[0]['blocking'])
        self.assertTrue(health_passes({'healthy':True},health))

    def test_partial_extraction_is_visible_and_keeps_usable_records(self):
        health = health_summary(self.bundle(errors=[{'reason':'detail_missing'}],status='partial'))
        self.assertFalse(health[0]['healthy'])
        self.assertFalse(health[0]['blocking'])
        self.assertEqual(health[0]['extraction_state'],'partial')
        self.assertTrue(health_passes({'healthy':True},health))

    def test_real_collector_with_no_data_still_blocks(self):
        health = health_summary(self.bundle(count=0,errors=[{'reason':'http_403'}],status='failed'))
        self.assertTrue(health[0]['blocking'])
        self.assertFalse(health_passes({'healthy':True},health))

    def test_corrupt_counts_and_incomplete_execution_still_block(self):
        bundle=self.bundle();bundle['sources'][0]['normalized']=2
        health=health_summary(bundle)
        self.assertTrue(health[0]['blocking'])
        self.assertFalse(health_passes({'healthy':True},health))
        self.assertFalse(health_passes({'healthy':False},health_summary(self.bundle())))

    def test_missing_probe_and_missing_collector_are_not_conflated(self):
        bundle={'observed_at':'2026-10-23T12:00:00+00:00','sources':[],'records':[]}
        health={x['source_id']:x for x in health_summary(bundle,expected_sources=['nordwind','smartavia_rules'])}
        self.assertFalse(health['nordwind']['blocking'])
        self.assertTrue(health['smartavia_rules']['blocking'])

if __name__ == '__main__': unittest.main()
