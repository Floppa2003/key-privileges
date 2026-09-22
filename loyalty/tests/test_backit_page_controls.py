"""Public purchase controls and rules are not optional merchant SEO copy."""
import sys,unittest
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0,str(Path(__file__).parents[1]))
import backit_source as b
from test_public_reward_sources import common
FIX=Path(__file__).parent/'fixtures_live/affordable/backit-kuper.html'
NOW='2026-09-22T10:42:11+00:00'
CARD={'url':b.ROOT+'/kuper','name':'Купер (бывший СберМаркет)'}

def no_seo():
 s=BeautifulSoup(FIX.read_text(),'html.parser')
 for n in s.select('.shop-markdown.markdown'):n.decompose()
 return s

class BackitPageControls(unittest.TestCase):
 def test_no_seo_instructions_uses_the_actual_page_buttons(self):
  r=b.parse_detail(str(no_seo()),CARD,NOW)
  self.assertIn('Купить с кэшбэком',r['redemption_text'])
  self.assertIn('Регистрация',r['redemption_text'])
  self.assertIn('одной браузерной сессии',r['conditions_text'])
 def test_optional_merchant_conditions_not_invented(self):
  s=no_seo();s.select_one('.shop-conditions').decompose()
  r=b.parse_detail(str(s),CARD,NOW)
  self.assertIn('merchant_specific_conditions_not_displayed',r['warnings'])
  self.assertIn('очисти корзину',r['conditions_text'])
 def test_missing_buttons_and_instructions_fails(self):
  s=no_seo();s.select_one('#activate-button').decompose()
  with self.assertRaises(ValueError):b.parse_detail(str(s),CARD,NOW)
 def test_observed_range_is_not_the_top_rate_for_everyone(self):
  s=BeautifulSoup(FIX.read_text(),'html.parser')
  n=s.select_one('.shop-rates .rate > span:not(.rate--old)');n.string='0.53%-10%'
  row=b.parse_detail(str(s),CARD,NOW);n=common(row)['benefits'][0]
  self.assertEqual((n['value_min'],n['value'],n['qualifier']),('0.53','10','range'))
 def test_zero_rate_scope_remains_a_condition_not_a_reward(self):
  s=BeautifulSoup(FIX.read_text(),'html.parser')
  s.select_one('.shop-rates .rate > span:not(.rate--old)').string='0%'
  row=b.parse_detail(str(s),CARD,NOW)
  self.assertNotIn('Кешбэк 0%',row['benefit_text'])
  self.assertIn('Кешбэк 0%',row['conditions_text'])
 def test_bank_names_without_word_bank_are_excluded(self):
  for name in ['ВТБ — дебетовая карта','МКБ — вклад','ОТП — кредитная карта']:
   self.assertTrue(b.EXCLUDED_NAME.search(name))
  self.assertFalse(b.EXCLUDED_NAME.search('Купер (бывший СберМаркет)'))
if __name__=='__main__':unittest.main()
