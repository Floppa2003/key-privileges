"""Numerical offer edits preserve full values, units and source ownership."""
import sys
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parents[1]))
from known_rules import parse_known_rule, CONFIG as RULES
from known_pdf import parse_pdf_pages
from partner_pages import extract_partner_page, CONFIG as PARTNERS
from tier_sources import ural_tiers, utair_tab
from x5_partners import detail as x5_detail
from test_public_product_rules import sample
import test_known_rules as rule_fixtures
from test_known_pdf import FIN, PRIM
from test_tier_sources import URAL, HEADER
from test_dom_card_boundaries import project

NOW = '2026-09-14T00:00:00+00:00'
SIM = '''<div class="article-content">Замена SIM. Курьерская доставка SIM-карты.
Стоимость услуги – 200 руб. Дополнительно оплачивается замена SIM-карты – 100 руб.
Для участников программы T2 Selection услуга предоставляется бесплатно.</div>'''
FAMILY = '''<div id="rec774881902">Семья, совместное использование миль</div>
<div id="rec774882054">Объедините до 7 счетов. Покинуть Семью можно через 6 месяцев.
Как минимум 299 рублей оплачиваются банковской картой.</div>'''
IWAY = '''<main><div class="promo">Аэрофлот Бонус.<div class="condition_earn">
Накопить мили. При заказе через турагентство 1 миля за каждые потраченные 90 ₽.
При заказе поездки в i’way 1 миля за каждые потраченные 50 ₽.</div>
Использовать мили: корпоративные поездки исключены.</div></main>'''
GENERATIONS = '''<div id="rec586475392">Поколения Utair - двойные мили.
Молодежь от 16 до 25 лет, от 55 лет (для женщин), от 60 лет (для мужчин).</div>
<div id="rec586348980">для молодежи UYOUTHWM; для людей старшего поколения UPENSWM.
Срок действия миль составляет 3 года. Покупка и полет в одном месяце.</div>'''
X5_RULE = '''<main><div class="w-full"><h2>О партнёре</h2><p>Аэрофлот Бонус</p></div>
<div class="w-full"><h2>Как воспользоваться?</h2><p>20 миль за каждые 500 баллов.</p></div>
<div class="w-full"><h2>Условия предложения</h2><p>Акция действует до 31 декабря 2026 года.</p></div></main>'''


def rule(source, raw):
    return parse_known_rule(source, raw, RULES[source]['url'], NOW)


def pdf(source, pages):
    return parse_pdf_pages(source, pages, NOW, document_sha256='f' * 64)


def change(pages, old, new):
    return [p.replace(old, new) for p in pages]


def exchange(ratio):
    card = dict(idOffer=222, nameOffer='Обмен баллов на мили', namePartnerOffer='Аэрофлот Бонус',
                cost=500, type='exchange', startDate='2026-06-04 00:00:00', endDate='2026-12-31 23:59:59')
    raw = f'''<main><div><h2>{card['nameOffer']}</h2><h3>Аэрофлот Бонус</h3>
    <p>Действует 04.06.2026 - 31.12.2026</p></div><div><h2>О партнёре</h2><p>{ratio}</p></div>
    <div><h2>Как воспользоваться?</h2><p>Укажите номер участника программы.</p></div>
    <div><h2>Условия предложения</h2><p>Списанные баллы не возвращаются.</p></div></main>'''
    return x5_detail(raw, card, 'Путешествия', NOW)


