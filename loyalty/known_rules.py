"""Reviewed public rule documents. Never treat rule bundles as new cash discounts.

Selectors and identities are checked-in code. Scraped links are evidence only;
this adapter neither follows them nor submits forms/activates an entitlement.
"""
from __future__ import annotations
import asyncio,json,re
import requests
from pathlib import Path
from datetime import date
from decimal import Decimal
from urllib.parse import urljoin,urlsplit,parse_qsl
from bs4 import BeautifulSoup
from html_text import html_text
from normalized import (canonical_url,make_offer,number,NUMERIC_TOKEN,
                        literal_number,number_starts_here)
from partner_pages import content,MONTHS
from read_budget import within_source_budget
from source_diagnostics import ParseError
from known_rule_terms import retail_redemption_terms

CONFIG=json.loads(Path(__file__).with_suffix('.json').read_text(encoding='utf8'))
NUM=NUMERIC_TOKEN


def flat(value):
    return re.sub(r'\s+',' ',value).replace('‑','-').strip()


def literal_lines(value):
    return re.sub(r'[^\S\n]+',' ',value).replace('‑','-').strip()


def match(pattern,value,reason):
    folded=literal_lines(value)
    # Reviewed patterns use literal spaces as word separators. Allow their
    # words to wrap, while NUMERIC_TOKEN cannot absorb a neighbouring block.
    found=re.search(pattern.replace(' ',r'\s+'),folded,re.I|re.S)
    if not found:raise ValueError(reason)
    for index,group in enumerate(found.groups(),1):
        if group is not None and re.fullmatch(r'\d[\d\s.,]*',group):
            start=found.start(index)
            # A preceding tariff label can end in a digit and a sentence dot
            # ("Тариф 1+0. 10 услуг"); that space is not a decimal continuation.
            sentence_boundary=bool(re.search(r'[.)]\s+$',folded[:start]))
            literal_boundary=(sentence_boundary or number_starts_here(folded,start)) and not re.search(
                r'(?:[+−]\s*|[–—-]|\d\s*[–—-]\s*)$',folded[:start])
            if literal_number(group) is None or not literal_boundary:
                raise ValueError(reason)
    return found


def whole_count(value,reason):
    parsed=literal_number(value)
    if parsed is None or not parsed.isdecimal() or int(parsed)<=0:
        raise ValueError(reason)
    return int(parsed)


def unique_match(pattern,value,reason):
    matches=list(re.finditer(pattern.replace(' ',r'\s+'),literal_lines(value),re.I|re.S))
    if len(matches)!=1:raise ValueError(reason)
    return match(pattern,value,reason)


def owned_match(anchor,pattern,value,reason):
    """Own the label before parsing its value, including malformed values."""
    folded=literal_lines(value)
    anchors=list(re.finditer(anchor.replace(' ',r'\s+'),folded,re.I))
    if len(anchors)!=1:raise ValueError(reason)
    return match(r'\A(?:'+pattern+r')',folded[anchors[0].start():],reason)


def sim_delivery_terms(nodes):
    """Own the courier service before interpreting its generic price labels."""
    headings=[h for node in nodes for h in node.find_all(re.compile(r'^h[1-6]$'))
              if flat(html_text(h)).casefold()=='замена sim-карты без обращения в салон']
    if len(headings)>1:raise ValueError('sim_courier_section_ambiguous')
    if headings:
        heading=headings[0];section=[]
        for sibling in heading.next_siblings:
            if (getattr(sibling,'name',None) and re.fullmatch(r'h[1-6]',sibling.name)
                    and int(sibling.name[1])<=int(heading.name[1])):break
            section.append(str(sibling))
        return html_text(''.join(section))
    # Compatibility for the original plain article fragment. A service label
    # is still required; prices preceding it never belong to courier delivery.
    value=content(nodes)
    anchors=list(re.finditer(r'Курьерская\s+доставка\s+SIM[-‑]карты',value,re.I))
    if len(anchors)!=1:raise ValueError('sim_courier_section_missing_or_ambiguous')
    return value[anchors[0].start():]


