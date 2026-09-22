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
TIERS = ('Гость', 'Ценитель', 'Знаток', 'Эксперт', 'Легенда')
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


def source_fields(e):
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
    if tier not in TIERS or not m or any(not 0 < float(number(v)) <= 100 for v in m.group(1, 2)):
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


def parse(raw, observed_at):
    soup = BeautifulSoup(raw, 'html.parser'); faq = {}; root = None
    for node in soup.select('.MuiAccordion-root'):
        q = plain(one(node, 'h3'))
        a = plain(one(node, '.MuiAccordionDetails-root'))
        if q in faq: raise ValueError('mantera_duplicate_question')
        faq[q] = a
        if q == TIER_QUESTION: root = node
    if root is None or any(q not in faq for q in QUESTIONS): raise ValueError('mantera_required_questions_missing')
    pilot_node = one(soup, '.pilot-loyalty-banner-icon').parent
    pilot = plain(pilot_node)
    block = one(root, '.payload-richtext')
    clauses = [re.sub(r'\s+', ' ', plain(n)) for n in block.select('ul > li')]
    if len(clauses) != len(TIERS): raise ValueError('mantera_unreviewed_tier_count')
    context = plain(one(block, 'p:first-child'))
    if '365 дней' not in context: raise ValueError('mantera_qualification_period_changed')
    records = []
    for tier, line in zip(TIERS, clauses):
        evidence = dict(url=URL, page_sha256=hashlib.sha256(raw.encode()).hexdigest(), tier=tier,
            tier_clause=line, tier_context=context, pilot=pilot, faq={q:faq[q] for q in QUESTIONS})
        records.append(make_record(SOURCE, evidence, observed_at))
    return records


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
    report['coverage'] = 'five_FAQ_tiers;independent_Congress_page;public_named_participants_and_scoped_resort_redemption;not_all_group_businesses'
    return records
