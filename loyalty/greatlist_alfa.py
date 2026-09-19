"""GreatList's public Alfa Only city tabs; no bank session or inferred cashback."""
from __future__ import annotations
import hashlib,json,re
from urllib.parse import urljoin,urlsplit,urlunsplit
from bs4 import BeautifulSoup,Comment
from normalized import make_offer,text
from read_budget import within_source_budget,stops_catalog

SOURCE_ID='greatlist_alfa_only'
ROOT='https://greatlist.ru/spb/alfa-only/'
HOST='greatlist.ru'
WARNINGS=['user_eligibility_not_verified','authenticated_partner_catalog_not_read',
          'public_guide_not_bank_promotion_rules','dates_caps_and_activation_not_inferred',
          'guide_and_bank_pdf_records_not_merged']


def public_url(value,base=ROOT):
    p=urlsplit(urljoin(base,value))
    if p.scheme!='https' or p.netloc!=HOST or p.query or '%' in p.path:
        raise ValueError('greatlist_url_outside_scope')
    return urlunsplit((p.scheme,p.netloc,p.path,'',''))


def page(raw,url):
    soup=BeautifulSoup(raw,'html.parser')
    links=soup.select('link[rel="canonical"][href]')
    if len(links)!=1 or public_url(links[0]['href'])!=url or soup.body is None:
        raise ValueError('greatlist_page_identity')
    return soup


def city_roots(raw):
    soup=page(raw,ROOT);cities={}
    for a in soup.select('.psevdo_select_area_city .psevdo_select_list a[href]'):
        p=urlsplit(urljoin(ROOT,a['href']))
        if p.hostname!=HOST:continue  # Foreign country editions are outside this source.
        url=public_url(a['href'])
        if not re.fullmatch(r'/[a-z]{2,12}/',p.path):raise ValueError('greatlist_city_path')
        name=text(a.get_text(' ',strip=True))
        if not name or (url in cities and cities[url]!=name):raise ValueError('greatlist_city_identity')
        cities[url]=name
    if not 1<=len(cities)<=12:raise ValueError('greatlist_city_count')
    return [{'url':url,'name':name} for url,name in cities.items()]


def alfa_tab(raw,city):
    soup=page(raw,city['url'])
    links={public_url(a['href'],city['url']) for a in soup.select('a[data-id="alfa-only"][href]')}
    if len(links)!=1:raise ValueError('greatlist_alfa_tab_not_unique')
    url=links.pop()
    if url!=city['url']+'alfa-only/':raise ValueError('greatlist_alfa_tab_identity')
    return url  # Return the observed link, not a generated navigation request.


def catalogue(raw,url,city):
    soup=page(raw,url)
    if 'term-alfa-only' not in soup.body.get('class',[]):raise ValueError('greatlist_wrong_catalogue')
    selected={public_url(a['href'],url) for a in soup.select('a[data-id="alfa-only"][href]')}
    containers=soup.select('.places_mansory.js_get_cards')
    if url not in selected or len(containers)!=1:raise ValueError('greatlist_catalogue_structure')
    if soup.select('a[rel="next"],link[rel="next"],.pagination a,.nav-links a,.load_more,.load-more'):
        raise ValueError('greatlist_unreviewed_pagination')
    cards=[];ids=set();urls=set()
    # No cards outside the one current inventory container may be silently mixed in.
    nodes=soup.select('a.place_card[data-objectid][href]')
    if len(nodes)!=len(containers[0].select('a.place_card[data-objectid][href]')):
        raise ValueError('greatlist_ambiguous_card_container')
    for a in nodes:
        ident=a['data-objectid'];link=public_url(a['href'],url);labels=a.select('.h2')
        if (not re.fullmatch(r'[1-9][0-9]{0,9}',ident) or len(labels)!=1
            or not re.fullmatch(re.escape(city['url'])+r'restaurant/[a-z0-9-]+/',link)):
            raise ValueError('greatlist_card_identity')
        name=text(labels[0].get_text(' ',strip=True))
        if not name or ident in ids or link in urls:raise ValueError('greatlist_duplicate_or_empty_card')
        ids.add(ident);urls.add(link)
        cards.append({'post_id':ident,'name':name,'url':link,'city':dict(city),'catalogue_url':url})
    if len(cards)>500:raise ValueError('greatlist_card_bound')
    return cards


def clean_block(node):
    # The source's expandable .alfa-section-hide is a normal UI section, not a
    # hidden fact. Actual hidden/form/script/comment contents are excluded.
    soup=BeautifulSoup(str(node),'html.parser')
    for el in soup.select('script,style,noscript,form,input,textarea,iframe,[hidden],[aria-hidden="true"]'):
        if el.parent is not None:el.decompose()
    for el in soup.find_all(string=lambda x:isinstance(x,Comment)):el.extract()
    return soup


def source_fields(e):
    city=e['city'];post=e['post_id'];url=public_url(e['url'])
    if (not re.fullmatch(r'[1-9][0-9]{0,9}',post)
        or not re.fullmatch(r'https://greatlist.ru/[a-z]{2,12}/',city['url'])
        or e['catalogue_url']!=city['url']+'alfa-only/'
        or not re.fullmatch(re.escape(city['url'])+r'restaurant/[a-z0-9-]+/',url)
        or not e['name'] or not city['name'] or not e['address']
        or not re.fullmatch(r'[a-f0-9]{64}',e['page_sha256'])):
        raise ValueError('greatlist_evidence_identity')
    bullets=e['bullets']
    if not isinstance(bullets,list) or not 1<=len(bullets)<=12 or any(not isinstance(x,str) or not x for x in bullets):
        raise ValueError('greatlist_benefit_bullets')
    if not e['block_text'].startswith('Привилегии для клиентов Alfa Only:') or any(x not in e['block_text'] for x in bullets):
        raise ValueError('greatlist_wrong_benefit_owner')
    benefit='Привилегии для клиентов Alfa Only:\n'+'\n'.join(bullets)
    redemption='\n'.join(x for x in bullets if re.search(r'брон|бронир|консьерж',x,re.I))
    location=city['name']+' — '+e['address']
    return {'benefit_text':benefit,'conditions_text':location+'\n'+e['block_text'],
            'redemption_text':redemption,'location':location}


