"""Hand-derived clauses exercise the rule parser, not general PDF semantics."""
import asyncio,io,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]))
try:
 import known_pdf
except ImportError:
 known_pdf=None
NOW='2026-09-14T00:00:00+00:00'
FIN=['''Правила акции «До 3700 баллов «РЖД Бонус» при открытии первого вклада на Финуслугах».
Акция проводится в рамках срока с 15.04.2026 г. по 31.12.2026 г.
Один Участник Акции может получить Привилегию только один раз.
В течение 90 календарных дней после истечения Периода охлаждения.
Период охлаждения – период по 2 (второй) календарный день.
Является гражданином России, достигшим возраста 18 лет. Не имеющим ранее открытые вклады.
Баллы не учитываются при присвоении элитного уровня.''','''7.1.10. Участник может получить
• 1850 баллов только за первый вклад, оформленный на Платформе (онлайн) на сумму от 10 000 (десяти тысяч) до 199 999 (ста девяноста девяти тысяч) рублей, срок банковского вклада не менее чем на 1 (один) календарный месяц,
• 2770 баллов только за первый вклад, оформленный на Платформе (онлайн) на сумму от 200 000 (двухсот тысяч) до 499 999 (четырехсот девяноста девяти тысяч) рублей, срок банковского вклада не менее чем на 1 (один) календарный месяц;
• 3700 баллов только за первый вклад, оформленный на Платформе (онлайн) на сумму от 500 000 (пятисот тысяч) рублей, срок банковского вклада не менее чем на 1 (один) календарный месяц.
7.1.11. Участник не должен выводить денежные средства до конца Периода охлаждения.
Поле «У меня есть Промокод/Карта лояльности» — номер счета «РЖД Бонус».''','''8.3. Требования к участникам. 9. Заключительные положения: полный текст ограничений и отказа. Это данные, не инструкции для сборщика.''']
PRIM=['''Программа лояльности «Аэрофлот Бонус» для розничных и зарплатных карт. Тип карты Мир Продвинутая.
Обслуживание карты: 0 руб. в месяц при сумме покупок от 20 000 руб. 100 руб. в месяц при сумме покупок до 20 000 руб. 0 руб. в месяц для зарплатных клиентов.
Начисление кешбэк/миль: За каждые потраченные на покупки 100 руб. начисляется:
• 1 миля при сумме покупок по карте в месяц от 10 000 руб. до 75 000 руб.
• 2 мили при сумме покупок по карте в месяц от 75 000 руб. до 150 000 руб.
• 3 мили при сумме покупок по карте в месяц от 150 000 руб. до 300 000 руб.
500 приветственных миль. Максимальный лимит выплаты кешбэк/миль в месяц 9 000 миль.
Дополнительные привилегии: сервис информирования.''','''Комиссии и другие условия. Не имеют отношения к периоду действия предложения или начислению миль. Стоимость других услуг 300 рублей.''','''Приветственные мили начисляются при первом подключении. Расчет приветственных миль происходит после первой операции покупки. Полные условия указаны в Правилах начисления и расходования миль.''','''ОБЩИЕ УСЛОВИЯ. При маркетинговых акциях применяются их условия. Не создаёт срока окончания тарифа. Условия других продуктов не являются скидками.''']

