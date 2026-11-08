"""Confirmed whole-branch review findings through real public entrypoints."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).parents[1]))
from catalogue_view import record_row
from normalized import normalize_rates
from unified_normalization import normalize_inputs, normalize_record
from unified_views import prepare_views
from test_unified_normalization import record


class RewardReviewRegressions(unittest.TestCase):
    def project(self,literal,**updates):
        raw=record(**{'benefit':literal,'conditions':'','activation':'',**updates})
        before=copy.deepcopy(raw)
        result=normalize_record(raw,as_of='2026-11-08')
        self.assertEqual(raw,before)
        self.assertEqual(result['raw'],before)
        return result

    def test_replaced_list_does_not_leak_its_later_quantities(self):
        for unit,kind in (('баллов','earn_points'),('миль','earn_miles')):
            for literal in (f'Получите 500 {unit} вместо 100 {unit} и 50 {unit}.',
                            f'Начисляем 500 {unit}, а не 100 {unit} и 50 {unit}.',
                            f'Вместо 100 {unit} и 50 {unit} получите 500 {unit}.'):
                with self.subTest(literal=literal):
                    benefits=self.project(literal)['benefits']
                    self.assertEqual([(b['kind'],b['value']) for b in benefits],[(kind,'500')])
                    if unit=='миль':
                        self.assertEqual([(r['kind'],r['value']) for r in normalize_rates(literal)],[('miles','500')])

    def test_new_action_and_contrast_end_the_reference_list(self):
        for unit,kind in (('баллов','earn_points'),('миль','earn_miles')):
            for literal in (f'Получите 500 {unit} вместо 100 {unit} и 50 {unit}, затем получите 200 {unit}.',
                            f'Не 100 {unit} и 50 {unit}, а 500 {unit} начислим.',
                            f'Получите 500 {unit} вместо 100 {unit} и получите 200 {unit}.'):
                with self.subTest(literal=literal):
                    expected=[(kind,'500')] if literal.startswith('Не') else [(kind,'500'),(kind,'200')]
                    self.assertCountEqual([(b['kind'],b['value']) for b in self.project(literal)['benefits']],expected)

    def test_category_and_payment_exclusions_preserve_positive_benefit(self):
        for literal,kind,value in (('Скидка 10% не действует на алкоголь.','discount','10'),
                                   ('Скидка 10% не действует при оплате баллами.','discount','10'),
                                   ('Кешбэк 5% не начисляется за оплату услуг ЖКХ.','cashback','5')):
            with self.subTest(literal=literal):
                self.assertEqual([(r['kind'],r['value']) for r in normalize_rates(literal)],[(kind,value)])
                result=self.project(literal)
                self.assertEqual([(b['kind'],b['value']) for b in result['benefits']],[(kind,value)])
                self.assertTrue(any(c['kind']=='exclusion' and c['evidence']['text']==literal
                                    for c in result['conditions']))

    def test_credit_destination_is_a_denial_not_a_product_exclusion(self):
        for tail in ('на счет','на ваш бонусный счёт','на баланс','на банковскую карту'):
            literal=f'Кешбэк 5% не начисляется {tail}.'
            with self.subTest(tail=tail):
                self.assertEqual(normalize_rates(literal),[])
                self.assertEqual(self.project(literal)['benefits'],[])

    def test_card_eligibility_restriction_is_not_a_denied_credit(self):
        for tail in ('для банковской карты Visa','на банковскую карту Visa'):
            literal=f'Скидка 10% не действует {tail}.'
            with self.subTest(tail=tail):
                self.assertEqual([(r['kind'],r['value']) for r in normalize_rates(literal)],[('discount','10')])
                self.assertEqual([(b['kind'],b['value']) for b in self.project(literal)['benefits']],
                                 [('discount','10')])
        self.assertEqual(self.project('Кешбэк 5% не предоставляется на банковскую карту.')['benefits'],[])

    def test_excluded_stage_is_not_a_positive_benefit_scope(self):
        result=self.project('Скидка 10% не действует на первый заказ.')
        self.assertEqual([(b['kind'],b['value'],b['scope']) for b in result['benefits']],
                         [('discount','10',{})])
        self.assertTrue(any(c['kind']=='exclusion' for c in result['conditions']))

    def test_owned_campaign_conditions_and_activation_cannot_bypass_draw_filter(self):
        for field in ('conditions','activation'):
            with self.subTest(field=field):
                result=self.project('50 000 миль',kind='campaign',
                                     **{field:'Получите шанс выиграть 50 000 миль.'})
                self.assertEqual(record_row(result,'2026-11-08'),(None,'розыгрыш'))
        control=self.project('Скидка 10% каждому участнику.',kind='campaign',
                              conditions='Не упустите шанс воспользоваться скидкой.')
        self.assertIsNotNone(record_row(control,'2026-11-08')[0])

    def test_repaired_semantics_do_not_reuse_the_historical_generation(self):
        raw=record(benefit='Не начисляем 500 миль.',conditions='',activation='')
        result=normalize_inputs([raw],as_of='2026-11-08')
        self.assertEqual(result['records'][0]['benefits'],[])
        generation=next(row[-1] for row in prepare_views(result)['normalization_audit'] if row[0]=='manifest')
        # Independently reproduced on 31993a6 with this exact raw/date: that
        # generation contained a false 500-mile award and must remain distinct.
        self.assertNotEqual(generation,'700b6898e676dd98ca8a782d7e0d3dadeaa108668fddad13f596e882ec6930bd')


if __name__=='__main__':
    unittest.main()
