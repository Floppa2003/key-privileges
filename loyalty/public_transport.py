"""Anonymous same-origin reads, finite timeouts, robots and challenge checks."""
from __future__ import annotations
import asyncio
import re
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
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
        self.context=None;self.page=None;self.lock=asyncio.Lock()

    async def __aenter__(self):
        self.context=await self.browser.new_context(locale='ru-RU')
        self.page=await self.context.new_page()
        return self

    async def __aexit__(self,*_):
        if self.context:await self.context.close()

    async def robots(self):
        url=f'https://{self.host}/robots.txt'
        try:
            res=await self.context.request.get(url,timeout=15000)
            status=res.status;body=await res.text()
        except Exception:
            status=None;body=''
        if status not in (200,404):
            # A regular browser read is a transport fallback, not CAPTCHA/login solving.
            res=await self.page.goto(url,wait_until='domcontentloaded',timeout=20000)
            status=res.status if res else 0
            body=await self.page.locator('body').inner_text()
        if status==404:
            body=''
        elif status!=200:
            raise RuntimeError(f'robots_http_{status}')
        if '<html' in body.lower() or BLOCKED.search(body[:350]):
            raise RuntimeError('robots_not_readable')
        self.policy=RobotFileParser(url);self.policy.parse(body.splitlines())

    def check_url(self,url):
        if not allowed_request(url,self.host):
            raise RuntimeError('request_outside_public_source')
        if self.policy is None or not self.policy.can_fetch('LoyaltyCatalogResearchBot',url):
            raise RuntimeError('robots_disallow')

    async def read(self,url: str,*,render=False) -> str:
        self.check_url(url)
        async with self.lock:
            await asyncio.sleep(0.25)
            if render:
                res=await self.page.goto(url,wait_until='domcontentloaded',timeout=30000)
                await self.page.wait_for_timeout(1200)
                if not res or not allowed_request(self.page.url,self.host):
                    raise RuntimeError('unexpected_redirect')
                body=await self.page.content();check_response(res.status,body)
            else:
                res=await self.context.request.get(url,timeout=20000)
                if not allowed_request(res.url,self.host):raise RuntimeError('unexpected_redirect')
                body=await res.text();check_response(res.status,body)
            if len(body.encode())>6000000:raise RuntimeError('source_response_too_large')
            return body

    async def json(self,url: str,*,method='GET',data=None,content_type=None):
        self.check_url(url)
        if method not in ('GET','POST') or (method=='POST' and not urlsplit(url).path.endswith('/promo/filter-json')):
            raise RuntimeError('non_catalog_post_refused')
        async with self.lock:
            await asyncio.sleep(0.25)
            headers={'Content-Type':content_type} if content_type else {}
            res=await self.context.request.fetch(url,method=method,data=data,headers=headers,timeout=20000)
            if not allowed_request(res.url,self.host):raise RuntimeError('unexpected_redirect')
            body=await res.text();check_response(res.status,body)
            if len(body.encode())>6000000:raise RuntimeError('source_response_too_large')
            return await res.json()
