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
                        reward_amounts, reward_basis, fixed_monetary_rewards, benefit_mentions,
                        monetary_caps, percentage_caps, rate_clause_contexts,
                        native_discount_heading)
from promo_codes import (LABEL, extract_promocodes, reconcile_promocode, reconcile_promocode_delivery,
                         coupon_restriction_continuation, coupon_owned_prefix,
                         promocode_occurrences, promocode_cancelled)
from iso_datetime import parse_iso_datetime
from reward_context import (reward_role, benefit_denied, gift_spans, mileage_formula_end,
                            purchase_requirement_denied, benefit_context_text, nominal_reward_cap,
                            nominal_reward_cap_basis, nominal_reward_cap_kind, reward_formula_scope,
                            owned_starred_footnote)
from reward_percentages import percentage_rewards
from reward_nominals import (point_declaration_role, percent_point_ceiling,
                             shared_point_card_options, demo_topup_bonuses)

VERSION = '1.0.12'
GROUPS = ('benefits', 'conditions', 'costs', 'codes')
INPUT_TABS = {
    'parser_offers': (1, 26), 'loyalty_partner_benefits': (4, 13),
    'yandex_discounts_complete_all': (1, 7), 'VG_community_offers': (4, 8),
    'parser_inbox': (1, 10),
}
NUM = NUMBER
MONEY = r'(?:₽|руб(?:лей|ля|ль|\.)?|RUB)'
QUOTED_LABEL = r'«[^»\n]{1,80}»|"[^"\n]{1,80}"'
QUOTED_ALTERNATIVES = rf'(?:{QUOTED_LABEL})(?:\s+или\s+(?:{QUOTED_LABEL})){{0,3}}'
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


def _mile_rule_contexts(raw, rule):
    """Match a retained quotation to its own numeric occurrences, never by value alone."""
    literal=rule.get('evidence')
    if (rule.get('unit')!='miles' or rule.get('basis_unit')!='RUB'
            or not isinstance(literal,str) or not literal):return []
    result=[]
    native_qualifiers=_explicit_qualifiers(rule.get('channel'))
    for path,text in _source_fields(raw):
        if literal not in text:continue
        phrases=_component_phrases(text) if native_qualifiers else {}
        for quote in re.finditer(re.escape(literal),text):
            candidates=[]
            for index,(match,amount) in enumerate(reward_amounts(text,'miles')):
                # The retained excerpt can begin at a range's upper endpoint.
                if not quote.start()<=match.start('value')<quote.end():continue
                basis=reward_basis(text,match.start(),match.end())
                if (basis is None or basis.get('basis_unit')!=rule['basis_unit']
                        or amount['value']!=str(rule['value'])
                        or basis.get('basis_amount')!=str(rule.get('basis_amount'))):continue
                # Include a forward denominator before inspecting a postfix
                # denial. Reverse-denominator quotations end at the reward.
                end=mileage_formula_end(text,match.end())
                denied=benefit_denied(text,match.start(),end)
                qualifier='exact' if amount['qualifier']=='unspecified' else amount['qualifier']
                # Evidence remains an exact substring in its original field.
                left=max((m.end() for m in re.finditer(r'[.!?](?:\s|$)|[;\n]',text[:match.start()])),default=0)
                stop=re.search(r'[.!?](?:\s|$)|[;\n]',text[end:])
                right=end+stop.start()+1 if stop else len(text)
                context=(denied,qualifier,amount['min_value'],path,text[left:right].strip())
                candidates.append((context,_explicit_qualifiers(phrases.get(('miles',index),''))))
            if native_qualifiers:
                if len(candidates)>1:
                    candidates=[c for c in candidates if _qualifiers_represented(native_qualifiers,c[1])]
                else:
                    candidates=[c for c in candidates if _qualifiers_compatible(native_qualifiers,c[1])]
            if len(candidates)==1:result.append(candidates[0][0])
    return result


def _reconciled_mile_rule(raw, rule):
    contexts=_mile_rule_contexts(raw,rule)
    if not contexts:return rule,None
    live=[context for context in contexts if not context[0]]
    if not live:return None,None
    semantics={(c[1],c[2]) for c in live}
    native=(rule.get('qualifier','exact'),rule.get('min_value'))
    if native in semantics:return rule,None
    # A short quote repeated under conflicting bounds has no unique native
    # owner. Let each original lexical occurrence retain its own semantics.
    if len(semantics)!=1:return None,None
    _,qualifier,minimum,path,literal=live[0]
    return {**rule,'qualifier':qualifier,'min_value':minimum,'evidence':literal},(path,literal)


def _retained_multiplier_denied(raw, literal):
    if not isinstance(literal,str) or not literal:return False
    occurrences=[benefit_denied(text,m.start(),m.end())
                 for _,text in _source_fields(raw)
                 for m in re.finditer(re.escape(literal),text)]
    return bool(occurrences) and all(occurrences)


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


def _owned_coupon_texts(raw, owned):
    """Keep scoped native codes bound to their original component evidence.

    Extend a uniquely located excerpt to its original sentence so a truncated
    native quotation cannot hide a postfix cancellation. Ambiguous or missing
    excerpts remain local; sibling occurrences cannot supply applicability.
    """
    if isinstance(owned, dict):
        # A literal code cell is the native assertion being checked, not an
        # independent live occurrence that can overrule its own row's prose.
        return [value for value in owned.get('row', []) if isinstance(value, str)]
    excerpts = [owned] if isinstance(owned, str) else owned if isinstance(owned, list) else []
    result = []
    for excerpt in excerpts:
        if not isinstance(excerpt, str) or not excerpt:
            continue
        contexts = []
        for _, value in _source_fields(raw):
            start = value.find(excerpt)
            if start >= 0 and value.find(excerpt, start + 1) < 0:
                end = start + len(excerpt.rstrip('.!?;'))
                left, right = _sentence_bounds(value, start, end)
                # Sibling audience/card clauses can share a sentence. A line
                # wrapping a postfix predicate still belongs to its literal.
                boundaries = list(re.finditer(
                    r'[,;]|\n(?!\s*(?:больше|уже|временно|сейчас|пока|не|отмен[её]н|аннулирован|недействителен)\b)',
                    value, re.I))
                left = max([left] + [m.end() for m in boundaries if m.end() <= start])
                prefix = coupon_owned_prefix(value, start)
                if re.search(r'\b(?:если|после|при)\b', prefix, re.I):
                    left = min(left, start - len(prefix))
                right = min([right] + [m.start() for m in boundaries if m.start() >= end
                                      and not (m[0] != ';' and coupon_restriction_continuation(value[m.end():]))])
                contexts.append(value[left:right])
        contexts = list(dict.fromkeys(contexts))
        result.extend(contexts if len(contexts) == 1 else [excerpt])
    return result


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
        # A native line wrap can separate the purchase noun from its bound.
        # Preserve offsets and the original evidence while keeping that one
        # syntactically incomplete phrase together for component ownership.
        contexts=value
        wrapped=(r'\b(?:заказ\w*|покупк\w*|чек\w*|бронировани\w*)[ \t]*\n'
                 r'(?=[ \t]*(?:от|до|не\s+менее|свыше|более)\s+'+NUMERIC_TOKEN+r'\s*'+MONEY+')')
        for match in re.finditer(wrapped,value,re.I):
            contexts=contexts[:match.start()]+contexts[match.start():match.end()].replace('\n',' ')+contexts[match.end():]
        clause_contexts=([(0,len(contexts),'')] if _cleaning_purchase_sequence(contexts)
                         else rate_clause_contexts(contexts))
        for left,right,list_heading in clause_contexts:
            literal=value[left:right]
            clause=literal.strip()
            if not clause:continue
            start=left+len(literal)-len(literal.lstrip())
            rate_clause=clause
            for left,right in spans:
                left=max(start,left)-start
                right=min(start+len(clause),right)-start
                if left<right:
                    # Separators cannot join labels or bases across removed text.
                    rate_clause=rate_clause[:left]+';'*(right-left)+rate_clause[right:]
            key=(clause,rate_clause,list_heading)
            if key in seen:continue
            if list_heading and (list_heading+' '+clause,list_heading+' '+rate_clause,'') in seen:
                continue
            seen.add(key)
            yield path,clause,rate_clause,list_heading


def _scope(clause):
    scope={}
    first=r'(?:перв(?:ый|ая|ое|ые|ого|ой|ую|ому|ым|ом|ых|ыми)|first)'
    repeat=r'(?:последующ\w*|повторн\w*|repeat|subsequent)'
    noun=(r'(?:(?:онлайн[-\s])?(?:заказ\w*|покупк\w*|визит\w*|посещен\w*|'
          r'чистк\w*|при[её]м\w*|бронирован\w*|обращен\w*|подключен\w*|'
          r'orders?|visits?|purchases?))\b')
    first_purchase=bool(re.search(r'\b'+first+r'\s+'+noun,clause,re.I)
                        or re.search(r'\b'+first+r'\s+(?:или|и|or|and)\s+'
                                     +repeat+r'\s+'+noun,clause,re.I))
    if re.search(r'перв\w*\s+(?:заказ|покупк|визит|посещен)|first\s+(?:order|visit|purchase)',clause,re.I):
        scope['purchase_stage']='first'
    # Repeating a PIN step, coupon issuance or participation does not identify
    # a purchase stage. Ellipsis is owned only by an explicit first purchase.
    repeat_purchase=bool(re.search(r'\b'+repeat+r'\s+'+noun,clause,re.I))
    if first_purchase and re.search(r'\b(?:на|за|при)\s+(?:все\s+)?'+repeat
                                    +r'(?=\s*(?:по\b|при\b|с\b|[,;.!?()]|$))',clause,re.I):
        repeat_purchase=True
    if repeat_purchase:
        scope['purchase_stage']='multiple_stages' if first_purchase or 'purchase_stage' in scope else 'repeat'
    return scope


def _cap_boundary_text(clause):
    """Keep the observed cap abbreviation from ending its own parenthesis."""
    return re.sub(r'(\bмакс)\.(?=\s*\d)',r'\1 ',clause,flags=re.I)


def _sentence_bounds(clause,start,end):
    """Original-text boundaries, preserving decimals and ruble abbreviations."""
    # A lowercase continuation after "руб." stays in the price clause. A capitalized
    # next sentence remains a boundary; this is not a general tokenizer.
    boundaries=[m for m in re.finditer(r'[.!?](?:\s|$)|;',_cap_boundary_text(clause))
                if not (m[0].startswith('.') and re.search(r'\bруб\Z',clause[:m.start()],re.I)
                        and re.match(r'\s+[а-яёa-z]',clause[m.start()+1:]))]
    left=max((m.end() for m in boundaries if m.end()<=start),default=0)
    right=min((m.start() for m in boundaries if m.start()>=end),default=len(clause))
    return left,right


