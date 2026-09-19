"""Source-local robots exception, old-snapshot compatibility and atomic failures."""
import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
sys.path.insert(0, str(Path(__file__).parents[1]))
from konsierge_catalog import ROOT, SOURCE, ROBOTS_POLICY, RECURRING_MODE, parse_capture
from konsierge_source import allowed_read, public_item, dom_capture, collect
from normalized import validate_offer, content_hash
import test_konsierge_catalog as fixtures
NOW=fixtures.NOW

CFG={'id':SOURCE,'name':'Konsierge — публичные привилегии','url':ROOT,'mode':'konsierge',
     'robots_policy':ROBOTS_POLICY,'timeout_seconds':420}


class RecurringTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.KonsiergeTests(); self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def recurring(self):
        self.fixture.report.update(collection_mode=RECURRING_MODE, robots_policy=ROBOTS_POLICY,
                                   robots_requests=0, one_off_public_ui_inspection=False)
        return self.fixture.bundle()

    def test_old_capture_is_still_manual_and_unchanged(self):
        row=self.fixture.row(2615)
        self.assertNotIn('collection_mode',row['details'])
        self.assertIn('manual_capture_not_recurring_collection',row['warnings'])
        validate_offer(row)

    def test_recurring_preserves_ids_terms_codes_and_common_scope(self):
        old={r['id']:r for r in self.fixture.bundle()['records']}
        new=self.recurring()
        self.assertEqual(set(old),{r['id'] for r in new['records']})
        for r in new['records']:
            for field in ('partner_name','benefit_text','conditions_text','redemption_text','promo_codes','valid_until'):
                self.assertEqual(r[field],old[r['id']][field])
            self.assertNotIn('manual_capture_not_recurring_collection',r['warnings'])
            self.assertEqual(r['details']['robots_policy'],ROBOTS_POLICY)
            validate_offer(r)
        self.assertEqual(self.fixture.common(2615)['benefits'][0]['value'],'10')
        self.assertEqual(self.fixture.common(2036)['validity']['status'],'source_date_conflict')

    def test_recurring_requires_explicit_profile_and_no_robots_read(self):
        self.recurring()
        base=copy.deepcopy(self.fixture.report)
        for key,value in [('robots_policy','skip_everything'),('robots_requests',1),
                          ('one_off_public_ui_inspection',True),('collection_mode','other')]:
            self.fixture.report=copy.deepcopy(base);self.fixture.report[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError): self.fixture.bundle()

    def test_profile_tampering_after_rehash_fails(self):
        row=self.recurring()['records'][0]
        row['details']['robots_policy']='unknown'
        row['content_sha256']=content_hash(row)
        with self.assertRaises(ValueError):validate_offer(row)

    def test_read_allowlist(self):
        for url in (ROOT,ROOT+'?rubric_id=24','https://konsierge.com/main.abc.js',
                    'https://benefits.konsierge.com/api/client/v1/benefits?page=1&per=12',
                    'https://benefits.konsierge.com/api/client/v1/rubrics'):
            self.assertTrue(allowed_read('GET',url),url)
        for url in ('https://konsierge.com/robots.txt', 'https://konsierge.com/robots.txt?x=1',
                    'https://benefits.konsierge.com/robots.txt',ROOT+'?rubric_id=24&account=1',
                    'https://konsierge.com/auth/login','https://benefits.konsierge.com/api/client/v1/account',
                    'https://evil.example/benefits','http://konsierge.com/benefits',
                    'https://konsierge.com.evil.example/benefits','https://x:y@konsierge.com/benefits'):
            self.assertFalse(allowed_read('GET',url),url)
        for method in ('POST','PATCH','PUT','DELETE'):
            self.assertFalse(allowed_read(method,ROOT))

    def test_public_projection_drops_unrelated_fields(self):
        item=copy.deepcopy(self.fixture.items[0]);item['unrelated_session']='synthetic-marker'
        self.assertNotIn('unrelated_session',public_item(item))
        self.assertNotIn('synthetic-marker',json.dumps(public_item(item)))

    def test_dom_retains_only_labels(self):
        raw='<qy-benefits-page><script>synthetic-marker</script><qy-benefit-teaser secret="synthetic-marker"><div class="BenefitTeaser-Title">Partner</div><div class="BenefitTeaser-OfferText">Скидка 5%</div><input value="synthetic-marker"></qy-benefit-teaser></qy-benefits-page>'
        html,cards=dom_capture(raw)
        self.assertNotIn('synthetic-marker',html)
        self.assertEqual(cards,[{'name':'Partner','offer':'Скидка 5%'}])

    def test_registry_has_one_exact_source_local_exception(self):
        entries=json.loads((Path(__file__).parents[1]/'sources_normalized.json').read_text())
        selected=[x for x in entries if x.get('robots_policy')==ROBOTS_POLICY]
        self.assertEqual(selected,[CFG])


class RoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_bad_configuration_fails_before_browser(self):
        browser=AsyncMock()
        for key,value in [('id','alfa_only_partner_offers'),('url','https://elsewhere.example/'),('robots_policy','')]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                await collect(browser,{**CFG,key:value},{},NOW,500)
        browser.new_context.assert_not_awaited()

    async def test_capture_failure_returns_no_partial_records(self):
        from collect_normalized import one
        with patch('konsierge_source.capture',AsyncMock(side_effect=RuntimeError('incomplete'))), \
             patch('collect_normalized.PublicSource',side_effect=AssertionError('global gate used')):
            report,rows=await one(AsyncMock(),CFG,NOW,500)
        self.assertEqual(rows,[])
        self.assertEqual(report['status'],'failed')
        self.assertEqual(report['errors'][0]['phase'],'source')
        self.assertEqual(report['robots']['state'],'not_requested')

    async def test_router_uses_browser_collector_without_global_preflight(self):
        from collect_normalized import one
        with patch('collect_normalized.collect_konsierge',AsyncMock(return_value=[])) as call, \
             patch('collect_normalized.PublicSource',side_effect=AssertionError('global gate used')):
            await one(AsyncMock(),CFG,NOW,500)
        call.assert_awaited_once()

    async def test_other_sources_still_call_robots(self):
        from collect_normalized import one
        client=AsyncMock();client.policy=None;client.robots_info=None
        client.robots.side_effect=RuntimeError('preflight-sentinel')
        context=AsyncMock();context.__aenter__.return_value=client
        with patch('collect_normalized.PublicSource',return_value=context):
            report,rows=await one(AsyncMock(),{'id':'moskvich','name':'x','mode':'html','url':'https://moskvichmag.ru/programma-loyalnosti/'},NOW,500)
        client.robots.assert_awaited_once()
        self.assertEqual(report['errors'][0]['reason'],'preflight-sentinel')
        self.assertEqual(rows,[])

if __name__=='__main__':unittest.main()
