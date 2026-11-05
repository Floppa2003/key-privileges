"""The ordinary capture reader must retain the reviewed source TLS policy.

Only HTTP/browser I/O is substituted. The trust bundle, source scope, routing,
status checks and PublicSource acquisition path run their production code.
"""
import hashlib
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from playwright.async_api import Error as BrowserError
import requests

sys.path.insert(0, str(Path(__file__).parents[1]))
from public_transport import PublicSource
from recovered_contract import CA_FILES, SOURCES

URL = SOURCES['af_vtb_rules']['url']
PDF_URL = SOURCES['af_primbank_rules']['url']
HTML = b'<html><body><h1>Complete bank rules</h1><p>Original conditions.</p></body></html>'
CA_BYTES = [b'fixture root certificate', b'fixture intermediate certificate']
FIXTURE_CAS = tuple((entry[0], hashlib.sha256(raw).hexdigest()) for entry, raw in zip(CA_FILES, CA_BYTES))


class Response:
    def __init__(self, body, status=200, headers=None):
        self.status_code, self.body = status, body
        self.headers = headers or {'Content-Type': 'text/html; charset=utf-8'}
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def iter_content(self, size): yield self.body


class Session:
    def __init__(self, *, page=None, bad_ca=False):
        self.calls, self.closed = [], False
        self.page = page or Response(HTML)
        self.bad_ca = bad_ca
        self.trust_env = True
    def get(self, url, **options):
        self.calls.append((url, options))
        for index, entry in enumerate(CA_FILES):
            if url == entry[0]:
                return Response(b'changed' if self.bad_ca else CA_BYTES[index])
        if isinstance(self.page, Exception): raise self.page
        verify = options['verify']
        if not isinstance(verify, str) or not all(raw in Path(verify).read_bytes() for raw in CA_BYTES):
            raise AssertionError('The source must receive the checked temporary CA bundle')
        if options['allow_redirects'] is not False:
            raise AssertionError('Unreviewed redirects must not be followed by requests')
        return self.page
    def close(self): self.closed = True


class Route:
    def __init__(self, page, url):
        self.request = SimpleNamespace(url=url, method='GET', resource_type='document',
                                       is_navigation_request=lambda: True, frame=page.main_frame)
        self.fulfilled = None
        self.aborted = False
    async def fulfill(self, **kwargs): self.fulfilled = kwargs
    async def abort(self, *args, **kwargs): self.aborted = True
    async def continue_(self, **kwargs): pass


class Page:
    def __init__(self, context):
        self.context, self.url = context, 'about:blank'
        self.main_frame, self.listeners = object(), {}
        self.body = ''
    def on(self, name, callback): self.listeners[name] = callback
    def remove_listener(self, name, callback): self.listeners.pop(name, None)
    async def goto(self, url, **kwargs):
        if self.context.handler is None:
            raise BrowserError('Page.goto: net::ERR_CERT_AUTHORITY_INVALID')
        route = Route(self, url)
        await self.context.handler(route)
        if not route.fulfilled:
            raise BrowserError('Page.goto: net::ERR_FAILED')
        self.url = url
        self.body = route.fulfilled['body'].decode('utf-8')
        response = SimpleNamespace(url=url, status=route.fulfilled['status'],
                                   headers=route.fulfilled.get('headers', {}), request=route.request)
        if 'response' in self.listeners: self.listeners['response'](response)
        return response
    async def content(self): return self.body
    async def wait_for_timeout(self, _): pass


class Context:
    def __init__(self):
        self.handler, self.closed = None, False
        self.request = self
    async def new_page(self): self.page = Page(self); return self.page
    async def route(self, pattern, handler): self.handler = handler
    async def fetch(self, *args, **kwargs):
        raise BrowserError('APIRequestContext.get: certificate verify failed')
    async def close(self): self.closed = True


class Browser:
    def __init__(self): self.options, self.contexts = [], []
    async def new_context(self, **kwargs):
        self.options.append(kwargs)
        context = Context(); self.contexts.append(context)
        return context


class CaptureTLSTests(unittest.IsolatedAsyncioTestCase):
    async def test_known_source_browser_renders_exact_verified_response(self):
        session, browser = Session(), Browser()
        with patch('recovered_sources.CA_FILES', FIXTURE_CAS), \
             patch('recovered_sources.requests.Session', return_value=session), \
             patch('recovered_sources.time.sleep'):
            async with PublicSource(browser, URL) as source:
                source.request_interval = 0
                body = await source.read(URL, render=True)
        self.assertEqual(body.encode(), HTML)
        self.assertEqual([u for u, _ in session.calls], [u for u, _ in CA_FILES] + [URL])
        self.assertNotIn('ignore_https_errors', browser.options[0])
        self.assertTrue(session.closed)
        self.assertTrue(browser.contexts[0].closed)

    async def test_extensionless_reviewed_pdf_uses_the_same_verified_bytes(self):
        raw = b'%PDF-1.7\nOriginal source bytes.'
        session, browser = Session(page=Response(raw, headers={'Content-Type': 'application/pdf'})), Browser()
        with patch('recovered_sources.CA_FILES', FIXTURE_CAS), \
             patch('recovered_sources.requests.Session', return_value=session), \
             patch('recovered_sources.time.sleep'):
            async with PublicSource(browser, PDF_URL) as source:
                source.request_interval = 0
                self.assertEqual(await source.read_pdf(PDF_URL), raw)
        self.assertEqual([u for u, _ in session.calls], [u for u, _ in CA_FILES] + [PDF_URL])

    async def test_unlisted_page_does_not_inherit_extra_certificate_trust(self):
        browser = Browser()
        with patch('recovered_sources.requests.Session') as session:
            async with PublicSource(browser, 'https://www.vtb.ru/unreviewed/') as source:
                with self.assertRaisesRegex(BrowserError, 'CERT_AUTHORITY_INVALID'):
                    await source.read('https://www.vtb.ru/unreviewed/', render=True)
        session.assert_not_called()

    async def test_changed_ca_is_rejected_before_any_source_request(self):
        session, browser = Session(bad_ca=True), Browser()
        with patch('recovered_sources.CA_FILES', FIXTURE_CAS), \
             patch('recovered_sources.requests.Session', return_value=session), \
             patch('recovered_sources.time.sleep'):
            with self.assertRaisesRegex(RuntimeError, 'official_ca_digest_changed_or_unavailable'):
                async with PublicSource(browser, URL): pass
        self.assertEqual([u for u, _ in session.calls], [CA_FILES[0][0]])
        self.assertTrue(session.closed)


if __name__ == '__main__': unittest.main()
