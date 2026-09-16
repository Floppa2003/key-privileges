"""Fresh parent links -> own rule article -> separate, non-promotional evidence."""
import copy,json,sys,tempfile,unittest
from datetime import datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import coral_import as g
import coral_linked_rules as rules
import test_coral_import as f
from normalized import content_hash,validate_offer
from unified_normalization import make_input,normalize_record
from sheets_normalized import prepare,SCHEMAS

RULE='https://coralbonus.ru/pravila-novogo-servisa/'

def article(url=RULE,body=None):
    return f.html(url,'<header>Не принадлежащая правилам скидка 90%</header><section class="article"><div><h1>Правила нового сервиса</h1><p>'+(body or 'Заявка принимается за 7 дней. Возвращается 100% оплаты. Пример: скидка 90% не применяется к данной услуге.')+'</p></div></section><footer>Чужие условия</footer>')

def parent(url=f.URL,link=RULE):
    raw=f.page(url).replace('</p>','</p><a href="'+link+'">Правила услуги</a>',1)
    return g.map_detail(f.obs(url,raw),'coral',{'url':url,'category':'Для детей','parent_url':f.CATEGORY},f.NOW)

class LinkedSource(f.Source):
    def __init__(self,fail=False,count=1):super().__init__();self.fail_rule=fail;self.calls=[];self.count=count
    def read(self,url):
        self.calls.append(url)
        if url==f.URL:
            links=''.join('<a href="https://coralbonus.ru/pravila-service-'+str(i)+'/">Правила '+str(i)+'</a>' for i in range(self.count))
            raw=f.page().replace('</p>','</p>'+links,1)
        elif rules.is_rule_url(url):
            if self.fail_rule:raise ValueError('cg_import_timeout_or_error')
            raw=article(url)
        else:return super().read(url)
        o=f.obs(url,raw);self.observations.append(o);return o

class Mapping(unittest.TestCase):
    def test_changed_source_links_not_fixed_inventory(self):
        a=rules.discover([parent()]);other=RULE.replace('novogo','drugogo')
        b=rules.discover([parent(link=other)])
        self.assertEqual(a[0]['url'],RULE);self.assertEqual(b[0]['url'],other)
        self.assertNotEqual(a,b)
    def test_same_document_once_with_two_own_parent_references(self):
        parents=[parent(),parent(url=f.CATEGORY+'second/')]
        entries=rules.discover(parents)
        self.assertEqual(len(entries),1);self.assertEqual(len(entries[0]['parents']),2)
        self.assertEqual({p['record_id'] for p in entries[0]['parents']},{p['id'] for p in parents})
    def test_foreign_account_query_fragment_and_traversal_not_discovered(self):
        for url in ('https://foreign.example/pravila-service/','http://coralbonus.ru/pravila-service/',
                    RULE+'?token=private',RULE+'#x','https://coralbonus.ru/account/',
                    'https://coralbonus.ru/pravila-../','https://coralbonus.ru/pravila-%2f/',
                    'https://coralbonus.ru/pravila-a/b/'):
            with self.subTest(url=url):self.assertFalse(rules.is_rule_url(url))
    def test_rule_text_and_amount_change_stable_identity(self):
        entry=rules.discover([parent()])[0]
        a=rules.map_rule(f.obs(RULE,article()),entry,f.NOW)
        b=rules.map_rule(f.obs(RULE,article(body='Заявка принимается за 11 дней. Поздняя отмена не допускается. Правила услуги указаны в полном объеме.')),entry,f.NOW)
        self.assertEqual(a['id'],b['id']);self.assertNotEqual(a['content_sha256'],b['content_sha256'])
        self.assertIn('11 дней',b['conditions_text']);self.assertNotIn('Чужие условия',b['conditions_text'])
        self.assertNotIn('Не принадлежащая',b['conditions_text']);self.assertFalse(a['rates']);self.assertFalse(a['benefit_text'])
    def test_wrong_canonical_login_ambiguous_and_oversized_fail(self):
        entry=rules.discover([parent()])[0]
        cases=[article().replace('href="'+RULE,'href="'+RULE+'other/'),
               article().replace('Правила нового сервиса','Вход в личный кабинет'),
               article().replace('</section>','<h1>Второй заголовок</h1></section>'),
               article(body='Правила '+('условие '*5000))]
        for raw in cases:
            with self.subTest(size=len(raw)),self.assertRaises((ValueError,RuntimeError)):
                rules.map_rule(f.obs(RULE,raw),entry,f.NOW)
    def test_rehashed_wrong_parent_or_conditions_fail_record_validation(self):
        record=rules.map_rule(f.obs(RULE,article()),rules.discover([parent()])[0],f.NOW)
        for change in ('body','parent','kind','method'):
            r=copy.deepcopy(record)
            if change=='body':r['conditions_text']='Иные условия'
            elif change=='parent':r['details']['parent_references'][0]['source_url']='https://foreign.example/'
            elif change=='kind':r['record_kind']='partner_offer'
            else:r['details']['full_eligibility_verified']=True
            r['content_sha256']=content_hash(r)
            with self.subTest(change=change),self.assertRaises(ValueError):validate_offer(r)
    def test_shared_text_preserves_table_cells_but_no_table_reward_inference(self):
        raw=article().replace('</section>','<table><tr><th>Срок</th><th>Возврат</th></tr><tr><td>7 дней</td><td>100%</td></tr></table></section>')
        row=rules.map_rule(f.obs(RULE,raw),rules.discover([parent()])[0],f.NOW)
        self.assertEqual(row['details']['public_rule']['tables'][0][1],['7 дней','100%'])
        self.assertFalse(row['tables']);self.assertFalse(row['rates'])
    def test_common_view_is_condition_only_not_discount_or_code(self):
        record=rules.map_rule(f.obs(RULE,article()),rules.discover([parent()])[0],f.NOW)
        values=prepare({'schema_version':2,'run_id':'1:1','observed_at':f.NOW,'records':[record],'sources':[{'source_id':rules.SOURCE_ID,'name':'Правила','root':g.c.CLUB,'status':'ok','discovered':1,'normalized':1,'failed':0,'coverage':'test','region':None,'errors':[],'observed_at':f.NOW}]})['parser_offers'][0]
        raw=make_input({'id':record['id'],'origin':'parser_offers','row':2,'fields':{k:{'value':v} for k,v in zip(SCHEMAS['parser_offers'],values)}})
        n=normalize_record(raw,as_of='2026-09-16')
        self.assertFalse(n['benefits']);self.assertFalse(n['costs']);self.assertFalse(n['codes'])
        self.assertEqual(len(n['conditions']),1);self.assertEqual(n['conditions'][0]['evidence']['text'],record['conditions_text'])
        self.assertFalse(n['conditions'][0]['standalone_offer'])

