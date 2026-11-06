"""The phrase reader must pass whole source numbers to rate validation."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from content_discovery import literal_benefits, literal_rates
from flystation_source import inventory, SOURCE
from public_reward_projection import make_record
from normalized import validate_offer


class LiteralBenefitNumericBoundaries(unittest.TestCase):
    def test_ranges_are_not_truncated_before_shared_rate_validation(self):
        for literal in ('Скидка от 5 до 15% на полёты.',
                        'Скидка от 5% до 15% на полёты.',
                        'Скидка 5%–15% на полёты.',
                        '5%–15% скидка на полёты.'):
            with self.subTest(literal=literal):
                claims, terms = literal_benefits(literal)
                self.assertEqual(claims, [literal])
                self.assertEqual([(x['value'], x.get('value_min'), x['qualifier']) for x in terms],
                                 [('15', '5', 'range')])
                self.assertEqual(terms[0]['fragment'], literal)

    def test_invalid_range_or_amount_does_not_become_a_shorter_valid_claim(self):
        for literal in ('Скидка 20%–10%.', '20%–10% скидка.', 'Скидка от 20% до 10%.',
                        'Скидка 1.500.5 руб.', '1.500.5% скидка.', 'Скидка 1 00%.'):
            with self.subTest(literal=literal):
                self.assertEqual(literal_benefits(literal), ([], []))
                self.assertEqual(literal_rates(literal), [])

    def test_range_does_not_absorb_a_payment_percentage(self):
        literal = 'Скидка от 5 до 15% при предоплате 50%.'
        self.assertEqual([(x['value'], x.get('value_min')) for x in literal_benefits(literal)[1]],
                         [('15', '5')])

    def test_real_source_adapter_preserves_the_full_range_and_original_clause(self):
        literal = 'Скидка 5%–15% на полёты при предоплате 50%.'
        html = ('<section class="promotions"><div class="promotions__slider-item-text">'
                '<p>Новое предложение</p><p>' + literal + '</p></div></section>')
        evidence, = inventory(html)
        row = make_record(SOURCE, evidence, '2026-11-06T00:00:00+00:00')
        validate_offer(row)
        self.assertEqual([(x['value'], x.get('min_value'), x['qualifier']) for x in row['rates']],
                         [('15', '5', 'range')])
        self.assertEqual(row['benefit_text'], literal)


if __name__ == '__main__':
    unittest.main()
