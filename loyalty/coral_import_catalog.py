"""Coral public sitemap/HTML projections using the released Coral detail mapper.

Google IMPORTDATA is a parsed projection, not original HTTP bytes. Reject numeric
coercion or delimiter splits rather than repairing an amount, code or table cell.
"""
from __future__ import annotations
import hashlib
import json
import re
from datetime import datetime
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
import coral_catalog as coral
from free_access_probe import sanitized_page
from normalized import content_hash, text

HOST='https://coralbonus.ru'
ROBOTS=HOST+'/robots.txt'
SITEMAP=HOST+'/sitemap/'
METHOD='coral_public_html_google_import_v1'
MAX_CELLS=4094
MAX_JSON=1500000
WARNINGS=['google_import_not_original_http_response','origin_cache_age_not_exposed',
          'sitemap_membership_not_current_category_or_eligibility_proof']


def digest(obj):
    return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def instant(value):
    t=datetime.fromisoformat(value.replace('Z','+00:00'))
    if t.tzinfo is None:raise ValueError('coral_import_time_zone')
    return t


def checked_url(url,kind):
    if kind=='robots' and url==ROBOTS:return url
    if kind=='sitemap' and url==SITEMAP:return url
    if kind=='club_index' and url==coral.CLUB:return url
    if kind=='promo_index' and url==coral.PROMO:return url
    if kind=='club_detail':return coral.checked_url(url,'/klub-privilegii/',3)
    if kind=='promo_detail':return coral.checked_url(url,'/promo/',2)
    raise ValueError('coral_import_url_scope')


def formula(url,kind):
    checked_url(url,kind)
    if kind=='sitemap':return f'=IMPORTXML("{url}";"//*[local-name()=\'loc\']")'
    # A source occurrence of this delimiter produces a second column and fails.
    # It is not a CSV reconstruction heuristic or an invitation to join fragments.
    return f'=IMPORTDATA("{url}";"¦";"en_US")'


def atom(cell,index,kind):
    v=cell.get('effectiveValue',{})
    if 'errorValue' in v:raise ValueError('coral_import_error_cell')
    if not v:return None
    if set(v)!={'stringValue'} or not isinstance(v['stringValue'],str):raise ValueError('coral_import_cell_coercion')
    if len(v['stringValue'])>49000:raise ValueError('coral_import_cell_bound')
    return {'type':'string','value':v['stringValue']} if v['stringValue'] else None


def checked_observation(obs):
    if set(obs)!={'url','kind','requested_at','calculated_at','cells','cells_sha256','formula_sha256'}:raise ValueError('coral_import_observation_shape')
    if obs['formula_sha256']!=digest(formula(obs['url'],obs['kind'])) or obs['cells_sha256']!=digest(obs['cells']):raise ValueError('coral_import_observation_hash')
    if not 0<=(instant(obs['calculated_at'])-instant(obs['requested_at'])).total_seconds()<=180:raise ValueError('coral_import_observation_time')
    cells=obs['cells']
    if not isinstance(cells,list) or not 1<=len(cells)<=MAX_CELLS or len(json.dumps(cells,ensure_ascii=False))>MAX_JSON:raise ValueError('coral_import_observation_bound')
    for i,c in enumerate(cells):
        if not isinstance(c,dict) or set(c)!={'type','value'} or c['type']!='string' or atom({'effectiveValue':{'stringValue':c['value']}},i,obs['kind'])!=c:raise ValueError('coral_import_cell_shape')
    return cells


def public_observation(obs):
    """Keep sanitized source HTML, not script/form/account template contents."""
    cells=checked_observation(obs);raw='\n'.join(c['value'] for c in cells)
    value=raw
    if obs['kind'] not in ('robots','sitemap'):
        if '<html' not in raw.lower() or '<body' not in raw.lower():raise ValueError('coral_import_html_shape')
        value,_=sanitized_page(raw,obs['url'],canonical_identity=True)
        public=BeautifulSoup(value,'html.parser')
        for node in public.select('.modal'):node.decompose()
        value=str(public)
    result={k:obs[k] for k in ('url','kind','requested_at','calculated_at','cells_sha256','formula_sha256')}
    result.update(content=value,content_sha256=hashlib.sha256(value.encode()).hexdigest(),
                  representation='sanitized_html_projection' if obs['kind'] not in ('robots','sitemap') else 'public_text_projection')
    validate_public(result)
    return result


