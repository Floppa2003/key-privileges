"""Source-observed non-tariff coupon and Latin-ruble label in Backit tables."""
import sys,unittest
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0,str(Path(__file__).parents[1]))
import backit_source as b
from test_public_reward_sources import common
FIX=Path(__file__).parent/'fixtures_live/affordable/backit-kuper.html'
NOW='2026-09-22T10:42:11+00:00'
CARD={'url':b.ROOT+'/kuper','name':'Купер (бывший СберМаркет)'}
class MixedTariffs(unittest.TestCase):
 def test_coupon_in_tariff_table_not_made_into_cashback(self):
  s=BeautifulSoup(FIX.read_text(),'html.parser')
  s.select_one('.shop-rates').append(BeautifulSoup('<div class="row"><div class="name">VS1857 промокод на скидку 200 руб при первом заказе от 1000 руб.</div><div class="rate"><span></span></div></div>','html.parser'))
  r=b.parse_detail(str(s),CARD,NOW)
  self.assertEqual(len(common(r)['benefits']),3)
  self.assertIn('VS1857',r['conditions_text'])
  self.assertIn('VS1857',str(r['promo_codes']))
  self.assertNotIn('200',r['benefit_text'])
 def test_empty_unexplained_tariff_still_fails(self):
  s=BeautifulSoup(FIX.read_text(),'html.parser');s.select_one('.shop-rates .rate span').string=''
  with self.assertRaises(ValueError):b.parse_detail(str(s),CARD,NOW)
 def test_actual_latin_p_ruble_typo_is_scoped_and_normalized(self):
  s=BeautifulSoup(FIX.read_text(),'html.parser');s.select_one('.shop-rates .rate span').string='301 p.'
  r=b.parse_detail(str(s),CARD,NOW)
  self.assertIn('301 р.',r['benefit_text'])
  self.assertEqual(common(r)['benefits'][0]['unit'],'RUB')
  self.assertEqual(r['details']['public_reward_evidence']['tariffs'][0]['rate'],'301 p.')
 def test_acquisition_card_and_return_to_catalogue_not_shopping_offer(self):
  self.assertTrue(b.EXCLUDED_NAME.search('МТС Деньги - Дебетовая карта'))
  raw='<html><head><title>Backit</title></head><body><a class="mu-store__wrapper" href="/ru/cashback/shops/kuper">Купер</a></body></html>'
  with self.assertRaisesRegex(b.ExcludedOffer,'replaced_by_catalogue'):b.parse_detail(raw,CARD,NOW)
if __name__=='__main__':unittest.main()
