"""Source-owned mileage polarity/bounds survive publication and retained rows."""
import copy
import unittest

from known_rules import earning_rules
from normalized import normalize_rates
from test_known_rules import parse, RETAIL
from test_source_numeric_invariance import GENERATIONS, IWAY
from test_dom_card_boundaries import project
from test_known_rule_value_changes import published_input
from unified_normalization import normalize_record

FORMULA = '1 миля начисляется за каждые потраченные 70 руб.'


def retail(literal):
    return parse('af_bootwood_rules', RETAIL.replace(FORMULA, literal))[0]


def miles(result):
    return {(b['value'], b['qualifier'], b['value_min'], b['basis_value'])
            for b in result['benefits'] if b['kind'] == 'earn_miles'}


class SourceMileageSemantics(unittest.TestCase):
    def retained(self, literal, *, field='earning_rules', value='2', basis='70',
                 evidence='2 мили за каждые потраченные 70 руб', **extras):
        raw = published_input(retail(FORMULA))
        raw['benefit'] = raw['conditions'] = literal
        raw['details'] = {field: [{'value': value, 'unit': 'miles',
                                  'basis_amount': basis, 'basis_unit': 'RUB',
                                  'evidence': evidence, **extras}]}
        before = copy.deepcopy(raw)
        result = normalize_record(raw, as_of='2026-11-13')
        self.assertEqual(raw, before)
        self.assertEqual(result['raw'], before)
        return result

    def test_source_denied_formula_is_evidence_without_positive_earning(self):
        for literal in ('Не начисляется 1 миля за каждые потраченные 70 руб.',
                        'Не начисляются 2,5 мили за каждые потраченные 85,50 руб.'):
            with self.subTest(literal=literal):
                row = retail(literal)
                self.assertEqual(row['details']['earning_rules'], [])
                self.assertIn(literal, row['benefit_text'])
                self.assertEqual(miles(project(row)), set())

    def test_source_bounds_retain_complete_expression_and_lower_endpoint(self):
        for literal, expected in (
            ('До 2 миль за каждые потраченные 70 руб.', ('2', 'up_to', None, '70')),
            ('От 1 до 2 миль за каждые потраченные 70 руб.', ('2', 'range', '1', '70')),
            ('От 1,5 до 3,5 мили за каждые потраченные 85,50 руб.', ('3.5', 'range', '1.5', '85.5')),
            ('Не менее 2,5 мили за каждые потраченные 1.500,50 руб.', ('2.5', 'at_least', None, '1500.5')),
        ):
            with self.subTest(literal=literal):
                row = retail(literal)
                self.assertEqual(miles(project(row)), {expected})
                rule, = row['details']['earning_rules']
                self.assertEqual(rule.get('qualifier'), expected[1])
                self.assertEqual(rule.get('min_value'), expected[2])
                self.assertEqual(rule['evidence'], literal)

    def test_source_mixed_occurrences_keep_only_live_formula(self):
        for denied in ('2', '3'):
            literal = (f'Не начисляются {denied} мили за каждые потраченные 70 руб.; '
                       'начисляются 2 мили за каждые потраченные 85 руб.')
            with self.subTest(denied=denied):
                row = retail(literal)
                self.assertEqual([(r['value'], r['basis_amount']) for r in row['details']['earning_rules']], [('2', '85')])
                self.assertEqual(miles(project(row)), {('2', 'exact', None, '85')})

    def test_source_full_evidence_does_not_hide_independent_discount(self):
        literal = 'До 2 мили за каждые потраченные 85 руб., скидка 7% на доставку.'
        result = project(retail(literal))
        self.assertEqual(miles(result), {('2', 'up_to', None, '85')})
        self.assertEqual({b['value'] for b in result['benefits'] if b['kind'] == 'discount'}, {'7'})

    def test_retained_range_with_adjacent_reward_preserves_both_occurrences(self):
        result = self.retained('От 1 до 2 мили за каждые потраченные 70 руб., скидка 7% на доставку.')
        self.assertEqual(miles(result), {('2', 'range', '1', '70')})
        self.assertEqual({b['value'] for b in result['benefits'] if b['kind'] == 'discount'}, {'7'})

    def test_postfix_formula_denial_stays_denied_through_both_entrypoints(self):
        for literal in ('2 мили за каждые потраченные 70 руб. больше не начисляются.',
                        '2,5 мили за каждые потраченные 85,50 ₽ временно не начисляются.'):
            with self.subTest(literal=literal):
                self.assertEqual(miles(project(retail(literal))), set())
                self.assertEqual(normalize_rates(literal), [])
                self.assertEqual(miles(self.retained(literal, value='2' if literal.startswith('2 мили') else '2.5',
                    basis='70' if literal.startswith('2 мили') else '85.5',
                    evidence='2 мили за каждые потраченные 70 руб' if literal.startswith('2 мили') else '2,5 мили за каждые потраченные 85,50 ₽')), set())

    def test_lexical_postfix_formula_denial_is_not_a_positive_rate(self):
        self.assertEqual(normalize_rates('2 мили за каждые потраченные 70 руб. больше не начисляются.'), [])

    def test_postfix_denial_does_not_borrow_neighbor_or_product_exclusion(self):
        for separator in ('; ', ', '):
            literal = ('2 мили за каждые потраченные 70 руб. больше не начисляются' + separator
                       + 'до 3 мили за каждые потраченные 85 руб. начисляются.')
            with self.subTest(separator=separator):
                self.assertEqual(miles(project(retail(literal))), {('3', 'up_to', None, '85')})
        literal = '2 мили за каждые потраченные 70 рублей не начисляются на подарочные карты.'
        self.assertEqual(miles(project(retail(literal))), {('2', 'exact', None, '70')})
        for literal, basis_unit in (('2 мили за каждые 90 баллов не начисляются.', 'points'),
                                    ('2 мили за каждые 3 дня не начисляются.', 'day')):
            with self.subTest(literal=literal):
                self.assertEqual(normalize_rates(literal), [])
                positive, = normalize_rates(literal.replace(' не начисляются', ' начисляются'))
                self.assertEqual(positive['basis_unit'], basis_unit)

    def test_source_product_exclusion_keeps_earning(self):
        row = retail('2 мили за каждые потраченные 85 руб. Мили не начисляются на подарочные карты.')
        self.assertEqual(miles(project(row)), {('2', 'exact', None, '85')})
        self.assertIn('подарочные карты', project(row)['raw']['conditions'])

    def test_source_utair_denial_does_not_become_multiplier(self):
        for phrase in ('двойные мили больше не начисляются',
                       '2,5-кратные мили временно не начисляются'):
            with self.subTest(phrase=phrase):
                row = parse('utair_generations_rules', GENERATIONS.replace('двойные мили', phrase))[0]
                self.assertIsNone(row['details']['reward_multiplier'])
                self.assertFalse(any(b['kind'] == 'reward_multiplier' for b in project(row)['benefits']))
                self.assertIn(phrase, row['conditions_text'])

    def test_source_live_multiplier_is_not_conflicted_by_denied_sibling(self):
        for phrase in ('двойные мили больше не начисляются; тройные мили начисляются',
                       'тройные мили больше не начисляются; тройные мили начисляются'):
            with self.subTest(phrase=phrase):
                row = parse('utair_generations_rules', GENERATIONS.replace('двойные мили', phrase))[0]
                self.assertEqual(row['details']['reward_multiplier'], 3)
                self.assertEqual([b['value'] for b in project(row)['benefits'] if b['kind'] == 'reward_multiplier'], ['3'])

    def test_retained_truncated_denied_fields_do_not_resurrect_earning(self):
        for field in ('earning_rules', 'flight_bonus_rates'):
            with self.subTest(field=field):
                result = self.retained('Не начисляются 2 мили за каждые потраченные 70 руб.', field=field)
                self.assertEqual(miles(result), set())

    def test_retained_truncated_bounds_replace_exact_semantics(self):
        for field in ('earning_rules', 'flight_bonus_rates'):
            for prefix, expected in (('До ', ('2', 'up_to', None, '70')),
                                     ('От 1 до ', ('2', 'range', '1', '70'))):
                with self.subTest(field=field, prefix=prefix):
                    self.assertEqual(miles(self.retained(prefix + '2 мили за каждые потраченные 70 руб.', field=field)), {expected})

    def test_retained_live_and_denied_same_quote_keep_live_semantics(self):
        for live in ('2 мили за каждые потраченные 70 руб.',
                     'До 2 мили за каждые потраченные 70 руб.'):
            result = self.retained('Не начисляются 2 мили за каждые потраченные 70 руб.; ' + live)
            qualifier = 'up_to' if live.startswith('До') else 'exact'
            self.assertEqual(miles(result), {('2', qualifier, None, '70')})

    def test_retained_multiplier_denial_is_reconciled_against_original(self):
        row = parse('utair_generations_rules', GENERATIONS)[0]
        raw = published_input(row)
        raw['benefit'] = raw['conditions'] = 'двойные мили больше не начисляются.'
        raw['details']['reward_multiplier_evidence'] = 'двойные мили'
        before = copy.deepcopy(raw)
        result = normalize_record(raw, as_of='2026-11-13')
        self.assertFalse(any(b['kind'] == 'reward_multiplier' for b in result['benefits']))
        self.assertEqual(result['raw'], before)

    def test_unmatched_retained_native_claim_and_channel_are_not_guessed_away(self):
        result = self.retained('Условия программы сохранены в документе.', channel='direct')
        rule, = [b for b in result['benefits'] if b['kind'] == 'earn_miles']
        self.assertEqual((rule['value'], rule['qualifier'], rule['basis_value']), ('2', 'exact', '70'))
        self.assertEqual(rule['scope'].get('channel'), 'direct')

    def test_live_channel_rates_survive_unrelated_corporate_exclusion(self):
        row = parse('af_iway_rules', IWAY.replace('Использовать мили:', 'Мили не начисляются по корпоративным поездкам. Использовать мили:'))[0]
        result = project(row)
        self.assertEqual(miles(result), {('1', 'exact', None, '50'), ('1', 'exact', None, '90')})
        self.assertEqual({b['scope'].get('channel') for b in result['benefits'] if b['kind'] == 'earn_miles' and b['method'] == 'structured_source'}, {'direct', 'travel_agent'})

    def test_missing_template_still_fails_and_literal_exact_still_works(self):
        with self.assertRaisesRegex(ValueError, 'retail_earning_rule_changed'):
            retail('Условия начисления будут опубликованы позднее.')
        self.assertEqual(miles(project(retail(FORMULA))), {('1', 'exact', None, '70')})
        self.assertEqual(earning_rules('1,5 мили за каждые потраченные 1.500,50 руб.')[0]['value'], '1.5')

    def test_retained_branded_formula_denial_and_bounds_use_original_occurrence(self):
        evidence = '2 мили «Аэрофлот Бонус» за каждые потраченные 70 руб'
        for field in ('earning_rules', 'flight_bonus_rates'):
            for literal, expected in (
                ('Не начисляются 2 мили «Аэрофлот Бонус» за каждые потраченные 70 руб.', set()),
                ('2 мили «Аэрофлот Бонус» за каждые потраченные 70 руб. больше не начисляются.', set()),
                ('До 2 мили «Аэрофлот Бонус» за каждые потраченные 70 руб.', {('2', 'up_to', None, '70')}),
                ('От 1 до 2 мили «Аэрофлот Бонус» за каждые потраченные 70 руб.', {('2', 'range', '1', '70')}),
                ('2 мили «Аэрофлот Бонус» за каждые потраченные 70 руб.', {('2', 'exact', None, '70')}),
            ):
                with self.subTest(field=field, literal=literal):
                    self.assertEqual(miles(self.retained(literal, field=field, evidence=evidence)), expected)
                    self.assertEqual(miles(project(retail(literal))), expected)

    def test_all_supported_forward_mileage_denominators_own_postfix_denial(self):
        cases = (
            ('2 мили S7 за каждые 70 руб.', '70', 'RUB'),
            ('2 мили S7 Airlines за каждые 85,50 ₽', '85.5', 'RUB'),
            ('2 мили за каждые сутки', '1', 'day'),
            ('2 мили в месяц', '1', 'month'),
            ('2 мили S7 за каждые сутки', '1', 'day'),
            ('2 мили S7 Airlines в месяц', '1', 'month'),
            ('2 мили «Аэрофлот Бонус» за каждые потраченные 70 руб.', '70', 'RUB'),
        )
        for formula, basis, unit in cases:
            with self.subTest(formula=formula):
                self.assertEqual(normalize_rates(formula + ' больше не начисляются.'), [])
                positive, = normalize_rates(formula + ' начисляются.')
                self.assertEqual((positive['value'], positive['basis_amount'], positive['basis_unit']), ('2', basis, unit))
                bounded, = normalize_rates('До ' + formula + ' начисляются.')
                self.assertEqual((bounded['value'], bounded['qualifier'], bounded['basis_amount'], bounded['basis_unit']), ('2', 'up_to', basis, unit))
                eligible, = normalize_rates(formula + ' не начисляются на подарочные карты.')
                self.assertEqual((eligible['value'], eligible['basis_amount'], eligible['basis_unit']), ('2', basis, unit))
                for separator in ('; ', ', '):
                    live = normalize_rates(formula + ' больше не начисляются' + separator +
                                           'до 3 мили за каждые потраченные 90 руб. начисляются.')
                    self.assertEqual([(r['value'], r['qualifier'], r['basis_amount'], r['basis_unit']) for r in live],
                                     [('3', 'up_to', '90', 'RUB')])
