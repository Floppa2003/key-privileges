"""Source-specific boundaries: a card/object is never paired by global DOM order."""
from __future__ import annotations
import json
import hashlib
import re
from datetime import datetime
from urllib.parse import urljoin, urlsplit, parse_qsl, urlencode
from bs4 import BeautifulSoup
from normalized import make_offer, text, BLOCKED

PROGRAMS = {'moskvich':'Карта «Москвича»','noname':'No Name Card','s7':'S7 Priority',
 'ural':'Уральские авиалинии — «Крылья»','rgo':'Программа лояльности членов РГО',
 'mir':'Привет! / Мир / СБП','azimut':'AZIMUT Bonus','rusimp':'Клуб Друзей Музея русского импрессионизма',
 'sogaz_medi':'СОГАЗ → МЕДИ','ekp_medi':'ЕКП → МЕДИ','ekp_neva':'ЕКП → Нева Тревел',
 'mir_neva':'Мир → Нева Тревел','promomiles':'Аэрофлот Бонус — Promo Miles','key':'KEY'}
BENEFIT = re.compile(r'скидк|подар|комплимент|кешбэк|кэшбэк|демонстрации карты|предъявлении карты|при заказе|бесплат|%|за каждые',re.I)


def node_text(n) -> str:
    return text(n.get_text(' ',strip=True)) if n else ''


def tables_in(n) -> list:
    return [[[node_text(c) for c in row.find_all(['th','td'],recursive=False)]
             for row in t.select('tr')] for t in n.select('table')]


def next_state(raw: str) -> dict:
    el=BeautifulSoup(raw,'html.parser').select_one('script#__NEXT_DATA__')
    if not el:
        raise ValueError('Missing S7 public application state')
    return json.loads(el.string or el.get_text())['props']['initialState']


def s7_catalog(state: dict) -> list[dict]:
    offers=state['offers']['partners']['offers']
    by_code={}
    for offer in offers:
        code=offer['code'];url=offer.get('priorityRulesUrl','')
        if not url or urlsplit(url).hostname!='marketplace.s7.ru':
            continue
        if code not in by_code:
            by_code[code]={'native_id':code,'url':url,'catalog_benefit':text(offer.get('content2','')),
                           'category_codes':[]}
        category=offer.get('category')
        if category and category not in by_code[code]['category_codes']:
            by_code[code]['category_codes'].append(category)
    return list(by_code.values())


def s7_detail(state: dict,url: str,observed_at: str) -> list[dict]:
    code=urlsplit(url).path.rstrip('/').split('/')[-1]
    obj=state['offer']['partners'].get(code)
    if not obj or obj['offer']['code']!=code:
        raise ValueError('S7 requested code does not match the detail object')
    partner=obj['partner'];fields=partner.get('priorityDetails',{})
    description=text(partner.get('description',''))
    # A source-provided short description, not the page H1 which is usually a rate.
    prefix=re.split(r'\s+[—–]\s+',description,maxsplit=1)[0]
    name=prefix if prefix and len(prefix)<=100 else None
    rules=text(fields.get('rule'))
    if not rules:
        rules=text(obj['offer'].get('content2'))
    details={'partner_code':partner.get('code'),'partner_description':description,
             'partner_description_long':text(fields.get('description')),
             'source_updated_at':partner.get('updatedAt'),
             'spending_rule':text(fields.get('spendingRule')),
             'spending_details':text(fields.get('spendingDetails'))}
    r=make_offer('s7',code,PROGRAMS['s7'],name,rules,url,observed_at,
                 conditions=text(fields.get('details')),
                 redemption='\n'.join(text(x) for x in fields.get('steps',[]) if text(x)),
                 title=rules,category=obj.get('category',{}).get('content1'),
                 details=details,locator=f'initialState.offer.partners[{code!r}].partner.priorityDetails')
    return [r]


