"""Anonymous same-origin reads, finite timeouts, rate limits and challenge checks."""
from __future__ import annotations
import asyncio
import re
import time
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from model import clean_url
from normalized import BLOCKED
from source_diagnostics import ReadError, ParseError
from playwright.async_api import Error as BrowserError, TimeoutError as BrowserTimeout


# Structural readiness only: offer names, values and counts remain source data.
CONTENT_READY_JS = "selectors => (Array.isArray(selectors) ? selectors : [selectors]).every(selector => Array.from(document.querySelectorAll(selector)).some(n => (n.textContent || '').trim().length > 0))"

def retryable_read_error(exc: Exception) -> bool:
    """Transient transport failures only; never authentication, TLS or policy errors."""
    return isinstance(exc, (TimeoutError, BrowserTimeout)) or (
        isinstance(exc, BrowserError) and bool(re.search(
            r"net::ERR_(?:CONNECTION_TIMED_OUT|CONNECTION_RESET|NETWORK_CHANGED|EMPTY_RESPONSE)(?:\b|$)",
            str(exc))))


def allowed_request(url: str, host: str) -> bool:
    try:
        u=urlsplit(clean_url(url))
        if u.hostname==host=='www.gazprombank.ru' and u.path=='/personal/cards/7515685/' and not u.query:
            return True  # Reviewed anonymous product page, not a personal account.
        return u.hostname==host and not re.search(r'/(?:auth|login|personal|register|accept|activate|participate)(?:/|$)',u.path,re.I)
    except (ValueError,TypeError):
        return False


def check_response(status: int, body: str) -> None:
    if status>=400:
        raise ReadError(f'http_{status}',status=status,body=body)
    soup=BeautifulSoup(body,'html.parser') if body.lstrip().startswith('<') else None
    headline=soup.title.get_text(' ',strip=True) if soup and soup.title else ''
    leading=soup.get_text(' ',strip=True)[:350] if soup else body[:350]
    if BLOCKED.search(headline) or BLOCKED.search(leading) or re.search(
            r'доступ.{0,90}ограничен.{0,40}владельцем|доступ.{0,90}запрещ[её]н.{0,40}владельцем',
            leading, re.I):
        raise ReadError('access_challenge',status=status,body=body)


