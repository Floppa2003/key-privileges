"""Alfa document values are data; document identity and clause ownership remain gates."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))
import alfa_public_rules as source
from test_alfa_public_rules import CORE_TEXT, CASHBACK_TEXT, NOW
from test_dom_card_boundaries import project
from catalogue_clauses import benefit_claim
from catalogue_view import record_row


def core(text=CORE_TEXT):
    with patch.object(source, 'pdf_text', return_value=text):
        return source.parse_core(b'%PDF-core-value-test', NOW)


def cashback(text=CASHBACK_TEXT):
    with patch.object(source, 'pdf_text', return_value=text):
        return source.parse_cashback(b'%PDF-cashback-value-test', NOW)[0]


class AlfaPublicValueInvariance(unittest.TestCase):
    def accepted(self, fn, text):
        try:
            return fn(text)
        except ValueError as exc:
            self.fail(f'Changed owned value rejected: {exc}')

    def test_restaurant_expense_retains_the_entire_number_and_unit(self):
        for old, new in [('списании 2 Альфа-Баллов', 'списании 20 Альфа-Баллов'),
                         ('списании 1 Альфа-Балла', 'списании 11 Альфа-Баллов')]:
            with self.subTest(new=new):
                row = self.accepted(core, CORE_TEXT.replace(old, new))[2]
                self.assertIn(new, row['benefit_text'])
                self.assertIn(new, str(project(row)['raw']['benefit']))
                self.assertEqual(row['id'], core()[2]['id'])

    def test_independent_money_caps_change_without_old_value_pins(self):
        changes = [
            ('такси, трансфер и каршеринг, но не более 2 500 рублей',
             'такси, трансфер и каршеринг, но не более 3 400,50 рублей', 0, 'benefit_text', '3 400,50'),
            ('не более 2 500 рублей за доступ', 'не более 3 100 рублей за доступ', 1, 'benefit_text', '3 100'),
            ('БЗ составляет 20 000 рублей', 'БЗ составляет 27 500,75 рублей', 1, 'conditions_text', '27 500,75'),
            ('2 500 рублей при списании', '3 500,50 рублей при списании', 2, 'benefit_text', '3 500,50'),
            ('5 000 рублей при списании', '6 700 рублей при списании', 2, 'benefit_text', '6 700'),
            ('РКБ составляет 20 000 рублей', 'РКБ составляет 31 000 рублей', 2, 'conditions_text', '31 000'),
            ('от 6 000 000 рублей', 'от 7 500 000,50 рублей', 4, 'benefit_text', '7 500 000,50'),
        ]
        for old, new, index, field, expected in changes:
            with self.subTest(new=new):
                rows = self.accepted(core, CORE_TEXT.replace(old, new))
                self.assertIn(expected, rows[index][field])
                self.assertEqual([r['id'] for r in rows], [r['id'] for r in core()])
                self.assertTrue(all(r['details']['document_revision'] == 47 for r in rows))

    def test_count_dependent_day_hour_and_companion_forms(self):
        changes = [('2 рабочих дней', '1 рабочего дня', 0, 'conditions_text'),
                   ('2 рабочих дней', '7 рабочих дней', 0, 'conditions_text'),
                   ('не более 3 лиц', 'не более 5 лиц', 3, 'benefit_text'),
                   ('не более 3 лиц', 'не более 1 лица', 3, 'benefit_text'),
                   ('в течение 24 часов', 'в течение 1 часа', 3, 'conditions_text'),
                   ('в течение 24 часов', 'в течение 48 часов', 3, 'conditions_text')]
        for old, new, index, field in changes:
            with self.subTest(new=new):
                rows = self.accepted(core, CORE_TEXT.replace(old, new))
                self.assertIn(new, rows[index][field])

    def test_parenthesized_words_and_actual_point_unit_are_preserved(self):
        text = CORE_TEXT.replace('2 500 рублей', '2 750 (по условиям) рублей')
        text = text.replace('списании 1 Альфа-Балла', 'списании 3 (трех) Баллов')
        text = text.replace('списании 2 Альфа-Баллов', 'списании 20 (двадцати) Баллов')
        text = text.replace('не более 3 лиц', 'не более 5 (пяти), не считая Участника')
        rows = self.accepted(core, text)
        for phrase in ('2 750 (по условиям) рублей', '3 (трех) Баллов', '20 (двадцати) Баллов'):
            self.assertIn(phrase, rows[2]['benefit_text'])
        self.assertIn('5 (пяти), не считая Участника', rows[3]['benefit_text'])

    def test_participant_labels_and_phone_digits_are_not_fixed_offer_values(self):
        old = 'Участнику 3, Участнику 4, Участнику 5 и Участнику 7 доступна Услуга «Консьерж сервис»'
        new = 'Участнику 8, Участнику 12 и Участнику 15 доступна Услуга «Консьерж сервис»'
        row = self.accepted(core, CORE_TEXT.replace(old, new))[5]
        self.assertIn(new, row['benefit_text'])
        row = self.accepted(core, CORE_TEXT.replace('+7 499-965-8083', '+7 (812) 345-67-89'))[5]
        self.assertIn('+7 (812) 345-67-89', row['conditions_text'])
        self.assertIn('participant_and_level_not_inferred', row['warnings'])

    def test_insurance_uses_and_expenses_vary_per_published_column(self):
        for old, new in [('1 (один) раз – 1 Промо-балл', '2 (два) раза – 4 Промо-балла'),
                         ('не более одной услуги', 'не более двух услуг'),
                         ('не более одной услуги', 'не более 11 услуг')]:
            with self.subTest(new=new):
                row = self.accepted(core, CORE_TEXT.replace(old, new))[8]
                self.assertIn(new, row['conditions_text'])
        pairs = ['2 (два) раза – 4 Промо-балла', '1 (один) раз – 3 Промо-балла',
                 '1 (один) раз – 1 Промо-балл', '3 (три) раза – 7 Промо-баллов']
        text = CORE_TEXT.replace('1 (один) раз – 1 Промо-балл.', ' '.join(pairs) + ' Не предоставляется. Услуга доступа к контенту Не предоставляется.')
        row = self.accepted(core, text)[8]
        for pair in pairs:
            self.assertIn(pair, row['conditions_text'])
        self.assertNotIn('Услуга доступа к контенту', row['conditions_text'])

    def test_cashback_category_and_cap_values_are_independent(self):
        for old, new in [('5 Категорий', '7 Категорий'), ('5 Категорий', '1 Категория'),
                         ('30 000 Альфа-Баллов', '40 000 Альфа-Баллов'),
                         ('50 000 Альфа-Баллов', '60 000 Альфа-Баллов'),
                         ('500 000 рублей', '600 000,50 рублей')]:
            with self.subTest(new=new):
                row = self.accepted(cashback, CASHBACK_TEXT.replace(old, new))
                self.assertIn(new, row['benefit_text'])
                self.assertIn('не персональные ставки', row['conditions_text'])
                self.assertEqual(row['id'], cashback()['id'])

    def test_repeated_insurance_expense_columns_do_not_create_a_reader_benefit(self):
        pair = '1 (один) раз – 1 Промо-балл'
        for copies in (1, 4, 7):
            with self.subTest(copies=copies):
                row = core(CORE_TEXT.replace(pair, ' '.join([pair] * copies)))[8]
                self.assertFalse(benefit_claim(row['conditions_text'].splitlines()[0]))
                visible, reason = record_row(project(row), NOW[:10])
                self.assertIsNone(visible)
                self.assertEqual(reason, 'нет конкретной выгоды')
        self.assertTrue(benefit_claim('Бесплатное страхование путешествий для участников программы.'))

    def test_cashback_retains_historical_context_and_ignores_next_package(self):
        text = CASHBACK_TEXT.replace('30 000 Альфа-Баллов', '15 000 АльфаБаллов (до февраля) 40 000 Альфа-Баллов (с марта)')
        text += ' ПУ «А-Клуб» 5 Категорий 30 000 Альфа-Баллов 50 000 Альфа-Баллов 900 000 рублей.'
        row = self.accepted(cashback, text)
        for fragment in ['15 000 АльфаБаллов (до февраля)', '40 000 Альфа-Баллов (с марта)']:
            self.assertIn(fragment, row['benefit_text'])
        self.assertNotIn('900 000', row['benefit_text'])
        self.assertNotIn('А-Клуб', row['benefit_text'])

    def test_invalid_money_tokens_cannot_be_replaced_with_other_clause_values(self):
        for invalid in ['1 00', '2.500.5', '-100', '−100', '100–200']:
            for old in ['такси, трансфер и каршеринг, но не более 2 500 рублей',
                        'БЗ составляет 20 000 рублей', 'РКБ составляет 20 000 рублей',
                        'от 6 000 000 рублей']:
                import re
                new = re.sub(r'\d[\d ]* рублей', invalid + ' рублей', old)
                with self.subTest(invalid=invalid, old=old), self.assertRaises(ValueError):
                    core(CORE_TEXT.replace(old, new))

    def test_first_malformed_cap_cannot_skip_to_a_later_valid_cap(self):
        for invalid in ['1 00', '-100', '100–200']:
            text = CORE_TEXT.replace('такси, трансфер и каршеринг, но не более 2 500 рублей',
                f'такси, трансфер и каршеринг, но не более {invalid} рублей; не более 2 500 рублей')
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                core(text)

    def test_duplicate_owned_clauses_fail_instead_of_choosing_one(self):
        for marker in ['Выплата – денежные средства', '6.6.7.', 'Телефон Партнера –']:
            line = next(line for line in CORE_TEXT.splitlines() if line.startswith(marker))
            with self.subTest(marker=marker), self.assertRaises(ValueError):
                core(CORE_TEXT + '\n' + line)
        line = next(line for line in CASHBACK_TEXT.splitlines() if line.startswith('УЛК'))
        with self.assertRaises(ValueError):
            cashback(CASHBACK_TEXT + '\n' + line)

    def test_related_payout_subjects_and_section_suffixes_do_not_duplicate_ownership(self):
        text = CORE_TEXT + '\nОперация становится доступной для получения Выплаты БЗ в течение 7 календарных дней.'
        text += '\n6.6.2. Получить Выплату БЗ по Расходной операции можно в рамках лимитов месяца.'
        rows = self.accepted(core, text)
        self.assertIn('2 рабочих дней', rows[0]['conditions_text'])
        self.assertNotIn('6.6.2.', rows[5]['benefit_text'])

    def test_lounge_cap_follows_the_non_numeric_list_heading(self):
        text = CORE_TEXT.replace('но не более 2 500 рублей за доступ',
            'но не более следующих сумм: при оплате доступа, не более 3 500 рублей за доступ')
        row = self.accepted(core, text)[1]
        self.assertIn('3 500 рублей за доступ', row['benefit_text'])

    def test_fractional_zero_and_ranged_counts_are_not_valid_suffixes(self):
        for invalid in ['1.5', '1 00', '-2', '0', '2–3']:
            for old, new in [('2 рабочих дней', invalid + ' рабочих дней'),
                             ('не более 3 лиц', 'не более ' + invalid + ' лиц'),
                             ('списании 2 Альфа-Баллов', 'списании ' + invalid + ' Альфа-Баллов')]:
                with self.subTest(old=old, invalid=invalid), self.assertRaises(ValueError):
                    core(CORE_TEXT.replace(old, new))

    def test_malformed_insurance_cell_cannot_fall_back_to_the_next_column(self):
        for invalid in ['1 00', '-2', '1.5', '0', '2–3']:
            pair = f'1 (один) раз – {invalid} Промо-баллов 1 (один) раз – 1 Промо-балл'
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                core(CORE_TEXT.replace('1 (один) раз – 1 Промо-балл', pair))

    def test_wrong_cashback_row_cannot_supply_missing_or_malformed_values(self):
        neighbour = ' ПУ «А-Клуб» 5 Категорий 30 000 Альфа-Баллов 50 000 Альфа-Баллов 500 000 рублей.'
        for invalid in ['1 00', '-40000', '30000–40000']:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                cashback(CASHBACK_TEXT.replace('30 000 Альфа-Баллов', invalid + ' Альфа-Баллов') + neighbour)
        with self.assertRaises(ValueError):
            cashback(CASHBACK_TEXT.replace('50 000 Альфа-Баллов', 'лимит неизвестен') + neighbour)


if __name__ == '__main__':
    unittest.main()
