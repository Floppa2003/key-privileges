"""Source-bound external RZD conditions, not a blanket discount for all tours."""
import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
import rzd_external as e
from sheets_normalized import prepare

NOW='2026-09-17T12:00:00+00:00'
URL=e.TOUR+'kruiznyie-turyi/kruiznyie-poezda/new-tour'

def tour(rate='7',title='New tour',extra=''):
    return '<html><head><title>Tour</title></head><body><h1 class="name">'+title+'</h1><div class="modal-main content-price"><div class="text-content-route"><p>Даты: 01.10.2026</p><table><tr><th>Категория</th><th>Цена</th></tr><tr><td>Купе</td><td>12345</td></tr></table><p>Участникам программы «РЖД Бонус» предоставляется скидка '+rate+'% при оформлении заявки с номером карты. Скидки не суммируются.</p>'+extra+'</div></div><footer>РЖД Бонус скидка 99%</footer></body></html>'

def bank(name='NewRules.pdf'):
    return '<html><head><title>CASH&amp;BACK</title></head><body><div class="parsys"><p>CASH&amp;BACK bank product</p><table class="downloadlist"><tr><td>Правила обслуживания карт с возможностью выплаты вознаграждения</td><td><a href="/content/dam/rewards/'+name+'">Скачать</a></td></tr><tr><td>Cookie policy</td><td><a href="/content/dam/cookie.pdf">Скачать</a></td></tr></table></div></body></html>'

class Mapping(unittest.TestCase):
    def test_changed_tour_values_stay_owned(self):
        for rate in ('3','7.5'):
            rows=e.tour_records(e.sanitize_html(tour(rate)),URL,NOW,{'sha256':'a'*64},[e.TOUR])
            self.assertEqual(len(rows),1);r=rows[0]
            self.assertEqual(r['rates'][0]['value'],rate)
            self.assertNotIn('99%',r['conditions_text']);self.assertIn('Купе | 12345',r['conditions_text'])
            self.assertIn('01.10.2026',r['conditions_text']);self.assertIsNone(r['valid_until'])
            self.assertEqual(r['details']['tour_url'],URL)
    def test_neighbor_footer_does_not_supply_loyalty(self):
        raw=tour().replace('РЖД Бонус','Other programme',1)
        self.assertEqual(e.tour_records(e.sanitize_html(raw),URL,NOW,{},[]),[])
    def test_missing_price_block_is_not_a_confirmed_absence(self):
        with self.assertRaisesRegex(ValueError,'rx_tour_layout'):
            e.tour_records(e.sanitize_html('<html><h1 class="name">Tour</h1></html>'),URL,NOW,{},[])
    def test_same_title_different_urls_different_ids(self):
        a=e.tour_records(e.sanitize_html(tour()),URL,NOW,{},[])
        b=e.tour_records(e.sanitize_html(tour()),URL+'-two',NOW,{},[])
        self.assertNotEqual(a[0]['id'],b[0]['id'])
    def test_changed_title_same_url_stable_id(self):
        a=e.tour_records(e.sanitize_html(tour()),URL,NOW,{},[])
        b=e.tour_records(e.sanitize_html(tour(title='Changed')),URL,NOW,{},[])
        self.assertEqual(a[0]['id'],b[0]['id']);self.assertNotEqual(a[0]['content_sha256'],b[0]['content_sha256'])
    def test_long_conditions_split_without_discarding_text(self):
        rows=e.tour_records(e.sanitize_html(tour(extra='<p>'+('Long rule. '*4000)+'</p>')),URL,NOW,{},[])
        self.assertGreater(len(rows),1)
        self.assertEqual(sum(r['record_kind']=='partner_offer' for r in rows),1)
        self.assertEqual(''.join(r['details']['condition_fragment'] for r in rows).count('Long rule.'),4000)
        prepare({'schema_version':2,'run_id':'1:1','observed_at':NOW,'records':rows,'sources':[e.report('rzd_tour_terms',len(rows),rows,[],{},NOW)]})
    def test_pdf_discovery_uses_rule_row_not_old_filename(self):
        result=e.bank_links(e.sanitize_html(bank('changed.pdf')))
        self.assertEqual(len(result),1);self.assertTrue(result[0]['url'].endswith('changed.pdf'))
    def test_bank_external_links_are_not_followed(self):
        raw=bank().replace('/content/dam/rewards/NewRules.pdf','https://other.example/rules.pdf')
        self.assertEqual(e.bank_links(e.sanitize_html(raw)),[])
    def test_tour_discovery_uses_sitemap_and_source_cards(self):
        xml='<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+u+'</loc></url>' for u in [URL,e.TOUR+'review',e.TOUR+'kruiznyie-turyi/kruiznyie-poezda/'])+'</urlset>'
        html='<html><div class="card"><a href="/root-tour">Details</a></div></html>'
        targets=e.tour_targets(xml,html)
        self.assertEqual(set(targets),{URL,e.TOUR+'root-tour'})
    def test_xml_entities_and_traversal_rejected(self):
        with self.assertRaises(ValueError):e.tour_targets('<!DOCTYPE x><urlset/>','')
        for url in ('http://rzdtour.com/','https://rzdtour.com.evil/a','https://rzdtour.com/%2e%2e/auth','https://rzdtour.com/a?token=x','https://rzdtour.com/a%252fb'):
            with self.subTest(url=url),self.assertRaises(ValueError):e.checked_url(url)
    def test_private_forms_removed_and_no_script_execution(self):
        safe=e.sanitize_html(tour()+'<form><input value="PRIVATE"/></form><script>SECRET</script>')
        self.assertNotIn('PRIVATE',safe);self.assertNotIn('SECRET',safe)
    def test_bank_product_is_not_an_rzd_exchange_benefit(self):
        r=e.bank_record(e.sanitize_html(bank()),NOW,{'sha256':'a'*64})
        self.assertEqual(r['benefit_text'],'');self.assertEqual(r['record_kind'],'source_observation')
        self.assertFalse(r['details']['rzd_exchange_verified'])

