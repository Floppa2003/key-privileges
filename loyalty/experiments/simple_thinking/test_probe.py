"""Contract tests: manipulate only declared variables and never accept partial output."""
import copy
import json
import unittest
import probe


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.target = {'partner': 'Test partner', 'program': 'Test club', 'as_of': '2026-09-27'}
        self.frozen = {'model': 'qwen3.5:4b', 'stream': False, 'think': False, 'keep_alive': '5m',
                       'format': {'old': True}, 'options': {'temperature': 0, 'seed': 1, 'num_predict': 1600},
                       'messages': [{'role': 'system', 'content': 'old'},
                                    {'role': 'user', 'content': 'old-schema-and-text', 'images': ['YWJj', 'ZGVm']}]}
        self.text = 'Target offer.\nComplete source ending.\n'

    def test_description_preserves_all_images_and_full_text_without_any_schema(self):
        before = copy.deepcopy(self.frozen)
        request = probe.description_request(self.frozen, self.target, self.text, False)
        self.assertEqual(request['messages'][1]['images'], ['YWJj', 'ZGVm'])
        self.assertTrue(request['messages'][1]['content'].endswith(self.text))
        self.assertNotIn('format', request)
        self.assertNotIn('old-schema-and-text', request['messages'][1]['content'])
        self.assertEqual(request['options']['temperature'], 0)
        self.assertEqual(request['options']['num_predict'], 4096)
        self.assertEqual(self.frozen, before)

    def test_reasoning_pair_changes_only_think(self):
        a = probe.description_request(self.frozen, self.target, self.text, False)
        b = probe.description_request(self.frozen, self.target, self.text, True)
        self.assertIs(a.pop('think'), False)
        self.assertIs(b.pop('think'), True)
        self.assertEqual(a, b)

    def test_structurer_sees_only_exact_final_description_and_target_not_thinking_or_images(self):
        request = probe.description_request(self.frozen, self.target, self.text, True)
        result = probe.structure_request(request, self.target, '  Неправленное описание.\n', {'type': 'object'})
        self.assertEqual(json.loads(result['messages'][1]['content']),
                         {'target': self.target, 'description': '  Неправленное описание.\n'})
        self.assertIs(result['think'], False)
        self.assertNotIn('images', result['messages'][1])
        self.assertEqual(result['format'], {'type': 'object'})
        self.assertNotIn(self.text, result['messages'][1]['content'])

    def test_empty_description_is_not_converted(self):
        with self.assertRaises(ValueError):
            probe.structure_request(self.frozen, self.target, ' \n', {})

    def test_incomplete_or_empty_answer_is_not_success(self):
        for response in [{'done': True, 'done_reason': 'length', 'message': {'content': 'partial'}},
                         {'done': True, 'done_reason': 'stop', 'message': {'content': '', 'thinking': 'reasoning only'}}]:
            with self.subTest(response=response), self.assertRaises(ValueError):
                probe.parse_answer(response, None)

    def test_raw_final_text_is_not_repaired_or_stripped(self):
        content = '  Ответ с пробелами.\n'
        response = {'done': True, 'done_reason': 'stop', 'message': {'content': content, 'thinking': 'not an answer'}}
        self.assertEqual(probe.parse_answer(response, None), content)

    def test_actual_schema_is_enforced(self):
        response = {'done': True, 'done_reason': 'stop', 'message': {'content': '{"has_offer": false, "offers": [], "unknowns": []}'}}
        with self.assertRaises(ValueError):
            probe.parse_answer(response, {'type': 'object', 'required': ['missing']})

    def test_mismatched_offer_state_is_not_success(self):
        response = {'done': True, 'done_reason': 'stop', 'message': {'content': '{"has_offer": true, "offers": [], "unknowns": []}'}}
        with self.assertRaises(ValueError):
            probe.parse_answer(response, {'type': 'object'})


if __name__ == '__main__':
    unittest.main()
