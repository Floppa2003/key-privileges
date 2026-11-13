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
BONUS_ENTRY = ('Введите промокод FIXTURE20 в разделе «Ваши бонусы» в личном '
               'кабинете и получите 2 000 бонусов.')
BONUS_ACTIVATION = ('Для получения 2 000 бонусов необходимо зарегистрироваться '
                    'и активировать промокод FIXTURE20 в разделе «Ваши бонусы» '
                    'личного кабинета.')
REPEAT_ENTRY = ('Активируйте промокод в личном кабинете example.org, '
                'нажав кнопку "Ввести промокод"')
REPEAT_USE = ('В случае повторного использования привилегии в последующих '
              'месяцах активация промокода в личном кабинете example.org не требуется.')
AUDIENCE_CODES = ('для молодежи DEMOYOUTH\n'
                  'для людей старшего поколения DEMOSENIOR')
PDF_REPEAT_USE = ('В случае повторного использования привилегии в последующих '
                  'месяцах активация\nпромокода в личном кабинете не требуется.')
PDF_CODE_FRAGMENT = 'промокода в личном кабинете не требуется.'


class PromoDeliveryRoles(unittest.TestCase):
    def source(self, text, benefit='Скидка 10%', **kwargs):
        return make_offer('s7', 'delivery-roles', 'Программа', 'Пример',
                          benefit, 'https://marketplace.s7.ru/partners/offer/fixture',
                          NOW, conditions=text, **kwargs)

    def assert_reader_codes(self, common, expected):
        row, reason = record_row(common, NOW[:10])
        self.assertIsNone(reason)
        self.assertEqual(row[3], expected)

    def retained(self, text, codes, delivery, **kwargs):
        raw = project(self.source(text, **kwargs))['raw']
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

    def test_source_bonus_activation_is_not_account_issuance(self):
        text = BONUS_ENTRY + '\n' + BONUS_ACTIVATION
        source = self.source(text, benefit='2 000 бонусов по промокоду для новых пользователей')
        self.assertEqual(source['promo_codes'], ['FIXTURE20'])
        self.assertEqual(source['details']['promo_code_delivery'], [])
        self.assertEqual(source['conditions_text'], text)

    def test_retained_bonus_activation_does_not_replace_rejected_entry(self):
        text = BONUS_ENTRY + '\n' + BONUS_ACTIVATION
        common = self.retained(text, ['FIXTURE20'],
                               [('account', BONUS_ENTRY), ('account', BONUS_ACTIVATION)],
                               benefit='2 000 бонусов по промокоду для новых пользователей')
        self.assertEqual([(c['value'], c['delivery']) for c in common['codes']],
                         [('FIXTURE20', 'literal')])
        self.assertTrue(any(c['kind'] == 'activation_step' for c in common['conditions']))
        self.assert_reader_codes(common, 'Код: FIXTURE20')

    def test_source_repeat_activation_exemption_is_not_account_issuance(self):
        text = REPEAT_ENTRY + '\n' + AUDIENCE_CODES + '\n' + REPEAT_USE
        source = self.source(text, benefit='Двойные мили', record_kind='program_rules')
        self.assertEqual(source['details']['promo_code_delivery'], [])
        self.assertEqual(source['conditions_text'], text)

    def test_retained_repeat_activation_exemption_keeps_audience_codes(self):
        text = REPEAT_ENTRY + '\n' + AUDIENCE_CODES + '\n' + REPEAT_USE
        common = self.retained(text, [], [('account', REPEAT_ENTRY), ('account', REPEAT_USE)],
                               benefit='Двойные мили', record_kind='program_rules', details={
                                   'reward_multiplier': 2,
                                   'reward_multiplier_evidence': 'Двойные мили',
                                   'audiences': [
                                       {'audience': 'youth', 'promo_code': 'DEMOYOUTH',
                                        'evidence': 'для молодежи DEMOYOUTH'},
                                       {'audience': 'senior', 'promo_code': 'DEMOSENIOR',
                                        'evidence': 'для людей старшего поколения DEMOSENIOR'},
                                   ],
                               })
        self.assertEqual([(c['value'], c['delivery'], c['scope']) for c in common['codes']], [
            ('DEMOYOUTH', 'literal', {'audience': 'youth'}),
            ('DEMOSENIOR', 'literal', {'audience': 'senior'}),
        ])
        self.assertTrue(all(not c['standalone_offer'] for c in common['codes']))
        self.assertTrue(any(c['kind'] == 'activation_step' for c in common['conditions']))
        self.assert_reader_codes(common, 'Код: DEMOYOUTH\nКод: DEMOSENIOR')

    def test_source_wrapped_repeat_exemption_is_not_account_issuance(self):
        text = REPEAT_ENTRY + ':\n' + PDF_REPEAT_USE
        source = self.source(text, benefit='Подробнее', record_kind='program_rules',
                             details={'pages': [{'number': 1, 'text': text}]})
        self.assertEqual(source['details']['promo_code_delivery'], [])
        self.assertEqual(source['conditions_text'], text)

    def test_retained_wrapped_repeat_exemption_keeps_document_context(self):
        text = REPEAT_ENTRY + ':\n' + PDF_REPEAT_USE
        common = self.retained(text, [],
                               [('account', REPEAT_ENTRY + ':'), ('account', PDF_CODE_FRAGMENT)],
                               benefit='Подробнее', record_kind='program_rules',
                               details={'pages': [{'number': 1, 'text': text}]})
        self.assertEqual(common['codes'], [])
        self.assertTrue(any(c['kind'] == 'activation_step' for c in common['conditions']))
        row, reason = record_row(common, NOW[:10])
        self.assertIsNone(row)
        self.assertEqual(reason, 'документ вместо предложения')
