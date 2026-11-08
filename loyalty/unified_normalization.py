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
from normalized import (normalize_rates, percent_spans, number, NUMBER, TYPES,
                        NUMERIC_TOKEN, literal_number, number_starts_here,
                        reward_amounts, reward_basis, fixed_discount_amounts, benefit_mentions)
from promo_codes import extract_promocodes
from iso_datetime import parse_iso_datetime
from reward_context import reward_role, benefit_denied, gift_spans

VERSION = '1.0.3'
GROUPS = ('benefits', 'conditions', 'costs', 'codes')
INPUT_TABS = {
    'parser_offers': (1, 26), 'loyalty_partner_benefits': (4, 13),
    'yandex_discounts_complete_all': (1, 7), 'VG_community_offers': (4, 8),
    'parser_inbox': (1, 10),
}
NUM = NUMBER
MONEY = r'(?:₽|руб(?:лей|ля|ль|\.)?|RUB)'
ENGLISH_RATE_LABEL = re.compile(r'\b(?:discount|off|cashback)(?=\W|\d|$)', re.I)
ENGLISH_RATE_ALIASES = {
    'discount': 'скидка', 'off': 'скидка', 'cashback': 'кешбэк',
    'prepayment': 'предоплата', 'prepayments': 'предоплата',
    'payment': 'оплата', 'payments': 'оплата',
    'tax': 'налог', 'taxes': 'налог', 'vat': 'НДС',
    'commission': 'комиссия', 'commissions': 'комиссия',
    'fee': 'комиссия', 'fees': 'комиссия', 'with': 'при', 'and': 'и',
}
ENGLISH_RATE_WORD = re.compile(r'\b(?:'+'|'.join(ENGLISH_RATE_ALIASES)+r')(?=\W|\d|$)', re.I)
RATE_LABEL = re.compile(TYPES['discount']+'|'+TYPES['cashback']+'|'+ENGLISH_RATE_LABEL.pattern,re.I)
REWARD_UNIT_WORDING = {
    'earn_points': r'\b(?:баллами|бонусами|в\s+(?:бонусных\s+)?баллах|в\s+бонусах|'
                   r'в\s+(?:виде|форме)\s+(?:баллов|бонусов|бонусных\s+баллов)|'
                   r'(?:in|as)\s+(?:(?:reward|bonus)\s+)?points)\b',
    'earn_miles': r'\b(?:милями|в\s+милях|в\s+(?:виде|форме)\s+(?:бонусных\s+)?миль|'
                  r'(?:in|as)\s+(?:(?:reward|bonus)\s+)?miles)\b',
    'cashback': r'\b(?:рублями|деньгами|в\s+рублях|(?:in|as)\s+cash)\b',
}
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
    s = number(str(v))
    x = Decimal(s)
    if not x.is_finite(): raise ValueError('Non-finite amount')
    return s


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
        try:return parse_iso_datetime(s).date().isoformat()
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
        for dest,col in (('valid_from','Начало'),('valid_until','Окончание')):
            value=_field(raw,col)
            r[dest]=iso_date(value)
            # Only blank structured date cells may become missing bounds.
            if r[dest] is None and value is not None and (not isinstance(value,str) or value.strip()):
                raise ValueError('Invalid structured source date: '+col)
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
        if isinstance(v,(int,float)) and not isinstance(v,bool) and '%' in d.get('format',''):
            r['benefit']='Discount '+decimal(Decimal(str(v))*100)+'%'
        else:r['benefit']='' if v is None else str(v)
        r['valid_until']=iso_date(_field(raw,'Validity'))
        interval=re.fullmatch(r'(\d{4}-\d{2}-\d{2})\s+(?:to|–|—)\s+(\d{4}-\d{2}-\d{2})',str(_field(raw,'Validity')).strip())
        if interval:
            # An explicit malformed endpoint is not an absent interval bound.
            r['valid_from']=date.fromisoformat(interval[1]).isoformat()
            r['valid_until']=date.fromisoformat(interval[2]).isoformat()
        r['details']={'explicit_code_cell':_text(raw,'Promo Code'),'region':_text(raw,'City') or None,
                      'corporate_eligibility_not_verified':True}
    return r


def _structured_mile_evidence(details):
    """Quotes safe to remove from the lexical buffer after structured projection."""
    result=[]
    for field in ('earning_rules','flight_bonus_rates'):
        for rule in details.get(field,[]):
            literal=rule.get('evidence')
            if (rule.get('unit')!='miles' or rule.get('basis_unit')!='RUB'
                    or not isinstance(literal,str) or '\n' not in literal):
                continue
            # Folding is only a consistency check, never stored evidence.
            # Do not remove a quote containing another reward or two literal
            # mileage claims, even if normalize_rates deduplicates their values.
            flat=' '.join(literal.split())
            if (ENGLISH_RATE_LABEL.search(flat)
                    or any(re.search(TYPES[k],flat,re.I) for k in ('discount','cashback'))):
                continue
            rates=normalize_rates(flat)
            if (len(rates)!=1
                    or len(re.findall(rf'{NUM}\s*мил[ьяиюе]\w*',flat,re.I))!=1):
                continue
            rate=rates[0]
            if (rate['kind']!='miles' or rate['unit']!='miles'
                    or rate.get('basis_unit')!='RUB'
                    or rate.get('basis_amount') is None
                    or rule.get('basis_amount') is None
                    or rate.get('qualifier','exact')!=rule.get('qualifier','exact')):
                continue
            try:
                matches=(decimal(rate['value'])==decimal(rule['value'])
                         and decimal(rate['basis_amount'])==decimal(rule['basis_amount']))
            except (ValueError,InvalidOperation):
                continue
            if matches:result.append(literal)
    return result