def _monetary_cap_kind(clause,cap):
    """Resolve the bound's local grammatical owner before reward fallback."""
    if cap['reward'] is not None:return 'benefit_cap'
    left,right=_sentence_bounds(clause,cap.start(),cap.end())
    prefix=re.split(r'[;,]|\b(?:а|но|или)\b',clause[left:cap.start()],flags=re.I)[-1]
    payment=r'(?:предоплат\w*|оплат\w*|аванс\w*|НДС|налог\w*|комисси\w*|штраф\w*|стоимост\w*|цен[аыуе])'
    purchase=r'(?:заказ\w*|покупк\w*|чек\w*|бронировани\w*|транзакци\w*)'
    reward=r'(?:скидк\w*|к[еэ]шб[еэ]к\w*)'
    explicit=(r'(?:(?:лимит|максимальн\w*|максимум)\s+(?:(?:размер|сумм\w*)\s+)?'+reward+
              r'|компенсаци\w*(?:\s+оплат\w*)?|компенсир\w*(?:\s+оплат\w*)?)')
    count=r'(?:кажд\w*|один|одн\w*|\d+|две|два|три|четыре|пять|шесть|семь|восемь|девять|десять)'
    owner=None
    for match in re.finditer(r'\b(?:(?P<explicit>'+explicit+r')|(?P<reward>'+reward+
                             r')|(?P<payment>'+payment+r')|(?P<purchase>'+purchase+r'))\b',prefix,re.I):
        # "Лимит скидки на заказ" and "компенсация ... за чек" name
        # the reward's basis, whereas "при сумме заказа" names spending.
        if (owner=='explicit' and match.lastgroup=='purchase'
                and re.search(r'\b(?:на|за)(?:\s+'+count+r')?\s*$',prefix[:match.start()],re.I)):
            continue
        owner=match.lastgroup
    if re.match(r'\s+'+payment+r'\b',clause[cap.end():right],re.I):owner='payment'
    if (owner=='purchase' and re.search(r'\(\s*$',prefix)
            and re.search(reward,prefix,re.I)):
        return 'benefit_cap'
    if owner in ('payment','purchase'):return 'maximum_amount_reference'
    if owner in ('reward','explicit'):return 'benefit_cap'
    # A percentage of the contract price is the basis of this explicit bonus
    # award. Its following monetary ceiling limits the award, not that price.
    bonus_basis=(r'\b(?:бонусы|баллы|мили)\s+начисля\w*\s+в\s+размере\s+'
                 +NUMERIC_TOKEN+r'\s*%\s+от\s+стоимост\w*'
                 r'[^0-9%.!?;\n]{0,120}?(?:,\s*)?(?:но\s+)?$')
    if re.search(bonus_basis,clause[left:cap.start()],re.I):return 'benefit_cap'
    # Keep the existing unlabelled reward-cap convention only in the absence
    # of an explicit local spending/payment owner.
    return ('benefit_cap' if re.search(r'скид|к[еэ]шб[еэ]к',clause,re.I)
            else 'maximum_amount_reference')


def _owned_accrual_cap_evidence(raw,path,clause):
    """Retain an immediately owned source heading for an otherwise bare bound."""
    if not re.match(r'\s*(?:не\s+более|не\s+больше|максимум)\b',clause,re.I):
        return None
    value=pointer(raw,path)
    if not isinstance(value,str):return None
    pattern=(r'^[ \t]*Лимит\s+по\s+сумме\s+начисления[ \t]*\r?\n[ \t]*'
             +re.escape(clause)+r'(?=[ \t]*\r?$)')
    matches=list(re.finditer(pattern,value,re.I|re.M))
    return matches[0][0].strip() if len(matches)==1 else None


def _monetary_cap_basis(clause,cap):
    """An explicit period or transaction following this monetary ceiling."""
    _,right=_sentence_bounds(clause,cap.start(),cap.end())
    tail=re.split(r'[,;]|\b(?:но|а|или)\b',clause[cap.end():right],maxsplit=1,flags=re.I)[0]
    patterns={
        'campaign':r'\b(?:за|на)\s+(?:весь\s+)?период\s+(?:проведения\s+)?акции\b',
        'month':r'\b(?:за|в)\s+(?:(?:каждый|один)\s+)?месяц\b',
        'day':r'\b(?:за|в)\s+(?:(?:каждый|один)\s+)?день\b',
        'payment':r'\b(?:за|на)\s+(?:(?:каждую|одну)\s+)?оплату\b',
        'booking':r'\b(?:за|на)\s+(?:(?:каждое|одно)\s+)?бронирование\b',
        'ride':r'\b(?:за|на)\s+(?:(?:каждую|одну)\s+)?поездку\b',
        'order':r'\b(?:за|на)\s+(?:(?:каждый|один)\s+)?заказ\b',
        'receipt':r'\b(?:за|на)\s+(?:(?:каждый|один)\s+)?чек\b',
        'purchase':r'\b(?:за|на)\s+(?:(?:каждую|одну)\s+)?покупку\b',
        'contract':r'\b(?:за|на)\s+(?:(?:каждый|один)\s+)?договор\b',
    }
    audience=(r'^\s*[*.]?\s*(?:(?:на|для)\s+(?:(?:одного|одну|каждого)\s+)?'
              r'(?:клиента|участника|пассажира|человека|карту)\s+)?')
    units=[unit for unit,pattern in patterns.items() if re.match(audience+pattern,tail,re.I)]
    return {'basis_value':1,'basis_unit':units[0]} if len(units)==1 else {}


def _owned_monetary_cap_footnote(raw,path,clause):
    """A single starred reward and a single starred bound retain their owner."""
    if not re.match(r'^\*\s*(?:не\s+более|не\s+больше|максимум)\b',clause,re.I):
        return None
    value=pointer(raw,path)
    footnote=owned_starred_footnote(value)
    if footnote is None or footnote['note']!=clause:return None
    owner=footnote['owner']
    rates=normalize_rates(owner,with_spans=True)
    if len(rates)!=1:return None
    rate=rates[0]
    key=(rate['unit'],rate.get('_percent_index') if rate['unit']=='percent'
         else rate.get('_amount_index'))
    _,owners=_component_context(owner)
    if key not in owners:return None
    return {'evidence':footnote['evidence'],'owner':(path,owner,owners[key])}


def _purchase_stage_scope(clause,index,spans):
    """Bind explicit purchase stages to their own component occurrence."""
    span=spans[index]
    first=r'(?:перв(?:ый|ая|ое|ые|ого|ой|ую|ому|ым|ом|ых|ыми)|first)'
    stage=r'(?:'+first+r'|повторн\w*|последующ\w*|repeat|subsequent)'
    ordinary_noun=r'(?:заказ\w*|покупк\w*|визит\w*|посещен\w*|orders?|purchases?|visits?)\b'
    noun=(r'(?:'+ordinary_noun+r'|(?:чистк\w*|при[её]м\w*|бронирован\w*|'
          r'обращен\w*|подключен\w*)\b)')
    service_noun=r'(?:заняти\w*|(?:месячн\w*\s+)?абонемент\w*)\b'
    first_service=r'перв(?:ый|ого|ому|ым|ом|ая|ой|ую|ое)'
    left,right=_sentence_bounds(clause,span['start'],span['end'])
    neighbours=[i for i,item in enumerate(spans)
                if left<=item['start'] and item['end']<=right]
    separator=r'[,;+\n]|\b(?:и|а|или|and|or|but)\b'
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
                                  r'\bследующ\w*\b(?=\s+(?:месячн\w*\s+)?абонемент\w*)|'
                                  r'\b'+first_service+r'\b(?=\s+'+service_noun+')|'
                                  r'\b(?:перв\w*|first)\b(?=\s+'+ordinary_noun+')|'
                                  r'\b'+first+r'\b(?=\s+'+noun+'|'+shared+')',
                                  clause[left:right],re.I)]
    # "На следующие" omits the purchase noun in an explicit first/repeat
    # contrast. A bare "next" booking/month is not a repeat-customer rule.
    if re.search(r'\b'+first+r'\s+'+noun,clause[left:right],re.I):
        markers.extend((left+m.start(1),left+m.end(1),'repeat')
                       for m in re.finditer(r'\bна\s+(?:все\s+)?(следующие)\b'
                                            r'(?=\s*(?:по\b|при\b|с\b|[,;.!?]|$))',
                                            clause[left:right],re.I))
    # An explicitly excluded purchase stage is a rule, not an affirmative
    # scope for that benefit. Other components still keep their own stages.
    exclusion=(r'\bне\s+(?:(?:будет|будут)\s+)?'
               r'(?:действ\w*|предостав\w*|начисл\w*|выда\w*)\s+(?:на|при|за|для)\b')
    excluded=[m for m in markers if any(lower<=m[0] and m[1]<=upper
              and re.search(exclusion,clause[lower:m[0]],re.I) for lower,upper in windows)]
    markers=[m for m in markers if m not in excluded]
    local={kind for start,end,kind in markers if owned_left<=start and end<=owned_right}
    # Only this sequential rate inherits the explicit earlier first visit.
    # Do not turn its ellipsis into a shared stage for another sibling offer.
    if (not local and any(kind=='first' and end<=owned_left for _,end,kind in markers)
            and re.fullmatch(r'\s*далее\s+',clause[owned_left:span['start']],re.I)):
        local={'repeat'}
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
        if shared_prefix or shared_suffix:
            local=all_stages
    if local:
        return {'purchase_stage':next(iter(local)) if len(local)==1 else 'multiple_stages'}
    return _scope(clause[left:right]) if len(neighbours)==1 and not excluded else {}


