"""New public link/document values are input; no snapshot answer fixtures."""
import copy,json,sys,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).parents[1]))
import ekp_linked_rules as r
import ekp_catalog as e
from normalized import validate_offer,content_hash
from sheets_normalized import prepare,SCHEMAS
from unified_normalization import make_input,normalize_record
from document_text import extract_pdf
from test_document_text import pdf
from test_rzd_external import Response

PARENT='2026-09-16T12:00:00+00:00'
NOW='2026-09-17T12:00:00+00:00'
CLOCK=datetime.fromisoformat(NOW)
URL='https://mpclinic.ru/upload/new-conditions.pdf'
HTML='https://ekp.spb.ru/silverage'
COMMIT='a'*40

def parent(ident='31',url=URL,locked=False,label='Приложение с условиями'):
    row={'id':ident,'name':'Партнер '+ident,'active':True,'description_authorized':locked,'categories':[],
        'text':'Публичное описание бизнеса','loyaltyDescription':'<p>Скидка 13% по карте ЕКП.</p><a href="'+url+'">'+label+'</a>',
        'discountScheme':'Предъявить свою карту до оплаты'}
    return e.make_record(row,PARENT,request=e.query(0),response_sha='b'*64,observed_total=1,completed_at=PARENT)

def base(rows=None):
    rows=rows if rows is not None else [parent()]
    return {'schema_version':2,'run_id':'123:1','observed_at':PARENT,'records':rows,'sources':[
        {'source_id':'ekp','name':'ЕКП','root':e.ROOT,'status':'ok','normalized':len(rows),'discovered':len(rows),
         'failed':0,'coverage':'public','region':None,'errors':[],'observed_at':PARENT}]}

def html(words='Возврат 100%. НДС 5%. Льготы по карте и для других категорий указаны отдельно. Покупка производится в кассе. Ограничения приведены в правилах.'):
    return ('<html><head><title>Публичные условия</title></head><body><header>Чужая скидка 99%</header><main><h1>Условия услуги</h1><p>'+words+'</p></main><footer>Телефон</footer></body></html>').encode()

def receipt(url=URL,data=b'%PDF-test',**kw):
    return {'url':url,'transport':'direct_https','requested_at':NOW,'finished_at':NOW,
        'status':200,'bytes':len(data),'sha256':r.sha(data),'mime':'application/pdf' if url.endswith('.pdf') else 'text/html',**kw}

def saved(folder,*,data=None,doc=None,bundle=None):
    data=data or pdf(['New rules, 17 percent is not an additional reward.'])
    bundle=bundle or base();entries,inventory=r.discover(bundle,CLOCK)
    out=Path(folder);(out/'objects').mkdir(exist_ok=True)
    rec=receipt(entries[0]['url'],data);filename=r.sha(entries[0]['url'].encode())+'.pdf'
    (out/'objects'/filename).write_bytes(data)
    audit={'run_id':'456:1','commit':COMMIT,'started_at':NOW,'finished_at':NOW,'inventory':inventory,
        'results':[{'url':entries[0]['url'],'file':filename,'sha256':r.sha(data),'receipt':rec,'document':doc or extract_pdf(data)}],
        'requests':[rec],'reserved':0,'source_account_used':False}
    result=r.assemble(bundle,audit,out)
    for name,value in [('parents.json',bundle),('audit.json',audit),('normalized.json',result)]:
        (out/name).write_text(json.dumps(value,ensure_ascii=False))
    return audit,result

def project(row):
    b={'schema_version':2,'run_id':'456:1','observed_at':NOW,'records':[row],
       'sources':[{'source_id':r.SID,'name':'Rules','root':r.ROOT,'status':'ok','normalized':1,'discovered':1,
                   'failed':0,'coverage':'one document','region':None,'errors':[],'observed_at':NOW}]}
    values=prepare(b)['parser_offers'][0]
    raw={'id':row['id'],'origin':'parser_offers','row':2,
         'fields':{k:{'value':v} for k,v in zip(SCHEMAS['parser_offers'],values)}}
    return normalize_record(make_input(raw),as_of='2026-09-17')

