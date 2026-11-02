"""Capture scheduling contracts; only browser acquisition is replaced locally."""
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from PIL import Image
from playwright.async_api import Error as BrowserError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import merchant_queue as q


class Clock:
    def __init__(self):
        self.wall = 1793577600
        self.elapsed = 0

    def time(self):
        return self.wall

    def monotonic(self):
        return self.elapsed

    def advance(self, seconds):
        self.wall += seconds
        self.elapsed += seconds


class CaptureFairnessTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.state_path = self.root / 'state.json'
        self.state = q.new_state()
        self.clock = Clock()
        self.registry = self.root / 'registry'
        self.registry.mkdir()
        for name in ('partner_pages.json', 'known_rules.json'):
            (self.registry / name).write_text('{}', encoding='utf-8')
        image = io.BytesIO()
        Image.new('RGB', (2, 2)).save(image, format='PNG')
        self.png = image.getvalue()

    def add(self, ident, origin, checked=None, previous=False):
        target = {'id': ident, 'url': f'https://{origin}/{ident}',
                  'partner': ident, 'program': 'Program',
                  'source_records': [{'partner_name': ident, 'program': 'Program',
                                      'benefit_text': 'Скидка 10%'}]}
        item = {'target': target}
        if checked is not None:
            item['last_checked'] = checked
        if previous:
            item.update(status='completed', fingerprint='prior-input-hash',
                        inferred_as_of='2026-10-01', inferred_provider='orcarouter',
                        extracted={'has_offer': True, 'offers': [{'prior': 'answer'}]})
        self.state['items'][ident] = item

    def document(self, target, out):
        folder = out / target['id']
        folder.mkdir()
        text = folder / 'text.txt'
        image = folder / 'page.png'
        text.write_text(f"{target['partner']}: Скидка 10%", encoding='utf-8')
        image.write_bytes(self.png)
        names = [str(path.relative_to(out)) for path in (text, image)]
        spec = {'id': target['id'], 'source_url': q.evidence.capture_url(target),
                'target': {'partner': target['partner'], 'program': target['program'],
                           'as_of': '2026-11-02'},
                'text': names[0], 'images': [names[1]],
                'sha256': {name: hashlib.sha256((out / name).read_bytes()).hexdigest()
                           for name in names}}
        return q.evidence.attach(spec, target, {'target_found': True, 'content_ready': True})

    async def prepare(self, limit, *, errors=None, durations=None, corrupt=()):
        errors, durations = errors or {}, durations or {}
        calls = []
        browser = SimpleNamespace(close=AsyncMock())
        playwright = MagicMock()
        playwright.__aenter__ = AsyncMock(return_value=SimpleNamespace(
            chromium=SimpleNamespace(launch=AsyncMock(return_value=browser))))
        playwright.__aexit__ = AsyncMock(return_value=False)

        async def capture(actual_browser, target, out):
            self.assertIs(actual_browser, browser)
            ident = target['id']
            calls.append(ident)
            self.clock.advance(durations.get(ident, 0))
            if ident in errors:
                raise errors[ident]
            spec = self.document(target, out)
            if ident in corrupt:
                spec['sha256'][spec['text']] = '0' * 64
            return spec

        out = self.root / 'capture'
        q.write_state(self.state_path, self.state)
        with patch.object(q, 'HERE', self.registry), patch.object(q, 'time', self.clock), \
                patch.object(q, 'capture_page', capture), \
                patch('playwright.async_api.async_playwright', return_value=playwright):
            result = await q.prepare_queue(self.state_path, self.root / 'absent-catalog.json',
                                           out, limit)
        browser.close.assert_awaited_once()
        self.state = q.read_state(self.state_path)
        manifest = json.loads((out / 'manifest.json').read_text(encoding='utf-8'))
        if manifest['documents']:
            # Real PNG, path, source-record, hash and document validation is active.
            q.extractor.load_manifest(out / 'manifest.json', max_documents=q.MAX_CAPTURE_PAGES)
        return result, manifest, calls

    @staticmethod
    def dns_error():
        return BrowserError('Page.goto: net::ERR_NAME_NOT_RESOLVED at https://dead.example/')

    async def test_round_robin_preserves_oldest_order_within_each_origin(self):
        self.add('a-late', 'a.example', checked=20)
        self.add('a-first', 'a.example')
        self.add('a-middle', 'a.example', checked=10)
        self.add('a-middle-twin', 'a.example', checked=10)
        self.add('b-late', 'b.example', checked=40)
        self.add('b-first', 'b.example', checked=30)
        result, manifest, calls = await self.prepare(6)
        self.assertEqual(calls, ['a-first', 'b-first', 'a-middle', 'b-late',
                                 'a-middle-twin', 'a-late'])
        self.assertEqual(result['captured'], 6)
        self.assertEqual([doc['id'] for doc in manifest['documents']], calls)

    async def test_27_failed_targets_do_not_block_other_origins_within_attempt_budget(self):
        dead = [f'a{index:02}' for index in range(1, 28)]
        for ident in dead:
            self.add(ident, 'dead.example', previous=ident != 'a01')
        for ident in ('b1', 'b2', 'b3', 'b4'):
            self.add(ident, 'live.example', previous=ident == 'b4')
        before = copy.deepcopy(self.state['items'])
        result, manifest, calls = await self.prepare(5, errors={ident: self.dns_error() for ident in dead})
        self.assertEqual(calls, ['a01', 'b1', 'a02', 'b2', 'a03'])
        self.assertEqual(result['captured'], 2)
        self.assertEqual([doc['id'] for doc in manifest['documents']], ['b1', 'b2'])
        self.assertEqual([row['id'] for row in result['observations']], calls)
        for ident in before.keys() - set(calls):
            self.assertEqual(self.state['items'][ident], before[ident])
        for ident in ('a01', 'a02', 'a03'):
            self.assertEqual(self.state['items'][ident]['capture_status'], 'failed')
            self.assertEqual(self.state['items'][ident]['last_checked'], self.clock.time())
        self.assertNotIn('status', self.state['items']['a01'])
        self.assertEqual(self.state['items']['a02']['extracted'], before['a02']['extracted'])
        self.assertEqual(self.state['items']['a02']['fingerprint'], before['a02']['fingerprint'])
        self.assertFalse(result['publication_allowed'])

    async def test_time_budget_stops_new_attempts_without_touching_omitted_items(self):
        for ident in ('a1', 'a2', 'a3', 'a4'):
            self.add(ident, 'dead.example')
        for ident in ('b1', 'b2', 'b3', 'b4'):
            self.add(ident, 'live.example', previous=ident == 'b4')
        before = copy.deepcopy(self.state['items'])
        result, manifest, calls = await self.prepare(8, errors={'a1': self.dns_error()},
            durations={ident: 200 for ident in before})
        self.assertEqual(calls, ['a1', 'b1', 'a2', 'b2', 'a3', 'b3'])
        self.assertEqual(result['captured'], 5)
        self.assertEqual([doc['id'] for doc in manifest['documents']], calls[1:])
        for ident in ('a4', 'b4'):
            self.assertEqual(self.state['items'][ident], before[ident])

    async def test_non_dns_page_failures_do_not_suppress_the_origin(self):
        for ident in ('a1', 'a2', 'a3'):
            self.add(ident, 'a.example')
        result, manifest, calls = await self.prepare(3, errors={
            'a1': BrowserError('Page.goto: net::ERR_CONNECTION_RESET'),
            'a2': ValueError('http_404')})
        self.assertEqual(calls, ['a1', 'a2', 'a3'])
        self.assertEqual([row['status'] for row in result['observations']],
                         ['failed', 'failed', 'captured'])
        self.assertEqual([doc['id'] for doc in manifest['documents']], ['a3'])

    async def test_dns_navigation_errors_do_not_skip_same_origin_neighbour(self):
        for ident in ('a1', 'a2', 'a3'):
            self.add(ident, 'a.example')
        # goto may fail resolving a redirect destination rather than the starting origin.
        error = 'Page.goto: net::ERR_NAME_NOT_RESOLVED at https://redirect.example/'
        result, manifest, calls = await self.prepare(3, errors={
            'a1': BrowserError(error), 'a2': BrowserError(error)})
        self.assertEqual(calls, ['a1', 'a2', 'a3'])
        self.assertEqual([row['status'] for row in result['observations']],
                         ['failed', 'failed', 'captured'])
        self.assertEqual([doc['id'] for doc in manifest['documents']], ['a3'])

    async def test_origin_uses_actual_capture_url_and_normalizes_host_and_default_port(self):
        self.add('a-detail', 'a.example')
        target = self.state['items']['a-detail']['target']
        target['url'] = 'http://a.example/legacy-catalogue'
        detail_url = 'https://A.EXAMPLE:443/published-detail'
        target['source_records'][0]['benefit_url'] = detail_url
        self.add('a2', 'a.example')
        self.add('a3', 'a.example:443')
        self.add('b1', 'b.example')
        self.assertEqual(q.evidence.capture_url(target), detail_url)
        result, manifest, calls = await self.prepare(4)
        self.assertEqual(calls, ['a-detail', 'b1', 'a2', 'a3'])
        self.assertEqual(result['captured'], 4)
        self.assertEqual([doc['id'] for doc in manifest['documents']], calls)
        self.assertEqual(manifest['documents'][0]['source_url'], detail_url)

    async def test_real_manifest_rejection_does_not_suppress_valid_neighbour(self):
        for ident in ('a1', 'a2', 'a3'):
            self.add(ident, 'a.example', previous=ident == 'a1')
        before = copy.deepcopy(self.state['items']['a1'])
        result, manifest, calls = await self.prepare(3, corrupt=('a1', 'a2'))
        self.assertEqual(calls, ['a1', 'a2', 'a3'])
        self.assertEqual([doc['id'] for doc in manifest['documents']], ['a3'])
        failed = [row for row in result['observations'] if row['status'] == 'failed']
        self.assertEqual(len(failed), 2)
        self.assertTrue(all(row['error'] == 'source_hash_mismatch' for row in failed))
        self.assertEqual(self.state['items']['a1']['extracted'], before['extracted'])

    async def test_malformed_legacy_urls_fail_individually_and_do_not_abort_grouping(self):
        malformed = {'bad1': 'https://[unclosed',
                     'bad2': 'https://bad.example:invalid/legacy', 'bad3': 'not a URL'}
        for ident, url in malformed.items():
            self.add(ident, 'unused.example', previous=True)
            self.state['items'][ident]['target']['url'] = url
        for ident in ('good1', 'good2'):
            self.add(ident, 'live.example')
        before = copy.deepcopy(self.state['items'])
        result, manifest, calls = await self.prepare(5, errors={
            ident: ValueError('malformed_source_url') for ident in malformed})
        self.assertEqual(calls, ['bad1', 'bad2', 'bad3', 'good1', 'good2'])
        self.assertEqual([doc['id'] for doc in manifest['documents']], ['good1', 'good2'])
        self.assertEqual([row['status'] for row in result['observations']],
                         ['failed', 'failed', 'failed', 'captured', 'captured'])
        for ident in malformed:
            self.assertEqual(self.state['items'][ident]['capture_status'], 'failed')
            self.assertEqual(self.state['items'][ident]['extracted'], before[ident]['extracted'])


if __name__ == '__main__':
    unittest.main()
