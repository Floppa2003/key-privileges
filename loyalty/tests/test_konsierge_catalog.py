"""Owned-source replay and negative canaries; fixture values are public, not entitlements."""
import copy
import hashlib
import html
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from konsierge_catalog import parse_capture, ROOT, SOURCE, validate_record, derived
from normalized import content_hash, validate_offer, text
from sheets_normalized import prepare, SCHEMAS
from unified_normalization import make_input, normalize_record

FIX=Path(__file__).parent/'fixtures_live'/'konsierge-public.json'
NOW='2026-09-19T19:18:49.862699+00:00'


class KonsiergeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)
        fix=json.loads(FIX.read_text());self.items=fix['items']
        self.report={'observed_at':NOW,'one_off_public_ui_inspection':True,'source_account_login':False,
            'direct_api_requests':0,'credential_values_read_or_replayed':False,'published':False,
            'errors':[],'rubrics':fix['rubrics'],'catalogues':[],'network_pages':[]}
        for rubric in [None]+fix['rubrics']:
            rid=rubric['id'] if rubric else None
            items=[i for i in self.items if rid is None or rid in [x['id'] for x in i['rubrics']]]
            if not items:continue
            filename='all.html' if rid is None else f'rubric-{rid}.html'
            node=lambda tag,cls,s:f'<{tag} class="{cls}">{html.escape(s)}</{tag}>'
            body='<qy-benefits-page>'+''.join('<qy-benefit-teaser>'+node('div','BenefitTeaser-Title',i['name'])+node('div','BenefitTeaser-OfferText',i['offer'])+'</qy-benefit-teaser>' for i in items)+'</qy-benefits-page>'
            (self.path/filename).write_text(body)
            pages=[items[x:x+12] for x in range(0,len(items),12)]
            self.report['catalogues'].append({'url':ROOT+(f'?rubric_id={rid}' if rid is not None else ''),
                'file':filename,'sha256':hashlib.sha256(body.encode()).hexdigest(),'cards':[{'name':i['name'].strip(),'offer':i['offer']} for i in items],
                'native_item_count':len(items),'native_pages':len(pages),'scroll_stop':'native_last_page_and_count'})
            for p,chunk in enumerate(pages,1):
                self.report['network_pages'].append({'path':'/api/client/v1/benefits','status':200,
                    'query':{'page':str(p),'per':'12',**({'rubric_id':str(rid)} if rid is not None else {})},
                    'received_at':NOW,'page':{'current_page':p,'total_pages':len(pages),'total_count':len(items),'count':len(chunk),'next_page':None if p==len(pages) else p+1},'items':copy.deepcopy(chunk)})

    def bundle(self):return parse_capture(self.report,self.path,'35463931323:1')
    def row(self,ident):return next(r for r in self.bundle()['records'] if r['native_id']==str(ident))
    def common(self,ident):
        b=self.bundle();row=next(r for r in prepare(b)['parser_offers'] if r[0]==self.row(ident)['id'])
        raw=make_input({'id':row[0],'origin':'parser_offers','row':2,'fields':{k:{'value':v} for k,v in zip(SCHEMAS['parser_offers'],row)}})
        return normalize_record(raw,as_of='2026-09-19')

    def test_full_bundle_and_generic_code(self):
        b=self.bundle();self.assertEqual(len(b['records']),len(self.items));prepare(b)
        self.assertEqual(self.row(2615)['promo_codes'],['GMSKonsierge26'])
        self.assertEqual(self.row(2442)['promo_codes'],['KONSIERGE7'])

    def test_complete_description_no_truncation(self):
        for i in self.items:
            r=self.row(i['id']);self.assertIn(text(i['description']),r['conditions_text'])
            self.assertIsNone(r['benefit_url'])

    def test_missing_root_page_fails(self):
        self.report['network_pages'].pop(1)
        with self.assertRaises(ValueError):self.bundle()

    def test_repeated_page_cannot_count_twice(self):
        self.report['network_pages'].insert(0,copy.deepcopy(self.report['network_pages'][0]))
        with self.assertRaises(ValueError):self.bundle()

    def test_total_drift_and_early_stop_fail(self):
        self.report['network_pages'][0]['page']['total_count']+=1
        with self.assertRaises(ValueError):self.bundle()

    def test_inactivity_is_not_completion(self):
        self.report['catalogues'][0]['scroll_stop']='stable'
        with self.assertRaises(ValueError):self.bundle()

    def test_dom_tamper_is_caught(self):
        p=self.path/'all.html';p.write_text(p.read_text().replace('10%','99%'))
        with self.assertRaisesRegex(ValueError,'dom_hash'):self.bundle()

    def test_same_dom_count_wrong_partner_is_caught(self):
        p=self.path/'all.html';p.write_text(p.read_text().replace('GMS (Смоленская)','Wrong partner'))
        self.report['catalogues'][0]['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError,'dom_item'):self.bundle()

    def test_category_ordering_is_not_semantic_drift(self):
        for p in self.report['network_pages']:
            if 'rubric_id' in p['query']:
                for i in p['items']:i['rubrics'].reverse()
        self.bundle()

    def test_actual_category_drift_is_caught(self):
        p=next(p for p in self.report['network_pages'] if 'rubric_id' in p['query'])
        p['items'][0]['description']+=' Wrong terms.'
        with self.assertRaisesRegex(ValueError,'cross_category_item_drift'):self.bundle()

    def test_root_only_records_not_dropped(self):
        r=self.row(2343);self.assertIsNone(r['category']);self.assertIn('root_only_not_in_public_category_tabs',r['warnings'])

    def test_unknown_and_codeword_are_preserved(self):
        n=self.common(2079);self.assertEqual(n['codes'][0]['value'],'Консьерж-Пять');self.assertEqual(n['codes'][0]['delivery'],'code_word')
        n=self.common(1912);self.assertIsNone(n['codes'][0]['value']);self.assertEqual(n['codes'][0]['delivery'],'app')

    def test_department_commission_not_customer_discount(self):
        n=self.common(2037);self.assertEqual(len(n['benefits']),1)
        self.assertEqual(n['benefits'][0]['value'],'20');self.assertEqual(n['benefits'][0]['qualifier'],'up_to')
        self.assertNotIn('25',[b['value'] for b in n['benefits']]);self.assertEqual(n['validity']['until'],'2026-12-31')

    def test_hotel_privilege_not_universal_spa_discount(self):
        n=self.common(2047);self.assertEqual(len(n['benefits']),1);self.assertIsNone(n['benefits'][0]['value'])
        self.assertIn('10%',n['conditions'][0]['evidence']['text']);self.assertIn('BAR',n['conditions'][0]['evidence']['text'])
        self.assertEqual(len(n['benefits'][0]['condition_ids']),2)

    def test_room_credit_not_cash(self):
        n=self.common(1838);self.assertIsNone(n['benefits'][0]['value']);self.assertIn('10 000',n['conditions'][0]['evidence']['text'])

    def test_expiry_conflict_not_silently_resolved(self):
        n=self.common(2036);self.assertEqual(n['validity']['status'],'source_date_conflict');self.assertIsNone(n['validity']['until'])
        self.assertIn('31.12.2026',n['conditions'][0]['evidence']['text']);self.assertIn('2025-12-30',n['conditions'][0]['evidence']['text'])

    def test_expired_hotel_and_metadata_only_expiry(self):
        self.assertEqual(self.common(1583)['validity']['status'],'expired')
        self.assertEqual(self.common(1995)['validity']['status'],'source_expiry_elapsed_customer_period_unknown')

    def test_rate_change_preserves_native_id(self):
        old=self.row(2615)
        i=copy.deepcopy(old['details']['public_item']);i['offer']='Скидка 11%'
        self.assertEqual(derived(i,NOW)[0],'Скидка 11%');self.assertEqual(i['id'],int(old['native_id']))

    def test_rehashed_row_field_tampering_fails(self):
        for k,v in [('program','Alfa Only'),('conditions_text',''),('valid_until','2099-01-01'),('warnings',[])]:
            r=self.row(2615);r[k]=v;r['content_sha256']=content_hash(r)
            with self.assertRaises(ValueError):validate_offer(r)

    def test_auth_or_error_flags_fail(self):
        self.report['source_account_login']=True
        with self.assertRaises(ValueError):self.bundle()

    def test_active_markup_fails(self):
        i=copy.deepcopy(self.items[0]);i['description']='<script>bad</script>'
        with self.assertRaisesRegex(ValueError,'active_markup'):derived(i,NOW)
