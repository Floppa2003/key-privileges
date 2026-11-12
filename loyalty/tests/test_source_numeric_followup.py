"""Supported source values retain their service, period and complete token."""
import unittest

from test_source_numeric_invariance import GENERATIONS, rule, sample
from test_dom_card_boundaries import project


SIM_ARTICLE = '''<div class="article-content"><h2>Замена SIM-карты</h2>
<p>Стоимость услуги для физических лиц составляет 100 руб.</p>
<h3>Замена SIM-карты без обращения в салон</h3>
<p>Получить SIM-карту можно с помощью услуги «Курьерская доставка SIM-карты».
Стоимость услуги – 200 руб. Дополнительно оплачивается замена SIM-карты – 100 руб.</p>
<p>Для участников программы T2 Selection услуга предоставляется бесплатно.</p>
<h3>Другая услуга</h3><p>Стоимость услуги – 900 руб.</p></div>'''
STUDENT = '''<div class="post__text">РЖД Бонус. Студенты очной формы обучения
до 25 лет (включительно): скидка 17%. Как подключить скидку?
Активация в течение 7 рабочих дней, действует до 2 сентября следующего учебного года.</div>'''
GPB_PRICE = 'Бесплатно — 1 месяц, далее — 399 ₽ в месяц'


class SourceNumericFollowup(unittest.TestCase):
    def accepted(self, source, raw):
        try:
            return rule(source, raw)[0]
        except ValueError as exc:
            self.fail('Complete owned source value was rejected: ' + str(exc))

    def test_sim_prices_belong_to_the_courier_section(self):
        row = self.accepted('t2_sim_rules', SIM_ARTICLE)
        fees = row['details']['fees']
        self.assertEqual((fees['delivery_standard_rub'], fees['replacement_rub'],
                          fees['delivery_selection_rub']), ('200', '100', '0'))
        self.assertIn('для физических лиц составляет 100 руб.', row['conditions_text'])
        self.assertIn('Стоимость услуги – 900 руб.', row['conditions_text'])
        self.assertEqual(project(row)['raw']['details']['fees'], fees)

    def test_sim_changed_prices_remain_independent_of_other_services(self):
        raw = SIM_ARTICLE.replace('– 200 руб.', '– 299,50 руб.').replace(
            'SIM-карты – 100 руб.', 'SIM-карты – 149.75 руб.')
        row = self.accepted('t2_sim_rules', raw)
        self.assertEqual(row['details']['fees']['delivery_standard_rub'], '299.5')
        self.assertEqual(row['details']['fees']['replacement_rub'], '149.75')
        self.assertEqual(row['id'], self.accepted('t2_sim_rules', SIM_ARTICLE)['id'])

    def test_sim_missing_or_conflicting_courier_value_cannot_borrow_another_section(self):
        for replacement in ['', 'Стоимость услуги – -200 руб.',
                            'Стоимость услуги – 200 руб. Стоимость услуги – 300 руб.']:
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                rule('t2_sim_rules', SIM_ARTICLE.replace('Стоимость услуги – 200 руб.', replacement))

    def test_sim_selection_free_statement_must_belong_to_the_same_service(self):
        free = '<p>Для участников программы T2 Selection услуга предоставляется бесплатно.</p>'
        raw = SIM_ARTICLE.replace(free, '').replace('</div>', free + '</div>')
        with self.assertRaises(ValueError):
            rule('t2_sim_rules', raw)

    def test_mileage_multiplier_keeps_its_complete_decimal_value(self):
        for literal, expected in [('1,5-кратные', '1.5'), ('2.5-кратные', '2.5'),
                                  ('12-кратные', '12'), ('1\u202f500-кратные', '1500')]:
            with self.subTest(literal=literal):
                row = self.accepted('utair_generations_rules',
                    GENERATIONS.replace('двойные мили', literal + ' мили'))
                self.assertEqual(str(row['details']['reward_multiplier']), expected)
                self.assertEqual([(b['value'], b['unit']) for b in project(row)['benefits']
                                  if b['kind'] == 'reward_multiplier'], [(expected, 'multiplier')])
                self.assertIn(literal.replace('\u202f', ' '), row['details']['reward_multiplier_evidence'])

    def test_invalid_numeric_multiplier_cannot_be_salvaged_as_a_positive_suffix(self):
        for token in ['-2', '− 2', '+2', '+ 2', '0', '12–15', '1 00', '1.500.5']:
            with self.subTest(token=token), self.assertRaises(ValueError):
                rule('utair_generations_rules', GENERATIONS.replace('двойные мили', token + '-кратные мили'))

    def test_conflicting_multiplier_is_rejected_but_repeated_identical_factor_is_preserved(self):
        for phrase in ['тройные мили', '3-кратные мили', '-2-кратные мили']:
            raw = GENERATIONS.replace('двойные мили.', 'двойные мили. ' + phrase + '.')
            with self.subTest(phrase=phrase), self.assertRaises(ValueError):
                rule('utair_generations_rules', raw)
        row = self.accepted('utair_generations_rules',
            GENERATIONS.replace('двойные мили.', 'двойные мили. Двойные мили.'))
        self.assertEqual(row['details']['reward_multiplier'], 2)

    def test_student_age_and_activation_inflections_follow_changed_counts(self):
        for age, days, noun in [(21, 1, 'рабочего дня'), (22, 21, 'рабочего дня'),
                                (31, 3, 'рабочих дней')]:
            raw = STUDENT.replace('25 лет', f'{age} года').replace('7 рабочих дней', f'{days} {noun}')
            with self.subTest(age=age, days=days):
                row = self.accepted('rzd_student_rules', raw)
                self.assertEqual(row['details']['age_max_inclusive'], age)
                self.assertEqual(row['details']['activation_workdays'], days)
                self.assertIsNone(row['valid_until'])

    def test_utair_age_forms_keep_each_audience(self):
        raw = GENERATIONS.replace('25 лет', '21 года').replace('55 лет', '61 года').replace('60 лет', '62 лет')
        audiences = self.accepted('utair_generations_rules', raw)['details']['audiences']
        self.assertEqual((audiences[0]['age_min'], audiences[0]['age_max']), (16, 21))
        self.assertEqual((audiences[1]['women_age_min'], audiences[1]['men_age_min']), (61, 62))

    def test_age_and_duration_fields_reject_nonpositive_or_fractional_counts(self):
        for token in ['0', '1,5', '− 2', '2–3', '1 00']:
            for source, raw in [
                ('rzd_student_rules', STUDENT.replace('25 лет', token + ' лет')),
                ('rzd_student_rules', STUDENT.replace('7 рабочих дней', token + ' рабочих дней')),
                ('utair_generations_rules', GENERATIONS.replace('25 лет', token + ' лет')),
                ('utair_generations_rules', GENERATIONS.replace('55 лет', token + ' лет')),
            ]:
                with self.subTest(source=source, token=token), self.assertRaises(ValueError):
                    rule(source, raw)

    def test_youth_interval_must_not_be_reversed(self):
        with self.assertRaises(ValueError):
            rule('utair_generations_rules', GENERATIONS.replace('от 16 до 25 лет', 'от 26 до 25 лет'))

    def test_subscription_introductory_and_ongoing_prices_keep_their_periods(self):
        for price, months, later, first_value, later_value in [
            ('99', 1, '399', '99', '399'), ('49,50', 3, '599.75', '49.5', '599.75')
        ]:
            literal = f'{price} ₽ в месяц — {months} месяц' + ('а' if months == 3 else '')
            raw = sample().replace(GPB_PRICE, literal + f', далее — {later} ₽ в месяц')
            with self.subTest(price=price):
                row = self.accepted('af_gpb_rules', raw)
                option = row['details']['mileage_options'][1]
                self.assertEqual(option['monthly_subscription_rub'], later_value)
                intro = option['introductory_subscription']
                self.assertEqual((intro['monthly_rub'], intro['months']), (first_value, months))
                self.assertIn(literal, intro['evidence'])
                costs = [c for c in project(row)['costs'] if c['kind'] == 'subscription_cost'
                         and c['scope'].get('option') == option['label']]
                self.assertEqual({(c['value'], c['scope'].get('subscription_phase')) for c in costs},
                                 {(first_value, 'introductory'), (later_value, 'ongoing')})
                first = next(c for c in costs if c['scope']['subscription_phase'] == 'introductory')
                self.assertEqual(first['scope']['duration_months'], months)

    def test_free_introduction_and_unconditional_free_option_remain_distinct(self):
        options = self.accepted('af_gpb_rules', sample())['details']['mileage_options']
        self.assertEqual(options[0]['monthly_subscription_rub'], '0')
        self.assertNotIn('introductory_subscription', options[0])
        self.assertEqual(options[1]['monthly_subscription_rub'], '399')
        self.assertIn('introductory_subscription', options[1])
        self.assertEqual(options[1]['introductory_subscription']['monthly_rub'], '0')
        self.assertEqual(options[1]['introductory_subscription']['months'], 1)

    def test_subscription_cannot_rescue_bad_or_ambiguous_prices_with_another_phase(self):
        for literal in [
            '99 ₽ в месяц — 1 месяц, далее — -399 ₽ в месяц',
            '99 ₽ в месяц — 1 месяц, далее — 1 00 ₽ в месяц',
            '-99 ₽ в месяц — 1 месяц, далее — 399 ₽ в месяц',
            '99 ₽ в месяц — 0 месяцев, далее — 399 ₽ в месяц',
            '99 ₽ в месяц, 399 ₽ в месяц',
            '99 ₽ в месяц — 1 месяц, далее — 399 ₽ в месяц, далее — 599 ₽ в месяц',
        ]:
            with self.subTest(literal=literal), self.assertRaises(ValueError):
                rule('af_gpb_rules', sample().replace(GPB_PRICE, literal))


if __name__ == '__main__':
    unittest.main()
