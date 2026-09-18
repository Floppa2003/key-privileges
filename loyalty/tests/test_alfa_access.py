"""Scoped trust and zero-private-output contract for the owner-requested bank URL."""
import asyncio,hashlib,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import alfa_access as a
import requests
from test_hse_alumni import NOW

class Response:
    def __init__(self,status=200,headers=None,body=b'public CA'):
        self.status_code=status;self.headers=headers or {};self.body=body
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def iter_content(self,n):yield self.body
    @property
    def text(self):raise AssertionError('No bank body may be read')
class Session:
    def __init__(self,response):
        self.response=response;self.calls=[];self.trust_env=True
        class Cookies:
            def clear(self):pass
        self.cookies=Cookies()
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def get(self,url,**kwargs):self.calls.append(('GET',url,kwargs));return Response()
    def head(self,url,**kwargs):
        self.calls.append(('HEAD',url,kwargs))
        assert isinstance(kwargs['verify'],str) and Path(kwargs['verify']).exists()
        if isinstance(self.response,Exception):raise self.response
        return self.response

class AccessTests(unittest.TestCase):
    def invoke(self,response):
        session=Session(response)
        with patch.object(a.requests,'Session',return_value=session),patch.object(a,'CA_FILES',[(a.CA_FILES[0][0],hashlib.sha256(b'public CA').hexdigest())]):
            result=a.inspect_access(a.ROOT)
        return result,session
    def test_auth_redirect_is_not_followed_or_exported(self):
        result,s=self.invoke(Response(302,{'Location':'https://'+a.AUTH_HOST+a.AUTH_PATH+'?private=DO_NOT_EXPORT','Set-Cookie':'SECRET'}))
        self.assertEqual(result['access_state'],'bank_authentication_redirect')
        self.assertNotIn('DO_NOT_EXPORT',json.dumps(result));self.assertNotIn('SECRET',json.dumps(result))
        self.assertEqual([c[0] for c in s.calls],['GET','HEAD']);self.assertFalse(s.trust_env)
        for method,url,kwargs in s.calls:self.assertFalse(kwargs['allow_redirects']);self.assertIsNot(kwargs['verify'],False)
        self.assertFalse(result['catalogue_collected']);self.assertFalse(result['response_body_read'])
        self.assertFalse(Path(s.calls[1][2]['verify']).exists())
    def test_unexpected_host_and_path_not_copied(self):
        for location in ('https://other.test/PRIVATE','https://'+a.AUTH_HOST+'/PRIVATE','http://'+a.AUTH_HOST+a.AUTH_PATH):
            result,s=self.invoke(Response(302,{'Location':location}))
            self.assertEqual(result['access_state'],'unexpected_redirect_not_followed');self.assertNotIn('PRIVATE',json.dumps(result))
    def test_head_200_is_not_collected_cashback(self):
        result,s=self.invoke(Response());self.assertFalse(result['catalogue_collected'])
        self.assertEqual(result['access_state'],'head_200_catalogue_body_not_read')
    def test_wrong_url_never_contacts_any_host(self):
        with patch.object(a.requests,'Session') as session:
            with self.assertRaises(ValueError):a.inspect_access(a.ROOT+'?account=private')
            session.assert_not_called()
    def test_changed_ca_fails_before_bank(self):
        s=Session(Response())
        with patch.object(a.requests,'Session',return_value=s):
            with self.assertRaisesRegex(RuntimeError,'official_ca_digest_changed'):a.inspect_access(a.ROOT)
        self.assertEqual(len(s.calls),1)
    def test_rate_limit_and_certificate_error_do_not_retry(self):
        for response,reason in [(Response(302,{'Retry-After':'10'}),'alfa_rate_limited'),(Response(429),'alfa_rate_limited'),(requests.exceptions.SSLError('SECRET'),'alfa_certificate_verification_failed')]:
            with self.assertRaisesRegex(RuntimeError,reason):self.invoke(response)
    def test_real_dispatcher_reports_failure_without_browser_or_offers(self):
        import collect_normalized as c
        cfg={'id':'alfa_only_partner_offers','name':'Alfa','mode':'probe','url':a.ROOT,'timeout_seconds':45}
        async def exercise():
            with patch.object(a,'inspect_access',return_value={'access_state':'bank_authentication_redirect','catalogue_collected':False}),patch.object(c,'PublicSource') as browser:
                report,rows=await c.one(None,cfg,NOW,200)
                browser.assert_not_called()
            self.assertEqual(rows,[]);self.assertEqual(report['status'],'failed')
            self.assertEqual(report['errors'][0]['reason'],'alfa_bank_authentication_redirect')
            self.assertFalse(json.loads(report['coverage'])['catalogue_collected'])
        asyncio.run(exercise())

if __name__=='__main__':unittest.main()
