"""Airline public tier sections. Rules are preserved, never reduced to a best rate."""
from __future__ import annotations
import json
import math
from decimal import Decimal
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup, Tag
from html_text import html_text
from normalized import canonical_url, make_offer, number, NUMERIC_TOKEN, literal_number
from partner_pages import content
from read_budget import within_source_budget

URAL_URL='https://www.uralairlines.ru/wings_rules/'
UTAIR_URL='https://media.utair.ru/status'
# Historical ID aliases are not an accepted-tier list. New labels are discovered.
URAL_LEGACY_IDS={'Синий':'blue','Серебряный':'silver','Золотой':'gold'}


def _match_text(value):
    return ' '.join(value.split())


def _qualification_number(match,*,integer=False):
    value=literal_number(match[1])
    if value is None or (integer and (not value.isdecimal() or int(value)<=0)):
        raise ValueError('tier_qualification_invalid_number')
    return int(value) if integer else value


def _qualification_clause(value,anchor,pattern):
    markers=list(re.finditer(anchor,value,re.I))
    if not markers:return None
    if len(markers)!=1:raise ValueError('ural_qualification_number_ambiguous')
    found=re.match(pattern,value[markers[0].start():],re.I)
    if found is None:raise ValueError('ural_qualification_number_missing')
    return found


def heading_body(heading):
    nodes=[]
    for node in heading.next_siblings:
        if isinstance(node,Tag) and node.name=='h2':break
        if isinstance(node,Tag):nodes.append(node)
    return nodes


def ural_tiers(raw, observed_at):
    soup=BeautifulSoup(raw,'html.parser')
    headings=soup.select('.uan-styled-text h2')
    general=[]
    for h in headings:
        if re.match(r'Бонусы программы|Уровни участия',_match_text(html_text(h))):
            general.append(content([h,*heading_body(h)]))
    observed=[];seen=set()
    for heading in headings:
        match=re.fullmatch(r'(.+?)\s+уровень',html_text(heading),re.I|re.S)
        if not match:continue
        label=match[1].strip()
        if not label or _match_text(label).casefold() in seen:raise ValueError('ural_tier_heading_missing_or_duplicated')
        seen.add(_match_text(label).casefold());observed.append((label,heading))
    if not observed or len(observed)>100:raise ValueError('ural_tier_inventory_bound')
    rows=[]
    for label,heading in observed:
        key=URAL_LEGACY_IDS.get(label,label.casefold())
        nodes=heading_body(heading);body=BeautifulSoup(''.join(map(str,nodes)),'html.parser')
        first=body.select_one('li')
        if first is None:raise ValueError('ural_qualification_missing')
        qualification=html_text(first);flat_qualification=_match_text(qualification)
        if sum('Присваивается' in html_text(n) for n in body.select('li'))>1:
            raise ValueError('ural_tier_boundary_ambiguous')
        q={'evidence':qualification,'registration':bool(re.search('при регистрации',flat_qualification,re.I)),
           'flights':None,'spend_rub':None,'operator':None,'window':None,'window_years':None,'required_previous_tier':None}
        f=_qualification_clause(flat_qualification,r'при совершении',rf'при совершении ({NUMERIC_TOKEN}) пол[её]т(?:ов|а)?\b')
        amount=_qualification_clause(flat_qualification,r'на сумму',rf'на сумму ({NUMERIC_TOKEN}) рубл(?:ей|я|ь)\b')
        years=_qualification_clause(flat_qualification,r'в течение',rf'в течение ({NUMERIC_TOKEN}) календарн(?:ого|ых) (?:года|лет)\b')
        if f:q['flights']=_qualification_number(f,integer=True)
        if amount:q['spend_rub']=_qualification_number(amount)
        if f and amount and 'либо' in flat_qualification:q['operator']='OR'
        if years:
            q['window_years']=_qualification_number(years,integer=True)
            if q['window_years']==1:q['window']='calendar_year'
        previous=re.search(r'участнику\s+([^,.]+?)\s+уровня',flat_qualification,re.I)
        if previous:
            q['required_previous_tier_evidence']=previous[0]
            candidates=[name for name,_ in observed if previous[1].casefold() in
                (_match_text(name).casefold(),re.sub(r'ый$', 'ого', _match_text(name).casefold()),re.sub(r'ий$', 'его', _match_text(name).casefold()))]
            if len(candidates)==1:q['required_previous_tier']=candidates[0]
        rates=[]
        for paragraph in body.select('p'):
            for line in content([paragraph]).splitlines():
                m=re.fullmatch(r'(\d+(?:[.,]\d+)?)\s*%\s+от суммы авиабилета\b.*',line)
                if m:
                    rates.append({'kind':'points','value':number(m[1]),'unit':'percent',
                        'reward_unit':'program_bonus','basis':'airfare_as_published','evidence':line})
        # A non-percentage tier remains a tier: preserve its complete section.
        evidence=content(nodes)
        rows.append(make_offer('ural_tiers','tier:'+key,'Уральские авиалинии — «Крылья»',
            'Уральские авиалинии',evidence,URAL_URL,observed_at,title=label+' уровень',
            record_kind='tier_benefit',link_kind='page_block',locator='h2='+label+' уровень',
            conditions='\n'.join([qualification,*general]),details={
                'tier':label,'qualification':q,'flight_bonus_rates':rates,
                'reward_account':'program_bonus_not_bank_cashback',
                'general_rules_excerpt':'\n'.join(general),
                'scope':'published_tier_section_including_nested_restrictions'},
            warnings=['actual_member_tier_not_verified','all_source_restrictions_apply',
                      'tier_duration_is_not_offer_expiry','bonus_points_are_not_purchase_price_discount']))
    return rows


