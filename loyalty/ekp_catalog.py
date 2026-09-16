"""Source-owned public EKP API fields; gated terms are never retained.

The anonymous POST and its filter/field meanings were verified against the
normal website's visible catalogue and four owned expanded cards. No account,
private coupon, inferred numeric teaser or fixed partner inventory is used.
"""
from __future__ import annotations
import hashlib
import json
import re
from urllib.parse import urlsplit
from bs4 import BeautifulSoup

ROOT='https://ekp.spb.ru/capabilities/loyalty/'
API='https://ekp.spb.ru/api/portal/loyalty/partners'
POLICY='https://ekp.spb.ru/robots.txt'
REGION='98'  # Literal filter emitted by the UI labelled "Все регионы"; not a geographic claim.
PAGE_SIZE=120  # An actual selectable page size in the observed public catalogue.
LOGIN='Для просмотра подробной информации о программе лояльности авторизуйтесь'
ROW_KEYS={'id','name','active','description_authorized','categories','text','loyaltyDescription','discountScheme'}


def sha(value):
    data=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    return hashlib.sha256(data).hexdigest()


def query(offset):
    if type(offset) is not int or offset<0 or offset%PAGE_SIZE or offset>5000:
        raise ValueError('ekp_invalid_offset')
    return {'pagination':{'limit':PAGE_SIZE,'offset':offset},
            'filters':{'categories':[],'name':'','qrDiscount':False,'region':REGION}}


def markup(value):
    if value is None:return ''
    if not isinstance(value,str) or len(value)>60000:raise ValueError('ekp_oversized_or_invalid_text')
    soup=BeautifulSoup(value,'html.parser')
    for n in soup.select('script,style,noscript,form,input,textarea,iframe,button,[hidden],[aria-hidden="true"]'):
        n.decompose()
    for n in soup.find_all(True):
        for key in list(n.attrs):
            if key not in ('href','colspan','rowspan'):del n.attrs[key]
        for key in ('colspan','rowspan'):
            if n.has_attr(key) and not re.fullmatch(r'[1-9][0-9]?',str(n[key])):del n.attrs[key]
        if n.has_attr('href'):
            u=urlsplit(n['href'])
            if u.scheme not in ('https','http') or not u.hostname or u.username or u.password or u.port not in (None,80,443):
                del n.attrs['href']
            else:n['href']=u._replace(query='',fragment='').geturl()
    return str(soup)


def plain(raw):
    soup=BeautifulSoup(raw,'html.parser')
    for n in soup.select('br'):n.replace_with('\n')
    # Preserve block boundaries so rates from separate clauses are not joined.
    for n in soup.select('p,li,tr,div,h1,h2,h3,h4'):
        n.insert_before('\n');n.insert_after('\n')
    return '\n'.join(' '.join(line.split()) for line in soup.get_text(' ',strip=False).splitlines() if line.strip())


def public_row(row):
    if not isinstance(row,dict) or not isinstance(row.get('id'),str) or not re.fullmatch(r'[0-9]{1,12}',row['id']):
        raise ValueError('ekp_invalid_partner_id')
    if not isinstance(row.get('name'),str) or not row['name'].strip() or len(row['name'])>1000:
        raise ValueError('ekp_invalid_partner_name')
    if type(row.get('active')) is not bool or type(row.get('description_authorized')) is not bool:
        raise ValueError('ekp_invalid_access_flags')
    result={k:row[k] for k in ('id','name','active','description_authorized')}
    categories=row.get('categories',[])
    if not isinstance(categories,list) or len(categories)>100:raise ValueError('ekp_invalid_categories')
    result['categories']=[]
    for cat in categories:
        if not isinstance(cat,dict) or type(cat.get('categoryId')) is not int or not isinstance(cat.get('categoryName'),str) or len(cat['categoryName'])>1000:
            raise ValueError('ekp_invalid_category')
        result['categories'].append({k:cat[k] for k in ('categoryId','categoryName')})
    result['text']=markup(row.get('text'))
    # Discard protected descriptions BEFORE parsing or serializing. An anonymous
    # response containing a field is not permission to override the UI login wall.
    if not row['description_authorized']:
        for key in ('loyaltyDescription','discountScheme'):result[key]=markup(row.get(key))
    return result


def page(payload,offset):
    if (not isinstance(payload,dict) or type(payload.get('total')) is not int
        or not 0<=payload['total']<=5000 or type(payload.get('offset')) is not int
        or payload['offset']!=offset or not isinstance(payload.get('partners'),list)
        or len(payload['partners'])>PAGE_SIZE):raise ValueError('ekp_page_contract_changed')
    ids=[]
    for row in payload['partners']:
        if not isinstance(row,dict) or not isinstance(row.get('id'),str) or not re.fullmatch(r'[0-9]{1,12}',row['id']):
            raise ValueError('ekp_page_identity_missing')
        ids.append(row['id'])
    if len(set(ids))!=len(ids) or offset+len(ids)>payload['total']:raise ValueError('ekp_page_identity_count_mismatch')
    return ids


def fields(row):
    name=plain(row['name'])
    program=plain(row.get('loyaltyDescription',''))
    redemption=plain(row.get('discountScheme',''))
    locked=row['description_authorized']
    if locked:kind,status,benefit,conditions='source_observation','public_catalog_details_require_login','',LOGIN
    elif not row['active']:kind,status,benefit,conditions='source_observation','public_catalog_api_inactive','',program or plain(row['text']) or name
    elif not program:kind,status,benefit,conditions='source_observation','public_catalog_terms_missing','',plain(row['text']) or name
    else:kind,status,benefit,conditions='partner_offer','public_catalog_api_terms',program,program
    return dict(partner_name=name,title=name,record_kind=kind,source_status=status,
                benefit_text=benefit,conditions_text=conditions,redemption_text=redemption)


