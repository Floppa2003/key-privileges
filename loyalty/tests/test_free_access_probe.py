"""Mock only the HTTP boundary; real budget, parsing and policy code executes."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0, str(Path(__file__).parents[1]))
import free_access_probe as p

KEY = 'test_credential_never_publish_83942617'
ROOTS = [
    {'id':'ekp','url':'https://ekp.spb.ru/capabilities/loyalty/'},
    {'id':'nordwind','url':'https://nordwindairlines.ru/ru/club/partnerlist'},
    {'id':'coral','url':'https://coralbonus.ru/klub-privilegii/'},
    {'id':'coral_promo','url':'https://coralbonus.ru/promo/'},
    {'id':'rzd','url':'https://www.rzd-bonus.ru/?accessible=true'},
    {'id':'aeroflot','url':'https://www.aeroflot.ru/ru-ru/afl_bonus/partners'},
]
USAGE = {'plan_name':'Free','plan_total_credits':10000,'remained_credits':9999}

class Response:
    def __init__(self, body, status=200, cost='1', headers=None):
        self.body=(body if isinstance(body,str) else json.dumps(body)).encode(); self.status_code=status
        self.headers={'Ant-credits-cost':cost, **(headers or {})}
    def __enter__(self):return self
    def __exit__(self,*_):pass
    def iter_content(self,_):yield self.body


def page(body, origin=200, cost='10', headers=None):
    return Response(body,cost=cost,headers={'Ant-page-status-code':str(origin),**(headers or {})})


def document(url):
    return '<html data-loyalty-probe-location="'+url+'"><head><title>Партнёры</title></head><body><main><a href="/partner/123">Новый партнёр 17%</a></main></body></html>'


def response_for(url, **kwargs):
    if url.endswith('usage'):return Response(USAGE)
    params=kwargs['params']; target=params['url']
    if target.endswith('/robots.txt'):
        return page('User-agent: *\nAllow: /',cost='1')
    return page(document(target),headers={'ant-original-header-set-cookie':'PRIVATE_SESSION',
                                               'private-header':'PRIVATE_XHR'})


class FreeAccessTests(unittest.TestCase):
    def reader(self, get=None):
        r=p.FreeReader(KEY, ROOTS, get=get or Mock(side_effect=response_for))
        r.preflight();return r

    def test_missing_key_sends_nothing_and_does_not_reuse_old_html(self):
        get=Mock(side_effect=AssertionError('network must stay unused'))
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'ekp.html').write_text('stale response')
            (Path(tmp)/'unrelated.txt').write_text('keep')
            result=p.run(ROOTS,'',tmp,get=get)
            self.assertEqual(result['status'],'not_configured');self.assertEqual(result['published_records'],0)
            self.assertFalse((Path(tmp)/'ekp.html').exists());self.assertTrue((Path(tmp)/'unrelated.txt').exists())
            self.assertEqual(json.loads((Path(tmp)/'report.json').read_text()),result)
        get.assert_not_called()

    def test_free_plan_and_invalid_paid_exhausted_balances(self):
        self.assertEqual(p.free_plan(USAGE),9999)
        for update in ({'plan_name':'Enthusiast'},{'plan_name':'Trial'}, {'plan_total_credits':100000},
                       {'remained_credits':64}, {'remained_credits':True}, {'remained_credits':10001},
                       {'plan_name':None}):
            with self.subTest(update=update),self.assertRaises(p.ProbeError):p.free_plan({**USAGE,**update})

    def test_paid_plan_sends_only_usage_request(self):
        get=Mock(return_value=Response({**USAGE,'plan_name':'Startup'}))
        reader=p.FreeReader(KEY,ROOTS,get=get)
        with self.assertRaisesRegex(p.ProbeError,'free_plan_not_confirmed'):reader.preflight()
        with self.assertRaises(p.ProbeError):reader.read(ROOTS[0]['url'],browser=True)
        self.assertEqual(get.call_count,1)

    def test_exact_request_and_no_cookies_or_disable_tls_or_paid_upgrade(self):
        get=Mock(side_effect=response_for);r=self.reader(get)
        r.read(ROOTS[4]['url'],browser=True)
        url=get.call_args.args[0];kw=get.call_args.kwargs
        self.assertEqual(url,p.API+'general');self.assertEqual(kw['params']['url'],ROOTS[4]['url'])
        self.assertEqual(kw['params']['proxy_country'],'RU');self.assertEqual(kw['params']['proxy_type'],'datacenter')
        self.assertEqual(kw['params']['x-api-key'],KEY);self.assertNotIn('cookies',kw)
        self.assertNotIn('cookies',kw['params']);self.assertNotIn('verify',kw)
        self.assertFalse(kw['allow_redirects']);self.assertEqual(kw['timeout'],(10,75))

    def test_only_exact_roots_and_robots(self):
        r=self.reader()
        for url in ('https://foreign.example','http://ekp.spb.ru/',ROOTS[0]['url']+'?account=1',
                    'https://coralbonus.ru/login','https://coralbonus.ru/klub-privilegii/new'):
            with self.subTest(url=url),self.assertRaisesRegex(p.ProbeError,'outside'):r.read(url,browser=True)
        self.assertEqual(r.calls,0)

    def test_credit_cost_discrepancy_stops_further_calls(self):
        get=Mock(side_effect=[Response(USAGE),page('x',cost='125')])
        r=self.reader(get)
        with self.assertRaisesRegex(p.ProbeError,'credit_cost'):r.read(ROOTS[0]['url'],browser=True)
        with self.assertRaises(p.ProbeError):r.read(ROOTS[1]['url'],browser=True)
        self.assertTrue(r.halted);self.assertEqual(get.call_count,2)

    def test_no_automatic_retry_on_provider_errors(self):
        for status in (301,401,402,403,409,422,423,429,500):
            get=Mock(side_effect=[Response(USAGE),Response({'detail':KEY},status=status)])
            r=self.reader(get)
            with self.subTest(status=status),self.assertRaises(p.ProbeError) as caught:r.read(ROOTS[0]['url'],browser=True)
            self.assertNotIn(KEY,str(caught.exception));self.assertEqual(get.call_count,2)

    def test_source_429_and_retry_after_stop(self):
        for status,headers in ((429,{}),(200,{'ant-original-header-retry-after':'30'})):
            get=Mock(side_effect=[Response(USAGE),page('x',origin=status,headers=headers)])
            r=self.reader(get)
            with self.assertRaisesRegex(p.ProbeError,'origin_rate_limit'):r.read(ROOTS[0]['url'],browser=True)
            self.assertTrue(r.halted)

    def test_secret_echo_and_transport_error_are_redacted(self):
        for fail in (Response({'html':KEY},cost='10'),RuntimeError('request?key='+KEY)):
            get=Mock(side_effect=[Response(USAGE),fail]);r=self.reader(get)
            with self.assertRaises(p.ProbeError) as caught:r.read(ROOTS[0]['url'],browser=True)
            self.assertNotIn(KEY,str(caught.exception));self.assertTrue(r.halted)

    def test_missing_status_cannot_be_source_success(self):
        get=Mock(side_effect=[Response(USAGE),Response('unlabelled body',cost='10')]);r=self.reader(get)
        with self.assertRaisesRegex(p.ProbeError,'origin_status_missing'):r.read(ROOTS[0]['url'],browser=True)

    def test_budget_and_request_cap(self):
        r=self.reader()
        for _ in range(6):r.read(ROOTS[0]['url'],browser=True)
        with self.assertRaisesRegex(p.ProbeError,'per_run_limit'):r.read(ROOTS[0]['url'],browser=True)
        self.assertEqual(r.reserved,60)
        r=self.reader()
        for _ in range(11):r.read('https://ekp.spb.ru/robots.txt',browser=False)
        with self.assertRaisesRegex(p.ProbeError,'per_run_limit'):r.read('https://ekp.spb.ru/robots.txt',browser=False)

    def test_time_budget(self):
        r=self.reader();r.deadline=0
        with self.assertRaisesRegex(p.ProbeError,'probe_time_budget'):r.read(ROOTS[0]['url'],browser=True)
        self.assertEqual(r.calls,0)

    def test_sanitization_and_final_location(self):
        url=ROOTS[0]['url']
        raw=document(url).replace('</main>','<script>PRIVATE_JS</script><form>PRIVATE_FORM</form><div hidden>PRIVATE_HIDDEN</div><a href="/offer?token=PRIVATE_TOKEN#x" onclick="PRIVATE_JS">public</a></main>')
        clean,meta=p.sanitized_page(raw,url)
        self.assertNotIn('PRIVATE_',clean);self.assertNotIn('onclick',clean)
        self.assertNotIn('data-loyalty-probe-location',clean)
        self.assertFalse(meta['catalogue_complete']);self.assertEqual(meta['detail_pages_read'],0)
        for bad in ('https://evil.example/',None,'https://ekp.spb.ru/login'):
            with self.assertRaises(p.ProbeError):p.sanitized_page(document(str(bad)),url)
        _,meta=p.sanitized_page(document('https://ekp.spb.ru/capabilities/loyalty/tiles'),url)
        self.assertTrue(meta['final_url'].endswith('/tiles'))

    def test_configuration_not_unrelated_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'sources.json';path.write_text(json.dumps(ROOTS+[{'id':'other','url':'http://unrelated.example/'}]))
            self.assertEqual(p.configured_roots(path),ROOTS)
            path.write_text(json.dumps(ROOTS[:-1]+[ROOTS[0]]))
            with self.assertRaises(p.ProbeError):p.configured_roots(path)

    @unittest.skipUnless(importlib.util.find_spec('protego'), 'production dependency installed in Actions')
    def test_end_to_end_probe_uses_eleven_reads_and_no_account_material(self):
        get=Mock(side_effect=response_for)
        with tempfile.TemporaryDirectory() as tmp:
            report=p.run(ROOTS,KEY,tmp,get=get,sleep=lambda _:None)
            self.assertEqual(report['status'],'checked');self.assertEqual(report['target_requests'],11)
            self.assertEqual(report['reserved_credits'],65);self.assertEqual(report['published_records'],0)
            self.assertEqual(len(list(Path(tmp).glob('*.html'))),6)
            self.assertTrue(all(s['status']=='candidate_requires_review' for s in report['sources']))
            text=''.join(x.read_text() for x in Path(tmp).iterdir())
            for forbidden in (KEY,'PRIVATE_SESSION','PRIVATE_XHR'):self.assertNotIn(forbidden,text)
        self.assertEqual(get.call_count,12)

    @unittest.skipUnless(importlib.util.find_spec('protego'), 'production dependency installed in Actions')
    def test_real_robots_disallow_and_root_refusal_are_not_success(self):
        def get(url,**kw):
            target=kw['params'].get('url','')
            if target.endswith('ekp.spb.ru/robots.txt'):
                return page('User-agent: *\nDisallow: /',cost='1')
            if 'nordwind' in target and not target.endswith('robots.txt'):
                return page('<title>Access denied</title>')
            return response_for(url,**kw)
        with tempfile.TemporaryDirectory() as tmp:
            report=p.run(ROOTS,KEY,tmp,get=get,sleep=lambda _:None)
            self.assertEqual(report['sources'][0]['error'],'robots_disallow')
            self.assertEqual(report['sources'][1]['error'],'access_challenge')
            self.assertFalse((Path(tmp)/'ekp.html').exists());self.assertFalse((Path(tmp)/'nordwind.html').exists())

if __name__=='__main__':unittest.main()
