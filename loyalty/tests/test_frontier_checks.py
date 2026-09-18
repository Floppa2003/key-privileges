"""Scoped recovery, current discovery and evidence replay; no live credentials."""
import copy,json,sys,tempfile,unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import frontier_checks as f
from test_rzd_import import observation,NOW
import test_rzd_import as fixture
from test_rzd_catalogue_cards import html
from test_coral_catalog import root,doc


def parent():
    rows=[]
    for ident,failure in [(71,'rzd_import_error_cell'),(72,'rzd_detail_empty_or_bound')]:
        obs=observation(f.rz.ROOT,'catalog_cards',[f.cards.sanitize(html(ident))])
        rows.append(f.cards.make_preview(next(iter(f.cards.previews(obs).values())),NOW,failure))
    return {'run_id':'prior:1','observed_at':NOW,'records':rows}

class RzdReader:
    cleanup_verified=True
    def __init__(self,*,missing=False,failure=None):self.calls=[];self.missing=missing;self.failure=failure;self.delay=20
    def read(self,url,kind):
        self.calls.append((url,kind))
        if kind=='robots':strings=['User-agent: *','Crawl-delay: 20']
        elif kind=='home':strings=['РЖД Бонус','/partners/']
        elif kind=='catalog_cards':strings=[f.cards.sanitize(html(999 if self.missing else 71,rate=31))]
        else:
            if self.failure:raise ValueError(self.failure)
            strings=['Новая акция','Скидка 31% по карте РЖД Бонус. Предъявите карту. Не суммируется с акциями.']
        return observation(url,kind,strings)

class RecoveryTests(unittest.TestCase):
    def run_collect(self,reader=None,p=None):
        reader=reader or RzdReader()
        with patch.object(f.rc,'policy_from',return_value=fixture.WalkTests.Policy()):
            return f.rzd_collect(p or parent(),reader,'123:1',NOW),reader
    def test_only_transient_target_is_read_no_whole_catalogue_or_login_retry(self):
        bundle,reader=self.run_collect()
        self.assertEqual(len(bundle['records']),1)
        self.assertEqual([k for _,k in reader.calls],['robots','home','catalog_cards','detail'])
        self.assertNotIn(f.rz.HOME+'promo/offer-72/',[u for u,_ in reader.calls])
        self.assertIn('31%',bundle['records'][0]['conditions_text'])
        self.assertNotEqual(bundle['records'][0]['id'],parent()['records'][0]['id'])
        self.assertEqual(json.loads(bundle['sources'][0]['coverage'])['scope'],'transient_detail_retry_not_full_catalogue')
    def test_removed_target_not_fetched_or_claimed_expired(self):
        b,r=self.run_collect(RzdReader(missing=True))
        self.assertFalse(b['records']);self.assertNotIn('detail',[k for _,k in r.calls])
        self.assertEqual(b['sources'][0]['errors'][-1]['reason'],'rzd_target_not_in_fresh_parent_page')
    def test_second_failure_keeps_old_parent_unchanged_and_no_fake_new_row(self):
        p=parent();original=copy.deepcopy(p);b,_=self.run_collect(RzdReader(failure='rzd_import_error_cell'),p)
        self.assertEqual(p,original);self.assertFalse(b['records']);self.assertEqual(b['sources'][0]['status'],'failed')
    def test_no_failed_targets_means_no_source_reads(self):
        p=parent();p['records']=p['records'][1:];b,r=self.run_collect(p=p)
        self.assertFalse(r.calls);self.assertFalse(b['records']);self.assertEqual(b['sources'][0]['discovered'],0)
    def test_policy_denial_prevents_read_and_is_not_relabelled_transient(self):
        class Policy(fixture.WalkTests.Policy):
            def can_fetch(self,url,bot):return '/promo/' not in url
        reader=RzdReader()
        with patch.object(f.rc,'policy_from',return_value=Policy()):b=f.rzd_collect(parent(),reader,'123:1',NOW)
        self.assertFalse(b['records']);self.assertNotIn('detail',[k for _,k in reader.calls])
        self.assertEqual(b['sources'][0]['errors'][0]['reason'],'rzd_policy_disallow')
    def test_replay_validates_same_output_and_rejects_forged_terms_or_run(self):
        reader=f.RecordingReader(RzdReader());p=parent()
        with patch.object(f.rc,'policy_from',return_value=fixture.WalkTests.Policy()):b=f.rzd_collect(p,reader,'123:1',NOW)
        audit={'run_id':'123:1','commit':'a'*40,'cleanup_verified':True,'source_account_used':False,'provider_credits':0,
            'started_at':NOW,'finished_at':NOW,'events':reader.events,'parent_sha256':f.rz.digest(p)}
        with tempfile.TemporaryDirectory() as folder,patch.object(f,'parent_bundle',return_value=p),patch.object(f.rc,'policy_from',return_value=fixture.WalkTests.Policy()):
            f.save(Path(folder)/'evidence.json',audit);f.save(Path(folder)/'normalized.json',b)
            self.assertEqual(f.validate_rzd(folder,'123:1','a'*40,datetime.fromisoformat(NOW)),b)
            with self.assertRaises(ValueError):f.validate_rzd(folder,'999:1','a'*40,datetime.fromisoformat(NOW))
            changed=copy.deepcopy(b);changed['records'][0]['conditions_text']='invented discount'
            f.save(Path(folder)/'normalized.json',changed)
            with self.assertRaises(ValueError):f.validate_rzd(folder,'123:1','a'*40,datetime.fromisoformat(NOW))
    def test_stale_parent_stops_before_transport(self):
        with tempfile.TemporaryDirectory() as folder:
            f.save(Path(folder)/'evidence.json',{'finished_at':'2020-01-01T00:00:00+00:00'})
            with self.assertRaisesRegex(ValueError,'parent_age'):f.parent_bundle(folder,datetime.fromisoformat(NOW))


