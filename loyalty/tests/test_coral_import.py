"""New current source inputs, typed Google errors, unchanged Coral terms/schema."""
import copy,json,sys,tempfile,unittest
from datetime import datetime,timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import coral_import_catalog as m
import coral_import_collect as c
import coral_catalog as coral
from test_coral_catalog import doc,product,promo,NOW,URL
from normalized import validate_offer,content_hash
from unittest.mock import patch


def obs(url,kind,raw):
    cells=[{'type':'string','value':s} for s in raw.splitlines() if s]
    return m.public_observation({'url':url,'kind':kind,'requested_at':NOW,'calculated_at':NOW,'cells':cells,
          'cells_sha256':m.digest(cells),'formula_sha256':m.digest(m.formula(url,kind))})


def root(sid):
    if sid=='coral':
        body='<h1>Клуб привилегий</h1><div class="category-box-menu"><h5><a href="'+coral.CLUB+'gifts/">Подарки</a></h5></div>'
    else:body='<h1>Акции</h1><div class="sale-item-description"><h5><a href="'+coral.PROMO+'future/">Бонусы нового путешествия</a></h5></div>'
    return doc(body,coral.CLUB if sid=='coral' else coral.PROMO)


class Source:
    cleanup_verified=True
    def __init__(self,fail=False):self.observations=[];self.fail=fail
    def read(self,url,kind):
        if kind=='robots':raw='User-agent: *\nDisallow: /api/customer\nSitemap: '+m.SITEMAP
        elif kind=='sitemap':raw='\n'.join([m.HOST+'/',coral.CLUB,coral.CLUB+'gifts/',URL])
        elif kind=='club_index':raw=root('coral')
        elif kind=='promo_index':raw=root('coral_promo')
        elif kind=='club_detail':raw=product()
        else:raw=promo()
        if self.fail and kind=='club_detail':
            self.observations.append({'url':url,'kind':kind,'requested_at':NOW,'calculated_at':NOW,'error':'coral_import_error_cell'})
            raise ValueError('coral_import_error_cell')
        o=obs(url,kind,raw);self.observations.append(o);return o


class MappingTests(unittest.TestCase):
    def test_changed_amount_date_and_native_identity_without_stored_answer(self):
        entry={'url':URL,'category':'Подарки','parent_url':coral.CLUB+'gifts/'}
        a=m.detail(obs(URL,'club_detail',product()),'coral',entry,NOW)
        b=m.detail(obs(URL,'club_detail',product('29','31.12.2026')),'coral',entry,NOW)
        self.assertEqual(a['id'],b['id']);self.assertNotEqual(a['content_sha256'],b['content_sha256'])
        self.assertEqual(b['rates'][0]['value'],'29');self.assertEqual(b['valid_until'],'2026-12-31')
        self.assertIn('авторизоваться',b['redemption_text']);self.assertIsNone(b['details']['retrieval']['origin_status']);validate_offer(b)
    def test_native_table_and_distinct_date_roles_still_retained(self):
        o=obs(coral.PROMO+'future/','promo_detail',promo())
        r=m.detail(o,'coral_promo',{'url':o['url'],'title':'Бонусы нового путешествия'},NOW)
        self.assertEqual(r['tables'][0][1],['Регион А','1234']);self.assertIn('Даты заказа',r['conditions_text']);self.assertIsNone(r['valid_until'])
    def test_forms_scripts_modal_content_not_in_public_artifact(self):
        o=obs(URL,'club_detail',product().replace('</body>','<script>SECRET_SESSION</script><form>SECRET_FORM</form></body>'))
        self.assertNotIn('SECRET',o['content']);self.assertNotIn('PRIVATE PLACEHOLDER',o['content'])
    def test_scope_checked_before_google_formula(self):
        for u in (URL+'?token=secret',m.HOST+'/api/customer',URL.replace('https:','http:'),m.HOST+'/api/promocode/1/get'):
            with self.assertRaises(ValueError):m.formula(u,'club_detail')
    def test_coerced_boolean_number_error_and_multi_cell_shape_rejected(self):
        for v in ({'numberValue':17},{'boolValue':True},{'errorValue':{'type':'N_A'}}):
            with self.assertRaises(ValueError):m.atom({'effectiveValue':v},0,'club_detail')
    def test_sitemap_follows_changed_urls_with_known_parent_not_hardcoded_membership(self):
        cat={coral.CLUB+'new-category/':'Новая категория'};u=coral.CLUB+'new-category/new-service/'
        entries,total=m.sitemap(obs(m.SITEMAP,'sitemap',u),cat)
        self.assertEqual(entries,[{'url':u,'category':'Новая категория','parent_url':coral.CLUB+'new-category/'}]);self.assertEqual(total,1)
        for raw in (u+'\n'+u,'https://other.example/item'):
            with self.assertRaises(ValueError):m.sitemap(obs(m.SITEMAP,'sitemap',raw),cat)
    def test_unadvertised_sitemap_and_disallow_stop(self):
        for raw in ('User-agent: *\nDisallow: /','User-agent: *\nDisallow: /klub-privilegii/\nSitemap: '+m.SITEMAP):
            with self.assertRaises(ValueError):m.policy(obs(m.ROBOTS,'robots',raw))
    def test_physically_identified_product_not_promoted_to_discount(self):
        raw=doc('<section><div><h1>Обычный товар</h1></div><div class="product-purchase-box">2000 рублей<button>В корзину</button></div></section>')
        self.assertTrue(m.physical_product(obs(URL,'club_detail',raw)))
        self.assertFalse(m.physical_product(obs(URL,'club_detail',product())))
    def test_sanitized_document_tamper_requires_binding(self):
        o=obs(URL,'club_detail',product());o['content']=o['content'].replace('17','29')
        with self.assertRaises(ValueError):m.validate_public(o)
    def test_source_canonical_must_match_before_sanitization(self):
        with self.assertRaises(Exception):obs(URL,'club_detail',product().replace('rel="canonical"','rel="other"'))


