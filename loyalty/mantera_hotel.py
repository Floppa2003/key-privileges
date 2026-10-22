"""One source-confirmed hotel, not an inferred six-partner programme inventory."""
import hashlib, re
from bs4 import BeautifulSoup
from public_reward_projection import one, plain, make_record
from normalized import number
URL='https://manteracongress.ru/loyalty-program'
NAME='Mantera Resort & Congress'
QUESTIONS=(
 'Нужно ли платить за участие в программе?',
 'Как долго действует мой статус в программе?',
 'На какие товары и услуги не начисляются бонусы?',
 'Что делать, если бонусы не начислены или начислены неверно?',
 'Можно ли снять бонусы наличными деньгами?',
)

def legacy_source_fields(e):
    from mantera_source import PROGRAM
    if e.get('url')!=URL or e.get('kind')!='hotel_participation' or not re.fullmatch('[a-f0-9]{64}',e.get('page_sha256','')):
        raise ValueError('mantera_hotel_identity')
    if 'включая отель '+NAME not in e.get('participation',''):
        raise ValueError('mantera_hotel_participation_not_confirmed')
    table=e.get('table',[]);faq=e.get('faq',{})
    if not table or len(table)>100 or set(faq)!=set(QUESTIONS) or any(not faq[q] for q in QUESTIONS):
        raise ValueError('mantera_hotel_terms_missing')
    if 'бесплатное' not in faq[QUESTIONS[0]] or 'до оформления' not in faq[QUESTIONS[3]] or 'невозможно' not in faq[QUESTIONS[4]]:
        raise ValueError('mantera_hotel_access_changed')
    if not all(s in e.get('limits','') for s in ('только накапливать','доступно и списание')):
        raise ValueError('mantera_hotel_redemption_scope_changed')
    benefits=[];claims=[];rules=[]
    seen=set()
    for cells in table:
        if len(cells)!=4 or not cells[0] or cells[0] in seen or not cells[1]:raise ValueError('mantera_hotel_tiers_changed')
        tier=cells[0];seen.add(tier)
        earn=re.fullmatch(r'(\d+(?:[.,]\d+)?)%',cells[2]);spend=re.fullmatch(r'до (\d+(?:[.,]\d+)?)%',cells[3])
        if not earn or not spend or not all(0<float(number(x[1]))<=100 for x in (earn,spend)):
            raise ValueError('mantera_hotel_rate_missing')
        claim=tier+' — '+cells[2]+' бонусами';claims.append(claim)
        benefits.append(dict(kind='earn_points',value=number(earn[1]),unit='percent',qualifier='exact',
          reward_unit='Mantera_bonus_not_cash',fragment=claim,scope={'member_tier':tier,'annual_spend_clause':cells[1]}))
        rules.append(tier+': сумма покупок за год '+cells[1]+'; начисление '+cells[2]+'; общий лимит списания '+cells[3]+'.')
    activation=e.get('activation','')
    if 'номер телефона' not in activation or 'СМС' not in activation:raise ValueError('mantera_hotel_activation_missing')
    conditions='\n'.join([*rules,*[faq[q] for q in QUESTIONS],e['limits'],
      'Участие отеля подтверждено его публичной страницей. Индивидуальная возможность списания бонусов в отеле не подтверждена: таблица содержит общие лимиты программы.'])
    return dict(native='hotel:mantera-resort-congress',program=PROGRAM,partner=NAME,title=PROGRAM+' → '+NAME,
      benefit='Начисление за проживание по статусу: '+'; '.join(claims),conditions=conditions,activation=activation,
      url=URL,category='Отели / бонусы',locator='hotel programme introduction; tier table; five practical FAQ answers',
      terms=benefits,scope={'hotel':NAME,'eligibility_not_verified':True,'redemption_availability_not_confirmed':True},
      warnings=['hotel_earning_not_all_group_partners','hotel_redemption_not_confirmed','bonus_not_cash'])