def gpb_subscription(value,label):
    """Read only this card's price block, preserving explicit price phases."""
    price=flat(value).split('Мили «Аэрофлот Бонус»',1)[0].removeprefix(label).strip()
    if re.fullmatch(r'Бесплатно\.?',price,re.I):return '0',None
    phased=re.fullmatch(
        rf'(?:(?P<free>Бесплатно)|(?P<first>{NUM})\s*₽\s*в\s+месяц)\s*[—–-]\s*'
        rf'(?P<months>{NUM})\s+месяц(?:а|ев)?\s*,\s*далее\s*[—–-]\s*'
        rf'(?P<later>{NUM})\s*₽\s*в\s+месяц\.?',price,re.I)
    if phased:
        first='0' if phased['free'] else literal_number(phased['first'])
        later=literal_number(phased['later'])
        if first is None or later is None:raise ValueError('gpb_monthly_cost_invalid')
        months=whole_count(phased['months'],'gpb_introductory_duration_invalid')
        return later,{'monthly_rub':first,'months':months,'evidence':price}
    monthly=re.fullmatch(rf'({NUM})\s*₽\s*в\s+месяц\.?',price,re.I)
    if monthly:
        cost=literal_number(monthly[1])
        if cost is None:raise ValueError('gpb_monthly_cost_invalid')
        return cost,None
    if re.search(r'₽|далее|бесплатно',price,re.I):
        raise ValueError('gpb_subscription_price_missing_or_ambiguous')
    return None,None


def mileage_multiplier(value):
    """Keep full literal factors; repeated matching claims may not conflict."""
    folded=literal_lines(value)
    pattern=rf'(?:(?P<word>двойные|тройные|четверные)|(?P<number>{NUM})[-‑]кратные)\s+мили\b'
    factors=[];evidence=[]
    for found in re.finditer(pattern,folded,re.I):
        if found['word']:
            factor=str({'двойные':2,'тройные':3,'четверные':4}[found['word'].casefold()])
        else:
            prefix=folded[:found.start('number')]
            # The reviewed title's spaced dash separates its name and claim;
            # a sign on the numerical factor is not that title separator.
            title_separator=re.search(r'(?:^|\n)Поколения Utair\s+[-–—]\s+$',prefix,re.I)
            if (not number_starts_here(folded,found.start('number'))
                    or re.search(r'[\w.,]$',prefix)
                    or re.search(r'[+−–—-]\s*$',prefix) and not title_separator):
                raise ValueError('generations_reward_multiplier_invalid')
            factor=literal_number(found['number'])
            if factor is None or Decimal(factor)<=0:
                raise ValueError('generations_reward_multiplier_invalid')
        factors.append(factor);evidence.append(found[0])
    if len(set(factors))>1:raise ValueError('generations_reward_multiplier_ambiguous')
    if not factors:return None,None
    factor=factors[0]
    return int(factor) if factor.isdecimal() else factor,evidence[0]


def date_label(pattern,value):
    m=re.search(pattern,flat(value),re.I)
    if not m:return None,None
    day,month,year=m.groups()
    return date(int(year),MONTHS[month.lower()],int(day)).isoformat(),m[0]


def earning_rules(value):
    # Do not turn redemption percentages or background programme examples into
    # earning. The caller passes only a reviewed earning section.
    pattern=rf'(?P<n>{NUMERIC_TOKEN})\s+мил[ьяиюе]\w*(?:\s+начисляется)?(?:\s+«Аэрофлот\s+Бонус»)?\s+за\s+каждые\s+(?:потраченные\s+)?(?P<base>{NUMERIC_TOKEN})\s*(?:руб\w*|₽)'
    found=[]
    folded=literal_lines(value)
    for m in re.finditer(pattern,folded,re.I):
        amount,basis=literal_number(m['n']),literal_number(m['base'])
        if amount is None or basis is None or not number_starts_here(folded,m.start('n')):
            continue
        item={'value':amount,'unit':'miles','basis_amount':basis,
              'basis_unit':'RUB','evidence':m[0]}
        if item not in found:found.append(item)
    return found