def _source_fields(raw):
    source_fields=[('/'+name,raw.get(name) or '') for name in ('benefit','conditions','activation')]
    details=raw.get('details',{})
    partner=details.get('public_partner')
    # Published Sheets rows can identify their adapter by retrieval method
    # without a separate source_id. The version marker also prevents downgrade.
    if (raw.get('source_id')=='aeroflot'
            or details.get('retrieval_method')=='aeroflot_public_api_google_import_v1'
            or isinstance(partner,dict) and 'link_projection_version' in partner):
        from aeroflot_import_catalog import fields,semantic_fields_for_details
        source=semantic_fields_for_details(details)
        if source is not None:
            benefit,conditions=fields(details['public_partner'])
            if (raw.get('benefit')!=benefit or raw.get('conditions')!=conditions
                    or raw.get('activation')!=source['redemption']):
                raise ValueError('af_record_semantic_display_binding')
            source_fields=[('/details/semantic_fields/'+name,source[name])
                           for name in ('benefit','conditions','redemption')]
    return source_fields


def _clauses(raw, *, extra_covered_quotes=None):
    seen=set()
    details=raw.get('details',{})
    structured_quotes=[] if details.get('pages') else _structured_mile_evidence(details)
    for path,value in _source_fields(raw):
        spans=[]
        for literal in [*structured_quotes, *(extra_covered_quotes or {}).get(path, [])]:
            start=value.find(literal)
            # Repeated quotes have no unambiguous structural owner. Keep the
            # prior lexical projection rather than choosing an occurrence.
            if start>=0 and value.find(literal,start+1)<0:
                spans.append((start,start+len(literal)))
        # Preserve decimal periods, URLs, dates and the actual original substring.
        for m in re.finditer(r'[^\n;]+',value):
            clause=m.group().strip()
            if not clause:continue
            start=m.start()+len(m.group())-len(m.group().lstrip())
            rate_clause=clause
            for left,right in spans:
                left=max(start,left)-start
                right=min(start+len(clause),right)-start
                if left<right:
                    # Separators cannot join labels or bases across removed text.
                    rate_clause=rate_clause[:left]+';'*(right-left)+rate_clause[right:]
            key=(clause,rate_clause)
            if key in seen:continue
            seen.add(key)
            yield path,clause,rate_clause


def _scope(clause):
    scope={}
    if re.search(r'перв\w*\s+(?:заказ|покупк|визит|посещен)|first\s+(?:order|visit|purchase)',clause,re.I):scope['purchase_stage']='first'
    if re.search(r'последующ|повторн|repeat|subsequent',clause,re.I):
        scope['purchase_stage']='multiple_stages' if 'purchase_stage' in scope else 'repeat'
    return scope


