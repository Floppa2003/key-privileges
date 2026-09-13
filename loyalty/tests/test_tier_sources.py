"""Airline tier boundaries, explicit eligibility and UI-to-panel identity."""
import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
try:
 import tier_sources as source
except ImportError:
 source=None
NOW='2026-09-13T19:00:00+00:00'
URAL='''<div class="uan-styled-text"><h2>Участие в программе</h2><p>Участие бесплатно с 2-х лет.</p>
<h2>Бонусы программы «Крылья» / как накопить/потратить бонусы</h2><p>1 бонус = 1 рубль. Бонусы начисляются на личный счёт.</p>
<h2>Синий уровень</h2><ul><li>Присваивается участнику при регистрации в программе. Срок действия уровня - 1 год с даты регистрации.</li><li>Начисление кешбэка в зависимости от тарифа:</li></ul><p><b>3%</b> от суммы авиабилета по тарифу Эконом на рейсах СНГ<br><b>7%</b> от суммы авиабилета по тарифу Бизнес на рейсах РФ</p><ul><li>Кешбэк за дополнительные услуги – 8 % от суммы услуги.</li></ul>
<h2>Серебряный уровень</h2><ul><li>Присваивается при совершении 15 полетов, либо полетов на сумму 200 000 рублей в течение 1 календарного года.</li><li>Все услуги предоставляются только держателю карты.</li></ul><p><b>4%</b> от суммы авиабилета по тарифу Эконом на рейсах СНГ</p>
<h2>Золотой уровень</h2><ul><li>Присваивается участнику <u>серебряного уровня</u> при совершении 25 полетов, либо полетов на сумму 400 000 рублей в течение 1 календарного года.</li><li>Разрешается провоз 1 места багажа до 23 кг. При информировании не менее чем за 3 часа до вылета.</li></ul><p><b>5%</b> от суммы авиабилета по тарифу Эконом на рейсах СНГ</p></div><footer>Скидка 99%</footer>'''
HEADER='''<div class="t-rec" id="rec759374982">
<div class="t396__elem status-block" data-field-left-value="12" data-field-top-value="50" data-field-width-value="193" data-field-height-value="116"></div>
<div class="t396__elem" data-elem-type="text" data-field-left-value="33" data-field-top-value="78" data-field-width-value="79" data-field-height-value="37"><div class="tn-atom">Start</div></div>
<div class="t396__elem" data-elem-type="text" data-field-left-value="33" data-field-top-value="129" data-field-width-value="150" data-field-height-value="22"><div class="tn-atom">бесплатно</div></div>
<div class="t396__elem status-block" data-field-left-value="211" data-field-top-value="50" data-field-width-value="193" data-field-height-value="116"></div>
<div class="t396__elem" data-elem-type="text" data-field-left-value="232" data-field-top-value="78" data-field-width-value="79" data-field-height-value="37"><div class="tn-atom">Basic</div></div>
<div class="t396__elem" data-elem-type="text" data-field-left-value="232" data-field-top-value="129" data-field-width-value="150" data-field-height-value="22"><div class="tn-atom">c 10 тыс. руб.</div></div>
<div class="t396__elem" data-elem-type="tooltip" data-field-left-value="320" data-field-top-value="132" data-field-width-value="16" data-field-height-value="16"><div class="tn-atom__tip-text">Потраченных на полеты с Utair, совершённые в календарном году</div></div>
</div>'''
PANEL='''<div class="t-rec description active" id="rec123"><div class="t396__elem" data-elem-type="text"><div class="tn-atom">Доступны привилегии предыдущего уровня</div></div><div class="t396__elem" data-elem-type="text"><div class="tn-atom">Двойные мили для молодежи и старшего поколения</div></div><div class="t396__elem" data-elem-type="tooltip"><div class="tn-atom__tip-text">Активируйте привилегию в профиле. <a href="https://ut0.ru/abc">Подробнее</a></div></div></div>'''
class UralTests(unittest.TestCase):
 def setUp(self):self.assertIsNotNone(source,'Airline tier adapters are absent')
 def test_three_tiers_keep_their_own_qualifications_and_restrictions(self):
  rows=source.ural_tiers(URAL,NOW);self.assertEqual(len(rows),3)
  blue,silver,gold=rows
  self.assertNotIn('23 кг',blue['benefit_text']);self.assertIn('за 3 часа',gold['benefit_text'])
  self.assertEqual(silver['details']['qualification']['flights'],15)
  self.assertEqual(silver['details']['qualification']['spend_rub'],'200000')
  self.assertEqual(silver['details']['qualification']['operator'],'OR')
  self.assertEqual(gold['details']['qualification']['required_previous_tier'],'Серебряный')
  self.assertIsNone(blue['valid_until']);self.assertTrue(blue['details']['qualification']['registration'])
 def test_unlabelled_percent_lines_are_scoped_bonus_rates_not_money_cashback(self):
  rows=source.ural_tiers(URAL,NOW)
  rates=rows[0]['details']['flight_bonus_rates']
  self.assertEqual([r['value'] for r in rates],['3','7'])
  self.assertEqual(rates[0]['reward_unit'],'program_bonus')
  self.assertIn('СНГ',rates[0]['evidence']);self.assertNotIn('99%',rows[0]['benefit_text'])
 def test_missing_or_repeated_tier_heading_fails_closed(self):
  for html in (URAL.replace('<h2>Золотой уровень</h2>',''),URAL.replace('<h2>Синий уровень</h2>','<h2>Синий уровень</h2><h2>Синий уровень</h2>')):
   with self.assertRaises(ValueError):source.ural_tiers(html,NOW)
 def test_rules_are_preserved_even_when_not_structurally_understood(self):
  html=URAL.replace('Кешбэк за дополнительные услуги','Не действует по субботам. Кешбэк за дополнительные услуги')
  self.assertIn('Не действует по субботам',source.ural_tiers(html,NOW)[0]['benefit_text'])
 def test_changed_amount_changes_content_not_tier_id(self):
  first=source.ural_tiers(URAL,NOW)[1];second=source.ural_tiers(URAL.replace('200 000','250 000'),NOW)[1]
  self.assertEqual(first['id'],second['id']);self.assertNotEqual(first['content_sha256'],second['content_sha256'])
