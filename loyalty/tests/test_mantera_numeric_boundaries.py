"""Source-owned tier rates cannot bypass the shared numeric boundaries."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
import mantera_source
from test_public_reward_sources import NOW, common, html


class ManteraNumericBoundaryTests(unittest.TestCase):
    def parse(self, original, replacement):
        source = html('mantera-faq.html')
        self.assertIn(original, source)
        return mantera_source.parse(source.replace(original, replacement, 1), NOW)[0]

    def test_earning_ranges_keep_both_bounds_through_common_projection(self):
        for rate in ('10%–15%', '10–15%', 'от 10 до 15%', 'от 10% до 15%'):
            with self.subTest(rate=rate):
                literal = 'с начислением ' + rate
                row = self.parse('с начислением 3%', literal)
                result = common(row)
                self.assertIn(literal, row['benefit_text'])
                self.assertEqual([(term['kind'], term['value'], term['value_min'],
                                   term['qualifier']) for term in result['benefits']],
                                 [('earn_points', '15', '10', 'range'),
                                  ('redeem_points', '20', None, 'up_to')])
                self.assertIn(literal, result['raw']['benefit'])

    def test_redemption_range_keeps_its_bounds_and_does_not_change_earning(self):
        row = self.parse('списанием 20%', 'списанием 10%–20%')
        result = common(row)
        self.assertEqual([(term['kind'], term['value'], term['value_min'],
                           term['qualifier']) for term in result['benefits']],
                         [('earn_points', '3', None, 'exact'),
                          ('redeem_points', '20', '10', 'range')])

    def test_invalid_explicit_percentage_is_rejected_as_a_whole(self):
        for label, old in (('с начислением ', '3%'), ('списанием ', '20%')):
            for invalid in ('20%–10%', '20–10%', '1.500.5%', '1 00%',
                            '110%', '110%–20%'):
                with self.subTest(label=label, invalid=invalid):
                    with self.assertRaisesRegex(ValueError, 'mantera_invalid_tier_rate'):
                        self.parse(label + old, label + invalid)

    def test_non_percentage_earning_stays_unclassified_with_valid_redemption(self):
        row = self.parse('с начислением 3%', 'с начислением приветственных бонусов')
        result = common(row)
        self.assertEqual([(term['kind'], term['value']) for term in result['benefits']],
                         [('redeem_points', '20')])
        self.assertIn('начислением приветственных бонусов', result['raw']['benefit'])


if __name__ == '__main__':
    unittest.main()
