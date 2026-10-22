"""HSE public inventory joined to source-owned anchors or current card headings."""
from __future__ import annotations
import hashlib,json,re
from urllib.parse import urljoin,urlsplit
from datetime import datetime
from bs4 import BeautifulSoup,Comment,Tag
from normalized import make_offer,text,normalize_rates,number
from partner_pages import content
from promo_codes import extract_promocodes,candidate
from model import clean_url

ROOT='https://alumni.hse.ru/loyalty/partners/'
PROGRAM='Карта выпускника НИУ ВШЭ'
# Historical readback only. Live discovery matches current catalogue names;
# this alias preserves the validation of previously published evidence.
UNANCHORED_HEADINGS={'mordapechat':'Морда довольна. Студия печати'}


def heading_matches_name(heading, name):
    """An exact current card name, optionally followed by a delimited descriptor."""
    h=text(heading).casefold();n=text(name).casefold()
    return bool(n) and (h==n or any(h.startswith(n+separator) for separator in ('. ', ': ', ' — ', ' – ')))


def heading_identity(section, names):
    titles={text(h.get_text(' ',strip=True)) for h in section.select('h1,h2,h3')}
    matches=[(key,title) for key,name in names.items() for title in titles if heading_matches_name(title,name)]
    if len(matches)>1:raise ValueError('hse_ambiguous_heading_ownership')
    return matches[0] if matches else None


def source_location(block,full):
    if not isinstance(block,dict) or not re.fullmatch('[A-Za-z0-9_-]{1,100}',block.get('anchor','')):raise ValueError('hse_invalid_block_identity')
    if block.get('identity_method')=='catalogue_heading':
        heading=block.get('detail_heading','')
        if (not full or not heading_matches_name(heading,block.get('name',''))
            or not block['body'].startswith(heading+'\n')):
            raise ValueError('hse_catalogue_heading_identity')
        return ROOT,'page_block','builder-section with catalogue-owned heading '+heading
    # Retained historical records only; current discovery never uses this alias.
    if block.get('identity_method')=='reviewed_heading':
        heading=UNANCHORED_HEADINGS.get(block['anchor'])
        if (not full or not heading or block.get('detail_heading')!=heading
            or not block['body'].startswith(heading+'\n')):
            raise ValueError('hse_unreviewed_heading_identity')
        return ROOT,'page_block','builder-section with exact heading '+heading
    if block.get('identity_method') is not None:raise ValueError('hse_unknown_identity_method')
    return (ROOT+'#'+block['anchor'],'page_anchor','a[name="'+block['anchor']+'"] and following sections before next named anchor') if full else (ROOT,'page_block','.fa-person__name[href ends with #'+block['anchor']+']')

CLAIM=re.compile(r'[сc]\s*кидк|[пp]\s*ромо[ -]?код|бесплат|подар|ключев\w* слов',re.I)
WARNINGS=['source_publication_not_personal_eligibility','linked_partner_sites_not_checked',
          'validity_not_inferred_from_coupon_spelling_or_month_without_year','rates_have_separate_audience_and_product_scopes']


def hse_codes(value,tables=None,*,preview=False):
    """Literal HSE label variants, including a percentage before the code."""
    result=extract_promocodes('' if preview else value,[] if preview else tables)
    label=r'(?:[пp]\s*ромо[ -]?код(?:а|у|ом|ы)?|(?:ключев|кодов)\w*\s+слов\w*)\b'
    if preview:
        if re.search(label,value,re.I):result['status']='mentioned_not_extracted'
        return result
    patterns=[label+r'\s*(?:[:—–-]\s*)?',
              label+r'\s+(?:на\s+)?\d+(?:[.,]\d+)?\s*%\s*[-—–:]?\s*',
              label+r'\s+и\s+скидка\s*:\s*']
    for pattern in patterns:
        for m in re.finditer(pattern,value,re.I):
            code,end=candidate(value,m.end(),value[max(0,m.start()-150):m.start()])
            if code and code not in result['codes']:
                result['codes'].append(code);result['evidence'].append({'code':code,'evidence':value[m.start():end].strip()})
    if result['codes']:result['status']='explicit_codes_extracted'
    elif re.search(label,value,re.I):result['status']='mentioned_not_extracted'
    return result



