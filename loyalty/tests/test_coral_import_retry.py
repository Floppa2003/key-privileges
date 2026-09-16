"""Exercise actual import polling/reinstallation at the Sheets HTTP boundary."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import coral_import as g
import test_coral_import as fixture

class RecoveringSheets(fixture.MemorySheets):
    def __init__(self,failures=1,message='Resource at url not found'):
        super().__init__();self.attempts=0;self.failures=failures;self.message=message
    def request(self,method,suffix='',**kwargs):
        if method=='POST':
            for r in kwargs['json']['requests']:
                op=r['updateCells']
                if op.get('start',{}).get('rowIndex')==1:self.attempts+=1
        data=super().request(method,suffix,**kwargs)
        if method=='GET' and self.formula and self.attempts<=self.failures:
            rows=data['sheets'][0]['data'][0]['rowData']
            rows[1]['values'][0]['effectiveValue']={'errorValue':{'type':'N_A','message':self.message}}
        return data

class RetryChecks(unittest.TestCase):
    def reader(self,**kwargs):
        self.t=0
        def sleep(seconds):self.t+=seconds
        client=RecoveringSheets(**kwargs)
        reader=g.Reader('test-only','1:1',client=client,clock=lambda:self.t,sleep=sleep)
        return reader,client
    def test_transient_error_recovers_once_in_actual_reader(self):
        reader,client=self.reader()
        o=reader.read(fixture.URL)
        self.assertEqual(client.attempts,2);self.assertEqual(reader.calls,2)
        self.assertEqual(reader.observations,[o]);self.assertTrue(reader.cleanup_verified)
        self.assertIsNone(client.formula);self.assertEqual(len(reader.retries),1)
        self.assertEqual(reader.retries[0]['result'],'ok');self.assertGreaterEqual(self.t,95)
    def test_second_failure_stops_and_cleans_up(self):
        reader,client=self.reader(failures=100)
        with self.assertRaisesRegex(ValueError,'cg_import_timeout_or_error'):reader.read(fixture.URL)
        self.assertEqual(client.attempts,2);self.assertFalse(reader.observations)
        self.assertTrue(reader.cleanup_verified);self.assertEqual(reader.retries[0]['result'],'cg_import_timeout_or_error')
    def test_quota_permission_and_unknown_errors_are_not_retried(self):
        for message in ('Too many requests','Import traffic quota exceeded','Permission denied','unrecognized error'):
            with self.subTest(message=message):
                reader,client=self.reader(message=message)
                with self.assertRaises(ValueError):reader.read(fixture.URL)
                self.assertEqual(client.attempts,1);self.assertFalse(reader.retries)
                self.assertTrue(reader.cleanup_verified)
    def test_already_successful_read_is_not_repeated(self):
        reader,client=self.reader(failures=0);reader.read(fixture.URL)
        self.assertEqual(client.attempts,1);self.assertFalse(reader.retries)
    def test_discovery_errors_are_not_retried(self):
        reader,client=self.reader(failures=100)
        with self.assertRaises(ValueError):reader.read(g.ROBOTS)
        self.assertEqual(client.attempts,1);self.assertFalse(reader.retries)
    def test_request_budget_cannot_be_expanded_by_retry(self):
        reader,client=self.reader();reader.calls=g.MAX_READS-1
        with self.assertRaises(ValueError):reader.read(fixture.URL)
        self.assertEqual(client.attempts,1);self.assertEqual(reader.calls,g.MAX_READS)
        self.assertFalse(reader.retries)
    def test_global_retry_bound_and_deadline_are_respected(self):
        for mode in ('limit','deadline'):
            with self.subTest(mode=mode):
                reader,client=self.reader()
                if mode=='limit':reader.retries=[{} for _ in range(g.MAX_DETAIL_RETRIES)]
                else:self.t=g.MAX_SECONDS-100
                with self.assertRaises(ValueError):reader.read(fixture.URL)
                self.assertEqual(client.attempts,1)
    def test_bad_data_and_failed_cleanup_never_retry(self):
        for code in ('cg_formula_changed','cg_import_wide','cg_import_type_coercion','cg_cleanup_failed','cg_restriction'):
            with self.subTest(code=code):
                reader,client=self.reader()
                with patch.object(reader,'_read_once',side_effect=ValueError(code)) as attempt:
                    with self.assertRaises(ValueError):reader.read(fixture.URL)
                    self.assertEqual(attempt.call_count,1)


class RetryEvidenceChecks(unittest.TestCase):
    def bundle(self,failed=False):
        reader=fixture.Source(fail=failed);b=g.collect(reader,'1:1',fixture.NOW)
        start=datetime.fromisoformat(fixture.NOW)
        from datetime import timedelta
        def stamp(n):return (start+timedelta(seconds=n)).isoformat()
        for o in reader.observations:
            if o['url']==fixture.URL:o.update(requested_at=stamp(32),calculated_at=stamp(34))
            if o['url']==fixture.PROMO:o.update(requested_at=stamp(36),calculated_at=stamp(38))
        # Rebuild under the updated current observation metadata.
        for sid,entry in fixture.targets()[0]:
            match=next((o for o in reader.observations if o['url']==entry['url']),None)
            if match:
                row=g.map_detail(match,sid,entry,fixture.NOW)
                for i,r in enumerate(b['records']):
                    if r['id']==row['id']:b['records'][i]=row
        retry={'url':fixture.URL,'initial_reason':'cg_import_timeout_or_error','failed_at':stamp(1),
               'retry_at':stamp(31),'finished_at':stamp(35),'result':'cg_import_timeout_or_error' if failed else 'ok'}
        audit={'run_id':'1:1','commit':'a'*40,'cleanup_verified':True,'scrapingant_credits':0,
          'source_account_used':False,'started_at':fixture.NOW,'finished_at':stamp(40),
          'observations':reader.observations,'retries':[retry],'import_requests':7}
        return b,audit,datetime.fromisoformat(stamp(40))
    def check(self,b,a,clock):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);(p/'evidence.json').write_text(json.dumps(a));(p/'normalized.json').write_text(json.dumps(b))
            return g.validate_bundle(p,'1:1','a'*40,clock)
    def test_successful_retry_reconstructs_current_record(self):
        b,a,clock=self.bundle();self.assertEqual(self.check(b,a,clock),b)
    def test_failed_retry_preserves_partial_bundle(self):
        b,a,clock=self.bundle(True);self.assertEqual(self.check(b,a,clock),b)
    def test_retry_cannot_promote_success_or_hide_budget(self):
        for mutation in ('outcome','duplicate','count','timing','scope'):
            with self.subTest(mutation=mutation):
                b,a,clock=self.bundle();r=a['retries'][0]
                if mutation=='outcome':r['result']='cg_import_timeout_or_error'
                elif mutation=='duplicate':a['retries']*=2
                elif mutation=='count':a['import_requests']=len(a['observations'])
                elif mutation=='timing':r['failed_at']=r['retry_at']
                else:r['url']=g.c.CLUB+'dlya-detei/not-discovered/'
                with self.assertRaises(ValueError):self.check(b,a,clock)

if __name__=='__main__':unittest.main()
