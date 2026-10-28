import base64
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import deepseek_capacity_probe as p


class CapacityProbeTests(unittest.TestCase):
    def response(self, content='{"code":"5837"}', finish='stop'):
        return {'model': 'deepseek-v4.1-flash', 'choices': [
            {'finish_reason': finish, 'message': {'content': content}}]}

    def test_plain_and_one_fence(self):
        for content in ('{"code":"5837"}', '```json\n{"code":"5837"}\n```'):
            self.assertEqual(p.validate_response(self.response(content), p.SMOKE_SCHEMA), {'code': '5837'})

    def test_incomplete_never_counts_as_ready(self):
        for finish in ('length', None, 'content_filter'):
            with self.assertRaises(ValueError):
                p.validate_response(self.response(finish=finish), p.SMOKE_SCHEMA)

    def test_tool_call_rejected(self):
        data = self.response()
        data['choices'][0]['message']['tool_calls'] = [{'name': 'websearch'}]
        with self.assertRaises(ValueError):
            p.validate_response(data, p.SMOKE_SCHEMA)

    def test_duplicate_json_is_not_repaired(self):
        with self.assertRaises(ValueError):
            p.validate_response(self.response('{"code":"5837","code":"0000"}'), p.SMOKE_SCHEMA)

    def test_full_input_and_images_are_preserved(self):
        doc = {'system': 'fixed', 'text': 'complete text\nwith last line',
               'images': [base64.b64encode(b'one').decode(), base64.b64encode(b'two').decode()]}
        before = copy.deepcopy(doc)
        payload = p.build_payload(doc, 'deepseek-v4.1-flash-free')
        self.assertEqual(doc, before)
        self.assertEqual(set(payload), {'model', 'stream', 'temperature', 'max_tokens', 'messages'})
        content = payload['messages'][1]['content']
        self.assertEqual(content[0]['text'], doc['text'])
        self.assertEqual([part['image_url']['url'].split(',', 1)[1] for part in content[1:]], doc['images'])

    def test_credit_provenance_does_not_accept_malformed_values(self):
        self.assertEqual(p.credit_numbers({'balance': '0', 'total_used': '0'}), (0, 0))
        for data in ({}, {'balance': '-1', 'total_used': '0'},
                     {'balance': 'NaN', 'total_used': '0'}, {'balance': 'Infinity', 'total_used': '0'}):
            self.assertIsNone(p.credit_numbers(data))

    def test_free_route_ids(self):
        for provider in ('openrouter', 'opencode'):
            self.assertTrue(all(model.endswith((':free', '-free')) for model in p.ROUTES[provider][2]))
        self.assertEqual(len(p.ROUTES['openrouter'][2]), 1)

    def test_cli_is_one_step_without_tools_or_paid_small_model(self):
        config = p.cli_config('unaltered prompt')
        self.assertEqual(config['permission'], {'*': 'deny'})
        self.assertEqual(config['agent']['extract']['steps'], 1)
        self.assertEqual(config['small_model'], config['model'])
        self.assertTrue(config['model'].endswith('-free'))
        self.assertEqual(config['agent']['extract']['prompt'], 'unaltered prompt')

    def test_redact_literal_and_encoded_key(self):
        key = 'TEST_SECRET_KEY_123'
        encoded = base64.b64encode(key.encode()).decode()
        text = p.scrub(key + ':' + encoded, key)
        self.assertNotIn(key, text)
        self.assertNotIn(encoded, text)


if __name__ == '__main__':
    unittest.main()
