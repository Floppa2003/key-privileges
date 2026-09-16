"""Source-owned airline rules: preserve cabin/tariff/code/footnote relations.

Coefficients are miles as a percentage of distance, never cash discounts.
A parent's returned rules remain a separate object, not a child's replacement.
"""
from __future__ import annotations
import math
import json
import re
from urllib.parse import urlencode
import aeroflot_import_catalog as m

CATALOG=m.HOST+'/partners/ws/v.0.0.2/json/skyteam?lang=ru&full=0'
DETAIL=m.HOST+'/partners/ws/v.0.0.2/json/airline/get'
METHOD='aeroflot_airline_api_google_import_v1'
MAX_AIRLINES=60
WARNINGS=m.WARNINGS+['mileage_percent_of_distance_not_cash_discount','parent_rules_not_automatically_inherited',
                     'source_metadata_not_independently_verified','fare_and_note_scope_required']
BASE={'airport','country','iata','icao','id','title','url','logoUrl','weight'}
FULL=BASE|{'callsign','alliance','imageUrl','milesMinimum','milesLimitation','earnDescription','earnText',
           'parent','children','milesTable','bookingClassComments','eliteCoefficients'}


def detail_url(ident):
    return DETAIL+'?'+urlencode({'lang':'ru','id':m.native_id(ident),'returnFullParentInfo':1})


def identity(obj):
    if not isinstance(obj,dict):raise ValueError('af_airline_identity')
    ident=m.native_id(obj.get('id'));title=m.plain(obj.get('title'));iata=obj.get('iata')
    if not title or len(title)>300 or m.BLOCKED.search(title) or not isinstance(iata,str) or not re.fullmatch('[A-Z0-9]{2}',iata):
        raise ValueError('af_airline_identity')
    return {'id':ident,'title':title,'iata':iata}


def catalog(obs):
    if obs['kind']!='airline_catalog':raise ValueError('af_airline_catalogue_kind')
    data=m.envelope(obs)
    if not isinstance(data,list) or not 1<=len(data)<=500:raise ValueError('af_airline_catalogue_bound')
    result={}
    for obj in data:
        if not isinstance(obj,dict) or set(obj)!=BASE or m.private_field(obj):raise ValueError('af_airline_preview_shape')
        p=identity(obj)
        if p['id'] in result:raise ValueError('af_airline_duplicate_identity')
        result[p['id']]={**p,'discovered_from_id':None}
    return result


def number(value,maximum):
    if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=maximum:
        raise ValueError('af_airline_numeric_field')
    return value


