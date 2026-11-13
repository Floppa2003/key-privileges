"""Anonymized encountered clauses: coupon issuance owns its channel."""
import copy
import unittest

from catalogue_view import record_row
from normalized import make_offer
from test_dom_card_boundaries import project
from unified_normalization import normalize_record


NOW = '2026-11-13T00:00:00+00:00'
ISSUANCE = ('Ваш уникальный промокод будет отображаться в личном кабинете '
            'на example.org и в приложении «Пример» в разделе «Промокоды и подарки».')
TARIFFS = ('*Тарифы, на которые действует промокод: Здание апартаментов '
           'Курорта Пример: Базовый тариф без питания')
SMS = 'Нажмите «Получить скидку» — вам придет SMS с промокодом.'
REDEMPTION = (
    'Введите промокод в приложении или на сайте «Пример».',
    'При покупке онлайн: авторизуйтесь на сайте или в мобильном приложении '
    'и введите промокод в специальное поле в корзине.',
    'Промокод предоставляет скидку 20% на весь ассортимент товаров в розничной '
    'сети, на сайте и в мобильном приложении «Пример» (кроме магазина-дисконта).',
)
CARD = ('Оформить бронирование номера по телефону или через сайт отеля '
        'с промокодом FIXTURE10 предъявить карту/виртуальную карту из '
        'мобильного приложения на стойке ресепшн при заезде.')
MEMBERSHIP = ('Для начисления миль введите номер Вашей карты участника программы '
              '«Пример» в поле «Промокод» при оформлении заказа на сайте '
              'или в мобильном приложении Сервис.')


class PromoDeliveryRoles(unittest.TestCase):
    def source(self, text):
        return make_offer('s7', 'delivery-roles', 'Программа', 'Пример',
                          'Скидка 10%', 'https://marketplace.s7.ru/partners/offer/fixture',
                          NOW, conditions=text)

    def assert_reader_codes(self, common, expected):
        row, reason = record_row(common, NOW[:10])
        self.assertIsNone(reason)
        self.assertEqual(row[3], expected)

    def retained(self, text, codes, delivery):
        raw = project(self.source(text))['raw']
        raw['codes'] = codes
        raw['details']['promo_code_delivery'] = [
            {'kind': 'delivery_reference', 'method': method, 'evidence': evidence}
            for method, evidence in delivery]
        before = copy.deepcopy(raw)
        common = normalize_record(raw, as_of=NOW[:10])
        self.assertEqual(common['raw'], before)
        self.assertEqual(raw, before)
        return common

    def test_source_tariff_applicability_heading_is_not_a_literal(self):
        source = self.source(ISSUANCE + '\n' + TARIFFS)
        self.assertEqual(source['promo_codes'], [])
        self.assertEqual([d['method'] for d in source['details']['promo_code_delivery']],
                         ['account', 'app'])
        self.assertEqual(source['conditions_text'], ISSUANCE + '\n' + TARIFFS)

    def test_retained_tariff_heading_keeps_only_account_and_app_issuance(self):
        common = self.retained(ISSUANCE + '\n' + TARIFFS, ['Здание'],
                               [('account', ISSUANCE), ('app', ISSUANCE)])
        self.assertEqual([(c['value'], c['delivery']) for c in common['codes']],
                         [(None, 'account'), (None, 'app')])
        self.assert_reader_codes(common, 'Получение: в личном кабинете\nПолучение: в приложении')

    def test_source_sms_issuance_does_not_turn_redemption_into_app_issuance(self):
        for redemption in REDEMPTION:
            with self.subTest(redemption=redemption):
                source = self.source(SMS + '\n' + redemption)
                self.assertEqual(source['promo_codes'], [])
                self.assertEqual([d['method'] for d in source['details']['promo_code_delivery']], ['sms'])

    def test_retained_sms_issuance_removes_app_redemption_assertion(self):
        for redemption in REDEMPTION:
            with self.subTest(redemption=redemption):
                common = self.retained(SMS + '\n' + redemption, [],
                                       [('sms', SMS), ('app', redemption)])
                self.assertEqual([(c['value'], c['delivery']) for c in common['codes']], [(None, 'sms')])
                self.assert_reader_codes(common, 'Получение: по SMS')

    def test_source_virtual_card_display_preserves_the_published_literal(self):
        source = self.source(CARD)
        self.assertEqual(source['promo_codes'], ['FIXTURE10'])
        self.assertEqual(source['details']['promo_code_delivery'], [])

    def test_retained_virtual_card_display_is_a_condition_not_code_issuance(self):
        common = self.retained(CARD, ['FIXTURE10'], [('app', CARD)])
        self.assertEqual([(c['value'], c['delivery']) for c in common['codes']], [('FIXTURE10', 'literal')])
        self.assertTrue(any(c['kind'] == 'card_required' for c in common['conditions']))
        self.assert_reader_codes(common, 'Код: FIXTURE10')

    def test_source_membership_number_in_promo_field_is_not_app_issuance(self):
        source = self.source(MEMBERSHIP)
        self.assertEqual(source['promo_codes'], [])
        self.assertEqual(source['details']['promo_code_delivery'], [])

    def test_retained_membership_number_in_promo_field_keeps_the_instruction(self):
        common = self.retained(MEMBERSHIP, [], [('app', MEMBERSHIP)])
        self.assertEqual(common['codes'], [])
        self.assertTrue(any(c['kind'] == 'activation_step' for c in common['conditions']))
        self.assert_reader_codes(common, '')