def _rate_scope(clause,rate,spans):
    """Bind explicit purchase stages to their own percent occurrence."""
    index=rate.get('_percent_index')
    if (type(index) is not int or not 0<=index<len(spans)
            or spans[index]['value']!=rate['value']
            or spans[index]['min_value']!=rate.get('min_value')):
        return {}
    span=spans[index]
    first=r'(?:перв(?:ый|ая|ое|ые|ого|ой|ую|ому|ым|ом|ых|ыми)|first)'
    stage=r'(?:'+first+r'|повторн\w*|последующ\w*|repeat|subsequent)'
    ordinary_noun=r'(?:заказ\w*|покупк\w*|визит\w*|посещен\w*|orders?|purchases?|visits?)\b'
    noun=(r'(?:'+ordinary_noun+r'|(?:чистк\w*|при[её]м\w*|бронирован\w*|'
          r'обращен\w*|подключен\w*)\b)')
    # A lowercase continuation after "руб." stays in the price clause. A capitalized
    # next sentence remains a boundary; this is not a general tokenizer.
    boundaries=[m for m in re.finditer(r'[.!?](?:\s|$)|;',clause)
                if not (m[0].startswith('.') and re.search(r'\bруб\Z',clause[:m.start()],re.I)
                        and re.match(r'\s+[а-яёa-z]',clause[m.start()+1:]))]
    left=max((m.end() for m in boundaries if m.end()<=span['start']),default=0)
    right=min((m.start() for m in boundaries if m.start()>=span['end']),default=len(clause))
    neighbours=[i for i,item in enumerate(spans)
                if left<=item['start'] and item['end']<=right]
    separator=r'[,;+]|\b(?:и|а|или|and|or|but)\b'
    def window(position):
        item=spans[neighbours[position]]
        lower,upper=left,right
        if position:
            start=spans[neighbours[position-1]]['end']
            split=list(re.finditer(separator,clause[start:item['start']],re.I))
            lower=start+split[-1].end() if split else item['start']
        if position+1<len(neighbours):
            stop=spans[neighbours[position+1]]['start']
            split=list(re.finditer(separator,clause[item['end']:stop],re.I))
            upper=item['end']+split[-1].start() if split else stop
        return lower,upper
    windows=[window(i) for i in range(len(neighbours))]
    owned_left,owned_right=windows[neighbours.index(index)]
    # A coordinated modifier may share the final noun: "15% на первый и
    # 10% на повторный заказ". An unrelated first payment is not an order.
    shared=(r'\s*(?:,|\b(?:и|или|and|or)\b)\s*'
            r'(?:'+NUMERIC_TOKEN+r'\s*%\s*(?:(?:на|при|за|on|for)\s+)?'
            r'(?:(?:the|your)\s+)?)?'+stage+r'\s+'+noun)
    markers=[(left+m.start(),left+m.end(),
              'first' if re.match(r'перв|first',m[0],re.I) else 'repeat')
             for m in re.finditer(r'\b(?:повторн\w*|последующ\w*|repeat|subsequent)\b|'
                                  r'\b(?:перв\w*|first)\b(?=\s+'+ordinary_noun+')|'
                                  r'\b'+first+r'\b(?=\s+'+noun+'|'+shared+')',
                                  clause[left:right],re.I)]
    # An explicitly excluded purchase stage is a rule, not an affirmative
    # scope for that benefit. Other components still keep their own stages.
    exclusion=(r'\bне\s+(?:(?:будет|будут)\s+)?'
               r'(?:действ\w*|предостав\w*|начисл\w*|выда\w*)\s+(?:на|при|за|для)\b')
    excluded=[m for m in markers if any(lower<=m[0] and m[1]<=upper
              and re.search(exclusion,clause[lower:m[0]],re.I) for lower,upper in windows)]
    markers=[m for m in markers if m not in excluded]
    local={kind for start,end,kind in markers if owned_left<=start and end<=owned_right}
    all_stages={kind for _,_,kind in markers}
    first,last=spans[neighbours[0]],spans[neighbours[-1]]
    if not local and markers:
        # A single shared prefix, or a suffix of a plain coordinated percent
        # list, may qualify the complete list; do not borrow another rate's tail.
        same_family=len({spans[i].get('family','percent') for i in neighbours})==1
        explicit_prefix=bool(re.match(r'\s*(?:только\s+)?(?:на|при|за|для|for|on)\s+',
                                      clause[left:markers[0][0]],re.I))
        shared_prefix=(all(end<=first['start'] for _,end,_ in markers)
                       and (same_family or explicit_prefix))
        shared_suffix=(same_family and all(start>=last['end'] for start,_,_ in markers)
                       and all(re.fullmatch(r'[\s,]*(?:(?:и|или|and|or)\b[\s,]*)?',
                                            clause[spans[a]['end']:spans[b]['start']],re.I)
                               for a,b in zip(neighbours,neighbours[1:])))
        if shared_prefix or shared_suffix or (same_family and len(all_stages)>1):
            local=all_stages
    if local:
        return {'purchase_stage':next(iter(local)) if len(local)==1 else 'multiple_stages'}
    return _scope(clause[left:right]) if len(neighbours)==1 and not excluded else {}


def _component_context(clause):
    """Purchase-stage owners across different literal benefit components.

    Parenthesized reward caps belong to their preceding component. Other
    quantities/markers are boundaries, even if they do not become benefits.
    """
    groups={'percent':percent_spans(clause)}
    for family in ('points','miles','RUB'):
        matches=(fixed_discount_amounts(clause) if family=='RUB' else reward_amounts(clause,family))
        groups[family]=[{'start':m.start(),'end':m.end(),**a} for m,a in matches]
    groups['gift']=[{'start':m.start(),'end':m.end(),'value':None,'min_value':None}
                    for m in gift_spans(clause,boundaries_only=True)]
    components=sorted(({**s,'family':family,'ordinal':i} for family,spans in groups.items()
                       for i,s in enumerate(spans)),key=lambda s:(s['start'],s['end']))
    anchors=[];owners={}
    for span in components:
        bracket_cap=(span['family'] in ('points','miles') and
                     re.search(r'\(\s*(?:до|не\s+более)\s*$',clause[:span['start']],re.I))
        denominator=(span['family'] in ('points','miles') and
                     re.search(r'\bза\s+(?:кажды[еий]\s+)?$',clause[:span['start']],re.I))
        if ((bracket_cap or denominator) and anchors and
                not re.search(r'[.!?](?:\s|$)|[;\n]',clause[anchors[-1]['end']:span['start']])):
            owners[(span['family'],span['ordinal'])]=len(anchors)-1
        else:
            owners[(span['family'],span['ordinal'])]=len(anchors)
            anchors.append(span)
    scopes={key:_rate_scope(clause,{'_percent_index':index,'value':anchors[index]['value'],
                                    'min_value':anchors[index]['min_value']},anchors)
            for key,index in owners.items()}
    return scopes,{key:(anchors[i]['family'],anchors[i]['ordinal']) for key,i in owners.items()}


def _english_rates(clause, *, heading_context='', with_spans=False):
    """Use the same local ownership rules for English and mixed source text."""
    # These are parser-token aliases in a temporary buffer. The source clause
    # remains unchanged, and every returned rate keeps its original evidence.
    working = ENGLISH_RATE_WORD.sub(lambda m: ENGLISH_RATE_ALIASES[m[0].casefold()], clause)
    working = re.sub(r'\bon\s+комиссия(?=\W|\d|$)', 'на комиссию', working, flags=re.I)
    working = re.sub(r'\bup\s+to(?=\W|\d|$)', 'до', working, flags=re.I)
    working = re.sub(r'\b(предоплат\w*|оплат\w*|налог\w*|НДС|комисси\w*)\s+'
                     r'(?:(?:of|is|at|equals)\s+)+', r'\1 ', working, flags=re.I)
    return [{**rate, 'evidence': clause}
            for rate in normalize_rates(working, heading_context=heading_context,with_spans=with_spans)]


