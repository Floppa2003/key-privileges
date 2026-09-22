"""Temporary hash-guarded installation; remove after feature verification."""
from pathlib import Path
import hashlib,json,sys
from bs4 import BeautifulSoup
ROOT=Path('loyalty')
EXPECTED={'collect_normalized.py':'1be213d8487cfdab1ef1e9857e0e1d0582b37c600ad0fcaad201c75a96b1bb35','normalized.py':'e3c118af3f157145e0a3a6c14b3ddfc64d61574ea486529c8bc60e3cca067102','unified_normalization.py':'a6cd63a6aa506dacab7c93f425810ad1adf1b964835a3e1211e6ac96358ad671','sources_normalized.json':'f2e8d567e04265d90e4b95d11a5108e735c136077db0ed3a8dd0698920953223'}
for name,digest in EXPECTED.items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name

def change(name,old,new):
    p=ROOT/name;s=p.read_text();assert s.count(old)==1,(name,old);p.write_text(s.replace(old,new))

change('collect_normalized.py','from konsierge_source import collect as collect_konsierge','from konsierge_source import collect as collect_konsierge\nfrom backit_catalog import collect as collect_backit\nfrom avolta_source import collect as collect_avolta\nfrom mantera_source import collect as collect_mantera')
change('collect_normalized.py',"if mode=='greatlist':records=await collect_greatlist(client,cfg,report,now,limit)","if mode=='backit':records=await collect_backit(client,cfg,report,now,limit)\n                elif mode=='avolta':records=await collect_avolta(client,cfg,report,now,limit)\n                elif mode=='mantera':records=await collect_mantera(client,cfg,report,now,limit)\n                elif mode=='greatlist':records=await collect_greatlist(client,cfg,report,now,limit)")
change('normalized.py',"HOSTS['greatlist_alfa_only']=['greatlist.ru']","HOSTS['greatlist_alfa_only']=['greatlist.ru']\nHOSTS['backit_public']=['backit.me']\nHOSTS['club_avolta_public']=['www.clubavolta.com']\nHOSTS['mantera_moments']=['lk.manteratravel.ru']")
change('normalized.py',"    if r['source_id']=='greatlist_alfa_only':","    if r['source_id'] in ('backit_public','club_avolta_public','mantera_moments'):\n        from public_reward_projection import validate_record\n        validate_record(r)\n    if r['source_id']=='greatlist_alfa_only':")
change('unified_normalization.py',"    if 'tsum_evidence' in d:","    if d.get('retrieval_method')=='source_owned_public_rewards_v1':\n        from public_reward_projection import project_common\n        return project_common(raw,n,benefit,condition,code)\n    if 'tsum_evidence' in d:")
change('backit_catalog.py','async def read(url):return await within_source_budget(client,lambda:client.read(url))','async def read(url,render=False):return await within_source_budget(client,lambda:client.read(url,render=render))')
change('backit_catalog.py','seed=await read(ROOT);','seed=await read(ROOT,render=True);')
change('backit_catalog.py',"inventory(await read(ROOT+'?page='+str(page)),page)","inventory(await read(ROOT+'?page='+str(page),render=True),page)")
p=ROOT/'sources_normalized.json';cfg=json.loads(p.read_text())
assert not set(x['id'] for x in cfg)&{'backit_public','club_avolta_public','mantera_moments'}
cfg.extend([
 {'id':'backit_public','name':'Backit — денежный кешбэк','mode':'backit','url':'https://backit.me/ru/cashback/shops','timeout_seconds':1000,'detail_limit':1200,'coverage_scope':'public_ru_shop_tariffs_not_marketplace_product_level_or_financial_acquisition_ads'},
 {'id':'club_avolta_public','name':'Club Avolta — публичные партнёры','mode':'avolta','url':'https://www.clubavolta.com/ru','timeout_seconds':420,'coverage_scope':'source_linked_russian_partner_cards_not_personal_eligibility'},
 {'id':'mantera_moments','name':'Мантера Моменты — публичные уровни','mode':'mantera','url':'https://lk.manteratravel.ru/faq','timeout_seconds':90,'coverage_scope':'five_public_tiers_pilot_hotels_accommodation_only'}])
p.write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n')

roots=list(map(Path,sys.argv[1:]));assert len(roots)==2
dest=ROOT/'tests/fixtures_live/affordable';dest.mkdir(exist_ok=True)
selected=[(1,'backit-page2.html','backit-list.html'),(0,'backit-1.html','backit-kuper.html'),(0,'backit-2.html','backit-sportmaster.html'),(0,'mantera_faq-0.html','mantera-faq.html'),(1,'avolta-sample-2.html','avolta-list.html'),(1,'avolta-sample-6.html','avolta-plaza.html'),(1,'avolta-sample-7.html','avolta-dragonpass.html')]
for idx,source,target in selected:
    s=BeautifulSoup((roots[idx]/source).read_text(),'html.parser')
    nodes=s.select('main#Main') if source.startswith('avolta') else [s.body]
    out=BeautifulSoup('<html><body></body></html>','html.parser')
    for n in nodes:
        assert n is not None;out.body.append(BeautifulSoup(str(n),'html.parser'))
    for n in out.select('script,style,noscript,svg,iframe,img,picture'):
        if n.parent is not None:n.decompose()
    (dest/target).write_text('<!-- Public source DOM excerpt; captured 2026-09-22; no authenticated user data. -->\n'+str(out))
print('Reviewed routing and seven public DOM fixtures prepared')
