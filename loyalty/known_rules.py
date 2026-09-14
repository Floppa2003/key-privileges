"""Reviewed public rule documents. Never treat rule bundles as new cash discounts.

Selectors and identities are checked-in code. Scraped links are evidence only;
this adapter neither follows them nor submits forms/activates an entitlement.
"""
from __future__ import annotations
import asyncio,json,re
import requests
from pathlib import Path
from datetime import date
from urllib.parse import urljoin,urlsplit,parse_qsl
from bs4 import BeautifulSoup
from normalized import canonical_url,make_offer,number,text
from partner_pages import content,MONTHS
from read_budget import within_source_budget

CONFIG=json.loads(Path(__file__).with_suffix('.json').read_text(encoding='utf8'))
NUM=r'\d[\d \u00a0\u202f]*(?:[.,]\d+)?'


def flat(value):
    return re.sub(r'\s+',' ',value).replace('‑','-').strip()


def match(pattern,value,reason):
    found=re.search(pattern,flat(value),re.I)
    if not found:raise ValueError(reason)
    return found


def date_label(pattern,value):
    m=re.search(pattern,flat(value),re.I)
    if not m:return None,None
    day,month,year=m.groups()
    return date(int(year),MONTHS[month.lower()],int(day)).isoformat(),m[0]


