"""Changed links, products and PDF text must come from current source responses."""
import copy,json,sys,tempfile,unittest
from datetime import datetime,timedelta
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]))
try: import aeroflot_linked_rules as r
except ImportError: r=None
import aeroflot_import_catalog as af
from test_aeroflot_import import partner,category_data,json_observation,NOW
from test_document_text import pdf
from test_rzd_external import Response
from sheets_normalized import prepare,SCHEMAS
from unified_normalization import make_input,normalize_record

ROOT='https://stoletov.ru/catalog/groups/'
FINAL='https://stoletov.ru/catalog/extra/spiski-tovarov/tovary-bez-skidok/'
PARK='https://parkingsvo.ru/vazhno-znat/pravila-ispolzovaniya.html'
DOC='https://parking.svo.su/storage/2040/02/03/new-rules.pdf'
CLOCK=datetime.fromisoformat(NOW)+timedelta(hours=1)

def base(url=ROOT,label='товары-исключения'):
    obj=partner();obj['earnText']='<a href="'+url+'">'+label+'</a>'
    preview=af.catalog(json_observation(category_data()))[71]
    row=af.detail(json_observation(obj,'detail'),preview,NOW)
    return {'schema_version':2,'run_id':'123:1','observed_at':NOW,'records':[row],
      'sources':[{'source_id':'aeroflot','name':'Aeroflot','root':af.ROOT,'status':'ok','discovered':1,
        'normalized':1,'failed':0,'errors':[],'coverage':'one current partner','region':None,'observed_at':NOW}]}

def page(names=('One','Two'),total=3,next_page=True):
    products=''.join('<a class="product-name" href="/catalog/item/'+n+'/">'+n+'</a>' for n in names)
    paging='<div class="pagination-microservices"><a href="?page=2">2</a></div>' if next_page else ''
    return ('<html><head><title>Exclusions</title></head><body><header>Unrelated discount 99%</header><main><h1>Товары-исключения</h1>'
      '<span class="app-main-title_count">'+str(total)+' товаров</span><div class="CatalogSlugsPage_headerSubText__changed">Баллы на эти товары не начисляются.</div>'
      +products+paging+'</main><footer>Код HELLO99</footer></body></html>').encode()

def project(row):
    bundle={'schema_version':2,'run_id':'456:1','observed_at':row['observed_at'],'records':[row],
      'sources':[{'source_id':r.SID,'name':'Rules','root':r.ROOT,'status':'ok','discovered':1,'normalized':1,
      'failed':0,'errors':[],'coverage':'one condition','region':None,'observed_at':row['observed_at']}]}
    cells=prepare(bundle)['parser_offers'][0]
    raw=make_input({'id':row['id'],'origin':'parser_offers','row':2,'fields':{k:{'value':v} for k,v in zip(SCHEMAS['parser_offers'],cells)}})
    return normalize_record(raw,as_of=row['observed_at'][:10])

class Network:
    def __init__(self,denied=False,repeat=False):self.calls=[];self.denied=denied;self.repeat=repeat
    def __call__(self,url,**kw):
        self.calls.append(url)
        if url.endswith('/robots.txt'):return Response(b'User-agent: *\nDisallow: /storage/\n' if self.denied and 'svo.su' in url else b'User-agent: *\nAllow: /\n',mime='text/plain')
        if url==ROOT:return Response(b'',301,headers={'Location':FINAL})
        if url==FINAL:return Response(page())
        if url==FINAL+'?page=2':return Response(page() if self.repeat else page(('Three',),next_page=False))
        if url==PARK:return Response(b'',302,headers={'Location':DOC})
        if url==DOC:return Response(pdf(['Parking use rules and exclusions.','Second page, edition changed.']),mime='application/pdf')
        raise AssertionError('Unrequested target '+url)

