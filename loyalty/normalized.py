"""Literal, evidence-backed offer normalization; no inference of eligibility."""
from __future__ import annotations
import hashlib
import html
import json
import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit
from html_text import html_text
from model import clean_url
from promo_codes import extract_promocodes
from table_benefits import extract_table_benefits
from recovered_contract import SOURCES as RECOVERED_SOURCES, http_url, validate_recovered
from reward_context import (reward_role, benefit_denied, gift_spans, mileage_formula_end,
                            forward_reward_basis, purchase_requirement_denied, benefit_context_text)

VERSION = '2.9.6'
HOSTS = {
 'moskvich': ['moskvichmag.ru'], 'noname': ['nonameburo.com'],
 's7': ['marketplace.s7.ru'], 'ural': ['www.uralairlines.ru'],
 'rgo': ['rgo.ru'], 'mir': ['vamprivet.ru'], 'azimut': ['azimuthotels.com'],
 'rusimp': ['www.rusimp.su'], 'promomiles': ['promomiles.aeroflot.ru'],
 'sogaz_medi': ['medi.spb.ru'], 'ekp_medi': ['medi.spb.ru'],
 'ekp_neva': ['neva.travel'], 'mir_neva': ['neva.travel'],
 'key': ['traveltg-bot.netlify.app'],
}
# Checked-in public page configuration is trusted code, never scraped configuration.
for _key,_cfg in json.loads(Path(__file__).with_name('partner_pages.json').read_text(encoding='utf8')).items():
    HOSTS[_key]=[urlsplit(_cfg['url']).hostname]
KNOWN_RULES=json.loads(Path(__file__).with_name('known_rules.json').read_text(encoding='utf8'))
for _key,_cfg in KNOWN_RULES.items():
    HOSTS[_key]=[urlsplit(_cfg['url']).hostname]
HOSTS['utair_media']=['media.utair.ru']
HOSTS['utair']=['www.utair.ru']
HOSTS['nordwind']=['nordwindairlines.ru']
HOSTS['hse_alumni']=['alumni.hse.ru']
HOSTS['greatlist_alfa_only']=['greatlist.ru']
HOSTS['x5_partners_public']=['x5club.ru']
HOSTS['magnit_partners_public']=['magnit.ru']
HOSTS['gorod_public']=['gorodtroika.ru']
HOSTS['tsvetnoy_public']=['tsvetnoy.com']
HOSTS['flystation_public']=['flystation.net']
HOSTS['backit_public']=['backit.me']
HOSTS['club_avolta_public']=['www.clubavolta.com']
HOSTS['mantera_moments']=['lk.manteratravel.ru','manteracongress.ru','sochiparkhotel.ru']
HOSTS['alfa_only_partner_offers']=['web.alfabank.ru']
HOSTS['alfa_only_public_rules']=['alfabank.servicecdn.ru']
HOSTS['alfa_only_cashback_rules']=['alfabank.servicecdn.ru']
HOSTS['alfa_only_partner_pdf_offers']=['alfabank.servicecdn.ru']
HOSTS['ekp']=['ekp.spb.ru']
HOSTS['ekp_linked_rules']=['ekp.spb.ru','xn--b1abfnwkklk1gdn5a.xn--p1ai','mpclinic.ru','vamprivet.ru']
HOSTS['rzd']=['rzd-bonus.ru']
HOSTS['rzd_tour_conditions']=['rzdtour.com']
HOSTS['rzd_unicredit_reference']=['www.unicreditbank.ru']
HOSTS['rzd_unicredit_rules']=['www.unicreditbank.ru']
HOSTS['aeroflot']=['www.aeroflot.ru']
HOSTS['aeroflot_linked_rules']=['stoletov.ru','samson-pharma.ru','parkingsvo.ru','parking.svo.aero','parking.svo.su']
HOSTS['coral']=['coralbonus.ru']
HOSTS['coral_promo']=['coralbonus.ru']
HOSTS['coral_rule_documents']=['coralbonus.ru']
HOSTS['coral_pdf_documents']=['coralbonus.ru']
HOSTS['ekp_announcements']=['t.me']
HOSTS['rzd_announcements']=['t.me']
HOSTS['mir_announcements']=['t.me']
HOSTS['bspb_announcements']=['t.me']
HOSTS['alfa_only_announcements']=['t.me']
for _source in ('t2_bolshe','t2_mixx','t2_selection','t2_mixx_s','t2_powerbank'):
    HOSTS[_source]=['msk.t2.ru']
HOSTS['t2_bolshe'].append('spb.t2.ru')
HOSTS['t2_selection_public']=['msk.t2.ru','spb.t2.ru']
HOSTS['utair_tiers']=['media.utair.ru']
HOSTS['ural_tiers']=['www.uralairlines.ru']
for _sid,_spec in RECOVERED_SOURCES.items():
    HOSTS[_sid]=[urlsplit(_spec['url']).hostname]
