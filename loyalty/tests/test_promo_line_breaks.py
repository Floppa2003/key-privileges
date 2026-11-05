"""A source label can place its literal code on the following line."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from adapters import extract
from promo_codes import extract_promocodes
from normalized import validate_offer


class PromoLineBreakTests(unittest.TestCase):
    def test_code_on_line_after_label_survives_html_extraction(self):
        for body in ['Промокод<br>SUMMER26', '<p>Промокод</p><p>SUMMER26</p>',
                     'Промокод<br>«SUMMER CLUB»']:
            with self.subTest(body=body):
                raw = ('<div class="lpp-card"><h3 class="lpp-card__name">Example</h3>'
                       '<div class="lpp-card__conditions">' + body + '</div></div>')
                row, = extract('moskvich', raw, 'https://moskvichmag.ru/programma-loyalnosti/',
                               '2026-11-05T22:00:00Z')
                validate_offer(row)
                self.assertEqual(row['promo_codes'], ['SUMMER CLUB' if 'CLUB' in body else 'SUMMER26'])

    def test_plain_line_break_preserves_literal_code_and_evidence(self):
        result = extract_promocodes('Промокод\nSUMMER26')
        self.assertEqual(result['codes'], ['SUMMER26'])
        self.assertEqual(result['evidence'][0]['evidence'], 'Промокод\nSUMMER26')

    def test_blank_line_does_not_attach_a_later_section_to_the_label(self):
        self.assertEqual(extract_promocodes('Промокод\n\nSUMMER26')['codes'], [])

    def test_delivery_instructions_do_not_become_codes_after_newline(self):
        for body in ['Промокод\nиз приложения', 'Промокод\nв личном кабинете', 'Промокод\nполучите по SMS']:
            with self.subTest(body=body):
                self.assertEqual(extract_promocodes(body)['codes'], [])


if __name__ == '__main__':
    unittest.main()