def parse_detail(raw,card,observed_at):
    soup=page(raw,card['url']);classes=soup.body.get('class',[])
    headings=soup.select('h1')
    if ('single-restaurant' not in classes or 'postid-'+card['post_id'] not in classes
        or len(headings)!=1 or not text(headings[0].get_text(' ',strip=True)).casefold().endswith(card['name'].casefold())):
        raise ValueError('greatlist_detail_identity')
    blocks=soup.select('.alfa-section-hide .alfa-section-text')
    addresses=soup.select('article.contacts .contacts_item_address')
    if len(blocks)!=1 or len(addresses)!=1:raise ValueError('greatlist_owned_block_missing_or_ambiguous')
    block=clean_block(blocks[0]);address=text(addresses[0].get_text(' ',strip=True))
    bullets=[text(li.get_text(' ',strip=True)) for li in block.select('ul > li')]
    full=text(block.get_text(' ',strip=True))
    if len(full)>6000:raise ValueError('greatlist_block_too_large')
    evidence={**card,'address':address,'bullets':bullets,'block_text':full,
              'page_sha256':hashlib.sha256(raw.encode()).hexdigest()}
    fields=source_fields(evidence)
    return make_offer(SOURCE_ID,city_id(card)+':'+card['post_id'],'Alfa Only',card['name'],
        fields['benefit_text'],card['url'],observed_at,title='Alfa Only → '+card['name']+' — '+card['city']['name'],
        conditions=fields['conditions_text'],redemption=fields['redemption_text'],category='Рестораны',
        locator='.alfa-section-hide .alfa-section-text',source_status='public_partner_guide',
        details={'greatlist_evidence':evidence,'activation':fields['redemption_text'],
                 'limitations':fields['location'],'authenticated_catalogue_equivalence':False},warnings=list(WARNINGS))


def city_id(card):return urlsplit(card['city']['url']).path.strip('/')


def validate_record(row):
    e=row.get('details',{}).get('greatlist_evidence',{})
    try:expected=source_fields(e)
    except (KeyError,TypeError):raise ValueError('greatlist_missing_evidence') from None
    checks={'source_id':SOURCE_ID,'native_id':city_id(e)+':'+e['post_id'],'program':'Alfa Only',
            'partner_name':e['name'],'source_url':e['url'],'benefit_url':e['url'],
            'title':'Alfa Only → '+e['name']+' — '+e['city']['name'],
            'record_kind':'partner_offer','source_status':'public_partner_guide','link_kind':'detail_page',
            'valid_from':None,'valid_until':None,
            **{k:expected[k] for k in ('benefit_text','conditions_text','redemption_text')}}
    if (any(row.get(k)!=v for k,v in checks.items())
        or row['details'].get('activation')!=expected['redemption_text']
        or row['details'].get('limitations')!=expected['location']
        or row['details'].get('authenticated_catalogue_equivalence') is not False
        or not set(WARNINGS).issubset(row.get('warnings',[]))):raise ValueError('greatlist_source_evidence_mismatch')


async def collect(client,cfg,report,observed_at,limit):
    if cfg['id']!=SOURCE_ID or cfg['url']!=ROOT:raise ValueError('greatlist_config_identity')
    async def read(url):return await within_source_budget(client,lambda:client.read(url))
    seed=await read(ROOT);cities=city_roots(seed);inventories=[];cards=[];rows=[];halted=False
    def error(exc,phase,url):
        report['errors'].append({'phase':phase,'url':url,
            'reason':str(exc)[:160] if isinstance(exc,(ValueError,RuntimeError)) else type(exc).__name__})
    for city in cities:
        try:
            url=alfa_tab(await read(city['url']),city)
            found=catalogue(seed if url==ROOT else await read(url),url,city)
            inventories.append({'city':city['name'],'url':url,'listed':len(found)})
            cards.extend(found)
        except Exception as exc:
            error(exc,'catalogue',city['url'])
            if stops_catalog(exc):halted=True;break
    for card in ([] if halted else cards[:limit]):
        try:rows.append(parse_detail(await read(card['url']),card,observed_at))
        except Exception as exc:
            error(exc,'detail',card['url'])
            if stops_catalog(exc):break
    if len(cards)>limit:report['errors'].append({'phase':'detail','reason':'detail_limit_reached','remaining':len(cards)-limit})
    report['discovered']=len(cards)
    report['coverage']=json.dumps({'scope':'visible_same_origin_russian_city_alfa_only_tabs',
        'cities_discovered':len(cities),'catalogues_read':inventories,'listed_cards':len(cards),
        'detail_pages_parsed':len(rows),'cashback_cards':sum(any(r['kind']=='cashback' for r in x['rates']) for x in rows),
        'all_discovered_cards_parsed':not report['errors'] and len(rows)==len(cards),
        'bank_catalogue_equivalence':False},ensure_ascii=False,sort_keys=True)
    return rows
