"""Public Aeroflot catalogue fields from current Google IMPORT calculations.

No source account, stored partner answers, or claim of an uncached HTTP response.
The endpoints and GET parameter names were read from the source's current module.
"""
from __future__ import annotations
import hashlib
import json
import math
import re
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit
from bs4 import BeautifulSoup

HOST='https://www.aeroflot.ru'
ROOT=HOST+'/ru-ru/afl_bonus/partners'
ROBOTS=HOST+'/robots.txt'
CATALOG=HOST+'/partners/ws/v.0.0.2/json/partner/categories?lang=ru'
DETAIL=HOST+'/partners/ws/v.0.0.3/json/partner/get'
METHOD='aeroflot_public_api_google_import_v1'
PERMISSION='owner_reported_source_permission_2026-09-16'
EMPTY='__AF_EMPTY_FIELD_V1__'
MAX_CELLS=4094
MAX_JSON=2000000
WARNINGS=['google_import_not_original_http_response','origin_cache_age_not_exposed',
          'user_eligibility_not_verified','linked_special_offers_and_image_rules_not_read',
          'dates_not_automatically_inferred','permission_reported_by_owner_email_not_independently_read']
BLOCKED=re.compile(r'access denied|captcha|проверка безопасности|доступ.{0,50}ограничен|отключите VPN',re.I)
INSTRUCTION=re.compile(r'ignore (?:all |the )?previous instructions|export private|reveal (?:your )?system prompt|игнорируй предыдущие инструкции',re.I)


def digest(obj):
    return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def instant(value):
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None:raise ValueError('af_time_zone_missing')
    return result


def native_id(value):
    if type(value) is not int or not 1<=value<=10**12:raise ValueError('af_partner_id_invalid')
    return value


def detail_url(ident):return DETAIL+'?'+urlencode({'id':native_id(ident),'lang':'ru'})


def checked_url(url,kind):
    if not isinstance(url,str) or len(url)>600:raise ValueError('af_url_scope')
    u=urlsplit(url)
    if u.scheme!='https' or u.netloc!='www.aeroflot.ru' or u.fragment or '\\' in url or '%' in u.path or '..' in u.path:
        raise ValueError('af_url_scope')
    if kind=='robots' and url==ROBOTS:return url
    if kind=='discovery' and url==ROOT:return url
    if kind=='catalog' and url==CATALOG:return url
    if kind=='detail' and u.path==urlsplit(DETAIL).path:
        pairs=parse_qsl(u.query,keep_blank_values=True);q=dict(pairs)
        if (len(pairs)==2 and set(q)=={'id','lang'} and q['lang']=='ru' and re.fullmatch('[1-9][0-9]{0,11}',q['id'])
            and url==detail_url(int(q['id']))):return url
    raise ValueError('af_url_scope')


def formula(url,kind):
    checked_url(url,kind)
    if kind=='robots':return f'=IMPORTDATA("{url}")'
    if kind=='discovery':
        xpath="//title | //body//text()[starts-with(normalize-space(.),'http') and contains(.,'/partners')]"
        return f'=IMPORTXML("{url}";"{xpath}")'
    if kind=='catalog':
        # Explicit delimiter prevents CSV's comma parsing from damaging JSON
        # strings. The two dimensions and empty marker retain every field.
        return (f'=LET(x;IMPORTDATA("{url}";"}}";"en_US");'
                f'VSTACK(ROWS(x);COLUMNS(x);TRANSPOSE(ARRAYFORMULA(IF(x="";"{EMPTY}";TO_TEXT(x))))))')
    return f'=IMPORTDATA("{url}";CHAR(9);"en_US")'


def atom(cell,index,kind):
    value=cell.get('effectiveValue',{})
    if 'errorValue' in value:raise ValueError('af_import_error_cell')
    if not value:return None
    if set(value)=={'stringValue'}:
        s=value['stringValue']
        if not isinstance(s,str) or len(s)>49000:raise ValueError('af_cell_bound')
        return {'type':'string','value':s} if s else None
    n=value.get('numberValue')
    if kind=='catalog' and index in (0,1) and set(value)=={'numberValue'} and type(n) in (int,float) and math.isfinite(n) and n==int(n) and 1<=n<=MAX_CELLS:
        return {'type':'integer','value':int(n)}
    raise ValueError('af_unexpected_cell_coercion')


