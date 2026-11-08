"""Only the amount owned by an affirmative earning action is an award."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from normalized import normalize_rates
from unified_normalization import normalize_inputs, normalize_record, validate_normalized
from unified_views import prepare_views, SCHEMAS
from test_unified_normalization import record


class RewardActionOwnershipTests(unittest.TestCase):
    def project(self, literal, **updates):
        source = record(**{'benefit': literal, 'conditions': '', 'activation': '', **updates})
        before = copy.deepcopy(source)
        result = normalize_record(source, as_of='2026-11-08')
        self.assertEqual(source, before)
        self.assertEqual(result['raw'], before)
        validate_normalized(json.loads(json.dumps(result)))
        for item in result['benefits']:
            self.assertIn(item['evidence']['text'], source[item['evidence']['path'].lstrip('/')])
        return result

    def assert_awards(self, literal, expected):
        result = self.project(literal)
        self.assertCountEqual([(b['kind'], b['value']) for b in result['benefits']], expected)
        return result

    def test_explicit_mileage_denial_is_rejected_at_source_and_common_boundaries(self):
        for literal in ('Не начисляем 500 миль.', '500 миль не начисляются.',
                        'Нельзя получить 500 миль.', '500 миль получить нельзя.',
                        'Не будут начислены 500 миль.'):
            with self.subTest(literal=literal):
                self.assertEqual(normalize_rates(literal), [])
                self.assert_awards(literal, [])

    def test_neighbouring_affirmative_amount_survives_in_both_units(self):
        for unit, kind in (('миль', 'earn_miles'), ('баллов', 'earn_points')):
            for literal in (f'Не начисляем 500 {unit}, но получите 100 {unit}.',
                            f'Получите 100 {unit}, 500 {unit} не начисляются.',
                            f'Не начисляем 500 {unit}, 100 {unit} получите.',
                            f'500 {unit} не начисляются, 100 {unit} будут начислены.'):
                with self.subTest(literal=literal):
                    self.assert_awards(literal, [(kind, '100')])

    def test_shared_denied_lists_do_not_award_any_amount(self):
        for literal in ('500 миль и 100 миль не начисляются.',
                        'Не начисляем 500 миль и 100 миль.',
                        '500 баллов и 100 миль не начисляются.',
                        '500 миль и 100 баллов получить нельзя.'):
            with self.subTest(literal=literal):
                self.assert_awards(literal, [])

    def test_expense_and_award_bind_to_their_own_amount(self):
        for unit, kind in (('миль', 'earn_miles'), ('баллов', 'earn_points')):
            for literal in (f'Потратьте 500 {unit} и получите 100 {unit}.',
                            f'Списывайте 500 {unit} и получите 100 {unit}.',
                            f'Спишите 500 {unit} и получите 100 {unit}.',
                            f'Получите 100 {unit} и спишите 500 {unit}.',
                            f'500 {unit} спишите, 100 {unit} получите.'):
                with self.subTest(literal=literal):
                    self.assert_awards(literal, [(kind, '100')])

    def test_balance_condition_does_not_become_an_award(self):
        for unit, kind in (('миль', 'earn_miles'), ('баллов', 'earn_points')):
            for literal in (f'Получите 500 {unit}, если у вас на счете менее 100 {unit}.',
                            f'Если на счете есть 100 {unit}, получите 500 {unit}.',
                            f'Получите 500 {unit} при балансе от 100 {unit}.'):
                with self.subTest(literal=literal):
                    self.assert_awards(literal, [(kind, '500')])

    def test_replaced_and_contrasted_amounts_remain_references(self):
        for unit, kind in (('миль', 'earn_miles'), ('баллов', 'earn_points')):
            for literal in (f'Начисляем 500 {unit}, а не 100 {unit}.',
                            f'Вы получите 500 {unit} вместо 100 {unit}.',
                            f'Не 100 {unit}, а 500 {unit} начислим за покупку.'):
                with self.subTest(literal=literal):
                    self.assert_awards(literal, [(kind, '500')])

    def test_certificate_face_value_is_not_earned_mileage(self):
        self.assert_awards('Подарочные сертификаты номиналом от 500 миль.', [])
        self.assert_awards('500 миль в подарок.', [('earn_miles', '500'), ('gift', None)])

    def test_unrelated_denial_does_not_erase_postfix_award(self):
        for unit, kind in (('миль', 'earn_miles'), ('баллов', 'earn_points')):
            for literal in (f'Если вы не получили письмо, 500 {unit} будут начислены.',
                            f'Не получили письмо, 500 {unit} уже начислены.',
                            f'Получите 500 {unit}, если не оформляли заказ ранее.',
                            f'Не только получите 500 {unit}, но и доступ к каталогу.'):
                with self.subTest(literal=literal):
                    self.assert_awards(literal, [(kind, '500')])

    def test_shared_positive_lists_keep_each_amount(self):
        for literal, expected in (
                ('Получите 500 баллов и 100 миль.', [('earn_points', '500'), ('earn_miles', '100')]),
                ('500 баллов и 100 миль начисляются.', [('earn_points', '500'), ('earn_miles', '100')]),
                ('Начислим 500 баллов, 100 миль не начисляются.', [('earn_points', '500')])):
            with self.subTest(literal=literal):
                self.assert_awards(literal, expected)

    def test_payment_noun_does_not_replace_the_earning_action(self):
        self.assert_awards('Начисляем за оплату картой 500 баллов.', [('earn_points', '500')])
        self.assert_awards('Получите за оплату заказа 500 миль.', [('earn_miles', '500')])
        self.assert_awards('Для оплаты билетов милями: 1 миля = 1 рубль.', [])

    def test_paid_purchase_modifier_does_not_become_a_spending_action(self):
        self.assert_awards('Баллы в программе начисляются за оплаченные и фактически совершённые '
                           'участником поездки из расчёта: 1 балл за каждые 3,34 рубля.',
                           [('earn_points', '1')])
        self.assert_awards('Оплачивайте 500 миль и получите 100 миль.', [('earn_miles', '100')])

    def test_denied_sublist_after_another_positive_award(self):
        self.assert_awards('Получите 500 баллов, а 100 баллов и 50 миль не начисляются.',
                           [('earn_points', '500')])
        self.assert_awards('Получите 500 миль, а 100 миль и 50 баллов не начисляются.',
                           [('earn_miles', '500')])

    def test_owned_postfix_action_after_a_pronoun_or_purchase_modifier(self):
        for unit, kind in (('миль', 'earn_miles'), ('баллов', 'earn_points')):
            for modifier in ('вам', 'за заказ', 'за первый заказ'):
                with self.subTest(unit=unit, modifier=modifier):
                    self.assert_awards(f'500 {unit} {modifier} не начисляются.', [])
                    self.assert_awards(f'500 {unit} {modifier} начисляются.', [(kind, '500')])

    def test_other_field_cannot_supply_an_action(self):
        result = self.project('Баланс 500 баллов.', conditions='Получите 100 баллов.')
        self.assertEqual([(b['kind'], b['value']) for b in result['benefits']], [('earn_points', '100')])
        self.assertEqual(result['benefits'][0]['evidence'], {'path': '/conditions', 'text': 'Получите 100 баллов.'})

    def test_common_views_include_only_the_owned_affirmative_amount(self):
        source = record(benefit='Не начисляем 500 миль. Спишите 200 баллов и получите 100 баллов.',
                        conditions='', activation='')
        bundle = normalize_inputs([source], as_of='2026-11-08')
        rows = prepare_views(bundle)['normalized_benefits']
        projected = [dict(zip(SCHEMAS['normalized_benefits'], row)) for row in rows]
        self.assertEqual([(r['Тип выгоды'], r['Значение']) for r in projected], [('earn_points', '100')])
        self.assertEqual(bundle['records'][0]['raw'], source)


if __name__ == '__main__':
    unittest.main()
