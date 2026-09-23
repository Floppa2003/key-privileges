"""FlyStation's public promotions, independent of any protected EKP offer."""
from __future__ import annotations
import re
from bs4 import BeautifulSoup
from expansion_common import compact,sha,identity,reported,ExcludedOffer,add_error,PROGRAMS
from public_reward_projection import make_record

SOURCE='flystation_public'
URL='https://flystation.net/promotions'
PANELS={'Раннее бронирование':'advance','День рождения в аэротрубе':'birthday',
        'Счастливые часы в аэротрубе':'happy-hours','Скидка после полёта':'after-flight',
        'Хочу ЕЩЁ!':'extra-time','Стать спортсменом':'sport-start'}

def inventory(raw):
    soup=BeautifulSoup(raw,'html.parser');roots=soup.select('section.promotions')
    if len(roots)!=1:raise ValueError('flystation_missing_root')
    nodes=roots[0].select('.promotions__slider-item-text')
    if not 1<=len(nodes)<=30:raise ValueError('flystation_inventory_bound')
    result=[];seen=set()
    for n in nodes:
        ps=n.find_all('p',recursive=False)
        title=compact(ps[0].get_text(' ',strip=True)) if ps else ''
        if title not in PANELS or title in seen:raise ValueError('flystation_unreviewed_or_duplicate_panel')
        seen.add(title);html=str(n)
        result.append(dict(native=PANELS[title],url=URL,title=title,panel_html=html,
                           panel_sha256=sha(html),page_sha256=sha(raw)))
    return result

def must(pattern,value):
    match=re.search(pattern,value,re.I)
    if not match:raise ValueError('flystation_required_clause_missing')
    return match

def source_fields(e):
    identity(e,SOURCE)
    if e.get('url')!=URL or sha(e.get('panel_html',''))!=e.get('panel_sha256'):raise ValueError('flystation_evidence_identity')
    soup=BeautifulSoup(e['panel_html'],'html.parser');nodes=soup.select('.promotions__slider-item-text')
    if len(nodes)!=1:raise ValueError('flystation_panel_identity')
    ps=[compact(p.get_text(' ',strip=True))for p in nodes[0].find_all('p',recursive=False)];ps=[p for p in ps if p]
    if not ps or ps[0]!=e.get('title') or PANELS.get(ps[0])!=e['native']:raise ValueError('flystation_heading_identity')
    native=e['native'];body='\n'.join(ps[1:]);terms=[];benefits=[];activation=''
    if native in ('extra-time','sport-start'):
        if re.search(r'скидк|в подарок|бесплатн|вместо|\d\s*%',body,re.I):raise ValueError('flystation_price_only_changed_requires_review')
        raise ExcludedOffer('no_concrete_partner_benefit')
    if native=='advance':
        matches=list(re.finditer(r'Бронирование за (\d+) дней — скидка (\d+)% на тарифы (\d+)[–-](\d+) минут',body))
        if len(matches)!=2 or len({m[1]for m in matches})!=2:raise ValueError('flystation_advance_scope')
        for m in matches:
            benefits.append(m[0]);terms.append(dict(kind='discount',value=m[2],unit='percent',qualifier='exact',fragment=m[0],scope={'advance_days':m[1],'flight_minutes':m[3]+'–'+m[4]}))
        must(r'Перенести оплаченную бронь на более ранние даты нельзя\. Акции не суммируются\.',body)
        activation='\n'.join(benefits)
    elif native=='birthday':
        m=must(r'Приобретая от (\d+) до (\d+) минут полёта включительно, мы дарим скидку — (\d+)% и электронное фото\.',body)
        gift=must(r'А при покупке тарифа (\d+) минут подарим сертификат на (\d+) минуты полёта и (\d+) электронное фото\.',body)
        benefits=[m[0],gift[0]];terms=[dict(kind='discount',value=m[3],unit='percent',qualifier='exact',fragment=m[0],scope={'flight_minutes':m[1]+'–'+m[2]}),dict(kind='partner_privilege',fragment=gift[0],scope={'purchased_flight_minutes':gift[1]})]
        activation=must(r'В свой день рождения[^\n]+',body)[0]
        must(r'два дня ДО и ПОСЛЕ',activation);must(r'при условии записи на полёт',activation)
    elif native=='happy-hours':
        m=must(r'Специальное предложение для новичков\. «Счастливые часы в аэротрубе» — с (\d+) до (\d+) часов по будням летайте со скидкой (\d+)%!',body)
        benefits=[m[0]];terms=[dict(kind='discount',value=m[3],unit='percent',qualifier='exact',fragment=m[0],scope={'audience':'новички','weekdays':'будни','hours':m[1]+'–'+m[2]})]
        activation=must(r'Чтобы воспользоваться этим предложением, необходимо заранее записаться[^\n]+',body)[0]
    elif native=='after-flight':
        m=must(r'После полёта каждый гость может приобрести сертификат с (\d+)% скидкой!',body)
        benefits=[m[0]];terms=[dict(kind='discount',value=m[1],unit='percent',qualifier='exact',fragment=m[0],scope={'purchase':'сертификат после полёта'})];activation=m[0]
    else:raise ValueError('flystation_unreviewed_native')
    # Preserve unknown offer-local clauses. Omit only explicitly identified promotional
    # filler and example price rows: their figures are not automatic extra discounts.
    conditions=[]
    for p in ps[1:]:
        price = re.match(r'^(\d+ минут(?:а|ы)?)\s*[:—–-]',p)
        if price:
            capacity=re.search(r'\((?:может|могут) полетать[^)]+\)',p)
            if capacity:conditions.append(price[1]+': '+capacity[0])
            if re.search(r'кроме|не действует|только|не распространяется',p,re.I):conditions.append(p)
            continue
        if p.startswith('Цены со скидкой'):continue
        if p in ('Летайте выгодно! Новая акция для раннего бронирования','Планируете полёт в аэротрубе заранее? Теперь это ещё и экономно!','Забронируйте сейчас — и летайте дешевле!'):continue
        if p.startswith('Также мы можем организовать'):continue
        if 'В свой день рождения' in p:p=p[p.index('В свой день рождения'):]
        p=p.replace('Приятный бонус, не правда ли?','').replace('Присмотритесь, предложение очень выгодное:','').replace('Вперёд, не упустите свой шанс!','').strip()
        conditions.append(p)
    return dict(native=native,program=PROGRAMS[SOURCE],partner='FlyStation',title=ps[0],
        benefit='\n'.join(benefits),conditions='\n'.join(conditions),activation=activation,
        url=URL,category='Развлечения / аэротруба',locator='section.promotions; heading '+ps[0],
        terms=terms,scope={'own_public_promotion':True,'EKP_entitlement_inferred':False},
        warnings=['not_EKP_catalogue_recovery','source_end_date_not_stated',
                  'published_example_prices_not_used_as_additional_discount_rates',
                  'booking_availability_not_verified'])

async def collect(client,cfg,report,now,limit):
    if cfg['url']!=URL:raise ValueError('flystation_config_url')
    raw=await client.read(URL);es=inventory(raw);rows=[];excluded={}
    for e in es[:limit]:
        try:rows.append(make_record(SOURCE,e,now))
        except ExcludedOffer as exc:excluded[e['native']]=str(exc)
        except (ValueError,RuntimeError) as exc:add_error(report,exc,e['native'])
    if len(es)>limit:report['errors'].append({'phase':'catalog','reason':'detail_limit_reached'})
    reported(report,rows,[e['native']for e in es],excluded,scope='all_public_promotion_panels_not_protected_EKP_terms',transport='verified_apex_host')
    return rows
