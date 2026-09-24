"""Exercise the production orchestration boundary, including cancellation and disk failure."""
import asyncio, copy, json, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
sys.path[:0] = [str(Path(__file__).parents[1]), str(Path(__file__).parent)]
from collection_runtime import atomic_json, collect_batch, execution_health, failed_result
from test_normalized_sync import bundle
from sheets_normalized import prepare

NOW = '2026-09-23T00:00:00+00:00'
CONFIGS = [{'id':sid,'name':sid,'url':'https://example.test/'+sid} for sid in ('s7','slow','last')]


def good(cfg):
    b=bundle();r=b['records'][0];report=b['sources'][0]
    r['observed_at']=NOW;report.update(observed_at=NOW,source_id=cfg['id'])
    return report,[r]


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'normalized.json';self.snapshots=[]
    def save(self, results, meta):
        b={'schema_version':2,'run_id':'test:1','observed_at':NOW,
           'sources':[r for r,_ in results],'records':[r for _,rows in results for r in rows],
           'collection_runtime':meta}
        prepare(b)
        atomic_json(self.path,b);self.snapshots.append(copy.deepcopy(b))
    def latest(self):return json.loads(self.path.read_text())

    async def test_completed_source_is_durable_while_other_read_still_hangs(self):
        started=asyncio.Event();stop=asyncio.Event()
        async def run(cfg):
            if cfg['id']=='s7':return good(cfg)
            started.set();await stop.wait();return failed_result(cfg,NOW,'fixture_failure')
        task=asyncio.create_task(collect_batch(CONFIGS[:2],run,lambda c:2,self.save,NOW))
        await started.wait()
        for _ in range(100):
            if self.latest()['records']:break
            await asyncio.sleep(.001)
        self.assertFalse(task.done());self.assertEqual(len(self.latest()['records']),1)
        self.assertEqual(self.latest()['collection_runtime']['state'],'running')
        stop.set();await task
        self.assertTrue(execution_health(self.latest(),['s7','slow'])['healthy'])

    async def test_deadline_preserves_completed_records_and_reports_all_selected(self):
        cancelled=asyncio.Event()
        async def run(cfg):
            if cfg['id']=='s7':return good(cfg)
            try:await asyncio.Event().wait()
            finally:cancelled.set()
        results=await collect_batch(CONFIGS,run,lambda c:2,self.save,NOW,run_timeout=.05,concurrency=1)
        b=self.latest();self.assertEqual([r['source_id'] for r,_ in results],['s7','slow','last'])
        self.assertEqual(len(b['records']),1);self.assertTrue(cancelled.is_set())
        self.assertEqual([r['collection_state'] for r in b['sources']],['finished','interrupted','not_started'])
        self.assertFalse(execution_health(b,['s7','slow','last'])['healthy'])
        self.assertEqual(len(prepare(b)['parser_offers']),1)
        self.assertEqual(b['records'][0]['observed_at'],NOW)

    async def test_external_cancellation_is_propagated_after_checkpoint(self):
        ready=asyncio.Event()
        async def run(cfg):
            if cfg['id']=='s7':return good(cfg)
            ready.set();await asyncio.Event().wait()
        task=asyncio.create_task(collect_batch(CONFIGS[:2],run,lambda c:2,self.save,NOW))
        await ready.wait();await asyncio.sleep(.01);task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertEqual(len(self.latest()['records']),1)
        self.assertEqual(self.latest()['collection_runtime']['state'],'cancelled')

    async def test_longest_budget_starts_first_but_reports_keep_config_order(self):
        calls=[]
        async def run(cfg):calls.append(cfg['id']);return failed_result(cfg,NOW,'fixture_failure')
        results=await collect_batch(CONFIGS,run,lambda c:3 if c['id']=='last' else 1,self.save,NOW,concurrency=1)
        self.assertEqual(calls,['last','s7','slow'])
        self.assertEqual([r['source_id'] for r,_ in results],['s7','slow','last'])

    async def test_waiting_in_queue_does_not_consume_source_timeout(self):
        # Assert timer placement, not that a shared CI runner responds within 30ms.
        # The real deadline/cancellation behavior is exercised by separate tests.
        gate = asyncio.Semaphore(1)
        queued = asyncio.Event()
        admitted = set()
        timers = []
        original_wait_for = asyncio.wait_for
        case = self

        class AdmissionGate:
            async def __aenter__(self):
                if gate.locked():
                    queued.set()
                await gate.acquire()
                admitted.add(asyncio.current_task())
                return self

            async def __aexit__(self, *exc):
                admitted.remove(asyncio.current_task())
                gate.release()

        async def observe_timer(awaitable, *, timeout):
            if asyncio.current_task() not in admitted:
                awaitable.close()
                case.fail('Source timer started before queue admission')
            timers.append(timeout)
            return await awaitable

        async def run(cfg):
            if cfg['id'] == 's7':
                await queued.wait()
                self.assertEqual(timers, [.2])
                return good(cfg)
            return failed_result(cfg, NOW, 'fixture_completed')

        with patch('collection_runtime.asyncio.Semaphore', return_value=AdmissionGate()), \
                patch('collection_runtime.asyncio.wait_for', side_effect=observe_timer):
            await original_wait_for(collect_batch(CONFIGS[:2], run,
                lambda c: .2 if c['id'] == 's7' else .03, self.save, NOW,
                concurrency=1), timeout=5)
        self.assertTrue(queued.is_set())
        self.assertEqual(timers, [.2, .03])
        self.assertEqual(self.latest()['sources'][1]['coverage'], 'fixture_completed')

    async def test_source_timeout_does_not_discard_another_source(self):
        async def run(cfg):
            if cfg['id']=='s7':return good(cfg)
            await asyncio.Event().wait()
        await collect_batch(CONFIGS[:2],run,lambda c:.02,self.save,NOW)
        self.assertEqual(len(self.latest()['records']),1)
        self.assertEqual(self.latest()['sources'][1]['coverage'],'source_timeout')

    async def test_unexpected_worker_error_is_sanitized_and_does_not_abort_siblings(self):
        async def run(cfg):
            if cfg['id']=='s7':return good(cfg)
            raise ValueError('SECRET source URL or cookie')
        await collect_batch(CONFIGS[:2],run,lambda c:1,self.save,NOW)
        b=self.latest();self.assertEqual(len(b['records']),1)
        self.assertNotIn('SECRET',self.path.read_text())
        self.assertFalse(execution_health(b,['s7','slow'])['healthy'])

    async def test_mismatched_source_result_is_not_accepted(self):
        async def run(cfg):return good(CONFIGS[0])
        await collect_batch(CONFIGS[:2],run,lambda c:1,self.save,NOW)
        self.assertEqual(len(self.latest()['records']),1)
        self.assertEqual(self.latest()['sources'][1]['coverage'],'collection_worker_exception')

    async def test_disk_error_cancels_workers_and_preserves_previous_checkpoint(self):
        original=self.save
        def save(results,meta):
            if any(rows for _,rows in results):raise OSError('disk full')
            original(results,meta)
        async def run(cfg):
            if cfg['id']=='s7':return good(cfg)
            await asyncio.Event().wait()
        with self.assertRaises(OSError):await collect_batch(CONFIGS[:2],run,lambda c:1,save,NOW)
        self.assertEqual(self.latest()['collection_runtime']['state'],'running')

    async def test_empty_or_duplicate_configuration_is_rejected_before_writes(self):
        async def run(cfg):self.fail('Must not run')
        for configs in ([],[CONFIGS[0],CONFIGS[0]]):
            with self.assertRaises(ValueError):await collect_batch(configs,run,lambda c:1,self.save,NOW)
        self.assertFalse(self.path.exists())


