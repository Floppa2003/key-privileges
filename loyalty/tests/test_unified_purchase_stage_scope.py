"""Explicit first/repeat purchase stages belong to their literal rate occurrence."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from unified_normalization import normalize_record, validate_normalized
from test_unified_normalization import record


class PurchaseStageScopes(unittest.TestCase):
    def project(self, literal):
        raw = record(benefit=literal, conditions='', activation='')
        before = copy.deepcopy(raw)
        normalized = normalize_record(raw, as_of='2026-11-06')
        self.assertEqual(raw, before)
        self.assertEqual(normalized['raw'], before)
        validate_normalized(json.loads(json.dumps(normalized)))
        return normalized

    def assert_stages(self, literal, expected):
        result = self.project(literal)
        self.assertCountEqual(
            [(b['value'], b['scope'].get('purchase_stage'))
             for b in result['benefits']], expected)
        for benefit in result['benefits']:
            self.assertEqual(benefit['evidence']['path'], '/benefit')
            self.assertIn(benefit['evidence']['text'], literal)
        return result

    def test_postfix_stages_bind_in_both_orders(self):
        for literal in (
                'Скидка 15% на первый заказ и 10% на повторный заказ.',
                'Скидка 10% на повторный заказ и 15% на первый заказ.',
                'Скидка 15% на первый заказ. Скидка 10% на повторный заказ.'):
            with self.subTest(literal=literal):
                self.assert_stages(literal, [('15', 'first'), ('10', 'repeat')])

    def test_prefix_stages_bind_in_both_orders(self):
        for literal in (
                'На первый заказ скидка 15%, на повторный заказ 10%.',
                'На повторный заказ скидка 10%, на первый заказ 15%.'):
            with self.subTest(literal=literal):
                self.assert_stages(literal, [('15', 'first'), ('10', 'repeat')])

    def test_shared_noun_keeps_the_elliptical_stage(self):
        for literal in (
                'Скидка 15% на первый и 10% на повторный заказ.',
                'Скидка 10% на повторный и 15% на первый заказ.'):
            with self.subTest(literal=literal):
                self.assert_stages(literal, [('15', 'first'), ('10', 'repeat')])
        self.assert_stages('Скидка 15% на первый и повторный заказ.',
                           [('15', 'multiple_stages')])

    def test_english_explicit_and_elliptical_stages(self):
        for literal in (
                'Discount 15% on your first order and 10% on repeat orders.',
                'Discount 10% on repeat orders and 15% on your first order.',
                'Discount 15% on first and 10% on repeat orders.',
                'For the first order discount 15%, for subsequent orders 10%.'):
            with self.subTest(literal=literal):
                self.assert_stages(literal, [('15', 'first'), ('10', 'repeat')])

    def test_identical_percent_values_keep_distinct_stage_owners(self):
        result = self.assert_stages(
            'Скидка 15% на первый заказ и 15% на повторный заказ.',
            [('15', 'first'), ('15', 'repeat')])
        self.assertEqual(len({b['id'] for b in result['benefits']}), 2)

    def test_mileage_fallback_keeps_its_own_percent_occurrence(self):
        for wording, stage in (('первый', 'first'), ('повторный', 'repeat')):
            with self.subTest(stage=stage):
                result = self.assert_stages(
                    f'До 13% суммы бронирования милями на {wording} заказ.',
                    [('13', stage)])
                self.assertEqual(result['benefits'][0]['kind'], 'earn_miles')
        with self.subTest(case='mixed_fallback_and_direct_mileage'):
            result = self.assert_stages(
                'До 13% суммы бронирования милями на первый заказ '
                'и 13% милями на повторный заказ.',
                [('13', 'first'), ('13', 'repeat')])
            self.assertTrue(all(b['kind'] == 'earn_miles' for b in result['benefits']))
        for literal in (
                'До 12% суммы бронирования милями + 25% кешбэка.',
                '50% предоплата, 12% суммы бронирования милями + 25% кешбэка.'):
            with self.subTest(literal=literal):
                result = self.project(literal)
                self.assertCountEqual(
                    [(b['kind'], b['value'], b['unit']) for b in result['benefits']],
                    [('earn_miles', '12', 'percent'), ('cashback', '25', 'percent')])
        for literal in (
                'Оплатите 50% суммы бронирования милями. Скидка 25%.',
                'Оплатите до 50% суммы бронирования милями. Скидка 25%.',
                'Скидка 25%. Оплатите 50% суммы бронирования милями.',
                'Не начисляется 12% суммы бронирования милями. Скидка 25%.',
                'Не будет начисляться 12% суммы бронирования милями. Скидка 25%.',
                '12% суммы бронирования милями не начисляются. Скидка 25%.'):
            with self.subTest(literal=literal):
                result = self.project(literal)
                self.assertEqual([(b['kind'], b['value']) for b in result['benefits']],
                                 [('discount', '25')])

    def test_shared_single_stage_stays_shared(self):
        for literal in (
                'На первый заказ скидка 15% на обувь и 10% на одежду.',
                'Скидка 15% и 10% на первый заказ.'):
            with self.subTest(literal=literal):
                self.assert_stages(literal, [('15', 'first'), ('10', 'first')])

    def test_ambiguous_shared_stages_remain_multiple(self):
        for literal in (
                'На первый и повторный заказ скидка 15% или 10%.',
                'Скидка 15% и 10% на первый и повторный заказ.',
                'Discount 15% and 10% for first and repeat orders.'):
            with self.subTest(literal=literal):
                self.assert_stages(literal,
                                   [('15', 'multiple_stages'), ('10', 'multiple_stages')])

    def test_stage_does_not_cross_a_sentence_or_field(self):
        self.assert_stages('Скидка 15% для всех. На повторный заказ скидка 10%.',
                           [('15', None), ('10', 'repeat')])
        raw = record(benefit='Скидка 15%.', conditions='Скидка 10% на повторный заказ.',
                     activation='')
        result = normalize_record(raw, as_of='2026-11-06')
        self.assertCountEqual([(b['value'], b['scope'].get('purchase_stage'))
                               for b in result['benefits']],
                              [('15', None), ('10', 'repeat')])

    def test_existing_newline_and_semicolon_scopes_stay_separate(self):
        for separator in ('\n', '; '):
            with self.subTest(separator=separator):
                self.assert_stages('Скидка 15% на первый заказ' + separator
                                   + 'Скидка 10% на повторный заказ.',
                                   [('15', 'first'), ('10', 'repeat')])

    def test_currency_abbreviation_keeps_its_owned_stage(self):
        self.assert_stages('Скидка 15% при покупке от 1000 руб. на первый заказ.',
                           [('15', 'first')])
        for continuation in ('только на', 'действует на', 'при оформлении заказа на'):
            for wording, stage in (('первый', 'first'), ('повторный', 'repeat')):
                with self.subTest(continuation=continuation, stage=stage):
                    self.assert_stages(
                        f'Скидка 15% при покупке от 1000 руб. {continuation} {wording} заказ.',
                        [('15', stage)])
        self.assert_stages('Скидка 15% при покупке от 1000 руб. на первый заказ. '
                           'Скидка 10% на повторный заказ.',
                           [('15', 'first'), ('10', 'repeat')])
        self.assert_stages('Скидка 15% при покупке от 1000 руб. '
                           'На повторный заказ скидка 10%.',
                           [('15', None), ('10', 'repeat')])

    def test_existing_repeat_prefix_without_purchase_noun_stays_shared(self):
        self.assert_stages('При повторном обращении предоставляется скидка 5% на услуги, '
                           'а на услуги на дому скидка 7%.',
                           [('5', 'repeat'), ('7', 'repeat')])

    def test_unknown_service_scope_is_not_borrowed_from_a_sibling(self):
        self.assert_stages('Скидка 80% на первичную консультацию и скидка 5% '
                           'на первичное посещение любой из процедур.',
                           [('80', None), ('5', 'first')])

    def test_observed_service_actions_keep_literal_first_and_repeat(self):
        cases = (
            ('Скидка 15% на первую чистку и 5% на последующие.',
             [('15', 'first'), ('5', 'repeat')]),
            ('Скидка 5% на первый прием и 3% на все последующие приемы.',
             [('5', 'first'), ('3', 'repeat')]),
            ('Скидка 5% на первый приём и 3% на все последующие приёмы.',
             [('5', 'first'), ('3', 'repeat')]),
            ('Скидка 10% на первое бронирование. На последующие визиты — чаепитие.',
             [('10', 'first')]),
            ('При первом подключении предоставляется скидка 100%. '
             'При повторном подключении плата спишется полностью.',
             [('100', 'first')]),
        )
        for literal, expected in cases:
            with self.subTest(literal=literal):
                self.assert_stages(literal, expected)

    def test_primary_medical_terms_do_not_create_first_purchase_scope(self):
        cases = (
            ('Скидка 10% на первичный прием врача.', [('10', None)]),
            ('Скидка 35% на все методы лечения, а также бесплатный первичный приём.',
             [('35', None)]),
            ('Скидка 25% на первичный прием врача и 15% при первичном обращении.',
             [('25', None), ('15', None)]),
            ('Скидка 5% на первичное посещение процедур.', [('5', 'first')]),
        )
        for literal, expected in cases:
            with self.subTest(literal=literal):
                self.assert_stages(literal, expected)

    def test_conditions_codes_raw_and_literal_evidence_are_preserved(self):
        literal = ('Скидка 15% на первый заказ и 10% на повторный заказ. '
                   'Введите промокод SCOPE15.')
        result = self.assert_stages(literal, [('15', 'first'), ('10', 'repeat')])
        self.assertEqual([b['evidence'] for b in result['benefits']],
                         [{'path': '/benefit', 'text': literal}] * 2)
        self.assertCountEqual([c['kind'] for c in result['conditions']],
                              ['audience_reference', 'activation_step'])
        for condition in result['conditions']:
            self.assertEqual(condition['scope'], {'purchase_stage': 'multiple_stages'})
            self.assertEqual(condition['evidence'], {'path': '/benefit', 'text': literal})
        self.assertEqual(len(result['codes']), 1)
        self.assertEqual(result['codes'][0]['value'], 'SCOPE15')
        self.assertEqual(result['codes'][0]['scope'], {'purchase_stage': 'multiple_stages'})
        self.assertEqual(result['codes'][0]['evidence'],
                         {'path': '/benefit', 'text': literal})


if __name__ == '__main__':
    unittest.main()
