"""Public named Mantera participants and separately scoped resort redemption.

The roster and the resort's redemption statement are independent sources. A
marketing counter is not an authoritative inventory, and general spending caps
do not prove that every hotel accepts bonuses. No account routes are followed.
"""
from __future__ import annotations

import hashlib
import re
from bs4 import BeautifulSoup
from normalized import number
from public_reward_projection import make_record, one, plain
from mantera_hotel import QUESTIONS

ROSTER_URL = 'https://sochiparkhotel.ru/about/programma-loyalnosti/'
RESORT_URL = 'https://krasnayapolyanaresort.ru/loyalty'
ROSTER_HEADING = 'Уже участвуют в программе лояльности «Мантера Моменты»'
CONGRESS = 'Мантера Resort & Congress 5*'
# Reviewed exact mappings, never substring-match Marriott inside Courtyard.
REDEMPTION_ALIASES = {
    'Долина 960': 'Долина 960 4*',
    'Кортьярд': 'Кортъярд Марриотт Сочи Красная Поляна 4*',
    'Марриотт': 'Сочи Марриотт Красная Поляна 5*',
}
TABLE_LABELS = ('Сумма покупок за год', 'Начисление бонусов', 'Списание бонусов')


def compact(value):
    return re.sub(r'\s+', ' ', value).strip()


def native_id(name):
    identity = re.sub(r'\s+\d\*$', '', compact(name)).casefold().replace('ё', 'е')
    return 'public-partner:' + hashlib.sha256(identity.encode()).hexdigest()[:24]


def record_id(native):
    return hashlib.sha256(('mantera_moments\n' + native).encode()).hexdigest()


def section(soup, heading):
    matches = [n.find_parent('section') for n in soup.select('h2') if compact(plain(n)) == heading]
    if len(matches) != 1 or matches[0] is None:
        raise ValueError('mantera_partner_section:' + heading)
    return matches[0]


def valid_names(names):
    if (not isinstance(names, list) or not 1 <= len(names) <= 80
            or any(not isinstance(n, str) or not 3 <= len(n) <= 150 or compact(n) != n for n in names)
            or len({native_id(n) for n in names}) != len(names)):
        raise ValueError('mantera_partner_inventory_identity')
    return names


def read_table(table):
    from mantera_source import TIERS
    if not isinstance(table, list) or len(table) != len(TIERS):
        raise ValueError('mantera_partner_tier_count')
    result = []
    for cells, tier in zip(table, TIERS):
        if len(cells) != 4 or cells[0] != tier or not cells[1]:
            raise ValueError('mantera_partner_tier_identity')
        earn = re.fullmatch(r'(\d+(?:[.,]\d+)?)\s*%', cells[2])
        spend = re.fullmatch(r'до\s+(\d+(?:[.,]\d+)?)\s*%', cells[3])
        if not earn or not spend or not all(0 < float(number(m[1])) <= 100 for m in (earn, spend)):
            raise ValueError('mantera_partner_tier_rate')
        result.append((tier, cells[1], number(earn[1]), number(spend[1])))
    return result


def parse_roster(raw):
    soup = BeautifulSoup(raw, 'html.parser')
    if 'Мантера Моменты' not in plain(soup):
        raise ValueError('mantera_partner_page_identity')
    root = section(soup, 'Партнеры программы')
    block = [n for n in root.select('.accordion__item')
             if compact(plain(one(n, '.accordion__item-button-text'))) == ROSTER_HEADING]
    if len(block) != 1 or root.select('.pagination,.load-more,[rel="next"]'):
        raise ValueError('mantera_partner_roster_block')
    listing = one(block[0], '.accordion__item-content ul')
    names = valid_names([compact(plain(n)) for n in listing.find_all('li', recursive=False)])
    rows = []
    for node in section(soup, 'Начисление и списание бонусов').select('.bonus-card'):
        items = node.select('.bonus-card__item')
        labels = tuple(compact(plain(one(n, '.bonus-card__label'))) for n in items)
        if labels != TABLE_LABELS:
            raise ValueError('mantera_partner_table_labels')
        rows.append([compact(plain(one(node, '.bonus-card__title')))] +
                    [compact(plain(one(n, '.bonus-card__value'))) for n in items])
    read_table(rows)
    faq = {}
    for node in root.select('.accordion__item'):
        question = compact(plain(one(node, '.accordion__item-button-text')))
        if question in QUESTIONS:
            if question in faq:
                raise ValueError('mantera_partner_duplicate_question')
            faq[question] = plain(one(node, '.accordion__item-content'))
    counter = [compact(plain(n)) for n in soup.select('.feature-content h3')
               if re.fullmatch(r'\d+ партнеров программы', compact(plain(n)))]
    if len(counter) != 1:
        raise ValueError('mantera_partner_counter_missing')
    rules = [compact(plain(n)) for n in section(soup, 'Как работает программа').select('.block--content li')]
    participation = compact(plain(one(section(soup, 'Как стать участником'), '.block--head_caption')))
    return {'url': ROSTER_URL, 'page_sha256': hashlib.sha256(raw.encode()).hexdigest(),
            'names': names, 'table': rows, 'faq': faq, 'rules': rules,
            'registration': participation, 'declared_count': int(counter[0].split()[0])}


