"""Anonymous same-origin reads, finite timeouts, robots and challenge checks."""
from __future__ import annotations
import asyncio
import re
from urllib.parse import urlsplit
from protego import Protego
from bs4 import BeautifulSoup
from model import clean_url
from normalized import BLOCKED


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
    if BLOCKED.search(headline) or BLOCKED.search(leading):
        raise RuntimeError('access_challenge')


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
        url=f'https://{self.host}/robots.txt'
        try:
            res=await self.context.request.get(url,timeout=15000)
            status=res.status;body=await res.text()
        except Exception:
            status=None;body=''
        if status not in (200,404):
            # A regular browser read is a transport fallback, not CAPTCHA/login solving.
            status,_=await self.navigate(url)
            body=await self.page.locator('body').inner_text()
        if status==404:
            body=''
        elif status!=200:
            raise RuntimeError(f'robots_http_{status}')
        if '<html' in body.lower() or BLOCKED.search(body[:350]):
            raise RuntimeError('robots_not_readable')
        self.policy=Protego.parse(body)
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
            res=await self.context.request.fetch(url,timeout=20000,**kwargs)
            if not allowed_request(res.url,self.host):raise RuntimeError('unexpected_redirect')
            if res.status not in (502,503,504) or attempt==2 or res.headers.get('retry-after'):
                return res
            await asyncio.sleep(2**attempt)
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
