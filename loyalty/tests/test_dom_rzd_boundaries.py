"""RZD and GreatList source fields preserve visible DOM text without re-parsing."""
import sys
import unittest
from pathlib import Path
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parents[1]))
import rzd_external as external
import rzd_catalogue_cards as previews
import greatlist_alfa as greatlist
import test_rzd_external as ef
import test_rzd_catalogue_cards as pf
import test_greatlist_alfa as gf
from test_dom_card_boundaries import ENTITY_HTML, ENTITY_TEXT, project


class RzdExternalDomBoundaries(unittest.TestCase):
    def test_wrapped_owned_tour_claim_keeps_discount_to_common(self):
        original = ('<p>Участникам РЖД Бонус скидка 13%. '
                    'Номер карты укажите при заявке.</p>')
        for tag in ('p', 'li'):
            for wrapped in ('скидка<br>13%', 'скидка 13<br>%'):
                with self.subTest(tag=tag, wrapped=wrapped):
                    claim = ('Участникам РЖД Бонус ' + wrapped
                             + '. Номер карты укажите при заявке.')
                    raw = ef.tour().replace(original, '<' + tag + '>' + claim + '</' + tag + '>')
                    row = external.tour_record(raw, ef.URL, external.TOUR, ef.NOW)
                    self.assertEqual(row['benefit_text'], claim.replace('<br>', ' '))
                    self.assertIn(claim.replace('<br>', '\n'), row['conditions_text'])
                    self.assertEqual([(r['kind'], r['value']) for r in row['rates']],
                                     [('discount', '13')])
                    self.assertEqual([(b['kind'], b['value']) for b in project(row)['benefits']],
                                     [('discount', '13')])

    def test_separate_tour_paragraphs_do_not_supply_rate_context(self):
        raw = ef.tour().replace(
            '<p>Участникам РЖД Бонус скидка 13%. Номер карты укажите при заявке.</p>',
            '<li><p>Участникам РЖД Бонус скидка</p>'
            '<p>13%. Номер карты укажите при заявке.</p></li>')
        row = external.tour_record(raw, ef.URL, external.TOUR, ef.NOW)
        self.assertIn('Участникам РЖД Бонус скидка\n13%', row['benefit_text'])
        self.assertEqual(row['rates'], [])
        self.assertEqual(project(row)['benefits'], [])

    def test_inline_tour_rate_and_title_survive_source_and_common_projection(self):
        raw = ef.tour('17<b>,</b>5', 'Новый ту<span>р</span> ' + ENTITY_HTML)
        row = external.tour_record(raw, ef.URL, external.TOUR, ef.NOW)
        claim = 'Участникам РЖД Бонус скидка 17,5%. Номер карты укажите при заявке.'
        self.assertEqual(row['title'], 'Новый тур ' + ENTITY_TEXT)
        self.assertEqual(row['benefit_text'], claim)
        self.assertEqual(row['details']['public_tour']['loyalty_text'], claim)
        self.assertEqual([(r['kind'], r['value']) for r in row['rates']], [('discount', '17.5')])
        common = project(row)
        self.assertEqual([(b['kind'], b['value']) for b in common['benefits']], [('discount', '17.5')])
        self.assertEqual(common['raw']['title'], 'Новый тур ' + ENTITY_TEXT)
        self.assertNotIn('99%', common['raw']['conditions'])

    def test_table_cell_and_owned_pricing_text_agree_on_literal_number(self):
        raw = ef.tour().replace('80 000', '12<span>34</span> &lt;VIP&gt;')
        row = external.tour_record(raw, ef.URL, external.TOUR, ef.NOW)
        self.assertEqual(row['details']['public_tour']['pricing_tables'][0][1],
                         ['Взрослый', '1234 <VIP>'])
        self.assertIn('Взрослый 1234 <VIP>', row['conditions_text'])
        self.assertEqual(project(row)['raw']['details']['public_tour']['pricing_tables'][0][1],
                         ['Взрослый', '1234 <VIP>'])

    def test_bank_pdf_discovery_matches_inline_and_wrapped_label(self):
        for label in ('Правила выплаты воз<span>наг</span>раждения',
                      'Правила<br>выплаты вознаграждения'):
            with self.subTest(label=label):
                raw = ef.bank().replace('Правила выплаты вознаграждения', label)
                fields = external.bank_fields(raw)
                expected = ('Правила\nвыплаты вознаграждения' if '<br>' in label
                            else 'Правила выплаты вознаграждения')
                self.assertEqual(fields['documents'], [{'url': ef.PDF, 'label': expected}])

    def test_bank_reference_keeps_entities_and_pre_lines_as_evidence_only(self):
        raw = ef.bank().replace('</p>', '</p><pre>' + ENTITY_HTML + '\r\nПервая\rВторая</pre>', 1)
        row = external.bank_record(raw, ef.NOW)
        self.assertIn(ENTITY_TEXT + '\nПервая\nВторая', row['conditions_text'])
        common = project(row)
        self.assertEqual(common['raw']['conditions'], row['conditions_text'])
        self.assertEqual(common['benefits'], [])
        self.assertEqual(common['codes'], [])


