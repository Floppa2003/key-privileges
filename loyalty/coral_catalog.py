"""Public Coral listing/detail traversal. Never signs in or issues a coupon."""
from __future__ import annotations
import hashlib
import json
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from free_access_probe import FreeReader, ProbeError, sanitized_page, read_policy, now
from normalized import make_offer, text

CLUB = 'https://coralbonus.ru/klub-privilegii/'
PROMO = 'https://coralbonus.ru/promo/'
MAX_CREDITS = 175
MAX_REQUESTS = 100
WARNINGS = ['user_eligibility_and_stacking_not_verified', 'private_coupon_not_requested',
            'outgoing_partner_links_not_fetched', 'image_only_conditions_not_transcribed',
            'regional_availability_not_verified']


def checked_url(url, prefix, depth):
    u = urlsplit(url)
    if (u.scheme != 'https' or u.netloc != 'coralbonus.ru' or u.query or u.fragment
        or not u.path.startswith(prefix) or len(u.path.strip('/').split('/')) != depth
        or not re.fullmatch(r'/[a-z0-9_/-]+/', u.path)):
        raise ValueError('coral_url_outside_discovered_scope')
    return url


def listing(raw, sid):
    soup = BeautifulSoup(raw, 'html.parser')
    heading = soup.select('h1')
    expected = 'Клуб привилегий' if sid == 'coral' else 'Акции'
    if len(heading) != 1 or text(heading[0].get_text(' ', strip=True)) != expected:
        raise ValueError('coral_listing_identity')
    selector = '.category-box-menu h5 a[href]' if sid == 'coral' else '.sale-item-description h5 a[href]'
    prefix = '/klub-privilegii/' if sid == 'coral' else '/promo/'
    result = {}
    for a in soup.select(selector):
        url = checked_url(a['href'], prefix, 2)
        label = text(a.get_text(' ', strip=True))
        if not label or (url in result and result[url]['title'] != label):
            raise ValueError('coral_listing_label_conflict')
        result[url] = {'url': url, 'title': label}
    if not 1 <= len(result) <= 200:
        raise ValueError('coral_listing_empty_or_limit')
    if soup.select_one('.pagination a[href],a[rel="next"]'):
        raise ValueError('coral_listing_pagination_not_supported')
    return list(result.values())


def category_cards(raw, entry, categories=None):
    categories = categories or {entry["url"]: entry["title"]}
    soup = BeautifulSoup(raw, 'html.parser')
    headings = soup.select('h1'); grids = soup.select('#categoryProductsList')
    if len(headings) != 1 or text(headings[0].get_text(' ', strip=True)) != entry['title'] or len(grids) != 1:
        raise ValueError('coral_category_identity')
    result = {}; excluded = 0
    for box in grids[0].select('.product-box'):
        if 'referal' not in box.get('class', []):
            excluded += 1
            continue
        urls = {checked_url(a['href'], '/klub-privilegii/', 3) for a in box.select('a[href]')}
        if len(urls) != 1:
            raise ValueError('coral_card_identity')
        url = urls.pop()
        parent = url.rsplit('/', 2)[0]+'/'
        if parent not in categories:
            raise ValueError('coral_card_unknown_category')
        result[url] = {'url': url, 'category': categories[parent], 'parent_url': entry['url']}
    section = headings[0].find_parent('section')
    if section is None or '{{' in section.get_text(' ', strip=True):
        raise ValueError('coral_category_not_rendered')
    if soup.select_one('.pagination a[href],a[rel="next"]'):
        raise ValueError('coral_category_pagination_not_supported')
    return list(result.values()), excluded


def own_text(node):
    return text(node.get_text('\n', strip=True))


def explicit_end(body):
    matches = re.findall(r'Срок\s+действия\s+предложения\s*:?\s*до\s+(\d{2})\.(\d{2})\.(\d{4})', body, re.I)
    dates = {date(int(y), int(m), int(d)).isoformat() for d, m, y in matches}
    return next(iter(dates)) if len(dates) == 1 else None


