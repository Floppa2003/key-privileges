"""Exact reviewed partner-page boundaries; not a generic entire-site extractor."""
from __future__ import annotations
import json,re
from pathlib import Path
from datetime import datetime
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from normalized import make_offer,text,canonical_url

CONFIG=json.loads(Path(__file__).with_suffix('.json').read_text(encoding='utf8'))
MONTHS={'января':1,'февраля':2,'марта':3,'апреля':4,'мая':5,'июня':6,'июля':7,
        'августа':8,'сентября':9,'октября':10,'ноября':11,'декабря':12}


def content(nodes):
    # Block boundaries matter; <strong>60 руб</strong> is inline, not a new clause.
    output=[]
    for n in nodes:
        clone=BeautifulSoup(str(n),'html.parser')
        for br in clone.select('br'):br.replace_with('\n')
        for block in clone.find_all(['p','li','div','section','h1','h2','h3','h4','tr']):
            block.insert_before('\n');block.insert_after('\n')
        value=text(clone.get_text(' ',strip=False))
        value=re.sub(r' *\n[ \n]*','\n',value).strip()
        if value:output.append(value)
    return '\n'.join(output)


def required(soup,selectors):
    nodes=[]
    for selector in selectors:
        matches=soup.select(selector)
        if not matches:raise ValueError('Reviewed partner content selector disappeared: '+selector)
        nodes.extend(matches)
    return nodes


def explicit_period(value,rule):
    """Only an explicitly labelled offer interval, not all date-looking text."""
    flat=re.sub(r'\s+',' ',value)
    if rule=='full_dmy':
        m=re.search(r'Предложение действует с (\d{2}\.\d{2}\.\d{4}) (?:по|до) (\d{2}\.\d{2}\.\d{4})',flat,re.I)
        if m:return *(datetime.strptime(s,'%d.%m.%Y').date().isoformat() for s in m.groups()),m[0]
    elif rule=='shared_year_dmy':
        m=re.search(r'Срок действия акции:\s*(\d{2}\.\d{2})\s*[-–—]\s*(\d{2}\.\d{2})[ .]*(\d{4})',flat,re.I)
        if m:return *(datetime.strptime(s+'.'+m[3],'%d.%m.%Y').date().isoformat() for s in (m[1],m[2])),m[0]
    elif rule=='single_month':
        m=re.search(r'Срок проведения акции с (\d{1,2}) по (\d{1,2}) ('+'|'.join(MONTHS)+r') (\d{4})',flat,re.I)
        if m:return *(datetime(int(m[4]),MONTHS[m[3].lower()],int(s)).date().isoformat() for s in (m[1],m[2])),m[0]
    return None,None,None


