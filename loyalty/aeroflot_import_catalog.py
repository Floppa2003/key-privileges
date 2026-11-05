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
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit
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
DETAIL_TEXT_FIELDS={'description':'description','shortDescription':'short_description','earnText':'earn_text',
                    'spendText':'spend_text','specialOffersText':'special_offers_text'}


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
    if kind in ('airline_catalog','airline_detail'):
        from aeroflot_airlines import CATALOG as AIRLINES,DETAIL as AIRLINE_DETAIL,detail_url as airline_url
        if kind=='airline_catalog' and url==AIRLINES:return url
        if kind=='airline_detail' and u.path==urlsplit(AIRLINE_DETAIL).path:
            pairs=parse_qsl(u.query,keep_blank_values=True);q=dict(pairs)
            if (len(pairs)==3 and set(q)=={'lang','id','returnFullParentInfo'} and q['lang']=='ru'
                and q['returnFullParentInfo']=='1' and re.fullmatch('[1-9][0-9]{0,11}',q['id'])
                and url==airline_url(int(q['id']))):return url
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
    elif obs['kind'] in ('detail','airline_catalog','airline_detail'):
        if len(cells)!=1 or cells[0]['type']!='string':raise ValueError('af_json_import_shape')
        raw=cells[0]['value']
    else:raise ValueError('af_not_json_observation')
    if len(raw)>MAX_JSON or not raw.startswith('{'):raise ValueError('af_json_document_invalid')
    try:obj=json.loads(raw,object_pairs_hook=no_duplicate_keys,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('af_nonfinite_json')))
    except (TypeError,json.JSONDecodeError):raise ValueError('af_json_document_invalid') from None
    if not isinstance(obj,dict) or set(obj)!={'isSuccess','errors','data'} or obj['isSuccess'] is not True or obj['errors']!=[]:
        raise ValueError('af_source_api_error_or_shape')
    return obj['data']


def published_link(value):
    """An advertised address is evidence, never authorization to fetch its target."""
    if (not isinstance(value,str) or not value or len(value)>2000
            or re.search(r'[\x00-\x20\x7f<>"\\\\]',value)
            or re.search(r'[\x00-\x1f\x7f\\\\]',unquote(value))):
        raise ValueError('af_published_link_shape')
    u=urlsplit(value)
    if u.scheme in ('https','http'):
        from normalized import canonical_url
        if u.username or u.password or u.port not in (None,443 if u.scheme=='https' else 80):
            raise ValueError('af_published_link_credentials_or_port')
        # Reuse the credential-query guard and tracking cleanup. This performs
        # no request; retain the advertised HTTP scheme in the resulting data.
        netloc=u.netloc[:-3] if u.scheme=='http' and u.netloc.endswith(':80') else u.netloc
        clean=canonical_url(u._replace(scheme='https',netloc=netloc).geturl())
        return (('http'+clean[5:]) if u.scheme=='http' else clean),'web'
    if u.netloc or u.query or u.fragment:
        raise ValueError('af_published_contact_shape')
    address=unquote(u.path)
    if u.scheme=='mailto' and re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}",address):
        return 'mailto:'+u.path,'email'
    if u.scheme=='tel' and re.fullmatch(r'\+?[0-9][0-9().-]{1,30}[0-9]',address):
        return 'tel:'+u.path,'phone'
    raise ValueError('af_published_link_unsupported')


