"""Main CLI integration uses the real checkpoint and publication boundaries."""
import asyncio,json,sys,tempfile,unittest,subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
sys.path.insert(0,str(Path(__file__).parents[1]))
import collect_normalized as collector
import collection_runtime as runtime
from normalized import make_offer
from sheets_normalized import prepare

URLS={'s7':'https://marketplace.s7.ru/partners/offer/fixture',
      'noname':'https://nonameburo.com/card#fixture'}
CFG=[{'id':sid,'name':sid,'url':url,'mode':'html','timeout_seconds':30}
     for sid,url in URLS.items()]
class BrowserContext:
    def __init__(self,browser):self.browser=browser
    async def __aenter__(self):return SimpleNamespace(chromium=SimpleNamespace(launch=AsyncMock(return_value=self.browser)))
    async def __aexit__(self,*args):return False

def record(cfg,now):
    row=make_offer(cfg['id'],'fixture','Fixture programme','Fixture partner','Скидка 10%',
                   cfg['url'],now)
    report,_=runtime.failed_result(cfg,now,'fixture_success')
    report.update(status='ok',normalized=1,discovered=1,failed=0,errors=[])
    return report,[row]

class EntryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.output=Path(self.temp.name);self.browser=SimpleNamespace(close=AsyncMock())
        self.enterContext(patch.object(sys,'argv',['collector','--out',str(self.output)]))
        self.enterContext(patch.object(collector,'select_sources',return_value=CFG))
        self.enterContext(patch.object(collector,'async_playwright',return_value=BrowserContext(self.browser)))
    def read(self):return json.loads((self.output/'normalized.json').read_text())
    async def test_main_preserves_completed_data_before_and_after_cancellation(self):
        ready=asyncio.Event()
        async def one(browser,cfg,now,limit):
            if cfg['id']=='s7':return record(cfg,now)
            ready.set();await asyncio.Event().wait()
        with patch.object(collector,'one',one):
            task=asyncio.create_task(collector.main());await ready.wait();await asyncio.sleep(.02)
            try:
                self.assertEqual(len(prepare(self.read())['parser_offers']),1)
            finally:
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):await task
        self.assertEqual(self.read()['collection_runtime']['state'],'cancelled')
        self.assertEqual(len(prepare(self.read())['parser_coverage']),2)
        self.browser.close.assert_awaited_once()
    async def test_main_cleanup_failure_does_not_destroy_completed_evidence(self):
        self.browser.close.side_effect=RuntimeError('fixture browser cleanup')
        with patch.object(collector,'one',AsyncMock(side_effect=lambda b,c,n,l:record(c,n))):
            with self.assertRaisesRegex(RuntimeError,'cleanup'):await collector.main()
        b=self.read();self.assertEqual(len(prepare(b)['parser_offers']),2)
        self.assertEqual(b['collection_runtime']['state'],'complete')
        self.assertTrue((self.output/'code_hashes.json').exists())
    async def test_main_soft_deadline_produces_publishable_partial_data_and_red_health(self):
        original=runtime.collect_batch
        async def short(*args,**kwargs):return await original(*args,**kwargs,run_timeout=.03)
        async def one(browser,cfg,now,limit):
            if cfg['id']=='s7':return record(cfg,now)
            await asyncio.Event().wait()
        with patch.object(collector,'one',one),patch.object(runtime,'collect_batch',short):
            await collector.main()
        b=self.read();self.assertEqual(b['collection_runtime']['state'],'deadline')
        self.assertEqual(len(prepare(b)['parser_offers']),1)
        script=Path(__file__).parents[1]/'source_lifecycle.py'
        proc=subprocess.run([sys.executable,str(script),'--input',str(self.output/'normalized.json'),
                             '--sources','s7,noname'],capture_output=True,text=True,timeout=10)
        self.assertEqual(proc.returncode,1,proc.stderr)
        self.assertFalse(json.loads(proc.stdout)['collection_execution']['healthy'])
        self.assertIn('noname',json.loads(proc.stdout)['collection_execution']['unfinished_sources'])
    async def test_missing_report_for_old_source_fails_real_health_cli(self):
        report,rows=record(CFG[0],'2026-09-23T00:00:00+00:00')
        runtime.atomic_json(self.output/'normalized.json',dict(schema_version=2,run_id='test:1',
            observed_at=report['observed_at'],sources=[report],records=rows))
        script=Path(__file__).parents[1]/'source_lifecycle.py'
        proc=subprocess.run([sys.executable,str(script),'--input',str(self.output/'normalized.json'),
                             '--sources','s7,noname'],capture_output=True,text=True,timeout=10)
        self.assertEqual(proc.returncode,1,proc.stderr)
        self.assertEqual(json.loads(proc.stdout)['collection_execution']['missing_sources'],['noname'])

if __name__=='__main__':unittest.main()
