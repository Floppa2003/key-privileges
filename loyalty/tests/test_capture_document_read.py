"""Raw acquisition regressions from merchant runs 41589577533/41782293858.

Finuslugi's extensionless URL serves application/pdf with a %PDF-1.7 signature.
The second repeated failure is Playwright's Page.content navigation race at
vip-zal.ru/aeroflot-bonus.php. No model or public-site request is used here.
"""
import asyncio
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from playwright.async_api import Error as BrowserError, TimeoutError as BrowserTimeout

sys.path[:0] = [str(Path(__file__).parents[1]), str(Path(__file__).parent)]
import merchant_queue as queue
from public_transport import PublicSource
from source_diagnostics import ParseError, ReadError
from test_document_text import pdf
from test_final_navigation import Page, Response

PDF_URL = 'https://assets.finuslugi.ru/sc-disclosure/293d2bf4-16c4-46c6-87a5-0a2d35d18ad8'
HTML_URL = 'https://vip-zal.ru/aeroflot-bonus.php'
RACE = 'Page.content: Unable to retrieve content because the page is navigating and changing the content.'
DOWNLOAD = 'Page.goto: Download is starting\nCall log:\n  - navigating to "' + PDF_URL + '", waiting until "domcontentloaded"\n'


class CaptureDocumentTests(unittest.IsolatedAsyncioTestCase):
    async def test_extensionless_download_keeps_pdf_text_and_every_rendered_page(self):
        raw = pdf(['Public Merchant: source page one', 'Unabridged conditions on page two'])

        class Source:
            page = type('Page', (), {'set_viewport_size': AsyncMock()})()
            navigate = AsyncMock(side_effect=BrowserError(DOWNLOAD))
            read_pdf = AsyncMock(return_value=raw)
            def __init__(self, browser, url):
                self.url = url
            async def __aenter__(self):
                return self
            async def __aexit__(self, *_):
                pass

        target = {'id': 'extensionless', 'url': PDF_URL, 'partner': 'Public Merchant', 'program': 'Public programme'}
        with tempfile.TemporaryDirectory() as directory, patch('public_transport.PublicSource', Source):
            root = Path(directory)
            spec = await queue.capture_page(None, target, root)
            self.assertEqual((root / 'extensionless/source.pdf').read_bytes(), raw)
            text = (root / spec['text']).read_text()
            self.assertIn('source page one', text)
            self.assertIn('Unabridged conditions on page two', text)
            self.assertEqual(len(spec['images']), 2)
            self.assertEqual(spec['capture']['scope'], 'pdf')
            self.assertTrue(spec['capture']['target_found'])
            self.assertEqual(spec['source_url'], PDF_URL)
            Source.read_pdf.assert_awaited_once_with(PDF_URL)

    async def test_navigation_refusal_does_not_try_a_second_pdf_route(self):
        for message in ('Page.goto: net::ERR_CERT_AUTHORITY_INVALID', 'Page.goto: net::ERR_NAME_NOT_RESOLVED'):
            with self.subTest(message=message):
                class Source:
                    page = type('Page', (), {'set_viewport_size': AsyncMock()})()
                    navigate = AsyncMock(side_effect=BrowserError(message))
                    read_pdf = AsyncMock()
                    def __init__(self, *args):
                        pass
                    async def __aenter__(self):
                        return self
                    async def __aexit__(self, *_):
                        pass
                with tempfile.TemporaryDirectory() as directory, patch('public_transport.PublicSource', Source):
                    with self.assertRaises(BrowserError):
                        await queue.capture_page(None, {'id': 'refusal', 'url': PDF_URL, 'partner': 'X', 'program': 'X'}, Path(directory))
                    Source.read_pdf.assert_not_awaited()


class PdfResponse:
    def __init__(self, *, url=PDF_URL, status=200, body=b'%PDF-1.7\r\npublic bytes', headers=None):
        self.url, self.status, self.data = url, status, body
        self.headers = headers or {'content-type': 'application/pdf'}
        self.body_reads = 0

    async def body(self):
        self.body_reads += 1
        return self.data