def section_markers(value,*labels):
    """Match reviewed labels without folding away the original evidence spans."""
    markers=[]
    for label in labels:
        words=r'\s+'.join(re.escape(word) for word in label.split())
        matches=list(re.finditer(r'(?<!\w)'+words+r'(?!\w)(?:\s*:)?',value,re.I))
        if len(matches)!=1:raise ValueError('known_rule_section_missing_or_ambiguous')
        markers.append(matches[0])
    if any(a.end()>b.start() for a,b in zip(markers,markers[1:])):
        raise ValueError('known_rule_section_order_changed')
    return markers


def linked_documents(nodes,url):
    result=[]
    for node in nodes:
        for a in node.select('a[href]'):
            raw=urljoin(url,a['href'])
            try:
                canonical_url(raw)
                # Unlike identity canonicalization, retain non-secret campaign
                # parameters: a required utm_source can control eligibility.
                if any(re.search(r'token|secret|password|session|signature|auth',k,re.I)
                       for k,_ in parse_qsl(urlsplit(raw).query,keep_blank_values=True)):
                    continue
            except (ValueError,TypeError):continue
            item={'label':html_text(a),'url':raw,'fetched':False}
            if item not in result:result.append(item)
    return result


def scoped(source,raw,url):
    cfg=CONFIG[source]
    if canonical_url(url)!=canonical_url(cfg['url']):raise ValueError('known_rule_url_not_reviewed')
    soup=BeautifulSoup(raw,'html.parser')
    for n in soup.select('script,style,form,input,textarea'):n.decompose()
    nodes=[]
    for selector in cfg['selectors']:
        found=soup.select(selector)
        if not found or (cfg.get('single_selectors',True) and len(found)!=1):
            raise ParseError('known_rule_scope_missing_or_ambiguous', selector=selector, matches=len(found))
        nodes.extend(found)
    handler=cfg.get('handler')
    if handler=='headquarters':
        nodes=[n for n in nodes if (h:=n.select_one('.accordion__title-text')) is not None
               and flat(html_text(h))=='Перечень льготных категорий']
        if len(nodes)!=1:raise ValueError('rgo_discount_accordion_not_unique')
    if handler=='comfort':
        nodes=[n for n in nodes[0].select('.t509__colwrapper')
               if 'Comfort Pass стал партнером программы' in flat(html_text(n))]
        if len(nodes)!=1:raise ValueError('comfort_base_news_not_unique')
    if handler=='x5':
        headings=[flat(html_text(n.select_one('h2'))) for n in nodes]
        if sorted(headings)!=sorted(['О партнёре','Как воспользоваться?','Условия предложения']):
            raise ValueError('x5_rule_sections_changed')
    if handler=='gpb':
        products=[n for n in nodes if any(re.fullmatch(r'TariffsMsbItemContent_root__(?!.*__)[A-Za-z0-9_-]+',c) for c in n.get('class',[]))]
        titles=['Условия по карте','Условия программы лояльности «Аэрофлот Бонус»']
        triggers=[n for n in nodes if flat(html_text(n)) in titles]
        accordions=[n.find_parent(lambda parent:any(
            re.fullmatch(r'Accordion_root__(?!.*__)[A-Za-z0-9_-]+',c)
            for c in parent.get('class',[]))) for n in triggers]
        if (not 1<=len(products)<=100 or sorted(flat(html_text(n)) for n in triggers)!=sorted(titles)
                or any(n is None for n in accordions)
                or len({id(n) for n in accordions})!=len(titles)):
            raise ValueError('gpb_public_sections_ambiguous')
        nodes=products+accordions
    terms=content(nodes)
    if any(x.casefold() not in flat(terms).casefold() for x in cfg['required']):
        raise ValueError('known_rule_required_evidence_missing')
    if len(terms)>36000:raise ValueError('rule_document_too_large_no_truncation')
    return cfg,soup,nodes,terms


