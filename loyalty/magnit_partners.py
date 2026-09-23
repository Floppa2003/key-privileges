"""Public Magnit partner cards; ordinary anonymous rendered pages, no login."""
from __future__ import annotations
import json,re
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from public_reward_projection import plain,one,make_record
from expansion_common import compact,sha,identity,iso,check_period,exclusion,ExcludedOffer,reported,add_error,PROGRAMS,links

SOURCE='magnit_partners_public';ROOT='https://magnit.ru/partners'

def public_data(raw,key):
    soup=BeautifulSoup(raw,'html.parser');nodes=soup.select('script#__NUXT_DATA__')
    if len(nodes)!=1:raise ValueError('magnit_state_missing')
    values=json.loads(nodes[0].get_text())
    if not isinstance(values,list) or len(values)>50000:raise ValueError('magnit_state_bound')
    def unwrap(i):
        value=values[i]
        while isinstance(value,list) and value and isinstance(value[0],str):
            if value[0] not in ('ShallowReactive','Reactive'):raise ValueError('magnit_state_wrapper')
            value=values[value[1]]
        return value
    # Do not decode pinia, profile or other optional guest/personal stores.
    root=unwrap(0);data=unwrap(root['data'])
    if key not in data:raise ValueError('magnit_owned_state_missing:'+key)
    def read(i,trail=()):
        if type(i) is not int:raise ValueError('magnit_state_reference')
        if i<0:return None
        if i>=len(values) or i in trail:raise ValueError('magnit_state_cycle')
        value=values[i];trail=trail+(i,)
        if isinstance(value,dict):return {k:read(v,trail) for k,v in value.items()}
        if isinstance(value,list):
            if value and isinstance(value[0],str):
                if value[0] not in ('ShallowReactive','Reactive'):raise ValueError('magnit_state_tag')
                return read(value[1],trail)
            return [read(v,trail) for v in value]
        return value
    return read(data[key])

def inventory(raw):
    s=BeautifulSoup(raw,'html.parser');root=one(s,'main')
    if root.select('[rel=next],.pagination,.load-more'):raise ValueError('magnit_unreviewed_pagination')
    cards={}
    for a in root.select('a[href]'):
        m=re.fullmatch(r'/partners/(\d+)/?',urlsplit(a['href']).path)
        if not m or not a.select('.card'):continue
        native=m[1];c={'native':native,'partner':plain(one(a,'.title')),'title':plain(one(a,'.description'))}
        if native in cards and cards[native]!=c:raise ValueError('magnit_duplicate_card_drift')
        cards[native]=c
    data=public_data(raw,'partners-offers')
    # All public items are embedded in this page; compare DOM against own store.
    if isinstance(data,dict):
        candidates=[v for k,v in data.items() if isinstance(v,list)]
        if len(candidates)!=1:raise ValueError('magnit_catalogue_store_shape')
        data=candidates[0]
    if not isinstance(data,list):raise ValueError('magnit_catalogue_store_type')
    stored={str(x['id']) for x in data}
    if not 1<=len(cards)<=200 or set(cards)!=stored:raise ValueError('magnit_catalogue_dom_store_mismatch')
    categories={str(x['id']):x['title'] for x in public_data(raw,'partners-categories')}
    return cards,categories

def practical_content(html):
    # These two terminal headings introduce corporate advertising, not terms.
    s=BeautifulSoup(html,'html.parser')
    for n in s.find_all(['b','strong','h2','h3']):
        if re.fullmatch(r'О партн[её]ре\s*:?',plain(n),re.I):
            for later in list(n.next_siblings):later.extract()
            if n.parent.name=='p':
                for later in list(n.parent.next_siblings):later.extract()
            n.extract();break
    lines=plain(s).splitlines();out=[]
    for line in lines:
        if re.match(r'Реклама(?:\s|$)|Организатор акции:',line,re.I):break
        out.append(line)
    return '\n'.join(out).strip()

def period(text):
    months=('января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря')
    text=re.sub(r'(\d{1,2})\s+('+ '|'.join(months) +r')\s+(\d{4})',lambda m:m[1].zfill(2)+'.'+str(months.index(m[2].lower())+1).zfill(2)+'.'+m[3],text,flags=re.I)
    pairs=re.findall(r'(?:Общий срок проведения акции|Сроки акции|Период проведения акции|Акция действует)\s*:?\s*с\s*(\d{2}\.\d{2}\.\d{4})\s*(?:по|до|–|-)\s*(\d{2}\.\d{2}\.\d{4})',text,re.I)
    ends=re.findall(r'(?:акци\w*\s+действует\s+до|предложение\s+действует\s+до|Срок\s+действия\s+акции\s*:\s*до)\s*(\d{2}\.\d{2}\.\d{4})',text,re.I)
    if len(set(pairs))>1 or (pairs and ends and set(ends)!={pairs[0][1]}):raise ValueError('magnit_conflicting_period')
    return (iso(pairs[0][0]),iso(pairs[0][1])) if pairs else (None,iso(ends[0]) if len(set(ends))==1 else None)

