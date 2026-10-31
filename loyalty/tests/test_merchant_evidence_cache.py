import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import merchant_evidence as e
import merchant_queue as q
from test_merchant_evidence import record


class EvidenceCacheTests(unittest.TestCase):
    def document(self,row):
        page='Full current original page'
        text=page+e.snapshot_text({'source_records':[row]})
        return {'target':{'partner':'X','program':'P','as_of':'2026-10-31'},'text':text,'images':[b'png'],
                'source':{'collector_context_start':len(page)}}

    def test_native_json_field_order_does_not_create_new_input(self):
        first={'id':1,'name':'Target','description':'Original terms'}
        second=dict(reversed(list(first.items())))
        self.assertEqual(e.native_text([first]),e.native_text([second]))

    def test_collection_metadata_does_not_exhaust_quota_on_unchanged_terms(self):
        first=record();first['details'].update(source_run='1',capture_sha256='aaa')
        second=copy.deepcopy(first);second['observed_at']='2026-10-31T13:00:00Z'
        second['details'].update(source_run='2',capture_sha256='bbb')
        a=self.document(first);b=self.document(second)
        self.assertNotEqual(a['text'],b['text'])  # the full observations are still sent/stored
        self.assertEqual(q.fingerprint(a,{},'prompt'),q.fingerprint(b,{},'prompt'))

    def test_real_source_dates_and_conditions_invalidate_cache(self):
        first=record();second=copy.deepcopy(first)
        second['details']['public_item']['description']='New conditions'
        self.assertNotEqual(q.fingerprint(self.document(first),{},'prompt'),q.fingerprint(self.document(second),{},'prompt'))
        second=copy.deepcopy(first);second['details']['public_item']['date_of_expiry']='2026-12-01'
        self.assertNotEqual(q.fingerprint(self.document(first),{},'prompt'),q.fingerprint(self.document(second),{},'prompt'))

    def test_unknown_or_broken_snapshot_metadata_falls_back_to_exact_input(self):
        doc=self.document(record());doc['source']['collector_context_start']=1
        self.assertEqual(e.fingerprint_text(doc),doc['text'])

if __name__=='__main__':unittest.main()
