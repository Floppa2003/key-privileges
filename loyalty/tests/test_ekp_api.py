"""Real public mapping and pagination; fake only network replies and clocks."""
import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).parents[1]))
import ekp_catalog as e
import ekp_api_collect as c
from normalized import validate_offer,content_hash
from sheets_normalized import prepare
from free_access_probe import ProbeError

NOW='2026-09-16T05:51:35+00:00'

def raw(ident='31',*,locked=False,active=True,value=17):
    return {'id':ident,'name':'Новый партнёр '+ident,'active':active,'description_authorized':locked,
        'text':'Описание бизнеса','categories':[{'categoryId':2,'categoryName':'Медицина'},{'categoryId':33,'categoryName':'Карелия'}],
        'loyaltyDescription':f'<p>Скидка {value}% на услуги</p><p>Покупка от 3000 руб. Не суммируется.</p>',
        'discountScheme':'Предъявите ЕКП до оплаты','shtrich':[{'name':'DO_NOT_EXPORT','link':'https://private.example/token'}]}


def record(row=None):
    return e.make_record(row or raw(),NOW,request=e.query(0),response_sha='a'*64,observed_total=1,completed_at=NOW)


class MappingTests(unittest.TestCase):
    def test_changed_input_not_fixed_answers(self):
        a=record();b=record(raw(value=23));d=record(raw('84'))
        self.assertEqual(a['id'],b['id']);self.assertNotEqual(a['content_sha256'],b['content_sha256'])
        self.assertNotEqual(a['id'],d['id']);self.assertEqual(b['rates'][0]['value'],'23')
        self.assertIn('Не суммируется',b['conditions_text']);self.assertIn('до оплаты',b['redemption_text'])

    def test_gated_fields_dropped_before_type_or_markup_processing(self):
        r=raw(locked=True);r['loyaltyDescription']={'private':'NO_EXPORT'};r['discountScheme']=['NO_EXPORT']
        x=record(r);dump=json.dumps(x)
        self.assertNotIn('NO_EXPORT',dump);self.assertNotIn('DO_NOT_EXPORT',dump)
        self.assertEqual(x['record_kind'],'source_observation');self.assertFalse(x['rates']);self.assertFalse(x['promo_codes'])
        self.assertNotIn('loyaltyDescription',x['details']['public_partner'])

    def test_inactive_and_missing_terms_are_not_active_offers(self):
        x=record(raw(active=False));self.assertEqual(x['record_kind'],'source_observation')
        self.assertEqual(x['source_status'],'public_catalog_api_inactive')
        r=raw();r['loyaltyDescription']=None
        self.assertEqual(record(r)['source_status'],'public_catalog_terms_missing')

    def test_tags_not_inferred_as_regions_or_categories(self):
        x=record();self.assertIsNone(x['category'])
        self.assertEqual(len(x['details']['public_partner']['categories']),2)
        self.assertEqual(x['details']['source_region_parameter'],'98')
        self.assertIsNone(x['benefit_url']);self.assertFalse(x['details']['detail_url_individually_opened'])

    def test_scoped_api_source_and_uninferred_dates(self):
        r=raw();r['loyaltyDescription']='Скидка 20% до 2027 года, подробности уточняйте.'
        x=record(r);self.assertEqual(x['source_url'],e.API);self.assertEqual(x['link_kind'],'page_block')
        self.assertIsNone(x['valid_until']);validate_offer(x)

    def test_rehashed_changes_cannot_promote_preview_or_replace_fields(self):
        x=record()
        for k,v in [('partner_name','other'),('benefit_text','Скидка 80%'),('source_status','verified'),('category','Карелия'),('benefit_url','https://ekp.spb.ru/')]:
            y=copy.deepcopy(x);y[k]=v;y['content_sha256']=content_hash(y)
            with self.subTest(k=k),self.assertRaises(ValueError):validate_offer(y)
        y=copy.deepcopy(x);y['details']['linked_terms_read']=True;y['content_sha256']=content_hash(y)
        with self.assertRaises(ValueError):validate_offer(y)

    def test_secret_like_fields_and_scripts_never_leave_projection(self):
        r=raw();r['loyaltyDescription']='<script>SECRET</script><form>HIDDEN</form><p onclick="bad">Скидка 5%</p><a href="https://example.org/?token=SECRET">Сайт</a>'
        x=record(r);s=json.dumps(x,ensure_ascii=False)
        for text in ('SECRET','HIDDEN','onclick','DO_NOT_EXPORT'):
            self.assertNotIn(text,s)
        self.assertIn('https://example.org/',s)

    def test_flags_and_ids_are_typed_not_guessed(self):
        for update in ({'active':'true'},{'description_authorized':0},{'id':'abc'},{'id':31},{'name':''}):
            with self.subTest(update=update),self.assertRaises(ValueError):record({**raw(),**update})

    def test_query_bounds(self):
        self.assertEqual(e.query(120)['pagination'],{'limit':120,'offset':120})
        for n in (-1,True,1,120.0,6000):
            with self.subTest(n=n),self.assertRaises(ValueError):e.query(n)

    def test_duplicate_wrong_offset_and_oversized_page_fail(self):
        for payload in ({'total':2,'offset':0,'partners':[raw(),raw()]},{'total':1,'offset':1,'partners':[raw()]},
                        {'total':1,'offset':0,'partners':[raw(),raw('32')]},{'total':True,'offset':0,'partners':[]}):
            with self.assertRaises(ValueError):e.page(payload,0)