BLOCKED = re.compile(r'access denied|just a moment|captcha|доступ к сайту временно ограничен|проверка безопасности|доступ запрещ[её]н', re.I)
NUMBER = r'\d+(?:[ .,\u00a0\u202f]\d{3})*(?:[.,]\d+)?'
# Consume a complete numeric token before validating it. Otherwise an invalid
# group such as "1 00%" can be rediscovered as the apparently valid suffix 00%.
NUMERIC_TOKEN = r'\d+(?:(?:[.,]|[^\S\r\n]+)\d+)*'
_HSPACE = r'[^\S\r\n]'
PERCENT_BOUND = rf'(?:до|от|не{_HSPACE}+(?:более|менее)(?:{_HSPACE}+чем)?)'
_PERCENT = re.compile(
    rf'\bот{_HSPACE}+(?P<word_lo>{NUMERIC_TOKEN}){_HSPACE}*%?{_HSPACE}+до{_HSPACE}+(?P<word_hi>{NUMERIC_TOKEN}){_HSPACE}*%'
    rf'|(?<![\d.])(?:(?P<lo>{NUMERIC_TOKEN}){_HSPACE}*%?{_HSPACE}*[–—-]{_HSPACE}*)?(?P<value>{NUMERIC_TOKEN}){_HSPACE}*%', re.I)
TYPES = {'discount': r'[сc]кидк', 'cashback': r'к[еэ]шб[еэ]к', 'miles':r'мил[ьяиюе]',
         'points':r'балл|бонус', 'gift':r'подар|комплимент', 'special_price':r'спеццен|специальн\w* цен'}


def text(value, *, markup: bool = True) -> str:
    """Normalize a source value, or already extracted text with markup=False.

    Source-facing callers retain HTML/entity decoding. Normalized offer fields
    are plain text, so their literal angle brackets and entities stay literal.
    """
    if value is None:
        return ''
    value = str(value)
    if markup:
        if '<' in value and re.search(r'</?[a-zA-Z][^>]*>', value):
            return html_text(value)
        value = html.unescape(value)
    return re.sub(r'[^\S\n]+', ' ', value).strip()


def canonical_url(value: str) -> str:
    # Keep a real page fragment; unlike tracking parameters it can identify a card.
    fragment = urlsplit(value).fragment
    if urlsplit(value).scheme == 'http':
        return http_url(value)
    return clean_url(value) + ('#' + fragment if fragment else '')


def number(value: str) -> str:
    raw = re.sub(r'[ \u00a0\u202f]', '', value)
    # A single separator remains decimal for compatibility. Multiple complete
    # groups, or grouping plus a different decimal mark, are unambiguous.
    for grouping, decimal_mark in (('.', ','), (',', '.')):
        group = re.escape(grouping)
        decimal = re.escape(decimal_mark)
        if (re.fullmatch(rf'\d{{1,3}}(?:{group}\d{{3}})+{decimal}\d+', raw)
                or re.fullmatch(rf'\d{{1,3}}(?:{group}\d{{3}}){{2,}}', raw)):
            raw = raw.replace(grouping, '')
            break
    raw = raw.replace(',', '.')
    decimal = Decimal(raw)
    result = format(decimal, 'f')
    return result.rstrip('0').rstrip('.') if '.' in result else result


def literal_number(value: str) -> str | None:
    """Canonical value of a complete numeric token, or None if malformed."""
    normalized = re.sub(r'[^\S\r\n]+', ' ', value)
    if not re.fullmatch(NUMBER, normalized):
        return None
    try:
        return number(normalized)
    except InvalidOperation:
        return None


def number_starts_here(value: str, start: int) -> bool:
    """Exclude numeric suffixes while retaining punctuation-separated list items."""
    prefix = value[:start]
    if re.search(r',[ \t\u00a0\u202f]+\Z', prefix):
        # A comma followed by space separates list values, not decimal digits.
        return True
    if re.search(r'\d[., \t\u00a0\u202f]*\Z', prefix):
        # A numbered list item is a boundary, not a malformed decimal prefix.
        return bool(re.search(r'(?:^|[:,;\n])[ \t]*\d+[.)][ \t]+\Z', prefix))
    return True


