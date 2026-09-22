"""Source retirement needs a complete new inventory, never an empty failed read."""
import copy, hashlib, json, sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from source_lifecycle import attach_inventory, reconcile_rows, reader_hold, validate_inventories
from sheets_normalized import SCHEMAS
S='backit_public';U='https://backit.me/ru/cashback/shops/kuper'
NOW='2026-09-22T16:00:00+00:00'
def old_row():
    row=['']*25
    row[0]=hashlib.sha256((S+'\nkuper').encode()).hexdigest()
    row[1]='Backit — денежный кешбэк';row[2]='Купер';row[7]='Кешбэк 5%'
    row[17]=U;row[20]=json.dumps({'public_reward_source':S,'public_reward_evidence':{'url':U}})
    row[22]='2026-09-21T16:00:00+00:00'
    return row
def bundle(accepted=False, failed=False):
    report={'source_id':S,'status':'failed' if failed else 'ok','errors':[{'reason':'http_403'}] if failed else [],
            'normalized':int(accepted),'observed_at':NOW}
    records=[{'source_id':S,'source_url':U}] if accepted else []
    attach_inventory(report,[U],[] if accepted else [{'url':U,'reason':'source_disclosed_temporarily_disabled'}])
    return {'run_id':'run:1','observed_at':NOW,'sources':[report],'records':records}
class LifecycleTests(unittest.TestCase):
    def test_confirmed_disabled_preserves_offer_time_and_managed_fields(self):
        before=old_row()
        rows=reconcile_rows(bundle(),[SCHEMAS['parser_offers'],before],[])
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0][:20],before[:20])
        self.assertEqual(rows[0][21:],before[21:])
        meta=json.loads(rows[0][20])['_lifecycle']
        self.assertEqual(meta['checked_at'],NOW)
        self.assertEqual(meta['reason'],'source_disclosed_temporarily_disabled')
    def test_failed_read_never_retires_or_refreshes(self):
        self.assertEqual(reconcile_rows(bundle(failed=True),[SCHEMAS['parser_offers'],old_row()],[]),[])
    def test_partial_never_retires(self):
        b=bundle();b['sources'][0]['status']='partial'
        self.assertEqual(reconcile_rows(b,[SCHEMAS['parser_offers'],old_row()],[]),[])
    def test_mismatched_or_duplicate_inventory_rejected(self):
        for bad in ([U,U],['https://evil.example/kuper']):
            with self.assertRaises(ValueError):attach_inventory({},bad,[],source_id=S)
        b=bundle();b['sources'][0]['inventory_v1']['urls'].append('https://backit.me/ru/cashback/shops/extra')
        with self.assertRaises(ValueError):validate_inventories(b)
    def test_empty_inventory_not_proof_of_disappearance(self):
        with self.assertRaises(ValueError):attach_inventory({},[],[],source_id=S)
    def test_complete_absence_reversibly_holds_previous_card(self):
        b=bundle();other='https://backit.me/ru/cashback/shops/other'
        attach_inventory(b['sources'][0],[other],[{'url':other,'reason':'source_disclosed_temporarily_disabled'}])
        rows=reconcile_rows(b,[SCHEMAS['parser_offers'],old_row()],[])
        self.assertEqual(json.loads(rows[0][20])['_lifecycle']['reason'],'not_in_complete_inventory')
    def test_successful_observation_restores_held_row(self):
        held=reconcile_rows(bundle(),[SCHEMAS['parser_offers'],old_row()],[])[0]
        fresh=old_row();fresh[22]=NOW
        result=reconcile_rows(bundle(accepted=True),[SCHEMAS['parser_offers'],held],[fresh])
        self.assertEqual(result,[fresh])
        self.assertNotIn('_lifecycle',json.loads(result[0][20]))
    def test_older_bundle_cannot_overwrite_newer_offer_or_hold(self):
        b=bundle(accepted=True);old=old_row();old[22]='2026-09-23T16:00:00+00:00'
        self.assertEqual(reconcile_rows(b,[SCHEMAS['parser_offers'],old],[old_row()]),[])
        self.assertEqual(reconcile_rows(bundle(),[SCHEMAS['parser_offers'],old],[]),[])
    def test_unrelated_rows_untouched(self):
        row=old_row();row[20]='{}'
        self.assertEqual(reconcile_rows(bundle(),[SCHEMAS['parser_offers'],row],[]),[])
    def test_freshness_limit_is_not_expiry_and_is_source_scoped(self):
        raw={'details':{'public_reward_source':S},'observed_at':'2026-09-15T16:00:00+00:00'}
        self.assertIsNone(reader_hold(raw,'2026-09-22'))
        self.assertEqual(reader_hold(raw,'2026-09-23'),'наблюдение старше 7 дней')
        self.assertIsNone(reader_hold({**raw,'details':{}},'2026-09-23'))
