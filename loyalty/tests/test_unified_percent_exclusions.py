"""Owned product-markdown exclusions must not become new discount benefits."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from unified_normalization import normalize_record, validate_normalized
from test_unified_normalization import record


class ExplicitPercentExclusionTests(unittest.TestCase):
    def project(self, conditions, *, benefit=''):
        raw = record(source_id='coral', program='CoralBonus', partner='Example',
                     benefit=benefit, conditions=conditions)
        before = copy.deepcopy(raw)
        result = normalize_record(raw, as_of='2026-11-06')
        validate_normalized(result)
        self.assertEqual(raw, before)
        self.assertEqual(result['raw'], before)
        return result

    @staticmethod
    def discounts(result):
        return {(b['value'], b['unit']) for b in result['benefits']
                if b['kind'] == 'discount'}

    def test_sunlight_product_markdown_stays_only_in_the_literal_exclusion(self):
        # Public SUNLIGHT wording, used as a fixture rather than a fresh observation.
        clause = ('* Скидка 1 000 рублей распространяется на весь ассортимент, '
                  'кроме подарочных сертификатов, упаковки, украшений категории '
                  '"Хит-цена", а также украшений с прямой скидкой -70%, '
                  'отмеченных красными ценами. Суммируется с бонусами и не '
                  'суммируется с другими акциями. Промокод дает право на скидку '
                  '1 000 рублей при покупке на сумму от 10 000 рублей.')
        result = self.project(clause, benefit='Скидка 1 000 рублей.')
        self.assertEqual(self.discounts(result), {('1000', 'RUB')})
        exclusions = [c for c in result['conditions'] if c['kind'] == 'exclusion']
        self.assertEqual([c['evidence']['text'] for c in exclusions], [clause])
        self.assertTrue(any(c['kind'] == 'minimum_purchase' and c['value'] == '10000'
                            for c in result['conditions']))

    def test_positive_discounts_before_the_list_and_in_next_sentence_survive(self):
        result = self.project('Скидка 10% распространяется на весь ассортимент, '
                              'кроме украшений с прямой скидкой -70%. '
                              'В интернет-магазине действует скидка 20%.')
        self.assertEqual(self.discounts(result), {('10', 'percent'), ('20', 'percent')})

    def test_decimal_points_and_commas_are_not_sentence_boundaries(self):
        for decimal in ('.', ','):
            with self.subTest(decimal=decimal):
                result = self.project(f'Скидка 7{decimal}5% распространяется на товары, '
                                      f'кроме украшений со скидкой -70{decimal}5%. '
                                      f'Для участников скидка 12{decimal}5%.')
                self.assertEqual(self.discounts(result),
                                 {('7.5', 'percent'), ('12.5', 'percent')})

    def test_same_numeric_value_outside_the_exception_is_not_removed(self):
        result = self.project('Скидка 70% распространяется на товары, '
                              'кроме украшений со скидкой -70%. '
                              'На доставку действует скидка 70%.')
        self.assertEqual(self.discounts(result), {('70', 'percent')})

    def test_multiple_explicit_products_in_one_exception_keep_their_ownership(self):
        result = self.project('Скидка 10% распространяется на товары, '
                              'кроме изделий со скидкой 50%, а также '
                              'украшений с прямой скидкой -70%.')
        self.assertEqual(self.discounts(result), {('10', 'percent')})

    def test_neighbouring_cashback_and_later_discount_keep_their_own_roles(self):
        result = self.project('Кешбэк 5%. Скидка 10% распространяется на товары, '
                              'кроме украшений со скидкой 70%. '
                              'Скидка 15% на доставку.')
        self.assertEqual(self.discounts(result), {('10', 'percent'), ('15', 'percent')})
        self.assertTrue(any(b['kind'] == 'cashback' and b['value'] == '5'
                            for b in result['benefits']))

    def test_additive_krome_togo_does_not_open_an_exception_list(self):
        for separator in (', ', '. '):
            for space in (' ', '  ', '\u00a0'):
                with self.subTest(separator=separator, space=space):
                    result = self.project('Скидка 10% распространяется на товары'
                                          + separator + 'кроме' + space + 'того, '
                                          'доступен выбор украшений со скидкой 20%.')
                    self.assertEqual(self.discounts(result),
                                     {('10', 'percent'), ('20', 'percent')})

        for connective in ('кроме того', 'кроме  того'):
            with self.subTest(later_connective=connective):
                result = self.project('Скидка 10% распространяется на товары, '
                                      'кроме изделий со скидкой 50%, '
                                      + connective + ', доступен выбор украшений '
                                      'со скидкой 70%.')
                self.assertEqual(self.discounts(result),
                                 {('10', 'percent'), ('70', 'percent')})

    def test_positive_product_markdown_without_an_applicability_exception_survives(self):
        result = self.project('Украшения с прямой скидкой -70%.')
        self.assertEqual(self.discounts(result), {('70', 'percent')})

    def test_new_paragraph_and_semicolon_do_not_extend_exception_ownership(self):
        for boundary in ('\n', '; '):
            with self.subTest(boundary=boundary):
                result = self.project('Скидка 10% распространяется на товары, '
                                      'кроме украшений со скидкой 70%' + boundary
                                      + 'Другие товары со скидкой 20%.')
                self.assertEqual(self.discounts(result),
                                 {('10', 'percent'), ('20', 'percent')})
    def test_independent_positive_statement_inside_sentence_is_not_product_descriptor(self):
        result = self.project('Скидка 10% распространяется на товары, '
                              'кроме украшений со скидкой 70%, '
                              'а на доставку действует скидка 20%.')
        self.assertEqual(self.discounts(result), {('10', 'percent'), ('20', 'percent')})


if __name__ == '__main__':
    unittest.main()