class WalkTests(unittest.TestCase):
    def test_both_scopes_and_sitemap_limit_not_full_program_claim(self):
        b=c.walk(Source(),'123:1',NOW)
        self.assertEqual(len(b['records']),2);self.assertEqual([s['status'] for s in b['sources']],['partial','ok'])
        self.assertFalse(json.loads(b['sources'][0]['coverage'])['full_program_catalog'])
        self.assertTrue(all(r['promo_codes']==[] for r in b['records']))
    def test_failed_detail_retains_other_source_without_freshening_old_row(self):
        b=c.walk(Source(True),'123:1',NOW)
        self.assertEqual(len(b['records']),1);self.assertEqual(b['records'][0]['source_id'],'coral_promo')
        self.assertEqual(b['sources'][0]['normalized'],0)
    def test_independent_replay_rejects_new_amount_or_missing_record(self):
        for fail in (False,True):
            r=Source(fail);b=c.walk(r,'123:1',NOW)
            a={'run_id':'123:1','commit':'a'*40,'cleanup_verified':True,'started_at':NOW,'finished_at':NOW,
               'source_accounts_used':False,'scrapingant_credits':0,'observations':r.observations}
            with tempfile.TemporaryDirectory() as d:
                p=Path(d);(p/'evidence.json').write_text(json.dumps(a));(p/'normalized.json').write_text(json.dumps(b))
                self.assertEqual(c.validate_bundle(p,run_id='123:1',commit='a'*40,clock=datetime.fromisoformat(NOW)),b)
                b['records'][0]['conditions_text']='FORGED';b['records'][0]['content_sha256']=content_hash(b['records'][0]);(p/'normalized.json').write_text(json.dumps(b))
                with self.assertRaises(ValueError):c.validate_bundle(p,run_id='123:1',commit='a'*40,clock=datetime.fromisoformat(NOW))
    def test_replay_bound_and_private_source_claim_rejected(self):
        r=Source();b=c.walk(r,'123:1',NOW)
        a={'run_id':'123:1','commit':'a'*40,'cleanup_verified':True,'started_at':NOW,'finished_at':NOW,
               'source_accounts_used':True,'scrapingant_credits':0,'observations':r.observations}
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'evidence.json').write_text(json.dumps(a));(p/'normalized.json').write_text(json.dumps(b))
            with self.assertRaises(ValueError):c.validate_bundle(p,run_id='123:1',commit='a'*40,clock=datetime.fromisoformat(NOW))
    def test_new_workflow_uses_existing_publication_without_provider_key(self):
        s=(Path(__file__).resolve().parents[2]/'.github/workflows/coral-import.yml').read_text()
        self.assertIn('47 9 * * 3,6',s);self.assertIn('sheets_normalized.py',s);self.assertIn('unified_publish.py',s)
        self.assertNotIn('SCRAPINGANT_API_KEY',s)


