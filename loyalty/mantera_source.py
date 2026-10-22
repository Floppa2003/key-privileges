"""Mantera Moments' five public tiers, explicitly limited to the pilot hotels."""
from __future__ import annotations
import hashlib, re
from bs4 import BeautifulSoup
from public_reward_projection import plain, one, make_record
from normalized import number

SOURCE = 'mantera_moments'
URL = 'https://lk.manteratravel.ru/faq'
PROGRAM = 'Мантера Моменты'
TIER_QUESTION = 'Какие статусы существуют в программе (Гость, Ценитель, Знаток, Эксперт, Легенда) и чем они отличаются?'
LEGACY_TIERS = ('Гость', 'Ценитель', 'Знаток', 'Эксперт', 'Легенда')
QUESTIONS = (
    'Кто может стать участником программы?',
    'Как зарегистрироваться в программе лояльности?',
    'Нужно ли платить за участие в программе?',
    'Как долго действует мой статус в программе?',
    'Что такое бонусы и как они начисляются?',
    'Какой эквивалент одного бонуса в рублях?',
    'На какие товары или услуги не начисляются бонусы?',
    'Могу ли я получить бонусы за покупку акционных товаров?',
    'Как использовать бонусы для оплаты покупок?',
    'Можно ли снять бонусы наличными деньгами?',
    'Что делать, если бонусы не были начислены (или начислены неверно)?',
    'Как потратить бонусы?',
    'Как заработать бонусы?',
    'Что произойдёт, если я не поддержу текущий статус на следующий год?',
    'Сохраняется ли статус при отсутствии покупок или при снижении сумм покупок?',
)


def legacy_source_fields(e):
    if e.get('kind') == 'public_partner':
        from mantera_partners import source_fields as partner_fields
        return partner_fields(e)
    if e.get('kind')=='hotel_participation':
        from mantera_hotel import source_fields as hotel_fields
        return hotel_fields(e)
    if e.get('url') != URL or not re.fullmatch(r'[a-f0-9]{64}', e.get('page_sha256', '')):
        raise ValueError('mantera_evidence_url')
    tier = e.get('tier'); line = e.get('tier_clause', '')
    m = re.fullmatch(re.escape(str(tier)) + r' — (?:базовый )?статус с начислением (\d+(?:[.,]\d+)?)%, списанием (\d+(?:[.,]\d+)?)%, (.+)', line)
    if tier not in LEGACY_TIERS or not m or any(not 0 < float(number(v)) <= 100 for v in m.group(1, 2)):
        raise ValueError('mantera_tier_clause')
    faq = e.get('faq', {})
    if set(faq) != set(QUESTIONS) or any(not isinstance(v, str) or not v for v in faq.values()): raise ValueError('mantera_required_terms')
    pilot = e.get('pilot', '')
    if not all(x in pilot for x in ('пилотного запуска', 'ограниченном числе отелей', 'услуги проживания')):
        raise ValueError('mantera_pilot_scope_changed')
    if 'бесплатное' not in faq[QUESTIONS[2]] or 'не предусмотрено' not in faq[QUESTIONS[2]]:
        raise ValueError('mantera_membership_cost_changed')
    if 'невозможно' not in faq[QUESTIONS[9]] or 'до оформления' not in faq[QUESTIONS[10]]:
        raise ValueError('mantera_cash_or_prebooking_condition_changed')
    warnings = ['pilot_hotel_participant_list_requires_account_not_read', 'bonus_redemption_cap_not_discount']
    if 'календарных' in faq[QUESTIONS[4]] and 'рабочих' in faq[QUESTIONS[12]]:
        warnings.append('source_conflict_calendar_versus_business_accrual_days')
    benefit = 'Бонусы «Мантера Моменты»: ' + line
    terms = [dict(kind='earn_points', value=number(m[1]), unit='percent', qualifier='exact',
                  reward_unit='Mantera_bonus_not_cash', fragment=line),
             dict(kind='redeem_points', value=number(m[2]), unit='percent', qualifier='up_to',
                  reward_unit='Mantera_bonus_not_cash', fragment=line)]
    # Practical clauses, not the whole FAQ or examples belonging to another tier.
    practical = [pilot, e['tier_context'], line, faq[QUESTIONS[0]], faq[QUESTIONS[2]],
        faq[QUESTIONS[3]], faq[QUESTIONS[4]], faq[QUESTIONS[5]], faq[QUESTIONS[6]],
        faq[QUESTIONS[7]], faq[QUESTIONS[9]], faq[QUESTIONS[10]].split('\n')[0],
        faq[QUESTIONS[11]], faq[QUESTIONS[14]]]
    practical.extend(s for s in faq[QUESTIONS[12]].splitlines() if 'рабочих' in s)
    return dict(native='tier:' + tier, program=PROGRAM, partner=PROGRAM, title=PROGRAM + ' — ' + tier,
        benefit=benefit, conditions='\n'.join(dict.fromkeys(practical)),
        activation=faq[QUESTIONS[1]], url=URL, category='Отели / бонусы', kind='tier_benefit',
        link_kind='page_block', locator='FAQ; ' + TIER_QUESTION + '; ' + tier, terms=terms,
        scope={'member_tier': tier, 'pilot_accommodation_only': True, 'eligibility_not_verified': True}, warnings=warnings)


