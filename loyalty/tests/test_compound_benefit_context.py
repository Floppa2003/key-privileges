"""Sibling benefits keep their own polarity, purchase stage and limit."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from normalized import normalize_rates
from unified_normalization import normalize_record, validate_normalized
from test_unified_normalization import record


class CompoundBenefitContextTests(unittest.TestCase):
    def project(self, literal):
        raw = record(benefit=literal, conditions='', activation='')
        before = copy.deepcopy(raw)
        result = normalize_record(raw, as_of='2026-11-08')
        self.assertEqual(raw, before)
        self.assertEqual(result['raw'], before)
        validate_normalized(json.loads(json.dumps(result)))
        for group in ('benefits', 'conditions'):
            for term in result[group]:
                self.assertIn(term['evidence']['text'], literal)
        return result

    def assert_benefits(self, literal, expected):
        result = self.project(literal)
        self.assertCountEqual([(b['kind'], b['value'], b['scope'].get('purchase_stage'))
                              for b in result['benefits']], expected)
        return result

    def test_bounded_postfix_discount_labels_are_recognized(self):
        for literal in ('10% (постоянной скидки).', '10% (скидка).', '10% постоянной скидки.'):
            with self.subTest(literal=literal):
                self.assertEqual([(r['kind'], r['value']) for r in normalize_rates(literal)],
                                 [('discount', '10')])
                self.assert_benefits(literal, [('discount', '10', None)])

    def test_postfix_label_cannot_label_a_neighbouring_payment_percentage(self):
        for literal in ('10% (постоянной скидки), предоплата 50%.',
                        '10% постоянной скидки и 50% НДС.',
                        '10% (скидка), комиссия 3%.'):
            with self.subTest(literal=literal):
                self.assertEqual([(r['kind'], r['value']) for r in normalize_rates(literal)],
                                 [('discount', '10')])
                self.assert_benefits(literal, [('discount', '10', None)])

    def test_public_bionika_discount_does_not_inherit_first_visit(self):
        self.assert_benefits('10% (постоянной скидки) + комплементарная процедура '
                             'на первое посещение HydraFacial', [('discount', '10', None)])

    def test_gift_and_discount_keep_their_own_stage_in_both_orders(self):
        for separator in (' + ', ' и '):
            for literal in ('Скидка 10%' + separator + 'комплиментарная процедура на первое посещение.',
                            'Комплиментарная процедура на первое посещение' + separator + 'скидка 10%.'):
                with self.subTest(literal=literal):
                    self.assert_benefits(literal, [('discount', '10', None), ('gift', None, 'first')])

    def test_different_reward_units_keep_their_own_stage(self):
        self.assert_benefits('Получите 500 баллов на первый заказ + скидка 10% на повторный заказ.',
                             [('earn_points', '500', 'first'), ('discount', '10', 'repeat')])
        self.assert_benefits('500 миль на первый заказ + кофе в подарок на повторный заказ.',
                             [('earn_miles', '500', 'first'), ('gift', None, 'repeat')])
        self.assert_benefits('Скидка 500 рублей на первый заказ + кофе в подарок на повторный заказ.',
                             [('discount', '500', 'first'), ('gift', None, 'repeat')])

    def test_explicit_shared_prefix_applies_to_the_whole_bundle(self):
        self.assert_benefits('На первый заказ скидка 10% + кофе в подарок.',
                             [('discount', '10', 'first'), ('gift', None, 'first')])
        self.assert_benefits('На первый заказ получите 500 баллов + скидка 10%.',
                             [('earn_points', '500', 'first'), ('discount', '10', 'first')])

    def test_denied_rates_do_not_survive_source_or_common_projection(self):
        for literal in ('Скидка 10% не предоставляется.', 'Не предоставляем скидку 10%.',
                        '10% (постоянной скидки) не предоставляется.',
                        'Кешбэк 5% не начисляется.', 'Скидки 10% и 5% не предоставляются.',
                        'Скидки 10% + 5% не предоставляются.', 'Не предоставляем скидку 500 рублей.'):
            with self.subTest(literal=literal):
                self.assertEqual(normalize_rates(literal), [])
                self.assert_benefits(literal, [])

    def test_positive_neighbouring_rate_survives(self):
        for literal in ('Скидка 10% не предоставляется, но действует скидка 5%.',
                        'Не предоставляем скидку 10%, скидка 5% предоставляется.',
                        'Предоставляем скидку 5%, скидка 10% не предоставляется.'):
            with self.subTest(literal=literal):
                self.assert_benefits(literal, [('discount', '5', None)])

    def test_explicit_gift_denial_is_not_a_gift(self):
        for literal in ('Кофе в подарок не предоставляется.', 'Не получите кофе в подарок.',
                        'Комплиментарная процедура не предоставляется.'):
            with self.subTest(literal=literal):
                self.assert_benefits(literal, [])

    def test_product_exclusions_and_unrelated_negation_keep_positive_benefits(self):
        for literal in ('Скидка 10% не действует на акционные товары.',
                        'Скидка 10% на товары, кроме подарочных сертификатов.',
                        'Скидка 10% не суммируется с другими акциями.'):
            with self.subTest(literal=literal):
                self.assert_benefits(literal, [('discount', '10', None)])
        self.assert_benefits('Кофе в подарок, если вы не оформляли заказ ранее.', [('gift', None, None)])
        self.assert_benefits('Экскурсия в подарок не является средством платежа, не выдается '
                             'в денежном эквиваленте и не может быть обменяна на товары.', [('gift', None, None)])
        self.assert_benefits('Кофе в подарок не выдается в денежном эквиваленте.', [('gift', None, None)])
        self.assert_benefits('Кешбэк 5% не начисляется на счет.', [])

    def test_point_limits_keep_the_stage_of_their_own_alternative(self):
        result = self.project('Кешбэк 10% бонусами за первую покупку (до 500 бонусов) '
                              'или кешбэк 5% за последующие покупки (до 250 бонусов).')
        caps = {c['value']: c for c in result['conditions'] if c['kind'] == 'benefit_cap'}
        self.assertEqual({v: c['scope'].get('purchase_stage') for v, c in caps.items()},
                         {'500': 'first', '250': 'repeat'})
        rewards = {b['value']: b for b in result['benefits']}
        self.assertIn(caps['500']['id'], rewards['10']['condition_ids'])
        self.assertNotIn(caps['250']['id'], rewards['10']['condition_ids'])
        self.assertIn(caps['250']['id'], rewards['5']['condition_ids'])
        self.assertNotIn(caps['500']['id'], rewards['5']['condition_ids'])

    def test_equal_or_unknown_stages_do_not_cross_link_alternative_limits(self):
        for stage in ('', ' за первую покупку', ' за последующие покупки'):
            with self.subTest(stage=stage):
                result=self.project(f'Кешбэк 10%{stage} (до 500 бонусов) или '
                                    f'кешбэк 5%{stage} (до 250 бонусов).')
                caps={c['value']:c for c in result['conditions'] if c['kind']=='benefit_cap'}
                rewards={b['value']:b for b in result['benefits']}
                for reward,own,other in (('10','500','250'),('5','250','500')):
                    self.assertIn(caps[own]['id'],rewards[reward]['condition_ids'])
                    self.assertNotIn(caps[other]['id'],rewards[reward]['condition_ids'])

    def test_gift_object_stage_before_marker_is_not_a_shared_prefix(self):
        for prefix in ('Кофе', 'Получите кофе'):
            with self.subTest(prefix=prefix):
                self.assert_benefits(prefix+' на первый заказ в подарок + скидка 10%.',
                                     [('gift',None,'first'),('discount','10',None)])

    def test_attached_numeric_footnote_does_not_erase_the_gift_marker(self):
        self.assert_benefits('Медицинская услуга в подарок2', [('gift',None,None)])

    def test_exchange_base_is_part_of_the_reward_scope(self):
        result=self.assert_benefits('20 миль за каждые 500 баллов на первый заказ + '
                                    'кофе в подарок на повторный заказ.',
                                    [('earn_miles','20','first'),('gift',None,'repeat')])
        self.assertEqual(result['benefits'][0]['basis_value'],'500')

    def test_contrast_does_not_deny_a_positive_sibling(self):
        self.assert_benefits('Кофе в подарок не предоставляется, а скидка 10%.',
                             [('discount','10',None)])
        self.assert_benefits('Скидка 10% не предоставляется, а кофе в подарок.',
                             [('gift',None,None)])

    def test_plural_denial_owns_a_mixed_list_but_singular_stays_local(self):
        for literal in ('Скидка 10% и кофе в подарок не предоставляются.',
                        'Скидка 10% и 500 баллов не предоставляются.'):
            with self.subTest(literal=literal):
                self.assertEqual(normalize_rates(literal),[])
                self.assert_benefits(literal,[])
        self.assert_benefits('Скидка 10% + кофе в подарок не предоставляется.',
                             [('discount','10',None)])

    def test_direct_mileage_percent_payment_is_not_an_earning_rate(self):
        for literal in ('Оплатите 50% милями. Скидка 25%.',
                        'Скидка 25%. Спишите 50% милями.',
                        'Начислим 5% милями, оплатите 50% милями.'):
            expected=[('miles','5')] if literal.startswith('Начислим') else [('discount','25')]
            with self.subTest(literal=literal):
                self.assertEqual([(r['kind'],r['value']) for r in normalize_rates(literal)],expected)
                self.assert_benefits(literal,[('earn_miles' if k=='miles' else k,v,None) for k,v in expected])

    def test_owned_postfix_denial_can_follow_a_purchase_stage(self):
        self.assert_benefits('Скидка 10% и кофе в подарок на первый заказ не предоставляются.',[])
        self.assert_benefits('Комплиментарная процедура на первое посещение не предоставляется.',[])
        for unit in ('баллов','миль'):
            with self.subTest(unit=unit):
                self.assert_benefits(f'Получите 500 {unit} на первый заказ не начисляются.',[])
        self.assert_benefits('Скидка 10% + кофе в подарок на первый заказ не предоставляется.',
                             [('discount','10',None)])


if __name__ == '__main__':
    unittest.main()
