"""Reward quantities retain bounds, wording and literal exchange denominators."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from normalized import normalize_rates
from unified_normalization import normalize_record, validate_normalized
from test_unified_normalization import record


class RewardAmountTermsTests(unittest.TestCase):
    def project(self, literal):
        raw = record(benefit=literal, conditions='', activation='')
        before = copy.deepcopy(raw)
        result = normalize_record(raw, as_of='2026-11-08')
        self.assertEqual(raw, before)
        self.assertEqual(result['raw'], before)
        validate_normalized(json.loads(json.dumps(result)))
        for group in ('benefits', 'conditions'):
            for term in result[group]:
                self.assertIn(term['evidence']['text'], literal)
        return result

    def test_lower_and_upper_bounds_are_preserved_for_each_unit(self):
        for unit, kind in (('баллов', 'earn_points'), ('миль', 'earn_miles')):
            for wording, qualifier in (('не более', 'up_to'), ('не менее', 'at_least'),
                                       ('до', 'up_to'), ('от', 'at_least')):
                with self.subTest(unit=unit, wording=wording):
                    result = self.project(f'Начислим {wording} 500 {unit}.')
                    self.assertEqual([(b['kind'], b['value'], b['value_min'], b['qualifier'])
                                      for b in result['benefits']], [(kind, '500', None, qualifier)])

    def test_word_and_dash_ranges_keep_both_endpoints(self):
        for unit, kind in (('баллов', 'earn_points'), ('миль', 'earn_miles')):
            for amount in ('от 100 до 500', '100–500', '100-500', 'от 100 ' + unit + ' до 500'):
                with self.subTest(unit=unit, amount=amount):
                    result = self.project(f'Получите {amount} {unit}.')
                    self.assertEqual([(b['kind'], b['value_min'], b['value'], b['qualifier'])
                                      for b in result['benefits']], [(kind, '100', '500', 'range')])

    def test_invalid_reward_range_cannot_leak_its_upper_suffix(self):
        for unit, kind in (('баллов', 'earn_points'), ('миль', 'earn_miles')):
            for amount in ('от 500 до 100', '500–100', 'от 1.500.5 до 500', '1 00–500',
                           '100–1.500.5', '-100', '−100', 'от -100 до 500'):
                with self.subTest(unit=unit, amount=amount):
                    result = self.project(f'Получите {amount} {unit}; получите 50 {unit}.')
                    self.assertEqual([(b['kind'], b['value']) for b in result['benefits']], [(kind, '50')])

    def test_bonus_adjective_and_earning_verb_are_literal_awards(self):
        for literal, kind in (
                ('Начислим 500 бонусных баллов.', 'earn_points'),
                ('Заработайте 500 баллов за заказ.', 'earn_points'),
                ('Начислим 500 дополнительных бонусных баллов.', 'earn_points'),
                ('Заработайте 500 дополнительных баллов.', 'earn_points'),
                ('Начислим 500 бонусных миль.', 'earn_miles')):
            with self.subTest(literal=literal):
                result = self.project(literal)
                self.assertEqual([(b['kind'], b['value']) for b in result['benefits']], [(kind, '500')])

    def test_new_wording_keeps_denials_and_expenses_out(self):
        for literal in ('Не заработаете 500 баллов.', 'Не начислим 500 бонусных баллов.',
                        'Потратьте 500 бонусных баллов.', 'Баланс + 500 баллов.',
                        'Цена: + 500 баллов.', '500 бонусных миль не начисляются.'):
            with self.subTest(literal=literal):
                self.assertEqual(self.project(literal)['benefits'], [])

    def test_additional_points_share_the_same_bounds_and_owned_action(self):
        cases = (
            ('Начислим не менее 500 дополнительных баллов.', [('500', 'at_least')]),
            ('Получите 500 дополнительных баллов и 100 дополнительных баллов.',
             [('500', 'unspecified'), ('100', 'unspecified')]),
            ('+ 500 дополнительных бонусных баллов.', [('500', 'unspecified')]),
            ('Не 500 дополнительных баллов начисляются, а 1000 дополнительных баллов.',
             [('1000', 'unspecified')]),
        )
        for literal, expected in cases:
            with self.subTest(literal=literal):
                self.assertEqual([(b['value'], b['qualifier']) for b in self.project(literal)['benefits']],
                                 expected)

    def test_plus_reward_is_preserved_with_the_neighbouring_discount(self):
        result = self.project('Скидка до 51% на первый заказ + 500 баллов.')
        self.assertEqual([(b['kind'], b['value'], b['unit']) for b in result['benefits']],
                         [('discount', '51', 'percent'), ('earn_points', '500', 'points')])
        self.assertEqual([(b['kind'], b['value']) for b in self.project('+ 500 баллов за первый заказ.')['benefits']],
                         [('earn_points', '500')])

    def test_points_exchange_base_is_preserved_at_source_and_common_boundaries(self):
        for literal in ('20 миль за каждые 500 баллов.',
                        'За каждые 500 баллов начисляем 20 миль.'):
            with self.subTest(literal=literal):
                rates = normalize_rates(literal)
                self.assertEqual([(r['value'], r['basis_amount'], r['basis_unit']) for r in rates],
                                 [('20', '500', 'points')])
                result = self.project(literal)
                self.assertEqual([(b['kind'], b['value'], b['basis_value'], b['basis_unit'])
                                  for b in result['benefits']], [('earn_miles', '20', '500', 'points')])

    def test_literal_points_earning_keeps_its_ruble_base(self):
        result = self.project('Начисляем 1 балл за каждые 3,34 рубля.')
        self.assertEqual([(b['kind'], b['value'], b['basis_value'], b['basis_unit'])
                          for b in result['benefits']], [('earn_points', '1', '3.34', 'RUB')])

    def test_malformed_exchange_base_does_not_become_a_bare_award(self):
        for unit in ('баллов', 'рублей'):
            for base in ('1.500.5', '1 00'):
                literal = f'20 миль за каждые {base} {unit}.'
                with self.subTest(literal=literal):
                    self.assertEqual(normalize_rates(literal), [])
                    self.assertEqual(self.project(literal)['benefits'], [])

    def test_nominal_period_limits_are_kept_as_caps(self):
        result = self.project('До 10 000 баллов в месяц, до 30 000 миль S7 за 30 дней.')
        self.assertEqual(result['benefits'], [])
        self.assertCountEqual([(c['kind'], c['value'], c['unit'], c['qualifier'],
                                c['basis_value'], c['basis_unit']) for c in result['conditions']],
                              [('benefit_cap', '10000', 'points', 'up_to', '1', 'month'),
                               ('benefit_cap', '30000', 'miles', 'up_to', '30', 'day')])

    def test_explicit_period_award_is_still_an_award(self):
        result = self.project('Начисляем до 500 баллов в месяц.')
        self.assertEqual([(b['kind'], b['value'], b['qualifier'], b['basis_value'], b['basis_unit'])
                          for b in result['benefits']], [('earn_points', '500', 'up_to', '1', 'month')])

    def test_denominator_cannot_cross_another_sentence_or_earning_action(self):
        for literal in ('За каждые 500 рублей получите чек. Начисляем 100 миль.',
                        'За каждые 500 рублей получите чек, а начисляем 100 миль.'):
            with self.subTest(literal=literal):
                self.assertEqual([(b['value'], b['basis_value'], b['basis_unit'])
                                  for b in self.project(literal)['benefits']], [('100', None, None)])
        literal = 'За каждые 500 руб. покупки начисляем 100 миль.'
        self.assertEqual([(b['value'], b['basis_value'], b['basis_unit'])
                          for b in self.project(literal)['benefits']], [('100', '500', 'RUB')])

    def test_nonpositive_or_range_denominator_is_not_silently_dropped(self):
        for base in ('-500', '0', '100–500', 'от 100 до 500'):
            literal = f'Начисляем 20 миль за каждые {base} баллов.'
            with self.subTest(literal=literal):
                self.assertEqual(normalize_rates(literal), [])
                self.assertEqual(self.project(literal)['benefits'], [])

    def test_incomplete_numeric_expression_is_not_reparsed_from_its_tail(self):
        for unit in ('баллов', 'миль'):
            for amount in ('100–200–500', 'от 100 до 200 до 500', '1e3–500',
                           '100–200 ' + unit + '–500'):
                literal = f'Получите {amount} {unit}.'
                with self.subTest(literal=literal):
                    self.assertEqual(self.project(literal)['benefits'], [])

    def test_parenthesized_limit_keeps_its_period_and_is_not_a_second_award(self):
        for unit, canonical, kind in (('баллов', 'points', 'earn_points'), ('миль', 'miles', 'earn_miles')):
            for bound in ('до', 'не более'):
                literal = f'Получите 500 {unit} ({bound} 1000 {unit} в месяц).'
                with self.subTest(literal=literal):
                    result = self.project(literal)
                    self.assertEqual([(b['kind'], b['value']) for b in result['benefits']], [(kind, '500')])
                    self.assertEqual([(c['kind'], c['value'], c['unit'], c['basis_value'], c['basis_unit'])
                                      for c in result['conditions']], [('benefit_cap', '1000', canonical, '1', 'month')])


if __name__ == '__main__':
    unittest.main()
