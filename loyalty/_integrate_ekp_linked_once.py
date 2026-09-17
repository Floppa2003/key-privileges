"""One-time branch integration; removed before release, never a collector input."""
import hashlib
from pathlib import Path

EXPECTED={'normalized.py':'42dade01330677df1607306cb666d28004e8d53f',
          'unified_normalization.py':'2c12d69984fa6b4d5de75123507dcc7725eb68e7',
          'ekp_linked_rules.py':'9876985769b3b2139726b82951b26c0425475f9a'}
files={}
for name,expected in EXPECTED.items():
    path=Path('loyalty')/name;data=path.read_bytes()
    assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==expected,name
    files[name]=data.decode()
def replace(name,old,new):
    assert files[name].count(old)==1,(name,old)
    files[name]=files[name].replace(old,new)

replace('normalized.py',"HOSTS['ekp']=['ekp.spb.ru']", "HOSTS['ekp']=['ekp.spb.ru']\nHOSTS['ekp_linked_rules']=['ekp.spb.ru','xn--b1abfnwkklk1gdn5a.xn--p1ai','mpclinic.ru','vamprivet.ru']")
replace('normalized.py',"    if r['source_id']=='coral_rule_documents':", "    if r['source_id']=='ekp_linked_rules':\n        from ekp_linked_rules import validate_record\n        validate_record(r)\n    if r['source_id']=='coral_rule_documents':")
replace('unified_normalization.py',"    if d.get('retrieval_method')=='rzd_external_direct_v1':", """    if d.get('retrieval_method')=='ekp_source_linked_rules_v1':
        if raw['kind'] not in ('program_rules','source_observation') or not d.get('parent_references'):
            raise ValueError('EKP linked rules provenance missing')
        if not d.get('live_document_text') and d.get('public_rule_text')!=raw.get('conditions'):
            raise ValueError('EKP linked HTML text mismatch')
        condition('linked_source_rules','/conditions',scope={'parent_references':d['parent_references'],
                  'document_part':d.get('document_part'),'applicability_requires_parent_offer_review':True})
        n['quality']['issues'].append('linked_rules_no_automatic_benefits_or_codes')
        n['content_sha256']=digest({k:v for k,v in n.items() if k!='content_sha256'})
        validate_normalized(n);return n
    if d.get('retrieval_method')=='rzd_external_direct_v1':""")
replace('ekp_linked_rules.py','MAX_CREDITS=200','MAX_CREDITS=400')
replace('ekp_linked_rules.py','self.free_checked=False','self.free_checked=False;self.provider_halted=False;self.delays={}')
replace('ekp_linked_rules.py',"            if provider:\n                if not self.key:","            if provider:\n                if self.provider_halted:raise ValueError('el_provider_stopped')\n                if not self.key:")
replace('ekp_linked_rules.py',"            item['error']=code;raise ValueError(code) from None", "            if provider and code in ('el_provider_auth_quota','el_unknown_credit_cost','el_credential_echo','el_rate_limit'):\n                self.provider_halted=True\n            item['error']=code;raise ValueError(code) from None")
replace('ekp_linked_rules.py',"self.next_at[host]=time.monotonic()+3", "self.next_at[host]=time.monotonic()+self.delays.get(host,3)")
replace('ekp_linked_rules.py',"                body=robots_document(raw.decode('utf8'))", "                try:body,_=robots_document(200,raw.decode('utf8'))\n                except (RuntimeError,UnicodeError):raise ValueError('el_policy_unreadable') from None")
replace('ekp_linked_rules.py',"        host=urlsplit(url).hostname;self.next_at[host]=max(self.next_at.get(host,0),time.monotonic()+delay)", "        host=urlsplit(url).hostname;self.delays[host]=delay\n        self.next_at[host]=max(self.next_at.get(host,0),time.monotonic()+delay)")
replace('ekp_linked_rules.py',"    if (clock-instant(audit['started_at'])).total_seconds()>7200 or audit['reserved']>MAX_CREDITS:raise ValueError('el_freshness_or_budget')", """    if (clock-instant(audit['started_at'])).total_seconds()>7200 or not 0<=audit['reserved']<=MAX_CREDITS:
        raise ValueError('el_freshness_or_budget')
    if audit.get('source_account_used') is not False or len(audit['requests'])>40:
        raise ValueError('el_privacy_or_request_budget')
    if sum(r.get('reserved_credits',0) for r in audit['requests'])!=audit['reserved']:
        raise ValueError('el_reservation_mismatch')
    for receipt in audit['requests']:
        checked_url(receipt['url'])
        if not instant(audit['started_at'])<=instant(receipt['requested_at'])<=instant(receipt['finished_at'])<=instant(audit['finished_at']):
            raise ValueError('el_receipt_time')
        if not 0<=receipt.get('charged_credits',0)<=receipt.get('reserved_credits',0):
            raise ValueError('el_charge_mismatch')""")