def detail(raw, sid, entry, observed_at, retrieval):
    prefix, depth = ('/klub-privilegii/', 3) if sid == 'coral' else ('/promo/', 2)
    url = checked_url(entry['url'], prefix, depth)
    soup = BeautifulSoup(raw, 'html.parser'); headings = soup.select('h1')
    if len(headings) != 1:
        raise ValueError('coral_detail_heading')
    h = headings[0]; title = text(h.get_text(' ', strip=True))
    section = h.find_parent('section')
    if section is None or not title or '{{' in title:
        raise ValueError('coral_detail_not_ready')
    if sid == 'coral':
        purchase = section.select('.product-purchase-box.referal')
        ticket = (not purchase and 'col-lg' in h.parent.get('class', [])
                  and len(h.parent.select('.order-canvas')) == 1
                  and len(h.parent.select('.order-autorize')) == 1)
        if ticket:
            auth = h.parent.select_one('.order-autorize')
            auth_title = auth.select_one('h3')
            if not auth_title or not re.fullmatch(r'Чтобы купить билеты нужно авторизоваться на сайте',
                                                  text(auth_title.get_text(' ', strip=True))):
                raise ValueError('coral_ticket_identity_not_supported')
        elif len(purchase) == 1 and 'order-lg-2' in h.parent.get('class', []):
            auth = purchase[0].select_one('.order-autorize')
        else:
            raise ValueError('coral_detail_not_referral')
        content = h.parent
        # Plain HTML can contain both Angular branches. Read only the explicit
        # authorization notice, never hidden generated coupon/account branches.
        auth_heading = auth.select_one('h3') if auth else None
        auth_text = text(auth_heading.get_text(' ', strip=True)) if auth_heading else ''
    else:
        if 'article' not in section.get('class', []) or section.select_one('.sale-item-description'):
            raise ValueError('coral_promotion_not_detail')
        if title != entry['title']:
            raise ValueError('coral_promotion_title_changed')
        content = section; auth_text = ''
    copy = BeautifulSoup(str(content), 'html.parser')
    for node in copy.select('script,style,form,input,textarea,iframe,button,.modal,.product-purchase-box,.order-canvas,.order-autorize'):
        node.decompose()
    body = own_text(copy)
    if len(body) < len(title) + 50 or '{{' in body:
        raise ValueError('coral_detail_body_missing')
    tables = [[[text(c.get_text(' ', strip=True)) for c in row.find_all(['th', 'td'], recursive=False)]
               for row in table.select('tr')] for table in copy.select('table')]
    table_contexts = []
    for table in copy.select('table'):
        previous = table.find_previous(['p', 'h2', 'h3', 'h4'])
        table_contexts.append(text(previous.get_text(' ', strip=True)) if previous else '')
    redemption = []
    for p in copy.select('p,h2,h3,h4'):
        if re.fullmatch(r'Как воспользоваться предложением\s*:?', text(p.get_text(' ', strip=True)), re.I):
            nxt = p.find_next_sibling()
            while nxt is not None and nxt.name in ('ul', 'ol'):
                redemption.append(own_text(nxt))
                nxt = nxt.find_next_sibling()
    if auth_text:
        redemption.append(auth_text)
    links = [{'label': text(a.get_text(' ', strip=True)), 'url': a['href']} for a in copy.select('a[href]')]
    block = {'title': title, 'body': body, 'redemption': '\n'.join(redemption),
             'authentication_notice': auth_text, 'tables': tables, 'table_contexts': table_contexts,
             'links': links, 'category': entry.get('category'), 'valid_until': explicit_end(body)}
    return make_offer(sid, 'path:'+urlsplit(url).path, 'CoralBonus — Клуб' if sid == 'coral' else 'CoralBonus — Акции',
        None, title, url, observed_at, title=title, conditions=body, redemption=block['redemption'],
        category=entry.get('category'), tables=tables, valid_until=block['valid_until'],
        record_kind='partner_offer' if sid == 'coral' else 'campaign',
        source_status=('public_conditions_purchase_requires_login' if sid == 'coral' and ticket else
                       'public_conditions_coupon_requires_login') if auth_text else 'public_source_terms',
        locator='h1 parent offer column' if sid == 'coral' else 'section.article',
        details={'public_coral_block': block, 'source_document_sha256': hashlib.sha256(raw.encode()).hexdigest(),
                 'discovered_from': entry.get('parent_url', PROMO), 'retrieval': retrieval,
                 'private_coupon_issued': False, 'full_program_catalog': False,
                 'redemption_mode': 'ticket_purchase' if sid == 'coral' and ticket else 'partner_code_or_link',
                 'partner_identity': 'not_inferred_from_campaign_title'}, warnings=WARNINGS)


