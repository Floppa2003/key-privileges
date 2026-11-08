"""Whole-branch review cases: validate the owned expression, not a valid remnant."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from catalogue_view import record_row
from unified_normalization import normalize_record, validate_normalized
from test_catalogue_view import record
from test_known_rules import RETAIL
from test_known_rule_value_changes import parse as retail, published_input
from test_alfa_partner_value_changes import source, parse as alfa


class NumericReviewRegressions(unittest.TestCase):
    def test_retail_rejects_complete_malformed_or_ranged_percent_expressions(self):
        for original in ('30%', '70%'):
            for expression in ('25%–50%', '25% до 50%', '25%%', '25%..5%',
                               '25%/50%', '25%+5%', '25%50%', '25%—до 50%'):
                with self.subTest(original=original, expression=expression):
                    with self.assertRaises(ValueError):
                        retail('af_bootwood_rules', RETAIL.replace(original, expression))

    def test_retail_invalid_first_clause_is_not_rescued_by_a_valid_later_one(self):
        for old, new in (
            ('не более 30%', 'не более -5%, не более 25%'),
            ('При этом 70%', 'При этом -5%, При этом 75%'),
        ):
            with self.subTest(new=new):
                with self.assertRaises(ValueError):
                    retail('af_bootwood_rules', RETAIL.replace(old,new))

    def test_cached_retail_percentages_are_rederived_from_the_owned_evidence(self):
        for cap,cash in (('45','55'), ('25,5','74,5'), ('7.5','92.5')):
            with self.subTest(cap=cap,cash=cash):
                raw=published_input(retail('af_bootwood_rules',RETAIL))
                raw['conditions']=raw['conditions'].replace('30%',cap+'%').replace('70%',cash+'%')
                red=raw['details']['redemption_rules']
                red['evidence']=red['evidence'].replace('30%',cap+'%').replace('70%',cash+'%')
                before=copy.deepcopy(raw)
                n=normalize_record(raw,as_of='2026-11-08');validate_normalized(n)
                self.assertEqual(raw,before);self.assertEqual(n['raw'],before)
                self.assertEqual(next(b['value'] for b in n['benefits'] if b['kind']=='redeem_rewards'),cap.replace(',','.'))
                self.assertEqual(next(c['value'] for c in n['conditions'] if c['kind']=='minimum_cash_payment'),cash.replace(',','.'))
                projected=next(c['scope']['source_value'] for c in n['conditions'] if c['kind']=='redemption_rules')
                self.assertEqual(projected['max_order_percent'],cap.replace(',','.'))
                self.assertEqual(projected['minimum_cash_percent'],cash.replace(',','.'))
                self.assertEqual(n['raw']['details']['redemption_rules']['max_order_percent'],'30')

    def test_cached_retail_projection_rejects_malformed_literal_percentages(self):
        for expression in ('25%–50%','25%%','25%..5%'):
            with self.subTest(expression=expression):
                raw=published_input(retail('af_bootwood_rules',RETAIL))
                raw['conditions']=raw['conditions'].replace('30%',expression)
                red=raw['details']['redemption_rules']
                red['evidence']=red['evidence'].replace('30%',expression)
                with self.assertRaises(ValueError):normalize_record(raw,as_of='2026-11-08')

    def test_payment_inflections_and_percentage_adjectives_are_not_benefits(self):
        for amount in ('25','50','75','100','12,5'):
            for template in ('При предоплате {n}%', 'При оплате {n}%',
                             'Оплатите {n}% стоимости', 'Оплачивается {n}%',
                             '{n}%-ная предоплата', '{n}%–ная предоплата'):
                claim=template.format(n=amount)
                with self.subTest(claim=claim):
                    self.assertIsNone(record_row(record(claim,conditions='',activation=''),'2026-11-08')[0])
        for claim in ('Скидка 15% при предоплате 50%','Возмещаем 50% оплаты'):
            self.assertEqual(record_row(record(claim,conditions='',activation=''),'2026-11-08')[0][2],claim)

    def test_paid_purchase_qualifier_does_not_hide_its_earned_percentage(self):
        for label in ('Оплаченный заказ нового клиента', 'Оплаченная бронь отеля',
                      'Оплаченное и прожитое бронирование отеля (РФ)'):
            for amount in ('2.4', '5.9', '12,5'):
                with self.subTest(label=label,amount=amount):
                    claim=f'Уровень 1 — Новичок / {label}: {amount}% бонусами'
                    row=record_row(record(claim,conditions='',activation=''),'2026-11-08')[0]
                    self.assertIsNotNone(row)
                    self.assertEqual(row[2],claim)

    def test_later_regular_price_cannot_rescue_an_invalid_promotional_price(self):
        for price in ('-2','−2','1–5','1%','1 00','1.5.0','1e1'):
            for activation in ('','Введите код из SMS.'):
                with self.subTest(price=price,activation=activation):
                    claim=f'Первые 14 дней подписки за {price} рублей, далее за 399 рублей.'
                    self.assertIsNone(record_row(record(claim,conditions='',activation=activation),'2026-11-08')[0])

    def test_trial_duration_is_a_positive_valid_literal(self):
        for days in ('1.5.0','1 00','-2','0','1–5'):
            with self.subTest(days=days):
                claim=f'Первые {days} дней подписки за 9 рублей.'
                self.assertIsNone(record_row(record(claim,conditions='',activation=''),'2026-11-08')[0])

    def test_code_activated_price_cannot_skip_an_invalid_first_price(self):
        for price in ('-2','1–5','1 00','1.5.0'):
            with self.subTest(price=price):
                claim=f'Подписка за {price} рублей, далее за 399 рублей.'
                self.assertIsNone(record_row(record(claim,conditions='',activation='Введите код из SMS.'),'2026-11-08')[0])
        claim='Первые 14 дней подписки за 9 рублей, далее за 399 рублей.'
        self.assertEqual(record_row(record(claim,conditions='',activation=''),'2026-11-08')[0][2],claim)

    def test_alfa_cap_must_be_unambiguous_even_if_a_later_cap_is_valid(self):
        for cap in ('-500 Альфа-Баллов/ Бонусных Миль и не более 2 500',
                    '1 500 Альфа-Баллов/ Бонусных Миль и не более 2 500',
                    '1 00 Альфа-Баллов/ Бонусных Миль и не более 2 500'):
            with self.subTest(cap=cap):
                with self.assertRaises(ValueError):alfa(source(cap=cap))

    def test_alfa_payout_must_be_unambiguous_even_if_a_later_delay_is_valid(self):
        for payout in ('-3 дня, в течение 21 дня', '3 дня, в течение 21 дня',
                       '1 00 дней, в течение 21 дня'):
            with self.subTest(payout=payout):
                with self.assertRaises(ValueError):alfa(source(payout=payout))

    def test_alfa_rate_rejects_numeric_continuations_after_the_percent_sign(self):
        for rate in ('25%..5','25%/5','25%+5','25%50','25%%'):
            with self.subTest(rate=rate):
                with self.assertRaisesRegex(ValueError,'alfa_partner_pdf_rate_invalid_or_changed'):
                    alfa(source(rate,headline_rate='100'))

    def test_explicit_early_closure_survives_malformed_scheduled_dates(self):
        for period in ('Акция действует до 31.02.2031.',
                       'Акция действует с 20.11.2031 по 10.11.2031.'):
            for conditions in ('Акция завершена досрочно. '+period,
                               period+' Акция завершена досрочно.'):
                with self.subTest(conditions=conditions):
                    self.assertIsNone(record_row(record(conditions=conditions),'2026-11-08')[0])


if __name__=='__main__':unittest.main()