class Discovery(unittest.TestCase):
    def test_new_document_slug_and_edition_are_discovered(self):
        for path in ('v3.pdf','changed-document-2040.pdf'):
            url='https://mpclinic.ru/upload/'+path
            entries,inventory=r.discover(base([parent(url=url)]),CLOCK)
            self.assertEqual(entries[0]['url'],url)
            self.assertEqual(entries[0]['parents'][0]['observed_at'],PARENT)
            self.assertTrue(inventory['parent_is_not_a_new_source_observation'])
    def test_shared_document_download_once_parent_links_all_preserved(self):
        entries,_=r.discover(base([parent('31'),parent('32')]),CLOCK)
        self.assertEqual(len(entries),1);self.assertEqual(len(entries[0]['parents']),2)
    def test_gated_row_cannot_seed_private_rules(self):
        rows=[parent(),parent('32',locked=True)]
        entries,inventory=r.discover(base(rows),CLOCK)
        self.assertEqual(inventory['gated_parent_count'],1);self.assertEqual(len(entries[0]['parents']),1)
        forged=copy.deepcopy(rows[1]);forged['details']['public_partner']['loyaltyDescription']='<a href="'+URL+'">SECRET</a>'
        forged['content_sha256']=content_hash(forged)
        with self.assertRaises(ValueError):r.discover(base([forged]),CLOCK)
    def test_old_snapshot_not_renamed_as_current_catalogue(self):
        with self.assertRaises(ValueError):r.discover(base(),datetime.fromisoformat('2026-09-24T12:00:01+00:00'))
        with self.assertRaises(ValueError):r.discover(base(),datetime.fromisoformat('2026-09-15T12:00:00+00:00'))
    def test_unreviewed_app_and_merchant_links_are_inventory_not_requests(self):
        for url in ('https://tutu.onelink.me/CCCT/new','https://mpclinic.ru/account','https://unknown.example/rules.pdf'):
            entries,inventory=r.discover(base([parent(url=url)]),CLOCK)
            self.assertEqual(entries,[]);self.assertNotEqual(inventory['links'][0]['classification'],'selected_public_rules')
    def test_idn_is_canonicalized_without_changing_path(self):
        self.assertEqual(r.checked_url('https://энергиявысоты.рф/img/dogovori/another.pdf'),
            'https://'+r.HOSTS[1]+'/img/dogovori/another.pdf')
    def test_unsafe_urls_are_rejected(self):
        for url in (URL+'?token=secret',URL+'#body',URL.replace('https','http'),URL.replace('mpclinic.ru','user@mpclinic.ru'),
                    'https://mpclinic.ru:8443/upload/test.pdf','https://mpclinic.ru/upload/../a.pdf','https://mpclinic.ru/upload/%2fsecret.pdf'):
            with self.subTest(url=url),self.assertRaises(ValueError):r.checked_url(url)

