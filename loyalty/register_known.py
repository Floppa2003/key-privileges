"""One-time checked code transfer; review workflow removes this after tests."""
import hashlib,subprocess
from pathlib import Path
before={'loyalty/known_rules.py':'d2d77bc7fdda2585d5b3175ec49ba753b4ab0566ecfcea3faf7b146a2fdc8930','loyalty/tests/test_public_product_rules.py':'ced3250ba6620d1ffcdf57ecd84d3e9dd56a19ae05b2d62c1a16b6f5524a7d79'}
for name,sha in before.items():
 if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=sha:raise ValueError('Unexpected baseline '+name)
p=Path('loyalty/known_rules.py');s=p.read_text().replace('import json,re','import asyncio,json,re\nimport requests',1)
s=s.replace("    if handler=='gpb':\n        options=[]", "    if handler=='gpb':\n        options=[];benefit_clauses=[]",1)
s=s.replace("            cost=match(r'далее [—-]", "            benefit_clauses.append(label+': '+rate[0]+'; '+cap[0])\n            cost=match(r'далее [—-]",1)
s=s.replace("        benefit='\\n'.join(o['evidence'] for o in options)", "        benefit='\\n'.join(benefit_clauses)",1)
helper='''def fetch_public_product(url):
    """The one reviewed public bank product; no redirect, login or refusal retry."""
    if url!='https://www.gazprombank.ru/personal/cards/7515685/':
        raise ValueError('unreviewed_public_product')
    from public_transport import check_response
    data=bytearray()
    try:
        with requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=(5,15),
                          allow_redirects=False,stream=True) as response:
            if response.status_code!=200:
                raise RuntimeError('http_'+str(response.status_code))
            if 'text/html' not in response.headers.get('Content-Type','').lower():
                raise RuntimeError('public_product_not_html')
            for block in response.iter_content(65536):
                data.extend(block)
                if len(data)>6000000:raise RuntimeError('source_response_too_large')
    except requests.RequestException:
        raise RuntimeError('public_product_transport_failed') from None
    body=data.decode('utf-8')
    check_response(200,body)
    return body


async def read_public_product(client,url):
    client.check_url(url)
    async with client.lock:
        await asyncio.sleep(client.request_interval)
        return await asyncio.to_thread(fetch_public_product,url)


'''
s=s.replace('async def collect_known_rules(client,cfg,report,now,limit):',helper+'async def collect_known_rules(client,cfg,report,now,limit):',1)
s=s.replace("        raw=await within_source_budget(client,lambda:client.read(cfg['url'],render=settings.get('render',True)))", "        if settings.get('handler')=='gpb':\n            raw=await within_source_budget(client,lambda:read_public_product(client,cfg['url']))\n        else:\n            raw=await within_source_budget(client,lambda:client.read(cfg['url'],render=settings.get('render',True)))",1)
p.write_text(s)
p=Path('loyalty/tests/test_public_product_rules.py');s=p.read_text()+r'''
class ProductTransportTests(unittest.IsolatedAsyncioTestCase):
 def old_refused_context(self):
  from types import SimpleNamespace
  async def fetch(*args,**kwargs):raise RuntimeError('http_403')
  return SimpleNamespace(request=SimpleNamespace(fetch=fetch))
 async def test_actual_rules_collector_uses_reviewed_anonymous_http_read(self):
  from unittest.mock import patch
  import requests
  from protego import Protego
  from public_transport import PublicSource
  from known_rules import collect_known_rules
  class Response:
   status_code=200
   headers={'Content-Type':'text/html; charset=utf-8'}
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def iter_content(self,size):yield sample().encode('utf8')
  client=PublicSource(None,URL);client.policy=Protego.parse('');client.request_interval=0;client.context=self.old_refused_context()
  report={'errors':[]}
  with patch.object(requests,'get',return_value=Response()) as get:
   try:rows=await collect_known_rules(client,{'id':'af_gpb_rules','url':URL},report,NOW,100)
   except Exception as exc:self.fail('Expected reviewed anonymous HTTP product content, got '+type(exc).__name__)
  self.assertEqual(len(rows),1)
  get.assert_called_once_with(URL,headers={'User-Agent':'Mozilla/5.0'},timeout=(5,15),allow_redirects=False,stream=True)
  self.assertEqual(rows[0]['details']['mileage_options'][1]['miles'],'2.5')
 async def test_http_refusal_is_not_retried_or_reported_as_a_product(self):
  from unittest.mock import patch
  import requests
  from protego import Protego
  from public_transport import PublicSource
  from known_rules import collect_known_rules
  class Response:
   headers={'Content-Type':'text/html'}
   def __init__(self,status):self.status_code=status
   def __enter__(self):return self
   def __exit__(self,*args):pass
  for status in (302,403,429):
   with self.subTest(status=status):
    client=PublicSource(None,URL);client.policy=Protego.parse('');client.request_interval=0;client.context=self.old_refused_context()
    with patch.object(requests,'get',return_value=Response(status)) as get:
     with self.assertRaises(RuntimeError):await collect_known_rules(client,{'id':'af_gpb_rules','url':URL},{'errors':[]},NOW,100)
     get.assert_called_once()
 async def test_reviewed_transport_still_obeys_source_policy(self):
  from unittest.mock import patch
  import requests
  from protego import Protego
  from public_transport import PublicSource
  from known_rules import collect_known_rules
  client=PublicSource(None,URL);client.policy=Protego.parse('User-agent: *\nDisallow: /')
  with patch.object(requests,'get') as get:
   with self.assertRaises(RuntimeError):await collect_known_rules(client,{'id':'af_gpb_rules','url':URL},{'errors':[]},NOW,100)
   get.assert_not_called()

class ProductMileageEvidenceTests(unittest.TestCase):
 def test_transfer_commission_is_not_extracted_as_a_loyalty_benefit(self):
  r=parse_known_rule('af_gpb_rules',sample(),URL,NOW)[0]
  self.assertNotIn('комиссия',r['benefit_text'])
  self.assertIn('комиссия 1,5%',r['conditions_text'])
  self.assertEqual(r['details']['mileage_options'][0]['miles'],'1.5')
''';p.write_text(s)
after={'loyalty/known_rules.py':'4ab582c9738775f6a368d73c486072dd837226dad1aa4b8d70387b86c9a92426','loyalty/tests/test_public_product_rules.py':'49ebe5c2d98dc7430fd55ed3d25e094454f46bf168c67446ad297698a4a7bfb9'}
for name,sha in after.items():
 if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=sha:raise ValueError('Result mismatch '+name)
subprocess.run(['git','add','--',*after],check=True)
print('Both files match the 335-test local revision.')
