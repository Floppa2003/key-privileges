"""The real native row -> normalization -> reader path retains reversible holds."""
import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from test_public_reward_sources import kuper,NOW
from test_sync import FakeSheets
from sheets_normalized import SCHEMAS,prepare,NormalizedSheets
from source_lifecycle import attach_inventory,reconcile_rows,health_summary
from unified_normalization import make_input,normalize_record
from catalogue_view import record_row

def payload(record,*,disabled=False,failed=False):
    report=dict(source_id=record['source_id'],name=record['program'],root=record['source_url'],
        status='failed' if failed else 'ok',normalized=0 if disabled else 1,
        discovered=1,failed=int(failed),coverage='fixture',region=None,
        errors=[{'reason':'http_403'}] if failed else [],observed_at=NOW)
    attach_inventory(report,[record['source_url']],[{'url':record['source_url'],
        'reason':'source_disclosed_temporarily_disabled'}] if disabled else [])
    return dict(schema_version=2,run_id='fixture:1',observed_at=NOW,
                records=[] if disabled else [record],sources=[report])

def reader(values,as_of=NOW[:10]):
    r=make_input(dict(id=values[0],origin='parser_offers',row=2,
      fields={h:{'value':v} for h,v in zip(SCHEMAS['parser_offers']+['Ручной комментарий'],values)}))
    return record_row(normalize_record(r,as_of=as_of),as_of)

class NativeLifecyclePipeline(unittest.TestCase):
    def test_upsert_hold_restore_and_no_manual_or_offer_time_loss(self):
        r=kuper();active=payload(r);values=prepare(active)['parser_offers'][0]
        memory=FakeSheets()
        memory.tabs['parser_offers']={'properties':{'title':'parser_offers','sheetId':30,
          'gridProperties':{'rowCount':5000,'columnCount':26}},
          'values':[SCHEMAS['parser_offers']+['Ручной комментарий'],values+['сохранить заметку']]}
        client=NormalizedSheets('fixture-sheet','fixture-token');client.request=memory.request
        self.assertIsNone(reader(values)[1])
        old=copy.deepcopy(memory.tabs['parser_offers']['values'])
        disabled=payload(r,disabled=True)
        rows=reconcile_rows(disabled,old,prepare(disabled)['parser_offers'])
        self.assertEqual(client.upsert('parser_offers',rows,expected_before=[v[:25] for v in old]),1)
        held=memory.tabs['parser_offers']['values'][1]
        self.assertEqual(held[:20],old[1][:20]);self.assertEqual(held[21:],old[1][21:])
        self.assertIsNone(reader(held)[0]);self.assertIn('не подтвердил',reader(held)[1])
        snapshot=copy.deepcopy(memory.tabs['parser_offers']['values'])
        failed=payload(r,disabled=True,failed=True)
        self.assertEqual(reconcile_rows(failed,snapshot,[]),[])
        self.assertEqual(memory.tabs['parser_offers']['values'],snapshot)
        restored=reconcile_rows(active,snapshot,prepare(active)['parser_offers'])
        self.assertEqual(client.upsert('parser_offers',restored,expected_before=[v[:25] for v in snapshot]),1)
        self.assertEqual(memory.tabs['parser_offers']['values'],old)
    def test_source_health_cannot_pass_empty_or_incomplete_catalogue(self):
        r=kuper();good=payload(r)
        self.assertTrue(health_summary(good)[0]['healthy'])
        fail=payload(r,disabled=True,failed=True)
        self.assertFalse(health_summary(fail)[0]['healthy'])
        no_manifest=payload(r);no_manifest['sources'][0].pop('inventory_v1')
        self.assertFalse(health_summary(no_manifest)[0]['healthy'])
    def test_native_reader_expiry_is_distinct_from_freshness_limit(self):
        vals=prepare(payload(kuper()))['parser_offers'][0]
        self.assertIsNone(reader(vals,'2026-09-29')[1])
        self.assertEqual(reader(vals,'2026-09-30')[1],'наблюдение старше 7 дней')
