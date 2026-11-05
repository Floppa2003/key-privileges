"""Independent races and response-boundary checks for verified capture routing."""
import asyncio
import sys
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).parents[1]), str(Path(__file__).parent)]
from capture_tls import VerifiedBrowserTransport, profile_for
from source_diagnostics import ReadError
from test_capture_tls import CA_FILES, FIXTURE_CAS, HTML, Response, Session, URL

ASSET_A = 'https://www.vtb.ru/assets/source-a.js'
ASSET_B = 'https://www.vtb.ru/assets/source-b.css'


class Route:
    def __init__(self, url, kind='script', *, on_fulfill=None):
        self.request = SimpleNamespace(url=url, method='GET', resource_type=kind)
        self.fulfilled = None
        self.aborted = self.continued = False
        self.on_fulfill = on_fulfill

    async def fulfill(self, **kwargs):
        self.fulfilled = kwargs
        if self.on_fulfill:
            await self.on_fulfill()

    async def abort(self, *args):
        self.aborted = True

    async def fallback(self):
        self.continued = True


class CaptureTLSReviewTests(unittest.IsolatedAsyncioTestCase):
    def transport(self):
        transport = VerifiedBrowserTransport(profile_for(URL), time.monotonic() + 30)
        transport.reader.interval = 0
        return transport

    async def finish_with_resource_delay(self, delay):
        """Advance only the transport clock while a real route awaits browser I/O."""
        entered, release = asyncio.Event(), asyncio.Event()

        async def delayed_fulfill():
            entered.set()
            await release.wait()

        session = Session()
        with patch('recovered_sources.CA_FILES', FIXTURE_CAS), \
             patch('recovered_sources.requests.Session', return_value=session):
            transport = self.transport()
            task = None
            try:
                await transport.start()
                task = asyncio.create_task(transport.route(Route(ASSET_A, on_fulfill=delayed_fulfill)))
                await asyncio.wait_for(entered.wait(), 2)
                clock = SimpleNamespace(now=1000.0)
                transport.reader.deadline = clock.now + 210
                ready_at = clock.now + delay

                async def controlled_wait(pending, *, timeout):
                    until_ready = max(0, ready_at - clock.now)
                    clock.now += min(timeout, until_ready)
                    if until_ready <= timeout:
                        release.set()
                        await asyncio.gather(*pending)
                        return set(pending), set()
                    return set(), set(pending)

                async def controlled_sleep(seconds):
                    clock.now += seconds
                    await asyncio.sleep(0)

                # Replace module bindings, never stdlib time.monotonic or the
                # event loop clock. No 30/210-second wall-clock wait is involved.
                scheduler = SimpleNamespace(current_task=asyncio.current_task,
                                            wait=controlled_wait, sleep=controlled_sleep)
                with patch('capture_tls.time', SimpleNamespace(monotonic=lambda: clock.now)), \
                     patch('capture_tls.asyncio', scheduler):
                    failure = None
                    try:
                        await transport.finish()
                    except ReadError as exc:
                        failure = str(exc)
                return {'failure': failure, 'elapsed': clock.now - 1000,
                        'resource_completed': task.done()}
            finally:
                release.set()
                if task is not None:
                    await asyncio.gather(task, return_exceptions=True)
                await transport.close()

    async def test_resource_after_thirty_seconds_uses_existing_source_budget(self):
        result = await self.finish_with_resource_delay(45)
        self.assertIsNone(result['failure'])
        self.assertTrue(result['resource_completed'])
        self.assertGreaterEqual(result['elapsed'], 45)
        self.assertLess(result['elapsed'], 210)

    async def test_resource_after_source_deadline_stays_failed(self):
        result = await self.finish_with_resource_delay(211)
        self.assertEqual(result['failure'], 'capture_tls_resources_not_complete')
        self.assertFalse(result['resource_completed'])
        self.assertEqual(result['elapsed'], 210)

    async def test_finish_waits_for_cascaded_resource_and_reports_its_refusal(self):
        loop = asyncio.get_running_loop()
        a_fulfilled, release_a, b_requested = asyncio.Event(), asyncio.Event(), asyncio.Event()
        release_b = threading.Event()
        tasks = []

        class CascadingSession(Session):
            def get(self, url, **kwargs):
                response = super().get(url, **kwargs)
                if url == ASSET_B:
                    loop.call_soon_threadsafe(b_requested.set)
                    if not release_b.wait(5):
                        raise AssertionError('Fake external resource was never released')
                    return Response(b'Forbidden', status=403)
                return response

        session = CascadingSession()
        route_b = Route(ASSET_B, 'stylesheet')

        async def start_cascaded_request():
            a_fulfilled.set()
            await release_a.wait()
            tasks.append(asyncio.create_task(transport.route(route_b)))
            await b_requested.wait()

        route_a = Route(ASSET_A, on_fulfill=start_cascaded_request)
        with patch('recovered_sources.CA_FILES', FIXTURE_CAS), \
             patch('recovered_sources.requests.Session', return_value=session):
            # Construct inside the external HTTP substitution so no real Session is used.
            transport = self.transport()
            try:
                await transport.start()
                first = asyncio.create_task(transport.route(route_a))
                tasks.append(first)
                await asyncio.wait_for(a_fulfilled.wait(), 2)
                finishing = asyncio.create_task(transport.finish())
                tasks.append(finishing)
                await asyncio.sleep(0)  # finish starts while only A is routed.
                release_a.set()
                await asyncio.wait_for(b_requested.wait(), 2)
                await first
                # Flush completion callbacks without relying on millisecond sleeps.
                await asyncio.sleep(0)
                await asyncio.sleep(0)
                self.assertFalse(finishing.done(), 'A spawned B, which is still waiting for HTTP')
                release_b.set()
                with self.assertRaisesRegex(ReadError, '^capture_tls_http_403$'):
                    await asyncio.wait_for(finishing, 3)
                self.assertTrue(route_b.aborted)
                self.assertIsNone(route_b.fulfilled)
            finally:
                release_a.set()
                release_b.set()
                await asyncio.gather(*tasks, return_exceptions=True)
                await transport.close()

    async def test_cancelled_start_does_not_close_session_during_ca_http_read(self):
        loop = asyncio.get_running_loop()
        requested = asyncio.Event()
        release = threading.Event()

        class BlockedStartupSession(Session):
            def get(self, url, **kwargs):
                if url == CA_FILES[0][0]:
                    loop.call_soon_threadsafe(requested.set)
                    if not release.wait(5):
                        raise AssertionError('Fake CA response was never released')
                return super().get(url, **kwargs)

        session = BlockedStartupSession()
        with patch('recovered_sources.CA_FILES', FIXTURE_CAS), \
             patch('recovered_sources.requests.Session', return_value=session):
            transport = self.transport()
            startup = asyncio.create_task(transport.start())
            try:
                await asyncio.wait_for(requested.wait(), 2)
                startup.cancel()
                await asyncio.sleep(0)
                await asyncio.sleep(0)
                self.assertFalse(session.closed, 'The worker still needs its session and CA directory')
                release.set()
                with self.assertRaises(asyncio.CancelledError):
                    await startup
                self.assertTrue(session.closed)
            finally:
                release.set()
                await asyncio.gather(startup, return_exceptions=True)
                await transport.close()

    async def test_asset_redirect_cannot_broaden_the_verified_host_scope(self):
        redirect = Response(b'', status=302, headers={'Location': 'https://outside.example/source.js'})
        session = Session(page=redirect)
        with patch('recovered_sources.CA_FILES', FIXTURE_CAS), \
             patch('recovered_sources.requests.Session', return_value=session):
            transport = self.transport()
            try:
                await transport.start()
                route = Route(ASSET_A)
                await transport.route(route)
                with self.assertRaisesRegex(ReadError, '^unexpected_source_redirect$'):
                    await transport.finish()
                self.assertTrue(route.aborted)
                self.assertIsNone(route.fulfilled)
                self.assertEqual([url for url, _ in session.calls], [url for url, _ in CA_FILES] + [ASSET_A])
            finally:
                await transport.close()

    async def test_decoded_entity_has_correct_headers_and_keeps_source_csp(self):
        headers = {'Content-Type': 'text/html; charset=utf-8', 'Content-Encoding': 'gzip',
                   'Content-Length': '20', 'Transfer-Encoding': 'chunked',
                   'Content-Security-Policy': "default-src 'self'", 'Set-Cookie': 'anonymous=value'}
        session = Session(page=Response(HTML, headers=headers))
        with patch('recovered_sources.CA_FILES', FIXTURE_CAS), \
             patch('recovered_sources.requests.Session', return_value=session):
            transport = self.transport()
            try:
                await transport.start()
                route = Route(URL, 'document')
                await transport.route(route)
                await transport.finish()
                self.assertFalse(route.aborted)
                self.assertEqual(route.fulfilled['status'], 200)
                self.assertEqual(route.fulfilled['body'], HTML)
                self.assertEqual(route.fulfilled['headers'], {
                    'content-type': 'text/html; charset=utf-8',
                    'content-security-policy': "default-src 'self'"})
            finally:
                await transport.close()

    async def test_unhandled_host_and_public_api_keep_ordinary_browser_transport(self):
        session = Session()
        with patch('recovered_sources.CA_FILES', FIXTURE_CAS), \
             patch('recovered_sources.requests.Session', return_value=session):
            transport = self.transport()
            try:
                await transport.start()
                for url, kind in [('https://outside.example/source.js', 'script'),
                                  ('https://www.vtb.ru/public-api', 'fetch')]:
                    with self.subTest(url=url, kind=kind):
                        route = Route(url, kind)
                        await transport.route(route)
                        self.assertTrue(route.continued)
                        self.assertFalse(route.aborted)
                        self.assertIsNone(route.fulfilled)
                await transport.finish()
                self.assertEqual([url for url, _ in session.calls], [url for url, _ in CA_FILES])
                self.assertEqual(transport.evidence()['responses'], [])
            finally:
                await transport.close()


if __name__ == '__main__':
    unittest.main()
