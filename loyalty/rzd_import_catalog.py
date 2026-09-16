"""Map only current public RZD pages returned by Google IMPORT functions.

The evidence is parsed Google cells, not original HTTP bytes or an origin-age
assertion. URLs come from the source's own catalogue; no source account is used.
"""
from __future__ import annotations
import hashlib
import json
import math
import re
from datetime import datetime
from urllib.parse import parse_qsl,urljoin,urlsplit
from normalized import make_offer,text

HOME='https://rzd-bonus.ru/'
ROOT=HOME+'partners/'
ROBOTS=HOME+'robots.txt'
ORIGINAL='https://www.rzd-bonus.ru/?accessible=true'
METHOD='google_import_public_text_v1'
XPATH={
 'home':"//title | //a[contains(@href,'/partners/')]/@href",
 'catalog':"//h1 | //div[contains(concat(' ',normalize-space(@class),' '),' partners__frame ')]//a/@href",
 'detail':"//h1 | //h1/following-sibling::text()[normalize-space()] | //h1/following-sibling::*//text()[normalize-space() and not(ancestor::script) and not(ancestor::style) and not(ancestor::form) and not(ancestor::noscript)]",
}
WARNINGS=['google_import_not_original_http_response','origin_cache_age_not_exposed',
          'user_eligibility_not_verified','linked_and_image_only_rules_not_read',
          'publication_dates_not_inferred_as_offer_validity']
RESTRICTION=re.compile(r'access denied|captcha|проверка безопасности|доступ.{0,40}ограничен',re.I)
INSTRUCTION=re.compile(r'ignore (?:all |the )?previous instructions|export private|reveal (?:your )?system prompt|игнорируй предыдущие инструкции',re.I)
REWARD=re.compile(r'скидк|балл|бонус|к[еэ]шб[еэ]к|промокод|подар',re.I)


def digest(obj):
    return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def instant(value):
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None:raise ValueError('rzd_time_zone_missing')
    return result


def checked_url(value):
    if not isinstance(value,str) or len(value)>500:raise ValueError('rzd_url_outside_scope')
    u=urlsplit(value)
    if (u.scheme!='https' or u.netloc!='rzd-bonus.ru' or u.fragment or '%' in u.path
            or '..' in u.path or '\\' in value or any(c.isspace() for c in value)):
        raise ValueError('rzd_url_outside_scope')
    if u.path in ('/','/robots.txt') and not u.query:return value
    if u.path=='/partners/':
        if not u.query:return value
        if re.fullmatch(r'PAGEN_[1-9][0-9]?=[1-9][0-9]?',u.query) and int(u.query.split('=')[1])<=50:return value
    if not u.query and (re.fullmatch(r'/partners/[0-9]{1,12}/',u.path) or re.fullmatch(r'/promo/[a-z0-9_-]{1,220}/',u.path)):
        return value
    raise ValueError('rzd_url_outside_scope')


def formula(url,kind):
    checked_url(url)
    if kind=='robots':
        if url!=ROBOTS:raise ValueError('rzd_wrong_policy_url')
        return f'=IMPORTDATA("{url}")'
    if kind not in XPATH:raise ValueError('rzd_import_kind_unknown')
    if ((kind=='home' and url!=HOME) or (kind=='catalog' and urlsplit(url).path!='/partners/')
            or (kind=='detail' and (urlsplit(url).query or not re.fullmatch(r'/partners/[0-9]+/|/promo/[a-z0-9_-]+/',urlsplit(url).path)))):
        raise ValueError('rzd_import_kind_url_mismatch')
    return f'=IMPORTXML("{url}";"{XPATH[kind]}")'


def cell_atom(cell):
    value=cell.get('effectiveValue',{})
    if 'errorValue' in value:raise ValueError('rzd_import_error_cell')
    if not value:return None
    if set(value)=={'stringValue'}:
        s=value['stringValue']
        if not isinstance(s,str) or len(s)>40000:raise ValueError('rzd_import_cell_bound')
        return {'text':s,'kind':'string'} if s else None
    # A date may be exposed as a Google serial. Preserve its displayed form and
    # original typed metadata, but never treat it as the offer's validity date.
    fmt=cell.get('effectiveFormat',{}).get('numberFormat',{})
    number=value.get('numberValue');display=cell.get('formattedValue','')
    if (set(value)=={'numberValue'} and type(number) in (int,float) and math.isfinite(number)
        and set(fmt)=={'type','pattern'} and 0<=number<=100000 and fmt.get('type') in ('DATE','DATE_TIME')
        and isinstance(fmt.get('pattern'),str) and len(fmt['pattern'])<=80
        and isinstance(display,str) and re.fullmatch(r'[0-9./: T+-]{6,40}',display)):
        return {'text':display,'kind':'google_date','number':number,'format':fmt}
    # Especially do not silently turn a numeric coupon with leading zeros into
    # another literal code, or infer a percentage from an unformatted decimal.
    raise ValueError('rzd_non_date_type_coercion')


def checked_observation(obs):
    keys={'url','kind','requested_at','calculated_at','cells','cells_sha256','formula_sha256'}
    if not isinstance(obs,dict) or set(obs)!=keys:raise ValueError('rzd_observation_contract')
    f=formula(obs['url'],obs['kind'])
    if obs['formula_sha256']!=digest(f) or obs['cells_sha256']!=digest(obs['cells']):raise ValueError('rzd_observation_hash')
    start,end=instant(obs['requested_at']),instant(obs['calculated_at'])
    if not 0<=(end-start).total_seconds()<=300:raise ValueError('rzd_observation_time')
    cells=obs['cells']
    if not isinstance(cells,list) or not 1<=len(cells)<2000 or len(json.dumps(cells,ensure_ascii=False))>700000:
        raise ValueError('rzd_observation_size')
    for c in cells:
        if not isinstance(c,dict) or not isinstance(c.get('text'),str) or len(c['text'])>40000:raise ValueError('rzd_atom_invalid')
        if c.get('kind')=='string':
            if set(c)!={'text','kind'}:raise ValueError('rzd_atom_invalid')
        elif c.get('kind')=='google_date':
            if set(c)!={'text','kind','number','format'}:raise ValueError('rzd_atom_invalid')
            if cell_atom({'effectiveValue':{'numberValue':c['number']},'formattedValue':c['text'],
                         'effectiveFormat':{'numberFormat':c['format']}})!=c:raise ValueError('rzd_atom_invalid')
        else:raise ValueError('rzd_atom_invalid')
    return cells