def make_record(row,observed_at,*,request,response_sha,observed_total,completed_at):
    from normalized import make_offer
    row=public_row(row);f=fields(row)
    evidence={'method':'anonymous_source_catalogue_api','api_url':API,'catalogue_root':ROOT,
        'public_partner':row,'public_partner_sha256':sha(row),'request':request,
        'origin_http_status':200,'source_response_sha256':response_sha,'source_reported_total':observed_total,
        'request_completed_at':completed_at,'source_region_parameter':REGION,
        'source_ui_filter_label_observed':'Все регионы','source_active':row['active'],
        'public_detail_url':ROOT+'tiles/'+row['id']+'?region='+REGION,
        'detail_url_individually_opened':False,'linked_terms_read':False,'user_eligibility_verified':False,
        'protected_terms_retained':False,'category_semantics':'mixed_source_tags_not_eligible_regions'}
    return make_offer('ekp','partner:'+row['id']+':region:'+REGION,'Единая карта петербуржца',
        f['partner_name'],f['benefit_text'],API,observed_at,title=f['title'],conditions=f['conditions_text'],
        redemption=f['redemption_text'],record_kind=f['record_kind'],source_status=f['source_status'],
        link_kind='page_block',locator='partners[id='+row['id']+']; filter.region='+REGION,details=evidence,
        warnings=['public_api_fields_not_full_eligibility_check','source_tags_not_eligible_region_claim',
                  'unread_linked_rules_and_image_only_terms','published_dates_not_automatically_inferred'])


def validate_record(record):
    from normalized import text
    d=record['details'];row=d.get('public_partner')
    if not isinstance(row,dict) or set(row)-ROW_KEYS or public_row(row)!=row:
        raise ValueError('ekp_public_projection_invalid')
    f=fields(row)
    if any(record[k]!=text(v) for k,v in f.items()):raise ValueError('ekp_owned_fields_mismatch')
    if (record['source_url']!=API or record['native_id']!='partner:'+row['id']+':region:'+REGION
        or record['link_kind']!='page_block' or record['benefit_url'] is not None or record['category'] is not None
        or record['tables'] or record['valid_from'] is not None or record['valid_until'] is not None
        or d.get('method')!='anonymous_source_catalogue_api' or d.get('api_url')!=API
        or d.get('catalogue_root')!=ROOT or d.get('request')!=query(d.get('request',{}).get('pagination',{}).get('offset'))
        or d.get('source_region_parameter')!=REGION or d.get('public_partner_sha256')!=sha(row)
        or not re.fullmatch(r'[a-f0-9]{64}',d.get('source_response_sha256',''))
        or d.get('origin_http_status')!=200 or d.get('source_active') is not row['active']
        or d.get('protected_terms_retained') is not False or d.get('detail_url_individually_opened') is not False
        or d.get('linked_terms_read') is not False or d.get('user_eligibility_verified') is not False
        or d.get('public_detail_url')!=ROOT+'tiles/'+row['id']+'?region='+REGION):
        raise ValueError('ekp_evidence_scope_mismatch')
    if row['description_authorized'] and (record['rates'] or record['promo_codes'] or 'loyaltyDescription' in row or 'discountScheme' in row):
        raise ValueError('ekp_protected_terms_exposed')


def validate_bundle(folder,*,run_id,commit,clock):
    """Independent public artifact reconstruction before Google authorization."""
    from datetime import datetime
    from pathlib import Path
    from sheets_normalized import prepare
    folder=Path(folder);audit=json.loads((folder/'report.json').read_text())
    bundle=json.loads((folder/'normalized.json').read_text())
    if audit.get('run_id')!=run_id or audit.get('commit')!=commit or audit.get('source_account_used') is not False:
        raise ValueError('ekp_artifact_identity_mismatch')
    start=datetime.fromisoformat(audit['started_at']);end=datetime.fromisoformat(audit['finished_at'])
    if start.tzinfo is None or end.tzinfo is None or not start<=end<=clock or (clock-start).total_seconds()>7200:
        raise ValueError('ekp_artifact_not_fresh')
    if bundle.get('run_id')!=run_id or bundle.get('observed_at')!=audit['started_at'] or [s['source_id'] for s in bundle['sources']]!=['ekp']:
        raise ValueError('ekp_bundle_identity_mismatch')
    rebuilt=[];seen=set()
    for item in audit['pages']:
        if not re.fullmatch(r'page-[0-9]{4}.json',item.get('file','')):raise ValueError('ekp_page_path_invalid')
        raw=(folder/item['file']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=item['public_projection_sha256']:raise ValueError('ekp_page_digest_mismatch')
        data=json.loads(raw)
        if item['request']!=query(data['offset']) or len(data['partners'])!=item['accepted'] or item['origin_status']!=200:
            raise ValueError('ekp_page_metadata_mismatch')
        for row in data['partners']:
            if row['id'] in seen:raise ValueError('ekp_duplicate_artifact_id')
            seen.add(row['id'])
            rebuilt.append(make_record(row,audit['started_at'],request=item['request'],response_sha=item['source_response_sha256'],
                                       observed_total=data['total'],completed_at=item['completed_at']))
    if rebuilt!=bundle['records'] or len(rebuilt)!=audit['accepted_records']:
        raise ValueError('ekp_artifact_reconstruction_mismatch')
    prepare(bundle)
    return bundle