def _coupon_scopes(value):
    """Keep each labelled coupon (or plural list) with its own stage."""
    mentions=[]
    for mention in LABEL.finditer(value):
        members=promocode_occurrences(value,mention)
        if members:
            end=members[-1][2]
            mentions.append({'start':mention.start(),'end':end-(value[end-1:end]=='.'),
                             'members':members,
                             'cancelled':promocode_cancelled(value,mention.start(),end)})
    result=[]
    extracted=extract_promocodes(value)['codes']
    context=value
    for mention in mentions:
        # Literal coupon spelling is opaque, even when it contains FIRST/REPEAT.
        start,end=mention['start'],mention['end']
        context=context[:start]+' '*(end-start)+context[end:]
    for index,mention in enumerate(mentions):
        if mention['cancelled']:continue
        scope=_purchase_stage_scope(context,index,mentions)
        # An unqualified single code may refer to the immediately preceding
        # sentence. A later or distant offer cannot supply its applicability.
        left,right=_sentence_bounds(context,mention['start'],mention['end'])
        if len(mentions)==1 and not scope and not _scope(context[left:right]):
            previous=context[:left].rstrip().rstrip('.!?;')
            previous_left,_=_sentence_bounds(previous,len(previous),len(previous))
            scope=_scope(re.split(r'\n\s*\n',previous[previous_left:])[-1])
        result.extend((code,scope) for code,_,_ in mention['members'] if code in extracted)
    covered={code for code,_ in result}
    # The extractor also licenses a semicolon-separated CODE - percent list.
    result.extend((code,_scope(context)) for code in extracted if code not in covered)
    return result


def _component_anchors(clause):
    """Purchase-stage owners across different literal benefit components.

    Parenthesized reward caps belong to their preceding component. Other
    quantities/markers are boundaries, even if they do not become benefits.
    """
    groups={'percent':percent_spans(clause)}
    percent_directions=percentage_rewards(clause,groups['percent'])
    boundary_text=_cap_boundary_text(clause)
    cap_starts={match.span('value'):match.start() for match,_ in monetary_caps(clause)}
    for family in ('points','miles','RUB'):
        matches=(((m,a) for m,a,_ in fixed_monetary_rewards(clause))
                 if family=='RUB' else reward_amounts(clause,family))
        groups[family]=[{'start':m.start(),'end':m.end(),**a,
                         'cap_start':cap_starts.get(m.span('value')) if family=='RUB' else None}
                        for m,a in matches]
    groups['gift']=[{'start':m.start(),'end':m.end(),'value':None,'min_value':None}
                    for m in gift_spans(clause,boundaries_only=True)]
    groups['free_delivery']=[{'start':m.start(),'end':m.end(),'value':None,'min_value':None}
                             for m in re.finditer(r'\bбесплатн\w*\s+доставк\w*',clause,re.I)]
    # An independently priced first visit owns its stage even though a plain
    # visit price is not a discount benefit. Do not lend it to a coordinated
    # subscription discount ("первого визита 4000₽ и скидка 15% ...").
    priced_purchase=(r'\b(?:перв\w*|повторн\w*|последующ\w*)\s+'
                     r'(?:визит\w*|посещен\w*|заказ\w*|покупк\w*|при[её]м\w*|бронирован\w*)'
                     r'\s*[-—–:]?\s*(?P<price>'+NUMERIC_TOKEN+r')\s*'+MONEY)
    groups['price_reference']=[
        {'start':m.start(),'end':m.end(),'value':None,'min_value':None}
        for m in re.finditer(priced_purchase,clause,re.I)
        if not any(s['start']<m.end() and m.start('price')<s['end']
                   for spans in groups.values() for s in spans)]
    components=sorted(({**s,'family':family,'ordinal':i} for family,spans in groups.items()
                       for i,s in enumerate(spans)),key=lambda s:(s['start'],s['end']))
    anchors=[];owners={}
    for span in components:
        nominal_cap=(nominal_reward_cap(clause,span['start'])
                     if span['family'] in ('points','miles') else None)
        previous_end=(_sentence_bounds(clause,anchors[-1]['start'],anchors[-1]['end'])[1]
                      if anchors else None)
        cap_continuation=(nominal_cap and anchors and
                          re.fullmatch(r'[.!?]\s*',clause[previous_end:nominal_cap.start()]))
        if (anchors and (nominal_cap or span['family']=='points' and percent_point_ceiling(clause[:span['start']]))):
            left,right=_sentence_bounds(clause,span['start'],span['end'])
            rate_owners=[a for a in anchors if a['family']=='percent' and left<=a['start']<right
                    and percent_directions.get(a['ordinal'],{}).get('kind')
                    in ('earn_points','earn_miles','earn_rewards','cashback')]
            # An explicit nominal ceiling continues one affirmative rate in
            # this same sentence. A list with several rates remains ambiguous.
            cap_continuation=cap_continuation or (len(rate_owners)==1 and rate_owners[0] is anchors[-1])
        bracket_cap=(span['family'] in ('points','miles') and
                     re.search(r'\(\s*(?:до|не\s+более)\s*$',clause[:span['start']],re.I))
        bracket_cap=bracket_cap or (span.get('cap_start') is not None
                     and re.search(r'\(\s*$',clause[:span['cap_start']]))
        bracket_cap=bracket_cap or (nominal_cap and re.search(r'\(\s*$',clause[:nominal_cap.start()]))
        denominator=(span['family'] in ('points','miles') and
                     re.search(r'\bза\s+(?:кажды[еий]\s+)?$',clause[:span['start']],re.I))
        if (cap_continuation or (bracket_cap or denominator) and anchors and
                not re.search(r'[.!?](?:\s|$)|[;\n]',boundary_text[anchors[-1]['end']:span['start']])):
            owners[(span['family'],span['ordinal'])]=len(anchors)-1
        else:
            owners[(span['family'],span['ordinal'])]=len(anchors)
            anchors.append(span)
    return anchors,owners


def _cleaning_purchase_sequence(value):
    """The retained first/second/others list explicitly shares its service noun."""
    percent=NUMERIC_TOKEN+r'\s*%'
    return re.fullmatch(r'\s*(?P<first>'+percent+r'\s+first cleaning)\s*;\s*'
                        r'(?P<second>'+percent+r'\s+second)\s*;\s*'
                        r'(?P<others>'+percent+r'\s+others)\s*[.!]?\s*',value,re.I)


def _service_audience_scope(clause,anchor,phrase):
    """Adult/child service restrictions belong to the local stated component."""
    if not re.search(r'\b(?:заняти\w*|абонемент\w*)\b',phrase,re.I):return {}
    pattern=r'\b(?:для ((?:взрослых|детей)(?:\s+и\s+(?:взрослых|детей))?)|(Взрослым|детям):)'
    def labels(value):
        return {'children' if word.casefold() in ('детей','детям') else 'adults'
                for m in re.finditer(pattern,value,re.I)
                for word in re.findall(r'взрослых|взрослым|детей|детям',m[1] or m[2],re.I)}
    audience=labels(phrase)
    if not audience:
        left,right=_sentence_bounds(clause,anchor['start'],anchor['end'])
        # A single explicit group label may qualify its comma-separated list.
        # Mixed adult/child clauses can only use their local label.
        audience=labels(clause[left:right])
    if len(audience)!=1:return {}
    owned=re.sub(r'\s+Разовая скидка\s*$','',phrase,flags=re.I).strip()
    return {'audience':next(iter(audience)),'source_clause':owned}


def _component_context(clause):
    anchors,owners=_component_anchors(clause)
    scopes={key:_purchase_stage_scope(clause,index,anchors)
            for key,index in owners.items()}
    numbered_pass=bool(re.search(r'\bпервый абонемент\b',clause,re.I)
                       and re.search(r'\bна второй и третий при последовательном продлении\b',clause,re.I))
    phrases=(_component_phrases(clause) if numbered_pass or re.search(
        r'\b(?:для (?:взрослых|детей)|Взрослым:|детям:)',clause,re.I) else {})
    cleaning=_cleaning_purchase_sequence(clause)
    for key,index in owners.items():
        anchor=anchors[index]
        if anchor['family']!='percent':continue
        phrase=phrases.get((anchor['family'],anchor['ordinal']),'')
        scopes[key].update(_service_audience_scope(clause,anchor,phrase))
        if numbered_pass and re.search(r'\bна второй и третий при последовательном продлении\b',phrase,re.I):
            scopes[key].update(purchase_stage='repeat',purchase_ordinals=[2,3],
                               purchase_unit='subscription',source_clause=phrase)
        if cleaning and len(anchors)==3:
            ordinal=anchor['ordinal']
            scopes[key].update(purchase_stage='first' if ordinal==0 else 'repeat',
                               purchase_unit='cleaning',
                               source_clause=cleaning[('first','second','others')[ordinal]])
            scopes[key]['purchase_ordinal' if ordinal<2 else 'purchase_ordinal_min']=ordinal+1
        # The literal tier list qualifies this mileage percentage and any
        # nominal limit explicitly attached to it, never the neighbouring row.
        tiers=re.match(r'\s+милями\s*[—–-]\s*для\s+уровней\s+'
                       r'(?P<tiers>[A-Za-z]+(?:\s*,\s*[A-Za-z]+)*)(?=\s*[.!?]|\s*$)',
                       clause[anchor['end']:],re.I)
        if tiers:scopes[key]['tiers']=re.split(r'\s*,\s*',tiers['tiers'])
    return scopes,{key:(anchors[i]['family'],anchors[i]['ordinal']) for key,i in owners.items()}


def _component_phrases(clause):
    """Original local phrases for occurrence ownership, without changing scopes."""
    anchors,_=_component_anchors(clause)
    result={}
    # Quoted label alternatives do not divide independent reward components.
    boundaries=re.sub(QUOTED_ALTERNATIVES,lambda m:' ' * len(m[0]),clause,flags=re.I)
    boundaries=re.sub(r'\bруб\.(?=\s*[-–—:])',lambda m:m[0][:-1]+' ',boundaries,flags=re.I)
    separator=r',(?!\d)|[;+]|\b(?:и|а|но|или|зато|однако|and|or|but)\b'
    for index,anchor in enumerate(anchors):
        left,right=_sentence_bounds(boundaries,anchor['start'],anchor['end'])
        if right<len(clause) and clause[right] in '.!?':right+=1
        if index and left<=anchors[index-1]['end']<=anchor['start']:
            previous=anchors[index-1]['end']
            splits=list(re.finditer(separator,boundaries[previous:anchor['start']],re.I))
            left=previous+splits[-1].end() if splits else anchor['start']
        if index+1<len(anchors) and anchor['end']<=anchors[index+1]['start']<right:
            following=anchors[index+1]['start']
            splits=list(re.finditer(separator,boundaries[anchor['end']:following],re.I))
            right=anchor['end']+splits[-1].start() if splits else following
        result[(anchor['family'],anchor['ordinal'])]=clause[left:right].strip(' \t\r\n,;')
    return result


