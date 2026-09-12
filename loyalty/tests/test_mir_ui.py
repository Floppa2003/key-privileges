"""Browser-owned response fixtures, not synthetic claims of live site coverage."""
import asyncio, json, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
from mir_ui import walk_ui_catalog, public_detail_envelope, catalog_snapshot


def page(n, *, count=3, items=None):
    return {'success': True, 'data': {'items': items if items is not None else [{'xml_id':str(n),'url':f'/promo/test/{n}/'}],
        'counter': {'qt': count}, 'pagination':[{'page':i,'isCurrent':i==n} for i in range(1,4)], 'pageTitle':'Москва и МО'}}

class Tests(unittest.IsolatedAsyncioTestCase):
    async def test_clicks_sequential_pages_and_reconciles(self):
        clicks=[]
        async def click(n):clicks.append(n);return catalog_snapshot(page(n),'sbp',n)
        items,report=await walk_ui_catalog(catalog_snapshot(page(1),'sbp',1),click)
        self.assertEqual(clicks,[2,3]);self.assertEqual(set(items),{'1','2','3'});self.assertEqual(report['errors'],[])
    async def test_click_failure_retains_previous_pages(self):
        async def click(n):raise RuntimeError('next_page_not_visible')
        items,report=await walk_ui_catalog(catalog_snapshot(page(1),'sbp',1),click)
        self.assertEqual(set(items),{'1'});self.assertEqual(report['observed'],1);self.assertTrue(report['errors'])
    async def test_wrong_page_or_profile_is_not_counted(self):
        async def click(n):return catalog_snapshot(page(1),'mir',1)
        items,report=await walk_ui_catalog(catalog_snapshot(page(1),'sbp',1),click)
        self.assertEqual(set(items),{'1'});self.assertTrue(report['errors'])
    async def test_duplicate_results_do_not_reconcile_count(self):
        async def click(n):return catalog_snapshot(page(n,items=[{'xml_id':'1','url':'/promo/test/1/'}]),'sbp',n)
        items,report=await walk_ui_catalog(catalog_snapshot(page(1),'sbp',1),click)
        self.assertEqual(len(items),1);self.assertTrue(report['errors'])
    def test_only_public_detail_object_is_retained(self):
        obj={'xml_id':'123','url':'/promo/test/1/','name':'Test','owner':{'name':'Partner'},'templates':[], 'desc':{},'secret':'not-public'}
        envelope={'data':{'content':{'promoDetail':{'promo':{'promoAction':obj}},'auth':{'token':'private'}}}}
        clean=public_detail_envelope(envelope)
        encoded=json.dumps(clean)
        self.assertNotIn('private',encoded);self.assertNotIn('not-public',encoded)
        self.assertEqual(clean['data']['content']['promoDetail']['promo']['promoAction']['xml_id'],'123')
    def test_unexpected_detail_shape_is_not_a_match(self):
        self.assertIsNone(public_detail_envelope({'data':{'content':{'profile':{'name':'private'}}}}))
    def test_catalog_rejects_unsafe_urls_and_unknown_filters(self):
        with self.assertRaises(ValueError):catalog_snapshot(page(1),'personal',1)
        with self.assertRaises(ValueError):catalog_snapshot(page(1,items=[{'xml_id':'a','url':'https://evil.invalid/'}]),'sbp',1)

if __name__=='__main__':unittest.main()