def source_fields(e):
    identity(e,SOURCE)
    if not re.fullmatch(r'\d+',e['native']) or e['url']!=ROOT+'/'+e['native']:raise ValueError('magnit_detail_url')
    if compact(e['title'])!=compact(e['catalogue_title']) or not e['partner']:raise ValueError('magnit_detail_identity')
    body=practical_content(e['content'])
    if len(body)<35 or not e['steps']:raise ValueError('magnit_detail_terms_missing')
    start,end=period(body)
    title=compact(e['title'])
    # Use the complete offer-specific conditions, without reclassifying the cost
    # of another subscription (e.g. 399 RUB/month) as a Magnit card fee or reward.
    conditions=body+'\n'+e['disclaimer']
    if e.get('rule_links'):conditions+='\nПравила предложения: '+'; '.join(e['rule_links'])
    return dict(native=e['native'],program=PROGRAMS[SOURCE],partner=e['partner'],title=title,benefit=title,
        conditions=conditions.strip(),activation='Войти в профиль Магнит Плюс.\n'+e['steps'],url=e['url'],
        category=e.get('category') or 'Партнёры',locator='public partners-detail store, content and steps',
        terms=[dict(kind='partner_privilege',fragment=title)],valid_from=start,valid_until=end,
        scope={'Magnit_loyalty_membership_required':True,'eligibility_not_verified':True},
        warnings=['partner_subscription_cost_not_Magnit_card_service_fee','bonuses_not_cashback_to_bank_card'])

def detail(raw,card,categories,now):
    native=card['native'];d=public_data(raw,'partners-detail:'+native)
    s=BeautifulSoup(raw,'html.parser');heading=plain(one(s,'h1.partners-detail-page__title'))
    if heading!=compact(d['title']) or compact(d['partner'])!=compact(card['partner']):raise ValueError('magnit_dom_store_identity')
    disc=s.select('.partners-detail-page__disclaimer')
    e=dict(native=native,url=ROOT+'/'+native,title=heading,catalogue_title=card['title'],partner=d['partner'],
        content=d['content'],steps='\n'.join(plain(x['text']) for x in d['steps']) or '\n'.join(plain(x) for x in BeautifulSoup(d['content'],'html.parser').select('ol > li')),disclaimer='\n'.join(plain(n)for n in disc),
        rule_links=links(d['content']),category=' / '.join(categories.get(str(x),str(x)) for x in d.get('categories',[])),page_sha256=sha(raw))
    f=source_fields(e);check_period(f['valid_from'],f['valid_until'],now)
    return make_record(SOURCE,e,now)

async def collect(client,cfg,report,now,limit):
    from read_budget import within_source_budget,stops_catalog
    if cfg['id']!=SOURCE or cfg['url']!=ROOT:raise ValueError('magnit_config')
    from magnit_policy import QuerylessMagnitPolicy
    client.policy=QuerylessMagnitPolicy(client.robots_rules)
    report['policy_matcher']='protego_062_queryless_magnit_cards_only'
    async def read(url,selector):
        await within_source_budget(client,lambda:client.read(url,render=True))
        await within_source_budget(client,lambda:client.page.locator(selector).first.wait_for(state='attached',timeout=12000))
        return await client.page.content()
    raw=await read(ROOT,'.card');cards,categories=inventory(raw)
    if len(cards)>limit:raise ValueError('magnit_detail_limit')
    rows=[];excluded={}
    for native,card in cards.items():
        why=exclusion(card['title'])
        if why:excluded[native]=why;continue
        try:rows.append(detail(await read(ROOT+'/'+native,'h1.partners-detail-page__title'),card,categories,now))
        except ExcludedOffer as exc:excluded[native]=str(exc)
        except Exception as exc:
            add_error(report,exc,native)
            if stops_catalog(exc):break
    reported(report,rows,list(cards),excluded,root_sha256=sha(raw),scope='all_public_catalogue_DOM_and_embedded_store_cards')
    return rows
