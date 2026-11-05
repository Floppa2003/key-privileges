"""Bounded original-source observations; no model, provider or Sheets calls.

Every failure remains a failure in observations.json. A completed probe job
means its evidence was recorded, not that all external sites were available.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'loyalty'))
import collect_normalized as collector
import merchant_queue as queue
import merchant_extract as extractor
from playwright.async_api import async_playwright
from recovered_contract import SOURCES

GROUPS = {
    'catalogue': [
        ('moskvich', 'https://moskvichmag.ru/programma-loyalnosti/', 'Москвич'),
        ('hse', 'https://alumni.hse.ru/loyalty/partners/', 'Skyeng'),
    ],
    'merchants': [
        ('sochi', 'https://sochiparkhotel.ru/about/programma-loyalnosti/', 'Сочи'),
        ('bootwood', 'https://bootwood.com/afl_bonus/', 'BOOTWOOD'),
        ('seagalaxy', 'https://seagalaxy.com/spec/programma-loyalnosti-krylya-offer', 'Крылья'),
        ('arendacar', 'https://sykt.arendacar.ru/news/novyj-partnjor-kompanii-uralskie-avialinii/', 'Уральские'),
    ],
    'banks': [
        (sid, SOURCES[sid]['url'], partner) for sid, partner in (
            ('af_primbank_rules', 'Аэрофлот'), ('af_vtb_rules', 'Аэрофлот'),
            ('nspk_ekp_rules', 'ЕКП'), ('uralsib_rzd_rules', 'РЖД'))
    ],
}


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


async def run(group, out):
    out.mkdir(parents=True, exist_ok=False)
    observed = datetime.now(timezone.utc).isoformat()
    observations, documents = [], []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            if group == 'static':
                configs = {row['id']: row for row in json.loads((ROOT / 'loyalty/sources_normalized.json').read_text())}
                for sid in ('ural_gloria_rules', 'af_istochnik'):
                    start = time.monotonic()
                    row = {'id': sid, 'url': configs[sid]['url']}
                    try:
                        report, records = await asyncio.wait_for(collector.one(browser, configs[sid], observed, 500), timeout=240)
                        save(out / (sid + '.json'), {'report': report, 'records': records})
                        row.update(status=report['status'], records=len(records), errors=report['errors'])
                    except Exception as exc:
                        row.update(status='failed', records=0, error_type=type(exc).__name__, error=str(exc)[:400])
                    row['elapsed_seconds'] = round(time.monotonic() - start, 3)
                    observations.append(row)
                    save(out / 'observations.json', {'group': group, 'observed_at': observed, 'observations': observations,
                                                     'model_calls': 0, 'publication': False})
                    print(json.dumps(row, ensure_ascii=False), flush=True)
            else:
                for ident, url, partner in GROUPS[group]:
                    start = time.monotonic()
                    row = {'id': ident, 'url': url}
                    try:
                        spec = await asyncio.wait_for(queue.capture_page(browser,
                            {'id': ident, 'url': url, 'partner': partner, 'program': 'Original public source observation'}, out), timeout=240)
                        check = out / 'check-manifest.json'
                        save(check, {'documents': [spec]})
                        loaded = extractor.load_manifest(check)[0]
                        check.unlink()
                        documents.append(spec)
                        row.update(status='captured', text_characters=len(loaded['text']),
                                   images=len(spec['images']), capture=spec.get('capture'), manifest_verified=True)
                    except Exception as exc:
                        row.update(status='failed', error_type=type(exc).__name__, error=str(exc)[:400])
                    row['elapsed_seconds'] = round(time.monotonic() - start, 3)
                    observations.append(row)
                    save(out / 'manifest.json', {'documents': documents})
                    save(out / 'observations.json', {'group': group, 'observed_at': observed, 'observations': observations,
                                                     'model_calls': 0, 'publication': False})
                    print(json.dumps(row, ensure_ascii=False), flush=True)
        finally:
            await browser.close()
    save(out / 'evidence-hashes.json', {str(path.relative_to(out)): hashlib.sha256(path.read_bytes()).hexdigest()
         for path in sorted(out.rglob('*')) if path.is_file() and path.name != 'evidence-hashes.json'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('group', choices=['static', *GROUPS])
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    asyncio.run(run(args.group, args.output))
