"""Live Utair support article, scoped leaf records rather than a full catalog."""
from __future__ import annotations
import asyncio
import hashlib
import json
import time
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from model import clean_url
from normalized import make_offer, text
from read_budget import within_source_budget

ROOT='https://www.utair.ru/support/2/kakiye_partnery_est_u_utair_status'
ARTICLE='[class*="SupportWidgets_content"]'


def own_label(tab):
    labels=[n for n in tab.select('.tab-label') if n.find_parent(class_='accordion-tab') is tab]
    if len(labels)!=1:raise ValueError('utair_leaf_label_ambiguous')
    return text(labels[0].get_text(' ',strip=True))


def article_blocks(raw):
    soup=BeautifulSoup(raw,'html.parser')
    articles=soup.select(ARTICLE);headings=soup.select('h1')
    if len(articles)!=1 or len(headings)!=1 or 'Utair Status' not in headings[0].get_text():
        raise ValueError('utair_support_article_not_ready')
    article=articles[0];blocks=[];identities=set()
    for tab in article.select('.accordion-tab'):
        if tab.select_one('.accordion-tab'):continue
        label=own_label(tab)
        contents=tab.find_all(class_='tab-content',recursive=False)
        if not label or len(contents)!=1:raise ValueError('utair_leaf_structure_changed')
        content=BeautifulSoup(str(contents[0]),'html.parser')
        for node in content.select('script,style,form,input,textarea,iframe'):node.decompose()
        body=text(content.get_text(' ',strip=True))
        if not body:raise ValueError('utair_leaf_text_missing')
        ancestors=[]
        for parent in tab.parents:
            if parent is article:break
            if 'accordion-tab' in parent.get('class',[]):ancestors.append(own_label(parent))
        path=list(reversed(ancestors));identity=json.dumps([path,label],ensure_ascii=False)
        if identity in identities:raise ValueError('utair_duplicate_leaf_identity')
        identities.add(identity);links=[];rejected=0
        for a in content.select('a[href]'):
            try:target=clean_url(urljoin(ROOT,a['href']))
            except (ValueError,TypeError):rejected+=1;continue
            link={'label':text(a.get_text(' ',strip=True)),'url':target}
            if link not in links:links.append(link)
        blocks.append({'section_path':path,'title':label,'text':body,'links':links,
                       'rejected_links':rejected,'native_id':'leaf:'+hashlib.sha256(identity.encode()).hexdigest()[:32]})
    if not blocks:raise ValueError('utair_support_article_not_ready')
    if len(blocks)>100:raise ValueError('utair_support_leaf_limit')
    return blocks


def parse_article(raw,observed_at):
    rows=[];blocks=article_blocks(raw)
    page_sha=hashlib.sha256(raw.encode()).hexdigest()
    for block in blocks:
        partner='Копить мили' in block['section_path']
        details={'scope':'one_leaf_of_public_support_article','public_article_block':block,
            'source_document_sha256':page_sha,'retrieval_method':'disposable_installed_chrome_CDP',
            'linked_terms_checked':False,'full_program_catalog':False}
        if not partner:details['evidence_role']='supplementary_rules_not_incremental_discount'
        rows.append(make_offer('utair',block['native_id'],'Utair Status',block['title'] if partner else None,
            block['text'] if partner else block['title'],ROOT,observed_at,
            title=block['title'],conditions=block['text'],link_kind='page_block',
            locator='SupportWidgets_content / '+' / '.join(block['section_path']+[block['title']]),
            record_kind='partner_offer' if partner else 'program_rules',
            source_status='public_support_article',details=details,
            warnings=['support_article_not_full_program_catalog','linked_partner_terms_not_fetched',
                      'user_eligibility_and_stacking_not_verified']))
    return rows


