"""A cashback reward unit requires an explicit source phrase, not a bonus label."""
import copy
import json
import unittest

from test_unified_normalization import record
from unified_normalization import normalize_record,validate_normalized


class CashbackRewardUnitTests(unittest.TestCase):
    def project(self,body,**fields):
        raw=record(benefit=body,conditions='',activation='',**fields)
        before=copy.deepcopy(raw)
        result=normalize_record(raw,as_of='2026-11-06')
        validate_normalized(json.loads(json.dumps(result)))
        self.assertEqual(raw,before)
        self.assertEqual(result['raw'],before)
        self.assertEqual(result['provenance']['observed_at'],before['observed_at'])
        return result

    def assert_reward(self,result,kind,unit):
        self.assertEqual([(b['kind'],b['value'],b['unit'],b['reward_unit'])
                          for b in result['benefits']],[(kind,'10','percent',unit)])

    def test_stored_alfa_travel_marketing_bonus_does_not_invent_points(self):
        # Relevant public source excerpts observed in the stored-row replay.
        body=('кэшбэк до 10% с бронирования вернётся приятным бонусом. '
              'без скрытых комиссий и переплат')
        result=self.project(body,source_id='alfa_only_announcements',kind='announcement')
        self.assert_reward(result,'cashback',None)
        self.assertEqual(result['benefits'][0]['qualifier'],'up_to')
        self.assertEqual(result['benefits'][0]['evidence'],{'path':'/benefit','text':body})

    def test_marketing_and_brand_words_do_not_define_reward_units(self):
        for body in (
                'Кешбэк 10% станет приятным бонусом к покупке.',
                'Кешбэк 10% по карте «РЖД Бонус».',
                'Кешбэк 10% в магазине «Бонус».',
                'Кешбэк 10% в клубе «Баллы».',
                'Cashback 10% with Points Club.',
                'Cashback 10% with Miles Club.',
                'Cashback 10% with Supermiles.',
                'Кешбэк 10% в магазине Bonus Points.'):
            with self.subTest(body=body):
                self.assert_reward(self.project(body),'cashback',None)

    def test_explicit_russian_points_and_bonus_units_remain_points(self):
        for body in (
                'Кешбэк 10% баллами.',
                'Кешбэк 10% бонусными баллами на следующую покупку.',
                'Кешбэк 10% бонусами.',
                'Кешбэк 10% начисляется в баллах.',
                'Кешбэк 10% возвращается в бонусах.',
                'Кешбэк 10% начисляется в бонусных баллах.',
                'Кешбэк 10% в виде баллов.',
                'Кешбэк 10% в виде бонусов.',
                'Кешбэк 10% в форме бонусных баллов.'):
            with self.subTest(body=body):
                self.assert_reward(self.project(body),'earn_points','points')

    def test_explicit_english_points_units_remain_points(self):
        for body in (
                'Cashback 10% in points.',
                'Cashback 10% credited as reward points.',
                'Cashback 10% paid in bonus points.'):
            with self.subTest(body=body):
                self.assert_reward(self.project(body),'earn_points','points')

    def test_plain_cashback_and_explicit_miles_keep_their_units(self):
        self.assert_reward(self.project('Кешбэк 10% на покупки.'),'cashback',None)
        self.assert_reward(self.project('Кешбэк 10% начисляется милями.'),'earn_miles','miles')
        self.assert_reward(self.project('Cashback 10% credited in miles.'),'earn_miles','miles')
        self.assert_reward(self.project('Cashback 10% paid as bonus miles.'),'earn_miles','miles')


if __name__=='__main__':
    unittest.main()
