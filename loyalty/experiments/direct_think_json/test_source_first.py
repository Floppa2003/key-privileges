import copy
import json
import unittest

from source_first import check_blocks, source_request, source_schema, to_legacy


class SourceFirstTests(unittest.TestCase):
    def setUp(self):
        self.schema = {
            'type': 'object', 'additionalProperties': False,
            'properties': {'has_offer': {'type': 'boolean'}, 'offers': {'type': 'array'}, 'unknowns': {'type': 'array'}},
            'required': ['has_offer', 'offers', 'unknowns'],
        }
        self.request = {
            'model': 'unchanged', 'think': True, 'stream': False, 'format': copy.deepcopy(self.schema),
            'options': {'seed': 1, 'temperature': 1.0, 'num_predict': 8192, 'num_gpu': 0},
            'messages': [{'role': 'system', 'content': 'baseline'}, {'role': 'user', 'content': 'old', 'images': ['exact_bytes_1', 'exact_bytes_2']}],
        }

    def test_schema_is_added_first_without_mutating_input(self):
        before = copy.deepcopy(self.schema)
        schema = source_schema(self.schema)
        self.assertEqual(self.schema, before)
        self.assertEqual(next(iter(schema['properties'])), 'target_blocks')
        self.assertEqual(schema['required'][0], 'target_blocks')
        self.assertEqual({k:v for k,v in schema['properties'].items() if k != 'target_blocks'}, before['properties'])

    def test_double_extension_fails(self):
        with self.assertRaises(ValueError): source_schema(source_schema(self.schema))

    def test_request_preserves_model_options_images_and_complete_text(self):
        before = copy.deepcopy(self.request)
        text = 'Program A\nall text\nProgram B\nforeign text is still present'
        out = source_request(self.request, {'program': 'A'}, text)
        self.assertEqual(self.request, before)
        for key in ('model', 'options', 'think', 'stream'): self.assertEqual(out[key], before[key])
        self.assertEqual(out['messages'][-1]['images'], before['messages'][-1]['images'])
        self.assertTrue(out['messages'][-1]['content'].endswith(text))
        self.assertTrue(out['messages'][0]['content'].startswith('baseline'))
        content = out['messages'][-1]['content']
        shown = content.split('\nSCHEMA: ', 1)[1].split('\nВсе изображения', 1)[0]
        self.assertEqual(json.loads(shown), out['format'])

    def test_whitespace_only_matching_and_non_mutation(self):
        raw = {'target_blocks': ['Heading\n10%'], 'has_offer': True, 'offers': [1]}
        before = copy.deepcopy(raw)
        review = check_blocks(raw, 'intro Heading   10% end')
        self.assertTrue(review['text_span_valid'])
        self.assertEqual(review['semantic_review'], 'pending')
        self.assertFalse(review['publication_allowed'])
        self.assertEqual(raw, before)

    def test_changed_quote_is_rejected(self):
        with self.assertRaises(ValueError): check_blocks({'target_blocks':['11%'], 'has_offer':True,'offers':[1]},'10%')

    def test_missing_blocks_with_offer_rejected(self):
        with self.assertRaises(ValueError): check_blocks({'target_blocks':[], 'has_offer':True,'offers':[1]},'10%')

    def test_inconsistent_offer_state_rejected(self):
        with self.assertRaises(ValueError): check_blocks({'target_blocks':[], 'has_offer':False,'offers':[1]},'text')

    def test_multiple_separate_blocks_allowed(self):
        result = check_blocks({'target_blocks':['A first','A last'], 'has_offer':True,'offers':[1]},'A first\nB other\nA last')
        self.assertEqual(len(result['normalized_spans']), 2)

    def test_reversed_or_duplicated_blocks_rejected(self):
        for blocks in (['A last', 'A first'], ['A first', 'A first']):
            with self.assertRaises(ValueError): check_blocks({'target_blocks':blocks,'has_offer':True,'offers':[1]},'A first B A last')

    def test_empty_unknown_target_allowed(self):
        self.assertTrue(check_blocks({'target_blocks':[], 'has_offer':False,'offers':[]},'text')['text_span_valid'])

    def test_span_match_is_not_semantic_approval(self):
        result = check_blocks({'target_blocks':['WRONG PROGRAM 90%'], 'has_offer':True,'offers':[1]},'TARGET 10% WRONG PROGRAM 90%')
        self.assertTrue(result['text_span_valid'])
        self.assertEqual(result['semantic_review'], 'pending')
        self.assertFalse(result['publication_allowed'])

    def test_legacy_mapping_is_exact_and_pure(self):
        raw = {'target_blocks':['text'], 'has_offer':True,'offers':[{'how_to_get':['book', 'enter number'], 'value':500}], 'unknowns':[]}
        before = copy.deepcopy(raw)
        result = to_legacy(raw, self.schema)
        self.assertEqual(raw, before)
        self.assertEqual(result, {'has_offer':True,'offers':[{'redemption':['book','enter number'],'value':500}], 'unknowns':[]})

    def test_ambiguous_legacy_fields_rejected(self):
        with self.assertRaises(ValueError):
            to_legacy({'target_blocks':[], 'has_offer':True,'offers':[{'how_to_get':[], 'redemption':[]}], 'unknowns':[]}, self.schema)


if __name__ == '__main__': unittest.main()
