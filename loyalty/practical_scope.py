"""Practical lookup scope. Omitted documents are not failed or expired offers.

Match explicit document provenance, never every program_rules/PDF/zero-rate row.
The source bundle is still validated intact before this publication projection.
"""
from __future__ import annotations
import copy,json,re
from collections import Counter
from urllib.parse import urlsplit

VERSION='practical-offers-v1'
GENERAL_CORAL_PATHS=frozenset({
    '/pravila-programmy/',
    '/pravila-i-usloviya-ispol-zovaniya-podarochnoi-karty-sertifikata/',
})


def exclusion_reason(details, url='', title='', kind=''):
    if details.get('products_are_exclusions_not_offers') is True:
        return 'product_exclusion_list'
    u=urlsplit(url)
    if u.netloc=='coralbonus.ru' and u.path in GENERAL_CORAL_PATHS:
        return 'general_contract'
    if details.get('live_document_text') is True:
        if details.get('retrieval_method')=='ekp_source_linked_rules_v1':
            return 'bulk_appendix'
        if details.get('retrieval_method')=='coral_source_linked_pdf_free_api_v1':
            return 'general_contract'
        part=details.get('document_part') or {}
        if part.get('total',1)>1 or details.get('page_count',0)>4:
            return 'bulk_document'
    return None


def follow_document_link(url,label):
    """Reject explicitly general attachments before spending requests or OCR."""
    u=urlsplit(url)
    if u.netloc=='coralbonus.ru' and u.path in GENERAL_CORAL_PATHS:return False
    return not bool(re.search(r'полны[еех]+\s+правил\w*\s+программ|правила\s+программы|'
        r'правила\s+обслуживания|пакет\s+банковских\s+услуг|прейскурант|товары[ -]исключения',label,re.I))


def row_exclusion(row):
    if not row or not row[0]:return None
    if len(row)<21:raise ValueError('Incomplete parser row for scope classification')
    d=json.loads(row[20] or '{}')
    if not isinstance(d,dict):raise ValueError('Invalid parser details')
    return exclusion_reason(d,row[17],row[3],row[5])


def publication_rows(prepared, source_ids=None):
    result=copy.deepcopy(prepared);kept=[];omitted=Counter()
    reports=result['parser_coverage']
    if source_ids is None:
        source_ids={r[0]:reports[0][2] for r in result['parser_offers']} if len(reports)==1 else {}
    for row in result['parser_offers']:
        reason=row_exclusion(row)
        if reason:
            if row[0] not in source_ids:raise ValueError('Scope exclusion has no source report')
            omitted[source_ids[row[0]]]+=1
        else:kept.append(row)
    result['parser_offers']=kept
    for report in reports:
        count=omitted[report[2]]
        if not count:continue
        original=report[9]
        try:original=json.loads(original)
        except (ValueError,TypeError):pass
        report[9]=json.dumps({'source_coverage':original,'publication_scope':VERSION,
            'normalized_before_scope':int(report[7]),'omitted_bulk_records':count,
            'omission_is_not_source_failure':True},ensure_ascii=False,sort_keys=True)
        report[7]=str(int(report[7])-count)
        if report[7]=='0':report[5]='out_of_scope'
    return result


def select_inputs(inputs):
    kept=[];excluded=Counter()
    for r in inputs:
        reason=exclusion_reason(r.get('details',{}),r.get('source_url') or '',r.get('title',''),r.get('kind','')) if r['origin']=='parser_offers' else None
        if reason:excluded[reason]+=1
        else:kept.append(r)
    return kept,dict(excluded)