def _explicit_qualifiers(text):
    """Literal channel/category qualifications used only to authorize ownership."""
    if not isinstance(text,str):return {}
    result={}
    channels=set()
    if re.search(r'\b(?:в|через)\s+(?:мобильн\w*\s+)?приложени\w*\b|\bapp\b',text,re.I):channels.add('app')
    if re.search(r'\b(?:на|через)\s+сайт\w*\b|\b(?:site|website)\b',text,re.I):channels.add('site')
    if channels:result['interface']=channels
    modes=set()
    if channels or re.search(r'\b(?:он-?лайн|online)\b',text,re.I):modes.add('online')
    if re.search(r'\b(?:оф-?лайн|offline)\b',text,re.I):modes.add('offline')
    if modes:result['mode']=modes
    labelled=(r'\b(?P<kind>раздел\w*|категори\w*|приложени\w*|сайт\w*|магазин\w*)\s+'
              r'(?P<labels>'+QUOTED_ALTERNATIVES+r')')
    for match in re.finditer(labelled,text,re.I):
        kind=match['kind'].casefold()
        key=('category' if re.match(r'раздел|категори',kind) else 'app_name' if kind.startswith('приложени')
             else 'site_name' if kind.startswith('сайт') else 'store_name')
        result.setdefault(key,set()).update(' '.join(name[0][1:-1].split()).casefold()
                                            for name in re.finditer(QUOTED_LABEL,match['labels']))
    return result


def _qualifiers_compatible(source, target):
    # An unqualified local benefit can inherit an explicit local requirement.
    # A broader or different explicitly qualified benefit cannot.
    return all(target[key]<=values for key,values in source.items() if key in target)


def _qualifiers_represented(native, candidate):
    return bool(native) and all(key in candidate and candidate[key]<=values
                                for key,values in native.items())


def _structured_occurrences(rates, clause, rate_text, structured, owners):
    """Reconcile complete signatures only with their unique literal occurrence."""
    groups=defaultdict(list)
    for index,rate in enumerate(rates):
        signature=(clause,KIND.get(rate['kind'],rate['kind']),rate['value'],rate.get('qualifier','exact'),
                   rate.get('min_value'),rate.get('basis_amount'),rate.get('basis_unit'))
        if signature in structured:groups[signature].append(index)
    if not groups:return set(),{}
    phrases=_component_phrases(rate_text)
    skipped=set();fragments={}
    for signature,indexes in groups.items():
        qualifiers={}
        for index in indexes:
            rate=rates[index]
            key=(rate['unit'],rate.get('_percent_index') if rate['unit']=='percent' else rate.get('_amount_index'))
            phrase=phrases.get(owners.get(key),clause)
            qualifiers[index]=_explicit_qualifiers(phrase)
            if len(indexes)>1 and phrase in clause:fragments[index]=phrase
        for channel in structured[signature]:
            native=_explicit_qualifiers(channel)
            if len(indexes)==1:
                candidates=[index for index in indexes if _qualifiers_compatible(native,qualifiers[index])]
            else:
                # Neither numeric equality nor position can choose between
                # independent equal formulas. Require explicit native ownership.
                candidates=[index for index in indexes if _qualifiers_represented(native,qualifiers[index])]
            if len(candidates)==1:skipped.add(candidates[0])
    return skipped,fragments


def _monetary_condition_context(clause,start,end):
    """Return occurrence owners for a monetary condition in one finite component window.

    Pure coordinated rate lists may share an outer purchase condition. Other
    components are separated in the original text, never by amount equality.
    With no local anchors, retain the existing explicit-scope linkage rule.
    """
    # A currency token can include the same period that ends its sentence.
    if clause[end-1:end]=='.':end-=1
    left,right=_sentence_bounds(clause,start,end)
    anchors,_=_component_anchors(clause)
    anchors=[a for a in anchors if left<=a['start'] and a['end']<=right]
    if not anchors:return _scope(clause[left:right]),None
    keys={(a['family'],a['ordinal']) for a in anchors}
    coordinated=all(re.fullmatch(r'[\s,]*(?:(?:и|или|and|or)\b[\s,]*)?',
                                  clause[a['end']:b['start']],re.I)
                    for a,b in zip(anchors,anchors[1:]))
    shared_prefix=(end<=anchors[0]['start']
                   and re.match(r'\s*при\s+(?:заказ\w*|покупк\w*|бронировани\w*)\b',clause[left:end],re.I)
                   and not _scope(clause[left:anchors[0]['start']]))
    if shared_prefix or (coordinated and (end<=anchors[0]['start'] or start>=anchors[-1]['end'])):
        return _scope(clause[left:right]),keys
    # Flattened source lists can omit punctuation between spend tiers. The
    # literal "5% за оплату заказа от ... 10% ..." still names this rate's
    # own purchase threshold; one unrelated unsplit gap must not link every
    # tier's minimum to every sibling benefit in the complete source clause.
    preceding=[a for a in anchors if a['end']<=start]
    if preceding and re.match(r'(?:заказ|покупк|чек|бронировани)\w*\b',clause[start:end],re.I):
        owner=preceding[-1]
        tail=clause[owner['end']:start]
        direct=(r'\s*(?:(?:скидк\w*|к[еэ]шб[еэ]к\w*)\s+)?'
                r'(?:на|за|при)\s+(?:(?:оплат\w*|сумм\w*)\s+)?')
        if re.fullmatch(direct,tail,re.I):
            return (_purchase_stage_scope(clause,anchors.index(owner),anchors),
                    {(owner['family'],owner['ordinal'])})
    boundaries=[left]
    for a,b in zip(anchors,anchors[1:]):
        splits=list(re.finditer(r',(?!\d)|[;+]|\b(?:и|а|или|and|or|but)\b',
                                clause[a['end']:b['start']],re.I))
        # No explicit separator means ownership is unresolved; do not choose
        # a numerically similar benefit or silently borrow its stage.
        if not splits:return _scope(clause[left:right]),None
        boundaries.append(a['end']+splits[-1].end())
    boundaries.append(right)
    for a,lower,upper in zip(anchors,boundaries,boundaries[1:]):
        if lower<=start and end<=upper:
            return _scope(clause[lower:upper]),{(a['family'],a['ordinal'])}
    return _scope(clause[left:right]),None


def _plain_repeated_purchase_rule(clause,start,end):
    """A restated rate/stage/minimum without an unmodelled product qualifier.

    Cross-field signature equality alone cannot distinguish a product-specific
    rule from the headline offer. Accept only a complete plain statement here;
    richer owned rules keep their local linkage and exact evidence.
    """
    stage=r'(?:перв\w*|повторн\w*|последующ\w*)'
    noun=r'(?:заказ\w*|покупк\w*|бронировани\w*)'
    pattern=(r'\s*(?:(?:получите|примените|используйте)\s+промокод\s+на\s+)?'
             r'(?:скидк\w*|к[еэ]шб[еэ]к\w*)\s+'+NUMERIC_TOKEN+r'\s*%\s+'
             r'(?:на|за|при)\s+'+stage+r'\s+'+noun+r'\s+(?:на\s+сумму\s+)?от\s+'
             +NUMERIC_TOKEN+r'\s*'+MONEY+r'\s*[.]?\s*')
    # Inspect this occurrence, not another plain statement in the evidence.
    if clause[end-1:end]=='.':end-=1
    left,right=_sentence_bounds(clause,start,end)
    return bool(re.fullmatch(pattern,clause[left:right],re.I))


def _extend_repeated_purchase_links(benefits,conditions,condition_benefits,component_benefits,plain_minima):
    """Keep a uniquely restated scoped offer's minimum across source fields."""
    fields={'/benefit','/conditions','/activation'}
    signature_fields=('kind','value','value_min','unit','qualifier','basis_value','basis_unit',
                      'scope','reward_unit','delivery')
    groups=defaultdict(list);by_id={b['id']:b for b in benefits}
    occurrences=defaultdict(set)
    for owner,ids in component_benefits.items():
        for bid in ids:occurrences[bid].add(owner)
    for b in benefits:
        if (b['evidence']['path'] in fields and b['scope']
                and b['scope'].get('purchase_stage')!='multiple_stages'):
            groups[dump([b[k] for k in signature_fields])].append(b)
    minima=defaultdict(set)
    for c in conditions:
        if c['kind']=='minimum_purchase':
            for bid in condition_benefits.get(c['id'],set()):minima[bid].add(c['id'])
    for c in conditions:
        local=condition_benefits.get(c['id'],set())
        if (c['kind']!='minimum_purchase' or len(local)!=1
                or c['id'] not in plain_minima):continue
        source=by_id[next(iter(local))]
        key=dump([source[k] for k in signature_fields])
        matching=groups.get(key,[])
        if sum(bool(minima[b['id']]) for b in matching)!=1:continue
        # Count original occurrences too: equal same-field benefits may have
        # deliberately deduplicated into one normalized benefit ID.
        by_path=defaultdict(list)
        for b in matching:by_path[b['evidence']['path']].append(b)
        if len(by_path[source['evidence']['path']])!=1 or len(occurrences[source['id']])!=1:continue
        for target in matching:
            path=target['evidence']['path']
            if (path==source['evidence']['path'] or len(by_path[path])!=1
                    or len(occurrences[target['id']])!=1 or minima[target['id']]):continue
            condition_benefits[c['id']].add(target['id'])


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


def _declared_discount_heading(raw, path, clause=''):
    """A native discount field labels its own benefit text, never other cells."""
    declared=raw.get('details',{}).get('declared_benefit_type','')
    if (raw['origin']=='loyalty_partner_benefits' and path=='/conditions'
            and declared=='Бесплатные сервисы + скидки'
            and re.match(r'^У\s+(?:Gold|Platinum)\s+отдельно\s+есть\s+\d+\s*%\s+в\s+«[^»]+»',clause)):
        return 'Скидка'
    if path != '/benefit':
        return ''
    if (raw['origin'] == 'parser_offers' and raw.get('program') == 'No Name Card'
            and raw.get('source_url') == 'https://nonameburo.com/card'
            and raw.get('link_kind') == 'page_block'
            and raw.get('details', {}).get('pairing') == 'same_record_aligned_column_nearest_label'):
        return native_discount_heading('noname', raw.get('benefit', ''))
    if re.search(r'\b(?:в\s+прежней\s+базе|в\s+старой\s+официальной\s+подборке|'
                 r'не\s+подтверждено|требуют\s+подтверждения)\b', raw.get('benefit',''), re.I):
        return ''
    if raw['origin'] in ('yandex_discounts_complete_all', 'VG_community_offers'):
        return 'Скидка'
    if (raw['origin']=='loyalty_partner_benefits' and re.search(r'скидк',declared,re.I)
            and not re.search(r'к[еэ]шб[еэ]к|спеццен',declared,re.I)):
        # Literal point/mileage units still own their individual components.
        # The native discount label only supplies the unlabelled price part.
        return 'Скидка'
    if (raw['origin']=='loyalty_partner_benefits' and declared in ('Привилегия','Пакет привилегий')
            and re.search(r'\d+\s*%\s+(?:на|у)\s+',clause,re.I)
            and not re.search(r'балл|бонус|мил[ьяиюе]|к[еэ]шб[еэ]к|годовых',clause,re.I)):
        return 'Скидка'
    return ''