def project(obj,*,parent=False):
    if not isinstance(obj,dict) or set(obj)!=FULL or m.private_field(obj):raise ValueError('af_airline_detail_shape')
    p=identity(obj)
    p.update(source_metadata={k:obj[k] for k in ('airport','country','icao','callsign','alliance','url','logoUrl','imageUrl','weight')},
        earning_description=m.plain(obj['earnDescription']),earning_exclusions=m.plain(obj['earnText']),
        miles_minimum=number(obj['milesMinimum'],10**7),miles_limitation=obj['milesLimitation'],
        children=[],miles_table=[],booking_comments=[],elite_coefficients=[],parent=None)
    for k in ('airport','country','icao','callsign','alliance','url','logoUrl','imageUrl'):
        if obj[k] is not None and (not isinstance(obj[k],str) or len(obj[k])>1000 or m.INSTRUCTION.search(obj[k])):
            raise ValueError('af_airline_metadata_shape')
    number(obj['weight'],10**6)
    if p['miles_limitation'] not in ('A','I','N'):raise ValueError('af_airline_minimum_scope')
    for k,bound in (('children',60),('milesTable',30),('bookingClassComments',100),('eliteCoefficients',40)):
        if not isinstance(obj[k],list) or len(obj[k])>bound:raise ValueError('af_airline_detail_bound')
    notes={};seen=set()
    for item in obj['bookingClassComments']:
        if not isinstance(item,list) or len(item)!=2:raise ValueError('af_airline_note_shape')
        ident=m.native_id(item[0]);value=m.plain(item[1])
        if ident in notes or not value or len(value)>3000:raise ValueError('af_airline_note_shape')
        notes[ident]=value;p['booking_comments'].append({'id':ident,'text':value})
    for cabin in obj['milesTable']:
        if not isinstance(cabin,dict) or set(cabin)!={'name','tariffs'} or not isinstance(cabin['tariffs'],list) or len(cabin['tariffs'])>40:
            raise ValueError('af_airline_table_shape')
        cabin_name=m.plain(cabin['name'])
        if not cabin_name or len(cabin_name)>300:raise ValueError('af_airline_table_shape')
        for tariff in cabin['tariffs']:
            if not isinstance(tariff,dict) or set(tariff)!={'name','groups'} or not isinstance(tariff['groups'],list) or len(tariff['groups'])>100:
                raise ValueError('af_airline_table_shape')
            tariff_name=m.plain(tariff['name'])
            if len(tariff_name)>300:raise ValueError('af_airline_table_shape')
            for group in tariff['groups']:
                if not isinstance(group,dict) or set(group)!={'codes','percent'} or not isinstance(group['codes'],list) or not 1<=len(group['codes'])<=300:
                    raise ValueError('af_airline_table_shape')
                row={'cabin':cabin_name,'tariff':tariff_name,'percent':number(group['percent'],1000),'codes':[]}
                for code in group['codes']:
                    if not isinstance(code,dict) or not {'code','id'}<=set(code) or set(code)-{'code','id','note'}:raise ValueError('af_airline_code_shape')
                    ident=m.native_id(code['id']);value=code['code'];note=code.get('note')
                    if ident in seen or not isinstance(value,str) or not re.fullmatch('[A-Z0-9]{1,12}',value):raise ValueError('af_airline_code_identity')
                    if note is not None and (type(note) is not int or note not in notes):raise ValueError('af_airline_note_missing')
                    seen.add(ident);row['codes'].append({'id':ident,'code':value,'note_id':note,'note_text':notes[note] if note is not None else ''})
                p['miles_table'].append(row)
    if len(p['miles_table'])>400 or len(seen)>4000:raise ValueError('af_airline_table_bound')
    tiers=set()
    for item in obj['eliteCoefficients']:
        if not isinstance(item,list) or len(item)!=2:raise ValueError('af_airline_elite_shape')
        tier=m.plain(item[0]);value=number(item[1],1000)
        if not tier or len(tier)>100 or tier in tiers:raise ValueError('af_airline_elite_shape')
        tiers.add(tier);p['elite_coefficients'].append({'tier':tier,'percent':value})
    seen=set()
    for child in obj['children']:
        if not isinstance(child,dict) or set(child)!={'id','title','iata','url'}:raise ValueError('af_airline_child_shape')
        child_id=identity(child)
        if child_id['id'] in seen or child_id['id']==p['id']:raise ValueError('af_airline_child_identity')
        seen.add(child_id['id']);p['children'].append(child_id)
    if obj['parent'] is not None:
        if parent:raise ValueError('af_airline_parent_depth')
        other=project(obj['parent'],parent=True)
        if other['id']==p['id'] or not any(x=={k:p[k] for k in ('id','title','iata')} for x in other['children']):
            raise ValueError('af_airline_parent_identity')
        p['parent']=other
    if not (p['earning_description'] or p['earning_exclusions'] or p['miles_table']):raise ValueError('af_airline_empty_rules')
    if len(json.dumps(p,ensure_ascii=False))>30000:raise ValueError('af_airline_projection_bound')
    return p


def add_children(partners,projection):
    for child in projection['children']:
        p={**identity(child),'discovered_from_id':projection['id']}
        old=partners.get(p['id'])
        if p['id']==projection['id'] or (old and any(old[k]!=p[k] for k in ('title','iata'))):raise ValueError('af_airline_child_conflict')
        if not old:
            if len(partners)>=500:raise ValueError('af_airline_graph_bound')
            partners[p['id']]=p


