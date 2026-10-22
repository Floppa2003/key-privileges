"""Regressions reduced from public page structures observed on 2026-10-22.

These are layout/ownership tests, not snapshots of the original failed HTTP
responses. No merchant names or rates form an acceptance list in production.
"""
import copy
import sys
import unittest
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0, str(Path(__file__).parents[1]))
import hse_alumni as hse
import known_rules
import mantera_hotel as hotel
import partner_pages
from normalized import validate_offer
from test_hse_alumni import card, page, section
import test_known_rules

NOW = '2026-10-22T12:16:49+00:00'

class Run132Recovery(unittest.TestCase):
    def collision_page(self, include_second=True):
        return page(card('gift', 'Общая марка Магазин') + card('print', 'Общая марка'),
                    section('gift', '<h2>Общая марка</h2><p>Скидка 20%, промокод SHOP_ONLY</p>') +
                    ('<div class="builder-section"><h2>Общая марка. Студия</h2>'
                     '<p>Скидка 15%, промокод PRINT_ONLY</p></div>' if include_second else ''))

    def test_hse_explicit_anchor_wins_over_shorter_catalogue_name(self):
        rows = hse.parse_catalog(self.collision_page(), NOW)
        self.assertEqual([r['promo_codes'] for r in rows], [['SHOP_ONLY'], ['PRINT_ONLY']])
        for row in rows: validate_offer(row)

    def test_hse_absent_section_cannot_steal_an_anchored_section(self):
        rows = hse.parse_catalog(self.collision_page(False), NOW)
        self.assertEqual(rows[0]['promo_codes'], ['SHOP_ONLY'])
        self.assertEqual(rows[1]['record_kind'], 'source_observation')
        self.assertEqual(rows[1]['promo_codes'], [])
        self.assertEqual(rows[1]['details']['public_catalog_block']['body'], '')

    def test_hse_unlisted_anchor_also_owns_its_following_text(self):
        raw=page(card('missing','Марка'),section('not_in_catalogue','<h2>Марка</h2><p>Промокод FOREIGN_ONLY, скидка 50%</p>'))
        rows=hse.parse_catalog(raw,NOW)
        self.assertEqual(rows[0]['record_kind'],'source_observation')
        self.assertEqual(rows[0]['promo_codes'],[])

    def test_hse_ambiguous_unanchored_card_does_not_discard_other_cards(self):
        raw = page(card('a', 'Марка') + card('ok', 'Независимая'),
                   '<div class="builder-section"><h2>Марка</h2><p>Скидка 10%</p></div>'
                   '<div class="builder-section"><h2>Марка. Студия</h2><p>Скидка 20%</p></div>' +
                   section('ok', '<p>Скидка 7%, промокод OK_ONLY</p>'))
        rows = hse.parse_catalog(raw, NOW)
        self.assertEqual(rows[0]['record_kind'], 'source_observation')
        self.assertEqual(rows[0]['details']['public_catalog_block']['detail_state'], 'ambiguous_heading')
        self.assertEqual(rows[1]['promo_codes'], ['OK_ONLY'])
        for row in rows: validate_offer(row)

    def test_smartavia_label_and_value_in_sibling_blocks(self):
        raw = test_known_rules.SmartaviaTests().fixture().replace('Тариф 1+0.',
              '</p><div class="sub-title">Тариф</div><div class="sm-title-extra"><strong>Семейный</strong></div><p>')
        # The original fixture does not necessarily include a period after the name.
        if 'sm-title-extra' not in raw:
            raw = test_known_rules.SmartaviaTests().fixture().replace('Тариф 1+0',
              '</p><div class="sub-title">Тариф</div><div class="sm-title-extra"><strong>Семейный</strong></div><p>')
        rows = known_rules.parse_known_rule('smartavia_rules', raw,
                  known_rules.CONFIG['smartavia_rules']['url'], NOW)
        plan = rows[0]['details']['subscription_plan']
        self.assertEqual(plan['label'], 'Семейный')
        self.assertIsNone(plan['additional_travelers'])

    def test_mantera_customer_status_paragraph_is_not_a_conflict(self):
        raw = (Path(__file__).parent/'fixtures_live/affordable/mantera-congress.html').read_text()
        raw = raw.replace('</body>', '<p>Чем чаще вы отдыхаете с Mantera Resort &amp; Congress, '
                          'тем выше ваш статус участника.</p></body>')
        row = hotel.parse(raw, NOW)
        self.assertEqual(row['partner_name'], hotel.NAME)
        validate_offer(row)

    def test_mantera_multiple_consistent_participation_statements(self):
        raw = (Path(__file__).parent/'fixtures_live/affordable/mantera-congress.html').read_text()
        raw = raw.replace('</body>', '<p>Отель Mantera Resort &amp; Congress участвует '
                          'в программе лояльности «Мантера Моменты».</p></body>')
        validate_offer(hotel.parse(raw, NOW))

    def test_mantera_negative_participation_cannot_confirm_membership(self):
        raw = (Path(__file__).parent/'fixtures_live/affordable/mantera-congress.html').read_text()
        dom = BeautifulSoup(raw, 'html.parser')
        for p in dom.select('p'):
            if hotel.NAME in p.get_text(): p.string = 'Отель '+hotel.NAME+' не участвует в программе лояльности.'
        with self.assertRaises(ValueError): hotel.parse(str(dom), NOW)

    def test_parkfly_new_article_container_excludes_other_promotions(self):
        raw = ('<article class="pf-post"><h1>Начисляем мили «Аэрофлот Бонус»</h1>'
               '<div class="pf-post__text"><p>1 миля за каждые 40 рублей.</p></div></article>'
               '<dialog><p>Скидка 99%, промокод FOREIGN_ONLY</p></dialog>')
        row, = partner_pages.extract_partner_page('af_parkfly', BeautifulSoup(raw, 'html.parser'),
                 partner_pages.CONFIG['af_parkfly']['url'], NOW)
        self.assertNotIn('FOREIGN_ONLY', row['conditions_text'])
        self.assertNotIn('99%', row['benefit_text'])
        validate_offer(row)

    def test_parkfly_multiple_articles_are_not_silently_joined(self):
        raw = '<article class="pf-post"><p>Аэрофлот Бонус: 1 миля за 40 рублей.</p></article>'
        with self.assertRaises(ValueError):
            partner_pages.extract_partner_page('af_parkfly', BeautifulSoup(raw*2, 'html.parser'),
                 partner_pages.CONFIG['af_parkfly']['url'], NOW)

if __name__ == '__main__': unittest.main()
