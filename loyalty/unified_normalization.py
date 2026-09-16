"""Source-preserving common model for public adapters and private legacy sheets.

No requests, LLM, prices, entitlements, or missing facts are invented here. Every
projected term carries a resolvable pointer to its own input. Source-specific
structures and unparsed text stay in ``raw``. This is not a savings calculator.
"""
from __future__ import annotations
import copy
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from normalized import normalize_rates
from promo_codes import extract_promocodes

VERSION = '1.0.1'
GROUPS = ('benefits', 'conditions', 'costs', 'codes')
INPUT_TABS = {
    'parser_offers': (1, 26), 'loyalty_partner_benefits': (4, 13),
    'yandex_discounts_complete_all': (1, 7), 'VG_community_offers': (4, 8),
    'parser_inbox': (1, 10),
}
NUM = r'\d+(?:[ \u00a0\u202f]\d{3})*(?:[.,]\d+)?'
MONEY = r'(?:₽|руб(?:лей|ля|ль|\.)?|RUB)'
KIND = {'discount':'discount','cashback':'cashback','miles':'earn_miles','points':'earn_points',
        'gift':'gift','special_price':'special_price'}
ALIASES = {
    'Карта «Москвича»':'moskvich', 'No Name Card':'noname', 'S7 Priority':'s7',
    'Уральские авиалинии — «Крылья»':'wings', 'Utair Status':'utair',
    'Аэрофлот Бонус':'aeroflot', 'РЖД Бонус':'rzd', 'РГО':'rgo',
    'Программа лояльности членов РГО':'rgo', 'AZIMUT Bonus':'azimut_hotels',
    'ЕКП — официальные объявления':'ekp', 'Единая карта петербуржца (ЕКП)':'ekp',
    'ЕКП → МЕДИ':'ekp', 'ЕКП → Нева Тревел':'ekp',
    'РЖД Бонус — объявления «Вагон скидок»':'rzd',
    'T2 «Больше»':'t2_bolshe', 'T2 Selection':'t2_selection',
    'MiXX M':'mixx_m', 'MiXX':'mixx', 'KEY':'key',
}


def dump(v):
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(v):
    return hashlib.sha256(dump(v).encode()).hexdigest()


def decimal(v):
    x = Decimal(str(v).replace('\u00a0','').replace('\u202f','').replace(' ','').replace(',','.'))
    if not x.is_finite(): raise ValueError('Non-finite amount')
    s = format(x,'f')
    return s.rstrip('0').rstrip('.') if '.' in s else s


def search_key(v):
    # Search key, not a claim that differently named businesses are one entity.
    if v is None: return None
    return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',str(v)).casefold()).strip()


def pointer(value, path):
    if path == '': return value
    for part in path.lstrip('/').split('/'):
        part = part.replace('~1','/').replace('~0','~')
        value = value[int(part)] if isinstance(value,list) else value[part]
    return value


def quote(value):
    return value if isinstance(value,str) else dump(value)


def evidence(raw, path, fragment=None):
    value = quote(pointer(raw,path))
    if fragment is not None and fragment not in value:
        raise ValueError('Evidence fragment not in its source')
    return {'path':path,'text':value if fragment is None else fragment}


def iso_date(value):
    if value is None or value == '': return None
    if isinstance(value,(int,float)) and 20000 < value < 70000:
        return (date(1899,12,30)+timedelta(days=int(value))).isoformat()
    s=str(value).strip()
    for fmt in ('%Y-%m-%d','%d.%m.%Y','%d %b %Y','%Y-%m-%d %H:%M:%S'):
        try:return datetime.strptime(s,fmt).date().isoformat()
        except ValueError:pass
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}T.+',s):
        try:return datetime.fromisoformat(s.replace('Z','+00:00')).date().isoformat()
        except ValueError:pass
    return None


def url_key(value):
    if not value:return None
    try:
        u=urlsplit(value)
        if u.scheme not in ('http','https') or not u.hostname:return None
        # Do not drop region/query identifiers, fragments or meaningful casing.
        params=[(k,v) for k,v in parse_qsl(u.query,keep_blank_values=True) if not k.lower().startswith('utm_')]
        return urlunsplit((u.scheme,u.netloc.lower(),u.path or '/',urlencode(params),u.fragment))
    except ValueError:return None


def _field(raw, name, default=''):
    return raw['fields'].get(name,{}).get('value',default)