class Clock:
    def __init__(self):self.value=0
    def now(self):return self.value
    def sleep(self,n):self.value+=n


class MemorySheets:
    def __init__(self,wrong=False,tamper=False,wide=False,numeric=False):
        self.generation='idle';self.formula=None;self.wrong=wrong;self.tamper=tamper;self.wide=wide;self.numeric=numeric;self.calls=[]
    def request(self,method,suffix='',**kwargs):
        self.calls.append((method,suffix,kwargs))
        if method=='POST':
            for request in kwargs['json']['requests']:
                op=request['updateCells'];where=op.get('start',op.get('range'));assert where['sheetId']==c.SHEET_ID
                if 'range' in op:self.formula=None
                elif where['rowIndex']==0:self.generation=op['rows'][0]['values'][0]['userEnteredValue']['stringValue']
                else:self.formula=op['rows'][0]['values'][0]['userEnteredValue']['formulaValue']
            return {}
        if 'ranges' not in kwargs['params']:
            return {'spreadsheetId':'wrong' if self.wrong else c.STAGING_ID,'properties':{'importFunctionsExternalUrlAccessAllowed':True},
                    'sheets':[{'properties':{'sheetId':c.SHEET_ID,'title':c.SHEET,'gridProperties':{'rowCount':c.ROWS,'columnCount':4}}}]}
        rows=[{'values':[{'userEnteredValue':{'stringValue':c.MARKER}},{},{'userEnteredValue':{'stringValue':self.generation}}]}]
        if self.formula:
            cell={'userEnteredValue':{'formulaValue':'=BAD' if self.tamper else self.formula},
                  'effectiveValue':{'numberValue':17} if self.numeric else {'stringValue':product()}}
            rows.append({'values':[cell]+([{'effectiveValue':{'stringValue':'split'}}] if self.wide else [])})
        return {'spreadsheetId':c.STAGING_ID,'sheets':[{'properties':{'sheetId':c.SHEET_ID,'title':c.SHEET},'data':[{'rowData':rows}]}]}


class ReaderTests(unittest.TestCase):
    def test_real_clear_stable_read_and_public_sanitization(self):
        clock=Clock();client=MemorySheets();r=c.ImportReader('NO_KEY','123:1',client=client,clock=clock.now,sleep=clock.sleep)
        o=r.read(URL,'club_detail');self.assertTrue(r.cleanup_verified);self.assertIsNone(client.formula)
        self.assertNotIn('PRIVATE PLACEHOLDER',json.dumps(o));self.assertGreaterEqual(clock.value,2)
    def test_foreign_workspace_no_write_and_errors_always_clean(self):
        clock=Clock();client=MemorySheets(wrong=True)
        with self.assertRaises(ValueError):c.ImportReader('', '123:1',client=client,clock=clock.now,sleep=clock.sleep)
        self.assertTrue(all(x[0]=='GET' for x in client.calls))
        for kwargs in ({'wide':True},{'tamper':True},{'numeric':True}):
            client=MemorySheets(**kwargs);r=c.ImportReader('', '123:1',client=client,clock=clock.now,sleep=clock.sleep)
            with self.assertRaises(ValueError):r.read(URL,'club_detail')
            self.assertIsNone(client.formula);self.assertTrue(r.cleanup_verified)
            self.assertEqual(len(r.observations),1);self.assertIn('error',r.observations[0])

if __name__=='__main__':unittest.main()