def percent_spans(value: str) -> list[dict]:
    """Valid literal percentage spans; positions refer to the unchanged input.

    Recognition does not assign a reward type or make an untyped percentage an
    entitlement. Invalid ranges and malformed groups are consumed as a whole.
    """
    result = []
    for match in _PERCENT.finditer(value):
        upper_key = 'word_hi' if match['word_hi'] is not None else 'value'
        lower_key = 'word_lo' if match['word_lo'] is not None else 'lo'
        first_key = lower_key if match[lower_key] is not None else upper_key
        if not number_starts_here(value, match.start(first_key)):
            continue
        upper = literal_number(match[upper_key])
        lower = literal_number(match[lower_key]) if match[lower_key] is not None else None
        if (upper is None or not 0 <= Decimal(upper) <= 100
                or (match[lower_key] is not None and
                    (lower is None or not 0 <= Decimal(lower) <= Decimal(upper)))):
            continue
        prefix = value[:match.start()]
        qualifier = ('range' if lower is not None else
                     'up_to' if re.search(rf'\b(?:до|не{_HSPACE}+более(?:{_HSPACE}+чем)?){_HSPACE}*$', prefix, re.I) else
                     'at_least' if re.search(rf'\b(?:от|не{_HSPACE}+менее(?:{_HSPACE}+чем)?){_HSPACE}*$', prefix, re.I) else 'exact')
        result.append({'start': match.start(), 'end': match.end(), 'value': upper,
                       'min_value': lower, 'qualifier': qualifier})
    return result


def reward_amounts(value: str, unit: str):
    """Validated reward spans, consuming both endpoints of a literal range."""
    word = r'мил[ьяиюе]\w*' if unit == 'miles' else r'(?:балл(?:ов|а)?|бонус(?:ов|а)?)'
    label = r'(?:(?:дополнительн\w*|бонусн\w*)\s+){0,2}' + word + r'\b'
    token = r'[−-]?' + NUMERIC_TOKEN
    pattern = (rf'(?:(?:\bот\s+(?P<word_lo>{token})\s*(?:{label}\s+)?до\s+)'
               rf'|(?P<lo>{token})\s*(?:{label}\s*)?[–—-]\s*)?'
               rf'(?P<value>{token})\s*(?P<reward_unit>{label})')
    for match in re.finditer(pattern, value, re.I):
        lower_key = 'word_lo' if match['word_lo'] is not None else 'lo'
        first_key = lower_key if match[lower_key] is not None else 'value'
        if not number_starts_here(value, match.start(first_key)):
            continue
        prefix = value[:match.start()]
        if (prefix and (prefix[-1].isalnum() or prefix[-1]=='_')):
            continue
        if re.search(rf'{NUMERIC_TOKEN}\s*(?:{label}\s*)?(?:[–—-]|\bдо)\s*$',prefix,re.I):
            continue
        if (match[lower_key] is not None
                and re.match(rf'\s*(?:[–—-]|\bдо)\s*{NUMERIC_TOKEN}',value[match.end():],re.I)):
            continue
        upper = literal_number(match['value'])
        lower = literal_number(match[lower_key]) if match[lower_key] is not None else None
        if upper is None or (match[lower_key] is not None
                             and (lower is None or Decimal(lower) > Decimal(upper))):
            continue
        qualifier = ('range' if lower is not None else
                     'up_to' if re.search(r'\b(?:до|не\s+более)\s*$', prefix, re.I) else
                     'at_least' if re.search(r'\b(?:от|не\s+менее)\s*$', prefix, re.I) else
                     'unspecified')
        yield match, {'value': upper, 'min_value': lower, 'qualifier': qualifier}


def reward_basis(clause: str, start: int, end: int):
    """Literal quantity denominator; None rejects an explicitly malformed base."""
    unit = r'(?:₽|руб\w*|RUB|(?:бонусн\w*\s+)?балл\w*|бонус(?:ов|а)?|дней|день|дня|месяц\w*)'
    # Consume an explicit numeric expression before validating it, including a
    # malformed/range base: it must not turn into a rate with no denominator.
    numeric = r'(?:от\s+)?[−+-]?\d[\w., \t\u00a0\u202f–—−-]*?'
    amount = rf'(?P<basis>{numeric})\s*(?P<unit>{unit})(?=\W|$)'
    forward=forward_reward_basis(clause,end,miles=bool(re.search(r'мил[ьяиюе]\w*$',clause[start:end],re.I)))
    match=forward if forward and forward['basis'] is not None else None
    if not match:
        prefix=re.sub(r'\bруб\.(?=\s)','руб ',clause[:start],flags=re.I)
        prefix=re.split(r'[.!?](?:\s|$)|[;\n]',prefix)[-1]
        # A textual currency in an earlier ratio is not part of this basis.
        reverse=list(re.finditer(r'\bза\s+кажды[еий]\b',prefix,re.I))
        if reverse:prefix=prefix[reverse[-1].start():]
        action=r'(?:начисл\w+|получ\w+|заработ\w+)'
        bridge=r'(?:(?!\b'+action+r'\b)[^0-9;.!?]){0,120}'
        match = re.search(r'\bза\s+кажды[еий]\s+(?:потраченн\w+\s+)?' + amount
                          + bridge + action + r'\s*$',prefix,re.I)
        if not match:
            # A monetary ratio can use a dash/colon instead of an earning verb.
            # Keep the separator adjacent to this reward, including its bound;
            # another amount, action or statement cannot supply the denominator.
            monetary=rf'(?P<basis>{numeric})\s*(?P<unit>₽|руб\w*|RUB)(?=\W|$)'
            match=re.search(r'\bза\s+кажды[еий]\s+(?:потраченн\w+\s+)?'+monetary
                            +r'\s*[–—:-]\s*(?:'+PERCENT_BOUND+r'\s+)?$',prefix,re.I)
    if match:
        base = literal_number(match['basis'])
        if base is None or Decimal(base)<=0:
            return None
        word = match['unit'].casefold()
        basis_unit = ('RUB' if re.match(r'₽|руб|rub', word) else
                      'month' if word.startswith('месяц') else
                      'day' if re.match(r'дн|день', word) else 'points')
        return {'basis_amount': base, 'basis_unit': basis_unit}
    if forward and forward['month']:
        return {'basis_amount': '1', 'basis_unit': 'month'}
    if forward and forward['day']:
        return {'basis_amount': '1', 'basis_unit': 'day'}
    return {'basis_amount': None, 'basis_unit': None}