def parse_resort(raw):
    soup = BeautifulSoup(raw, 'html.parser')
    if 'Мантера Моменты' not in plain(one(soup, 'h1')):
        raise ValueError('mantera_resort_page_identity')
    clauses = [compact(plain(n)) for n in soup.select('.markdown p')
               if 'Уже сейчас в отелях' in plain(n)]
    if len(clauses) != 1:
        raise ValueError('mantera_resort_redemption_clause')
    table = [[compact(plain(c)) for c in row.select('.content-tables-accordions-desktop-cell')]
             for row in one(soup, '.content-tables-accordions-desktop-list').select('.content-tables-accordions-desktop-row')]
    if not table or table[0] != ['Статус', *TABLE_LABELS]:
        raise ValueError('mantera_resort_table_headers')
    read_table(table[1:])
    return {'url': RESORT_URL, 'page_sha256': hashlib.sha256(raw.encode()).hexdigest(),
            'clause': clauses[0], 'table': table[1:]}


def validate_evidence(roster, resort):
    for evidence, url in ((roster, ROSTER_URL), (resort, RESORT_URL)):
        if evidence.get('url') != url or not re.fullmatch('[a-f0-9]{64}', evidence.get('page_sha256', '')):
            raise ValueError('mantera_partner_source_identity')
    valid_names(roster['names'])
    if type(roster.get('declared_count')) is not int or not 1 <= roster['declared_count'] <= 80:
        raise ValueError('mantera_partner_counter_identity')
    tiers = read_table(roster['table'])
    other = read_table(resort['table'])
    # Compare qualification and rates, normalizing only whitespace and dash glyphs.
    semantic = lambda table: [(t, re.sub(r'[\s–—-]', '', q), e, s) for t, q, e, s in table]
    if semantic(tiers) != semantic(other):
        raise ValueError('mantera_partner_source_rate_conflict')
    faq = roster['faq']
    if set(faq) != set(QUESTIONS) or any(not isinstance(v, str) or not v for v in faq.values()):
        raise ValueError('mantera_partner_terms_missing')
    if ('бесплатное' not in faq[QUESTIONS[0]] or 'не предусмотрено' not in faq[QUESTIONS[0]]
            or 'до оформления' not in faq[QUESTIONS[3]] or 'невозможно' not in faq[QUESTIONS[4]]
            or '18 лет' not in roster['registration']):
        raise ValueError('mantera_partner_access_changed')
    rules = roster['rules']
    if not isinstance(rules, list) or len(rules) != 5 or '1 бонус = 1 рубль' not in rules[0]:
        raise ValueError('mantera_partner_rules_changed')
    match = re.search(r'Уже сейчас в отелях (.+?) бонусы можно и копить, и тратить\.', resort['clause'])
    if not match or 'В остальных отелях Курорта Красная Поляна пока доступно только начисление' not in resort['clause']:
        raise ValueError('mantera_resort_redemption_scope_changed')
    aliases = re.split(r',\s*|\s+и\s+', match[1])
    if not aliases or len(aliases) != len(set(aliases)) or not set(aliases) <= set(REDEMPTION_ALIASES):
        raise ValueError('mantera_resort_unreviewed_name_mapping')
    names = {REDEMPTION_ALIASES[a] for a in aliases}
    if not names <= set(roster['names']):
        raise ValueError('mantera_partner_roster_redemption_conflict')
    return tiers, names


