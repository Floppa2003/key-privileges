"""Source-linked public Coral rules, separate from offers and monetary benefits.

Only links in freshly read parent conditions can seed traversal. One document
can have several parent references; no values or eligibility are copied back.
"""
from __future__ import annotations
import re
from urllib.parse import urljoin,urlsplit
from bs4 import BeautifulSoup
import coral_catalog as c
from normalized import make_offer,text
from practical_scope import follow_document_link

SOURCE_ID='coral_rule_documents'
METHOD='coral_linked_public_rules_google_import_v1'
MAX_RULES=12
WARNINGS=['supplementary_rules_not_additional_discount','google_import_not_original_http_response',
          'origin_cache_age_not_exposed','rule_effective_date_not_offer_validity',
          'linked_documents_and_images_not_read','user_eligibility_not_verified']


def is_rule_url(value):
    if not isinstance(value,str) or len(value)>500:return False
    u=urlsplit(value)
    return (u.scheme=='https' and u.netloc=='coralbonus.ru' and not u.query and not u.fragment
            and re.fullmatch(r'/(?:pravila|poryadok)-[a-z0-9-]{1,200}/',u.path) is not None)


def discover(records):
    found={}
    for r in records:
        if r['source_id'] not in ('coral','coral_promo'):continue
        for link in r['details']['public_coral_block']['links']:
            url=link['url']
            if not is_rule_url(url) or not follow_document_link(url,link['label']):continue
            entry=found.setdefault(url,{'url':url,'parents':[]})
            parent={'record_id':r['id'],'source_url':r['source_url'],'title':r['title'],
                    'content_sha256':r['content_sha256'],'label':link['label']}
            if parent not in entry['parents']:entry['parents'].append(parent)
    if len(found)>MAX_RULES*10:raise ValueError('cg_rule_discovery_bound')
    return [found[url] for url in sorted(found)]


def source_fields(raw,url):
    if not is_rule_url(url):raise ValueError('cg_rule_url')
    soup=BeautifulSoup(raw,'html.parser')
    # The shared sanitizer validates the original canonical before removing
    # rel attributes. Require its exact retained head link, not a body link.
    if not any(n.get('href')==url for n in soup.select('head link[href]')):
        raise ValueError('cg_rule_canonical')
    headings=soup.select('h1')
    if len(headings)!=1:raise ValueError('cg_rule_heading')
    h=headings[0];title=text(h.get_text(' ',strip=True));section=h.find_parent('section')
    if section is None or not re.match(r'^(?:Правила|Порядок)\b',title,re.I):raise ValueError('cg_rule_article')
    # Both reviewed layouts have one heading-owned section: an article or the
    # programme contract's container. Header/footer and forms are not conditions.
    for n in section.select('script,style,noscript,form,input,textarea,iframe,button,header,footer,nav'):
        n.decompose()
    for br in section.select('br'):br.replace_with('\n')
    body=text(section.get_text('\n',strip=True))
    if (not 80<=len(body)<=35000 or len(title)>300 or '{{' in body
        or re.search(r'captcha|access denied|игнорируй предыдущие инструкции|ignore previous instructions',body,re.I)):
        raise ValueError('cg_rule_content')
    tables=[]
    for table in section.select('table'):
        cells=[[text(td.get_text(' ',strip=True)) for td in tr.select(':scope > th,:scope > td')] for tr in table.select('tr')]
        tables.append([row for row in cells if row])
    links=[]
    for a in section.select('a[href]'):
        value=urljoin(url,a['href']);u=urlsplit(value)
        if u.scheme!='https' or u.username or u.password or u.query or u.fragment:continue
        link={'label':text(a.get_text(' ',strip=True)),'url':value}
        if link not in links:links.append(link)
    return {'title':title,'text':body,'tables':tables,'unread_links':links}


def map_rule(obs,entry,observed_at):
    from coral_import import checked,digest
    if obs['url']!=entry['url']:raise ValueError('cg_rule_source_identity')
    p=source_fields(checked(obs),obs['url'])
    return make_offer(SOURCE_ID,'rule:'+urlsplit(obs['url']).path,'CoralBonus — Правила',None,'',obs['url'],observed_at,
        title=p['title'],conditions=p['text'],record_kind='program_rules',source_status='public_linked_rules_text',
        locator='heading-owned section',warnings=list(WARNINGS),
        details={'retrieval_method':METHOD,'public_rule':p,'public_rule_sha256':digest(p),
            'parent_references':entry['parents'],'evidence_role':'supplementary_rules_not_incremental_discount',
            'import_observation':{k:v for k,v in obs.items() if k!='text'},
            'origin_http_status':None,'origin_cache_age_verified':False,'account_used':False,
            'coupon_issued':False,'full_eligibility_verified':False,'recursive_links_read':False})


def validate_record(r):
    from coral_import import digest,formula,instant
    d=r.get('details',{});p=d.get('public_rule',{});o=d.get('import_observation',{})
    if (d.get('retrieval_method')!=METHOD or set(p)!={'title','text','tables','unread_links'}
        or d.get('public_rule_sha256')!=digest(p) or d.get('evidence_role')!='supplementary_rules_not_incremental_discount'):
        raise ValueError('cg_rule_evidence')
    if (not is_rule_url(r['source_url']) or r['source_id']!=SOURCE_ID
        or r['native_id']!='rule:'+urlsplit(r['source_url']).path or r['program']!='CoralBonus — Правила'
        or r['title']!=p['title'] or r['conditions_text']!=p['text'] or r['partner_name'] is not None
        or r['benefit_text'] or r['redemption_text'] or r['rates'] or r['tables']
        or r['record_kind']!='program_rules' or r['source_status']!='public_linked_rules_text'
        or r['benefit_url']!=r['source_url'] or r['link_kind']!='detail_page' or r['locator']!='heading-owned section'
        or r['valid_from'] is not None or r['valid_until'] is not None or not set(WARNINGS)<=set(r['warnings'])):
        raise ValueError('cg_rule_binding')
    if (set(o)!={'url','requested_at','calculated_at','formula_sha256','typed_lines_sha256','sha256'}
        or o['url']!=r['source_url'] or o['formula_sha256']!=digest(formula(o['url']))
        or not all(re.fullmatch('[a-f0-9]{64}',o[k]) for k in ('sha256','typed_lines_sha256'))
        or not instant(r['observed_at'])<=instant(o['requested_at'])<=instant(o['calculated_at'])
        or (instant(o['calculated_at'])-instant(o['requested_at'])).total_seconds()>180):
        raise ValueError('cg_rule_observation')
    parents=d.get('parent_references')
    if not isinstance(parents,list) or not 1<=len(parents)<=100:raise ValueError('cg_rule_parents')
    for parent in parents:
        if (set(parent)!={'record_id','source_url','title','content_sha256','label'}
            or not all(isinstance(v,str) for v in parent.values())
            or not re.fullmatch('[a-f0-9]{64}',parent['record_id'])
            or not re.fullmatch('[a-f0-9]{64}',parent['content_sha256']) or not parent['title']):
            raise ValueError('cg_rule_parent_identity')
        prefix,depth=('/klub-privilegii/',3) if parent['source_url'].startswith(c.CLUB) else ('/promo/',2)
        c.checked_url(parent['source_url'],prefix,depth)
    if (d.get('origin_http_status') is not None
        or any(d.get(k) is not False for k in ('origin_cache_age_verified','account_used','coupon_issued','full_eligibility_verified','recursive_links_read'))):
        raise ValueError('cg_rule_promotion')
