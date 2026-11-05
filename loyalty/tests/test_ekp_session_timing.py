"""Exercise the production JS with a virtual clock and delayed HTTP bodies."""
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/'ekp_session_ui.js'
HARNESS=r'''
const assert=require('node:assert/strict'),fs=require('node:fs'),crypto=require('node:crypto');
const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
const source=fs.readFileSync(process.argv[1],'utf8');
async function run({total=245,delays=[1000],refuseAt=-1,bodyDelay=0,effects={},rootText='Партнеры',
                    pacingLag=0,start=Date.parse('2026-09-16T00:00:00Z')}={}){
 let clock=start,id=0,output,finished=false,failure;
 const beginning=clock,timers=new Map(),calls=[];
 class Clock extends Date{constructor(...args){super(...(args.length?args:[clock]));}static now(){return clock;}}
 const later=(fn,ms)=>{const n=++id;timers.set(n,{fn,due:clock+ms});return n;};
 const clear=n=>timers.delete(n);
 const wait=(ms,signal)=>new Promise((resolve,reject)=>{
   const n=later(()=>{signal?.removeEventListener('abort',abort);resolve();},ms);
   function abort(){clear(n);reject(new DOMException('Timed out','AbortError'));}
   if(signal?.aborted)abort();else signal?.addEventListener('abort',abort,{once:true});
 });
 const fetch=async(url,options)=>{
   assert.equal(url,'https://ekp.spb.ru/api/portal/loyalty/partners');
   assert.equal(options.credentials,'omit');assert.equal(options.redirect,'error');
   assert.equal(options.method,'POST');const request=JSON.parse(options.body);
   const offset=request.pagination.offset,effect=effects[calls.length]||{};
   assert.equal(request.pagination.limit,120);calls.push({offset,at:clock-beginning});
   assert.deepEqual(request.filters,{categories:[],name:'',qrDiscount:false,region:'98'});
   await wait(effect.headerDelay??(delays[Math.min(calls.length-1,delays.length-1)]-bodyDelay),options.signal);
   if(effect.headerError)throw new DOMException('SECRET_RESPONSE_DETAILS',effect.headerError);
   return {status:effect.status??(offset===refuseAt?403:200),url:effect.url??url,
     headers:{has(name){return name==='Retry-After'&&Boolean(effect.retryAfter);}},text:async()=>{
     await wait(effect.bodyDelay??bodyDelay,options.signal);
     if(effect.bodyError)throw new DOMException('SECRET_RESPONSE_DETAILS',effect.bodyError);
     if(effect.raw!==undefined)return effect.raw;
     const data={total,offset,partners:Array.from({length:Math.min(120,total-offset)},(_,i)=>({
       id:String(offset+i),name:'Partner '+(offset+i),active:true,description_authorized:(offset+i)%3===0,
       categories:[],text:'Public',loyaltyDescription:'TERMS',discountScheme:'INSTRUCTIONS',accountToken:'PRIVATE'
     }))};
     if(effect.mutate)effect.mutate(data);
     return JSON.stringify(data);
   }};
 };
 const document={title:'Партнеры',body:{textContent:rootText,replaceChildren(node){output=JSON.parse(node.textContent);}},createElement(){return {};}};
 const hash={subtle:{digest:async(_,bytes)=>crypto.createHash('sha256').update(bytes).digest()}};
 const job=new AsyncFunction('Date','document','location','fetch','crypto','TextEncoder','AbortController','setTimeout','clearTimeout',source)(
   Clock,document,{href:'https://ekp.spb.ru/capabilities/loyalty/tiles?region=98'},fetch,hash,TextEncoder,AbortController,
   (fn,ms)=>later(fn,ms+(ms===1100?pacingLag:0)),clear
 ).then(()=>{finished=true;},e=>{failure=e;finished=true;});
 for(let count=0;!finished&&count<1000;count++){
   await new Promise(setImmediate);
   if(finished)break;
   if(!timers.size)throw Error('virtual_clock_stalled');
   const [n,timer]=[...timers.entries()].sort((a,b)=>a[1].due-b[1].due||a[0]-b[0])[0];
   timers.delete(n);clock=timer.due;timer.fn();
 }
 assert.ok(finished,'virtual clock did not terminate');await job;if(failure)throw failure;
 assert.ok(output);assert.ok(clock-beginning<=43000,'global script deadline exceeded');
 assert.equal(output.requests.length,calls.length);assert.ok(calls.length<=11,'HTTP attempt budget exceeded');
 for(let i=1;i<calls.length;i++)assert.ok(calls[i].at-(Date.parse(output.requests[i-1].finishedAt)-beginning)>=1100,'request pacing shortened');
 assert.ok(!JSON.stringify(output).includes('SECRET_RESPONSE_DETAILS'),'raw exception details escaped');
 for(const page of output.pages)for(const row of page.partners){
   assert.equal(row.accountToken,undefined);
   if(row.description_authorized){assert.equal(row.loyaltyDescription,undefined);assert.equal(row.discountScheme,undefined);}
 }
 return {output,calls,elapsed:clock-beginning};
}
(async()=>{
 const mode=process.argv[2];
 if(mode==='slow_headers'){
   const r=await run({delays:[8000,1000]});assert.equal(r.output.complete,true,'an eight-second first response was discarded');
   assert.deepEqual(r.calls.map(x=>x.offset),[0,120,240]);assert.equal(r.output.requests[0].elapsedMs,8000);
 }else if(mode==='slow_body'){
   const r=await run({delays:[8000],bodyDelay:7500});assert.equal(r.output.complete,true,'slow response body was discarded');
   assert.equal(r.output.requests[0].elapsedMs,8000);
 }else if(mode==='timeout'){
   const r=await run({delays:[16000]});assert.equal(r.output.complete,false);assert.equal(r.calls.length,2);
   assert.deepEqual(r.calls.map(x=>x.offset),[0,0]);
   assert.deepEqual(r.output.errors,['source_headers_timeout']);assert.equal(r.elapsed,31100);
 }else if(mode==='body_timeout'){
   const r=await run({delays:[16000],bodyDelay:15500});assert.deepEqual(r.output.errors,['source_body_timeout']);
   assert.equal(r.elapsed,31100);assert.equal(r.calls.length,2);assert.deepEqual(r.calls.map(x=>x.offset),[0,0]);
 }else if(mode==='deadline'){
   const r=await run({total:1046,delays:[8000]});assert.equal(r.output.complete,false);
   assert.ok(r.output.pages.length>=4);assert.ok(r.output.pages.length<9);
   assert.ok(r.output.requests.at(-1).timeoutMs<15000);
 }else if(mode==='refusal'){
   const r=await run({refuseAt:120});assert.equal(r.output.pages.length,1);assert.equal(r.calls.length,2);
   assert.deepEqual(r.output.errors,['source_http_refusal']);assert.equal(r.output.requests[1].status,403);
 }else if(mode==='ordinary'){
   const r=await run({total:1046});assert.equal(r.output.complete,true);assert.equal(r.output.pages.length,9);
   assert.equal(r.output.requests.length,9);assert.equal(r.output.observed,1046);
 }else if(mode==='body_recovery'){
   const r=await run({effects:{1:{bodyError:'TypeError'}}});
   assert.equal(r.output.complete,true,'a transient body failure was not recovered');
   assert.deepEqual(r.calls.map(x=>x.offset),[0,120,120,240]);
   assert.deepEqual(r.output.pages.map(x=>x.offset),[0,120,240]);assert.equal(r.output.observed,245);
   assert.deepEqual(r.output.errors,[]);assert.equal(r.output.timingVersion,2);
   assert.deepEqual(r.output.requests.map(x=>x.attempt),[1,1,2,1]);
   assert.equal(r.output.requests[1].error,'source_body_type_error');assert.equal(r.output.requests[1].phase,'body');
   assert.equal(r.output.requests[1].outcome,'error');assert.equal(r.output.requests[2].outcome,'accepted');
   assert.equal(r.output.requests[2].sourceSha,r.output.pages[1].sourceSha);
 }else if(mode==='timeout_recovery'){
   for(const effect of [{headerDelay:16000},{headerDelay:500,bodyDelay:15500}]){
     const r=await run({effects:{0:effect}});assert.equal(r.output.complete,true);
     assert.deepEqual(r.calls.map(x=>x.offset),[0,0,120,240]);
     assert.equal(r.output.requests[0].error,effect.bodyDelay?'source_body_timeout':'source_headers_timeout');
   }
 }else if(mode==='body_exhausted'){
   const r=await run({effects:{1:{bodyError:'TypeError'},2:{bodyError:'TypeError'}}});
   assert.equal(r.output.complete,false);assert.deepEqual(r.calls.map(x=>x.offset),[0,120,120]);
   assert.equal(r.output.pages.length,1);assert.deepEqual(r.output.errors,['source_body_type_error']);
   assert.deepEqual(r.output.requests.slice(1).map(x=>x.phase),['body','body']);
   assert.deepEqual(r.output.requests.slice(1).map(x=>x.attempt),[1,2]);
 }else if(mode==='captured_failure_timing'){
   // The production failure timings are fixed; the subsequent successful reads
   // are simulated. This proves recovery can fit, not that the live API recovers.
   const r=await run({total:1019,delays:[2442,2174,2495,2033,14598,1000],effects:{4:{bodyError:'TypeError'}}});
   assert.equal(r.output.complete,true);assert.equal(r.output.observed,1019);
   assert.deepEqual(r.calls.map(x=>x.offset),[0,120,240,360,480,480,600,720,840,960]);
   assert.equal(r.elapsed,38642);assert.equal(r.output.requests[4].elapsedMs,14598);
 }else if(mode==='attempt_bound'){
   const r=await run({total:1201,effects:{0:{bodyError:'TypeError'},2:{bodyError:'TypeError'}}});
   assert.equal(r.calls.length,11);assert.equal(r.output.complete,false);assert.equal(r.output.observed,1080);
   assert.deepEqual(r.calls.map(x=>x.offset),[0,0,120,120,240,360,480,600,720,840,960]);
   assert.deepEqual(r.output.errors,['request_count_bound']);
 }else if(mode==='no_retry_room'){
   const r=await run({total:1046,delays:[8000],effects:{4:{headerDelay:5000,bodyError:'TypeError'}}});
   assert.equal(r.output.complete,false);assert.equal(r.calls.length,5);assert.equal(r.output.pages.length,4);
   assert.ok(r.output.errors.includes('source_body_type_error'));assert.ok(r.output.errors.includes('source_time_bound'));
 }else if(mode==='late_pacing'){
   const r=await run({total:1046,delays:[8000],pacingLag:5,effects:{4:{headerDelay:2980,bodyError:'TypeError'}}});
   assert.equal(r.output.complete,false);assert.equal(r.calls.length,5);assert.equal(r.output.pages.length,4);
   assert.equal(r.elapsed,40505);assert.deepEqual(r.output.errors,['source_body_type_error','source_time_bound']);
 }else if(mode==='terminal_transport'){
   for(const effect of [{status:403},{status:429},{retryAfter:true},{url:'https://ekp.spb.ru/cabinet/'}]){
     const r=await run({effects:{1:effect}});assert.equal(r.output.pages.length,1);
     assert.deepEqual(r.calls.map(x=>x.offset),[0,120]);assert.deepEqual(r.output.errors,['source_http_refusal']);
   }
   // redirect:'error' rejects redirects as TypeError before exposing a response.
   // Such an ambiguous headers failure must remain terminal, never be retried.
   const r=await run({effects:{1:{headerError:'TypeError'}}});
   assert.deepEqual(r.calls.map(x=>x.offset),[0,120]);assert.deepEqual(r.output.errors,['source_headers_type_error']);
 }else if(mode==='terminal_content'){
   const cases=[
     [{raw:'<html>captcha access denied</html>'},'source_json_invalid'],
     [{raw:'{"partners":'},'source_json_invalid'],
     [{mutate:d=>{d.offset=0;}},'page_schema_changed'],
     [{mutate:d=>{d.total=246;}},'catalogue_changed'],
     [{mutate:d=>{d.partners[0].id='0';}},'repeated_partner_ids'],
     [{mutate:d=>{d.partners[0].active='yes';}},'partner_schema_changed'],
     [{bodyError:'InvalidStateError'},'source_body_error']
   ];
   for(const [effect,expected]of cases){
     const r=await run({effects:{1:effect}});assert.deepEqual(r.calls.map(x=>x.offset),[0,120]);
     assert.equal(r.output.pages.length,1);assert.equal(r.output.complete,false);assert.deepEqual(r.output.errors,[expected]);
     assert.equal(r.output.requests[1].error,expected);assert.equal(r.output.requests[1].outcome,'error');
   }
   const r=await run({rootText:'captcha access denied'});assert.equal(r.calls.length,0);assert.deepEqual(r.output.errors,['restriction_document']);
 }else if(mode==='export_recovery'||mode==='export_partial'){
   const effects={1:{bodyError:'TypeError'}};if(mode==='export_partial')effects[2]={bodyError:'TypeError'};
   const r=await run({effects,start:Date.now()-60000});console.log(JSON.stringify(r.output));return;
 }else throw Error('unknown_test_mode');
 console.log('timing assertions passed: '+mode);
})().catch(e=>{console.error(e);process.exit(1);});
'''

