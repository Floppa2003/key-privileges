"""A monetary limit owns its own occurrence, not every reward in the line."""
import copy
import hashlib
import json
import unittest

from test_unified_normalization import record
from test_literal_polarity_followup import source_row, project, NOW
from unified_normalization import normalize_record, normalize_inputs
from unified_views import prepare_views
from normalized import normalize_rates


class MoneyCapOwnershipFollowup(unittest.TestCase):
    def common(self, body):
        raw = record(benefit=body, conditions='', activation='')
        original = copy.deepcopy(raw)
        common = normalize_record(raw, as_of=NOW[:10])
        self.assertEqual(raw, original)
        self.assertEqual(common['raw'], original)
        return common

    def assert_separate_reward_and_cap(self, body, reward, cap):
        common = self.common(body)
        self.assertEqual([(b['kind'], b['value'], b['scope'].get('purchase_stage'))
                          for b in common['benefits']], [('discount', reward, 'first')])
        limits = [c for c in common['conditions'] if c['kind'] == 'benefit_cap']
        self.assertEqual([(c['value'], c['scope'].get('purchase_stage')) for c in limits], [(cap, 'repeat')])
        self.assertNotIn(limits[0]['id'], common['benefits'][0]['condition_ids'])
        self.assertIn(common['benefits'][0]['evidence']['text'], body)
        self.assertIn(limits[0]['evidence']['text'], body)

    def test_later_cap_cannot_erase_a_discount_in_another_sentence(self):
        self.assert_separate_reward_and_cap(
            'Скидка 500 ₽ на первый заказ. Максимальная скидка 1000 ₽ на повторные заказы.', '500', '1000')

    def test_changing_prices_order_and_separators_keeps_their_own_purchase_stage(self):
        for first, cap, reward, limit in [
            ('500 ₽', '1000 ₽', '500', '1000'),
            ('1.500,50 руб.', '2\u202f500,75 руб.', '1500.5', '2500.75'),
            ('700 руб.', '700 руб.', '700', '700'),
        ]:
            for separator in ['. ', '; ', ', а ']:
                one = 'Скидка ' + first + ' на первый заказ'
                two = 'Максимальная скидка ' + cap + ' на повторные заказы'
                for body in [one + separator + two + '.', two + separator + one + '.']:
                    with self.subTest(body=body):
                        self.assert_separate_reward_and_cap(body, reward, limit)

    def test_unlabelled_cap_amount_keeps_its_own_sentence_scope(self):
        self.assert_separate_reward_and_cap(
            'Скидка 500 ₽ на первый заказ. Не более 1000 ₽ на повторные заказы.', '500', '1000')

    def test_amounts_in_dates_and_urls_are_not_sentence_or_price_boundaries(self):
        body = ('Скидка 500,50 руб. на первый заказ до 31.12.2026, условия https://example.com/offer. '
                'Максимальная скидка 1000,75 руб. на повторные заказы.')
        self.assert_separate_reward_and_cap(body, '500.5', '1000.75')

    def test_cap_only_source_never_publishes_a_positive_fixed_discount(self):
        for body in ['Максимальная скидка 1000 ₽.', 'Максимум скидки 1000 ₽.', 'Лимит скидки 1000 ₽.']:
            with self.subTest(body=body):
                self.assertEqual(normalize_rates(body), [])
                row = source_row(body)
                self.assertEqual(row['rates'], [])
                self.assertEqual(row['record_kind'], 'source_observation')
                self.assertEqual(row['conditions_text'], body)
                self.assertEqual(project(row)['benefits'], [])
                self.assertEqual(self.common(body)['benefits'], [])

    def test_literal_source_keeps_discount_but_does_not_promote_neighbouring_cap(self):
        body = 'Скидка 500 ₽ на первый заказ. Максимальная скидка 1000 ₽ на повторные заказы.'
        row = source_row(body)
        self.assertEqual([(r['value'], r['unit']) for r in row['rates']], [('500', 'RUB')])
        self.assertEqual([(b['value'], b['unit']) for b in project(row)['benefits']], [('500', 'RUB')])
        self.assertEqual(row['conditions_text'], body)

    def test_same_stage_discount_keeps_its_explicit_limit(self):
        common = self.common('Скидка 500 ₽ на первый заказ, максимум скидки 1000 ₽ на первый заказ.')
        self.assertEqual(len(common['benefits']), 1)
        reward, = common['benefits']
        cap, = [c for c in common['conditions'] if c['kind'] == 'benefit_cap']
        self.assertEqual((reward['value'], reward['scope'].get('purchase_stage')), ('500', 'first'))
        self.assertEqual((cap['value'], cap['scope'].get('purchase_stage')), ('1000', 'first'))
        self.assertIn(cap['id'], reward['condition_ids'])

    def test_percentage_reward_is_preserved_with_its_monetary_cap(self):
        common = self.common('Скидка 10% на первый заказ. Максимальная скидка 1000 ₽ на первый заказ.')
        self.assertEqual([(b['value'], b['unit']) for b in common['benefits']], [('10', 'percent')])
        self.assertTrue(any(c['kind'] == 'benefit_cap' and c['value'] == '1000' for c in common['conditions']))

    def test_generation_changes_without_changing_raw_input_or_assessment_date(self):
        raw = record()
        original = copy.deepcopy(raw)
        bundle = normalize_inputs([raw], as_of='2026-11-12')
        old_generation = hashlib.sha256(json.dumps(
            [bundle['audit']['source_snapshot_sha256'], '2026-11-12', '1.0.4'],
            ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.assertTrue(all(row[-1] != old_generation for rows in prepare_views(bundle).values() for row in rows))
        self.assertEqual(raw, original)


if __name__ == '__main__':
    unittest.main()