def validate_support_record(row):
    block=row.get('details',{}).get('public_article_block',{})
    path=block.get('section_path');label=block.get('title')
    if not isinstance(path,list) or not all(isinstance(x,str) for x in path) or not isinstance(label,str):
        raise ValueError('utair_support_identity_missing')
    native='leaf:'+hashlib.sha256(json.dumps([path,label],ensure_ascii=False).encode()).hexdigest()[:32]
    partner='Копить мили' in path
    if (row['source_url']!=ROOT or row['link_kind']!='page_block' or row['benefit_url'] is not None
        or row['source_status']!='public_support_article' or row['native_id']!=native
        or row['title']!=label or row['conditions_text']!=text(block.get('text'))
        or row['partner_name']!=(label if partner else None)
        or row['benefit_text']!=(text(block.get('text')) if partner else label)
        or row['record_kind']!=('partner_offer' if partner else 'program_rules')
        or row['details'].get('linked_terms_checked') is not False
        or row['details'].get('full_program_catalog') is not False):
        raise ValueError('utair_support_text_or_scope_mismatch')
    for link in block.get('links',[]):clean_url(link['url'])


async def read_article(client):
    from public_transport import check_response
    client.check_url(ROOT);page=client.page;responses=[]
    def observe(response):
        if response.request.is_navigation_request() and response.request.frame==page.main_frame:
            responses.append(response)
    page.on('response',observe)
    try:
        await asyncio.sleep(client.request_interval)
        await page.goto(ROOT,wait_until='commit',timeout=25000)
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            if responses:
                last=responses[-1]
                if clean_url(last.url)!=ROOT or clean_url(page.url)!=ROOT:raise RuntimeError('utair_unexpected_redirect')
                if last.headers.get('retry-after'):raise RuntimeError('utair_retry_after')
                if last.status not in (200,401):raise RuntimeError('http_'+str(last.status))
                if last.status==200:
                    try:raw=await asyncio.wait_for(page.content(),5)
                    except Exception:
                        await asyncio.sleep(.5);continue
                    # DOM extraction awaits the renderer; recheck identity after it.
                    if responses[-1] is not last:
                        continue
                    if clean_url(page.url)!=ROOT:
                        raise RuntimeError('utair_unexpected_redirect')
                    check_response(last.status,raw)
                    if len(raw.encode())>6000000:raise RuntimeError('source_response_too_large')
                    try:article_blocks(raw)
                    except ValueError as exc:
                        if str(exc)!='utair_support_article_not_ready':raise
                    else:return raw,[r.status for r in responses]
            await asyncio.sleep(.5)
        if responses and responses[-1].status!=200:raise RuntimeError('http_'+str(responses[-1].status))
        raise RuntimeError('utair_support_article_not_ready')
    finally:page.remove_listener('response',observe)


async def collect_utair(cfg,report,observed_at,limit):
    from installed_browser import installed_chrome
    from public_transport import PublicSource
    if cfg['id']!='utair' or cfg['url']!=ROOT:raise ValueError('unconfigured_utair_support_source')
    if not 1<=limit<=500:raise ValueError('invalid_record_limit')
    async with installed_chrome() as (context,page):
        client=PublicSource(None,ROOT);client.context=context;client.page=page
        client.deadline=time.monotonic()+120
        try:
            await within_source_budget(client,client.robots)
            raw,statuses=await within_source_budget(client,lambda:read_article(client))
            rows=parse_article(raw,observed_at)
            report['discovered']=len(rows)
            report['coverage']=json.dumps({'method':'live_public_support_article_leaves',
                'article_url':ROOT,'leaf_blocks':len(rows),'returned':min(limit,len(rows)),
                'main_document_statuses':statuses,'full_program_catalog':False,
                'linked_terms_checked':False,'tls_verification':True},ensure_ascii=False)
            if len(rows)>limit:report['errors'].append({'phase':'extraction','reason':'record_limit'})
            return rows[:limit]
        finally:
            if getattr(client,'robots_info',None):report['robots']=client.robots_info
