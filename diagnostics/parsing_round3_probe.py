"""Bounded original HSE observations, without models, accounts or publication."""
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'loyalty'))
from playwright.async_api import async_playwright
from public_transport import PublicSource, check_response
from hse_alumni import ROOT as SOURCE_URL, PROGRAM, parse_catalog
from normalized import validate_offer
from merchant_queue import capture_page
from merchant_extract import load_manifest


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


async def run(out):
    out.mkdir(parents=True, exist_ok=False)
    code = [*sorted((ROOT / 'loyalty').glob('*.py')),
            ROOT / 'diagnostics/deepseek_acceptance.py', Path(__file__)]
    save(out / 'code-hashes.json', {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in code})
    observed = datetime.now(timezone.utc).isoformat()
    report = {'observed_at': observed, 'model_calls': 0, 'publication': False, 'observations': []}
    documents = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            async with PublicSource(browser, SOURCE_URL) as source:
                status, raw = await source.navigate(SOURCE_URL)
                check_response(status, raw)
            (out / 'catalogue.html').write_text(raw, encoding='utf-8')
            rows = parse_catalog(raw, observed)
            for row in rows:
                validate_offer(row)
            save(out / 'catalogue-records.json', rows)
            full = [r for r in rows if r['record_kind'] == 'partner_offer']
            previews = [r for r in rows if r['record_kind'] == 'source_observation']
            report.update(catalogue_records=len(rows), detail_records=len(full), preview_records=len(previews))
            if not full:
                raise ValueError('hse_no_current_details')
            # Selection is based on this response's structure, never a saved name/rate.
            candidates = [full[0], full[-1]]
            heading = next((r for r in full if r['details']['public_catalog_block'].get('identity_method') == 'catalogue_heading'), None)
            if heading:
                candidates.append(heading)
            if previews:
                candidates.append(previews[0])
            chosen = {r['native_id']: r for r in candidates}
            for index, row in enumerate(chosen.values(), 1):
                ident = 'hse_' + str(index)
                target = {'id': ident, 'url': row['source_url'], 'partner': row['partner_name'],
                          'program': PROGRAM, 'source_records': [row]}
                result = {'id': ident, 'native_id': row['native_id'], 'partner': row['partner_name'],
                          'bootstrap_detail_state': row['details']['public_catalog_block']['detail_state']}
                started = time.monotonic()
                try:
                    spec = await asyncio.wait_for(capture_page(browser, target, out), timeout=240)
                    check = out / 'check-manifest.json'
                    save(check, {'documents': [spec]})
                    document = load_manifest(check)[0]
                    check.unlink()
                    documents.append(spec)
                    result.update(status='captured', regions=len(spec['capture']['regions']),
                                  images=len(spec['images']), text_characters=len(document['text']),
                                  manifest_verified=True, scope=spec['capture']['scope'])
                except Exception as exc:
                    result.update(status='failed', error_type=type(exc).__name__, error=str(exc)[:400])
                result['elapsed_seconds'] = round(time.monotonic()-started, 3)
                report['observations'].append(result)
                save(out / 'observations.json', report)
                save(out / 'manifest.json', {'documents': documents})
                print(json.dumps(result, ensure_ascii=False), flush=True)
        finally:
            await browser.close()
            report['finished_at'] = datetime.now(timezone.utc).isoformat()
            save(out / 'observations.json', report)
    save(out / 'evidence-hashes.json', {str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
         for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'evidence-hashes.json'})


if __name__ == '__main__':
    asyncio.run(run(Path(sys.argv[1])))