class CheckpointTests(unittest.TestCase):
    def test_failed_replace_keeps_previous_complete_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'normalized.json';atomic_json(path,{'old':1})
            with patch('collection_runtime.os.replace',side_effect=OSError('full')):
                with self.assertRaises(OSError):atomic_json(path,{'new':2})
            self.assertEqual(json.loads(path.read_text()),{'old':1})
            self.assertFalse(path.with_name(path.name+'.tmp').exists())
    def test_failed_serialization_does_not_damage_previous_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'normalized.json';atomic_json(path,{'old':1})
            with self.assertRaises(TypeError):atomic_json(path,{'new':object()})
            self.assertEqual(json.loads(path.read_text()),{'old':1})
    def test_health_detects_missing_legacy_source_outside_three_rewards(self):
        b=bundle();self.assertTrue(execution_health(b,['s7'])['healthy'])
        self.assertFalse(execution_health(b,['s7','noname'])['healthy'])
    def test_runtime_count_drift_or_running_checkpoint_cannot_be_green(self):
        b=bundle();b['sources'][0]['collection_state']='finished'
        for state,count in [('running',1),('complete',0)]:
            b['collection_runtime']={'version':1,'state':state,'selected_sources':1,'completed_sources':count}
            self.assertFalse(execution_health(b,['s7'])['healthy'])

if __name__=='__main__':unittest.main()
