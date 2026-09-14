"""Production adapters for reviewed public HTTP / scoped national-CA endpoints."""
from __future__ import annotations
import asyncio
import hashlib
import json
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urljoin, parse_qs
import certifi
import requests
from bs4 import BeautifulSoup
from protego import Protego
from recovered_contract import (API, SOURCES, CA_FILES, HTTP_PROFILE, HTTP_WARNING,
    collection_url, http_url, checked_config, transport_evidence, linked_pdf_url)
from normalized import make_offer, text, number, content_hash
from document_text import extract_pdf, document_records
from public_transport import check_response, robots_document
from known_rules import linked_documents

MAX_BYTES = 5_000_000


class ScopedReader:
    """One anonymous session, exact endpoints, verified TLS or explicit Loyals HTTP."""
    def __init__(self, cfg, report, deadline):
        self.spec = checked_config(cfg)
        self.sid = cfg['id']
        self.report = report
        self.deadline = deadline
        self.session = requests.Session()
        self.session.trust_env = False
        self.temp = None
        self.verify = True
        self.policy = None
        self.interval = 1.0
        self.last_read = 0.0
        self.document_urls = set()

    def __enter__(self):
        try:
            if self.sid != 'loyals':
                self.temp = tempfile.TemporaryDirectory()
                bundle = Path(self.temp.name) / 'source-ca.pem'
                data = Path(certifi.where()).read_bytes() + b'\n'
                for url, sha in CA_FILES:
                    status, _, raw = self._get(url, ca_download=True)
                    if status != 200 or hashlib.sha256(raw).hexdigest() != sha:
                        raise RuntimeError('official_ca_digest_changed_or_unavailable')
                    data += raw + b'\n'
                bundle.write_bytes(data)
                self.verify = str(bundle)
            root = urlsplit(self.spec['url'])
            robots = f'{root.scheme}://{root.netloc}/robots.txt'
            status, headers, raw = self._get(robots)
            rules, state = robots_document(status, raw.decode('utf-8'))
            self.policy = Protego.parse(rules)
            delay = self.policy.crawl_delay('LoyaltyCatalogResearchBot') or 0
            rate = self.policy.request_rate('LoyaltyCatalogResearchBot')
            self.interval = max(1.0, delay, rate.seconds / rate.requests if rate else 0)
            self.report['robots'] = {'state':state,'http_status':status,'method':'scoped_public_http'}
            return self
        except Exception:
            self.__exit__(None,None,None)
            raise

    def __exit__(self, *_):
        self.session.close()
        if self.temp:
            self.temp.cleanup()

    def allowed(self, url):
        if self.sid == 'loyals':
            return http_url(url)
        base = urlsplit(self.spec['url'])
        if url not in (self.spec['url'], f'https://{base.netloc}/robots.txt') and url not in self.document_urls:
            raise ValueError('request_outside_exact_recovered_source')
        return url

    def bind_document_links(self, links):
        """Only direct PDF links extracted from this run's reviewed page section."""
        self.document_urls=set()
        for link in links:
            try:url=linked_pdf_url(link['url'].strip(),self.sid)
            except ValueError:continue
            self.document_urls.add(url)
        if len(self.document_urls)>30:raise RuntimeError('linked_document_count_limit')

    def read_document(self,url):
        if url not in self.document_urls:raise ValueError('document_not_in_live_source_listing')
        # Direct user-authorized file downloads, not a site-wide crawl. Record the
        # robots rule separately; it is not proof of a target HTTP access refusal.
        status,headers,raw=self._get(url)
        if status!=200:raise RuntimeError('document_http_'+str(status))
        if not raw.startswith(b'%PDF-'):raise RuntimeError('linked_resource_not_pdf')
        return raw,{'robots_allows_crawling':self.policy.can_fetch(url,'LoyaltyCatalogResearchBot'),
            'mode':'direct_advertised_public_file_download','http_status':status}


    def _get(self, url, *, ca_download=False):
        if ca_download:
            if url not in {u for u,_ in CA_FILES}:
                raise ValueError('unreviewed_CA_download')
        else:
            self.allowed(url)
        # Redirects never broaden the allowlist or send cookies to another host.
        original = url
        for redirect in range(4):
            remaining = self.deadline - time.monotonic()
            if remaining < 2:
                raise RuntimeError('source_time_budget_exhausted')
            pause = max(0, self.interval - (time.monotonic() - self.last_read))
            if pause + 2 > remaining:
                raise RuntimeError('source_time_budget_exhausted')
            time.sleep(pause)
            try:
                with self.session.get(url, headers={'User-Agent':'Mozilla/5.0',
                        'Accept-Language':'ru-RU,ru;q=0.9'},
                        verify=True if ca_download else self.verify,
                        timeout=(min(7,remaining/2), min(20,remaining/2)),
                        allow_redirects=False, stream=True) as response:
                    data = bytearray()
                    for chunk in response.iter_content(32768):
                        data.extend(chunk)
                        if len(data) > (25000 if ca_download else MAX_BYTES):
                            raise RuntimeError('source_response_too_large')
                        if time.monotonic() >= self.deadline:
                            raise RuntimeError('source_time_budget_exhausted')
                    status, headers, raw = response.status_code, dict(response.headers), bytes(data)
            except requests.exceptions.SSLError:
                raise RuntimeError('source_certificate_verification_failed') from None
            except requests.RequestException:
                raise RuntimeError('source_transport_failed') from None
            finally:
                self.last_read = time.monotonic()
            if status == 429 or response.headers.get('Retry-After'):
                raise RuntimeError('source_rate_limited')
            if status not in (301,302,303,307,308):
                return status, response.headers, raw
            location = urljoin(url, response.headers.get('Location',''))
            # Only Uralsib's observed same-URL anonymous session redirect is allowed.
            if ca_download or self.sid != 'uralsib_rzd_rules' or location != original or redirect == 3:
                raise RuntimeError('unexpected_source_redirect')
            url = location
        raise RuntimeError('source_redirect_limit')

    def read(self, url):
        self.allowed(url)
        if self.policy is None or not self.policy.can_fetch(url,'LoyaltyCatalogResearchBot'):
            raise RuntimeError('robots_disallow')
        status, headers, raw = self._get(url)
        body = raw.decode('utf-8')
        check_response(status, body)
        return headers, raw


