"""Published parameters may change without changing the source's grammar."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from normalized import content_hash
from known_rules import CONFIG, parse_known_rule
from sheets_normalized import SCHEMAS, prepare
from unified_normalization import make_input, normalize_record, validate_normalized
from test_known_rules import RETAIL, NOW
from test_public_product_rules import sample as gpb_sample


def parse(source, html):
    return parse_known_rule(source, html, CONFIG[source]['url'], NOW)[0]


def published_input(row):
    report = dict(source_id=row['source_id'], name='Public rule',
                  root=CONFIG[row['source_id']]['url'], status='ok', discovered=1,
                  normalized=1, failed=0, coverage='fixture', region=None,
                  errors=[], observed_at=NOW)
    bundle = dict(schema_version=2, run_id='fixture:numeric-substitution',
                  observed_at=NOW, records=[row], sources=[report])
    values = prepare(bundle)['parser_offers'][0]
    return make_input(dict(id=row['id'], origin='parser_offers', row=2,
                          fields={h: {'value': v}
                                  for h, v in zip(SCHEMAS['parser_offers'], values)}))


class KnownRuleValueChanges(unittest.TestCase):
    def common(self, row):
        raw = published_input(row)
        before = copy.deepcopy(raw)
        result = normalize_record(raw, as_of='2026-11-08')
        self.assertEqual(raw, before)
        self.assertEqual(result['raw'], before)
        validate_normalized(result)
        return result

    def test_redemption_basis_follows_both_literal_components(self):
        cases = (
            ('с учётом всех скидок, без учёта стоимости доставки',
             'order_after_discounts_excluding_delivery_as_published'),
            ('с учётом всех скидок, с учётом стоимости доставки',
             'order_after_discounts_including_delivery_as_published'),
            ('без учёта всех скидок, без учёта стоимости доставки',
             'order_before_discounts_excluding_delivery_as_published'),
            ('без учёта всех скидок, с учётом стоимости доставки',
             'order_before_discounts_including_delivery_as_published'),
            ('с учётом всех скидок', None),
            ('', None),
            ('с учётом всех скидок, без учёта стоимости доставки; '
             'с учётом стоимости доставки', None),
        )
        for phrase, expected in cases:
            with self.subTest(phrase=phrase):
                html = RETAIL.replace('с учётом всех скидок, без учёта стоимости доставки', phrase)
                row = parse('af_bootwood_rules', html)
                self.assertEqual(row['details']['redemption_rules']['basis'], expected)
                result = self.common(row)
                reward = next(b for b in result['benefits'] if b['kind'] == 'redeem_rewards')
                self.assertEqual(reward['scope']['basis'], expected)

    def test_old_stored_basis_is_rederived_without_rewriting_raw(self):
        for phrase, expected in (
                ('с учётом всех скидок, с учётом стоимости доставки',
                 'order_after_discounts_including_delivery_as_published'),
                ('', None)):
            with self.subTest(phrase=phrase):
                row = parse('af_bootwood_rules', RETAIL.replace(
                    'с учётом всех скидок, без учёта стоимости доставки', phrase))
                row['details']['redemption_rules']['basis'] = 'order_after_discounts_excluding_delivery_as_published'
                row['content_sha256'] = content_hash(row)
                result = self.common(row)
                reward = next(b for b in result['benefits'] if b['kind'] == 'redeem_rewards')
                self.assertEqual(reward['scope']['basis'], expected)
                rule = next(c for c in result['conditions'] if c['kind'] == 'redemption_rules')
                self.assertEqual(rule['scope']['source_value']['basis'], expected)
                self.assertEqual(result['raw']['details']['redemption_rules']['basis'],
                                 'order_after_discounts_excluding_delivery_as_published')

    def test_foreign_redemption_evidence_cannot_rewrite_the_basis(self):
        row = parse('af_bootwood_rules', RETAIL)
        row['details']['redemption_rules']['evidence'] = 'Иная покупка с учётом всех скидок, с учётом стоимости доставки.'
        row['content_sha256'] = content_hash(row)
        with self.assertRaisesRegex(ValueError, 'redemption_evidence'):
            self.common(row)

    def test_redemption_percentages_are_literal_decimal_parameters(self):
        for maximum, cash in (('45', '55'), ('25,5', '74,5'), ('7.5', '92.5')):
            with self.subTest(maximum=maximum):
                html = RETAIL.replace('30%', maximum + '%').replace('70%', cash + '%')
                try:
                    row = parse('af_bootwood_rules', html)
                except ValueError as exc:
                    self.fail(f'Valid changed percentages rejected: {exc}')
                red = row['details']['redemption_rules']
                self.assertEqual(red['max_order_percent'], maximum.replace(',', '.'))
                self.assertEqual(red['minimum_cash_percent'], cash.replace(',', '.'))
                result = self.common(row)
                self.assertTrue(any(b['kind'] == 'redeem_rewards' and b['value'] == maximum.replace(',', '.')
                                    for b in result['benefits']))

    def test_redemption_percentages_reject_invalid_values(self):
        for amount in ('101', '-5', '1 00', '1.5.0', '10–30'):
            with self.subTest(amount=amount):
                with self.assertRaises(ValueError):
                    parse('af_bootwood_rules', RETAIL.replace('30%', amount + '%'))

    def test_notification_start_month_and_fee_are_source_values(self):
        for month, price, expected in (('1', '49', '49'), ('3', '129', '129'), ('12', '149,50', '149.5')):
            with self.subTest(month=month, price=price):
                html = gpb_sample().replace('со 2 месяца – 99 ₽/мес', f'со {month} месяца – {price} ₽/мес')
                try:
                    row = parse('af_gpb_rules', html)
                except ValueError as exc:
                    self.fail(f'Valid changed notification terms rejected: {exc}')
                fees = row['details']['fees']
                self.assertEqual(fees['notifications_from_month'], int(month))
                self.assertEqual(fees['notifications_monthly_rub'], expected)
                self.assertNotIn('notifications_after_first_month_rub', fees)
                result = self.common(row)
                projected = next(c for c in result['costs'] if c['kind'] == 'fees')
                self.assertEqual(projected['scope']['source_value']['notifications_from_month'], int(month))

    def test_second_month_retains_compatible_fee_alias(self):
        fees = parse('af_gpb_rules', gpb_sample())['details']['fees']
        self.assertEqual(fees.get('notifications_from_month'), 2)
        self.assertEqual(fees.get('notifications_monthly_rub'), '99')
        self.assertEqual(fees['notifications_after_first_month_rub'], '99')

    def test_notification_month_rejects_invalid_or_ambiguous_values(self):
        for month in ('0', '-1', '1.5', '1 2', '2–3'):
            with self.subTest(month=month):
                with self.assertRaises(ValueError):
                    parse('af_gpb_rules', gpb_sample().replace('со 2 месяца', f'со {month} месяца'))
        with self.assertRaises(ValueError):
            parse('af_gpb_rules', gpb_sample().replace('со 2 месяца – 99 ₽/мес',
                  'со 2 месяца – 99 ₽/мес; со 3 месяца – 129 ₽/мес'))

    def test_student_expiry_follows_stated_day_and_month_without_a_year(self):
        for expiry in ('2 сентября', '15 октября', '29 февраля', '31 декабря'):
            with self.subTest(expiry=expiry):
                html = ('<div class="post__text">РЖД Бонус. Студенты очной формы обучения '
                        'до 25 лет (включительно): скидка 17%. Как подключить скидку? '
                        'Активация в течение 7 рабочих дней, действует до ' + expiry +
                        ' следующего учебного года.</div>')
                try:
                    row = parse('rzd_student_rules', html)
                except ValueError as exc:
                    self.fail(f'Valid relative expiry rejected: {exc}')
                self.assertEqual(row['details']['entitlement_expiry_text'],
                                 'до ' + expiry + ' следующего учебного года')
                self.assertIsNone(row['valid_until'])
                self.assertIsNone(self.common(row)['validity']['until'])

    def test_student_expiry_rejects_impossible_or_ambiguous_dates(self):
        for expiry in ('0 сентября', '32 сентября', '31 апреля', '1.5 сентября',
                       '1 сентября следующего учебного года; до 2 октября'):
            with self.subTest(expiry=expiry):
                html = ('<div class="post__text">РЖД Бонус. Студенты очной формы обучения '
                        'до 23 лет (включительно): скидка 15%. Как подключить скидку? '
                        'Активация в течение 5 рабочих дней, действует до ' + expiry +
                        ' следующего учебного года.</div>')
                with self.assertRaises(ValueError):
                    parse('rzd_student_rules', html)


if __name__ == '__main__':
    unittest.main()