class PdfReadTests(unittest.IsolatedAsyncioTestCase):
    def client(self, responses):
        client = PublicSource(None, PDF_URL)
        client.request_interval = 0
        client.context = type('Context', (), {'request': type('Requests', (), {
            'fetch': AsyncMock(side_effect=responses)})()})()
        return client

    async def test_extensionless_pdf_is_identified_from_response_bytes(self):
        for mime in ('application/pdf', 'application/octet-stream'):
            response = PdfResponse(headers={'content-type': mime})
            client = self.client([response])
            self.assertEqual(await client.read_pdf(PDF_URL), response.data)

    async def test_pdf_mime_and_download_name_do_not_turn_html_into_pdf(self):
        response = PdfResponse(body=b'<html><title>Access denied</title></html>', headers={
            'content-type': 'application/pdf', 'content-disposition': 'attachment; filename="rules.pdf"'})
        with self.assertRaisesRegex(RuntimeError, 'not_a_pdf'):
            await self.client([response]).read_pdf(PDF_URL)

    async def test_same_origin_redirect_is_checked_and_followed_explicitly(self):
        final_url = PDF_URL + '/current'
        client = self.client([PdfResponse(status=302, headers={'location': '/sc-disclosure/' + PDF_URL.rsplit('/', 1)[-1] + '/current'}),
                              PdfResponse(url=final_url)])
        self.assertTrue((await client.read_pdf(PDF_URL)).startswith(b'%PDF-'))
        calls = client.context.request.fetch.await_args_list
        self.assertEqual([c.args[0] for c in calls], [PDF_URL, final_url])
        self.assertTrue(all(c.kwargs.get('max_redirects') == 0 for c in calls))

    async def test_redirect_outside_public_source_is_not_requested(self):
        for location in ('https://other.example/rules.pdf', '/login/', 'http://assets.finuslugi.ru/rules.pdf',
                         'https://assets.finuslugi.ru:8443/rules.pdf'):
            with self.subTest(location=location):
                client = self.client([PdfResponse(status=302, headers={'location': location})])
                with self.assertRaisesRegex(RuntimeError, 'unexpected_redirect'):
                    await client.read_pdf(PDF_URL)
                self.assertEqual(client.context.request.fetch.await_count, 1)

    async def test_cyclic_redirects_stop_without_replaying_same_url(self):
        client = self.client([PdfResponse(status=302, headers={'location': PDF_URL})])
        with self.assertRaisesRegex(RuntimeError, 'pdf_redirect_limit'):
            await client.read_pdf(PDF_URL)
        self.assertEqual(client.context.request.fetch.await_count, 1)

    async def test_http_refusal_never_becomes_pdf_success(self):
        for status in (401, 403, 429, 503):
            response = PdfResponse(status=status, headers={'retry-after': '120'})
            client = self.client([response])
            with self.assertRaisesRegex(RuntimeError, 'http_' + str(status)):
                await client.read_pdf(PDF_URL)
            self.assertEqual(response.body_reads, 0)
            self.assertEqual(client.context.request.fetch.await_count, 1)

    async def test_existing_six_mb_budget_still_rejects_large_document(self):
        response = PdfResponse(body=b'%PDF-' + b'x' * 6000000)
        with self.assertRaisesRegex(RuntimeError, 'source_response_too_large'):
            await self.client([response]).read_pdf(PDF_URL)


class RacingPage(Page):
    def __init__(self, *, final_status=200, final_url=HTML_URL, always_racing=False, wait_timeout=False):
        super().__init__([(200, '<html><body>initial document</body></html>')], HTML_URL)
        self.final_status = final_status
        self.final_url = final_url
        self.always_racing = always_racing
        self.wait_timeout = wait_timeout
        self.content_calls = 0
        self.gotos = 0
        self.load_waits = []

    async def goto(self, url, **kwargs):
        self.gotos += 1
        return await super().goto(url, **kwargs)

    async def content(self):
        self.content_calls += 1
        if self.content_calls == 1 or self.always_racing:
            if not self.wait_timeout:
                asyncio.get_running_loop().call_soon(self.finish_navigation)
            raise BrowserError(RACE)
        return self.body

    async def wait_for_load_state(self, state, *, timeout):
        # Playwright may immediately return the *old* document's loaded state
        # before a pending main navigation commits. This must not certify it.
        self.load_waits.append((state, timeout))
        if self.wait_timeout:
            raise BrowserTimeout('ongoing page navigation')

    def finish_navigation(self):
        self.url = self.final_url
        self.body = '<html><body>Public Merchant: complete current offer</body></html>'
        response = Response(self, self.final_status, self.url)
        if 'response' in self.listeners:
            self.listeners['response'](response)
        if 'domcontentloaded' in self.listeners:
            self.listeners['domcontentloaded'](self)


