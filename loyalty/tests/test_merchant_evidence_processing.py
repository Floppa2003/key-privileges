"""Exercise actual request preparation, cache and queue; replace HTTP only."""
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import merchant_extract as m
import merchant_queue as q
from test_merchant_queue import Clock, HTTP, Response, SCHEMA, EMPTY
from test_merchant_evidence import record


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                   separators=(',', ':')).encode()).hexdigest()


class EvidenceProcessingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state = q.new_state(); self.path = self.root / 'state.json'; self.clock = Clock()
        png = io.BytesIO(); Image.new('RGB', (2, 2)).save(png, format='PNG'); self.png = png.getvalue()

    def document(self, records=None, ready=True):
        records = [] if records is None else records
        return {'id': 'target', 'target': {'partner': 'Independent merchant',
                'program': 'Public programme', 'as_of': '2026-10-31'},
                'text': 'Публичная страница; здесь нет нужной карточки.', 'images': [self.png],
                'source': {'source_url': 'https://example.org/benefits',
                    'source_records': records, 'source_records_sha256': digest(records),
                    'capture': {'input_contract_version': 2, 'target_found': ready,
                                'content_ready': ready, 'scope': 'page'}}}

    def run_document(self, document, output=EMPTY, name='run'):
        data = {'model': 'deepseek-v4-1-flash-261017', 'choices': [{'finish_reason': 'stop',
                'message': {'role': 'assistant', 'content': json.dumps(output)}}], 'usage': {'cost': 0}}
        http = HTTP([Response(data=data)])
        result = q.process_documents([document], self.state, self.path, self.root / name,
            'TEST_SECRET', SCHEMA, 'prompt', session=http, now=self.clock.now,
            sleep=self.clock.sleep, max_requests=1)
        return result, http

    def test_original_record_is_in_actual_request_without_rewriting_images_or_text(self):
        original = record()
        doc = self.document([original], ready=False)
        result, http = self.run_document(doc, {'has_offer': True, 'offers': [{'value': 17}], 'unknowns': []})
        body = json.loads(http.calls[0][1]['data'])
        text = body['messages'][1]['content'][0]['text']
        self.assertIn('unknown_source_field', text)
        self.assertIn('<p>Полные исходные условия.</p>', text)
        self.assertIn('Бронирование через консьерж-сервис.', text)
        self.assertIn(doc['text'], text)
        self.assertEqual(len(body['messages'][1]['content']), 2)
        import base64
        self.assertEqual(base64.b64decode(body['messages'][1]['content'][1]['image_url']['url'].split(',')[1]), self.png)
        self.assertEqual(result['completed'], 1)
        saved = json.loads((self.root / 'run/target/input.json').read_text())
        self.assertEqual(saved['source']['source_records'], [original])

    def test_missing_target_negative_is_saved_for_diagnosis_not_completed_or_cached(self):
        result, _ = self.run_document(self.document(ready=False))
        self.assertEqual(result['completed'], 0)
        item = self.state['items']['target']
        self.assertEqual(item['status'], 'needs_source')
        self.assertNotIn('extracted', item)
        self.assertEqual(item['unresolved_extraction'], EMPTY)
        self.assertTrue((self.root / 'run/target/direct/extracted.json').exists())

    def test_negative_contradicting_supplied_terms_is_not_certified_as_no_offer(self):
        result, _ = self.run_document(self.document([record()], ready=False))
        self.assertEqual(result['completed'], 0)
        self.assertEqual(self.state['items']['target']['status'], 'needs_review')
        self.assertEqual(self.state['items']['target']['unresolved_extraction'], EMPTY)
        self.assertNotIn('extracted', self.state['items']['target'])

    def test_negative_on_ready_target_without_collector_offer_remains_valid(self):
        result, _ = self.run_document(self.document(ready=True))
        self.assertEqual(result['completed'], 1)
        self.assertEqual(self.state['items']['target']['extracted'], EMPTY)

    def test_new_original_terms_invalidate_cache_but_acquisition_timestamp_does_not(self):
        doc = self.document([record()]); first = q.fingerprint(doc, SCHEMA, 'prompt')
        copy_doc = copy.deepcopy(doc)
        copy_doc['source']['source_records'][0]['observed_at'] = '2026-11-01T09:01:02Z'
        copy_doc['source']['source_records_sha256'] = digest(copy_doc['source']['source_records'])
        self.assertEqual(q.fingerprint(copy_doc, SCHEMA, 'prompt'), first)
        copy_doc['source']['source_records'][0]['details']['public_item']['description'] = 'Новые реальные условия'
        copy_doc['source']['source_records_sha256'] = digest(copy_doc['source']['source_records'])
        self.assertNotEqual(q.fingerprint(copy_doc, SCHEMA, 'prompt'), first)

    def test_migration_prioritizes_old_false_results_without_erasing_audit_or_quota(self):
        target = q.discover_targets({'records': [record()]}, {}, {})[0]
        legacy_target = {k: v for k, v in target.items() if k != 'source_records'}
        self.state['items'][target['id']] = {'target': legacy_target, 'extracted': EMPTY,
            'fingerprint': 'old', 'status': 'completed', 'last_checked': 123456}
        self.state['usage'] = {'date': '2026-10-31', 'attempts': 49}
        q.merge_targets(self.state, [target])
        item = self.state['items'][target['id']]
        self.assertEqual(item['extracted'], EMPTY)
        self.assertEqual(item['status'], 'needs_source')
        self.assertEqual(item['last_checked'], 0)
        self.assertEqual(self.state['usage']['attempts'], 49)

    def test_manifest_detects_changed_original_records_and_keeps_valid_source(self):
        (self.root / 'text.txt').write_text('Полная страница')
        (self.root / 'page.png').write_bytes(self.png)
        source = self.document([record()])['source']
        spec = {**source, 'id': 'target', 'target': self.document()['target'],
                'text': 'text.txt', 'images': ['page.png'],
                'sha256': {name: hashlib.sha256((self.root / name).read_bytes()).hexdigest()
                           for name in ['text.txt', 'page.png']}}
        path = self.root / 'manifest.json'
        path.write_text(json.dumps({'documents': [spec]}))
        self.assertEqual(m.load_manifest(path)[0]['source']['source_records'][0]['native_id'], '731')
        spec['source_records'][0]['details']['public_item']['offer'] = 'tampered'
        path.write_text(json.dumps({'documents': [spec]}))
        with self.assertRaisesRegex(ValueError, 'source_records_hash_mismatch'):
            m.load_manifest(path)


if __name__ == '__main__':
    unittest.main()
