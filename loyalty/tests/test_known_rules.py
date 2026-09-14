"""Literal fixtures and negative canaries for reviewed public rule boundaries."""
import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
try:
 from known_rules import parse_known_rule
except ImportError:
 parse_known_rule=None
NOW='2026-09-14T08:00:00+00:00'
CFG=json.loads((Path(__file__).parents[1]/'known_rules.json').read_text())
def parse(sid,html):
 if parse_known_rule is None:raise AssertionError('Known-rule extraction not implemented')
 return parse_known_rule(sid,html,CFG[sid]['url'],NOW)
RETAIL='''<div class="afl"><h1>Аэрофлот Бонус</h1><h3>Условия начислений:</h3><p>1 миля начисляется за каждые потраченные 70 руб.</p><p>Мили начисляются в течение 35 дней после оплаты и доставки заказа.</p><h3>Условия списаний:</h3><p>Ограничения по использованию миль — не более 30% от итоговой суммы к оплате с учётом всех скидок, без учёта стоимости доставки.</p><p>При этом 70% от суммы чека необходимо оплатить денежными средствами.</p><p>Одновременно списывать мили Аэрофлот Бонус и бонусы Bootwood невозможно.</p></div>'''
class RuleTests(unittest.TestCase):
 def test_earning_and_redemption_are_not_a_thirty_percent_discount(self):
  r=parse('af_bootwood_rules',RETAIL+'<aside>Скидка 99% на рекламу</aside>')[0]
  self.assertEqual(r['details']['earning_rules'][0]['basis_amount'],'70')
  self.assertEqual(r['details']['redemption_rules']['max_order_percent'],'30')
  self.assertEqual(r['details']['redemption_rules']['minimum_cash_percent'],'70')
  self.assertNotIn('99%',r['conditions_text']);self.assertEqual(r['record_kind'],'program_rules')
  self.assertFalse(any(x['kind']=='discount' for x in r['rates']))
 def test_same_native_id_survives_a_rate_edit(self):
  a=parse('af_bootwood_rules',RETAIL)[0];b=parse('af_bootwood_rules',RETAIL.replace('70 руб.','80 руб.'))[0]
  self.assertEqual(a['id'],b['id']);self.assertNotEqual(a['content_sha256'],b['content_sha256'])
 def test_missing_or_duplicated_scoped_content_fails_instead_of_reading_whole_body(self):
  for html in [RETAIL.replace('class="afl"','class="renamed"'),RETAIL+RETAIL]:
   with self.assertRaises(ValueError):parse('af_bootwood_rules',html)
 def test_exact_reviewed_url_is_required(self):
  self.assertIsNotNone(parse_known_rule)
  with self.assertRaises(ValueError):parse_known_rule('af_bootwood_rules',RETAIL,'https://bootwood.com/another',NOW)
 def test_miles_expiry_is_not_program_expiry_and_codes_bind_to_age(self):
  h='''<div id="rec586475392">Поколения Utair - двойные мили. Молодежь в возрасте от 16 до 25 лет и пенсионеры в возрасте от 55 лет (для женщин), от 60 лет (для мужчин) могут получить двойные мили.</div><div id="rec586348980">Активируйте промокод для молодежи UYOUTHWM; для людей старшего поколения UPENSWM. Покупка билета и полет должны быть совершены в одном месяце. Срок действия миль по правилам программы составляет 3 года. Получите мили до 10 числа месяца, следующего за месяцем покупки билета и полета.</div>'''
  r=parse('utair_generations_rules',h)[0]
  self.assertIsNone(r['valid_until']);self.assertEqual(r['details']['reward_lifetime_years'],3)
  self.assertEqual(r['details']['audiences'][0]['promo_code'],'UYOUTHWM')
  self.assertEqual(r['details']['audiences'][0]['age_min'],16)
  self.assertEqual(r['details']['audiences'][0]['age_max'],25)
  self.assertEqual(r['details']['audiences'][1]['women_age_min'],55)
  self.assertEqual(r['details']['audiences'][1]['men_age_min'],60)
  self.assertEqual(r['details']['reward_multiplier'],2)
 def test_sim_delivery_is_free_but_replacement_price_remains_payable(self):
  h='''<div class="article-content">Замена SIM. Курьерская доставка SIM-карты. Стоимость услуги – 200 руб. Дополнительно оплачивается замена SIM-карты – 100 руб. Для участников программы T2 Selection услуга предоставляется бесплатно. На 24 часа ограничиваются SMS.</div>'''
  r=parse('t2_sim_rules',h)[0];d=r['details']['fees']
  self.assertEqual(d['delivery_standard_rub'],'200');self.assertEqual(d['replacement_rub'],'100')
  self.assertEqual(d['delivery_selection_rub'],'0')
 def test_student_relative_entitlement_expiry_is_not_guessed_year(self):
  h='''<div class="post__text">РЖД Бонус. Студенты очной формы обучения до 23 лет (включительно), граждане РФ: скидка 15%. Как подключить скидку? Активация в течение 5 рабочих дней, действует до 1 сентября следующего учебного года.</div>'''
  r=parse('rzd_student_rules',h)[0]
  self.assertIsNone(r['valid_until']);self.assertEqual(r['details']['age_max_inclusive'],23)
  self.assertEqual(r['details']['activation_workdays'],5)
 def test_x5_points_to_miles_are_not_rubles_and_related_offer_is_excluded(self):
  h='''<main><div class="w-full"><h2>О партнёре</h2><p>Аэрофлот Бонус</p></div><div class="w-full"><h2>Как воспользоваться?</h2><p>20 миль за каждые 500 баллов. Мили начисляются в течение 5 дней.</p></div><div class="w-full"><h2>Условия предложения</h2><p>Акция действует до 31 декабря 2026 года. Списанные баллы не подлежат возврату.</p></div><aside>99 миль за 1 балл</aside></main>'''
  r=parse('af_x5_rules',h)[0]
  self.assertEqual(r['details']['exchange_rule']['basis_unit'],'X5_points')
  self.assertEqual(r['details']['exchange_rule']['basis_amount'],'500')
  self.assertEqual(r['details']['exchange_rule']['miles'],'20');self.assertNotIn('99 миль',r['conditions_text'])
  self.assertEqual(r['valid_until'],'2026-12-31')
 def test_undated_comfort_base_does_not_absorb_old_multiplier(self):
  h='''<div class="news-section"><div class="t509__colwrapper">Comfort Pass стал партнером программы «Аэрофлот Бонус». Получайте 1 милю за каждые потраченные 60 рублей.</div><div class="t509__colwrapper">В три раза больше миль: 3 мили за 60 рублей, июль 2023.</div></div>'''
  r=parse('af_comfort_rules',h)[0]
  self.assertNotIn('2023',r['conditions_text']);self.assertIsNone(r['benefit_url']);self.assertIsNone(r['valid_until'])
 def test_family_rule_requires_all_operational_constraints(self):
  h='''<div id="rec774881902">Семья, совместное использование миль</div><div id="rec774882054">Объедините до 7 счетов. Покинуть Семью можно через 6 месяцев. Как минимум 299 рублей оплачиваются банковской картой. Дети до 14 лет — законный представитель. На счете приглашаемого участника нужен оплаченный совершенный перелет. Только Basic, Bronze, Silver, Gold, Platinum.</div>'''
  r=parse('utair_family_rules',h)[0]
  self.assertEqual(r['details']['family']['max_accounts'],7);self.assertEqual(r['details']['family']['minimum_membership_months'],6)
  self.assertEqual(r['details']['miles_payment']['minimum_cash_rub'],'299')
 def test_source_rule_cannot_be_relabelled_into_a_new_partner_offer(self):
  from normalized import content_hash,validate_offer
  r=parse('af_bootwood_rules',RETAIL)[0];r['record_kind']='partner_offer';r['content_sha256']=content_hash(r)
  with self.assertRaises(ValueError):validate_offer(r)
 def test_fixture_script_and_unsafe_links_do_not_become_conditions(self):
  r=parse('af_bootwood_rules',RETAIL.replace('</div>','<script>SECRET=4</script><a href="https://example.com/?token=secret">rules</a></div>'))[0]
  self.assertNotIn('SECRET',r['conditions_text']);self.assertEqual(r['details']['linked_documents'],[])