def _declared_reward_heading(raw, path):
    if path!='/benefit' or raw.get('origin')!='loyalty_partner_benefits':return ''
    if re.search(r'\b(?:в\s+прежней\s+базе|в\s+старой\s+официальной\s+подборке|'
                 r'не\s+подтверждено|требуют\s+подтверждения)\b',raw.get('benefit',''),re.I):return ''
    declared=raw.get('details',{}).get('declared_benefit_type','')
    allowed={'Баллы','Бонусы','Мили','Начисление бонусов','Бонусы/кешбэк','Бонусы/привилегии',
             'Статусное начисление','Повышенное начисление','Кешбэк'}
    return declared if declared in allowed else ''


def _legacy_package_comparison_echo(raw, path, clause):
    """A museum package's restatement also compares a different membership.

    The own programme discount is already stated in this record's benefit;
    the following individual-card percentage is not another package benefit.
    """
    if (raw['origin']!='loyalty_partner_benefits' or path!='/conditions'
            or raw.get('details',{}).get('declared_benefit_type')!='Пакет привилегий'):
        return False
    comparison=re.fullmatch(r'Скидка\s+('+NUMERIC_TOKEN+r')\s*%\s+на\s+музейные\s+программы\s+'
                            r'против\s+'+NUMERIC_TOKEN+r'\s*%\s+у\s+индивидуальной\s+карты\.?',clause,re.I)
    if not comparison:return False
    own=literal_number(comparison[1]);text=raw.get('benefit','')
    return any(span['value']==own and re.match(r'\s+на\s+программы\b',text[span['end']:],re.I)
               for span in percent_spans(text))


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


def _purchase_minima(clause):
    """Explicit purchase thresholds, retaining their local phrase ownership."""
    purchase=r'(?:заказ\w*|покупк\w*|чек\w*|бронировани\w*)(?:\(и\))?'
    direct=rf'{purchase}\s+(?:на\s+сумму\s+)?от\s+({NUMERIC_TOKEN})\s*{MONEY}'
    covered=set()
    for match,value in _amount_matches(direct,clause):
        covered.add(match.start(1))
        if not purchase_requirement_denied(clause[:match.start()],clause[match.end():]):
            yield match,value,False
    # The retained tour cashback states its eligible payment in both a short
    # headline and the imperative purchase instruction. These are spending
    # thresholds, not another monetary reward.
    tour=rf'\b(?:оплату\s+тура|оплатите\s+тур\s+стоимостью)\s+от\s+({NUMERIC_TOKEN})\s*{MONEY}'
    for match,value in _amount_matches(tour,clause):
        covered.add(match.start(1))
        if not purchase_requirement_denied(clause[:match.start()],clause[match.end():]):
            yield match,value,False
    # A channel/category or basket qualifier may intervene before the explicit
    # "на сумму". Do not cross another purchase, benefit, amount or sentence.
    opening=(r'(?:(?:в|на|через)\s+(?:раздел\w*|категори\w*|приложени\w*|сайт\w*|магазин\w*)'
             r'|онлайн\b|офлайн\b|(?:сложив|добавив|положив|собрав|набрав)\b)')
    other=(purchase+r'|[сc]кидк\w*|к[еэ]шб[еэ]к\w*|мил[ьяиюе]\w*|балл\w*|бонус\w*'
           r'|подар\w*|доставк\w*|начисл\w*|получ\w*|не|нельзя|невозможно|но|а|или|зато|однако')
    bridge=rf'(?:(?:{QUOTED_ALTERNATIVES})|(?!(?:\b(?:{other})\b))[^0-9.!?;\n«»"]){{1,160}}?'
    extended=rf'\b{purchase}\s*,?\s+(?={opening}){bridge}\s+на\s+сумму\s+от\s+({NUMERIC_TOKEN})\s*{MONEY}'
    for match,value in _amount_matches(extended,clause):
        left,_=_sentence_bounds(clause,match.start(),match.end())
        prefix=re.split(r'[,;]|\b(?:а|но|зато|однако)\b',clause[left:match.start()],flags=re.I)[-1]
        if (match.start(1) not in covered
                and not purchase_requirement_denied(prefix,clause[match.end():])):
            yield match,value,True


