import json,sys,unittest,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from adapters import extract,s7_detail,mir_detail
from fixtures import fixture
NOW='2026-09-12T15:00:00+00:00'
class AdapterTests(unittest.TestCase):
 def test_moskvich_does_not_shift_benefits_to_next_card(self):
  rs=extract('moskvich',fixture('moskvich.html'),'https://moskvichmag.ru/programma-loyalnosti/',NOW)
  self.assertEqual(len(rs),3)
  self.assertIn('15%',rs[0]['benefit_text']);self.assertIn('Перспектива',rs[0]['partner_name'])
  self.assertIsNone(rs[0]['benefit_url']);self.assertEqual(rs[0]['link_kind'],'page_block')
 def test_noname_pairs_by_card_geometry_not_dom_order(self):
  rs=extract('noname',fixture('noname.html'),'https://nonameburo.com/card',NOW)
  self.assertEqual(len(rs),6)
  lookup={r['partner_name'].lower():r for r in rs}
  self.assertIn('10%',lookup['studio 29']['benefit_text'])
  self.assertIn('20%',lookup['my dear petra']['benefit_text'])
  self.assertIn('200 000',lookup['ex bags']['benefit_text'])
  self.assertIn('5 часов',lookup['lobster studio']['benefit_text'])
  self.assertNotIn('экскурси',lookup['времена года кинотеатр']['benefit_text'].lower())
 def test_noname_ambiguous_two_labels_rejects_instead_of_guessing(self):
  html='''<div class="t-rec" id="rec1"><div class="t396__elem" data-elem-id="1" data-field-top-value="260" data-field-left-value="10"><div class="tn-atom">Shop A</div></div><div class="t396__elem" data-elem-id="2" data-field-top-value="260" data-field-left-value="11"><div class="tn-atom">Shop B</div></div><div class="t396__elem" data-elem-id="3" data-field-top-value="300" data-field-left-value="10"><div class="tn-atom">Скидка 10% при демонстрации карты</div></div></div>'''
  with self.assertRaises(ValueError):extract('noname',html,'https://nonameburo.com/card',NOW)
 def test_ural_uses_partner_block_and_preserves_tier_table(self):
  rs=extract('ural',fixture('ural.html'),'https://www.uralairlines.ru/partners/',NOW)
  self.assertEqual(len(rs),4);self.assertTrue(any(r['tables'] for r in rs))
  for r in rs:self.assertIn('#partner_',r['benefit_url']);self.assertNotEqual(r['partner_name'],r['benefit_text'])
 def test_rgo_retains_karting_gift(self):
  rs=extract('rgo',fixture('rgo_detail.html'),'https://rgo.ru/membership/loyalty-program/gostinitsa-paddok-3-zvezdy/',NOW)
  self.assertEqual(len(rs),1);self.assertIn('картинг',rs[0]['conditions_text'].lower())
 def test_s7_extracts_only_this_partner_not_other_offers(self):
  state=json.loads(fixture('s7_detail.json'))
  rs=s7_detail(state,'https://marketplace.s7.ru/partners/offer/flowwow',NOW)
  self.assertEqual(len(rs),1);r=rs[0]
  self.assertIn('Флаувау',r['partner_name']);self.assertIn('17%',r['benefit_text'])
  self.assertIn('1500',r['redemption_text'].replace(' ',''));self.assertIn('не суммируется',r['conditions_text'].lower())
  self.assertNotIn('outLink',json.dumps(r));self.assertNotIn('UNRELATED_CANARY',json.dumps(r))
 def test_medi_does_not_omit_insurance_exclusion(self):
  rs=extract('sogaz_medi',fixture('sogaz_medi.html'),'https://medi.spb.ru/medi/spetspredlozheniya/partnerskie-programmy/sogaz/',NOW)
  self.assertEqual(len(rs),1);self.assertIn('ОМС',rs[0]['conditions_text'])
 def test_rusimp_preserves_two_plan_prices(self):
  rs=extract('rusimp',fixture('rusimp.html'),'https://www.rusimp.su/membership/friends',NOW)
  self.assertEqual(len(rs),2)
  self.assertIn('5 000',rs[0]['conditions_text']);self.assertIn('7 500',rs[1]['conditions_text'])
  self.assertIn('гостя',rs[1]['benefit_text'])
 def test_archive_heading_is_not_ignored(self):
  rs=extract('promomiles',fixture('promomiles.html'),'https://promomiles.aeroflot.ru/',NOW)
  self.assertEqual(len(rs),4);self.assertTrue(all(r['source_status']=='archived' for r in rs))
