"""Exercise the actual HTTP->browser policy fallback, never bypass a refusal."""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).parents[1]))
import free_access_probe as p
from test_free_access_probe import KEY, ROOTS, USAGE, Response, page, document, response_for

URL = 'https://ekp.spb.ru/robots.txt'

def browser_policy(target=URL, rules='User-agent: *\nAllow: /'):
    return '<html data-loyalty-probe-location="'+target+'"><body><pre>'+rules+'</pre></body></html>'

class PolicyFallbackTests(unittest.TestCase):
    def reader(self, responses):
        get=Mock(side_effect=[Response(USAGE)]+responses)
        r=p.FreeReader(KEY, ROOTS, get=get);r.preflight()
        return r,get

    def test_real_unreachable_http_then_real_browser_document(self):
        r,get=self.reader([Response('unreachable',status=404),page(browser_policy())])
        info={};status,raw,cost=p.read_policy(r,URL,info)
        self.assertEqual(status,200);self.assertIn('User-agent:',raw)
        self.assertEqual(info['method'],'browser_after_unreachable_http')
        self.assertEqual([x.kwargs['params'].get('browser') for x in get.call_args_list],[None,'false','true'])
        self.assertEqual(r.calls,2);self.assertEqual(r.reserved,11);self.assertEqual(r.known_charged_credits,10)

    def test_ordinary_http_success_has_no_second_request(self):
        r,get=self.reader([page('User-agent: *\nAllow: /',cost='1')])
        info={};p.read_policy(r,URL,info)
        self.assertEqual(info['method'],'http');self.assertEqual(get.call_count,2)

    def test_auth_quota_challenge_and_rate_failures_are_not_retried(self):
        for status in (401,403,409,423,429):
            r,get=self.reader([Response('refused',status=status)])
            with self.subTest(status=status),self.assertRaises(p.ProbeError):p.read_policy(r,URL,{})
            self.assertEqual(get.call_count,2)

    def test_second_unreachable_does_not_loop(self):
        r,get=self.reader([Response('unreachable',status=404),Response('unreachable',status=404)])
        with self.assertRaises(p.ProbeError):p.read_policy(r,URL,{})
        self.assertEqual(get.call_count,3)

    def test_browser_redirect_or_missing_identity_is_not_policy(self):
        for body in (browser_policy('https://foreign.example/'),'<pre>User-agent: *\nAllow: /</pre>'):
            r,get=self.reader([Response('unreachable',status=404),page(body)])
            with self.assertRaisesRegex(p.ProbeError,'final_location'):p.read_policy(r,URL,{})

    def test_actual_target_403_remains_an_origin_response_not_network_error(self):
        r,get=self.reader([page('Forbidden',origin=403,cost='1')])
        status,_,_=p.read_policy(r,URL,{})
        self.assertEqual(status,403);self.assertEqual(get.call_count,2)

    @unittest.skipUnless(importlib.util.find_spec('protego'),'pinned dependency in Actions')
    def test_fallback_disallow_still_prevents_root_fetch(self):
        def respond(url,**kw):
            target=kw['params'].get('url','')
            if target==URL:
                if kw['params']['browser']=='false':return Response('unreachable',status=404)
                return page(browser_policy(rules='User-agent: *\nDisallow: /'))
            return response_for(url,**kw)
        get=Mock(side_effect=respond)
        with tempfile.TemporaryDirectory() as tmp:
            report=p.run(ROOTS,KEY,tmp,get=get,sleep=lambda _:None)
            self.assertEqual(report['sources'][0]['error'],'robots_disallow')
            self.assertEqual(report['sources'][0]['robots']['method'],'browser_after_unreachable_http')
            self.assertFalse((Path(tmp)/'ekp.html').exists())
        self.assertNotIn(ROOTS[0]['url'],[x.kwargs['params'].get('url') for x in get.call_args_list])

if __name__=='__main__':unittest.main()
