"""Regional catalogue union must add coverage, not duplicate shared offers.
Fixtures are the existing four public T2 objects; modified cases are synthetic.
"""
import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).parents[1]))
import t2_regions as t2
from normalized import validate_offer
from public_transport import PublicSource
from test_final_navigation import Page

NOW = '2026-09-13T18:00:00+00:00'
FIXTURE = Path(__file__).with_name('fixtures_live') / 't2-catalog.json'
MSK = 'https://msk.t2.ru/bolshe/offers'
SPB = 'https://spb.t2.ru/bolshe/offers'

def payload():
    return json.loads(FIXTURE.read_text())

class RegionTests(unittest.TestCase):
    def merger(self):
        fn = getattr(t2, 'merge_regional_catalogs', None)
        self.assertTrue(callable(fn), 'No regional union mapper')
        return fn

    def test_shared_native_id_is_one_offer_with_two_listing_regions(self):
        rows, coverage = self.merger()([('msk', payload()), ('spb', payload())], NOW)
        self.assertEqual(len(rows), 4)
        self.assertEqual(coverage['shared_observations_merged'], 4)
        self.assertEqual(coverage['errors'], [])
        first = rows[0]
        self.assertEqual(first['details']['catalog_regions'], [
            {'key':'msk','region':'Москва и область','source_url':MSK},
            {'key':'spb','region':'Санкт-Петербург и Ленинградская область','source_url':SPB}])
        self.assertEqual(first['source_url'], MSK)
        self.assertEqual(first['id'], hashlib.sha256(b't2_bolshe\n5871FFCF1EE82EACE0630D06F60A6869').hexdigest())
        validate_offer(first)

    def test_spb_only_offer_uses_actual_regional_source_not_moscow(self):
        spb = payload(); spb['data']['offers'] = spb['data']['offers'][:1]
        spb['data']['offers'][0]['id'] = 'A' * 32
        spb['data']['offers'][0]['companyName'] = 'Синтетический локальный партнёр'
        rows, meta = self.merger()([('msk', payload()),('spb',spb)], NOW)
        self.assertEqual(len(rows), 5)
        row = next(r for r in rows if r['native_id']=='A'*32)
        self.assertEqual(row['source_url'], SPB)
        self.assertIsNone(row['benefit_url'])
        self.assertEqual(row['details']['region'], 'Санкт-Петербург и Ленинградская область')
        self.assertEqual([x['key'] for x in row['details']['catalog_regions']], ['spb'])
        self.assertEqual(meta['shared_observations_merged'], 0)
        validate_offer(row)

    def test_same_id_different_terms_cannot_be_added_as_matching_region(self):
        spb = payload();spb['data']['offers'][0]['agreement'] += '<p>Не действует по субботам.</p>'
        rows, meta = self.merger()([('msk',payload()),('spb',spb)], NOW)
        self.assertEqual(len(rows),4)
        self.assertEqual([x['key'] for x in rows[0]['details']['catalog_regions']], ['msk'])
        self.assertNotIn('Не действует по субботам',rows[0]['conditions_text'])
        self.assertEqual(len(meta['errors']),1)
        self.assertEqual(meta['errors'][0]['reason'],'regional_terms_conflict')
        self.assertEqual(meta['errors'][0]['region'],'spb')
        self.assertEqual(meta['shared_observations_merged'],3)

    def test_unknown_region_cannot_change_the_fetch_destination(self):
        with self.assertRaises(ValueError):self.merger()([('evil',payload())],NOW)

    def test_repeated_profile_is_rejected_instead_of_counted_twice(self):
        with self.assertRaises(ValueError):self.merger()([('msk',payload()),('msk',payload())],NOW)

    def test_duplicate_native_objects_inside_one_profile_are_not_silently_removed(self):
        data=payload();data['data']['offers'].append(copy.deepcopy(data['data']['offers'][0]))
        with self.assertRaises(ValueError):self.merger()([('spb',data)],NOW)

    def test_input_data_are_not_mutated_by_regional_normalization(self):
        data=payload();before=copy.deepcopy(data)
        self.merger()([('msk',data),('spb',data)],NOW)
        self.assertEqual(data,before)

class CollectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_spb_read_preserves_moscow_without_fake_spb_coverage(self):
        self.assertTrue(hasattr(t2,'read_region_catalog'),'No region read boundary')
        async def read(client,key):
            if key=='msk':return payload()
            if key=='spb':raise RuntimeError('http_503')
            raise AssertionError('Unknown fetch target')
        report={'errors':[]}
        with patch.object(t2,'read_region_catalog',read):
            rows=await t2.collect_t2(SimpleNamespace(),{},report,NOW,200)
        self.assertEqual(len(rows),4)
        self.assertEqual(report['errors'][0]['region'],'spb')
        self.assertTrue(all([x['key'] for x in r['details']['catalog_regions']]==['msk'] for r in rows))

    async def test_failed_moscow_read_does_not_prevent_independent_spb_read(self):
        self.assertTrue(hasattr(t2,'read_region_catalog'),'No region read boundary')
        async def read(client,key):
            if key=='msk':raise RuntimeError('http_503')
            if key=='spb':return payload()
            raise AssertionError('Unknown fetch target')
        report={'errors':[]}
        with patch.object(t2,'read_region_catalog',read):
            rows=await t2.collect_t2(SimpleNamespace(),{},report,NOW,200)
        self.assertEqual(len(rows),4)
        self.assertTrue(all(r['source_url']==SPB for r in rows))

    async def test_limit_is_applied_after_union_with_explicit_partial_coverage(self):
        self.assertTrue(hasattr(t2,'read_region_catalog'),'No region read boundary')
        async def read(client,key):return payload()
        report={'errors':[]}
        with patch.object(t2,'read_region_catalog',read):
            rows=await t2.collect_t2(SimpleNamespace(),{},report,NOW,2)
        self.assertEqual(len(rows),2);self.assertEqual(report['discovered'],4)
        self.assertTrue(any(e['reason']=='detail_limit_reached' for e in report['errors']))

    async def test_spb_natural_document_reload_is_awaited_like_moscow(self):
        client=PublicSource(None,SPB)
        client.page=Page([(503,'loading'),(503,'loading'),(200,'<main>Больше: скидка 20%</main>')],SPB)
        status,body=await client.navigate(SPB)
        self.assertEqual(status,200)
        self.assertIn('скидка 20%',body)
        self.assertEqual(client.page.listeners,{})