replace('ekp_linked_rules.py',"        data=(Path(folder)/'objects'/result['file']).read_bytes()", """        target=entry['url'];visited=set()
        for _ in range(3):
            if target==result['receipt'].get('url'):break
            if target in visited:raise ValueError('el_redirect_loop')
            visited.add(target)
            hops=[r['redirect'] for r in audit['requests'] if r['url']==target and r.get('redirect')]
            if len(set(hops))!=1:raise ValueError('el_unbound_receipt')
            target=checked_url(hops[0])
            if urlsplit(target).hostname!=urlsplit(entry['url']).hostname:raise ValueError('el_foreign_redirect')
        else:raise ValueError('el_unbound_receipt')
        data=(Path(folder)/'objects'/result['file']).read_bytes()""")
replace('ekp_linked_rules.py',"            if doc['document_sha256']!=sha(data):raise ValueError('el_pdf_hash')", """            if doc['document_sha256']!=sha(data):raise ValueError('el_pdf_hash')
            import io
            from pypdf import PdfReader
            count=len(PdfReader(io.BytesIO(data),strict=True).pages)
            if doc['page_count']!=count or [p['number'] for p in doc['pages']]!=list(range(1,count+1)):
                raise ValueError('el_pdf_page_identity')
            if doc['ocr_pages']!=sum(p['method']=='ocr_unverified' for p in doc['pages']):
                raise ValueError('el_ocr_page_count')
            if any(p['sha256']!=sha(p['text'].encode()) for p in doc['pages']):raise ValueError('el_pdf_page_hash')""")
contract='''
def validate_record(r):
    d=r['details'];url=checked_url(r['source_url']);parents=d.get('parent_references',[])
    if (r['source_id']!=SID or d.get('retrieval_method')!=METHOD or not parents or len(parents)>200
        or r['record_kind'] not in ('program_rules','source_observation') or r['rates'] or r['tables']
        or r['valid_from'] is not None or r['valid_until'] is not None
        or any(d.get(k) is not False for k in ('source_account_used','eligibility_verified','recursive_links_read'))):
        raise ValueError('el_record_scope')
    for parent in parents:
        if (parent.get('source_url')!='https://ekp.spb.ru/api/portal/loyalty/partners'
            or checked_url(parent.get('original_link'))!=url
            or not re.fullmatch('[a-f0-9]{64}',parent.get('record_id',''))
            or not re.fullmatch('[a-f0-9]{64}',parent.get('content_sha256',''))
            or parent.get('field') not in ('loyaltyDescription','discountScheme')
            or instant(parent['observed_at'])>instant(r['observed_at'])):
            raise ValueError('el_parent_binding')
    names=sorted({p['partner'] for p in parents})
    if r['partner_name']!=(names[0] if len(names)==1 else None):raise ValueError('el_partner_binding')
    if not d.get('live_document_text'):
        if (r['native_id']!='html:'+sha(url.encode()) or r['conditions_text']!=d.get('public_rule_text')
            or r['benefit_text'] or r['source_status']!='public_linked_rules_text'):
            raise ValueError('el_html_binding')
    elif not r['native_id'].startswith('pdf:'+sha(url.encode())):
        raise ValueError('el_pdf_binding')

'''
replace('ekp_linked_rules.py','def main():',contract+'def main():')
for name,value in files.items():(Path('loyalty')/name).write_text(value)
print('Applied three exact, reviewable code changes; no source or destination credentials used.')