def public_post_record(post, cfg, now, response_url, index, response_sha):
    if (type(post.get('id')) is not int or post['id'] <= 0 or post.get('status') != 'publish'
            or post.get('type') != 'post' or post.get('content',{}).get('protected') is not False):
        raise ValueError('not_an_unprotected_public_post')
    title = text(post['title']['rendered'])
    body = text(post['content']['rendered'])
    if not title:
        raise ValueError('missing_public_post_title')
    link = urlsplit(post.get('link',''))
    if (link.scheme not in ('http','https') or link.netloc != 'loyals.ru'
            or link.fragment or link.username or re.search(r'token|secret|password|auth|session',link.query,re.I)):
        raise ValueError('invalid_publisher_link')
    for key in ('date_gmt','modified_gmt'):
        if post.get(key):
            datetime.fromisoformat(post[key])
    soup = BeautifulSoup(post['content']['rendered'],'html.parser')
    tables = [[[text(c.get_text(' ',strip=True)) for c in tr.find_all(['th','td'])]
        for tr in table.find_all('tr')] for table in soup.find_all('table')]
    details = {'_source':{'source_id':'loyals'},'transport':transport_evidence('loyals'),'public_post':post,
        'publisher_canonical_url':post['link'],'publisher_canonical_url_fetched':False,
        'response_sha256':response_sha,'response_json_pointer':f'/{index}',
        'source_published_at_gmt':post.get('date_gmt'),
        'source_modified_at_gmt':post.get('modified_gmt'),
        'empty_body':not bool(body),'source_dates_are_not_offer_validity':True}
    warnings = [HTTP_WARNING,'current_eligibility_and_validity_unknown',
        'source_modification_date_not_fresh_offer_verification','publisher_https_link_not_verified']
    if not body:
        warnings.append('empty_public_post_title_only_not_an_offer')
    return make_offer('loyals',str(post['id']),cfg['name'],title,body,response_url,now,
        title=title,conditions=body or title,tables=tables,details=details,warnings=warnings,
        source_status='public_http_unverified',link_kind='api_record',locator=f'/{index}',
        record_kind='partner_offer' if body else 'source_observation')