class RzdCatalogueDomBoundaries(unittest.TestCase):
    def record(self, raw):
        obs = pf.observation(pf.m.ROOT, 'catalog_cards', [previews.sanitize(raw)])
        entry, = previews.previews(obs).values()
        return previews.make_preview(entry, pf.NOW, 'rzd_import_error_cell')

    def test_inline_summary_and_code_keep_exact_evidence_only_preview(self):
        raw = pf.html(rate='17<b>,</b>5', body='Промокод SUM<span>MER</span>26. ' + ENTITY_HTML)
        try:
            row = self.record(raw)
        except ValueError as exc:
            self.fail('Literal catalogue evidence failed record binding: ' + str(exc))
        expected = 'Скидка 17,5% в отеле Пример\n\nПромокод SUMMER26. ' + ENTITY_TEXT
        self.assertEqual(row['conditions_text'], expected)
        self.assertEqual(row['title'], 'Скидка 17,5% в отеле Пример')
        self.assertEqual(row['rates'], [])
        common = project(row)
        self.assertEqual(common['raw']['conditions'], expected)
        self.assertEqual(common['benefits'], [])
        self.assertEqual(common['codes'], [])
        self.assertEqual(common['costs'], [])
        self.assertEqual(common['quality']['level'], 'evidence_only')

    def test_preview_preserves_br_and_pre_with_all_source_newlines(self):
        for newline in ('\r', '\r\n', '\n'):
            with self.subTest(newline=repr(newline)):
                row = self.record(pf.html(body='Начало<br>Ограничения<pre>Первая'
                                          + newline + 'Вторая</pre>'))
                expected = ('Скидка 17% в отеле Пример\n\nНачало\nОграничения'
                            '\nПервая\nВторая')
                self.assertEqual(row['conditions_text'], expected)
                self.assertEqual(project(row)['raw']['conditions'], expected)