def mir_detail(data: dict,url: str,observed_at: str) -> list[dict]:
    p=data['data']['content']['promoDetail']['promo']['promoAction']
    if urlsplit(url).path.rstrip('/')!=urlsplit(p['url']).path.rstrip('/'):
        raise ValueError('Mir detail URL mismatch')
    templates=[{'name':x.get('templateName'),'title':text(x.get('templateTitle')),
                'text':text(x.get('templateText'))} for x in (p.get('templates') or [])]
    desc=p.get('desc',{});num=desc.get('number',{})
    benefit=text(text(num.get('PREFIX'))+' '+text(num.get('AMOUNT'))+' '+text(desc.get('text')))
    def iso(value):
        return datetime.strptime(value,'%d.%m.%Y').date().isoformat() if value else None
    dates={k:iso(p.get(v)) for k,v in [('valid_from','startDate'),('valid_until','endDate')]}
    status='cancelled' if p.get('promoIsCancelled') else 'finished' if p.get('promoIsFinished') else p.get('status','unknown')
    links=[]
    for x in (p.get('templates') or []):
        for a in BeautifulSoup(x.get('templateText') or '','html.parser').select('a[href]'):
            if x.get('templateName')=='rules':
                links.append(urljoin(url,a['href']))
    details={'templates':templates,'payment_badges':[text(x.get('text')) for x in (p.get('promoBadges') or [])],
             'rules_urls':links,'source_prize_suspended':p.get('prizeIsSuspended'),
             'limit_source_fields':{'perPromoActionLimit':p.get('perPromoActionLimit'),'clientTimeLimit':p.get('clientTimeLimit')},
             'source_is_started':p.get('promoIsStarted')}
    # Keep only public offer fields. iframe/auth and recommendations are deliberately not copied.
    r=make_offer('mir',p['xml_id'],PROGRAMS['mir'],p.get('owner',{}).get('name'),benefit,url,observed_at,
         conditions='\n'.join((x['title']+'\n'+x['text']).strip() for x in templates if x['text']),
         redemption=text(p.get('freeFormBlock')),title=p.get('name',''),category=p.get('short_desc'),
         details=details,source_status=status,locator='promoDetail.promo.promoAction',**dates)
    return [r]