def tier_parts(line):
    match=re.fullmatch(r'(.+?)\s+[—–-]\s+(.+)',line)
    if not match:raise ValueError('mantera_tier_label_missing')
    return match[1].strip(),match[2]


def source_fields(e):
    if e.get('kind') == 'public_partner':
        from mantera_partners import source_fields as partner_fields
        return partner_fields(e)
    if e.get('kind') == 'hotel_participation':
        from mantera_hotel import source_fields as hotel_fields
        return hotel_fields(e)
    if e.get('projection_version') is None:
        return legacy_source_fields(e)
    if e.get('projection_version') != 2:raise ValueError('mantera_projection_version')
    from content_discovery import faq_text,validate_faq
    if e.get('url') != URL or not re.fullmatch(r'[a-f0-9]{64}',e.get('page_sha256','')):
        raise ValueError('mantera_evidence_url')
    tier,body=tier_parts(e.get('tier_clause',''))
    if tier!=e.get('tier'):raise ValueError('mantera_tier_identity')
    names=e.get('tier_inventory',[])
    if not names or len(names)!=len(set(names)) or tier not in names:
        raise ValueError('mantera_tier_inventory')
    validate_faq(e.get('faq'))
    terms=[]
    for kind,pattern,qualifier in (
        ('earn_points',r'начисл\w*\s+(\d+(?:[.,]\d+)?)\s*%','exact'),
        ('redeem_points',r'списан\w*\s+(?:до\s+)?(\d+(?:[.,]\d+)?)\s*%','up_to')):
        found=list(re.finditer(pattern,body,re.I))
        if len(found)>1:raise ValueError('mantera_ambiguous_tier_rate')
        if found:
            value=number(found[0][1])
            if not 0<=float(value)<=100:raise ValueError('mantera_invalid_tier_rate')
            terms.append(dict(kind=kind,value=value,unit='percent',qualifier=qualifier,
                              reward_unit='Mantera_bonus_not_cash',fragment=e['tier_clause']))
    warnings=['bonus_redemption_cap_not_discount','programme_eligibility_not_verified']
    if not terms:
        warnings.append('tier_rates_unclassified_original_clause_preserved')
    questions=faq_text(e['faq'])
    if 'календарных' in questions and 'рабочих' in questions:
        warnings.append('source_conflict_calendar_versus_business_accrual_days')
    conditions='\n'.join(x for x in (e.get('pilot',''),e.get('tier_context',''),e['tier_clause'],questions) if x)
    return dict(native='tier:'+tier,program=PROGRAM,partner=PROGRAM,title=PROGRAM+' — '+tier,
        benefit='Бонусы «Мантера Моменты»: '+e['tier_clause'],conditions=conditions,
        activation=e.get('registration',''),url=URL,category='Отели / бонусы',kind='tier_benefit' if terms else 'source_observation',
        link_kind='page_block',locator='FAQ; '+e['tier_heading']+'; '+tier,terms=terms,
        scope={'member_tier':tier,'published_program_context':e.get('pilot',''),'eligibility_not_verified':True},
        warnings=warnings)


