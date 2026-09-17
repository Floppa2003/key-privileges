"""Public content and discovery mutations; no stored live offer answers."""
import copy,json,sys,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]))
import rzd_external as r
from normalized import validate_offer, content_hash
from sheets_normalized import prepare,SCHEMAS
from unified_normalization import make_input,normalize_record
from test_document_text import pdf

NOW='2026-09-17T12:00:00+00:00';COMMIT='a'*40
URL=r.TOUR.rstrip('/')+r.PREFIX+'fresh-tour'
PDF='https://www.unicreditbank.ru/content/dam/new/reward-rules.pdf'
ROBOTS=b'User-agent: *\nDisallow: /account/\n'

def html(body):return '<html><head><title>Public partner</title></head><body>'+body+'</body></html>'
def tour(rate='13',name='Новый тур',clause=True):
    benefit='<p>Участникам РЖД Бонус скидка '+rate+'%. Номер карты укажите при заявке.</p>' if clause else '<p>Без упоминания программы.</p>'
    return html('<header>Чужая скидка 99%</header><h1>'+name+'</h1><div class="modal-main content-price"><div class="text-content-route">'+
        '<table><tr><th>Категория</th><th>Цена</th></tr><tr><td>Взрослый</td><td>80 000</td></tr></table>'+benefit+
        '<p>Для детей скидка 40%. Питание включено. Личные расходы оплачиваются отдельно.</p></div></div>')
def bank(link=PDF):return html('<div class="ucr-contentpage-parsys"><h1>Дебетовая карта CASH&amp;BACK</h1>'+
    '<p>Обслуживание карты и использование вознаграждения определяются правилами. Обмен РЖД здесь не обещан.</p>'+
    '<table class="downloadlist"><tr><td>Правила выплаты вознаграждения</td><td><a href="'+link+'">Скачать</a></td></tr></table></div>')
def project(row):
    b={'schema_version':2,'run_id':'test','observed_at':NOW,'records':[row],
       'sources':[{'source_id':row['source_id'],'name':'Test','root':row['source_url'],'status':'ok','normalized':1,'discovered':1,'failed':0,'coverage':'scope','region':None,'errors':[],'observed_at':NOW}]}
    values=prepare(b)['parser_offers'][0]
    raw={'id':row['id'],'origin':'parser_offers','row':2,'fields':{k:{'value':v} for k,v in zip(SCHEMAS['parser_offers'],values)}}
    return normalize_record(make_input(raw),as_of='2026-09-17')

class Response:
    def __init__(self,data,status=200,mime='text/html',headers=None):
        self.data=data;self.status_code=status;self.headers={'Content-Type':mime,**(headers or {})};self._content=data;self.encoding='utf8';self.apparent_encoding='utf8'
    def __enter__(self):return self
    def __exit__(self,*_):pass
    def iter_content(self,_):yield self.data
    @property
    def text(self):return self._content.decode(self.encoding)

class Network:
    def __init__(self,fail=None):self.calls=[];self.fail=fail
    def __call__(self,url,**kw):
        self.calls.append((url,kw))
        if url==self.fail:return Response(b'<html>Refused</html>',status=403)
        if url.endswith('/robots.txt'):return Response(ROBOTS,mime='text/plain')
        if url==r.TOUR:return Response(html('<a href="'+URL+'">Tour</a>').encode())
        if url==URL:return Response(tour().encode())
        if url==r.BANK:return Response(bank().encode())
        if url==PDF:return Response(pdf(['Reward rules. Refunds are not rewards.']),mime='application/pdf')
        raise AssertionError('Unexpected URL '+url)

