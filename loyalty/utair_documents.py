"""Configured public Utair rule PDFs, with transient same-host signed downloads.

No personal session, private-code activation, OCR, TLS override or arbitrary
outgoing URL fetch. Full page text is evidence, not a table/entitlement model.
"""
from __future__ import annotations
import asyncio
import copy
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin,urlsplit
import requests
from bs4 import BeautifulSoup
from known_pdf import pdf_pages
from normalized import make_offer,content_hash
from read_budget import within_source_budget

DOCUMENTS=json.loads(Path(__file__).with_suffix('.json').read_text(encoding='utf8'))
ROOT='https://media.utair.ru/status'
HEADERS={'User-Agent':'Mozilla/5.0'}


def checked_download_target(value):
    u=urlsplit(value)
    if (u.scheme!='https' or u.hostname!='eu-s3.beelinecloud.ru' or u.username
        or u.password or u.port not in (None,443) or not u.path or u.fragment):
        raise ValueError('unreviewed_document_redirect')
    return value


def parse_document(key,pages,digest,observed_at):
    cfg=DOCUMENTS[key]
    if len(pages)!=cfg['pages'] or not re.fullmatch('[0-9a-f]{64}',digest):
        raise ValueError('document_page_count_or_digest_invalid')
    norm=lambda v:re.sub(r'\s+',' ',v).strip()
    if not pages or not norm(pages[0]).startswith(cfg['title']):
        raise ValueError('public_document_title_changed')
    if any(len(re.findall('[A-Za-zА-Яа-яЁё]',p))<80 and norm(p)!=cfg.get('short_pages',{}).get(str(i)) for i,p in enumerate(pages,1)) or sum(map(len,pages))>35000:
        raise ValueError('unsupported_document_text')
    url='https://ut0.ru/'+key
    full='\n\n'.join(f'[Страница {n}]\n{p.strip()}' for n,p in enumerate(pages,1))
    return make_offer('utair_rule_documents','document:'+key,'Utair Status','Utair',
        cfg['title'],url,observed_at,title=cfg['title'],conditions=full,
        record_kind='program_rules',link_kind='detail_page',source_status='public_rules_text',
        locator='official shortlink '+key+'; native PDF text',details={
            'evidence_role':'supplementary_rules_not_incremental_discount',
            'supplements_source_ids':['utair_tiers','utair_generations_rules'],
            'extraction_method':'native_pdf_text_no_table_inference',
            'parent_source':ROOT,'document_sha256':digest,'public_aliases':[url],
            'page_count':len(pages),'pages':[{'number':i,'text':p,
                'sha256':hashlib.sha256(p.encode()).hexdigest()} for i,p in enumerate(pages,1)],
            'validity_extraction':'not_inferred_from_entitlement_or_reward_lifetime',
            'linked_documents_fetched':False},warnings=[
            'rule_bundle_not_additive_discount','user_eligibility_not_verified',
            'pdf_tables_not_mapped_to_tier_entitlements','linked_documents_not_fetched',
            'source_documents_can_conflict_with_landing_page'])


def fetch_document(key,observed_at):
    # Errors deliberately omit response headers, signed URL and exception text.
    public='https://ut0.ru/'+key
    if key not in DOCUMENTS:raise ValueError('unconfigured_public_document')
    try:
        first=requests.get(public,headers=HEADERS,timeout=(5,12),allow_redirects=False)
        if first.status_code not in (301,302,303,307,308):
            raise RuntimeError('shortlink_http_'+str(first.status_code))
        target=checked_download_target(first.headers.get('Location',''))
        data=bytearray()
        with requests.get(target,headers=HEADERS,timeout=(5,15),allow_redirects=False,stream=True) as response:
            if response.status_code!=200:raise RuntimeError('document_http_'+str(response.status_code))
            for block in response.iter_content(65536):
                data.extend(block)
                if len(data)>3000000:raise ValueError('document_size_limit')
        pages=pdf_pages(bytes(data),DOCUMENTS[key]['pages'],short_pages=DOCUMENTS[key].get('short_pages'))
        return parse_document(key,pages,hashlib.sha256(data).hexdigest(),observed_at)
    except requests.RequestException:
        raise RuntimeError('public_document_transport_failed') from None


def merge_documents(rows):
    result=[];by_hash={}
    for original in rows:
        row=copy.deepcopy(original);d=row['details'];key=d['document_sha256']
        if key in by_hash:
            first=by_hash[key]
            if first['conditions_text']!=row['conditions_text']:
                raise ValueError('same_document_digest_different_text')
            for alias in d['public_aliases']:
                if alias not in first['details']['public_aliases']:first['details']['public_aliases'].append(alias)
            first['content_sha256']=content_hash(first)
        else:by_hash[key]=row;result.append(row)
    return result


async def collect_documents(client,cfg,report,now,limit):
    if cfg['id']!='utair_rule_documents' or cfg['url']!=ROOT:
        raise ValueError('unreviewed_document_source')
    raw=await within_source_budget(client,lambda:client.read(ROOT,render=True))
    urls={urljoin(ROOT,a['href']) for a in BeautifulSoup(raw,'html.parser').select('a[href]')}
    records=[];attempted=0
    for key in DOCUMENTS:
        public='https://ut0.ru/'+key
        if public not in urls:
            report['errors'].append({'phase':'document_listing','key':key,'reason':'configured_link_not_currently_published'})
            continue
        if len(records)>=limit:
            report['errors'].append({'phase':'document','reason':'record_limit'});break
        try:
            attempted+=1
            record=await within_source_budget(client,lambda:asyncio.to_thread(fetch_document,key,now))
            records.append(record)
        except Exception as exc:
            reason=str(exc) if isinstance(exc,RuntimeError) and re.fullmatch(r'(?:shortlink_http_\d+|document_http_\d+|public_document_transport_failed|source_budget_exhausted)',str(exc)) else type(exc).__name__
            report['errors'].append({'phase':'document','key':key,'reason':reason})
            if reason.endswith('_429') or reason=='source_budget_exhausted':break
        await asyncio.sleep(0.5)
    rows=merge_documents(records)
    report['discovered']=sum('https://ut0.ru/'+k in urls for k in DOCUMENTS)
    report['coverage']=json.dumps({'method':'configured_public_shortlinks_to_native_PDF_text',
        'configured_links':len(DOCUMENTS),'links_attempted':attempted,'links_read':len(records),
        'identical_pdf_aliases_merged':len(records)-len(rows),'unique_documents':len(rows),
        'signed_urls_persisted':False,'all_embedded_links_followed':False},ensure_ascii=False)
    return rows