def fixed_discount_amounts(value: str):
    """Validated fixed-price discount spans, shared with component ownership."""
    for match in re.finditer(rf'скидк\w*\s+(?P<qual>до\s+)?(?P<value>{NUMERIC_TOKEN})\s*(?:₽|руб\w*)',value,re.I):
        amount=literal_number(match['value'])
        if amount is not None:
            yield match, {'value':amount,'min_value':None,
                          'qualifier':'up_to' if match['qual'] else 'exact'}


def monetary_caps(value: str):
    """One bounded cap grammar for reward exclusion and literal conditions.

    Positions and explicit reward labels refer to the unchanged source. An
    unlabelled maximum still needs a semantic owner in the common model.
    """
    pattern=(r'\b(?:максимум|максимальн\w*|лимит|не\s+более(?:\s+чем)?)'
             r'(?:\s+(?:размер|сумм\w*|выплат\w*))?\s*[:—–-]?\s*'
             r'(?:(?P<reward>скидк\w*|к[еэ]шб[еэ]к\w*)\s*'
             r'(?:составля\w*\s*)?[:—–-]?\s*)?'
             rf'(?P<value>{NUMERIC_TOKEN})\s*(?:₽|руб(?:лей|ля|ль|\.)?|RUB)')
    for match in re.finditer(pattern,value,re.I):
        amount=literal_number(match['value'])
        if amount is not None and number_starts_here(value,match.start('value')):
            yield match,amount


def _postfix_rate_label(clause, end):
    for kind in ('discount','cashback','miles'):
        pattern=(r'\s*(?:\(\s*)?(?:постоянн\w*\s+)?'+TYPES[kind]+r'\w*\s*\)?')
        match=re.match(pattern,clause[end:],re.I)
        if match:return kind,end+match.end()
    return None,end


def benefit_mentions(clause):
    """Context-only spans for a shared denial over a literal benefit list."""
    spans=[(s['start'],_postfix_rate_label(clause,s['end'])[1]) for s in percent_spans(clause)]
    for unit in ('points','miles'):
        spans.extend((m.start(),m.end()) for m,_ in reward_amounts(clause,unit))
    spans.extend((m.start(),m.end()) for m,_ in fixed_discount_amounts(clause))
    spans.extend((m.start(),m.end()) for m in gift_spans(clause))
    return sorted(spans)


