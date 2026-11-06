"""Remaining DOM label boundaries must not change source identity or inventory."""
import copy
import hashlib
import html
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from bs4 import BeautifulSoup
from adapters import extract
from announcements import parse_feed
from expansion_common import sha
from flystation_source import inventory, source_fields
from konsierge_source import dom_capture
from mir_ui import dom_snapshot
from recovered_sources import parse_bank_page
from tsum_alfa import SOURCE_ID as TSUM, URL as TSUM_URL, QUESTIONS, derived, extract_tsum
from unified_inputs import inputs_from_tables
from unified_normalization import make_input, normalize_record
import test_konsierge_catalog as konsierge
import test_more_announcements as announcement
import test_recovered_sources as recovered
import test_sacvoyage_loyalty as sacvoyage
import test_flystation as flystation
from test_owned_dom_literal_boundaries import MARKUP, LITERAL, publication

FIX = Path(__file__).parent / 'fixtures_live'


class SacvoyageDomBoundaryTests(unittest.TestCase):
    def rows(self, raw):
        return extract(sacvoyage.SID, raw, sacvoyage.URL, sacvoyage.NOW)

    def test_inline_bold_heading_cannot_lose_or_merge_audiences(self):
        raw = sacvoyage.page().replace('Программа лояльности', 'Про<span>грамма</span> лояльности')
        rows = self.rows(raw)
        self.assertEqual([row['native_id'] for row in rows], ['member', 'referred_guest'])
        self.assertEqual([[rate['value'] for rate in row['rates']] for row in rows], [['7'], ['12']])
        self.assertNotIn('корпоративным', rows[1]['conditions_text'])
        self.assertNotIn('подарок', rows[0]['conditions_text'])
        for row in rows:
            publication(row)

    def test_formatted_heading_keeps_legacy_identity_and_rejects_duplicate(self):
        raw = sacvoyage.page().replace('Программа лояльности', 'Программа<br>лояльности')
        rows = self.rows(raw)
        self.assertEqual(rows[0]['native_id'], 'member')
        self.assertEqual(rows[0]['title'], 'Программа лояльности')
        duplicated = raw.replace('Реферальная программа', 'Программа лояльности')
        with self.assertRaisesRegex(ValueError, 'sacvoyage_duplicate_section'):
            self.rows(duplicated)

    def test_heading_and_bare_text_nodes_decode_once_and_keep_paragraphs(self):
        raw = sacvoyage.page().replace('>Скидки</h2>', '>Скидки ' + MARKUP + '</h2>').replace(
            '</div></main>', ' Только при предъявлении ' + MARKUP + '</div></main>')
        rows = self.rows(raw)
        self.assertEqual(rows[0]['details']['source_heading_context'], 'Скидки ' + LITERAL)
        self.assertIn('сайте.\nСкидка не суммируется', rows[0]['benefit_text'])
        self.assertIn('Только при предъявлении ' + LITERAL, rows[1]['conditions_text'])
        self.assertIn(LITERAL, publication(rows[1])['Условия'])

    def test_br_before_percent_survives_source_publisher_and_common(self):
        rows = self.rows(sacvoyage.page(member='7<br>'))
        inputs, _ = inputs_from_tables(sacvoyage.published_tables(rows))
        before = copy.deepcopy(inputs)
        common = [normalize_record(row, as_of='2026-11-06') for row in inputs]
        expected = [[('discount', '7')], [('discount', '12')]]
        for stage, actual in (
                ('source', [[(rate['kind'], rate['value']) for rate in row['rates']] for row in rows]),
                ('common', [sorted({(benefit['kind'], benefit['value']) for benefit in row['benefits']
                                    if benefit['unit'] == 'percent'}) for row in common])):
            with self.subTest(stage=stage):
                self.assertEqual(actual, expected)
        self.assertEqual(inputs, before)
        self.assertEqual([row['raw'] for row in common], before)

    def test_neighbouring_paragraphs_cannot_complete_percent(self):
        rows = self.rows(sacvoyage.page(member='7</p><p>'))
        self.assertIn('скидку 7\n% на бронирования', rows[0]['benefit_text'])
        self.assertEqual([row['native_id'] for row in rows], ['member', 'referred_guest'])
        inputs, _ = inputs_from_tables(sacvoyage.published_tables(rows))
        common = [normalize_record(row, as_of='2026-11-06') for row in inputs]
        expected = [[], [('discount', '12')]]
        self.assertEqual([[(rate['kind'], rate['value']) for rate in row['rates']]
                          for row in rows], expected)
        self.assertEqual([[(benefit['kind'], benefit['value']) for benefit in row['benefits']
                           if benefit['unit'] == 'percent'] for row in common], expected)


