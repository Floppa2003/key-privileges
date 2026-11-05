"""Real Chromium over original-byte fixtures; no source or model network."""
import asyncio
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'loyalty'), str(ROOT / 'loyalty/tests')]
from playwright.async_api import async_playwright
import merchant_queue as queue
import merchant_extract as extractor
from recovered_contract import SOURCES, CA_FILES
from test_capture_tls import Response, CA_BYTES, FIXTURE_CAS
from test_document_text import pdf

URL = SOURCES['af_vtb_rules']['url']
STYLE = 'https://www.vtb.ru/source-style.css'
SCRIPT = 'https://www.vtb.ru/source-script.js'
HTML = b'''<!doctype html><html><head><link rel="stylesheet" href="/source-style.css">
<script src="/source-script.js" defer></script></head><body>
<h1>Independent verified merchant</h1><p id="conditions">Original public conditions.</p>
<div id="late"></div></body></html>'''


class SourceSession:
    def __init__(self, *, refused_asset=False, document=None):
        self.calls, self.trust_env = [], False
        self.refused_asset, self.document = refused_asset, document
    def get(self, url, **kwargs):
        self.calls.append(url)
        for index, item in enumerate(CA_FILES):
            if url == item[0]: return Response(CA_BYTES[index])
        bundle = kwargs['verify']
        if not isinstance(bundle, str) or not all(raw in Path(bundle).read_bytes() for raw in CA_BYTES):
            raise AssertionError('Missing verified CA bundle')
        if kwargs['allow_redirects'] is not False:
            raise AssertionError('Unreviewed redirect follow')
        if url == URL:
            return Response(HTML, headers={'Content-Type': 'text/html; charset=utf-8',
                            'Content-Encoding': 'gzip', 'Content-Length': '999999'})
        if url == STYLE:
            return Response(b'body{margin:0} #conditions{color:rgb(17,34,51)}',
                            status=403 if self.refused_asset else 200,
                            headers={'Content-Type': 'text/css'})
        if url == SCRIPT:
            return Response(b'document.querySelector("#late").textContent="Complete late source section.";',
                            headers={'Content-Type': 'application/javascript'})
        if url == SOURCES['af_primbank_rules']['url'] and self.document:
            return Response(self.document, headers={'Content-Type': 'application/pdf',
                            'Content-Disposition': 'attachment; filename="rules.pdf"'})
        raise AssertionError('Unexpected fixture request: ' + url)
    def close(self): pass


class OfflineBrowser:
    def __init__(self, real): self.real = real
    async def new_context(self, **kwargs):
        context = await self.real.new_context(**kwargs)
        # Unhandled requests must stay offline. The source bridge uses fallback
        # so this also catches accidental broadening of the reviewed route.
        await context.route('**/*', lambda route: route.abort())
        return context


class VerifiedCaptureBrowserTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.out = Path(self.tmp.name)
        self.pw = await async_playwright().start()
        self.real = await self.pw.chromium.launch(headless=True)
        self.browser = OfflineBrowser(self.real)
    async def asyncTearDown(self):
        await self.real.close(); await self.pw.stop(); self.tmp.cleanup()

    async def capture(self, session, *, url=URL, ident='verified'):
        target = {'id': ident, 'url': url, 'partner': 'Independent verified merchant', 'program': 'Fixture'}
        with patch('recovered_sources.CA_FILES', FIXTURE_CAS), \
             patch('recovered_sources.requests.Session', return_value=session), \
             patch('recovered_sources.time.sleep'):
            return await queue.capture_page(self.browser, target, self.out)

    async def test_real_dom_script_and_images_use_unmodified_verified_entities(self):
        session = SourceSession()
        spec = await self.capture(session)
        visible = (self.out / spec['text']).read_text()
        self.assertIn('Original public conditions.', visible)
        self.assertIn('Complete late source section.', visible)
        proof = spec['capture']['transport']
        self.assertFalse(proof['browser_tls_verification_disabled'])
        responses = {row['url']: row for row in proof['responses']}
        self.assertEqual(set(responses), {URL, STYLE, SCRIPT})
        self.assertEqual(responses[URL]['entity_sha256'], hashlib.sha256(HTML).hexdigest())
        self.assertEqual(spec['source_url'], URL)
        manifest = self.out / 'manifest.json'
        manifest.write_text(json.dumps({'documents': [spec]}))
        self.assertEqual(len(extractor.load_manifest(manifest)), 1)

    async def test_failed_stylesheet_cannot_be_reported_as_a_complete_capture(self):
        with self.assertRaisesRegex(RuntimeError, 'capture_tls_http_403'):
            await self.capture(SourceSession(refused_asset=True))

    async def test_extensionless_pdf_is_downloaded_once_and_all_pages_are_kept(self):
        raw = pdf(['Independent verified merchant: page one', 'Original conditions on page two'])
        session = SourceSession(document=raw)
        url = SOURCES['af_primbank_rules']['url']
        spec = await self.capture(session, url=url, ident='pdf')
        self.assertEqual((self.out / 'pdf/source.pdf').read_bytes(), raw)
        self.assertEqual(len(spec['images']), 2)
        self.assertEqual(session.calls.count(url), 1)
        self.assertIn('Original conditions on page two', (self.out / spec['text']).read_text())
        self.assertEqual(spec['capture']['transport']['document_url'], url)


if __name__ == '__main__': unittest.main(verbosity=2)
