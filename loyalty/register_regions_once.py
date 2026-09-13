"""One-time source registration; review CI removes this helper before integration."""
from pathlib import Path
import hashlib

before={
 'loyalty/t2_source.py':'33c9fa48de79dee0eb79c07ab8ee9ae419e7aa27d15ad1de58a5a50bd13812d2',
 'loyalty/collect_normalized.py':'1b78057a43d1969d93c1009829dc92569e15db468fb54f1b614a416973922b62',
 'loyalty/normalized.py':'02830537ba87507decc48cb05cdbce42255465f51b0dcd13d770a3690635e761',
 'loyalty/public_transport.py':'efc8a781516cefc1e0eae94bb3d4bcb710cde8a69aa7ccef656ac237f601c0fb'}
for name,sha in before.items():
 if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=sha:raise ValueError('Unexpected baseline '+name)
p=Path('loyalty/t2_source.py');s=p.read_text()
s=s.replace("ROOT='https://msk.t2.ru/bolshe/offers'", "ROOT='https://msk.t2.ru/bolshe/offers'\nREGIONS = {\n    'msk': {'region': 'Москва и область', 'source_url': ROOT},\n    'spb': {'region': 'Санкт-Петербург и Ленинградская область',\n            'source_url': 'https://spb.t2.ru/bolshe/offers'},\n}")
s=s.replace('def catalog_records(data,observed_at):\n', "def catalog_records(data,observed_at,*,region_key='msk'):\n    if region_key not in REGIONS:raise ValueError('unknown_t2_region')\n    region=REGIONS[region_key]\n")
s=s.replace('company,benefit,ROOT,observed_at,',"company,benefit,region['source_url'],observed_at,")
s=s.replace("'region':'Москва и область','source_scope':", "'region':region['region'],'source_scope':")
a=s.index('async def collect_t2(');b=s.index('\ndef period(',a);s=s[:a]+s[b:];p.write_text(s)
p=Path('loyalty/collect_normalized.py');s=p.read_text().replace('from t2_source import collect_t2','from t2_regions import collect_t2').replace('                await client.robots()\n                mode=',"                if cfg['mode']!='t2':await client.robots()\n                mode=");p.write_text(s)
p=Path('loyalty/normalized.py');s=p.read_text().replace("VERSION = '2.3.4'","VERSION = '2.4.0'").replace("    HOSTS[_source]=['msk.t2.ru']","    HOSTS[_source]=['msk.t2.ru']\nHOSTS['t2_bolshe'].append('spb.t2.ru')");p.write_text(s)
p=Path('loyalty/public_transport.py');p.write_text(p.read_text().replace("12 if self.host == 'msk.t2.ru' else 0", "12 if self.host in ('msk.t2.ru','spb.t2.ru') else 0"))
after={
 'loyalty/t2_source.py':'9277dc45cbf8e14977de51260139b67b5b00be7679dbad92ae810dd2148d24f5',
 'loyalty/collect_normalized.py':'bebb3aedd776fcf5df438a3e00493302465c7541a1152e167132e9f43d8c889c',
 'loyalty/normalized.py':'78695a52d7cad9cdd98af567fdd875edc5c423cf8b8ef446053c29294a819643',
 'loyalty/public_transport.py':'fcdefa809b6f55c17fca9c7c63f56630e3ce183f7570feb6184584f982b835e7'}
for name,sha in after.items():
 if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=sha:raise ValueError('Unexpected final bytes '+name)
print('Four registered source files match locally tested bytes.')