def _discount_percent_is_product_exception(clause, rate, spans):
    """Own only a product markdown inside a positive applicability exception."""
    index=rate.get('_percent_index')
    if (rate.get('kind')!='discount' or rate.get('unit')!='percent'
            or not isinstance(index,int) or not 0<=index<len(spans)
            or spans[index]['value']!=rate.get('value')
            or spans[index]['min_value']!=rate.get('min_value')):
        return False
    # Periods within decimal numbers are not sentence boundaries. A new
    # sentence/paragraph or semicolon cannot inherit an earlier exception.
    before=clause[:spans[index]['start']]
    start=max((m.end() for m in re.finditer(r'[.!?](?=\s|$)|[\n;]',before)),default=0)
    context=before[start:]
    applies=re.search(r'\bраспространя(?:ется|ются)\s+на\s+',context,re.I)
    if not applies or re.search(r'\bне\b',context[:applies.start()],re.I):
        return False
    scope=context[applies.end():]
    exception=re.search(r',\s*кроме(?!\s+того\b)\s+',scope,re.I)
    if not exception:
        return False
    # Require the percentage's own product descriptor, rather than every
    # later rate in the sentence. "А на доставку скидка 20%" remains a benefit.
    # This deliberately does not interpret arbitrary exclusions or negations.
    descriptor=scope[exception.end():]
    if re.search(r'\bкроме\s+того\b',descriptor,re.I):
        return False
    return bool(re.search(r'\b(?:товар(?:а|ов)|издели(?:я|й)|украшени(?:я|й))'
                          r'\s+(?:с|со)\s+(?:прямой\s+)?скидкой\s*'
                          r'(?:[-−–—]\s*)?(?:(?:до|от)\s*)?$',descriptor,re.I))


def _cashback_kind(clause,rate,spans):
    """Bind reward units to one occurrence, retaining the original rate schema."""
    index=rate.get('_percent_index')
    if (not isinstance(index,int) or not 0<=index<len(spans)
            or spans[index]['value']!=rate['value']
            or spans[index]['min_value']!=rate.get('min_value')):
        return 'cashback'
    def preposed_unit(i):
        if i==0:return None
        left=spans[i-1]['end']
        fragment=clause[left:spans[i]['start']]
        boundaries=list(re.finditer(r'[,;+]|\b(?:и|and)\b',fragment,re.I))
        if not boundaries:return None
        boundary=boundaries[-1];local=fragment[boundary.end():]
        if any(re.search(pattern,local,re.I) for pattern in REWARD_UNIT_WORDING.values()):
            return left+boundary.start(),local
        return None

    span=spans[index];labels=list(RATE_LABEL.finditer(clause))
    before=[label for label in labels if label.start()<span['start']]
    after=[label for label in labels if label.start()>=span['end']]
    postfix=(after[0] if after and not clause[span['end']:after[0].start()].strip() else None)
    # A shared prefix such as "кешбэк в баллах" can label several rates, but
    # another rate's postfix ("10% баллами") cannot label its neighbour.
    prefix=''
    if before and postfix is None:
        label=before[-1]
        labels_previous=any(item['end']<=label.start() and
                            not clause[item['end']:label.start()].strip()
                            for item in spans[:index])
        if not labels_previous:
            first=next(item for item in spans if item['start']>=label.start())
            prefix=clause[label.start():first['start']]
    right=spans[index+1]['start'] if index+1<len(spans) else len(clause)
    next_prefix=preposed_unit(index+1) if index+1<len(spans) else None
    if next_prefix:right=min(right,next_prefix[0])
    later=[label.start() for label in after if label is not postfix]
    if later:right=min(right,later[0])
    sentence_break=r'[.!?](?:\s|$)|;'
    tail=clause[span['end']:right]
    sentences=re.split(sentence_break,tail,maxsplit=2)
    suffix=sentences[0]
    local_prefix=preposed_unit(index)
    for local in (suffix,local_prefix[1] if local_prefix else '',prefix):
        kinds=[kind for kind,pattern in REWARD_UNIT_WORDING.items() if re.search(pattern,local,re.I)]
        if kinds:return kinds[0] if len(kinds)==1 else 'cashback'
    # An immediately following sentence may name the same payout explicitly.
    # Require one owner and a positive amount/return construction, not merely
    # a later mention of points in payment instructions or exclusions.
    if (len(sentences)<2 or tail[len(suffix)]!='.'
            or (len(sentences)==2 and right<len(clause))):
        return 'cashback'
    sentence_start=max((m.end() for m in re.finditer(sentence_break,clause)
                        if m.end()<=span['start']),default=0)
    if any(item['start']>=sentence_start for item in spans[:index]):
        return 'cashback'
    continuation=sentences[1].strip()
    payout=re.match(r'(?:(?:(?:полная|вся|эта)\s+)?(?:стоимость|сумма)\s+'
                    r'(?:верн[её]тся|возвращается|начисляется|будет\s+(?:возвращена|начислена))'
                    r'(?:\s+вам)?(?:\s+на\s+(?:ваш\s+)?сч[её]т)?|'
                    r'(?:the\s+)?amount\s+(?:is|will\s+be)\s+(?:credited|returned|paid))\s+',
                    continuation,re.I)
    if payout:
        local=continuation[payout.end():]
        kinds=[kind for kind,pattern in REWARD_UNIT_WORDING.items() if re.search(pattern,local,re.I)]
        if len(kinds)==1 and re.match(REWARD_UNIT_WORDING[kinds[0]],local,re.I):
            return kinds[0]
    return 'cashback'


