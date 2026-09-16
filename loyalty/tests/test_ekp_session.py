"""One-browser production logic; synthetic HTTP boundary and real JS execution."""
import copy
import hashlib
import html
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).parents[1]))
import ekp_session_collect as c
import ekp_catalog as e
from free_access_probe import ProbeError
from test_ekp_api import raw


def session(total=245):
    stamp=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
    obj={'initialUrl':e.ROOT+'tiles?region=98','finalUrl':e.ROOT+'tiles?region=98',
         'startedAt':stamp,'finishedAt':stamp,'complete':True,'errors':[],'total':total,'observed':total,'pages':[]}
    for offset in range(0,total,120):
        rows=[raw(str(i),locked=i%3==0) for i in range(offset,min(offset+120,total))]
        obj['pages'].append({'request':e.query(offset),'total':total,'offset':offset,'partners':rows,
            'sourceSha':'a'*64,'status':200,'url':e.API,'completedAt':stamp})
    return obj


class Fake:
    def __init__(self,obj=None,policy='User-agent: *\nAllow: /'):
        self.obj=obj or session();self.policy=policy;self.calls=0;self.reserved=0;self.charged=0;self.balance=9000
        self.http=SimpleNamespace(halted=False);self.sleep=Mock()
    def preflight(self):pass
    def closing_balance(self):return self.balance-self.charged
    def read(self,url):
        self.calls+=1;cost=25 if url==e.POLICY else 125;self.reserved+=cost;self.charged+=cost
        return self.policy if url==e.POLICY else '<pre id="loyalty-session-api">'+html.escape(json.dumps(self.obj))+'</pre>'


def run(reader,tmp):
    observed=(datetime.now(timezone.utc)-timedelta(seconds=3)).isoformat()
    return c.collect(reader,tmp,run_id='fixture:1',observed_at=observed,commit='test')


