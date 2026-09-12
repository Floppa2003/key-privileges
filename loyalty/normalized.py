"""Literal, evidence-backed offer normalization; no inference of eligibility."""
from __future__ import annotations
import hashlib
import html
import json
import re
from datetime import datetime, date
from decimal import Decimal
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from model import clean_url

VERSION = '2.0.0'
HOSTS = {
 'moskvich': ['moskvichmag.ru'], 'noname': ['nonameburo.com'],
 's7': ['marketplace.s7.ru'], 'ural': ['www.uralairlines.ru'],
 'rgo': ['rgo.ru'], 'mir': ['vamprivet.ru'], 'azimut': ['azimuthotels.com'],
 'rusimp': ['www.rusimp.su'], 'promomiles': ['promomiles.aeroflot.ru'],
 'sogaz_medi': ['medi.spb.ru'], 'ekp_medi': ['medi.spb.ru'],
 'ekp_neva': ['neva.travel'], 'mir_neva': ['neva.travel'],
 'key': ['traveltg-bot.netlify.app'],
}
BLOCKED = re.compile(r'access denied|just a moment|captcha|доступ к сайту временно ограничен|проверка безопасности|доступ запрещ[её]н', re.I)
NUMBER = r'\d+(?:[ .,\u00a0]\d{3})*(?:[.,]\d+)?'
TYPES = {'discount': r'скидк', 'cashback': r'к[еэ]шб[еэ]к', 'miles':r'мил[ьяиюе]',
         'points':r'балл|бонус', 'gift':r'подар|комплимент', 'special_price':r'спеццен|специальн\w* цен'}


def text(value) -> str:
    if value is None:
        return ''
    value = str(value)
    if '<' in value and re.search(r'</?[a-zA-Z][^>]*>', value):
        soup = BeautifulSoup(value, 'html.parser')
        for el in soup(['script','style']):
            el.decompose()
        value = soup.get_text(' ', strip=True)
    return re.sub(r'[^\S\n]+', ' ', html.unescape(value)).strip()


def canonical_url(value: str) -> str:
    # Keep a real page fragment; unlike tracking parameters it can identify a card.
    fragment = urlsplit(value).fragment
    return clean_url(value) + ('#' + fragment if fragment else '')


def number(value: str) -> str:
    raw = re.sub(r'[ \u00a0\u202f]', '', value).replace(',', '.')
    decimal = Decimal(raw)
    result = format(decimal, 'f')
    return result.rstrip('0').rstrip('.') if '.' in result else result


def normalize_rates(value: str) -> list[dict]:
    """Only recognizable local rate phrases; context is mandatory for every value.
    Rates are NOT combinable without interpreting their evidence/conditions.
    Purchase thresholds, old prices and untyped percentages are not rates.
    """
    result = []
    for clause in re.split(r'[\n;]', text(value)):
        clause = clause.strip()
        labels = [(m.start(), k) for k in ('discount','cashback') for m in re.finditer(TYPES[k],clause,re.I)]
        for m in re.finditer(r'(?:(?P<lo>\d+(?:[.,]\d+)?)\s*[–—-]\s*)?(?P<value>\d+(?:[.,]\d+)?)\s*%', clause):
            before = sorted((pos,k) for pos,k in labels if pos < m.start())
            if not before:
                continue
            kind = before[-1][1]
            amount = number(m['value'])
            if not 0 <= Decimal(amount) <= 100:
                continue
            prefix = clause[max(0,m.start()-12):m.start()]
            qualifier = 'range' if m['lo'] else 'up_to' if re.search(r'до\s*$',prefix,re.I) else 'at_least' if re.search(r'от\s*$',prefix,re.I) else 'exact'
            r = {'kind':kind,'value':amount,'unit':'percent','qualifier':qualifier,'basis_amount':None,'basis_unit':None,'evidence':clause}
            if m['lo']:
                r['min_value'] = number(m['lo'])
            result.append(r)
        pattern = rf'(?P<qual>до\s+)?(?P<value>{NUMBER})\s*мил[ьяиюе]\w*(?:\s+за\s+(?:кажды[еий]\s+)?(?P<basis>{NUMBER})\s*(?:₽|руб\w*))?'
        for m in re.finditer(pattern,clause,re.I):
            result.append({'kind':'miles','value':number(m['value']),'unit':'miles','qualifier':'up_to' if m['qual'] else 'exact','basis_amount':number(m['basis']) if m['basis'] else None,'basis_unit':'RUB' if m['basis'] else None,'evidence':clause})
        for m in re.finditer(rf'скидк\w*\s+(?P<qual>до\s+)?(?P<value>{NUMBER})\s*(?:₽|руб\w*)',clause,re.I):
            result.append({'kind':'discount','value':number(m['value']),'unit':'RUB','qualifier':'up_to' if m['qual'] else 'exact','basis_amount':None,'basis_unit':None,'evidence':clause})
    unique = {json.dumps(r,ensure_ascii=False,sort_keys=True):r for r in result}
    return list(unique.values())