def _text(raw,name):
    v=_field(raw,name)
    return '' if v is None else str(v)


def _list_field(raw,name):
    s=_text(raw,name)
    if not s:return []
    value=json.loads(s)
    if not isinstance(value,list):raise ValueError('Expected array in known source column')
    return value


def make_input(raw):
    """Map one exact source row; never use a template row to fill a missing field."""
    origin=raw['origin']
    if origin not in INPUT_TABS:raise ValueError('Unsupported source table')
    r=dict(id=raw['id'],origin=origin,source_row=raw['row'],program=None,partner=None,title='',
           kind='legacy_offer',benefit='',conditions='',activation='',codes=[],rates=[],details={},
           valid_from=None,valid_until=None,source_url=None,benefit_url=None,link_kind='legacy_reference',
           observed_at=None,source_status=None,source_id=origin,source_warnings=[],privacy='private',
           original=copy.deepcopy(raw),validity_raw=None)
    if origin=='parser_offers':
        for dest,col in [('program','Программа'),('partner','Партнёр'),('title','Заголовок'),
            ('kind','Тип записи'),('benefit','Выгода'),('conditions','Условия'),('activation','Как получить'),
            ('source_url','Источник'),('benefit_url','Ссылка на бенефит'),('link_kind','Тип ссылки'),
            ('observed_at','Получено UTC'),('source_status','Статус источника')]:
            r[dest]=_text(raw,col) or ('' if dest in ('title','benefit','conditions','activation') else None)
        r.update(privacy='public',codes=_list_field(raw,'Промокоды JSON'),rates=_list_field(raw,'Ставки JSON'),
                 source_warnings=_list_field(raw,'Ограничения JSON'))
        r['details']=json.loads(_text(raw,'Детали JSON') or '{}')
        if not isinstance(r['details'],dict):raise ValueError('Expected source details object')
        r['source_id']=r['details'].get('_source',{}).get('source_id',origin)
        r['valid_from']=iso_date(_field(raw,'Начало'));r['valid_until']=iso_date(_field(raw,'Окончание'))
        r['category']=_text(raw,'Категория') or None
    elif origin=='parser_inbox':
        r.update(program=_text(raw,'Источник'),title=_text(raw,'Заголовок страницы'),kind='raw_page',
                 benefit=_text(raw,'Текст страницы — требует разбора'),source_url=_text(raw,'Ссылка на карточку'),
                 observed_at=_text(raw,'Получено UTC'),source_status=_text(raw,'Статус'),privacy='unclassified')
    elif origin=='loyalty_partner_benefits':
        r.update(program=_text(raw,'Программа'),partner=_text(raw,'Партнёр / сервис'),title=_text(raw,'Партнёр / сервис'),
                 benefit=_text(raw,'Выгода'),conditions='\n'.join(filter(None,(_text(raw,'Доступ / стоимость'),_text(raw,'Требуемый уровень / условия'),_text(raw,'Комментарий')))),
                 activation=_text(raw,'Как получить'),source_url=_text(raw,'Ссылка на бенефит'),
                 observed_at=iso_date(_field(raw,'Проверено')),source_status=_text(raw,'Статус'),category=_text(raw,'Категория'))
        r['details']={'declared_benefit_type':_text(raw,'Тип выгоды'),'access_text':_text(raw,'Доступ / стоимость')}
        # Neither a claimed "current" status nor a URL copied across rows is verified now.
        if re.search(r'скидк',r['details']['declared_benefit_type'],re.I) and re.match(r'^\s*\d',r['benefit']):r['benefit']='Скидка '+r['benefit']
        r['validity_raw']=r['source_status']
        matches=re.findall(r'(?:\bдо|завершено|закончился)\s+(\d{2}\.\d{2}\.\d{4})',r['source_status'],re.I)
        if len(set(matches))==1:r['valid_until']=iso_date(matches[0])
    else:
        r.update(program='Яндекс — корпоративные предложения' if origin.startswith('yandex') else 'VG — предложения сообщества',
                 partner=_text(raw,'Service Name'),title=_text(raw,'Service Name'),conditions=_text(raw,'Notes'),
                 category=_text(raw,'Category'),validity_raw=_field(raw,'Validity'),source_url=_text(raw,'Link') or None,
                 source_status='stored_legacy_not_reverified')
        d=raw['fields'].get('Discount',{});v=d.get('value')
        if isinstance(v,(int,float)) and '%' in d.get('format',''):
            r['benefit']='Discount '+decimal(Decimal(str(v))*100)+'%'
        else:r['benefit']='' if v is None else str(v)
        r['valid_until']=iso_date(_field(raw,'Validity'))
        interval=re.fullmatch(r'(\d{4}-\d{2}-\d{2})\s+(?:to|–|—)\s+(\d{4}-\d{2}-\d{2})',str(_field(raw,'Validity')).strip())
        if interval:r['valid_from']=iso_date(interval[1]);r['valid_until']=iso_date(interval[2])
        r['details']={'explicit_code_cell':_text(raw,'Promo Code'),'region':_text(raw,'City') or None,
                      'corporate_eligibility_not_verified':True}
    return r


