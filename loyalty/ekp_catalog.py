"""Public EKP catalogue evidence. Unread cards never become verified offers."""
from __future__ import annotations
import asyncio
import copy
import hashlib
import time
import re
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup
from normalized import make_offer, text

ROOT = 'https://ekp.spb.ru/capabilities/loyalty/'
CATALOG_URLS = (ROOT, 'https://ekp.spb.ru/capabilities/loyalty/tiles')
CARD_PATH = re.compile(r'/capabilities/loyalty/tiles/([0-9]+)/?')
PREVIEW_WARNINGS = [
    'catalog_preview_not_full_partner_rules',
    'detail_link_observed_not_fetched',
    'user_eligibility_not_verified',
    'private_code_not_requested',
]


def detail_identity(value):
    u = urlsplit(urljoin(ROOT, value))
    match = CARD_PATH.fullmatch(u.path)
    if u.scheme != 'https' or u.netloc != 'ekp.spb.ru' or u.query or u.fragment or not match:
        raise ValueError('ekp_untrusted_card_link')
    return match[1], f'https://ekp.spb.ru{u.path.rstrip("/")}'


def own(box, selector):
    return [n for n in box.select(selector) if n.find_parent(class_='v-card') is box]


def node_text(node):
    return text(node.get_text(' ', strip=True))


def parse_catalog(raw, url):
    """Parse only owned rendered card blocks, not page menus or cached answers."""
    if url not in CATALOG_URLS:
        raise ValueError('ekp_wrong_catalog_url')
    if not isinstance(raw, str) or len(raw.encode()) > 6000000:
        raise ValueError('ekp_invalid_catalog_body')
    soup = BeautifulSoup(raw, 'html.parser')
    mains = soup.select('main')
    if len(mains) > 1 or (soup.title is not None and node_text(soup.title) != 'Партнеры'):
        raise ValueError('ekp_missing_catalog_identity')
    if not mains or soup.title is None or not mains[0].select('.text-h4'):
        raise ValueError('ekp_catalog_not_ready')
    if [node_text(h) for h in mains[0].select('.text-h4')] != ['Партнеры']:
        raise ValueError('ekp_missing_catalog_identity')
    boxes = [b for b in mains[0].select('.v-card') if b.find_parent(class_='v-card') is None]
    if len(boxes) > 2000:
        raise ValueError('ekp_unbounded_cards')
    if not boxes:
        raise ValueError('ekp_catalog_not_ready')
    cards = []
    seen = set()
    for box in boxes:
        if box.select('.v-card'):
            raise ValueError('ekp_nested_card_scope')
        titles = own(box, '.v-card-title')
        links = own(box, '.v-card-actions a[href]')
        # The observed catalogue filter is a v-card too, but has no offer actions.
        if own(box, '.v-input') and not own(box, '.v-card-actions') and not titles:
            continue
        if len(titles) != 1 or not node_text(titles[0]) or len(links) != 1:
            raise ValueError('ekp_ambiguous_card_identity')
        native, link = detail_identity(links[0]['href'])
        if native in seen:
            raise ValueError('ekp_duplicate_card_identity')
        seen.add(native)
        labels = [node_text(n) for n in own(box, '.v-card-subtitle,.v-chip__content')]
        labels = [s for s in labels if s]
        if not labels or len(set(labels)) != 1:
            raise ValueError('ekp_missing_or_conflicting_benefit')
        descriptions = own(box, '.v-card-text.line-clamp-2')
        if len(descriptions) > 1:
            raise ValueError('ekp_ambiguous_card_description')
        category_nodes = own(box, '.v-card-text.text-caption span')
        categories = list(dict.fromkeys(node_text(n) for n in category_nodes if node_text(n)))
        cards.append({'native_id': native, 'detail_url': link,
                      'partner_name': node_text(titles[0]), 'benefit_text': labels[0],
                      'description': node_text(descriptions[0]) if descriptions else '',
                      'tags': categories,
                      'authentication_required': 'Требуется авторизация' in node_text(box),
                      'card_text': node_text(box)})
    if not cards:
        raise ValueError('ekp_catalog_not_ready')
    return {'url': url, 'cards': cards, 'page_sha256': hashlib.sha256(raw.encode()).hexdigest()}


