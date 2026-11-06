"""New roster projections are neutral; retained v2 and legacy data stay readable."""
import copy
import sys
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mantera_partners as partners
from catalogue_view import record_row
from public_reward_projection import make_record
from test_dom_card_boundaries import project
from test_public_reward_sources import html, NOW

RESTAURANTS = ('Ресторан Apre Ski (Курорт Красная Поляна)',
               'Ресторан «Птицы Захмелели» (Курорт Красная Поляна)')
UNKNOWN = 'Новый участник программы'


def roster_with_participants():
    soup = BeautifulSoup(html('mantera-partners.html'), 'html.parser')
    listing = soup.select_one('.accordion__item-content ul')
    for name in (*RESTAURANTS, UNKNOWN):
        item = soup.new_tag('li')
        item.string = name
        listing.append(item)
    return str(soup)


def retained_evidence(version=2):
    roster = partners.parse_roster(roster_with_participants())
    evidence = {'kind': 'public_partner', 'url': partners.ROSTER_URL,
                'name': RESTAURANTS[0], 'roster': roster,
                'resort': partners.parse_resort(html('mantera-redemption.html'))}
    if version is not None:
        evidence['projection_version'] = version
    else:
        # Synthetic old projection shape: the original five reviewed FAQ fields.
        roster['faq'] = {question: roster['faq'][question] for question in partners.QUESTIONS}
    return evidence


class ManteraPartnerScopeTests(unittest.TestCase):
    def test_restaurants_and_unknown_participant_use_neutral_scope(self):
        rows, inventory = partners.parse_pair(roster_with_participants(), html('mantera-redemption.html'), NOW)
        self.assertEqual((len(inventory['names']), len(rows)), (14, 13))
        selected = [row for row in rows if row['partner_name'] in (*RESTAURANTS, UNKNOWN)]
        self.assertEqual(len(selected), 3)
        for row in selected:
            with self.subTest(name=row['partner_name']):
                self.assertEqual(row['details']['public_reward_evidence']['projection_version'], 3)
                self.assertEqual(row['category'], 'Партнёры / бонусы')
                self.assertIn('partner_redemption_not_confirmed', row['warnings'])
                self.assertNotIn('hotel_redemption_not_confirmed', row['warnings'])
                self.assertIn('Личный доступ и конкретная покупка не проверялись.', row['conditions_text'])
                common = project(row)
                self.assertEqual([b['kind'] for b in common['benefits']], ['earn_points'] * 5)
                for term in common['benefits'] + common['conditions']:
                    self.assertEqual(term['scope']['partner'], row['partner_name'])
                    self.assertNotIn('hotel', term['scope'])
                view, reason = record_row(common, NOW[:10])
                self.assertIsNone(reason)
                self.assertIsNotNone(view)

    def test_neutral_projection_keeps_the_exact_named_redemption_membership(self):
        rows, inventory = partners.parse_pair(html('mantera-partners.html'), html('mantera-redemption.html'), NOW)
        self.assertEqual((inventory['version'], len(inventory['names']), len(rows)), (1, 11, 10))
        for row in rows:
            with self.subTest(name=row['partner_name']):
                common = project(row)
                self.assertEqual(row['category'], 'Партнёры / бонусы')
                earned = [b['value'] for b in common['benefits'] if b['kind'] == 'earn_points']
                redeemed = [b['value'] for b in common['benefits'] if b['kind'] == 'redeem_points']
                self.assertEqual(earned, ['3', '5', '7', '10', '15'])
                self.assertEqual(redeemed, ['20', '20', '30', '40', '50']
                                 if row['partner_name'] in partners.REDEMPTION_ALIASES.values() else [])
                self.assertTrue(all(b['scope']['partner'] == row['partner_name'] for b in common['benefits']))
                previous = copy.deepcopy(row['details']['public_reward_evidence'])
                previous['projection_version'] = 2
                self.assertEqual(make_record('mantera_moments', previous, NOW)['id'], row['id'])

    def test_retained_v2_keeps_its_old_fields_and_common_projection(self):
        evidence = retained_evidence()
        before = copy.deepcopy(evidence)
        row = make_record('mantera_moments', evidence, NOW)
        common = project(row)
        self.assertEqual(row['category'], 'Отели / бонусы')
        self.assertIn('hotel_redemption_not_confirmed', row['warnings'])
        self.assertNotIn('partner_redemption_not_confirmed', row['warnings'])
        self.assertIn('Личный доступ и конкретное бронирование не проверялись.', row['conditions_text'])
        self.assertTrue(all(b['scope']['hotel'] == RESTAURANTS[0] for b in common['benefits']))
        self.assertTrue(all('partner' not in b['scope'] for b in common['benefits']))
        self.assertEqual(common['raw']['details']['public_reward_evidence'], before)
        self.assertEqual(evidence, before)

    def test_unversioned_legacy_keeps_its_original_mapper(self):
        evidence = retained_evidence(None)
        before = copy.deepcopy(evidence)
        fields = partners.source_fields(evidence)
        self.assertEqual(fields, partners.legacy_source_fields(evidence))
        row = make_record('mantera_moments', evidence, NOW)
        common = project(row)
        self.assertEqual(row['category'], 'Отели / бонусы')
        self.assertIn('hotel_redemption_not_confirmed', row['warnings'])
        self.assertTrue(all(b['scope']['hotel'] == RESTAURANTS[0] for b in common['benefits']))
        self.assertEqual(common['raw']['details']['public_reward_evidence'], before)
        self.assertEqual(evidence, before)

    def test_unknown_projection_versions_remain_rejected(self):
        for version in (-1, 1, 4, '3', True):
            with self.subTest(version=version):
                with self.assertRaisesRegex(ValueError, 'mantera_partner_projection_version'):
                    make_record('mantera_moments', retained_evidence(version), NOW)


if __name__ == '__main__':
    unittest.main()
