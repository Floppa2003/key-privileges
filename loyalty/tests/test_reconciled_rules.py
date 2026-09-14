"""Catch exact-page omissions, neighbouring promotions, and false tier/identity mapping."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from known_rules import CONFIG,parse_known_rule
from normalized import validate_offer
NOW='2026-09-14T10:00:00+00:00'
FIX=Path(__file__).parent/'fixtures/reconciled'
IDS=['ural_ramada_rules','ural_seagalaxy_rules','ural_smart_rules','ural_airharbour_rules','ural_carsgo_rules','ural_gloria_rules','ural_triangle_rules','ural_visotsky_rules','ural_angara_rules','ural_ecospa_rules']
class ReconciledRulesTests(unittest.TestCase):
 def read(self,k,raw=None):
  self.assertIn(k,CONFIG,'Missing reviewed source registration')
  return parse_known_rule(k,raw or (FIX/(k+'.html')).read_text(),CONFIG[k]['url'],NOW)[0]
 def test_every_reviewed_partner_page_is_supplementary_and_has_real_evidence(self):
  for k in IDS:
   with self.subTest(k=k):
    r=self.read(k);validate_offer(r)
    self.assertEqual(r['record_kind'],'program_rules');self.assertEqual(r['details']['supplements_source_ids'],['ural'])
    self.assertIsNone(r['valid_until']);self.assertIn('Крылья',r['conditions_text'])
 def test_airharbour_rejects_unrelated_conference_and_loyal_customer_rates(self):
  raw=(FIX/'ural_airharbour_rules.html').read_text().replace('</div>','<hr><p>Конференция: скидка 99%</p><p>Постоянным клиентам 88%</p></div>',1)
  r=self.read('ural_airharbour_rules',raw)
  self.assertNotIn('99%',r['conditions_text']);self.assertNotIn('88%',r['conditions_text']);self.assertIn('7%',r['conditions_text'])
 def test_smart_course_discount_does_not_absorb_airline_cashback(self):
  raw=(FIX/'ural_smart_rules.html').read_text().replace('</body>','<div data-elem-id="1716884919137">Бонусы авиакомпании 12%</div></body>')
  r=self.read('ural_smart_rules',raw)
  self.assertNotIn('12%',r['benefit_text']);self.assertIn('7%',r['benefit_text'])
 def test_gloria_actual_table_is_retained_and_matched_by_card_not_domain(self):
  r=self.read('ural_gloria_rules');self.assertEqual(r['partner_name'],'GLORIA')
  rows=r['details']['table_benefits']['components'];self.assertEqual(len(rows),3)
  self.assertEqual([x['rate']['value'] for x in rows],['5','7','10'])
 def test_rate_edit_changes_evidence_without_renaming_record(self):
  k='ural_ramada_rules';a=self.read(k)
  raw=(FIX/(k+'.html')).read_text().replace('10%','11%')
  # Required invariants are identity/contract words, not an immutable rate.
  b=self.read(k,raw);self.assertEqual(a['id'],b['id']);self.assertNotEqual(a['content_sha256'],b['content_sha256']);self.assertIn('11%',b['benefit_text'])
 def test_visotsky_room_scope_never_becomes_gold_equals_fifteen(self):
  r=self.read('ural_visotsky_rules');self.assertIn('Делюкс',r['conditions_text']);self.assertIn('Silver',r['conditions_text']);self.assertIn('Gold',r['conditions_text'])
  self.assertIn('rates_are_room_categories_not_card_tiers',r['warnings'])
 def test_wrong_partner_page_or_missing_scope_is_refused(self):
  self.assertIn('ural_ramada_rules',CONFIG)
  with self.assertRaises(ValueError):parse_known_rule('ural_ramada_rules','<body>Крылья 10%</body>',CONFIG['ural_ramada_rules']['url'],NOW)
  with self.assertRaises(ValueError):parse_known_rule('ural_ramada_rules',(FIX/'ural_ramada_rules.html').read_text(),'https://ramadayekaterinburg.com/other/',NOW)