class Contracts(unittest.TestCase):
    def setUp(self):self.assertIsNotNone(r,'New source-linked collector is absent')
    def test_discovery_uses_source_link_and_retains_parent_time(self):
        entries,inventory=r.discover(base(),CLOCK)
        self.assertEqual([e['url'] for e in entries],[ROOT]);self.assertEqual(entries[0]['parents'][0]['observed_at'],NOW)
        self.assertEqual(r.discover(base('https://other.test/rules','Правила'),CLOCK)[0],[])
    def test_stale_parent_rejected(self):
        with self.assertRaises(ValueError):r.discover(base(),CLOCK+timedelta(days=8))
    def test_urls_reject_credentials_foreign_hosts_and_unbounded_queries(self):
        for url in ['http://stoletov.ru/catalog/groups/',FINAL+'?token=secret',FINAL+'?page=9999',FINAL+'?page=2&page=3','https://parking.svo.su.evil.test/storage/a.pdf','https://stoletov.ru/personal/']:
            with self.subTest(url=url),self.assertRaises(ValueError):r.checked_url(url)
    def test_sanitization_retains_owned_relative_product_and_pagination_links(self):
        value=r.clean_html(page(),FINAL)
        self.assertEqual(r.clean_html(value.encode(),FINAL),value)
        fields=r.catalog_fields(value,FINAL)
        self.assertEqual(len(fields['products']),2);self.assertEqual(fields['next_links'],[FINAL+'?page=2'])
        self.assertNotIn('HELLO99',value);self.assertNotIn('99%',value)
    def test_password_page_rejected(self):
        with self.assertRaises(ValueError):r.clean_html(b'<html><body><input type="password"></body></html>',FINAL)
    def test_changed_product_membership_changes_output(self):
        a=r.catalog_fields(r.clean_html(page(),FINAL),FINAL)
        b=r.catalog_fields(r.clean_html(page(('Changed',),total=1,next_page=False),FINAL),FINAL)
        self.assertNotEqual(a['products'],b['products']);self.assertEqual(b['total'],1)
    def test_complete_pagination_keeps_all_unique_items_without_product_requests(self):
        net=Network()
        with tempfile.TemporaryDirectory() as tmp:
            bundle,audit=r.collect(base(),tmp,'456:1','a'*40,get=net,sleep=lambda _:None,observed_at=CLOCK.isoformat())
            self.assertEqual(bundle['sources'][0]['status'],'ok')
            self.assertEqual(audit['results'][0]['unique_products'],3)
            self.assertTrue(audit['results'][0]['catalogue_complete'])
            self.assertEqual(len(bundle['records']),2)
            for row in bundle['records']:
                projected=project(row);self.assertFalse(projected['benefits']);self.assertFalse(projected['codes']);self.assertEqual(len(projected['conditions']),1)
        self.assertFalse(any('/catalog/item/' in u for u in net.calls))
    def test_repeated_page_does_not_certify_completeness(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle,audit=r.collect(base(),tmp,'456:1','a'*40,get=Network(repeat=True),sleep=lambda _:None,observed_at=CLOCK.isoformat())
            self.assertEqual(bundle['sources'][0]['status'],'partial');self.assertFalse(audit['results'][0]['catalogue_complete'])
    def test_changed_pdf_destination_and_pages_are_read_and_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle,audit=r.collect(base(PARK,'Правила использования'),tmp,'456:1','a'*40,get=Network(),sleep=lambda _:None,observed_at=CLOCK.isoformat(),allow_ocr=False)
            self.assertTrue(bundle['records']);self.assertEqual(bundle['records'][0]['details']['page_count'],2)
            self.assertEqual(bundle['records'][0]['details']['download_url'],DOC)
            self.assertFalse(project(bundle['records'][0])['benefits'])
    def test_redirect_destination_policy_checked_before_target_request(self):
        net=Network(denied=True)
        with tempfile.TemporaryDirectory() as tmp:
            bundle,audit=r.collect(base(PARK,'Правила'),tmp,'456:1','a'*40,get=net,sleep=lambda _:None,observed_at=CLOCK.isoformat())
            self.assertEqual(bundle['sources'][0]['status'],'failed')
            self.assertNotIn(DOC,net.calls)
    def test_publisher_reconstructs_and_rejects_changed_object_and_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle,audit=r.collect(base(),tmp,'456:1','a'*40,get=Network(),sleep=lambda _:None,observed_at=CLOCK.isoformat())
            clock=datetime.fromisoformat(audit['finished_at'])
            self.assertEqual(r.validate_bundle(tmp,'456:1','a'*40,clock),bundle)
            with self.assertRaises(ValueError):r.validate_bundle(tmp,'other','a'*40,clock)
            payload=Path(tmp)/'normalized.json';changed=copy.deepcopy(bundle);changed['records'][0]['conditions_text']='Made up'
            payload.write_text(json.dumps(changed))
            with self.assertRaises(ValueError):r.validate_bundle(tmp,'456:1','a'*40,clock)
    def test_rate_limit_not_retried(self):
        calls=[]
        def get(url,**kwargs):calls.append(url);return Response(b'',429,headers={'Retry-After':'60'})
        with tempfile.TemporaryDirectory() as tmp:
            bundle,audit=r.collect(base(),tmp,'456:1','a'*40,get=get,sleep=lambda _:None,observed_at=CLOCK.isoformat())
            self.assertEqual(len(calls),1);self.assertEqual(bundle['sources'][0]['status'],'failed')

if __name__=='__main__':unittest.main()
