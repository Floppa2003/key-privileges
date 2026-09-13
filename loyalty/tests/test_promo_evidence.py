"""Regressions from the published 2.3.1 payload: instructions are not codes."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
from normalized import make_offer, validate_offer, content_hash

NOW = '2026-09-13T10:00:00+00:00'
def record(value):
    return make_offer('s7', 'fixture', 'S7', 'Example', 'Скидка 10%',
                      'https://marketplace.s7.ru/partners/offer/fixture', NOW,
                      conditions=value)

class PromoEvidenceTests(unittest.TestCase):
    def test_sms_instruction_never_becomes_literal_code(self):
        r = record('Введите промокод из SMS. Вам придёт SMS с промокодом.')
        self.assertEqual(r['promo_codes'], [])
        self.assertTrue(any(x['method'] == 'sms' for x in r['details']['promo_code_delivery']))

    def test_dates_and_duration_are_not_codes(self):
        r = record('Срок действия промокода до 15.09.2026. Промокод действует 30 дней. '
                   'Скидка по промокоду на 90 дней абонентской платы.')
        self.assertEqual(r['promo_codes'], [])

    def test_currency_cap_is_not_a_numeric_coupon(self):
        r = record('Максимальный размер скидки по промокоду — 200 ₽. '
                   'Размер скидки по промокоду составляет 2000 рублей.')
        self.assertEqual(r['promo_codes'], [])

    def test_numbered_redemption_steps_are_not_codes(self):
        r = record('Как воспользоваться промокодом: 1. Перейдите на сайт. '
                   'Введите промокод KRILYA10 в поле «промокод».')
        self.assertEqual(r['promo_codes'], ['KRILYA10'])

    def test_generic_provider_name_is_not_a_coupon(self):
        self.assertEqual(record('Введите промокод от Т2. Промокод из SMS.')['promo_codes'], [])

    def test_real_cyrillic_title_case_code_survives(self):
        r = record('При бронировании введите промокод: Скидка 10% для держателей карт '
                   'по промокоду - Крылья. Карта предъявляется при заезде.')
        self.assertEqual(r['promo_codes'], ['Крылья'])

    def test_lowercase_public_code_is_preserved(self):
        self.assertEqual(record('Скидка по промокоду moskvichmag при заказе.')['promo_codes'], ['moskvichmag'])

    def test_quoted_spacing_is_trimmed_without_changing_internal_code(self):
        self.assertEqual(record('Промокод « Крылья5 »; промокод «Крылья5».')['promo_codes'], ['Крылья5'])

    def test_explicit_multiword_codes_keep_exact_spelling_and_evidence(self):
        r = record('Скидка по промокоду MOSKVICH MAG при бронировании; '
                   'промокод «Скидка BLUE WINGS».')
        self.assertEqual(r['promo_codes'], ['MOSKVICH MAG', 'Скидка BLUE WINGS'])
        self.assertEqual([x['code'] for x in r['details']['promo_code_evidence']], r['promo_codes'])
        self.assertTrue(all(x['code'] in x['evidence'] for x in r['details']['promo_code_evidence']))

    def test_actual_numeric_codes_are_not_removed_with_caps(self):
        r = record('Примените промокод 2026. Промокод «86023».')
        self.assertEqual(r['promo_codes'], ['2026', '86023'])

    def test_unpublished_personal_code_stays_unknown_and_source_text_is_kept(self):
        value = 'Ваш уникальный промокод будет отображаться в Личном кабинете.'
        r = record(value)
        self.assertEqual(r['promo_codes'], [])
        self.assertEqual(r['conditions_text'], value)
        self.assertIn('promo_code_mentioned_not_extracted', r['warnings'])
        self.assertEqual(r['details']['promo_code_delivery'][0]['method'], 'account')

    def test_published_and_sms_code_mechanisms_can_coexist(self):
        r = record('Промокод FIRST10 для первого заказа. Другой промокод придёт в SMS.')
        self.assertEqual(r['promo_codes'], ['FIRST10'])
        self.assertTrue(r['details']['promo_code_delivery'])

    def test_rehashed_fake_code_is_rejected_at_publication_boundary(self):
        r = record('Получите промокод из SMS.')
        r['promo_codes'] = ['SECRET90']
        r['content_sha256'] = content_hash(r)
        with self.assertRaises(ValueError):
            validate_offer(r)

    def test_rehashed_fake_code_evidence_is_rejected(self):
        r = record('Промокод REAL10.')
        r['details']['promo_code_evidence'] = [{'code': 'REAL10', 'evidence': 'not in source'}]
        r['content_sha256'] = content_hash(r)
        with self.assertRaises(ValueError):
            validate_offer(r)

    def test_plural_quoted_code_list_is_not_reduced_to_first_item(self):
        self.assertEqual(record('Промокоды: «BLUE», «SILVER» и «GOLD».')['promo_codes'], ['BLUE', 'SILVER', 'GOLD'])

    def test_unrelated_quoted_ui_labels_do_not_become_codes(self):
        r = record('Нажмите «Получить промокод». Введите промокод в поле «Промокод». '
                   'Откройте раздел «Промокоды и скидки».')
        self.assertEqual(r['promo_codes'], [])

class PublishedInstructionRegressions(unittest.TestCase):
    def test_cyrillic_instructions_and_section_headings_are_not_codes(self):
        fragments = [
            'Промокоды указаны в личном кабинете.',
            'Промокоды действуют до 30.04.2026 г.',
            'Промокод предоставьте администратору.',
            'После применения промокода нажмите кнопку.',
            'По промокоду возможна только одна покупка.',
            'Промокод недоступен повторно.',
            'При наличии промокода стоимость изменится.',
            'Промокод многоразовый, доступно несколько покупок.',
            'Промокод нельзя передавать.',
            'Промокод применяется при оплате.',
            'Промокод направляются в SMS.',
            'Промокод\nОформите заказ на сайте.',
            'Промокод\nМир\nОформите заказ.',
        ]
        for fragment in fragments:
            with self.subTest(fragment=fragment):
                self.assertEqual(record(fragment)['promo_codes'], [])

    def test_tier_table_label_does_not_make_siniy_a_code(self):
        r = record('Тип карты Скидка Промокод\nСиний 3% UAir3 Серебряный 5% UAir5')
        self.assertEqual(r['promo_codes'], [])

    def test_url_after_a_label_is_not_a_code(self):
        self.assertEqual(record('Промокод https://example.org/redeem')['promo_codes'], [])

    def test_unquoted_code_does_not_jump_to_next_paragraph(self):
        self.assertEqual(record('В поле промокод\nFIRST10 — название другой акции.')['promo_codes'], [])

    def test_explicit_delimited_code_can_start_on_next_line(self):
        self.assertEqual(record('Ваш промокод:\nFIRST10 для первого заказа.')['promo_codes'], ['FIRST10'])

    def test_quoted_cyrillic_code_is_literal_not_instruction(self):
        self.assertEqual(record('Скидка по промокоду «Уральские».')['promo_codes'], ['Уральские'])

class StructuredPromoTests(unittest.TestCase):
    def test_explicit_coupon_column_retains_tier_row_as_evidence(self):
        table = [['Тип карты','Скидка','Промокод'],
                 ['Синий','3%','UAir3'],['Серебряный','5%','UAir5'],['Золотой','7%','UAir7']]
        r = make_offer('ural','test-table','Крылья','Олимп','Скидки участникам',
            'https://www.uralairlines.ru/partners/',NOW,tables=[table])
        self.assertEqual(r['promo_codes'], ['UAir3','UAir5','UAir7'])
        evidence = r['details']['promo_code_evidence'][1]
        self.assertEqual(evidence['row'], ['Серебряный','5%','UAir5'])
        self.assertEqual(evidence['headers'], table[0])
        self.assertEqual(evidence['table_index'],0)
        self.assertEqual(evidence['row_index'],2)
        self.assertEqual(evidence['code_column'],2)
        self.assertEqual(evidence['kind'],'source_table')

    def test_table_without_code_header_or_ragged_rows_is_not_guessed(self):
        tables=[[['Тип карты','Скидка'],['Синий','5%']],
                [['Тип карты','Промокод'],['Синий','MISSING','COLUMN']]]
        r = make_offer('ural','fixture','Крылья','Test','Скидка 5%',
            'https://www.uralairlines.ru/partners/',NOW,tables=tables)
        self.assertEqual(r['promo_codes'],[])

    def test_delivery_instruction_in_coupon_column_is_not_a_code(self):
        tables=[[['Промокод'],['Получите в SMS']]]
        r = make_offer('ural','fixture','Крылья','Test','Скидка 5%',
            'https://www.uralairlines.ru/partners/',NOW,tables=tables)
        self.assertEqual(r['promo_codes'],[])

    def test_plural_semicolon_offer_list_yields_both_codes_not_directions(self):
        r = record('Промокоды: URAL3 - 3% на туры от 100 000 руб.; '
                   'URAL5 - 5% на туры от 150 000 руб. Промокоды действуют до 30.04.2026 г.')
        self.assertEqual(r['promo_codes'], ['URAL3','URAL5'])

class RoundtripNoiseTests(unittest.TestCase):
    def test_instruction_after_list_dash_is_not_a_delimited_code(self):
        for verb in ['Приходите','Оформите','Нажмите','Оплатите','Зарегистрируйтесь']:
            with self.subTest(verb=verb):
                self.assertEqual(record(f'Назовите промокод – {verb} в приложении.')['promo_codes'],[])

    def test_counted_brand_coupons_are_not_literal_codes(self):
        r = record('Один абонент может получить и активировать два промокода «Чиббис» за весь период акции.')
        self.assertEqual(r['promo_codes'],[])
