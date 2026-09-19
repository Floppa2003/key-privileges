"""Temporary branch-only installation of reviewed edits; remove before release."""
import hashlib,html,io,json,os,zipfile
from pathlib import Path
import requests
from bs4 import BeautifulSoup
ROOT=Path('loyalty')
EXPECTED={
'partner_pages.json':'db589d14be7ee775740f67429530c45aa5b1cff39c8f0d61294234c02223128d',
'partner_pages.py':'d29f8aa923c91069d03f32dc4b2d303a97ead4d5a4502cf863d23e8706faafa8',
'announcements.py':'75591953a656c7151bce7f90a24fc378a8e2ef32fc8502e66cdffab5a3ace1e8',
'normalized.py':'81209863e491f1d6949ff1152bfebc655ef32efb38f0a1e21fa67a0748ce515b',
'sources_normalized.json':'3e854684ec0b5087b80519c3d63855a70b60e0ce8964836e95af1f202cc64456',
'unified_normalization.py':'faa648f75fef318b6f04e7672438195f2a2e319031928e63fd97837721997793'}
for name,digest in EXPECTED.items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest, name

def replace(name,old,new):
    p=ROOT/name;s=p.read_text();assert s.count(old)==1,(name,old);p.write_text(s.replace(old,new))

p=ROOT/'partner_pages.json';v=json.loads(p.read_text())
v['alfa_only_tsum']={'url':'https://www.tsum.ru/lp/alfa-only/','program':'Alfa Only','partner':'ЦУМ / ДЛТ','category':'Покупки','parser':'tsum_alfa'}
p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
replace('partner_pages.py',"    blocks=required(soup,cfg['selectors']);terms=content(blocks)","    if cfg.get('parser') == 'tsum_alfa':\n        from tsum_alfa import extract_tsum\n        return extract_tsum(source,soup,url,observed_at,cfg)\n    blocks=required(soup,cfg['selectors']);terms=content(blocks)")
replace('announcements.py',"'bspb_announcements':'mybspb'}","'bspb_announcements':'mybspb', 'alfa_only_announcements':'aaa_only'}")
replace('announcements.py',"    if cfg['id'] == 'rzd_announcements':",r"""    if cfg['id'] == 'alfa_only_announcements':
        # Channel provenance is not customer eligibility. Do not turn a random
        # privilege wheel, deposit yield or lifestyle story into a guaranteed perk.
        if re.search(r'барабан|лотере|разыгр|опрос|голосован', body, re.I):
            return False
        context = re.search(r'Alfa\s+Only|Альфа[ -]Тревел', body, re.I)
        reward = re.search(r'скидк|к[еэ]шб[еэ]к|промокод|комплимент', body, re.I)
        return bool(context and reward and (NUMERIC_BENEFIT.search(body) or re.search(r'комплимент', body, re.I)))
    if cfg['id'] == 'rzd_announcements':""")
replace('normalized.py',"HOSTS['bspb_announcements']=['t.me']","HOSTS['bspb_announcements']=['t.me']\nHOSTS['alfa_only_announcements']=['t.me']")
replace('normalized.py',"    if r['source_id']=='greatlist_alfa_only':","    if r['source_id']=='alfa_only_tsum':\n        from tsum_alfa import validate_record\n        validate_record(r)\n    if r['source_id']=='greatlist_alfa_only':")
replace('normalized.py',"'mir_announcements','bspb_announcements') or", "'mir_announcements','bspb_announcements','alfa_only_announcements') or")
replace('normalized.py',"'bspb_announcements':'mybspb'}.get", "'bspb_announcements':'mybspb','alfa_only_announcements':'aaa_only'}.get")
p=ROOT/'sources_normalized.json';v=json.loads(p.read_text())
v.extend([{'id':'alfa_only_tsum','name':'Alfa Only — ЦУМ / ДЛТ, условия магазина','url':'https://www.tsum.ru/lp/alfa-only/','mode':'html','coverage_scope':'two_merchant_loyalty_tiers_not_bank_cash_or_full_partner_catalog'},
{'id':'alfa_only_announcements','name':'Alfa Only — публичные объявления','channel':'aaa_only','url':'https://t.me/s/aaa_only','mode':'announcements','lookback_days':180,'max_pages':60,'timeout_seconds':240}])
p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
replace('unified_normalization.py',"    if d.get('scope')=='only_cards_in_current_public_partner_inventory':", """    if 'tsum_evidence' in d:
        from tsum_alfa import URL, derived
        tier=d.get('tsum_tier')
        claim,terms,activation=derived(d['tsum_evidence'],tier)
        if (raw['program']!='Alfa Only' or raw['source_url']!=URL or raw['kind']!='partner_offer'
            or raw['benefit']!=claim or raw['conditions']!=terms or raw['activation']!=activation):
            raise ValueError('TSUM owned evidence changed')
        scope={'merchant_tier':tier,'reward_program':'TSUM_DLT','eligibility_not_verified':True}
        rule=condition('owned_merchant_rules','/conditions',scope=scope)
        action=condition('activation_step','/activation',scope=scope)
        rates=normalize_rates(claim)
        if len(rates)!=1:raise ValueError('TSUM tier rate count')
        rate=rates[0]
        b=benefit('earn_points','/benefit',value=rate['value'],unit='percent',qualifier='exact',
            reward_unit='TSUM_DLT_loyalty_credit',scope=scope,method='owned_source_clause')
        b.update(condition_ids=[rule['id'],action['id']],condition_linkage='full_owned_record_rules',remaining_record_rules_require_review=True)
        n['quality']['level']='structured_with_review'
        n['quality']['issues'].append('shop_loyalty_not_cash_baseline_rates_remain_conditions')
        n['content_sha256']=digest({k:v for k,v in n.items() if k!='content_sha256'})
        validate_normalized(n);return n
    if d.get('scope')=='only_cards_in_current_public_partner_inventory':""")
