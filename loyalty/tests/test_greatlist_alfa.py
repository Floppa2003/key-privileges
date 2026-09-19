"""GreatList source ownership, complete visible inventory and common-view checks."""
import asyncio,copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import greatlist_alfa as g
from normalized import content_hash,validate_offer
from sheets_normalized import prepare,SCHEMAS
from unified_normalization import make_input,normalize_record
NOW='2026-09-19T09:00:00+00:00'
CITY={'url':'https://greatlist.ru/spb/','name':'Санкт-Петербург'}
CARD={'post_id':'123','name':'Fixture','url':'https://greatlist.ru/spb/restaurant/fixture/','city':CITY,'catalogue_url':g.ROOT}

def wrap(body,url,classes='term-alfa-only',extra=''):
    return f'<html><head><title>Выбор Alfa Only - GreatList</title><link rel="canonical" href="{url}"/></head><body class="{classes}">{body}{extra}</body></html>'
def nav():
    return '<div class="psevdo_select_area_city"><div class="psevdo_select_list"><a href="https://greatlist.ru/spb/">Санкт-Петербург</a><a href="https://greatlist.ae/">Dubai</a></div></div>'
def tab():
    return f'<a data-id="alfa-only" href="{g.ROOT}">Выбор Alfa Only</a>'
def listing(empty=False):
    card='' if empty else '<a class="place_card" data-objectid="123" href="/spb/restaurant/fixture/"><div class="h2">Fixture</div></a>'
    return wrap(nav()+tab()+f'<div class="places_mansory js_get_cards">{card}</div>',g.ROOT)
def detail(cashback=True,extra=''):
    rate='<li>кэшбэк до 12%</li>' if cashback else ''
    body=f'<h1>Ресторан Fixture</h1><article class="contacts"><div class="contacts_item_address">Улица Примерная, 1</div></article><div class="alfa-section-hide"><div class="alfa-section-text">Привилегии для клиентов Alfa Only:<ul>{rate}<li>приоритетная бронь через консьерж-сервис</li></ul>В меню — фирменный коктейль и десерт, созданные вместе с шефами</div></div>'
    return wrap(body,CARD['url'],'single-restaurant postid-123',extra)
def common(row):
    report={'source_id':g.SOURCE_ID,'name':'GreatList','root':g.ROOT,'status':'ok','normalized':1,'discovered':1,'failed':0,'coverage':'fixture','errors':[],'region':None,'observed_at':NOW}
    bundle={'schema_version':2,'run_id':'fixture:1','observed_at':NOW,'records':[row],'sources':[report]}
    values=prepare(bundle)['parser_offers'][0]
    raw=make_input({'id':row['id'],'origin':'parser_offers','row':2,'fields':{h:{'value':v} for h,v in zip(SCHEMAS['parser_offers'],values)}})
    return normalize_record(raw,as_of='2026-09-19')

