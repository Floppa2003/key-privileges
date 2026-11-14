"""Native supplementary rewards keep programme, trigger and acquisition distinct."""
import copy
import json
from pathlib import Path
import unittest

from public_reward_projection import make_record
from test_source_availability_dates import stored_input
from unified_normalization import make_input, normalize_record


CAPTURE = json.loads(Path(__file__).with_name('fixtures_live').joinpath(
    'observed-owned-bonus-followup-20261114.json').read_text())['records']
CASES = {item['name']: item for item in CAPTURE}
AS_OF = '2026-11-14'


def retained(name):
    item = CASES[name]
    row = make_record(item['source'], item['evidence'], item['observed_at'])
    source_row = stored_input({
        'schema_version': 2, 'run_id': '43612232710:1', 'observed_at': row['observed_at'],
        'records': [row], 'sources': [{
            'source_id': item['source'], 'name': row['program'], 'root': row['source_url'],
            'status': 'ok', 'normalized': 1, 'discovered': 1, 'failed': 0,
            'coverage': 'complete_observed_public_native_object', 'region': None,
            'errors': [], 'observed_at': row['observed_at'],
        }],
    })
    return make_input(source_row)


def projected(name):
    return normalize_record(retained(name), as_of=AS_OF)


class ObservedOwnedBonusFollowup(unittest.TestCase):
    def test_hotel_birthday_gift_has_its_programme_occasion_and_own_eligibility(self):
        n = projected('hotel_birthday')
        grants = [b for b in n['benefits'] if b['kind'] == 'earn_points' and b['unit'] == 'points']
        self.assertEqual([(b['value'], b['reward_unit']) for b in grants],
                         [('3000', 'Mantera_bonus_not_cash')])
        grant = grants[0]
        self.assertEqual(grant['scope']['reward_program'], 'Мантера Моменты')
        self.assertEqual(grant['scope']['occasion'], 'birthday')
        self.assertNotIn('member_tier', grant['scope'])
        self.assertIn('у которых заполнена дата рождения', grant['scope']['eligibility_clause'])
        self.assertIn('за 1 месяц до даты рождения', grant['scope']['crediting_clause'])
        self.assertIn('в течение 1 года', grant['scope']['bonus_validity_clause'])
        self.assertEqual(grant['evidence']['path'], '/conditions')
        self.assertEqual([b['value'] for b in n['benefits'] if b['unit'] == 'percent'],
                         ['3', '5', '7', '10', '15'])

    def test_gorod_t2_awards_preserve_the_two_literal_second_month_occurrences(self):
        n = projected('t2_activation_renewals')
        grants = [b for b in n['benefits'] if b['kind'] == 'earn_points']
        self.assertEqual([(b['value'], b['unit'], b['reward_unit']) for b in grants],
                         [('100', 'points', 'Gorod_bonus_not_cash'),
                          ('150', 'points', 'Gorod_bonus_not_cash'),
                          ('200', 'points', 'Gorod_bonus_not_cash')])
        self.assertEqual([b['scope']['occasion'] for b in grants], [
            'активации тарифа и привязки номера в профиле участника программы лояльности',
            'продления тарифа на второй месяц', 'продления тарифа на второй месяц'])
        for grant in grants:
            self.assertEqual(grant['scope']['reward_program'], 'Город / Тройка')
            self.assertIn('в течении 30 календарных дней', grant['scope']['crediting_clause'])
            self.assertEqual(grant['scope']['coupon_id'], 19047)
            self.assertEqual(grant['evidence']['path'], '/conditions')
            self.assertIs(grant['standalone_offer'], False)
        self.assertEqual([(b['value'], b['unit']) for b in n['benefits'] if b['kind'] == 'discount'],
                         [('50', 'percent')])
        self.assertNotIn('225', [b['value'] for b in grants])

    def test_all_38_native_coupon_purchase_rewards_have_their_own_scope(self):
        names = [name for name in CASES if name.startswith('coupon_purchase_')]
        self.assertEqual(len(names), 38)
        for name in names:
            with self.subTest(coupon=name):
                n = projected(name)
                grants = [b for b in n['benefits'] if b['kind'] == 'earn_points']
                self.assertEqual([(b['value'], b['unit'], b['reward_unit']) for b in grants],
                                 [('10', 'percent', 'Gorod_bonus_not_cash')])
                grant = grants[0]
                self.assertEqual(grant['scope']['reward_program'], 'Город / Тройка')
                self.assertEqual(grant['scope']['occasion'], 'coupon_purchase')
                self.assertEqual(grant['scope']['coupon_id'], CASES[name]['evidence']['data']['id'])
                self.assertEqual(grant['evidence']['path'], '/conditions')
                self.assertIn('Вознаграждение за покупку купона:', grant['evidence']['text'])
                self.assertIs(grant['standalone_offer'], False)

    def test_actual_controls_do_not_inherit_other_cards_bonus_components(self):
        for name in ('programme_tier_control', 'discount_only_control'):
            with self.subTest(name=name):
                n = projected(name)
                self.assertFalse(any(b['unit'] == 'points' and b['kind'] == 'earn_points'
                                     for b in n['benefits']))
                self.assertFalse(any(b['scope'].get('occasion') in ('birthday', 'coupon_purchase')
                                     for b in n['benefits']))

    def test_gorod_native_redemption_bubble_retains_its_literal_upper_bound(self):
        for name, limit in (('gorod_redemption_3121', '40'), ('gorod_redemption_3197', '40'),
                            ('gorod_redemption_3170', '30')):
            with self.subTest(name=name):
                n = projected(name)
                spend = [b for b in n['benefits'] if b['kind'] == 'redeem_points']
                self.assertEqual([(b['value'], b['unit'], b['qualifier'], b['reward_unit']) for b in spend],
                                 [(limit, 'percent', 'up_to', 'Gorod_bonus_not_cash')])
                self.assertEqual(spend[0]['evidence']['text'],
                                 'Оплата накопленными бонусами: Списание: до ' + limit + '%')
                self.assertFalse(any(b['kind'] == 'discount' for b in n['benefits']))

    def test_nine_mantera_general_rule_candidates_do_not_override_named_redemption_scope(self):
        names = [name for name in CASES if name.startswith('mantera_redemption_unconfirmed_')]
        self.assertEqual(len(names), 9)
        for name in names:
            with self.subTest(name=name):
                n = projected(name)
                self.assertIn('В остальных отелях Курорта Красная Поляна пока доступно только начисление',
                              n['raw']['conditions'])
                self.assertIn('от 20% до 50%', n['raw']['conditions'])
                self.assertFalse(any(b['kind'] == 'redeem_points' for b in n['benefits']))
                self.assertTrue(all(b['scope']['redemption_publicly_supported'] is False
                                    for b in n['benefits']))

    def test_all_native_raw_rules_and_condition_links_are_preserved(self):
        for name in CASES:
            with self.subTest(name=name):
                raw = retained(name)
                before = copy.deepcopy(raw)
                n = normalize_record(raw, as_of=AS_OF)
                self.assertEqual(raw, before)
                self.assertEqual(n['raw'], before)
                full_rules = {c['id'] for c in n['conditions'] if c['kind'] == 'owned_programme_rules'}
                self.assertTrue(full_rules)
                self.assertTrue(all(full_rules <= set(b['condition_ids']) for b in n['benefits']))


if __name__ == '__main__':
    unittest.main()
