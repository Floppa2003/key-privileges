"""The converter must see the same schema that constrains its decoder."""
import copy
import json
import unittest
import probe


class VisibleSchemaTests(unittest.TestCase):
    def test_converter_receives_literal_schema_and_unchanged_description(self):
        schema = {'type': 'object', 'properties': {'amount': {'type': 'number'}},
                  'required': ['amount'], 'additionalProperties': False}
        target = {'partner': 'Example', 'program': 'Club', 'as_of': '2026-01-01'}
        original = {'think': True, 'options': {'num_predict': 4096},
                    'messages': [{'role': 'user', 'content': 'raw page', 'images': ['png']}]}
        request = probe.structure_request(original, target, '12 points per visit.', schema)
        content = json.loads(request['messages'][-1]['content'])
        self.assertEqual(content['schema'], schema)
        self.assertEqual(request['format'], schema)
        self.assertEqual(content['description'], '12 points per visit.')
        self.assertEqual(content['target'], target)
        self.assertNotIn('images', request['messages'][-1])
        self.assertEqual(original['messages'][-1]['images'], ['png'])

    def test_exposing_schema_does_not_mutate_source_or_other_request_fields(self):
        original = {'model': 'qwen3.5:4b', 'think': True, 'format': {'type': 'object'},
                    'options': {'seed': 1}, 'messages': [
                        {'role': 'system', 'content': 'Convert.'},
                        {'role': 'user', 'content': json.dumps({'description': 'unchanged'})}]}
        before = copy.deepcopy(original)
        result = probe.with_visible_schema(original)
        self.assertEqual(original, before)
        self.assertEqual(json.loads(result['messages'][-1]['content']),
                         {'description': 'unchanged', 'schema': {'type': 'object'}})
        result['messages'][-1]['content'] = before['messages'][-1]['content']
        self.assertEqual(result, before)

    def test_contradictory_prompt_schema_is_rejected_not_silently_overwritten(self):
        request = {'format': {'type': 'object'}, 'messages': [
            {'role': 'user', 'content': json.dumps({'schema': {'type': 'array'}})}]}
        with self.assertRaises(ValueError):
            probe.with_visible_schema(request)


if __name__ == '__main__':
    unittest.main()
