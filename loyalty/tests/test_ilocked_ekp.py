"""Boundary regressions; source smoke checks use separately timestamped artifacts."""
import json, sys, unittest
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters import extract
from partner_pages import CONFIG, extract_partner_page
from normalized import validate_offer

SID = 'ekp_ilocked_chuzhoy'
URL = 'https://ilocked.ru/quest/chuzhoy'
NOW = '2026-09-18T00:00:00+00:00'  # Synthetic test observation only.


def claim(rate='17,5', code='FIXTURE_ONLY'):
    return ('Для владельцев карты Единая Карта Петербуржца: '
            f'{rate}% СКИДКА. Промокод: {code}. '
            'Перед игрой необходимо предъявить саму карту!')


def page(body=None, title='Synthetic quest', heading='БРОНИРОВАНИЕ КВЕСТА'):
    body = claim() if body is None else body
    return (f'<html><body><h1>{title}</h1><p>Invented plot.</p><p>{body}</p>'
            '<p>ВАЖНО: Synthetic deposit 1234 RUB; a minor needs an adult.</p>'
            f'<h3>{heading}</h3><p>Скидка 99%, промокод OTHER_ONLY.</p>'
            '<h3>Похожие квесты</h3><p>Birthday package.</p></body></html>')


class IlockedEkpTests(unittest.TestCase):
    def test_end_to_end_source_mapping_is_dynamic(self):
        for value in ('17,5', '23'):
            record, = extract(SID, page(claim(value)), URL, NOW)
            self.assertEqual(record['rates'][0]['value'], value.replace(',', '.'))
            self.assertEqual(record['promo_codes'], ['FIXTURE_ONLY'])
            self.assertEqual(record['title'], 'Synthetic quest')
            self.assertIn('1234', record['conditions_text'])
            self.assertFalse(record['details']['gated_catalogue_terms_recovered'])
            self.assertIsNone(record['valid_until'])
            self.assertNotIn('OTHER_ONLY', json.dumps(record))
            validate_offer(record)

    def test_party_heading_also_ends_own_intro(self):
        record, = extract(SID, page(heading='ВЫБЕРИТЕ СВОЙ ПРАЗДНИК'), URL, NOW)
        self.assertNotIn('Birthday', record['conditions_text'])

    def test_other_quest_must_not_supply_missing_own_offer(self):
        with self.assertRaises(ValueError):
            extract(SID, page('No own EKP offer.') + '<p>' + claim() + '</p>', URL, NOW)

    def test_missing_card_requirement_is_not_assumed(self):
        with self.assertRaises(ValueError):
            extract(SID, page(claim().split('Перед игрой')[0]), URL, NOW)

    def test_multiple_claims_or_rates_are_rejected(self):
        for body in (claim() + claim('30', 'OTHER'), claim().replace('17,5%', '17,5% или 30%')):
            with self.subTest(body=body), self.assertRaises(ValueError):
                extract(SID, page(body), URL, NOW)

    def test_missing_or_ambiguous_title_is_rejected(self):
        for raw in (page().replace('<h1>Synthetic quest</h1>', ''), page().replace('</h1>', '</h1><h1>Other</h1>')):
            with self.assertRaises(ValueError):
                extract(SID, raw, URL, NOW)

    def test_missing_section_boundary_fails_closed(self):
        with self.assertRaises(ValueError):
            extract(SID, page().replace('h3>', 'div>'), URL, NOW)

    def test_hidden_claims_and_form_values_do_not_supply_evidence(self):
        body = '<div hidden>' + claim() + '</div><form>' + claim() + '</form>'
        with self.assertRaises(ValueError):
            extract(SID, page(body), URL, NOW)

    def test_html_comment_does_not_become_an_offer(self):
        raw = page('<!-- ' + claim('45', 'COMMENT_ONLY') + ' -->' + claim())
        record, = extract(SID, raw, URL, NOW)
        self.assertEqual(record['promo_codes'], ['FIXTURE_ONLY'])
        self.assertNotIn('COMMENT_ONLY', json.dumps(record))

    def test_exact_url_scope_rejects_foreign_or_tracking_urls(self):
        for url in (URL + '?code=OTHER', URL + '#other', URL.replace('ilocked.ru', 'example.test'),
                    URL.replace('chuzhoy', 'mumiya')):
            with self.assertRaises(ValueError):
                extract(SID, page(), url, NOW)

    def test_does_not_mutate_supplied_dom(self):
        dom = BeautifulSoup(page(), 'html.parser')
        before = str(dom)
        extract_partner_page(SID, dom, URL, NOW)
        self.assertEqual(str(dom), before)

    def test_eight_configured_quests_have_distinct_matching_routes(self):
        routes = json.loads(Path(__file__).resolve().parents[1].joinpath('sources_normalized.json').read_text())
        selected = [r for r in routes if r['id'].startswith('ekp_ilocked_')]
        self.assertEqual(len(selected), 8)
        self.assertEqual(len({r['url'] for r in selected}), 8)
        for route in selected:
            self.assertEqual(route['url'], CONFIG[route['id']]['url'])
            record, = extract(route['id'], page(title=route['id']), route['url'], NOW)
            self.assertEqual(record['source_id'], route['id'])
            self.assertEqual(record['title'], route['id'])


class IlockedCertificateTests(unittest.TestCase):
    SID = 'ilocked_certificate_terms'
    URL = 'https://ilocked.ru/certificate'

    def page(self, text='На игры по подарочным сертификатам скидки не распространяются.'):
        return ('<html><h1>Сертификат на квест</h1><div class="t165__textwrapper">'
                '<div class="t165__btn-container"><p>' + text + '</p></div></div>'
                '<div id="text">Long contract: 99%, промокод WRONG_ONLY</div></html>')

    def test_only_short_owned_restriction_projects_no_benefit_or_code(self):
        r, = extract(self.SID, self.page(), self.URL, NOW)
        self.assertEqual(r['record_kind'], 'program_rules')
        self.assertEqual(r['benefit_text'], '')
        self.assertEqual(r['rates'], [])
        self.assertEqual(r['promo_codes'], [])
        self.assertIsNone(r['benefit_url'])
        self.assertNotIn('contract', r['conditions_text'])
        self.assertLess(len(r['conditions_text']), 100)
        validate_offer(r)

    def test_missing_moved_positive_and_ambiguous_restrictions_fail(self):
        for raw in (self.page().replace('t165__textwrapper', 'other'),
                    self.page('Подарочным сертификатам предоставляются скидки.'),
                    self.page().replace('</p>', '</p><p>На игры по подарочным сертификатам скидки не распространяются.</p>'),
                    self.page().replace('<p>', '<p hidden>')):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                extract(self.SID, raw, self.URL, NOW)

    def test_changed_literal_restriction_is_preserved_not_canned(self):
        wording='На любые игры по подарочным сертификатам скидки не распространяются. Действует для всех сеансов.'
        r, = extract(self.SID, self.page(wording), self.URL, NOW)
        self.assertEqual(r['conditions_text'], wording)

    def test_quest_requires_independent_certificate_record_without_false_fetch(self):
        r, = extract(SID, page(), URL, NOW)
        link, = r['details']['linked_documents']
        self.assertEqual(link['source_id'], self.SID)
        self.assertFalse(link['same_observation'])

if __name__ == '__main__':
    unittest.main()