def source_fields(e):
    if e.get('projection_version') is None:return legacy_source_fields(e)
    if e.get('projection_version')!=2:raise ValueError('mantera_hotel_projection_version')
    from mantera_source import PROGRAM
    from mantera_partners import read_table
    from content_discovery import faq_text, validate_faq
    if e.get('url')!=URL or e.get('kind')!='hotel_participation' or not re.fullmatch('[a-f0-9]{64}',e.get('page_sha256','')):
        raise ValueError('mantera_hotel_identity')
    validate_faq(e.get('faq'))
    if not e.get('participation') or NAME not in e['participation']:
        raise ValueError('mantera_hotel_participation_not_confirmed')
    tiers=read_table(e['table']);terms=[];claims=[];rules=[]
    for tier,threshold,earn,spend in tiers:
        claim=tier+' — '+earn+'% бонусами';claims.append(claim)
        terms.append(dict(kind='earn_points',value=earn,unit='percent',qualifier='exact',
            reward_unit='Mantera_bonus_not_cash',fragment=claim,scope={'member_tier':tier,'annual_spend_clause':threshold}))
        rules.append(tier+': сумма покупок за год '+threshold+'; начисление '+earn+'%; общий лимит списания до '+spend+'%.')
    conditions='\n'.join([*rules,e['participation'],e['context'],faq_text(e['faq']),
        'Индивидуальная возможность списания бонусов в отеле не подтверждена: таблица содержит общие лимиты программы.'])
    return dict(native='hotel:mantera-resort-congress',program=PROGRAM,partner=NAME,title=PROGRAM+' → '+NAME,
        benefit='Начисление за проживание по статусу: '+'; '.join(claims),conditions=conditions,activation=e['activation'],
        url=URL,category='Отели / бонусы',locator='hotel programme introduction; observed tier table; all public FAQ answers',
        terms=terms,scope={'hotel':NAME,'eligibility_not_verified':True,'redemption_availability_not_confirmed':True},
        warnings=['hotel_earning_not_all_group_partners','hotel_redemption_not_confirmed','bonus_not_cash'])


def parse(raw,observed_at):
    from content_discovery import clean_dom, read_faq, action_clauses
    soup=clean_dom(raw)
    if 'мантера моменты' not in plain(one(soup,'h1')).casefold():raise ValueError('mantera_hotel_page_identity')
    # The hotel owns this page; only a positive participation statement with
    # its name supports membership, not an arbitrary name elsewhere in a footer.
    participation=[]
    name=re.escape(NAME)
    positive=re.compile(r'включая\s+отель\s+'+name+r'|' + name +
                        r'\s+(?:является\s+участником|участвует)\s+в?\s*программ',re.I)
    negative=re.compile(name+r'\s+(?:больше\s+)?не\s+(?:участвует|является\s+участником)',re.I)
    for node in soup.select('p'):
        value=plain(node)
        if negative.search(value):raise ValueError('mantera_hotel_participation_conflict')
        if positive.search(value) and value not in participation:participation.append(value)
    if not participation:raise ValueError('mantera_hotel_owned_blocks')
    table=one(soup,'table')
    headers=[plain(n) for n in table.select('thead th')]
    # Column meanings are a schema, not the current data in its rows.
    if len(headers)!=4 or not all(re.search(pattern,h,re.I) for pattern,h in zip(
        (r'статус|уровень',r'сумма|покуп',r'начисл',r'списан'),headers)):
        raise ValueError('mantera_hotel_table_headers')
    faq=read_faq(soup.select('.MuiAccordion-root'),'h3','.MuiAccordionDetails-root',plain)
    context=BeautifulSoup(str(soup),'html.parser')
    for n in context.select('table,.MuiAccordion-root'):
        if n.parent is not None:n.decompose()
    context=plain(context)
    e=dict(projection_version=2,kind='hotel_participation',url=URL,page_sha256=hashlib.sha256(raw.encode()).hexdigest(),
        participation='\n'.join(participation),context=context,activation=action_clauses(context),faq=faq,
        table=[[plain(n) for n in tr.select('td')] for tr in table.select('tbody tr')])
    return make_record('mantera_moments',e,observed_at)