class KonsiergeDomBoundaryTests(unittest.TestCase):
    def test_capture_keeps_inline_name_rate_literal_and_block_text(self):
        raw = '<qy-benefits-page><qy-benefit-teaser><div class="BenefitTeaser-Title">G<span>MS</span><br>' + MARKUP + '</div><div class="BenefitTeaser-OfferText">Скидка 1<span>0</span>%</div></qy-benefit-teaser></qy-benefits-page>'
        stored, cards = dom_capture(raw)
        self.assertEqual(cards, [{'name': 'GMS\n' + LITERAL, 'offer': 'Скидка 10%'}])
        self.assertIn('&lt;VIP&gt;', stored)
        self.assertNotIn('<VIP>', stored)
        self.assertEqual(dom_capture(stored)[1], cards)

    def test_inline_native_dom_reconciliation_keeps_unchanged_json_contract(self):
        fixture = konsierge.KonsiergeTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        expected = fixture.bundle()
        original_pages = copy.deepcopy(fixture.report['network_pages'])
        name = fixture.items[0]['name'].strip()
        markup = html.escape(name[:1]) + '<span>' + html.escape(name[1:]) + '</span>'
        for catalogue in fixture.report['catalogues']:
            path = fixture.path / catalogue['file']
            raw = path.read_text().replace(html.escape(name), markup)
            path.write_text(raw)
            catalogue['sha256'] = hashlib.sha256(raw.encode()).hexdigest()
        actual = fixture.bundle()
        self.assertEqual([row['id'] for row in actual['records']], [row['id'] for row in expected['records']])
        self.assertEqual([row['rates'] for row in actual['records']], [row['rates'] for row in expected['records']])
        self.assertEqual(fixture.report['network_pages'], original_pages)
        for row in actual['records']:
            publication(row)


class TsumDomBoundaryTests(unittest.TestCase):
    def rows(self, raw):
        return extract_tsum(TSUM, BeautifulSoup(raw, 'html.parser'), TSUM_URL, sacvoyage.NOW, {})

    def test_inline_card_rate_and_tier_remain_one_public_reward(self):
        raw = (FIX / 'tsum-alfa.html').read_text().replace('20%', '2<span>0</span>%').replace(
            '>Black<', '>Bl<span>ack</span><')
        rows = self.rows(raw)
        row = next(row for row in rows if row['details']['tsum_tier'] == 'Black')
        self.assertEqual(row['native_id'], 'loyalty-cashback:black')
        self.assertEqual(row['record_kind'], 'partner_offer')
        self.assertEqual([rate['value'] for rate in row['rates']], ['20'])
        published = publication(row)
        source = make_input({'id': row['id'], 'origin': 'parser_offers', 'row': 2,
                             'fields': {key: {'value': value} for key, value in published.items()}})
        common = normalize_record(source, as_of='2026-11-06')
        self.assertEqual([(benefit['kind'], benefit['value']) for benefit in common['benefits']], [('earn_points', '20')])
        self.assertEqual(common['benefits'][0]['reward_unit'], 'TSUM_DLT_loyalty_credit')

    def test_faq_and_card_boundaries_remain_evidence_while_checks_ignore_whitespace(self):
        raw = (FIX / 'tsum-alfa.html').read_text().replace(
            'кешбэк на карту лояльности ЦУМа и ДЛТ', 'кешбэк<br>на карту лояльности ЦУМа и ДЛТ').replace(
            '20% вместо 10%', '20%<br>вместо 10%')
        row = next(row for row in self.rows(raw) if row['details']['tsum_tier'] == 'Black')
        self.assertEqual(row['record_kind'], 'partner_offer')
        self.assertEqual([rate['value'] for rate in row['rates']], ['20'])
        self.assertIn('кешбэк\nна карту лояльности ЦУМа и ДЛТ', row['conditions_text'])
        self.assertIn('20%\nвместо 10%', row['conditions_text'])
        self.assertEqual(row['details']['tsum_evidence']['cards']['Black'], 'Black\n20%')
        publication(row)
        with self.assertRaisesRegex(ValueError, 'tier_rate_disagreement'):
            self.rows(raw.replace('20%<br>вместо 10%', '19%<br>вместо 10%'))

    def test_old_stored_legacy_evidence_remains_valid_without_rewriting_it(self):
        faq = {question: 'Остальные опубликованные условия.' for question in QUESTIONS}
        faq[QUESTIONS[0]] = 'Кешбэк на карту лояльности ЦУМа и ДЛТ: 8% вместо 5% по карте Orange, 20% вместо 10% по карте Black.'
        faq[QUESTIONS[7]] = 'Нет, начисляется только кешбэк на карту лояльности.'
        evidence = dict(url=TSUM_URL, reward_currency='TSUM_DLT_loyalty_credit', page_sha256='a' * 64,
                        cards={'Black': 'Black 20%', 'Orange': 'Orange 8%', 'White': 'White Повышение до Orange, 8%'},
                        faq=faq, redemption='Alfa Only; виджет ЦУМ; Повышенный кешбэк в ЦУМе')
        before = copy.deepcopy(evidence)
        self.assertIn('20% по карте Black', derived(evidence, 'Black')[0])
        self.assertIn('8% по карте Orange', derived(evidence, 'Orange')[0])
        self.assertEqual(evidence, before)


