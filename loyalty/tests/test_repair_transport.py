"""Retry only transient reads; refusals, certificates and policy remain terminal."""
import sys, unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from playwright.async_api import TimeoutError as BrowserTimeout, Error as BrowserError
from protego import Protego
sys.path.insert(0, str(Path(__file__).parents[1]))
from public_transport import PublicSource, check_response

URL='https://medsi.ru/actions/aeroflot-bonus-v-klinikakh-medsi/'
class Response:
    def __init__(self,status=200,headers=None):
        self.status=status;self.url=URL;self.headers=headers or {}
    async def text(self):return '<main>МЕДСИ: 1 миля за 60 рублей</main>'
class Requests:
    def __init__(self,items):self.items=list(items);self.calls=[]
    async def fetch(self,url,**kwargs):
        self.calls.append((url,kwargs))
        obj=self.items.pop(0)
        if isinstance(obj,Exception):raise obj
        return obj
class RepairTests(unittest.IsolatedAsyncioTestCase):
    def client(self,items):
        c=PublicSource(None,URL);c.context=type('Context',(),{'request':Requests(items)})();c.policy=Protego.parse('');return c
    async def test_timed_out_public_get_recovers_without_mutating_request(self):
        c=self.client([BrowserTimeout('request timed out'),Response()])
        with patch('public_transport.asyncio.sleep',new_callable=AsyncMock):
            try:body=await c.read(URL)
            except BrowserTimeout:self.fail('Transient network timeout was not retried')
        self.assertIn('МЕДСИ',body);self.assertEqual(len(c.context.request.calls),2)
        self.assertEqual(c.context.request.calls[0],c.context.request.calls[1])
    async def test_reset_connection_is_retried_but_certificate_error_is_not(self):
        c=self.client([BrowserError('net::ERR_CONNECTION_RESET'),Response()])
        with patch('public_transport.asyncio.sleep',new_callable=AsyncMock):
            try:body=await c.read(URL)
            except BrowserError:self.fail('Reset connection was not retried')
        self.assertIn('МЕДСИ',body)
        c=self.client([BrowserError('net::ERR_CERT_DATE_INVALID'),Response()])
        with self.assertRaises(BrowserError):await c.read(URL)
        self.assertEqual(len(c.context.request.calls),1)
    async def test_persistent_timeout_is_bounded(self):
        c=self.client([BrowserTimeout('timeout')]*4)
        with patch('public_transport.asyncio.sleep',new_callable=AsyncMock):
            with self.assertRaises(BrowserTimeout):await c.read(URL)
        self.assertEqual(len(c.context.request.calls),3)
    def test_owner_restriction_in_russian_is_not_accepted_as_data(self):
        with self.assertRaises(RuntimeError):
            check_response(200,'<html><title>Ошибка</title><body>Доступ к запрашиваемому ресурсу ограничен владельцем сайта</body></html>')

class BrowserRepairTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_navigation_retries_without_losing_response_listener(self):
        from test_final_navigation import Page
        class TimeoutOncePage(Page):
            calls=0
            async def goto(self,url,**kw):
                self.calls+=1
                if self.calls==1:raise BrowserTimeout('timeout')
                return await super().goto(url,**kw)
        c=PublicSource(None,URL);c.page=TimeoutOncePage([(200,'<main>МЕДСИ</main>')],URL)
        with patch('public_transport.asyncio.sleep',new_callable=AsyncMock):
            try:status,body=await c.navigate(URL)
            except BrowserTimeout:self.fail('Browser timeout was not retried')
        self.assertEqual((status,body),(200,'<main>МЕДСИ</main>'))
        self.assertEqual(c.page.calls,2);self.assertEqual(c.page.listeners,{})
    async def test_browser_503_retry_after_does_not_trigger_navigation_retry(self):
        from test_final_navigation import Page
        class RetryAfterPage(Page):
            calls=0
            async def goto(self,url,**kw):
                self.calls+=1;r=await super().goto(url,**kw);r.headers={'retry-after':'120'};return r
        c=PublicSource(None,URL);c.page=RetryAfterPage([(503,'<main>busy</main>')],URL)
        status,_=await c.navigate(URL)
        self.assertEqual(status,503);self.assertEqual(c.page.calls,1)
