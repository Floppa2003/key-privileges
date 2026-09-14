"""Public product paths are not personal sessions; rates keep their subscription."""
import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from public_transport import allowed_request
from known_rules import parse_known_rule
URL='https://www.gazprombank.ru/personal/cards/7515685/'
NOW='2026-09-14T00:00:00+00:00'
def sample():
    return '''<div class="TariffsMsbItemContent_root__abc"><h5>Без Газпром Бонус «Плюс»</h5>Бесплатно<p>Мили «Аэрофлот Бонус» 1,5 мили за 100 ₽ покупок</p><p>Максимум миль в месяц 3 000</p><p>Переводы комиссия 1,5%</p></div>
<div class="TariffsMsbItemContent_root__abc"><h5>С Газпром Бонус «Плюс»</h5>Бесплатно — 1 месяц, далее — 399 ₽ в месяц<p>Мили «Аэрофлот Бонус» 2,5 мили за 100 ₽ покупок</p><p>Максимум миль в месяц 5 000</p></div>
<div class="Accordion_root__abc"><div><div class="Accordion_root__trigger_title__abc">Условия по карте</div></div><p>Стоимость обслуживания 0 ₽ – без дополнительных условий</p><p>Информирование об операциях В течение 1-го календарного месяца – 0 ₽, со 2 месяца – 99 ₽/мес.</p></div>
<div class="Accordion_root__abc"><div><div class="Accordion_root__trigger_title__abc">Условия программы лояльности «Аэрофлот Бонус»</div></div><p>Обязательное условие для начисления миль Минимальная сумма покупок по карте в месяц - 5 000 ₽</p><p>Программа начисления бонусных миль «Аэрофлот Бонус»</p></div>
<div class="Accordion_root__abc"><div><div class="Accordion_root__trigger_title__abc">Другая акция</div></div>Кешбэк 100%</div>'''
class PublicProductTests(unittest.TestCase):
 def test_reviewed_public_card_is_readable_without_opening_personal_accounts(self):
  self.assertTrue(allowed_request(URL,'www.gazprombank.ru'))
  for url in (URL+'login',URL+'../account','https://www.gazprombank.ru/personal/','https://www.gazprombank.ru/personal/cards/other/',URL+'?token=secret',URL+'?redirect=/personal/account','https://evil.example/personal/cards/7515685/'):
   with self.subTest(url=url):self.assertFalse(allowed_request(url,'www.gazprombank.ru'))
 def test_paid_and_free_mileage_rules_do_not_borrow_neighbour_rates(self):
  r=parse_known_rule('af_gpb_rules',sample(),URL,NOW)[0]
  d=r['details'];self.assertEqual(r['record_kind'],'program_rules')
  self.assertEqual(d['monthly_minimum_purchases_rub'],'5000')
  self.assertEqual([(x['subscription'],x['miles'],x['basis_rub'],x['monthly_cap_miles'],x['monthly_subscription_rub']) for x in d['mileage_options']],[(False,'1.5','100','3000','0'),(True,'2.5','100','5000','399')])
  self.assertEqual(d['fees']['notifications_after_first_month_rub'],'99')
  self.assertNotIn('100%',r['conditions_text']);self.assertNotIn('Другая акция',r['conditions_text'])
 def test_ambiguous_or_missing_tariff_is_not_success(self):
  for raw in (sample().replace('2,5 мили','неизвестные мили'),sample().replace('5 000 ₽',''),sample()+sample().split('<div class="Accordion')[0]):
   with self.subTest(raw=raw[:40]):
    with self.assertRaises(ValueError):parse_known_rule('af_gpb_rules',raw,URL,NOW)
if __name__=='__main__':unittest.main()

class ProductTransportTests(unittest.IsolatedAsyncioTestCase):
 def old_refused_context(self):
  from types import SimpleNamespace
  async def fetch(*args,**kwargs):raise RuntimeError('http_403')
  return SimpleNamespace(request=SimpleNamespace(fetch=fetch))
 async def test_actual_rules_collector_uses_reviewed_anonymous_http_read(self):
  from unittest.mock import patch
  import requests
  from protego import Protego
  from public_transport import PublicSource
  from known_rules import collect_known_rules
  class Response:
   status_code=200
   headers={'Content-Type':'text/html; charset=utf-8'}
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def iter_content(self,size):yield sample().encode('utf8')
  client=PublicSource(None,URL);client.policy=Protego.parse('');client.request_interval=0;client.context=self.old_refused_context()
  report={'errors':[]}
  with patch.object(requests,'get',return_value=Response()) as get:
   try:rows=await collect_known_rules(client,{'id':'af_gpb_rules','url':URL},report,NOW,100)
   except Exception as exc:self.fail('Expected reviewed anonymous HTTP product content, got '+type(exc).__name__)
  self.assertEqual(len(rows),1)
  get.assert_called_once_with(URL,headers={'User-Agent':'Mozilla/5.0'},timeout=(5,15),allow_redirects=False,stream=True)
  self.assertEqual(rows[0]['details']['mileage_options'][1]['miles'],'2.5')
 async def test_http_refusal_is_not_retried_or_reported_as_a_product(self):
  from unittest.mock import patch
  import requests
  from protego import Protego
  from public_transport import PublicSource
  from known_rules import collect_known_rules
  class Response:
   headers={'Content-Type':'text/html'}
   def __init__(self,status):self.status_code=status
   def __enter__(self):return self
   def __exit__(self,*args):pass
  for status in (302,403,429):
   with self.subTest(status=status):
    client=PublicSource(None,URL);client.policy=Protego.parse('');client.request_interval=0;client.context=self.old_refused_context()
    with patch.object(requests,'get',return_value=Response(status)) as get:
     with self.assertRaises(RuntimeError):await collect_known_rules(client,{'id':'af_gpb_rules','url':URL},{'errors':[]},NOW,100)
     get.assert_called_once()
 async def test_reviewed_transport_still_obeys_source_policy(self):
  from unittest.mock import patch
  import requests
  from protego import Protego
  from public_transport import PublicSource
  from known_rules import collect_known_rules
  client=PublicSource(None,URL);client.policy=Protego.parse('User-agent: *\nDisallow: /')
  with patch.object(requests,'get') as get:
   with self.assertRaises(RuntimeError):await collect_known_rules(client,{'id':'af_gpb_rules','url':URL},{'errors':[]},NOW,100)
   get.assert_not_called()

class ProductMileageEvidenceTests(unittest.TestCase):
 def test_transfer_commission_is_not_extracted_as_a_loyalty_benefit(self):
  r=parse_known_rule('af_gpb_rules',sample(),URL,NOW)[0]
  self.assertNotIn('комиссия',r['benefit_text'])
  self.assertIn('комиссия 1,5%',r['conditions_text'])
  self.assertEqual(r['details']['mileage_options'][0]['miles'],'1.5')