class TimingTests(unittest.TestCase):
    def check_mode(self,mode):
        run=subprocess.run(['node','-e',HARNESS,str(SCRIPT),mode],capture_output=True,text=True,timeout=10)
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertIn('timing assertions passed',run.stdout)

    def test_slow_headers_under_request_allowance(self):self.check_mode('slow_headers')
    def test_slow_body_is_covered_by_same_timeout(self):self.check_mode('slow_body')
    def test_unresponsive_headers_stop_after_one_retry(self):self.check_mode('timeout')
    def test_unresponsive_body_stop_after_one_retry(self):self.check_mode('body_timeout')
    def test_global_deadline_preserves_accepted_pages(self):self.check_mode('deadline')
    def test_http_refusal_is_not_a_timeout_retry(self):self.check_mode('refusal')
    def test_ordinary_full_pagination_still_works(self):self.check_mode('ordinary')
    def test_body_failure_retries_the_same_page_once(self):self.check_mode('body_recovery')
    def test_header_and_body_timeout_can_recover_in_the_same_session(self):self.check_mode('timeout_recovery')
    def test_repeated_body_failure_preserves_prior_pages_and_error_phase(self):self.check_mode('body_exhausted')
    def test_captured_failure_timing_with_fast_recovery_fits_existing_deadline(self):self.check_mode('captured_failure_timing')
    def test_retries_consume_the_same_eleven_attempt_budget(self):self.check_mode('attempt_bound')
    def test_retry_is_not_started_without_time_for_pacing_and_a_request(self):self.check_mode('no_retry_room')
    def test_late_pacing_timer_preserves_error_when_retry_no_longer_fits(self):self.check_mode('late_pacing')
    def test_refusal_rate_limit_redirect_and_ambiguous_header_error_are_terminal(self):self.check_mode('terminal_transport')
    def test_challenge_schema_catalogue_and_duplicate_errors_are_terminal(self):self.check_mode('terminal_content')

class TimingValidationTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0,str(SCRIPT.parent))
        import ekp_session_collect
        self.collector=ekp_session_collect
        self.start=datetime(2026,9,16,tzinfo=timezone.utc)

    def attempt(self,offset,number,at,*,error=None,phase='body',duration=1000):
        item={'offset':offset,'attempt':number,'timeoutMs':15000,'elapsedMs':duration,
              'startedAt':(self.start+timedelta(milliseconds=at)).isoformat(),
              'finishedAt':(self.start+timedelta(milliseconds=at+duration)).isoformat(),
              'status':200,'phase':phase if error else 'accepted','outcome':'error' if error else 'accepted'}
        if error:item['error']=error
        else:item['sourceSha']='a'*64
        return item

    def recovery(self):
        return [self.attempt(0,1,0),self.attempt(120,1,2100,error='source_body_type_error'),
                self.attempt(120,2,4200),self.attempt(240,1,6300)]

    def check(self,items,end_ms=7300):
        return self.collector.checked_timings(items,self.start,self.start+timedelta(milliseconds=end_ms),version=2)

    def test_v2_timings_prove_a_single_recovered_attempt_and_contiguous_successes(self):
        items=self.recovery();self.assertEqual(self.check(items),items)

    def test_v2_rejects_unproved_retries_and_unbound_success(self):
        changes=[(2,{'attempt':3}),(2,{'offset':240}),(2,{'attempt':1}),
                 (2,{'sourceSha':'bad'}),(1,{'sourceSha':'b'*64}),
                 (1,{'phase':'headers'}),(1,{'error':'source_headers_type_error','phase':'headers'}),
                 (1,{'error':'source_http_refusal','phase':'headers','status':403}),
                 (2,{'phase':'body'}),(2,{'headers':{'cookie':'PRIVATE'}}),
                 (2,{'timeoutMs':15001}),(2,{'elapsedMs':True}),
                 (1,{'error':'SECRET: https://example.invalid/token'})]
        for index,change in changes:
            items=self.recovery();items[index].update(change)
            with self.subTest(index=index,change=change),self.assertRaises(ValueError):self.check(items)
        for field in ('attempt','phase','outcome','sourceSha'):
            items=self.recovery();items[2].pop(field)
            with self.subTest(missing=field),self.assertRaises(ValueError):self.check(items)

    def test_v2_rejects_short_pacing_extra_attempts_and_global_deadline_overrun(self):
        items=self.recovery();items[2]=self.attempt(120,2,4000)
        with self.assertRaises(ValueError):self.check(items)
        items=[self.attempt(120*i,1,2100*i) for i in range(12)]
        with self.assertRaises(ValueError):self.check(items,end_ms=24100)
        with self.assertRaises(ValueError):self.check(self.recovery(),end_ms=43001)
        items=[self.attempt(0,2,0)]
        with self.assertRaises(ValueError):self.check(items)
        items=[self.attempt(0,1,0),self.attempt(0,2,2100)]
        with self.assertRaises(ValueError):self.check(items)

    def test_v2_cannot_continue_after_a_second_failure_of_one_page(self):
        items=self.recovery();items[2]=self.attempt(120,2,4200,error='source_body_type_error')
        with self.assertRaises(ValueError):self.check(items)
        self.assertEqual(self.check(items[:3]),items[:3])

    def test_timing_metadata_has_no_unbounded_fields(self):
        from ekp_session_collect import checked_timings,instant
        start=instant('2026-09-16T00:00:00Z');end=instant('2026-09-16T00:00:08Z')
        item={'offset':0,'timeoutMs':15000,'elapsedMs':8000,
              'startedAt':start.isoformat(),'finishedAt':end.isoformat(),'status':200}
        self.assertEqual(checked_timings([item],start,end),[item])
        for change in ({'headers':{'cookie':'NO_EXPORT'}},{'elapsedMs':True},{'offset':120},
                       {'timeoutMs':20000},{'error':'https://private.example/token'},
                       {'finishedAt':'2099-01-01T00:00:00Z'}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                checked_timings([{**item,**change}],start,end)


class SessionContractTests(unittest.TestCase):
    def js_output(self,mode):
        completed=subprocess.run(['node','-e',HARNESS,str(SCRIPT),mode],capture_output=True,text=True,timeout=10)
        self.assertEqual(completed.returncode,0,completed.stderr)
        return json.loads(completed.stdout)

    def collect(self,obj,folder):
        sys.path.insert(0,str(SCRIPT.parent))
        import ekp_session_collect as c
        from test_ekp_session import Fake
        reader=Fake(obj)
        bundle=c.collect(reader,folder,run_id='retry-fixture:1',commit='fixture',
                         observed_at=(datetime.fromisoformat(obj['startedAt'].replace('Z','+00:00'))-timedelta(seconds=1)).isoformat())
        self.assertEqual((reader.calls,reader.reserved,reader.charged),(1,125,125))
        return c,bundle

    def test_real_js_recovery_is_independently_reconstructed(self):
        obj=self.js_output('export_recovery')
        with tempfile.TemporaryDirectory() as folder:
            c,bundle=self.collect(obj,folder)
            self.assertEqual(bundle['sources'][0]['status'],'ok');self.assertEqual(len(bundle['records']),245)
            audit=json.loads((Path(folder)/'report.json').read_text())
            self.assertEqual(audit['session']['timing_version'],2)
            self.assertEqual([x['attempt'] for x in audit['session']['requests']],[1,1,2,1])
            self.assertEqual(c.validate_session_bundle(folder,run_id='retry-fixture:1',commit='fixture',clock=datetime.now(timezone.utc)),bundle)

    def test_real_js_exhaustion_preserves_partial_and_precise_error(self):
        obj=self.js_output('export_partial')
        with tempfile.TemporaryDirectory() as folder:
            c,bundle=self.collect(obj,folder)
            self.assertEqual(bundle['sources'][0]['status'],'partial');self.assertEqual(len(bundle['records']),120)
            self.assertIn({'phase':'session','reason':'source_body_type_error'},bundle['sources'][0]['errors'])
            self.assertEqual(c.validate_session_bundle(folder,run_id='retry-fixture:1',commit='fixture',clock=datetime.now(timezone.utc)),bundle)

    def test_artifact_validation_binds_successful_attempt_to_accepted_page_and_version(self):
        obj=self.js_output('export_recovery')
        with tempfile.TemporaryDirectory() as folder:
            c,bundle=self.collect(obj,folder);self.assertEqual(len(bundle['records']),245)
            path=Path(folder)/'report.json';original=json.loads(path.read_text())
            for mutation in ('hash','offset','missing_success','version','legacy_hash','unknown_hash','unresolved_failure'):
                audit=copy.deepcopy(original);session=audit['session']
                if mutation=='hash':session['requests'][2]['sourceSha']='b'*64
                elif mutation=='offset':session['requests'][2]['offset']=240
                elif mutation=='missing_success':session['requests'].pop(2)
                elif mutation=='version':session['timing_version']=1
                elif mutation=='legacy_hash':audit['script_sha256']='f6d244c0b626e0c98bcfebb32805911dae76e0c6dfbf323a408d6976da78ee98'
                elif mutation=='unresolved_failure':
                    last=session['requests'][-1];start=datetime.fromisoformat(last['finishedAt'].replace('Z','+00:00'))+timedelta(seconds=1.1)
                    finish=start+timedelta(seconds=1)
                    session['requests'].append({'offset':360,'attempt':1,'timeoutMs':15000,'elapsedMs':1000,
                        'startedAt':start.isoformat(),'finishedAt':finish.isoformat(),'status':200,
                        'phase':'body','outcome':'error','error':'source_body_type_error'})
                    session['finished_at']=finish.isoformat()
                else:audit['script_sha256']='b'*64
                path.write_text(json.dumps(audit))
                with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                    c.validate_session_bundle(folder,run_id='retry-fixture:1',commit='fixture',clock=datetime.now(timezone.utc))

    def test_terminal_failure_cannot_disappear_from_the_session_report(self):
        obj=self.js_output('export_partial')
        with tempfile.TemporaryDirectory() as folder:
            c,_=self.collect(obj,folder);path=Path(folder)/'report.json';audit=json.loads(path.read_text())
            audit['session']['errors']=[];path.write_text(json.dumps(audit))
            with self.assertRaises(ValueError):
                c.validate_session_bundle(folder,run_id='retry-fixture:1',commit='fixture',clock=datetime.now(timezone.utc))

    def test_only_pinned_historical_script_accepts_legacy_timing_contract(self):
        obj=self.js_output('export_recovery')
        with tempfile.TemporaryDirectory() as folder:
            c,bundle=self.collect(obj,folder);self.assertEqual(len(bundle['records']),245)
            path=Path(folder)/'report.json';audit=json.loads(path.read_text());session=audit['session']
            session.pop('timing_version')
            session['requests']=[{k:v for k,v in item.items() if k not in ('attempt','phase','outcome','sourceSha')}
                                 for item in session['requests'] if item['outcome']=='accepted']
            audit['script_sha256']='f6d244c0b626e0c98bcfebb32805911dae76e0c6dfbf323a408d6976da78ee98'
            path.write_text(json.dumps(audit))
            self.assertEqual(c.validate_session_bundle(folder,run_id='retry-fixture:1',commit='fixture',clock=datetime.now(timezone.utc)),bundle)
            audit['script_sha256']=hashlib.sha256(SCRIPT.read_bytes()).hexdigest();path.write_text(json.dumps(audit))
            with self.assertRaises(ValueError):
                c.validate_session_bundle(folder,run_id='retry-fixture:1',commit='fixture',clock=datetime.now(timezone.utc))

if __name__=='__main__':unittest.main()
