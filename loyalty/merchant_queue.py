"""Daily public-page LLM queue. Persistent progress; independent free quotas, no publishing or paid fallback."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlsplit

import merchant_extract as extractor
from model import clean_url

HERE = Path(__file__).resolve().parent
DAILY_REQUESTS = 50
REQUEST_INTERVAL = 7
# Harbor's 200/day is OUR workload ceiling, not a claim about its weekly allowance.
PROVIDER_DAILY_LIMITS = {'orcarouter': DAILY_REQUESTS, 'tokenharbor': 200}
PROVIDER_INTERVALS = {'orcarouter': REQUEST_INTERVAL, 'tokenharbor': 2}
POOL_REQUESTS = sum(PROVIDER_DAILY_LIMITS.values())
MAX_CAPTURE_PAGES = 300


def provider_state(state: dict, provider: str) -> dict:
    extractor.provider_config(provider)
    # Keep the original Orca ledger in place: no quota reset when upgrading v1.
    if provider == 'orcarouter':
        return state
    return state.setdefault('providers', {}).setdefault(provider, {
        'usage': {'date': '', 'attempts': 0}, 'provider_not_before': 0, 'last_request_at': 0})


def provider_eligible(state: dict, provider: str, timestamp: float) -> bool:
    ledger = provider_state(state, provider)
    day = datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat()
    return ledger.get('provider_not_before', 0) <= timestamp and not (
        ledger['usage']['date'] == day and ledger['usage']['attempts'] >= PROVIDER_DAILY_LIMITS[provider])



def new_state() -> dict:
    return {'version': 1, 'items': {}, 'usage': {'date': '', 'attempts': 0},
            'provider_not_before': 0, 'last_request_at': 0}


def read_state(path: Path) -> dict:
    if not path.exists():
        return new_state()
    state = extractor.strict_json(path.read_text(encoding='utf-8'))
    if state.get('version') != 1 or not isinstance(state.get('items'), dict):
        raise ValueError('unsupported_or_corrupt_queue_state')
    return state


def write_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    extractor.save(temporary, state)
    temporary.replace(path)


def discover_targets(catalog: dict | None, partners: dict, rules: dict) -> list[dict]:
    """Source registries are seeds, not an allowlist; new catalogue partners join automatically."""
    candidates = [dict(value, source_id=sid) for mapping in (partners, rules)
                  for sid, value in mapping.items()]
    candidates.extend({'url': r.get('source_url'), 'partner': r.get('partner_name'),
                       'program': r.get('program'), 'source_id': r.get('source_id')}
                      for r in (catalog or {}).get('records', []))
    result = {}
    for candidate in candidates:
        partner, program = candidate.get('partner'), candidate.get('program')
        if not all(isinstance(v, str) and v.strip() for v in (partner, program)):
            continue
        try:
            url = clean_url(candidate['url'])
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
        identity = [url, partner.strip(), program.strip()]
        ident = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()[:32]
        result.setdefault(ident, {'id': ident, 'url': url, 'partner': partner.strip(),
                                  'program': program.strip(), 'source_id': candidate.get('source_id')})
    return list(result.values())


def merge_targets(state: dict, targets: list[dict]) -> None:
    # Incomplete catalogue reads must not delete previously discovered work/results.
    for target in targets:
        item = state['items'].setdefault(target['id'], {})
        item['target'] = target


def pending_targets(state: dict) -> list[dict]:
    items = [item for item in state['items'].values() if 'target' in item]
    # Preserve insertion order within a cohort: newly discovered, then oldest checked.
    items.sort(key=lambda item: item.get('last_checked', 0))
    return [item['target'] for item in items]


def fingerprint(document: dict, schema: dict, system: str) -> str:
    target = {**document['target'], 'as_of': ''}
    payload = extractor.build_request(target, document['text'], document['images'], schema, system)
    raw = json.dumps({'endpoint': extractor.ENDPOINT, 'payload': payload},
                     ensure_ascii=False, sort_keys=True, allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def process_documents(documents: list[dict], state: dict, state_path: Path, out: Path,
                      key: str, schema: dict, system: str, *, session=None,
                      now=time.time, sleep=time.sleep, max_requests=DAILY_REQUESTS, time_budget=1500,
                      provider='orcarouter') -> dict:
    ledger = provider_state(state, provider)
    daily_limit = PROVIDER_DAILY_LIMITS[provider]
    if not 1 <= max_requests <= daily_limit:
        raise ValueError('daily_request_budget')
    out.mkdir(parents=True, exist_ok=False)
    deadline = now() + time_budget
    summary = {'status': 'completed', 'completed': 0, 'cached': 0, 'http_attempts': 0,
               'results': [], 'not_attempted': [], 'publication_allowed': False}
    for index, document in enumerate(documents):
        ident = document['id']
        item = state['items'].setdefault(ident, {})
        digest = fingerprint(document, schema, system)
        if item.get('fingerprint') == digest and 'extracted' in item:
            summary['cached'] += 1
            item.update(last_checked=now(), status='cached')
            summary['results'].append({'id': ident, 'status': 'cached',
                                       'inferred_as_of': item.get('inferred_as_of')})
            write_state(state_path, state)
            continue
        day = datetime.fromtimestamp(now(), timezone.utc).date().isoformat()
        if ledger['usage']['date'] != day:
            ledger['usage'] = {'date': day, 'attempts': 0}
        remaining = min(daily_limit - ledger['usage']['attempts'],
                        max_requests - summary['http_attempts'])
        if ledger.get('provider_not_before', 0) > now() or remaining <= 0 or now() >= deadline:
            summary.update(status='deferred', not_attempted=[d['id'] for d in documents[index:]])
            break
        wait = ledger.get('last_request_at', 0) + PROVIDER_INTERVALS[provider] - now()
        if wait > 0:
            sleep(wait)
        folder = out / ident
        payload = extractor.prepare_document(document, folder, schema, system, provider=provider)
        # Reserve before IO. An interrupted request must not silently restore its quota.
        reserved = min(extractor.MAX_ATTEMPTS, remaining)
        ledger['usage']['attempts'] += reserved
        ledger['last_request_at'] = now()
        item['status'] = 'in_flight'
        write_state(state_path, state)
        result = extractor.infer(payload, schema, folder / 'direct', key,
                                 session=session, sleep=sleep, max_attempts=reserved, provider=provider)
        attempts = result['http_attempts']
        ledger['usage']['attempts'] -= reserved - attempts
        ledger['last_request_at'] = now()
        summary['http_attempts'] += attempts
        item.update(status=result['status'], last_checked=now(), last_result=result)
        if result['status'] == 'completed':
            item.update(fingerprint=digest,
                        extracted=extractor.strict_json((folder / 'direct/extracted.json').read_text()),
                        inferred_as_of=document['target']['as_of'], inferred_at=now(),
                        inferred_provider=provider, returned_model=result.get('returned_model'),
                        publication_allowed=False)
            summary['completed'] += 1
        else:
            summary['status'] = 'incomplete'
        summary['results'].append({'id': ident, 'status': result['status'], 'http_attempts': attempts})
        stop = result.get('stop_batch_reason')
        if stop == 'provider_rate_limited':
            # No server reset hint means temporary saturation, not an invented daily reset.
            ledger['provider_not_before'] = now() + max(60, result.get('retry_after_seconds', 0))
        write_state(state_path, state)
        extractor.save(out / 'summary.json', summary)
        if stop or result['status'] == 'credential_echo':
            summary.update(stop_reason=stop or 'credential_echo',
                           status='deferred' if stop == 'provider_rate_limited' else 'incomplete',
                           not_attempted=[d['id'] for d in documents[index+1:]])
            break
    summary.update(provider=provider, daily_usage=ledger['usage'], provider_not_before=ledger.get('provider_not_before', 0),
                   queue_size=len(state['items']))
    write_state(state_path, state)
    extractor.save(out / 'summary.json', summary)
    return summary


def process_pool(documents: list[dict], state: dict, state_path: Path, out: Path,
                 keys: dict, schema: dict, system: str, *, sessions=None,
                 now=time.time, sleep=time.sleep, max_requests=POOL_REQUESTS,
                 time_budget=4500, providers=('orcarouter', 'tokenharbor')) -> dict:
    """Try independent free accounts in order, never regenerate a model answer.

    Both routes share the evidence/contract fingerprint, not serving credentials.
    Exact serving route and returned snapshot remain attached to each accepted result.
    """
    if not 1 <= max_requests <= POOL_REQUESTS:
        raise ValueError('pool_request_budget')
    if not providers or len(set(providers)) != len(providers):
        raise ValueError('invalid_provider_order')
    for provider in providers:
        extractor.provider_config(provider)
    out.mkdir(parents=True, exist_ok=False)
    deadline = now() + time_budget
    def cached(document):
        item = state['items'].get(document['id'], {})
        return 'extracted' in item and item.get('fingerprint') == fingerprint(document, schema, system)
    initially_cached = {d['id'] for d in documents if cached(d)}
    for ident in initially_cached:
        state['items'][ident].update(last_checked=now(), status='cached')
    summary = {'status': 'completed', 'completed': 0, 'cached': len(initially_cached),
               'http_attempts': 0, 'providers': [], 'pending': [], 'publication_allowed': False}
    no_retry = set()
    for provider in providers:
        pending = [d for d in documents if not cached(d) and d['id'] not in no_retry]
        if not pending or summary['http_attempts'] >= max_requests or now() >= deadline:
            break
        key = keys.get(provider, '')
        if not isinstance(key, str) or not key.strip():
            summary['providers'].append({'provider': provider, 'status': 'missing_key', 'http_attempts': 0})
            continue
        result = process_documents(pending, state, state_path, out / provider, key, schema, system,
            provider=provider, session=(sessions or {}).get(provider), now=now, sleep=sleep,
            max_requests=min(PROVIDER_DAILY_LIMITS[provider], max_requests-summary['http_attempts']),
            time_budget=max(0, deadline-now()))
        summary['providers'].append(result)
        summary['completed'] += result['completed']
        summary['http_attempts'] += result['http_attempts']
        # Validation failures are model answers, not quota failures. Unknown network
        # outcomes are also not retried via a second account in this run.
        no_retry.update(row['id'] for row in result['results']
                        if row['status'] in ('failed_validation', 'transport_error'))
        stop = result.get('stop_reason')
        if stop in ('credential_echo', 'nonzero_reported_cost', 'invalid_reported_cost'):
            summary['stop_reason'] = stop
            break
        extractor.save(out/'summary.json', summary)
    summary['pending'] = [d['id'] for d in documents if not cached(d)]
    summary['queue_size'] = len(state['items'])
    if summary.get('stop_reason') or no_retry:
        summary['status'] = 'incomplete'
    elif not documents:
        summary['status'] = 'no_input'
    elif summary['pending']:
        usable = any(isinstance(keys.get(p), str) and keys[p].strip() for p in providers)
        summary['status'] = 'deferred' if usable else 'unavailable'
    write_state(state_path, state)
    extractor.save(out/'summary.json', summary)
    return summary


async def capture_page(browser, target: dict, out: Path) -> dict:
    # Reuse the existing lossless evidence recorder. No acceptance case list is used.
    sys.path.insert(0, str(HERE.parent))
    from diagnostics.deepseek_acceptance import tile_png, store
    from public_transport import PublicSource, check_response
    ident, url = target['id'], target['url']
    folder = out / ident
    folder.mkdir()
    async with PublicSource(browser, url) as source:
        if urlsplit(url).path.lower().endswith('.pdf'):
            raw = await source.read_pdf(url)
            pdf = folder / 'source.pdf'; pdf.write_bytes(raw)
            # Embedded text plus ALL rendered pages. No OCR or text-only substitution.
            subprocess.run(['pdftotext', '-layout', str(pdf), str(folder/'visible-text.txt')],
                           check=True, timeout=60, capture_output=True)
            subprocess.run(['pdftoppm', '-scale-to', '1024', '-png', str(pdf), str(folder/'pdf')],
                           check=True, timeout=180, capture_output=True)
            pages = sorted(folder.glob('pdf-*.png'), key=lambda p: int(p.stem.split('-')[-1]))
            if not 1 <= len(pages) <= 40:
                raise ValueError('image_count_budget_no_truncation')
            images = [p.read_bytes() for p in pages]
            text = (folder/'visible-text.txt').read_text(encoding='utf-8')
            if not text.strip(): text = '[PDF without embedded text; use all attached rendered pages.]'
        else:
            await source.page.set_viewport_size({'width': 1024, 'height': 1024})
            status, html = await source.navigate(url)
            check_response(status, html)
            # Reveal native HTML disclosures; no form submissions or account interaction.
            await source.page.evaluate("document.querySelectorAll('details').forEach(n => n.open = true)")
            for _ in range(40):
                size = await source.page.evaluate('({y:scrollY,h:innerHeight,total:document.documentElement.scrollHeight})')
                if size['total'] > 40960: raise ValueError('image_budget_no_truncation')
                if size['y'] + size['h'] >= size['total'] - 2: break
                await source.page.evaluate('window.scrollBy(0,900)')
                await source.page.wait_for_timeout(100)
            else: raise ValueError('scroll_budget_no_truncation')
            await source.page.evaluate('window.scrollTo(0,0)')
            await source.page.wait_for_timeout(700)
            text = await source.page.locator('body').inner_text(timeout=15000)
            if not text.strip(): raise ValueError('empty_page')
            (folder/'source.html').write_text(await source.page.content(), encoding='utf-8')
            images = tile_png(await source.page.screenshot(full_page=True, animations='disabled', timeout=30000))
        return store(out, ident, {'partner': target['partner'], 'program': target['program'],
                                  'as_of': datetime.now(timezone.utc).date().isoformat()},
                     text, images, source_url=url)


async def prepare_queue(state_path: Path, catalog_path: Path, out: Path, max_pages: int,
                        providers=('orcarouter',)) -> dict:
    from playwright.async_api import async_playwright
    if not 1 <= max_pages <= MAX_CAPTURE_PAGES: raise ValueError('capture_budget')
    state = read_state(state_path)
    catalog = extractor.strict_json(catalog_path.read_text()) if catalog_path.exists() else None
    targets = discover_targets(catalog, json.loads((HERE/'partner_pages.json').read_text()),
                                json.loads((HERE/'known_rules.json').read_text()))
    merge_targets(state, targets)
    out.mkdir(parents=True, exist_ok=False)
    documents, observations = [], []
    day = datetime.now(timezone.utc).date().isoformat()
    eligible = any(provider_eligible(state, provider, time.time()) for provider in providers)
    if eligible:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            started = time.monotonic()
            try:
                for target in pending_targets(state)[:max_pages]:
                    if time.monotonic() - started > 1200: break
                    ident = target['id']
                    try:
                        document = await asyncio.wait_for(capture_page(browser, target, out), timeout=240)
                        # Validate this document alone: one oversized input must not block its neighbours.
                        extractor.save(out/'check-document.json', {'documents': [document]})
                        extractor.load_manifest(out/'check-document.json')
                        (out/'check-document.json').unlink()
                        documents.append(document)
                        observations.append({'id': ident, 'status': 'captured', 'url': target['url']})
                        # A captured but not inferred page stays at the front of the queue.
                    except Exception as exc:
                        state['items'][ident].update(last_checked=time.time(), capture_status='failed',
                                                    capture_error=type(exc).__name__)
                        observations.append({'id': ident, 'status': 'failed', 'error_type': type(exc).__name__,
                                             'error': str(exc)[:300], 'url': target['url']})
                    write_state(state_path, state)
                    extractor.save(out/'manifest.json', {'documents': documents})
                    extractor.save(out/'capture-summary.json', {'observations': observations})
            finally:
                await browser.close()
    write_state(state_path, state)
    result = {'observations': observations, 'queue_size': len(state['items']), 'captured': len(documents),
              'catalog_available': catalog is not None, 'provider_eligible': eligible,
              'publication_allowed': False}
    extractor.save(out/'manifest.json', {'documents': documents})
    extractor.save(out/'capture-summary.json', result)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prepare = sub.add_parser('prepare')
    prepare.add_argument('--catalog', type=Path, required=True)
    prepare.add_argument('--max-pages', type=int, default=100)
    extract = sub.add_parser('extract')
    extract.add_argument('--manifest', type=Path, required=True)
    extract.add_argument('--max-requests', type=int, default=DAILY_REQUESTS)
    extract.add_argument('--execute', action='store_true')
    pool = sub.add_parser('pool')
    pool.add_argument('--manifest', type=Path, required=True)
    pool.add_argument('--max-requests', type=int, default=POOL_REQUESTS)
    pool.add_argument('--execute', action='store_true')
    pool.add_argument('--providers', default='orcarouter,tokenharbor')
    prepare.add_argument('--providers', default='orcarouter')
    for command in (prepare, extract, pool):
        command.add_argument('--state', type=Path, required=True)
        command.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == 'prepare':
        result = asyncio.run(prepare_queue(args.state, args.catalog, args.out, args.max_pages,
                                          providers=tuple(args.providers.split(','))))
    elif not args.execute:
        args.out.mkdir(parents=True, exist_ok=False)
        result = {'status': 'prepared_not_inferred', 'http_attempts': 0, 'publication_allowed': False}
        extractor.save(args.out/'summary.json', result)
    else:
        import os
        state = read_state(args.state)
        manifest = extractor.strict_json(args.manifest.read_text())
        documents = extractor.load_manifest(args.manifest, max_documents=MAX_CAPTURE_PAGES) if manifest['documents'] else []
        schema = extractor.strict_json((HERE/'merchant_offer.schema.json').read_text())
        system = (HERE/'merchant_prompt.txt').read_text()
        if args.command == 'pool':
            providers = tuple(args.providers.split(','))
            keys = {p: os.environ.get(extractor.provider_config(p)['secret'], '') for p in providers}
            result = process_pool(documents, state, args.state, args.out, keys, schema, system,
                                  max_requests=args.max_requests, providers=providers)
        else:
            result = process_documents(documents, state, args.state, args.out,
                os.environ.get('ORCAROUTER_API_KEY', ''), schema, system, max_requests=args.max_requests)
        # Quota deferral is a normal queue outcome, not a fictitious parser failure.
        if not documents and args.command == 'extract':
            today = datetime.now(timezone.utc).date().isoformat()
            limited = state.get('provider_not_before', 0) > time.time() or (
                state['usage']['date'] == today and state['usage']['attempts'] >= DAILY_REQUESTS)
            result['status'] = 'deferred' if limited else 'no_input'
            extractor.save(args.out/'summary.json', result)
    print(json.dumps(result, ensure_ascii=False))
    return 2 if result.get('stop_reason') in ('provider_access_error','provider_nonretryable_error',
                                             'credential_echo','nonzero_reported_cost','invalid_reported_cost') else 0


if __name__ == '__main__':
    raise SystemExit(main())