def extract(source: str,raw: str,url: str,observed_at: str) -> list[dict]:
    soup=BeautifulSoup(raw,'html.parser')
    if BLOCKED.search(node_text(soup.select_one('title'))) or BLOCKED.search(node_text(soup)[:350]):
        raise ValueError('Access challenge is not a catalog')
    if source=='s7':
        return s7_detail(next_state(raw),url,observed_at)
    result=[]
    def add(native,name,benefit,**kw):
        result.append(make_offer(source,str(native),PROGRAMS[source],name,benefit,url,observed_at,**kw))
    if source=='moskvich':
        for card in soup.select('.lpp-card'):
            name=node_text(card.select_one('.lpp-card__name'))
            benefit=node_text(card.select_one('.lpp-card__conditions'))
            if not name or not benefit:
                raise ValueError('Moskvich card lacks name or conditions')
            add(name.casefold(),name,benefit,conditions=benefit,link_kind='page_block',
                locator='.lpp-card / .lpp-card__name = '+name,
                warnings=['conditions_share_the_benefit_block'])
    elif source=='noname':
        for rec in soup.select('.t-rec[id]'):
            els=[]
            for el in rec.select('.t396__elem[data-elem-id]'):
                t=node_text(el.select_one('.tn-atom'))
                if not t or not el.has_attr('data-field-top-value') or not el.has_attr('data-field-left-value'):
                    continue
                try:xy=(float(el['data-field-left-value']),float(el['data-field-top-value']))
                except ValueError:continue
                els.append({'id':el['data-elem-id'],'x':xy[0],'y':xy[1],'text':t})
            used=set()
            for b in [e for e in els if BENEFIT.search(e['text'])]:
                names=[n for n in els if n['id']!=b['id'] and 0<b['y']-n['y']<=85
                       and abs(n['x']-b['x'])<=12 and len(n['text'])<=100
                       and not BENEFIT.search(n['text']) and '%' not in n['text']]
                if not names:continue
                if len(names)!=1 or names[0]['id'] in used:
                    raise ValueError('Ambiguous No Name card geometry; refusing brand pairing')
                n=names[0];used.add(n['id'])
                add(rec['id']+':'+n['id'],n['text'],b['text'],conditions=b['text'],
                    link_kind='page_block',locator='#'+rec['id']+' [data-elem-id="'+n['id']+'"]',
                    details={'benefit_element_id':b['id'],'pairing':'same_record_aligned_column_nearest_label'},
                    warnings=['conditions_share_the_benefit_block'])
    elif source=='ural':
        for card in soup.select('li[id^="partner_"]'):
            name=node_text(card.select_one('.uk-accordion-title'))
            content=card.select_one('.uk-accordion-content')
            if not name or content is None:raise ValueError('Incomplete Ural card')
            intro=content.select_one('.margin-top--20px')
            terms=content.select_one('.uan-styled-text') or content
            # Source table rows retain card-level columns; no cross-tier rate maximum is taken.
            claims=[node_text(x) for x in terms.select('p,li,tr') if re.search(r'%|скидк|подар|мил[ьяию]|бонус',node_text(x),re.I)]
            benefit='\n'.join(dict.fromkeys(claims)) or node_text(intro) or node_text(terms)
            out_url=urlsplit(url)._replace(query='',fragment=card['id']).geturl()
            result.append(make_offer(source,card['id'],PROGRAMS[source],name,benefit,out_url,observed_at,
                          conditions=node_text(terms),tables=tables_in(terms),
                          redemption='\n'.join(node_text(x) for x in terms.select('ol')),
                          link_kind='page_anchor',locator='#'+card['id']))
    elif source=='rgo':
        h=soup.select_one('h1');name=node_text(h)
        blocks=soup.select('.section-text-2col,.section-text')
        terms='\n'.join(dict.fromkeys(node_text(b) for b in blocks if node_text(b)))
        if not name or not terms:raise ValueError('Missing RGO offer content')
        add(urlsplit(url).path.rstrip('/').split('/')[-1],name,terms,conditions=terms,
            locator='h1 + .section-text-2col / .section-text',warnings=['published_text_requires_eligibility_check'])
    elif source in ('sogaz_medi','ekp_medi'):
        contents=soup.select('.content');content=next((x for x in contents if 'скидк' in node_text(x).lower()),None)
        if not content:raise ValueError('Missing MEDI partner terms')
        benefit='\n'.join(node_text(x) for x in content.select('li'))
        add(source,'МЕДИ',benefit or node_text(content),conditions=node_text(content),locator='.content')
    elif source in ('ekp_neva','mir_neva'):
        title=soup.select_one('h1')
        content=soup.select_one('.stock-left-contentId')
        if not content:raise ValueError('Unknown Neva detail markup')
        add(urlsplit(url).path,'Нева Тревел',node_text(content),conditions=node_text(content),title=node_text(title),locator='.stock-left-contentId')
    elif source=='rusimp':
        headings=soup.select('.product-card__heading')
        plans=soup.select('.museum-friend')
        if len(headings)!=len(plans):raise ValueError('Museum plan grouping changed')
        for heading,plan in zip(headings,plans):
            name=node_text(heading.select_one('h3'))
            benefit='\n'.join(node_text(x) for x in plan.select('.museum-friend-adv'))
            add(name,name,benefit,conditions=node_text(heading),record_kind='membership_plan',
                link_kind='page_block',locator='.product-card__heading = '+name,
                details={'plan_price_text':node_text(heading.select_one('.h4'))})
    elif source=='azimut':
        # Table columns explicitly bind each perk to a membership tier. Image-coded values
        # remain references when no textual value is published; do not guess SVG numbers.
        table=soup.select_one('table');notes=node_text(table.find_next_sibling(class_='t-note1')) if table else ''
        header=table.select('thead tr')[0] if table else None
        levels=[node_text(x) for x in header.select('th')][1:] if header else []
        if table:
            for row in table.select('tbody tr'):
                cells=row.select('td')
                if len(cells)!=len(levels)+1:raise ValueError('AZIMUT tier table width changed')
                name=node_text(cells[0]);values=[]
                for level,c in zip(levels,cells[1:]):
                    images=[x.get('src','') for x in c.select('img')]
                    flag=True if images and all('/b-yes-' in x for x in images) else False if images and all('/b-no-' in x for x in images) else None
                    values.append({'tier':level,'included':flag,'text':node_text(c),'source_icons':images})
                add('table:'+name,'AZIMUT Hotels',name,conditions='\n'.join(levels)+'\n'+notes,details={'tier_values':values},
                    record_kind='tier_benefit',link_kind='page_block',locator='table tbody tr = '+name,
                    warnings=['consult_linked_program_rules_for_operating_conditions'])
        for card in soup.select('.post-mini'):
            name=node_text(card.select_one('.post-mini__title'));benefit=node_text(card.select_one('.post-mini__text'))
            if not name or not benefit:continue
            a=card.select_one('a.post-mini__link-overlay[href]')
            add('card:'+name,'AZIMUT Hotels',benefit,title=name,link_kind='page_block',locator='.post-mini = '+name,
                details={'terms_url':urljoin(url,a['href']) if a else None},
                warnings=['card_summary_tier_eligibility_is_in_separate_table_and_rules'])
    elif source=='promomiles':
        for card in soup.select('a.promotion-mini[href]'):
            heading=node_text(card.find_previous('h2'))
            archived=bool(re.search(r'заверш[её]н',heading,re.I))
            name=node_text(card.select_one('.promotion-mini__title'));benefit=node_text(card.select_one('.promotion-mini__text'))
            target=urljoin(url,card['href'])
            result.append(make_offer(source,card['href'],PROGRAMS[source],None,benefit,url,observed_at,
                         title=name,conditions=node_text(card.select_one('.promotion-mini__info')),
                         record_kind='campaign',source_status='archived' if archived else 'published',
                         details={'detail_url':target},link_kind='catalog_link',locator='.promotion-mini[href="'+card['href']+'"]',
                         warnings=['catalog_announcement_not_full_campaign_rules']))
    else:raise ValueError('No reviewed extractor for source '+source)
    seen=set()
    for r in result:
        if r['id'] in seen:raise ValueError('Duplicate native offer identity')
        seen.add(r['id'])
    return result