def collect_loyals(reader, cfg, report, now, limit):
    records, seen, home_ids, pages_read = [], set(), set(), []
    total = pages = None
    _, raw = reader.read(cfg['url'])
    soup = BeautifulSoup(raw,'html.parser')
    link = soup.select_one('link[rel="https://api.w.org/"]')
    if not link or link.get('href') not in ('https://loyals.ru/wp-json/','http://loyals.ru/wp-json/'):
        raise ValueError('public_API_no_longer_advertised')
    for a in soup.select('a[href]'):
        u = urlsplit(urljoin(cfg['url'],a['href']))
        p = parse_qs(u.query).get('p',[])
        if u.hostname == 'loyals.ru' and len(p)==1 and p[0].isdigit():
            home_ids.add(int(p[0]))
    stop = 'page_limit'
    for page in range(1,11):
        url = collection_url(page)
        try:
            headers, raw = reader.read(url)
            current_total = int(headers['X-WP-Total'])
            current_pages = int(headers['X-WP-TotalPages'])
            if not 0 <= current_total <= 500 or not 1 <= current_pages <= 10:
                raise ValueError('public_API_pagination_outside_bound')
            if total is not None and (total,pages) != (current_total,current_pages):
                raise ValueError('public_API_totals_changed')
            total,pages = current_total,current_pages
            values = json.loads(raw)
            if not isinstance(values,list) or len(values)>50:
                raise ValueError('invalid_public_post_list')
            response_sha = hashlib.sha256(raw).hexdigest()
            pages_read.append({'url':url,'count':len(values),'sha256':response_sha})
            for index, post in enumerate(values):
                native = post.get('id')
                if type(native) is not int or native in seen:
                    raise ValueError('invalid_or_duplicate_public_post_id')
                seen.add(native)
                if len(records) >= limit:
                    stop = 'record_limit'
                    break
                records.append(public_post_record(post,cfg,now,url,index,response_sha))
            if stop == 'record_limit':
                break
            if page == pages:
                stop = 'advertised_collection_exhausted'
                break
        except (RuntimeError, ValueError, KeyError, TypeError) as exc:
            report['errors'].append({'phase':'public_api','page':page,'reason':str(exc)[:160]})
            stop = 'read_or_validation_error'
            break
    complete = total is not None and len(records)==total and len(seen)==total and not report['errors']
    missing = sorted(home_ids-seen)
    if not complete and not report['errors']:
        report['errors'].append({'phase':'public_api','reason':stop if stop=='record_limit' else 'post_count_mismatch'})
    if missing:
        report['errors'].append({'phase':'homepage','reason':'homepage_post_ids_missing','ids':missing})
    report['discovered'] = max(total or 0,len(seen),len(records))
    report['coverage'] = json.dumps({'kind':'advertised_public_WordPress_collection_not_current_offers',
        'transport':'HTTP_unverified','api_total':total,'pages':pages_read,'complete_api_collection':complete,
        'homepage_ids':len(home_ids),'homepage_ids_missing':missing,'stop_reason':stop,
        'empty_body_records':sum(r['details']['empty_body'] for r in records)},ensure_ascii=False)
    return records


def one_node(soup, selector):
    nodes=soup.select(selector)
    if len(nodes)!=1:
        raise ValueError('missing_or_ambiguous_source_scope:'+selector)
    return nodes[0]


