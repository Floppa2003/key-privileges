"""Literal amounts and percentage roles survive the public record boundary."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from normalized import make_offer, validate_offer


def record(body):
    return make_offer('moskvich', 'numeric-literals', 'Карта', 'Партнёр', body,
                      'https://moskvichmag.ru/programma-loyalnosti/',
                      '2026-11-05T22:00:00Z')


def card_record(body):
    from adapters import extract
    raw = ('<div class="lpp-card"><h3 class="lpp-card__name">Партнёр</h3>'
           '<div class="lpp-card__conditions">' + body + '</div></div>')
    row, = extract('moskvich', raw, 'https://moskvichmag.ru/programma-loyalnosti/',
                   '2026-11-05T22:00:00Z')
    validate_offer(row)
    return row


class NumericLiteralTests(unittest.TestCase):
    def test_unambiguous_grouped_currency_amounts_do_not_abort_the_record(self):
        cases = [('1.000.000', '1000000'), ('1,000,000', '1000000'),
                 ('1.500,50', '1500.5'), ('1,500.50', '1500.5')]
        for source, expected in cases:
            with self.subTest(source=source):
                try:
                    row = record('Скидка ' + source + ' ₽')
                except ArithmeticError as exc:
                    self.fail('Published numeric punctuation aborted extraction: ' + str(exc))
                validate_offer(row)
                self.assertEqual([(r['kind'], r['value'], r['unit']) for r in row['rates']],
                                 [('discount', expected, 'RUB')])

    def test_grouped_miles_and_purchase_basis_keep_their_full_values(self):
        try:
            row = record('1.000.000 миль за каждые 1.500,50 ₽')
        except ArithmeticError as exc:
            self.fail('Published mile amount aborted extraction: ' + str(exc))
        validate_offer(row)
        self.assertEqual([(r['value'], r['basis_amount'], r['basis_unit']) for r in row['rates']],
                         [('1000000', '1500.5', 'RUB')])

    def test_grouped_order_threshold_and_discount_cap_retain_distinct_roles(self):
        try:
            row = record('Скидка 10% при заказе от 1.500,50 ₽. Максимальная скидка — 1.000.000 ₽.')
        except ArithmeticError as exc:
            self.fail('Published numeric condition aborted extraction: ' + str(exc))
        validate_offer(row)
        conditions = row['details']['lexical_conditions']
        self.assertEqual([(c['kind'], c['value']) for c in conditions],
                         [('minimum_purchase', '1500.5'), ('maximum_benefit', '1000000')])

    def test_existing_decimal_precision_is_not_reinterpreted_as_thousands(self):
        for source, expected in [('6,5', '6.5'), ('6.5', '6.5'), ('1,500', '1.5'),
                                 ('1.500', '1.5'), ('1\u202f500,50', '1500.5')]:
            with self.subTest(source=source):
                row = record('Скидка ' + source + ' ₽')
                validate_offer(row)
                self.assertEqual(row['rates'][0]['value'], expected)


class PercentageRoleTests(unittest.TestCase):
    def test_postfix_reward_label_does_not_own_a_later_payment_rate(self):
        cases = [('10% скидка, 100% предоплата.', [('discount', '10')]),
                 ('5% кешбэк, комиссия 2%.', [('cashback', '5')]),
                 ('10% скидка, 20% НДС.', [('discount', '10')])]
        for body, expected in cases:
            with self.subTest(body=body):
                row = record(body)
                validate_offer(row)
                self.assertEqual([(r['kind'], r['value']) for r in row['rates']], expected)
                self.assertEqual(row['benefit_text'], body)

    def test_postfix_label_keeps_explicit_new_rewards_and_sentence_boundaries(self):
        cases = [
            ('10% скидка. Комиссия 2%.', [('discount', '10')]),
            ('10% скидка, кэшбэк 5% оплаты за проживание.',
             [('discount', '10'), ('cashback', '5')]),
            ('10% скидка, на комиссию 50%.', [('discount', '10'), ('discount', '50')]),
        ]
        for body, expected in cases:
            with self.subTest(body=body):
                row = record(body)
                validate_offer(row)
                self.assertEqual([(r['kind'], r['value']) for r in row['rates']], expected)

    def test_tax_or_prepayment_in_later_sentence_is_not_another_discount(self):
        for suffix in ['НДС 20%.', 'Предоплата 30%.', 'предоплата 30%.']:
            with self.subTest(suffix=suffix):
                row = record('Скидка 10%. ' + suffix)
                validate_offer(row)
                self.assertEqual([(r['kind'], r['value']) for r in row['rates']], [('discount', '10')])
                self.assertIn(suffix, row['benefit_text'])

    def test_prepayment_in_same_sentence_does_not_inherit_discount_role(self):
        for condition in ['при предоплате 30%', 'при 30% предоплате', 'при оплате 30% стоимости']:
            with self.subTest(condition=condition):
                row = record('Скидка 10% ' + condition)
                validate_offer(row)
                self.assertEqual([(r['kind'], r['value']) for r in row['rates']], [('discount', '10')])

    def test_separately_named_rewards_and_explicit_discount_lists_remain(self):
        cases = [
            ('Скидка 10%, кешбэк 5%.', [('discount', '10'), ('cashback', '5')]),
            ('Скидки 5%, 10% и 15%.', [('discount', '5'), ('discount', '10'), ('discount', '15')]),
            ('Скидка на проживание 15%.', [('discount', '15')]),
            ('Скидка составляет 15%.', [('discount', '15')]),
            ('Скидка 10%. Дополнительная скидка 5%.', [('discount', '10'), ('discount', '5')]),
        ]
        for body, expected in cases:
            with self.subTest(body=body):
                row = record(body)
                validate_offer(row)
                self.assertEqual([(r['kind'], r['value']) for r in row['rates']], expected)

    def test_parallel_reward_scopes_keep_each_published_percentage(self):
        cases = [
            ('Скидка 20% при посещении до 18:00 и 10% — после 18:00.', ['20', '10']),
            ('Скидка 15% на первый визит и 10% на каждый пятый.', ['15', '10']),
            ('Скидка на первый визит 10% и на повторный визит 5%.', ['10', '5']),
            ('Скидка 30% на все меню и 20% на напитки.', ['30', '20']),
            ('Кэшбэк в косметологии 5%, другие услуги 10%.', ['5', '10']),
        ]
        for body, expected in cases:
            with self.subTest(body=body):
                row = record(body)
                self.assertEqual([r['value'] for r in row['rates']], expected)

    def test_reward_applied_to_a_fee_or_payment_keeps_its_own_rate(self):
        cases = [('Скидка на комиссию 50%.', [('discount', '50')]),
                 ('Кэшбэк 5% оплаты за проживание.', [('cashback', '5')]),
                 ('Кэшбэк за проживание — 5% оплаты.', [('cashback', '5')])]
        for body, expected in cases:
            with self.subTest(body=body):
                row = record(body)
                self.assertEqual([(r['kind'], r['value']) for r in row['rates']], expected)

    def test_audience_abbreviations_do_not_end_a_reward_clause(self):
        cases = [('Скидка 10% для физ. лиц и 5% для юр. лиц.', ['10', '5']),
                 ('Скидка для физ. лиц 10%.', ['10']),
                 ('Скидка для юр. лиц 15%. НДС 20%.', ['15'])]
        for body, expected in cases:
            with self.subTest(body=body):
                row = record(body)
                self.assertEqual([r['value'] for r in row['rates']], expected)

    def test_payment_condition_without_a_published_discount_amount_stays_untyped(self):
        for body in ['Скидка при 30% предоплате.',
                     'Скидки при 100% предоплате.',
                     'Скидки с учетом НДС 20%.',
                     'Скидки за 100% предоплату.']:
            with self.subTest(body=body):
                row = record(body)
                self.assertEqual(row['rates'], [])

    def test_explicit_abbreviations_preserve_rates_through_html_pipeline(self):
        cases = [('Скидка на доп. услуги 10%.', ['10']),
                 ('Скидка на всё, в т. ч. на напитки, 10%.', ['10']),
                 ('Скидка на доп. услуги 10%. Предоплата 30%.', ['10']),
                 ('Скидка на доп. услуги 10%. предоплата 30%.', ['10'])]
        for body, expected in cases:
            with self.subTest(body=body):
                row = card_record(body)
                self.assertEqual([r['value'] for r in row['rates']], expected)
                self.assertEqual(row['benefit_text'], body)

    def test_parallel_commission_discount_is_not_a_commission_condition(self):
        cases = [('Скидка на доставку 10% и на комиссию 50%.', ['10', '50']),
                 ('Скидка на доставку 10%, на комиссию — до 50%.', ['10', '50']),
                 ('Скидка 10% на доставку и 50% на комиссию.', ['10', '50']),
                 ('Скидка 10%, комиссия 50%.', ['10']),
                 ('Скидка 10% при комиссии 50%.', ['10']),
                 ('Скидка 10% при согласии на комиссию 5%.', ['10']),
                 ('Скидка при комиссии 50%.', [])]
        for body, expected in cases:
            with self.subTest(body=body):
                row = card_record(body)
                self.assertEqual([r['value'] for r in row['rates']], expected)
                self.assertTrue(all(r['kind'] == 'discount' for r in row['rates']))

    def test_qualifier_is_a_separate_word_not_a_brand_suffix(self):
        vtb = ('До 6% на WB Скидка с картой ВТБ 3 мили За каждые потраченные 90 ₽ '
               'по карте Привилегия Аэрофлот 7% Кешбэк в ресторанах: White Rabbit Family, '
               'Novikov Group, Pinsky&Co, Ginza Project, Lucky Group, Buro Group, '
               'Рестораны Арама Мнацаканова 2 990 ₽ Ежегодная комиссия за предоставление в пользование')
        cases = [(vtb, [('cashback', '7', 'exact')]),
                 ('Скидка в Эльдорадо 10%.', [('discount', '10', 'exact')]),
                 ('Скидка 10%.', [('discount', '10', 'exact')]),
                 ('Скидка от 10%.', [('discount', '10', 'at_least')]),
                 ('Скидка до 10%.', [('discount', '10', 'up_to')])]
        for body, expected in cases:
            with self.subTest(body=body):
                row = card_record(body)
                self.assertEqual([(r['kind'], r['value'], r['qualifier']) for r in row['rates']
                                  if r['unit'] == 'percent'], expected)


if __name__ == '__main__':
    unittest.main()