def parse(raw, observed_at):
    from content_discovery import read_faq
    soup=BeautifulSoup(raw,'html.parser')
    nodes=soup.select('.MuiAccordion-root')
    all_faq=read_faq(nodes,'h3','.MuiAccordionDetails-root',plain)
    candidates=[]
    for node in nodes:
        for listing in node.select('.MuiAccordionDetails-root ul'):
            lines=[re.sub(r'\s+',' ',plain(n)).strip() for n in listing.find_all('li',recursive=False)]
            if lines and any(re.search(r'\s[—–-]\s.*(?:начисл|списан|статус)',line,re.I) for line in lines):
                candidates.append((node,listing,lines))
    if len(candidates)!=1:raise ValueError('mantera_tier_section_ambiguous_or_missing')
    node,listing,lines=candidates[0]
    names=[tier_parts(line)[0] for line in lines]
    if len(names)!=len(set(names)) or len(names)>100:raise ValueError('mantera_tier_inventory')
    heading=plain(one(node,'h3'))
    # The other tier clauses never become this tier's scope or rate.
    faq={q:a for q,a in all_faq.items() if q!=heading}
    context=BeautifulSoup(str(one(node,'.MuiAccordionDetails-root')),'html.parser')
    for ul in context.select('ul'):ul.decompose()
    context=plain(context)
    banners=soup.select('.pilot-loyalty-banner-icon')
    if len(banners)>1:raise ValueError('mantera_duplicate_banner')
    pilot=plain(banners[0].parent) if banners else ''
    registration='\n'.join(plain(n) for n in soup.select('.MuiAccordionDetails-root ol'))
    rows=[]
    for name,line in zip(names,lines):
        evidence=dict(url=URL,page_sha256=hashlib.sha256(raw.encode()).hexdigest(),projection_version=2,
            tier=name,tier_clause=line,tier_heading=heading,tier_context=context,tier_inventory=names,
            pilot=pilot,faq=faq,registration=registration)
        rows.append(make_record(SOURCE,evidence,observed_at))
    return rows


async def collect(client, cfg, report, observed_at, limit):
    if cfg['url'] != URL or cfg['id'] != SOURCE: raise ValueError('mantera_config_identity')
    from read_budget import within_source_budget
    records = parse(await within_source_budget(client, lambda:client.read(URL)), observed_at)
    if len(records)+1 > limit: raise RuntimeError('mantera_record_limit')
    from public_transport import PublicSource
    import mantera_hotel
    try:
        async with PublicSource(client.browser,mantera_hotel.URL) as hotel:
            hotel.deadline=getattr(client,'deadline',float('inf'))
            await within_source_budget(hotel,hotel.robots)
            record=mantera_hotel.parse(await within_source_budget(hotel,lambda:hotel.read(mantera_hotel.URL)),observed_at)
            records.append(record)
    except Exception as exc:
        report['errors'].append({'phase':'hotel_public_page','url':mantera_hotel.URL,'reason':str(exc)[:140] if isinstance(exc,(RuntimeError,ValueError)) else type(exc).__name__})
    import mantera_partners
    try:
        partners, inventory = await mantera_partners.collect(
            client.browser, getattr(client, 'deadline', float('inf')), observed_at)
        if len(records) + len(partners) > limit:
            raise RuntimeError('mantera_record_limit')
        records.extend(partners)
        report['mantera_public_inventory'] = inventory
    except Exception as exc:
        report['errors'].append({'phase':'public_partner_inventory', 'url':mantera_partners.ROSTER_URL,
            'reason':str(exc)[:140] if isinstance(exc,(RuntimeError,ValueError)) else type(exc).__name__})
    report['discovered'] = len(records)+len(report['errors'])
    report['coverage'] = 'all_current_FAQ_tiers;independent_Congress_page;public_named_participants_and_scoped_resort_redemption;not_all_group_businesses'
    return records