def _amount_matches(pattern,clause):
    """Validate the entire captured numeric token before deriving an amount."""
    for match in re.finditer(pattern,clause,re.I):
        if not number_starts_here(clause,match.start(1)):
            continue
        value=literal_number(match[1])
        if value is not None:
            yield match,value


def _validate_as_of(as_of):
    # Validity comparisons require the same canonical date form on both sides.
    if not isinstance(as_of,str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}',as_of):
        raise ValueError('as_of must use YYYY-MM-DD')
    date.fromisoformat(as_of)


def normalize_record(raw, *, as_of):
    _validate_as_of(as_of)
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
    cap_owners={};component_benefits=defaultdict(set)
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
        return signatures[group][key]
    def benefit(kind,path,**kw):return add('benefits',kind,path,**kw)
    def condition(kind,path,**kw):return add('conditions',kind,path,**kw)
    def code(value,path,scope=None,delivery='literal',fragment=None):
        return add('codes','promo_code',path,value=value,scope=scope,delivery=delivery,fragment=fragment)
    if d.get('retrieval_method')=='konsierge_public_browser_capture_v1':
        from konsierge_catalog import project_common
        return project_common(raw,n,benefit,condition,code)
    if d.get('retrieval_method')=='source_owned_public_rewards_v1':
        from public_reward_projection import project_common
        return project_common(raw,n,benefit,condition,code)
    if raw['origin']=='parser_offers':
        from alfa_partner_rules import BY_URL as ALFA_PARTNER_URLS, BY_RECORD_ID as ALFA_PARTNER_IDS, SOURCE_ID as ALFA_PARTNER_SOURCE
        if raw.get('source_url') in ALFA_PARTNER_URLS or raw['id'] in ALFA_PARTNER_IDS or raw.get('source_id')==ALFA_PARTNER_SOURCE:
            from alfa_partner_rules import project_common
            return project_common(raw,n,benefit,condition,code)
    if 'tsum_evidence' in d:
        from tsum_alfa import URL, derived
        tier=d.get('tsum_tier')
        claim,terms,activation=derived(d['tsum_evidence'],tier)
        if (raw['program']!='Alfa Only' or raw['source_url']!=URL or raw['kind']!='partner_offer'
            or raw['benefit']!=claim or raw['conditions']!=terms or raw['activation']!=activation):
            raise ValueError('TSUM owned evidence changed')
        scope={'merchant_tier':tier,'reward_program':'TSUM_DLT','eligibility_not_verified':True}
        rule=condition('owned_merchant_rules','/conditions',scope=scope)
        action=condition('activation_step','/activation',scope=scope)
        rates=normalize_rates(claim)
        if len(rates)!=1:raise ValueError('TSUM tier rate count')
        rate=rates[0]
        b=benefit('earn_points','/benefit',value=rate['value'],unit='percent',qualifier='exact',
            reward_unit='TSUM_DLT_loyalty_credit',scope=scope,method='owned_source_clause')
        b.update(condition_ids=[rule['id'],action['id']],condition_linkage='full_owned_record_rules',remaining_record_rules_require_review=True)
        n['quality']['level']='structured_with_review'
        n['quality']['issues'].append('shop_loyalty_not_cash_baseline_rates_remain_conditions')
        n['content_sha256']=digest({k:v for k,v in n.items() if k!='content_sha256'})
        validate_normalized(n);return n
    if d.get('scope')=='only_cards_in_current_public_partner_inventory':
        from hse_alumni import PROGRAM,ROOT,claim_text,hse_rates,source_location
        block=d.get('public_catalog_block',{})
        if (raw['program']!=PROGRAM or raw['source_url']!=source_location(block,True)[0]
            or raw['conditions']!=block.get('body') or raw['benefit']!=claim_text(block.get('body',''))):
            raise ValueError('HSE owned evidence changed')
        scope={'anchor':block['anchor'],'programme_membership_not_verified':True}
        if block.get('identity_method'):
            scope.update(identity_method=block['identity_method'],detail_heading=block['detail_heading'])
        rule=condition('owned_partner_rules','/conditions',scope=scope)
        for rate in hse_rates(raw['benefit']):
            local={**scope,**_scope(rate['evidence'])}
            if rate['evidence'] in d.get('month_limited_clauses',[]):
                local['calendar_constraint_text']=rate['evidence']
            b=benefit(rate['kind'],'/benefit',value=rate['value'],unit=rate['unit'],
                qualifier=rate['qualifier'],value_min=rate.get('min_value'),scope=local,
                fragment=rate['evidence'],method='owned_source_clause')
            b.update(condition_ids=[rule['id']],condition_linkage='full_owned_record_rules',remaining_record_rules_require_review=True)
        for i,value in enumerate(raw['codes']):code(value,f'/codes/{i}',scope)
        n['quality']['level']='structured_with_review'
        n['quality']['issues'].append('month_product_audience_and_code_scopes_require_owned_rules')
        n['content_sha256']=digest({k:v for k,v in n.items() if k!='content_sha256'})
        validate_normalized(n);return n
    if d.get('retrieval_method') in ('ekp_source_linked_rules_v1','aeroflot_source_linked_rules_v1'):
        if raw['kind'] not in ('program_rules','source_observation') or not d.get('parent_references'):
            raise ValueError('EKP linked rules provenance missing')
        if not d.get('live_document_text') and d.get('public_rule_text')!=raw.get('conditions'):
            raise ValueError('EKP linked HTML text mismatch')
        condition('linked_source_rules','/conditions',scope={'parent_references':d['parent_references'],
                  'document_part':d.get('document_part'),'applicability_requires_parent_offer_review':True})
        n['quality']['issues'].append('linked_rules_no_automatic_benefits_or_codes')
        n['content_sha256']=digest({k:v for k,v in n.items() if k!='content_sha256'})
        validate_normalized(n);return n
    if d.get('retrieval_method')=='rzd_external_direct_v1':
        # Only the tour-owned RZD clause projects benefits. Other price-table
        # discounts, bank refund rules and illustrative codes stay conditions.
        scope={'source_url':raw['source_url'],'title':raw['title'],'eligibility_not_verified':True}
        if d.get('public_tour'):
            for rate in normalize_rates(raw.get('benefit','')):
                benefit(rate['kind'],'/benefit',value=rate['value'],unit=rate['unit'],
                        qualifier=rate['qualifier'],scope=scope)
        condition('external_partner_rules','/conditions',scope=scope)
        n['quality']['issues'].append('external_context_not_generalized_to_all_products')
        n['content_sha256']=digest({k:v for k,v in n.items() if k!='content_sha256'})
        validate_normalized(n);return n
    if raw['kind']=='program_rules' and d.get('retrieval_method')=='coral_source_linked_pdf_free_api_v1':
        # The PDF is a contract, not a catalogue of extra discounts or codes.
        if not d.get('live_document_text') or not d.get('parent_references'):
            raise ValueError('Linked PDF provenance missing')
        condition('linked_pdf_rules','/conditions',scope={'parent_references':d['parent_references'],
                  'document_part':d['document_part'],'document_sha256':d['document_sha256'],
                  'applicability_requires_parent_offer_review':True})
        n['quality']['level']='structured_with_review'
        n['quality']['issues'].append('linked_rules_no_automatic_benefits_or_codes')
        n['content_sha256']=digest({k:v for k,v in n.items() if k!='content_sha256'})
        validate_normalized(n);return n
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
    covered_quotes={}
    if raw.get('source_id')=='af_vtb_rules':
        from vtb_card_projection import project_stored_card
        owned=project_stored_card(raw)
        if owned:
            covered_quotes=owned['covered_quotes']
            cashback=owned['cashback']
            benefit('cashback',cashback['path'],value=cashback['value'],unit=cashback['unit'],
                    qualifier=cashback['qualifier'],scope=cashback['scope'],
                    fragment=cashback['evidence'],method='owned_source_clause')
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
    redemption_path='/details/redemption_rules'
    if isinstance(red,dict):
        from known_rules import CONFIG as KNOWN_RULES
        if raw['origin']=='parser_offers' and any(
                cfg.get('handler')=='retail_miles' and cfg['url']==raw.get('source_url')
                for cfg in KNOWN_RULES.values()):
            from known_rule_terms import retail_redemption_terms
            literal=red.get('evidence')
            if (not isinstance(literal,str) or not literal.strip()
                    or ' '.join(literal.split()) not in ' '.join(raw.get('conditions','').split())):
                raise ValueError('known_rule_redemption_evidence_mismatch')
            # Old stored adapters hardcoded the basis. Derive all associated
            # terms from the quotation so stale numbers cannot contradict the
            # same evidence, leaving historical raw untouched.
            red={**red,**retail_redemption_terms(literal)}
            redemption_path+='/evidence'
        if red.get('max_order_percent') is not None:benefit('redeem_rewards',redemption_path,value=red['max_order_percent'],unit='percent_of_order',qualifier='up_to',scope={'basis':red.get('basis')})
        if red.get('minimum_cash_percent') is not None:condition('minimum_cash_payment',redemption_path,value=red['minimum_cash_percent'],unit='percent_of_order',qualifier='at_least')
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
            projected=red if key=='redemption_rules' else d[key]
            path=redemption_path if key=='redemption_rules' else '/details/'+key
            add(group,key,path,scope={'source_value':projected})
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
    # A label and its literal coupon may occupy adjacent lines of one field.
    # Recover these before clause splitting, keeping the same local context and
    # never joining separate fields, blank sections or repeated ambiguous quotes.
    if not d.get('pages'):
        for path,value in _source_fields(raw):
            for item in extract_promocodes(value)['evidence']:
                literal=item['evidence']
                if ('\n' not in literal or value.count(literal)!=1
                        or any(c['value']==item['code'] for c in n['codes'])):
                    continue
                start=value.index(literal);stop=start+len(literal)
                left=max(value.rfind('\n',0,start),value.rfind(';',0,start))+1
                ends=[p for separator in ('\n',';') if (p:=value.find(separator,stop))>=0]
                fragment=value[left:min(ends) if ends else len(value)].strip()
                code(item['code'],path,_scope(fragment),fragment=fragment)
    # Lexical projections are attached to the full original clause, never to every
    # partner in a roundup or every price in a source table.
    owned_heading=''
    heading=d.get('source_heading_context')
    # Older published hotel rows predate the explicit adapter ID. Recognize
    # only their exact source contract; retain the original source metadata.
    legacy_hotel=(raw.get('origin')=='parser_offers'
                  and raw.get('source_id')=='parser_offers' and '_source' not in d)
    if (raw.get('source_url')=='https://sacvoyage.ru/aktsii/'
            and (raw.get('source_id')=='sacvoyage_loyalty' or legacy_hotel)
            and d.get('source_scope')=='hotel_owned_loyalty_not_RZD'
            and isinstance(heading,str) and heading
            and raw.get('benefit','').startswith(heading+': ')):
        owned_heading=heading
    for path,clause,rate_clause in (() if airline_rules else _clauses(raw,extra_covered_quotes=covered_quotes)):
        scope=_scope(clause);recognized=rate_clause!=clause
        # Do not derive benefits from unassigned raw PDF table text.
        # The hotel's published heading labels only its owned benefit section;
        # common conditions and unrelated sources cannot inherit that label.
        heading_context=owned_heading if path=='/benefit' else ''
        rate_text=rate_clause.removeprefix(heading_context+': ') if heading_context else rate_clause
        spans=percent_spans(rate_text)
        rate_scopes,rate_owners=_component_context(rate_text)
        clause_scopes,clause_owners=(rate_scopes,rate_owners) if rate_text==clause else _component_context(clause)
        rates=[]
        if not d.get('pages'):
            rate_parser = _english_rates if ENGLISH_RATE_LABEL.search(rate_text) else normalize_rates
            rates = rate_parser(rate_text, heading_context=heading_context,with_spans=True)
            # Only the known legacy Discount column supplies an implicit
            # label. A bare percent in Notes or another source does not.
            if (path=='/benefit' and raw['origin'] in ('yandex_discounts_complete_all','VG_community_offers')
                    and re.fullmatch(r'\s*('+NUM+r')\s*%\s*',rate_clause)
                    and len(spans)==1 and spans[0]['min_value'] is None):
                rates.append({'kind':'discount','value':spans[0]['value'],'unit':'percent',
                              'qualifier':'exact','evidence':clause,'_percent_index':0})
            for m,value in _amount_matches(r'(?:up to\s+)?('+NUMERIC_TOKEN+r')\s*RUB\s+(?:off|discount)\b',rate_clause):
                rates.append({'kind':'discount','value':value,'unit':'RUB','qualifier':'up_to' if re.search('up to',m[0],re.I) else 'exact','evidence':clause})
        if not d.get('pages') and re.search(r'\d\s*%.*милями',rate_clause,re.I):
            covered={rate.get('_percent_index') for rate in rates if rate['unit']=='percent'}
            for index,span in enumerate(spans):
                if index in covered:continue
                # Complete only this occurrence; another recognized rate does
                # not cover it, and a neighbour's mileage unit cannot label it.
                right=spans[index+1]['start'] if index+1<len(spans) else len(rate_text)
                parts=re.split(r'[.!?](?:\s|$)|;',rate_text[span['end']:right],maxsplit=1)
                tail=parts[0]
                if index+1<len(spans) and len(parts)==1:
                    boundaries=list(re.finditer(r'[,;+]|\b(?:и|или|and|or)\b',tail,re.I))
                    if boundaries:tail=tail[:boundaries[-1].start()]
                prefix=re.split(r'[.!?](?:\s|$)|;',rate_text[:span['start']])[-1]
                denied=r'\bне\s+(?:(?:будет|будут)\s+)?(?:начисл\w*|получ\w*|верн\w*|возвращ\w*)'
                if (re.search(r'\bмилями\b',tail,re.I)
                        and reward_role(rate_text,span['start'],span['end'],amounts=benefit_mentions(rate_text))
                            not in ('denied','spend','reference')
                        and not re.match(r'\s*(?:предоплат|оплат|аванс|НДС|налог|комисси|штраф)',tail,re.I)
                        and not re.search(r'\b(?:оплат\w*|спис\w*|потрат\w*|предоплат\w*|аванс\w*)(?:\s+(?:до|от))?\s*\Z',prefix,re.I)
                        and not re.search(denied+r'[^%.,;!?]*\Z',prefix,re.I)
                        and not re.search(denied,tail,re.I)):
                    rates.append({'kind':'miles','value':span['value'],'min_value':span['min_value'],
                                  'unit':'percent','qualifier':span['qualifier'],'evidence':clause,
                                  '_percent_index':index})
        for rr in rates:
            if _discount_percent_is_product_exception(rate_text,rr,spans):continue
            if rate_clause!=clause:rr['evidence']=clause
            if rr.get('evidence') in structured_evidence:continue
            rate_key=(rr['unit'],rr.get('_percent_index') if rr['unit']=='percent' else rr.get('_amount_index'))
            rate_scope=rate_scopes.get(rate_key,scope if rr['unit']!='percent' else {})
            owner=(path,clause,rate_owners.get(rate_key))
            if rr.get('_reward_cap'):
                cap=condition('benefit_cap',path,value=rr['value'],unit=rr['unit'],qualifier='up_to',
                          basis_value=rr['basis_amount'],basis_unit=rr['basis_unit'],
                          scope=rate_scope,fragment=clause,method='clause_candidate')
                cap_owners.setdefault(cap['id'],set()).add(owner)
                recognized=True
                continue
            # Locally labelled discount/cashback rates already exclude payment
            # percentages. A separate commission must not erase those rewards.
            if (re.search(r'комисси|commission',clause,re.I)
                    and not (rr.get('evidence') and rr['kind'] in ('discount','cashback'))):continue
            # A limit or minimum is a constraint, not an extra cashback/discount.
            if rr['unit']=='RUB' and re.search(r'максимум|максимальн|не более|лимит',clause,re.I):continue
            kind=KIND.get(rr['kind'],rr['kind'])
            # A marketing "bonus" or a program name does not state the reward
            # unit. Require literal wording for payment/credit in points.
            if kind=='cashback':
                kind=_cashback_kind(rate_text,rr,spans)
            reward=benefit(kind,path,value=rr['value'],unit=rr['unit'],qualifier=rr.get('qualifier','unspecified'),value_min=rr.get('min_value'),
                    basis_value=rr.get('basis_amount'),basis_unit=rr.get('basis_unit'),
                    scope=rate_scope,fragment=clause,
                    method='clause_candidate',reward_unit='miles' if kind=='earn_miles' else 'points' if kind=='earn_points' else None)
            component_benefits[owner].add(reward['id'])
            recognized=True
        if not d.get('pages'):
            for index,(m,amount) in enumerate(reward_amounts(clause,'points')):
                value=amount['value']
                amount_scope=clause_scopes.get(('points',index),{})
                owner=(path,clause,clause_owners.get(('points',index)))
                role=reward_role(clause,m.start(),m.end())
                prefix=clause[:m.start()]
                basis=reward_basis(clause,m.start(),m.end())
                if basis is None:continue
                bracket_cap=re.search(r'\(\s*(?:до|не\s+более)\s*$',prefix,re.I)
                period_cap=(role not in ('denied','spend','reference') and amount['qualifier']=='up_to'
                            and (bracket_cap or (role=='unknown' and basis['basis_unit'] in ('month','day'))))
                if period_cap:
                    cap=condition('benefit_cap',path,value=value,unit='points',qualifier='up_to',
                              basis_value=basis['basis_amount'],basis_unit=basis['basis_unit'],
                              scope=amount_scope,fragment=clause,method='clause_candidate')
                    cap_owners.setdefault(cap['id'],set()).add(owner)
                    recognized=True
                    continue
                if role!='earn' and not (role=='unknown' and re.search(r'\+\s*$',prefix)):
                    continue
                # A points-to-money equation alone does not award points.
                # Require its own earning action; a later exchange action
                # owns the formula, but an exchange purchase before an explicit
                # award ("за обмен валюты начисляем...") does not cancel it.
                if re.match(r'\s*=\s*'+NUMERIC_TOKEN+r'\s*'+MONEY+r'(?=\W|$)',clause[m.end():],re.I):
                    local_prefix=re.split(r'[.!?](?:\s|$)|[;,]',prefix)[-1]
                    earning=list(re.finditer(r'\b(?:получ\w*|начисл\w*|заработ\w*)\b',local_prefix,re.I))
                    exchange=list(re.finditer(r'\b(?:обменять|обменяйте|конвертировать|конвертируйте)\b',local_prefix,re.I))
                    if not earning or (exchange and exchange[-1].start()>earning[-1].start()):
                        continue
                reward=benefit('earn_points',path,value=value,unit='points',qualifier=amount['qualifier'],
                        value_min=amount['min_value'],basis_value=basis['basis_amount'],basis_unit=basis['basis_unit'],
                        scope=amount_scope,fragment=clause,method='clause_candidate',reward_unit='points')
                component_benefits[owner].add(reward['id'])
                recognized=True
        if not d.get('pages'):
            projected_gifts={(m.start(),m.end()) for m in gift_spans(clause)}
            for index,m in enumerate(gift_spans(clause,boundaries_only=True)):
                if ((m.start(),m.end()) not in projected_gifts or
                        benefit_denied(clause,m.start(),m.end(),amounts=benefit_mentions(clause),gift=True)):continue
                benefit('gift',path,scope=clause_scopes.get(('gift',index),{}),fragment=clause,method='clause_candidate')
                recognized=True
        for m,value in _amount_matches(rf'(?:заказ\w*|покупк\w*|чек\w*|бронировани\w*)\s+(?:на\s+сумму\s+)?от\s+({NUMERIC_TOKEN})\s*{MONEY}',clause):
            condition('minimum_purchase',path,value=value,unit='RUB',qualifier='at_least',scope=scope,fragment=clause,method='clause_candidate');recognized=True
        for m,value in _amount_matches(rf'(?:максимум(?:\s+скидки)?|максимальн\w*\s+(?:размер\s+)?(?:скидк\w*|к[еэ]шб[еэ]к\w*)|не более)\s*[:—–-]?\s*({NUMERIC_TOKEN})\s*{MONEY}',clause):
            condition('benefit_cap' if re.search(r'скид|к[еэ]шб[еэ]к',clause,re.I) else 'maximum_amount_reference',path,value=value,unit='RUB',qualifier='up_to',scope=scope,fragment=clause,method='clause_candidate');recognized=True
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
    cap_benefits={cap:set().union(*(component_benefits[owner] for owner in owners))
                  for cap,owners in cap_owners.items()}
    for b in n['benefits']:
        b['condition_ids']=[c['id'] for c in n['conditions']
                            if ((b['id'] in cap_benefits[c['id']]) if c['id'] in cap_benefits else
                                ({c['scope'].get('purchase_stage'),b['scope'].get('purchase_stage')}!={'first','repeat'}
                                 and (c['evidence']==b['evidence'] or (c['scope'] and c['scope']==b['scope']))))]
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
    _validate_as_of(as_of)
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
