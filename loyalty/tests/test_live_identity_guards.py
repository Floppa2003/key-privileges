"""Live amounts, codes and cardinalities must not be page-identity predicates."""
import sys,unittest
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0,str(Path(__file__).parents[1]))
from known_rules import CONFIG,parse_known_rule
from partner_pages import extract_partner_page
NOW='2026-09-14T18:00:00+00:00'
def parse(s,h):return parse_known_rule(s,h,CONFIG[s]['url'],NOW)

class LiveIdentityGuards(unittest.TestCase):
 def test_sfera_and_rgo_accept_new_discount_not_old_percentage(self):
  for rate in (13,27):
   r=parse('ekp_sfera_rules',f'<div class="n2-ss-slide-11">Единая карта. Косметология. Скидка {rate}%.</div>')[0]
   self.assertIn(str(rate),{x['value'] for x in r['rates']})
   h=f'<div class="accordion"><div class="accordion__title-text">Перечень льготных категорий</div><p>На скидку в {rate}% имеют право члены Русского географического общества.</p></div>'
   r=parse('rgo_headquarters_rules',h)[0]
   self.assertIn(str(rate),{x['value'] for x in r['rates']})
 def test_mixx_price_is_not_a_document_identity_marker(self):
  for price in (699,829):
   h=f'<div class="option-detail-t2-header-card">MiXX M</div><div class="terms-of-service">в месяц {price} ₽</div><div class="option-detail-t2-other-conditions-container">Тариф Федеральный исключен</div>'
   r=parse('t2_mixx_rules',h)[0]
   self.assertEqual(r['details']['subscription']['monthly_rub'],str(price))
 def test_family_changed_account_limit_cash_minimum_and_duration(self):
  h='<div id="rec774881902">Семья, использование миль</div><div id="rec774882054">Объедините до 9 счетов. Выход через 8 месяцев. Как минимум 399 рублей оплачиваются картой.</div>'
  r=parse('utair_family_rules',h)[0]
  self.assertEqual(r['details']['family']['max_accounts'],9)
  self.assertEqual(r['details']['family']['minimum_membership_months'],8)
  self.assertEqual(r['details']['miles_payment']['minimum_cash_rub'],'399')
 def test_cashback_cap_and_percentage_are_not_old_snapshot_requirements(self):
  h='<div class="page-content-wrap">Бронируйте с умом. Срок проведения Акции: с 01 июня 2027 года по 20 декабря 2027 года. Кешбэк 14%, но не более 12 500 (суммы) рублей за одно Бронирование. Дата выезда не позднее 10 января 2028 года. Акционный канал: https://101hotels.com/?utm_source=newCampaign;</div>'
  r=parse('mir_101_rules',h)[0]
  self.assertEqual(r['details']['cashback_cap_rub'],'12500')
  self.assertEqual(r['valid_until'],'2027-12-20')
  h='<div class="aeMobilePad main">Аэроэкспресс: кешбэк СБП 9%. Получить кешбэк можно до 31 декабря 2027 года.</div>'
  r=parse('mir_aeroexpress_rules',h)[0]
  self.assertIn('9',{x['value'] for x in r['rates']})
 def test_changed_coupon_and_year_do_not_reuse_old_code_title(self):
  h='<div class="terms-use">Отелло, промокод NEXT77: скидка 14%. Срок активации промокода: с 01 марта 2027 года по 31 мая 2027 года.</div>'
  r=parse('promomiles_otello_rules',h)[0]
  self.assertNotIn('AF2026',r['title']);self.assertNotIn('AF2026',r['conditions_text'])
  self.assertEqual(r['valid_until'],'2027-05-31')
  self.assertIn('NEXT77',r['promo_codes'])
 def test_changed_wings_coupons_remain_live_page_data(self):
  h='<div class="ft offset__24">Крылья: скидка 13% по промокоду NEW13, скидка 21% по промокоду NEW21.</div>'
  r=parse('ural_carsgo_rules',h)[0]
  self.assertEqual({x['value'] for x in r['rates']},{'13','21'})
  self.assertIn('NEW21',r['conditions_text'])
 def test_smartavia_new_plan_count_and_multidigit_companions(self):
  for labels in ([0,4],[0,1,2,4,12]):
   cards=''.join(f'<div class="smartup-tariff-item">Тариф 1+{n}. 12 услуг «Багаж 24 кг» со скидкой 450 ₽. 14 сегментов со скидкой 390 ₽. Оформить за {2500+n} ₽</div>' for n in labels)
   h='<div id="js-smartup-tariff-cardboard">Выберите подходящий тариф. Единая карта. Все держатели ЕКП могут купить годовую Подписку Smartavia со скидкой 19%.'+cards+'</div>'
   rs=parse('smartavia_rules',h)
   self.assertEqual(len(rs),len(labels)+1)
   self.assertEqual([r['details']['subscription_plan']['additional_travelers'] for r in rs[:-1]],labels)
 def test_askona_changed_base_and_dated_reward_stay_separate(self):
  for value,base in [('2','150'),('2,5','125')]:
   h=f'<div id="popup-rules">Аэрофлот Бонус. Участники получают {value} мили за каждые {base} рублей в Askona. В период с 01.08.2026 по 31.08.2026 за каждые потраченные 100 рублей начисляется 4 мили в Askona Home.</div>'
   rs=extract_partner_page('af_askona',BeautifulSoup(h,'html.parser'),'https://www.askona.ru/landing/aeroflot/',NOW)
   self.assertEqual(len(rs),2)
   self.assertIn(value,rs[0]['benefit_text']);self.assertIn(base,rs[0]['benefit_text'])
   self.assertNotIn('4 мили',rs[0]['benefit_text']);self.assertIn('4 мили',rs[1]['benefit_text'])
 def test_vtb_footer_is_markup_not_a_phone_number(self):
  from recovered_sources import parse_bank_page
  h='<h1>Дебетовая карта Привилегия Аэрофлот</h1><section class="xNativeSection">Дебетовая карта Привилегия Аэрофлот</section><section class="xNativeSection">Как начисляются мили по карте ВТБ. За каждые 120 ₽ вы получите 5 мили.</section>'
  for phone in ('2000','9000'):
   footer=f'<section class="xNativeSection"><div class="footerstyles__Container-footer-new__dynamic">{phone} Бесплатно с мобильного. Справочный кешбэк 77%.</div></section>'
   r=parse_bank_page('af_vtb_rules',h+footer,NOW)
   self.assertNotIn('77%',r['conditions_text']);self.assertNotIn(phone,r['conditions_text'])
   self.assertEqual(r['details']['earning_rules'][0]['basis_amount'],'120')
 def test_askona_ambiguous_or_only_dated_rate_is_not_base(self):
  for body in ['В период с 01.08.2026 по 31.08.2026 участникам начисляется 1 миля за каждые 100 рублей в Askona.', '1 миля за каждые 100 рублей. 2 мили за каждые 100 рублей.']:
   h='<div id="popup-rules">Аэрофлот Бонус. '+body+'</div>'
   with self.assertRaises(ValueError):extract_partner_page('af_askona',BeautifulSoup(h,'html.parser'),'https://www.askona.ru/landing/aeroflot/',NOW)

if __name__=='__main__':unittest.main()