def checked_observation(obs):
    if not isinstance(obs,dict) or set(obs)!={'url','kind','requested_at','calculated_at','cells','cells_sha256','formula_sha256'}:
        raise ValueError('af_observation_contract')
    if obs['formula_sha256']!=digest(formula(obs['url'],obs['kind'])) or obs['cells_sha256']!=digest(obs['cells']):
        raise ValueError('af_observation_digest')
    if not 0<=(instant(obs['calculated_at'])-instant(obs['requested_at'])).total_seconds()<=180:
        raise ValueError('af_observation_time')
    cells=obs['cells']
    if not isinstance(cells,list) or not 1<=len(cells)<=MAX_CELLS or len(json.dumps(cells,ensure_ascii=False))>MAX_JSON+100000:
        raise ValueError('af_observation_size')
    for i,c in enumerate(cells):
        if not isinstance(c,dict) or set(c)!={'type','value'}:raise ValueError('af_cell_contract')
        value={'stringValue':c['value']} if c['type']=='string' else {'numberValue':c['value']} if c['type']=='integer' else {}
        if atom({'effectiveValue':value},i,obs['kind'])!=c:raise ValueError('af_cell_contract')
    return cells


def no_duplicate_keys(pairs):
    d={}
    for k,v in pairs:
        if k in d:raise ValueError('af_duplicate_json_key')
        d[k]=v
    return d


def envelope(obs):
    cells=checked_observation(obs)
    if obs['kind']=='catalog':
        if len(cells)<4 or cells[0]!= {'type':'integer','value':1} or cells[1]['type']!='integer':
            raise ValueError('af_json_import_shape')
        fields=cells[2:]
        if len(fields)!=cells[1]['value'] or any(c['type']!='string' for c in fields):raise ValueError('af_json_import_shape')
        # No guessed punctuation or repaired values: use exactly the explicit
        # delimiter, dimensions, and fields returned by the current calculation.
        raw='}'.join('' if c['value']==EMPTY else c['value'] for c in fields)
    elif obs['kind']=='detail':
        if len(cells)!=1 or cells[0]['type']!='string':raise ValueError('af_json_import_shape')
        raw=cells[0]['value']
    else:raise ValueError('af_not_json_observation')
    if len(raw)>MAX_JSON or not raw.startswith('{'):raise ValueError('af_json_document_invalid')
    try:obj=json.loads(raw,object_pairs_hook=no_duplicate_keys,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('af_nonfinite_json')))
    except (TypeError,json.JSONDecodeError):raise ValueError('af_json_document_invalid') from None
    if not isinstance(obj,dict) or set(obj)!={'isSuccess','errors','data'} or obj['isSuccess'] is not True or obj['errors']!=[]:
        raise ValueError('af_source_api_error_or_shape')
    return obj['data']


def plain(value):
    if value is None:return ''
    if not isinstance(value,str) or len(value)>100000:raise ValueError('af_source_text_shape')
    if INSTRUCTION.search(value):raise ValueError('af_source_instruction_text')
    soup=BeautifulSoup(value,'html.parser')
    for n in soup.select('script,style,form,input,iframe,noscript'):n.decompose()
    for br in soup.select('br'):br.replace_with('\n')
    for tag in soup.select('p,div,li,tr,h1,h2,h3'):tag.insert_before('\n')
    result=re.sub(r'[^\S\n]+',' ',soup.get_text(' ',strip=False)).strip()
    return re.sub(r'\n[ \t]*\n+','\n',result)


