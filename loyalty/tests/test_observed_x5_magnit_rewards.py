"""All retained native X5/Magnit cards, with target rewards and costs separate."""
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from public_reward_projection import make_record, fields
from test_observed_campaign_periods import AS_OF, retained_without_dates
from test_source_availability_dates import stored_input
from unified_normalization import make_input, normalize_record


CAPTURE = json.loads(Path(__file__).with_name('fixtures_live').joinpath(
    'observed-x5-magnit-rewards-20261114.json').read_text())['records']
CASES = {(s['source'], s['evidence']['native']): s for s in CAPTURE}
X5 = 'x5_partners_public'
MAGNIT = 'magnit_partners_public'
MAGNIT_POINTS = 'Magnit_bonus_not_cash'
X5_POINTS = 'X5_Club_points_not_cash'
X5_DISCOUNTS = {
    '222': [('7', 'percent')], '229': [('100', 'percent')],
    '150': [('100', 'RUB')], '175': [('200', 'RUB')],
    '223': [('20', 'percent')], '224': [('20', 'percent')],
    '56': [('20', 'percent')], '199': [('11', 'percent')],
}
X5_AWARDS = {
    '231': ('100', 'Vkusno_i_tochka_bonus_not_cash'),
    '232': ('200', 'Vkusno_i_tochka_bonus_not_cash'),
    '180': ('100', 'Yandex_Plus_points_not_cash'),
    '181': ('200', 'Yandex_Plus_points_not_cash'),
    '213': ('150', 'MTS_Urent_bonus_not_cash'),
    '214': ('300', 'MTS_Urent_bonus_not_cash'),
}
MAGNIT_AWARDS = {
    '1787': [('420', 'points')], '1838': [('750', 'points')],
    '1754': [('500', 'points'), ('300', 'points')],
    '1752': [('4', 'percent'), ('2', 'percent')], '1835': [('300', 'points')],
    '1793': [('20', 'percent'), ('10', 'percent')],
    '1781': [('20', 'percent'), ('15', 'percent'), ('12', 'percent'), ('7', 'percent')],
    '1751': [('4', 'percent')], '1782': [('5', 'percent'), ('3', 'percent')],
    '1785': [('1000', 'points')], '1758': [('2', 'percent')],
    '1763': [('11', 'percent'), ('2', 'percent')],
    '1783': [('9', 'percent'), ('80', 'points')],
    '1768': [('6', 'percent'), ('3', 'percent')],
    '1767': [('4', 'percent'), ('0.7', 'percent')], '1792': [('1200', 'points')],
    '1764': [('7', 'percent')], '1773': [('510', 'points')],
    '1774': [('9', 'percent')],
    '1766': [('4', 'percent'), ('2', 'percent'), ('0.1', 'percent')],
    '1776': [('3.5', 'percent')],
    '1769': [('7', 'percent'), ('6', 'percent'), ('1', 'percent')],
    '1777': [('20', 'percent')], '1756': [('4.5', 'percent')],
    '1761': [('30', 'percent')], '1780': [('5', 'percent')],
    '1757': [('4', 'percent')], '1765': [('30', 'percent')],
    '1760': [('5', 'percent'), ('2.5', 'percent'), ('1.8', 'percent')],
    '1778': [('3', 'percent')], '2100': [('6', 'percent'), ('4', 'percent')],
    '2101': [('7', 'percent')], '2062': [],
}


def source_record(source, native):
    capture = CASES[source, native]
    return make_record(source, capture['evidence'], capture['observed_at'])


def retained_record(source, native):
    row = source_record(source, native)
    source_row = stored_input({
        'schema_version': 2, 'run_id': '43612232710:1', 'observed_at': row['observed_at'],
        'records': [row], 'sources': [{
            'source_id': source, 'name': row['program'], 'root': row['source_url'],
            'status': 'ok', 'normalized': 1, 'discovered': 1, 'failed': 0,
            'coverage': 'complete_observed_public_native_object', 'region': None,
            'errors': [], 'observed_at': row['observed_at'],
        }],
    })
    return make_input(source_row)


def projected(source, native):
    return normalize_record(retained_record(source, native), as_of=AS_OF)


