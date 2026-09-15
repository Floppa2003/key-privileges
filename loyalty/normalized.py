"""Literal, evidence-backed offer normalization; no inference of eligibility."""
from __future__ import annotations
import hashlib
import html
import json
import re
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from model import clean_url
from promo_codes import extract_promocodes
from table_benefits import extract_table_benefits
from recovered_contract import SOURCES as RECOVERED_SOURCES, http_url, validate_recovered

VERSION = '2.9.5'
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
HOSTS['coral']=['coralbonus.ru']
HOSTS['coral_promo']=['coralbonus.ru']
HOSTS['ekp_announcements']=['t.me']
HOSTS['rzd_announcements']=['t.me']
HOSTS['mir_announcements']=['t.me']
HOSTS['bspb_announcements']=['t.me']
for _source in ('t2_bolshe','t2_mixx','t2_selection','t2_mixx_s','t2_powerbank'):
    HOSTS[_source]=['msk.t2.ru']
HOSTS['t2_bolshe'].append('spb.t2.ru')
HOSTS['t2_selection_public']=['msk.t2.ru','spb.t2.ru']
HOSTS['utair_tiers']=['media.utair.ru']
HOSTS['ural_tiers']=['www.uralairlines.ru']
for _sid,_spec in RECOVERED_SOURCES.items():
    HOSTS[_sid]=[urlsplit(_spec['url']).hostname]
BLOCKED = re.compile(r'access denied|just a moment|captcha|доступ к сайту временно ограничен|проверка безопасности|доступ запрещ[её]н', re.I)
NUMBER = r'\d+(?:[ .,\u00a0]\d{3})*(?:[.,]\d+)?'
TYPES = {'discount': r'[сc]кидк', 'cashback': r'к[еэ]шб[еэ]к', 'miles':r'мил[ьяиюе]',
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
    if urlsplit(value).scheme == 'http':
        return http_url(value)
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
            after = next((k for k in ('discount','cashback') if re.match(r'\s*'+TYPES[k],clause[m.end():],re.I)),None)
            if re.match(r'\s*мил(?:ями|и|ь)\b',clause[m.end():],re.I):
                after='miles'
            if not before and not after:
                continue
            kind = after or before[-1][1]
            amount = number(m['value'])
            if not 0 <= Decimal(amount) <= 100:
                continue
            prefix = clause[max(0,m.start()-12):m.start()]
            qualifier = 'range' if m['lo'] else 'up_to' if re.search(r'до\s*$',prefix,re.I) else 'at_least' if re.search(r'от\s*$',prefix,re.I) else 'exact'
            r = {'kind':kind,'value':amount,'unit':'percent','qualifier':qualifier,'basis_amount':None,'basis_unit':None,'evidence':clause}
            if m['lo']:
                r['min_value'] = number(m['lo'])
            result.append(r)
        pattern = rf'(?P<qual>до\s+)?(?P<value>{NUMBER})\s*мил[ьяиюе]\w*(?:\s+(?:начисля\w+\s+)?за\s+(?:кажды[еий]\s+)?(?:потраченн\w+\s+)?(?P<basis>{NUMBER})\s*(?:₽|руб\w*))?'
        for m in re.finditer(pattern,clause,re.I):
            basis=m['basis']
            if not basis:
                preceding=re.search(rf'за\s+кажды[еий]\s+(?:потраченн\w+\s+)?({NUMBER})\s*(?:₽|руб\w*\.?)[^0-9;]{{0,120}}(?:начисля\w+|получаете|получите)\s*$',clause[:m.start()],re.I)
                if preceding:basis=preceding[1]
            result.append({'kind':'miles','value':number(m['value']),'unit':'miles','qualifier':'up_to' if m['qual'] else 'exact','basis_amount':number(basis) if basis else None,'basis_unit':'RUB' if basis else None,'evidence':clause})
        for m in re.finditer(rf'скидк\w*\s+(?P<qual>до\s+)?(?P<value>{NUMBER})\s*(?:₽|руб\w*)',clause,re.I):
            result.append({'kind':'discount','value':number(m['value']),'unit':'RUB','qualifier':'up_to' if m['qual'] else 'exact','basis_amount':None,'basis_unit':None,'evidence':clause})
    unique = {json.dumps(r,ensure_ascii=False,sort_keys=True):r for r in result}
    return list(unique.values())



def lexical_conditions(value: str) -> list[dict]:
    """Recognized clauses only; no claim to exhaust all eligibility conditions."""
    result=[]
    for clause in re.split(r'\n|(?<=[.!?])\s+(?=[А-ЯA-Z])',text(value)):
        clause=clause.strip()
        if not clause:continue
        def add(kind,**kwargs):result.append({'kind':kind,'evidence':clause,**kwargs})
        for match in re.finditer(rf'(?:заказ\w*|покупк\w*|чек\w*|бронировани\w*)\s+(?:на\s+сумму\s+)?от\s+({NUMBER})\s*(?:₽|руб\w*)',clause,re.I):
            add('minimum_purchase',value=number(match[1]),unit='RUB',qualifier='at_least')
        for match in re.finditer(rf'максимальн\w*\s+(?:размер\s+)?(?:скидк\w*|к[еэ]шб[еэ]к\w*)\s*(?:составля\w*\s*)?[:—–-]?\s*({NUMBER})\s*(?:₽|руб\w*)',clause,re.I):
            add('maximum_benefit',value=number(match[1]),unit='RUB',qualifier='up_to')
        if re.search(r'\b(?:перв\w*\s+(?:заказ|покупк|бронирован)|нов\w*\s+(?:клиент|пользоват))',clause,re.I):
            # This is a referenced audience, not proof that every other audience is excluded.
            add('first_purchase' if re.search(r'перв\w*\s+(?:заказ|покупк|бронирован)',clause,re.I) else 'new_customer_reference')
        if re.search(r'не\s+суммиру\w*|не\s+сочета\w*\s+с',clause,re.I):add('stacking_restriction')
    unique={json.dumps(x,ensure_ascii=False,sort_keys=True):x for x in result}
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
    promo = extract_promocodes(all_text, tables)
    codes = promo['codes']
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
    if r.get('rates')!=normalize_rates(r.get('benefit_text','')):
        raise ValueError('Rate evidence mismatch')
    promo=extract_promocodes('\n'.join(r.get(k,'') for k in ('benefit_text','conditions_text','redemption_text')),r.get('tables',[]))
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
    if r['source_id'] in ('coral','coral_promo'):
        from coral_catalog import validate_record
        validate_record(r)
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
    if r['source_id'] in ('ekp_announcements','rzd_announcements','mir_announcements','bspb_announcements') or r['link_kind']=='source_post':
        channel={'ekp_announcements':'ekpcard','rzd_announcements':'fpcrussia','mir_announcements':'promomir','bspb_announcements':'mybspb'}.get(r['source_id'])
        if r['link_kind']!='source_post' or not channel or not re.fullmatch('/'+channel+r'/[0-9]+',urlsplit(r['source_url']).path) or r['benefit_url'] is not None or r['record_kind']!='announcement' or r['source_status']!='announced_unverified':
            raise ValueError('Invalid announcement identity or evidence status')
    if r['link_kind']=='page_block' and r['benefit_url'] is not None:
        raise ValueError('Shared-page block is not a detail URL')
    if len(json.dumps(r,ensure_ascii=False))>90000:
        raise ValueError('Oversized normalized record')