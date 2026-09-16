"""Current parent -> binary document -> reconstructed, non-promotional records."""
import copy, json, sys, tempfile, unittest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]))
import coral_pdf_collect as p
import coral_import as g
import test_coral_import as f
import test_coral_linked_rules as rules
from test_document_text import pdf
from normalized import content_hash,validate_offer
from unified_normalization import make_input,normalize_record
from sheets_normalized import SCHEMAS,prepare

URL='https://coralbonus.ru/media/example/new-rules.pdf'
KEY='fixture-key-not-a-real-secret-12345'
NOW=datetime.fromisoformat(f.NOW)

class Source(rules.LinkedSource):
    def read(self,url):
        if g.linked.is_rule_url(url):
            raw=rules.article(url).replace('</section>',f'<a href="{URL}">Document</a></section>')
            o=f.obs(url,raw);self.observations.append(o);return o
        return super().read(url)

class Response:
    def __init__(self,data,status=200,headers=None):
        self.data=data;self.status_code=status
        self.headers={'Ant-credits-cost':'1','Ant-page-status-code':'200','Content-Type':'application/pdf',**(headers or {})}
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def iter_content(self,n):
        for start in range(0,len(self.data),n):yield self.data[start:start+n]

class Network:
    def __init__(self,body=None,status=200,headers=None):
        self.body=body or pdf(['Rules and requirements, not a new discount.'])
        self.status=status;self.headers=headers;self.calls=[]
    def __call__(self,url,**kwargs):
        self.calls.append((url,kwargs))
        if url.endswith('/usage'):
            return Response(json.dumps({'plan_name':'Free','plan_total_credits':10000,'remained_credits':6000}).encode())
        return Response(self.body,self.status,self.headers)
    def reader(self,key):return p.Reader(key,get=self,clock=lambda:0,sleep=lambda _:None)

def make_base(folder):
    source=Source();b=g.collect(source,'7:1',f.NOW)
    audit={'run_id':'7:1','commit':'a'*40,'started_at':f.NOW,'finished_at':f.NOW,'cleanup_verified':True,
           'scrapingant_credits':0,'source_account_used':False,'observations':source.observations}
    (folder/'normalized.json').write_text(json.dumps(b));(folder/'evidence.json').write_text(json.dumps(audit))
    return b