def _clauses(raw):
    seen=set()
    for name in ('benefit','conditions','activation'):
        value=raw.get(name) or ''
        # Preserve decimal periods, URLs, dates and the actual original substring.
        for m in re.finditer(r'[^\n;]+',value):
            clause=m.group().strip()
            if not clause or clause in seen:continue
            seen.add(clause)
            yield '/'+name,clause


def _scope(clause):
    scope={}
    if re.search(r'перв\w*\s+(?:заказ|покупк|визит|посещен)|first\s+(?:order|visit|purchase)',clause,re.I):scope['purchase_stage']='first'
    if re.search(r'последующ|повторн|repeat|subsequent',clause,re.I):
        scope['purchase_stage']='multiple_stages' if 'purchase_stage' in scope else 'repeat'
    return scope


def normalize_record(raw, *, as_of):
    date.fromisoformat(as_of)
    raw=copy.deepcopy(raw)
    program=raw.get('program')
    n=dict(schema_version=1,normalizer_version=VERSION,id=raw['id'],
           program={'key':ALIASES.get(program,'label:'+str(search_key(program))),'name':program},
           partner={'name':raw.get('partner'),'search_key':search_key(raw.get('partner'))},
           title=raw.get('title'),kind=raw['kind'],category=raw.get('category'),
           privacy=raw['privacy'],eligibility_verified=None,
           provenance={k:raw.get(k) for k in ('origin','source_row','source_id','observed_at','source_url','benefit_url','link_kind','source_status')},
           validity={'from':raw.get('valid_from'),'until':raw.get('valid_until'),'as_of':as_of,'status':'unknown'},
           benefits=[],conditions=[],costs=[],codes=[],raw=raw,
           quality={'level':'partial','verification':'source_snapshot' if raw['origin']=='parser_offers' else 'legacy_not_reverified',
                    'issues':list(raw.get('source_warnings',[])),'unparsed_clause_count':0,'semantic_completeness':'not_certified'},
           relationships=[])
    if n['validity']['until']:n['validity']['status']='expired' if n['validity']['until']<as_of else 'within_stated_period'
    if n['validity']['from'] and n['validity']['from']>as_of:n['validity']['status']='not_started'
    if raw['kind'] in ('raw_page','source_observation') or raw.get('details',{}).get('extraction_method')=='digest_bound_visual_review':
        n['quality']['level']='evidence_only';n['quality']['issues'].append('evidence_only_no_automatic_benefits')
        validate_normalized(n);return n
    d=raw.get('details',{})
    n['availability']={k:d.get(k) for k in ('source_is_started','source_prize_suspended')}
    if d.get('pages'):n['quality']['issues'].append('pdf_table_semantics_not_inferred')
    if raw['kind']=='announcement':n['quality']['issues'].append('announcement_is_not_verified_current_offer')
    supplemental=raw['kind'] in ('program_rules','tier_benefit','announcement','raw_page')
    signatures={g:{} for g in GROUPS}
    def add(group,kind,path,*,value=None,unit=None,qualifier='unspecified',basis_value=None,basis_unit=None,
            scope=None,fragment=None,method='structured_source',reward_unit=None,delivery=None,value_min=None):
        ev=evidence(raw,path,fragment)
        obj={'record_id':raw['id'],'kind':kind,'value':None if value is None else str(value),'unit':unit,
             'qualifier':qualifier,'basis_value':None if basis_value is None else str(basis_value),'basis_unit':basis_unit,
             'scope':scope or {},'evidence':ev,'method':method,'review_required':True,
             'standalone_offer':False if supplemental else raw['kind']=='partner_offer','reward_unit':reward_unit,
             'delivery':delivery,'value_min':None if value_min is None else decimal(value_min)}
        # Include context in identity. Equal rates with different rules cannot merge.
        key=digest({k:v for k,v in obj.items() if k not in ('method',)})
        if key not in signatures[group]:
            obj['id']=digest([raw['id'],group,key]);signatures[group][key]=obj;n[group].append(obj)
        return obj
    def benefit(kind,path,**kw):return add('benefits',kind,path,**kw)
    def condition(kind,path,**kw):return add('conditions',kind,path,**kw)
    def code(value,path,scope=None,delivery='literal',fragment=None):
        return add('codes','promo_code',path,value=value,scope=scope,delivery=delivery,fragment=fragment)
    if raw['kind']=='program_rules' and d.get('retrieval_method')=='coral_linked_public_rules_google_import_v1':
        # Refund percentages, penalty amounts and illustrative codes in a
        # contract are not offers. Preserve the complete linked source text.
        if d.get('public_rule',{}).get('text')!=raw.get('conditions'):
            raise ValueError('Linked rule text mismatch')
        condition('linked_source_rules','/conditions',scope={'parent_references':d['parent_references'],
                  'applicability_requires_parent_offer_review':True})
        n['quality']['level']='structured_with_review'
        n['quality']['issues'].append('linked_rules_no_automatic_benefits_or_codes')
        n['content_sha256']=digest({k:v for k,v in n.items() if k!='content_sha256'})
        validate_normalized(n);return n
    # Existing structure is more precise than the legacy top-level lexical arrays.
    structured_evidence=set()
    airline_rules=d.get('retrieval_method')=='aeroflot_airline_api_google_import_v1'
    if airline_rules:
        # These source coefficients use distance, not the ticket price. A fare
        # exclusion mentioning a discount must not become a discount offer.
        p=d['public_airline']
        for i,row in enumerate(p['miles_table']):
            benefit('earn_miles',f'/details/public_airline/miles_table/{i}',value=row['percent'],unit='percent_of_distance',
                basis_value=100,basis_unit='distance_miles',reward_unit='miles',qualifier='source_table',
                scope={'airline_id':p['id'],'iata':p['iata'],'cabin':row['cabin'],'tariff':row['tariff'],'codes':row['codes'],
                       'qualifying_miles':True,'remaining_exclusions_require_review':True})
        for i,row in enumerate(p['elite_coefficients']):
            benefit('earn_miles',f'/details/public_airline/elite_coefficients/{i}',value=row['percent'],unit='percent_of_distance',
                basis_value=100,basis_unit='distance_miles',reward_unit='miles',qualifier='source_table',
                scope={'airline_id':p['id'],'tier':row['tier'],'qualifying_miles':False})
        condition('airline_source_rules','/conditions',scope={'airline_id':p['id'],'table_exceptions_require_review':True})
        condition('minimum_mileage_source','/details/public_airline/miles_minimum',value=p['miles_minimum'],unit='miles',
            scope={'source_limitation_code':p['miles_limitation'],'applicability_not_inferred':True})
        if p['parent']:condition('parent_airline_reference','/details/public_airline/parent',scope={'not_applied_as_child_table':True})

    for i,c in enumerate(d.get('table_benefits',{}).get('components',[])):
        p=f'/details/table_benefits/components/{i}';rate=c.get('rate');scope=c.get('scope',{})
        scope={scope['kind']:scope.get('value')} if scope.get('kind') else scope
        if rate:
            benefit(KIND.get(rate['kind'],rate['kind']),p+'/evidence',value=decimal(rate['value']),unit=rate['unit'],
                    qualifier=rate.get('qualifier','unspecified'),scope=scope,method='structured_table',value_min=rate.get('min_value'),
                    reward_unit='miles' if rate['kind']=='miles' else 'points' if rate['kind']=='points' else None)
        for j,v in enumerate(c.get('promo_codes',[])):code(v,p+f'/promo_codes/{j}',scope)
    for field in ('earning_rules','flight_bonus_rates'):
        for i,c in enumerate(d.get(field,[])):
            p=f'/details/{field}/{i}';unit=c.get('unit','unknown');kind='earn_miles' if unit=='miles' else 'earn_points' if c.get('reward_unit')=='program_bonus' else KIND.get(c.get('kind'), 'earn_rewards')
            benefit(kind,p,value=decimal(c['value']),unit=unit,qualifier=c.get('qualifier','exact'),
                    basis_value=c.get('basis_amount'),basis_unit=c.get('basis_unit'),reward_unit='miles' if kind=='earn_miles' else c.get('reward_unit','points'),scope={'source_rule':field})
            if c.get('evidence'):structured_evidence.add(c['evidence'])
    red=d.get('redemption_rules')
    if isinstance(red,dict):
        if red.get('max_order_percent') is not None:benefit('redeem_rewards','/details/redemption_rules',value=red['max_order_percent'],unit='percent_of_order',qualifier='up_to',scope={'basis':red.get('basis')})
        if red.get('minimum_cash_percent') is not None:condition('minimum_cash_payment','/details/redemption_rules',value=red['minimum_cash_percent'],unit='percent_of_order',qualifier='at_least')
    for i,c in enumerate(d.get('mileage_options',[])):
        p=f'/details/mileage_options/{i}';scope={'option':c['label']}
        benefit('earn_miles',p,value=c['miles'],unit='miles',basis_value=c['basis_rub'],basis_unit='RUB',qualifier='exact',scope=scope,reward_unit='miles')
        condition('reward_cap',p,value=c.get('monthly_cap_miles'),unit='miles',qualifier='up_to',scope={**scope,'period':'month'})
        add('costs','subscription_cost',p,value=c.get('monthly_subscription_rub'),unit='RUB',qualifier='exact',scope={**scope,'period':'month'})
    for i,c in enumerate(d.get('deposit_reward_tiers',[])):
        p=f'/details/deposit_reward_tiers/{i}'
        scope={k:v for k,v in c.items() if k not in ('points','evidence','reward_unit')}
        benefit('earn_points',p,value=c['points'],unit='points',qualifier='exact',scope=scope,reward_unit=c.get('reward_unit','points'))
    for i,c in enumerate(d.get('spend_reward_tiers',[])):
        p=f'/details/spend_reward_tiers/{i}';scope={k:v for k,v in c.items() if k not in ('miles','evidence')}
        benefit('earn_miles',p,value=c['miles'],unit='miles',basis_value=d.get('earning_basis_rub'),basis_unit='RUB',scope=scope,reward_unit='miles',qualifier='exact')
    for i,c in enumerate(d.get('audiences',[])):
        p=f'/details/audiences/{i}';scope={k:v for k,v in c.items() if k not in ('evidence','promo_code')}
        condition('audience',p,scope=scope)
        if c.get('promo_code'):code(c['promo_code'],p+'/promo_code',scope)
    if d.get('reward_multiplier') is not None:benefit('reward_multiplier','/details/reward_multiplier',value=d['reward_multiplier'],unit='multiplier',qualifier='exact',reward_unit='miles' if re.search('мил',raw.get('benefit',''),re.I) else None)
    scalar_conditions={
        'monthly_minimum_purchases_rub':('minimum_purchase','RUB','at_least','month'),
        'monthly_miles_cap':('reward_cap','miles','up_to','month'),
        'cashback_cap_rub':('benefit_cap','RUB','up_to',None),
        'reward_lifetime_years':('reward_lifetime','years','exact',None),
        'credit_wait_days':('reward_credit_delay','days','up_to',None),
        'cooling_days':('cooling_period','days','exact',None),
        'selection_slots':('selection_limit','services','exact',None),
        'activation_workdays':('activation_delay','workdays','up_to',None),
    }
    for key,(kind,unit,q,period) in scalar_conditions.items():
        if d.get(key) is not None:condition(kind,'/details/'+key,value=d[key],unit=unit,qualifier=q,scope={'period':period} if period else {})
    for key in ('qualification','source_eligibility_flags','membership_component','tier','required_program','required_tariff',
                'required_entry_url','required_entry_evidence','checkout_deadline','family','miles_payment','payment_badges',
                'subscription','fees','service_fee_conditions','earning_conditions','redemption_rules','limitations','audience','activation'):
        if d.get(key) not in (None,{},[], ''):
            group='costs' if key in ('fees','service_fee_conditions','subscription') else 'conditions'
            add(group,key,'/details/'+key,scope={'source_value':d[key]})
    for i,c in enumerate(d.get('tier_values',[])):
        p=f'/details/tier_values/{i}'
        benefit('tier_inclusion',p,value=str(c.get('included')).lower() if c.get('included') is not None else None,unit='boolean',scope={'tier':c.get('tier'),'text':c.get('text')})
    for i,c in enumerate(d.get('tier_rates',[])):
        # Retain the source object without pretending all formats share one rate geometry.
        condition('tier_rate_source','/details/tier_rates/'+str(i),scope={'source_value':c})
    if isinstance(d.get('subscription_plan'),dict):
        c=d['subscription_plan'];p='/details/subscription_plan';scope={'plan':c.get('label')}
        add('costs','subscription_cost',p,value=c.get('annual_rub'),unit='RUB',qualifier='exact',scope={**scope,'period':'year'})
        for f,label,limit in [('flight_discount_rub','flight_discount','flight_segments'),('baggage_discount_rub','baggage_discount','baggage_services')]:
            if c.get(f) is not None:benefit('discount',p,value=c[f],unit='RUB',qualifier='exact',scope={**scope,'service':label,'usage_limit':c.get(limit),'baggage_kg':c.get('baggage_kg') if f=='baggage_discount_rub' else None})
    for i,c in enumerate(raw.get('codes',[])):
        if not isinstance(c,str):raise ValueError('Non-string source promo code')
        if not any(x['value']==c and x['scope'] for x in n['codes']):code(c,f'/codes/{i}')
    explicit=d.get('explicit_code_cell','')
    if explicit:
        # Interpret each cell item independently: "none for exhibitions" is an
        # instruction, while a parenthesized audience label is not code text.
        for item in re.split(r'[,;\n]|\s+/\s+',explicit):
            item=item.strip()
            if not item:continue
            if re.search(r'^(?:no code|none\b|form required|multiple codes|not specified|нет\b|получить)',item,re.I):
                condition('code_instructions','/details/explicit_code_cell',fragment=item)
                continue
            labelled=re.fullmatch(r'(.+?)\s+\(([^()]+)\)',item)
            value=labelled[1].strip() if labelled else item
            scope={'source_label':labelled[2]} if labelled else {}
            code(value,'/details/explicit_code_cell',scope,fragment=item)
    for i,c in enumerate(d.get('promo_code_delivery',[])):
        add('codes','code_delivery',f'/details/promo_code_delivery/{i}',delivery=c.get('method'))
    # Lexical projections are attached to the full original clause, never to every
    # partner in a roundup or every price in a source table.
    numeric_pattern=re.compile(NUM)
    for path,clause in (() if airline_rules else _clauses(raw)):
        scope=_scope(clause);recognized=False
        # Do not derive benefits from unassigned raw PDF table text.
        rates=[] if d.get('pages') else normalize_rates(clause)
        if (re.search(r'\b(?:discount|off|cashback)\b',clause,re.I) or
            (raw['origin'] in ('yandex_discounts_complete_all','VG_community_offers') and re.fullmatch(r'\s*'+NUM+r'\s*%\s*',clause))):
            for m in re.finditer(r'(?:up to\s+)?('+NUM+r')\s*%',clause,re.I):
                rates.append({'kind':'cashback' if re.search('cashback',clause,re.I) else 'discount','value':decimal(m[1]),'unit':'percent','qualifier':'up_to' if re.search('up to',m[0],re.I) else 'exact'})
        if not d.get('pages'):
            for m in re.finditer(r'(?:up to\s+)?('+NUM+r')\s*RUB\s+(?:off|discount)\b',clause,re.I):
                rates.append({'kind':'discount','value':decimal(m[1]),'unit':'RUB','qualifier':'up_to' if re.search('up to',m[0],re.I) else 'exact'})
        if re.search(r'\d\s*%.*милями',clause,re.I) and not rates:
            m=re.search(r'('+NUM+r')\s*%',clause)
            rates=[{'kind':'miles','value':decimal(m[1]),'unit':'percent','qualifier':'up_to' if re.search('до',clause[:m.start()],re.I) else 'exact'}]
        for rr in rates:
            if rr.get('evidence') in structured_evidence:continue
            if re.search(r'комисси|commission',clause,re.I):continue
            # A limit or minimum is a constraint, not an extra cashback/discount.
            if rr['unit']=='RUB' and re.search(r'максимум|максимальн|не более|лимит',clause,re.I):continue
            # Raw points/miles numbers in a payment instruction may be redemption
            # costs, not earning. Keep such clauses for review instead.
            if rr['unit']=='miles' and re.search(r'спис|обмен|оплат\w*\s+мил|потратить',clause,re.I) and not re.search(r'начисл|получ|заработ',clause,re.I):continue
            kind=KIND.get(rr['kind'],rr['kind'])
            if kind=='cashback' and re.search(r'балл|бонус|points',clause,re.I):kind='earn_points'
            elif kind=='cashback' and re.search(r'милями|miles',clause,re.I):kind='earn_miles'
            benefit(kind,path,value=rr['value'],unit=rr['unit'],qualifier=rr.get('qualifier','unspecified'),value_min=rr.get('min_value'),
                    basis_value=rr.get('basis_amount'),basis_unit=rr.get('basis_unit'),scope=scope,fragment=clause,
                    method='clause_candidate',reward_unit='miles' if kind=='earn_miles' else 'points' if kind=='earn_points' else None)
            recognized=True
        if not d.get('pages') and re.search(r'получ\w*|начисл\w*',clause,re.I) and not re.search(r'спис|оплат\w* балл|комисси',clause,re.I):
            for m in re.finditer(r'('+NUM+r')\s+(?:бонус(?:ов|а)?|балл(?:ов|а)?)\b',clause,re.I):
                benefit('earn_points',path,value=decimal(m[1]),unit='points',qualifier='unspecified',scope=scope,fragment=clause,method='clause_candidate',reward_unit='points');recognized=True
        if not d.get('pages') and re.search(r'в подарок|комплиментар|подарок при|gift (?:with|on|for)|complimentary',clause,re.I):
            benefit('gift',path,scope=scope,fragment=clause,method='clause_candidate');recognized=True
        for m in re.finditer(rf'(?:заказ\w*|покупк\w*|чек\w*|бронировани\w*)\s+(?:на\s+сумму\s+)?от\s+({NUM})\s*{MONEY}',clause,re.I):
            condition('minimum_purchase',path,value=decimal(m[1]),unit='RUB',qualifier='at_least',scope=scope,fragment=clause,method='clause_candidate');recognized=True
        for m in re.finditer(rf'(?:максимум(?:\s+скидки)?|максимальн\w*\s+(?:размер\s+)?(?:скидк\w*|к[еэ]шб[еэ]к\w*)|не более)\s*[:—–-]?\s*({NUM})\s*{MONEY}',clause,re.I):
            condition('benefit_cap' if re.search(r'скид|к[еэ]шб[еэ]к',clause,re.I) else 'maximum_amount_reference',path,value=decimal(m[1]),unit='RUB',qualifier='up_to',scope=scope,fragment=clause,method='clause_candidate');recognized=True
        classifiers={
            'stacking_restriction':r'не\s+суммир|не\s+сочета|not combin',
            'exclusion':r'исключ|кроме|не действует|не предоставля|не начисля|not valid|exclud',
            'audience_reference':r'нов\w* клиент|нов\w* пользовател|перв\w* заказ|держател|участник|employee|badge|relatives',
            'card_required':r'предъяв\w* карт|покаж\w* карт|show.*badge',
            'channel_reference':r'онлайн|офлайн|он-лайн|доставк|самовывоз|online|offline',
            'payment_requirement':r'оплат\w*.*(?:СБП|картой|наличн)|payment.*card',
            'timing_condition':r'в течение|до \d+ числа|календарн|рабочих дней|within \d+|Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday',
            'activation_step':r'активиру|зарегистриру|перейдите|укажите|введите|получите.*код|свяжитесь|apply.*code|enter.*code|register',
            'choice_reference':r'\bили\b|либо|на выбор|вместо|\bor\b|choose|select',
            'fee_reference':r'комисси|стоимость.*подпис|автопродлен|commission|subscription fee',
        }
        for kind,pat in classifiers.items():
            if re.search(pat,clause,re.I):
                add('costs' if kind=='fee_reference' else 'conditions',kind,path,scope=scope,fragment=clause,method='clause_candidate');recognized=True
        promo=extract_promocodes(clause,[])
        for c in promo['codes']:
            if not any(x['value']==c for x in n['codes']):code(c,path,scope,fragment=clause)
        for c in promo['delivery']:
            add('codes','code_delivery',path,delivery=c.get('method'),fragment=clause)
        if not recognized:n['quality']['unparsed_clause_count']+=1
    # Codes may occur in both a native field and an explicit audience/table. Only
    # collapse exact value+scope+delivery duplicates; keep all evidence locations.
    seen={};codes=[]
    for c in n['codes']:
        key=dump([c['value'],c['scope'],c['delivery']])
        if key not in seen:seen[key]=c;codes.append(c)
    n['codes']=codes
    for b in n['benefits']:
        b['condition_ids']=[c['id'] for c in n['conditions'] if c['evidence']==b['evidence'] or
                            (c['scope'] and c['scope']==b['scope'])]
        b['condition_linkage']='same_evidence_or_explicit_scope_only'
        b['remaining_record_rules_require_review']=True
    n['quality']['level']='structured_with_review' if any(n[g] for g in GROUPS) else 'evidence_only'
    if n['quality']['unparsed_clause_count']:n['quality']['issues'].append('unparsed_clauses_preserved_in_raw')
    n['quality']['issues']=list(dict.fromkeys(n['quality']['issues']))
    n['content_sha256']=digest({k:v for k,v in n.items() if k!='content_sha256'})
    validate_normalized(n)
    return n


