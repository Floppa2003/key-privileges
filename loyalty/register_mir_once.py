"""Apply the reviewed routing regression fix, then removed by the review job."""
from pathlib import Path
import hashlib,subprocess
before={'loyalty/collect_normalized.py':'8fba0102ca316ccfb3f7899a03c73e785de1e3659d2f204e4415da35fa06b909','loyalty/tests/test_mir_regions.py':'6b7761b110e634a4eaffc08916d86663ca91a8fd64ac03a2545a98b6bcaae461'}
for name,sha in before.items():
 if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=sha:raise ValueError('Unexpected baseline '+name)
p=Path('loyalty/collect_normalized.py');s=p.read_text();assert s.count('from mir_source import collect_mir')==1;p.write_text(s.replace('from mir_source import collect_mir','from mir_regions import collect_mir'))
p=Path('loyalty/tests/test_mir_regions.py');p.write_text(p.read_text()+'''
class ProductionRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_main_dispatch_uses_both_region_reads_not_compatibility_alias(self):
        import collect_normalized as production
        self.assertIsNotNone(region)
        seen=[]
        class Source:
            policy=None
            def __init__(self,*args):pass
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
        async def read(client,cfg,key,now,limit):
            seen.append(key)
            return [offer()],{'errors':[],'discovered':1,'coverage':'fixture','discovered_urls':[URL]}
        cfg={'id':'mir','mode':'mir','name':'Привет! / Мир / СБП','url':'https://vamprivet.ru/promo/'}
        with patch.object(production,'PublicSource',Source),patch.object(region,'read_region',read):
            report,rows=await production.one(None,cfg,NOW,500)
        self.assertEqual(seen,['msk','spb'])
        self.assertEqual(report['status'],'ok',report)
        self.assertEqual(len(rows),1)
        self.assertEqual(len(rows[0]['details']['catalog_listings']),2)
''')
after={'loyalty/collect_normalized.py':'bc7215f663313a98d8e1bc60f4de137c99752046bf8dcb2ffc6efc1b4d06d479','loyalty/tests/test_mir_regions.py':'3551ac620383fffacc58e958a78419dcd359d7ab13da8e0a87922f0ccb4cba55'}
for name,sha in after.items():
 if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=sha:raise ValueError('Unexpected fixed bytes '+name)
subprocess.run(['git','add','--',*after],check=True)
print('Routing fix and production-path regression test match local 257-test revision.')