def parse_known_rule(source,raw,url,observed_at):
    cfg,soup,nodes,terms=scoped(source,raw,url)
    details={'evidence_role':'supplementary_rules_not_incremental_discount',
        'supplements_source_ids':cfg.get('supplements',[]),
        'scope':'reviewed_public_sections_only','linked_documents':linked_documents(nodes,url)}
    warnings=['user_eligibility_not_verified','rule_bundle_not_additive_discount']+cfg.get('warnings',[])
    benefit=terms;start=end=None;handler=cfg.get('handler')
    if handler=='gpb':
        options=[];benefit_clauses=[]
        products=[n for n in nodes if any(re.fullmatch(r'TariffsMsbItemContent_root__(?!.*__)[A-Za-z0-9_-]+',c) for c in n.get('class',[]))]
        labels=set()
        for node in products:
            value=html_text(node)
            heading=node.select('h5')
            if len(heading)!=1:raise ValueError('gpb_subscription_label_missing')
            label=flat(html_text(heading[0]))
            if not label or label in labels:raise ValueError('gpb_subscription_label_duplicate')
            labels.add(label)
            rate=match(r'Мили «Аэрофлот Бонус» ('+NUM+r') мил[ьяи] за ('+NUM+r') ₽ покупок',value,'gpb_rate_missing')
            cap=match(r'Максимум миль в месяц ('+NUM+r')(?= Переводы|$)',value,'gpb_cap_missing')
            benefit_clauses.append(label+': '+rate[0]+'; '+cap[0])
            cost,introduction=gpb_subscription(value,label)
            paid=(Decimal(cost)>0) if cost is not None else None
            options.append({'subscription':paid,'label':label,'miles':number(rate[1]),'basis_rub':number(rate[2]),
                'monthly_cap_miles':number(cap[1]),'monthly_subscription_rub':cost,'evidence':value})
            if introduction:options[-1]['introductory_subscription']=introduction
        minimum=match(r'Минимальная сумма покупок по карте в месяц [—–-] ('+NUM+r') ₽',terms,'gpb_minimum_missing')
        service=owned_match(r'Стоимость обслуживания',r'Стоимость обслуживания ('+NUM+r') ₽',terms,'gpb_service_fee_missing')
        notify=unique_match(r'со? ('+NUM+r') месяца [—–-] ('+NUM+r') ₽/мес',
                            terms,'gpb_notification_fee_missing')
        notification_month=Decimal(literal_number(notify[1]))
        if notification_month<=0 or notification_month!=notification_month.to_integral_value():
            raise ValueError('gpb_notification_month_invalid')
        fees={'card_service_rub':number(service[1]),
              'notifications_from_month':int(notification_month),
              'notifications_monthly_rub':number(notify[2]),'evidence':notify[0]}
        if notification_month==2:
            fees['notifications_after_first_month_rub']=fees['notifications_monthly_rub']
        details.update(mileage_options=options,monthly_minimum_purchases_rub=number(minimum[1]),
            minimum_evidence=minimum[0],fees=fees)
        benefit='\n'.join(benefit_clauses)
    elif handler=='retail_miles':
        first,second=section_markers(terms,'Условия начислений','Условия списаний')
        earning=terms[first.end():second.start()].strip()
        redemption=terms[second.end():].strip()
        rules=earning_rules(earning)
        if not rules:raise ValueError('retail_earning_rule_changed')
        details.update(earning_rules=rules,redemption_rules=retail_redemption_terms(redemption),
                       earning_conditions=earning)
        benefit=earning
    elif handler=='iway':
        e=nodes[0].select_one('.condition_earn')
        if e is None:raise ValueError('iway_earning_section_missing')
        first,second=section_markers(terms,'Накопить мили','Использовать мили')
        earning=content([e]);redemption=terms[second.end():]
        rates=[]
        for label,channel in ((r'При заказе поездки в i[’\']way','direct'),(r'При заказе через турагентство','travel_agent')):
            clause=owned_match(label,label+r'\s+('+NUM+r' мил[ьяиюе] за каждые потраченные '+NUM+r'\s*(?:₽|руб\w*))',earning,'iway_earning_channel_missing')
            parsed=earning_rules(clause[0])
            if len(parsed)!=1:raise ValueError('iway_ambiguous_channel_rate')
            rates.append({**parsed[0],'channel':channel,'evidence':clause[0]})
        details.update(earning_rules=rates,
            redemption_rules={'evidence':redemption},
            promotional_teaser={'evidence':terms[:first.start()],
                                'period_resolved':False,'not_a_cash_discount':True})
        benefit=earning;warnings.append('month_only_redemption_promotion_not_assigned_a_year')
    elif handler=='skyshop':
        first,second=section_markers(terms,'Условия начислений','Условия получения премий')
        earning=terms[first.end():second.start()]
        details.update(earning_rules=earning_rules(earning),redemption_rules={'evidence':terms[second.end():]})
        if not details['earning_rules']:raise ValueError('skyshop_earning_rule_missing')
        benefit=earning;warnings.append('rate_effective_date_not_full_offer_validity')
    elif handler=='x5':
        m=match(r'('+NUM+r') мил[ьяи] за каждые ('+NUM+r') балл(?:ов|а)?\b',terms,'x5_exchange_rule_missing')
        details['exchange_rule']={'miles':number(m[1]),'basis_amount':number(m[2]),'basis_unit':'X5_points','evidence':m[0]}
        end,evidence=date_label(r'Акция действует до (\d{1,2}) ('+'|'.join(MONTHS)+r') (\d{4})',terms)
        details['validity_evidence']=evidence
    elif handler in ('tripster','vipzal'):
        details['earning_rules']=earning_rules(terms)
        if not details['earning_rules']:raise ValueError('partner_earning_rule_missing')
        if handler=='tripster':warnings.append('publication_date_is_not_offer_start')
    elif handler=='comfort':
        details['earning_rules']=earning_rules(terms)
        if not details['earning_rules']:raise ValueError('comfort_base_rate_missing')
    elif handler=='students':
        age=owned_match(r'до (?=[^;\n]*?\(включительно\))',
                        rf'до ({NUM}) (?:год(?:а)?|лет) \(включительно\)',terms,'student_age_missing')
        activation=owned_match(r'в течение',rf'в течение ({NUM}) рабоч(?:их|его) дн(?:ей|я)\b',
                               terms,'student_activation_time_missing')
        expiry=unique_match(r'до (\d{1,2}) ('+'|'.join(MONTHS)+r') следующего учебного года',
                            terms,'student_relative_expiry_missing')
        # A leap year validates possible month/day pairs without assigning an
        # actual calendar year to the source's relative academic-year expiry.
        date(2000,MONTHS[expiry[2].casefold()],int(expiry[1]))
        details.update(age_max_inclusive=whole_count(age[1],'student_age_invalid'),
                       activation_workdays=whole_count(activation[1],'student_activation_time_invalid'),
                       entitlement_expiry_text=expiry[0])
        warnings.append('relative_student_entitlement_expiry_not_calendar_offer_end')
    elif handler=='sim':
        courier=sim_delivery_terms(nodes)
        delivery=owned_match(r'Стоимость услуги',r'Стоимость услуги [–—-] ('+NUM+r') руб',courier,'sim_delivery_price_missing')
        replacement=owned_match(r'Дополнительно оплачивается замена SIM-карты',r'Дополнительно оплачивается замена SIM-карты [–—-] ('+NUM+r') руб',courier,'sim_replacement_price_missing')
        free=match(r'Для участников программы T2 Selection услуга предоставляется бесплатно',courier,'sim_selection_delivery_missing')
        details['fees']={'delivery_standard_rub':number(delivery[1]),'replacement_rub':number(replacement[1]),
                         'delivery_selection_rub':'0','evidence':[delivery[0],replacement[0],free[0]]}
    elif handler=='magnit':
        details['activation']={'same_phone_required':bool(re.search('под номером, на котором подключена подписка',flat(terms))),
                               'evidence':terms}
    elif handler=='registration':
        details['scope']='public_registration_help_not_another_partner_catalog'
    elif handler=='mixx':
        value=content([soup.select_one('.terms-of-service')])
        price=match(r'в месяц\s*('+NUM+r')\s*₽',value,'mixx_monthly_price_missing')
        details['subscription']={'monthly_rub':number(price[1]),'evidence':value,
                                 'trial_end_not_assumed_one_month':True}
    elif handler=='azimut_earning':
        details['illustrative_examples_not_universal_rates']=True
        warnings.append('worked_examples_preserved_not_promoted_to_global_rates')
    elif handler=='family':
        maximum=owned_match(r'\bдо\s+(?=[^.!?;\n]*?\bсчет(?:ов|а)?\b)',r'до ('+NUM+r') счет(?:ов|а)?\b',terms,'family_account_bound_missing')
        months=owned_match(r'\bчерез\s+(?=[^.!?;\n]*?\bмесяц(?:ев|а)?\b)',r'через ('+NUM+r') месяц(?:ев|а)?\b',terms,'family_exit_bound_missing')
        cash=owned_match(r'Как минимум',r'Как минимум ('+NUM+r') рубл(?:ей|я|ь)\b',terms,'miles_minimum_cash_missing')
        details['family']={'max_accounts':whole_count(maximum[1],'family_account_invalid'),
            'minimum_membership_months':whole_count(months[1],'family_months_invalid'),
            'evidence':terms.split('Как минимум',1)[0]}
        details['miles_payment']={'minimum_cash_rub':number(cash[1]),'evidence':'Как минимум'+terms.split('Как минимум',1)[1]}
    elif handler=='generations':
        young=owned_match(r'от (?=[^,;\n]*?\bдо\b)',rf'от ({NUM}) до ({NUM}) (?:год(?:а)?|лет)\b',
                          terms,'generations_youth_age_missing')
        senior=owned_match(r'от (?=(?:(?!\bот\b)[^,;\n])*?\(для женщин\))',
                           rf'от ({NUM}) (?:год(?:а)?|лет) \(для женщин\), от ({NUM}) (?:год(?:а)?|лет) \(для мужчин\)',
                           terms,'generations_senior_age_missing')
        ages=[whole_count(v,'generations_age_invalid') for v in (*young.groups(),*senior.groups())]
        if ages[0]>ages[1]:raise ValueError('generations_youth_age_interval_invalid')
        youthcode=match(r'для молодежи\s+([A-Z][A-Z0-9]+)',terms,'generations_youth_code_missing')
        seniorcode=match(r'для людей старшего поколения\s+([A-Z][A-Z0-9]+)',terms,'generations_senior_code_missing')
        life=match(r'Срок действия миль.{0,60}составляет ('+NUM+r') (?:год(?:а)?|лет)\b',terms,'generations_reward_lifetime_missing')
        factor,multiplier_evidence=mileage_multiplier(terms)
        details.update(reward_multiplier=factor,reward_multiplier_evidence=multiplier_evidence,
          reward_lifetime_years=whole_count(life[1],'generations_reward_lifetime_invalid'),reward_lifetime_evidence=life[0],
          audiences=[{'audience':'youth','age_min':ages[0],'age_max':ages[1],'promo_code':youthcode[1],'evidence':[young[0],youthcode[0]]},
                     {'audience':'senior','women_age_min':ages[2],'men_age_min':ages[3],'promo_code':seniorcode[1],'evidence':[senior[0],seniorcode[0]]}])
        warnings.append('reward_lifetime_is_not_offer_expiry')
    elif handler=='mir101':
        pattern=r'Срок проведения Акции: с (\d{1,2}) ('+'|'.join(MONTHS)+r') (\d{4}) года'
        start,a=date_label(pattern,terms)
        end,b=date_label(r'Срок проведения Акции:.{0,50}? по (\d{1,2}) ('+'|'.join(MONTHS)+r') (\d{4}) года',terms)
        checkout,c=date_label(r'выезда не позднее (\d{1,2}) ('+'|'.join(MONTHS)+r') (\d{4}) года',terms)
        cap=match(r'но не более ('+NUM+r')\s*\([^)]*\) рублей за одно Бронирование',terms,'mir101_cap_missing')
        published=match(r'Акционный канал:\s*(https://101hotels\.com/\?utm_source=[A-Za-z0-9_-]+)',terms,'mir101_required_entry_url_missing')
        entry=published[1]
        canonical_url(entry)  # validate, but never strip the required campaign parameter
        details['required_entry_evidence']=published[0]
        if not start or not end or not checkout or not entry:raise ValueError('mir101_explicit_campaign_conditions_missing')
        details.update(validity_evidence=[a,b],checkout_deadline=checkout,checkout_evidence=c,
                       cashback_cap_rub=number(cap[1]),cashback_cap_evidence=cap[0],required_entry_url=entry)
    elif handler=='aeroexpress':
        end,evidence=date_label(r'можно до (\d{1,2}) ('+'|'.join(MONTHS)+r') (\d{4}) года',terms)
        if not end:raise ValueError('aeroexpress_end_missing')
        details['validity_evidence']=evidence
    elif handler=='otello':
        start,a=date_label(r'Срок активации промокода: с (\d{1,2}) ('+'|'.join(MONTHS)+r') (\d{4}) года',terms)
        end,b=date_label(r'Срок активации промокода:.{0,50}? по (\d{1,2}) ('+'|'.join(MONTHS)+r') (\d{4}) года',terms)
        if not start or not end:raise ValueError('otello_activation_period_missing')
        details.update(validity_evidence=[a,b],validity_scope='promo_activation_window')
    if handler=='smartavia':return smartavia_records(cfg,nodes,terms,details,warnings,url,observed_at)
    # Opt-in native tables from already scoped sections, never a fabricated table.
    tables=[[[html_text(cell) for cell in row.find_all(['th','td'],recursive=False)]
             for row in table.select('tr')] for node in nodes for table in node.select('table')] if cfg.get('capture_tables') else []
    return [make_offer(source,'rules:page',cfg['program'],cfg['partner'],benefit,url,observed_at,
        title=cfg['title'],conditions=terms,link_kind=cfg.get('link_kind','detail_page'),
        record_kind=cfg['record_kind'],locator=' + '.join(cfg['selectors']),details=details,
        warnings=warnings,valid_from=start,valid_until=end,tables=tables)]