def extract_partner_page(source,soup,url,observed_at):
    cfg=CONFIG[source]
    if canonical_url(url)!=canonical_url(cfg['url']):
        raise ValueError('Requested URL is not the reviewed partner offer URL')
    blocks=required(soup,cfg['selectors']);terms=content(blocks)
    flat=re.sub(r'\s+',' ',terms)
    program_rx=r'Аэрофлот.{0,5}Бону[сc]' if source.startswith('af_') else r'РЖД.{0,5}Бонус' if source.startswith('rzd_') else r'Един\w* карт\w* петербуржца|ЕКП'
    program_rx=cfg.get('program_regex',program_rx)
    if not re.search(program_rx,flat,re.I):raise ValueError('Partner content does not name the requested program')
    if not re.search(r'мил[ьяюеи]|милz|скидк',flat,re.I):raise ValueError('Missing actual partner benefit')
    details={'source_scope':'reviewed_partner_page_not_program_catalog',
             'partner_identity_origin':'reviewed_exact_partner_owned_url'}
    date_from,date_until,date_evidence=explicit_period(terms,cfg.get('date_rule'))
    if date_evidence:details['validity_evidence']=date_evidence
    warnings=['publication_is_not_confirmation_of_current_user_eligibility']+cfg.get('warnings',[])
    if cfg.get('date_rule') and not date_evidence:warnings.append('explicit_period_not_extracted')
    def make(native,benefit,**kwargs):
        return make_offer(source,native,cfg['program'],cfg['partner'],benefit,url,observed_at,
            category=cfg['category'],conditions=terms,locator=' + '.join(cfg['selectors']),
            warnings=warnings.copy(),details={**details,**kwargs.pop('details',{})},**kwargs)
    if source=='af_askona':
        # A finite multiplier is not the ongoing base accrual rate.
        # Identify the undated accrual clause by its role, not today's rate.
        # Dated campaign sentences cannot supply a fallback base rate.
        rate_pattern=r'\d+(?:[.,]\d+)?\s+мил[ьяюие]\w*.*?за каждые\s+\d[\d \u00a0\u202f]*(?:[.,]\d+)?\s+(?:руб\w*|₽)'
        period_pattern=r'\b(?:период|акци\w*|срок)\b|(?<!\d)\d{1,2}[./]\d{1,2}[./]\d{4}'
        base=[sentence for sentence in re.split(r'(?<=[.!?])\s+',flat)
              if re.search(rate_pattern,sentence,re.I) and not re.search(period_pattern,sentence,re.I)]
        promo=re.search(r'В период с (\d{2}\.\d{2}\.\d{4}) по (\d{2}\.\d{2}\.\d{4}) (.*?начисляется \d+(?:[.,]\d+)? мил[ьяюи][^.]*\.)',flat,re.I)
        if len(base)!=1:raise ValueError('Askona undated base accrual missing or ambiguous')
        rows=[make('base',base[0],details={'rate_scope':'base','has_separate_dated_promotion':bool(promo)})]
        if promo:
            start,end=(datetime.strptime(s,'%d.%m.%Y').date().isoformat() for s in (promo[1],promo[2]))
            rows.append(make('promotion:'+start+':'+end,promo[0],record_kind='campaign',valid_from=start,valid_until=end,
                             details={'rate_scope':'temporary_multiplier','validity_evidence':promo[0]}))
        return rows
    if source=='ekp_rostelecom':
        paragraph=next((p for p in blocks[0].select('p') if 'новые клиенты' in text(p.get_text(' ',strip=True))),None)
        if paragraph is None:raise ValueError('Rostelecom audience paragraph missing')
        prose=text(paragraph.get_text(' ',strip=True))
        m=re.fullmatch(r'(.*?новые клиенты.*?) (Для действующих абонентов.*?) (Подробная информация.*)',prose,re.S)
        if not m:raise ValueError('Rostelecom audience boundaries changed')
        publication=soup.select_one('.newsdata')
        publication=datetime.strptime(text(publication.get_text()),'%d.%m.%Y').date().isoformat() if publication else None
        return [make(audience,claim,redemption=m[3],details={'audience':audience,'article_published_at':publication,
              'limitations':'press_release_not_full_partner_card_rules'})
                for audience,claim in [('new_customers',m[1]),('existing_customers',m[2])]]
    if source=='nordwind_domina':
        match=re.search(r'Каждые ([0-9 ]+)₽, потраченные в Domina Пулково ([0-9]+) мил[ьяию]',flat)
        if not match:raise ValueError('Nordwind hotel earning card changed')
        return [make('offer',match[0],details={'earning_rule':{
            'value':match[2],'unit':'miles','basis_amount':match[1].replace(' ',''),'basis_unit':'RUB','evidence':match[0]}})]
    benefit=content(required(soup,cfg['benefit_selectors'])) if cfg.get('benefit_selectors') else terms
    return [make('offer',benefit,valid_from=date_from,valid_until=date_until)]


def utair_partners(soup,url,observed_at):
    panel=soup.select_one('#rec774882292.uc-showmore3')
    if not panel:raise ValueError('Utair partner panel missing')
    names={'utair.tvil.ru':'ТВИЛ.РУ','otello.2gis.ru':'Otello','utair.ostrovok.ru':'Островок!',
           'utair.iway.ru':'i’way','utair.sutochno.ru':'Суточно.ру'}
    rows=[];seen=set()
    for a in panel.select('a[href]'):
        claim=text(a.get_text(' ',strip=True))
        if not re.search(r'\d[,.\d]*%\s+милями',claim,re.I):continue
        target=canonical_url(a['href']);host=urlsplit(target).hostname
        if target in seen:continue
        seen.add(target)
        if host not in names:raise ValueError('Unknown Utair partner destination; identity review required')
        tier_rates=[]
        for clause in re.split(r'(?<=[.!])\s+',claim):
            tiers=re.findall(r'\b(?:Start|Basic|Bronze|Silver|Gold|Platinum)\b',clause)
            rate=re.search(r'(\d+(?:[.,]\d+)?)%\s+милями',clause)
            if tiers and rate:tier_rates.append({'tiers':tiers,'value':rate[1].replace(',','.'),'unit':'percent_miles','evidence':clause})
        native=host+urlsplit(target).path
        rows.append(make_offer('utair_media',native,'Utair Status',names[host],claim,url,observed_at,
            conditions=claim,redemption='Переход по опубликованной ссылке партнёра; полные условия на стороне партнёра не проверены.',
            link_kind='page_block',locator='#rec774882292 a[href="'+a['href']+'"]',
            details={'partner_url':target,'tier_rates':tier_rates,'partner_identity_origin':'reviewed_destination_domain'},
            warnings=['public_partner_card_summary_not_full_partner_terms']))
    return rows