class SessionTests(unittest.TestCase):
    def test_actual_acceptor_complete_pagination_and_reconstruction(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Fake();b=run(r,tmp)
            self.assertEqual(len(b['records']),245);self.assertEqual(b['sources'][0]['status'],'ok')
            self.assertEqual((r.calls,r.reserved),(2,150))
            self.assertEqual(c.validate_session_bundle(tmp,run_id='fixture:1',commit='test',clock=datetime.now(timezone.utc)),b)

    def test_source_refusal_after_good_pages_preserves_partial(self):
        obj=session();obj['pages']=obj['pages'][:1];obj['complete']=False;obj['errors']=['source_http_refusal']
        with tempfile.TemporaryDirectory() as tmp:
            b=run(Fake(obj),tmp)
            self.assertEqual(len(b['records']),120);self.assertEqual(b['sources'][0]['status'],'partial')
            self.assertIn({'phase':'session','reason':'source_http_refusal'},b['sources'][0]['errors'])

    def test_count_change_or_duplicate_does_not_certify_end(self):
        for mutation in ('total','id','request','url','completedAt'):
            obj=session();second=obj['pages'][1]
            if mutation=='total':second['total']+=1
            elif mutation=='id':second['partners'][0]['id']='0'
            elif mutation=='request':second['request']['pagination']['offset']=0
            elif mutation=='url':second['url']='https://example.org/'
            else:second['completedAt']='2099-01-01T00:00:00Z'
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as tmp:
                b=run(Fake(obj),tmp)
                self.assertEqual(len(b['records']),120);self.assertEqual(b['sources'][0]['status'],'partial')
                self.assertFalse(json.loads(b['sources'][0]['coverage'])['catalogue_pagination_complete'])

    def test_forged_complete_flag_not_accepted_as_full(self):
        obj=session();obj['pages']=obj['pages'][:1]
        with tempfile.TemporaryDirectory() as tmp:
            b=run(Fake(obj),tmp)
            self.assertEqual(b['sources'][0]['status'],'partial')
            self.assertIn('ekp_completion_count_mismatch',str(b['sources'][0]['errors']))

    def test_gated_terms_removed_before_saving_even_if_returned_by_api(self):
        obj=session(1);obj['pages'][0]['partners'][0].update(loyaltyDescription='SECRET_PRIVATE_RATE',discountScheme={'secret':'TOKEN'})
        with tempfile.TemporaryDirectory() as tmp:
            b=run(Fake(obj),tmp);files=''.join(p.read_text() for p in Path(tmp).iterdir())
            self.assertNotIn('SECRET_PRIVATE_RATE',files);self.assertNotIn('TOKEN',files);self.assertNotIn('DO_NOT_EXPORT',files)
            self.assertEqual(b['records'][0]['record_kind'],'source_observation')
            self.assertFalse(b['records'][0]['rates'])

    def test_bad_individual_record_preserves_other_rows_and_marks_gap(self):
        obj=session(2);obj['pages'][0]['partners'][1]['active']='yes'
        with tempfile.TemporaryDirectory() as tmp:
            b=run(Fake(obj),tmp);self.assertEqual(len(b['records']),1)
            self.assertEqual(b['sources'][0]['status'],'partial')
            meta=json.loads(b['sources'][0]['coverage']);self.assertTrue(meta['catalogue_pagination_complete']);self.assertFalse(meta['all_source_rows_mapped'])

    def test_foreign_root_or_unrecognized_region_rejected_before_mapping(self):
        for url in ('https://evil.example/','https://ekp.spb.ru/cabinet/','https://ekp.spb.ru/capabilities/loyalty/tiles?region=99'):
            obj=session();obj['finalUrl']=url
            with self.subTest(url=url),tempfile.TemporaryDirectory() as tmp:
                self.assertFalse(run(Fake(obj),tmp)['records'])

    def test_source_policy_disallow_or_new_pacing_rule_stops_browser(self):
        for policy in ('User-agent: *\nDisallow: /api/','User-agent: *\nCrawl-delay: 5'):
            with self.subTest(policy=policy),tempfile.TemporaryDirectory() as tmp:
                r=Fake(policy=policy);b=run(r,tmp);self.assertEqual(r.calls,1);self.assertFalse(b['records'])

    def test_artifact_script_and_completeness_tampering_rejected(self):
        for mutation in ('script_sha256','pagination_complete'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as tmp:
                run(Fake(),tmp);p=Path(tmp)/'report.json';a=json.loads(p.read_text())
                a[mutation]='0'*64 if mutation=='script_sha256' else False;p.write_text(json.dumps(a))
                with self.assertRaises(ValueError):c.validate_session_bundle(tmp,run_id='fixture:1',commit='test',clock=datetime.now(timezone.utc))

    def test_no_marker_never_publishes_navigation_html(self):
        r=Fake();old=r.read
        r.read=lambda url:old(url) if url==e.POLICY else '<html><title>Каталог</title><body>Загрузка</body></html>'
        with tempfile.TemporaryDirectory() as tmp:
            b=run(r,tmp);self.assertFalse(b['records']);self.assertEqual(b['sources'][0]['status'],'failed')


class ReaderTests(unittest.TestCase):
    def test_both_provider_requests_and_browser_script_are_bound(self):
        from test_free_access_probe import Response,page,USAGE
        get=Mock(side_effect=[Response(USAGE),page('User-agent: *\nAllow: /',cost='25'),page('public',cost='125')])
        r=c.Reader('fixture-key',get=get,sleep=Mock());r.preflight();r.read(e.POLICY);r.read(e.ROOT)
        self.assertEqual((r.calls,r.reserved,r.charged),(2,150,150))
        call=get.call_args.kwargs
        self.assertEqual(call['params']['url'],e.ROOT);self.assertEqual(call['params']['browser'],'true')
        self.assertEqual(call['params']['proxy_type'],'residential');self.assertNotIn('cookies',call)
        with self.assertRaises(ProbeError):r.read(e.ROOT)
        self.assertEqual(get.call_count,3)

    def test_policy_retry_and_single_browser_remain_under175(self):
        from test_free_access_probe import Response,page,USAGE
        get=Mock(side_effect=[Response(USAGE),Response('{}',status=404),page('User-agent: *\nAllow: /',cost='25'),page('public',cost='125')])
        r=c.Reader('fixture-key',get=get,sleep=Mock());r.preflight();c.policy_document(r,{});r.read(e.ROOT)
        self.assertEqual((r.calls,r.reserved,r.charged),(3,175,150));r.sleep.assert_any_call(10)
        with self.assertRaises(ProbeError):r.read(e.POLICY)

    def test_paid_low_balance_quota_and_cost_are_terminal(self):
        from test_free_access_probe import Response,page,USAGE
        for usage in ({**USAGE,'plan_name':'Paid'},{**USAGE,'remained_credits':174}):
            get=Mock(return_value=Response(usage));r=c.Reader('fixture-key',get=get)
            with self.assertRaises(ProbeError):r.preflight()
            self.assertEqual(get.call_count,1)
        for bad in (Response('{}',status=429),page('body',cost='200'),page('body',headers={'ant-original-header-retry-after':'5'})):
            get=Mock(side_effect=[Response(USAGE),bad]);r=c.Reader('fixture-key',get=get,sleep=Mock());r.preflight()
            with self.assertRaises(ProbeError):r.read(e.ROOT)
            with self.assertRaises(ProbeError):r.read(e.POLICY)
            self.assertEqual(get.call_count,2)

    def test_browser_refusal_cannot_be_retried_or_route_to_other_url(self):
        from test_free_access_probe import Response,USAGE
        get=Mock(side_effect=[Response(USAGE),Response('{}',status=423)])
        r=c.Reader('fixture-key',get=get,sleep=Mock());r.preflight()
        with self.assertRaises(ProbeError):r.read(e.ROOT)
        with self.assertRaises(ProbeError):r.read(e.ROOT)
        with self.assertRaises(ProbeError):r.read(e.API)
        self.assertEqual(get.call_count,2)


class ActualJavaScriptTests(unittest.TestCase):
    def test_real_script_paginate_without_credentials_or_protected_output(self):
        # The actual browser program runs in Node with only the fetch/DOM boundary
        # replaced. This checks query offsets, delay, explicit source refusals and
        # privacy behavior, not merely that the JS text mentions an API name.
        harness=r'''
const assert=require('node:assert/strict'),fs=require('node:fs'),crypto=require('node:crypto');
const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
const source=fs.readFileSync(process.argv[1],'utf8');
async function run(refuse){
 const calls=[],delays=[];let output;
 const document={title:'Партнеры',body:{textContent:'Партнеры',replaceChildren(n){output=JSON.parse(n.textContent);}},createElement(){return {};}};
 const fetch=async(url,options)=>{assert.equal(url,'https://ekp.spb.ru/api/portal/loyalty/partners');
  assert.equal(options.credentials,'omit');assert.equal(options.redirect,'error');assert.equal(options.method,'POST');
  const req=JSON.parse(options.body);calls.push(req);const o=req.pagination.offset;
  assert.deepEqual(req.filters,{categories:[],name:'',qrDiscount:false,region:'98'});
  if(refuse&&o===120)return {status:403,url,headers:{has(){return false;}}};
  const rows=Array.from({length:Math.min(120,245-o)},(_,i)=>({id:String(o+i),name:'Partner '+(o+i),active:true,
   description_authorized:(o+i)%3===0,categories:[],text:'Public',loyaltyDescription:'PRIVATE_IF_LOCKED',discountScheme:'CODE_IF_LOCKED',accountToken:'MUST_NOT_LEAVE'}));
  return {status:200,url,headers:{has(){return false;}},text:async()=>JSON.stringify({total:245,offset:o,partners:rows})};
 };
 const timer=(fn,ms)=>{if(ms<=1100){delays.push(ms);return setTimeout(fn,0);}return setTimeout(fn,ms);};
 await new AsyncFunction('document','location','fetch','crypto','TextEncoder','AbortController','setTimeout','clearTimeout',source)(
   document,{href:'https://ekp.spb.ru/capabilities/loyalty/tiles?region=98'},fetch,crypto.webcrypto,TextEncoder,AbortController,timer,clearTimeout);
 assert.equal(output.complete,!refuse);assert.equal(output.pages.length,refuse?1:3);
 assert.deepEqual(calls.map(x=>x.pagination.offset),refuse?[0,120]:[0,120,240]);
 for(const p of output.pages)for(const row of p.partners){assert.equal(row.accountToken,undefined);if(row.description_authorized){assert.equal(row.loyaltyDescription,undefined);assert.equal(row.discountScheme,undefined);}}
 if(refuse)assert.deepEqual(output.errors,['source_http_refusal']);else assert.equal(output.observed,245);
 assert.ok(delays.every(ms=>ms===1100));
}
(async()=>{await run(false);await run(true);console.log('actual JS pagination/privacy/refusal assertions passed');})().catch(e=>{console.error(e);process.exit(1);});
'''
        completed=subprocess.run(['node','-e',harness,str(c.SCRIPT)],text=True,capture_output=True,timeout=20)
        self.assertEqual(completed.returncode,0,completed.stderr)
        self.assertIn('assertions passed',completed.stdout)

if __name__=='__main__':unittest.main()
