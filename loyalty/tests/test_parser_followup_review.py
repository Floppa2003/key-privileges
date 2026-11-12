"""Complete tokens and semantic owners at the reviewed failure boundaries."""
import unittest

from test_source_numeric_invariance import GENERATIONS, SIM, rule
from test_source_numeric_followup import SIM_ARTICLE
from test_literal_polarity_followup import source_row, project, NOW
from test_unified_normalization import record
from normalized import lexical_conditions
from unified_normalization import normalize_record


class ReviewSourceOwnership(unittest.TestCase):
    def test_unknown_sim_heading_cannot_borrow_the_following_service_price(self):
        raw = SIM_ARTICLE.replace(
            'Замена SIM-карты без обращения в салон', 'Курьерская доставка'
        ).replace('Стоимость услуги – 200 руб.', '')
        with self.assertRaises(ValueError):
            rule('t2_sim_rules', raw)

    def test_unstructured_sim_fragment_keeps_its_owned_prices(self):
        fees = rule('t2_sim_rules', SIM)[0]['details']['fees']
        self.assertEqual((fees['delivery_standard_rub'], fees['replacement_rub']), ('200', '100'))

    def test_fraction_or_ratio_cannot_donate_a_multiplier_suffix(self):
        for token in ['1/2', '1 / 2', '1:2', '1 : 2', '1,5/2.5']:
            with self.subTest(token=token), self.assertRaises(ValueError):
                rule('utair_generations_rules', GENERATIONS.replace('двойные мили', token + '-кратные мили'))

    def test_ordinary_colon_remains_a_valid_multiplier_delimiter(self):
        raw = GENERATIONS.replace('Поколения Utair - двойные мили.', 'Поколения Utair: 2,5-кратные мили.')
        row = rule('utair_generations_rules', raw)[0]
        self.assertEqual(str(row['details']['reward_multiplier']), '2.5')
        self.assertEqual([(b['value'], b['unit']) for b in project(row)['benefits']], [('2.5', 'multiplier')])


class ReviewMoneyCapOwnership(unittest.TestCase):
    def common(self, body):
        raw = record(benefit=body, conditions='', activation='')
        common = normalize_record(raw, as_of=NOW[:10])
        self.assertEqual(common['raw'], raw)
        return common

    def test_cap_separators_never_manufacture_a_source_reward(self):
        for prefix in ['Лимит:', 'Лимит —', 'Максимум:', 'Максимальная сумма', 'Максимальная выплата']:
            body = prefix + ' скидки 1000 ₽.'
            with self.subTest(body=body):
                row = source_row(body)
                self.assertEqual((row['record_kind'], row['rates']), ('source_observation', []))
                self.assertEqual(project(row)['benefits'], [])
                self.assertEqual(row['conditions_text'], body)
                common = self.common(body)
                self.assertEqual(common['benefits'], [])
                self.assertEqual([(c['kind'], c['value']) for c in common['conditions']], [('benefit_cap', '1000')])

    def test_cap_sum_grammar_preserves_the_restriction_beside_a_live_reward(self):
        for literal, expected in [('1000', '1000'), ('2\u202f500,75', '2500.75')]:
            body = 'Скидка 500 ₽ на первый заказ. Максимальная сумма скидки ' + literal + ' ₽ на первый заказ.'
            with self.subTest(literal=literal):
                common = self.common(body)
                reward, = common['benefits']
                cap, = [c for c in common['conditions'] if c['kind'] == 'benefit_cap']
                self.assertEqual((reward['value'], cap['value']), ('500', expected))
                self.assertIn(cap['id'], reward['condition_ids'])
                self.assertEqual([(c['kind'], c['value']) for c in lexical_conditions(body)
                                  if c['kind'] == 'maximum_benefit'], [('maximum_benefit', expected)])

    def test_payment_bound_cannot_borrow_an_earlier_reward_label_or_link(self):
        for payment in ['Оплата', 'Предоплата', 'Комиссия', 'Стоимость покупки']:
            for separator in ['. ', '; ', ', а ']:
                body = 'Скидка 500 ₽ на первый заказ' + separator + payment + ' не более 1000 ₽ на первый заказ.'
                with self.subTest(payment=payment, separator=separator):
                    common = self.common(body)
                    reward, = common['benefits']
                    self.assertEqual(reward['value'], '500')
                    self.assertFalse([c for c in common['conditions'] if c['kind'] == 'benefit_cap'])
                    bound, = [c for c in common['conditions'] if c['kind'] == 'maximum_amount_reference']
                    self.assertEqual(bound['value'], '1000')
                    self.assertNotIn(bound['id'], reward['condition_ids'])

    def test_payment_bound_after_amount_cannot_become_a_benefit_cap(self):
        body = 'Скидка 500 ₽ на первый заказ. Не более 1000 ₽ предоплаты на первый заказ.'
        common = self.common(body)
        reward, = common['benefits']
        bound, = [c for c in common['conditions'] if c['value'] == '1000']
        self.assertEqual(bound['kind'], 'maximum_amount_reference')
        self.assertNotIn(bound['id'], reward['condition_ids'])

    def test_explicit_reward_cap_remains_reward_owned_after_payment_context(self):
        body = 'Оплата картой. Скидка 10%, при оплате максимальная сумма скидки 1000 ₽.'
        common = self.common(body)
        self.assertEqual([(b['value'], b['unit']) for b in common['benefits']], [('10', 'percent')])
        self.assertEqual([(c['kind'], c['value']) for c in common['conditions'] if c['value'] == '1000'],
                         [('benefit_cap', '1000')])

    def test_denied_cap_cannot_create_a_structured_restriction(self):
        body = 'Скидка 500 ₽ действует. Максимальная скидка 1000 ₽ не предоставляется.'
        common = self.common(body)
        self.assertEqual([(b['value'], b['unit']) for b in common['benefits']], [('500', 'RUB')])
        self.assertFalse([c for c in common['conditions'] if c['kind'] == 'benefit_cap'])
        self.assertFalse([c for c in lexical_conditions(body) if c['kind'] == 'maximum_benefit'])

    def test_denial_of_one_cap_does_not_erase_an_equal_live_cap(self):
        body = ('Максимальная скидка 1000 ₽ не предоставляется, '
                'но максимальная скидка 1000 ₽ на первый заказ действует.')
        common = self.common(body)
        self.assertEqual(common['benefits'], [])
        caps = [c for c in common['conditions'] if c['kind'] == 'benefit_cap']
        self.assertEqual([(c['value'], c['scope'].get('purchase_stage')) for c in caps], [('1000', 'first')])

    def test_optional_than_in_cap_prefix_cannot_promote_the_discount(self):
        body = 'Не более чем скидка 1000 ₽.'
        row = source_row(body)
        self.assertEqual((row['record_kind'], row['rates']), ('source_observation', []))
        self.assertEqual(self.common(body)['benefits'], [])


if __name__ == '__main__':
    unittest.main()