class FakeReader:
    def __init__(self,total=245,fail_at=None,mutate_total=False,locked=False):
        self.calls=0;self.reserved=0;self.charged=0;self.balance=9999;self.total=total;self.interval=0
        self.fail_at=fail_at;self.mutate_total=mutate_total;self.queries=[];self.locked=locked
    def preflight(self):pass
    def closing_balance(self):return self.balance-self.charged
    def read(self,url,body=None):
        self.calls+=1;self.reserved+=25;self.charged+=25
        if url==e.POLICY:return 'User-agent: *\nAllow: /'
        off=body['pagination']['offset'];self.queries.append(copy.deepcopy(body))
        if off==self.fail_at:raise ProbeError('provider_http_423')
        rows=[raw(str(n),locked=self.locked) for n in range(off,min(off+120,self.total))]
        return json.dumps({'total':self.total+(1 if self.mutate_total and off else 0),'offset':off,'partners':rows})


class PaginationTests(unittest.TestCase):
    def test_actual_collector_full_pagination_publication_and_reconstruction(self):
        reader=FakeReader()
        with tempfile.TemporaryDirectory() as tmp:
            b=c.collect(reader,tmp,run_id='fixture:1',observed_at=datetime.now(timezone.utc).isoformat(),commit='test')
            self.assertEqual(len(b['records']),245);self.assertEqual(b['sources'][0]['status'],'ok')
            self.assertEqual([q['pagination']['offset'] for q in reader.queries],[0,120,240])
            self.assertEqual(len(prepare(b)['parser_offers']),245)
            # Controlled observation instant, not future source data.
            clock=datetime.now(timezone.utc)
            self.assertEqual(e.validate_bundle(tmp,run_id='fixture:1',commit='test',clock=clock),b)

    def test_late_refusal_preserves_earlier_current_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=c.collect(FakeReader(fail_at=120),tmp,run_id='fixture:1',observed_at=NOW,commit='test')
            self.assertEqual(len(b['records']),120);self.assertEqual(b['sources'][0]['status'],'partial')
            self.assertEqual(b['sources'][0]['errors'][0]['reason'],'provider_http_423')

    def test_total_mutation_cannot_claim_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=c.collect(FakeReader(mutate_total=True),tmp,run_id='fixture:1',observed_at=NOW,commit='test')
            self.assertEqual(len(b['records']),120)
            self.assertFalse(json.loads(b['sources'][0]['coverage'])['catalogue_pagination_complete'])

    def test_resource_bound_not_full_catalogue(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=FakeReader(total=2000);b=c.collect(r,tmp,run_id='fixture:1',observed_at=NOW,commit='test')
            self.assertEqual(r.calls,12);self.assertEqual(r.reserved,300)
            self.assertEqual(len(b['records']),1320);self.assertEqual(b['sources'][0]['status'],'partial')

    def test_protected_text_not_written_anywhere(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=c.collect(FakeReader(total=1,locked=True),tmp,run_id='fixture:1',observed_at=NOW,commit='test')
            content=''.join(p.read_text() for p in Path(tmp).iterdir() if p.is_file())
            self.assertNotIn('Скидка 17%',content);self.assertNotIn('DO_NOT_EXPORT',content)
            self.assertEqual(b['records'][0]['record_kind'],'source_observation')

    def test_artifact_tampering_and_wrong_run_block_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            stamp=datetime.now(timezone.utc).isoformat()
            c.collect(FakeReader(total=1),tmp,run_id='fixture:1',observed_at=stamp,commit='test')
            clock=datetime.now(timezone.utc)
            with self.assertRaises(ValueError):e.validate_bundle(tmp,run_id='wrong:1',commit='test',clock=clock)
            p=Path(tmp)/'page-0000.json';p.write_text(p.read_text()+' ')
            with self.assertRaises(ValueError):e.validate_bundle(tmp,run_id='fixture:1',commit='test',clock=clock)

    def test_policy_disallow_never_requests_api(self):
        r=FakeReader(total=1);original=r.read
        def read(url,body=None):
            if url==e.POLICY:r.calls+=1;return 'User-agent: *\nDisallow: /api/'
            return original(url,body)
        r.read=read
        with tempfile.TemporaryDirectory() as tmp:
            b=c.collect(r,tmp,run_id='fixture:1',observed_at=NOW,commit='test')
            self.assertEqual(len(r.queries),0);self.assertFalse(b['records'])


class TransportTests(unittest.TestCase):
    def test_exact_read_only_post_and_no_source_cookies(self):
        from test_free_access_probe import Response,page,USAGE
        get=Mock(return_value=Response(USAGE));post=Mock(return_value=page('{}',cost='25'))
        r=c.Reader('fixture-key',get=get,post=post,sleep=lambda _:None);r.preflight();r.read(e.API,e.query(0))
        kw=post.call_args.kwargs
        self.assertEqual(json.loads(kw['data']),e.query(0));self.assertEqual(kw['params']['url'],e.API)
        self.assertEqual(kw['params']['browser'],'false');self.assertEqual(kw['headers']['Ant-Content-Type'],'application/json')
        self.assertFalse(kw['allow_redirects']);self.assertNotIn('cookies',kw);self.assertNotIn('verify',kw)

    def test_paid_and_insufficient_balance_stop_before_post(self):
        from test_free_access_probe import Response,USAGE
        for change in ({'plan_name':'Paid'},{'remained_credits':299}):
            post=Mock();r=c.Reader('fixture-key',get=Mock(return_value=Response({**USAGE,**change})),post=post)
            with self.assertRaises(ProbeError):r.preflight()
            with self.assertRaises(ProbeError):r.read(e.API,e.query(0))
            post.assert_not_called()

    def test_quota_rate_and_cost_error_prevent_further_requests(self):
        from test_free_access_probe import Response,page,USAGE
        for response in (Response('{}',status=429),page('{}',cost='126'),page('{}',headers={'ant-original-header-retry-after':'30'})):
            post=Mock(return_value=response);r=c.Reader('fixture-key',get=Mock(return_value=Response(USAGE)),post=post)
            r.preflight()
            with self.assertRaises(ProbeError):r.read(e.API,e.query(0))
            with self.assertRaises(ProbeError):r.read(e.API,e.query(120))
            self.assertEqual(post.call_count,1)


class BudgetRoutingTests(unittest.TestCase):
    def test_separate_ekp_omits_only_replaced_route_and_enforces_smaller_budget(self):
        import free_access_probe as p
        from test_free_access_probe import ROOTS,KEY,response_for
        get=Mock(side_effect=response_for)
        with tempfile.TemporaryDirectory() as tmp:
            r=p.run(ROOTS,KEY,tmp,get=get,sleep=lambda _:None,separate_ekp=True)
            self.assertEqual(r['source_ids'],[s for s in p.SOURCE_IDS if s!='ekp'])
            self.assertEqual(r['maximum_estimated_credits'],94)
            self.assertFalse(any('ekp.spb.ru' in q.kwargs.get('params',{}).get('url','') for q in get.call_args_list))
        self.assertLessEqual((94+175)*31+300*5,10000)

    def test_five_source_report_requires_explicit_trusted_mode(self):
        from test_nordwind_catalog import document,report,CLOCK
        from free_catalog_bundle import build
        from free_access_probe import configured_roots
        roots=configured_roots(Path(__file__).parents[1]/'sources_normalized.json');html=document();r=report(html)
        r['source_ids'].remove('ekp')
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp,'nordwind.html').write_text(html)
            with self.assertRaises(ValueError):build(r,roots,tmp,run_id='fixture-run',attempt='2',commit='fixture-commit',clock=CLOCK)
            b=build(r,roots,tmp,run_id='fixture-run',attempt='2',commit='fixture-commit',clock=CLOCK,separate_ekp=True)
            self.assertEqual(len(b['sources']),5);self.assertNotIn('ekp',[s['source_id'] for s in b['sources']])

if __name__=='__main__':unittest.main()
