"""Minimal anonymized encountered login and comma-separated order actions."""
import unittest

import test_promo_delivery_roles as roles


LOGIN = ('– Перейдите на сайт Пример – Зарегистрируйтесь или войдите в личный '
         'кабинет на сайте интернет-магазина – Добавляйте товары в корзину и '
         'указывайте в специальном поле промокод FIXTURE25 – Оплачивайте покупки '
         'на сумму чека от 4 000 ₽ картой «Мир» со скидкой 25%')
ORDER = ('Получить промокод в карточке Программа, оформить услугу на сайте/в '
         'приложении Сервис, ввести промокод; 500 миль начисляются в течение '
         '45 дней после завершения заказа')


class ObservedPromoActions(unittest.TestCase):
    source = roles.PromoDeliveryRoles.source
    retained = roles.PromoDeliveryRoles.retained
    assert_reader_codes = roles.PromoDeliveryRoles.assert_reader_codes

    def test_fresh_merchant_login_preserves_literal_without_account_issuance(self):
        source = self.source(LOGIN, benefit='Скидка 25%')
        self.assertEqual(source['details']['promo_code_delivery'], [])
        self.assertEqual(source['promo_codes'], ['FIXTURE25'])
        self.assertEqual(source['conditions_text'], LOGIN)

    def test_retained_merchant_login_preserves_literal_scope_and_terms(self):
        common = self.retained(LOGIN, ['FIXTURE25'], [('account', LOGIN)], benefit='Скидка 25%')
        self.assertEqual([(c['value'], c['delivery'], c['scope']) for c in common['codes']],
                         [('FIXTURE25', 'literal', {})])
        self.assertTrue(any(c['kind'] == 'minimum_purchase' and c['value'] == '4000'
                            for c in common['conditions']))
        self.assertTrue(any(b['kind'] == 'discount' and b['value'] == '25'
                            for b in common['benefits']))
        self.assert_reader_codes(common, 'Код: FIXTURE25')

    def test_fresh_comma_order_does_not_borrow_card_issuance(self):
        source = self.source(ORDER, benefit='Скидка 20% и 500 миль')
        self.assertEqual(source['details']['promo_code_delivery'], [])
        self.assertEqual(source['promo_codes'], [])
        self.assertEqual(source['conditions_text'], ORDER)

    def test_retained_comma_order_preserves_genuine_miles_and_instruction(self):
        common = self.retained(ORDER, [], [('app', ORDER.split(';')[0])],
                               benefit='Скидка 20% и 500 миль')
        self.assertEqual(common['codes'], [])
        self.assertTrue(any(b['kind'] == 'earn_miles' and b['value'] == '500'
                            for b in common['benefits']))
        self.assertEqual(common['raw']['conditions'], ORDER)
        self.assert_reader_codes(common, '')


# The merchant, supplied literal and commercial values are anonymized; the
# navigation, applicability and separate login/entry wording is encountered.
APP_BENEFIT = 'Скидка 7% на оплату от 4 000 ₽ на сайте и в приложении по промокоду'
APP_NAVIGATION = ('– Перейдите на сайт или в приложение ( Google Play , AppStore , '
                  'AppGallery , RuStore ) Пример – Зарегистрируйтесь или войдите '
                  'в личный кабинет – Добавляйте товары в корзину и указывайте '
                  'в специальном поле промокод FIXTURE7 – Оплачивайте покупки '
                  'на сумму чека от 4 000 ₽ картой «Мир» со скидкой 7%')
APP_APPLICATION = ('Промокод доступен для применения только при оформлении '
                   'заказа онлайн — на сайте или в мобильном приложении.')


class ObservedMerchantAppRedemption(unittest.TestCase):
    source = roles.PromoDeliveryRoles.source
    retained = roles.PromoDeliveryRoles.retained
    assert_reader_codes = roles.PromoDeliveryRoles.assert_reader_codes

    def test_fresh_app_venues_do_not_issue_the_supplied_code(self):
        for text in (APP_NAVIGATION, APP_NAVIGATION + '\n' + APP_APPLICATION):
            with self.subTest(text=text):
                source = self.source(text, benefit=APP_BENEFIT)
                self.assertEqual(source['details']['promo_code_delivery'], [])
                self.assertEqual(source['promo_codes'], ['FIXTURE7'])
                self.assertEqual(source['conditions_text'], text)

    def test_retained_app_venues_cannot_replace_one_another(self):
        text = APP_NAVIGATION + '\n' + APP_APPLICATION
        evidences = [APP_BENEFIT, APP_NAVIGATION, APP_APPLICATION]
        # Each false evidence must be rejected on its own as well as together;
        # otherwise reconciliation can silently fall back to a sibling claim.
        for selected in ([e] for e in evidences):
            with self.subTest(evidences=selected):
                self.check_app_redemption(text, selected)
        self.check_app_redemption(text, evidences)

    def check_app_redemption(self, text, evidences):
        common = self.retained(text, ['FIXTURE7'],
                               [('app', e) for e in evidences] + [('account', APP_NAVIGATION)],
                               benefit=APP_BENEFIT)
        self.assertEqual([(c['value'], c['delivery'], c['scope']) for c in common['codes']],
                         [('FIXTURE7', 'literal', {})])
        self.assertTrue(any(b['kind'] == 'discount' and b['value'] == '7'
                            for b in common['benefits']))
        self.assertTrue(any(c['kind'] == 'minimum_purchase' and c['value'] == '4000'
                            for c in common['conditions']))
        self.assertEqual(common['raw']['conditions'], text)
        self.assert_reader_codes(common, 'Код: FIXTURE7')


CHECKOUT = ('Скачайте приложение, укажите промокод FIXTURERIDE при заказе '
            'и наслаждайтесь дорогой.')
CHECKOUT_BENEFIT = ('Специальное предложение — скидку 10% по промокоду '
                    'FIXTURERIDE при заказе через приложение.')


class ObservedAppCheckout(unittest.TestCase):
    source = roles.PromoDeliveryRoles.source
    retained = roles.PromoDeliveryRoles.retained
    assert_reader_codes = roles.PromoDeliveryRoles.assert_reader_codes

    def test_fresh_checkout_input_does_not_issue_the_supplied_code(self):
        source = self.source(CHECKOUT, benefit=CHECKOUT_BENEFIT)
        self.assertEqual(source['details']['promo_code_delivery'], [])
        self.assertEqual(source['promo_codes'], ['FIXTURERIDE'])
        self.assertEqual(source['conditions_text'], CHECKOUT)

    def test_retained_checkout_input_cannot_replace_discount_application(self):
        common = self.retained(CHECKOUT, ['FIXTURERIDE'],
                               [('app', CHECKOUT_BENEFIT), ('app', CHECKOUT)],
                               benefit=CHECKOUT_BENEFIT)
        self.assertEqual([(c['value'], c['delivery'], c['scope']) for c in common['codes']],
                         [('FIXTURERIDE', 'literal', {})])
        self.assertEqual(common['raw']['conditions'], CHECKOUT)
        self.assertTrue(any(b['kind'] == 'discount' and b['value'] == '10'
                            for b in common['benefits']))
        self.assert_reader_codes(common, 'Код: FIXTURERIDE')
