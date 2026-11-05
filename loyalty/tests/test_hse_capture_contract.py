"""Scoped source capture must preserve identity and remain an explicit scope."""
import hashlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import merchant_evidence as evidence
import merchant_extract as extractor
from hse_alumni import ROOT, PROGRAM
from test_hse_alumni import page, card, section


class HseReadinessTests(unittest.IsolatedAsyncioTestCase):
    def browser_page(self, raw):
        # Only the browser boundary is replaced; ownership uses the actual DOM parser.
        return SimpleNamespace(content=AsyncMock(return_value=raw), evaluate=AsyncMock(),
                               wait_for_function=AsyncMock())

    async def test_full_detail_selects_all_owned_sections_without_other_partner(self):
        raw = page(details=section('a', '<h2>A</h2><p>Скидка 13%</p>')
                   + '<div class="builder-section"><p>Только по карте выпускника</p></div>'
                   + section('b', '<h2>B</h2><p>Соседняя скидка 99%</p>'))
        capture = await evidence.prepare_public_page(self.browser_page(raw),
            {'url': ROOT, 'partner': 'a', 'program': PROGRAM})
        self.assertEqual(capture['scope'], 'hse_partner_sections')
        self.assertTrue(capture['content_ready'])
        selected = '\n'.join(r['source_text'] for r in capture['selection']['regions'])
        self.assertIn('Только по карте выпускника', selected)
        self.assertNotIn('Соседняя скидка 99%', selected)

    async def test_preview_only_is_not_admitted_as_a_complete_source(self):
        raw = page(cards=card('missing'), details='')
        with self.assertRaisesRegex(ValueError, 'hse_detail_missing'):
            await evidence.prepare_public_page(self.browser_page(raw),
                {'url': ROOT, 'partner': 'missing', 'program': PROGRAM})

    async def test_owned_image_only_region_keeps_its_pixels_without_invented_text(self):
        from hse_capture import capture_regions
        from hse_capture_plan import fragment_evidence
        raw = '<div><img src="https://example.org/terms.png"></div>'
        output = io.BytesIO()
        Image.new('RGB', (2, 2), 'black').save(output, format='PNG')

        class Element:
            async def count(self): return 1
            async def is_visible(self): return True
            async def scroll_into_view_if_needed(self, **kwargs): pass
            async def evaluate(self, expression):
                if 'outerHTML' in expression:
                    return raw
                if 'getBoundingClientRect' in expression:
                    return {'width': 2, 'height': 2, 'scrollWidth': 2, 'scrollHeight': 2}
                raise AssertionError('Unexpected browser operation')
            async def inner_text(self, **kwargs): return ''
            async def screenshot(self, **kwargs): return output.getvalue()

        element = Element()
        def locate(selector):
            self.assertEqual(selector, 'div')
            return element
        plan = {'regions': [{'role': 'detail', 'locator': 'div', 'visual_only': True,
                             **fragment_evidence(raw)}]}
        try:
            text, images, regions = await capture_regions(SimpleNamespace(locator=locate), plan, {})
        except ValueError as exc:
            self.fail(f'Owned image-only terms were discarded: {exc}')
        self.assertEqual(len(images), 1)
        self.assertEqual(regions[0]['text'], '')
        self.assertEqual(regions[0]['image_count'], 1)
        self.assertNotIn('Скидка', text)


class HseManifestTests(unittest.TestCase):
    def scoped_fixture(self, root):
        from hse_capture_plan import selection
        from hse_capture import joined_text
        raw = page(cards=card('a'), details=section('a',
            '<h2>A</h2><p>Промокод AB CD действует до окончания акции.</p>'))
        target = {'partner': 'a', 'program': PROGRAM, 'as_of': '2026-11-05'}
        plan = selection(raw, {**target, 'url': ROOT})
        (root / 'source.html').write_text(raw, encoding='utf-8')
        output = io.BytesIO()
        Image.new('RGB', (2, 2)).save(output, format='PNG')
        regions, names = [], []
        for index, selected in enumerate(plan['regions']):
            name = f'region-{index}.png'
            (root / name).write_bytes(output.getvalue())
            names.append(name)
            regions.append({'role': selected['role'], 'locator': selected['locator'],
                'text': selected['source_text'], 'image_start': index, 'image_count': 1,
                'layout': {'order': 'row_major_left_to_right_then_top_to_bottom',
                           'width': 2, 'height': 2,
                           'tiles': [{'x': 0, 'y': 0, 'width': 2, 'height': 2}]}})
        (root / 'text.txt').write_text(joined_text(regions), encoding='utf-8')
        return {'id': 'hse_fixture', 'source_url': ROOT, 'source_html': 'source.html',
                'target': target, 'text': 'text.txt', 'images': names,
                'sha256': {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                           for name in ('text.txt', 'source.html', *names)},
                'capture': {'scope': 'hse_partner_sections', 'target_found': True,
                            'content_ready': True, 'selection': plan, 'regions': regions}}

    def test_rehashed_text_cannot_merge_distinct_promocode_tokens(self):
        from hse_capture import joined_text
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self.scoped_fixture(root)
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({'documents': [spec]}), encoding='utf-8')
            self.assertEqual(len(extractor.load_manifest(manifest)), 1)
            changed = copy.deepcopy(spec)
            for region in changed['capture']['regions']:
                region['text'] = region['text'].replace('AB CD', 'ABCD')
            (root / 'text.txt').write_text(joined_text(changed['capture']['regions']), encoding='utf-8')
            changed['sha256']['text.txt'] = hashlib.sha256((root / 'text.txt').read_bytes()).hexdigest()
            manifest.write_text(json.dumps({'documents': [changed]}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'hse_scope_text_mismatch'):
                extractor.load_manifest(manifest)

    def test_rehashed_original_html_cannot_replace_captured_partner_terms(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = self.scoped_fixture(root)
            raw = (root / 'source.html').read_text().replace('AB CD', 'OTHER_ONLY')
            (root / 'source.html').write_text(raw, encoding='utf-8')
            spec['sha256']['source.html'] = hashlib.sha256((root / 'source.html').read_bytes()).hexdigest()
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({'documents': [spec]}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'hse_scope_selection_mismatch'):
                extractor.load_manifest(manifest)

    def test_scope_without_original_html_cannot_pass_manifest_admission(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            text = 'Полные исходные условия выбранного партнёра.'
            (root / 'text.txt').write_text(text, encoding='utf-8')
            output = io.BytesIO()
            Image.new('RGB', (2, 2)).save(output, format='PNG')
            (root / 'image.png').write_bytes(output.getvalue())
            spec = {'id': 'hse_fixture', 'source_url': ROOT,
                    'target': {'partner': 'a', 'program': PROGRAM, 'as_of': '2026-11-05'},
                    'text': 'text.txt', 'images': ['image.png'],
                    'sha256': {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                               for name in ('text.txt', 'image.png')},
                    'capture': {'scope': 'hse_partner_sections'}}
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({'documents': [spec]}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'hse_scope'):
                extractor.load_manifest(manifest)

    def test_scoped_input_is_labelled_even_without_old_collector_records(self):
        document = {'text': 'Исходные условия.',
                    'source': {'capture': {'scope': 'hse_partner_sections'}}}
        actual = evidence.request_text(document)
        self.assertIn('выбранных разделов', actual)
        self.assertTrue(actual.endswith('Исходные условия.'))


if __name__ == '__main__':
    unittest.main()