class ObservedX5MagnitRewards(unittest.TestCase):
    def test_every_native_magnit_award_has_its_own_unit_and_stated_amount(self):
        self.assertEqual({native for source, native in CASES if source == MAGNIT}, set(MAGNIT_AWARDS))
        for native, expected in MAGNIT_AWARDS.items():
            with self.subTest(native=native):
                terms = [b for b in projected(MAGNIT, native)['benefits'] if b['kind'] == 'earn_points']
                self.assertEqual([(b['value'], b['unit']) for b in terms], expected)
                self.assertTrue(all(b['reward_unit'] == MAGNIT_POINTS for b in terms))
                self.assertTrue(all(b['qualifier'] == 'exact' for b in terms))

    def test_magnit_native_tiers_and_extra_skyeng_award_keep_their_owners(self):
        yandex = [b for b in projected(MAGNIT, '1754')['benefits'] if b['kind'] == 'earn_points']
        self.assertEqual([(b['value'], b['scope']['audience']) for b in yandex], [
            ('500', 'Для новых пользователей мультиподписки Яндекс Плюс:'),
            ('300', 'Для тех, у кого была мультиподписка и закончилась более 30 дней назад:'),
        ])
        skyeng = [b for b in projected(MAGNIT, '1783')['benefits'] if b['kind'] == 'earn_points']
        self.assertEqual(len(skyeng), 2)
        self.assertIn('от суммы покупки', skyeng[0]['scope']['source_clause'])
        self.assertIn('прохождение бесплатного вводного урока', skyeng[1]['scope']['source_clause'])
        self.assertTrue(all(b['evidence']['path'] == '/conditions' for b in yandex + skyeng))

    def test_netprint_first_and_repeat_purchase_rates_keep_explicit_stages(self):
        terms = [b for b in projected(MAGNIT, '2100')['benefits'] if b['kind'] == 'earn_points']
        self.assertEqual([(b['value'], b['scope'].get('purchase_stage')) for b in terms],
                         [('6', 'first'), ('4', 'repeat')])
        self.assertIn('за первую покупку', terms[0]['scope']['source_clause'])
        self.assertIn('за повторную покупку', terms[1]['scope']['source_clause'])

    def test_magnit_t2_monthly_caps_are_conditions_and_never_awards(self):
        n = projected(MAGNIT, '2062')
        caps = [c for c in n['conditions'] if c['kind'] == 'benefit_cap']
        self.assertEqual([(c['value'], c['unit'], c['basis_unit'], c['scope']['purchase_channel'])
                          for c in caps], [('2000', 'points', 'month', 'cashdesk'),
                                          ('4000', 'points', 'month', 'online')])
        self.assertTrue(all(c['reward_unit'] == MAGNIT_POINTS for c in caps))
        self.assertFalse(any(b['kind'] == 'earn_points' for b in n['benefits']))

    def test_magnit_expired_extra_discount_keeps_its_component_period(self):
        n = projected(MAGNIT, '1761')
        discounts = [b for b in n['benefits'] if b['kind'] == 'discount']
        self.assertEqual([(b['value'], b['unit']) for b in discounts], [('10', 'percent')])
        self.assertIs(discounts[0]['standalone_offer'], False)
        self.assertEqual(discounts[0]['scope']['component_validity'],
                         {'from': '2025-04-17', 'until': '2025-12-31'})
        self.assertIsNone(n['validity']['until'])
        self.assertEqual(discounts[0]['evidence']['path'], '/conditions')

    def test_all_explicit_x5_headline_discounts_are_not_the_price_in_points(self):
        for native, expected in X5_DISCOUNTS.items():
            with self.subTest(native=native):
                n = projected(X5, native)
                discounts = [b for b in n['benefits'] if b['kind'] == 'discount']
                self.assertEqual([(b['value'], b['unit']) for b in discounts], expected)
                self.assertTrue(all(b['reward_unit'] is None for b in discounts))

    def test_x5_issued_partner_bonuses_have_the_target_currency(self):
        for native, (value, currency) in X5_AWARDS.items():
            with self.subTest(native=native):
                n = projected(X5, native)
                awards = [b for b in n['benefits'] if b['kind'] == 'earn_points']
                self.assertEqual([(b['value'], b['unit'], b['reward_unit']) for b in awards],
                                 [(value, 'points', currency)])

    def test_all_x5_native_purchased_costs_are_required_spent_points(self):
        self.assertEqual(sum(source == X5 for source, native in CASES), 38)
        for (source, native), capture in CASES.items():
            if source != X5:
                continue
            with self.subTest(native=native):
                n = projected(source, native)
                costs = [c for c in n['conditions'] if c['kind'] == 'redemption_cost']
                card = capture['evidence']['card']
                if card['type'] == 'purchased':
                    self.assertEqual([(c['value'], c['unit'], c['reward_unit']) for c in costs],
                                     [(str(card['cost']), 'points', X5_POINTS)])
                    self.assertTrue(all(costs[0]['id'] in b['condition_ids'] for b in n['benefits']))
                else:
                    self.assertEqual(costs, [])
                if native != '219':
                    self.assertFalse(any(b['kind'] == 'earn_points' and b['reward_unit'] == X5_POINTS
                                         for b in n['benefits']))

    def test_x5_mileage_exchange_keeps_spent_points_in_the_denominator(self):
        terms = [b for b in projected(X5, '202')['benefits'] if b['kind'] == 'earn_miles']
        self.assertEqual([(b['value'], b['unit'], b['basis_value'], b['basis_unit']) for b in terms],
                         [('20', 'miles', '500', 'points')])
        self.assertEqual(terms[0]['scope']['basis_reward_unit'], X5_POINTS)
        self.assertEqual(terms[0]['scope']['reward_program'], 'Аэрофлот Бонус')

    def test_x5_beeline_uplift_is_named_points_with_a_monthly_cap(self):
        n = projected(X5, '219')
        terms = [b for b in n['benefits'] if b['kind'] == 'earn_points']
        self.assertEqual([(b['value'], b['unit'], b['reward_unit']) for b in terms],
                         [('9', 'percent', X5_POINTS)])
        self.assertTrue(terms[0]['scope']['additional_cashback'])
        caps = [c for c in n['conditions'] if c['kind'] == 'benefit_cap']
        self.assertEqual([(c['value'], c['unit'], c['basis_unit']) for c in caps],
                         [('60000', 'points', 'month')])
        self.assertIn(caps[0]['id'], terms[0]['condition_ids'])

    def test_magnit_owned_participation_periods_exclude_later_crediting_delays(self):
        for native, start in (('1785', '2026-04-14'), ('1792', '2026-05-04')):
            with self.subTest(native=native):
                row = source_record(MAGNIT, native)
                self.assertEqual((row['valid_from'], row['valid_until']), (start, '2026-12-31'))
                raw = retained_without_dates(row)
                n = normalize_record(raw, as_of=AS_OF)
                self.assertEqual((n['validity']['from'], n['validity']['until']), (start, '2026-12-31'))
                self.assertEqual(n['raw'], raw)

    def test_x5_conflicting_action_end_is_not_silently_treated_as_current(self):
        for native in ('150', '175'):
            with self.subTest(native=native):
                n = projected(X5, native)
                self.assertEqual(n['validity']['status'], 'source_date_conflict')
                self.assertEqual(n['raw']['valid_until'], '2027-02-01')
                self.assertIn('Акция действует до 20.02.2026.', n['raw']['conditions'])

    def test_all_native_fields_and_retained_source_snapshots_are_unchanged(self):
        for source, native in CASES:
            with self.subTest(source=source, native=native):
                raw = retained_record(source, native)
                before = copy.deepcopy(raw)
                n = normalize_record(raw, as_of=AS_OF)
                self.assertEqual(raw, before)
                self.assertEqual(n['raw'], before)
                for benefit in n['benefits']:
                    self.assertTrue(benefit['condition_ids'])
                    self.assertEqual(benefit['condition_linkage'], 'full_owned_record_rules')

    def test_shared_term_contract_rejects_foreign_paths_and_positive_standalone_override(self):
        raw = retained_record(MAGNIT, '1758')
        original = fields(MAGNIT, CASES[MAGNIT, '1758']['evidence'])
        for change, message in (({'path': '/details/public_reward_evidence/title'}, 'term_path'),
                                ({'standalone_offer': True}, 'standalone_override')):
            with self.subTest(change=change):
                derived = copy.deepcopy(original)
                derived['terms'][0].update(change)
                with patch('public_reward_projection.fields', return_value=derived):
                    with self.assertRaisesRegex(ValueError, message):
                        normalize_record(raw, as_of=AS_OF)


if __name__ == '__main__':
    unittest.main()
