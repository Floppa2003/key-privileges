"""X5's anonymous route loader inventory and source-owned offer details."""
from __future__ import annotations
import json,re
from urllib.parse import urlencode
from bs4 import BeautifulSoup
from public_reward_projection import plain,one,make_record
from expansion_common import compact,sha,identity,iso,check_period,exclusion,ExcludedOffer,reported,add_error,PROGRAMS

SOURCE='x5_partners_public';ROOT='https://x5club.ru/partners'
ROUTE='routes/_unauth.partners._index'

def decode_loader(raw):
    # Only the first resolved, anonymous catalogue frame. Deferred wheel/game
    # promises are not catalogue evidence and are never traversed.
    values=json.loads(raw.splitlines()[0])
    if not isinstance(values,list) or not 1<=len(values)<=30000:raise ValueError('x5_loader_bound')
    cache={}
    def read(i,trail=()):
        if type(i) is not int:raise ValueError('x5_loader_reference')
        if i in (-1,-5,-7):return None
        if i<0 or i>=len(values) or i in trail:raise ValueError('x5_loader_cycle_or_index')
        if i in cache:return cache[i]
        v=values[i];path=trail+(i,)
        if isinstance(v,dict):
            if any(not re.fullmatch(r'_\d+',k) for k in v):raise ValueError('x5_loader_key')
            out={read(int(k[1:]),path):read(ref,path) for k,ref in v.items()}
        elif isinstance(v,list):
            if v and isinstance(v[0],str):
                if v[0]!='P':raise ValueError('x5_unreviewed_loader_tag')
                out=None
            else:out=[read(ref,path) for ref in v]
        else:out=v
        cache[i]=out;return out
    result=read(0)
    if not isinstance(result,dict) or set(result)!={ROUTE}:raise ValueError('x5_loader_route')
    d=result[ROUTE]['data']
    if d.get('partnerOffersError'):raise ValueError('x5_loader_reported_error')
    return d

def page_data(raw,index):
    d=decode_loader(raw);p=d['partnerOffers']
    if p['page']!=index or type(p['pageTotal']) is not int or not 1<=p['pageTotal']<=40 or not isinstance(p['partnerOffers'],list):
        raise ValueError('x5_pagination_contract')
    return d

def source_fields(e):
    identity(e,SOURCE)
    if not re.fullmatch(r'\d+',e['native']) or e['url']!=ROOT+'/'+e['native']:raise ValueError('x5_offer_url')
    card=e['card'];title=compact(e['heading'])
    if card['idOffer']!=int(e['native']) or title!=compact(card['nameOffer']):raise ValueError('x5_detail_heading_drift')
    partner=compact(e['partner']);expected=compact(card.get('namePartnerOffer') or card.get('namePartner'))
    if not partner or (expected and partner!=expected):raise ValueError('x5_partner_identity')
    if not e['activation'] or not e['conditions']:raise ValueError('x5_missing_detail_terms')
    start,end=iso(card.get('startDate')),iso(card.get('endDate'))
    period=re.search(r'Действует\s+(\d{2}\.\d{2}\.\d{4})\s*-\s*(\d{2}\.\d{2}\.\d{4})',e['period'])
    if not period or (iso(period[1]),iso(period[2]))!=(start,end):raise ValueError('x5_catalogue_detail_period_drift')
    cost=card.get('cost'); typ=card.get('type')
    if type(cost) not in (int,float) or cost<0 or typ not in ('purchased','exchange'):raise ValueError('x5_cost_type')
    access=(f'Получение: {cost:g} баллов X5 Клуба.' if typ=='purchased' else 'Обмен баллов X5; курс и единицы обмена определяются условиями ниже.')
    return dict(native=e['native'],program=PROGRAMS[SOURCE],partner=partner,title=title,benefit=title,
        url=e['url'],conditions='\n'.join([access,e['period'],e['conditions']]),activation=e['activation'],
        valid_from=start,valid_until=end,category=e.get('category') or 'Партнёры',locator='main; own heading, dates, redemption and conditions',
        terms=[dict(kind='partner_privilege',fragment=title)],scope={'X5_membership_required':True,'individual_code_not_issued':True},
        warnings=['X5_points_cost_not_cash_discount'])

