"""Content-derived identities and literal block extraction, never title allowlists.

These helpers do not certify eligibility or infer a missing rate. Unclassified
blocks remain evidence instead of disappearing from an inventory.
"""
from __future__ import annotations
import hashlib
import re
from bs4 import BeautifulSoup, Comment
from normalized import normalize_rates


def compact(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def clean_dom(raw):
    soup = BeautifulSoup(str(raw), 'html.parser')
    for node in soup.select('script,style,noscript,form,input,textarea,nav,header,footer,svg,[hidden],[aria-hidden="true"]'):
        if node.parent is not None:
            node.decompose()
    for node in soup.find_all(string=lambda s: isinstance(s, Comment)):
        node.extract()
    return soup


def label_id(label, prefix='block'):
    label = compact(label)
    if not label:
        raise ValueError('content_missing_label')
    return prefix + ':' + hashlib.sha256(label.casefold().encode()).hexdigest()[:24]


def read_faq(nodes, heading, answer, plain):
    result = {}
    for node in nodes:
        titles, bodies = node.select(heading), node.select(answer)
        if len(titles) != 1 or len(bodies) != 1:
            raise ValueError('content_faq_structure')
        q, a = plain(titles[0]), plain(bodies[0])
        if not q or not a or q in result:
            raise ValueError('content_faq_empty_or_duplicate')
        result[q] = a
    validate_faq(result)
    return result


def validate_faq(faq):
    if (not isinstance(faq, dict) or not faq or len(faq) > 200
            or any(not isinstance(k, str) or not k.strip() or not isinstance(v, str) or not v.strip()
                   for k, v in faq.items())):
        raise ValueError('content_faq_evidence')


def faq_text(faq):
    validate_faq(faq)
    # Evidence dictionaries are canonicalized with sorted keys in Sheets.
    return '\n'.join(q + '\n' + faq[q] for q in sorted(faq))


def sentences(value):
    return [s.strip() for s in re.split(r'\n|(?<=[.!?])\s+(?=[А-ЯЁA-Z])', value) if s.strip()]


def literal_benefits(body):
    """Recognized reward clauses, scoped to their full original sentence.

An unrecognized sentence is still retained by the caller in conditions_text.
A quoted price or a non-stacking rule alone is not a positive reward.
"""
    claims, terms = [], []
    for clause in sentences(body):
        if re.match(r'^\d+(?:[.,]\d+)?\s+(?:минут\w*|час\w*|руб\w*)\s*[:—–-]', clause, re.I):
            continue
        if re.match(r'Цены со скидкой', clause, re.I):
            continue
        if re.fullmatch(r'(?:Акции|Скидки)\s+не\s+(?:суммируются|предоставляются)\.?', clause, re.I):
            continue
        # Accept amounts syntactically attached to a reward word. A later
        # prepayment percentage in the same sentence is not another discount.
        amount=r'(?:\d+(?:[.,]\d+)?\s*[–—-]\s*)?\d+(?:[.,]\d+)?\s*(?:%|₽|руб\.?\w*)'
        word=r'(?:скидк[а-яё]*|к[еэ]шб[еэ]к[а-яё]*)'
        forward=word+r'\s*(?:(?:в размере|составляет|—|–|-|до|от)\s*)*'+amount
        reverse=amount+r'\s+'+word
        phrases=[m.group() for pattern in (forward,reverse) for m in re.finditer(pattern,clause,re.I)]
        rates=[]
        for phrase in phrases:
            for rate in normalize_rates(phrase):
                if rate['kind'] in ('discount','cashback') and rate not in rates:rates.append(rate)
        if re.search(r'(?:скидк\w*\s+не\s+(?:предостав|действ)|без\s+скид)', clause, re.I):
            rates = []
        local = {'source_clause': clause}
        for pattern, key in ((r'за\s+(\d+)\s+дн', 'advance_days'),
                             (r'на тарифы\s+(\d+[–—-]\d+)\s+минут', 'flight_minutes')):
            match = re.search(pattern, clause, re.I)
            if match:
                local[key] = match[1]
        match = re.search(r'от\s+(\d+)\s+до\s+(\d+)\s+минут', clause, re.I)
        if match:
            local['flight_minutes'] = match[1] + '–' + match[2]
        for rate in rates:
            term = {k: rate[k] for k in ('kind', 'value', 'unit', 'qualifier')}
            if rate.get('min_value') is not None:
                term['value_min'] = rate['min_value']
            terms.append(dict(term, fragment=clause, scope=local))
        gift = re.search(r'\b(?:дарим|подарим|в\s+подарок|бесплатн\w*|комплимент\w*)\b', clause, re.I)
        if re.search(r'не\s+(?:дарим|подарим|бесплатн)|бесплатн\w*\s+\w*\s*(?:нет|не\s+предостав)',clause,re.I):gift=None
        # An imperative to buy a gift is not a promised gift from the merchant.
        if gift and not rates:
            terms.append(dict(kind='partner_privilege', fragment=clause, scope=local))
        if rates or gift:
            claims.append(clause)
    return list(dict.fromkeys(claims)), terms


def literal_rates(body):
    """Canonical rates for the same reward phrases used by literal_benefits."""
    _, terms = literal_benefits(body)
    result = []
    for term in terms:
        if term['kind'] not in ('discount', 'cashback'):
            continue
        rate = {k: term[k] for k in ('kind', 'value', 'unit', 'qualifier')}
        rate.update(basis_amount=None, basis_unit=None, evidence=term['fragment'])
        if 'value_min' in term:
            rate['min_value'] = term['value_min']
        if rate not in result:
            result.append(rate)
    return result


def action_clauses(body):
    return '\n'.join(s for s in sentences(body) if re.search(
        r'чтобы\s+воспольз|(?:необходимо|нужно)\s+(?:запис|предъяв|указ|оформ|брониров|зарегистр)|'
        r'\b(?:запишитесь|записаться|предъявите|укажите|перейдите|введите|оформите|забронируйте)\b', s, re.I))
