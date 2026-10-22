"""Share only a successful policy read within one anonymous browser run."""
import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
sys.path.insert(0,str(Path(__file__).parents[1]))
from public_transport import PublicSource, RobotsCache
from test_robots_response_semantics import Response, RULES

class RunCacheTests(unittest.IsolatedAsyncioTestCase):
    def client(self, browser, response, host='example.com'):
        client=PublicSource(browser,'https://'+host+'/catalog')
        client.context=SimpleNamespace(request=SimpleNamespace(get=AsyncMock(return_value=response)))
        client.navigate=AsyncMock(side_effect=AssertionError('unexpected browser request'))
        return client

    async def test_parallel_sources_fetch_policy_once(self):
        browser=SimpleNamespace(_loyalty_robots_cache=RobotsCache())
        first=self.client(browser,Response(200,RULES))
        second=self.client(browser,Response(503))
        await asyncio.gather(first.robots(),second.robots())
        self.assertEqual(first.context.request.get.await_count+second.context.request.get.await_count,1)
        self.assertEqual(second.robots_info['method'],'run_cache')
        self.assertIs(first.lock,second.lock)  # Shared pacing, not just a shared policy.
        self.assertGreaterEqual(second.request_interval,2)
        with self.assertRaisesRegex(RuntimeError,'robots_disallow'):
            second.check_url('https://example.com/private/secret')

    async def test_failed_policy_does_not_become_cached_permission(self):
        browser=SimpleNamespace(_loyalty_robots_cache=RobotsCache())
        first=self.client(browser,Response(429))
        second=self.client(browser,Response(200,RULES))
        with self.assertRaisesRegex(RuntimeError,'robots_http_429'):await first.robots()
        self.assertIsNone(first.policy)
        await second.robots()
        second.context.request.get.assert_awaited_once()
        with self.assertRaisesRegex(RuntimeError,'robots_disallow'):
            second.check_url('https://example.com/private/secret')

    async def test_expiry_and_browser_run_boundaries_require_fresh_read(self):
        clock=[0.0]
        browser=SimpleNamespace(_loyalty_robots_cache=RobotsCache(ttl=5,clock=lambda:clock[0]))
        first=self.client(browser,Response(200,RULES));await first.robots()
        clock[0]=6
        second=self.client(browser,Response(200,'User-agent: *\nDisallow: /'))
        await second.robots();second.context.request.get.assert_awaited_once()
        with self.assertRaisesRegex(RuntimeError,'robots_disallow'):second.check_url('https://example.com/catalog')
        third=self.client(SimpleNamespace(_loyalty_robots_cache=RobotsCache()),Response(200,RULES))
        await third.robots();third.context.request.get.assert_awaited_once()

    async def test_cache_does_not_cross_origins_or_replace_target_refusal(self):
        browser=SimpleNamespace(_loyalty_robots_cache=RobotsCache())
        first=self.client(browser,Response(200,RULES));await first.robots()
        second=self.client(browser,Response(200,'User-agent: *\nDisallow: /',url='https://other.example/robots.txt'),host='other.example')
        await second.robots();second.context.request.get.assert_awaited_once()
        self.assertIsNot(first.lock,second.lock)
        from public_transport import check_response
        with self.assertRaisesRegex(RuntimeError,'http_403'):check_response(403,'Forbidden')

    async def test_tls_failure_is_not_retried_in_browser(self):
        from playwright.async_api import Error
        client=self.client(None,Response(200,RULES))
        client.context.request.get.side_effect=Error('net::ERR_CERT_AUTHORITY_INVALID')
        with self.assertRaises(Error):await client.robots()
        client.navigate.assert_not_awaited()
        self.assertIsNone(client.policy)

if __name__=='__main__':unittest.main()