class FlyStationDomBoundaryTests(unittest.TestCase):
    def test_inline_heading_keeps_current_inventory_identity_and_detail(self):
        raw = flystation.RAW.replace('Раннее бронирование', 'Раннее брони<span>рование</span>')
        entries = inventory(raw)
        self.assertEqual(len(entries), 6)
        entry = next(entry for entry in entries if entry['native'] == 'advance')
        self.assertEqual(entry['title'], 'Раннее бронирование')
        fields = source_fields(entry)
        self.assertEqual([term['value'] for term in fields['terms']], ['20', '30'])
        self.assertNotIn('День рождения', fields['conditions'])

    def test_legacy_html_recognizes_inline_digits_without_reinterpreting_evidence_schema(self):
        entry = next(entry for entry in inventory(flystation.RAW) if entry['native'] == 'advance')
        entry.pop('projection_version')
        expected = source_fields(entry)
        entry['panel_html'] = entry['panel_html'].replace('20%', '2<span>0</span>%')
        entry['panel_sha256'] = sha(entry['panel_html'])
        actual = source_fields(entry)
        self.assertEqual(actual, expected)
        self.assertNotIn('projection_version', entry)


class RemainingLabelBoundaryTests(unittest.TestCase):
    def test_inline_reward_link_does_not_remove_a_nonnumeric_announcement(self):
        cfg = announcement.config('mir_announcements', 'promomir')
        body = '<a href="https://partner.example/offer">Ски<span>дка</span> на проживание в отеле</a>'
        parsed = parse_feed(announcement.post('promomir', 2000, body), cfg, announcement.NOW)
        self.assertEqual(parsed['errors'], [])
        self.assertEqual(len(parsed['records']), 1)
        row = parsed['records'][0]
        self.assertEqual(row['details']['linked_cards'],
                         [{'label': 'Скидка на проживание в отеле', 'url': 'https://partner.example/offer'}])
        self.assertEqual(row['record_kind'], 'announcement')
        self.assertIsNone(row['benefit_url'])
        publication(row)

    def test_literal_only_owned_section_is_not_empty_html(self):
        raw = recovered.VTB + '<section class="xNativeSection">&lt;VIP&gt;</section>'
        row = parse_bank_page('af_vtb_rules', raw, recovered.NOW)
        self.assertEqual(row['details']['sections'][-1], '<VIP>')
        self.assertTrue(row['conditions_text'].endswith('<VIP>'))
        self.assertEqual(row['details']['earning_rules'][0]['value'], '3')
        publication(row)

    def test_mir_snapshot_keeps_one_inline_partner_label(self):
        raw = '<main><div class="styles-module__promos__abc"><a class="promo-card-v2__link" href="/promo/test/a/"><div class="promo-card-v2-owner__name">Тех<span>нопарк</span></div></a></div></main>'
        result = dom_snapshot(raw, {'expected': 1, 'page_title': 'Mir'}, 'mir', 1)
        self.assertEqual(result['items'], [{'xml_id': None, 'url': '/promo/test/a/', 'name': 'Технопарк'}])


if __name__ == '__main__':
    unittest.main()