def catalog(obs):
    data=envelope(obs)
    if not isinstance(data,list) or not 1<=len(data)<=100:raise ValueError('af_category_shape')
    rows={};categories={}
    for category in data:
        if not isinstance(category,dict) or set(category)!={'id','title','partners'}:raise ValueError('af_category_shape')
        ident=native_id(category['id']);name=plain(category['title'])
        if ident in categories or not 1<=len(name)<=300:raise ValueError('af_category_identity')
        categories[ident]=name
        if not isinstance(category['partners'],list) or len(category['partners'])>2000:raise ValueError('af_partner_list_shape')
        for p in category['partners']:
            if not isinstance(p,dict) or set(p)!={'id','name','shortDescription','milesActionType','logoUrl'}:raise ValueError('af_preview_shape')
            pid=native_id(p['id']);title=plain(p['name']);short=plain(p['shortDescription'])
            if not 1<=len(title)<=300 or len(short)>5000 or p['milesActionType'] not in ('earn','spend','all'):raise ValueError('af_preview_shape')
            view={'id':pid,'title':title,'short_description':short,'miles_action':p['milesActionType']}
            if pid in rows and any(rows[pid][k]!=v for k,v in view.items()):raise ValueError('af_conflicting_preview')
            row=rows.setdefault(pid,{**view,'categories':[]})
            row['categories'].append({'id':ident,'title':name})
    if not rows or len(rows)>2000:raise ValueError('af_catalogue_bound')
    return rows


def private_field(value):
    if isinstance(value,dict):return any(re.search(r'password|token|secret|cookie|authorization',k,re.I) or private_field(v) for k,v in value.items())
    return any(private_field(v) for v in value) if isinstance(value,list) else False


def project_detail(obs,preview):
    obj=envelope(obs)
    required={'id','title','description','shortDescription','earnText','spendText','awards','categories','mileAction','specialOffers','specialOffersText'}
    allowed=required|{'weight','isNew','url','imageUrl','tags','logoUrl'}
    if not isinstance(obj,dict) or not required<=set(obj) or set(obj)-allowed or private_field(obj):raise ValueError('af_detail_shape')
    pid=native_id(obj['id'])
    if pid!=preview['id'] or obs['url']!=detail_url(pid):raise ValueError('af_detail_wrong_partner')
    projection={'id':pid,'title':plain(obj['title']),'description':plain(obj['description']),
        'short_description':plain(obj['shortDescription']),'earn_text':plain(obj['earnText']),
        'spend_text':plain(obj['spendText']),'special_offers_text':plain(obj['specialOffersText']),
        'categories':obj['categories'],'mile_action':obj['mileAction'],'awards':{},'special_offers':obj['specialOffers'],
        'outgoing_links':[]}
    from normalized import canonical_url
    candidates=[]
    if obj.get('url'):candidates.append(('partner_url','Сайт партнёра',obj['url']))
    for key in ('description','earnText','spendText','specialOffersText'):
        for link in BeautifulSoup(obj.get(key) or '', 'html.parser').select('a[href]'):
            candidates.append((key,plain(link.get_text(' ',strip=True)),link['href']))
    for field,label,url in candidates:
        try:clean=canonical_url(url)
        except (ValueError,TypeError):continue
        entry={'field':field,'label':label,'url':clean,'target_read':False}
        if entry not in projection['outgoing_links']:projection['outgoing_links'].append(entry)
    if not 1<=len(projection['title'])<=300 or BLOCKED.search(projection['title']):raise ValueError('af_detail_title')
    if not isinstance(obj['categories'],list) or any(type(c) is not int for c in obj['categories']) or obj['mileAction'] not in ('E','S','A'):
        raise ValueError('af_detail_category_or_action')
    if not isinstance(obj['awards'],dict) or set(obj['awards'])!={'accumulation','spending'}:raise ValueError('af_awards_shape')
    for role,awards in obj['awards'].items():
        if not isinstance(awards,list) or len(awards)>100:raise ValueError('af_awards_shape')
        projection['awards'][role]=[]
        for a in awards:
            if not isinstance(a,dict) or set(a)!={'miles','description','weight'}:raise ValueError('af_awards_shape')
            miles=a['miles']
            if type(miles) not in (int,float) or not math.isfinite(miles) or not 0<=miles<=10**12:raise ValueError('af_awards_shape')
            projection['awards'][role].append({'miles':miles,'description':plain(a['description']),'weight':a['weight']})
    if not isinstance(obj['specialOffers'],list) or len(obj['specialOffers'])>100 or len(json.dumps(obj['specialOffers'],ensure_ascii=False))>10000:
        raise ValueError('af_special_offer_bound')
    if len(json.dumps(projection,ensure_ascii=False))>30000:raise ValueError('af_public_projection_bound')
    return projection


