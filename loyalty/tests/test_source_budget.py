import asyncio,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
import collect_normalized as c
class SourceBudgetTests(unittest.IsolatedAsyncioTestCase):
 async def test_queue_wait_does_not_spend_source_network_budget(self):
  run=getattr(c,'bounded_source',None)
  self.assertTrue(callable(run),'Missing source budget after queue admission')
  sem=asyncio.Semaphore(1);await sem.acquire();calls=[]
  async def work():calls.append('started');return 42
  task=asyncio.create_task(run(work,sem,0.02))
  await asyncio.sleep(0.04)
  self.assertFalse(task.done(),'Queued source timed out before admission')
  sem.release()
  self.assertEqual(await task,42);self.assertEqual(calls,['started'])
 async def test_admitted_stalled_source_is_cancelled(self):
  run=getattr(c,'bounded_source',None)
  self.assertTrue(callable(run),'Missing bounded source execution')
  stopped=asyncio.Event()
  async def stall():
   try:await asyncio.Event().wait()
   finally:stopped.set()
  with self.assertRaises(asyncio.TimeoutError):await run(stall,asyncio.Semaphore(1),0.01)
  self.assertTrue(stopped.is_set())
if __name__=='__main__':unittest.main()