def hse_rates(value):
    """Published coupon percentages are discounts, not payment prerequisites."""
    rows=[]
    for clause in value.splitlines():
        eligible=[]
        for m in re.finditer(r'(\d+(?:[.,]\d+)?)\s*%',clause):
            if re.match(r'\s*(?:[-—–]\s*)?(?:оплат|предоплат|платеж|аванс)',clause[m.end():],re.I):continue
            if 0<=float(number(m[1]))<=100:eligible.append(m)
        amounts={number(m[1]) for m in eligible}
        parsed=[r for r in normalize_rates(clause) if r['unit']!='percent' or r['value'] in amounts]
        if not parsed and len(eligible)==1 and CLAIM.search(clause):
            m=eligible[0];prefix=clause[max(0,m.start()-12):m.start()]
            # Only the already-owned public benefit clause can supply this type.
            parsed=[{'kind':'discount','value':number(m[1]),'unit':'percent',
                     'qualifier':'up_to' if re.search(r'до\s*$',prefix,re.I) else 'at_least' if re.search(r'от\s*$',prefix,re.I) else 'exact',
                     'basis_amount':None,'basis_unit':None,'evidence':clause}]
        rows.extend(parsed)
    return rows


def explicit_end(body):
    matches=list(re.finditer(r'(?:скидк\w*|предложени\w*)\s+действует\s+до\s+(\d{2}\.\d{2}\.\d{4})(?!\d)',body,re.I))
    dates={m[1] for m in matches}
    if len(dates)>1:raise ValueError('hse_ambiguous_end_dates')
    if matches:return datetime.strptime(matches[0][1],'%d.%m.%Y').date().isoformat(),matches[0][0]
    return None,None


def claim_text(body):
    return '\n'.join(dict.fromkeys(line for line in body.splitlines() if CLAIM.search(line)))