def _rect(node):
    values=[float(node[f'data-field-{p}-value']) for p in ('left','top','width','height')]
    if not all(math.isfinite(x) for x in values) or any(x<=0 for x in values[2:]):
        raise ValueError('invalid_utair_tab_geometry')
    return values


def _inside(node,rect):
    x,y,w,h=_rect(node);left,top,width,height=rect
    return left<=x+w/2<=left+width and top<=y+h/2<=top+height


def utair_tabs(raw):
    """Discover every current tab from the site's geometry, not a name enum."""
    soup=BeautifulSoup(raw,'html.parser')
    nav=soup.select('#rec759374982')
    if len(nav)!=1:raise ValueError('utair_tab_header_missing')
    blocks=nav[0].select('.status-block')
    if not blocks or len(blocks)>100:raise ValueError('utair_tab_inventory_bound')
    elements=nav[0].select('.t396__elem[data-elem-type="text"]')
    result={};owned=set()
    for block in blocks:
        box=_rect(block)
        texts=sorted([n for n in elements if _inside(n,box)],key=lambda n:(_rect(n)[1],_rect(n)[0]))
        if len(texts)!=2 or any(id(n) in owned for n in texts):raise ValueError('utair_tab_geometry_ambiguous')
        owned.update(id(n) for n in texts)
        tier,price=[html_text(n) for n in texts]
        if not tier or _match_text(tier).casefold() in {_match_text(t).casefold() for t in result}:raise ValueError('utair_duplicate_or_empty_tier')
        hints=[html_text(n) for n in nav[0].select('.t396__elem[data-elem-type="tooltip"]') if _inside(n,box)]
        if len(hints)>1:raise ValueError('utair_qualification_window_ambiguous')
        amount=re.fullmatch(rf'[cс] ({NUMERIC_TOKEN}) тыс\. руб\.',_match_text(price),re.I)
        window='calendar_year' if hints and 'календарном году' in _match_text(hints[0]) else None
        result[tier]={'tier':tier,'qualification_text':price,'scope_text':hints[0] if hints else None,
                      'spend_rub':number(str(Decimal(_qualification_number(amount))*1000)) if amount else None,
                      'window':window}
    if len(owned)!=len(elements):raise ValueError('utair_unowned_tab_text')
    return result


def utair_tab(raw, tier):
    tabs=utair_tabs(raw)
    if tier not in tabs:raise ValueError('utair_tier_not_in_current_page')
    return tabs[tier]


def utair_intro_context(raw):
    soup=BeautifulSoup(raw,'html.parser')
    observations=[];amounts=set()
    for block in soup.select('.t-rec'):
        value=html_text(block);flat_value=_match_text(value)
        if not flat_value.startswith('Программа лояльности Utair Status'):continue
        for match in re.finditer(r'с ([\d \u00a0]+) ₽, потраченных на полеты',flat_value):
            amount=number(match[1].strip());amounts.add(amount)
            observations.append({'spend_rub':amount,'evidence':value})
    return {'observations':observations,'spend_rub_values':sorted(amounts,key=int),
            'conflict':len(amounts)>1,'basis':'published_intro_blocks_not_tier_qualification_table'}


