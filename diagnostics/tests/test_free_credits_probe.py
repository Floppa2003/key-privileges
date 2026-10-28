import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import free_credits_probe as probe


class FreeCreditsTests(unittest.TestCase):
    def test_zero_account_can_activate(self):
        self.assertTrue(probe.free_credit_budget({'balance': '0', 'total_used': '0'}, initial=True))
        self.assertFalse(probe.free_credit_budget({'balance': '0', 'total_used': '0'}))

    def test_initialized_free_grant_is_accepted(self):
        self.assertTrue(probe.free_credit_budget({'balance': '5', 'total_used': '0'}, initial=True))
        self.assertTrue(probe.free_credit_budget({'balance': '4.99', 'total_used': '.01'}))

    def test_paid_unknown_or_exhausted_budget_is_not_used(self):
        for data in ({'balance': '10', 'total_used': '0'}, {'balance': '4', 'total_used': '1'},
                     {'balance': '5', 'total_used': '10'}, {'balance': 'NaN', 'total_used': '0'},
                     {'balance': '-1', 'total_used': '0'}, {}, {'balance': 'x', 'total_used': 0}):
            with self.subTest(data=data):
                self.assertFalse(probe.free_credit_budget(data, initial=True))

    def test_complete_input_no_search_no_server_schema(self):
        doc = {'id': 'document', 'system': 'source only', 'text': 'entire document',
               'images': ['eA==', 'eQ==']}
        old = copy.deepcopy(doc)
        for provider, (_, models) in probe.ROUTES.items():
            body = probe.payload(doc, provider, models[0])
            self.assertEqual(body['messages'][1]['content'][0]['text'], doc['text'])
            self.assertEqual([p['image_url']['url'] for p in body['messages'][1]['content'][1:]],
                             ['data:image/png;base64,eA==', 'data:image/png;base64,eQ=='])
            self.assertFalse(set(body) & {'tools', 'plugins', 'web_search_options', 'response_format'})
            self.assertEqual(body['max_tokens'], 16384)
        self.assertEqual(doc, old)

    def test_only_free_suffixes_on_permanent_free_routers(self):
        for provider in ('experiential', 'openrouter'):
            self.assertTrue(all(m.endswith(':free') for m in probe.ROUTES[provider][1]))

    def test_cost_nano_and_headers_are_checked(self):
        self.assertIsNone(probe.unexpected_cost({'usage': {'cost': 0}}, {}))
        self.assertIsNotNone(probe.unexpected_cost({'usage': {'cost': '.01'}}, {}))
        self.assertIsNotNone(probe.unexpected_cost({'cost_nano_usd': 10}, {}))
        self.assertIsNotNone(probe.unexpected_cost({'usage': {'billed_cost_nano_usd': 1}}, {}))
        self.assertIsNotNone(probe.unexpected_cost({}, {'X-Gateway-Cost-Nano-Usd': '1'}))
        self.assertIsNotNone(probe.unexpected_cost({}, {'X-Gateway-Cost-Usd': 'NaN'}))

    def test_incomplete_is_not_success(self):
        response = {'choices': [{'finish_reason': 'length', 'message': {'content': '{"code":"5837"}'}}]}
        with self.assertRaises(ValueError):
            probe.common.validate_response(response, probe.common.SMOKE_SCHEMA)

    def test_markdown_not_a_false_blocker(self):
        self.assertEqual(probe.common.validate_content('```json\n{"code":"5837"}\n```',
                         probe.common.SMOKE_SCHEMA), {'code': '5837'})


if __name__ == '__main__':
    unittest.main()