class PublicSource:
    def __init__(self,browser,url: str):
        self.browser=browser;self.host=urlsplit(url).hostname
        self.context=None;self.page=None;self.lock=asyncio.Lock();self.request_interval=0.25

    async def __aenter__(self):
        # Shared pacing remains independent of any auxiliary source file.
        locks=getattr(self.browser,'_loyalty_read_locks',None)
        if locks is not None:self.lock=locks.setdefault(self.host,asyncio.Lock())
        self.context=await self.browser.new_context(locale='ru-RU')
        self.page=await self.context.new_page()
        return self

    async def __aexit__(self,*_):
        if self.context:await self.context.close()

    async def navigate(self, url: str, *, ready_selector=None) -> tuple[int, str]:
        # Preserve the same anonymous context/URL. Only failed connections retry;
        # actual HTTP refusals and access challenges remain terminal for this read.
        for attempt in range(3):
            try:
                return await self._navigate_once(url, **({'ready_selector': ready_selector} if ready_selector else {}))
            except Exception as exc:
                if not retryable_read_error(exc) or attempt == 2:
                    raise
                await asyncio.sleep(max(self.request_interval, 2 ** attempt))
        raise AssertionError('unreachable navigation retry state')

    async def _navigate_once(self, url: str, *, ready_selector=None) -> tuple[int, str]:
        """Observe the final main document; never click or solve access challenges."""
        if not allowed_request(url, self.host):
            raise RuntimeError('request_outside_public_source')
        latest = []
        def observe(response):
            request = response.request
            if request.is_navigation_request() and request.frame == self.page.main_frame:
                latest.append(response)
        self.page.on('response', observe)
        try:
            initial = await self.page.goto(url, wait_until='domcontentloaded', timeout=30000)
            if not initial:
                raise RuntimeError('missing_navigation_response')
            if not latest:
                latest.append(initial)
            await self.page.wait_for_timeout(1200)
            # T2's ordinary page loader may replace an initial 503 with a successful
            # same-origin document. Waiting does not replay/solve its internal checks.
            for _ in range(12 if self.host in ('msk.t2.ru','spb.t2.ru') else 0):
                if latest[-1].status != 503 or getattr(latest[-1],'headers',{}).get('retry-after'):
                    break
                await self.page.wait_for_timeout(1000)
            final = latest[-1]
            if not allowed_request(final.url, self.host) or not allowed_request(self.page.url, self.host):
                raise RuntimeError('unexpected_redirect')
            body = await self.page.content()
            if ready_selector:
                # Fail on refusals before waiting, then re-check the final main
                # document: hydration can coincide with a redirect or an error.
                check_response(final.status, body)
                try:
                    await self.page.wait_for_function(CONTENT_READY_JS, arg=ready_selector, timeout=10000)
                except BrowserTimeout:
                    final = latest[-1]
                    if not allowed_request(final.url, self.host) or not allowed_request(self.page.url, self.host):
                        raise RuntimeError('unexpected_redirect')
                    body = await self.page.content()
                    check_response(final.status, body)
                    raise ParseError('page_content_not_ready',
                                     selector=', '.join(ready_selector) if isinstance(ready_selector, list) else ready_selector) from None
                final = latest[-1]
                if not allowed_request(final.url, self.host) or not allowed_request(self.page.url, self.host):
                    raise RuntimeError('unexpected_redirect')
                body = await self.page.content()
                check_response(final.status, body)
            return final.status, body
        finally:
            self.page.remove_listener('response', observe)


    def check_url(self,url):
        if not allowed_request(url,self.host):
            raise RuntimeError('request_outside_public_source')

    async def fetch_read(self,url,**kwargs):
        # Only GETs / the validated read-only catalog POST reach this helper.
        # Never retry authorization, CAPTCHA or rate-limit responses.
        for attempt in range(3):
            try:
                res=await self.context.request.fetch(url,timeout=20000,**kwargs)
            except Exception as exc:
                if not retryable_read_error(exc) or attempt == 2:
                    raise
                await asyncio.sleep(max(self.request_interval, 2 ** attempt))
                continue
            if not allowed_request(res.url,self.host):raise RuntimeError('unexpected_redirect')
            if res.status not in (502,503,504) or attempt==2 or res.headers.get('retry-after'):
                return res
            await asyncio.sleep(max(self.request_interval, 2**attempt))
        raise AssertionError('unreachable retry state')

    async def read(self,url: str,*,render=False,ready_selector=None) -> str:
        if ready_selector is not None:
            if not render:
                raise ValueError('readiness_requires_render')
            selectors = ready_selector if isinstance(ready_selector, list) else [ready_selector]
            if not 1 <= len(selectors) <= 20 or any(not isinstance(q, str) or not 1 <= len(q) <= 240 or '\n' in q for q in selectors):
                raise ValueError('invalid_readiness_selector')
        self.check_url(url)
        async with self.lock:
            await asyncio.sleep(self.request_interval)
            if render:
                status,body=await self.navigate(url, **({'ready_selector': ready_selector} if ready_selector else {}))
                check_response(status,body)
            else:
                res=await self.fetch_read(url,method='GET')
                if not allowed_request(res.url,self.host):raise RuntimeError('unexpected_redirect')
                body=await res.text();check_response(res.status,body)
            if len(body.encode())>6000000:raise RuntimeError('source_response_too_large')
            return body

    async def read_pdf(self, url: str) -> bytes:
        self.check_url(url)
        async with self.lock:
            await asyncio.sleep(self.request_interval)
            response=await self.fetch_read(url,method='GET')
            if response.status != 200:raise RuntimeError(f'http_{response.status}')
            data=await response.body()
            if len(data)>6000000:raise RuntimeError('source_response_too_large')
            if not data.startswith(b'%PDF-'):raise RuntimeError('not_a_pdf')
            return data

    async def json(self,url: str,*,method='GET',data=None,content_type=None):
        self.check_url(url)
        if method not in ('GET','POST') or (method=='POST' and not urlsplit(url).path.endswith('/promo/filter-json')):
            raise RuntimeError('non_catalog_post_refused')
        async with self.lock:
            await asyncio.sleep(self.request_interval)
            headers={'Content-Type':content_type} if content_type else {}
            res=await self.fetch_read(url,method=method,data=data,headers=headers)
            if not allowed_request(res.url,self.host):raise RuntimeError('unexpected_redirect')
            body=await res.text();check_response(res.status,body)
            if len(body.encode())>6000000:raise RuntimeError('source_response_too_large')
            return await res.json()