def blocks(raw):
    dom=BeautifulSoup(raw,'html.parser')
    for n in dom.select('script,style,noscript,form,input,textarea,iframe,[hidden],[aria-hidden="true"]'):n.decompose()
    for n in dom.find_all(string=lambda s:isinstance(s,Comment)):n.extract()
    roots=dom.select('.post__text.builder_content')
    if len(roots)!=1:raise ValueError('hse_programme_body')
    root=roots[0];cards=root.select('.fa-person__item')
    if not 1<=len(cards)<=200:raise ValueError('hse_card_count')
    names={}
    for item in cards:
        for label in item.select('.fa-person__name'):
            target=urlsplit(urljoin(ROOT,label.get('href','').strip()))
            if target.fragment:names[target.fragment]=text(label.get_text(' ',strip=True))
    # Reserve explicit-anchor sections before considering heading-only joins.
    # The first nonempty section after an anchor belongs to that anchor even
    # when its shorter display title also matches a different catalogue card.
    explicit_parts={};reserved=set()
    for anchor in names:
        targets=root.find_all('a',attrs={'name':anchor})
        if len(targets)>1:raise ValueError('hse_duplicate_target')
        if not targets:continue
        owner=targets[0].find_parent('div',class_='builder-section')
        if owner is None or owner.parent is not root:raise ValueError('hse_anchor_owner')
        if len(owner.select('a[name]'))!=1:raise ValueError('hse_anchor_ambiguous')
        parts=[owner] if text(owner.get_text(' ',strip=True)) else []
        for node in owner.next_siblings:
            if not isinstance(node,Tag):continue
            if node.select('a[name]') or node.select('.nom h1'):break
            if node.select('.fa-person__item'):raise ValueError('hse_detail_reentered_inventory')
            if not text(node.get_text(' ',strip=True)):continue
            if parts:
                try:owned=heading_identity(node,names)
                except ValueError:break  # An ambiguous next heading is a boundary.
                if owned and owned[0]!=anchor:break
            parts.append(node)
        explicit_parts[anchor]=parts
        reserved.update(id(node) for node in parts)
    # A named section not in today's catalogue is still not ownerless. Never
    # use it to fill an unrelated card whose explicit anchor is missing.
    for marker in root.select('a[name]'):
        if marker.get('name') in names:continue
        owner=marker.find_parent('div',class_='builder-section')
        if owner is None or owner.parent is not root:continue
        reserved.add(id(owner))
        for node in owner.next_siblings:
            if not isinstance(node,Tag):continue
            if node.select('a[name]') or node.select('.nom h1'):break
            reserved.add(id(node))
    seen=set();result=[]
    for card in cards:
        labels=card.select('.fa-person__name');summaries=card.select('.fa-person__info')
        group=card.find_parent(class_='fa-card__group')
        headings=group.select('.builder-section__title') if group else []
        if len(labels)!=1 or len(summaries)!=1 or len(headings)!=1:raise ValueError('hse_card_fields')
        label=labels[0];name=text(label.get_text(' ',strip=True));summary=text(summaries[0].get_text(' ',strip=True))
        u=urlsplit(urljoin(ROOT,label.get('href','').strip()))
        if (u.scheme!='https' or u.netloc!='alumni.hse.ru' or u.path!=urlsplit(ROOT).path or u.query
            or not re.fullmatch('[A-Za-z0-9_-]{1,100}',u.fragment) or not name or not summary):raise ValueError('hse_card_identity')
        anchor=u.fragment
        if anchor in seen:raise ValueError('hse_duplicate_card')
        seen.add(anchor)
        parts=[];state='missing_anchor';identity={}
        if anchor in explicit_parts:
            parts=explicit_parts[anchor]
            state='detail' if parts else 'empty_section'
        else:
            matches=[];ambiguous=False
            for node in root.find_all('div',class_='builder-section',recursive=False):
                if id(node) in reserved or node.select('a[name],.fa-person__item,.nom h1'):continue
                titles={text(h.get_text(' ',strip=True)) for h in node.select('h1,h2,h3')}
                candidates=[(key,title) for key,name in names.items() for title in titles
                            if heading_matches_name(title,name)]
                own=[title for key,title in candidates if key==anchor]
                if not own:continue
                if len(candidates)!=1:ambiguous=True
                else:matches.append((node,own[0]))
            if ambiguous or len(matches)>1:
                state='ambiguous_heading'
            elif matches:
                node,heading=matches[0];parts=[node];state='detail'
                identity={'identity_method':'catalogue_heading','detail_heading':heading}
        body=content(parts) if parts else '';links=[]
        if len(body)>12000:raise ValueError('hse_detail_size')
        for part in parts:
            for link in part.select('a[href]'):
                try:target=clean_url(urljoin(ROOT,link['href'].strip()))
                except (ValueError,TypeError):continue
                item={'label':text(link.get_text(' ',strip=True)),'url':target}
                if item not in links:links.append(item)
        result.append({'anchor':anchor,'name':name,'category':text(headings[0].get_text(' ',strip=True)),
                       'summary':summary,'body':body,'links':links,'detail_state':state,**identity})
    return result


