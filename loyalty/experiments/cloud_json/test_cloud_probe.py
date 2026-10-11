"""Contracts: unmodified evidence, strict final output, free route and safe logs."""
import base64
import copy
import json
import unittest

from cloud_probe import build_payload, parse_final, request_log, scrub_bytes, select_model

SCHEMA = {'type': 'object', 'additionalProperties': False,
          'properties': {'has_offer': {'type': 'boolean'}, 'offers': {'type': 'array'},
                         'unknowns': {'type': 'array'}},
          'required': ['has_offer', 'offers', 'unknowns']}
EMPTY = {'has_offer': False, 'offers': [], 'unknowns': []}


class CloudContracts(unittest.TestCase):
    def setUp(self):
        self.baseline = {'format': copy.deepcopy(SCHEMA), 'options': {'temperature': 1.0},
                         'messages': [{'role': 'system', 'content': 'Exact system'},
                                      {'role': 'user', 'content': 'TARGET A\nSCHEMA\nA first\nB foreign\nA last',
                                       'images': ['Zmlyc3Q=', 'c2Vjb25k']}]}

    def test_gemini_payload_preserves_both_images_text_and_schema(self):
        self.assertEqual(build_payload('gemini', self.baseline), {
            'systemInstruction': {'parts': [{'text': 'Exact system'}]},
            'contents': [{'role': 'user', 'parts': [
                {'text': 'TARGET A\nSCHEMA\nA first\nB foreign\nA last'},
                {'inlineData': {'mimeType': 'image/png', 'data': 'Zmlyc3Q='}},
                {'inlineData': {'mimeType': 'image/png', 'data': 'c2Vjb25k'}}]}],
            'generationConfig': {'temperature': 1.0, 'maxOutputTokens': 8192,
                                 'thinkingConfig': {'thinkingLevel': 'HIGH', 'includeThoughts': False},
                                 'responseMimeType': 'application/json', 'responseJsonSchema': SCHEMA}})

    def test_kilo_payload_preserves_both_images_text_and_schema(self):
        self.assertEqual(build_payload('kilo', self.baseline), {
            'model': 'minimax/minimax-m3:free', 'stream': False, 'temperature': 1.0, 'max_tokens': 8192,
            'reasoning': {'enabled': True, 'effort': 'high'},
            'messages': [{'role': 'system', 'content': 'Exact system'},
                         {'role': 'user', 'content': [
                             {'type': 'text', 'text': 'TARGET A\nSCHEMA\nA first\nB foreign\nA last'},
                             {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,Zmlyc3Q='}},
                             {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,c2Vjb25k'}}]}],
            'response_format': {'type': 'json_schema', 'json_schema': {
                'name': 'loyalty_offer', 'strict': True, 'schema': SCHEMA}}})

    def test_input_is_not_mutated(self):
        before = copy.deepcopy(self.baseline)
        build_payload('gemini', self.baseline)
        build_payload('kilo', self.baseline)
        self.assertEqual(before, self.baseline)

    def test_unknown_provider_rejected(self):
        with self.assertRaises(ValueError): build_payload('auto', self.baseline)

    def response(self, provider, content=None, finish=None):
        text = json.dumps(EMPTY) if content is None else content
        if provider == 'gemini':
            return {'modelVersion': 'gemini-3.8-flash', 'candidates': [{
                'finishReason': finish or 'STOP', 'content': {'parts': [{'text': text}]}}]}
        return {'model': 'minimax/minimax-m3', 'choices': [{
            'finish_reason': finish or 'stop', 'message': {'content': text}}]}

    def test_both_providers_parse_only_final_json(self):
        for p in ('gemini', 'kilo'):
            self.assertEqual(parse_final(p, self.response(p), SCHEMA), EMPTY)

    def test_length_refusal_empty_and_markdown_are_not_repaired(self):
        for p in ('gemini', 'kilo'):
            for text, finish in (('', None), ('```json\n{}\n```', None),
                                 (json.dumps(EMPTY), 'length'), ('{}', None)):
                with self.subTest(provider=p, text=text, finish=finish):
                    with self.assertRaises(ValueError): parse_final(p, self.response(p, text, finish), SCHEMA)

    def test_foreign_model_is_rejected(self):
        for p in ('gemini', 'kilo'):
            data = self.response(p)
            data['modelVersion' if p == 'gemini' else 'model'] = 'different-model'
            with self.assertRaises(ValueError): parse_final(p, data, SCHEMA)

    def test_thoughts_do_not_substitute_for_final_answer(self):
        data = self.response('gemini')
        data['candidates'][0]['content']['parts'][0]['thought'] = True
        with self.assertRaises(ValueError): parse_final('gemini', data, SCHEMA)

    def test_multiple_candidates_and_inconsistent_state_rejected(self):
        for p in ('gemini', 'kilo'):
            data = self.response(p)
            key = 'candidates' if p == 'gemini' else 'choices'
            data[key] *= 2
            with self.assertRaises(ValueError): parse_final(p, data, SCHEMA)
            data = self.response(p, '{"has_offer":false,"offers":[1],"unknowns":[]}')
            with self.assertRaises(ValueError): parse_final(p, data, SCHEMA)

    def model(self):
        return {'id': 'minimax/minimax-m3:free', 'isFree': True,
                'pricing': {'prompt': '0', 'completion': '0'},
                'architecture': {'input_modalities': ['text', 'image']},
                'supported_parameters': ['response_format', 'reasoning']}

    def test_kilo_requires_exact_free_multimodal_route(self):
        m = self.model()
        self.assertEqual(select_model('kilo', {'data': [m]}), m)
        for changed in ({'id': 'minimax/minimax-m3'}, {'isFree': False},
                        {'pricing': {'prompt': '0.001', 'completion': '0'}},
                        {'architecture': {'input_modalities': ['text']}},
                        {'supported_parameters': ['reasoning']}):
            bad = {**m, **changed}
            with self.assertRaises(ValueError): select_model('kilo', {'data': [bad]})

    def test_gemini_requires_requested_model_and_generation_method(self):
        m = {'name': 'models/gemini-3.8-flash', 'supportedGenerationMethods': ['generateContent']}
        self.assertEqual(select_model('gemini', m), m)
        with self.assertRaises(ValueError): select_model('gemini', {**m, 'name': 'models/other'})

    def test_secret_echo_is_removed_before_any_artifact_write(self):
        self.assertEqual(scrub_bytes(b'{"error":"token=SECRET_A"}', ['SECRET_A', '']),
                         b'{"error":"token=[REDACTED]"}')

    def test_image_log_is_reconstructible_without_changing_payload(self):
        for p in ('gemini', 'kilo'):
            payload = build_payload(p, self.baseline)
            before = copy.deepcopy(payload)
            log = request_log(p, payload)
            self.assertIsInstance(log, dict)
            if log is None: continue
            self.assertNotIn('Zmlyc3Q=', json.dumps(log))
            self.assertEqual(log['images'][0]['sha256'],
                             'a7937b64b8caa58f03721bb6bacf5c78cb235febe0e70b1b84cd99541461a08e')
            self.assertEqual(payload, before)



    def test_explicit_qwen_keeps_payload_except_model_identity(self):
        expected = build_payload('kilo', self.baseline)
        expected['model'] = 'qwen/qwen3.8-27b:free'
        self.assertEqual(build_payload('kilo', self.baseline, model='qwen/qwen3.8-27b:free'), expected)

    def test_paid_auto_and_cross_provider_models_are_rejected(self):
        for provider, model in (('kilo', 'minimax/minimax-m3'), ('kilo', 'openrouter/free'),
                                ('gemini', 'qwen/qwen3.8-27b:free')):
            with self.subTest(provider=provider, model=model):
                with self.assertRaises(ValueError): build_payload(provider, self.baseline, model=model)

    def test_structured_outputs_metadata_accepts_exact_free_qwen(self):
        m = {**self.model(), 'id': 'qwen/qwen3.8-27b:free',
             'supported_parameters': ['structured_outputs', 'reasoning']}
        try:
            actual = select_model('kilo', {'data': [m]}, model=m['id'])
        except ValueError:
            actual = None
        self.assertEqual(actual, m)
        for change in ({'isFree': False}, {'pricing': {'prompt': '0', 'completion': '1'}},
                       {'supported_parameters': ['reasoning']},
                       {'architecture': {'input_modalities': ['text']}}):
            with self.assertRaises(ValueError):
                select_model('kilo', {'data': [{**m, **change}]}, model=m['id'])

    def test_qwen_response_cannot_be_substituted_with_minimax(self):
        with self.assertRaises(ValueError):
            parse_final('kilo', self.response('kilo'), SCHEMA, model='qwen/qwen3.8-27b:free')
        data = self.response('kilo')
        data['model'] = 'qwen/qwen3.8-27b'
        self.assertEqual(parse_final('kilo', data, SCHEMA, model='qwen/qwen3.8-27b:free'), EMPTY)


if __name__ == '__main__': unittest.main()
