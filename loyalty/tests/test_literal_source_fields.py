"""Owned-source validators must compare decoded text without parsing it again."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
import aeroflot_import_catalog as aero
import coral_catalog as coral
import hse_alumni as hse
from free_access_probe import sanitized_page
from normalized import content_hash, validate_offer
from test_aeroflot_import import category_data, json_observation, partner, NOW as AERO_NOW
from test_coral_catalog import product, promo, root as coral_index, URL as CORAL_URL, NOW as CORAL_NOW
from test_ekp_api import raw as ekp_source, record as ekp_record
from test_hse_alumni import card, page, section, NOW as HSE_NOW


MARKUP = 'Укажите &lt;VIP&gt; и &amp;lt;tag&amp;gt;; знак &amp;amp;.'
VISIBLE = 'Укажите <VIP> и &lt;tag&gt;; знак &amp;.'


class LiteralSourceFieldTests(unittest.TestCase):
    def assert_literal_record(self, row):
        self.assertIn(VISIBLE, row['conditions_text'])
        stored = json.loads(json.dumps(row, ensure_ascii=False))
        validate_offer(stored)
        changed = copy.deepcopy(stored)
        changed['conditions_text'] = changed['conditions_text'].replace('<VIP>', '<ALTERED>')
        changed['content_sha256'] = content_hash(changed)
        with self.assertRaises(ValueError):
            validate_offer(changed)

    def test_hse_literal_terms_survive_creation_and_stored_validation(self):
        raw = page(card('a'), section('a', '<p>Скидка 10%.</p><p>' + MARKUP + '</p>'))
        row, = hse.parse_catalog(raw, HSE_NOW)

        self.assert_literal_record(row)
        self.assertIn(VISIBLE, row['redemption_text'])

    def test_ekp_literal_terms_survive_creation_and_stored_validation(self):
        source = ekp_source()
        source['loyaltyDescription'] = '<p>Скидка 10%.</p><p>' + MARKUP + '</p>'
        row = ekp_record(source)

        self.assert_literal_record(row)
        self.assertIn(VISIBLE, row['benefit_text'])

    def test_aeroflot_projection_is_not_decoded_again_when_fields_are_joined(self):
        source = partner()
        source['description'] = '<p>' + MARKUP + '</p>'
        source['shortDescription'] = 'Скидка 10%. ' + MARKUP
        preview = aero.catalog(json_observation(category_data()))[71]
        row = aero.detail(json_observation(source, 'detail'), preview, AERO_NOW)

        self.assert_literal_record(row)
        self.assertEqual(row['benefit_text'], 'Скидка 10%. ' + VISIBLE)

    def test_aeroflot_decoded_category_is_compared_as_plain_text(self):
        categories = category_data()
        categories[0]['title'] = 'Категория &lt;VIP&gt; &amp;amp;'
        preview = aero.catalog(json_observation(categories))[71]
        row = aero.detail(json_observation(partner(), 'detail'), preview, AERO_NOW)

        self.assertEqual(row['category'], 'Категория <VIP> &amp;')
        validate_offer(json.loads(json.dumps(row, ensure_ascii=False)))

    def test_aeroflot_inline_tokens_survive_source_projection(self):
        source = partner()
        source['shortDescription'] = 'Скидка 1<span>,</span>5% по промокоду SUM<span>MER</span>26.'
        source['earnText'] = '<a href="https://partner.example/rules">Part<span>ner</span> &lt;VIP&gt;</a>'
        preview = aero.catalog(json_observation(category_data()))[71]
        row = aero.detail(json_observation(source, 'detail'), preview, AERO_NOW)

        self.assertEqual(row['promo_codes'], ['SUMMER26'])
        self.assertEqual([r['value'] for r in row['rates']], ['1.5'])
        links = row['details']['public_partner']['outgoing_links']
        self.assertEqual(next(link['label'] for link in links if link['field'] == 'earnText'), 'Partner <VIP>')
        validate_offer(json.loads(json.dumps(row, ensure_ascii=False)))

    def test_ekp_inline_tokens_survive_sanitized_api_fields(self):
        source = ekp_source()
        source['loyaltyDescription'] = '<p>Скидка 1<span>,</span>5% по промокоду SUM<span>MER</span>26.</p>'
        row = ekp_record(source)

        self.assertEqual(row['promo_codes'], ['SUMMER26'])
        self.assertEqual([r['value'] for r in row['rates']], ['1.5'])
        validate_offer(json.loads(json.dumps(row, ensure_ascii=False)))

    def test_hse_inline_name_keeps_anchor_and_heading_ownership(self):
        for detail in (
            section('a', '<p>Скидка 10%.</p>'),
            '<div class="builder-section"><h2>Pa<strong>rtner</strong></h2><p>Скидка 10%.</p></div>',
        ):
            with self.subTest(detail=detail):
                row, = hse.parse_catalog(page(card('a', name='Part<span>ner</span>'), detail), HSE_NOW)
                self.assertEqual(row['partner_name'], 'Partner')
                self.assertEqual(row['record_kind'], 'partner_offer')
                self.assertEqual([r['value'] for r in row['rates']], ['10'])
                validate_offer(json.loads(json.dumps(row, ensure_ascii=False)))

    def test_coral_inline_headline_decimal_remains_fractional_rate(self):
        clean, _ = sanitized_page(product('1<span>,</span>5'), CORAL_URL)
        row = coral.detail(clean, 'coral', {'url': CORAL_URL, 'category': 'Подарки',
                                          'parent_url': coral.CLUB + 'gifts/'},
                           CORAL_NOW, {'method': 'fixture'})

        self.assertEqual(row['benefit_text'], 'Скидка 1,5% в Новый сервис')
        self.assertEqual([r['value'] for r in row['rates']], ['1.5'])
        validate_offer(json.loads(json.dumps(row, ensure_ascii=False)))

    def test_coral_promo_listing_and_detail_keep_same_inline_identity(self):
        listing = coral_index('coral_promo').replace('нового', 'но<span>во</span>го')
        entry, = coral.listing(listing, 'coral_promo')
        clean, _ = sanitized_page(promo().replace('нового', 'но<span>во</span>го'), entry['url'])
        row = coral.detail(clean, 'coral_promo', entry, CORAL_NOW, {'method': 'fixture'})

        self.assertEqual(row['title'], 'Бонусы нового путешествия')
        self.assertEqual(entry['title'], row['title'])
        validate_offer(json.loads(json.dumps(row, ensure_ascii=False)))

    def test_coral_owned_text_does_not_reparse_escaped_source_markup(self):
        raw = product().replace('<p>Условия действуют', '<p>' + MARKUP + '</p><p>Условия действуют')
        clean, _ = sanitized_page(raw, CORAL_URL)
        row = coral.detail(clean, 'coral', {'url': CORAL_URL, 'category': 'Подарки',
                                          'parent_url': coral.CLUB + 'gifts/'},
                           CORAL_NOW, {'method': 'fixture'})

        self.assert_literal_record(row)


if __name__ == '__main__':
    unittest.main()
