"""Real read/normalize/write pipeline; only Google HTTP is replaced in memory."""
import copy,contextlib,io,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from test_sync import FakeSheets
from unified_publish import UnifiedSheets,publish_all
from unified_inputs import HEADERS
from unified_normalization import INPUT_TABS
from unified_views import SCHEMAS

class FakeUnified(UnifiedSheets,FakeSheets):
 def __init__(self):
  self.tabs={};self.calls=[];self.source_reads=0;self.change_at=None;self.corrupt=False
  for name,(header,width) in INPUT_TABS.items():
   self.tabs[name]={'properties':{'sheetId':len(self.tabs)+1,'title':name,'gridProperties':{'rowCount':header+3,'columnCount':width}},'values':[[] for _ in range(header-1)]+[HEADERS[name].copy()]}
  self.tabs['yandex_discounts_complete_all']['values'].append(['Demo','','https://example.com','Discount 10%','SYNTHETIC_ONLY','2025-12-31','show employee badge'])
 def request(self,method,suffix='',**kwargs):
  self.calls.append((method,suffix))
  if method=='GET' and kwargs.get('params',{}).get('ranges'):
   self.source_reads+=1
   if self.source_reads==self.change_at:self.tabs['yandex_discounts_complete_all']['values'][-1][3]='Discount 20%'
   name=kwargs['params']['ranges'].split('!')[0].strip("'")
   vals=copy.deepcopy(self.tabs[name]['values'])
   return {'sheets':[{'properties':{'title':name},'data':[{'rowData':[{'values':[{'userEnteredValue':{'stringValue':v}} if v!='' else {} for v in row]} for row in vals]}]}]}
  if method=='POST':
   for req in kwargs['json']['requests']:
    if 'setBasicFilter' in req:
     f=req['setBasicFilter']['filter'];tab=next(x for x in self.tabs.values() if x['properties']['sheetId']==f['range']['sheetId']);self.assert_owned(tab);tab['filter']=copy.deepcopy(f)
  return FakeSheets.request(self,method,suffix,**kwargs)
 @staticmethod
 def assert_owned(table):
  if table['properties']['title'] not in SCHEMAS:raise AssertionError('Wrote to a source tab')

class LivePipelineTests(unittest.TestCase):
 def test_real_pipeline_keeps_source_and_literal_code_private_in_stdout(self):
  s=FakeUnified();before=copy.deepcopy(s.tabs);out=io.StringIO()
  with contextlib.redirect_stdout(out):result=publish_all(as_of='2026-09-14',client=s)
  self.assertNotIn('SYNTHETIC_ONLY',out.getvalue())
  self.assertEqual(result['audit']['output_records'],1)
  for name in INPUT_TABS:self.assertEqual(s.tabs[name],before[name])
  rows=s.tabs['normalized_records']['values'];self.assertEqual(rows[1][rows[0].index('Статус срока')],'expired')
  codes=s.tabs['normalized_codes']['values'];self.assertEqual(codes[1][4],'SYNTHETIC_ONLY')
  manifest=next(r for r in s.tabs['normalization_audit']['values'] if r and r[0]=='manifest');self.assertEqual(manifest[4],'verified')
 def test_recalculation_retires_old_terms_and_keeps_manual_note(self):
  s=FakeUnified()
  with contextlib.redirect_stdout(io.StringIO()):publish_all(as_of='2026-09-14',client=s)
  name='normalized_benefits';row=s.tabs[name]['values'][1];oldid=row[0];row.append('manual-note')
  s.tabs['yandex_discounts_complete_all']['values'][-1][3]='Discount 20%'
  with contextlib.redirect_stdout(io.StringIO()):publish_all(as_of='2026-09-14',client=s)
  old=next(r for r in s.tabs[name]['values'] if r and r[0]==oldid)
  self.assertEqual(old[-1],'manual-note');self.assertEqual(old[len(SCHEMAS[name])-2],'retired_from_normalization')
  self.assertTrue(any(r[5]=='20' and r[-2]=='current' for r in s.tabs[name]['values'][1:] if len(r)==len(SCHEMAS[name])))
 def test_changed_inputs_do_not_get_verified_manifest(self):
  s=FakeUnified();s.change_at=11
  with self.assertRaises(ValueError),contextlib.redirect_stdout(io.StringIO()):publish_all(as_of='2026-09-14',client=s)
  manifest=next(r for r in s.tabs['normalization_audit']['values'] if r and r[0]=='manifest');self.assertEqual(manifest[4],'publishing')
 def test_derived_values_corruption_is_not_success(self):
  s=FakeUnified();s.corrupt=True
  with self.assertRaises(ValueError),contextlib.redirect_stdout(io.StringIO()):publish_all(as_of='2026-09-14',client=s)
 def test_changed_inputs_before_first_write_leave_destination_absent(self):
  s=FakeUnified();s.change_at=6
  with self.assertRaises(ValueError):publish_all(as_of='2026-09-14',client=s)
  self.assertNotIn('normalization_audit',s.tabs)

if __name__=='__main__':unittest.main()
