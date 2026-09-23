"""Real public-panel replay; no affiliation, rate or activation inferred across panels."""
import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from flystation_source import inventory,source_fields,collect,SOURCE
from expansion_common import ExcludedOffer,sha
from public_reward_projection import make_record
from sheets_normalized import prepare
from source_lifecycle import health_summary,reconcile_rows
from test_lifecycle_pipeline import reader
from test_catalogue_expansion import bundle,OLD,NEW

RAW=Path(__file__).with_name('fixtures_live').joinpath('flystation-promotions.html').read_text()
def entries():return inventory(RAW)
class FlyStation(unittest.TestCase):
    def test_real_inventory_and_price_only_exclusions(self):
        es=entries();self.assertEqual(len(es),6)
        for e in es:
            if e['native'] in ('extra-time','sport-start'):
                with self.assertRaises(ExcludedOffer):source_fields(e)
        self.assertEqual(len(self.accepted()),4)
    def accepted(self):return[e for e in entries()if e['native']not in ('extra-time','sport-start')]
    def test_advance_scope_is_separate_for_each_rate(self):
        e=next(e for e in entries()if e['native']=='advance');f=source_fields(e)
        self.assertEqual([(x['value'],x['scope']['advance_days'])for x in f['terms']],[('20','30'),('30','60')])
        self.assertIn('2–15 минут',f['benefit']);self.assertIn('не суммируются',f['conditions'])
    def test_birthday_gift_does_not_grant_discount_on_30_minutes(self):
        f=source_fields(next(e for e in entries()if e['native']=='birthday'))
        self.assertEqual(len([t for t in f['terms']if t['kind']=='discount']),1)
        self.assertEqual(f['terms'][0]['scope']['flight_minutes'],'2–15')
        self.assertIn('30 минут',f['terms'][1]['fragment']);self.assertIn('два дня',f['conditions'])
    def test_happy_hours_keeps_novice_weekday_and_booking(self):
        f=source_fields(next(e for e in entries()if e['native']=='happy-hours'))
        for term in ('новичков','11 до 16','по будням','заранее записаться'):self.assertIn(term,f['benefit']+f['conditions']+f['activation'])
        self.assertEqual(f['terms'][0]['value'],'15')
    def test_certificate_sharing_capacity_is_not_lost_with_price_examples(self):
        f=source_fields(next(e for e in entries()if e['native']=='after-flight'))
        self.assertIn('4 минуты: (могут полетать до 2 человек)',f['conditions'])
        self.assertIn('от 2 до 15 человек',f['conditions'])
    def test_source_period_is_unknown_and_ekp_not_inferred(self):
        for e in self.accepted():
            f=source_fields(e);self.assertNotIn('valid_until',f);self.assertIn('not_EKP_catalogue_recovery',f['warnings']);self.assertIn('FlyStation',f['program'])
    def test_all_real_accepted_records_reach_actual_reader(self):
        p=bundle(SOURCE,self.accepted(),all_ids=[e['native']for e in entries()],excluded={'extra-time':'no_concrete_partner_benefit','sport-start':'no_concrete_partner_benefit'})
        self.assertTrue(health_summary(p,expected_sources=[SOURCE])[0]['healthy'])
        for row in prepare(p)['parser_offers']:
            v,reason=reader(row,OLD[:10]);self.assertIsNotNone(v);self.assertIsNone(reason)
    def test_unreviewed_panel_is_an_error_not_silent_exclusion(self):
        bad=RAW.replace('Хочу ЕЩЁ!','Новая неизвестная скидка')
        with self.assertRaises(ValueError):inventory(bad)
    def test_duplicate_identity_fails(self):
        with self.assertRaises(ValueError):inventory(RAW.replace('Скидка после полёта','День рождения в аэротрубе'))
    def test_evidence_modification_or_cross_panel_identity_rejected(self):
        e=self.accepted()[0];e['panel_html']+='changed'
        with self.assertRaises(ValueError):source_fields(e)
        e=self.accepted()[0];e['native']='birthday'
        with self.assertRaises(ValueError):source_fields(e)
    def test_new_discount_in_price_only_panel_requires_review(self):
        e=next(e for e in entries()if e['native']=='extra-time');e['panel_html']=e['panel_html'].replace('2500 рублей','2500 рублей со скидкой 10%');e['panel_sha256']=sha(e['panel_html'])
        with self.assertRaisesRegex(ValueError,'price_only'):source_fields(e)
    def test_publication_hold_and_return_preserve_manual_notes(self):
        es=self.accepted();p=bundle(SOURCE,es);old=[['header']*26]+[r+['manual']for r in prepare(p)['parser_offers']]
        later=bundle(SOURCE,es[1:],now=NEW)
        changes=reconcile_rows(later,old,prepare(later)['parser_offers']);held=next(r for r in changes if r[0]==old[1][0]);self.assertEqual(held[22],old[1][22]);self.assertIsNone(reader(held,NEW[:10])[0]);self.assertEqual(old[1][-1],'manual')
    def test_three_and_seven_programme_native_formula_upgrade(self):
        import ui_freshness as u
        from test_ui_freshness import F
        full=u.upgrade_formula(F)
        for count in (3,7):
            names='{'+ ';'.join('"'+p+'"' for p in u.PROGRAMMES[:count])+'}'
            all_names='{'+ ';'.join('"'+p+'"' for p in u.PROGRAMMES)+'}'
            self.assertEqual(u.upgrade_formula(full.replace(all_names,names)),full)
        self.assertEqual(u.upgrade_formula(full),full)
class FlyCollector(unittest.IsolatedAsyncioTestCase):
    async def test_actual_collector_full_inventory(self):
        class Client:
            async def read(self,url):return RAW
        report=dict(source_id=SOURCE,errors=[])
        rs=await collect(Client(),dict(url='https://flystation.net/promotions'),report,OLD,500)
        self.assertEqual(len(rs),4);self.assertTrue(report['native_inventory_v1']['complete']);self.assertEqual(len(report['native_inventory_v1']['ids']),6)
    async def test_limit_is_partial_not_full_coverage(self):
        class Client:
            async def read(self,url):return RAW
        report=dict(source_id=SOURCE,errors=[])
        await collect(Client(),dict(url='https://flystation.net/promotions'),report,OLD,1)
        self.assertFalse(report['native_inventory_v1']['complete']);self.assertTrue(report['errors'])
if __name__=='__main__':unittest.main()
