"""Independent-review counterexamples at real source and reader boundaries."""
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from test_avolta_quantity_invariance import record, common, source, NOW as AVOLTA_NOW
from test_source_numeric_invariance import (
    rule, pdf, change, sample, SIM, FAMILY, IWAY, FIN, PRIM, URAL, NOW,
    ural_tiers, extract_partner_page, PARTNERS,
)
from test_alfa_public_value_invariance import core, cashback, CORE_TEXT, CASHBACK_TEXT
from catalogue_clauses import benefit_claim
from catalogue_view import record_row
from x5_partners import exchange_line


class NumericInvarianceReview(unittest.TestCase):
    def test_cancelled_quantity_offers_do_not_reach_source_or_reader(self):
        for text in ['Отменена акция «3 по цене 2».',
                     'Акция «3 по цене 2» более не действует.',
                     'Акция «3 по цене 2 » не действует.',
                     'Завершена акция «3 по цене 2».',
                     'Акция «3 по цене 2 » уже отменена.']:
            with self.subTest(text=text):
                with self.assertRaises(source.ExcludedOffer):
                    record(text)
                self.assertFalse(benefit_claim(text))

    def test_local_restrictions_and_other_offer_cancellation_keep_live_bundle(self):
        for text in ['Акция «3 по цене 2 » более не действует на акционные товары.',
                     'Акция «3 по цене 2 » не суммируется с другими акциями.',
                     'Старая акция отменена. Акция «3 по цене 2» действует.',
                     'Отменена акция «5 по цене 4», но акция «3 по цене 2» действует.']:
            with self.subTest(text=text):
                visible, reason = record_row(common(record(text)), AVOLTA_NOW[:10])
                self.assertIsNone(reason)
                self.assertIn('3 по цене 2', visible[2])

    def test_quantity_offer_never_loses_a_spaced_sign(self):
        for sign in ['− ', '−\u00a0', '- ', '+ ']:
            text = f'Акция «{sign}3 по цене 2» на аттракционы.'
            with self.subTest(sign=sign):
                with self.assertRaises(source.ExcludedOffer):
                    record(text)
                self.assertFalse(benefit_claim(text))

    def test_pdf_rates_never_lose_a_spaced_sign(self):
        for sign in ['− ', '−\u00a0', '- ', '+ ']:
            with self.subTest(sign=sign), self.assertRaises(ValueError):
                pdf('af_primbank_rules', change(PRIM, '1 миля при', sign + '1 миля при'))

    def test_x5_exchange_never_loses_a_spaced_sign(self):
        for sign in ['− ', '−\u00a0', '- ', '+ ']:
            for line in [sign + '1 миля за каждые 500 баллов',
                         '1 миля за каждые ' + sign + '500 баллов']:
                with self.subTest(line=line):
                    self.assertFalse(exchange_line(line))

    def test_cashback_limits_never_lose_a_spaced_sign(self):
        for sign in ['− ', '−\u00a0', '- ', '+ ']:
            for value in ['30 000 Альфа-Баллов', '500 000 рублей']:
                with self.subTest(sign=sign, value=value), self.assertRaises(ValueError):
                    cashback(CASHBACK_TEXT.replace(value, sign + value))

    def test_structural_price_separators_remain_valid(self):
        for dash in ['–', '—', '-']:
            with self.subTest(dash=dash):
                fees = rule('t2_sim_rules', SIM.replace('–', dash))[0]['details']['fees']
                self.assertEqual(fees['delivery_standard_rub'], '200')
                rows = core(CORE_TEXT.replace('раз – 1 Промо', f'раз {dash} 1 Промо'))
                self.assertEqual(len(rows), 9)
                self.assertIn(f'раз {dash} 1 Промо-балл', rows[8]['conditions_text'])

    def test_gpb_service_label_cannot_choose_a_later_or_conflicting_price(self):
        for first in ['-100', '100', 'неизвестно']:
            raw = sample().replace('Стоимость обслуживания 0 ₽',
                f'Стоимость обслуживания {first} ₽. Стоимость обслуживания 199 ₽')
            with self.subTest(first=first), self.assertRaises(ValueError):
                rule('af_gpb_rules', raw)

    def test_sim_price_label_cannot_choose_a_later_or_conflicting_price(self):
        for first in ['-200', '200', 'неизвестно']:
            raw = SIM.replace('Стоимость услуги – 200 руб.',
                f'Стоимость услуги – {first} руб. Стоимость услуги – 300 руб.')
            with self.subTest(first=first), self.assertRaises(ValueError):
                rule('t2_sim_rules', raw)

    def test_family_bound_cannot_choose_a_later_or_conflicting_quantity(self):
        for first in ['-7', '7', 'неизвестного числа']:
            with self.subTest(first=first), self.assertRaises(ValueError):
                rule('utair_family_rules', FAMILY.replace('до 7 счетов', f'до {first} счетов, до 8 счетов'))

    def test_iway_channel_cannot_choose_a_later_or_conflicting_rate(self):
        original = 'При заказе поездки в i’way 1 миля за каждые потраченные 50 ₽.'
        for first in ['-1 миля', '1 миля', 'неизвестные мили']:
            replacement = (f'При заказе поездки в i’way {first} за каждые потраченные 50 ₽. '
                           'При заказе поездки в i’way 2 мили за каждые потраченные 50 ₽.')
            with self.subTest(first=first), self.assertRaises(ValueError):
                rule('af_iway_rules', IWAY.replace(original, replacement))

    def test_ural_qualification_cannot_choose_a_later_or_conflicting_quantity(self):
        for first in ['-15', '15', 'неизвестного числа']:
            raw = URAL.replace('при совершении 15 полетов',
                f'при совершении {first} полетов, при совершении 20 полетов')
            self.assertNotEqual(raw, URAL)
            with self.subTest(first=first), self.assertRaises(ValueError):
                ural_tiers(raw, NOW)

    def test_domina_card_cannot_choose_a_later_or_conflicting_rate(self):
        original = (Path(__file__).parent / 'fixtures_live/nordwind_domina.html').read_text()
        for first in ['-100', '100', 'неизвестные']:
            soup = BeautifulSoup(original, 'html.parser')
            for node in soup.select('section.section'):
                if 'Каждые' in node.get_text():
                    node.clear()
                    node.append('Nordwind Club. '
                        f'Каждые {first}₽, потраченные в Domina Пулково 1 миля. '
                        'Каждые 100₽, потраченные в Domina Пулково 1 миля.')
                    break
            else:
                self.fail('Missing original Domina earning card')
            with self.subTest(first=first), self.assertRaises(ValueError):
                extract_partner_page('nordwind_domina', soup, PARTNERS['nordwind_domina']['url'], NOW)

    def test_alfa_payout_label_cannot_skip_a_bad_or_conflicting_first_cap(self):
        for subject in ['БЗ', 'РКБ']:
            original = f'Максимальная сумма Выплаты {subject} составляет 20 000 рублей'
            for first in ['-10', '10', 'неизвестно']:
                replacement = (f'Максимальная сумма Выплаты {subject} составляет {first} рублей; '
                               f'максимальная сумма Выплаты {subject} составляет 20 000 рублей')
                with self.subTest(subject=subject, first=first), self.assertRaises(ValueError):
                    core(CORE_TEXT.replace(original, replacement))

    def test_alfa_dated_payout_clause_is_not_mistaken_for_a_new_section(self):
        text = CORE_TEXT.replace('Максимальная сумма Выплаты', 'С 01.03.2025 максимальная сумма Выплаты')
        rows = core(text)
        for index in (1, 2):
            self.assertIn('С 01.03.2025', rows[index]['conditions_text'])
            self.assertIn('20 000 рублей', rows[index]['conditions_text'])

    def test_alfa_lounge_person_basis_is_literal_and_changes_independently(self):
        for phrase in ['двух лиц', '2 лиц', 'двадцати одного лица', '21 лица']:
            text = CORE_TEXT.replace('за доступ одного лица', 'за доступ ' + phrase)
            with self.subTest(phrase=phrase):
                rows = core(text)
                self.assertEqual(len(rows), 9)
                self.assertIn('за доступ ' + phrase, rows[1]['benefit_text'])
                self.assertIn('2 500 рублей', rows[1]['benefit_text'])

    def test_alfa_payout_participant_and_month_bases_are_not_one_only(self):
        for old, new in [('на одного Участника', 'на двух Участников'),
                         ('на одного Участника', 'на 2 Участников'),
                         ('за один календарный месяц', 'за два календарных месяца'),
                         ('за один календарный месяц', 'за 2 календарных месяца'),
                         ('за один календарный месяц', 'за пять календарных месяцев')]:
            with self.subTest(new=new):
                rows = core(CORE_TEXT.replace(old, new))
                for index in (1, 2):
                    self.assertIn(new, rows[index]['conditions_text'])
                    self.assertIn('20 000 рублей', rows[index]['conditions_text'])

    def test_alfa_payout_bases_reject_incomplete_or_nonpositive_counts(self):
        for token in ['0', '1,5', '− 2', '2–3', 'сто два', 'неизвестно']:
            for old, new in [('одного лица', token + ' лиц'),
                             ('одного Участника', token + ' Участников'),
                             ('один календарный месяц', token + ' календарных месяца')]:
                with self.subTest(token=token, old=old), self.assertRaises(ValueError):
                    core(CORE_TEXT.replace(old, new))

    def test_finuslugi_points_and_days_follow_number_inflections(self):
        for value, noun in [('1851', 'балл'), ('1852', 'балла')]:
            with self.subTest(noun=noun):
                row = pdf('rzd_finuslugi_rules', change(FIN, '1850 баллов только', f'{value} {noun} только'))
                self.assertEqual(row['details']['deposit_reward_tiers'][0]['points'], value)
        row = pdf('rzd_finuslugi_rules', change(FIN, '90 календарных дней', '21 календарного дня'))
        self.assertEqual(row['details']['credit_wait_days'], 21)

    def test_finuslugi_deposit_money_preserves_decimal_bounds(self):
        pages = change(FIN, '10 000 (десяти тысяч)', '10 000,50 (десяти тысяч рублей и пятидесяти копеек)')
        pages = change(pages, '199 999 (ста девяноста девяти тысяч)', '199 999,75 (по условиям)')
        row = pdf('rzd_finuslugi_rules', pages)
        tier = row['details']['deposit_reward_tiers'][0]
        self.assertEqual((tier['deposit_min_rub'], tier['deposit_max_rub']), ('10000.5', '199999.75'))
        self.assertEqual(tier['term_min_months'], 1)
        self.assertIn('10 000,50', tier['evidence'])
        with self.assertRaises(ValueError):
            pdf('rzd_finuslugi_rules', change(pages, '199 999,75', '10 000,49'))

    def test_primbank_mile_cap_and_welcome_inflections_follow_number(self):
        for cap, unit, welcome, form in [('9 001', 'миля', '501', 'приветственная миля'),
                                        ('9 002', 'мили', '502', 'приветственные мили')]:
            pages = change(PRIM, '9 000 миль', cap + ' ' + unit)
            pages = change(pages, '500 приветственных миль', welcome + ' ' + form)
            with self.subTest(cap=cap):
                row = pdf('af_primbank_rules', pages)
                self.assertEqual(row['details']['monthly_miles_cap'], cap.replace(' ', ''))
                self.assertEqual(row['details']['welcome_miles'], welcome)
                self.assertIn(welcome + ' ' + form, row['benefit_text'])


if __name__ == '__main__':
    unittest.main()
