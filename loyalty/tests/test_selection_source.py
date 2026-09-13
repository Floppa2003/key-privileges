"""Public preview evidence must not become a full personalized catalogue."""
import copy
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]))
try:
 import selection_source as source
except ImportError:
 source=None
from normalized import content_hash,validate_offer
NOW='2026-09-13T19:00:00+00:00'
CARD='<div class="loyalty-short-offers-offer-card"><h4 class="loyalty-short-offers-offer-card__info-title">Доступ в бизнес-залы</h4><p class="loyalty-short-offers-offer-card__info-text">MILE·ON·AIR</p></div>'
POPUP='<div data-element="Popup"><h2>ДОСТУП В БИЗНЕС-ЗАЛЫ</h2><div class="more-offer-info-popup"><div data-element="Text">Доступ в бизнес-залы аэропортов Москвы, Санкт-Петербурга и Екатеринбурга</div><div class="more-offer-info-popup__hint">Акция действует до 30 сентября 2026</div></div></div>'
def snapshot(card=CARD,popup=POPUP):return {'card_html':card,'popup_html':popup}
class MappingTests(unittest.TestCase):
 def setUp(self):self.assertIsNotNone(source,'Public Selection preview adapter is absent')
 def test_exact_popup_scope_and_gate_are_preserved(self):
  r=source.preview_record(snapshot(),'msk',NOW)
  self.assertEqual(r['partner_name'],'MILE·ON·AIR');self.assertEqual(r['source_id'],'t2_selection_public')
  self.assertEqual(r['record_kind'],'tier_benefit');self.assertEqual(r['source_status'],'public_preview_requires_login')
  self.assertEqual(r['valid_until'],'2026-09-30');self.assertIsNone(r['valid_from']);self.assertIsNone(r['benefit_url'])
  self.assertEqual(r['source_url'],'https://msk.t2.ru/bolshe/selection')
  self.assertEqual(r['rates'],[]);self.assertNotIn('бесплатн',r['benefit_text'].lower());validate_offer(r)
 def test_no_percent_is_inferred_from_ruble_amount(self):
  c=CARD.replace('Доступ в бизнес-залы','Скидка 500 рублей').replace('MILE·ON·AIR','Ultima Яндекс Go')
  p=POPUP.replace('ДОСТУП В БИЗНЕС-ЗАЛЫ','СКИДКА 500 РУБЛЕЙ').replace('Доступ в бизнес-залы аэропортов Москвы, Санкт-Петербурга и Екатеринбурга','Скидка 500 рублей на поездку.')
  r=source.preview_record(snapshot(c,p),'spb',NOW)
  self.assertTrue(all(x['unit']=='RUB' for x in r['rates']));self.assertEqual(r['rates'][0]['value'],'500')
 def test_only_public_popup_is_evidence_not_unrelated_page_footer(self):
  p=POPUP+'<footer>Скидка 99% всем навсегда</footer>'
  r=source.preview_record(snapshot(popup=p),'msk',NOW)
  self.assertNotIn('99%',r['conditions_text']);self.assertNotIn('99%',r['benefit_text'])
 def test_wrong_or_multiple_popup_fails_not_neighbor_benefit(self):
  for p in (POPUP.replace('ДОСТУП В БИЗНЕС-ЗАЛЫ','СКИДКА 500 РУБЛЕЙ'),POPUP+POPUP):
   with self.assertRaises(ValueError):source.preview_record(snapshot(popup=p),'msk',NOW)
 def test_login_form_is_not_a_public_offer(self):
  with self.assertRaises(ValueError):source.preview_record(snapshot(popup='<div data-element="Popup"><h2>ВОЙТИ</h2></div>'),'msk',NOW)
 def test_timestamp_is_not_expiry_when_published_hint_is_missing(self):
  p=POPUP.replace('Акция действует до 30 сентября 2026','Срок указан в личном кабинете')
  r=source.preview_record(snapshot(popup=p),'msk',NOW)
  self.assertIsNone(r['valid_until']);self.assertEqual(r['validity_status'],'not_stated')
 def test_invalid_explicit_date_is_an_error_not_unknown_expiry(self):
  with self.assertRaises(ValueError):source.preview_record(snapshot(popup=POPUP.replace('30 сентября','31 сентября')),'msk',NOW)
 def test_existing_native_identity_survives_changed_discount(self):
  a=source.preview_record(snapshot(),'msk',NOW)
  b=source.preview_record(snapshot(popup=POPUP.replace('Екатеринбурга','Сочи')),'msk',NOW)
  self.assertEqual(a['id'],b['id']);self.assertNotEqual(a['content_sha256'],b['content_sha256'])
 def test_unknown_region_is_not_an_arbitrary_destination(self):
  with self.assertRaises(ValueError):source.preview_record(snapshot(),'evil',NOW)
 def test_same_partner_with_two_different_local_cards_is_not_silently_joined(self):
  with self.assertRaises(ValueError):source.merge_previews([('msk',[snapshot(),snapshot()])],NOW)
 def test_shared_regions_join_only_with_identical_evidence(self):
  rows,meta=source.merge_previews([('msk',[snapshot()]),('spb',[snapshot()])],NOW)
  self.assertEqual(len(rows),1);self.assertEqual(meta['shared_observations_merged'],1)
  self.assertEqual([x['key'] for x in rows[0]['details']['catalog_regions']],['msk','spb']);validate_offer(rows[0])
 def test_conflicting_region_does_not_inherit_primary_conditions(self):
  other=snapshot(popup=POPUP.replace('Екатеринбурга','Сочи'))
  rows,meta=source.merge_previews([('msk',[snapshot()]),('spb',[other])],NOW)
  self.assertEqual(len(rows),1);self.assertEqual([x['key'] for x in rows[0]['details']['catalog_regions']],['msk'])
  self.assertEqual(meta['errors'][0]['reason'],'regional_terms_conflict')
 def test_record_cannot_be_promoted_to_verified_partner_offer(self):
  r=source.preview_record(snapshot(),'msk',NOW)
  r.update(record_kind='partner_offer',source_status='published',link_kind='detail_page',benefit_url=r['source_url'])
  r['content_sha256']=content_hash(r)
  with self.assertRaises(ValueError):validate_offer(r)

class CollectionTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):self.assertIsNotNone(source,'Public Selection collector is absent')
 async def test_second_region_failure_preserves_first(self):
  async def read(c,key,limit):
   if key=='msk':return [snapshot()],{'discovered':1,'errors':[]}
   raise RuntimeError('http_503')
  report={'errors':[]}
  with patch.object(source,'read_region_previews',read):rows=await source.collect_selection(SimpleNamespace(),{},report,NOW,500)
  self.assertEqual(len(rows),1);self.assertEqual(report['errors'][0]['region'],'spb')
  self.assertIn('public_preview_not_personal_catalog',report['coverage'])
 async def test_per_source_limit_is_enforced_after_region_union(self):
  other=snapshot(CARD.replace('MILE·ON·AIR','Other partner'),POPUP)
  async def read(c,key,limit):return ([snapshot()] if key=='msk' else [other]),{'discovered':1,'errors':[]}
  report={'errors':[]}
  with patch.object(source,'read_region_previews',read):rows=await source.collect_selection(SimpleNamespace(),{},report,NOW,1)
  self.assertEqual(len(rows),1);self.assertEqual(report['discovered'],2)
  self.assertTrue(any(x['reason']=='record_limit' for x in report['errors']))

class PartialPreviewTests(unittest.IsolatedAsyncioTestCase):
 async def test_bad_late_popup_does_not_discard_the_preceding_card(self):
  bad=snapshot(CARD.replace('MILE·ON·AIR','Other'),POPUP.replace('ДОСТУП В БИЗНЕС-ЗАЛЫ','ВОЙТИ'))
  async def read(c,key,limit):
   if key=='msk':return [snapshot(),bad],{'discovered':2,'errors':[]}
   raise RuntimeError('http_503')
  report={'errors':[]}
  with patch.object(source,'read_region_previews',read):rows=await source.collect_selection(SimpleNamespace(),{},report,NOW,500)
  self.assertEqual(len(rows),1);self.assertEqual(rows[0]['partner_name'],'MILE·ON·AIR')
  self.assertTrue(any(e['phase']=='preview_validation' for e in report['errors']))