def smartavia_records(cfg,nodes,terms,details,warnings,url,now):
    cards=nodes[0].select('.smartup-tariff-item')
    if not 1<=len(cards)<=20:raise ValueError('smartavia_plan_count_outside_bound')
    records=[];labels=set()
    for card in cards:
        value=content([card])
        # The visible label and value may be separate sibling blocks. Read
        # only this card's title; do not join the following price/benefit text.
        titles=card.select('.sm-title-extra')
        labels_in_card=([html_text(n) for n in titles] if titles else
                        re.findall(r'(?:^|\n)Тариф\s+([^\n]+?)(?=\.\s|\n|$)',value))
        if len(labels_in_card)!=1:raise ValueError('smartavia_plan_label_missing_or_ambiguous')
        key=labels_in_card[0].strip()
        if not key:raise ValueError('smartavia_plan_label_missing')
        travelers=re.fullmatch(r'1\+(0|[1-9]\d*)',key)
        if key in labels:raise ValueError('smartavia_duplicate_plan_label')
        labels.add(key)
        price=match(r'Оформить за ('+NUM+r')\s*₽',value,'smartavia_plan_price_missing')
        segments=match(r'('+NUM+r') сегмент(?:ов|а)? со скидкой ('+NUM+r') ₽',value,'smartavia_segments_missing')
        baggage=match(r'('+NUM+r') услуг(?:а|и)? «Багаж ('+NUM+r') кг» со скидкой ('+NUM+r') ₽',value,'smartavia_baggage_missing')
        d={**details,'subscription_plan':{'label':key,'additional_travelers':int(travelers[1]) if travelers else None,
           'annual_rub':number(price[1]),'flight_segments':whole_count(segments[1],'smartavia_segments_invalid'),
           'flight_discount_rub':number(segments[2]),
           'baggage_services':whole_count(baggage[1],'smartavia_baggage_count_invalid'),
           'baggage_kg':whole_count(baggage[2],'smartavia_baggage_weight_invalid'),'baggage_discount_rub':number(baggage[3]),
           'evidence':value},'scope':'published_plan_card_and_common_subscription_rules'}
        records.append(make_offer('smartavia_rules','plan:'+key,cfg['program'],cfg['partner'],value,url,now,
            title='Подписка Smartavia '+key,record_kind='membership_plan',link_kind='page_block',
            locator='.smartup-tariff-item label='+key,conditions=terms,details=d,
            warnings=warnings+['annual_plan_duration_not_offer_expiry','subscription_cost_is_not_discount']))
    # The EKP benefit is not applied silently to each published base plan price.
    claim=match(r'Все держатели ЕКП могут купить годовую Подписку Smartavia со скидкой ('+NUM+r')%\.',terms,'smartavia_ekp_claim_missing')
    if not 0<Decimal(number(claim[1]))<=100:raise ValueError('smartavia_ekp_percent_invalid')
    d={**details,'discount_percent':number(claim[1]),'discount_basis':'annual_subscription_not_air_ticket',
       'base_plan_prices_not_recalculated':True}
    records.append(make_offer('smartavia_rules','ekp:annual-subscription','Единая карта петербуржца (ЕКП)','Smartavia',claim[0],url,now,
      title='Скидка ЕКП на годовую подписку Smartavia',record_kind='program_rules',link_kind='page_block',
      locator='#js-smartup-tariff-cardboard EKP question',conditions=terms,details=d,warnings=warnings))
    return records


