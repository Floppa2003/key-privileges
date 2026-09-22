"""A contradictory lounge fee must not swallow an independent restaurant reward."""
import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
import avolta_source as a
from test_public_reward_sources import html, NOW, common
from catalogue_view import record_row
CARD={'url':a.PREFIX+'zaly-ozhidaniya/dragonpass','name':'Dragonpass','category':'Залы ожидания'}
class ComponentScopeTests(unittest.TestCase):
    def test_price_conflict_withholds_only_lounge_component(self):
        row=a.parse_detail(html('avolta-dragonpass.html'),CARD,NOW)
        self.assertEqual(row['redemption_text'],'')
        n=common(row)
        self.assertEqual([(x['kind'],x['value']) for x in n['benefits']],[('discount','25')])
        reader,reason=record_row(n,NOW[:10]);self.assertIsNone(reason)
        self.assertIn('ресторанах аэропорта',reader[2])
        for value in ('28','31','доступ в зал'):
            self.assertNotIn(value,reader[2].lower())
        self.assertIn('противореч',reader[5])
        self.assertIn('не раскрыт',reader[5])
        self.assertIn('partial_restaurant_reward_only',row['warnings'])
    def test_conflicting_restaurant_discount_is_not_cherry_picked(self):
        raw=html('avolta-dragonpass.html').replace('25%','30%',1)
        with self.assertRaises(a.ExcludedOffer):a.parse_detail(raw,CARD,NOW)
