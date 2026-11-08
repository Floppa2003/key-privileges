"""Changing numbers must not change the role of owned reader clauses."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from catalogue_clauses import benefit_claim, practical_terms
from catalogue_view import owned_source_text, record_row
from test_catalogue_view import record


class CatalogueValueChanges(unittest.TestCase):
    def row(self, benefit='Скидка 15% на меню', *, as_of='2026-11-08', **kw):
        kw.setdefault('conditions', '')
        kw.setdefault('activation', '')
        return record_row(record(benefit, **kw), as_of)[0]

    def test_flight_qualification_survives_count_substitution(self):
        for count in ('двух', 'трёх', 'пяти', '2', '17', '21', 'не менее пяти'):
            with self.subTest(count=count):
                clause=f'После совершения {count} перелётов можно оплатить билет бонусами.'
                general='Приветствуем участников программы.\n'+clause
                n=record('Скидка 15%', conditions=general,
                         details={'general_rules_excerpt':general, 'qualification':{'flights':count}})
                before=copy.deepcopy(n)
                self.assertIn(clause, owned_source_text(n['raw'])['conditions'])
                self.assertIn(clause, ' '.join(record_row(n, '2026-11-08')[0][2:6]))
                self.assertEqual(n, before)

    def test_flight_line_wrap_and_nbsp_keep_the_whole_condition(self):
        clause='После совершения\n17\u00a0перелетов можно оплатить билет бонусами.'
        n=record('Скидка 15%', conditions=clause,
                 details={'general_rules_excerpt':clause, 'qualification':{'flights':17}})
        row=record_row(n, '2026-11-08')[0]
        self.assertIn('После совершения 17 перелетов можно оплатить билет бонусами.', ' '.join(row[2:6]))

    def test_campaign_end_dates_are_relative_to_as_of_in_any_year(self):
        for year in (2025, 2026, 2027, 2031):
            for verb in ('действует', 'действовала', 'шла'):
                for end in (f'10.11.{year}', f'{year}-11-10', f'10 ноября {year}'):
                    with self.subTest(year=year, verb=verb, end=end):
                        conditions=f'Акция {verb} с 1 января {year} по {end}.'
                        self.assertIsNotNone(self.row(conditions=conditions, as_of=f'{year}-11-09'))
                        self.assertIsNotNone(self.row(conditions=conditions, as_of=f'{year}-11-10'))
                        self.assertIsNone(self.row(conditions=conditions, as_of=f'{year}-11-11'))

    def test_explicit_completion_does_not_need_a_known_year(self):
        for year in (2025, 2026, 2027, 2031):
            for status in ('Акция завершена', 'Акция завершилась', 'Акция закончилась', 'Срок акции уже истёк'):
                with self.subTest(year=year, status=status):
                    self.assertIsNone(self.row(conditions=f'{status} 10 ноября {year}.', as_of=f'{year}-11-11'))

    def test_start_only_date_never_establishes_expiry(self):
        for year in (2025, 2026, 2027, 2031):
            for verb in ('действует', 'действовала', 'шла'):
                with self.subTest(year=year, verb=verb):
                    self.assertIsNotNone(self.row(conditions=f'Акция {verb} с 1 января {year}.', as_of='2032-01-01'))

    def test_labelled_end_date_and_structured_expiry(self):
        self.assertIsNone(self.row(conditions='Срок проведения акции: до 31.12.2031.', as_of='2032-01-01'))
        self.assertIsNotNone(self.row(conditions='Срок действия акции: до 31.12.2031.', as_of='2031-12-31'))
        n=record(); n['validity']['status']='expired'
        self.assertIsNone(record_row(n, '2031-01-01')[0])

    def test_other_campaigns_and_conditional_completion_do_not_expire_offer(self):
        for value in (
            'Если акция завершилась, обратитесь в поддержку.',
            'Предыдущая акция действовала с 1 января 2025 по 10 ноября 2025.',
            'Акция не действует на алкоголь.',
            'Акция действует с 1 января 2025. Заказ нужно оплатить до 10 ноября 2025.',
        ):
            with self.subTest(value=value):
                self.assertIsNotNone(self.row(conditions=value, as_of='2026-11-08'))

    def test_bad_or_conflicting_end_dates_do_not_create_expiry(self):
        for value in (
            'Акция действует до 31.02.2025.',
            'Акция действует до 10.11.',
            'Акция действует с 20.11.2025 по 10.11.2025.',
            'Акция действует до 10.11.2025. Акция действует до 10.11.2031.',
        ):
            with self.subTest(value=value):
                self.assertIsNotNone(self.row(conditions=value))

    def test_free_form_end_conflicting_with_published_interval_stays_unknown(self):
        for year in (2025, 2026, 2027, 2031):
            with self.subTest(year=year):
                self.assertIsNotNone(self.row(conditions=f'Акция действует до 10.11.{year}.',
                    valid_until=f'{year+1}-02-01', as_of=f'{year}-11-11'))
                self.assertIsNone(self.row(conditions=f'Акция завершена досрочно 10 ноября {year}.',
                    valid_until=f'{year+1}-02-01', as_of=f'{year}-11-11'))

    def test_payment_percentages_are_conditions_not_benefits(self):
        for value in ('0', '25', '50', '75', '99', '100', '12,5', '37.5'):
            for template in ('Оплата {n}%', 'При условии предоплаты {n}%', '{n}% предоплата', 'Предоплата в размере {n} %'):
                claim=template.format(n=value)
                with self.subTest(claim=claim):
                    raw=record(claim, conditions='', activation='')['raw']
                    self.assertFalse(benefit_claim(claim, raw))
                    self.assertIsNone(self.row(claim))

    def test_real_discount_survives_changed_prepayment_condition(self):
        for value in ('25', '50', '75', '100', '12,5'):
            with self.subTest(value=value):
                claim=f'Скидка 15% при предоплате {value}%'
                self.assertEqual(self.row(claim)[2], claim)
                clause=f'При условии предоплаты {value}%.'
                row=self.row('Скидка 15%', conditions=clause)
                self.assertIn(clause, row[5])
        self.assertEqual(self.row('Возмещаем 50% оплаты')[2], 'Возмещаем 50% оплаты')

    def test_promotional_addon_price_does_not_depend_on_one_ruble(self):
        for price, minimum in (('1', '1190'), ('2', '1490'), ('9', '2100'), ('15,5', '2 750')):
            with self.subTest(price=price):
                claim=f'Пицца «Ветчина и грибы» 25 см за {price} рублей при заказе от {minimum} рублей'
                self.assertEqual(self.row(claim, activation='Введите код из SMS.')[2], claim)

    def test_trial_subscription_prices_do_not_depend_on_one_ruble(self):
        for price in ('1', '2', '9', '15.5'):
            for prefix in ('Первые 14 дней подписки', 'Пробный период подписки'):
                with self.subTest(price=price, prefix=prefix):
                    claim=f'{prefix} за {price} ₽'
                    self.assertEqual(self.row(claim)[2], claim)

    def test_price_with_own_code_activation_is_promotional(self):
        for price in ('1', '2', '9', '15,5'):
            for activation in ('Введите код из SMS.', 'Примените промокод в корзине.'):
                with self.subTest(price=price, activation=activation):
                    claim=f'Подписка на 30 дней за {price} рублей'
                    self.assertEqual(self.row(claim, activation=activation)[2], claim)

    def test_ordinary_price_is_not_automatically_a_benefit(self):
        for price in ('1', '2', '9', '499'):
            for claim in (f'Товар за {price} рублей', f'Подписка за {price} рублей в месяц'):
                with self.subTest(claim=claim):
                    self.assertIsNone(self.row(claim))
                    self.assertIsNone(self.row(claim, activation='Не используйте промокод.'))
                    self.assertIsNone(self.row(claim, details={'unrelated':{'activation':'Введите промокод.'}}))

    def test_malformed_promotional_price_is_not_recovered_as_suffix(self):
        for price in ('-1', '−2', '1 00', '1..5', '1—5'):
            with self.subTest(price=price):
                self.assertIsNone(self.row(f'Первые 14 дней подписки за {price} рублей'))

    def test_purchase_minimum_does_not_make_an_ordinary_cost_a_reward(self):
        for price in ('1', '2', '99', '499'):
            with self.subTest(price=price):
                self.assertIsNone(self.row(f'Доставка за {price} рублей при заказе от 1500 рублей'))

    def test_code_for_a_different_component_does_not_own_subscription_price(self):
        clause='По промокоду действует скидка 10% на такси.'
        for price in ('1', '2', '299'):
            with self.subTest(price=price):
                row=self.row(f'Подписка за {price} рублей.', conditions=clause)
                self.assertEqual(row[2], clause)

    def test_trial_words_in_regular_price_do_not_establish_trial_benefit(self):
        for claim in ('После пробного периода подписка за 399 рублей в месяц.',
                      'Оплата пробного периода подписки за 399 рублей.',
                      'Не первые 14 дней подписки за 399 рублей.'):
            with self.subTest(claim=claim):
                self.assertIsNone(self.row(claim))
        self.assertIsNotNone(self.row('Оплатите заказ 300 бонусами.'))

    def test_literal_reimbursement_survives_plain_payment_cost_filter(self):
        for days, amount in ((7, '2 500'), (11, '3 750'), (21, '4 000')):
            with self.subTest(days=days, amount=amount):
                claim=(f'Выплата БЗ переводится в течение {days} рабочих дней с даты обращения '
                       f'в сумме операции оплаты посещения Бизнес-зала, но не более {amount} рублей за доступ одного лица.')
                self.assertIsNotNone(self.row(claim))
                self.assertIsNone(self.row(f'Оплата доступа в Бизнес-зал: {amount} рублей.'))

    def test_percentile_marketing_is_independent_of_rank(self):
        for rank in (90, 95, 98, 99):
            with self.subTest(rank=rank):
                self.assertEqual(practical_terms(f'Преподаватели {rank}-го процентиля помогают учиться.'), '')
        self.assertEqual(practical_terms('Преподаватели 99-го класса участвуют в программе.'),
                         'Преподаватели 99-го класса участвуют в программе.')


if __name__ == '__main__':
    unittest.main()