def source_fields(e):
    from mantera_source import PROGRAM
    if e.get('kind') != 'public_partner' or e.get('url') != ROSTER_URL:
        raise ValueError('mantera_public_partner_identity')
    roster, resort = e['roster'], e['resort']
    tiers, redeemable = validate_evidence(roster, resort)
    name = e['name']
    if name not in roster['names'] or name == CONGRESS:
        raise ValueError('mantera_public_partner_not_listed_or_duplicate')
    can_redeem = name in redeemable
    terms, earning, spending, qualification = [], [], [], []
    for tier, threshold, earn, spend in tiers:
        scope = {'member_tier': tier, 'annual_spend_clause': threshold, 'hotel': name}
        earning.append(tier + ' — ' + earn + '%')
        terms.append(dict(kind='earn_points', value=earn, unit='percent', qualifier='exact',
                          reward_unit='Mantera_bonus_not_cash', fragment=earning[-1], scope=scope))
        qualification.append(tier + ': сумма покупок за год ' + threshold + '.')
        if can_redeem:
            spending.append(tier + ' — до ' + spend + '%')
            terms.append(dict(kind='redeem_points', value=spend, unit='percent', qualifier='up_to',
                              reward_unit='Mantera_bonus_not_cash', fragment=spending[-1], scope=scope))
    benefit = 'Начисление бонусов по статусу: ' + '; '.join(earning) + '.'
    if can_redeem:
        benefit += '\nОплата накопленными бонусами: ' + '; '.join(spending) + '.'
    conditions = [*qualification, *roster['rules'][:3], *[roster['faq'][q] if q != QUESTIONS[3] else roster['faq'][q].split('\n')[0] for q in QUESTIONS],
                  'Партнёр назван в публичном списке программы. Личный доступ и конкретное бронирование не проверялись.']
    if can_redeem:
        conditions.extend([resort['clause'].split(' Присоединяйтесь,')[0], 'Подтверждение возможности списания: ' + RESORT_URL,
                           'Лимит оплаты бонусами — не скидка и не денежный кешбэк.'])
    else:
        conditions.append('Возможность списания именно у этого партнёра отдельно не подтверждена; общие лимиты программы не означают доступность списания во всех объектах.')
    warnings = ['public_named_roster_not_all_group_businesses', 'bonus_not_cash', 'bonus_redemption_cap_not_discount']
    if not can_redeem:
        warnings.append('hotel_redemption_not_confirmed')
    if roster['declared_count'] != len(roster['names']):
        warnings.append('source_partner_counter_conflicts_with_named_roster')
        conditions.append(f"Счётчик источника: {roster['declared_count']}; именованных позиций в списке: {len(roster['names'])}. Полнота всей программы не подтверждена.")
    return dict(native=native_id(name), program=PROGRAM, partner=name, title=PROGRAM+' → '+name,
                benefit=benefit, conditions='\n'.join(conditions),
                activation=roster['registration']+'\n'+roster['faq'][QUESTIONS[3]].split('\n')[0],
                url=ROSTER_URL, category='Отели / бонусы', link_kind='page_block',
                locator=ROSTER_HEADING+'; '+name, terms=terms,
                scope={'hotel':name, 'eligibility_not_verified':True, 'redemption_publicly_supported':can_redeem}, warnings=warnings)


def parse_pair(roster_raw, resort_raw, observed_at):
    roster, resort = parse_roster(roster_raw), parse_resort(resort_raw)
    validate_evidence(roster, resort)
    records = [make_record('mantera_moments', {'kind':'public_partner', 'url':ROSTER_URL,
               'name':name, 'roster':roster, 'resort':resort}, observed_at)
               for name in roster['names'] if name != CONGRESS]
    inventory = {'version':1, 'roster_url':ROSTER_URL, 'resort_url':RESORT_URL,
                 'names':roster['names'], 'declared_count':roster['declared_count'],
                 'record_ids':[r['id'] for r in records]}
    return records, inventory


async def collect(browser, deadline, observed_at):
    from public_transport import PublicSource
    from read_budget import within_source_budget
    pages = []
    for url in (ROSTER_URL, RESORT_URL):
        async with PublicSource(browser, url) as client:
            client.deadline = deadline
            await within_source_budget(client, client.robots)
            pages.append(await within_source_budget(client, lambda:client.read(url)))
    return parse_pair(*pages, observed_at)


def health(report, records):
    """Verify the observed named inventory instead of a magic record count."""
    from mantera_source import TIERS
    meta = report.get('mantera_public_inventory')
    if (report.get('status') != 'ok' or report.get('errors') or not isinstance(meta, dict)
            or meta.get('version') != 1 or meta.get('roster_url') != ROSTER_URL or meta.get('resort_url') != RESORT_URL):
        return False
    try:
        names = valid_names(meta['names'])
        expected_partners = {record_id(native_id(n)) for n in names if n != CONGRESS}
        expected_base = {record_id('tier:'+t) for t in TIERS} | {record_id('hotel:mantera-resort-congress')}
        ids = [r['id'] for r in records]
        if (set(meta['record_ids']) != expected_partners or len(meta['record_ids']) != len(expected_partners)
                or set(ids) != expected_base | expected_partners or len(ids) != len(set(ids))
                or report['normalized'] != len(ids)):
            return False
        from public_reward_projection import validate_record
        for row in records:
            validate_record(row)
            if row['observed_at'] != report['observed_at']:
                return False
            e = row['details']['public_reward_evidence']
            if e.get('kind') == 'public_partner' and (e['roster']['names'] != names or e['roster']['declared_count'] != meta['declared_count']):
                return False
    except (ValueError, KeyError, TypeError):
        return False
    return True
