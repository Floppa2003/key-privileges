"""Published link forms and separate tier claims must survive partner discovery."""
import sys
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parents[1]))
from adapters import extract
from normalized import validate_offer

NOW = '2026-11-06T00:00:00+00:00'
URL = 'https://media.utair.ru/status'
BRONZE = 'ТВИЛ.РУ — 5% милями для уровня Bronze'
GOLD = 'ТВИЛ.РУ — 10% милями для уровня Gold'


def panel(anchors):
    return '<div id="rec774882292" class="uc-showmore3">' + anchors + '</div>'


class UtairPartnerDiscoveryTests(unittest.TestCase):
    def parse(self, anchors):
        rows = extract('utair_media', panel(anchors), URL, NOW)
        for row in rows:
            validate_offer(row)
        return rows

    def test_protocol_relative_destination_resolves_to_https(self):
        try:
            rows = self.parse('<a href="//utair.tvil.ru/">' + BRONZE + '</a>')
        except ValueError as exc:
            self.fail('A public relative HTTPS link was rejected: ' + str(exc))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['details']['partner_url'], 'https://utair.tvil.ru/')
        self.assertEqual(rows[0]['native_id'], 'utair.tvil.ru/')
        self.assertEqual(rows[0]['partner_name'], 'ТВИЛ.РУ')

    def test_same_destination_preserves_distinct_tier_conditions(self):
        first = '<a href="https://utair.tvil.ru/">' + BRONZE + '</a>'
        rows = self.parse(first + '<a href="https://utair.tvil.ru/">' + GOLD + '</a>')
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['conditions_text'], BRONZE + '\n' + GOLD)
        self.assertEqual(row['benefit_text'], BRONZE + '\n' + GOLD)
        self.assertEqual(row['id'], self.parse(first)[0]['id'])
        self.assertEqual([r['value'] for r in row['rates']], ['5', '10'])
        self.assertEqual(row['details']['tier_rates'], [
            {'tiers': ['Bronze'], 'value': '5', 'unit': 'percent_miles', 'evidence': BRONZE},
            {'tiers': ['Gold'], 'value': '10', 'unit': 'percent_miles', 'evidence': GOLD},
        ])

    def test_canonical_aliases_keep_locators_for_every_distinct_claim(self):
        anchors = ('<a href="https://utair.tvil.ru/?utm_source=bronze">' + BRONZE + '</a>'
                   '<a href="https://utair.tvil.ru/?utm_source=gold">' + GOLD + '</a>')
        row = self.parse(anchors)[0]
        matched = BeautifulSoup(panel(anchors), 'html.parser').select(row['locator'])
        self.assertEqual([a.get_text() for a in matched], [BRONZE, GOLD])

    def test_query_specific_claims_keep_one_stable_partner_identity(self):
        bronze_url = 'https://utair.tvil.ru/?tariff=bronze'
        gold_url = 'https://utair.tvil.ru/?tariff=gold'
        first = '<a href="' + bronze_url + '">' + BRONZE + '</a>'
        anchors = first + '<a href="' + gold_url + '">' + GOLD + '</a>'
        try:
            rows = self.parse(anchors)
        except ValueError as exc:
            self.fail('Query variants lost the shared partner identity: ' + str(exc))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['native_id'], 'utair.tvil.ru/')
        self.assertEqual(row['id'], self.parse(first)[0]['id'])
        self.assertEqual(row['details']['partner_url'], bronze_url)
        self.assertEqual(row['details']['partner_urls'], [bronze_url, gold_url])
        self.assertEqual([(c['url'], c['claim']) for c in row['details']['published_claims']],
                         [(bronze_url, BRONZE), (gold_url, GOLD)])
        self.assertEqual(row['conditions_text'], BRONZE + '\n' + GOLD)
        self.assertEqual([(r['tiers'], r['value']) for r in row['details']['tier_rates']],
                         [(['Bronze'], '5'), (['Gold'], '10')])
        source = BeautifulSoup(panel(anchors), 'html.parser')
        for claim in row['details']['published_claims']:
            self.assertEqual(source.select_one(claim['locator']).get_text(), claim['claim'])

    def test_inline_markup_keeps_literal_rate_and_promo_code(self):
        rows = self.parse('<a href="https://utair.tvil.ru/">'
                          '1<span>0</span>% милями для уровня Gold. '
                          'Промокод MI<b>LES</b>2027.</a>')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['benefit_text'],
                         '10% милями для уровня Gold. Промокод MILES2027.')
        self.assertEqual([r['value'] for r in rows[0]['rates']], ['10'])
        self.assertEqual(rows[0]['promo_codes'], ['MILES2027'])

    def test_source_entities_are_decoded_once(self):
        row = self.parse('<a href="https://utair.tvil.ru/">5% милями; '
                         'текст &lt;b&gt;VIP&lt;/b&gt;; метка &amp;lt;tag&amp;gt;.</a>')[0]
        self.assertEqual(row['benefit_text'],
                         '5% милями; текст <b>VIP</b>; метка &lt;tag&gt;.')

    def test_explicit_line_break_keeps_each_tier_with_its_rate(self):
        row = self.parse('<a href="https://utair.tvil.ru/">' + BRONZE + '<br>' + GOLD + '</a>')[0]
        self.assertEqual([(r['tiers'], r['value']) for r in row['details']['tier_rates']],
                         [(['Bronze'], '5'), (['Gold'], '10')])

    def test_duplicate_markup_does_not_repeat_identical_conditions(self):
        anchor = '<a href="https://utair.tvil.ru/">' + BRONZE + '</a>'
        row = self.parse(anchor + anchor)[0]
        self.assertEqual(row['conditions_text'], BRONZE)
        self.assertEqual([r['value'] for r in row['rates']], ['5'])
        self.assertEqual(len(row['details']['tier_rates']), 1)

    def test_resolving_relative_links_keeps_destination_validation(self):
        for href in ('//user:pass@utair.tvil.ru/', 'javascript:alert(1)', 'mailto:help@example.com'):
            with self.subTest(href=href), self.assertRaises(ValueError):
                self.parse('<a href="' + href + '">' + BRONZE + '</a>')


if __name__ == '__main__':
    unittest.main()
