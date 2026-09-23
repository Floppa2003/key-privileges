"""A real coupon shape states its gift in redemption, not its short heading."""
import unittest
from test_catalogue_expansion import coupon, OLD, bundle
from test_lifecycle_pipeline import reader
from sheets_normalized import prepare
from gorod_source import source_fields

class GorodGiftReader(unittest.TestCase):
    def evidence(self):
        e = coupon()
        e['data']['name'] = 'Пицца на выбор при заказе от 1 419₽ в PizzaSushiWok'
        e['data']['terms'] = 'На выбор представлены 3 пиццы (20 см).'
        e['data']['howToAsList'] = [
            'Получите купон.',
            'Введите код с купона. Подарочная пицца добавится в корзину.',
            'Соберите и оплатите заказ на сумму от 1 419 ₽.',
        ]
        return e

    def test_explicit_gift_reaches_reader_with_minimum_and_cost(self):
        e = self.evidence()
        row = prepare(bundle('gorod_public', [e]))['parser_offers'][0]
        view, reason = reader(row, OLD[:10])
        self.assertIsNone(reason)
        self.assertIsNotNone(view)
        self.assertIn('в подарок', view[2])
        self.assertIn('1 419', view[2])
        self.assertIn('жетоны', view[5])
        self.assertEqual(source_fields(e)['title'], e['data']['name'])

    def test_no_gift_inferred_from_name_alone(self):
        e = self.evidence()
        e['data']['howToAsList'][1] = 'Введите код с купона.'
        self.assertNotIn('в подарок', source_fields(e)['benefit'])

if __name__ == '__main__': unittest.main()