def detail(raw,card,category,now):
    soup=BeautifulSoup(raw,'html.parser');root=one(soup,'main');h=root.select('h2')
    if not h:raise ValueError('x5_detail_missing_heading')
    def section(label):
        nodes=[n for n in h if compact(plain(n))==label]
        if len(nodes)!=1:raise ValueError('x5_owned_section_missing:'+label)
        children=[n for n in nodes[0].parent.find_all(recursive=False) if n!=nodes[0]]
        return '\n'.join(plain(n) for n in children).strip()
    container=h[0].parent
    e=dict(native=str(card['idOffer']),url=ROOT+'/'+str(card['idOffer']),card={k:card.get(k) for k in
        ('idOffer','nameOffer','cost','startDate','endDate','type','namePartnerOffer','namePartner')},
        heading=plain(h[0]),partner=plain(one(container,'h3')),period=plain(one(container,'p')),
        activation=section('Как воспользоваться?'),conditions=section('Условия предложения'),category=category,page_sha256=sha(raw))
    check_period(iso(card.get('startDate')),iso(card.get('endDate')),now)
    return make_record(SOURCE,e,now)

async def collect(client,cfg,report,now,limit):
    from read_budget import within_source_budget,stops_catalog
    if cfg['id']!=SOURCE or cfg['url']!=ROOT:raise ValueError('x5_config')
    async def read(u):return await within_source_budget(client,lambda:client.read(u))
    cards={};categories={};total=None;page_hashes=[]
    for page in range(41):
        u=ROOT+'.data?'+urlencode({'page':page,'_routes':ROUTE})
        raw=await read(u);d=page_data(raw,page);p=d['partnerOffers']
        if total is None:total=p['pageTotal']
        if p['pageTotal']!=total:raise ValueError('x5_page_total_changed')
        page_hashes.append({'page':page,'sha256':sha(raw)})
        if page==total:
            if p['partnerOffers']:raise ValueError('x5_terminal_page_not_empty')
            break
        if not p['partnerOffers']:raise ValueError('x5_empty_nonterminal_page')
        categories.update({str(x.get('idCategory',x.get('id'))):x.get('nameCategory',x.get('name')) for x in d.get('categories',[])})
        for c in p['partnerOffers']:
            native=str(c['idOffer'])
            if native in cards:raise ValueError('x5_duplicate_page_card')
            cards[native]=c
        if page==0:paid=d.get('paidOffers',[])
    else:raise ValueError('x5_page_bound')
    # The separately promoted block can contain offers outside page zero.
    for c in paid:
        native=str(c['idOffer'])
        if native not in cards:cards[native]=c
        elif any(c.get(k)!=cards[native].get(k) for k in ('nameOffer','cost','startDate','endDate','type')):
            raise ValueError('x5_promoted_card_drift')
    if not 1<=len(cards)<=limit:raise ValueError('x5_card_limit')
    rows=[];excluded={}
    for native,c in cards.items():
        why=exclusion(c['nameOffer'])
        if why:excluded[native]=why;continue
        try:
            category=' / '.join(filter(None,(categories.get(str(x)) for x in c.get('categoryOffers',[]))))
            rows.append(detail(await read(ROOT+'/'+native),c,category,now))
        except ExcludedOffer as exc:excluded[native]=str(exc)
        except Exception as exc:
            add_error(report,exc,native)
            if stops_catalog(exc):break
    reported(report,rows,list(cards),excluded,pages=page_hashes,scope='all_anonymous_partner_loader_pages_and_promoted_block')
    return rows
