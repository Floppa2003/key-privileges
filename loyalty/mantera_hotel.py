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

def source_fields(e):
    from mantera_source import TIERS,PROGRAM
    if e.get('url')!=URL or e.get('kind')!='hotel_participation' or not re.fullmatch('[a-f0-9]{64}',e.get('page_sha256','')):
        raise ValueError('mantera_hotel_identity')
    if 'включая отель '+NAME not in e.get('participation',''):
        raise ValueError('mantera_hotel_participation_not_confirmed')
    table=e.get('table',[]);faq=e.get('faq',{})
    if len(table)!=5 or set(faq)!=set(QUESTIONS) or any(not faq[q] for q in QUESTIONS):
        raise ValueError('mantera_hotel_terms_missing')
    if 'бесплатное' not in faq[QUESTIONS[0]] or 'до оформления' not in faq[QUESTIONS[3]] or 'невозможно' not in faq[QUESTIONS[4]]:
        raise ValueError('mantera_hotel_access_changed')
    if not all(s in e.get('limits','') for s in ('только накапливать','доступно и списание')):
        raise ValueError('mantera_hotel_redemption_scope_changed')
    benefits=[];claims=[];rules=[]
    for cells,tier in zip(table,TIERS):
        if len(cells)!=4 or cells[0]!=tier or not cells[1]:raise ValueError('mantera_hotel_tiers_changed')
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

def parse(raw,observed_at):
    soup=BeautifulSoup(raw,'html.parser')
    if plain(one(soup,'h1')).casefold()!='мантера моменты':raise ValueError('mantera_hotel_page_identity')
    participation=[plain(n) for n in soup.select('p') if 'включая отель '+NAME in plain(n)]
    limits=[plain(n) for n in soup.select('p') if 'только накапливать' in plain(n) and 'доступно и списание' in plain(n)]
    activation=[plain(n) for n in soup.select('p') if 'номер телефона' in plain(n) and 'СМС' in plain(n)]
    if any(len(v)!=1 for v in (participation,limits,activation)):raise ValueError('mantera_hotel_owned_blocks')
    table=one(soup,'table')
    if [plain(n) for n in table.select('thead th')]!=['Статус','Сумма покупок за год','Начисление бонусов','Списание бонусов']:
        raise ValueError('mantera_hotel_table_headers')
    faq={}
    for n in soup.select('.MuiAccordion-root'):
        q=plain(one(n,'h3'))
        if q in QUESTIONS:
            if q in faq:raise ValueError('mantera_hotel_duplicate_question')
            faq[q]=plain(one(n,'.MuiAccordionDetails-root'))
    e=dict(kind='hotel_participation',url=URL,page_sha256=hashlib.sha256(raw.encode()).hexdigest(),
      participation=participation[0],limits=limits[0],activation=activation[0],faq=faq,
      table=[[plain(n) for n in tr.select('td')] for tr in table.select('tbody tr')])
    return make_record('mantera_moments',e,observed_at)