def preview_record(card, observed_at, page_sha256, *, catalog_url=ROOT):
    if catalog_url not in CATALOG_URLS:
        raise ValueError('ekp_wrong_catalog_url')
    native, link = detail_identity(card['detail_url'])
    if native != card['native_id'] or not re.fullmatch(r'[a-f0-9]{64}', page_sha256):
        raise ValueError('ekp_invalid_preview_identity')
    return make_offer('ekp', 'card:' + native, 'ЕКП — каталог', card['partner_name'],
                      card['benefit_text'], catalog_url, observed_at,
                      title=card['partner_name'], conditions=card['card_text'],
                      record_kind='source_observation',
                      link_kind='page_block', locator='main .v-card: detail path=' + urlsplit(link).path,
                      source_status='public_catalog_preview', warnings=PREVIEW_WARNINGS,
                      details={'public_scope': 'catalog_card_only', 'detail_fetched': False,
                               'authentication_required': True if card['authentication_required'] else None,
                               'card': copy.deepcopy(card), 'parent_response_sha256': page_sha256})


def validate_catalog_record(record):
    d = record['details']
    c = d.get('card', {})
    native, link = detail_identity(c.get('detail_url', ''))
    if (record['native_id'] != 'card:' + native or c.get('native_id') != native
        or record['source_url'] not in CATALOG_URLS or record['benefit_url'] is not None
        or record['record_kind'] != 'source_observation' or record['link_kind'] != 'page_block'
        or record['source_status'] != 'public_catalog_preview'
        or record['program'] != 'ЕКП — каталог' or record['category'] is not None
        or record['title'] != c.get('partner_name')
        or record['partner_name'] != c.get('partner_name')
        or record['benefit_text'] != c.get('benefit_text')
        or record['conditions_text'] != c.get('card_text')
        or d.get('public_scope') != 'catalog_card_only' or d.get('detail_fetched') is not False
        or type(c.get('authentication_required')) is not bool
        or d.get('authentication_required') is not (True if c['authentication_required'] else None)
        or record['redemption_text'] or record['tables']
        or record['valid_from'] is not None or record['valid_until'] is not None
        or record['validity_status'] != 'not_stated'
        or record['locator'] != 'main .v-card: detail path=' + urlsplit(link).path
        or not re.fullmatch(r'[a-f0-9]{64}', d.get('parent_response_sha256', ''))
        or any(w not in record['warnings'] for w in PREVIEW_WARNINGS)):
        raise ValueError('ekp_preview_cannot_certify_unread_detail')


def guard_catalog(client, navigation, api_refusals):
    if api_refusals:
        raise RuntimeError(api_refusals[0])
    if not navigation:
        raise RuntimeError('ekp_missing_navigation_response')
    current = navigation[-1]
    if current.url not in CATALOG_URLS or client.page.url not in CATALOG_URLS:
        raise RuntimeError('ekp_unexpected_redirect')
    if current.headers.get('retry-after'):
        raise RuntimeError('ekp_retry_after')
    if current.status != 200:
        raise RuntimeError('http_' + str(current.status))
    client.check_url(current.url)
    client.check_url(client.page.url)
    return current


async def read_snapshot(client, navigation, api_refusals, previous=None):
    """Wait for actual card growth; recheck navigation after every awaited DOM read."""
    from public_transport import check_response
    previous = previous or set()
    page = client.page
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        response = guard_catalog(client, navigation, api_refusals)
        try:
            raw = await asyncio.wait_for(page.content(), 5)
        except asyncio.TimeoutError:
            await asyncio.sleep(.5)
            continue
        current = guard_catalog(client, navigation, api_refusals)
        if current is not response:
            continue
        check_response(current.status, raw)
        try:
            snapshot = parse_catalog(raw, page.url)
        except ValueError as exc:
            if str(exc) != 'ekp_catalog_not_ready':
                raise
        else:
            ids = {c['native_id'] for c in snapshot['cards']}
            if previous - ids:
                raise RuntimeError('ekp_load_more_lost_previous_cards')
            if ids - previous:
                return snapshot
        await asyncio.sleep(.5)
    raise RuntimeError('ekp_catalog_not_ready' if not previous else 'ekp_load_more_no_growth')


