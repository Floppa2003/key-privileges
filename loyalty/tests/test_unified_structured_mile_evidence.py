"""Structured mileage quotes own exact occurrences, not matching reward numbers."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from unified_normalization import make_input, normalize_record, validate_normalized

NOW = '2026-11-06T01:00:00+00:00'
EVIDENCE = 'За каждые 70 ₽\nполучите 4 мили'
SHA256 = 'a' * 64


class StructuredMileEvidenceTests(unittest.TestCase):
    def project(self, body, *, conditions=None, evidence=EVIDENCE,
                changes=None, structured=True):
        details = {'_source': {'source_id': 'af_vtb_rules'}}
        if structured:
            details['earning_rules'] = [{
                'value': '4', 'unit': 'miles', 'basis_amount': '70',
                'basis_unit': 'RUB', 'qualifier': 'exact', 'evidence': evidence,
                **(changes or {}),
            }]
        values = {
            'Программа': 'Аэрофлот Бонус', 'Партнёр': 'ВТБ',
            'Заголовок': 'Public mileage fixture', 'Тип записи': 'program_rules',
            'Выгода': body, 'Условия': body if conditions is None else conditions,
            'Источник': 'https://www.vtb.ru/privilegia/karty/debetovye/privilegiya-aeroflot/',
            'Получено UTC': NOW, 'Статус источника': 'public_rules_text',
            'Детали JSON': json.dumps(details, ensure_ascii=False), 'SHA256': SHA256,
        }
        source = {
            'id': 'fixture:structured-mile', 'origin': 'parser_offers', 'row': 2,
            'fields': {name: {'value': value} for name, value in values.items()},
        }
        raw = make_input(source)
        before = copy.deepcopy(raw)
        result = normalize_record(raw, as_of='2026-11-06')
        validate_normalized(result)
        self.assertEqual(raw, before)
        self.assertEqual(result['raw'], before)
        self.assertEqual(result['provenance']['source_id'], 'af_vtb_rules')
        self.assertEqual(result['provenance']['observed_at'], NOW)
        self.assertEqual(result['raw']['original']['fields']['SHA256']['value'], SHA256)
        return result

    def miles(self, result, *, method=None):
        return [item for item in result['benefits']
                if item['kind'] == 'earn_miles'
                and (method is None or item['method'] == method)]

    def assert_miles(self, result, expected):
        self.assertCountEqual(
            [(item['value'], item['unit'], item['basis_value'], item['basis_unit'])
             for item in self.miles(result)], expected,
        )

    def assert_discount(self, result):
        self.assertEqual(
            [(item['value'], item['unit']) for item in result['benefits']
             if item['kind'] == 'discount'], [('7', 'percent')],
        )

    def test_multiline_quote_keeps_one_full_rule_and_literal_evidence(self):
        result = self.project('Правила карты\n' + EVIDENCE + '.\nСкидка 7% на покупки.')
        self.assert_miles(result, [('4', 'miles', '70', 'RUB')])
        self.assert_discount(result)
        rule = self.miles(result)[0]
        self.assertEqual(rule['method'], 'structured_source')
        self.assertEqual(rule['evidence']['path'], '/details/earning_rules/0')
        self.assertEqual(json.loads(rule['evidence']['text'])['evidence'], EVIDENCE)
        self.assertEqual(result['raw']['details']['earning_rules'][0]['evidence'], EVIDENCE)

    def test_same_words_before_or_after_owned_occurrence_remain_independent(self):
        bodies = (
            EVIDENCE + '.\nДругой бонус:\nполучите 4 мили.\nСкидка 7%.',
            'получите 4 мили.\nУсловия карты:\n' + EVIDENCE + '.\nСкидка 7%.',
        )
        for body in bodies:
            with self.subTest(body=body):
                result = self.project(body)
                self.assert_miles(result, [
                    ('4', 'miles', '70', 'RUB'), ('4', 'miles', None, None),
                ])
                self.assert_discount(result)
                candidate = self.miles(result, method='clause_candidate')
                self.assertEqual(len(candidate), 1)
                self.assertEqual(candidate[0]['evidence']['text'], 'получите 4 мили.')

    def test_same_words_in_another_source_field_remain_independent(self):
        for body, conditions in (
            (EVIDENCE + '.', 'получите 4 мили.\nСкидка 7%.'),
            ('получите 4 мили.\nСкидка 7%.', EVIDENCE + '.'),
        ):
            with self.subTest(body=body):
                result = self.project(body, conditions=conditions)
                self.assert_miles(result, [
                    ('4', 'miles', '70', 'RUB'), ('4', 'miles', None, None),
                ])
                self.assert_discount(result)

    def test_separate_reward_with_same_value_keeps_its_scope(self):
        result = self.project(
            EVIDENCE + '.\nПолучите 4 мили за первый заказ.\nСкидка 7%.'
        )
        self.assert_miles(result, [
            ('4', 'miles', '70', 'RUB'), ('4', 'miles', None, None),
        ])
        candidate = self.miles(result, method='clause_candidate')
        self.assertEqual(len(candidate), 1)
        self.assertEqual(candidate[0]['scope'], {'purchase_stage': 'first'})
        self.assertEqual(candidate[0]['evidence']['text'], 'Получите 4 мили за первый заказ.')
        self.assert_discount(result)

    def test_unowned_tail_of_same_line_keeps_miles_and_discount(self):
        body = EVIDENCE + '. Получите 4 мили за регистрацию. Скидка 7%.'
        result = self.project(body)
        self.assert_miles(result, [
            ('4', 'miles', '70', 'RUB'), ('4', 'miles', None, None),
        ])
        self.assert_discount(result)
        for item in result['benefits']:
            if item['method'] == 'clause_candidate':
                self.assertEqual(item['evidence']['text'], body.split('\n')[1])

    def test_mismatched_structured_value_or_basis_does_not_hide_source_claim(self):
        for changes in (
            {'value': '5'}, {'basis_amount': '80'}, {'basis_unit': 'USD'},
            {'unit': 'points'}, {'qualifier': 'up_to'},
        ):
            with self.subTest(changes=changes):
                result = self.project(EVIDENCE + '.\nСкидка 7%.', changes=changes)
                candidates = self.miles(result, method='clause_candidate')
                self.assertEqual(len(candidates), 1)
                self.assertEqual(
                    (candidates[0]['value'], candidates[0]['basis_value']), ('4', None),
                )
                self.assert_discount(result)

    def test_repeated_full_quote_does_not_choose_an_arbitrary_owner(self):
        result = self.project(
            EVIDENCE + '.\nДругая карта:\n' + EVIDENCE + '.\nСкидка 7%.'
        )
        self.assert_miles(result, [
            ('4', 'miles', '70', 'RUB'), ('4', 'miles', None, None),
        ])
        self.assertEqual(len(self.miles(result, method='clause_candidate')), 1)
        self.assert_discount(result)

    def test_quote_with_another_rate_is_not_removed_as_one_formula(self):
        for label in ('Скидка 7%.', 'Discount 7%.'):
            with self.subTest(label=label):
                literal = 'За каждые 70 ₽\n' + label + '\nполучите 4 мили'
                result = self.project(literal + '.', evidence=literal)
                self.assert_miles(result, [
                    ('4', 'miles', '70', 'RUB'), ('4', 'miles', None, None),
                ])
                self.assert_discount(result)

    def test_quote_with_two_mileage_claims_keeps_both_literal_candidates(self):
        literal = EVIDENCE + '\nи получите 4 мили'
        result = self.project(literal + '.', evidence=literal)
        self.assert_miles(result, [
            ('4', 'miles', '70', 'RUB'),
            ('4', 'miles', None, None), ('4', 'miles', None, None),
        ])
        self.assertEqual(len(self.miles(result, method='clause_candidate')), 2)

    def test_nonmatching_literal_and_ordinary_single_line_keep_prior_behavior(self):
        flat = EVIDENCE.replace('\n', ' ')
        # Whitespace-equivalent display is not the same owned occurrence.
        result = self.project(flat + '.', evidence=EVIDENCE)
        self.assert_miles(result, [
            ('4', 'miles', '70', 'RUB'), ('4', 'miles', '70', 'RUB'),
        ])
        result = self.project(flat, evidence=flat)
        self.assert_miles(result, [('4', 'miles', '70', 'RUB')])
        result = self.project(flat + '.\nСкидка 7%.', structured=False)
        self.assert_miles(result, [('4', 'miles', '70', 'RUB')])
        self.assert_discount(result)


if __name__ == '__main__':
    unittest.main()
