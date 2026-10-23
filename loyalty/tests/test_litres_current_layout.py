"""Current public campaign boundaries, captured on the same GitHub runner."""
import copy
import json
import sys
import unittest
from pathlib import Path
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parents[1]))
from adapters import extract
from normalized import validate_offer
from partner_pages import CONFIG

NOW = '2026-10-23T10:30:00+00:00'
RAW = (Path(__file__).parent / 'fixtures_live/litres-20261023.html').read_text()

class LitresCurrentLayout(unittest.TestCase):
    def rows(self, raw):
        rows = extract('ekp_litres', raw, CONFIG['ekp_litres']['url'], NOW)
        for row in rows:
            validate_offer(row)
        return rows

    def test_captured_current_layout_preserves_complete_offer(self):
        rows = self.rows(RAW)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertIn('2 книги', row['benefit_text'])
        self.assertIn('20%', row['benefit_text'])
        self.assertIn('Взять себе', row['redemption_text'])
        self.assertIn('1 покупку', row['conditions_text'])
        self.assertIn('3-х дней', row['conditions_text'])
        self.assertIn('количество книг в корзине не ограничено', row['conditions_text'])
        self.assertIn('public_landing_copy_is_not_user_account_activation', row['warnings'])
        self.assertIsNone(row['valid_until'])

    def test_css_hashes_and_offer_values_are_not_allowlists(self):
        raw = RAW.replace('PgQ91q_', 'DifferentBuild_').replace('BPBMYG_', 'OtherHash_')
        raw = raw.replace('20%', '17%').replace('2 книги', '3 книги')
        row = self.rows(raw)[0]
        self.assertIn('17%', row['benefit_text'])
        self.assertIn('3 книги', row['benefit_text'])

    def test_unrelated_descriptions_do_not_supply_conditions(self):
        soup = BeautifulSoup(RAW, 'html.parser')
        noise = BeautifulSoup('<section><div class="Other_description">Скидка 91% WRONGPRODUCT</div></section>', 'html.parser').section
        soup.main.append(noise)
        soup.body.append(BeautifulSoup('<footer><div class="Other_abonementBlock"><div class="Other_description">Скидка 93% WRONGFOOTER</div></div></footer>', 'html.parser').footer)
        serialized = json.dumps(self.rows(str(soup)), ensure_ascii=False)
        self.assertNotIn('WRONG', serialized)

    def test_duplicate_owned_description_is_rejected(self):
        soup = BeautifulSoup(RAW, 'html.parser')
        block = soup.select_one("[class$='_description']")
        block.insert_after(copy.copy(block))
        with self.assertRaisesRegex(ValueError, 'partner_content_selector_ambiguous'):
            self.rows(str(soup))

    def test_duplicate_page_heading_is_rejected(self):
        soup = BeautifulSoup(RAW, 'html.parser')
        soup.h1.insert_after(copy.copy(soup.h1))
        with self.assertRaisesRegex(ValueError, 'partner_content_selector_ambiguous'):
            self.rows(str(soup))

    def test_empty_description_does_not_pass_on_title_alone(self):
        soup = BeautifulSoup(RAW, 'html.parser')
        soup.select_one("[class$='_description']").clear()
        with self.assertRaisesRegex(ValueError, 'partner_content_selector_empty'):
            self.rows(str(soup))

    def test_missing_owner_cannot_fall_back_to_other_page_text(self):
        soup = BeautifulSoup(RAW, 'html.parser')
        soup.main['aria-labelledby'] = 'otherPage'
        with self.assertRaisesRegex(ValueError, 'partner_content_selector_missing'):
            self.rows(str(soup))

if __name__ == '__main__':
    unittest.main()
