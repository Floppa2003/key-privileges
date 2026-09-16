"""Exercise the production JS with a virtual clock and delayed HTTP bodies."""
import subprocess
import unittest
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/'ekp_session_ui.js'
HARNESS=r'''
const assert=require('node:assert/strict'),fs=require('node:fs'),crypto=require('node:crypto');
const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
const source=fs.readFileSync(process.argv[1],'utf8');
async function run({total=245,delays=[1000],refuseAt=-1,bodyDelay=0}={}){
 let clock=Date.parse('2026-09-16T00:00:00Z'),id=0,output,finished=false,failure;
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
   const offset=request.pagination.offset;calls.push({offset,at:clock-beginning});
   assert.deepEqual(request.filters,{categories:[],name:'',qrDiscount:false,region:'98'});
   await wait(delays[Math.min(calls.length-1,delays.length-1)]-bodyDelay,options.signal);
   return {status:offset===refuseAt?403:200,url,headers:{has(){return false;}},text:async()=>{
     await wait(bodyDelay,options.signal);
     return JSON.stringify({total,offset,partners:Array.from({length:Math.min(120,total-offset)},(_,i)=>({
       id:String(offset+i),name:'Partner '+(offset+i),active:true,description_authorized:(offset+i)%3===0,
       categories:[],text:'Public',loyaltyDescription:'TERMS',discountScheme:'INSTRUCTIONS',accountToken:'PRIVATE'
     }))});
   }};
 };
 const document={title:'Партнеры',body:{textContent:'Партнеры',replaceChildren(node){output=JSON.parse(node.textContent);}},createElement(){return {};}};
 const hash={subtle:{digest:async(_,bytes)=>crypto.createHash('sha256').update(bytes).digest()}};
 const job=new AsyncFunction('Date','document','location','fetch','crypto','TextEncoder','AbortController','setTimeout','clearTimeout',source)(
   Clock,document,{href:'https://ekp.spb.ru/capabilities/loyalty/tiles?region=98'},fetch,hash,TextEncoder,AbortController,later,clear
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
 assert.equal(new Set(calls.map(x=>x.offset)).size,calls.length,'no read is retried');
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
   const r=await run({delays:[16000]});assert.equal(r.output.complete,false);assert.equal(r.calls.length,1);
   assert.deepEqual(r.output.errors,['source_headers_timeout']);assert.equal(r.elapsed,15000);
 }else if(mode==='body_timeout'){
   const r=await run({delays:[16000],bodyDelay:15500});assert.deepEqual(r.output.errors,['source_body_timeout']);
   assert.equal(r.elapsed,15000);assert.equal(r.calls.length,1);
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
    def test_unresponsive_headers_stop_without_retry(self):self.check_mode('timeout')
    def test_unresponsive_body_stop_without_retry(self):self.check_mode('body_timeout')
    def test_global_deadline_preserves_accepted_pages(self):self.check_mode('deadline')
    def test_http_refusal_is_not_a_timeout_retry(self):self.check_mode('refusal')
    def test_ordinary_full_pagination_still_works(self):self.check_mode('ordinary')

class TimingValidationTests(unittest.TestCase):
    def test_timing_metadata_has_no_unbounded_fields(self):
        import sys
        sys.path.insert(0,str(SCRIPT.parent))
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

if __name__=='__main__':unittest.main()