class Walk(unittest.TestCase):
    def bundle(self,source):
        b=g.collect(source,'1:1',f.NOW)
        a={'run_id':'1:1','commit':'a'*40,'started_at':f.NOW,'finished_at':f.NOW,'cleanup_verified':True,'scrapingant_credits':0,'source_account_used':False,'observations':source.observations}
        return b,a
    def validate(self,b,a):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'normalized.json').write_text(json.dumps(b));(p/'evidence.json').write_text(json.dumps(a))
            return g.validate_bundle(p,'1:1','a'*40,datetime.fromisoformat(f.NOW))
    def test_full_real_collector_and_publisher_reconstruction(self):
        source=LinkedSource();b,a=self.bundle(source)
        self.assertEqual(len(b['records']),3);self.assertEqual(b['sources'][2]['source_id'],rules.SOURCE_ID)
        self.assertEqual(len([u for u in source.calls if rules.is_rule_url(u)]),1)
        self.assertEqual(self.validate(b,a),b)
    def test_failed_rule_does_not_lose_parent_or_claim_full_conditions(self):
        b,a=self.bundle(LinkedSource(fail=True));self.assertEqual(len(b['records']),2)
        self.assertEqual(b['sources'][2]['failed'],1);self.assertEqual(b['sources'][2]['normalized'],0)
        self.assertEqual(self.validate(b,a),b)
    def test_extra_unlinked_observation_rejected(self):
        b,a=self.bundle(LinkedSource());a['observations'].append(f.obs(RULE,article()))
        with self.assertRaises(ValueError):self.validate(b,a)
    def test_parent_link_mismatch_after_rehash_rejected(self):
        b,a=self.bundle(LinkedSource());r=b['records'][-1];r['details']['parent_references'][0]['label']='Чужая ссылка';r['content_sha256']=content_hash(r)
        with self.assertRaises(ValueError):self.validate(b,a)
    def test_rule_bound_does_not_expand_import_budget(self):
        source=LinkedSource(count=rules.MAX_RULES+2);b,a=self.bundle(source)
        self.assertEqual(len([u for u in source.calls if rules.is_rule_url(u)]),rules.MAX_RULES)
        self.assertEqual(b['sources'][2]['discovered'],rules.MAX_RULES+2)
        self.assertEqual(b['sources'][2]['status'],'partial');self.assertEqual(self.validate(b,a),b)
    def test_rule_source_cannot_be_omitted_from_bundle(self):
        b,a=self.bundle(LinkedSource());b['sources'].pop();b['records'].pop()
        with self.assertRaises(ValueError):self.validate(b,a)
    def test_rules_not_requested_when_parent_fails(self):
        class FailedParent(LinkedSource):
            def read(self,url):
                if url==f.URL:raise ValueError('cg_import_timeout_or_error')
                return super().read(url)
        source=FailedParent();b,a=self.bundle(source)
        self.assertFalse(any(rules.is_rule_url(u) for u in source.calls));self.assertEqual(len(b['sources']),2)
        self.assertEqual(self.validate(b,a),b)

if __name__=='__main__':unittest.main()
