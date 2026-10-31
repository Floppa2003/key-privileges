"""Lossless collector-to-model handoff and bounded readiness of public pages.

No offer interpretation, synthetic screenshots, model calls or account access.
The original source object and browser evidence stay separately identifiable.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from urllib.parse import urlsplit

from playwright.async_api import TimeoutError as BrowserTimeout

INPUT_CONTRACT_VERSION = 2


def digest(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def validate_source_records(spec: dict, target: dict) -> None:
    if 'source_records' not in spec:
        return  # Frozen/legacy documents do not contain a collector handoff.
    records = spec['source_records']
    if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
        raise ValueError('source_records_shape')
    if digest(records) != spec.get('source_records_sha256'):
        raise ValueError('source_records_hash_mismatch')
    for row in records:
        if row.get('partner_name', '').strip() != target['partner'].strip() or row.get('program', '').strip() != target['program'].strip():
            raise ValueError('source_record_target_mismatch')


def cache_records(records: list[dict]) -> list[dict]:
    """Ignore acquisition-only metadata, never timestamps inside source objects."""
    result = copy.deepcopy(records)
    for row in result:
        row.pop('observed_at', None)
        details = row.get('details')
        if isinstance(details, dict):
            for field in ('source_run', 'capture_sha256'):
                details.pop(field, None)
    return result


def request_text(document: dict, *, for_cache: bool = False) -> str:
    source = document.get('source', {})
    records = source.get('source_records', [])
    if not records:
        return document['text']
    if for_cache:
        records = cache_records(records)
    # No filtering or hand-authored summary of the original offer. The normalized
    # fields and original nested objects are both retained and labelled as such.
    supplement = (
        'COLLECTOR_RECORDS для указанного TARGET, без сокращения. '
        'Вложенные исходные объекты (например details.public_item) — данные источника; '
        'нормализованные поля — результат сборщика, а не независимое подтверждение. '
        'observed_at — время получения записи, не срок акции.\n'
        + json.dumps(records, ensure_ascii=False, sort_keys=True, allow_nan=False)
        + '\nEND_COLLECTOR_RECORDS\n\nПолный видимый текст захваченной страницы:\n'
    )
    return supplement + document['text']


def recorded_offer(records: list[dict]) -> bool:
    """A contradiction flag, not a semantic substitute for model extraction."""
    for row in records:
        if row.get('record_kind') == 'partner_offer' and any(
            isinstance(row.get(k), str) and row[k].strip()
            for k in ('benefit_text', 'conditions_text', 'redemption_text')
        ):
            return True
    return False


def negative_status(document: dict, answer: dict) -> str | None:
    if answer.get('has_offer') is not False:
        return None
    source = document.get('source', {})
    if recorded_offer(source.get('source_records', [])):
        return 'needs_review'
    capture = source.get('capture', {})
    if capture.get('input_contract_version') == INPUT_CONTRACT_VERSION and (
        not capture.get('target_found') or not capture.get('content_ready')
    ):
        return 'needs_source'
    return None


def cache_usable(item: dict, document: dict) -> bool:
    if item.get('status') in ('needs_source', 'needs_review'):
        return False
    if 'extracted' not in item:
        return False
    version = document.get('source', {}).get('capture', {}).get('input_contract_version')
    return not (version == INPUT_CONTRACT_VERSION and item['extracted'].get('has_offer') is False
                and item.get('input_contract_version') != INPUT_CONTRACT_VERSION)


def attach(spec: dict, target: dict, capture: dict) -> dict:
    records = copy.deepcopy(target.get('source_records', []))
    return {**spec, 'source_records': records, 'source_records_sha256': digest(records),
            'capture': {'input_contract_version': INPUT_CONTRACT_VERSION, **capture}}


def has_target(text: str, partner: str) -> bool:
    def normalized(value):
        return re.sub(r'\s+', ' ', value).strip().casefold()
    needle = normalized(partner)
    return bool(needle and needle in normalized(text))


def catalogue_ids(target: dict) -> list[str]:
    # DOM navigation identity only; values and interpretation remain in the source.
    return list(dict.fromkeys(str(r['native_id']) for r in target.get('source_records', [])
        if r.get('source_id') == 'konsierge_public' and str(r.get('native_id', '')).isdigit()))


def capture_url(target: dict) -> str:
    """Use existing same-origin detail URLs, never manufacture a merchant link."""
    records = target.get('source_records', [])
    candidates = {r.get('benefit_url') for r in records if r.get('benefit_url')}
    if len(candidates) == 1:
        candidate = next(iter(candidates))
        from public_transport import allowed_request
        if isinstance(candidate, str) and allowed_request(candidate, urlsplit(target['url']).hostname):
            return candidate
    return target['url']


async def prepare_public_page(page, target: dict) -> dict:
    """Wait for actual target content; absent readiness is diagnostic, not a gate.

    Konsierge exposes full descriptions in its browser JSON, not in a detail
    modal. Find the native card by image ID and title, retaining the raw object
    from the ordinary collector. No direct API call, guessed link or click.
    """
    from public_transport import check_response
    ids = catalogue_ids(target)
    catalogue = urlsplit(target['url']).hostname == 'konsierge.com' and bool(ids)
    info = {'target_found': False, 'content_ready': False,
            'scope': 'catalogue_card' if catalogue else 'page'}
    await page.evaluate("document.querySelectorAll('details').forEach(n => n.open = true)")
    if catalogue:
        info['native_ids'] = ids
        try:
            await page.wait_for_selector('qy-benefit-teaser', timeout=15000)
        except BrowserTimeout:
            info['readiness'] = 'catalogue_not_loaded'
            return info
        missing = list(ids)
        stalls = 0
        for _ in range(40):
            found = await page.evaluate('''({ids, name}) => {
                const norm = s => (s || '').replace(/\\s+/g,' ').trim().toLocaleLowerCase();
                return ids.filter(id => Array.from(document.querySelectorAll('qy-benefit-teaser')).some(n =>
                    norm(n.querySelector('.BenefitTeaser-Title')?.textContent) === norm(name) &&
                    Array.from(n.querySelectorAll('img')).some(im =>
                        [im.getAttribute('src'),im.getAttribute('data-src')].some(s =>
                            (s || '').includes('/benefit/image/' + id + '/')))));
            }''', {'ids': ids, 'name': target['partner']})
            missing = [ident for ident in ids if ident not in found]
            if not missing:
                info.update(target_found=True, content_ready=True, readiness='native_cards_loaded')
                return info
            count = await page.locator('qy-benefit-teaser').count()
            await page.evaluate('window.scrollTo(0,0)')
            await page.wait_for_timeout(250)
            await page.evaluate('window.scrollTo(0,document.documentElement.scrollHeight)')
            try:
                await page.wait_for_function('(n)=>document.querySelectorAll("qy-benefit-teaser").length>n',
                                             arg=count, timeout=5000)
                stalls = 0
            except BrowserTimeout:
                stalls += 1
                if stalls >= 2:
                    break
        info.update(readiness='target_cards_not_loaded', missing_native_ids=missing)
        check_response(200, await page.content())
        return info
    # Body text at domcontentloaded can be only a loading indicator. Wait for the
    # named target, then still scroll/reveal below-the-fold content in the caller.
    try:
        await page.wait_for_function('''name => {
            const norm = s => (s || '').replace(/\\s+/g,' ').trim().toLocaleLowerCase();
            return norm(document.body.innerText).includes(norm(name));
        }''', arg=target['partner'], timeout=10000)
        info.update(target_found=True, content_ready=True, readiness='target_text_loaded')
    except BrowserTimeout:
        info['readiness'] = 'target_text_not_loaded'
    return info
