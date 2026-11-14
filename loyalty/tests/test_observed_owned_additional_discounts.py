"""Additional literal discounts retain their native coupon or service rules."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from public_reward_projection import fields, make_record
from test_observed_campaign_periods import retained_without_dates
from unified_normalization import normalize_record, validate_normalized


CASES = json.loads((Path(__file__).parent /
    'fixtures_live/observed-owned-additional-discounts-20261114.json').read_text())['cases']
EXPECTED = {
    'ВкусВилл': [('200', 'RUB')],
    'Авито бронирование жилья': [('1000', 'RUB')],
    'Авито бронирование отелей': [],
    'Pharmacosmetica': [],
    'englex.ru': [('40', 'percent')],
    'Studiofloristic': [('2', 'percent'), ('3', 'percent'), ('2', 'percent'), ('5', 'percent')],
    'King Power': [('10', 'percent'), ('20', 'percent'), ('15', 'percent'),
                   ('10', 'percent'), ('20', 'percent'), ('10', 'percent'), ('20', 'percent')],
    'Kolet': [('10', 'percent')],
    'Autogrill': [('5', 'percent')],
}


class ObservedOwnedAdditionalDiscounts(unittest.TestCase):
    def test_source_components_reach_common_with_their_conditions_and_raw_unchanged(self):
        for case in CASES:
            with self.subTest(partner=case['evidence']['name']):
                row = make_record(case['source'], case['evidence'], case['observed_at'])
                raw = retained_without_dates(row)
                before = copy.deepcopy(raw)
                n = normalize_record(raw, as_of='2026-11-14')
                validate_normalized(n)
                self.assertEqual(raw, before)
                self.assertEqual(n['raw'], before)
                terms = [b for b in n['benefits'] if b['evidence']['path'] == '/conditions' and b['kind'] == 'discount']
                self.assertEqual([(b['value'], b['unit']) for b in terms], EXPECTED[case['evidence']['name']])
                for b in terms:
                    self.assertFalse(b['standalone_offer'])
                    self.assertTrue(b['condition_ids'])
                    self.assertEqual(b['condition_linkage'], 'full_owned_record_rules')

    def test_extra_rates_are_scoped_to_native_conditions_not_merchant_cashback(self):
        for case in CASES:
            e = case['evidence']
            with self.subTest(partner=e['name']):
                before = copy.deepcopy(e)
                f = fields(case['source'], e)
                self.assertEqual(e, before)
                terms = [t for t in f['terms'] if t.get('path') == '/conditions' and t['kind'] == 'discount']
                self.assertEqual([(t['value'], t['unit']) for t in terms], EXPECTED[e['name']])
                for t in terms:
                    self.assertEqual(t['kind'], 'discount')
                    self.assertFalse(t['standalone_offer'])
                    self.assertIn(t['fragment'], f['conditions'])
                    self.assertEqual(t['scope']['source_clause'], t['fragment'])
                self.assertTrue(any(t.get('path', '/benefit') == '/benefit' for t in f['terms']))

    def test_dated_coupon_and_tariff_descriptions_do_not_gain_unqualified_discount(self):
        for case in CASES:
            if case['evidence']['name'] not in ('Pharmacosmetica', 'Авито бронирование отелей'):
                continue
            f = fields(case['source'], case['evidence'])
            self.assertTrue(all(t['kind'] == 'cashback' for t in f['terms']))
            self.assertIn('Скидка 20%' if case['evidence']['name'] == 'Pharmacosmetica'
                          else 'скидкой 5%', f['conditions'] + '\n' + f['benefit'])


if __name__ == '__main__':
    unittest.main()