async def walk_catalog(client, report, observed_at, limit):
    import json
    from read_budget import within_source_budget
    client.check_url(ROOT)
    page = client.page
    navigation, api_refusals = [], []
    rows, seen, prior = [], set(), {}
    stop, captures = 'read_error', 0
    def observe(response):
        if response.request.is_navigation_request() and response.request.frame == page.main_frame:
            navigation.append(response)
        u = urlsplit(response.url)
        if u.netloc == 'ekp.spb.ru' and u.path.startswith('/api/portal/loyalty/'):
            if response.headers.get('retry-after'):
                api_refusals.append('ekp_retry_after')
            elif response.status >= 400:
                api_refusals.append('http_' + str(response.status))
    page.on('response', observe)
    try:
        await asyncio.sleep(client.request_interval)
        await within_source_budget(client, lambda: page.goto(ROOT, wait_until='commit', timeout=25000))
        for _ in range(40):
            snapshot = await within_source_budget(client, lambda: read_snapshot(client, navigation, api_refusals, seen))
            captures += 1
            candidates = snapshot['cards']
            report['discovered'] = max(report['discovered'], len(candidates))
            for card in candidates:
                ident = card['native_id']
                if ident in prior and card != prior[ident]:
                    raise RuntimeError('ekp_catalog_changed_during_pagination')
            for card in candidates:
                ident = card['native_id']
                if ident not in seen and len(rows) < limit:
                    rows.append(preview_record(card, observed_at, snapshot['page_sha256'], catalog_url=snapshot['url']))
                    prior[ident] = card
                    seen.add(ident)
            if len(rows) >= limit:
                stop = 'record_limit'
                break
            more = page.get_by_role('button', name=re.compile(r'^Показать еще$'))
            if await more.count() != 1 or not await more.is_visible() or not await more.is_enabled():
                stop = 'no_single_enabled_visible_load_more'
                break
            await within_source_budget(client, lambda: asyncio.sleep(client.request_interval))
            guard_catalog(client, navigation, api_refusals)
            # Reuse the actual UI; no private endpoints, IDs or query parameters are replayed.
            await within_source_budget(client, lambda: more.click(timeout=8000))
        else:
            stop = 'page_limit'
    except Exception as exc:
        report['errors'].append({'phase':'catalog','reason':str(exc)[:180] if isinstance(exc,RuntimeError) else type(exc).__name__})
    finally:
        page.remove_listener('response', observe)
        report['coverage'] = json.dumps({'method':'anonymous_EKP_UI_catalog_previews',
            'snapshots_read':captures, 'observed_cards':report['discovered'], 'returned':len(rows),
            'stop_reason':stop, 'full_catalog_complete':False, 'details_fetched':False,
            'private_codes_requested':False, 'api_replay':False,
            'main_document_statuses':[r.status for r in navigation]},ensure_ascii=False)
    if rows:
        report['errors'].append({'phase':'coverage','reason':'preview_only_details_and_total_not_verified'})
        if stop in ('record_limit','page_limit'):
            report['errors'].append({'phase':'coverage','reason':stop})
    return rows


async def collect_ekp(cfg, report, observed_at, limit):
    from installed_browser import installed_chrome
    from public_transport import PublicSource
    from read_budget import within_source_budget
    if cfg['id'] != 'ekp' or cfg['url'] != ROOT:
        raise ValueError('unconfigured_ekp_catalog_source')
    if type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError('invalid_record_limit')
    async with installed_chrome() as (context, page):
        client = PublicSource(None, ROOT)
        client.context, client.page = context, page
        client.deadline = time.monotonic() + 300
        try:
            await within_source_budget(client, client.robots)
            return await walk_catalog(client, report, observed_at, limit)
        finally:
            if getattr(client, 'robots_info', None):
                report['robots'] = client.robots_info
