"""Source-owned sections, dynamic values and explicit audience separation."""
import copy,json,sys,unittest
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters import extract
from partner_pages import CONFIG,extract_partner_page
from normalized import content_hash,validate_offer
from sheets_normalized import prepare
from unified_inputs import HEADERS,inputs_from_tables
from unified_normalization import INPUT_TABS,normalize_inputs,validate_normalized
SID='sacvoyage_loyalty';URL='https://sacvoyage.ru/aktsii/'
NOW='2026-09-18T00:00:00+00:00'


def page(member='7',friend='12'):
    return ('<html><body><main><h2 class="about__title">Скидки</h2><div class="services__text">'
        '<p><strong>Программа лояльности</strong></p>'
        f'<p>При регистрации получаете скидку {member}% на бронирования на нашем сайте.</p>'
        '<p>Скидка не суммируется с акциями; не действует через агентства и по корпоративным тарифам.</p>'
        '<p><strong>Реферальная программа</strong></p><p>В профиле есть персональная ссылка.</p>'
        f'<p>Друг получает {friend}% на первое проживание.</p>'
        '<p>Рекомендателю подарок после регистрации и выезда друга.</p>'
        '<p>Условия могут меняться. Актуальная скидка в личном кабинете.</p>'
        '</div></main><aside>РЖД Бонус: скидка 91%, промокод OUTSIDE_ONLY.</aside></body></html>')


def published_tables(rows):
    report={'source_id':SID,'name':'Sacvoyage','root':URL,'status':'ok',
            'discovered':len(rows),'normalized':len(rows),'failed':0,'errors':[],
            'region':None,'coverage':'source-owned audiences','observed_at':NOW}
    bundle={'schema_version':2,'run_id':'test:sacvoyage','observed_at':NOW,
            'records':rows,'sources':[report]}
    values=prepare(json.loads(json.dumps(bundle)))['parser_offers']
    tables={tab:[[] for _ in range(header-1)]+[[{'value':h} for h in HEADERS[tab]]]
            for tab,(header,_) in INPUT_TABS.items()}
    tables['parser_offers'].extend([[{'value':v} for v in row+['']] for row in values])
    return tables


def legacy_row(row):
    row=copy.deepcopy(row)
    row['details'].pop('_source',None)
    row['content_sha256']=content_hash(row)
    return row