class SourceNumericInvariance(unittest.TestCase):
    def accepted(self, fn, *args):
        try:
            return fn(*args)
        except ValueError as exc:
            self.fail(f'Complete changed value rejected: {exc}')

    def test_gpb_decimal_service_and_grouped_basis_are_independent(self):
        for old, new, field, expected in (
            ('Стоимость обслуживания 0 ₽', 'Стоимость обслуживания 199,50 ₽', 'fee', '199.5'),
            ('за 100 ₽', 'за 1 500 ₽', 'basis', '1500'),
            ('за 100 ₽', 'за 1\u202f500,50 ₽', 'basis', '1500.5'),
        ):
            with self.subTest(new=new):
                row = self.accepted(rule, 'af_gpb_rules', sample().replace(old, new))[0]
                d = row['details']
                self.assertEqual(d['fees']['card_service_rub'] if field == 'fee'
                                 else d['mileage_options'][0]['basis_rub'], expected)
                self.assertEqual(d['mileage_options'][0]['miles'], '1.5')
                self.assertEqual(row['id'], rule('af_gpb_rules', sample())[0]['id'])
                self.assertEqual(project(row)['raw']['details']['mileage_options'], d['mileage_options'])
                self.assertEqual(project(row)['raw']['details']['fees'], d['fees'])

    def test_sim_decimal_prices_do_not_change_free_selection_delivery(self):
        for old, new, field in [('200 руб', '299,50 руб', 'delivery_standard_rub'),
                                ('100 руб', '149.75 руб', 'replacement_rub')]:
            with self.subTest(field=field):
                d = self.accepted(rule, 't2_sim_rules', SIM.replace(old, new))[0]['details']['fees']
                self.assertEqual(d[field], '299.5' if field == 'delivery_standard_rub' else '149.75')
                self.assertEqual(d['delivery_selection_rub'], '0')

    def test_family_money_and_count_inflections(self):
        row = self.accepted(rule, 'utair_family_rules', FAMILY.replace('299 рублей', '349,50 рублей'))[0]
        self.assertEqual(row['details']['miles_payment']['minimum_cash_rub'], '349.5')
        for old, new, key, expected in [('7 счетов', '1 счет', 'max_accounts', 1),
                                       ('6 месяцев', '3 месяца', 'minimum_membership_months', 3)]:
            with self.subTest(new=new):
                row = self.accepted(rule, 'utair_family_rules', FAMILY.replace(old, new))[0]
                self.assertEqual(row['details']['family'][key], expected)

    def test_iway_fractional_miles_stay_with_own_channel(self):
        raw = IWAY.replace('i’way 1 миля', 'i’way 1,5 мили')
        row = self.accepted(rule, 'af_iway_rules', raw)[0]
        rates = {r['channel']: (r['value'], r['basis_amount']) for r in row['details']['earning_rules']}
        self.assertEqual(rates, {'direct': ('1.5', '50'), 'travel_agent': ('1', '90')})

    def test_smartavia_decimal_discounts_and_count_inflections(self):
        original = rule_fixtures.SmartaviaTests().fixture()
        changes = [('скидкой 200 ₽', 'скидкой 249,50 ₽', 'flight_discount_rub', '249.5'),
                   ('скидкой 300 ₽', 'скидкой 349.50 ₽', 'baggage_discount_rub', '349.5'),
                   ('10 сегментов', '3 сегмента', 'flight_segments', 3),
                   ('10 услуг', '1 услуга', 'baggage_services', 1)]
        for old, new, key, expected in changes:
            with self.subTest(new=new):
                row = self.accepted(rule, 'smartavia_rules', original.replace(old, new))[0]
                self.assertEqual(row['details']['subscription_plan'][key], expected)
                self.assertEqual(row['details']['subscription_plan']['annual_rub'], '1190')
        rows = self.accepted(rule, 'smartavia_rules', original.replace('скидкой 20%.', 'скидкой 12,5%.'))
        self.assertEqual(rows[-1]['details']['discount_percent'], '12.5')

    def test_reward_lifetime_accepts_year_inflections_without_offer_expiry(self):
        for value, word in [(1, 'год'), (5, 'лет'), (21, 'год')]:
            with self.subTest(value=value):
                row = self.accepted(rule, 'utair_generations_rules', GENERATIONS.replace('3 года', f'{value} {word}'))[0]
                self.assertEqual(row['details']['reward_lifetime_years'], value)
                self.assertIsNone(row['valid_until'])

    def test_changed_multiplier_has_no_stale_double_miles_title(self):
        row = rule('utair_generations_rules', GENERATIONS.replace('двойные мили', 'тройные мили'))[0]
        self.assertEqual(row['details']['reward_multiplier'], 3)
        self.assertNotIn('двойн', row['title'].lower())

    def test_finuslugi_month_inflections_preserve_each_tier(self):
        for value, word in [(3, 'календарных месяца'), (6, 'календарных месяцев')]:
            pages = change(FIN, '1 (один) календарный месяц', f'{value} (по условиям) {word}')
            row = self.accepted(pdf, 'rzd_finuslugi_rules', pages)
            self.assertEqual([r['term_min_months'] for r in row['details']['deposit_reward_tiers']], [value] * 3)
            self.assertEqual(row['details']['deposit_reward_tiers'][0]['points'], '1850')

    def test_primbank_fractional_rate_and_money_preserve_tier(self):
        for old, new, key, expected in [('1 миля при', '1,5 мили при', 'miles', '1.5'),
                                       ('1 миля при', '5 миль при', 'miles', '5'),
                                       ('от 10 000 руб.', 'от 10 000,50 руб.', 'monthly_spend_from_rub', '10000.5')]:
            with self.subTest(new=new):
                row = self.accepted(pdf, 'af_primbank_rules', change(PRIM, old, new))
                self.assertEqual(row['details']['spend_reward_tiers'][0][key], expected)
                self.assertEqual(row['details']['spend_reward_tiers'][1]['miles'], '2')
                self.assertEqual(project(row)['raw']['details']['spend_reward_tiers'], row['details']['spend_reward_tiers'])

    def test_domina_decimal_miles_and_basis(self):
        original = (Path(__file__).parent / 'fixtures_live/nordwind_domina.html').read_text()
        for old, new, key, expected in [('>1 миля<', '>1.5 мили<', 'value', '1.5'),
                                       ('>1 миля<', '>5 миль<', 'value', '5')]:
            with self.subTest(new=new):
                self.assertIn(old, original)
                rows = self.accepted(extract_partner_page, 'nordwind_domina',
                    BeautifulSoup(original.replace(old, new), 'html.parser'), PARTNERS['nordwind_domina']['url'], NOW)
                self.assertEqual(rows[0]['details']['earning_rule'][key], expected)

    def test_x5_mile_inflections_survive_rules_and_native_detail(self):
        for value, word, expected in [('1', 'миля', '1'), ('2', 'мили', '2'), ('1,5', 'мили', '1.5'), ('1 500', 'миль', '1500')]:
            ratio = f'{value} {word} за каждые 500 баллов'
            with self.subTest(ratio=ratio):
                row = self.accepted(rule, 'af_x5_rules', X5_RULE.replace('20 миль за каждые 500 баллов', ratio))[0]
                self.assertEqual(row['details']['exchange_rule']['miles'], expected)
                detail = exchange(ratio)
                self.assertIn(ratio, detail['benefit_text'])
                self.assertIn(ratio, str(project(detail)))

    def test_ural_full_flight_counts_and_window_years(self):
        for value, word, expected in [('1 500', 'полетов', 1500), ('1\u202f500', 'полётов', 1500), ('1', 'полет', 1)]:
            with self.subTest(value=value):
                row = self.accepted(ural_tiers, URAL.replace('15 полетов', f'{value} {word}'), NOW)[1]
                self.assertEqual(row['details']['qualification']['flights'], expected)
                self.assertEqual(row['details']['qualification']['spend_rub'], '200000')
                self.assertEqual(row['details']['tier'], 'Серебряный')
        for value, noun in [(1, 'года'), (2, 'лет'), (21, 'года'), (101, 'года')]:
            with self.subTest(years=value):
                row = self.accepted(ural_tiers, URAL.replace('1 календарного года', f'{value} календарных {noun}'), NOW)[1]
                q = row['details']['qualification']
                self.assertEqual(q.get('window_years'), value)
                self.assertEqual(q['window'], 'calendar_year' if value == 1 else None)

    def test_utair_grouped_thousands_preserve_full_money(self):
        for value, expected in [('1 000', '1000000'), ('1\u00a0000,5', '1000500'), ('25,5', '25500')]:
            with self.subTest(value=value):
                result = utair_tab(HEADER.replace('10 тыс.', value + ' тыс.'), 'Basic')
                self.assertEqual(result['spend_rub'], expected)
                self.assertEqual(result['window'], 'calendar_year')

    def test_invalid_required_money_tokens_fail_without_suffix_salvage(self):
        for token in ['1 00', '1.500.5', '-10', '−10', '1–10']:
            for source, raw in [('af_gpb_rules', sample().replace('Стоимость обслуживания 0 ₽', f'Стоимость обслуживания {token} ₽')),
                                ('t2_sim_rules', SIM.replace('200 руб', f'{token} руб')),
                                ('utair_family_rules', FAMILY.replace('299 рублей', f'{token} рублей'))]:
                with self.subTest(source=source, token=token), self.assertRaises(ValueError):
                    rule(source, raw)

    def test_fractional_or_invalid_counts_cannot_become_integer_suffixes(self):
        for token in ['0.5', '-5', '−5', '1–5', '1 00', '0']:
            with self.subTest(source='ural', token=token), self.assertRaises(ValueError):
                ural_tiers(URAL.replace('15 полетов', token + ' полетов'), NOW)
            with self.subTest(source='years', token=token), self.assertRaises(ValueError):
                rule('utair_generations_rules', GENERATIONS.replace('3 года', token + ' года'))
            with self.subTest(source='smartavia', token=token), self.assertRaises(ValueError):
                rule('smartavia_rules', rule_fixtures.SmartaviaTests().fixture().replace('10 сегментов', token + ' сегментов'))

    def test_malformed_primbank_rate_cannot_recover_valid_suffix(self):
        for token in ['1.500.5', '1 00', '-5', '−5', '1–5']:
            with self.subTest(token=token), self.assertRaises(ValueError):
                pdf('af_primbank_rules', change(PRIM, '1 миля при', token + ' мили при'))

    def test_unsupported_utair_number_never_produces_a_threshold(self):
        for token in ['1 00', '1.500.5', '-10', '1–10']:
            with self.subTest(token=token):
                try:
                    result = utair_tab(HEADER.replace('10 тыс.', token + ' тыс.'), 'Basic')
                except ValueError:
                    continue
                self.assertIsNone(result['spend_rub'])


if __name__ == '__main__':
    unittest.main()
