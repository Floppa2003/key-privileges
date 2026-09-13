"""Exercise real S7/RGO collectors at the slow I/O boundary, not a mock collector."""
import asyncio
import copy
import json
import sys
import time
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
import collect_normalized as collect
from fixtures import S7, fixture

NOW='2026-09-13T10:40:00+00:00'

def state_html(state):
    return '<script id="__NEXT_DATA__">'+json.dumps({'props':{'initialState':state}})+'</script>'

class S7Client:
    def __init__(self, error=None):
        self.calls=[]; self.cancelled=False; self.error=error
        self.deadline=time.monotonic()+5.03
    async def read(self,url,**kwargs):
        self.calls.append(url)
        if '/category/' in url:
            return state_html({'offers':{'partners':{'offers':[
                {'code':c,'priorityRulesUrl':'https://marketplace.s7.ru/partners/offer/'+c}
                for c in ('flowwow','slow','untouched')]}}})
        if url.endswith('/slow'):
            if self.error: raise self.error
            try: await asyncio.Event().wait()
            finally:self.cancelled=True
        data=copy.deepcopy(S7)
        if not url.endswith('/flowwow'):
            obj=data['offer']['partners'].pop('flowwow')
            obj['offer']['code']='untouched'
            data['offer']['partners']['untouched']=obj
        return state_html(data)

class RgoLocator:
    def __init__(self,selector):self.selector=selector
    @property
    def first(self):return self
    async def count(self):return 3 if self.selector=='.loyalty-card' else 0

class RgoPage:
    def locator(self,selector):return RgoLocator(selector)
    async def content(self):
        return ''.join('<a class="loyalty-card__link" href="'+name+'/"></a>'
                       for name in ('good','slow','untouched'))

class RgoClient:
    def __init__(self,error=None):
        self.page=RgoPage();self.calls=[];self.cancelled=False;self.error=error
        self.deadline=time.monotonic()+5.03
    async def read(self,url,**kwargs):
        self.calls.append(url)
        if url.endswith('/loyalty-program/'):return await self.page.content()
        if url.endswith('/slow/'):
            if self.error:raise self.error
            try:await asyncio.Event().wait()
            finally:self.cancelled=True
        return fixture('rgo_detail.html')

class CollectorDeadlineTests(unittest.IsolatedAsyncioTestCase):
    async def collect_rows(self,kind,client):
        root=('https://marketplace.s7.ru/partners/category/retail' if kind=='s7'
              else 'https://rgo.ru/membership/loyalty-program/')
        report={'errors':[]}
        try:
            rows=await asyncio.wait_for(getattr(collect,'collect_'+kind)(client,{'url':root},report,NOW,10),.2)
        except asyncio.TimeoutError:
            self.fail('Whole source lost already collected rows to a stalled detail')
        return rows,report

    async def test_s7_retains_prior_records_before_deadline_and_cancels_stalled_io(self):
        client=S7Client();rows,report=await self.collect_rows('s7',client)
        self.assertEqual([r['native_id'] for r in rows],['flowwow'])
        self.assertTrue(client.cancelled)
        self.assertEqual(report['discovered'],3)
        self.assertEqual(report['errors'][-1]['reason'],'source_time_budget_reached')
        self.assertFalse(any('untouched' in u for u in client.calls))

    async def test_rgo_retains_prior_records_before_deadline_and_cancels_stalled_io(self):
        client=RgoClient();rows,report=await self.collect_rows('rgo',client)
        self.assertEqual(len(rows),1);self.assertTrue(client.cancelled)
        self.assertEqual(report['discovered'],3)
        self.assertEqual(report['errors'][-1]['reason'],'source_time_budget_reached')
        self.assertFalse(any('untouched' in u for u in client.calls))

    async def test_s7_rate_limit_stops_next_card_without_losing_prior_rows(self):
        client=S7Client(RuntimeError('http_429'));rows,report=await self.collect_rows('s7',client)
        self.assertEqual(len(rows),1)
        self.assertFalse(any('untouched' in u for u in client.calls),'Source continued issuing requests after rate limit')

    async def test_rgo_rate_limit_stops_next_card_without_losing_prior_rows(self):
        client=RgoClient(RuntimeError('http_429'));rows,report=await self.collect_rows('rgo',client)
        self.assertEqual(len(rows),1)
        self.assertFalse(any('untouched' in u for u in client.calls),'Source continued issuing requests after rate limit')

    async def test_leaf_timeout_is_not_mislabeled_as_source_deadline(self):
        client=S7Client(TimeoutError());client.deadline=time.monotonic()+50
        rows,report=await self.collect_rows('s7',client)
        self.assertEqual(len(rows),2)
        self.assertEqual(report['errors'][0]['reason'],'TimeoutError')

    async def test_expired_budget_does_not_start_another_detail(self):
        client=S7Client();client.deadline=time.monotonic()-1
        report={'errors':[]}
        try:
            rows=await asyncio.wait_for(collect.collect_s7(client,{'url':'https://marketplace.s7.ru/partners/category/retail'},report,NOW,10),.2)
        except RuntimeError as exc:
            self.assertEqual(str(exc),'source_time_budget_reached');return
        except asyncio.TimeoutError:
            self.fail('Expired source still performed a hanging detail read')
        self.assertEqual(rows,[])
        self.assertFalse(any('/offer/' in u for u in client.calls))