def validate_public(o):
    expected={'url','kind','requested_at','calculated_at','cells_sha256','formula_sha256','content','content_sha256','representation'}
    if not isinstance(o,dict) or set(o)!=expected:raise ValueError('coral_import_public_shape')
    if (o['formula_sha256']!=digest(formula(o['url'],o['kind'])) or not re.fullmatch('[a-f0-9]{64}',o['cells_sha256'])
        or not isinstance(o['content'],str) or not 1<=len(o['content'])<=MAX_JSON
        or o['content_sha256']!=hashlib.sha256(o['content'].encode()).hexdigest()):raise ValueError('coral_import_public_hash')
    if not 0<=(instant(o['calculated_at'])-instant(o['requested_at'])).total_seconds()<=180:raise ValueError('coral_import_public_time')
    html=o['kind'] not in ('robots','sitemap')
    if o['representation']!=('sanitized_html_projection' if html else 'public_text_projection'):raise ValueError('coral_import_representation')
    if html:
        soup=BeautifulSoup(o['content'],'html.parser')
        if soup.select('script,form,input,textarea,iframe,.modal'):raise ValueError('coral_import_private_template')
        canonical=[n for n in soup.select('link[href]') if n['href']==o['url']]
        if len(canonical)!=1:raise ValueError('coral_import_canonical')
    return o


def policy(o):
    from protego import Protego
    validate_public(o);s=o['content']
    if o['kind']!='robots' or not re.search(r'^User-agent:',s,re.I|re.M) or '<html' in s.lower():raise ValueError('coral_import_policy_unreadable')
    if not re.search(r'^Sitemap:\s*'+re.escape(SITEMAP)+r'\s*$',s,re.M|re.I):raise ValueError('coral_import_sitemap_not_advertised')
    p=Protego.parse(s)
    for u in (SITEMAP,coral.CLUB,coral.PROMO):
        if not p.can_fetch(u,'LoyaltyCatalogResearchBot'):raise ValueError('coral_import_policy_disallow')
    return p


def sitemap(o,categories):
    validate_public(o)
    if o['kind']!='sitemap':raise ValueError('coral_import_sitemap_kind')
    urls=o['content'].splitlines()
    if not 1<=len(urls)<=2000 or len(set(urls))!=len(urls):raise ValueError('coral_import_sitemap_bound_or_duplicate')
    result=[]
    for u in urls:
        x=urlsplit(u)
        if x.scheme!='https' or x.netloc!='coralbonus.ru' or x.query or x.fragment:raise ValueError('coral_import_sitemap_foreign_url')
        if x.path.startswith('/klub-privilegii/') and len(x.path.strip('/').split('/'))==3:
            coral.checked_url(u,'/klub-privilegii/',3)
            parent=u.rsplit('/',2)[0]+'/'
            if parent in categories:result.append({'url':u,'category':categories[parent],'parent_url':parent})
    if not result:raise ValueError('coral_import_sitemap_no_cards')
    return result,len(urls)


def physical_product(o):
    """Only positively identified non-referral merchandise is excluded."""
    soup=BeautifulSoup(o['content'],'html.parser');hs=soup.select('h1')
    if len(hs)!=1:return False
    sec=hs[0].find_parent('section')
    if not sec or sec.select_one('.product-purchase-box.referal,.order-autorize'):return False
    box=sec.select_one('.product-purchase-box')
    return bool(box and re.search(r'В корзину|Добавить в корзину',box.get_text(' ',strip=True),re.I))


def detail(o,sid,entry,observed_at):
    validate_public(o)
    if o['kind']!=('club_detail' if sid=='coral' else 'promo_detail') or o['url']!=entry['url']:raise ValueError('coral_import_detail_identity')
    retrieval={'method':METHOD,'identity':'source_canonical_in_imported_html','fetched_at':o['calculated_at'],
               'requested_at':o['requested_at'],'origin_status':None,'origin_cache_age_verified':False,
               'google_cells_sha256':o['cells_sha256'],'formula_sha256':o['formula_sha256'],
               'representation':o['representation'],'account_used':False}
    row=coral.detail(o['content'],sid,entry,observed_at,retrieval)
    row['warnings']=sorted(set(row['warnings'])|set(WARNINGS))
    row['details']['google_import_scope']='sitemap_card_under_current_category' if sid=='coral' else 'current_promo_index_card'
    row['details']['discovery_sitemap']=SITEMAP if sid=='coral' else None
    row['content_sha256']=content_hash(row)
    return row