class UtairTests(unittest.TestCase):
 def setUp(self):self.assertIsNotNone(source,'Airline tier adapters are absent')
 def test_tab_scope_uses_its_bounding_box_not_global_text_order(self):
  a=source.utair_tab(HEADER,'Start');b=source.utair_tab(HEADER,'Basic')
  self.assertEqual(a['spend_rub'],None);self.assertEqual(a['qualification_text'],'бесплатно')
  self.assertEqual(b['spend_rub'],'10000');self.assertEqual(b['window'],'calendar_year')
 def test_ambiguous_header_geometry_is_not_guessed(self):
  with self.assertRaises(ValueError):source.utair_tab(HEADER.replace('data-field-left-value="211"','data-field-left-value="12"'),'Basic')
 def test_selected_panel_keeps_tooltip_and_inheritance_evidence(self):
  tab=source.utair_tab(HEADER,'Basic')
  row=source.utair_tier(PANEL,tab,'Общие исключения: чартерные рейсы.',NOW)
  self.assertEqual(row['details']['tier'],'Basic');self.assertTrue(row['details']['inherits_previous_tiers'])
  self.assertIn('Активируйте привилегию',row['benefit_text']);self.assertIn('чартерные',row['conditions_text'])
  self.assertIsNone(row['benefit_url']);self.assertEqual(row['record_kind'],'tier_benefit')
 def test_unselected_panel_cannot_be_assigned_to_clicked_tier(self):
  with self.assertRaises(ValueError):source.utair_tier(PANEL.replace('description active','description'),source.utair_tab(HEADER,'Basic'),'',NOW)
 def test_multiple_panels_are_not_flattened_into_one_tier(self):
  with self.assertRaises(ValueError):source.utair_tier(PANEL+PANEL,source.utair_tab(HEADER,'Basic'),'',NOW)
 def test_signed_external_rules_links_are_not_persisted_as_credentials(self):
  row=source.utair_tier(PANEL.replace('https://ut0.ru/abc','https://example.com/x?Signature=abc'),source.utair_tab(HEADER,'Basic'),'',NOW)
  self.assertNotIn('Signature',str(row['details']));self.assertTrue(row['warnings'])

class SourceConflictTests(unittest.TestCase):
 def setUp(self):self.assertIsNotNone(source,'Airline tier adapters are absent')
 def test_disagreeing_intro_thresholds_are_not_silently_reconciled(self):
  self.assertTrue(hasattr(source,'utair_intro_context'),'No conflicting source-intro evidence')
  raw='<div class="t-rec">Программа лояльности Utair Status: сервисы с 10 000 ₽, потраченных на полеты.</div><div class="t-rec">Программа лояльности Utair Status: привилегии с 7 000 ₽, потраченных на полеты.</div>'
  context=source.utair_intro_context(raw)
  self.assertEqual(context['spend_rub_values'],['7000','10000']);self.assertTrue(context['conflict'])
  r=source.utair_tier(PANEL,source.utair_tab(HEADER,'Basic'),'',NOW,intro_context=context)
  self.assertIn('conflicting_intro_spend_thresholds',r['warnings'])
  self.assertEqual(r['details']['qualification']['spend_rub'],'10000')
  self.assertIn('7 000',str(r['details']['intro_context']))
