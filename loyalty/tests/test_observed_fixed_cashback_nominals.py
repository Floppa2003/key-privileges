"""Owned nominal rewards in retained public content and an anonymous excerpt."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))
from normalized import normalize_rates
from content_discovery import literal_benefits, literal_rates
from unified_normalization import normalize_record, validate_normalized
from test_unified_normalization import record

ROOT = Path(__file__).parent
PUBLIC = json.loads((ROOT / 'fixtures_live' /
                     'observed-fixed-cashback-rub-20261114.json').read_text())['cases']
OPTIONS = json.loads((ROOT / 'fixtures' /
                      'observed-shared-point-options-20261114.json').read_text())


def public_record(case):
    return record(id='observed-cashback:' + case, source_row=None, original={},
                  **PUBLIC[case])


class ObservedFixedCashbackNominalTests(unittest.TestCase):
    def normalized(self, raw):
        original = copy.deepcopy(raw)
        result = normalize_record(raw, as_of='2026-11-14')
        self.assertEqual(raw, original)
        self.assertEqual(result['raw'], original)
        validate_normalized(result)
        return result

    def test_public_full_sources_award_the_literal_cashback_not_the_purchase_amount(self):
        for case in ('mir_tour_cashback', 'ekp_tour_cashback'):
            with self.subTest(case=case):
                raw = public_record(case)
                result = self.normalized(raw)
                awards = [b for b in result['benefits'] if b['kind'] == 'cashback']
                self.assertTrue(awards, result['benefits'])
                self.assertEqual({(b['value'], b['unit'], b['qualifier']) for b in awards},
                                 {('1000', 'RUB', 'exact')})
                minima = [c for c in result['conditions']
                          if c['kind'] == 'minimum_purchase' and c['value'] == '300000']
                self.assertTrue(minima)
                for award in awards:
                    own = [c for c in minima if c['evidence'] == award['evidence']]
                    self.assertTrue(own, award)
                    self.assertTrue({c['id'] for c in own} & set(award['condition_ids']), award)
                self.assertFalse(any(b['value'] in ('300000', '3000') for b in result['benefits']))
                if case == 'mir_tour_cashback':
                    self.assertTrue(any(c['kind'] == 'benefit_cap' and c['value'] == '3000'
                                        for c in result['conditions']))

    def test_source_rate_parser_keeps_fixed_monetary_cashback_type(self):
        raw = public_record('mir_tour_cashback')
        rates = normalize_rates(raw['benefit'])
        self.assertEqual([(r['kind'], r['value'], r['unit'], r['qualifier']) for r in rates],
                         [('cashback', '1000', 'RUB', 'exact')])

    def test_literal_source_projection_uses_the_same_monetary_occurrence(self):
        raw = public_record('mir_tour_cashback')
        claims, terms = literal_benefits(raw['benefit'])
        self.assertEqual(claims, [raw['benefit']])
        self.assertEqual([(t['kind'], t['value'], t['unit']) for t in terms],
                         [('cashback', '1000', 'RUB')])
        self.assertEqual(terms[0]['fragment'], raw['benefit'])

    def test_public_literal_discovery_keeps_each_owned_cashback_statement(self):
        for case, counts in (('mir_tour_cashback', (1, 1, 0)),
                             ('ekp_tour_cashback', (0, 0, 1))):
            for field, count in zip(('benefit', 'conditions', 'activation'), counts):
                with self.subTest(case=case, field=field):
                    literal = PUBLIC[case][field]
                    claims, terms = literal_benefits(literal)
                    expected = [('cashback', '1000', 'RUB', 'exact')] * count
                    self.assertEqual(len(claims), count)
                    self.assertEqual([(t['kind'], t.get('value'), t.get('unit'),
                                       t.get('qualifier')) for t in terms], expected)
                    self.assertEqual([t['fragment'] for t in terms], claims)
                    self.assertTrue(all(claim in literal for claim in claims))
                    self.assertEqual([(r['kind'], r['value'], r['unit'], r['qualifier'])
                                      for r in literal_rates(literal)], expected)

    def test_demo_topup_bonus_owns_its_requirement_and_event_deadline(self):
        raw = public_record('finpodushka_topup_bonus')
        result = self.normalized(raw)
        awards = result['benefits']
        self.assertEqual(len(awards), 1)
        bonus = awards[0]
        self.assertEqual((bonus['kind'], bonus['value'], bonus['unit'], bonus['qualifier']),
                         ('earn_rewards', '500', 'RUB', 'exact'))
        self.assertFalse(bonus['standalone_offer'])
        self.assertIsNone(bonus['reward_unit'])
        self.assertEqual(bonus['scope']['occasion'], 'demo_account_topup')
        expected = ('Пополните счёт на 10 000 ₽ до окончания демопериода — '
                    'и заберите дополнительный бонус 500 ₽')
        self.assertEqual(bonus['evidence'], {'path': '/activation', 'text': expected})
        linked = [c for c in result['conditions'] if c['id'] in bonus['condition_ids']]
        self.assertEqual({c['kind'] for c in linked},
                         {'required_account_topup', 'timing_condition'})
        topup = next(c for c in linked if c['kind'] == 'required_account_topup')
        self.assertEqual((topup['value'], topup['unit'], topup['qualifier']),
                         ('10000', 'RUB', 'exact'))
        timing = next(c for c in linked if c['kind'] == 'timing_condition')
        self.assertEqual(timing['scope']['timing_basis'], 'customer_demo_period')
        self.assertEqual(timing['evidence']['text'], 'до окончания демопериода')
        self.assertIsNone(timing['value'])
        self.assertFalse(any(k in bonus['scope'] for k in ('valid_from', 'valid_until')))
        self.assertFalse(any(b['value'] in ('100000', '10000', '100') or b['kind'] == 'cashback'
                             for b in awards))

    def test_retained_caps_and_other_nominals_are_not_new_cash_awards(self):
        for case in ('caps', 'backit_megafon', 'telegram_cap'):
            with self.subTest(case=case):
                raw = public_record(case)
                result = self.normalized(raw)
                rub = [b for b in result['benefits'] if b['kind'] == 'cashback' and b['unit'] == 'RUB']
                self.assertEqual([(b['value'], b['scope'].get('tariff_condition')) for b in rub],
                                 [('240', 'Подключения (активированная сим-карта и др.)')]
                                 if case == 'backit_megafon' else [])
                self.assertFalse(any(r['unit'] == 'RUB' for r in
                                     normalize_rates(raw['conditions'] + '\n' + raw['activation'])))

    def test_legacy_closed_card_options_share_their_own_point_unit(self):
        raw = record(origin='loyalty_partner_benefits', privacy='private', kind='legacy_offer',
                     program='Программа', title='Банк — приветственные баллы',
                     benefit=OPTIONS['benefit'], conditions=OPTIONS['conditions'],
                     activation=OPTIONS['activation'], rates=[],
                     details={'declared_benefit_type': OPTIONS['declared_benefit_type']})
        result = self.normalized(raw)
        awards = result['benefits']
        self.assertEqual(len(awards), 3)
        self.assertEqual({b['scope'].get('card_option'): b['value'] for b in awards},
                         OPTIONS['option_values'])
        self.assertEqual({(b['kind'], b['unit'], b['reward_unit'], b['qualifier']) for b in awards},
                         {('earn_points', 'points', 'points', 'exact')})
        caps = [c for c in result['conditions'] if c['kind'] == 'benefit_cap'
                and c['value'] == '14000' and c['unit'] == 'points']
        self.assertEqual(len(caps), 1)
        self.assertEqual(caps[0]['scope']['limit_scope'], 'multiple_participating_cards')
        for award in awards:
            self.assertIn(caps[0]['id'], award['condition_ids'])
            self.assertIn('14 000 баллов', award['evidence']['text'])
        self.assertTrue(any(c['kind'] == 'minimum_purchase' and c['value'] == '3000'
                            and c['unit'] == 'RUB' for c in result['conditions']))
        self.assertFalse(any(b['value'] == '14000' or b['unit'] == 'RUB' for b in awards))


if __name__ == '__main__':
    unittest.main()