ARTICLE_READY_JS=r"(q)=>{const a=document.querySelectorAll(q.selector);const n=(s)=>s.replace(/\s+/g,' ').replace(/‑/g,'-');return a.length===1 && n(a[0].innerText).includes(n(q.text))}"


def fetch_public_product(url):
    """The one reviewed public bank product; no redirect, login or refusal retry."""
    if url!='https://www.gazprombank.ru/personal/cards/7515685/':
        raise ValueError('unreviewed_public_product')
    from public_transport import check_response
    data=bytearray()
    try:
        with requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=(5,15),
                          allow_redirects=False,stream=True) as response:
            if response.status_code!=200:
                raise RuntimeError('http_'+str(response.status_code))
            if 'text/html' not in response.headers.get('Content-Type','').lower():
                raise RuntimeError('public_product_not_html')
            for block in response.iter_content(65536):
                data.extend(block)
                if len(data)>6000000:raise RuntimeError('source_response_too_large')
    except requests.RequestException:
        raise RuntimeError('public_product_transport_failed') from None
    body=data.decode('utf-8')
    check_response(200,body)
    return body


async def read_public_product(client,url):
    client.check_url(url)
    async with client.lock:
        await asyncio.sleep(client.request_interval)
        return await asyncio.to_thread(fetch_public_product,url)