def fields(p):
    from normalized import text
    table=[['Класс обслуживания','Тариф','Классы бронирования (сноски)','Мили, % от расстояния']]
    for row in p['miles_table']:
        codes=', '.join(x['code']+(f" [{x['note_id']}: {x['note_text']}]" if x['note_id'] is not None else '') for x in row['codes'])
        table.append([row['cabin'],row['tariff'],codes,f"{row['percent']:g}%"])
    elite=[['Уровень в исходных данных','Дополнительные мили, % от расстояния']]+[[x['tier'],f"{x['percent']:g}%"] for x in p['elite_coefficients']]
    sections=[p['earning_description'],p['earning_exclusions']]
    if len(table)>1:sections.append('Таблица начисления квалификационных миль (% от расстояния, не скидка)\n'+'\n'.join(' | '.join(r) for r in table))
    if len(elite)>1:sections.append('Дополнительные неквалификационные мили за уровень\n'+'\n'.join(' | '.join(r) for r in elite))
    sections.append(f"Минимум миль: {p['miles_minimum']:g}; код области минимума в API: {p['miles_limitation']}. Применимость — по исходным условиям.")
    if p['booking_comments']:sections.append('Сноски источника\n'+'\n'.join(f"{x['id']}: {x['text']}" for x in p['booking_comments']))
    if p['parent']:
        parent=p['parent'];sections.append('Отдельные условия родительской авиакомпании '+parent['title']+' (не подстановка её тарифной таблицы)\n'+parent['earning_description']+'\n'+parent['earning_exclusions'])
    full=text('\n\n'.join(s for s in sections if s))
    if len(full)>35000:raise ValueError('af_airline_terms_bound')
    return text(p['earning_description'] or 'Правила начисления миль на рейсах '+p['title']),full,[t for t in (table,elite) if len(t)>1]


def detail(obs,preview,observed_at):
    from normalized import make_offer
    if obs['kind']!='airline_detail':raise ValueError('af_airline_detail_kind')
    p=project(m.envelope(obs))
    if obs['url']!=detail_url(p['id']) or any(preview.get(k)!=p[k] for k in ('id','title','iata')):raise ValueError('af_airline_detail_identity')
    if preview['discovered_from_id'] is not None and (not p['parent'] or p['parent']['id']!=preview['discovered_from_id']):raise ValueError('af_airline_parent_discovery')
    benefit,conditions,tables=fields(p)
    return make_offer('aeroflot','airline:'+str(p['id']),'Аэрофлот Бонус',p['title'],benefit,obs['url'],observed_at,
        title=p['title'],category='Авиакомпании',conditions=conditions,tables=tables,record_kind='program_rules',
        source_status='public_airline_rules_google_import',locator='public airline API id='+str(p['id']),warnings=list(WARNINGS),
        details={'retrieval_method':METHOD,'public_airline':p,'public_airline_sha256':m.digest(p),'catalogue_preview':preview,
          'import_metadata':{k:obs[k] for k in ('url','kind','requested_at','calculated_at','cells_sha256','formula_sha256')},
          'catalogue_root':m.ROOT,'catalogue_api':CATALOG,'permission_basis':m.PERMISSION,'permission_email_independently_read':False,
          'account_used':False,'coupon_issued':False,'linked_terms_read':False,'origin_http_status':None,
          'origin_cache_age_verified':False,'full_eligibility_verified':False,'parent_rates_applied_to_child':False})


def validate_record(r):
    d=r.get('details',{});p=d.get('public_airline',{});meta=d.get('import_metadata',{});preview=d.get('catalogue_preview',{})
    benefit,conditions,tables=fields(p)
    if (d.get('public_airline_sha256')!=m.digest(p) or r['native_id']!='airline:'+str(m.native_id(p['id']))
        or r['source_id']!='aeroflot' or r['source_url']!=detail_url(p['id']) or r['title']!=p['title'] or r['partner_name']!=p['title']
        or r['benefit_text']!=benefit or r['conditions_text']!=conditions or r['tables']!=tables or r['redemption_text']!=''
        or r['record_kind']!='program_rules' or r['category']!='Авиакомпании' or r['source_status']!='public_airline_rules_google_import'
        or r['benefit_url']!=r['source_url'] or r['link_kind']!='detail_page' or r['valid_from'] is not None or r['valid_until'] is not None
        or any(preview.get(k)!=p[k] for k in ('id','title','iata')) or not set(WARNINGS)<=set(r['warnings'])):raise ValueError('af_airline_record_binding')
    if (d.get('retrieval_method')!=METHOD or d.get('permission_basis')!=m.PERMISSION or d.get('origin_http_status') is not None
        or meta.get('url')!=r['source_url'] or meta.get('kind')!='airline_detail'
        or meta.get('formula_sha256')!=m.digest(m.formula(r['source_url'],'airline_detail'))
        or not re.fullmatch('[a-f0-9]{64}',meta.get('cells_sha256',''))
        or any(d.get(k) is not False for k in ('permission_email_independently_read','account_used','coupon_issued','linked_terms_read',
            'origin_cache_age_verified','full_eligibility_verified','parent_rates_applied_to_child'))):raise ValueError('af_airline_evidence_promotion')
    if not 0<=(m.instant(meta['calculated_at'])-m.instant(meta['requested_at'])).total_seconds()<=180:raise ValueError('af_airline_time')