def plain(value, *, links=None, field=None):
    if value is None:return ''
    if not isinstance(value,str) or len(value)>100000:raise ValueError('af_source_text_shape')
    if INSTRUCTION.search(value):raise ValueError('af_source_instruction_text')
    soup=BeautifulSoup(value,'html.parser')
    for n in soup.select('script,style,form,input,iframe,noscript'):n.decompose()
    if links is not None:
        for anchor in soup.select('a[href]'):
            try:url,kind=published_link(anchor['href'])
            except (ValueError,TypeError):continue
            label=plain(anchor.get_text(' ',strip=True))
            entry={'field':field,'label':label,'url':url,'kind':kind,'target_read':False}
            if entry not in links:links.append(entry)
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
    links=[]
    if obj.get('url'):
        try:
            url,kind=published_link(obj['url'])
            links.append({'field':'partner_url','label':'Сайт партнёра' if kind=='web' else 'Контакт партнёра',
                          'url':url,'kind':kind,'target_read':False})
        except (ValueError,TypeError):pass
    projection={'id':pid,'title':plain(obj['title']),
        **{dest:plain(obj[key],links=links,field=key) for key,dest in DETAIL_TEXT_FIELDS.items()},
        'categories':obj['categories'],'mile_action':obj['mileAction'],'awards':{},'special_offers':obj['specialOffers'],
        'outgoing_links':links,'link_projection_version':1}
    if not 1<=len(projection['title'])<=300 or BLOCKED.search(projection['title']):raise ValueError('af_detail_title')
    if not isinstance(obj['categories'],list) or any(type(c) is not int for c in obj['categories']) or obj['mileAction'] not in ('E','S','A'):
        raise ValueError('af_detail_category_or_action')
    if not isinstance(obj['awards'],dict) or set(obj['awards'])!={'accumulation','spending'}:raise ValueError('af_awards_shape')
    for role,awards in obj['awards'].items():
        if not isinstance(awards,list) or len(awards)>100:raise ValueError('af_awards_shape')
        projection['awards'][role]=[]
        for index,a in enumerate(awards):
            if not isinstance(a,dict) or set(a)!={'miles','description','weight'}:raise ValueError('af_awards_shape')
            miles=a['miles']
            if type(miles) not in (int,float) or not math.isfinite(miles) or not 0<=miles<=10**12:raise ValueError('af_awards_shape')
            projection['awards'][role].append({'miles':miles,
                'description':plain(a['description'],links=links,field=f'awards.{role}.{index}.description'),'weight':a['weight']})
    if not isinstance(obj['specialOffers'],list) or len(obj['specialOffers'])>100 or len(json.dumps(obj['specialOffers'],ensure_ascii=False))>10000:
        raise ValueError('af_special_offer_bound')
    if len(json.dumps(projection,ensure_ascii=False))>30000:raise ValueError('af_public_projection_bound')
    return projection


def semantic_fields(projection):
    """Original visible terms, without any addresses recovered from hrefs."""
    from normalized import text
    p=projection;sections=[p['description']]
    for key,label in (('earn_text','Начисление миль'),('spend_text','Использование миль'),('special_offers_text','Специальные предложения')):
        if p[key]:sections.append(label+'\n'+p[key])
    for key,label in (('accumulation','Начисление: поля тарифов источника'),('spending','Использование: поля тарифов источника')):
        if p['awards'][key]:
            sections.append(label+'\n'+'\n'.join(f"Мили: {a['miles']:g}; {a['description']}" for a in p['awards'][key]))
    full=text('\n\n'.join(x for x in sections if x))
    if not full or len(full)>35000:raise ValueError('af_empty_or_oversized_terms')
    return {'benefit':text(p['short_description']),'conditions':full,'redemption':''}


def fields(projection):
    from normalized import text
    source=semantic_fields(projection);full=source['conditions']
    if 'link_projection_version' in projection:
        addresses=[];seen=set()
        for link in projection['outgoing_links']:
            url=link['url']
            address=unquote(url.split(':',1)[1]) if link['kind'] in ('email','phone') else url
            if address in full or address in seen:continue
            seen.add(address)
            addresses.append((link['label']+': ' if link['label'] else '')+address)
        if addresses:full=text(full+'\n\nСсылки и контакты источника\n'+'\n'.join(addresses))
    if len(full)>35000:raise ValueError('af_empty_or_oversized_terms')
    return source['benefit'],full