class GreatListTests(unittest.TestCase):
    def test_city_links_are_ui_derived_deduplicated_and_russian_only(self):
        self.assertEqual(g.city_roots(listing()),[CITY])
        self.assertEqual(g.city_roots(listing().replace(nav(),nav()+nav())),[CITY])
        with self.assertRaises(ValueError):g.city_roots(wrap('',g.ROOT))
    def test_exact_alfa_tab_not_a_club_or_constructed_path(self):
        self.assertEqual(g.alfa_tab(wrap(tab(),CITY['url'],''),CITY),g.ROOT)
        with self.assertRaises(ValueError):g.alfa_tab(wrap('<a data-id="alfa" href="/spb/alfa/">A Club</a>',CITY['url'],''),CITY)
    def test_cards_and_valid_empty_catalogue(self):
        self.assertEqual(g.catalogue(listing(),g.ROOT,CITY),[CARD])
        self.assertEqual(g.catalogue(listing(empty=True),g.ROOT,CITY),[])
        with self.assertRaises(ValueError):g.catalogue(wrap('',g.ROOT),g.ROOT,CITY)
    def test_duplicate_id_foreign_url_wrong_city_and_pagination_fail_closed(self):
        raw=listing(); a='<a class="place_card" data-objectid="123" href="/spb/restaurant/other/"><div class="h2">Other</div></a>'
        for bad in (raw.replace('</body>',a+'</body>'),raw.replace('/spb/restaurant/fixture/','https://other.test/spb/restaurant/fixture/'),raw.replace('/spb/restaurant/fixture/','/msk/restaurant/fixture/'),raw.replace('</body>','<a rel="next" href="/spb/alfa-only/page/2/">next</a></body>')):
            with self.assertRaises(ValueError):g.catalogue(bad,g.ROOT,CITY)
    def test_source_rate_not_hardcoded_menu_is_not_gift(self):
        row=g.parse_detail(detail(),CARD,NOW);validate_offer(row)
        self.assertEqual([(r['value'],r['qualifier']) for r in row['rates']],[('12','up_to')])
        self.assertNotIn('коктейль',row['benefit_text']);self.assertIn('коктейль',row['conditions_text'])
        self.assertNotIn('gift',row['benefit_types']);self.assertIsNone(row['valid_until'])
    def test_booking_only_does_not_inherit_cashback(self):
        row=g.parse_detail(detail(False),CARD,NOW);validate_offer(row)
        self.assertEqual(row['rates'],[]);self.assertEqual(row['promo_codes'],[])
        self.assertIn('консьерж',row['redemption_text']);self.assertNotIn('cashback',row['benefit_types'])
    def test_unrelated_hidden_form_comment_rates_cannot_supply_benefit(self):
        raw=detail(False,extra='<p>Скидка 99%</p><div class="a-club">кэшбэк 88%</div>')
        raw=raw.replace('</ul>','<li hidden>кэшбэк 77%</li><li aria-hidden="true">кэшбэк 66%</li><form><li>кэшбэк 55%</li></form><!-- кэшбэк 44% --></ul>')
        row=g.parse_detail(raw,CARD,NOW);self.assertEqual(row['rates'],[])
    def test_wrong_postid_canonical_or_title_fail(self):
        for raw in (detail().replace('postid-123','postid-124'),detail().replace('rel="canonical"','rel="other"'),detail().replace('Ресторан Fixture','Ресторан Other')):
            with self.assertRaises(ValueError):g.parse_detail(raw,CARD,NOW)
    def test_wrong_program_or_missing_owned_bullets_does_not_create_offer(self):
        for raw in (detail().replace('для клиентов Alfa Only','для клиентов A-Клуб'),detail().replace('alfa-section-text','unrelated')):
            with self.assertRaises(ValueError):g.parse_detail(raw,CARD,NOW)
    def test_visible_common_conditions_and_unverified_eligibility(self):
        row=g.parse_detail(detail(False),CARD,NOW);n=common(row)
        txt=json.dumps(n['conditions'],ensure_ascii=False)
        self.assertIn('Примерная',txt);self.assertIn('консьерж',txt)
        self.assertIsNone(n['eligibility_verified'])
    def test_rehashed_relabel_or_changed_source_values_rejected(self):
        row=g.parse_detail(detail(),CARD,NOW)
        for field,value in [('benefit_text','кэшбэк 99%'),('conditions_text','no limits'),('redemption_text','buy'),('source_status','published'),('partner_name','Other'),('valid_until','2030-01-01')]:
            bad=copy.deepcopy(row);bad[field]=value;bad['content_sha256']=content_hash(bad)
            with self.assertRaises(ValueError):validate_offer(bad)
    def test_real_collector_error_and_limit_report_keep_denominator(self):
        class Client:
            async def read(self,url,render=False):
                if url==g.ROOT:return listing()
                if url==CITY['url']:return wrap(tab(),CITY['url'],'')
                if url==CARD['url']:raise RuntimeError('http_503')
                raise AssertionError(url)
        report={'errors':[]};rows=asyncio.run(g.collect(Client(),{'id':g.SOURCE_ID,'url':g.ROOT},report,NOW,20))
        self.assertEqual(rows,[]);self.assertEqual(report['discovered'],1);self.assertEqual(len(report['errors']),1)
        self.assertEqual(json.loads(report['coverage'])['detail_pages_parsed'],0)
    def test_limit_reports_omitted_cards_without_claiming_complete_inventory(self):
        extra='<a class="place_card" data-objectid="124" href="/spb/restaurant/second/"><div class="h2">Second</div></a>'
        class Client:
            async def read(self,url,render=False):
                if url==g.ROOT:return listing().replace('</div></body>',extra+'</div></body>')
                if url==CITY['url']:return wrap(tab(),CITY['url'],'')
                if url==CARD['url']:return detail(False)
                raise AssertionError(url)
        report={'errors':[]};rows=asyncio.run(g.collect(Client(),{'id':g.SOURCE_ID,'url':g.ROOT},report,NOW,1))
        self.assertEqual(len(rows),1);self.assertEqual(report['discovered'],2)
        self.assertFalse(json.loads(report['coverage'])['all_discovered_cards_parsed'])
        self.assertEqual(report['errors'][0]['reason'],'detail_limit_reached')
    def test_rate_limit_stops_new_requests(self):
        seen=[]
        class Client:
            async def read(self,url,render=False):
                seen.append(url)
                if url==g.ROOT:return listing()
                raise RuntimeError('http_429')
        report={'errors':[]}
        asyncio.run(g.collect(Client(),{'id':g.SOURCE_ID,'url':g.ROOT},report,NOW,20))
        self.assertEqual(seen,[g.ROOT,CITY['url']])
    def test_registration(self):
        configs=json.loads(Path(__file__).resolve().parents[1].joinpath('sources_normalized.json').read_text())
        self.assertEqual([c['url'] for c in configs if c['id']==g.SOURCE_ID],[g.ROOT])

if __name__=='__main__':unittest.main()
