"""Retain owned catalogue text when a discovered RZD detail cannot be read.

Previews are separate evidence-only records, never replacements for previously
read full conditions. No rates, eligibility or authentication are inferred.
"""
from __future__ import annotations
import re
from urllib.parse import urljoin,urlsplit
from bs4 import BeautifulSoup
import rzd_import_catalog as m
from normalized import make_offer,text

METHOD='google_import_rzd_catalogue_preview_v1'
WARNINGS=m.WARNINGS+['catalogue_preview_not_full_detail','detail_read_failed',
    'catalogue_rates_may_conflict_no_automatic_benefits','authentication_not_determined_from_preview']


def sanitize(raw):
    if not isinstance(raw,str) or len(raw)>700000:raise ValueError('rzd_catalogue_html_bound')
    soup=BeautifulSoup(raw,'html.parser');head=soup.find('h1');frames=soup.select('.partners__frame')
    if not head or not re.fullmatch('Партн[её]ры',head.get_text(strip=True),re.I) or not 1<=len(frames)<=50:
        raise ValueError('rzd_catalogue_html_identity')
    safe=BeautifulSoup(str(head)+''.join(str(n) for n in frames),'html.parser')
    for n in safe.select('script,style,form,input,textarea,noscript,iframe,img,svg,button'):n.decompose()
    for n in safe.find_all(True):
        for key in list(n.attrs):
            if key not in ('class','id','href'):del n.attrs[key]
        if n.has_attr('href'):
            value=urljoin(m.HOME,n['href']);u=urlsplit(value)
            # Preserve public links for the existing scope classifier, but no
            # session/account/form query values may be archived.
            if (u.scheme not in ('http','https') or u.username or u.password or
                re.search(r'(?:token|session|password|auth|login|backurl|back_url)=',u.query,re.I)):
                del n.attrs['href']
    result=str(BeautifulSoup(str(safe),'html.parser'))
    if len(result)>600000 or m.INSTRUCTION.search(safe.get_text(' ',strip=True)):raise ValueError('rzd_catalogue_html_content')
    return result


def read_html(obs):
    cells=m.checked_observation(obs)
    if obs['kind']!='catalog_cards' or len(cells)!=1 or cells[0]['kind']!='string':raise ValueError('rzd_catalogue_html_observation')
    raw=cells[0]['text']
    if sanitize(raw)!=raw:raise ValueError('rzd_catalogue_html_not_sanitized')
    return BeautifulSoup(raw,'html.parser')


def previews(obs):
    soup=read_html(obs);out={}
    for frame in soup.select('.partners__frame'):
        for node in frame.select('.article__item'):
            if node.find_parent(class_='partners__frame') is not frame:continue
            links=node.select(':scope > a[href]');desc=node.select_one(':scope > .desc')
            if len(links)!=1 or desc is None:continue
            url=urljoin(m.HOME,links[0]['href'])
            try:m.checked_url(url)
            except ValueError:continue
            if not re.fullmatch(r'/partners/[0-9]+/|/promo/[a-z0-9_-]+/',urlsplit(url).path):continue
            summary=desc.select_one(':scope > .bonuse');category=desc.select_one(':scope > p:not(.bonuse)')
            body=desc.select_one('.more__inf');element=node.get('id','')
            if not re.fullmatch(r'bx_[0-9]+_[0-9]+',element):continue
            for br in desc.select('br'):br.replace_with('\n')
            card={'url':url,'element_id':element,'category':text(category.get_text(' ',strip=True)) if category else '',
                'summary':text(summary.get_text(' ',strip=True)) if summary else '',
                'conditions':text(body.get_text('\n',strip=True)) if body else ''}
            if not card['summary'] or not card['conditions']:continue
            if len(card['summary'])>1000 or len(card['conditions'])>25000:raise ValueError('rzd_preview_bound')
            if m.RESTRICTION.search(card['summary']) or m.INSTRUCTION.search(card['conditions']):raise ValueError('rzd_preview_content')
            entry={'card':card,'catalogue_url':obs['url'],'catalogue_cells_sha256':obs['cells_sha256'],
                   'formula_sha256':obs['formula_sha256'],'requested_at':obs['requested_at'],'calculated_at':obs['calculated_at']}
            if url in out and out[url]['card']!=card:raise ValueError('rzd_preview_conflicting_cards')
            out.setdefault(url,entry)
    if not out:raise ValueError('rzd_no_owned_previews')
    return out


