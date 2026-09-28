"""Contract regressions: advice must be labelled, source bytes must stay frozen."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest

import prompt_ab as runner

old = runner.old


def advice_schema():
    schema = copy.deepcopy(old.SCHEMA)
    offer = schema['properties']['offers']['items']
    offer['properties']['practical_advice'] = {
        'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False,
            'properties': {'text': {'type': 'string', 'minLength': 1},
                           'basis': {'type': 'string', 'enum': ['inference']}},
            'required': ['text', 'basis']}}
    offer['required'].append('practical_advice')
    return schema


def example_output():
    return {'has_offer': True, 'offers': [{
        'benefit_kind': 'discount', 'value': 8, 'unit': '%',
        'basis': 'входной билет', 'audience': 'держатели карты Клуб Кедр',
        'restrictions': ['покупка в кассе'], 'redemption': [],
        'promo_code': None, 'valid_until': None, 'accrual_timing': None,
        'evidence': ['Держателям карты Клуб Кедр скидка 8% в кассе.'],
        'practical_advice': [{'text': 'Возьмите карту с собой.', 'basis': 'inference'}]
    }], 'unknowns': []}


def response(value):
    return {'model': old.MODEL, 'done': True, 'done_reason': 'stop',
            'message': {'role': 'assistant', 'content': json.dumps(value)}}


class PracticalContractTests(unittest.TestCase):
    def candidate(self, request, schema):
        with tempfile.TemporaryDirectory() as tmp:
            prompt = Path(tmp) / 'prompt.txt'
            prompt.write_text('Use conditions and labelled advice separately.')
            try:
                return runner.with_prompt(request, 'defined', prompt, schema)
            except TypeError as exc:
                self.fail('Candidate schema is not yet supported: ' + str(exc))

    def parse(self, value, schema):
        try:
            return old.parse_response(response(value), schema=schema)
        except TypeError as exc:
            self.fail('Response parser does not use requested schema: ' + str(exc))

    def test_advice_is_accepted_only_with_explicit_candidate_schema(self):
        value = example_output()
        self.assertEqual(self.parse(value, advice_schema()), value)
        with self.assertRaisesRegex(ValueError, 'invalid_model_json'):
            old.parse_response(response(value))

    def test_missing_or_source_label_is_not_inference(self):
        for label in (None, 'source'):
            with self.subTest(label=label):
                value = example_output()
                advice = value['offers'][0]['practical_advice'][0]
                if label is None:
                    del advice['basis']
                else:
                    advice['basis'] = label
                with self.assertRaisesRegex(ValueError, 'invalid_model_json'):
                    self.parse(value, advice_schema())

    def test_schema_switch_preserves_target_text_images_and_options(self):
        text = 'Держателям карты Клуб Кедр скидка 8% в кассе.'
        req = old.payload({'partner': 'Example', 'program': 'Клуб Кедр'}, text, [b'PNG fixture'])
        before = copy.deepcopy(req)
        updated = self.candidate(req, advice_schema())
        self.assertEqual(req, before)
        self.assertEqual(updated['format'], advice_schema())
        self.assertEqual(updated['options'], before['options'])
        self.assertEqual(updated['messages'][-1]['images'], before['messages'][-1]['images'])
        prefix, rest = updated['messages'][-1]['content'].split('\nСхема:\n', 1)
        schema_text, actual = rest.split('\nВсе изображения', 1)
        self.assertEqual(json.loads(schema_text), advice_schema())
        self.assertEqual(prefix, before['messages'][-1]['content'].split('\nСхема:\n', 1)[0])
        self.assertTrue(actual.endswith(text))
        self.assertEqual(updated['model'], before['model'])

    def test_baseline_ignores_candidate_schema(self):
        req = old.payload({'partner': 'Example'}, 'source', [b'png'])
        try:
            updated = runner.with_prompt(req, 'old', None, advice_schema())
        except TypeError as exc:
            self.fail('Candidate schema option missing: ' + str(exc))
        self.assertEqual(updated, req)

    def test_schema_switch_refuses_missing_embedded_schema(self):
        req = old.payload({'partner': 'Example'}, 'source', [b'png'])
        req['messages'][-1]['content'] = 'No schema envelope'
        with self.assertRaisesRegex(ValueError, 'embedded_schema_mismatch'):
            self.candidate(req, advice_schema())

    def test_infer_saves_advice_without_repair(self):
        # Only the external HTTP boundary is simulated; infer/parsing/disk writes are real.
        value = example_output()
        wire = response(value)
        class Reply:
            status_code = 200
            def __init__(self, data):
                self.data = data
                self.content = json.dumps(data).encode()
            def json(self): return self.data
            def raise_for_status(self): return None
        class Client:
            def post(self, url, *, json, timeout):
                if url != old.BASE + '/api/chat' or json['format'] != advice_schema():
                    raise AssertionError('Wrong inference request')
                return Reply(wire)
            def get(self, url, *, timeout):
                if url != old.BASE + '/api/ps': raise AssertionError('Unexpected endpoint')
                return Reply({'models': [{'name': old.MODEL, 'size_vram': 0}]})
        req = old.payload({'partner': 'Example'}, 'source', [b'png'])
        req['format'] = advice_schema()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            result = old.infer(Client(), req, out, os.getpid())
            self.assertTrue(result['schema_valid'], result)
            self.assertEqual(json.loads((out / 'extracted.json').read_text()), value)
            self.assertEqual(json.loads((out / 'response.json').read_text()), wire)

if __name__ == '__main__': unittest.main()