if __name__=='__main__':unittest.main()

class Response:
    def __init__(self,url,body,status=200,mime='text/html',headers=None):
        self.url=url;self.body=body.encode() if isinstance(body,str) else body;self.status_code=status
        self.headers={'Content-Type':mime,**(headers or {})}
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def iter_content(self,size):yield self.body

class Network:
    def __init__(self,root):self.root=root;self.calls=[]
    def get(self,url,**kwargs):
        self.calls.append((url,kwargs))
        if url.endswith('/robots.txt'):
            return Response(url,'User-agent: *\nAllow: /\nSitemap: '+e.TOUR+'sitemap.xml',mime='text/plain')
        if url==e.TOUR:return Response(url,'<html><div class="card"><a href="'+URL+'">Tour</a></div></html>')
        if url==e.TOUR+'sitemap.xml':
            return Response(url,'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>'+URL+'</loc></url></urlset>',mime='application/xml')
        if url==URL:return Response(url,tour())
        if url==e.BANK:return Response(url,bank())
        from test_document_text import pdf
        return Response(url,pdf(['Terms of bank reward program. No source eligibility inference.']),mime='application/pdf')

class Integration(unittest.TestCase):
    def test_network_collector_prepares_real_pdf_and_no_credentials(self):
        with tempfile.TemporaryDirectory() as d:
            net=Network(d);reader=e.Reader(d,get=net.get,sleep=lambda _:None)
            bundle=e.collect(reader,'1:1',NOW)
            self.assertEqual(len(bundle['records']),3)
            self.assertEqual([s['status'] for s in bundle['sources']],['ok','ok','ok'])
            self.assertEqual(len(net.calls),7)
            self.assertTrue(all(k['allow_redirects'] is False for _,k in net.calls))
            self.assertTrue(all('cookies' not in k and 'auth' not in k for _,k in net.calls))
            prepare(bundle)
    def test_actual_rates_only_project_on_matching_tour(self):
        from unified_inputs import inputs_from_tables, HEADERS
        from unified_normalization import INPUT_TABS,normalize_inputs
        with tempfile.TemporaryDirectory() as d:
            net=Network(d);bundle=e.collect(e.Reader(d,get=net.get,sleep=lambda _:None),'1:1',NOW)
            rows=prepare(bundle)['parser_offers']
            tables={name:[[]]*(header-1)+[[{'value':s} for s in HEADERS[name]]] for name,(header,width) in INPUT_TABS.items()}
            tables['parser_offers'] += [[{'value':v} for v in row]+[{}] for row in rows]
            raw,_=inputs_from_tables(tables);result=normalize_inputs(raw,as_of='2026-09-17')
            for record in result['records']:
                self.assertEqual(len(record['benefits']),1 if record['partner']['name']=='РЖД Тур' else 0)
                self.assertEqual(len(record['codes']),0)
    def test_429_or_retry_after_is_terminal(self):
        for response in (Response(e.TOUR+'robots.txt','',429),Response(e.TOUR+'robots.txt','',headers={'Retry-After':'5'})):
            with tempfile.TemporaryDirectory() as d:
                reader=e.Reader(d,get=lambda *a,**k:response,sleep=lambda _:None)
                with self.assertRaisesRegex(ValueError,'rx_rate_limit'):reader.read(e.TOUR+'robots.txt','robots')
                with self.assertRaisesRegex(ValueError,'rx_host_halted'):reader.read(e.TOUR+'robots.txt','robots')
                self.assertEqual(len(reader.requests),1)
    def test_http_200_html_is_never_a_pdf(self):
        with tempfile.TemporaryDirectory() as d:
            net=Network(d);reader=e.Reader(d,get=net.get,sleep=lambda _:None)
            reader.read('https://www.unicreditbank.ru/robots.txt','robots')
            reader.get=lambda url,**k:Response(url,'<html>not a PDF</html>')
            with self.assertRaisesRegex(ValueError,'rx_not_pdf'):reader.read('https://www.unicreditbank.ru/content/dam/new.pdf','pdf')
            self.assertFalse(list(Path(d).glob('*.pdf')))
    def test_sanitized_bank_download_survives_no_browser_marker(self):
        with tempfile.TemporaryDirectory() as d:
            net=Network(d);reader=e.Reader(d,get=net.get,sleep=lambda _:None)
            reader.read('https://www.unicreditbank.ru/robots.txt','robots')
            data,_=reader.read(e.BANK,'html')
            self.assertEqual(len(e.bank_links(data.decode())),1)

