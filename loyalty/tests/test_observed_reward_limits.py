"""Literal reward ceilings from the retained 2026-11-14 public sources."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))
from normalized import normalize_rates
from unified_normalization import normalize_record, validate_normalized
from test_unified_normalization import record

LIMITS = json.loads((Path(__file__).parent / 'fixtures' /
                     'observed_reward_limits_20261114.json').read_text())


class ObservedRewardLimitsTests(unittest.TestCase):
    def test_bspb_description_of_redemption_is_not_a_nominal_maximum(self):
        # Retained public post https://t.me/mybspb/1438
        text = ('💰 Как использовать бонусы ЯРКО? Всё максимально просто и прозрачно: '
                '1 бонус = 1 рубль. Вы можете компенсировать накопленными бонусами '
                '100% стоимости любых ваших покупок по карте.')
        result = normalize_record(record(benefit=text, conditions='', details={}), as_of='2026-11-14')
        self.assertFalse(any(c['kind'] == 'benefit_cap' for c in result['conditions']))

    def test_nominal_limits_preserve_units_and_are_never_flat_awards(self):
        for source in LIMITS:
            with self.subTest(url=source['source_url']):
                raw = record(benefit=source['text'], conditions='', activation='',
                             source_url=source['source_url'], details={})
                before = copy.deepcopy(raw)
                result = normalize_record(raw, as_of='2026-11-14')
                self.assertEqual(raw, before)
                self.assertEqual(result['raw'], before)
                validate_normalized(result)
                self.assertFalse(any(b['value'] == source['value'] and b['unit'] == source['unit']
                                     for b in result['benefits']))
                limit, = [c for c in result['conditions'] if c['kind'] == source['kind']]
                self.assertEqual((limit['value'], limit['unit'], limit['qualifier']),
                                 (source['value'], source['unit'], 'up_to'))
                self.assertEqual((limit['basis_value'], limit['basis_unit']),
                                 ('1' if source['basis_unit'] else None, source['basis_unit']))
                self.assertEqual(limit['evidence']['text'], source['text'])
                self.assertFalse(any(r['value'] == source['value'] and r['unit'] == source['unit']
                                     for r in normalize_rates(source['text'])))

    def test_wollmer_cap_is_linked_to_the_percentage_it_bounds(self):
        source = next(s for s in LIMITS if s['value'] == '5000')
        result = normalize_record(record(benefit=source['text'], conditions='', details={}),
                                  as_of='2026-11-14')
        benefit, = result['benefits']
        self.assertEqual((benefit['kind'], benefit['value'], benefit['unit']),
                         ('earn_points', '15', 'percent'))
        cap, = [c for c in result['conditions'] if c['kind'] == 'benefit_cap']
        self.assertIn(cap['id'], benefit['condition_ids'])


if __name__ == '__main__':
    unittest.main()
