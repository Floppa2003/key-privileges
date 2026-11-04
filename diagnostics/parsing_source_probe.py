"""Bounded anonymous DOM evidence for the two failed source parsers.

No publication, credentials, model calls, clicks or form submissions. A saved
failure DOM is diagnostic evidence and is never an accepted catalogue.
"""
import asyncio
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'loyalty'))
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from public_transport import PublicSource, check_response
from source_diagnostics import error_record
from flystation_source import inventory
from known_rules import parse_known_rule

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else 'parsing-probe-output')
CASES = [
    ('flystation', 'https://flystation.net/promotions'),
    ('t2-magnit', 'https://msk.t2.ru/help/article/magnit-plus-premium'),
]
SOURCE_CONFIG = json.loads((ROOT / 'loyalty/sources_normalized.json').read_text())


def save_dom(name, stage, raw, metadata):
    data = raw.encode('utf-8')
    path = OUT / f'{name}-{stage}.html'
    path.write_bytes(data)
    soup = BeautifulSoup(raw, 'html.parser')
    return dict(path=path.name, sha256=hashlib.sha256(data).hexdigest(), bytes=len(data),
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        title=soup.title.get_text(' ', strip=True) if soup.title else None,
        selectors={selector: len(soup.select(selector)) for selector in (
            'section.promotions', '.promotions__slider-item-text',
            '.promotions__accordion-inner', '.article-content',
            '.support-article__article-title', 'h1', 'h2')}, **metadata)


async def probe(browser, name, url):
    result = {'name': name, 'url': url, 'stages': []}
    observed = datetime.now(timezone.utc).isoformat()
    async with PublicSource(browser, url) as client:
        responses = []
        def observe(response):
            if response.request.is_navigation_request() and response.request.frame == client.page.main_frame:
                responses.append({'url': response.url, 'status': response.status})
        client.page.on('response', observe)
        try:
            for stage in ('initial', 'settled'):
                if stage == 'initial':
                    cfg = next((c for c in SOURCE_CONFIG if c['id'] == 't2_magnit_rules'), {}) if name == 't2-magnit' else {}
                    readiness = {'ready_selector': cfg['ready_selector']} if cfg.get('ready_selector') else {}
                    raw = await client.read(url, render=True, **readiness)
                else:
                    # Observe the ordinary page after hydration without another
                    # request, interaction or an assumption about a CSS selector.
                    await client.page.wait_for_timeout(10000)
                    raw = await client.page.content()
                    client.check_url(client.page.url)
                    if not responses:
                        raise RuntimeError('missing_navigation_response')
                    client.check_url(responses[-1]['url'])
                    check_response(responses[-1]['status'], raw)
                info = save_dom(name, stage, raw, dict(final_url=client.page.url,
                    response=responses[-1] if responses else None, accepted_read=True))
                try:
                    rows = inventory(raw) if name == 'flystation' else parse_known_rule(
                        't2_magnit_rules', raw, url, observed)
                    info['parse'] = {'status': 'ok', 'records': len(rows)}
                except Exception as exc:
                    info['parse'] = error_record(exc, 'parse', url)
                result['stages'].append(info)
        except Exception as exc:
            result['error'] = error_record(exc, 'read', url)
            try:
                result['stages'].append(save_dom(name, 'failure', await client.page.content(),
                    dict(final_url=client.page.url, accepted_read=False,
                         response=responses[-1] if responses else None)))
            except Exception as snapshot_error:
                result['snapshot_error'] = type(snapshot_error).__name__
        finally:
            client.page.remove_listener('response', observe)
    (OUT / f'{name}.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False))


async def probe_capture(browser, source_id):
    from known_rules import CONFIG
    from merchant_queue import capture_page
    from merchant_extract import load_manifest
    cfg = CONFIG[source_id]
    target = {'id': source_id, 'url': cfg['url'], 'partner': cfg['partner'], 'program': cfg['program']}
    folder = OUT / 'raw-captures'
    folder.mkdir(exist_ok=True)
    result = {'source_id': source_id, 'url': cfg['url'], 'model_requests': 0}
    try:
        spec = await asyncio.wait_for(capture_page(browser, target, folder), timeout=240)
        manifest = folder / f'{source_id}-manifest.json'
        manifest.write_text(json.dumps({'documents': [spec]}, ensure_ascii=False, indent=2)+'\n')
        documents = load_manifest(manifest)
        text = (folder / spec['text']).read_text()
        original = folder / source_id / ('source.pdf' if spec['capture']['scope'] == 'pdf' else 'source.html')
        result.update(status='captured_and_manifest_validated', documents=len(documents),
            capture=spec['capture'], images=len(spec['images']), text_characters=len(text),
            source_sha256=hashlib.sha256(original.read_bytes()).hexdigest())
    except Exception as exc:
        result.update(status='failed', error=error_record(exc, 'capture', cfg['url']))
    (OUT / f'{source_id}-capture.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False))


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            for case in CASES:
                await asyncio.wait_for(probe(browser, *case), timeout=180)
            for source_id in ('rzd_finuslugi_rules', 'af_vipzal_rules'):
                await probe_capture(browser, source_id)
        finally:
            await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
