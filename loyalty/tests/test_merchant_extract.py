"""Direct Gemini contracts: complete input, fixed model, bounded retry, no repair."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import merchant_extract as m

SCHEMA = {'type': 'object', 'additionalProperties': False, 'properties': {
    'has_offer': {'type': 'boolean'}, 'offers': {'type': 'array'},
    'unknowns': {'type': 'array'}}, 'required': ['has_offer', 'offers', 'unknowns']}
EMPTY = {'has_offer': False, 'offers': [], 'unknowns': []}


def answer(content=None, finish='STOP', model='gemini-3.8-flash'):
    return {'modelVersion': model, 'candidates': [{'finishReason': finish,
            'content': {'parts': [{'text': json.dumps(EMPTY) if content is None else content}]}}],
            'usageMetadata': {'promptTokenCount': 20, 'candidatesTokenCount': 8}}


class Response:
    def __init__(self, status=200, data=None, headers=None):
        self.status_code = status
        self.content = json.dumps(answer() if data is None else data).encode()
        self.headers = headers or {}


class Transport:
    """Only the external HTTP boundary is faked; the request and retry logic are real."""
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


class Clock:
    def __init__(self): self.t = 0; self.waits = []
    def now(self): return self.t
    def sleep(self, seconds): self.waits.append(seconds); self.t += seconds


class DirectGeminiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name) / 'run'
        self.payload = {'generationConfig': {'responseJsonSchema': SCHEMA},
                        'contents': [{'parts': [{'text': 'A 10%\nB foreign'}]}]}

    def infer(self, transport, clock=None):
        clock = clock or Clock()
        return m.infer(self.payload, SCHEMA, self.out, 'TEST_API_SECRET',
                       session=transport, sleep=clock.sleep, monotonic=clock.now,
                       jitter=lambda: 0)

    def test_full_text_all_images_and_schema_are_preserved(self):
        target = {'partner': 'A', 'program': 'P', 'as_of': '2026-09-27'}
        actual = m.build_request(target, 'A 10%\nB foreign\nA continuation',
                                 [b'first', b'second'], SCHEMA, 'exact system')
        self.assertIsInstance(actual, dict)
        self.assertEqual(actual, {
            'systemInstruction': {'parts': [{'text': 'exact system'}]},
            'contents': [{'role': 'user', 'parts': [
                {'text': 'TARGET: ' + json.dumps(target, ensure_ascii=False) + '\nSCHEMA: '
                 + json.dumps(SCHEMA, ensure_ascii=False) + '\nВсе изображения идут по порядку страниц. Полный текст:\nA 10%\nB foreign\nA continuation'},
                {'inlineData': {'mimeType': 'image/png', 'data': 'Zmlyc3Q='}},
                {'inlineData': {'mimeType': 'image/png', 'data': 'c2Vjb25k'}}]}],
            'generationConfig': {'temperature': 1.0, 'maxOutputTokens': 8192,
                'thinkingConfig': {'thinkingLevel': 'HIGH', 'includeThoughts': False},
                'responseMimeType': 'application/json', 'responseJsonSchema': SCHEMA}})

    def test_completed_json_is_not_changed(self):
        self.assertEqual(m.parse_final(answer(), SCHEMA), EMPTY)

    def test_partial_foreign_and_thought_only_outputs_rejected(self):
        thought = answer(); thought['candidates'][0]['content']['parts'][0]['thought'] = True
        for data in (answer(finish='MAX_TOKENS'), answer(model='other'), thought, answer('')):
            with self.subTest(data=data):
                with self.assertRaises(ValueError): m.parse_final(data, SCHEMA)

    def test_invalid_markdown_duplicates_and_nonfinite_json_rejected(self):
        for text in ('```json\n{}\n```', '{}', '{"has_offer":false,"has_offer":true,"offers":[],"unknowns":[]}',
                     '{"has_offer":true,"offers":[NaN],"unknowns":[]}',
                     '{"has_offer":true,"offers":[1e999],"unknowns":[]}',
                     '{"has_offer":false,"offers":[1],"unknowns":[]}'):
            with self.subTest(text=text):
                with self.assertRaises(ValueError): m.parse_final(answer(text), SCHEMA)

    def test_no_model_tools_or_multiple_candidates(self):
        tool = answer(); tool['candidates'][0]['content']['parts'].append({'functionCall': {'name': 'x'}})
        many = answer(); many['candidates'] *= 2
        for data in (tool, many):
            with self.assertRaises(ValueError): m.parse_final(data, SCHEMA)

    def test_transient_retry_reuses_exact_body_and_preserves_both_attempts(self):
        transport = Transport([Response(503, {'error': {'status': 'UNAVAILABLE'}}), Response()])
        clock = Clock(); result = self.infer(transport, clock)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual([a['http_status'] for a in result['attempts']], [503, 200])
        self.assertEqual(clock.waits, [15])
        self.assertEqual(transport.calls[0][1]['data'], transport.calls[1][1]['data'])
        self.assertEqual(transport.calls[0][0], 'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent')
        self.assertEqual(transport.calls[0][1]['headers']['x-goog-api-key'], 'TEST_API_SECRET')
        self.assertFalse(transport.calls[0][1]['allow_redirects'])
        self.assertTrue((self.out / 'attempt-1/response.json').exists())
        self.assertEqual(json.loads((self.out / 'extracted.json').read_text()), EMPTY)

    def test_three_http_attempts_are_a_hard_bound(self):
        clock = Clock(); transport = Transport([Response(503, {}), Response(503, {}), Response(503, {}), Response()])
        result = self.infer(transport, clock)
        self.assertEqual(result['status'], 'deferred')
        self.assertEqual(len(transport.calls), 3)
        self.assertEqual(clock.waits, [15, 30])
        self.assertFalse((self.out / 'extracted.json').exists())

    def test_retry_after_seconds_is_not_shortened(self):
        clock = Clock(); transport = Transport([Response(429, {}, {'Retry-After': '42'}), Response()])
        result = self.infer(transport, clock)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(clock.waits, [42])

    def test_google_retryinfo_is_respected(self):
        data = {'error': {'details': [{'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '23.5s'}]}}
        clock = Clock(); result = self.infer(Transport([Response(429, data), Response()]), clock)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(clock.waits, [23.5])

    def test_long_retry_after_defers_without_bypassing_daily_limit(self):
        clock = Clock(); transport = Transport([Response(429, {}, {'Retry-After': '86400'}), Response()])
        result = self.infer(transport, clock)
        self.assertEqual(result['status'], 'deferred')
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(clock.waits, [])

    def test_permanent_http_error_does_not_retry_or_become_no_offer(self):
        transport = Transport([Response(403, {'error': {'message': 'denied'}}), Response()])
        result = self.infer(transport)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(len(transport.calls), 1)
        self.assertFalse((self.out / 'extracted.json').exists())

    def test_bad_json_is_not_retried_to_obtain_a_better_answer(self):
        transport = Transport([Response(data=answer('{}')), Response()])
        result = self.infer(transport)
        self.assertEqual(result['status'], 'failed_validation')
        self.assertEqual(len(transport.calls), 1)

    def test_response_timeout_is_recorded_without_hidden_repeat(self):
        import requests
        transport = Transport([requests.ReadTimeout('unknown outcome'), Response()])
        result = self.infer(transport)
        self.assertEqual(result['status'], 'transport_error')
        self.assertEqual(len(transport.calls), 1)

    def test_secret_echo_cannot_enter_logs_or_be_accepted_as_repaired_json(self):
        transport = Transport([Response(403, {'error': {'message': 'TEST_API_SECRET'}})])
        result = self.infer(transport)
        self.assertEqual(result['status'], 'credential_echo')
        self.assertFalse(any(b'TEST_API_SECRET' in p.read_bytes() for p in self.out.rglob('*') if p.is_file()))

    def test_input_and_payload_are_not_mutated(self):
        before = copy.deepcopy(self.payload)
        result = self.infer(Transport([Response()]))
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(self.payload, before)

    def test_output_cannot_overwrite_a_previous_result(self):
        self.out.mkdir(); (self.out/'keep').write_text('original')
        with self.assertRaises(FileExistsError): self.infer(Transport([Response()]))
        self.assertEqual((self.out/'keep').read_text(), 'original')

    def test_missing_key_does_not_send_a_request(self):
        transport = Transport([Response()])
        with self.assertRaises(ValueError):
            m.infer(self.payload, SCHEMA, self.out, '', session=transport)
        self.assertEqual(transport.calls, [])

    def test_malformed_retry_metadata_does_not_hide_original_http_error(self):
        self.assertEqual(m.retry_delay({}, {'error': {'details': None}}), 0)

    def test_retry_after_http_date_and_invalid_values(self):
        self.assertEqual(m.retry_delay({'Retry-After': 'Thu, 01 Jan 1970 00:01:00 GMT'}, {}, now=10), 50)
        for value in ('NaN', 'inf', '-1', 'not-a-date'):
            self.assertEqual(m.retry_delay({'Retry-After': value}, {}, now=10), 0)


class ManifestTests(unittest.TestCase):
    def setUp(self):
        from PIL import Image
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'text.txt').write_text('P 10%\nOther programme 50%', encoding='utf-8')
        Image.new('RGB', (2, 3)).save(self.root / 'one.png')
        self.target = {'partner': 'A', 'program': 'P', 'as_of': '2026-09-27'}
        self.spec = {'id': 'a', 'target': self.target, 'text': 'text.txt', 'images': ['one.png'],
                     'sha256': {n: hashlib.sha256((self.root/n).read_bytes()).hexdigest()
                                for n in ('text.txt', 'one.png')}}
        self.manifest = self.root / 'manifest.json'
        self.write([self.spec])

    def write(self, documents):
        self.manifest.write_text(json.dumps({'documents': documents}), encoding='utf-8')

    def test_all_input_bytes_are_loaded_without_selecting_target_text(self):
        docs = m.load_manifest(self.manifest)
        self.assertIsInstance(docs, list)
        self.assertEqual(docs[0]['text'], 'P 10%\nOther programme 50%')
        self.assertEqual(docs[0]['images'], [(self.root/'one.png').read_bytes()])
        self.assertEqual(docs[0]['target'], self.target)
        self.assertEqual(docs[0]['source'], self.spec)

    def test_corrupt_hash_missing_image_and_path_escape_are_rejected(self):
        for changed in ({'sha256': {'text.txt': '0'*64, 'one.png': self.spec['sha256']['one.png']}},
                        {'images': []}, {'text': '../outside.txt'}):
            self.write([{**self.spec, **changed}])
            with self.assertRaises(ValueError): m.load_manifest(self.manifest)

    def test_duplicate_document_ids_and_incomplete_targets_rejected(self):
        self.write([self.spec, self.spec])
        with self.assertRaises(ValueError): m.load_manifest(self.manifest)
        self.write([{**self.spec, 'target': {'partner': 'A'}}])
        with self.assertRaises(ValueError): m.load_manifest(self.manifest)

    def test_dry_run_does_not_require_secret_or_contact_any_provider(self):
        with patch('merchant_extract.requests.Session') as http:
            code = m.main(['--manifest', str(self.manifest), '--out', str(self.root/'output')])
        self.assertEqual(code, 0)
        self.assertFalse(http.called)
        summary = json.loads((self.root/'output/summary.json').read_text())
        self.assertEqual(summary['requested_model'], 'gemini-3.8-flash')
        self.assertEqual(summary['http_attempts'], 0)
        self.assertFalse(summary['publication_allowed'])

    def test_execute_cli_uses_direct_gemini_and_saves_source_and_result(self):
        import os
        transport = Transport([Response()]); transport.close = lambda: None
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'TEST_API_SECRET'}), patch('merchant_extract.requests.Session', return_value=transport):
            code = m.main(['--manifest', str(self.manifest), '--out', str(self.root/'output'), '--execute'])
        self.assertEqual(code, 0)
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual((self.root/'output/a/page-1.png').read_bytes(), (self.root/'one.png').read_bytes())
        self.assertEqual(json.loads((self.root/'output/a/direct/extracted.json').read_text()), EMPTY)
        self.assertFalse(any(b'TEST_API_SECRET' in p.read_bytes() for p in (self.root/'output').rglob('*') if p.is_file()))

    def test_batch_preserves_completed_and_stops_after_unavailable_provider(self):
        import os
        self.write([self.spec, {**self.spec, 'id': 'b'}, {**self.spec, 'id': 'c'}])
        transport = Transport([Response(), Response(403, {}), Response()]); transport.close = lambda: None
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'TEST_API_SECRET'}), patch('merchant_extract.requests.Session', return_value=transport), patch('merchant_extract.time.sleep'):
            code = m.main(['--manifest', str(self.manifest), '--out', str(self.root/'output'), '--execute'])
        self.assertEqual(code, 2)
        self.assertEqual(len(transport.calls), 2)
        summary = json.loads((self.root/'output/summary.json').read_text())
        self.assertEqual(summary['completed'], 1)
        self.assertEqual(summary['not_attempted'], ['c'])
        self.assertFalse((self.root/'output/b/direct/extracted.json').exists())


if __name__ == '__main__': unittest.main()