def scoped_bank_sections(sid, raw):
    soup=BeautifulSoup(raw,'html.parser')
    for n in soup.select('script,style,form,input,textarea,noscript'):
        n.decompose()
    if sid=='nspk_ekp_rules':
        return [one_node(soup,'.pages-press-center-details-article-slug')]
    if sid=='uralsib_rzd_rules':
        return [one_node(soup,'h1'),one_node(soup,'section#textBlock')]
    one_node(soup,'h1')
    # Top-level page sections only; exclude related product, navigation and footer.
    candidates=[n for n in soup.select('section[class*="NativeSection"]')
                if n.find_parent('section') is None]
    selected=[]
    for n in candidates:
        body=text(n.get_text(' ',strip=True))
        if (n.get('id') in ('how','widget-panel') or body.startswith('1000 Бесплатно')):
            continue
        if body:
            selected.append(n)
    if not selected or not any('Как начисляются мили' in n.get_text() for n in selected):
        raise ValueError('vtb_product_sections_changed')
    return selected


def parse_bank_page(sid, raw, now):
    spec=SOURCES[sid]
    nodes=scoped_bank_sections(sid,raw)
    blocks=[text(n.get_text(' ',strip=True)) for n in nodes]
    terms='\n'.join(blocks)
    details={'_source':{'source_id':sid},'transport':transport_evidence(sid),'evidence_role':'supplementary_rules_not_incremental_discount',
        'sections':blocks,'linked_documents':linked_documents(nodes,spec['url']),
        'page_sha256':hashlib.sha256(raw.encode('utf-8')).hexdigest()}
    warnings=['personal_eligibility_not_verified','linked_full_documents_not_fetched']
    start=end=None
    if sid=='af_vtb_rules':
        if 'Дебетовая карта Привилегия Аэрофлот' not in terms or 'Прайм Аэрофлот' in terms:
            raise ValueError('vtb_product_identity_or_related_product_contamination')
        paragraph=next(x for x in blocks if x.startswith('Как начисляются мили'))
        m=re.search(r'За\s+каждые\s+([\d ]+)\s*₽.*?получите\s+(\d+)\s+мили',paragraph,re.I)
        if not m:raise ValueError('vtb_earning_contract_changed')
        details['earning_rules']=[{'value':m[2],'unit':'miles','basis_amount':number(m[1]),
            'basis_unit':'RUB','qualifier':'exact','evidence':m[0]}]
        details['fees']=[x for x in blocks if 'комисси' in x.lower()]
        details['earning_conditions']=paragraph
        details['qualification']=next((x for x in blocks if x.startswith('Премиум-обслуживание')),'')
        campaign=next((x for x in blocks if x.startswith('Празднуем')),'')
        if campaign:details['individual_campaign_rules']={'text':campaign,'scope':'individual_offer_not_base_card_terms'}
        warnings.append('campaign_dates_do_not_expire_base_card_rules')
        program='Аэрофлот Бонус';partner='ВТБ';title='ВТБ Привилегия Аэрофлот — условия карты'
    elif sid=='nspk_ekp_rules':
        if 'Держатели ЕКП смогут экономить' not in terms or 'vamprivet.ru' not in terms:
            raise ValueError('nspk_article_identity_changed')
        program='Единая карта петербуржца (ЕКП)';partner='НСПК';title='НСПК — объявление о кешбэке ЕКП'
        warnings.append('announcement_article_not_full_campaign_rules')
        details['scope']='published_article_not_complete_offer_catalogue'
    else:
        if 'Приветственные баллы РЖД за оформление карты' not in terms:
            raise ValueError('uralsib_campaign_identity_changed')
        m=re.search(r'В период с (\d{2}\.\d{2}\.\d{4}) по (\d{2}\.\d{2}\.\d{4}) оформить заявку',terms)
        if not m:raise ValueError('uralsib_application_period_missing')
        start,end=[datetime.strptime(x,'%d.%m.%Y').date().isoformat() for x in m.groups()]
        details['validity_scope']='card_application_window';details['application_period_evidence']=m[0]
        details['tables']=[[[text(c.get_text(' ',strip=True)) for c in tr.find_all(['th','td'])]
            for tr in t.find_all('tr')] for n in nodes for t in n.find_all('table')]
        warnings.append('historical_campaign_not_current_card_offer')
        program='РЖД Бонус';partner='Уралсиб';title='Уралсиб — приветственные баллы РЖД (правила акции)'
    return make_offer(sid,'public-rules',program,partner,terms,spec['url'],now,
        title=title,conditions=terms,details=details,tables=details.get('tables',[]),warnings=warnings,
        valid_from=start,valid_until=end,record_kind='program_rules',
        link_kind='page_block' if sid=='nspk_ekp_rules' else 'detail_page',
        source_status='public_announcement_not_full_rules' if sid=='nspk_ekp_rules' else 'public_rules_text')