def fields(projection):
    from normalized import text
    p=projection;sections=[p['description']]
    for key,label in (('earn_text','Начисление миль'),('spend_text','Использование миль'),('special_offers_text','Специальные предложения')):
        if p[key]:sections.append(label+'\n'+p[key])
    for key,label in (('accumulation','Начисление: поля тарифов источника'),('spending','Использование: поля тарифов источника')):
        if p['awards'][key]:
            sections.append(label+'\n'+'\n'.join(f"Мили: {a['miles']:g}; {a['description']}" for a in p['awards'][key]))
    full=text('\n\n'.join(x for x in sections if x))
    if not full or len(full)>35000:raise ValueError('af_empty_or_oversized_terms')
    return text(p['short_description']),full


def detail(obs,preview,observed_at):
    from normalized import make_offer
    p=project_detail(obs,preview);benefit,conditions=fields(p)
    meta={k:obs[k] for k in ('url','kind','requested_at','calculated_at','cells_sha256','formula_sha256')}
    return make_offer('aeroflot','partner:'+str(p['id']),'Аэрофлот Бонус',p['title'],benefit,obs['url'],observed_at,
        title=p['title'],conditions=conditions,category='; '.join(c['title'] for c in preview['categories']),
        source_status='public_api_google_import',locator='public partner API id='+str(p['id']),warnings=list(WARNINGS),
        details={'retrieval_method':METHOD,'public_partner':p,'public_partner_sha256':digest(p),'catalogue_preview':preview,
          'import_metadata':meta,'catalogue_root':ROOT,'catalogue_api':CATALOG,'permission_basis':PERMISSION,
          'permission_email_independently_read':False,'account_used':False,'coupon_issued':False,'linked_terms_read':False,
          'origin_http_status':None,'origin_cache_age_verified':False,'full_eligibility_verified':False,
          'special_offers_links_individually_read':False,'human_detail_url_verified':False})


def validate_record(r):
    from normalized import text
    d=r.get('details',{});p=d.get('public_partner',{});meta=d.get('import_metadata',{});preview=d.get('catalogue_preview',{})
    if d.get('public_partner_sha256')!=digest(p):raise ValueError('af_record_projection_digest')
    benefit,conditions=fields(p)
    if (r['source_id']!='aeroflot' or r['native_id']!='partner:'+str(native_id(p['id'])) or r['source_url']!=detail_url(p['id'])
        or meta.get('url')!=r['source_url'] or meta.get('kind')!='detail' or preview.get('id')!=p['id']
        or r['title']!=p['title'] or r['partner_name']!=p['title'] or r['benefit_text']!=benefit or r['conditions_text']!=conditions
        or r['redemption_text']!='' or r['source_status']!='public_api_google_import' or r['record_kind']!='partner_offer'
        or r['link_kind']!='detail_page' or r['benefit_url']!=r['source_url'] or r['tables']!=[]
        or r['category']!=text('; '.join(c['title'] for c in preview['categories']))
        or r['valid_from'] is not None or r['valid_until'] is not None or not set(WARNINGS)<=set(r['warnings'])):
        raise ValueError('af_record_source_binding')
    if (d.get('retrieval_method')!=METHOD or d.get('permission_basis')!=PERMISSION or d.get('origin_http_status') is not None
        or meta.get('formula_sha256')!=digest(formula(r['source_url'],'detail'))
        or not re.fullmatch('[a-f0-9]{64}',meta.get('cells_sha256',''))
        or any(d.get(k) is not False for k in ('account_used','coupon_issued','linked_terms_read','origin_cache_age_verified',
              'full_eligibility_verified','permission_email_independently_read','special_offers_links_individually_read','human_detail_url_verified'))):
        raise ValueError('af_record_evidence_promotion')
    if not 0<=(instant(meta['calculated_at'])-instant(meta['requested_at'])).total_seconds()<=180:raise ValueError('af_record_time')
