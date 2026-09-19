"""Validate a finite, anonymous public-browser capture; never call the private API.

Collection is manual until the main-origin robots transport is accepted. Root and
rubric pagination are independently reconciled. UI labels are not entitlements.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from bs4 import BeautifulSoup
from normalized import make_offer, text, normalize_rates

SOURCE = 'konsierge_public'
PROGRAM = 'Konsierge — публичные привилегии'
ROOT = 'https://konsierge.com/benefits'
METHOD = 'konsierge_public_browser_capture_v1'
ITEM_KEYS = {'id','name','offer','link','description','enabled','date_of_expiry',
             'date_of_release','created_at','updated_at','rubrics'}
WARNINGS = ['user_eligibility_not_verified','only_assist_equivalence_not_asserted',
            'public_website_response_not_customer_account','full_description_scope_requires_review',
            'manual_capture_not_recurring_collection','source_cache_age_not_provided']


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def require(ok, reason):
    if not ok: raise ValueError('konsierge_' + reason)


def stamp(value):
    d = datetime.fromisoformat(value.replace('Z','+00:00'))
    require(d.tzinfo is not None,'naive_timestamp')
    return d


def category_id(url):
    if url == ROOT: return None
    u = urlsplit(url); q = parse_qs(u.query)
    require(u.scheme == 'https' and u.netloc == 'konsierge.com' and u.path == '/benefits'
            and not u.fragment and set(q) == {'rubric_id'} and len(q['rubric_id']) == 1
            and re.fullmatch(r'[1-9]\d*',q['rubric_id'][0]),'category_url')
    return int(q['rubric_id'][0])


def item_fields(item):
    require(set(item) == ITEM_KEYS,'item_fields')
    require(type(item['id']) is int and item['id'] > 0 and type(item['enabled']) is bool,'item_identity')
    for key in ('name','offer','description'):
        require(isinstance(item[key],str) and 0 < len(item[key].strip()) <= 20000,'missing_or_large_'+key)
        require(not re.search(r'<(?:script|iframe|style|form)\b',item[key],re.I),'active_markup')
    require(item['link'] is None or isinstance(item['link'],str),'link_type')
    require(isinstance(item['rubrics'],list),'item_rubrics')
    ids = [x['id'] for x in item['rubrics'] if isinstance(x,dict) and set(x) == {'id'}]
    require(len(ids) == len(item['rubrics']) and len(set(ids)) == len(ids)
            and all(type(x) is int and x > 0 for x in ids),'item_rubric_ids')
    for key in ('date_of_expiry','date_of_release','created_at','updated_at'):
        if item[key] is not None: stamp(item[key])
    return {**item,'rubrics':sorted(ids)}


def redemption(description):
    # Keep whole source paragraphs, not generated instructions. Full limitations
    # always remain in conditions, including those outside these paragraphs.
    return text('\n\n'.join(p for p in description.split('\n\n') if re.search(
        r'консьерж|промокод|кодово|воспользова|бронирован|предъяв|оформлен|заказ',p,re.I)))


def code_words(description):
    result = []
    for m in re.finditer(r'кодово\w*\s+слов\w*\s+[«\"“]?([A-Za-zА-Яа-яЁё0-9]+(?:[-–][A-Za-zА-Яа-яЁё0-9]+)*)',description,re.I):
        value = {'value':m[1],'evidence':m[0]}
        if value not in result: result.append(value)
    return result


def derived(item, observed_at):
    item_fields(item)
    body = text(item['description']); warnings = list(WARNINGS)
    dates = sorted({datetime.strptime(m,'%d.%m.%Y').date().isoformat()
                    for m in re.findall(r'\bдо\s+(\d{2}\.\d{2}\.\d{4})',body)})
    end = dates[0] if len(dates) == 1 else None
    expiry = stamp(item['date_of_expiry']) if item['date_of_expiry'] else None
    conflict = bool(expiry and end and abs((expiry.date()-datetime.fromisoformat(end).date()).days) > 1)
    if conflict:
        warnings.append('source_expiry_conflicts_with_description'); end = None
    if expiry:
        body += '\n\nСлужебное поле date_of_expiry (UTC): ' + item['date_of_expiry']
        warnings.append('source_expiry_timestamp_not_customer_timezone')
        if expiry < stamp(observed_at): warnings.append('source_expiry_timestamp_elapsed')
    if not item['enabled']: warnings.append('source_disabled')
    link = item['link']
    if link and (urlsplit(link).scheme not in ('https','http') or not urlsplit(link).hostname):
        warnings.append('source_link_placeholder_not_followed')
    if not end: warnings.append('customer_validity_not_established')
    label = text(item['offer'])
    label_rates = normalize_rates(label)
    detail_rates = normalize_rates(item['description'])
    if label_rates and detail_rates and not any(x['value']==label_rates[0]['value'] for x in detail_rates):
        warnings.append('card_label_rate_not_confirmed_in_detail')
    return label,body,redemption(item['description']),end,warnings,code_words(item['description'])


def validate_record(row):
    d = row.get('details',{}); item = d.get('public_item',{})
    label,body,activation,end,warnings,words = derived(item,row['observed_at'])
    require(row['source_id'] == SOURCE and row['native_id'] == str(item['id'])
            and row['program'] == PROGRAM and row['partner_name'] == text(item['name'])
            and row['title'] == text(item['name']) and row['record_kind'] == 'partner_offer'
            and row['source_url'] == ROOT and row['link_kind'] == 'page_block'
            and row['benefit_url'] is None and row['locator'] == 'public benefit id='+str(item['id'])
            and row['source_status'] == 'public_catalogue_terms_unverified_eligibility'
            and row['benefit_text'] == label and row['conditions_text'] == body
            and row['redemption_text'] == activation and row['valid_from'] is None
            and row['valid_until'] == end,'record_fields')
    require(d.get('retrieval_method') == METHOD and d.get('only_assist_equivalence') is False
            and d.get('code_words') == words and d.get('item_sha256') == digest(item)
            and set(warnings).issubset(row['warnings']),'record_evidence')
    require(re.fullmatch(r'[a-f0-9]{64}',d.get('capture_sha256',''))
            and re.fullmatch(r'\d+:\d+',d.get('source_run','')),'capture_identity')
    cats = d.get('public_categories',[])
    require(len({x['id'] for x in cats}) == len(cats)
            and all(x['id'] in [r['id'] for r in item['rubrics']] and category_id(x['url']) == x['id'] for x in cats)
            and row['category'] == (' / '.join(x['name'] for x in cats) or None),'record_categories')


def parse_capture(report, directory, source_run):
    require(report.get('one_off_public_ui_inspection') is True and report.get('source_account_login') is False
            and report.get('direct_api_requests') == 0 and report.get('credential_values_read_or_replayed') is False
            and report.get('published') is False and not report.get('errors'),'capture_not_accepted')
    observed = stamp(report['observed_at'])
    require(re.fullmatch(r'\d+:\d+',source_run),'source_run')
    rubrics = report['rubrics']; names = {r['id']:text(r['name']) for r in rubrics}
    require(1 <= len(names) == len(rubrics) <= 32 and all(type(k) is int and k>0 and v for k,v in names.items()),'rubric_inventory')
    catalogues = {category_id(c['url']):c for c in report['catalogues']}
    require(len(catalogues) == len(report['catalogues']) and set(catalogues) == {None,*names},'category_coverage')
    pages = {k:[] for k in catalogues}
    for p in report['network_pages']:
        q=p['query']; rid=int(q['rubric_id']) if 'rubric_id' in q else None
        require(rid in pages and p['status']==200 and p['path']=='/api/client/v1/benefits'
                and set(q).issubset({'rubric_id','page','per'}) and q.get('per')=='12','native_page_route')
        require(observed <= stamp(p['received_at']) <= observed+timedelta(minutes=20),'response_time')
        pages[rid].append(p)
    inventories={}; memberships={}
    for rid, ps in pages.items():
        ps.sort(key=lambda p:p['page']['current_page'])
        require(ps and len(ps) <= 50,'page_budget')
        total=ps[0]['page']['total_count']; all_items=[]
        require(type(total) is int and 0 < total <= 500,'total_count')
        for index,p in enumerate(ps,1):
            m=p['page']; last=index==len(ps)
            require(m['current_page']==index and int(p['query']['page'])==index and m['total_pages']==len(ps)
                    and m['total_count']==total and m['count']==len(p['items'])
                    and m['next_page']==(None if last else index+1)
                    and 0<len(p['items'])<=12 and (last or len(p['items'])==12),'pagination_contract')
            all_items.extend(p['items'])
        ids=[i['id'] for i in all_items]
        require(len(ids)==len(set(ids))==total,'duplicate_or_missing_item')
        inventories[rid]={i['id']:item_fields(i) for i in all_items}
        c=catalogues[rid]
        require(c['scroll_stop']=='native_last_page_and_count' and c['native_item_count']==total
                and c['native_pages']==len(ps) and len(c['cards'])==total,'dom_count')
        require(re.fullmatch(r'(?:all|rubric-\d+)\.html',c['file']),'dom_filename')
        raw=(Path(directory)/c['file']).read_bytes()
        require(hashlib.sha256(raw).hexdigest()==c['sha256'],'dom_hash')
        nodes=BeautifulSoup(raw,'html.parser').select('qy-benefit-teaser')
        require(len(nodes)==total,'dom_nodes')
        for item,card,node in zip(all_items,c['cards'],nodes):
            title=node.select_one('.BenefitTeaser-Title'); offer=node.select_one('.BenefitTeaser-OfferText')
            require(title is not None and offer is not None and text(title.get_text(' ',strip=True))==text(item['name'])==card['name']
                    and text(offer.get_text(' ',strip=True))==text(item['offer'])==card['offer'],'dom_item')
            if rid is not None: memberships.setdefault(item['id'],[]).append(rid)
    root=inventories[None]
    for rid, items in inventories.items():
        if rid is None: continue
        require(set(items)=={i for i,v in root.items() if rid in v['rubrics']},'rubric_membership')
        require(all(v==root[i] for i,v in items.items()),'cross_category_item_drift')
    rows=[]; sha=digest(report)
    original=[i for p in pages[None] for i in p['items']]
    for item in original:
        label,body,activation,end,warnings,words=derived(item,report['observed_at'])
        cats=[{'id':k,'name':v,'url':ROOT+'?rubric_id='+str(k)} for k,v in names.items() if k in memberships.get(item['id'],[])]
        if not cats: warnings.append('root_only_not_in_public_category_tabs')
        rows.append(make_offer(SOURCE,str(item['id']),PROGRAM,item['name'],label,ROOT,report['observed_at'],
            title=item['name'],conditions=body,redemption=activation,category=' / '.join(x['name'] for x in cats) or None,
            link_kind='page_block',locator='public benefit id='+str(item['id']),valid_until=end,
            source_status='public_catalogue_terms_unverified_eligibility',warnings=warnings,
            details={'retrieval_method':METHOD,'public_item':item,'item_sha256':digest(item),
                     'public_categories':cats,'only_assist_equivalence':False,'code_words':words,
                     'capture_sha256':sha,'source_run':source_run,'_source':{'source_id':SOURCE}}))
    coverage={'source_id':SOURCE,'name':PROGRAM,'root':ROOT,'status':'ok','discovered':len(rows),
              'normalized':len(rows),'failed':0,'coverage':'complete_public_root_and_all_visible_rubrics; manual_capture; eligibility_not_verified',
              'region':None,'errors':[],'observed_at':report['observed_at'],
              'categories':[{'id':k,'name':names[k],'count':len(v)} for k,v in inventories.items() if k is not None],
              'root_only':len(set(root)-set(memberships))}
    return {'schema_version':2,'run_id':source_run,'observed_at':report['observed_at'],'records':rows,'sources':[coverage]}


def project_common(raw,n,benefit,condition,code):
    """Do not promote department-specific rates, commissions or room credits.

    The one headline benefit always links to the complete owned conditions. Rich
    privileges and quoted code words remain searchable, without inventing scope.
    """
    from unified_normalization import digest as common_digest, validate_normalized
    from promo_codes import extract_promocodes
    d=raw['details']; item=d['public_item']
    label,body,activation,end,warnings,words=derived(item,raw['observed_at'])
    require(raw['program']==PROGRAM and raw['partner']==text(item['name']) and raw['title']==text(item['name'])
            and raw['kind']=='partner_offer' and raw['source_url']==ROOT and raw['link_kind']=='page_block'
            and raw['benefit_url'] is None and raw['benefit']==label and raw['conditions']==body
            and raw['activation']==activation and raw['valid_from'] is None and raw['valid_until']==end
            and set(warnings).issubset(raw['source_warnings']) and d['code_words']==words
            and d['only_assist_equivalence'] is False and d['item_sha256']==digest(item),'common_fields')
    require(raw['codes']==extract_promocodes('\n'.join((label,body,activation)))['codes'],'common_codes')
    scope={'public_benefit_id':item['id'],'headline_label_only':True,'eligibility_not_verified':True}
    rules=[condition('owned_partner_rules','/conditions',scope=scope)]
    if activation: rules.append(condition('redemption_instructions','/activation',scope=scope))
    rates=normalize_rates(label)
    if rates:
        require(len(rates)==1,'headline_rate_count')
        r=rates[0]; b=benefit(r['kind'],'/benefit',value=r['value'],unit=r['unit'],qualifier=r['qualifier'],scope=scope)
    else:
        b=benefit('special_privilege','/benefit',scope=scope)
    b.update(condition_ids=[r['id'] for r in rules],condition_linkage='full_owned_record_rules',remaining_record_rules_require_review=True)
    for i,value in enumerate(raw['codes']):code(value,f'/codes/{i}',scope)
    for i,word in enumerate(words):code(word['value'],f'/details/code_words/{i}/value',scope,delivery='code_word')
    for i,delivery in enumerate(d.get('promo_code_delivery',[])):
        code(None,f'/details/promo_code_delivery/{i}/evidence',scope,delivery=delivery['method'])
    n['availability'].update(source_enabled=item['enabled'],source_expiry_utc=item['date_of_expiry'])
    if 'source_expiry_conflicts_with_description' in warnings:n['validity']['status']='source_date_conflict'
    elif 'source_expiry_timestamp_elapsed' in warnings and not end:n['validity']['status']='source_expiry_elapsed_customer_period_unknown'
    n['quality']['level']='structured_with_review'
    n['quality']['issues'].append('headline_not_all_service_rates_full_owned_conditions_required')
    n['content_sha256']=common_digest({k:v for k,v in n.items() if k!='content_sha256'})
    validate_normalized(n)
    return n


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--capture',required=True);p.add_argument('--source-run',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    d=Path(a.capture);r=json.loads((d/'report.json').read_text());b=parse_capture(r,d,a.source_run)
    Path(a.out).write_text(json.dumps(b,ensure_ascii=False,indent=2))
    print(json.dumps({'records':len(b['records']),'coverage':b['sources']},ensure_ascii=False))