def _collect(cfg, report, now, limit):
    deadline=time.monotonic()+cfg.get('timeout_seconds',240)-2
    with ScopedReader(cfg,report,deadline) as reader:
        if cfg['id']=='loyals':
            return collect_loyals(reader,cfg,report,now,limit)
        _, raw=reader.read(cfg['url'])
        parent=parse_bank_page(cfg['id'],raw.decode('utf-8'),now)
        records=[parent];inventory=[];seen=set()
        links=parent['details']['linked_documents'];reader.bind_document_links(links)
        for link in links:
            url=link['url'].strip()
            if url in seen:continue
            seen.add(url)
            item={'url':url,'label':link['label'],'status':'outside_direct_PDF_scope'}
            inventory.append(item)
            if url not in reader.document_urls:continue
            try:
                if len(records)>=limit:raise RuntimeError('record_limit')
                data,transport=reader.read_document(url)
                doc=extract_pdf(data)
                children=document_records(cfg['id'],'linked-pdf:'+hashlib.sha256(url.encode()).hexdigest()[:32],
                    parent['program'],parent['partner_name'],url,now,doc,
                    parent_source=cfg['url'],parent_sha256=hashlib.sha256(raw).hexdigest(),label=link['label'],
                    extra_details={'transport':transport_evidence(cfg['id']),'document_download':transport,
                        'parent_record_id':parent['id']})
                if len(records)+len(children)>limit:raise RuntimeError('record_limit')
                records.extend(children)
                item.update(status='read',record_ids=[r['id'] for r in children],**transport)
                if doc['errors']:
                    report['errors'].append({'phase':'document_text','path':urlsplit(url).path,'errors':doc['errors']})
            except Exception as exc:
                reason=str(exc)[:160] if isinstance(exc,(RuntimeError,ValueError)) else type(exc).__name__
                item.update(status='failed',reason=reason)
                report['errors'].append({'phase':'document','path':urlsplit(url).path,'reason':reason})
                if reason in ('source_rate_limited','source_time_budget_exhausted','record_limit'):break
        parent['details']['linked_document_inventory']=inventory
        parent['details']['linked_documents_discovery']='live_parent_page_direct_PDFs_only'
        parent['warnings']=[w for w in parent['warnings'] if w!='linked_full_documents_not_fetched']
        parent['warnings'].append('only_direct_public_PDF_links_followed')
        parent['content_sha256']=content_hash(parent)
        report['discovered']=1+len(reader.document_urls)
        report['coverage']=json.dumps({'kind':'live_page_and_discovered_direct_PDFs',
            'pdf_candidates':len(reader.document_urls),'pdfs_read':sum(x['status']=='read' for x in inventory),
            'page_records':len(records),'recursive_links_followed':False},ensure_ascii=False)
        return records


async def collect_recovered(cfg, report, now, limit):
    return await asyncio.to_thread(_collect,cfg,report,now,limit)