def content_hash(record: dict) -> str:
    content = {k:v for k,v in record.items() if k not in ('observed_at','content_sha256','run_id')}
    return hashlib.sha256(json.dumps(content,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


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
    benefit,conditions,redemption = map(text,(benefit,conditions,redemption))
    if not benefit and not conditions:
        raise ValueError('An offer needs source evidence')
    if any(len(s)>40000 for s in (benefit,conditions,redemption)):
        raise ValueError('Oversized text; refusing to truncate conditions')
    all_text = '\n'.join((benefit,conditions,redemption))
    codes = []
    pattern = r'промокод(?:у|ом|а)?\s*[:—–-]?\s*(?:[«"“]([^»"”\n]{2,60})[»"”]|([A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9_.-]{1,49})(?=\W|$))'
    for m in re.finditer(pattern,all_text,re.I):
        c=m[1] or m[2]
        if m[2]:
            tail=re.match(r'(?: +[A-ZА-ЯЁ0-9][A-ZА-ЯЁ0-9_.-]{1,30}){1,3}(?=\W|$)',all_text[m.end():])
            if tail:
                c+=tail[0]
        if (c.isupper() or re.search(r'[A-Z0-9_.-]',c)) and c not in codes:
            codes.append(c)
    r = {'schema_version':2,'adapter_version':VERSION,
         'id':hashlib.sha256((source_id+'\n'+native_id).encode()).hexdigest(),
         'source_id':source_id,'native_id':native_id,'program':text(program),
         'record_kind':record_kind,'partner_name':text(partner_name) or None,
         'title':text(title) or text(partner_name) or native_id,'category':text(category) or None,
         'benefit_text':benefit,'conditions_text':conditions,'redemption_text':redemption,
         'benefit_types':[k for k,p in TYPES.items() if re.search(p,benefit,re.I)],
         'rates':normalize_rates(benefit),'promo_codes':codes,
         'valid_from':valid_from,'valid_until':valid_until,'validity_status':validity,
         'source_status':source_status,'source_url':url,
         'benefit_url':url if link_kind in ('detail_page','page_anchor') else None,
         'link_kind':link_kind,'locator':locator,'tables':tables or [],'details':details or {},
         'normalization_status':'source_fields_extracted',
         'warnings':warnings or [],'observed_at':observed_at}
    if not r['partner_name']:
        r['warnings'].append('partner_display_name_not_resolved')
    r['content_sha256'] = content_hash(r)
    validate_offer(r)
    return r


def validate_offer(r: dict) -> None:
    if r.get('schema_version')!=2 or r.get('adapter_version')!=VERSION:
        raise ValueError('Unexpected schema/adapter version')
    if r.get('source_id') not in HOSTS or urlsplit(r.get('source_url','')).hostname not in HOSTS[r['source_id']]:
        raise ValueError('Unexpected source URL')
    canonical_url(r['source_url'])
    if r.get('id')!=hashlib.sha256((r['source_id']+'\n'+r['native_id']).encode()).hexdigest():
        raise ValueError('Stable ID mismatch')
    if r.get('content_sha256')!=content_hash(r):
        raise ValueError('Evidence hash mismatch')
    if r.get('rates')!=normalize_rates(r.get('benefit_text','')):
        raise ValueError('Rate evidence mismatch')
    if r['link_kind']=='page_block' and r['benefit_url'] is not None:
        raise ValueError('Shared-page block is not a detail URL')
    if len(json.dumps(r,ensure_ascii=False))>90000:
        raise ValueError('Oversized normalized record')