def normalize_rates(value: str, *, heading_context: str = '', with_spans: bool = False) -> list[dict]:
    """Only recognizable local rate phrases; context is mandatory for every value.
    Rates are NOT combinable without interpreting their evidence/conditions.
    Purchase thresholds, old prices and untyped percentages are not rates.
    """
    result = []
    percent_index = 0
    amount_indexes = {'miles':0,'RUB':0}
    heading_kinds = [k for k in ('discount','cashback') if re.search(TYPES[k],heading_context,re.I)]
    heading_kind = heading_kinds[0] if len(heading_kinds)==1 else None
    value=text(value, markup=False)
    for match in re.finditer(r'[^\n;]+',benefit_context_text(value)):
        clause = value[match.start():match.end()].strip()
        # In an explicit price band, "от 1000 руб. — 10%", the currency dot
        # is an abbreviation. Other sentence endings remain boundaries.
        # Keep character positions stable for the original label/rate spans.
        price_band = rf'\b(?:до|от|свыше|более|менее)\s+{NUMBER}\s*руб\.'
        ruble_band = rf'{price_band}(?=\s*[-–—:]\s*(?:(?:до|от)\s+)?(?:{_PERCENT.pattern}))'
        scoped_clause = re.sub(ruble_band, lambda match: match[0][:-1] + ' ', clause, flags=re.I)
        labels = [(m.start(), k) for k in ('discount','cashback') for m in re.finditer(TYPES[k],clause,re.I)]
        percentages=percent_spans(clause)
        polarity_spans=benefit_mentions(clause)
        for span in percentages:
            index = percent_index
            percent_index += 1
            start, end = span['start'], span['end']
            before = sorted((pos,k) for pos,k in labels if pos < start)
            if before:
                between = clause[before[-1][0]:start]
                # A reward label does not extend into another sentence.
                # Parallel scopes within one sentence still share their label.
                abbreviations = r'\b(?:физ|юр)\.(?=\s+лиц)|\bдоп\.(?=\s+\w)|\bв\s+т\.\s*ч\.(?=\s|$)'
                scope_text = re.sub(abbreviations, lambda match: match[0].replace('.', ''),
                                    scoped_clause[before[-1][0]:start], flags=re.I)
                if re.search(r'[.!?](?:\s|$)', scope_text):
                    before = []
            after,label_end = _postfix_rate_label(clause,end)
            payment = r'\b(?:предоплат\w*|оплат\w*|аванс\w*|НДС|налог\w*|комисси\w*|штраф\w*)\b'
            # A postfix reward label belongs to the percentage just before it;
            # it does not also label a later payment or tax percentage.
            payment_context = bool((before and ('%' in between
                                   or re.search(r'%\s*(?:\(\s*)?(?:постоянн\w*\s+)?$', clause[:before[-1][0]],re.I)
                                   or re.search(r'\b(?:при|на условиях|с уч[её]том)\b|\bза\s*$', between, re.I)))
                                   or (heading_kind and not before))
            price_tail = rf'(?:{price_band}\s*[-–—:]\s*)?'
            discounted_commission = ((before[-1][1] if before else heading_kind)=='discount'
                and re.search(rf'(?:^|,|\bи)\s*на\s+комисси(?:ю|и)\s*{price_tail}(?:(?:—|–|:|{PERCENT_BOUND})\s*)*$', clause[:start], re.I))
            # A fee/prepayment band does not become a reward because an earlier
            # discount exists. Ordinary purchase/payment thresholds still can.
            charge_band = (r'\b(?:предоплат\w*|аванс\w*|НДС|налог\w*|комисси\w*|штраф\w*)\b'
                           rf'[^%.,;\n]*?{price_band}\s*[-–—:]\s*(?:{PERCENT_BOUND}\s+)?$')
            if payment_context and not after and not discounted_commission and (
                    re.search(payment+rf'\s*(?:(?:в размере|составляет|—|–|:|{PERCENT_BOUND})\s*)*$', clause[:start], re.I)
                    or re.search(charge_band, clause[:start], re.I)
                    or re.match(r'\s*'+payment, clause[end:], re.I)):
                continue
            if not before and not after and not heading_kind:
                continue
            kind = after or (before[-1][1] if before else heading_kind)
            if benefit_denied(clause,start,label_end,amounts=polarity_spans):
                continue
            if kind=='miles' and reward_role(clause,start,label_end,amounts=polarity_spans) in ('denied','spend','reference'):
                continue
            r = {'kind':kind,'value':span['value'],'unit':'percent','qualifier':span['qualifier'],'basis_amount':None,'basis_unit':None,'evidence':clause}
            if span['min_value'] is not None:
                r['min_value'] = span['min_value']
            if with_spans:
                r['_percent_index'] = index
            result.append(r)
        for m,amount in reward_amounts(clause,'miles'):
            index=amount_indexes['miles'];amount_indexes['miles']+=1
            role=reward_role(clause,m.start(),m.end())
            formula_end=mileage_formula_end(clause,m.end())
            # An affirmative postfix after this denominator owns this reward,
            # even when the quantity-only prefix inherited a sibling's denial.
            if formula_end>m.end() and reward_role(clause,m.start(),formula_end)=='earn':
                role='earn'
            if (role in ('denied','spend','reference')
                    or benefit_denied(clause,m.start(),formula_end)):
                continue
            basis=reward_basis(clause,m.start(),m.end())
            if basis is None:
                continue
            rate={'kind':'miles','value':amount['value'],'unit':'miles',
                  'qualifier':'exact' if amount['qualifier']=='unspecified' else amount['qualifier'],
                  **basis,'evidence':clause}
            if amount['min_value'] is not None:rate['min_value']=amount['min_value']
            if with_spans:rate['_amount_index']=index
            bracket_cap=re.search(r'\(\s*(?:до|не\s+более)\s*$',clause[:m.start()],re.I)
            if (with_spans and amount['qualifier']=='up_to' and
                    (bracket_cap or (role=='unknown' and basis['basis_unit'] in ('month','day')))):
                rate['_reward_cap']=True
            result.append(rate)
        cap_spans={m.span('value') for m,_ in monetary_caps(clause)}
        for m,amount in fixed_discount_amounts(clause):
            index=amount_indexes['RUB'];amount_indexes['RUB']+=1
            # The bound labels this occurrence only. A later cap must not
            # erase another fixed discount, and a cap is not an earned amount.
            if m.span('value') in cap_spans:
                continue
            if benefit_denied(clause,m.start(),m.end(),amounts=polarity_spans):continue
            rate={'kind':'discount','value':amount['value'],'unit':'RUB','qualifier':amount['qualifier'],
                  'basis_amount':None,'basis_unit':None,'evidence':clause}
            if with_spans:rate['_amount_index']=index
            result.append(rate)
    unique = {json.dumps(r,ensure_ascii=False,sort_keys=True):r for r in result}
    return list(unique.values())



