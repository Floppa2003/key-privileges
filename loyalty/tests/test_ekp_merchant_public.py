"""Source-owned clauses, product ownership and required redemption restrictions."""
import json, sys, unittest
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters import extract
from normalized import validate_offer
from partner_pages import CONFIG

NOW = '2026-09-24T07:20:15+00:00'
FIXTURES = Path(__file__).parent / 'fixtures_live' / 'ekp_merchants'
IDS = {'artparking': 'ekp_artparking_public', 'domknigi': 'ekp_domknigi_public', 'itc': 'ekp_itc_public'}


def parse(name, raw=None):
    sid = IDS[name]
    return extract(sid, raw if raw is not None else (FIXTURES / (name + '.html')).read_text(), CONFIG[sid]['url'], NOW)


class PublicMerchantTests(unittest.TestCase):
    def test_actual_captured_pages_dispatch_and_validate(self):
        for name, count in [('artparking', 2), ('domknigi', 1), ('itc', 1)]:
            rows = parse(name); self.assertEqual(len(rows), count)
            for row in rows:
                validate_offer(row)
                self.assertFalse(row['details']['authenticated_catalogue_equivalence'])
                self.assertFalse(row['details']['coupon_issued'])

    def test_artparking_product_rates_codes_and_exclusions(self):
        concert, kids = parse('artparking')
        self.assertEqual(concert['rates'][0]['value'], '15')
        self.assertEqual(kids['rates'][0]['value'], '5')
        for r in (concert, kids):
            self.assertEqual(r['promo_codes'], ['edkarta'])
            self.assertIn('Зеленогорской кирхе', r['conditions_text'])
            self.assertIn('необходимо предъявить Единую карту', r['redemption_text'])
            self.assertIsNone(r['valid_until'])
        self.assertNotIn('оплачивать заранее', concert['conditions_text'])
        self.assertIn('оплачивать заранее', kids['conditions_text'])

    def test_changed_rates_and_literal_codes_not_canned(self):
        raw = (FIXTURES / 'artparking.html').read_text().replace('15%', '17%').replace('5%', '6%').replace('edkarta', 'newekp')
        concert, kids = parse('artparking', raw)
        self.assertEqual([concert['rates'][0]['value'], kids['rates'][0]['value']], ['17', '6'])
        self.assertEqual(concert['promo_codes'], ['newekp'])
        raw = (FIXTURES / 'itc.html').read_text().replace('-15%', '-12%')
        self.assertEqual(parse('itc', raw)[0]['rates'][0]['value'], '12')

    def test_missing_product_or_exclusion_fails(self):
        raw = (FIXTURES / 'artparking.html').read_text()
        for remove in ('Детские программы www.gorodmus.ru – 5% Промокод edkarta', 'Зеленогорской кирхе'):
            with self.assertRaises(ValueError): parse('artparking', raw.replace(remove, ''))

    def test_domknigi_start_not_article_date_and_no_invented_code(self):
        row, = parse('domknigi')
        self.assertEqual(row['valid_from'], '2026-02-24')
        self.assertIsNone(row['valid_until'])
        self.assertEqual(row['promo_codes'], [])
        self.assertEqual(row['rates'][0]['value'], '10')
        self.assertIn('Оплатить покупку бонусами также нельзя', row['conditions_text'])
        self.assertIn('Интернет', row['redemption_text'])
        self.assertIn('назвать промокод на кассе', row['redemption_text'])

    def test_domknigi_rate_conflict_missing_scope_and_wrong_date_fail(self):
        raw = (FIXTURES / 'domknigi.html').read_text()
        for value in (raw.replace('10%', '11%', 1), raw.replace('Оплатить покупку бонусами также нельзя', ''), raw.replace('24.02.2026', '31.02.2026')):
            with self.assertRaises(ValueError): parse('domknigi', value)

    def test_itc_payment_not_merely_showing_card(self):
        row, = parse('itc')
        self.assertEqual(row['rates'][0]['value'], '15')
        self.assertIn('при оплате ЕКП', row['redemption_text'])
        self.assertEqual(row['promo_codes'], [])
        self.assertNotIn('Антикоррупционная', row['conditions_text'])

    def test_browser_repaired_itc_paragraphs(self):
        dom = BeautifulSoup((FIXTURES / 'itc.html').read_text(), 'html.parser')
        block = dom.select_one('#bx_3218110189_78981')
        inner = list(block.find_all('p', recursive=False))
        for n in reversed(inner): block.insert_after(n.extract())
        row, = parse('itc', str(dom))
        self.assertEqual(row['rates'][0]['value'], '15')
        self.assertNotIn('Антикоррупционная', row['conditions_text'])

    def test_missing_itc_discount_cannot_borrow_next_partner(self):
        raw = (FIXTURES / 'itc.html').read_text().replace('-15% при оплате ЕКП!', 'особые условия!')
        raw = raw.replace('Антикоррупционная Хартия', 'Скидка -99% при оплате ЕКП! Антикоррупционная Хартия')
        with self.assertRaises(ValueError): parse('itc', raw)

    def test_duplicate_scope_and_foreign_page_fail(self):
        for name in IDS:
            raw = (FIXTURES / (name + '.html')).read_text()
            with self.assertRaises(ValueError): parse(name, raw + raw)
            with self.assertRaises(ValueError): extract(IDS[name], raw, CONFIG[IDS[name]]['url'] + 'other', NOW)

    def test_registry_wired_once(self):
        sources = json.loads(Path(__file__).resolve().parents[1].joinpath('sources_normalized.json').read_text())
        for sid in IDS.values():
            matches = [s for s in sources if s['id'] == sid]
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0]['mode'], 'html')
            self.assertEqual(matches[0]['url'], CONFIG[sid]['url'])

if __name__ == '__main__': unittest.main()