if __name__=='__main__':unittest.main()

class AdditionalAdapterTests(unittest.TestCase):
 def test_mir_dates_and_sbp_not_taken_from_neighbor_promotions(self):
  d=json.loads(fixture('mir_detail.json'))
  r=mir_detail(d,'https://vamprivet.ru/promo/transport/ekspress-v-aeroport-s-vygodoy-i-komfortom-1/',NOW)[0]
  self.assertEqual(r['valid_until'],'2026-09-30');self.assertEqual(r['rates'][0]['value'],'5')
  self.assertEqual(r['details']['payment_badges'],['СБП'])
  self.assertIn('1 500',r['conditions_text']);self.assertNotIn('iframe',json.dumps(r))
 def test_neva_other_promotions_are_excluded(self):
  rs=extract('ekp_neva',fixture('ekp_neva.html'),'https://neva.travel/ru/promotions/skidka-dlya-derzhateley-edinoy-karty-peterburzhtsa/',NOW)
  self.assertEqual(len(rs),1);self.assertIn('100 руб',rs[0]['conditions_text']);self.assertNotIn('50%',rs[0]['conditions_text'])
 def test_azimut_platinum_only_perk_does_not_become_universal(self):
  rs=extract('azimut',fixture('azimut.html'),'https://azimuthotels.com/ru/info/bonus',NOW)
  breakfast=next(r for r in rs if 'завтрак' in r['benefit_text'].lower())
  self.assertEqual([x['included'] for x in breakfast['details']['tier_values']],[False,False,False,True])

class MoreBoundaryTests(unittest.TestCase):
 def test_active_campaign_before_archive_heading_is_not_archived(self):
  card='<a class="promotion-mini" href="/act/{code}"><div class="promotion-mini__title">{code}</div><div class="promotion-mini__text">Скидка 10%</div></a>'
  raw='<h2>Текущие акции</h2>'+card.format(code='live')+'<h2>Завершенные акции</h2>'+card.format(code='old')
  rows=extract('promomiles',raw,'https://promomiles.aeroflot.ru/',NOW)
  self.assertEqual([r['source_status'] for r in rows],['published','archived'])

class UralJsonTests(unittest.TestCase):
 def test_catalog_json_retains_partner_id_category_and_card_specific_terms(self):
  from adapters import ural_catalog
  d={'category':[{'id':'3','name':'Отель'}],'partners':[{'id':'123','name':'Отель A','category':'3','city':['20'],'text':{'preview':'Описание отеля','detail':'<p>Скидка 10% для синей карты.</p><p>Без суммирования с акциями.</p>'}}]}
  rs=ural_catalog(d,'https://www.uralairlines.ru/partners/?ajax=partners&action=default',NOW)
  self.assertEqual(len(rs),1);r=rs[0];self.assertEqual(r['native_id'],'partner_123');self.assertEqual(r['category'],'Отель')
  self.assertIn('10%',r['benefit_text']);self.assertIn('Без суммирования',r['conditions_text'])

class KeyTests(unittest.TestCase):
 def test_special_offer_reordering_does_not_change_identity(self):
  from adapters import key_catalog
  data={'partners':[],'special_offers':{'ru':['Скидка 10% на A','Подарок в B']},'source_urls':{'base_catalog':'https://traveltg-bot.netlify.app/lib/data.js'},'fetched_at':NOW,'remote_ok':True}
  a=key_catalog(data,NOW);data['special_offers']['ru'].reverse();b=key_catalog(data,NOW)
  self.assertEqual(len(a),2);self.assertEqual({x['id'] for x in a},{x['id'] for x in b})