def semantic_fields_for_details(details):
    """Verify the source-bound cache before semantic parsers use it.

    Historical records and airline records keep their original extraction path.
    New company records display href destinations separately so URI escapes,
    paths and query parameters cannot become rates, codes or conditions.
    """
    p=details.get('public_partner',{})
    if not isinstance(p,dict):raise ValueError('af_record_semantic_projection')
    if 'link_projection_version' not in p:
        if 'semantic_fields' in details:raise ValueError('af_record_link_version')
        return None
    if type(p['link_projection_version']) is not int or p['link_projection_version']!=1:
        raise ValueError('af_record_link_version')
    if details.get('retrieval_method')!=METHOD:raise ValueError('af_record_semantic_method')
    if details.get('public_partner_sha256')!=digest(p):raise ValueError('af_record_projection_digest')
    source=semantic_fields(p)
    if details.get('semantic_fields')!=source:raise ValueError('af_record_semantic_fields')
    return source


def detail(obs,preview,observed_at):
    from normalized import make_offer
    p=project_detail(obs,preview);benefit,conditions=fields(p)
    meta={k:obs[k] for k in ('url','kind','requested_at','calculated_at','cells_sha256','formula_sha256')}
    return make_offer('aeroflot','partner:'+str(p['id']),'Аэрофлот Бонус',p['title'],benefit,obs['url'],observed_at,
        title=p['title'],conditions=conditions,category='; '.join(c['title'] for c in preview['categories']),
        source_status='public_api_google_import',locator='public partner API id='+str(p['id']),warnings=list(WARNINGS),
        details={'retrieval_method':METHOD,'public_partner':p,'public_partner_sha256':digest(p),'catalogue_preview':preview,
          'semantic_fields':semantic_fields(p),
          'import_metadata':meta,'catalogue_root':ROOT,'catalogue_api':CATALOG,'permission_basis':PERMISSION,
          'permission_email_independently_read':False,'account_used':False,'coupon_issued':False,'linked_terms_read':False,
          'origin_http_status':None,'origin_cache_age_verified':False,'full_eligibility_verified':False,
          'special_offers_links_individually_read':False,'human_detail_url_verified':False})


def validate_record(r):
    from normalized import canonical_url,text
    d=r.get('details',{});p=d.get('public_partner',{});meta=d.get('import_metadata',{});preview=d.get('catalogue_preview',{})
    if d.get('public_partner_sha256')!=digest(p):raise ValueError('af_record_projection_digest')
    # Historical projections remain literal evidence of their original read.
    # Their removed hrefs cannot be recovered without the original observation.
    versioned='link_projection_version' in p
    if versioned and (type(p['link_projection_version']) is not int or p['link_projection_version']!=1):
        raise ValueError('af_record_link_version')
    if not isinstance(p.get('outgoing_links'),list):raise ValueError('af_record_links_shape')
    link_keys={'field','label','url','target_read'}|({'kind'} if versioned else set())
    for link in p['outgoing_links']:
        if (not isinstance(link,dict) or set(link)!=link_keys
                or not isinstance(link['field'],str) or not isinstance(link['label'],str)
                or link['target_read'] is not False):
            raise ValueError('af_record_link_shape')
        if not versioned:
            try:url=canonical_url(link['url'])
            except (ValueError,TypeError):raise ValueError('af_record_link_address') from None
            if (url!=link['url'] or link['field'] not in
                    ('partner_url','description','earnText','spendText','specialOffersText')):
                raise ValueError('af_record_link_legacy')
            continue
        try:url,kind=published_link(link['url'])
        except (ValueError,TypeError):raise ValueError('af_record_link_address') from None
        if url!=link['url'] or kind!=link['kind']:raise ValueError('af_record_link_address')
        if link['field']=='partner_url':continue
        if link['field'] in DETAIL_TEXT_FIELDS:
            value=p[DETAIL_TEXT_FIELDS[link['field']]]
        else:
            match=re.fullmatch(r'awards\.(accumulation|spending)\.([0-9]+)\.description',link['field'])
            if not match or int(match[2])>=len(p['awards'][match[1]]):raise ValueError('af_record_link_field')
            value=p['awards'][match[1]][int(match[2])]['description']
        if re.sub(r'\s+',' ',link['label']).strip() not in re.sub(r'\s+',' ',value):
            raise ValueError('af_record_link_text')
    semantic_fields_for_details(d)
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
