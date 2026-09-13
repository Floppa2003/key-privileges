"""Airline public tier sections. Rules are preserved, never reduced to a best rate."""
from __future__ import annotations
import json
import math
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup, Tag
from normalized import canonical_url, make_offer, number, text
from partner_pages import content
from read_budget import within_source_budget

URAL_URL='https://www.uralairlines.ru/wings_rules/'
UTAIR_URL='https://media.utair.ru/status'
UTAIR_TIERS=('Start','Basic','Bronze','Silver','Gold','Platinum')


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
        if re.match(r'Бонусы программы|Уровни участия',text(h.get_text())):
            general.append(content([h,*heading_body(h)]))
    rows=[]
    for key,label in (('blue','Синий'),('silver','Серебряный'),('gold','Золотой')):
        matching=[h for h in headings if text(h.get_text())==label+' уровень']
        if len(matching)!=1:raise ValueError('ural_tier_heading_missing_or_duplicated')
        nodes=heading_body(matching[0]);body=BeautifulSoup(''.join(map(str,nodes)),'html.parser')
        first=body.select_one('li')
        if first is None:raise ValueError('ural_qualification_missing')
        qualification=text(first.get_text(' ',strip=True))
        if 'Присваивается' not in qualification:raise ValueError('ural_qualification_not_recognized')
        q={'evidence':qualification,'registration':bool(re.search('при регистрации',qualification,re.I)),
           'flights':None,'spend_rub':None,'operator':None,'window':None,'required_previous_tier':None}
        f=re.search(r'(\d+) пол[её]тов',qualification,re.I)
        amount=re.search(r'на сумму ([\d\s\u00a0]+) рублей',qualification,re.I)
        if f:q['flights']=int(f[1])
        if amount:q['spend_rub']=number(amount[1].strip())
        if f and amount and 'либо' in qualification:q['operator']='OR'
        if re.search(r'1 календарного года',qualification):q['window']='calendar_year'
        if re.search('участнику серебряного уровня',qualification,re.I):q['required_previous_tier']='Серебряный'
        rates=[]
        for paragraph in body.select('p'):
            for line in content([paragraph]).splitlines():
                m=re.fullmatch(r'(\d+(?:[.,]\d+)?)\s*%\s+от суммы авиабилета\b.*',line)
                if m:
                    rates.append({'kind':'points','value':number(m[1]),'unit':'percent',
                        'reward_unit':'program_bonus','basis':'airfare_as_published','evidence':line})
        if not rates:raise ValueError('ural_flight_rate_section_missing')
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


def utair_tab(raw, tier):
    if tier not in UTAIR_TIERS:raise ValueError('unknown_utair_tier')
    soup=BeautifulSoup(raw,'html.parser')
    nav=soup.select('#rec759374982')
    if len(nav)!=1:raise ValueError('utair_tab_header_missing')
    elements=nav[0].select('.t396__elem[data-elem-type="text"]')
    labels=[x for x in elements if text(x.get_text(' ',strip=True))==tier]
    if len(labels)!=1:raise ValueError('utair_tier_label_missing_or_duplicated')
    matching=[x for x in nav[0].select('.status-block') if _inside(labels[0],_rect(x))]
    if len(matching)!=1:raise ValueError('utair_tab_geometry_ambiguous')
    box=_rect(matching[0])
    prices=[text(x.get_text(' ',strip=True)) for x in elements if x is not labels[0] and _inside(x,box)]
    if len(prices)!=1:raise ValueError('utair_qualification_ambiguous')
    hints=[text(x.get_text(' ',strip=True)) for x in nav[0].select('.t396__elem[data-elem-type="tooltip"]') if _inside(x,box)]
    if len(hints)>1:raise ValueError('utair_qualification_window_ambiguous')
    amount=re.fullmatch(r'[cс] (\d+) тыс\. руб\.',prices[0],re.I)
    if not amount and prices[0].casefold()!='бесплатно':raise ValueError('utair_qualification_format_changed')
    window='calendar_year' if hints and 'календарном году' in hints[0] else None
    return {'tier':tier,'qualification_text':prices[0],'scope_text':hints[0] if hints else None,
            'spend_rub':str(int(amount[1])*1000) if amount else None,'window':window}


def utair_intro_context(raw):
    soup=BeautifulSoup(raw,'html.parser')
    observations=[];amounts=set()
    for block in soup.select('.t-rec'):
        value=text(block.get_text(' ',strip=True))
        if not value.startswith('Программа лояльности Utair Status'):continue
        for match in re.finditer(r'с ([\d \u00a0]+) ₽, потраченных на полеты',value):
            amount=number(match[1].strip());amounts.add(amount)
            observations.append({'spend_rub':amount,'evidence':value})
    return {'observations':observations,'spend_rub_values':sorted(amounts,key=int),
            'conflict':len(amounts)>1,'basis':'published_intro_blocks_not_tier_qualification_table'}


def utair_tier(panel_html, tab, exclusions, observed_at, *, intro_context=None):
    if tab.get('tier') not in UTAIR_TIERS:raise ValueError('invalid_utair_selected_tier')
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
        item={'label':text(a.get_text(' ',strip=True)),'url':url}
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
    headers={tier:utair_tab(raw,tier) for tier in UTAIR_TIERS}
    soup=BeautifulSoup(raw,'html.parser')
    exclusions=[text(n.get_text(' ',strip=True)) for n in soup.select('.t-rec')
                if text(n.get_text(' ',strip=True)).startswith('Привилегии не предоставляются')]
    if len(exclusions)!=1:raise ValueError('utair_general_exclusions_not_found')
    report['discovered']=len(headers);rows=[];panels=set()
    nav=client.page.locator('#rec759374982')
    for tier in UTAIR_TIERS[:limit]:
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
    report['coverage']='all_three_public_tier_sections_with_nested_conditions; no member eligibility verification'
    if limit<len(rows):report['errors'].append({'phase':'tier','reason':'record_limit','limit':limit})
    return rows[:limit]
