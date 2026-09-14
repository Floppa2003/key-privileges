import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
try:
 from unified_publish import UnifiedSheets
except ImportError:UnifiedSheets=None
from sheets_sync import Sheets
class PublishTests(unittest.TestCase):
 def test_dedicated_writer_does_not_write_source_tabs(self):
  self.assertIsNotNone(UnifiedSheets,'Dedicated writer missing')
  s=UnifiedSheets('fixture','token')
  with self.assertRaises(ValueError):s.ensure_tab('parser_offers')
 def test_new_bound_does_not_expand_legacy_writer(self):
  self.assertEqual(getattr(Sheets,'max_rows',None),5000)
  self.assertEqual(getattr(UnifiedSheets,'max_rows',None),30000)
if __name__=='__main__':unittest.main()

class QuotaTests(unittest.TestCase):
 def test_live_requests_are_paced_without_affecting_existing_writer(self):
  from unittest.mock import patch
  import unified_publish
  now=[0.0];times=[]
  def request(*a,**kw):times.append(now[0]);return {}
  def sleep(t):now[0]+=t
  with patch.object(Sheets,'request',request),patch.object(unified_publish,'time',create=True) as clock:
   clock.monotonic.side_effect=lambda:now[0];clock.sleep.side_effect=sleep
   client=UnifiedSheets('fixture','token');client.request('GET');client.request('GET')
  self.assertGreaterEqual(times[1]-times[0],1.0)
 def test_only_explicit_quota_refusal_retries_not_ambiguous_network_failure(self):
  from unittest.mock import patch
  import unified_publish
  attempts=[]
  def request(*a,**kw):
   attempts.append(1)
   if len(attempts)==1:raise RuntimeError('Google Sheets HTTP 429')
   return {'ok':True}
  with patch.object(Sheets,'request',request),patch.object(unified_publish,'time',create=True) as clock:
   clock.monotonic.return_value=0
   try:result=UnifiedSheets('fixture','token').request('POST',':batchUpdate')
   except RuntimeError:result=None
   self.assertEqual(result,{'ok':True})
  self.assertEqual(len(attempts),2)
