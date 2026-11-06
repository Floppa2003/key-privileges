"""Percent units and bounds belong to their own literal rate occurrence."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from unified_normalization import normalize_record
from test_unified_normalization import record


class UnifiedRateOwnership(unittest.TestCase):
    def benefits(self, literal, **updates):
        raw = record(benefit=literal, conditions='', **updates)
        result = normalize_record(raw, as_of='2026-11-06')
        self.assertEqual(result['raw'], raw)
        for benefit in result['benefits']:
            self.assertIn(benefit['evidence']['text'], literal)
        return result['benefits']

    def test_real_tvil_cashback_does_not_inherit_neighboring_mileage_unit(self):
        literal = ('TVIL - до 13 % милями за бронирование отелей и квартир на TVIL '
                   '+ кешбэк 30% на следующие поездки.')
        values = self.benefits(literal)
        self.assertCountEqual([(x['kind'], x['value'], x['reward_unit']) for x in values],
                              [('earn_miles', '13', 'miles'), ('cashback', '30', None)])

    def test_same_amount_with_distinct_reward_units_keeps_both_claims(self):
        for literal in ('Кешбэк 10% баллами + кешбэк 10% рублями.',
                        'Кешбэк 10% рублями + кешбэк 10% баллами.'):
            with self.subTest(literal=literal):
                values = self.benefits(literal)
                self.assertCountEqual([(x['kind'], x['value']) for x in values],
                                      [('earn_points', '10'), ('cashback', '10')])

    def test_shared_cashback_label_keeps_local_postfix_units(self):
        values = self.benefits('Кешбэк 10% баллами, 20% рублями и 30% милями.')
        self.assertCountEqual([(x['kind'], x['value']) for x in values],
                              [('earn_points', '10'), ('cashback', '20'),
                               ('earn_miles', '30')])

    def test_explicit_local_cash_unit_overrides_shared_point_label(self):
        values = self.benefits('Кешбэк в баллах 10%, 20% деньгами.')
        self.assertCountEqual([(x['kind'], x['value']) for x in values],
                              [('earn_points', '10'), ('cashback', '20')])

    def test_parallel_preposed_units_belong_to_the_following_rates(self):
        cases = (
            ('Кешбэк рублями 10%, баллами 20%.',
             [('cashback', '10'), ('earn_points', '20')]),
            ('Кешбэк баллами 10%, рублями 20%.',
             [('earn_points', '10'), ('cashback', '20')]),
            ('Кешбэк рублями 10% и милями 20%.',
             [('cashback', '10'), ('earn_miles', '20')]),
            ('Cashback in cash 10% and in points 20%.',
             [('cashback', '10'), ('earn_points', '20')]),
        )
        for literal, expected in cases:
            with self.subTest(literal=literal):
                self.assertCountEqual([(x['kind'], x['value']) for x in self.benefits(literal)],
                                      expected)

    def test_postfix_label_unit_does_not_become_shared_prefix_for_next_rate(self):
        values = self.benefits('10% кешбэк баллами, 20% на следующие покупки.')
        self.assertCountEqual([(x['kind'], x['value']) for x in values],
                              [('earn_points', '10'), ('cashback', '20')])

    def test_english_aliases_preserve_occurrence_identity(self):
        values = self.benefits('Cashback 10% in points + cashback 10% in cash.')
        self.assertCountEqual([(x['kind'], x['value']) for x in values],
                              [('earn_points', '10'), ('cashback', '10')])

    def test_legacy_discount_column_does_not_bypass_numeric_validation(self):
        for literal in ('110%', '1 000%', '1.5.5%'):
            with self.subTest(literal=literal):
                self.assertEqual(self.benefits(literal,
                                 origin='VG_community_offers'), [])

    def test_mileage_fallback_does_not_salvage_invalid_rate_suffixes(self):
        for literal in ('110% суммы бронирования милями.',
                        '1 000% суммы бронирования милями.',
                        '10–5% суммы бронирования милями.'):
            with self.subTest(literal=literal):
                self.assertEqual(self.benefits(literal), [])

    def test_mileage_fallback_retains_both_verbal_range_bounds(self):
        values = self.benefits('От 5 до 10% суммы бронирования милями.')
        self.assertEqual([(x['value_min'], x['value'], x['qualifier']) for x in values],
                         [('5', '10', 'range')])

    def test_later_mileage_label_does_not_attach_to_earlier_prepayment(self):
        values = self.benefits('50% предоплата, 10% суммы бронирования милями.')
        self.assertEqual([(x['kind'], x['value']) for x in values], [('earn_miles', '10')])


if __name__ == '__main__':
    unittest.main()
