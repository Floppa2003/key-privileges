import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from adapters import extract
NOW='2026-09-12T20:00:00+00:00'
class NordwindTests(unittest.TestCase):
 def test_exact_hotel_source_preserves_rate_and_exclusions(self):
  raw=Path(__file__).with_name('fixtures_live').joinpath('nordwind_domina.html').read_text()
  try:rows=extract('nordwind_domina',raw,'https://dominapulkovo.ru/nordwind',NOW)
  except (ValueError,KeyError):rows=[]
  self.assertEqual(len(rows),1)
  row=rows[0]
  self.assertEqual(row['partner_name'],'Domina Пулково')
  self.assertIn('При условии оплаты третьими лицами',row['conditions_text'])
  self.assertIn('При долгосрочной аренде апартаментов',row['conditions_text'])
  rate=row['details']['earning_rule']
  self.assertEqual((rate['value'],rate['unit'],rate['basis_amount'],rate['basis_unit']),('1','miles','100','RUB'))
  self.assertIsNone(row['valid_until'])
 def test_wrong_program_source_is_rejected(self):
  raw='<main><section class="section">Other hotel Скидка 25%</section></main>'
  with self.assertRaises((ValueError,KeyError)):
   extract('nordwind_domina',raw,'https://dominapulkovo.ru/nordwind',NOW)