class GreatListDomBoundaries(unittest.TestCase):
    def test_inline_catalogue_and_detail_names_remain_the_same_restaurant(self):
        name = 'Fix<span>tu</span>re &lt;VIP&gt; &amp;lt;tag&amp;gt;'
        listing = gf.listing().replace('>Fixture<', '>' + name + '<')
        card, = greatlist.catalogue(listing, greatlist.ROOT, gf.CITY)
        self.assertEqual(card['name'], 'Fixture <VIP> &lt;tag&gt;')
        raw = gf.detail().replace('Ресторан Fixture', 'Ресторан Fixture &lt;VIP&gt; &amp;lt;tag&amp;gt;')
        try:
            row = greatlist.parse_detail(raw, card, gf.NOW)
        except ValueError as exc:
            self.fail('Equivalent catalogue/detail names did not match: ' + str(exc))
        self.assertEqual(row['partner_name'], 'Fixture <VIP> &lt;tag&gt;')
        self.assertEqual(row['native_id'], 'spb:123')
        self.assertEqual(project(row)['partner']['name'], 'Fixture <VIP> &lt;tag&gt;')

    def test_inline_cashback_and_literal_address_survive_common_view(self):
        raw = gf.detail().replace('12%', '1<span>2</span>%').replace(
            'Улица Примерная, 1', 'Улица Примерная, 1. ' + ENTITY_HTML)
        row = greatlist.parse_detail(raw, gf.CARD, gf.NOW)
        self.assertEqual(row['details']['greatlist_evidence']['bullets'],
                         ['кэшбэк до 12%', 'приоритетная бронь через консьерж-сервис'])
        self.assertEqual(row['details']['greatlist_evidence']['address'],
                         'Улица Примерная, 1. ' + ENTITY_TEXT)
        self.assertEqual([(r['kind'], r['value']) for r in row['rates']], [('cashback', '12')])
        common = project(row)
        self.assertEqual({(b['kind'], b['value']) for b in common['benefits']}, {('cashback', '12')})
        self.assertIn(ENTITY_TEXT, common['raw']['conditions'])
        self.assertNotIn('gift', {b['kind'] for b in common['benefits']})

    def test_wrapped_owned_bullet_keeps_cashback_to_common(self):
        row = greatlist.parse_detail(gf.detail().replace('кэшбэк до', 'кэшбэк<br>до'), gf.CARD, gf.NOW)
        self.assertEqual(row['details']['greatlist_evidence']['bullets'][0], 'кэшбэк до 12%')
        self.assertEqual([(r['kind'], r['value']) for r in row['rates']], [('cashback', '12')])
        self.assertEqual({(b['kind'], b['value']) for b in project(row)['benefits']}, {('cashback', '12')})

    def test_separate_paragraphs_inside_bullet_do_not_supply_rate_context(self):
        raw = gf.detail().replace('кэшбэк до 12%', '<p>кэшбэк</p><p>до 12%</p>')
        row = greatlist.parse_detail(raw, gf.CARD, gf.NOW)
        self.assertEqual(row['details']['greatlist_evidence']['bullets'][0], 'кэшбэк\nдо 12%')
        self.assertEqual(row['rates'], [])
        self.assertEqual(project(row)['benefits'], [])

    def test_wrapped_list_owner_and_heading_keep_list_boundaries(self):
        raw = gf.detail().replace('Ресторан Fixture', 'Ресторан<br>Fixture').replace(
            'Привилегии для клиентов Alfa Only:', 'Привилегии для клиентов<br>Alfa Only:')
        try:
            row = greatlist.parse_detail(raw, gf.CARD, gf.NOW)
        except ValueError as exc:
            self.fail('A previously supported wrapped heading/owner was rejected: ' + str(exc))
        self.assertTrue(row['details']['greatlist_evidence']['block_text'].startswith(
            'Привилегии для клиентов Alfa Only:\nкэшбэк до 12%'))
        self.assertEqual(row['native_id'], 'spb:123')

    def test_wrapped_paragraph_owner_still_excludes_menu_from_benefit(self):
        dom = BeautifulSoup(gf.detail(False), 'html.parser')
        block = dom.select_one('.alfa-section-text')
        block.clear()
        block.append(BeautifulSoup(
            'Клиентам Alfa<br>Only доступна приоритетная бронь через консьерж-сервис.'
            '<p>В меню — фирменный коктейль</p>', 'html.parser'))
        try:
            row = greatlist.parse_detail(str(dom), gf.CARD, gf.NOW)
        except ValueError as exc:
            self.fail('A previously supported wrapped paragraph was rejected: ' + str(exc))
        self.assertEqual(row['benefit_text'],
                         'Клиентам Alfa Only доступна приоритетная бронь через консьерж-сервис.')
        self.assertNotIn('В меню', row['benefit_text'])
        self.assertIn('В меню', row['conditions_text'])
        self.assertEqual(row['rates'], [])


if __name__ == '__main__':
    unittest.main()
