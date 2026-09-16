"""Synthetic public page tests; no accounts or network requests."""
import json,sys,tempfile,unittest
from pathlib import Path
from datetime import datetime
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import coral_import as g
from normalized import validate_offer
NOW='2026-09-16T15:40:00+00:00'
CATEGORY=g.c.CLUB+'dlya-detei/'
URL=CATEGORY+'new-course/'
PROMO=g.c.PROMO+'current-campaign/'

def html(url,body):return '<html><head><link rel="canonical" href="'+url+'"><title>CoralBonus</title></head><body>'+body+'</body></html>'
def roots():
    return {g.c.CLUB:html(g.c.CLUB,'<h1>Клуб привилегий</h1><div class="category-box-menu"><h5><a href="'+CATEGORY+'">Для детей</a></h5></div>'),g.c.PROMO:html(g.c.PROMO,'<h1>Акции</h1><div class="sale-item-description"><h5><a href="'+PROMO+'">Акция</a></h5></div>')}
def page(url=URL,rate=17,store=False):
    return html(url,'<section><div class="order-lg-2"><h1>Новый партнёр — скидка '+str(rate)+'%</h1><p>Предложение программы для участников. Действует только при соблюдении условий на сайте партнёра, без суммирования.</p><div class="product-purchase-box'+('' if store else ' referal')+'"><div class="order-autorize"><h3>Чтобы получить промо-код нужно авторизоваться на сайте</h3></div></div></div></section>')
def obs(url,raw):
    value=g.sanitize(raw,url)
    return {'url':url,'requested_at':NOW,'calculated_at':NOW,'formula_sha256':g.digest(g.formula(url)),'typed_lines_sha256':'a'*64,'text':value,'sha256':g.digest(value)}
def source_map(urls):return '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+u+'</loc></url>' for u in urls)+'</urlset>'
def targets(urls=None):
    r=roots();return g.candidates(obs(g.c.CLUB,r[g.c.CLUB]),obs(g.c.PROMO,r[g.c.PROMO]),obs(g.SITEMAP,source_map(urls or [URL])))

class Mapping(unittest.TestCase):
    def test_changed_urls_titles_and_rates(self):
        changed=CATEGORY+'another-partner/';items,n,p=targets([changed])
        self.assertEqual(n,1);self.assertEqual(p,1);self.assertEqual(items[0][1]['url'],changed)
        a=g.map_detail(obs(URL,page()),'coral',targets()[0][0][1],NOW)
        b=g.map_detail(obs(changed,page(changed,32)),'coral',items[0][1],NOW)
        self.assertNotEqual(a['id'],b['id']);self.assertIn('32%',b['title']);validate_offer(b)
    def test_sitemap_is_not_active_listing_proof(self):
        r=g.map_detail(obs(URL,page()),'coral',targets()[0][0][1],NOW)
        self.assertIsNone(r['details']['retrieval']['origin_status']);self.assertFalse(r['details']['google_import']['active_catalogue_listing_verified'])
        self.assertIn('sitemap_presence_does_not_prove_active_catalogue_listing',r['warnings'])
    def test_store_product_is_excluded(self):
        self.assertIsNone(g.map_detail(obs(URL,page(store=True)),'coral',targets()[0][0][1],NOW))
    def test_unknown_category_and_noncurrent_promo_not_requested(self):
        items,_,_=targets([URL,g.c.CLUB+'unknown/unlisted/',g.c.PROMO+'not-current/'])
        self.assertEqual([e['url'] for s,e in items],[URL,PROMO])
    def test_duplicate_sitemap_fails(self):
        with self.assertRaises(ValueError):targets([URL,URL])
    def test_foreign_sitemap_fails(self):
        with self.assertRaises(ValueError):g.sanitize(source_map(['https://example.test/catalogue/']),g.SITEMAP)
    def test_formula_rejects_other_sources(self):
        for url in (URL+'?unexpected=1',URL.replace('https','http'),'https://example.test/catalogue/'):
            with self.subTest(url=url),self.assertRaises(ValueError):g.formula(url)
    def test_canonical_mismatch_fails(self):
        with self.assertRaises(RuntimeError):obs(URL,page().replace(URL,URL+'other/'))
    def test_observation_hash_and_time(self):
        o=obs(URL,page());o['text']+='changed'
        with self.assertRaises(ValueError):g.checked(o)
        o=obs(URL,page());o['calculated_at']='2026-09-16T16:00:00+00:00'
        with self.assertRaises(ValueError):g.checked(o)

class Source:
    cleanup_verified=True
    def __init__(self,fail=False):self.observations=[];self.fail=fail
    def read(self,url):
        if self.fail and url==URL:raise ValueError('cg_import_timeout_or_error')
        if url==g.ROBOTS:raw='User-agent: *\nSitemap: '+g.SITEMAP+'\n'
        elif url in roots():raw=roots()[url]
        elif url==g.SITEMAP:raw=source_map([URL])
        elif url==URL:raw=page()
        elif url==PROMO:raw=html(PROMO,'<section class="article"><h1>Акция</h1><p>Бонусы для участников программы. Дополнительные условия и ограничения указаны в этом предложении.</p></section>')
        else:raise ValueError('unexpected_test_url')
        o=obs(url,raw);self.observations.append(o);return o

class Walk(unittest.TestCase):
    def test_both_sources_collect(self):
        b=g.collect(Source(),'1:1',NOW)
        self.assertEqual(len(b['records']),2);self.assertTrue(all(s['status']=='ok' for s in b['sources']));g.prepare(b)
    def test_partial_failure_keeps_other_source(self):
        b=g.collect(Source(True),'1:1',NOW)
        self.assertEqual(len(b['records']),1);self.assertEqual(b['sources'][0]['status'],'failed');self.assertEqual(b['sources'][1]['status'],'ok');g.prepare(b)
    def test_bundle_reconstruction_and_omission(self):
        reader=Source();b=g.collect(reader,'1:1',NOW)
        a={'run_id':'1:1','commit':'a'*40,'cleanup_verified':True,'scrapingant_credits':0,'started_at':NOW,'finished_at':NOW,'observations':reader.observations}
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);(p/'normalized.json').write_text(json.dumps(b));(p/'evidence.json').write_text(json.dumps(a))
            self.assertEqual(g.validate_bundle(p,'1:1','a'*40,datetime.fromisoformat(NOW)),b)
            b['records'].pop();(p/'normalized.json').write_text(json.dumps(b))
            with self.assertRaises(ValueError):g.validate_bundle(p,'1:1','a'*40,datetime.fromisoformat(NOW))
if __name__=='__main__':unittest.main()