class Mapping(unittest.TestCase):
    def test_html_changed_conditions_stable_id_no_other_page_chrome(self):
        entry=r.discover(base([parent(url=HTML)]),CLOCK)[0][0]
        data=r.clean_html(html()).encode();a=r.rows_for(data,entry,receipt(HTML,data),NOW)[0]
        changed=r.clean_html(html('Правила изменены. '+('Новый срок 11 дней. '*8))).encode()
        b=r.rows_for(changed,entry,receipt(HTML,changed),NOW)[0]
        self.assertEqual(a['id'],b['id']);self.assertNotEqual(a['content_sha256'],b['content_sha256'])
        self.assertNotIn('99%',a['conditions_text']);self.assertIn('11 дней',b['conditions_text'])
        self.assertFalse(project(a)['benefits']);self.assertFalse(project(a)['codes'])
    def test_ambiguous_empty_login_and_script_shell_fail(self):
        for raw in (b'<html><body>JavaScript required</body></html>',html().replace(b'</main>',b'<h1>Other</h1></main>'),
                    html().replace(b'</main>',b'<input type=password></main>')):
            with self.subTest(raw=raw[:30]),self.assertRaises(ValueError):r.html_fields(r.clean_html(raw))
    def test_sanitizer_is_idempotent_and_removes_active_content(self):
        raw=html().replace(b'</main>',b'<script>SECRET</script><form>PRIVATE</form><button>Buy</button></main>')
        a=r.clean_html(raw);self.assertEqual(a,r.clean_html(a))
        for word in ('SECRET','PRIVATE','<script','<form','<button'):self.assertNotIn(word,a)
    def test_pdf_number_of_pages_and_text_changes_are_not_fixed(self):
        for n in (1,3):
            with tempfile.TemporaryDirectory() as folder:
                data=pdf(['Document change '+str(i) for i in range(n)])
                audit,b=saved(folder,data=data)
                self.assertEqual(b['records'][0]['details']['page_count'],n)
                self.assertFalse(project(b['records'][0])['benefits']);self.assertFalse(project(b['records'][0])['codes'])
                self.assertEqual(len(project(b['records'][0])['conditions']),1)
    def test_saved_ocr_is_replayed_without_a_second_ocr_call(self):
        data=pdf(['',''])
        with patch('document_text.ocr_pages',return_value={1:('Machine read page 1',{}),2:('Machine read page 2',{})}) as ocr:
            doc=extract_pdf(data)
        self.assertEqual(ocr.call_count,1)
        with tempfile.TemporaryDirectory() as folder,patch('document_text.ocr_pages',side_effect=AssertionError('second OCR')):
            _,b=saved(folder,data=data,doc=doc)
            r.validate_bundle(folder,'456:1',COMMIT,CLOCK)
            self.assertEqual(b['records'][0]['source_status'],'public_rules_ocr_unverified')
            self.assertIn('ocr_text_unverified_no_manual_corrections',b['records'][0]['warnings'])
    def test_record_rehash_does_not_hide_wrong_parent_or_promotion(self):
        with tempfile.TemporaryDirectory() as folder:
            _,b=saved(folder);row=b['records'][0]
            for key,value in [('source_account_used',True),('eligibility_verified',True),('retrieval_method','fake')]:
                changed=copy.deepcopy(row);changed['details'][key]=value;changed['content_sha256']=content_hash(changed)
                with self.subTest(key=key),self.assertRaises(ValueError):validate_offer(changed)
    def test_corrupted_object_page_hash_receipt_or_run_are_rejected(self):
        for kind in ('object','page','receipt','run','credits'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as folder:
                audit,b=saved(folder);p=Path(folder)
                if kind=='object':(p/'objects'/audit['results'][0]['file']).write_bytes(b'not PDF')
                if kind=='page':audit['results'][0]['document']['pages'][0]['text']='Fabricated'
                if kind=='receipt':audit['results'][0]['receipt']['url']=HTML
                if kind=='run':audit['run_id']='other:1'
                if kind=='credits':audit['reserved']=r.MAX_CREDITS+1
                (p/'audit.json').write_text(json.dumps(audit))
                with self.assertRaises(ValueError):r.validate_bundle(p,'456:1',COMMIT,CLOCK)
    def test_one_failed_document_retains_successful_document(self):
        with tempfile.TemporaryDirectory() as folder:
            audit,b=saved(folder);parents=base([parent(),parent('32',HTML)])
            entries,inventory=r.discover(parents,CLOCK)
            good=audit['results'][0];audit['results']=[good if x['url']==URL else {'url':x['url'],'error':'el_http_403'} for x in entries]
            audit['inventory']=inventory
            rebuilt=r.assemble(parents,audit,folder)
            self.assertEqual(len(rebuilt['records']),1);self.assertEqual(rebuilt['sources'][0]['status'],'partial')

class Network(unittest.TestCase):
    def reader(self,replies):
        session=Mock();session.get.side_effect=replies
        client=r.Reader('',session=session,sleep=lambda _:None)
        return client,session
    def test_policy_denial_never_fetches_target(self):
        client,s=self.reader([Response(b'User-agent: *\nDisallow: /upload/\n',mime='text/plain')])
        with self.assertRaisesRegex(ValueError,'el_source_policy'):client.read(URL)
        self.assertEqual(s.get.call_count,1)
    def test_target_403_and_429_stop_without_proxy_retry(self):
        for status in (403,429):
            client,s=self.reader([Response(b'User-agent: *\nAllow: /\n',mime='text/plain'),Response(b'no',status=status)])
            with self.assertRaises(ValueError):client.read(URL)
            self.assertEqual(s.get.call_count,2)
    def test_direct_pdf_needs_no_api_key(self):
        data=pdf(['Document source conditions'])
        client,s=self.reader([Response(b'User-agent: *\nAllow: /\n',mime='text/plain'),Response(data,mime='application/pdf')])
        self.assertEqual(client.read(URL)[0],data);self.assertEqual(client.reserved,0)
    def test_foreign_redirect_is_not_followed(self):
        client,s=self.reader([Response(b'User-agent: *\nAllow: /\n',mime='text/plain'),Response(b'',status=302,headers={'Location':'https://private.example/file'})])
        with self.assertRaises(ValueError):client.read(URL)
        self.assertEqual(s.get.call_count,2)
    def test_declarations_and_credit_limits_remain_bounded(self):
        client,s=self.reader([Response(b'User-agent: *\nAllow: /\nCrawl-delay: 9\n',mime='text/plain'),Response(pdf(['Rules']),mime='application/pdf')])
        client.read(URL);self.assertEqual(client.delays['mpclinic.ru'],9)
        client.key='synthetic';client.free_checked=True;client.reserved=r.MAX_CREDITS
        with self.assertRaisesRegex(ValueError,'el_credit_budget'):client.raw(URL,provider='datacenter')
    def test_provider_auth_refusal_halts_all_further_provider_calls(self):
        client,s=self.reader([Response(b'no',status=402)])
        client.key='synthetic';client.free_checked=True
        with self.assertRaises(ValueError):client.raw(URL,provider='datacenter')
        with self.assertRaisesRegex(ValueError,'el_provider_stopped'):client.raw(URL,provider='residential')
        self.assertEqual(s.get.call_count,1)

if __name__=='__main__':unittest.main()