def catalog(obs):
    cells=checked_observation(obs)
    if obs['kind']!='catalog' or cells[0]['kind']!='string' or not re.fullmatch('Партн[её]ры',cells[0]['text'].strip(),re.I):
        raise ValueError('rzd_catalogue_identity')
    out={'details':[],'pages':[],'external_links':0,'combined_pagination_links':0,'excluded_navigation_links':0}
    current=dict(parse_qsl(urlsplit(obs['url']).query))
    for cell in cells[1:]:
        if cell['kind']!='string':raise ValueError('rzd_link_type')
        raw=cell['text'].strip()
        if not raw:continue
        url=urljoin(HOME,raw);u=urlsplit(url)
        if u.hostname!='rzd-bonus.ru':out['external_links']+=1;continue
        if u.path=='/partners/' and u.query:
            pairs=parse_qsl(u.query,keep_blank_values=True)
            if len(pairs)>1 and len(dict(pairs))==len(pairs) and all(re.fullmatch(r'PAGEN_[1-9][0-9]?',k) and v.isdigit() and 1<=int(v)<=50 for k,v in pairs):
                # Each source-owned category has a separate Bitrix pager. The
                # root links seed every one; don't crawl their Cartesian product.
                if not current or not all(dict(pairs).get(k)==v for k,v in current.items()):
                    raise ValueError('rzd_unowned_combined_pagination')
                out['combined_pagination_links']+=1;continue
        try:checked_url(url)
        except ValueError:
            out['excluded_navigation_links']+=1;continue
        if u.path=='/partners/':
            if u.query and url not in out['pages']:out['pages'].append(url)
        elif re.fullmatch(r'/partners/[0-9]+/|/promo/[a-z0-9_-]+/',u.path):
            if url not in out['details']:out['details'].append(url)
        else:out['excluded_navigation_links']+=1
    if not out['details']:raise ValueError('rzd_no_owned_cards')
    return out


def source_fields(obs):
    cells=checked_observation(obs)
    if obs['kind']!='detail' or cells[0]['kind']!='string':raise ValueError('rzd_detail_identity')
    title=text(cells[0]['text']);body=text('\n'.join(c['text'] for c in cells))
    if not 2<=len(title)<=300 or len(body)<60 or len(body)>35000 or len(cells)<2:raise ValueError('rzd_detail_empty_or_bound')
    if RESTRICTION.search(title+' '+body[:600]):raise ValueError('rzd_restriction_document')
    if INSTRUCTION.search(body):raise ValueError('rzd_source_instruction_text')
    partner=title if re.fullmatch('/partners/[0-9]+/',urlsplit(obs['url']).path) else None
    benefit=body if REWARD.search(body) else ''
    return title,body,partner,benefit


def detail(obs,observed_at):
    title,body,partner,benefit=source_fields(obs)
    warnings=list(WARNINGS)
    if any(c['kind']=='google_date' for c in obs['cells']):warnings.append('google_import_date_format_not_original_lexeme')
    return make_offer('rzd',urlsplit(obs['url']).path,'РЖД Бонус',partner,benefit,obs['url'],observed_at,
        title=title,conditions=body,record_kind='partner_offer' if benefit else 'source_observation',
        source_status='public_google_import_text',locator=XPATH['detail'],warnings=warnings,
        details={'retrieval_method':METHOD,'import_observation':obs,'origin_http_status':None,
          'origin_response_bytes_retained':False,'origin_cache_age_verified':False,
          'formula_refresh_requested':True,'account_used':False,'coupon_issued':False,
          'linked_terms_read':False,'full_eligibility_verified':False,'catalogue_root':ROOT,
          'dates_preserved_as_google_display_not_inferred_validity':True})


def validate_record(r):
    d=r.get('details',{});obs=d.get('import_observation')
    title,body,partner,benefit=source_fields(obs)
    if (r['source_id']!='rzd' or r['source_url']!=obs['url'] or r['native_id']!=urlsplit(obs['url']).path
        or r['title']!=title or r['conditions_text']!=body or r['partner_name']!=partner or r['benefit_text']!=benefit
        or r['source_status']!='public_google_import_text' or r['link_kind']!='detail_page'
        or r['benefit_url']!=obs['url'] or r['locator']!=XPATH['detail']
        or r['record_kind']!=('partner_offer' if benefit else 'source_observation')
        or r['valid_from'] is not None or r['valid_until'] is not None or not set(WARNINGS)<=set(r['warnings'])):
        raise ValueError('rzd_record_source_binding')
    if (d.get('retrieval_method')!=METHOD or d.get('origin_http_status') is not None
        or any(d.get(k) is not False for k in ('account_used','coupon_issued','origin_response_bytes_retained','origin_cache_age_verified','linked_terms_read','full_eligibility_verified'))):
        raise ValueError('rzd_evidence_promotion')
    if any(c['kind']=='google_date' for c in obs['cells']) and 'google_import_date_format_not_original_lexeme' not in r['warnings']:
        raise ValueError('rzd_date_coercion_hidden')
