"""Public DOM replay and negative canaries; tests do not access source accounts."""
import copy,json,sys,unittest
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0,str(Path(__file__).parents[1]))
import backit_source as b
import avolta_source as a
import mantera_source as m
from normalized import validate_offer,content_hash
from sheets_normalized import prepare,SCHEMAS
from unified_normalization import make_input,normalize_record
from catalogue_view import record_row
FIX=Path(__file__).parent/'fixtures_live/affordable'
NOW='2026-09-22T10:42:11+00:00'
def html(name):return (FIX/name).read_text()
def kuper(raw=None):return b.parse_detail(raw or html('backit-kuper.html'),{'url':b.ROOT+'/kuper','name':'Купер (бывший СберМаркет)'},NOW)
def plaza(raw=None):return a.parse_detail(raw or html('avolta-plaza.html'),{'url':a.PREFIX+'zaly-ozhidaniya/plaza','name':'Plaza','category':'Залы ожидания'},NOW)
def common(row):
    report=dict(source_id=row['source_id'],name=row['program'],root=row['source_url'],status='ok',normalized=1,discovered=1,failed=0,coverage='fixture',errors=[],region=None,observed_at=NOW)
    values=prepare(dict(schema_version=2,run_id='fixture:1',observed_at=NOW,records=[row],sources=[report]))['parser_offers'][0]
    raw=make_input(dict(id=row['id'],origin='parser_offers',row=2,fields={h:{'value':v} for h,v in zip(SCHEMAS['parser_offers'],values)}))
    return normalize_record(raw,as_of=NOW[:10])

