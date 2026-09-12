import unittest
from test_sync import FakeSheets
class WideSheets(FakeSheets):
 schemas={'parser_offers':[f'Field {i}' for i in range(25)]}
class WideTests(unittest.TestCase):
 def test_wide_rows_keep_manual_column_and_are_idempotent(self):
  s=WideSheets();row=['id']+[str(i) for i in range(24)]
  self.assertEqual(s.upsert('parser_offers',[row]),1)
  s.tabs['parser_offers']['values'][1].append('manual')
  self.assertEqual(s.upsert('parser_offers',[row]),0)
  changed=row.copy();changed[23]='new hash'
  self.assertEqual(s.upsert('parser_offers',[changed]),1)
  self.assertEqual(s.tabs['parser_offers']['values'][1][25],'manual')
  self.assertEqual(s.tabs['loyalty_partner_benefits']['values'],[['DO NOT TOUCH']])
 def test_old_intake_still_uses_nine_managed_columns(self):
  s=FakeSheets();row=['id']+['value']*8
  self.assertEqual(s.upsert('parser_inbox',[row]),1)
  self.assertEqual(len(s.tabs['parser_inbox']['values'][0]),10)
if __name__=='__main__':unittest.main()