if __name__=='__main__':unittest.main()

class KnownRuleRegressionTests(unittest.TestCase):
 def test_required_campaign_url_in_plain_text_keeps_utm_and_checkout_is_separate(self):
  h='''<div class="page-content-wrap">Бронируйте с умом. Срок проведения Акции: с 01 июня 2026 года по 20 декабря 2026 года включительно. Максимальный кешбэк 10%, но не более 10 000 (десяти тысяч) рублей за одно Бронирование. Оформить бронирование с датой выезда не позднее 10 января 2027 года. Совершить переход через Акционный канал: https://101hotels.com/?utm_source=privetMIR6;</div>'''
  r=parse('mir_101_rules',h)[0]
  self.assertEqual(r['details']['required_entry_url'],'https://101hotels.com/?utm_source=privetMIR6')
  self.assertEqual(r['valid_from'],'2026-06-01');self.assertEqual(r['valid_until'],'2026-12-20')
  self.assertEqual(r['details']['checkout_deadline'],'2027-01-10')
  self.assertEqual(r['details']['cashback_cap_rub'],'10000')
 def test_coupon_activation_period_not_arbitrary_date_or_observation(self):
  h='''<div class="terms-use">Отелло, промокод AF2026: скидка 10%. Срок активации промокода: с 01 марта 2026 года по 31 мая 2026 года.</div>'''
  r=parse('promomiles_otello_rules',h)[0]
  self.assertEqual(r['validity_status'],'expired_by_published_end');self.assertEqual(r['valid_until'],'2026-05-31')
  self.assertEqual(r['details']['validity_scope'],'promo_activation_window')
 def test_iway_earning_channel_does_not_depend_on_dom_order(self):
  h='''<main><div class="promo">Аэрофлот Бонус.<div class="condition_earn">Накопить мили. При заказе через турагентство 1 миля за каждые потраченные 90 ₽. При заказе поездки в i’way 1 миля за каждые потраченные 50 ₽.</div>Использовать мили: корпоративные поездки исключены.</div></main>'''
  r=parse('af_iway_rules',h)[0];d={x['channel']:x['basis_amount'] for x in r['details']['earning_rules']}
  self.assertEqual(d,{'travel_agent':'90','direct':'50'})
 def test_changed_generations_multiplier_fails_not_hardcoded_double(self):
  h='''<div id="rec586475392">Поколения Utair - тройные мили. Молодежь от 16 до 25 лет, от 55 лет (для женщин), от 60 лет (для мужчин).</div><div id="rec586348980">для молодежи UYOUTHWM; для людей старшего поколения UPENSWM. Срок действия миль составляет 3 года. Покупка и полет в одном месяце.</div>'''
  with self.assertRaises(ValueError):parse('utair_generations_rules',h)