def validate_record(row):
    b = row.get('details', {}).get('public_coral_block', {})
    sid = row['source_id']; prefix, depth = ('/klub-privilegii/', 3) if sid == 'coral' else ('/promo/', 2)
    checked_url(row['source_url'], prefix, depth)
    if (row['native_id'] != 'path:'+urlsplit(row['source_url']).path or row['partner_name'] is not None
        or row['title'] != b.get('title') or row['benefit_text'] != b.get('title')
        or row['conditions_text'] != b.get('body') or row['redemption_text'] != b.get('redemption')
        or row['tables'] != b.get('tables') or row['valid_until'] != explicit_end(b.get('body', ''))
        or row['category'] != b.get('category') or row['link_kind'] != 'detail_page'
        or row['benefit_url'] != row['source_url']
        or row['record_kind'] != ('partner_offer' if sid == 'coral' else 'campaign')
        or row['program'] != ('CoralBonus — Клуб' if sid == 'coral' else 'CoralBonus — Акции')
        or row['source_status'] != (('public_conditions_purchase_requires_login' if row['details'].get('redemption_mode') == 'ticket_purchase' else 'public_conditions_coupon_requires_login') if b.get('authentication_notice') else 'public_source_terms')
        or not re.fullmatch('[a-f0-9]{64}', row['details'].get('source_document_sha256', ''))
        or row['details'].get('private_coupon_issued') is not False
        or row['details'].get('full_program_catalog') is not False
        or not set(WARNINGS).issubset(row['warnings'])):
        raise ValueError('coral_source_evidence_mismatch')