def utair_tier(panel_html, tab, exclusions, observed_at, *, intro_context=None):
    if not isinstance(tab.get('tier'),str) or not tab['tier'].strip():raise ValueError('invalid_utair_selected_tier')
    soup=BeautifulSoup(panel_html,'html.parser')
    panels=soup.select('.t-rec.description.active')
    if len(panels)!=1:raise ValueError('utair_panel_not_uniquely_active')
    panel=panels[0];evidence=content([panel])
    if not evidence:raise ValueError('utair_active_panel_empty')
    blocks=[]
    for node in panel.select('.t396__elem'):
        value=content([node])
        if value:blocks.append({'kind':node.get('data-elem-type'),'source_element_id':node.get('data-elem-id'),'text':value})
    links=[];skipped=0
    for a in panel.select('a[href]'):
        try:url=canonical_url(urljoin(UTAIR_URL,a['href']))
        except (ValueError,TypeError):skipped+=1;continue
        item={'label':html_text(a),'url':url}
        if item not in links:links.append(item)
    warnings=['linked_full_rules_not_fetched','actual_member_tier_not_verified',
              'layout_blocks_not_individual_offer_counts','inheritance_not_expanded']
    if skipped:warnings.append('signed_or_unsupported_rules_links_not_persisted')
    if intro_context and intro_context['conflict']:warnings.append('conflicting_intro_spend_thresholds')
    return make_offer('utair_tiers','tier:'+tab['tier'].lower(),'Utair Status','Utair',
        evidence,UTAIR_URL,observed_at,title='Уровень '+tab['tier'],record_kind='tier_benefit',
        link_kind='page_block',locator='tab='+tab['tier']+'; active #'+str(panel.get('id')),
        conditions='\n'.join(filter(None,(tab['qualification_text'],tab['scope_text'],exclusions))),
        details={'tier':tab['tier'],'qualification':tab,'active_panel_id':panel.get('id'),
                 'source_blocks':blocks,'linked_rules':links,'intro_context':intro_context,
                 'inherits_previous_tiers':bool(re.search(r'Доступны привилегии предыдущ',evidence)),
                 'scope':'visible_selected_tier_and_embedded_tooltips'},warnings=warnings)


async def collect_utair_tiers(client,cfg,report,now,limit):
    raw=await within_source_budget(client,lambda:client.read(UTAIR_URL,render=True))
    headers=utair_tabs(raw)
    soup=BeautifulSoup(raw,'html.parser')
    exclusions=[html_text(n) for n in soup.select('.t-rec')
                if _match_text(html_text(n)).startswith('Привилегии не предоставляются')]
    if len(exclusions)!=1:raise ValueError('utair_general_exclusions_not_found')
    report['discovered']=len(headers);rows=[];panels=set()
    nav=client.page.locator('#rec759374982')
    for tier in list(headers)[:limit]:
        try:
            async def read_tier():
                await nav.scroll_into_view_if_needed(timeout=4000)
                label=nav.get_by_text(tier,exact=True)
                box=await label.bounding_box()
                if not box:raise RuntimeError('utair_label_not_visible')
                # The site's transparent click target covers the text: use the
                # same screen point as a normal user, not JS class mutation.
                await client.page.mouse.click(box['x']+box['width']/2,box['y']+box['height']/2)
                await client.page.wait_for_timeout(350)
                active=client.page.locator('.t-rec.description.active')
                if await active.count()!=1:raise RuntimeError('utair_active_panel_ambiguous')
                return await active.evaluate('(e)=>e.outerHTML')
            panel=await within_source_budget(client,read_tier)
            row=utair_tier(panel,headers[tier],exclusions[0],now,intro_context=utair_intro_context(raw))
            pid=row['details']['active_panel_id']
            if pid in panels:raise RuntimeError('utair_tier_click_did_not_switch_panel')
            panels.add(pid);rows.append(row)
        except Exception as exc:
            report['errors'].append({'phase':'tier','tier':tier,
                'reason':str(exc)[:180] if isinstance(exc,RuntimeError) else type(exc).__name__})
            break
    if limit<len(headers):report['errors'].append({'phase':'tier','reason':'record_limit','limit':limit})
    report['coverage']=json.dumps({'method':'visible_tier_tab_clicks','discovered_tiers':list(headers),
        'read_tiers':[r['details']['tier'] for r in rows],'linked_rules_read':False},ensure_ascii=False)
    return rows


async def collect_ural_tiers(client,cfg,report,now,limit):
    raw=await within_source_budget(client,lambda:client.read(URAL_URL,render=True))
    rows=ural_tiers(raw,now);report['discovered']=len(rows)
    report['coverage']=json.dumps({'method':'all_current_tier_headings','discovered_tiers':[r['details']['tier'] for r in rows],'no_member_eligibility_verification':True},ensure_ascii=False)
    if limit<len(rows):report['errors'].append({'phase':'tier','reason':'record_limit','limit':limit})
    return rows[:limit]