class SmartaviaTests(unittest.TestCase):
 def fixture(self):
  cards=''.join(f'<div class="smartup-tariff-item">Тариф 1+{i}. {count} услуг «Багаж 23 кг» со скидкой 300 ₽. {count} сегментов со скидкой 200 ₽. Оформить за {price} ₽</div>' for i,count,price in [(0,10,1190),(1,10,1990),(2,20,2790),(3,20,3490)])
  return '<div id="js-smartup-tariff-cardboard">Выберите подходящий тариф. Единая карта. Все держатели ЕКП могут купить годовую Подписку Smartavia со скидкой 20%.'+cards+'</div>'
 def test_four_plan_prices_do_not_apply_ekp_discount_silently(self):
  rs=parse('smartavia_rules',self.fixture());self.assertEqual(len(rs),5)
  self.assertEqual([r['details']['subscription_plan']['annual_rub'] for r in rs[:4]],['1190','1990','2790','3490'])
  self.assertEqual(rs[3]['details']['subscription_plan']['additional_travelers'],3)
  self.assertEqual(rs[3]['details']['subscription_plan']['flight_segments'],20)
  self.assertEqual(rs[-1]['details']['discount_basis'],'annual_subscription_not_air_ticket')
  self.assertIsNone(rs[0]['valid_until'])
 def test_missing_duplicate_or_unknown_plan_label_rejected(self):
  for a,b in [('Тариф 1+2','Тариф 1+3'),('Тариф 1+2','Тариф X+2')]:
   with self.assertRaises(ValueError):parse('smartavia_rules',self.fixture().replace(a,b))