def validate_normalized(n):
    if n['schema_version']!=1 or not n['id'] or n['eligibility_verified'] is not None:
        raise ValueError('Invalid normalized record identity/eligibility')
    if 'content_sha256' in n and n['content_sha256']!=digest({k:v for k,v in n.items() if k!='content_sha256'}):
        raise ValueError('Normalized content hash mismatch')
    condition_ids={c['id'] for c in n['conditions']}
    if any(set(b.get('condition_ids',[]))-condition_ids for b in n['benefits']):
        raise ValueError('Unresolved condition reference')
    ids=set()
    for group in GROUPS:
        for term in n[group]:
            if term['id'] in ids or term['record_id']!=n['id']:raise ValueError('Duplicate or foreign term')
            ids.add(term['id']);ev=term['evidence'];source=quote(pointer(n['raw'],ev['path']))
            if ev['text'] not in source:raise ValueError('Ungrounded evidence')
            if group!='codes' and term['value'] is not None and term['unit'] not in ('boolean',None):decimal(term['value'])
            if term.get('value_min') is not None:
                if term['value'] is None or Decimal(term['value_min'])>Decimal(term['value']):raise ValueError('Reversed numeric range')
    for field in ('from','until'):
        if n['validity'][field]:date.fromisoformat(n['validity'][field])
    if n['validity']['from'] and n['validity']['until'] and n['validity']['from']>n['validity']['until']:
        raise ValueError('Reversed source validity interval')


