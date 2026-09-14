"""Discover public Utair PDFs from each live landing page; never replay old text."""
from __future__ import annotations
import asyncio
import copy
import hashlib
import json
import re
from urllib.parse import urljoin,urlsplit
import requests
from bs4 import BeautifulSoup
from document_text import extract_pdf,document_records
from normalized import content_hash,text
from read_budget import within_source_budget

ROOT='https://media.utair.ru/status'
HEADERS={'User-Agent':'Mozilla/5.0'}


def checked_shortlink(value):
    u=urlsplit(value)
    if (u.scheme!='https' or u.netloc!='ut0.ru' or u.query or u.fragment
            or not re.fullmatch(r'/[A-Za-z0-9_-]{1,80}',u.path)):
        raise ValueError('unreviewed_public_shortlink')
    return u.path[1:]


def checked_download_target(value):
    u=urlsplit(value)
    if (u.scheme!='https' or u.hostname!='eu-s3.beelinecloud.ru' or u.username
            or u.password or u.port not in (None,443) or not u.path or u.fragment):
        raise ValueError('unreviewed_document_redirect')
    return value


def discover_documents(raw):
    result={};soup=BeautifulSoup(raw,'html.parser')
    for a in soup.select('a[href]'):
        url=urljoin(ROOT,a['href'].strip())
        if urlsplit(url).hostname!='ut0.ru':continue
        key=checked_shortlink(url)
        context=a.find_parent(class_='tn-atom__tip-text') or a.parent
        label=text(a.get_text(' ',strip=True));context=text(context.get_text(' ',strip=True))
        if key not in result:result[key]={'key':key,'url':url,'labels':[],'contexts':[]}
        if label and label not in result[key]['labels']:result[key]['labels'].append(label)
        if context and context not in result[key]['contexts']:result[key]['contexts'].append(context)
    if not result:raise RuntimeError('no_public_document_links_discovered')
    if len(result)>80:raise RuntimeError('public_document_listing_limit')
    return list(result.values())


def fetch_document(entry,observed_at,parent_sha256):
    public=entry['url'];key=checked_shortlink(public)
    try:
        # The shortlink is a public redirect, not a login or private session.
        first=requests.get(public,headers=HEADERS,timeout=(5,12),allow_redirects=False)
        if first.status_code not in (301,302,303,307,308) or first.headers.get('Retry-After'):
            raise RuntimeError('shortlink_http_'+str(first.status_code))
        target=checked_download_target(first.headers.get('Location',''))
        data=bytearray()
        with requests.get(target,headers=HEADERS,timeout=(5,15),allow_redirects=False,stream=True) as response:
            if response.status_code!=200 or response.headers.get('Retry-After'):
                raise RuntimeError('document_http_'+str(response.status_code))
            for block in response.iter_content(65536):
                data.extend(block)
                if len(data)>5_000_000:raise ValueError('document_size_limit')
        doc=extract_pdf(bytes(data))
        rows=document_records('utair_rule_documents','document:'+key,'Utair Status','Utair',
            public,observed_at,doc,parent_source=ROOT,parent_sha256=parent_sha256,
            label='; '.join(entry['labels']))
        for row in rows:
            row['details']['discovery_contexts']=entry['contexts']
            row['content_sha256']=content_hash(row)
        return rows
    except requests.RequestException:
        raise RuntimeError('public_document_transport_failed') from None


def merge_documents(rows):
    result=[];by_hash={}
    for original in rows:
        row=copy.deepcopy(original);d=row['details']
        key=(d['document_sha256'],d['document_part']['number'])
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
    entries=discover_documents(raw);parent_sha=hashlib.sha256(raw.encode()).hexdigest()
    records=[];attempted=0;read=0
    for entry in entries:
        if len(records)>=limit:
            report['errors'].append({'phase':'document','reason':'record_limit'});break
        try:
            attempted+=1
            rows=await within_source_budget(client,lambda:asyncio.to_thread(fetch_document,entry,now,parent_sha))
            if len(records)+len(rows)>limit:raise RuntimeError('record_limit')
            records.extend(rows);read+=1
            if rows[0]['details']['document_errors']:
                report['errors'].append({'phase':'document_text','key':entry['key'],'errors':rows[0]['details']['document_errors']})
        except Exception as exc:
            reason=str(exc) if isinstance(exc,RuntimeError) and re.fullmatch(r'(?:shortlink_http_\d+|document_http_\d+|public_document_transport_failed|source_budget_exhausted|record_limit)',str(exc)) else type(exc).__name__
            report['errors'].append({'phase':'document','key':entry['key'],'reason':reason})
            if reason.endswith('_429') or reason in ('source_budget_exhausted','record_limit'):break
        await asyncio.sleep(0.5)
    rows=merge_documents(records)
    report['discovered']=len(entries)
    report['coverage']=json.dumps({'method':'live_shortlink_discovery_native_PDF_or_OCR',
        'discovered_links':len(entries),'links_attempted':attempted,'links_read':read,
        'identical_pdf_aliases_merged':len(records)-len(rows),'output_records':len(rows),
        'signed_urls_persisted':False,'recursive_document_links_followed':False},ensure_ascii=False)
    return rows