# Restore only public source excerpts from the independently checked probe artifact.
u='https://api.github.com/repos/Floppa2003/key-privileges/actions/artifacts/10583439102/zip'
r=requests.get(u,headers={'Authorization':'Bearer '+os.environ['GITHUB_TOKEN'],'Accept':'application/vnd.github+json'},timeout=25,allow_redirects=False)
assert r.status_code==302
assert r.headers['Location'].startswith('https://')
r=requests.get(r.headers['Location'],timeout=40);r.raise_for_status();data=r.content
assert len(data)<2000000 and hashlib.sha256(data).hexdigest()=='5275ea2a7d152c364e4c54f0085d0f7fe5cf8661e40d0b08ac6077e2c4c8d1a8'
z=zipfile.ZipFile(io.BytesIO(data));assert z.testzip() is None
s=BeautifulSoup(z.read('tsum-000.html').decode(),'html.parser');fixture=BeautifulSoup('<html><body></body></html>','html.parser')
for selector in ['[class*="AlfaOnly__logoTitle___"]','[class*="AlfaOnly__bounsWrapper___"]','[class*="AlfaOnly__privelegiesBlock___"]','[class*="AlfaOnly__faqBlock___"]']:
    for node in s.select(selector):fixture.body.append(BeautifulSoup(str(node),'html.parser'))
for n in fixture.select('script,style,svg'):
    if n.parent is not None:n.decompose()
(ROOT/'tests/fixtures_live/tsum-alfa.html').write_text('<!-- Public DOM snapshot 2026-09-19T11:54:37Z; markup/text preserved; unrelated navigation, SVG and scripts omitted. -->\n'+str(fixture))
s=BeautifulSoup(z.read('alfa_channel-000.html').decode(),'html.parser');n=s.select_one('[data-post="aaa_only/1589"]')
assert n is not None
caption=n.select_one('.tgme_widget_message_text');clone=BeautifulSoup(str(caption),'html.parser')
for br in clone.select('br'):br.replace_with('\n')
paragraphs=clone.get_text('',strip=False).strip().split('\n\n')
selected=[p for p in paragraphs if '15,8%' in p or p.startswith('Премиальным клиентам Alfa Only')]
assert len(selected)==2
caption.clear();caption.append(BeautifulSoup('<br><br>'.join(html.escape(p) for p in selected),'html.parser'))
fixture=BeautifulSoup('<html><body></body></html>','html.parser');fixture.body.append(n)
for el in fixture.select('script,style,svg,.tgme_widget_message_photo_wrap,.tgme_widget_message_user,.tgme_widget_message_footer .tgme_widget_message_views'):
    if el.parent is not None:el.decompose()
(ROOT/'tests/fixtures_live/alfa-simpleprive-post.html').write_text('<!-- Source-owned excerpt: market-return and benefit paragraphs only; not a whole-post snapshot. -->\n'+str(fixture))
print(json.dumps({'changed':[str(ROOT/p) for p in EXPECTED], 'artifact_digest_verified':True,'public_excerpt_fixtures':2}))