class PublicRewardTests(unittest.TestCase):
    def test_backit_inventory_exact_size_and_page(self):
        cards,total,size=b.inventory(html('backit-list.html'),2)
        self.assertEqual((len(cards),total,size),(40,916,40))
        with self.assertRaises(ValueError):b.inventory(html('backit-list.html'),1)
    def test_backit_missing_card_is_not_complete(self):
        s=BeautifulSoup(html('backit-list.html'),'html.parser');s.select_one('a.mu-store__wrapper').decompose()
        with self.assertRaises(ValueError):b.inventory(str(s),2)
    def test_foreign_or_unreviewed_urls_rejected(self):
        for url in ['https://evil.test/ru/cashback/shops/kuper',b.ROOT+'/kuper?token=x',b.ROOT+'/category/1']:
            with self.assertRaises(ValueError):b.card_url(url)
        with self.assertRaises(ValueError):a.reviewed_url('https://evil.test/ru/nashi-partnery/oteli/a')
    def test_financial_ads_not_shopping(self):
        for name in ['Сбербанк — вклад','Кредитная карта','Яндекс Браузер']:self.assertTrue(b.EXCLUDED_NAME.search(name))
        for name in ['Купер','Hoff','Спортмастер','ВкусВилл']:self.assertFalse(b.EXCLUDED_NAME.search(name))
    def test_backit_each_customer_scope_has_correct_currency(self):
        n=common(kuper());self.assertEqual([(x['value'],x['unit']) for x in n['benefits']],[('388','RUB'),('24','RUB'),('388','RUB')])
        self.assertIn('старого',n['benefits'][1]['scope']['tariff_condition'])
        self.assertTrue(all(x['kind']=='cashback' for x in n['benefits']))
    def test_backit_reader_preserves_restrictions_and_activation(self):
        row,reason=record_row(common(kuper()),NOW[:10]);self.assertIsNone(reason)
        for marker in ('мобильного приложения','1500','24 р.'):self.assertIn(marker,row[5])
        self.assertIn('Активировать',row[4])
    def test_backit_no_cross_merchant_or_old_rate_fallback(self):
        with self.assertRaises(ValueError):b.parse_detail(html('backit-kuper.html'),{'url':b.ROOT+'/kuper','name':'Wrong'},NOW)
        with self.assertRaises(b.ExcludedOffer):b.parse_detail(html('backit-sportmaster.html'),{'url':b.ROOT+'/sportmaster','name':'Спортмастер'},NOW)
    def test_backit_rate_update_keeps_identity(self):
        old=kuper();new=kuper(html('backit-kuper.html').replace('388 р.','389 р.'))
        self.assertEqual(old['id'],new['id']);self.assertNotEqual(old['content_sha256'],new['content_sha256'])
    def test_backit_missing_or_duplicate_rate_fails(self):
        s=BeautifulSoup(html('backit-kuper.html'),'html.parser');s.select_one('.shop-rates').decompose()
        with self.assertRaises(ValueError):kuper(str(s))
        s=BeautifulSoup(html('backit-kuper.html'),'html.parser');n=s.select_one('.shop-rates .rate span');n.insert_after(copy.copy(n))
        with self.assertRaises(ValueError):kuper(str(s))
    def test_avolta_owned_category(self):
        cards=a.catalogue(html('avolta-list.html'),a.PREFIX+'zaly-ozhidaniya','Залы ожидания')
        self.assertEqual([c['name'] for c in cards],['Plaza','Dragonpass'])
        with self.assertRaises(ValueError):a.catalogue(html('avolta-list.html'),a.PREFIX+'oteli','Отели')
    def test_plaza_is_discount_not_free_pass(self):
        n=common(plaza());self.assertEqual([(x['kind'],x['value']) for x in n['benefits']],[('discount','25')])
        row,reason=record_row(n,NOW[:10]);self.assertIsNone(reason);self.assertIn('3 раза в год',row[5]);self.assertIn('Smart Traveller',row[4])
    def test_dragonpass_real_price_disagreement_quarantined(self):
        row=a.parse_detail(html('avolta-dragonpass.html'),{'url':a.PREFIX+'zaly-ozhidaniya/dragonpass','name':'Dragonpass','category':'Залы ожидания'},NOW)
        self.assertIn('source_conflict_lounge_admission_price_withheld',row['warnings'])
        self.assertNotRegex(row['benefit_text'],r'28|31')
    def test_avolta_missing_terms_fails(self):
        s=BeautifulSoup(html('avolta-plaza.html'),'html.parser');s.select_one('.two-column-block').decompose()
        with self.assertRaises(ValueError):plaza(str(s))
    def test_mantera_five_tiers(self):
        rows=m.parse(html('mantera-faq.html'),NOW);self.assertEqual(len(rows),5)
        self.assertEqual([common(r)['benefits'][0]['value'] for r in rows],['3','5','7','10','15'])
    def test_mantera_spending_cap_is_not_discount(self):
        n=common(m.parse(html('mantera-faq.html'),NOW)[0])
        self.assertEqual([(x['kind'],x['value']) for x in n['benefits']],[('earn_points','3'),('redeem_points','20')])
        self.assertTrue(all(x['reward_unit']=='Mantera_bonus_not_cash' for x in n['benefits']))
    def test_mantera_pilot_prebooking_and_day_discrepancy_survive(self):
        original=m.parse(html('mantera-faq.html'),NOW)[0];row,reason=record_row(common(original),NOW[:10]);self.assertIsNone(reason)
        for marker in ('пилотного','ограниченном числе отелей','услуги проживания','до оформления','наличных невозможно','календарных','рабочих'):self.assertIn(marker,row[5])
        self.assertTrue(any('calendar_versus_business' in s for s in original['warnings']))
    def test_mantera_missing_terms_or_pilot_fails(self):
        s=BeautifulSoup(html('mantera-faq.html'),'html.parser');next(n for n in s.select('.MuiAccordion-root') if m.QUESTIONS[2] in n.get_text()).decompose()
        with self.assertRaises(ValueError):m.parse(str(s),NOW)
        s=BeautifulSoup(html('mantera-faq.html'),'html.parser');s.select_one('.pilot-loyalty-banner-icon').parent.decompose()
        with self.assertRaises(ValueError):m.parse(str(s),NOW)
    def test_mantera_rates_not_hardcoded(self):
        old=m.parse(html('mantera-faq.html'),NOW)[0];new=m.parse(html('mantera-faq.html').replace('с начислением 3%','с начислением 4%'),NOW)[0]
        self.assertEqual(old['id'],new['id']);self.assertEqual(common(new)['benefits'][0]['value'],'4')
    def test_rehash_cannot_remove_rules(self):
        for original in [kuper(),plaza(),m.parse(html('mantera-faq.html'),NOW)[0]]:
            for key,value in [('conditions_text',''),('partner_name','Wrong'),('warnings',[]),('valid_until','2099-01-01')]:
                row=copy.deepcopy(original);row[key]=value;row['content_sha256']=content_hash(row)
                with self.assertRaises(ValueError):validate_offer(row)
    def test_scripts_are_not_evidence(self):
        s=BeautifulSoup(html('backit-kuper.html'),'html.parser');s.select_one('.shop-conditions').append(BeautifulSoup('<script>Secret 99% discount</script>','html.parser'))
        self.assertNotIn('Secret',kuper(str(s))['conditions_text'])
    def test_registered_and_linked(self):
        cfg={s['id']:s for s in json.loads((Path(__file__).parents[1]/'sources_normalized.json').read_text())}
        self.assertEqual([cfg[k]['mode'] for k in (b.SOURCE,a.SOURCE,m.SOURCE)],['backit','avolta','mantera'])
        for row in [kuper(),plaza(),m.parse(html('mantera-faq.html'),NOW)[0]]:
            n=common(row)
            for value in n['benefits']:self.assertEqual(len(value['condition_ids']),2)
            self.assertIsNone(n['eligibility_verified'])