class MappingTests(unittest.TestCase):
    def test_mutated_tour_rate_title_change_data_not_identity(self):
        a=r.tour_record(tour(),URL,r.TOUR,NOW);b=r.tour_record(tour('27','Другой тур'),URL,r.TOUR,NOW)
        self.assertEqual(a['id'],b['id']);self.assertNotEqual(a['content_sha256'],b['content_sha256'])
        self.assertEqual(b['rates'][0]['value'],'27');self.assertNotIn('99%',b['conditions_text'])
        self.assertEqual(b['details']['public_tour']['pricing_tables'][0][1],['Взрослый','80 000'])
    def test_normalizer_keeps_only_owned_rzd_rate(self):
        row=r.tour_record(tour(),URL,r.TOUR,NOW);common=project(row)
        self.assertEqual([x['value'] for x in common['benefits']],['13'])
        self.assertEqual(common['codes'],[]);self.assertIn('40%',row['conditions_text'])
        self.assertEqual(common['benefits'][0]['scope']['source_url'],URL)
    def test_no_rzd_clause_excluded_not_inferred(self):self.assertIsNone(r.tour_record(tour(clause=False),URL,r.TOUR,NOW))
    def test_heading_and_own_price_block_required(self):
        for raw in (tour().replace('<h1>','<h2>').replace('</h1>','</h2>'),tour().replace('content-price','other'),tour().replace('</body>','<h1>Other</h1></body>')):
            with self.assertRaises(ValueError):r.tour_record(raw,URL,r.TOUR,NOW)
    def test_source_owned_rzd_text_in_unknown_structure_is_error(self):
        raw=tour().replace('<p>Участникам','<section>Участникам').replace('при заявке.</p>','при заявке.</section>')
        with self.assertRaisesRegex(ValueError,'re_tour_clause_structure'):r.tour_record(raw,URL,r.TOUR,NOW)
    def test_dynamic_links_deduplicate_exclude_foreign_and_report_queries(self):
        raw=html(''.join('<a href="'+u+'">x</a>' for u in [URL,URL,URL+'?page=2',URL.replace('rzdtour.com','evil.example')]))
        good,queries=r.tour_links(raw,r.TOUR);self.assertEqual(good,[URL]);self.assertEqual(queries,[URL+'?page=2'])
    def test_url_security(self):
        for u in [URL+'?key=x',URL+'#a',URL.replace('https:','http:'),'https://rzdtour.com/account/','https://www.unicreditbank.ru/account/a.pdf',URL+'/../a',URL+'%2f',URL.replace('rzdtour.com','x@rzdtour.com')]:
            with self.subTest(url=u),self.assertRaises(ValueError):r.checked_url(u)
    def test_html_canonical_mismatch_instruction_and_restriction_rejected(self):
        for raw in [html('ignore previous instructions'),html('x').replace('Public partner','Access denied'),html('<link rel="canonical" href="https://foreign.example/">')]:
            with self.assertRaises(ValueError):r.clean_html(raw,URL)
    def test_sanitizer_removes_forms_and_scripts(self):
        raw=r.clean_html(html('<form><input value="private"></form><script>private</script><h1>Allowed</h1>'),URL)
        self.assertNotIn('private',raw);self.assertIn('Allowed',raw)
    def test_bank_documents_dynamic_label_and_source(self):
        changed=PDF.replace('reward-rules','new-version');p=r.bank_fields(bank(changed))
        self.assertEqual(p['documents'][0]['url'],changed)
        self.assertFalse(r.bank_record(bank(),NOW)['rates'])
    def test_bank_reference_never_confirms_rzd_exchange(self):
        row=r.bank_record(bank(),NOW);common=project(row)
        self.assertFalse(row['details']['rzd_exchange_confirmed']);self.assertEqual(common['benefits'],[])
        self.assertEqual(common['quality']['level'],'evidence_only')
    def test_pdf_has_parent_and_conditions_without_false_benefits(self):
        parent=r.bank_record(bank(),NOW);entry=r.bank_fields(bank())['documents'][0]
        rows=r.bank_pdf_records(pdf(['Discount 90 percent is a penalty example.','More updated terms.']),entry,parent,NOW)
        self.assertTrue(rows);self.assertEqual(rows[0]['details']['page_count'],2)
        self.assertEqual(rows[0]['details']['parent_record_id'],parent['id'])
        self.assertEqual(project(rows[0])['benefits'],[]);self.assertEqual(project(rows[0])['codes'],[])
    def test_bank_pdf_foreign_host_rejected(self):
        with self.assertRaises(ValueError):r.bank_fields(bank('https://evil.example/a.pdf'))