def ural_catalog(data,url,observed_at):
    categories={x['id']:x for x in data['category']}
    records=[]
    for p in data['partners']:
        raw=p.get('text',{}).get('detail','')
        if not text(raw):
            continue
        category=categories.get(p.get('category'),{})
        detail=BeautifulSoup(raw,'html.parser')
        claims=[node_text(x) for x in detail.select('p,li,tr') if re.search(r'%|скидк|подар|мил[ьяию]|бонус',node_text(x),re.I)]
        benefit='\n'.join(dict.fromkeys(claims)) or text(raw)
        native='partner_'+str(p['id'])
        target='https://www.uralairlines.ru/partners/#'+native
        records.append(make_offer('ural',native,PROGRAMS['ural'],p['name'],benefit,target,observed_at,
          conditions=text(raw)+'\n'+text(category.get('text')),category=category.get('name'),tables=tables_in(detail),
          redemption='\n'.join(node_text(x) for x in detail.select('ol')),
          details={'city_ids':p.get('city',[]),'retrieval_url':url,'preview':text(p.get('text',{}).get('preview'))},
          link_kind='page_anchor',locator='#'+native))
    return records

def key_catalog(data,observed_at):
    records=[];url=data['source_urls']['base_catalog']
    for p in data['partners']:
        records.append(make_offer('key',p['id'],'KEY',p['name'],'\n'.join(p['perks']),url,observed_at,
          conditions=p.get('scope','')+'\n'+p.get('source',{}).get('conditions',''),
          link_kind='api_record',locator='partners.cards.'+p['id'],
          details={'brands':p['brands'],'partner_source':p['source'],'source_fetched_at':data['fetched_at'],'remote_ok':data['remote_ok']},
          warnings=['KEY_published_catalog_not_hotel_booking_eligibility_confirmation']))
    for offer in dict.fromkeys(data.get('special_offers',{}).get('ru',[])):
        native='special:'+hashlib.sha256(offer.encode()).hexdigest()[:24]
        records.append(make_offer('key',native,'KEY',None,offer,url,observed_at,
          record_kind='campaign',link_kind='api_record',locator='specialOffers.ru: '+offer,
          warnings=['special_offer_has_no_native_id_text_based_identity']))
    return records


def mir_page_url(source_query: str, link: str, base: str) -> str:
    """Follow the published read-only pagination link without stale POST page state."""
    target=urlsplit(urljoin(base,link))
    query=dict(parse_qsl(urlsplit(source_query).query))
    query.update(parse_qsl(target.query))
    return target._replace(query=urlencode(query)).geturl()
