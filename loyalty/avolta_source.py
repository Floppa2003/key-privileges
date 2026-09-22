"""Anonymous Russian Club Avolta partner pages via the ordinary browser.

Collect observed category/detail links only, without joining or activating any
partner offer. Keep geography and programme/tier restrictions inside each card.
"""
from __future__ import annotations
import hashlib, json, re
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup
from normalized import normalize_rates
from public_reward_projection import plain, one, make_record

SOURCE = 'club_avolta_public'
ROOT = 'https://www.clubavolta.com/ru'
PREFIX = ROOT + '/nashi-partnery/'
PROGRAM = 'Club Avolta'


class ExcludedOffer(ValueError): pass


def reviewed_url(value, category=False):
    pattern = re.escape(PREFIX) + r'[a-z0-9-]+' + ('' if category else r'/[a-z0-9-]+')
    if not re.fullmatch(pattern, value): raise ValueError('avolta_url_scope')
    return value


def categories(raw):
    soup=BeautifulSoup(raw,'html.parser'); one(soup,'main#Main')
    result={reviewed_url(urljoin(ROOT,a['href']),True):plain(a) for a in soup.select('a.partners-tile[href]')}
    if not 1<=len(result)<=10 or any(not v for v in result.values()):raise ValueError('avolta_category_inventory')
    return result


def catalogue(raw,url,label):
    soup=BeautifulSoup(raw,'html.parser');root=one(soup,'main#Main')
    if plain(one(root,'h1')).casefold()!=label.casefold():raise ValueError('avolta_category_heading')
    if root.select('[rel="next"],.pagination,.load-more'):raise ValueError('avolta_unreviewed_pagination')
    result=[]
    for a in root.select('a.partner[href]'):
        target=reviewed_url(urljoin(url,a['href']))
        if not target.startswith(url+'/'):raise ValueError('avolta_foreign_category_card')
        result.append(dict(url=target,name=plain(one(a,'.partner-name')),category=label,category_url=url))
    if len({x['url'] for x in result})!=len(result):raise ValueError('avolta_duplicate_card')
    return result


def source_fields(e):
    url=reviewed_url(e['url']);name=e.get('name','')
    if not name or not re.fullmatch(r'[a-f0-9]{64}',e.get('page_sha256','')):raise ValueError('avolta_evidence_identity')
    headline=e.get('headline','');intro=e.get('intro','');body=e.get('body','')
    if not headline or not intro or not body or not e.get('category'):raise ValueError('avolta_missing_owned_text')
    if url.endswith('/dragonpass'):
        amounts=set(re.findall(r'за\s+(\d+(?:[.,]\d+)?)\s+доллар',headline+'\n'+intro+'\n'+body,re.I))
        if len(amounts)>1:raise ExcludedOffer('source_conflict_lounge_admission_price')
    candidates=[headline]+intro.splitlines()+body.splitlines()
    meaningful=[s for s in candidates if 0<len(s)<=800 and re.search(r'\d|бесплат|балл|мили|Avios',s,re.I)]
    if not meaningful:raise ExcludedOffer('no_concrete_partner_benefit')
    claim=meaningful[0]
    rates=normalize_rates(claim)
    terms=[dict(kind=r['kind'],value=r['value'],unit=r['unit'],qualifier=r['qualifier'],fragment=r['evidence']) for r in rates]
    if not terms:terms=[dict(kind='partner_privilege',fragment=claim)]
    actions=[s for s in (intro+'\n'+body).splitlines() if re.search(r'зарегистр|активир|установ|скач|введ|предъяв|загруз|покаж|перейд|приложени',s,re.I)]
    return dict(native=url[len(PREFIX):],program=PROGRAM,partner=name,title='Club Avolta → '+name,
        benefit=claim,conditions='\n'.join(dict.fromkeys([headline,intro,body])),activation='\n'.join(actions),
        url=url,category=e['category'],locator='main#Main; hero description and partner usercontent',
        terms=terms,scope={'programme_membership_required':True,'eligibility_not_verified':True},
        warnings=['country_tier_and_partner_redemption_terms_require_review','public_partner_conditions_not_booking_availability'])


def parse_detail(raw,card,observed_at):
    soup=BeautifulSoup(raw,'html.parser');root=one(soup,'main#Main')
    name=plain(one(root,'.breadcrumb [aria-current="location"]'))
    if name.casefold()!=card['name'].casefold():raise ValueError('avolta_detail_identity')
    headline=plain(one(root,'h1'))
    intro_node=one(root,'.full-width-cta-image-text-description')
    intro=plain(intro_node)
    blocks=root.select('.two-column-block .usercontent')
    if not blocks:raise ValueError('avolta_detail_conditions_missing')
    evidence={**card,'headline':headline,'intro':intro,'body':'\n'.join(plain(n) for n in blocks),
              'page_sha256':hashlib.sha256(raw.encode()).hexdigest()}
    return make_record(SOURCE,evidence,observed_at)


async def collect(client,cfg,report,observed_at,limit):
    from read_budget import within_source_budget,stops_catalog
    if cfg['id']!=SOURCE or cfg['url']!=ROOT:raise ValueError('avolta_config_identity')
    client.request_interval=max(1,client.request_interval)
    async def read(url):return await within_source_budget(client,lambda:client.read(url,render=True))
    cats=categories(await read(ROOT));cards=[];inventories=[]
    for url,label in cats.items():
        current=catalogue(await read(url),url,label)
        cards.extend(current);inventories.append({'url':url,'name':label,'cards':len(current)})
    if not cards or len(cards)>min(limit,80) or len({c['url'] for c in cards})!=len(cards):raise ValueError('avolta_card_inventory_bound')
    rows=[];excluded=[]
    for card in cards:
        try:rows.append(parse_detail(await read(card['url']),card,observed_at))
        except ExcludedOffer as exc:excluded.append({'url':card['url'],'reason':str(exc)})
        except Exception as exc:
            report['errors'].append({'phase':'detail','url':card['url'],'reason':str(exc)[:150] if isinstance(exc,(RuntimeError,ValueError)) else type(exc).__name__})
            if stops_catalog(exc) or str(exc) in ('http_401','http_403','access_challenge','unexpected_redirect'):break
    report['discovered']=len(rows)+len(report['errors'])
    report['coverage']=json.dumps({'scope':'public_russian_partner_categories','categories':inventories,
        'listed':len(cards),'parsed':len(rows),'excluded':excluded,
        'all_inventory_accounted':len(rows)+len(excluded)+len(report['errors'])==len(cards)},ensure_ascii=False)
    return rows
