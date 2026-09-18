"""Synthetic boundary regressions. Actual source replay lives in timestamped artifacts."""
import asyncio,copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hse_alumni import ROOT,PROGRAM,blocks,parse_catalog,hse_codes,hse_rates,explicit_end,collect_hse
from normalized import validate_offer,content_hash,normalize_rates
from sheets_normalized import prepare,SCHEMAS
from unified_normalization import make_input,normalize_record
from source_selection import select_sources
NOW='2026-09-18T00:00:00+00:00'


def card(anchor,name=None,summary='Скидка 91% — только превью'):
    return f'<div class="fa-person__item"><a class="fa-person__name" href="#{anchor}">{name or anchor}</a><div class="fa-person__info">{summary}</div></div>'
def section(anchor,body):
    return f'<div class="builder-section"><a name="{anchor}"></a></div><div class="builder-section">{body}</div>'
def page(cards=None,details=None):
    cards=card('a')+card('b') if cards is None else cards
    details=section('b','<h2>B</h2><p>Скидка до 8% по промокоду B_ONLY</p>')+section('a','<h2>A</h2><p>Скидка 13% по промокоду A_ONLY</p><p>Предъявить карту выпускника; не суммируется.</p>') if details is None else details
    return '<div class="post__text builder_content"><div class="fa-card__group"><h2 class="builder-section__title">Synthetic category</h2>'+cards+'</div>'+details+'</div>'

def common(row):
    bundle={'schema_version':2,'run_id':'fixture:1','observed_at':NOW,'records':[row],
            'sources':[{'source_id':'hse_alumni','name':'HSE','root':ROOT,'status':'ok','normalized':1,'discovered':1,'failed':0,'coverage':'fixture','errors':[],'region':None,'observed_at':NOW}]}
    values=prepare(bundle)['parser_offers'][0]
    raw=make_input({'id':row['id'],'origin':'parser_offers','row':2,'fields':{h:{'value':v} for h,v in zip(SCHEMAS['parser_offers'],values)}})
    return normalize_record(raw,as_of='2026-09-18')