def earning_rules(value):
    # Do not turn redemption percentages or background programme examples into
    # earning. The caller passes only a reviewed earning section.
    pattern=rf'(?P<n>\d+(?:[.,]\d+)?)\s+мил[ьяиюе]\w*(?:\s+начисляется)?(?:\s+«Аэрофлот\s+Бонус»)?\s+за\s+каждые\s+(?:потраченные\s+)?(?P<base>{NUM})\s*(?:руб\w*|₽)'
    found=[]
    for m in re.finditer(pattern,flat(value),re.I):
        item={'value':number(m['n']),'unit':'miles','basis_amount':number(m['base']),
              'basis_unit':'RUB','evidence':m[0]}
        if item not in found:found.append(item)
    return found


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
            item={'label':text(a.get_text(' ',strip=True)),'url':raw,'fetched':False}
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
            raise ValueError('known_rule_scope_missing_or_ambiguous:'+selector)
        nodes.extend(found)
    handler=cfg.get('handler')
    if handler=='headquarters':
        nodes=[n for n in nodes if (h:=n.select_one('.accordion__title-text')) is not None
               and text(h.get_text())=='Перечень льготных категорий']
        if len(nodes)!=1:raise ValueError('rgo_discount_accordion_not_unique')
    if handler=='comfort':
        nodes=[n for n in nodes[0].select('.t509__colwrapper')
               if 'Comfort Pass стал партнером программы' in flat(n.get_text())]
        if len(nodes)!=1:raise ValueError('comfort_base_news_not_unique')
    if handler=='x5':
        headings=[text(n.select_one('h2').get_text()) for n in nodes]
        if sorted(headings)!=sorted(['О партнёре','Как воспользоваться?','Условия предложения']):
            raise ValueError('x5_rule_sections_changed')
    if handler=='gpb':
        products=[n for n in nodes if any(re.fullmatch(r'TariffsMsbItemContent_root__(?!.*__)[A-Za-z0-9_-]+',c) for c in n.get('class',[]))]
        titles=['Условия по карте','Условия программы лояльности «Аэрофлот Бонус»']
        accordions=[n.parent.parent for n in nodes if text(n.get_text(' ',strip=True)) in titles]
        if len(products)!=2 or len(accordions)!=2:raise ValueError('gpb_public_sections_ambiguous')
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
        for node,label,paid in zip(nodes[:2],('Без Газпром Бонус «Плюс»','С Газпром Бонус «Плюс»'),(False,True)):
            value=flat(node.get_text(' ',strip=True))
            if not value.startswith(label):raise ValueError('gpb_subscription_label_mismatch')
            rate=match(r'Мили «Аэрофлот Бонус» (\d+(?:[.,]\d+)?) мили за (\d+) ₽ покупок',value,'gpb_rate_missing')
            cap=match(r'Максимум миль в месяц ('+NUM+r')(?= Переводы|$)',value,'gpb_cap_missing')
            benefit_clauses.append(label+': '+rate[0]+'; '+cap[0])
            cost=match(r'далее [—-] (\d+) ₽ в месяц',value,'gpb_subscription_price_missing')[1] if paid else '0'
            if not paid and 'Бесплатно' not in value:raise ValueError('gpb_free_option_missing')
            options.append({'subscription':paid,'label':label,'miles':number(rate[1]),'basis_rub':rate[2],
                'monthly_cap_miles':number(cap[1]),'monthly_subscription_rub':cost,'evidence':value})
        minimum=match(r'Минимальная сумма покупок по карте в месяц [—–-] ('+NUM+r') ₽',terms,'gpb_minimum_missing')
        service=match(r'Стоимость обслуживания (\d+) ₽',terms,'gpb_service_fee_missing')
        notify=match(r'со 2 месяца [—–-] (\d+) ₽/мес',terms,'gpb_notification_fee_missing')
        details.update(mileage_options=options,monthly_minimum_purchases_rub=number(minimum[1]),
            minimum_evidence=minimum[0],fees={'card_service_rub':service[1],
            'notifications_after_first_month_rub':notify[1],'evidence':notify[0]})
        benefit='\n'.join(benefit_clauses)
    elif handler=='retail_miles':
        earning=terms.split('Условия начислений:',1)[1].split('Условия списаний:',1)[0].strip()
        redemption=terms.split('Условия списаний:',1)[1].strip()
        rules=earning_rules(earning)
        if not rules:raise ValueError('retail_earning_rule_changed')
        cap=match(r'не более (\d+)%',redemption,'retail_redemption_cap_missing')
        cash=match(r'При этом (\d+)%',redemption,'retail_cash_share_missing')
        details.update(earning_rules=rules,redemption_rules={
            'max_order_percent':cap[1],'minimum_cash_percent':cash[1],
            'basis':'order_after_discounts_excluding_delivery_as_published',
            'evidence':redemption},earning_conditions=earning)
        benefit=earning
    elif handler=='iway':
        e=nodes[0].select_one('.condition_earn')
        if e is None:raise ValueError('iway_earning_section_missing')
        earning=content([e]);redemption=terms.split('Использовать мили',1)[1]
        rates=[]
        for label,channel in ((r'При заказе поездки в i[’\']way','direct'),(r'При заказе через турагентство','travel_agent')):
            clause=match(label+r'\s+(\d+ мил[ьяиюе] за каждые потраченные '+NUM+r'\s*(?:₽|руб\w*))',earning,'iway_earning_channel_missing')
            parsed=earning_rules(clause[0])
            if len(parsed)!=1:raise ValueError('iway_ambiguous_channel_rate')
            rates.append({**parsed[0],'channel':channel,'evidence':clause[0]})
        details.update(earning_rules=rates,
            redemption_rules={'evidence':redemption},
            promotional_teaser={'evidence':terms.split('Накопить мили',1)[0],
                                'period_resolved':False,'not_a_cash_discount':True})
        benefit=earning;warnings.append('month_only_redemption_promotion_not_assigned_a_year')
    elif handler=='skyshop':
        earning=terms.split('Условия начислений:',1)[1].split('Условия получения премий:',1)[0]
        details.update(earning_rules=earning_rules(earning),redemption_rules={'evidence':terms.split('Условия получения премий:',1)[1]})
        if not details['earning_rules']:raise ValueError('skyshop_earning_rule_missing')
        benefit=earning;warnings.append('rate_effective_date_not_full_offer_validity')
    elif handler=='x5':
        m=match(r'(\d+) миль за каждые (\d+) баллов',terms,'x5_exchange_rule_missing')
        details['exchange_rule']={'miles':m[1],'basis_amount':m[2],'basis_unit':'X5_points','evidence':m[0]}
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
        age=match(r'до (\d+) лет \(включительно\)',terms,'student_age_missing')
        activation=match(r'в течение (\d+) рабочих дней',terms,'student_activation_time_missing')
        expiry=match(r'до 1 сентября следующего учебного года',terms,'student_relative_expiry_missing')
        details.update(age_max_inclusive=int(age[1]),activation_workdays=int(activation[1]),
                       entitlement_expiry_text=expiry[0])
        warnings.append('relative_student_entitlement_expiry_not_calendar_offer_end')
    elif handler=='sim':
        delivery=match(r'Стоимость услуги [–—-] (\d+) руб',terms,'sim_delivery_price_missing')
        replacement=match(r'Дополнительно оплачивается замена SIM-карты [–—-] (\d+) руб',terms,'sim_replacement_price_missing')
        free=match(r'Для участников программы T2 Selection услуга предоставляется бесплатно',terms,'sim_selection_delivery_missing')
        details['fees']={'delivery_standard_rub':delivery[1],'replacement_rub':replacement[1],
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
        maximum=match(r'до (\d+) счетов',terms,'family_account_bound_missing')
        months=match(r'через (\d+) месяцев',terms,'family_exit_bound_missing')
        cash=match(r'Как минимум (\d+) рублей',terms,'miles_minimum_cash_missing')
        details['family']={'max_accounts':int(maximum[1]),'minimum_membership_months':int(months[1]),
            'evidence':terms.split('Как минимум',1)[0]}
        details['miles_payment']={'minimum_cash_rub':cash[1],'evidence':'Как минимум'+terms.split('Как минимум',1)[1]}
    elif handler=='generations':
        young=match(r'от (\d+) до (\d+) лет',terms,'generations_youth_age_missing')
        senior=match(r'от (\d+) лет \(для женщин\), от (\d+) лет \(для мужчин\)',terms,'generations_senior_age_missing')
        youthcode=match(r'для молодежи\s+([A-Z][A-Z0-9]+)',terms,'generations_youth_code_missing')
        seniorcode=match(r'для людей старшего поколения\s+([A-Z][A-Z0-9]+)',terms,'generations_senior_code_missing')
        life=match(r'Срок действия миль.{0,60}составляет (\d+) года',terms,'generations_reward_lifetime_missing')
        multiplier=match(r'двойные мили',terms,'generations_multiplier_not_recognized')
        details.update(reward_multiplier=2,reward_multiplier_evidence=multiplier[0],
          reward_lifetime_years=int(life[1]),reward_lifetime_evidence=life[0],
          audiences=[{'audience':'youth','age_min':int(young[1]),'age_max':int(young[2]),'promo_code':youthcode[1],'evidence':[young[0],youthcode[0]]},
                     {'audience':'senior','women_age_min':int(senior[1]),'men_age_min':int(senior[2]),'promo_code':seniorcode[1],'evidence':[senior[0],seniorcode[0]]}])
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
    return [make_offer(source,'rules:page',cfg['program'],cfg['partner'],benefit,url,observed_at,
        title=cfg['title'],conditions=terms,link_kind=cfg.get('link_kind','detail_page'),
        record_kind=cfg['record_kind'],locator=' + '.join(cfg['selectors']),details=details,
        warnings=warnings,valid_from=start,valid_until=end)]


def smartavia_records(cfg,nodes,terms,details,warnings,url,now):
    cards=nodes[0].select('.smartup-tariff-item')
    if len(cards)!=4:raise ValueError('smartavia_four_plan_cards_required')
    records=[];labels=set()
    for card in cards:
        value=content([card]);m=match(r'Тариф (1\+[0-3])',value,'smartavia_plan_label_missing');key=m[1]
        if key in labels:raise ValueError('smartavia_duplicate_plan_label')
        labels.add(key)
        price=match(r'Оформить за ('+NUM+r')\s*₽',value,'smartavia_plan_price_missing')
        segments=match(r'(\d+) сегментов со скидкой (\d+) ₽',value,'smartavia_segments_missing')
        baggage=match(r'(\d+) услуг «Багаж (\d+) кг» со скидкой (\d+) ₽',value,'smartavia_baggage_missing')
        d={**details,'subscription_plan':{'label':key,'additional_travelers':int(key[-1]),
           'annual_rub':number(price[1]),'flight_segments':int(segments[1]),'flight_discount_rub':segments[2],
           'baggage_services':int(baggage[1]),'baggage_kg':int(baggage[2]),'baggage_discount_rub':baggage[3],
           'evidence':value},'scope':'published_plan_card_and_common_subscription_rules'}
        records.append(make_offer('smartavia_rules','plan:'+key,cfg['program'],cfg['partner'],value,url,now,
            title='Подписка Smartavia '+key,record_kind='membership_plan',link_kind='page_block',
            locator='.smartup-tariff-item label='+key,conditions=terms,details=d,
            warnings=warnings+['annual_plan_duration_not_offer_expiry','subscription_cost_is_not_discount']))
    if labels!={'1+0','1+1','1+2','1+3'}:raise ValueError('smartavia_plan_set_changed')
    # The EKP benefit is not applied silently to each published base plan price.
    claim=match(r'Все держатели ЕКП могут купить годовую Подписку Smartavia со скидкой (\d+)%\.',terms,'smartavia_ekp_claim_missing')
    d={**details,'discount_percent':claim[1],'discount_basis':'annual_subscription_not_air_ticket',
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
            raw=await within_source_budget(client,lambda:client.read(cfg['url'],render=settings.get('render',True)))
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