class SacvoyageTests(unittest.TestCase):
    def test_dynamic_real_dispatch_and_audience_boundaries(self):
        rows=extract(SID,page('7,5','13'),URL,NOW)
        self.assertEqual([r['rates'][0]['value'] for r in rows],['7.5','13'])
        self.assertEqual([r['native_id'] for r in rows],['member','referred_guest'])
        self.assertIn('корпоративным',rows[0]['conditions_text'])
        self.assertNotIn('корпоративным',rows[1]['conditions_text'])
        self.assertNotIn('подарок',rows[0]['conditions_text'])
        self.assertIn('подарок',rows[1]['conditions_text'])
        for r in rows:
            self.assertFalse(r['details']['gated_catalogue_terms_recovered'])
            self.assertIn('личном кабинете',r['conditions_text'])
            self.assertNotIn('OUTSIDE_ONLY',json.dumps(r))
            self.assertEqual(r['promo_codes'],[])
            self.assertIsNone(r['valid_until']);validate_offer(r)

    def test_missing_rate_cannot_come_from_other_audience(self):
        rows=extract(SID,page().replace('скидку 7%','привилегию'),URL,NOW)
        self.assertEqual(rows[0]['rates'],[])
        self.assertEqual(rows[0]['record_kind'],'source_observation')
        self.assertEqual(rows[1]['rates'][0]['value'],'12')

    def test_alternative_rates_stay_in_their_own_section(self):
        rows=extract(SID,page('7% или 9'),URL,NOW)
        self.assertEqual([r['value'] for r in rows[0]['rates']],['7','9'])
        self.assertEqual([r['value'] for r in rows[1]['rates']],['12'])
        self.assertIn('или',rows[0]['conditions_text'])

    def test_owned_heading_reaches_common_view_without_typing_payment_percent(self):
        raw=page().replace('Друг получает 12% на первое проживание.',
                           'Друг получает 12% на первое проживание. Предоплата 100%.')
        row=extract(SID,raw,URL,NOW)[1]
        self.assertEqual([(r['kind'],r['value']) for r in row['rates']],[('discount','12')])
        inputs,_=inputs_from_tables(published_tables([row]))
        before=copy.deepcopy(inputs)
        result=normalize_inputs(inputs,as_of='2026-11-06')['records'][0]
        validate_normalized(result)
        self.assertEqual([(b['kind'],b['value']) for b in result['benefits'] if b['unit']=='percent'],
                         [('discount','12')])
        self.assertEqual(result['provenance']['source_id'],SID)
        self.assertEqual(inputs,before)
        self.assertEqual(result['raw'],before[0])
        self.assertIn('Предоплата 100%.',result['raw']['conditions'])
        self.assertEqual(result['provenance']['observed_at'],NOW)
        self.assertEqual(result['raw']['original']['fields']['SHA256']['value'],row['content_sha256'])

    def test_legacy_stored_heading_keeps_rate_without_changing_source_snapshot(self):
        row=legacy_row(extract(SID,page(),URL,NOW)[1])
        inputs,_=inputs_from_tables(published_tables([row]))
        before=copy.deepcopy(inputs)
        self.assertEqual(inputs[0]['source_id'],'parser_offers')
        self.assertNotIn('_source',inputs[0]['details'])
        result=normalize_inputs(inputs,as_of='2026-11-06')['records'][0]
        validate_normalized(result)
        self.assertEqual([(b['kind'],b['value']) for b in result['benefits'] if b['unit']=='percent'],
                         [('discount','12')])
        self.assertEqual(inputs,before)
        self.assertEqual(result['raw'],before[0])
        self.assertEqual(result['provenance']['source_id'],'parser_offers')
        self.assertEqual(result['provenance']['observed_at'],NOW)
        self.assertEqual(result['raw']['original']['fields']['SHA256']['value'],row['content_sha256'])

    def test_legacy_heading_fallback_requires_exact_source_and_prefix(self):
        row=legacy_row(extract(SID,page(),URL,NOW)[1])
        original=published_tables([row])
        for label,column,value,details in (
                ('other path','Источник','https://sacvoyage.ru/partners/rzhd-bonus/',{}),
                ('tracking query','Источник',URL+'?utm_source=other',{}),
                ('fragment','Источник',URL+'#other',{}),
                ('foreign host','Источник','https://example.com/aktsii/',{}),
                ('explicit other source',None,None,{'_source':{'source_id':'s7'}}),
                ('empty source binding',None,None,{'_source':{}}),
                ('other scope',None,None,{'source_scope':'RZD_Bonus_partner_offer'}),
                ('mismatched heading',None,None,{'source_heading_context':'Кешбэк'}),
                ('absent prefix','Выгода',row['benefit_text'].removeprefix('Скидки: '),{})):
            with self.subTest(case=label):
                tables=copy.deepcopy(original)
                cells=tables['parser_offers'][1]
                if column:
                    cells[HEADERS['parser_offers'].index(column)]['value']=value
                if details:
                    cell=cells[HEADERS['parser_offers'].index('Детали JSON')]
                    cell['value']=json.dumps({**json.loads(cell['value']),**details})
                inputs,_=inputs_from_tables(tables)
                result=normalize_inputs(inputs,as_of='2026-11-06')['records'][0]
                validate_normalized(result)
                self.assertFalse(any(b['unit']=='percent' for b in result['benefits']))

    def test_heading_is_not_borrowed_by_common_conditions_or_activation(self):
        raw=page().replace('Друг получает 12% на первое проживание.',
                           'Друг получает подарок на первое проживание. Предоплата 100%.').replace(
                           'Условия могут меняться.','Общие условия: вознаграждение 42%.')
        row=extract(SID,raw,URL,NOW)[1]
        self.assertEqual(row['rates'],[])
        for source_row in (row,legacy_row(row)):
            with self.subTest(legacy='_source' not in source_row['details']):
                inputs,_=inputs_from_tables(published_tables([source_row]))
                result=normalize_inputs(inputs,as_of='2026-11-06')['records'][0]
                validate_normalized(result)
                self.assertFalse(any(b['unit']=='percent' for b in result['benefits']))
                self.assertIn('вознаграждение 42%',result['raw']['conditions'])
                self.assertIn('Предоплата 100%',result['raw']['activation'])

    def test_duplicate_missing_and_moved_panels_fail(self):
        for raw in (page().replace('services__text','other'),page().replace('Реферальная программа','Программа лояльности'),
                    page().replace('</main>','<h2 class="about__title">Скидки</h2></main>')):
            with self.subTest(raw=raw),self.assertRaises(ValueError):extract(SID,raw,URL,NOW)

    def test_new_clause_markup_is_preserved_not_silently_skipped(self):
        for extra in ('<div>Не действует по субботам.</div>', 'Не действует по субботам.'):
            raw=page().replace('</div></main>',extra+'</div></main>')
            rows=extract(SID,raw,URL,NOW)
            self.assertTrue(any('Не действует по субботам.' in r['conditions_text'] for r in rows))

    def test_removed_account_notice_is_not_invented(self):
        rows=extract(SID,page().replace('Условия могут меняться. Актуальная скидка в личном кабинете.',''),URL,NOW)
        self.assertTrue(all('Актуальная скидка в личном кабинете.' not in r['conditions_text'] for r in rows))

    def test_missing_material_restriction_is_not_assumed(self):
        rows=extract(SID,page().replace('корпоративным','другим'),URL,NOW)
        self.assertIn('другим тарифам',rows[0]['conditions_text'])
        self.assertNotIn('корпоративным',rows[0]['conditions_text'])

    def test_hidden_and_comment_rates_do_not_supply_values(self):
        raw=page().replace('При регистрации получаете скидку 7%',
                          '<span hidden>При регистрации скидка 7%</span><!-- скидка 7% -->При регистрации')
        rows=extract(SID,raw,URL,NOW)
        self.assertEqual(rows[0]['rates'],[])
        self.assertEqual(rows[0]['record_kind'],'source_observation')

    def test_exact_url_rejects_other_program_and_tracking(self):
        for url in (URL+'?code=other',URL+'#other','https://sacvoyage.ru/partners/rzhd-bonus/'):
            with self.assertRaises(ValueError):extract(SID,page(),url,NOW)

    def test_source_dom_not_mutated(self):
        dom=BeautifulSoup(page(),'html.parser');before=str(dom)
        extract_partner_page(SID,dom,URL,NOW);self.assertEqual(str(dom),before)

    def test_registration_has_one_matching_source_and_is_not_rzd(self):
        routes=json.loads(Path(__file__).resolve().parents[1].joinpath('sources_normalized.json').read_text())
        selected=[r for r in routes if r['id']==SID]
        self.assertEqual(len(selected),1);self.assertEqual(selected[0]['url'],URL)
        self.assertEqual(CONFIG[SID]['url'],URL)
        self.assertNotIn('РЖД',CONFIG[SID]['program'])

if __name__=='__main__':unittest.main()
