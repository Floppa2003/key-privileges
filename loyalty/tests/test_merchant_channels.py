"""New route integration, with doubles only at HTTP/time boundaries."""
import base64
import copy
from decimal import Decimal
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import merchant_channels as c
import merchant_extract as m
import merchant_queue as q

SCHEMA = {'type': 'object', 'properties': {'has_offer': {'type': 'boolean'}, 'offers': {'type': 'array'},
    'unknowns': {'type': 'array'}}, 'required': ['has_offer', 'offers', 'unknowns']}
EMPTY = {'has_offer': False, 'offers': [], 'unknowns': []}
KEY = 'TEST_CHANNEL_SECRET'
NOW = 1793358000


def answer(provider, cost=0):
    return {'model': c.NEW_PROVIDERS[provider]['model'], 'choices': [{'finish_reason': 'stop',
        'message': {'content': json.dumps(EMPTY)}}],
        'usage': {'cost': cost, 'is_byok': False, 'total_tokens': 100}}


class Response:
    def __init__(self, data, status=200):
        self.status_code = status
        self.content = json.dumps(data).encode()
        self.headers = {}


class HTTP:
    def __init__(self, responses=(), remaining=48, credits=None, model=None):
        self.responses = list(responses)
        self.calls = []
        self.gets = []
        self.remaining = remaining
        self.credits = credits or {'balance': '4.99', 'total_used': '0.01'}
        self.model = model or {'id': c.SUPER_VL, 'context_window': 1000000,
            'pricing': {'input': '0.0000002', 'output': '0.0000005'}}
    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value
    def get(self, url, **kwargs):
        self.gets.append((url, kwargs))
        if url.endswith('/key'):
            return Response({'data': {'limit_remaining': 9999,
                'free_model_daily_requests': {'remaining': self.remaining}}})
        if url.endswith('/credits'):
            return Response(self.credits)
        if url.endswith('/models'):
            return Response({'data': [self.model]})
        raise AssertionError(url)


class ChannelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state_path = self.root / 'state.json'
        self.state = q.new_state()
        raw = io.BytesIO()
        Image.new('RGB', (2, 2)).save(raw, format='PNG')
        self.png = raw.getvalue()
        self.document = {'id': 'example', 'target': {'partner': 'Example', 'program': 'P', 'as_of': '2026-10-30'},
            'text': 'No published offer.', 'images': [self.png, self.png], 'source': {'source_url': 'https://example.org'}}
    def payload(self, provider):
        return m.build_request(self.document['target'], self.document['text'], self.document['images'],
                               SCHEMA, 'source-only JSON', provider=provider)
    def batch(self, provider, http, name='result'):
        return q.process_documents([self.document], self.state, self.state_path, self.root / name,
            KEY, SCHEMA, 'source-only JSON', provider=provider, session=http, now=lambda: NOW,
            sleep=lambda _: None, max_requests=1)

    def test_all_exact_routes_are_registered_without_replacing_originals(self):
        self.assertEqual(set(m.PROVIDERS), {'orcarouter', 'tokenharbor', *c.NEW_PROVIDERS})
        for provider, config in c.NEW_PROVIDERS.items():
            self.assertEqual(m.provider_config(provider), config)
        self.assertEqual(m.MODEL, 'deepseek/deepseek-v4.1-flash-free')

    def test_new_payloads_keep_all_images_full_text_target_and_schema(self):
        for provider in c.NEW_PROVIDERS:
            payload = self.payload(provider)
            rendered = json.dumps(payload, ensure_ascii=False)
            self.assertIn(self.document['text'], rendered)
            self.assertIn('Example', rendered)
            self.assertIn('has_offer', rendered)
            self.assertEqual(rendered.count(base64.b64encode(self.png).decode()), 2)
            self.assertNotIn('tools', payload)
            self.assertNotIn('web_search_options', payload)
            self.assertNotIn(base64.b64encode(self.png).decode(), json.dumps(c.redact_images(payload, provider)))

    def test_openrouter_and_kilo_high_reasoning_vercel_default(self):
        for provider in ('openrouter', 'kilo'):
            self.assertEqual(self.payload(provider)['reasoning']['effort'], 'high')
            self.assertEqual(self.payload(provider)['max_tokens'], 16384)
        for provider in ('vercel', 'experiential'):
            self.assertNotIn('reasoning', self.payload(provider))

    def test_expected_models_and_wrong_models(self):
        for provider in ('experiential', 'kilo', 'openrouter', 'vercel'):
            self.assertEqual(m.parse_final(answer(provider), SCHEMA, provider=provider), EMPTY)
            wrong = answer(provider)
            wrong['model'] = 'unapproved-model'
            with self.assertRaises(ValueError):
                m.parse_final(wrong, SCHEMA, provider=provider)

    def test_native_gemini_parse_and_token_accounting(self):
        data = {'modelVersion': 'gemini-3.8-flash', 'candidates': [{'finishReason': 'STOP',
            'content': {'parts': [{'text': 'private thought', 'thought': True}, {'text': json.dumps(EMPTY)}]}}],
            'usageMetadata': {'promptTokenCount': 100, 'candidatesTokenCount': 20,
                              'thoughtsTokenCount': 30, 'totalTokenCount': 150}}
        self.assertEqual(m.parse_final(data, SCHEMA, provider='gemini'), EMPTY)
        native = c.normalize_response(data, 'gemini')
        self.assertEqual(native['usage']['completion_tokens'], 50)
        self.assertEqual(native['usage']['total_tokens'], 150)
        data['candidates'][0]['content']['parts'].append({'functionCall': {'name': 'bad'}})
        with self.assertRaises(ValueError):
            m.parse_final(data, SCHEMA, provider='gemini')

    def test_new_free_routes_reject_paid_and_byok_costs(self):
        for provider in ('experiential', 'kilo', 'openrouter'):
            self.assertEqual(c.cost_warning(answer(provider, 0.01), provider), 'nonzero_reported_cost')
            data = answer(provider)
            data['usage']['is_byok'] = True
            self.assertEqual(c.cost_warning(data, provider), 'unexpected_byok')
            self.assertEqual(c.cost_warning({}, provider), 'missing_reported_cost')
        self.assertIsNone(c.cost_warning(answer('vercel', 0.001), 'vercel'))
        self.assertEqual(c.cost_warning(answer('vercel', float('nan')), 'vercel'), 'invalid_reported_cost')

    def test_openrouter_uses_actual_request_counter_not_spending_cap(self):
        result = c.admission('openrouter', {}, KEY, {}, NOW, HTTP(remaining=0))
        self.assertFalse(result['allowed'])
        self.assertEqual(result['account_remaining'], 0)
        self.assertTrue(c.admission('openrouter', {}, KEY, {}, NOW, HTTP(remaining=48))['allowed'])
        self.assertFalse(c.admission('openrouter', {}, KEY, {}, NOW, HTTP(remaining=None))['allowed'])

    def test_kilo_pacing_and_daily_ceiling(self):
        self.assertGreaterEqual(q.PROVIDER_INTERVALS['kilo'], 20)
        self.assertLessEqual(q.PROVIDER_DAILY_LIMITS['kilo'], 180)

    def test_experiential_counts_input_plus_output_without_double_reasoning(self):
        ledger = {}
        c.reconcile('experiential', ledger, {}, {'http_attempts': 1, 'usage': {'total_tokens': 10619}}, NOW)
        self.assertEqual(ledger['budget']['tokens'], 10619)
        ledger['budget']['tokens'] = 1000000
        self.assertFalse(c.admission('experiential', {}, KEY, ledger, NOW)['allowed'])
        self.assertTrue(c.admission('experiential', {}, KEY, ledger, NOW + 86400)['allowed'])

    def test_vercel_reserves_whole_context_not_one_example_cost(self):
        check = c.admission('vercel', self.payload('vercel'), KEY, {}, NOW, HTTP())
        self.assertTrue(check['allowed'], check)
        self.assertGreater(Decimal(check['reservation_usd']), Decimal('0.2'))
        self.assertLess(Decimal(check['reservation_usd']), Decimal('1'))

    def test_vercel_unknown_grant_balance_or_price_blocks_without_post(self):
        for client in (HTTP(credits={'balance': '6', 'total_used': '0'}),
                       HTTP(credits={'balance': '0', 'total_used': '5'}),
                       HTTP(model={'id': c.SUPER_VL, 'pricing': {}}),
                       HTTP(model={'id': c.SUPER_VL, 'context_window': 1000,
                           'pricing': {'input': '0', 'output': '0', 'image': '1'}})):
            check = c.admission('vercel', self.payload('vercel'), KEY, {}, NOW, client)
            self.assertFalse(check['allowed'], check)
            self.assertEqual(client.calls, [])

    def test_vercel_reservation_persists_then_refunds_only_known_difference(self):
        ledger = {}
        check = c.admission('vercel', self.payload('vercel'), KEY, ledger, NOW, HTTP())
        c.reserve_budget(ledger, check, NOW)
        saved = json.loads(json.dumps(ledger))
        self.assertTrue(saved['spend_needs_review'])
        self.assertFalse(c.admission('vercel', self.payload('vercel'), KEY, saved, NOW, HTTP())['allowed'])
        c.reconcile('vercel', saved, check, {'usage': {'cost': '0.0013669'}}, NOW)
        self.assertFalse(saved['spend_needs_review'])
        self.assertEqual(Decimal(saved['budget']['usd']), Decimal('0.0013669'))
        self.assertEqual(Decimal(saved['credit_remaining']), Decimal('4.9886331'))

    def test_unknown_vercel_network_outcome_keeps_reservation_across_days(self):
        ledger = {}
        check = c.admission('vercel', self.payload('vercel'), KEY, ledger, NOW, HTTP())
        c.reserve_budget(ledger, check, NOW)
        result = {'status': 'transport_error', 'attempts': [{'error_type': 'ReadTimeout'}]}
        c.reconcile('vercel', ledger, check, result, NOW)
        self.assertTrue(ledger['spend_needs_review'])
        self.assertFalse(c.admission('vercel', self.payload('vercel'), KEY, ledger, NOW + 86400, HTTP())['allowed'])

    def test_explicit_vercel_access_denial_releases_reservation(self):
        ledger = {}
        check = c.admission('vercel', self.payload('vercel'), KEY, ledger, NOW, HTTP())
        c.reserve_budget(ledger, check, NOW)
        c.reconcile('vercel', ledger, check, {'attempts': [{'http_status': 403}]}, NOW)
        self.assertFalse(ledger['spend_needs_review'])
        self.assertEqual(Decimal(ledger['budget']['usd']), 0)

    def test_vercel_daily_cost_cap_uses_reservation_not_just_spent(self):
        ledger = {}
        c.daily_budget(ledger, NOW)['usd'] = '0.95'
        self.assertFalse(c.admission('vercel', self.payload('vercel'), KEY, ledger, NOW, HTTP())['allowed'])

    def test_gemini_blocks_without_key_specific_unexpired_billing_evidence(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(c.admission('gemini', {}, KEY, {}, NOW)['allowed'])
        with patch.dict(os.environ, {'GEMINI_FREE_TIER_KEY_SHA256': hashlib.sha256(KEY.encode()).hexdigest(),
                'GEMINI_FREE_TIER_VERIFIED_UNTIL': c.datetime.fromtimestamp(NOW + 3600, c.timezone.utc).isoformat()}):
            self.assertTrue(c.admission('gemini', {}, KEY, {}, NOW)['allowed'])
            self.assertFalse(c.admission('gemini', {}, 'OTHER_KEY', {}, NOW)['allowed'])
            self.assertFalse(c.admission('gemini', {}, KEY, {}, NOW + 7200)['allowed'])

    def test_each_new_openai_channel_runs_through_existing_persistent_queue(self):
        for provider in ('experiential', 'kilo', 'openrouter', 'vercel'):
            self.state = q.new_state()
            client = HTTP([Response(answer(provider, 0.001 if provider == 'vercel' else 0))])
            result = self.batch(provider, client, provider)
            self.assertEqual(result['completed'], 1, result)
            self.assertEqual(result['http_attempts'], 1)
            saved = q.read_state(self.state_path)['items']['example']
            self.assertEqual(saved['inferred_provider'], provider)
            self.assertEqual(saved['extracted'], EMPTY)
            self.assertFalse(saved['publication_allowed'])
            self.assertNotIn(KEY, self.state_path.read_text())

    def test_cross_provider_success_is_cached_without_even_account_reads(self):
        self.batch('kilo', HTTP([Response(answer('kilo'))]), 'first')
        client = HTTP()
        result = self.batch('vercel', client, 'second')
        self.assertEqual(result['cached'], 1)
        self.assertEqual(client.calls, [])
        self.assertEqual(client.gets, [])

    def test_gemini_gate_leaves_work_pending_without_generation(self):
        client = HTTP()
        with patch.dict(os.environ, {}, clear=True):
            result = self.batch('gemini', client)
        self.assertEqual(result['stop_reason'], 'billing_status_unverified')
        self.assertEqual(result['not_attempted'], ['example'])
        self.assertEqual(client.calls, [])

    def test_new_provider_does_not_retry_explicit_503_inside_one_slot(self):
        client = HTTP([Response({'error': {}}, 503), Response(answer('kilo'))])
        result = self.batch('kilo', client)
        self.assertEqual(result['http_attempts'], 1)
        self.assertEqual(len(client.calls), 1)

    def test_pool_quota_failure_falls_through_to_next_confirmed_channel(self):
        clients = {'experiential': HTTP([Response({'error': {}}, 429)]),
                   'kilo': HTTP([Response(answer('kilo'))])}
        result = q.process_pool([self.document], self.state, self.state_path, self.root / 'pool',
            {p: KEY for p in clients}, SCHEMA, 'source-only JSON', sessions=clients,
            providers=tuple(clients), now=lambda: NOW, sleep=lambda _: None, max_requests=2)
        self.assertEqual(result['completed'], 1, result)
        self.assertEqual(result['pending'], [])
        self.assertEqual(self.state['items']['example']['inferred_provider'], 'kilo')

    def test_invalid_answer_is_not_repaired_through_another_account(self):
        bad = answer('kilo')
        bad['choices'][0]['message']['content'] = '{'
        clients = {'kilo': HTTP([Response(bad)]), 'openrouter': HTTP()}
        result = q.process_pool([self.document], self.state, self.state_path, self.root / 'pool',
            {p: KEY for p in clients}, SCHEMA, 'source-only JSON', sessions=clients,
            providers=tuple(clients), now=lambda: NOW, sleep=lambda _: None, max_requests=2)
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(clients['openrouter'].calls, [])
        self.assertEqual(clients['openrouter'].gets, [])

if __name__ == '__main__':
    unittest.main()