def collect(root_report, folder, key, observed_at, *, get=None, sleep=time.sleep, other_half=False):
    """Full promo index + alternating category halves; failed pages remain explicit."""
    if type(other_half) is not bool:
        raise ValueError('invalid_coral_half_selection')
    from public_transport import robots_document, check_response
    from protego import Protego
    path = Path(folder); out = path / 'coral-details'; out.mkdir(exist_ok=True)
    day = date.fromisoformat(observed_at[:10]).toordinal()
    shard = (day + int(other_half)) % 2
    observations = {r['source_id']: r for r in root_report['sources']}
    results = {}; pages = []
    kwargs = {'get': get} if get else {}
    reader = FreeReader(key, [{'url': CLUB}, {'url': PROMO}], max_credits=MAX_CREDITS, max_requests=MAX_REQUESTS, **kwargs)
    diagnostics = {'pages': pages, 'started_at': now(), 'scope': 'public_promo_and_alternating_referral_categories',
                   'run_id': root_report['run_id'], 'commit': root_report['commit']}
    def save():
        diagnostics.update(reserved_credits=reader.reserved, source_requests=reader.calls,
                           known_cost_headers=reader.known_charged_credits)
        (out / 'report.json').write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2))
    try:
        reader.preflight()
        info = {}; status, raw, _ = read_policy(reader, 'https://coralbonus.ru/robots.txt', info)
        rules, _ = robots_document(status, raw); policy = Protego.parse(rules)
        rate = policy.request_rate('LoyaltyCatalogResearchBot')
        interval = max(1, policy.crawl_delay('LoyaltyCatalogResearchBot') or 0, rate.seconds/rate.requests if rate else 0)
        if interval > 30: raise ProbeError('crawl_delay_exceeds_budget')
        last = time.monotonic()
        def read(url, browser):
            nonlocal last
            if not policy.can_fetch(url, 'LoyaltyCatalogResearchBot'): raise ProbeError('robots_disallow')
            reader.allowed.add(url)
            sleep(max(0, interval - (time.monotonic()-last)))
            p = {'url': url, 'browser': browser, 'started_at': now()}; pages.append(p)
            try:
                status, raw, cost = reader.read(url, browser=browser); last = time.monotonic()
                p.update(origin_http_status=status, credits=cost)
                check_response(status, raw)
                clean, meta = sanitized_page(raw, url, canonical_identity=not browser)
                p.update(meta); p['sha256'] = hashlib.sha256(clean.encode()).hexdigest()
                p['file'] = p['sha256']+'.html'; (out / p['file']).write_text(clean)
                return clean, {'method': 'scrapingant_free_browser' if browser else 'scrapingant_free_http',
                               'identity': 'browser_location' if browser else 'source_canonical_url',
                               'fetched_at': now(), 'origin_status': status}
            except Exception as exc:
                p['error'] = safe_error(exc); raise
            finally:
                p['finished_at'] = now(); save()
        for sid, root in (('coral_promo', PROMO), ('coral', CLUB)):
            result = {'records': [], 'errors': [], 'meta': {'full_program_catalog': False}}
            results[sid] = result
            try:
                seen_details = set()
                result['meta']['detail_pages_attempted'] = 0
                result['meta']['duplicate_detail_links'] = 0
                obs = observations.get(sid, {})
                if obs.get('status') != 'candidate_requires_review': raise ValueError('root_not_read')
                raw = (path / (sid+'.html')).read_bytes()
                if (obs.get('origin_http_status') != 200 or obs.get('final_url') != root
                    or hashlib.sha256(raw).hexdigest() != obs.get('sanitized_dom_sha256')):
                    raise ValueError('root_identity_or_hash')
                entries = listing(raw.decode(), sid)
                categories = {e['url']: e['title'] for e in entries}
                result['meta']['index_entries'] = len(entries)
                result['meta']['index_sha256'] = obs['sanitized_dom_sha256']
                if sid == 'coral_promo':
                    # Rotate priority too, so budget/transport interruptions do not starve a tail.
                    k = day % len(entries); targets = entries[k:]+entries[:k]
                    result['meta']['scope'] = 'all_current_promo_index_links'
                    result['meta']['discovered_details'] = len(targets)
                    groups = [(None, targets)]
                else:
                    ordered = sorted(entries, key=lambda e: e['url'])
                    selected = ordered[shard::2]
                    k = (day//2) % len(selected) if selected else 0
                    selected = selected[k:]+selected[:k]
                    result['meta'].update(scope='alternating_category_half_public_referral_offers',
                        category_shard=shard, category_shards=2, selection_mode='complementary_half' if other_half else 'utc_day_half', selected_categories=[e['url'] for e in selected],
                        categories_read=0, excluded_non_referral_products=0, discovered_details=0)
                    groups = [(e, None) for e in selected]
                for category, targets in groups:
                    if reader.halted: raise ProbeError('reader_not_ready_or_stopped')
                    if category:
                        try:
                            cat, _ = read(category['url'], True)
                            targets, excluded = category_cards(cat, category, categories)
                            result['meta']['categories_read'] += 1
                            result['meta']['excluded_non_referral_products'] += excluded
                            result['meta']['discovered_details'] = len(seen_details | {e['url'] for e in targets})
                        except Exception as exc:
                            result['errors'].append({'phase': 'category', 'path': urlsplit(category['url']).path, 'reason': safe_error(exc)})
                            if reader.halted or str(exc) == 'per_run_limit': break
                            continue
                    for entry in targets:
                        if entry['url'] in seen_details:
                            result['meta']['duplicate_detail_links'] += 1
                            continue
                        seen_details.add(entry['url'])
                        result['meta']['detail_pages_attempted'] += 1
                        try:
                            page, identity = read(entry['url'], False)
                            result['records'].append(detail(page, sid, entry, observed_at, identity))
                        except Exception as exc:
                            result['errors'].append({'phase': 'detail', 'path': urlsplit(entry['url']).path, 'reason': safe_error(exc)})
                            if reader.halted or str(exc) == 'per_run_limit': break
                    if reader.halted or reader.reserved >= MAX_CREDITS: break
                result['meta']['detail_records'] = len(result['records'])
                result['meta']['all_observed_promo_details_read'] = sid == 'coral_promo' and len(result['records']) == len(entries) and not result['errors']
            except Exception as exc:
                result['errors'].append({'phase': 'catalogue', 'reason': safe_error(exc)})
    except Exception as exc:
        diagnostics['error'] = safe_error(exc)
    finally:
        diagnostics['finished_at'] = now(); save()
    return results


def safe_error(exc):
    value = str(exc)
    if isinstance(exc, (ValueError, RuntimeError)) and re.fullmatch('[a-z_0-9]+', value):
        return value[:120]
    return type(exc).__name__