def merge_previews(existing,incoming):
    for url,entry in incoming.items():
        old=existing.get(url)
        if old and any(old['card'][k]!=entry['card'][k] for k in ('url','category','summary','conditions')):
            # Do not choose one contradictory same-run source version.
            raise ValueError('rzd_preview_conflicting_versions')
        existing.setdefault(url,entry)


def make_preview(entry,observed_at,failure):
    p=entry['card'];url=m.checked_url(entry['catalogue_url'])
    if not re.fullmatch(r'rzd_[a-z_]{1,100}|[A-Za-z]+Error',failure):raise ValueError('rzd_preview_failure')
    return make_offer('rzd','catalogue:'+urlsplit(p['url']).path,'РЖД Бонус',None,'',
        url+'#'+p['element_id'],observed_at,title=p['summary'][:300],category=p['category'],
        conditions=p['summary']+'\n\n'+p['conditions'],record_kind='source_observation',
        link_kind='page_anchor',locator='article__item#'+p['element_id'],source_status='public_catalogue_preview_detail_unread',
        warnings=list(WARNINGS),details={'retrieval_method':METHOD,'catalogue_preview':entry,
            'catalogue_preview_sha256':m.digest(entry),'discovered_detail_url':p['url'],'detail_failure':failure,
            'full_detail_read':False,'authentication_required':None,'origin_http_status':None,
            'origin_cache_age_verified':False,'account_used':False,'coupon_issued':False,'full_eligibility_verified':False})


def validate_record(r):
    d=r.get('details',{});entry=d.get('catalogue_preview',{});p=entry.get('card',{})
    if d.get('retrieval_method')!=METHOD or d.get('catalogue_preview_sha256')!=m.digest(entry):raise ValueError('rzd_preview_evidence')
    url=m.checked_url(entry['catalogue_url']);target=m.checked_url(p['url'])
    if urlsplit(url).path!='/partners/' or not re.fullmatch(r'/partners/[0-9]+/|/promo/[a-z0-9_-]+/',urlsplit(target).path):raise ValueError('rzd_preview_scope')
    if (set(p)!={'url','element_id','category','summary','conditions'} or not re.fullmatch(r'bx_[0-9]+_[0-9]+',p['element_id'])
        or not p['summary'] or not p['conditions'] or m.INSTRUCTION.search(p['summary']+' '+p['conditions'])):raise ValueError('rzd_preview_card_shape')
    if (r['source_id']!='rzd' or r['native_id']!='catalogue:'+urlsplit(target).path
        or r['source_url']!=url+'#'+p['element_id'] or r['benefit_url']!=r['source_url']
        or r['title']!=text(p['summary'][:300]) or r['category']!=(text(p['category']) or None) or r['partner_name'] is not None
        or r['conditions_text']!=text(p['summary']+'\n\n'+p['conditions']) or r['benefit_text'] or r['redemption_text']
        or r['record_kind']!='source_observation' or r['source_status']!='public_catalogue_preview_detail_unread'
        or r['link_kind']!='page_anchor' or r['locator']!='article__item#'+p['element_id'] or r['rates'] or r['tables']
        or r['valid_from'] is not None or r['valid_until'] is not None or not set(WARNINGS)<=set(r['warnings'])):raise ValueError('rzd_preview_record_binding')
    if (d.get('discovered_detail_url')!=target or d.get('authentication_required') is not None or d.get('origin_http_status') is not None
        or not re.fullmatch(r'rzd_[a-z_]{1,100}|[A-Za-z]+Error',d.get('detail_failure',''))
        or any(d.get(k) is not False for k in ('full_detail_read','origin_cache_age_verified','account_used','coupon_issued','full_eligibility_verified'))):raise ValueError('rzd_preview_promotion')
    if (entry['formula_sha256']!=m.digest(m.formula(url,'catalog_cards')) or not re.fullmatch('[a-f0-9]{64}',entry['catalogue_cells_sha256'])
        or not 0<=(m.instant(entry['calculated_at'])-m.instant(entry['requested_at'])).total_seconds()<=300):raise ValueError('rzd_preview_provenance')