def normalize_inputs(inputs, *, as_of, public_only=False):
    ids=set();records=[]
    for raw in inputs:
        if raw['id'] in ids:raise ValueError('Duplicate source identity')
        ids.add(raw['id'])
        if public_only and raw['privacy']!='public':continue
        if public_only and raw.get('original',{}).get('fields',{}).get('Ручной комментарий',{}).get('value') not in (None,''):
            raise ValueError('Private manual comment in public export candidate')
        records.append(normalize_record(raw,as_of=as_of))
    # Candidate relations are explicit and non-destructive; no rate/condition is
    # copied between sources, including old manual records and newer observations.
    groups=defaultdict(list)
    for n in records:
        if n['partner']['search_key'] and n['provenance']['source_url']:
            groups[(n['program']['key'],n['partner']['search_key'],url_key(n['provenance']['source_url']))].append(n)
    for group in groups.values():
        for n in group:
            n['relationships']=[{'kind':'same_label_and_url_candidate','record_id':other['id'],'equivalence_verified':False} for other in group if other['id']!=n['id']]
    for n in records:n['content_sha256']=digest({k:v for k,v in n.items() if k!='content_sha256'})
    counts=Counter(n['provenance']['origin'] for n in records)
    return {'schema_version':1,'normalizer_version':VERSION,'as_of':as_of,'records':records,
            'audit':{'input_records':len(inputs),'output_records':len(records),'by_input':dict(counts),
                     'terms':{g:sum(len(n[g]) for n in records) for g in GROUPS},
                     'privacy_mode':'public_only' if public_only else 'private_complete',
                     'unverified_equivalence':'no_cross_record_values_merged',
                     'source_snapshot_sha256':digest(inputs)}}