class PdfTests(unittest.TestCase):
    def collect(self,folder,net=None,key=KEY):
        make_base(folder);net=net or Network()
        with patch.object(p,'now',return_value=f.NOW),patch.object(p,'datetime') as clock:
            clock.now.return_value=NOW
            return p.collect(folder,key,'7:1','a'*40,reader_factory=net.reader)
    def test_changed_discovered_filename_and_parent_binding(self):
        with tempfile.TemporaryDirectory() as d:
            base=make_base(Path(d));first=p.discover(base['records']);new=copy.deepcopy(base['records'])
            new[-1]['details']['public_rule']['unread_links'][0]['url']=URL.replace('new-rules','changed')
            self.assertNotEqual(first,p.discover(new));self.assertEqual(first[0]['parents'][0]['record_id'],base['records'][-1]['id'])
    def test_scope_rejects_foreign_account_query_and_encoded_path_escape(self):
        for value in ('http://coralbonus.ru/media/x/a.pdf',URL+'?token=x',URL+'#x',URL.replace('coralbonus.ru','evil.example'),
                      'https://coralbonus.ru/media/a/../x.pdf','https://coralbonus.ru/media/a/%2fsecret.pdf',
                      'https://coralbonus.ru/media/a/%252fsecret.pdf','https://coralbonus.ru/account/x.pdf'):
            with self.subTest(url=value):self.assertFalse(p.is_pdf(value))
        self.assertTrue(p.is_pdf(URL));self.assertTrue(p.is_pdf(URL.replace('new-rules','правила-2027')))
    def test_full_collection_and_independent_binary_reconstruction(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);b=self.collect(root);self.assertEqual(len(b['records']),4)
            self.assertEqual(b['sources'][-1]['source_id'],p.SOURCE_ID);self.assertEqual(b['sources'][-1]['status'],'ok')
            self.assertEqual(p.validate_bundle(root,'7:1','a'*40,NOW),b)
            self.assertEqual(json.loads((root/'pdf-report.json').read_text())['reserved'],1)
    def test_changed_text_and_page_count_change_output_not_url_identity(self):
        out=[]
        for values in (['New terms 11'],['Changed terms 29','Page two terms']):
            with tempfile.TemporaryDirectory() as d:out.append(self.collect(Path(d),Network(pdf(values)))['records'][-1])
        self.assertEqual(out[0]['id'],out[1]['id']);self.assertNotEqual(out[0]['content_sha256'],out[1]['content_sha256'])
        self.assertIn('29',out[1]['conditions_text']);self.assertEqual(out[1]['details']['page_count'],2)
    def test_no_key_keeps_all_base_rows_and_reports_unread_file(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);b=self.collect(root,key='')
            self.assertEqual(len(b['records']),3);self.assertEqual(b['sources'][-1]['status'],'failed')
            self.assertEqual(p.validate_bundle(root,'7:1','a'*40,NOW),b)
    def test_html_response_is_not_pdf_or_full_conditions(self):
        with tempfile.TemporaryDirectory() as d:
            b=self.collect(Path(d),Network(b'<html>error</html>'))
            self.assertEqual(len(b['records']),3);self.assertEqual(b['sources'][-1]['failed'],1)
    def test_corrupt_pdf_bytes_cannot_pass_by_retaining_the_record(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.collect(root);path=next((root/'pdf').glob('*.pdf'));path.write_bytes(pdf(['Wrong content']))
            with self.assertRaises(ValueError):p.validate_bundle(root,'7:1','a'*40,NOW)
    def test_changed_published_text_or_parent_rejected_after_rehash(self):
        for kind in ('text','parent','status'):
            with tempfile.TemporaryDirectory() as d:
                root=Path(d);b=self.collect(root);r=b['records'][-1]
                if kind=='text':r['conditions_text']='Invented rules'
                elif kind=='parent':r['details']['parent_references'][0]['label']='Wrong parent'
                else:b['sources'][-1]['discovered']=100
                r['content_sha256']=content_hash(r);(root/'combined.json').write_text(json.dumps(b))
                with self.subTest(kind=kind),self.assertRaises(ValueError):p.validate_bundle(root,'7:1','a'*40,NOW)
    def test_receipt_origin_status_and_scope_are_mandatory(self):
        for field,value in (('origin_status','403'),('url','https://other.example/x.pdf'),('charged',99)):
            with tempfile.TemporaryDirectory() as d:
                root=Path(d);self.collect(root);a=json.loads((root/'pdf-report.json').read_text());a['requests'][0][field]=value
                (root/'pdf-report.json').write_text(json.dumps(a))
                with self.subTest(field=field),self.assertRaises(ValueError):p.validate_bundle(root,'7:1','a'*40,NOW)
    def test_account_or_paid_plan_stops_before_download(self):
        for plan in ('Pro','unknown'):
            def get(url,**kw):return Response(json.dumps({'plan_name':plan,'plan_total_credits':10000,'remained_credits':9000}).encode())
            with self.subTest(plan=plan),self.assertRaises(Exception):p.Reader(KEY,get=get)
    def test_rate_limit_is_not_retried_as_another_proxy(self):
        net=Network(status=429);r=net.reader(KEY)
        with self.assertRaisesRegex(ValueError,'cp_provider_auth_quota_or_rate_limit'):r.read(URL)
        self.assertEqual(len(r.requests),1);self.assertTrue(r.stopped)
    def test_oversized_body_and_key_echo_never_archived(self):
        for data in (b'%PDF-'+b'x'*p.MAX_BYTES,b'%PDF-'+KEY.encode()):
            r=Network(data).reader(KEY)
            with self.assertRaises(ValueError):r.read(URL)
            self.assertTrue(r.stopped)
    def test_pdf_only_safe_step_has_no_google_credential(self):
        path=Path(__file__).parents[2]/'.github/workflows/coral-import.yml'
        text=path.read_text();step=text.split('- name: Download source-linked public PDFs')[1].split('- uses:')[0]
        self.assertIn('SCRAPINGANT_API_KEY',step);self.assertNotIn('GOOGLE_ACCESS_TOKEN',step)
        self.assertIn('from coral_pdf_collect import validate_bundle',text);self.assertIn('combined.json --publish',text)
    def test_pdf_rules_are_not_projected_as_discounts_or_codes(self):
        with tempfile.TemporaryDirectory() as d:
            b=self.collect(Path(d),Network(pdf(['Refund 90 percent. Promo code EXAMPLE123 is a fictional example.'])))
            r=b['records'][-1];validate_offer(r);row=prepare(b)['parser_offers'][-1]
            raw=make_input({'id':r['id'],'origin':'parser_offers','row':2,'fields':{k:{'value':v} for k,v in zip(SCHEMAS['parser_offers'],row)}})
            n=normalize_record(raw,as_of='2026-09-16')
            self.assertFalse(n['benefits']);self.assertFalse(n['codes']);self.assertFalse(n['costs']);self.assertTrue(n['conditions'])

if __name__=='__main__':unittest.main()
