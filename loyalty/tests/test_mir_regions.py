"""Regional collection must retain the exact card and payment/region relationship."""
import asyncio, copy, json, sys, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]))
try: import mir_regions as region
except ImportError: region=None
import mir_ui
from adapters import mir_detail
from normalized import validate_offer, content_hash
from fixtures import fixture
NOW='2026-09-13T18:00:00+00:00'
URL='https://vamprivet.ru/promo/transport/ekspress-v-aeroport-s-vygodoy-i-komfortom-1/'
def offer():
    record=mir_detail(json.loads(fixture('mir_detail.json')),URL,NOW)[0]
    record['details'].update(catalog_profiles=['sbp'],catalog_region='Акции СБП в Москве и МО',retrieval_attempts=1)
    record['content_sha256']=content_hash(record)
    return record

class UnionTests(unittest.TestCase):
    def mapper(self):
        self.assertIsNotNone(region,'Regional Mir union is missing')
        return region.merge_regions
    def test_same_card_keeps_stable_id_with_two_listing_regions(self):
        a=offer();b=copy.deepcopy(a);b['details']['catalog_region']='Акции СБП в Санкт-Петербурге и ЛО';b['details']['retrieval_attempts']=2
        rows,meta=self.mapper()([('msk',[a]),('spb',[b])])
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['id'],a['id']);self.assertEqual(meta['shared_observations_merged'],1)
        self.assertEqual([r['region_key'] for r in rows[0]['details']['catalog_listings']],['msk','spb']);validate_offer(rows[0])
    def test_payment_membership_remains_region_specific(self):
        a=offer();b=copy.deepcopy(a);b['details']['catalog_profiles']=['mir']
        rows,_=self.mapper()([('msk',[a]),('spb',[b])])
        self.assertEqual(rows[0]['details']['catalog_profiles'],['sbp'])
        self.assertEqual(rows[0]['details']['catalog_listings'][1]['payment_types'],['mir'])
    def test_conflicting_terms_do_not_extend_primary_card_eligibility(self):
        a=offer();b=copy.deepcopy(a);b['conditions_text']+=' Только по субботам.'
        rows,meta=self.mapper()([('msk',[a]),('spb',[b])])
        self.assertEqual(len(rows),1);self.assertEqual(len(rows[0]['details']['catalog_listings']),1)
        self.assertEqual(meta['errors'][0]['reason'],'regional_terms_conflict')
        self.assertNotIn('субботам',rows[0]['conditions_text'])
    def test_new_card_id_adds_row_without_reusing_neighbor_terms(self):
        a=offer();b=copy.deepcopy(a);b['id']='b'*64;b['native_id']='distinct-card'
        rows,_=self.mapper()([('msk',[a]),('spb',[b])])
        self.assertEqual(len(rows),2);self.assertEqual(rows[1]['details']['catalog_listings'][0]['region_key'],'spb')
    def test_unknown_profile_and_duplicate_ids_are_rejected(self):
        fn=self.mapper()
        for source in [[('evil',[offer()])],[('msk',[offer(),offer()])],[('msk',[offer()]),('msk',[])]]:
            with self.assertRaises(ValueError):fn(source)
    def test_inputs_are_unchanged(self):
        a=offer();before=copy.deepcopy(a);self.mapper()([('msk',[a])]);self.assertEqual(a,before)

class CollectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_second_region_failure_keeps_first_region_complete_records(self):
        self.assertIsNotNone(region,'Regional Mir collector is missing')
        async def read(client,cfg,key,now,limit):
            if key=='msk':return [offer()],{'errors':[],'discovered':1,'coverage':'complete synthetic example','discovered_urls':[URL]}
            raise RuntimeError('http_403')
        report={'errors':[]}
        with patch.object(region,'read_region',read):rows=await region.collect_mir(SimpleNamespace(),{},report,NOW,500)
        self.assertEqual(len(rows),1);self.assertEqual(report['errors'][0]['region'],'spb')
    async def test_limit_follows_unique_union_and_is_reported(self):
        self.assertIsNotNone(region,'Regional Mir collector is missing')
        async def read(client,cfg,key,now,limit):return [offer()],{'errors':[],'discovered':1,'coverage':'fixture','discovered_urls':[URL]}
        report={'errors':[]}
        with patch.object(region,'read_region',read):rows=await region.collect_mir(SimpleNamespace(),{},report,NOW,1)
        self.assertEqual(len(rows),1);self.assertEqual(report['discovered'],1);self.assertEqual(report['errors'],[])

    async def test_failed_details_remain_in_unique_discovery_count(self):
        self.assertIsNotNone(region)
        async def read(client,cfg,key,now,limit):
            return [offer()],{'errors':[{'phase':'detail','reason':'http_503'}],
                'discovered':2,'coverage':'partial fixture',
                'discovered_urls':[URL,'https://vamprivet.ru/promo/test/missing/']}
        report={'errors':[]}
        with patch.object(region,'read_region',read):
            rows=await region.collect_mir(SimpleNamespace(),{},report,NOW,500)
        self.assertEqual(len(rows),1);self.assertEqual(report['discovered'],2)

class Locator:
    def __init__(self,page,kind,text=None):self.page=page;self.kind=kind;self.text=text
    def get_by_role(self,*args,**kwargs):return Locator(self.page,'confirm',kwargs['name'])
    def get_by_text(self,text,**kwargs):return Locator(self.page,'region',text)
    async def count(self):return 0 if self.kind=='confirm' else 1
    async def is_visible(self):return True
    async def inner_text(self):return self.page.selected
    async def click(self,**kwargs):
        self.page.clicked.append((self.kind,self.text))
        if self.kind=='region':
            self.page.selected=self.text
            self.page.capture.catalogs.append(self.page.new_response)
class Page:
    def __init__(self):self.selected='Москва и МО';self.clicked=[];self.capture=None
    def locator(self,selector):return Locator(self,selector)
    async def wait_for_function(self,*args,**kwargs):return
class Capture:
    def __init__(self,page,new):self.catalogs=[{'payment_type':'sbp','page':1,'page_title':'Акции СБП в Москве и МО'}];page.capture=self;page.new_response=new
    async def wait(self,items,offset,predicate,**kwargs):
        for item in items[offset:]:
            if predicate(item):return item
        raise RuntimeError('expected_public_response_not_observed')
class SelectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_selects_actual_ui_and_requires_new_regional_response(self):
        fn=getattr(mir_ui,'select_listing_region',None);self.assertTrue(callable(fn),'No explicit region selector')
        page=Page();fresh={'page':1,'payment_type':'sbp','page_title':'Акции СБП в Санкт-Петербурге и ЛО'};capture=Capture(page,fresh)
        result=await fn(page,capture,capture.catalogs[0],'spb')
        self.assertEqual(result,fresh);self.assertIn(('region','Санкт-Петербург и ЛО'),page.clicked)
    async def test_old_moscow_response_cannot_satisfy_spb_selection(self):
        fn=getattr(mir_ui,'select_listing_region',None);self.assertTrue(callable(fn),'No explicit region selector')
        page=Page();capture=Capture(page,{'page':1,'payment_type':'sbp','page_title':'Акции СБП в Москве и МО'})
        with self.assertRaises(RuntimeError):await fn(page,capture,capture.catalogs[0],'spb')

class ProductionRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_main_dispatch_uses_both_region_reads_not_compatibility_alias(self):
        import collect_normalized as production
        self.assertIsNotNone(region)
        seen=[]
        class Source:
            policy=None
            def __init__(self,*args):pass
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
        async def read(client,cfg,key,now,limit):
            seen.append(key)
            return [offer()],{'errors':[],'discovered':1,'coverage':'fixture','discovered_urls':[URL]}
        cfg={'id':'mir','mode':'mir','name':'Привет! / Мир / СБП','url':'https://vamprivet.ru/promo/'}
        with patch.object(production,'PublicSource',Source),patch.object(region,'read_region',read):
            report,rows=await production.one(None,cfg,NOW,500)
        self.assertEqual(seen,['msk','spb'])
        self.assertEqual(report['status'],'ok',report)
        self.assertEqual(len(rows),1)
        self.assertEqual(len(rows[0]['details']['catalog_listings']),2)