class HseTests(unittest.TestCase):
    def test_exact_anchor_join_not_sequence_or_preview_rate(self):
        rows=parse_catalog(page(),NOW)
        self.assertEqual([r['rates'][0]['value'] for r in rows],['13','8'])
        self.assertEqual([r['promo_codes'] for r in rows],[['A_ONLY'],['B_ONLY']])
        for r in rows:
            self.assertNotIn('91%',r['benefit_text']);validate_offer(r)
    def test_absolute_whitespace_href_supported_without_tracking(self):
        raw=page().replace('href="#a"',f'href=" {ROOT}#a"')
        self.assertEqual(parse_catalog(raw,NOW)[0]['source_url'],ROOT+'#a')
        for bad in ('https://example.test/#a',ROOT+'?tracking=1#a',ROOT):
            with self.assertRaises(ValueError):parse_catalog(page().replace('href="#a"','href="'+bad+'"'),NOW)
    def test_missing_and_empty_details_remain_observations(self):
        rows=parse_catalog(page(card('missing',summary='Скидка 44%, промокод PREVIEW_ONLY')+card('empty'),section('empty','')),NOW)
        self.assertEqual([r['details']['public_catalog_block']['detail_state'] for r in rows],['missing_anchor','empty_section'])
        for r in rows:
            self.assertEqual(r['record_kind'],'source_observation');self.assertEqual(r['rates'],[]);self.assertEqual(r['promo_codes'],[])
            self.assertEqual(r['benefit_text'],'');self.assertIsNone(r['benefit_url'])
            self.assertEqual(common(r)['benefits'],[])
    def test_unlisted_and_empty_named_boundaries_prevent_contamination(self):
        detail=section('a','<p>Скидка 7%, промокод OWN_ONLY</p>')+section('','<p>Скидка 99%, промокод OTHER_ONLY</p>')
        r,=parse_catalog(page(card('a'),detail),NOW)
        self.assertEqual(r['promo_codes'],['OWN_ONLY']);self.assertNotIn('99',r['conditions_text'])
    def test_category_h1_stops_section_but_partner_h1_does_not(self):
        detail=section('a','<h1>A</h1><p>Скидка 7%</p>')+'<div class="builder-section"><div class="nom"><h1>NEXT CATEGORY</h1></div></div>'
        r,=parse_catalog(page(card('a'),detail),NOW);self.assertEqual(r['rates'][0]['value'],'7');self.assertNotIn('NEXT CATEGORY',r['conditions_text'])
    def test_two_content_sections_owned_by_same_anchor_are_kept(self):
        detail=section('a','<p>Скидка 7%</p>')+'<div class="builder-section"><p>Нужно предъявить карту</p></div>'
        self.assertIn('Нужно предъявить карту',parse_catalog(page(card('a'),detail),NOW)[0]['conditions_text'])
    def test_duplicate_card_or_target_fails(self):
        for raw in (page(card('a')+card('a')),page(details=section('a','one')+section('a','two'))):
            with self.assertRaises(ValueError):parse_catalog(raw,NOW)
    def test_wrong_anchor_owner_and_double_roots_fail(self):
        for raw in (page().replace('<a name="a">','<div class="builder-section"><a name="a">').replace('</a></div><div class="builder-section"><h2>A','</a></div></div><div class="builder-section"><h2>A'),page()+page()):
            with self.assertRaises(ValueError):parse_catalog(raw,NOW)
    def test_hidden_form_comment_values_not_used(self):
        detail=section('a','<p>Скидка 6%</p><p hidden>Промокод HIDDEN_ONLY</p><form>Промокод FORM_ONLY</form><!-- Промокод COMMENT_ONLY -->')
        r,=parse_catalog(page(card('a'),detail),NOW);self.assertEqual(r['promo_codes'],[])
    def test_links_preserve_target_not_display_name(self):
        r,=parse_catalog(page(card('a'),section('a','<p>Скидка 6%</p><a href="https://example.test/right">wrong.test</a>')),NOW)
        self.assertEqual(r['details']['public_catalog_block']['links'],[{'label':'wrong.test','url':'https://example.test/right'}])
    def test_explicit_published_expiry_and_month_suboffer(self):
        detail=section('a','<p>Скидка 12%</p><p>Только в августе скидка 19%</p><p>Предложение действует до 31.12.2026 г.</p>')
        r,=parse_catalog(page(card('a'),detail),NOW)
        self.assertEqual(r['valid_until'],'2026-12-31');self.assertEqual(len(r['details']['month_limited_clauses']),1)
        n=common(r);seasonal=[b for b in n['benefits'] if b['value']=='19'][0]
        self.assertIn('августе',seasonal['scope']['calendar_constraint_text'])
    def test_past_end_is_expired_not_new_current_offer(self):
        r,=parse_catalog(page(card('a'),section('a','<p>Скидка 9%</p><p>Скидка действует до 01.01.2026</p>')),NOW)
        self.assertEqual(r['validity_status'],'expired_by_published_end');self.assertEqual(common(r)['validity']['status'],'expired')
    def test_coupon_year_and_biography_do_not_become_expiry(self):
        self.assertEqual(explicit_end('Основано в 2017 году. Промокод HSE25. Только в августе.'),(None,None))
    def test_multiple_conflicting_or_invalid_end_dates_rejected(self):
        for text in ('Скидка действует до 31.02.2026','Скидка действует до 01.01.2026; предложение действует до 31.12.2026'):
            with self.assertRaises(ValueError):explicit_end(text)
    def test_validator_rejects_changed_evidence_even_rehashed(self):
        row=parse_catalog(page(),NOW)[0]
        for field,value in [('benefit_text','Скидка 77%'),('valid_until','2030-12-31'),('source_url',ROOT+'#other'),('redemption_text','invented')]:
            r=copy.deepcopy(row);r[field]=value;r['content_sha256']=content_hash(r)
            with self.assertRaises(ValueError):validate_offer(r)
    def test_source_specific_coupon_grammars_and_case(self):
        cases={'Скидка по промокоду 15% Friends':'Friends','Промокод на 15% - HSE':'HSE','П ромо-код HSE20 на 20%':'HSE20',
               'Промокод и скидка: AlUMNI15 / скидка15%':'AlUMNI15','По ключевому слову HSEALUMNI':'HSEALUMNI','Кодовое слово ЭКОНОМИКА17':'ЭКОНОМИКА17'}
        for text,value in cases.items():self.assertIn(value,hse_codes(text)['codes'],text)
    def test_coupon_mentions_and_numbers_not_literal_codes(self):
        for text in ('Промокод нужно получить в личном кабинете','Промокод на 15%','Промокод 20%','Размер промокода 500 рублей','Промокода нет'):
            self.assertEqual(hse_codes(text)['codes'],[],text)
    def test_payment_percentage_never_discount_even_in_common_view(self):
        r,=parse_catalog(page(card('a'),section('a','<p>Скидка 7% при 100% оплате или ипотеке</p>')),NOW)
        self.assertEqual([x['value'] for x in r['rates']],['7'])
        n=common(r);self.assertEqual([x['value'] for x in n['benefits']],['7']);self.assertIn('100%',n['conditions'][0]['evidence']['text'])
    def test_coupon_percentage_can_supply_owned_rate_not_global_change(self):
        self.assertEqual(hse_rates('Промокод EXAMPLE_ONLY на 17,5%')[0]['value'],'17.5')
        self.assertEqual(normalize_rates('Промокод EXAMPLE_ONLY на 17,5%'),[])
        self.assertEqual(hse_rates('Промокод EXAMPLE_ONLY на 101%'),[])
    def test_limit_and_missing_report_in_real_collector_entrypoint(self):
        class Client:
            async def read(self,url,render=False):
                self.url=url;self.render=render;return page(card('a')+card('missing'),section('a','<p>Скидка 7%</p>'))
        client=Client();report={'errors':[]};cfg={'id':'hse_alumni','url':ROOT}
        rows=asyncio.run(collect_hse(client,cfg,report,NOW,1))
        self.assertEqual(len(rows),1);self.assertEqual(client.url,ROOT);self.assertTrue(client.render)
        self.assertEqual(report['discovered'],2);self.assertEqual(len(report['errors']),2)
        self.assertFalse(json.loads(report['coverage'])['all_listed_cards_represented'])
    def test_source_read_failure_propagates_no_canned_fallback(self):
        class Client:
            async def read(self,*a,**kw):raise RuntimeError('source_failed')
        with self.assertRaises(RuntimeError):asyncio.run(collect_hse(Client(),{'id':'hse_alumni','url':ROOT},{'errors':[]},NOW,100))
    def test_both_requested_sources_registered_exactly_once(self):
        config=json.loads(Path(__file__).resolve().parents[1].joinpath('sources_normalized.json').read_text())
        selected=select_sources(config,'hse_alumni,alfa_only_partner_offers')
        self.assertEqual(len(selected),2);self.assertEqual(selected[0]['mode'],'hse');self.assertEqual(selected[0]['url'],ROOT)
        self.assertEqual(selected[1]['url'],'https://web.alfabank.ru/partner-offers/');self.assertEqual(selected[1]['mode'],'probe')

if __name__=='__main__':unittest.main()
