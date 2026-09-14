"""One-time, checksum-bound development patch. Removed before integration."""
from pathlib import Path
from hashlib import sha256
import json
HASHES={
'loyalty/known_rules.json':('f0bbc6a180cfb4d359a5196348fcb07491dcfc885397d540d97d9636f833c3dc','a224fd2cb012147f13a3ee9ee55d6764da2cbe406e25def7ba987e8ac75e3f05'),
'loyalty/known_rules.py':('aad2232692646bb520c5dd83bcfa74b106b54c6ae288624d1ce3d90b4279fa54','7b6e9c8b5a972b51004e14d3b4db8c5a56bdbe8bfa11f5a36ef51985a0106904'),
'loyalty/partner_pages.py':('8165d2285cada1f1c046535e5fb227ad53b7c28560378d428b02531a00201f4d','4a79559a85456db0328332cc399cb474dc9e3c6124c4cef15be21cf8f836aff6'),
'loyalty/sources_normalized.json':('b8513e0fcc8dd49f6c71694d463f6e7a995299dfa38b01ff3a0173b6a3f5f4e7','d8ea59e7fd741cf07bfaa6e11b981b876d97f8b703c87dc6254444ff15670f75'),
'loyalty/normalized.py':('56d9068b0acdb742c7e992822ca506b304e83324698fcabaaa8011d82c16c28a','19d2d41a686447da7158e3571503705050004ecb58a62198c3581ec57412ffea'),
'loyalty/recovered_sources.py':('d7f199714896b517c938c40ce386c2872c7564e4aca4ba73259f04d02759bbdb','4d96ce1e21462e74479aa6b36a79abf4a05a425d5422391a1a4a98a9eb11ad07'),
'loyalty/tests/test_known_rules.py':('143ae6409a8d50bcea787a9f85fa66c73b4e702290603ae09b1efb1ce1067057','cf92b8eeb6b58e5ff0b7666429a6810dd4a42c06e212fb879a44ef67f6d3c281')}
for name,(before,after) in HASHES.items():
    if sha256(Path(name).read_bytes()).hexdigest()!=before:raise SystemExit('unexpected patch input: '+name)
root=Path('loyalty')
p=root/'known_rules.json';cfg=json.loads(p.read_text())
changes={'ekp_sfera_rules':['Единая карта','косметология'],
'rgo_headquarters_rules':['Перечень льготных категорий','скидку','члены Русского географического общества'],
 't2_mixx_rules':['MiXX M','Федеральный'], 'utair_family_rules':['Семья','счетов','Как минимум'],
 'mir_101_rules':['Бронируйте с умом','Срок проведения Акции'], 'mir_aeroexpress_rules':['Аэроэкспресс','СБП'],
 'promomiles_otello_rules':['Отелло','промокод'], 'ural_carsgo_rules':['Крылья']}
for key,value in changes.items():cfg[key]['required']=value
cfg['promomiles_otello_rules']['title']='Правила промокода Отелло'
cfg['azimut_earning_rules']['required']=[x.replace('Пример 1','Пример') for x in cfg['azimut_earning_rules']['required']]
p.write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n')
p=root/'sources_normalized.json';cfg=json.loads(p.read_text())
for x in cfg:
    if x['id']=='promomiles_otello_rules':x['name']='Отелло — правила промокода Аэрофлот Бонус'
p.write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n')
p=root/'known_rules.py';s=p.read_text()
s=s.replace("if len(cards)!=4:raise ValueError('smartavia_four_plan_cards_required')", "if not 1<=len(cards)<=20:raise ValueError('smartavia_plan_count_outside_bound')")
s=s.replace("r'Тариф (1\\+[0-3])'", "r'Тариф (1\\+(?:0|[1-9]\\d*))(?=\\s|[.,:;!?]|$)'")
s=s.replace("'additional_travelers':int(key[-1])", "'additional_travelers':int(key.split('+')[1])")
s=s.replace("    if labels!={'1+0','1+1','1+2','1+3'}:raise ValueError('smartavia_plan_set_changed')\n",'')
p.write_text(s)
p=root/'partner_pages.py';s=p.read_text()
old="        base=re.search(r'(?:Участники[^.]*?)?1 мил[ьяю][^.]*?за каждые 100 рублей[^.]*\\.',flat,re.I)"
new="""        # Identify the undated accrual clause by its role, not today's rate.
        # Dated campaign sentences cannot supply a fallback base rate.
        rate_pattern=r'\\d+(?:[.,]\\d+)?\\s+мил[ьяюие]\\w*.*?за каждые\\s+\\d[\\d \\u00a0\\u202f]*(?:[.,]\\d+)?\\s+(?:руб\\w*|₽)'
        period_pattern=r'\\b(?:период|акци\\w*|срок)\\b|(?<!\\d)\\d{1,2}[./]\\d{1,2}[./]\\d{4}'
        base=[sentence for sentence in re.split(r'(?<=[.!?])\\s+',flat)
              if re.search(rate_pattern,sentence,re.I) and not re.search(period_pattern,sentence,re.I)]"""
assert old in s;s=s.replace(old,new)
s=s.replace("if not base:raise ValueError('Askona base accrual sentence changed; review required')", "if len(base)!=1:raise ValueError('Askona undated base accrual missing or ambiguous')")
p.write_text(s)
p=root/'recovered_sources.py';s=p.read_text();s=s.replace("body.startswith('1000 Бесплатно')","n.select_one('[class*=\"Container-footer-new\"]') is not None");p.write_text(s)
p=root/'tests/test_known_rules.py';s=p.read_text().replace("('Тариф 1+2','Тариф 1+7')", "('Тариф 1+2','Тариф X+2')");p.write_text(s)
p=root/'normalized.py';s=p.read_text().replace("'2.9.0'","'2.9.1'");p.write_text(s)
for name,(before,after) in HASHES.items():
    if sha256(Path(name).read_bytes()).hexdigest()!=after:raise SystemExit('unexpected patch output: '+name)
Path(__file__).unlink()
print('Seven exact code/config updates materialized; development helper removed.')