def coral_obs(url,body):
    return {'url':url,'requested_at':NOW,'calculated_at':NOW,'formula_sha256':f.cg.digest(f.cg.formula(url)),
        'typed_lines_sha256':'a'*64,'text':body,'sha256':f.cg.digest(body)}

class InventoryReader:
    cleanup_verified=True
    def __init__(self,fail=False):self.calls=[];self.fail=fail;self.delay=5
    def _read_once(self,url):
        self.calls.append(url)
        if url==f.cg.ROBOTS:body='User-agent: *\nAllow: /\nSitemap: '+f.cg.SITEMAP
        elif url==f.coral.CLUB:body=root()
        elif url==f.cg.SITEMAP:body=json.dumps([f.coral.CLUB+'one/ordinary-product/',f.coral.CLUB+'two/offer-b/'])
        else:
            key=url.split('/')[-2]
            if key=='two' and self.fail:raise ValueError('cg_import_timeout_or_error')
            title={'one':'Первая','two':'Вторая'}[key]
            body=doc('<section><h1>'+title+'</h1><div id="categoryProductsList"><div class="product-box referal"><a href="'+url+'offer-'+key+'/">Partner</a></div><div class="product-box base">Ordinary product</div></div></section>',url)
        return coral_obs(url,body)

class InventoryTests(unittest.TestCase):
    def test_formula_accepts_only_public_category_depth_without_broadening_account_scope(self):
        self.assertIn(f.coral.CLUB+'new-category/',f.cg.formula(f.coral.CLUB+'new-category/'))
        for url in ('https://coralbonus.ru/account/',f.coral.CLUB+'one/?token=x',f.coral.CLUB+'one/a/b/',f.coral.CLUB+'../account/'):
            with self.assertRaises(ValueError):f.cg.formula(url)
    def test_inventory_reads_every_category_but_no_detail_or_pdf(self):
        r=InventoryReader()
        with patch.object(f.cg,'policy',return_value=fixture.WalkTests.Policy()):result=f.coral_inventory(r)
        self.assertTrue(result['complete']);self.assertEqual(len(result['categories']),2)
        self.assertEqual(len(r.calls),5)
        self.assertEqual(len(result['interactive_not_sitemap']),2)
        self.assertEqual(len(result['sitemap_candidate_urls']),2)
        self.assertEqual(sum(x['excluded_merchandise'] for x in result['categories']),2)
    def test_failed_category_is_partial_not_absence_or_deleted_offers(self):
        r=InventoryReader(fail=True)
        with patch.object(f.cg,'policy',return_value=fixture.WalkTests.Policy()):result=f.coral_inventory(r)
        self.assertFalse(result['complete']);self.assertEqual(len(result['categories']),1)
        self.assertEqual(len(result['errors']),1);self.assertTrue(result['sitemap_only_may_be_merchandise_or_unread_categories'])

if __name__=='__main__':unittest.main()
