"""Structural line breaks cannot change source identity or partner ownership."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters import extract
import coral_catalog as coral
from hse_alumni import parse_catalog, ROOT as HSE_ROOT
from normalized import validate_offer
from test_coral_catalog import doc, root
from test_hse_unanchored import fixture, TITLE
from test_utair_partner_discovery import panel, URL as UTAIR_URL

NOW = '2026-11-06T00:00:00+00:00'


class SourceHtmlBoundaryContractsTests(unittest.TestCase):
    def test_hse_wrapped_heading_still_separates_two_partners(self):
        raw = fixture().replace(
            '<h2>' + TITLE + '</h2>',
            '<h2>Морда<br>довольна. Студия печати</h2>',
        )
        before, printed, after = parse_catalog(raw, NOW)
        self.assertEqual(before['promo_codes'], ['DESIGN_ONLY'])
        self.assertEqual([r['value'] for r in before['rates']], ['7'])
        self.assertNotIn('PRINT_ONLY', before['conditions_text'])
        self.assertEqual(printed['record_kind'], 'partner_offer')
        self.assertEqual(printed['promo_codes'], ['PRINT_ONLY'])
        self.assertEqual([r['value'] for r in printed['rates']], ['23'])
        self.assertNotIn('DESIGN_ONLY', printed['conditions_text'])
        self.assertEqual(printed['source_url'], HSE_ROOT)
        self.assertEqual(printed['details']['public_catalog_block']['detail_heading'],
                         'Морда\nдовольна. Студия печати')
        self.assertIn('Морда\nдовольна. Студия печати', printed['conditions_text'])
        self.assertEqual(after['promo_codes'], ['OTHER_ONLY'])
        for row in (before, printed, after):
            validate_offer(json.loads(json.dumps(row, ensure_ascii=False)))

    def test_coral_root_heading_break_keeps_the_same_categories(self):
        raw = root().replace('<h1>Клуб привилегий</h1>', '<h1>Клуб<br>привилегий</h1>')
        try:
            entries = coral.listing(raw, 'coral')
        except ValueError as exc:
            self.fail(f'Valid Coral catalogue heading was rejected: {exc}')
        self.assertEqual(entries, [
            {'url': coral.CLUB + 'one/', 'title': 'Первая'},
            {'url': coral.CLUB + 'two/', 'title': 'Вторая'},
        ])

    def test_coral_category_heading_break_keeps_the_card_owner(self):
        entries = coral.listing(root().replace('>Первая<', '>Первая категория<'), 'coral')
        entry = entries[0]
        raw = doc(
            '<section><h1>Первая<br>категория</h1><div id="categoryProductsList">'
            '<div class="product-box referal"><a href="' + coral.CLUB + 'one/future/">Offer</a>'
            '</div></div></section>', entry['url'],
        )
        try:
            cards, excluded = coral.category_cards(raw, entry)
        except ValueError as exc:
            self.fail(f'Valid Coral category heading was rejected: {exc}')
        self.assertEqual(cards, [{
            'url': coral.CLUB + 'one/future/',
            'category': 'Первая категория', 'parent_url': coral.CLUB + 'one/',
        }])
        self.assertEqual(excluded, 0)
        self.assertEqual(entry['title'], 'Первая категория')
        with self.assertRaises(ValueError):
            coral.category_cards(raw.replace('Первая<br>категория', 'Другая<br>категория'), entry)

    def test_coral_duplicate_category_labels_ignore_only_structural_whitespace(self):
        first = '<div class="category-box-menu"><h5><a href="' + coral.CLUB + 'one/">Первая категория</a></h5></div>'
        second = '<div class="category-box-menu"><h5><a href="' + coral.CLUB + 'one/">Первая<br>категория</a></h5></div>'
        raw = doc('<h1>Клуб привилегий</h1>' + first + second, coral.CLUB)
        entries = coral.listing(raw, 'coral')
        self.assertEqual(entries, [{
            'url': coral.CLUB + 'one/', 'title': 'Первая\nкатегория',
        }])
        with self.assertRaises(ValueError):
            coral.listing(raw.replace('Первая<br>категория', 'Другая<br>категория'), 'coral')

    def utair(self, anchors):
        rows = extract('utair_media', panel(anchors), UTAIR_URL, NOW)
        self.assertEqual(len(rows), 1)
        validate_offer(json.loads(json.dumps(rows[0], ensure_ascii=False)))
        return rows[0]

    def test_utair_wrapped_tier_keeps_its_literal_rate_evidence(self):
        row = self.utair(
            '<a href="https://utair.tvil.ru/">'
            'ТВИЛ.РУ — 5% милями для уровня<br>Bronze</a>'
        )
        self.assertEqual([r['value'] for r in row['rates']], ['5'])
        self.assertEqual(row['details']['tier_rates'], [{
            'tiers': ['Bronze'], 'value': '5', 'unit': 'percent_miles',
            'evidence': 'ТВИЛ.РУ — 5% милями для уровня\nBronze',
        }])
        self.assertEqual(row['conditions_text'], 'ТВИЛ.РУ — 5% милями для уровня\nBronze')

    def test_utair_wrapped_first_tier_does_not_consume_the_next_tier(self):
        row = self.utair(
            '<a href="https://utair.tvil.ru/">'
            'ТВИЛ.РУ — 5% милями для уровня<br>Bronze<br>'
            'ТВИЛ.РУ — 10% милями для уровня Gold</a>'
        )
        self.assertEqual([r['value'] for r in row['rates']], ['5', '10'])
        self.assertEqual(row['details']['tier_rates'], [
            {'tiers': ['Bronze'], 'value': '5', 'unit': 'percent_miles',
             'evidence': 'ТВИЛ.РУ — 5% милями для уровня\nBronze'},
            {'tiers': ['Gold'], 'value': '10', 'unit': 'percent_miles',
             'evidence': 'ТВИЛ.РУ — 10% милями для уровня Gold'},
        ])

    def test_utair_incomplete_claim_cannot_take_another_links_tier(self):
        row = self.utair(
            '<a href="https://utair.tvil.ru/">ТВИЛ.РУ — 5% милями для уровня</a>'
            '<a href="https://utair.tvil.ru/">ТВИЛ.РУ — 10% милями для уровня Bronze</a>'
        )
        self.assertEqual([r['value'] for r in row['rates']], ['5', '10'])
        self.assertEqual(row['details']['tier_rates'], [{
            'tiers': ['Bronze'], 'value': '10', 'unit': 'percent_miles',
            'evidence': 'ТВИЛ.РУ — 10% милями для уровня Bronze',
        }])



    def test_utair_scope_words_and_tier_list_can_wrap(self):
        literal = 'ТВИЛ.РУ — 5% милями для\nуровней\nBronze,\nSilver и\nGold'
        row = self.utair(
            '<a href="https://utair.tvil.ru/">'
            'ТВИЛ.РУ — 5% милями для<br>уровней<br>Bronze,<br>Silver и<br>Gold</a>'
        )
        self.assertEqual(row['details']['tier_rates'], [{
            'tiers': ['Bronze', 'Silver', 'Gold'], 'value': '5',
            'unit': 'percent_miles', 'evidence': literal,
        }])
        self.assertEqual(row['conditions_text'], literal)

    def test_utair_next_offer_label_is_not_a_tier(self):
        row = self.utair(
            '<a href="https://utair.tvil.ru/">'
            'ТВИЛ.РУ — 5% милями для уровня<br>'
            'Otello — 10% милями для уровня Gold</a>'
        )
        self.assertEqual([r['value'] for r in row['rates']], ['5', '10'])
        self.assertEqual(row['details']['tier_rates'], [{
            'tiers': ['Gold'], 'value': '10', 'unit': 'percent_miles',
            'evidence': 'Otello — 10% милями для уровня Gold',
        }])


if __name__ == '__main__':
    unittest.main()