async def collect_known_rules(client,cfg,report,now,limit):
    settings=CONFIG[cfg['id']]
    if settings.get('format')=='pdf':
        from known_pdf import collect_pdf_rule
        rows=await collect_pdf_rule(client,cfg,now)
    else:
        if settings.get('handler')=='gpb':
            raw=await within_source_budget(client,lambda:read_public_product(client,cfg['url']))
        else:
            readiness={'ready_selector':cfg['ready_selector']} if cfg.get('ready_selector') else {}
            raw=await within_source_budget(client,lambda:client.read(cfg['url'],render=settings.get('render',True),**readiness))
        if settings.get('ready_text'):
            selector=settings['selectors'][0]
            async def ready_article():
                await client.page.wait_for_function(
                    ARTICLE_READY_JS,
                    arg={'selector':selector,'text':settings['ready_text']},timeout=8000)
                if canonical_url(client.page.url)!=canonical_url(cfg['url']):
                    raise RuntimeError('known_rule_redirect_during_readiness')
                return await client.page.content()
            raw=await within_source_budget(client,ready_article)
        rows=parse_known_rule(cfg['id'],raw,cfg['url'],now)
    report['discovered']=len(rows)
    report['coverage']='reviewed_known_public_rule_sections; supplementary evidence, not full programme catalogue'
    if len(rows)>limit:report['errors'].append({'phase':'rules','reason':'record_limit','limit':limit})
    return rows[:limit]
