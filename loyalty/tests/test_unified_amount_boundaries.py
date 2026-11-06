"""Malformed source numbers remain evidence instead of crashing common parsing."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from unified_normalization import normalize_record
from test_unified_normalization import record


class UnifiedNumericLiterals(unittest.TestCase):
    def parse(self, literal):
        raw = record(benefit=literal, conditions='')
        result = normalize_record(raw, as_of='2026-11-06')
        self.assertEqual(result['raw'], raw)
        return result

    def test_malformed_amount_is_neither_crash_nor_suffix_amount(self):
        patterns = (
            ('Покупка от {} рублей.', 'conditions', 'minimum_purchase'),
            ('Максимальный размер скидки {} рублей.', 'conditions', 'benefit_cap'),
            ('Получите {} баллов.', 'benefits', 'earn_points'),
            ('{} RUB off.', 'benefits', 'discount'),
        )
        for pattern, group, kind in patterns:
            for literal in ('1.500.5', '1 00', '1,5,5', '1.500,5.5'):
                with self.subTest(pattern=pattern, literal=literal):
                    result = self.parse(pattern.format(literal))
                    self.assertFalse([x for x in result[group] if x['kind'] == kind])

    def test_valid_grouped_amounts_keep_original_evidence(self):
        patterns = (
            ('Покупка от {} рублей.', 'conditions', 'minimum_purchase'),
            ('Максимальный размер скидки {} рублей.', 'conditions', 'benefit_cap'),
            ('Получите {} баллов.', 'benefits', 'earn_points'),
            ('{} RUB off.', 'benefits', 'discount'),
        )
        for pattern, group, kind in patterns:
            for amount in ('1 500,50', '1.500,50', '1,500.50', '1500.50'):
                with self.subTest(pattern=pattern, amount=amount):
                    literal = pattern.format(amount)
                    result = self.parse(literal)
                    terms = [x for x in result[group] if x['kind'] == kind]
                    self.assertEqual([(x['value'], x['evidence']['text']) for x in terms],
                                     [('1500.5', literal)])

    def test_invalid_reward_does_not_hide_next_valid_reward(self):
        result = self.parse('Получите 1.500.5 баллов; получите 250 баллов.')
        self.assertEqual([(x['kind'], x['value']) for x in result['benefits']],
                         [('earn_points', '250')])


if __name__ == '__main__':
    unittest.main()