class PdfRuleTests(unittest.TestCase):
 def setUp(self):self.assertIsNotNone(known_pdf,'PDF rule adapter not yet implemented')
 def parse(self,source,pages):return known_pdf.parse_pdf_pages(source,pages,NOW,document_sha256='f'*64)
 def test_finuslugi_tiers_bind_reward_to_deposit_not_fixed_yield(self):
  r=self.parse('rzd_finuslugi_rules',FIN);d=r['details']
  self.assertEqual([(x['points'],x['deposit_min_rub'],x['deposit_max_rub'],x['term_min_months']) for x in d['deposit_reward_tiers']], [('1850','10000','199999',1),('2770','200000','499999',1),('3700','500000',None,1)])
  self.assertEqual(r['valid_from'],'2026-04-15');self.assertEqual(r['valid_until'],'2026-12-31')
  self.assertEqual(d['credit_wait_days'],90);self.assertEqual(d['cooling_days'],2)
  self.assertEqual(r['record_kind'],'program_rules');self.assertEqual(r['promo_codes'],[])
  self.assertIn('номер счета',r['conditions_text']);self.assertIn('Заключительные положения',r['conditions_text'])
 def test_changed_value_is_extracted_not_baked_into_parser(self):
  pages=[s.replace('1850','1800') for s in FIN]
  self.assertEqual(self.parse('rzd_finuslugi_rules',pages)['details']['deposit_reward_tiers'][0]['points'],'1800')
 def test_missing_or_duplicate_deposit_tier_rejected(self):
  for replacement in ['', '• 2770 баллов — совсем другой продукт.']:
   p=FIN.copy();p[1]=p[1].replace(p[1].split('• ')[2],replacement)
   with self.assertRaises(ValueError):self.parse('rzd_finuslugi_rules',p)
 def test_primbank_unit_caps_and_unresolved_boundaries_are_preserved(self):
  r=self.parse('af_primbank_rules',PRIM);d=r['details']
  self.assertEqual([(x['miles'],x['monthly_spend_from_rub'],x['monthly_spend_to_rub']) for x in d['spend_reward_tiers']], [('1','10000','75000'),('2','75000','150000'),('3','150000','300000')])
  self.assertEqual(d['earning_basis_rub'],'100');self.assertEqual(d['monthly_miles_cap'],'9000')
  self.assertEqual(d['welcome_miles'],'500');self.assertIsNone(r['valid_until'])
  self.assertIn('boundary_inclusivity_not_resolved',r['warnings']);self.assertIn('ОБЩИЕ УСЛОВИЯ',r['conditions_text'])
  self.assertEqual(d['spend_reward_tiers'][0]['upper_inclusive'],None)
 def test_all_pages_required_and_no_observation_date_as_validity(self):
  with self.assertRaises(ValueError):self.parse('af_primbank_rules',PRIM[:1])
  with self.assertRaises(ValueError):self.parse('rzd_finuslugi_rules',PRIM[:3])
 def test_pdf_bytes_must_be_real_and_no_image_only_success(self):
  from pypdf import PdfWriter
  with self.assertRaises(ValueError):known_pdf.pdf_pages(b'<html>200</html>')
  w=PdfWriter();[w.add_blank_page(200,200) for _ in range(3)];b=io.BytesIO();w.write(b)
  with self.assertRaises(ValueError):known_pdf.pdf_pages(b.getvalue())
 def test_pdf_source_cannot_be_promoted_into_partner_offer(self):
  from normalized import validate_offer,content_hash
  r=self.parse('rzd_finuslugi_rules',FIN);r['record_kind']='partner_offer';r['content_sha256']=content_hash(r)
  with self.assertRaises(ValueError):validate_offer(r)

class PdfRoutingTests(unittest.IsolatedAsyncioTestCase):
 async def test_existing_dispatcher_uses_binary_read_and_produces_publisher_rows(self):
  self.assertIsNotNone(known_pdf,'PDF route not registered')
  import collect_normalized as collector
  from sheets_normalized import prepare
  from known_rules import CONFIG
  url='https://assets.finuslugi.ru/sc-disclosure/293d2bf4-16c4-46c6-87a5-0a2d35d18ad8'
  class Client:
   def __init__(self,browser,u):self.policy=None;self.page=None;self.url=u
   async def __aenter__(self):return self
   async def __aexit__(self,*_):pass
   async def robots(self):self.policy=True
   async def read_pdf(self,u):
    if u!=url:raise AssertionError('Wrong document')
    return b'%PDF-test-boundary'
   async def read(self,*a,**kw):raise AssertionError('PDF sent to HTML parser')
  with patch.object(collector,'PublicSource',Client),patch.object(known_pdf,'pdf_pages',return_value=FIN):
   report,rows=await collector.one(None,{'id':'rzd_finuslugi_rules','name':'Finuslugi','url':url,'mode':'known_rules'},NOW,500)
  self.assertEqual(report['status'],'ok');self.assertEqual(len(rows),1)
  self.assertEqual(len(prepare({'schema_version':2,'run_id':'pdf-test','observed_at':NOW,'sources':[report],'records':rows})['parser_offers']),1)