def _purchase_bounds(clause):
    """Literal spend/payment bounds, including their comparator and price phase."""
    covered=set()
    for match,value,extended in _purchase_minima(clause):
        covered.add(match.start(1))
        yield match,value,extended,'minimum_purchase','at_least',{}
    purchase=r'(?:заказ\w*|покупк\w*|чек\w*|бронировани\w*)'
    bound=r'(?:не\s+менее|свыше|более|до|от)'
    amount=rf'{bound}\s+({NUMERIC_TOKEN})\s*{MONEY}'
    # Product, merchant, card and delivery nouns may qualify the purchase.
    # A new purchase, reward, action or contrast cannot be crossed to borrow
    # the next component's amount. Quoted merchant/category names stay whole.
    stop=(purchase+r'|от|до|не|свыше|более|но|а|или|зато|однако|если|когда|'
          r'скидк\w*|к[еэ]шб[еэ]к\w*|балл\w*|мил[ьяиюе]\w*|бонус\w*|'
          r'подар\w*|выгод\w*|получ\w*|начисл\w*|состав\w*|предостав\w*|верн\w*|возвращ\w*')
    word=rf'(?!(?:{stop})\b)[^\W\d_][\w/-]*'
    qualifiers=rf'(?:(?:{QUOTED_ALTERNATIVES}|{word})\s+){{0,9}}?'
    qualified=rf'\b{purchase}\s+{qualifiers}'
    nominal=(rf'(?:минимальн\w*\s+|общ\w*\s+)?сумм\w*\s+{purchase}'
             r'(?:,\s*за\s+котор\w*\s+начисля\w*\s+(?:мил[ьяиюе]\w*|балл\w*|бонус\w*)\s*,)?'
             r'(?:\s+до\s+скидки)?\s+(?:должна\s+(?:быть|составлять)|составляет)\s+')
    patterns=(
        (qualified+amount,'purchase'),
        (rf'\b{purchase},\s+сумма\s+которых\s+{amount}','purchase'),
        (nominal+amount,'purchase'),
        (r'минимальн\w*\s+сумм\w*\s+к\s+доплате(?:\s+по\s+кассовому\s+чеку)?'
         r'\s+составля\w*\s+'+amount,'cash_payment'),
        (qualified+rf'от\s+{NUMERIC_TOKEN}\s*{MONEY}\s+до\s+({NUMERIC_TOKEN})\s*{MONEY}',
         'purchase_range'),
    )
    for pattern,role in patterns:
        for match,value in _amount_matches(pattern,clause):
            if (match.start(1) in covered
                    # Tier qualification may combine spending, purchase count
                    # and alternative periods; it is not a direct offer bound.
                    or re.search(r'\bприсваивается\s+за\s+',clause[:match.start()],re.I)
                    or purchase_requirement_denied(clause[:match.start()],clause[match.end():])
                    or benefit_denied(clause,match.start(),match.end(),amounts=benefit_mentions(clause))):
                continue
            if role=='purchase_range':
                lower=re.search(r'\bот\s+('+NUMERIC_TOKEN+r')\s*'+MONEY,match[0],re.I)
                if lower is None or match.start()+lower.start(1) not in covered:continue
            covered.add(match.start(1))
            comparator=re.search(r'(не\s+менее|свыше|более|до|от)\s*$',clause[match.start():match.start(1)],re.I)[1]
            qualifier=('greater_than' if comparator.casefold() in ('свыше','более') else
                       'up_to' if comparator.casefold()=='до' else 'at_least')
            kind=('maximum_' if qualifier=='up_to' else 'minimum_')+role.removesuffix('_range')
            extra={}
            if re.search(r'\bдо\s+скидки\b',match[0],re.I):extra['price_phase']='before_discount'
            if (re.match(r'покупки\b',match[0],re.I)
                    and re.search(r'\b(?:на\s+)?общ(?:ую|ей)\s+(?:сумму|стоимостью)\b',match[0],re.I)):
                extra['spending_basis']='aggregate'
            left,right=_sentence_bounds(clause,match.start(),match.end())
            suffix=clause[match.end():right]
            if re.match(r'\s*\(без\s+уч[её]та\s+стоимости\s+доставки\)',suffix,re.I):
                extra['delivery_included']=False
            if re.match(r'\s*после\s+вычета\s+товаров-исключений\b',suffix,re.I):
                extra['excluded_products_removed']=True
            yield match,value,False,kind,qualifier,extra


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
    from owned_offer_dates import project_retained_validity, retained_mir_start_conflict, MIR_START_CONFLICT
    project_retained_validity(raw,n['validity'])
    if n['validity']['until']:n['validity']['status']='expired' if n['validity']['until']<as_of else 'within_stated_period'
    if n['validity']['from'] and n['validity']['from']>as_of:n['validity']['status']='not_started'
    if retained_mir_start_conflict(raw):
        n['validity']['from']=None
        if n['validity']['status']!='expired':n['validity']['status']='source_date_conflict'
        if MIR_START_CONFLICT not in n['quality']['issues']:n['quality']['issues'].append(MIR_START_CONFLICT)
    if raw['kind'] in ('raw_page','source_observation') or raw.get('details',{}).get('extraction_method')=='digest_bound_visual_review':
        n['quality']['level']='evidence_only';n['quality']['issues'].append('evidence_only_no_automatic_benefits')
        validate_normalized(n);return n
    d=raw.get('details',{})
    n['availability']={k:d.get(k) for k in ('source_is_started','source_prize_suspended')}
    from ekp_catalog import project_retained_availability
    project_retained_availability(raw,n['availability'])
    if d.get('pages'):n['quality']['issues'].append('pdf_table_semantics_not_inferred')
    if raw['kind']=='announcement':n['quality']['issues'].append('announcement_is_not_verified_current_offer')
    supplemental=raw['kind'] in ('program_rules','tier_benefit','announcement','raw_page')
    signatures={g:{} for g in GROUPS}
    cap_owners={};component_benefits=defaultdict(set);plain_minima=set()
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
    def code(value,path,scope=None,delivery='literal',fragment=None,*,labels=None):
        # Source-owned projectors can return before the generic projection.
        # Reconcile their native arrays at this shared seam as well, without
        # treating code words or component-owned literals as unscoped coupons.
        if delivery=='literal' and path.startswith('/codes/'):
            value=reconcile_promocode(value,[text for _,text in _source_fields(raw)],labels=labels)
            if value is None:return None
        if path.startswith('/details/promo_code_delivery/'):
            reference=pointer(raw,'/'.join(path.split('/')[:4]))
            if not reconcile_promocode_delivery(delivery,reference.get('evidence')):return None
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
        from hse_alumni import (PROGRAM,ROOT,claim_text,hse_rates,source_location,CODE_LABEL_PATTERNS,
                               hse_rate_signature,hse_coupon_instructions)
        block=d.get('public_catalog_block',{})
        if (raw['program']!=PROGRAM or raw['source_url']!=source_location(block,True)[0]
            or raw['conditions']!=block.get('body') or raw['benefit']!=claim_text(block.get('body',''))):
            raise ValueError('HSE owned evidence changed')
        scope={'anchor':block['anchor'],'programme_membership_not_verified':True}
        if block.get('identity_method'):
            scope.update(identity_method=block['identity_method'],detail_heading=block['detail_heading'])
        rule=condition('owned_partner_rules','/conditions',scope=scope)
        rates=hse_rates(raw['benefit'],with_spans=True)
        counts=Counter(hse_rate_signature(rate) for rate in rates)
        instructions=hse_coupon_instructions(raw['conditions']);code_owners=defaultdict(list)
        for rate in rates:
            clause=rate['evidence']
            rate_scopes,_=_component_context(clause)
            key=(rate['unit'],rate.get('_percent_index') if rate['unit']=='percent'
                 else rate.get('_amount_index'))
            local={**scope,**rate_scopes.get(key,{})};linked=[rule['id']]
            if rate['evidence'] in d.get('month_limited_clauses',[]):
                local['calendar_constraint_text']=rate['evidence']
            signature=hse_rate_signature(rate)
            own=[section for section in instructions if section['signature']==signature]
            if counts[signature]==1 and len(own)==1:
                section=own[0];local['promo_code']=section['codes'][0]
                action=condition('activation_step','/conditions',scope=local,
                                 fragment=section['evidence'],method='owned_source_clause')
                linked.append(action['id'])
                for value in section['codes']:
                    if local not in code_owners[value]:code_owners[value].append(local)
            b=benefit(rate['kind'],'/benefit',value=rate['value'],unit=rate['unit'],
                qualifier=rate['qualifier'],value_min=rate.get('min_value'),scope=local,
                fragment=rate['evidence'],method='owned_source_clause')
            b.update(condition_ids=linked,condition_linkage='full_owned_record_rules',remaining_record_rules_require_review=True)
        for i,value in enumerate(raw['codes']):
            owners=code_owners.get(value,[])
            code(value,f'/codes/{i}',owners[0] if len(owners)==1 else scope,labels=CODE_LABEL_PATTERNS)
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
    def cover_owned_quote(literal):
        # Native typed rules can quote a PDF phrase whose layout whitespace
        # differs in the summary. Match only that complete phrase, once per
        # field, and retain the actual original fragment as the covered span.
        if not isinstance(literal,str) or not literal.strip():return
        pattern=r'\s+'.join(re.escape(part) for part in literal.split())
        if literal[0].isalnum():pattern=r'(?<!\w)'+pattern
        if literal[-1].isalnum():pattern+=r'(?!\w)'
        for path,text in _source_fields(raw):
            matches=list(re.finditer(pattern,text))
            if len(matches)==1:covered_quotes.setdefault(path,[]).append(matches[0][0])
    for path,text in _source_fields(raw):
        for match,topup,bonus in demo_topup_bonuses(text):
            local={'occasion':'demo_account_topup','timing_basis':'customer_demo_period',
                   'source_clause':match[0]}
            reward=benefit('earn_rewards',path,value=bonus,unit='RUB',qualifier='exact',
                           scope=local,fragment=match[0],method='owned_source_clause')
            reward['standalone_offer']=False
            component_benefits[(path,match[0],None)].add(reward['id'])
            condition('required_account_topup',path,value=topup,unit='RUB',qualifier='exact',
                      scope=local,fragment=match[0],method='owned_source_clause')
            condition('timing_condition',path,scope=local,fragment=match['timing'],
                      method='owned_source_clause')
    point_options=shared_point_card_options(raw.get('benefit',''),
                    declared_type=_declared_reward_heading(raw,'/benefit'))
    if point_options:
        owner=('/benefit',raw['benefit'],'shared_point_card_options')
        for option in point_options['options']:
            reward=benefit('earn_points','/benefit',value=option['value'],unit='points',
                           qualifier='exact',reward_unit='points',scope={'card_option':option['label']},
                           method='owned_source_clause')
            component_benefits[owner].add(reward['id'])
        cap=condition('benefit_cap','/benefit',value=point_options['cap'],unit='points',qualifier='up_to',
                      scope={'limit_scope':'multiple_participating_cards'},
                      fragment=point_options['cap_evidence'],method='owned_source_clause')
        cap_owners.setdefault(cap['id'],set()).add(owner)
        for field in ('conditions','activation'):
            if raw.get(field):
                rule=condition('owned_option_rules','/'+field,method='owned_source_clause')
                cap_owners.setdefault(rule['id'],set()).add(owner)
    def cover_owned_option_restatements(option):
        # The public bank FAQ repeats the same typed options under shared
        # denominator/cap headings. Only a complete matching label and number
        # licenses coverage; a bare equal amount elsewhere remains independent.
        item=(rf'(?P<value>{NUMERIC_TOKEN})\s+мил[ьяиюе]\w*\s+'
              r'(?P<preposition>с\s+сервисом|без\s+сервиса)\s+(?P<label>[^\n]+)')
        item_line=rf'[ \t]*{NUMERIC_TOKEN}\s+мил[ьяиюе]\w*\s+(?:с\s+сервисом|без\s+сервиса)\s+[^\n]+'
        headings=(
            (rf'За\s+каждые\s+(?P<basis>{NUMERIC_TOKEN})\s+рубл\w*\s+покупок\s+вам\s+будет\s+начислено:', 'miles'),
            (r'Максимальное\s+кол-во\s+миль\s+в\s+месяц', 'monthly_cap_miles'),
        )
        for path,text in _source_fields(raw):
            for heading,key in headings:
                for group in re.finditer(heading+rf'\n(?P<items>{item_line}(?:\n{item_line})*)',text,re.I):
                    if key=='miles' and literal_number(group['basis'])!=str(option['basis_rub']):continue
                    for match in re.finditer(item,group['items'],re.I):
                        label=('С ' if match['preposition'].casefold().startswith('с ') else 'Без ')+match['label']
                        if (search_key(label)==search_key(option['label'])
                                and literal_number(match['value'])==str(option.get(key))):
                            literal=match[0]
                            if text.count(literal)==1:covered_quotes.setdefault(path,[]).append(literal)
    structured_rates=defaultdict(list)
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
        for j,v in enumerate(c.get('promo_codes',[])):
            v=reconcile_promocode(v,_owned_coupon_texts(raw,c.get('evidence')))
            if v is not None:code(v,p+f'/promo_codes/{j}',scope)
    for field in ('earning_rules','flight_bonus_rates','earning_rule'):
        items=([d[field]] if isinstance(d.get(field),dict) else []) if field=='earning_rule' else d.get(field,[])
        for i,c in enumerate(items):
            c,reconciled_evidence=_reconciled_mile_rule(raw,c)
            if c is None:continue
            p=f'/details/{field}'+('' if field=='earning_rule' else f'/{i}');unit=c.get('unit','unknown');kind='earn_miles' if unit=='miles' else 'earn_points' if c.get('reward_unit')=='program_bonus' else KIND.get(c.get('kind'), 'earn_rewards')
            fragment=None
            if reconciled_evidence:p,fragment=reconciled_evidence
            scope={'source_rule':field}
            if c.get('channel') is not None:scope['channel']=c['channel']
            benefit(kind,p,value=decimal(c['value']),unit=unit,qualifier=c.get('qualifier','exact'),
                    value_min=c.get('min_value'),fragment=fragment,
                    basis_value=c.get('basis_amount'),basis_unit=c.get('basis_unit'),reward_unit='miles' if kind=='earn_miles' else c.get('reward_unit','points'),scope=scope)
            if c.get('evidence'):
                signature=(c['evidence'],kind,decimal(c['value']),c.get('qualifier','exact'),
                           c.get('min_value'),c.get('basis_amount'),c.get('basis_unit'))
                structured_rates[signature].append(c.get('channel'))
                if field=='earning_rule':cover_owned_quote(c['evidence'])
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
        reward=benefit('earn_miles',p,value=c['miles'],unit='miles',basis_value=c['basis_rub'],basis_unit='RUB',qualifier='exact',scope=scope,reward_unit='miles')
        cap=condition('reward_cap',p,value=c.get('monthly_cap_miles'),unit='miles',qualifier='up_to',scope={**scope,'period':'month'})
        owner=(p,None,'mileage_option')
        component_benefits[owner].add(reward['id']);cap_owners[cap['id']]={owner}
        literal=c.get('evidence','')
        for match,amount in reward_amounts(literal,'miles'):
            basis=reward_basis(literal,match.start(),match.end())
            if (amount['value']==str(c['miles']) and basis
                    and basis=={'basis_amount':str(c['basis_rub']),'basis_unit':'RUB'}):
                cover_owned_quote(literal[match.start():mileage_formula_end(literal,match.end())])
        cover_owned_option_restatements(c)
        intro=c.get('introductory_subscription')
        ongoing_scope={**scope,'period':'month'}
        if intro:
            ongoing_scope.update(subscription_phase='ongoing',from_month=intro['months']+1)
            add('costs','subscription_cost',p+'/introductory_subscription',value=intro['monthly_rub'],
                unit='RUB',qualifier='exact',scope={**scope,'period':'month',
                'subscription_phase':'introductory','duration_months':intro['months']})
        add('costs','subscription_cost',p,value=c.get('monthly_subscription_rub'),unit='RUB',qualifier='exact',scope=ongoing_scope)
    for i,c in enumerate(d.get('deposit_reward_tiers',[])):
        p=f'/details/deposit_reward_tiers/{i}'
        scope={k:v for k,v in c.items() if k not in ('points','evidence','reward_unit')}
        benefit('earn_points',p,value=c['points'],unit='points',qualifier='exact',scope=scope,reward_unit=c.get('reward_unit','points'))
    for i,c in enumerate(d.get('spend_reward_tiers',[])):
        p=f'/details/spend_reward_tiers/{i}';scope={k:v for k,v in c.items() if k not in ('miles','evidence')}
        reward=benefit('earn_miles',p,value=c['miles'],unit='miles',basis_value=d.get('earning_basis_rub'),basis_unit='RUB',scope=scope,reward_unit='miles',qualifier='exact')
        component_benefits[('/details/spend_reward_tiers',None,'monthly_spending')].add(reward['id'])
        cover_owned_quote(c.get('evidence'))
    if d.get('welcome_miles') is not None and d.get('welcome_miles_evidence'):
        benefit('earn_miles','/details/welcome_miles_evidence',value=d['welcome_miles'],unit='miles',
                qualifier='exact',reward_unit='miles',scope={'reward_event':'welcome'})
        cover_owned_quote(d['welcome_miles_evidence'])
    for i,c in enumerate(d.get('audiences',[])):
        p=f'/details/audiences/{i}';scope={k:v for k,v in c.items() if k not in ('evidence','promo_code')}
        condition('audience',p,scope=scope)
        if c.get('promo_code'):
            value=reconcile_promocode(c['promo_code'],_owned_coupon_texts(raw,c.get('evidence')))
            if value is not None:code(value,p+'/promo_code',scope)
    if (d.get('reward_multiplier') is not None
            and not _retained_multiplier_denied(raw,d.get('reward_multiplier_evidence'))):benefit('reward_multiplier','/details/reward_multiplier',value=d['reward_multiplier'],unit='multiplier',qualifier='exact',reward_unit='miles' if re.search('мил',raw.get('benefit',''),re.I) else None)
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
        if d.get(key) is not None:
            cap=condition(kind,'/details/'+key,value=d[key],unit=unit,qualifier=q,scope={'period':period} if period else {})
            if key=='monthly_miles_cap' and d.get('spend_reward_tiers'):
                cap_owners[cap['id']]={('/details/spend_reward_tiers',None,'monthly_spending')}
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
    source_coupon_scopes=[item for _,text in _source_fields(raw) for item in _coupon_scopes(text)]
    def coupon_scopes(c,local=None):
        return ([local] if local else
                [scope for value,scope in source_coupon_scopes if value==c and scope] or [{}])
    for i,c in enumerate(raw.get('codes',[])):
        if not isinstance(c,str):raise ValueError('Non-string source promo code')
        c=reconcile_promocode(c,[text for _,text in _source_fields(raw)])
        if c is None:continue
        if not any(x['value']==c and x['scope'] for x in n['codes']):
            for scope in coupon_scopes(c):code(c,f'/codes/{i}',scope)
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
        if reconcile_promocode_delivery(c.get('method'),c.get('evidence')):
            add('codes','code_delivery',f'/details/promo_code_delivery/{i}',delivery=c.get('method'))
    # A label and its literal coupon may occupy adjacent lines of one field.
    # Recover these before clause splitting, keeping the same local context and
    # never joining separate fields, blank sections or repeated ambiguous quotes.
    if not d.get('pages'):
        for path,value in _source_fields(raw):
            for item in extract_promocodes(value)['evidence']:
                literal=item['evidence']
                contexts=_owned_coupon_texts(raw,literal)
                wrapped_context=contexts[0] if len(contexts)==1 and '\n' in contexts[0] else None
                if (('\n' not in literal and not wrapped_context) or value.count(literal)!=1
                        or any(c['value']==item['code'] for c in n['codes'])):
                    continue
                start=value.index(literal);stop=start+len(literal)
                left=max(value.rfind('\n',0,start),value.rfind(';',0,start))+1
                ends=[p for separator in ('\n',';') if (p:=value.find(separator,stop))>=0]
                fragment=value[left:min(ends) if ends else len(value)].strip()
                if '\n' not in literal and wrapped_context:fragment=wrapped_context.strip()
                for c,local in _coupon_scopes(fragment):
                    if c==item['code']:
                        for scope in coupon_scopes(c,local):code(c,path,scope,fragment=fragment)
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
    for path,clause,rate_clause,list_heading in (() if airline_rules else _clauses(raw,extra_covered_quotes=covered_quotes)):
        # This complete closed list, including its final cap, is already
        # projected from its own shared unit. Other fields remain independent.
        if point_options and path=='/benefit':continue
        scope=_scope(clause);recognized=rate_clause!=clause
        # Do not derive benefits from unassigned raw PDF table text.
        # The hotel's published heading labels only its owned benefit section;
        # common conditions and unrelated sources cannot inherit that label.
        heading_context=(owned_heading if path=='/benefit' else '') or list_heading
        rate_text=rate_clause.removeprefix(heading_context+': ') if heading_context else rate_clause
        spans=percent_spans(rate_text)
        rate_scopes,rate_owners=_component_context(rate_text)
        clause_scopes,clause_owners=(rate_scopes,rate_owners) if rate_text==clause else _component_context(clause)
        rates=[]
        if not d.get('pages'):
            declared_heading=_declared_discount_heading(raw,path,rate_text)
            reward_heading=_declared_reward_heading(raw,path)
            english_column=declared_heading and raw['origin'] in ('yandex_discounts_complete_all','VG_community_offers')
            rate_parser = _english_rates if ENGLISH_RATE_LABEL.search(rate_text) or english_column else normalize_rates
            rates = rate_parser(rate_text, heading_context=heading_context or declared_heading or reward_heading,with_spans=True)
            if _legacy_package_comparison_echo(raw,path,rate_text):rates=[]
            for m,value in _amount_matches(r'(?:up to\s+)?('+NUMERIC_TOKEN+r')\s*RUB\s+(?:off|discount)\b',rate_clause):
                rates.append({'kind':'discount','value':value,'unit':'RUB','qualifier':'up_to' if re.search('up to',m[0],re.I) else 'exact','evidence':clause})
            directions=percentage_rewards(rate_text,spans,heading_context=heading_context or reward_heading)
            covered={rate.get('_percent_index') for rate in rates if rate['unit']=='percent'}
            for index,item in directions.items():
                if index in covered:continue
                if item['kind'] not in ('redeem_rewards','earn_rewards'):continue
                span=spans[index];rate_scope=rate_scopes.get(('percent',index),{})
                reward=benefit(item['kind'],path,value=span['value'],value_min=span['min_value'],
                               unit='percent_of_order' if item['kind']=='redeem_rewards' else 'percent',
                               qualifier=span['qualifier'],reward_unit=item['reward_unit'],
                               scope=rate_scope,fragment=clause,method='clause_candidate')
                component_benefits[(path,clause,rate_owners.get(('percent',index)))].add(reward['id'])
                recognized=True
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
        represented,rate_fragments=_structured_occurrences(rates,clause,rate_text,structured_rates,rate_owners)
        for rate_index,rr in enumerate(rates):
            if _discount_percent_is_product_exception(rate_text,rr,spans):continue
            # Keep the same original quotation used by structured reconciliation
            # available to the remaining lexical context checks.
            rr['evidence']=clause
            if rate_index in represented:continue
            rate_key=(rr['unit'],rr.get('_percent_index') if rr['unit']=='percent' else rr.get('_amount_index'))
            rate_scope=rate_scopes.get(rate_key,scope if rr['unit']!='percent' else {})
            rate_scope={**rate_scope,**rr.get('_reward_scope',{})}
            if (raw['origin']=='loyalty_partner_benefits' and path=='/benefit'
                    and rr['kind']=='discount' and rr['unit']=='percent'):
                tier=re.fullmatch(r'\s*(Синий|Серебряный|Золотой)\s+',
                                  rate_text[:spans[rr['_percent_index']]['start']],re.I)
                if tier:rate_scope['member_tier']=tier[1]
            owner=(path,clause,rate_owners.get(rate_key))
            if rr.get('_reward_cap'):
                cap=condition(rr.get('_reward_cap_kind','benefit_cap'),path,value=rr['value'],unit=rr['unit'],qualifier='up_to',
                          basis_value=rr['basis_amount'],basis_unit=rr['basis_unit'],
                          scope=rate_scope,fragment=clause,method='clause_candidate')
                if not rr.get('_option_cap'):cap_owners.setdefault(cap['id'],set()).add(owner)
                recognized=True
                continue
            # Locally labelled discount/cashback rates already exclude payment
            # percentages. A separate commission must not erase those rewards.
            if (re.search(r'комисси|commission',clause,re.I)
                    and not (rr.get('evidence') and rr['kind'] in ('discount','cashback'))):continue
            # The shared parser has already excluded each owned monetary cap.
            # A cap elsewhere in this line cannot suppress this reward.
            kind=KIND.get(rr['kind'],rr['kind'])
            # A marketing "bonus" or a program name does not state the reward
            # unit. Require literal wording for payment/credit in points.
            if kind=='cashback':
                kind=_cashback_kind(rate_text,rr,spans)
            reward=benefit(kind,path,value=rr['value'],unit=rr['unit'],qualifier=rr.get('qualifier','unspecified'),value_min=rr.get('min_value'),
                    basis_value=rr.get('basis_amount'),basis_unit=rr.get('basis_unit'),
                    scope=rate_scope,fragment=rate_fragments.get(rate_index,clause),
                    method='clause_candidate',reward_unit='miles' if kind=='earn_miles' else 'points' if kind=='earn_points' else None)
            component_benefits[owner].add(reward['id'])
            recognized=True
        if not d.get('pages'):
            for index,span,kind in percentage_caps(rate_text,heading_context=heading_context or _declared_reward_heading(raw,path)):
                condition(kind,path,value=span['value'],unit='percent',qualifier='up_to',
                          scope=rate_scopes.get(('percent',index),{}),fragment=clause,method='clause_candidate')
                recognized=True
            for index,item in directions.items():
                if item['kind']!='earn_points':continue
                # A closed parenthesis can omit the already literal point
                # unit. Stop at this rate's next percentage or sentence;
                # dates and monetary quantities cannot match the bare cap.
                right=spans[index+1]['start'] if index+1<len(spans) else len(rate_text)
                tail=re.split(r'[.!?](?:\s|$)|[;\n]',rate_text[spans[index]['end']:right])[0]
                for cap_match in re.finditer(r'\(\s*(?:до|не\s+более)\s*('+NUMERIC_TOKEN+r')\s*\)',tail,re.I):
                    amount=literal_number(cap_match[1])
                    if amount is None:continue
                    cap=condition('benefit_cap',path,value=amount,unit='points',qualifier='up_to',
                                  scope=rate_scopes.get(('percent',index),{}),fragment=clause,method='clause_candidate')
                    cap_owners.setdefault(cap['id'],set()).add((path,clause,rate_owners.get(('percent',index))))
                    recognized=True
            for span in spans:
                if re.match(r'\s+от\s+(?:суммы\s+чека|стоимости\s+бронирования)\s+'
                            r'необходимо\s+оплатить\s+(?:банковской\s+картой|денежными\s+средствами)',
                            rate_text[span['end']:],re.I):
                    if not any(c['kind']=='minimum_cash_payment' and c['value']==span['value']
                               and c['evidence']['path'].startswith('/details/redemption_rules') for c in n['conditions']):
                        condition('minimum_cash_payment',path,value=span['value'],unit='percent_of_order',
                                  qualifier='at_least',fragment=clause,method='clause_candidate')
                    recognized=True
        if not d.get('pages'):
            previous_point_award_end=None
            point_amounts=list(reward_amounts(clause,'points',heading_context=list_heading))
            point_rates=[{'kind':'points','unit':'points','value':amount['value'],
                          'qualifier':'exact' if amount['qualifier']=='unspecified' else amount['qualifier'],
                          'min_value':amount['min_value'],'_amount_index':index,
                          **(reward_basis(clause,m.start(),m.end()) or {})}
                         for index,(m,amount) in enumerate(point_amounts)]
            represented_points,_=_structured_occurrences(point_rates,clause,clause,structured_rates,clause_owners)
            for index,(m,amount) in enumerate(point_amounts):
                if index in represented_points:continue
                value=amount['value']
                amount_scope=clause_scopes.get(('points',index),{})
                amount_scope={**amount_scope,**reward_formula_scope(clause,m.start(),m.end())}
                owner=(path,clause,clause_owners.get(('points',index)))
                role=reward_role(clause,m.start(),m.end())
                prefix=clause[:m.start()]
                basis=reward_basis(clause,m.start(),m.end())
                if basis is None:continue
                nominal_cap=nominal_reward_cap(clause,m.start())
                if nominal_cap:basis=nominal_reward_cap_basis(clause,m.start(),m.end())
                bracket_cap=re.search(r'\(\s*(?:до|не\s+более)\s*$',prefix,re.I)
                period_cap=(role not in ('denied','spend','reference') and amount['qualifier']=='up_to'
                            and (bracket_cap or (role=='unknown' and basis['basis_unit'] in ('month','day'))))
                if nominal_cap or period_cap or percent_point_ceiling(prefix):
                    cap=condition(nominal_reward_cap_kind(nominal_cap) if nominal_cap else 'benefit_cap',
                              path,value=value,unit='points',qualifier='up_to',
                              basis_value=basis['basis_amount'],basis_unit=basis['basis_unit'],
                              scope=amount_scope,fragment=clause,method='clause_candidate')
                    cap_owners.setdefault(cap['id'],set()).add(owner)
                    recognized=True
                    continue
                role=point_declaration_role(clause,m.start(),m.end(),role=role,basis=basis,
                    heading=list_heading,declared=bool(re.search(r'балл|бонус|начисление',
                                                    _declared_reward_heading(raw,path),re.I)),
                    previous_award_end=previous_point_award_end)
                if role in ('redemption_allowance','multiplier'):
                    reward=benefit('redeem_rewards' if role=='redemption_allowance' else 'reward_multiplier',
                        path,value=value,unit='points' if role=='redemption_allowance' else 'multiplier',
                        qualifier=amount['qualifier'],value_min=amount['min_value'],
                        scope=amount_scope,fragment=clause,method='clause_candidate',reward_unit='points')
                    component_benefits[owner].add(reward['id'])
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
                previous_point_award_end=m.end()
                recognized=True
            for m,value in _amount_matches(r'\bБонус\s+(?:(?:до|от)\s+)?('+NUMERIC_TOKEN+r')\s*'+MONEY+r'(?=\W|$)',clause):
                if (m.start()!=0 or benefit_denied(clause,m.start(),m.end(),amounts=benefit_mentions(clause))):continue
                qualifier='up_to' if re.search(r'\bдо\b',m[0],re.I) else 'at_least' if re.search(r'\bот\b',m[0],re.I) else 'exact'
                reward=benefit('earn_rewards',path,value=value,unit='RUB',qualifier=qualifier,
                               fragment=clause,method='clause_candidate')
                component_benefits[(path,clause,None)].add(reward['id'])
                recognized=True
        if not d.get('pages'):
            projected_gifts={(m.start(),m.end()) for m in gift_spans(clause)}
            for index,m in enumerate(gift_spans(clause,boundaries_only=True)):
                if ((m.start(),m.end()) not in projected_gifts or
                        benefit_denied(clause,m.start(),m.end(),amounts=benefit_mentions(clause),gift=True)):continue
                reward=benefit('gift',path,scope=clause_scopes.get(('gift',index),{}),fragment=clause,method='clause_candidate')
                component_benefits[(path,clause,clause_owners.get(('gift',index)))].add(reward['id'])
                recognized=True
        for m,value,extended,minimum_kind,minimum_qualifier,minimum_extra in _purchase_bounds(clause):
            minimum_scope,owners=_monetary_condition_context(clause,m.start(),m.end())
            minimum_scope={**minimum_scope,**minimum_extra}
            if extended and owners is None:
                # A separate local threshold sentence can own one explicitly
                # staged component in this same field. Equal rates/stages in
                # another field, or several local components, are insufficient.
                candidates={clause_owners[key] for key,component_scope in clause_scopes.items()
                            if minimum_scope and component_scope==minimum_scope}
                owners=candidates if len(candidates)==1 else set()
            if extended:
                minimum_qualifiers=_explicit_qualifiers(m[0])
                phrases=_component_phrases(clause)
                owners={owner for owner in owners
                        if _qualifiers_compatible(minimum_qualifiers,_explicit_qualifiers(phrases.get(owner,'')))}
            minimum=condition(minimum_kind,path,value=value,unit='RUB',qualifier=minimum_qualifier,scope=minimum_scope,fragment=clause,method='clause_candidate')
            if owners is not None:
                cap_owners.setdefault(minimum['id'],set()).update((path,clause,key) for key in owners)
                if _plain_repeated_purchase_rule(clause,m.start(),m.end()):plain_minima.add(minimum['id'])
            recognized=True
        for m,value in monetary_caps(clause):
            start=m.start('reward') if m['reward'] is not None else m.start()
            if benefit_denied(clause,start,m.end(),amounts=benefit_mentions(clause)):continue
            # Match positions, not values: first/repeat caps may have equal
            # amounts. Otherwise use only this cap's original sentence.
            cap_scope=None;owners=None
            for index,(amount,_,_) in enumerate(fixed_monetary_rewards(clause)):
                if amount.span('value')==m.span('value'):
                    key=('RUB',index)
                    cap_scope=clause_scopes.get(key,{})
                    owner=clause_owners.get(key)
                    if owner is not None and owner!=key:
                        cap_scope,owners=_monetary_condition_context(clause,m.start(),m.end())
                    break
            if cap_scope is None:
                cap_scope,owners=_monetary_condition_context(clause,m.start(),m.end())
            labelled_cap=_owned_accrual_cap_evidence(raw,path,clause)
            footnote=_owned_monetary_cap_footnote(raw,path,clause)
            kind='benefit_cap' if labelled_cap or footnote else _monetary_cap_kind(clause,m)
            cap_basis=_monetary_cap_basis(clause,m) if kind=='benefit_cap' else {}
            cap=condition(kind,path,value=value,unit='RUB',qualifier='up_to',scope=cap_scope,
                          **cap_basis,
                          fragment=labelled_cap or (footnote['evidence'] if footnote else clause),method='clause_candidate')
            if footnote:
                cap_owners.setdefault(cap['id'],set()).add(footnote['owner'])
            elif kind=='maximum_amount_reference':
                # A shared stage/evidence string is not an explicit reward link.
                cap_owners[cap['id']]=set()
            elif owners is not None:
                cap_owners.setdefault(cap['id'],set()).update((path,clause,key) for key in owners)
            recognized=True
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
            'fee_reference':r'комисси|стоимость.*подписк|автопродлен|commission|subscription fee',
        }
        for kind,pat in classifiers.items():
            if re.search(pat,clause,re.I):
                add('costs' if kind=='fee_reference' else 'conditions',kind,path,scope=scope,fragment=clause,method='clause_candidate');recognized=True
        promo=extract_promocodes(clause,[])
        for c,coupon_scope in _coupon_scopes(clause):
            if reconcile_promocode(c,_owned_coupon_texts(raw,clause)) is None:continue
            for local in coupon_scopes(c,coupon_scope):
                if not any(x['value']==c and (x['scope']==local
                           or x['evidence']['path'].startswith(('/codes/','/details/')))
                           for x in n['codes']):code(c,path,local,fragment=clause)
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
    _extend_repeated_purchase_links(n['benefits'],n['conditions'],cap_benefits,component_benefits,plain_minima)
    # A narrowed quotation still belongs to its original clause's shared rules.
    # Explicit monetary owners above continue to take precedence over this map.
    lexical_contexts=defaultdict(set)
    for (path,clause,_),benefits in component_benefits.items():
        lexical_contexts[(path,clause)].update(benefits)
    for b in n['benefits']:
        b['condition_ids']=[c['id'] for c in n['conditions']
                            if ((b['id'] in cap_benefits[c['id']]) if c['id'] in cap_benefits else
                                ({c['scope'].get('purchase_stage'),b['scope'].get('purchase_stage')}!={'first','repeat'}
                                 and (c['evidence']==b['evidence']
                                      or b['id'] in lexical_contexts.get((c['evidence']['path'],c['evidence']['text']),())
                                      or (c['scope'] and c['scope']==b['scope']))))]
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