class NavigationSnapshotTests(unittest.IsolatedAsyncioTestCase):
    def client(self, page):
        client = PublicSource(None, HTML_URL)
        client.request_interval = 0
        client.page = page
        return client

    async def test_observed_vip_zal_content_race_recovers_without_replaying_get(self):
        page = RacingPage()
        body = await self.client(page).read(HTML_URL, render=True)
        self.assertIn('complete current offer', body)
        self.assertEqual(page.gotos, 1)
        self.assertEqual(page.content_calls, 2)
        self.assertEqual(page.load_waits, [])
        self.assertEqual(page.listeners, {})

    async def test_status_after_automatic_navigation_is_not_the_initial_200(self):
        page = RacingPage(final_status=403)
        with self.assertRaisesRegex(ReadError, 'http_403'):
            await self.client(page).read(HTML_URL, render=True)
        self.assertEqual(page.gotos, 1)
        self.assertEqual(page.listeners, {})

    async def test_redirect_during_content_retry_still_fails(self):
        for url in ('https://other.example/offer', 'https://vip-zal.ru/login/'):
            with self.subTest(url=url):
                page = RacingPage(final_url=url)
                with self.assertRaisesRegex(RuntimeError, 'unexpected_redirect'):
                    await self.client(page).read(HTML_URL, render=True)
                self.assertEqual(page.gotos, 1)
                self.assertEqual(page.listeners, {})

    async def test_unstable_page_has_bounded_dom_reads_and_no_navigation_replay(self):
        page = RacingPage(always_racing=True)
        with self.assertRaisesRegex(ParseError, 'page_navigation_unstable'):
            await self.client(page).read(HTML_URL, render=True)
        self.assertEqual(page.content_calls, 3)
        self.assertEqual(page.gotos, 1)
        self.assertEqual(page.listeners, {})

    async def test_pending_navigation_timeout_is_not_replayed_as_a_network_timeout(self):
        page = RacingPage(wait_timeout=True)
        with patch('public_transport.asyncio.wait_for', new=AsyncMock(side_effect=asyncio.TimeoutError)), \
                self.assertRaisesRegex(ParseError, 'page_navigation_unstable'):
            await self.client(page).read(HTML_URL, render=True)
        self.assertEqual(page.gotos, 1)
        self.assertEqual(page.load_waits, [])
        self.assertEqual(page.listeners, {})

    async def test_status_changed_during_successful_content_call_is_rechecked(self):
        class ReplacedPage(RacingPage):
            async def content(self):
                self.content_calls += 1
                if self.content_calls == 1:
                    self.finish_navigation()
                return self.body
        page = ReplacedPage(final_status=403)
        with self.assertRaisesRegex(ReadError, 'http_403'):
            await self.client(page).read(HTML_URL, render=True)
        self.assertEqual(page.gotos, 1)
        self.assertEqual(page.listeners, {})

    async def test_unrelated_content_failure_is_not_retried(self):
        page = RacingPage()
        page.content = AsyncMock(side_effect=BrowserError('Page.content: Target page has been closed'))
        with self.assertRaisesRegex(BrowserError, 'Target page has been closed'):
            await self.client(page).read(HTML_URL, render=True)
        self.assertEqual(page.gotos, 1)
        self.assertEqual(page.content.await_count, 1)
        self.assertEqual(page.load_waits, [])
        self.assertEqual(page.listeners, {})

    async def test_capture_observation_includes_navigation_after_initial_read(self):
        page = RacingPage()
        client = self.client(page)
        await client.navigate(HTML_URL)
        page.final_status = 403
        with client.observe_navigation(include_current=True) as latest:
            page.finish_navigation()
            status, body = await client.document_content(latest)
        self.assertEqual(status, 403)
        self.assertIn('complete current offer', body)
        self.assertEqual(page.gotos, 1)
        self.assertEqual(page.listeners, {})


if __name__ == '__main__':
    unittest.main()