class Reconstruction(unittest.TestCase):
    def produce(self,d,status=None):
        from datetime import timedelta
        from unittest.mock import patch
        clock=[0.0]
        def sleep(v):clock[0]+=v
        def now():return (datetime.fromisoformat(NOW)+timedelta(seconds=clock[0])).isoformat()
        network=Network(d)
        original=network.get
        if status:
            network.get=lambda url,**kw:Response(url,'failed',status=status) if url==URL else original(url,**kw)
        reader=e.Reader(d,get=network.get,sleep=sleep,clock=lambda:clock[0])
        with patch.object(e,'now',now):bundle=e.collect(reader,'1:1',NOW)
        audit={'run_id':'1:1','commit':'a'*40,'started_at':NOW,'finished_at':now(),'tour_limit':e.MAX_TOURS,
               'accounts_used':False,'provider_credits':0,'requests':reader.requests}
        root=Path(d);(root/'report.json').write_text(json.dumps(audit));(root/'normalized.json').write_text(json.dumps(bundle))
        return bundle,datetime.fromisoformat(now())+timedelta(seconds=1)
    def test_full_reconstruction_and_result_tampering(self):
        with tempfile.TemporaryDirectory() as d:
            bundle,clock=self.produce(d)
            self.assertEqual(e.validate_bundle(d,run_id='1:1',commit='a'*40,clock=clock),bundle)
            bundle['records'][0]['conditions_text']='Changed'
            (Path(d)/'normalized.json').write_text(json.dumps(bundle))
            with self.assertRaises(ValueError):e.validate_bundle(d,run_id='1:1',commit='a'*40,clock=clock)
    def test_partial_403_reconstructs_without_fabricated_tour(self):
        with tempfile.TemporaryDirectory() as d:
            bundle,clock=self.produce(d,status=403)
            self.assertEqual(bundle['sources'][0]['status'],'failed')
            self.assertEqual(len(bundle['records']),2)
            self.assertEqual(e.validate_bundle(d,run_id='1:1',commit='a'*40,clock=clock),bundle)
    def test_reconstruction_rejects_file_hash_change(self):
        with tempfile.TemporaryDirectory() as d:
            _,clock=self.produce(d)
            target=next(Path(d).glob('*.pdf'));target.write_bytes(target.read_bytes()+b'BAD')
            with self.assertRaisesRegex(ValueError,'rx_receipt_hash'):e.validate_bundle(d,run_id='1:1',commit='a'*40,clock=clock)
