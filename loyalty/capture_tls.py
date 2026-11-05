"""Verified source bytes for the four already reviewed national-CA endpoints.

Chromium renders the real response at its original URL. Extra trust stays in a
temporary requests bundle; browser/system trust and source markup are unchanged.
Only the exact document and its public same-origin static assets use this path.
"""
from __future__ import annotations
import asyncio
import hashlib
import json
import re
import time
from urllib.parse import parse_qsl, unquote, urlsplit

from recovered_contract import SOURCES, CA_PROFILE, transport_evidence
from recovered_sources import ScopedReader
from source_diagnostics import ReadError

STATIC_TYPES = {'stylesheet', 'script', 'image', 'font'}
MAX_REQUESTS = 100
MAX_TOTAL_BYTES = 30_000_000
UNSAFE_HEADERS = {'content-encoding', 'content-length', 'transfer-encoding',
                  'connection', 'keep-alive', 'proxy-authenticate',
                  'proxy-authorization', 'te', 'trailer', 'upgrade', 'set-cookie'}


def profile_for(url):
    return next(({'id': sid, 'url': url, 'access_profile': spec['profile']}
                 for sid, spec in SOURCES.items()
                 if spec.get('profile') == CA_PROFILE and spec['url'] == url), None)


class CaptureReader(ScopedReader):
    def __init__(self, cfg, deadline):
        super().__init__(cfg, {}, deadline)
        self.document_url = cfg['url']
        self.asset_urls = set()

    def allow_asset(self, url, kind):
        from public_transport import allowed_request
        base, target = urlsplit(self.document_url), urlsplit(url)
        decoded = unquote(target.path)
        if (kind not in STATIC_TYPES or target.scheme != 'https' or target.netloc != base.netloc
                or target.fragment or not allowed_request(url, base.hostname)
                or '..' in decoded.split('/') or '\\' in decoded
                or re.search(r'/(?:auth|login|personal|register|accept|activate|participate)(?:/|$)', decoded, re.I)
                or any(re.search(r'token|secret|password|auth|session|credential', key, re.I)
                       for key, _ in parse_qsl(target.query))):
            raise ReadError('capture_tls_asset_outside_scope')
        self.asset_urls.add(url)

    def allowed(self, url):
        if url == self.document_url or url in self.asset_urls:
            return url
        raise ReadError('capture_tls_request_outside_scope')


class VerifiedResponse:
    def __init__(self, url, status, headers, body):
        self.url, self.status, self.headers, self.data = url, status, headers, body
    async def body(self): return self.data
    async def text(self):
        charset = re.search(r'charset\s*=\s*[\"\']?([\w-]+)', self.headers.get('content-type', ''), re.I)
        return self.data.decode(charset[1] if charset else 'utf-8')
    async def json(self): return json.loads(await self.text())


class VerifiedBrowserTransport:
    def __init__(self, cfg, deadline):
        self.cfg = cfg
        self.reader = CaptureReader(cfg, deadline)
        self.lock = asyncio.Lock()  # Deliberately separate from PublicSource.lock.
        self.cache, self.receipts, self.failures = {}, [], []
        self.tasks = set()
        self.requests = self.total_bytes = 0
        self.generation = 0
        self.closed = False

    async def start(self):
        task = asyncio.create_task(asyncio.to_thread(self.reader.__enter__))
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            try:
                await task
            finally:
                await self.close()
            raise
        except BaseException:
            await self.close()
            raise

    async def close(self):
        # A requests read has a finite timeout and must finish before its bundle
        # is removed. Shielding prevents cancellation from closing active TLS I/O.
        async with self.lock:
            if not self.closed:
                await asyncio.to_thread(self.reader.__exit__)
                self.closed = True

    async def fetch(self, url, *, kind='document', method='GET'):
        if method != 'GET':
            raise ReadError('capture_tls_non_get_refused')
        if kind == 'document':
            if url != self.cfg['url']:
                raise ReadError('capture_tls_document_outside_scope')
        else:
            self.reader.allow_asset(url, kind)
        async with self.lock:
            if url in self.cache:
                return self.cache[url]
            if self.requests >= MAX_REQUESTS:
                raise ReadError('capture_tls_request_budget')
            self.requests += 1
            task = asyncio.create_task(asyncio.to_thread(self.reader._get, url))
            try:
                status, headers, body = await asyncio.shield(task)
            except asyncio.CancelledError:
                await task
                raise
            self.total_bytes += len(body)
            if self.total_bytes > MAX_TOTAL_BYTES:
                raise ReadError('capture_tls_response_budget')
            # iter_content returns decoded entity bytes, not compressed wire data.
            headers = {str(k).lower(): str(v) for k, v in headers.items()
                       if str(k).lower() not in UNSAFE_HEADERS}
            response = VerifiedResponse(url, status, headers, body)
            self.receipts.append({'url': url, 'resource_type': kind, 'http_status': status,
                                  'entity_bytes': len(body),
                                  'entity_sha256': hashlib.sha256(body).hexdigest()})
            self.cache[url] = response
            return response

    async def route(self, route):
        request = route.request
        if urlsplit(request.url).hostname != urlsplit(self.cfg['url']).hostname:
            await route.fallback()
            return
        # Extra CA trust is never given to APIs, submissions, private navigation
        # or arbitrary hosts. Unhandled requests retain normal browser TLS.
        kind = request.resource_type
        if kind not in STATIC_TYPES and kind != 'document':
            await route.fallback()
            return
        task = asyncio.current_task()
        self.generation += 1
        self.tasks.add(task)
        try:
            response = await self.fetch(request.url, kind=kind, method=request.method)
            if response.status >= 400:
                raise ReadError('capture_tls_http_' + str(response.status), status=response.status)
            await route.fulfill(status=response.status, headers=response.headers, body=response.data)
        except Exception as exc:
            reason = str(exc)
            if not re.fullmatch('[a-z][a-z_0-9]{0,159}', reason):
                reason = 'capture_tls_transport_failed'
            self.failures.append({'path': urlsplit(request.url).path, 'resource_type': kind,
                                  'reason': reason, 'error_type': type(exc).__name__})
            await route.abort('failed')
        finally:
            self.tasks.discard(task)

    def check(self):
        if self.failures:
            raise ReadError(self.failures[0]['reason'])

    async def finish(self):
        end = min(self.reader.deadline, time.monotonic() + 30)
        while True:
            self.check()
            if time.monotonic() >= end:
                raise ReadError('capture_tls_resources_not_complete')
            generation = self.generation
            pending = [task for task in self.tasks if task is not asyncio.current_task()]
            if pending:
                await asyncio.wait(pending, timeout=max(0, end - time.monotonic()))
                continue
            # A stylesheet/script can enqueue further requests as it finishes.
            # Wait for a stable empty set, not just the first task snapshot.
            await asyncio.sleep(min(0.1, max(0, end - time.monotonic())))
            if generation == self.generation and not self.tasks:
                self.check()
                return

    def evidence(self):
        return {**transport_evidence(self.cfg['id']),
                'mode': 'verified_original_http_entities_rendered_at_source_url',
                'resource_generation': self.generation,
                'browser_tls_verification_disabled': False,
                'document_url': self.cfg['url'], 'responses': list(self.receipts),
                'failures': list(self.failures)}
