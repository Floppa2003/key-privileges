"""A generic anchor must not hide reviewed rules or mix two pharmacy lists."""
import copy,json,tempfile,unittest
from datetime import datetime
from pathlib import Path
from test_aeroflot_linked_rules import r,base,page,project,Response,CLOCK,FINAL

SAMSON='https://samson-pharma.ru/catalog/extra/spiski-tovarov/tovary-bez-skidok/'
NOTE='На данную группу товаров не начисляются баллы программы лояльности аптеки, а также бонусы СберСпасибо'

def samson_page(names=('Alpha','Beta'),total=3,next_page=True):
    return page(names,total,next_page).decode().replace('CatalogSlugsPage_headerSubText__changed','CatalogSlugs_bottomText__fresh').replace('Баллы на эти товары не начисляются.',NOTE).encode()

class PublicPages:
    def __init__(self,names=('Alpha','Beta'),failed_second=False,repeat=False):
        self.names=names;self.failed_second=failed_second;self.repeat=repeat;self.calls=[]
    def __call__(self,url,**kwargs):
        self.calls.append(url)
        if url=='https://samson-pharma.ru/robots.txt':
            return Response(b'User-agent: *\nDisallow: /?page=\nDisallow: /personal/\n',mime='text/plain')
        if url==SAMSON:return Response(samson_page(self.names))
        if url==SAMSON+'?page=2':
            if self.failed_second:return Response(b'',403)
            return Response(samson_page(self.names if self.repeat else ('Gamma',),next_page=False))
        raise AssertionError('Unexpected source request: '+url)

def collect(tmp,net=None):
    return r.collect(base(SAMSON,'на сайте'),tmp,'456:1','a'*40,get=net or PublicPages(),sleep=lambda _:None,observed_at=CLOCK.isoformat())

class SamsonRules(unittest.TestCase):
    def setUp(self):self.assertIsNotNone(r,'The existing linked-rule collector must import')
    def test_reviewed_route_does_not_depend_on_anchor_wording(self):
        for url in (FINAL,SAMSON):
            with self.subTest(url=url):
                entries,inventory=r.discover(base(url,'на сайте'),CLOCK)
                self.assertEqual([e['url'] for e in entries],[url])
                self.assertEqual(entries[0]['parents'][0]['label'],'на сайте')
                self.assertEqual(entries[0]['parents'][0]['observed_at'],base()['observed_at'])
    def test_homepage_and_unknown_generic_routes_are_not_rule_targets(self):
        for url in ('https://samson-pharma.ru/','https://samson-pharma.ru/personal/','https://other.test/catalog/extra/spiski-tovarov/tovary-bez-skidok/'):
            self.assertEqual(r.discover(base(url,'на сайте'),CLOCK)[0],[])
    def test_current_layout_preserves_own_note_products_and_pagination(self):
        clean=r.clean_html(samson_page(),SAMSON)
        self.assertEqual(r.clean_html(clean.encode(),SAMSON),clean)
        fields=r.catalog_fields(clean,SAMSON)
        self.assertEqual(fields['note'],NOTE)
        self.assertEqual(fields['total'],3)
        self.assertEqual(fields['products'],[{'url':'https://samson-pharma.ru/catalog/item/Alpha/','name':'Alpha'},{'url':'https://samson-pharma.ru/catalog/item/Beta/','name':'Beta'}])
        self.assertEqual(fields['next_links'],[SAMSON+'?page=2'])
        self.assertNotIn('HELLO99',clean)
    def test_two_pages_reconcile_without_product_card_requests(self):
        net=PublicPages()
        with tempfile.TemporaryDirectory() as tmp:
            bundle,audit=collect(tmp,net)
            self.assertEqual(bundle['sources'][0]['status'],'ok')
            self.assertEqual(len(bundle['records']),2)
            self.assertEqual(audit['results'][0]['unique_products'],3)
            self.assertTrue(audit['results'][0]['catalogue_complete'])
            for row in bundle['records']:
                result=project(row)
                self.assertEqual(len(result['conditions']),1)
                for key in ('benefits','codes','costs'):self.assertEqual(result[key],[])
        self.assertEqual(net.calls,['https://samson-pharma.ru/robots.txt',SAMSON,SAMSON+'?page=2'])
    def test_changed_names_change_evidence_without_changing_identity(self):
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
            old,_=collect(a);new,_=collect(b,PublicPages(names=('Delta','Epsilon')))
            self.assertEqual(len(old['records']),2);self.assertEqual(len(new['records']),2)
            self.assertEqual(old['records'][0]['id'],new['records'][0]['id'])
            self.assertNotEqual(old['records'][0]['content_sha256'],new['records'][0]['content_sha256'])
            self.assertIn('Delta',new['records'][0]['conditions_text'])
            self.assertNotIn('Alpha',new['records'][0]['conditions_text'])
    def test_cross_pharmacy_redirects_are_not_allowed(self):
        for start,end in ((FINAL,SAMSON),(SAMSON,FINAL)):
            self.assertEqual(r.redirect_allowed(start,start),start)
            with self.assertRaisesRegex(ValueError,'al_cross_partner_redirect'):r.redirect_allowed(start,end)
    def test_foreign_products_and_pagination_do_not_borrow_other_pharmacy(self):
        clean=r.clean_html(samson_page(),SAMSON)
        for changed in (clean.replace('https://samson-pharma.ru/catalog/item/Alpha/','https://stoletov.ru/catalog/item/Alpha/'),clean.replace(SAMSON+'?page=2',FINAL+'?page=2')):
            with self.assertRaises(ValueError):r.catalog_fields(changed,SAMSON)
    def test_repeated_products_cannot_certify_the_advertised_total(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle,audit=collect(tmp,PublicPages(repeat=True))
            self.assertEqual(bundle['sources'][0]['status'],'partial')
            self.assertFalse(audit['results'][0]['catalogue_complete'])
    def test_target_refusal_keeps_first_page_without_retry(self):
        net=PublicPages(failed_second=True)
        with tempfile.TemporaryDirectory() as tmp:
            bundle,audit=collect(tmp,net)
            self.assertEqual(len(bundle['records']),1)
            self.assertEqual(bundle['sources'][0]['status'],'partial')
            self.assertFalse(audit['results'][0]['catalogue_complete'])
            self.assertIn({'url':SAMSON+'?page=2','reason':'al_http_403'},bundle['sources'][0]['errors'])
        self.assertEqual(net.calls.count(SAMSON+'?page=2'),1)
    def test_publisher_reconstructs_current_pages_and_rejects_tampered_terms(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle,audit=collect(tmp)
            self.assertEqual(len(bundle['records']),2)
            clock=datetime.fromisoformat(audit['finished_at'])
            self.assertEqual(r.validate_bundle(tmp,'456:1','a'*40,clock),bundle)
            changed=copy.deepcopy(bundle);changed['records'][0]['conditions_text']='Скидка 99%'
            changed['records'][0]['content_sha256']=r.content_hash(changed['records'][0])
            (Path(tmp)/'normalized.json').write_text(json.dumps(changed))
            with self.assertRaises(ValueError):r.validate_bundle(tmp,'456:1','a'*40,clock)

if __name__=='__main__':unittest.main()
