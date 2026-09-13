"""Anonymous same-origin reads, finite timeouts, robots and challenge checks."""
from __future__ import annotations
import asyncio
import re
from urllib.parse import urlsplit
from protego import Protego
from bs4 import BeautifulSoup
from model import clean_url
from normalized import BLOCKED
from playwright.async_api import Error as BrowserError, TimeoutError as BrowserTimeout


def retryable_read_error(exc: Exception) -> bool:
    """Transient transport failures only; never authentication, TLS or policy errors."""
    return isinstance(exc, (TimeoutError, BrowserTimeout)) or (
        isinstance(exc, BrowserError) and bool(re.search(
            r"net::ERR_(?:CONNECTION_TIMED_OUT|CONNECTION_RESET|NETWORK_CHANGED|EMPTY_RESPONSE)(?:\b|$)",
            str(exc))))



def allowed_request(url: str, host: str) -> bool:
    try:
        u=urlsplit(clean_url(url))
        return u.hostname==host and not re.search(r'/(?:auth|login|personal|register|accept|activate|participate)(?:/|$)',u.path,re.I)
    except (ValueError,TypeError):
        return False


def check_response(status: int, body: str) -> None:
    if status>=400:
        raise RuntimeError(f'http_{status}')
    soup=BeautifulSoup(body,'html.parser') if body.lstrip().startswith('<') else None
    headline=soup.title.get_text(' ',strip=True) if soup and soup.title else ''
    leading=soup.get_text(' ',strip=True)[:350] if soup else body[:350]
    if BLOCKED.search(headline) or BLOCKED.search(leading) or re.search(
            r'доступ.{0,90}ограничен.{0,40}владельцем|доступ.{0,90}запрещ[её]н.{0,40}владельцем',
            leading, re.I):
        raise RuntimeError('access_challenge')


def robots_document(status: int, body: str) -> tuple[str,str]:
    """Interpret robots only; never use this function for a target response."""
    if status==429:
        raise RuntimeError('robots_http_429')
    if 400<=status<500:
        return '', 'unavailable_4xx'
    if not 200<=status<300:
        raise RuntimeError(f'robots_http_{status}')
    if len(body.encode('utf-8'))>1024*1024:
        raise RuntimeError('robots_response_too_large')
    body='\n'.join(line for line in body.splitlines() if not line.lstrip().startswith('#'))
    # Some origins wrap actual rules in <pre>. Extract rules, not HTML tags.
    # An arbitrary home/challenge page still is not a robots rule set.
    if re.search(r'<(?:!doctype|html|head|body|pre)\b',body,re.I):
        soup=BeautifulSoup(body,'html.parser')
        title=soup.title.get_text(' ',strip=True) if soup.title else ''
        if BLOCKED.search(title):
            raise RuntimeError('robots_not_readable')
        for node in soup.select('script,style'):node.decompose()
        visible=soup.get_text('\n')
        if not re.search(r'^\s*user-agent\s*:',visible,re.I|re.M):
            raise RuntimeError('robots_not_readable')
        body=visible
    # Ignore challenge words when they are merely paths or comments in real
    # rules, e.g. Disallow: /captcha/ and Disallow: /forbidden/.
    directives=re.search(r'^\s*(?:user-agent|allow|disallow|sitemap)\s*:',body,re.I|re.M)
    if not directives and BLOCKED.search(body[:350]):
        raise RuntimeError('robots_not_readable')
    return body,'rules_loaded' if body.strip() else 'empty_2xx'


class PublicSource:
    def __init__(self,browser,url: str):
        self.browser=browser;self.host=urlsplit(url).hostname;self.policy=None
        self.context=None;self.page=None;self.lock=asyncio.Lock();self.request_interval=0.25

    async def __aenter__(self):
        self.context=await self.browser.new_context(locale='ru-RU')
        self.page=await self.context.new_page()
        return self

    async def __aexit__(self,*_):
        if self.context:await self.context.close()

    async def navigate(self, url: str) -> tuple[int, str]:
        # Preserve the same anonymous context/URL. Only failed connections retry;
        # actual HTTP refusals and access challenges remain terminal for this read.
        for attempt in range(3):
            try:
                return await self._navigate_once(url)
            except Exception as exc:
                if not retryable_read_error(exc) or attempt == 2:
                    raise
                await asyncio.sleep(max(self.request_interval, 2 ** attempt))
        raise AssertionError('unreachable navigation retry state')

    async def _navigate_once(self, url: str) -> tuple[int, str]:
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
            for _ in range(12 if self.host == 'msk.t2.ru' else 0):
                if latest[-1].status != 503:
                    break
                await self.page.wait_for_timeout(1000)
            final = latest[-1]
            if not allowed_request(final.url, self.host) or not allowed_request(self.page.url, self.host):
                raise RuntimeError('unexpected_redirect')
            return final.status, await self.page.content()
        finally:
            self.page.remove_listener('response', observe)

    async def robots(self):
        """RFC 9309: unavailable (4xx) is distinct from unreachable (5xx/network).

        A missing robots file is not a target-page authorization failure. Keep
        actual target responses, rate limits, and explicit rules independent.
        """
        url=f'https://{self.host}/robots.txt'
        self.policy=None
        self.robots_info={'state':'fetching','http_status':None,'method':'http'}
        try:
            res=await self.context.request.get(url,timeout=15000)
        except Exception:
            status=None;body='';headers={}
        else:
            if not allowed_request(getattr(res,'url',url),self.host):
                self.robots_info['state']='unexpected_redirect'
                raise RuntimeError('robots_unexpected_redirect')
            status=res.status;body=await res.text();headers=getattr(res,'headers',{})
        self.robots_info['http_status']=status
        # Retry-After and 429 are intentionally stricter than generic RFC 4xx:
        # do not create another browser request when asked to slow down.
        if headers.get('retry-after'):
            self.robots_info['state']='retry_after'
            raise RuntimeError('robots_retry_after')
        if status==429:
            self.robots_info['state']='rate_limited'
            raise RuntimeError('robots_http_429')
        if status is None or status>=500 or 300<=status<400:
            self.robots_info['method']='browser_fallback'
            try:
                status,_=await self.navigate(url)
                body=await self.page.locator('body').inner_text()
            except Exception:
                self.robots_info['state']='unreachable'
                raise
            self.robots_info['http_status']=status
        try:
            rules,state=robots_document(status,body)
        except RuntimeError:
            self.robots_info['state']='unreadable_or_unreachable'
            raise
        self.policy=Protego.parse(rules)
        self.robots_info['state']=state
        delay=self.policy.crawl_delay('LoyaltyCatalogResearchBot') or 0
        rate=self.policy.request_rate('LoyaltyCatalogResearchBot')
        self.request_interval=max(0.25,delay,rate.seconds/rate.requests if rate else 0)

    def check_url(self,url):
        if not allowed_request(url,self.host):
            raise RuntimeError('request_outside_public_source')
        if self.policy is None or not self.policy.can_fetch(url,'LoyaltyCatalogResearchBot'):
            raise RuntimeError('robots_disallow')

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

    async def read(self,url: str,*,render=False) -> str:
        self.check_url(url)
        async with self.lock:
            await asyncio.sleep(self.request_interval)
            if render:
                status,body=await self.navigate(url)
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
