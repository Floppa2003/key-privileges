"""Real public card excerpts and deliberately changed fixtures for scope regressions."""
import json
import sys
import unittest
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters import extract
from normalized import validate_offer
from partner_pages import CONFIG, extract_partner_page

FIX = Path(__file__).parent / 'fixtures_live' / 'ekp_public_20260925'
NOW = '2026-09-24T20:10:41.041736+00:00'
IDS = {'ladoga': 'ekp_ladoga_public', 'brawl': 'ekp_ilocked_brawl_stars'}


def parse(name='ladoga', raw=None, url=None):
    sid = IDS[name]
    return extract(sid, raw if raw is not None else (FIX / (name + '.html')).read_text(),
                   CONFIG[sid]['url'] if url is None else url, NOW)


class PublicContinuationTests(unittest.TestCase):
    def test_live_dom_excerpts_dispatch_validate_and_have_different_ids(self):
        rows = [parse(name)[0] for name in IDS]
        for row in rows:
            validate_offer(row)
            self.assertFalse(row['details']['source_account_used'])
            self.assertIsNone(row['valid_from'])
            self.assertIsNone(row['valid_until'])
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])

    def test_ladoga_is_gift_not_percentage_or_ruble_discount(self):
        row, = parse()
        self.assertEqual(row['benefit_types'], ['gift'])
        self.assertEqual(row['rates'], [])
        self.assertEqual(row['promo_codes'], [])
        self.assertEqual(row['details']['minimum_stay']['value'], 2)
        self.assertEqual(row['details']['minimum_stay']['unit'], 'days')
        self.assertEqual(row['details']['gift']['duration_hours'], 2)
        self.assertEqual(row['details']['gift']['choice'], 'one_of')
        self.assertEqual([x['quantity'] for x in row['details']['gift']['options']], [2, 2])
        self.assertIn('любого из домов', row['conditions_text'])
        self.assertFalse(row['details']['authenticated_catalogue_equivalence'])
        self.assertFalse(row['details']['linked_page_read'])

    def test_gift_counts_are_read_not_hardcoded(self):
        raw = (FIX / 'ladoga.html').read_text().replace('от 2х суток', 'от 3-х суток').replace(
            '2 часа проката 2-х велосипедов или 2-х сапбордов',
            '4 часа проката 5-х велосипедов или 6-х сапбордов')
        row, = parse(raw=raw)
        self.assertEqual(row['details']['minimum_stay']['value'], 3)
        self.assertEqual(row['details']['gift']['duration_hours'], 4)
        self.assertEqual([x['quantity'] for x in row['details']['gift']['options']], [5, 6])
        self.assertEqual(row['rates'], [])

    def test_general_note_preserved_separately_without_asserting_scope(self):
        row, = parse()
        self.assertEqual(len(row['details']['general_page_notes']), 1)
        self.assertIn('Telegram или Max', row['details']['general_page_notes'][0])
        self.assertEqual(row['details']['general_page_notes_apply_to_EKP'], 'not_established')
        self.assertNotIn('не суммируется', row['conditions_text'])
        self.assertEqual(row['details']['lexical_conditions'], [])

    def test_other_promotions_do_not_supply_discount_or_code(self):
        dom = BeautifulSoup((FIX / 'ladoga.html').read_text(), 'html.parser')
        card = dom.select_one('.js-product')
        other = BeautifulSoup(str(card), 'html.parser').select_one('.js-product')
        other.select_one('.js-product-name').string = 'День рождения'
        other.select_one('.t778__descr').string = 'Скидка 99%, промокод FOREIGN_ONLY'
        card.insert_before(other)
        row, = parse(raw=str(dom))
        self.assertEqual(row['rates'], [])
        self.assertNotIn('FOREIGN_ONLY', json.dumps(row))

    def test_missing_own_gift_cannot_borrow_another_card(self):
        raw = (FIX / 'ladoga.html').read_text()
        dom = BeautifulSoup(raw, 'html.parser')
        own = dom.select_one('.t778__descr')
        clause = own.get_text(' ', strip=True)
        own.string = 'Подробности отсутствуют'
        dom.body.append(BeautifulSoup('<p>' + clause + '</p>', 'html.parser'))
        with self.assertRaises(ValueError): parse(raw=str(dom))

    def test_missing_duplicate_or_changed_critical_terms_fail(self):
        raw = (FIX / 'ladoga.html').read_text()
        for changed in (raw + raw, raw.replace('js-product-name', 'other'),
                        raw.replace('t778__descr', 'other'),
                        raw.replace('любого из домов', ''),
                        raw.replace('сапбордов', 'лодок'),
                        raw.replace('от 2х суток', 'от 0х суток'),
                        raw.replace('2 часа проката', '0 часа проката'),
                        raw.replace('на выбор', 'одновременно'),
                        raw.replace('При бронировании', 'Скидка 10%. При бронировании')):
            with self.subTest(changed=changed[:50]), self.assertRaises(ValueError): parse(raw=changed)

    def test_missing_and_changed_eligibility_link_fail(self):
        raw = (FIX / 'ladoga.html').read_text()
        for changed in (raw.replace('https://ekp.spb.ru/capabilities?capability=offer',
                                    'https://example.test/unreviewed'),
                        raw.replace('href=', 'data-old-href=')):
            with self.assertRaises(ValueError): parse(raw=changed)

    def test_source_owned_additional_conditions_are_not_dropped(self):
        dom = BeautifulSoup((FIX / 'ladoga.html').read_text(), 'html.parser')
        dom.select_one('.t778__descr').append(' Только по предварительному согласованию.')
        row, = parse(raw=str(dom))
        self.assertIn('Только по предварительному согласованию.', row['conditions_text'])
        self.assertNotIn('Только по', row['benefit_text'])

    def test_hidden_forms_and_comments_cannot_supply_card(self):
        raw = (FIX / 'ladoga.html').read_text()
        for changed in ('<form>' + raw + '</form>', '<div hidden>' + raw + '</div>',
                        '<!-- ' + raw + ' -->', '<script>' + raw + '</script>'):
            with self.assertRaises(ValueError): parse(raw=changed)

    def test_duplicate_description_or_title_fails(self):
        for selector in ('.t778__descr', '.js-product-name'):
            dom = BeautifulSoup((FIX / 'ladoga.html').read_text(), 'html.parser')
            node = dom.select_one(selector)
            node.insert_after(BeautifulSoup(str(node), 'html.parser'))
            with self.assertRaises(ValueError): parse(raw=str(dom))

    def test_exact_source_url_and_input_dom_are_preserved(self):
        raw = (FIX / 'ladoga.html').read_text()
        for url in ('http://ladogabaza.ru/', 'https://ladogabaza.ru/?x=1',
                    'https://ladogabaza.ru/#other', 'https://example.test/'):
            with self.assertRaises(ValueError): parse(raw=raw, url=url)
        dom = BeautifulSoup(raw, 'html.parser'); before = str(dom)
        sid = IDS['ladoga']; extract_partner_page(sid, dom, CONFIG[sid]['url'], NOW)
        self.assertEqual(str(dom), before)

    def test_brawl_is_own_quest_not_its_atlantis_scenery(self):
        row, = parse('brawl')
        self.assertEqual(row['title'], 'BRAWL STARS')
        self.assertEqual(row['source_url'], 'https://ilocked.ru/quest/brawl-stars')
        self.assertEqual(row['rates'][0]['value'], '20')
        self.assertEqual(row['promo_codes'], ['ПЕТЕРБУРГ'])
        self.assertIn('на любое время и кол-во игроков', row['conditions_text'])
        self.assertIn('предъявить саму карту', row['redemption_text'])
        self.assertFalse(row['details']['applies_to_entire_catalogue'])
        self.assertFalse(row['details']['gated_catalogue_terms_recovered'])
        self.assertNotIn('Атлантида', row['title'])

    def test_brawl_missing_claim_cannot_borrow_booking_panel(self):
        raw = (FIX / 'brawl.html').read_text()
        dom = BeautifulSoup(raw, 'html.parser')
        claim = next(n for n in dom.find_all(string=True) if 'Перед игрой необходимо' in n)
        value = str(claim); claim.replace_with('No offer')
        dom.body.append(BeautifulSoup('<p>' + value + '</p>', 'html.parser'))
        with self.assertRaises(ValueError): parse('brawl', str(dom))

    def test_two_registry_entries_match_config_and_are_unique(self):
        registry = json.loads(Path(__file__).resolve().parents[1].joinpath('sources_normalized.json').read_text())
        for sid in IDS.values():
            rows = [r for r in registry if r['id'] == sid]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['url'], CONFIG[sid]['url'])
            self.assertEqual(rows[0]['mode'], 'html')


if __name__ == '__main__': unittest.main()