def lexical_conditions(value: str) -> list[dict]:
    """Recognized clauses only; no claim to exhaust all eligibility conditions."""
    result=[]
    for clause in re.split(r'\n|(?<=[.!?])\s+(?=[А-ЯA-Z])',text(value, markup=False)):
        clause=clause.strip()
        if not clause:continue
        def add(kind,**kwargs):result.append({'kind':kind,'evidence':clause,**kwargs})
        for match in re.finditer(rf'(?:заказ\w*|покупк\w*|чек\w*|бронировани\w*)\s+(?:на\s+сумму\s+)?от\s+({NUMERIC_TOKEN})\s*(?:₽|руб\w*\.?|RUB)',clause,re.I):
            amount = literal_number(match[1])
            if amount is not None and not purchase_requirement_denied(clause[:match.start()],clause[match.end():]):
                add('minimum_purchase',value=amount,unit='RUB',qualifier='at_least')
        for match,amount in monetary_caps(clause):
            if (match['reward'] is not None and not benefit_denied(
                    clause,match.start('reward'),match.end(),amounts=benefit_mentions(clause))):
                add('maximum_benefit',value=amount,unit='RUB',qualifier='up_to')
        if re.search(r'\b(?:перв\w*\s+(?:заказ|покупк|бронирован)|нов\w*\s+(?:клиент|пользоват))',clause,re.I):
            # This is a referenced audience, not proof that every other audience is excluded.
            add('first_purchase' if re.search(r'перв\w*\s+(?:заказ|покупк|бронирован)',clause,re.I) else 'new_customer_reference')
        if re.search(r'не\s+суммиру\w*|не\s+сочета\w*\s+с',clause,re.I):add('stacking_restriction')
    unique={json.dumps(x,ensure_ascii=False,sort_keys=True):x for x in result}
    return list(unique.values())