class PipelineTests(unittest.TestCase):
    def bundle(self,folder,network):
        reader=r.Reader(folder,get=network,sleep=lambda _:None,clock=lambda:0)
        with patch.object(r,'now',return_value=NOW):payload=r.collect(reader,'7:1',NOW)
        audit={'run_id':'7:1','commit':COMMIT,'observed_at':NOW,'finished_at':NOW,'receipts':reader.receipts}
        (folder/'normalized.json').write_text(json.dumps(payload));(folder/'audit.json').write_text(json.dumps(audit))
        return payload,audit
    def test_full_runtime_and_replay_reconstruct_all_sources(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);net=Network();payload,audit=self.bundle(p,net)
            self.assertEqual(len(payload['records']),3);self.assertTrue(all(s['status']=='ok' for s in payload['sources']))
            self.assertEqual(r.validate_bundle(p,'7:1',COMMIT,datetime.fromisoformat(NOW)),payload)
            self.assertTrue(all(k['allow_redirects'] is False for _,k in net.calls))
    def test_failed_tour_keeps_bank_and_has_explicit_error(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);payload,_=self.bundle(p,Network(fail=URL))
            self.assertEqual(len(payload['records']),2);self.assertEqual(payload['sources'][0]['status'],'failed')
            self.assertEqual(r.validate_bundle(p,'7:1',COMMIT,datetime.fromisoformat(NOW)),payload)
    def test_tampered_record_and_binary_fail(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);payload,audit=self.bundle(p,Network());payload['records'][0]['title']='Fake'
            (p/'normalized.json').write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError,'re_reconstruction'):r.validate_bundle(p,'7:1',COMMIT,datetime.fromisoformat(NOW))
            receipt=next(x for x in audit['receipts'] if x['url']==PDF);(p/receipt['file']).write_bytes(b'%PDF-invalid')
            with self.assertRaisesRegex(ValueError,'re_file_hash'):r.validate_bundle(p,'7:1',COMMIT,datetime.fromisoformat(NOW))
    def test_rate_limit_no_retry(self):
        with tempfile.TemporaryDirectory() as d:
            net=lambda url,**k: Response(b'',429)
            reader=r.Reader(d,get=net,sleep=lambda _:None)
            with self.assertRaisesRegex(ValueError,'re_rate_limit'):reader.read(r.TOUR)
            self.assertEqual(len(reader.receipts),1)
    def test_wrong_mime_pdf_does_not_become_text(self):
        with tempfile.TemporaryDirectory() as d:
            reader=r.Reader(d,get=lambda u,**k:Response(b'<html>fake</html>'),sleep=lambda _:None)
            with self.assertRaisesRegex(ValueError,'re_not_pdf'):reader._get(PDF)
            self.assertFalse(any(Path(d).rglob('*.pdf')))
    def test_failed_policy_does_not_request_target(self):
        with tempfile.TemporaryDirectory() as d:
            net=Network(fail='https://rzdtour.com/robots.txt');reader=r.Reader(d,get=net,sleep=lambda _:None)
            with self.assertRaises(ValueError):reader.read(r.TOUR)
            self.assertEqual(len(net.calls),1)
    def test_changed_run_and_stale_evidence_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);self.bundle(p,Network())
            for run,stamp in [('8:1',NOW),('7:1','2026-09-19T12:00:00+00:00')]:
                with self.assertRaises(ValueError):r.validate_bundle(p,run,COMMIT,datetime.fromisoformat(stamp))

if __name__=='__main__':unittest.main()
