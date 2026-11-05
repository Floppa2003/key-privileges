"""Anonymous same-origin reads, finite timeouts, rate limits and challenge checks."""
from __future__ import annotations
import asyncio
import re
import time
from contextlib import contextmanager
from urllib.parse import urljoin, urlsplit
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
        self.source_url = url
        self.context=None;self.page=None;self.lock=asyncio.Lock();self.request_interval=0.25
        self._document_response = None
        self._verified_transport = None

    async def __aenter__(self):
        # Shared pacing remains independent of any auxiliary source file.
        locks=getattr(self.browser,'_loyalty_read_locks',None)
        if locks is not None:self.lock=locks.setdefault(self.host,asyncio.Lock())
        from capture_tls import profile_for, VerifiedBrowserTransport
        profile = profile_for(self.source_url)
        try:
            if profile:
                self._verified_transport = VerifiedBrowserTransport(profile, getattr(self, 'deadline', time.monotonic() + 210))
                await self._verified_transport.start()
            self.context=await self.browser.new_context(locale='ru-RU', **({'service_workers': 'block'} if profile else {}))
            if self._verified_transport:
                await self.context.route('**/*', self._verified_transport.route)
            self.page=await self.context.new_page()
            return self
        except BaseException:
            await self.__aexit__(None, None, None)
            raise

    async def __aexit__(self,*_):
        try:
            if self.context:await self.context.close()
        finally:
            if self._verified_transport:
                await self._verified_transport.close()

    async def finish_capture(self):
        if self._verified_transport:
            await self._verified_transport.finish()
            return self._verified_transport.evidence()
        return None

    def capture_transport_evidence(self):
        """Return acquired receipts even after a failed or cancelled capture."""
        return self._verified_transport.evidence() if self._verified_transport else None

    async def navigate(self, url: str, *, ready_selector=None) -> tuple[int, str]:
        # Preserve the same anonymous context/URL. Only failed connections retry;
        # actual HTTP refusals and access challenges remain terminal for this read.
        for attempt in range(3):
            try:
                return await self._navigate_once(url, **({'ready_selector': ready_selector} if ready_selector else {}))
            except Exception as exc:
                if self._verified_transport:self._verified_transport.check()
                if not retryable_read_error(exc) or attempt == 2:
                    raise
                await asyncio.sleep(max(self.request_interval, 2 ** attempt))
        raise AssertionError('unreachable navigation retry state')

    @contextmanager
    def observe_navigation(self, *, include_current=False):
        """Keep status evidence for automatic main-document replacements."""
        latest = [self._document_response] if include_current and self._document_response else []
        def observe(response):
            request = response.request
            if request.is_navigation_request() and request.frame == self.page.main_frame:
                latest.append(response)
        self.page.on('response', observe)
        try:
            yield latest
        finally:
            self.page.remove_listener('response', observe)

    async def document_content(self, latest) -> tuple[int, str]:
        """Retry only a DOM read interrupted by an already running navigation.

        The response listener must span the read. A fresh status and URL are
        checked after every wait; no GET is replayed and no refusal is retried.
        """
        for attempt in range(3):
            if not latest:
                raise RuntimeError('missing_navigation_response')
            final, url = latest[-1], self.page.url
            if not allowed_request(final.url, self.host) or not allowed_request(url, self.host):
                raise RuntimeError('unexpected_redirect')
            loaded = asyncio.get_running_loop().create_future()
            def on_loaded(*_, pending=loaded):
                if not pending.done():
                    pending.set_result(None)
            # Register before content(): the new event may happen during the
            # failing read. wait_for_load_state alone can return the old state.
            self.page.on('domcontentloaded', on_loaded)
            try:
                try:
                    body = await self.page.content()
                except BrowserError as exc:
                    if 'Unable to retrieve content because the page is navigating and changing the content' not in str(exc):
                        raise
                else:
                    if not allowed_request(latest[-1].url, self.host) or not allowed_request(self.page.url, self.host):
                        raise RuntimeError('unexpected_redirect')
                    if latest[-1] is final and self.page.url == url:
                        self._document_response = final
                        return final.status, body
                if attempt == 2:
                    break
                try:
                    await asyncio.wait_for(loaded, timeout=10)
                except asyncio.TimeoutError:
                    break
            finally:
                self.page.remove_listener('domcontentloaded', on_loaded)
                if not loaded.done():
                    loaded.cancel()
        # Do not let navigate() treat a moving DOM as a transport timeout and
        # start the URL again. Persistent navigation remains an explicit failure.
        raise ParseError('page_navigation_unstable')

    async def _navigate_once(self, url: str, *, ready_selector=None) -> tuple[int, str]:
        """Observe the final main document; never click or solve access challenges."""
        if not allowed_request(url, self.host):
            raise RuntimeError('request_outside_public_source')
        with self.observe_navigation() as latest:
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
            status, body = await self.document_content(latest)
            if ready_selector:
                # Fail on refusals before waiting, then re-check the final main
                # document: hydration can coincide with a redirect or an error.
                check_response(status, body)
                try:
                    await self.page.wait_for_function(CONTENT_READY_JS, arg=ready_selector, timeout=10000)
                except BrowserTimeout:
                    status, body = await self.document_content(latest)
                    check_response(status, body)
                    raise ParseError('page_content_not_ready',
                                     selector=', '.join(ready_selector) if isinstance(ready_selector, list) else ready_selector) from None
                status, body = await self.document_content(latest)
                check_response(status, body)
            return status, body


    def check_url(self,url):
        if not allowed_request(url,self.host):
            raise RuntimeError('request_outside_public_source')

    async def fetch_read(self,url,**kwargs):
        # Only GETs / the validated read-only catalog POST reach this helper.
        # Never retry authorization, CAPTCHA or rate-limit responses.
        if self._verified_transport:
            return await self._verified_transport.fetch(url, method=kwargs.get('method', 'GET'))
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
            seen = set()
            for _ in range(6):
                if url in seen:
                    raise RuntimeError('pdf_redirect_limit')
                seen.add(url)
                # Validate each Location before following it, including for
                # extensionless browser downloads. Never fetch a foreign/login URL.
                response=await self.fetch_read(url,method='GET',max_redirects=0)
                if response.status not in (301,302,303,307,308):
                    break
                location = response.headers.get('location')
                if not location:
                    raise RuntimeError('pdf_redirect_missing_location')
                url = urljoin(response.url, location)
                if not allowed_request(url, self.host):
                    raise RuntimeError('unexpected_redirect')
            else:
                raise RuntimeError('pdf_redirect_limit')
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