def block_hash(block):
    return hashlib.sha256(json.dumps(block,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def parse_catalog(raw,observed_at):
    rows=[]
    for block in blocks(raw):
        full=block['detail_state']=='detail';warnings=WARNINGS.copy()
        if not full:warnings.append('catalogue_preview_not_full_detail')
        benefit=claim_text(block['body']) if full else ''
        end,end_evidence=explicit_end(block['body']) if full else (None,None)
        month_limited=[line for line in block['body'].splitlines() if re.search(r'только в (?:январ|феврал|март|апрел|ма[ейя]|июн|июл|август|сентябр|октябр|ноябр|декабр)',line,re.I)]
        if month_limited:warnings.append('contains_month_limited_suboffer_not_universal_rate')
        if full and not benefit:warnings.append('benefit_clause_not_structurally_extracted')
        source_url,link_kind,locator=source_location(block,full)
        rows.append(make_offer('hse_alumni','anchor:'+block['anchor'],PROGRAM,block['name'],benefit,
            source_url,observed_at,title=block['name'],category=block['category'],
            conditions=block['body'] if full else block['summary'],redemption=block['body'] if full else '',
            link_kind=link_kind,locator=locator,
            record_kind='partner_offer' if full else 'source_observation',valid_until=end,
            source_status='public_hse_partner_detail' if full else 'public_hse_preview_detail_missing',
            details={'public_catalog_block':block,'source_block_sha256':block_hash(block),
                     'scope':'only_cards_in_current_public_partner_inventory','detail_read':full,
                     'validity_evidence':end_evidence,'month_limited_clauses':month_limited,
                     'source_account_used':False,'user_eligibility_verified':False,'linked_terms_checked':False},warnings=warnings))
    return rows


def validate_record(r):
    b=r['details'].get('public_catalog_block',{});full=b.get('detail_state')=='detail'
    source_url,link_kind,locator=source_location(b,full)
    if (not re.fullmatch('[A-Za-z0-9_-]{1,100}',b.get('anchor','')) or r['native_id']!='anchor:'+b['anchor']
        or r['program']!=PROGRAM or r['partner_name']!=b.get('name') or r['title']!=b.get('name')
        or r['category']!=b.get('category') or r['benefit_text']!=(claim_text(b['body']) if full else '')
        or r['conditions_text']!=text(b['body'] if full else b['summary'])
        or r['source_url']!=source_url
        or r['benefit_url']!=(source_url if link_kind=='page_anchor' else None)
        or r['link_kind']!=link_kind or r['locator']!=locator
        or r['redemption_text']!=text(b['body'] if full else '')
        or r['valid_from'] is not None or r['valid_until']!=(explicit_end(b['body'])[0] if full else None)
        or r['details'].get('user_eligibility_verified') is not False
        or r['record_kind']!=('partner_offer' if full else 'source_observation')
        or r['source_status']!=('public_hse_partner_detail' if full else 'public_hse_preview_detail_missing')
        or r['details'].get('source_block_sha256')!=block_hash(b)
        or r['details'].get('detail_read') is not full or r['details'].get('source_account_used') is not False
        or r['details'].get('linked_terms_checked') is not False or not set(WARNINGS).issubset(r['warnings'])):
        raise ValueError('hse_evidence_or_scope_mismatch')


async def collect_hse(client,cfg,report,observed_at,limit):
    if cfg['id']!='hse_alumni' or cfg['url']!=ROOT:raise ValueError('hse_unconfigured_source')
    raw=await client.read(ROOT,render=True);rows=parse_catalog(raw,observed_at)
    missing=[r['details']['public_catalog_block']['anchor'] for r in rows if r['record_kind']=='source_observation']
    report['discovered']=len(rows)
    report['coverage']=json.dumps({'catalogue_cards':len(rows),'detail_records':len(rows)-len(missing),
        'preview_only':len(missing),'missing_detail_anchors':missing,'scope':'one_public_inventory_and_its_owned_sections',
        'all_listed_cards_represented':len(rows)<=limit,'unlisted_detail_anchors_not_imported':True},ensure_ascii=False)
    if missing:report['errors'].append({'phase':'detail','reason':'source_has_missing_or_empty_detail_sections','anchors':missing})
    if len(rows)>limit:report['errors'].append({'phase':'extraction','reason':'record_limit'})
    return rows[:limit]
