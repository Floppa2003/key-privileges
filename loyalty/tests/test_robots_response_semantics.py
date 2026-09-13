"""Protocol status is not target authorization. Test the real PublicSource seam."""
import sys, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
sys.path.insert(0,str(Path(__file__).parents[1]))
from public_transport import PublicSource, check_response

URL='https://example.com/robots.txt'
RULES='User-agent: *\nDisallow: /private/\nAllow: /private/public/\nCrawl-delay: 2\n'
class Response:
    def __init__(self,status,body='',headers=None,url=URL):
        self.status,self._body,self.headers,self.url=status,body,headers or {},url
    async def text(self): return self._body

class RobotsResponseTests(unittest.IsolatedAsyncioTestCase):
    def client(self,response):
        c=PublicSource(None,'https://example.com/catalog')
        c.context=SimpleNamespace(request=SimpleNamespace(get=AsyncMock(return_value=response)))
        c.navigate=AsyncMock(side_effect=AssertionError('unnecessary browser robots fetch'))
        return c
    async def test_403_is_missing_robots_not_a_sitewide_denial(self):
        c=self.client(Response(403,'<title>Forbidden</title>'))
        await c.robots(); c.check_url('https://example.com/catalog')
        c.navigate.assert_not_awaited()
    async def test_other_4xx_are_missing_robots_except_rate_limit(self):
        for status in (400,401,404,410,451):
            c=self.client(Response(status,'Not found'));await c.robots();c.check_url('https://example.com/catalog')
            c.navigate.assert_not_awaited()
    async def test_204_is_an_empty_rule_set(self):
        c=self.client(Response(204));await c.robots();c.check_url('https://example.com/catalog')
    async def test_429_does_not_retry_in_a_browser(self):
        c=self.client(Response(429))
        with self.assertRaisesRegex(RuntimeError,'robots_http_429'):await c.robots()
        c.navigate.assert_not_awaited();self.assertIsNone(c.policy)
    async def test_retry_after_remains_a_stop_even_with_4xx(self):
        c=self.client(Response(403,headers={'retry-after':'120'}))
        with self.assertRaisesRegex(RuntimeError,'robots_retry_after'):await c.robots()
        c.navigate.assert_not_awaited()
    async def test_valid_robots_paths_do_not_trigger_captcha_or_forbidden_filter(self):
        c=self.client(Response(200,'User-agent: *\nDisallow: /captcha/\nDisallow: /forbidden/\n'))
        await c.robots();c.check_url('https://example.com/catalog')
        with self.assertRaisesRegex(RuntimeError,'robots_disallow'):c.check_url('https://example.com/captcha/x')
    async def test_html_wrapper_with_real_rules_is_parsed(self):
        c=self.client(Response(200,'<!DOCTYPE html><html><body><pre>'+RULES+'</pre></body></html>'))
        await c.robots();c.check_url('https://example.com/private/public/x')
        with self.assertRaisesRegex(RuntimeError,'robots_disallow'):c.check_url('https://example.com/private/x')
        self.assertGreaterEqual(c.request_interval,2)
    async def test_invalid_html_is_not_permission_to_crawl(self):
        c=self.client(Response(200,'<html><title>Welcome</title><body>Home</body></html>'))
        with self.assertRaisesRegex(RuntimeError,'robots_not_readable'):await c.robots()
        self.assertIsNone(c.policy)
    async def test_200_owner_denial_is_not_empty_robots(self):
        c=self.client(Response(200,'<html><body>Доступ к сайту ограничен владельцем сайта</body></html>'))
        with self.assertRaisesRegex(RuntimeError,'robots_not_readable'):await c.robots()
    async def test_5xx_and_network_failure_still_fail_closed(self):
        for response in (Response(503),Response(500)):
            c=self.client(response);c.navigate=AsyncMock(return_value=(response.status,'Unavailable'))
            c.page=SimpleNamespace(locator=lambda _:SimpleNamespace(inner_text=AsyncMock(return_value='Unavailable')))
            with self.assertRaisesRegex(RuntimeError,'robots_http_50'):await c.robots()
            self.assertIsNone(c.policy)
    async def test_cross_origin_robots_redirect_is_not_trusted(self):
        c=self.client(Response(200,RULES,url='https://evil.example/robots.txt'))
        with self.assertRaisesRegex(RuntimeError,'robots_unexpected_redirect'):await c.robots()
    def test_target_403_is_not_reinterpreted_as_available(self):
        with self.assertRaisesRegex(RuntimeError,'http_403'):check_response(403,'Forbidden')

if __name__=='__main__': unittest.main()
