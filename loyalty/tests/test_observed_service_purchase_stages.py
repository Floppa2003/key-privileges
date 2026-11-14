"""Actual service offers retain each ordinal and its own adult/child scope."""
import copy
import json
import unittest
from pathlib import Path

from test_unified_normalization import record
from unified_normalization import normalize_record


CASES = json.loads((Path(__file__).parent / 'fixtures/reconciled/observed_service_purchase_stages_20261114.json').read_text())['cases']


class ObservedServicePurchaseStages(unittest.TestCase):
    def normalize(self, name):
        raw = record(**CASES[name])
        before = copy.deepcopy(raw)
        n = normalize_record(raw, as_of='2026-11-14')
        self.assertEqual(raw, before)
        self.assertEqual(n['raw'], before)
        return n

    def test_cleaning_ordinals_are_three_distinct_scopes(self):
        n = self.normalize('qlean')
        self.assertEqual([(b['value'], b['scope'].get('purchase_stage'),
                           b['scope'].get('purchase_ordinal'), b['scope'].get('purchase_ordinal_min'))
                          for b in n['benefits']],
                         [('30', 'first', 1, None), ('20', 'repeat', 2, None),
                          ('10', 'repeat', None, 3)])
        self.assertTrue(all(b['scope']['purchase_unit'] == 'cleaning' for b in n['benefits']))
        self.assertTrue(all(b['scope']['source_clause'] in n['raw']['benefit'] for b in n['benefits']))

    def test_child_first_lesson_and_monthly_pass_do_not_qualify_adult_rates(self):
        n = self.normalize('bereg_public')
        self.assertEqual([(b['value'], b['scope'].get('purchase_stage'), b['scope'].get('audience'))
                          for b in n['benefits']],
                         [('10', None, 'adults'), ('15', None, 'adults'),
                          ('50', 'first', 'children'), ('20', 'first', 'children')])
        by_value = {b['value']: b for b in n['benefits']}
        self.assertIn('первое занятие для детей', by_value['50']['scope']['source_clause'])
        self.assertIn('первый месячный абонемент для детей', by_value['20']['scope']['source_clause'])
        self.assertNotIn('месячный абонемент', by_value['50']['scope']['source_clause'])
        for value in ('10', '15'):
            self.assertNotIn('для детей', by_value[value]['scope']['source_clause'])

    def test_joint_adult_child_services_do_not_gain_an_exclusive_audience(self):
        for name in ('adult_child_combined', 'child_adult_combined'):
            with self.subTest(name=name):
                n = self.normalize(name)
                self.assertTrue(n['benefits'])
                self.assertTrue(all(b['scope'].get('audience') not in ('adults', 'children')
                                    for b in n['benefits']))

    def test_counted_first_lessons_are_not_a_first_purchase_requirement(self):
        for name in ('gift_count_not_first_purchase', 'gift_count_not_first_purchase_activation'):
            with self.subTest(name=name):
                n = self.normalize(name)
                self.assertTrue(any(b['kind'] == 'gift' for b in n['benefits']))
                self.assertTrue(all(b['scope'].get('purchase_stage') is None
                                    for b in n['benefits'] + n['codes']))

    def test_explicit_next_subscription_is_repeat_but_not_the_trial_lesson(self):
        n = self.normalize('following_subscription')
        self.assertEqual([(b['value'], b['scope'].get('purchase_stage')) for b in n['benefits']],
                         [('50', None), ('10', 'first'), ('5', 'repeat')])

    def test_second_and_third_subscription_remain_a_bounded_repeat_list(self):
        n = self.normalize('second_and_third_subscription')
        by_value = {b['value']: b for b in n['benefits']}
        self.assertEqual(by_value['15']['scope'].get('purchase_stage'), 'first')
        self.assertEqual(by_value['10']['scope'].get('purchase_stage'), 'repeat')
        self.assertEqual(by_value['10']['scope']['purchase_ordinals'], [2, 3])
        self.assertIn('при последовательном продлении', by_value['10']['scope']['source_clause'])


if __name__ == '__main__':
    unittest.main()