def content_hash(record: dict) -> str:
    content = {k:v for k,v in record.items() if k not in ('observed_at','content_sha256','run_id')}
    return hashlib.sha256(json.dumps(content,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def offer_rates(source_id, value):
    if source_id=='sacvoyage_loyalty':
        heading,separator,body=value.partition(': ')
        if separator:
            return normalize_rates(body,heading_context=heading)
    if source_id in ('ekp_ladoga_public', 'flystation_public'):
        from content_discovery import literal_rates
        return literal_rates(value)
    if source_id=='hse_alumni':
        from hse_alumni import hse_rates
        return hse_rates(value)
    if source_id=='alfa_only_partner_pdf_offers':
        from alfa_partner_rules import partner_rates
        return partner_rates(value)
    return normalize_rates(value)


def source_extraction_text(source_id, benefit, conditions, redemption, details):
    if source_id=='aeroflot':
        from aeroflot_import_catalog import semantic_fields_for_details
        source=semantic_fields_for_details(details or {})
        if source is not None:
            return '\n'.join(source[k] for k in ('benefit','conditions','redemption'))
    return '\n'.join((benefit,conditions,redemption))


def make_offer(source_id: str, native_id: str, program: str, partner_name: str | None,
               benefit: str, url: str, observed_at: str, *, conditions: str = '',
               redemption: str = '', title: str = '', category: str | None = None,
               link_kind: str = 'detail_page', locator: str = '', tables: list | None = None,
               details: dict | None = None, valid_from: str | None = None,
               valid_until: str | None = None, source_status: str = 'published',
               warnings: list[str] | None = None, record_kind: str = 'partner_offer') -> dict:
    if source_id not in HOSTS or urlsplit(url).hostname not in HOSTS[source_id]:
        raise ValueError('Source URL is outside the source allowlist')
    url = canonical_url(url)
    if not isinstance(native_id,str) or not native_id.strip() or len(native_id)>1000:
        raise ValueError('Invalid native source ID')
    if datetime.fromisoformat(observed_at).tzinfo is None:
        raise ValueError('Timestamp must include timezone')
    validity = 'not_stated'
    today = datetime.fromisoformat(observed_at).date()
    if valid_from:
        date.fromisoformat(valid_from)
    if valid_until:
        date.fromisoformat(valid_until)
        validity = 'expired_by_published_end' if date.fromisoformat(valid_until)<today else 'within_published_period'
    if valid_from and date.fromisoformat(valid_from)>today:
        validity = 'not_started'
    if valid_from and valid_until and valid_from>valid_until:
        raise ValueError('Reversed validity interval')
    benefit,conditions,redemption = (text(v, markup=False) for v in (benefit,conditions,redemption))
    if not benefit and not conditions:
        raise ValueError('An offer needs source evidence')
    if any(len(s)>40000 for s in (benefit,conditions,redemption)):
        raise ValueError('Oversized text; refusing to truncate conditions')
    all_text = source_extraction_text(source_id,benefit,conditions,redemption,details)
    if source_id=='hse_alumni':
        from hse_alumni import hse_codes
        promo=hse_codes(all_text,tables,preview=record_kind=='source_observation')
    else:
        promo = extract_promocodes(all_text, tables)
    codes = promo['codes']
    r = {'schema_version':2,'adapter_version':VERSION,
         'id':hashlib.sha256((source_id+'\n'+native_id).encode()).hexdigest(),
         'source_id':source_id,'native_id':native_id,'program':text(program, markup=False),
         'record_kind':record_kind,'partner_name':text(partner_name, markup=False) or None,
         'title':text(title, markup=False) or text(partner_name, markup=False) or native_id,
         'category':text(category, markup=False) or None,
         'benefit_text':benefit,'conditions_text':conditions,'redemption_text':redemption,
         'benefit_types':[k for k,p in TYPES.items() if re.search(p,benefit,re.I)],
         'rates':offer_rates(source_id,benefit),'promo_codes':codes,
         'valid_from':valid_from,'valid_until':valid_until,'validity_status':validity,
         'source_status':source_status,'source_url':url,
         'benefit_url':url if link_kind in ('detail_page','page_anchor') else None,
         'link_kind':link_kind,'locator':locator,'tables':tables or [],
         'details':{**(details or {}),'lexical_conditions':lexical_conditions(all_text),
                    'promo_code_evidence':promo['evidence'],'promo_code_delivery':promo['delivery'],
                    'promo_code_status':promo['status'],
                    'table_benefits':extract_table_benefits(tables or [])},
         'normalization_status':'source_fields_extracted',
         'warnings':list(warnings or []),'observed_at':observed_at}
    if promo['status']=='mentioned_not_extracted':
        r['warnings'].append('promo_code_mentioned_not_extracted')
    if not r['partner_name']:
        r['warnings'].append('partner_display_name_not_resolved')
    r['content_sha256'] = content_hash(r)
    validate_offer(r)
    return r


HOSTS['utair_rule_documents']=['ut0.ru','media.utair.ru']
HOSTS['konsierge_public']=['konsierge.com']

def validate_offer(r: dict) -> None:
    if r.get('schema_version')!=2 or r.get('adapter_version')!=VERSION:
        raise ValueError('Unexpected schema/adapter version')
    if r.get('source_id') not in HOSTS or urlsplit(r.get('source_url','')).hostname not in HOSTS[r['source_id']]:
        raise ValueError('Unexpected source URL')
    canonical_url(r['source_url'])
    validate_recovered(r)
    if r['source_id']=='loyals':
        post=r['details']['public_post']
        if (r['benefit_text'] != text(post['content']['rendered'])
                or r['title'] != text(post['title']['rendered'])
                or r['conditions_text'] != (r['benefit_text'] or r['title'])):
            raise ValueError('Loyals post text evidence mismatch')
    if r.get('id')!=hashlib.sha256((r['source_id']+'\n'+r['native_id']).encode()).hexdigest():
        raise ValueError('Stable ID mismatch')
    if r.get('content_sha256')!=content_hash(r):
        raise ValueError('Evidence hash mismatch')
    if r.get('rates')!=offer_rates(r['source_id'],r.get('benefit_text','')):
        raise ValueError('Rate evidence mismatch')
    all_text=source_extraction_text(r['source_id'],r.get('benefit_text',''),r.get('conditions_text',''),
                                    r.get('redemption_text',''),r.get('details',{}))
    if r['source_id']=='hse_alumni':
        from hse_alumni import hse_codes
        promo=hse_codes(all_text,r.get('tables',[]),preview=r['record_kind']=='source_observation')
    else:
        promo=extract_promocodes(all_text,r.get('tables',[]))
    if (r.get('promo_codes')!=promo['codes']
        or r.get('details',{}).get('promo_code_evidence')!=promo['evidence']
        or r.get('details',{}).get('promo_code_delivery')!=promo['delivery']
        or r.get('details',{}).get('promo_code_status')!=promo['status']):
        raise ValueError('Promo code evidence mismatch')
    if r.get('details',{}).get('table_benefits')!=extract_table_benefits(r.get('tables',[])):
        raise ValueError('Table benefit evidence mismatch')
    if r['details'].get('live_document_text'):
        from document_text import validate_document_record
        validate_document_record(r)
    if r['source_id']=='aeroflot_linked_rules':
        from aeroflot_linked_rules import validate_record
        validate_record(r)
    if r['source_id']=='ekp_linked_rules':
        from ekp_linked_rules import validate_record
        validate_record(r)
    if r['source_id']=='coral_rule_documents':
        from coral_linked_rules import validate_record
        validate_record(r)
    if r['source_id'] in ('coral','coral_promo'):
        from coral_catalog import validate_record
        validate_record(r)
    if r['source_id']=='aeroflot':
        if r['native_id'].startswith('airline:'):
            from aeroflot_airlines import validate_record
        else:
            from aeroflot_import_catalog import validate_record
        validate_record(r)
    if r['source_id']=='rzd':
        from rzd_import_catalog import validate_record
        validate_record(r)
    if r['source_id']=='ekp':
        from ekp_catalog import validate_record
        validate_record(r)
    if r['source_id']=='hse_alumni':
        from hse_alumni import validate_record
        validate_record(r)
    if r['source_id']=='konsierge_public':
        from konsierge_catalog import validate_record
        validate_record(r)
    if r['source_id']=='alfa_only_tsum':
        from tsum_alfa import validate_record
        validate_record(r)
    if r['source_id'] in ('backit_public','club_avolta_public','mantera_moments',
                         'x5_partners_public','magnit_partners_public','gorod_public','tsvetnoy_public','flystation_public'):
        from public_reward_projection import validate_record
        validate_record(r)
    if r['source_id']=='greatlist_alfa_only':
        from greatlist_alfa import validate_record
        validate_record(r)
    if r['source_id'] in ('alfa_only_public_rules','alfa_only_cashback_rules'):
        from alfa_public_rules import validate_public_record
        validate_public_record(r)
    if r['source_id']=='alfa_only_partner_pdf_offers':
        from alfa_partner_rules import validate_partner_record
        validate_partner_record(r)
    if r['source_id']=='nordwind':
        from nordwind_catalog import validate_catalog_record
        validate_catalog_record(r)
    if r['source_id']=='utair':
        from utair_support import validate_support_record
        validate_support_record(r)
    if r['source_id']=='utair_rule_documents':
        from utair_document_routes import validate_utair_document
        validate_utair_document(r)
    if r['source_id'] in KNOWN_RULES:
        cfg=KNOWN_RULES[r['source_id']]
        allowed_kinds=('program_rules','membership_plan') if r['source_id']=='smartavia_rules' else ('program_rules',)
        if (r['record_kind'] not in allowed_kinds or canonical_url(r['source_url'])!=canonical_url(cfg['url'])
            or r['details'].get('evidence_role')!='supplementary_rules_not_incremental_discount'):
            raise ValueError('Known rules cannot be relabelled as new verified partner offers')
    if r['source_id']=='t2_selection_public':
        if r['record_kind']!='tier_benefit' or r['link_kind']!='page_block' or r['source_status']!='public_preview_requires_login' or r['benefit_url'] is not None or urlsplit(r['source_url']).path!='/bolshe/selection':
            raise ValueError('Selection preview cannot certify private catalogue eligibility')
    if r['source_id'] in ('ekp_announcements','rzd_announcements','mir_announcements','bspb_announcements','alfa_only_announcements') or r['link_kind']=='source_post':
        channel={'ekp_announcements':'ekpcard','rzd_announcements':'fpcrussia','mir_announcements':'promomir','bspb_announcements':'mybspb','alfa_only_announcements':'aaa_only'}.get(r['source_id'])
        if r['link_kind']!='source_post' or not channel or not re.fullmatch('/'+channel+r'/[0-9]+',urlsplit(r['source_url']).path) or r['benefit_url'] is not None or r['record_kind']!='announcement' or r['source_status']!='announced_unverified':
            raise ValueError('Invalid announcement identity or evidence status')
    if r['link_kind']=='page_block' and r['benefit_url'] is not None:
        raise ValueError('Shared-page block is not a detail URL')
    if len(json.dumps(r,ensure_ascii=False))>90000:
        raise ValueError('Oversized normalized record')
