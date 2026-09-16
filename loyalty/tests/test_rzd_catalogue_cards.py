"""Real catalogue ownership, changed inputs, and failed-detail fallback."""
import copy,json,sys,unittest,tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import rzd_import_catalog as m
import rzd_import_collect as c
from test_rzd_import import NOW,observation,WalkTests,MemorySheets,Clock


def html(ident=71,rate=17,body='Условия только этого партнёра. Не суммируется с акциями.'):
    return f'''<html><h1>Партнеры</h1><script>private-session</script><div class="partners__frame">
    <div class="article__item" id="bx_222_{ident}"><a href="/promo/offer-{ident}/"><img alt="" src="/logo.png"></a>
    <div class="desc"><p>Отели</p><p class="bonuse">Скидка {rate}% в отеле Пример</p>
    <span class="more__inf">{body}</span></div></div></div></html>'''

class Tests(unittest.TestCase):
    def module(self):
        import rzd_catalogue_cards as a
        return a
    def source(self,raw=None):
        a=self.module();return observation(m.ROOT,'catalog_cards',[a.sanitize(raw or html())])
    def test_changed_identity_rate_and_own_source_text(self):
        a=self.module();o=self.source();p=a.previews(o)
        r=a.make_preview(p[m.HOME+'promo/offer-71/'],NOW,'rzd_import_error_cell')
        n=self.source(html(932,29));r2=a.make_preview(a.previews(n)[m.HOME+'promo/offer-932/'],NOW,'rzd_import_error_cell')
        self.assertNotEqual(r['id'],r2['id']);self.assertIn('29%',r2['conditions_text'])
        self.assertEqual(r['record_kind'],'source_observation');self.assertFalse(r['benefit_text']);self.assertFalse(r['rates'])
        self.assertNotIn('private-session',json.dumps(o));m.validate_record(r2)
    def test_neighbor_card_never_becomes_this_cards_conditions(self):
        a=self.module();raw=html()+html(72,93,body='Только другой партнер')
        o=self.source(raw);p=a.previews(o)
        self.assertNotIn('93%',p[m.HOME+'promo/offer-71/']['card']['conditions'])
        self.assertNotIn('другой',p[m.HOME+'promo/offer-71/']['card']['conditions'])
    def test_duplicate_target_conflict_is_not_silently_chosen(self):
        a=self.module()
        with self.assertRaises(ValueError):a.previews(self.source(html()+html(71,99)))
    def test_catalogue_result_uses_current_links_and_pagination(self):
        o=self.source(html().replace('</div></html>','<a href="/partners/?PAGEN_3=2">2</a></div></html>'))
        p=m.catalog(o);self.assertEqual(p['details'],[m.HOME+'promo/offer-71/'])
        self.assertEqual(p['pages'],[m.ROOT+'?PAGEN_3=2'])
    def test_form_script_and_external_card_are_not_archived(self):
        a=self.module();raw=html(body='<form><input value="secret">private-form</form>Публичные условия и текст.')
        s=a.sanitize(raw);self.assertNotIn('secret',s);self.assertNotIn('private-form',s)
        with self.assertRaises(ValueError):a.previews(self.source(html().replace('/promo/offer-71/','https://evil.test/promo/offer-71/')))
    def test_record_rehash_cannot_promote_preview_to_detail(self):
        a=self.module();r=a.make_preview(next(iter(a.previews(self.source()).values())),NOW,'rzd_detail_empty_or_bound')
        from normalized import content_hash
        for key,value in [('record_kind','partner_offer'),('conditions_text','Придуманные условия'),('source_status','public_google_import_text')]:
            changed=copy.deepcopy(r);changed[key]=value;changed['content_sha256']=content_hash(changed)
            with self.assertRaises(ValueError):m.validate_record(changed)
    def test_actual_walk_keeps_failed_detail_preview_and_coverage_partial(self):
        a=self.module()
        class Reader:
            cleanup_verified=True
            def __init__(self):self.observations=[]
            def read(self,url,kind):
                if kind=='robots':o=observation(url,kind,['User-agent: *','Crawl-delay: 20'])
                elif kind=='home':o=observation(url,kind,['РЖД Бонус','/partners/'])
                elif kind=='catalog_cards':o=observation(url,kind,[a.sanitize(html())])
                else:raise ValueError('rzd_import_error_cell')
                self.observations.append(o);return o
        reader=Reader()
        with patch.object(c,'policy_from',return_value=WalkTests.Policy()):
            b=c.walk(reader,'123:1','a'*40,NOW,include_previews=True)
            self.assertEqual(len(b['records']),1);self.assertEqual(b['sources'][0]['status'],'partial')
            scope=json.loads(b['sources'][0]['coverage']);self.assertEqual(scope['accepted_detail_records'],0)
            self.assertEqual(scope['accepted_catalogue_previews'],1);self.assertFalse(scope['all_discovered_details_read'])
            audit={'run_id':'123:1','commit':'a'*40,'started_at':NOW,'finished_at':NOW,'cleanup_verified':True,
                'source_accounts_used':False,'scrapingant_credits':0,'observations':reader.observations,'include_previews':True}
            with tempfile.TemporaryDirectory() as temp:
                p=Path(temp);(p/'normalized.json').write_text(json.dumps(b));(p/'evidence.json').write_text(json.dumps(audit))
                self.assertEqual(c.validate_bundle(p,run_id='123:1',commit='a'*40,clock=datetime.fromisoformat(NOW)),b)
                b['records'][0]['conditions_text']='forged';(p/'normalized.json').write_text(json.dumps(b))
                with self.assertRaises(ValueError):c.validate_bundle(p,run_id='123:1',commit='a'*40,clock=datetime.fromisoformat(NOW))
    def test_normalization_remains_evidence_only(self):
        a=self.module();r=a.make_preview(next(iter(a.previews(self.source()).values())),NOW,'rzd_import_error_cell')
        from unified_normalization import normalize_record
        # Real native publisher row and input adapter, not a fake summary.
        from sheets_normalized import prepare,SCHEMAS
        from unified_inputs import inputs_from_tables,HEADERS
        from unified_normalization import INPUT_TABS
        tables={k:[[]]*(v[0]-1)+[[{'value':x} for x in HEADERS[k]]] for k,v in INPUT_TABS.items()}
        report={'source_id':'rzd','name':'RZD','root':m.ORIGINAL,'status':'partial','discovered':1,'normalized':1,'failed':1,'errors':[],'coverage':'preview','region':None,'observed_at':NOW}
        cells=prepare({'schema_version':2,'run_id':'123:1','observed_at':NOW,'records':[r],'sources':[report]})['parser_offers'][0]
        tables['parser_offers'].append([{'value':x} for x in cells]);raw,_=inputs_from_tables(tables)
        out=normalize_record(raw[0],as_of='2026-09-16');self.assertFalse(out['benefits']);self.assertFalse(out['codes'])
        self.assertEqual(out['quality']['level'],'evidence_only')


    def test_sanitization_is_idempotent_for_removed_media_and_forms(self):
        a=self.module();raw=html(body='<img src="/x"><br><form><input name="session" value="secret"></form>Публичный текст')
        first=a.sanitize(raw);self.assertEqual(a.sanitize(first),first)
        self.assertNotIn('secret',first);self.assertNotIn('img',first)
    def test_cross_page_conflict_fails_but_dom_prefix_change_does_not(self):
        a=self.module();entries=a.previews(self.source());other=a.previews(self.source(html().replace('bx_222_','bx_333_')))
        a.merge_previews(entries,other)
        with self.assertRaisesRegex(ValueError,'conflicting_versions'):
            a.merge_previews(entries,a.previews(self.source(html(rate=91))))
    def test_real_reader_archives_only_sanitized_owned_html_and_cleans(self):
        a=self.module()
        class HtmlSheets(MemorySheets):
            def request(self,method,suffix='',**kwargs):
                result=super().request(method,suffix,**kwargs)
                if method=='GET' and 'ranges' in kwargs['params'] and self.current:
                    block=result['sheets'][0]['data'][0]['rowData']
                    block[1:]=[{'values':[{'userEnteredValue':{'formulaValue':self.current},'effectiveValue':{'stringValue':html()}}]}]
                return result
        clock=Clock();client=HtmlSheets();reader=c.ImportReader('PRIVATE', '123:1',client=client,clock=clock.now,sleep=clock.sleep)
        o=reader.read(m.ROOT,'catalog_cards');self.assertEqual(o['cells'][0]['text'],a.sanitize(html()))
        self.assertEqual(len(reader.observations),1);self.assertIsNone(client.current);self.assertTrue(reader.cleanup_verified)
        self.assertNotIn('private-session',json.dumps(o));self.assertEqual(len(m.catalog(o)['details']),1)
    def test_complete_detail_does_not_create_duplicate_preview(self):
        a=self.module()
        class Reader:
            cleanup_verified=True
            def read(self,url,kind):
                if kind=='robots':return observation(url,kind,['User-agent: *'])
                if kind=='home':return observation(url,kind,['РЖД Бонус','/partners/'])
                if kind=='catalog_cards':return observation(url,kind,[a.sanitize(html())])
                return observation(url,kind,['Партнер Пример','Скидка 17% для участников РЖД Бонус. Не суммируется с другими акциями.'])
        with patch.object(c,'policy_from',return_value=WalkTests.Policy()):b=c.walk(Reader(),'123:1','a'*40,NOW,include_previews=True)
        self.assertEqual(len(b['records']),1);self.assertEqual(b['sources'][0]['status'],'ok')
        self.assertEqual(b['records'][0]['native_id'],'/promo/offer-71/')
        self.assertEqual(json.loads(b['sources'][0]['coverage'])['accepted_catalogue_previews'],0)
    def test_rotating_detail_subset_reconstructs_in_actual_attempt_order(self):
        a=self.module()
        class Reader:
            cleanup_verified=True
            def __init__(self):self.observations=[]
            def read(self,url,kind):
                if kind=='robots':o=observation(url,kind,['User-agent: *'])
                elif kind=='home':o=observation(url,kind,['РЖД Бонус','/partners/'])
                elif kind=='catalog_cards':o=observation(url,kind,[a.sanitize(''.join(html(i) for i in range(71,74)))])
                else:raise ValueError('rzd_import_error_cell')
                self.observations.append(o);return o
        reader=Reader()
        with patch.object(c,'policy_from',return_value=WalkTests.Policy()),patch.object(c,'MAX_DETAILS',2):
            b=c.walk(reader,'123:1','a'*40,NOW,include_previews=True)
            self.assertEqual(len(b['records']),2);self.assertEqual(b['sources'][0]['discovered'],3)
            audit={'run_id':'123:1','commit':'a'*40,'started_at':NOW,'finished_at':NOW,'cleanup_verified':True,
                'source_accounts_used':False,'scrapingant_credits':0,'observations':reader.observations,'include_previews':True}
            with tempfile.TemporaryDirectory() as temp:
                p=Path(temp);(p/'normalized.json').write_text(json.dumps(b));(p/'evidence.json').write_text(json.dumps(audit))
                self.assertEqual(c.validate_bundle(p,run_id='123:1',commit='a'*40,clock=datetime.fromisoformat(NOW)),b)
    def test_policy_denial_is_not_replaced_with_preview(self):
        a=self.module()
        class Policy(WalkTests.Policy):
            def can_fetch(self,url,agent):return '/promo/' not in url
        class Reader:
            def read(self,url,kind):
                if kind=='robots':return observation(url,kind,['User-agent: *'])
                if kind=='home':return observation(url,kind,['РЖД Бонус','/partners/'])
                if kind=='catalog_cards':return observation(url,kind,[a.sanitize(html())])
                raise AssertionError('Denied target requested')
        with patch.object(c,'policy_from',return_value=Policy()):b=c.walk(Reader(),'123:1','a'*40,NOW,include_previews=True)
        self.assertFalse(b['records']);self.assertEqual(b['sources'][0]['errors'][0]['reason'],'rzd_policy_disallow')

if __name__=='__main__':unittest.main()
