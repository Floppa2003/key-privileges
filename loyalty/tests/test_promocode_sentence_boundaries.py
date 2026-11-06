"""Sentence punctuation must not manufacture a spaced promo code."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from normalized import make_offer
from promo_codes import extract_promocodes


class PromocodeSentenceBoundaryTests(unittest.TestCase):
    def test_word_after_terminal_period_is_not_appended_to_code(self):
        for following in ('SMS с подтверждением придёт после заказа.',
                          'VIP — название другого тарифа.',
                          'СКИДКА действует на первый заказ.'):
            with self.subTest(following=following):
                result = extract_promocodes('Промокод FIRST10. ' + following)
                self.assertEqual(result['codes'], ['FIRST10'])
                self.assertEqual(result['evidence'][0]['evidence'], 'Промокод FIRST10.')

    def test_terminal_period_after_a_spaced_code_stops_at_that_word(self):
        for code in ('BLUE WINGS', 'BLUE WINGS CLUB'):
            with self.subTest(code=code):
                result = extract_promocodes('Промокод ' + code + '. SMS придёт позже.')
                self.assertEqual(result['codes'], [code])
                self.assertEqual(result['evidence'][0]['evidence'], 'Промокод ' + code + '.')

    def test_internal_dots_and_following_code_words_are_literal(self):
        for code in ('PROMO.CODE CLUB', 'BLUE WINGS.VIP CLUB'):
            with self.subTest(code=code):
                result = extract_promocodes('Промокод ' + code + ' при заказе.')
                self.assertEqual(result['codes'], [code])
                self.assertIn(code, result['evidence'][0]['evidence'])

    def test_quotes_keep_an_explicit_period_inside_the_code(self):
        result = extract_promocodes('Промокод «BLUE WINGS. VIP» действует при заказе.')
        self.assertEqual(result['codes'], ['BLUE WINGS. VIP'])
        self.assertIn('BLUE WINGS. VIP', result['evidence'][0]['evidence'])

    def test_offer_keeps_source_and_only_publishes_the_literal_code(self):
        body = 'Промокод FIRST10. SMS с подтверждением придёт после заказа.'
        offer = make_offer('moskvich', 'sentence-boundary', 'Карта', 'Партнёр',
                           'Скидка 10%', 'https://moskvichmag.ru/programma-loyalnosti/',
                           '2026-11-06T00:00:00Z', conditions=body)
        self.assertEqual(offer['conditions_text'], body)
        self.assertEqual(offer['promo_codes'], ['FIRST10'])
        self.assertTrue(all(item['code'] in item['evidence']
                            for item in offer['details']['promo_code_evidence']))


if __name__ == '__main__':
    unittest.main()
