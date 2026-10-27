"""Provider-scoped response aliases must not weaken request or output validation."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import merchant_extract as m
from test_merchant_extract import EMPTY, SCHEMA, Clock, Response, Transport, answer


ECONOMY = 'deepseek-v4-1-flash-economy-261017'
ROUTES = {
    'orcarouter': 'deepseek/deepseek-v4.1-flash-free',
    'tokenharbor': 'deepseek-v4.1-flash:free',
}


class ResponseAliasTests(unittest.TestCase):
    def run_response(self, data, provider='orcarouter'):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'result'
            transport = Transport([Response(data=data)])
            clock = Clock()
            payload = {'model': ROUTES[provider], 'stream': False,
                       'messages': [{'role': 'user', 'content': 'public source'}]}
            result = m.infer(payload, SCHEMA, out, 'TEST_API_SECRET',
                             provider=provider, session=transport,
                             monotonic=clock.now, sleep=clock.sleep, jitter=lambda: 0)
            extracted = out / 'extracted.json'
            return (result,
                    json.loads(extracted.read_text()) if extracted.exists() else None,
                    json.loads((out / 'attempt-1/response.json').read_text()),
                    json.loads(transport.calls[0][1]['data']))

    def test_orca_snapshot_is_accepted_without_changing_response_or_free_route(self):
        data = answer(model=ECONOMY)
        original = copy.deepcopy(data)
        result, extracted, raw, request = self.run_response(data)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(extracted, EMPTY)
        self.assertEqual(raw, original)
        self.assertEqual(data, original)
        self.assertEqual(result['returned_model'], ECONOMY)
        self.assertEqual(request['model'], 'deepseek/deepseek-v4.1-flash-free')
        self.assertEqual(result['http_attempts'], 1)
        self.assertFalse(result['publication_allowed'])
        self.assertEqual(result['semantic_review'], 'pending')

    def test_orca_snapshot_is_not_accepted_from_tokenharbor(self):
        result, extracted, _, _ = self.run_response(answer(model=ECONOMY), 'tokenharbor')
        self.assertEqual(result['status'], 'failed_validation')
        self.assertEqual(result['error'], 'returned_model_mismatch')
        self.assertIsNone(extracted)

    def test_unknown_economy_versions_and_other_models_stay_rejected(self):
        for model in ('deepseek-v4-1-flash-economy',
                      'deepseek-v4-1-flash-economy-261018',
                      'deepseek-v4-1-flash-economy-261017:free',
                      'other/deepseek-v4-1-flash-economy-261017',
                      'deepseek-v4-1-flash-economy-261017-extra',
                      'deepseek-v4-1-pro-economy-261017', 'other'):
            with self.subTest(model=model):
                result, extracted, _, _ = self.run_response(answer(model=model))
                self.assertEqual(result['error'], 'returned_model_mismatch')
                self.assertIsNone(extracted)

    def test_alias_does_not_accept_truncated_or_blocked_generation(self):
        for finish in ('length', 'content_filter', None):
            with self.subTest(finish=finish):
                result, extracted, _, _ = self.run_response(answer(model=ECONOMY, finish=finish))
                self.assertEqual(result['error'], 'incomplete_or_blocked_generation')
                self.assertIsNone(extracted)

    def test_alias_does_not_bypass_json_schema_or_duplicate_keys(self):
        for content in ('{}', '{"has_offer":false,"has_offer":true,"offers":[],"unknowns":[]}'):
            with self.subTest(content=content):
                result, extracted, _, _ = self.run_response(answer(model=ECONOMY, content=content))
                self.assertEqual(result['error'], 'invalid_final_json')
                self.assertIsNone(extracted)

    def test_alias_preserves_cost_stop_without_discarding_valid_json(self):
        data = answer(model=ECONOMY)
        data['usage']['cost'] = 0.01
        result, extracted, _, _ = self.run_response(data)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(extracted, EMPTY)
        self.assertEqual(result['stop_batch_reason'], 'nonzero_reported_cost')

    def test_returned_alias_is_not_an_approved_request_route(self):
        with tempfile.TemporaryDirectory() as directory:
            transport = Transport([Response()])
            with self.assertRaisesRegex(ValueError, '^unapproved_request_model$'):
                m.infer({'model': ECONOMY}, SCHEMA, Path(directory) / 'result',
                        'TEST_API_SECRET', provider='orcarouter', session=transport)
            self.assertEqual(transport.calls, [])

    def test_existing_free_and_native_names_still_work_for_both_providers(self):
        for provider in ROUTES:
            for model in ('deepseek/deepseek-v4.1-flash-free',
                          'deepseek-v4.1-flash:free', 'deepseek-v4.1-flash',
                          'deepseek-v4-1-flash-261017'):
                with self.subTest(provider=provider, model=model):
                    result, extracted, _, _ = self.run_response(answer(model=model), provider)
                    self.assertEqual(result['status'], 'completed')
                    self.assertEqual(extracted, EMPTY)
