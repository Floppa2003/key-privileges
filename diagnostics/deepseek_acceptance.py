"""Prepare frozen controls and new public pages for the selected extractor.

This is acceptance-data preparation, not a second extractor. No model secrets,
search, account cookies, publishing, OCR or source-specific extraction rules.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'loyalty'))
from merchant_extract import save


def tile_png(raw: bytes) -> list[bytes]:
    """Lossless ordered screenshot tiles, with no dropped bottom rows."""
    image = Image.open(io.BytesIO(raw))
    image.load()
    if image.width > 1024 or image.height > 40960:
        raise ValueError('image_budget_no_truncation')
    result = []
    for top in range(0, image.height, 1024):
        buffer = io.BytesIO()
        image.crop((0, top, image.width, min(top + 1024, image.height))).save(buffer, format='PNG')
        result.append(buffer.getvalue())
    return result


def store(out: Path, case: str, target: dict, text: str, images: list[bytes], *, source_url=None) -> dict:
    folder = out / case
    folder.mkdir(exist_ok=True)
    (folder / 'visible-text.txt').write_text(text, encoding='utf-8')
    names = []
    for n, raw in enumerate(images, 1):
        name = f'{case}/page-{n}.png'
        (out / name).write_bytes(raw)
        names.append(name)
    text_name = f'{case}/visible-text.txt'
    return {'id': case, 'target': target, 'text': text_name, 'images': names,
            'source_url': source_url,
            'sha256': {n: hashlib.sha256((out/n).read_bytes()).hexdigest() for n in [text_name, *names]}}


async def prepare(frozen: Path, out: Path) -> None:
    from playwright.async_api import async_playwright
    from public_transport import PublicSource, check_response

    out.mkdir(parents=True, exist_ok=False)
    documents, observations = [], []
    system = (ROOT/'loyalty/merchant_prompt.txt').read_text(encoding='utf-8')
    schema = json.loads((ROOT/'loyalty/merchant_offer.schema.json').read_text())
    for doc in json.loads(frozen.read_text()):
        if doc['system'] != system or doc['schema'] != schema:
            raise ValueError('acceptance_contract_changed')
        target_text, full_text = doc['text'].split('\nВсе изображения идут по порядку страниц. Полный текст:\n', 1)
        target = json.loads(target_text.split('\n', 1)[0].removeprefix('TARGET: '))
        images = [base64.b64decode(b, validate=True) for b in doc['images']]
        documents.append(store(out, doc['id'], target, full_text, images))
        observations.append({'id':doc['id'], 'kind':'frozen_control', 'status':'prepared',
                             'images':len(images), 'source_as_of':target['as_of']})

    # These are acceptance samples, not a list of permitted merchants in the extractor.
    samples = [
        ('af_parkfly', 'Park&Fly', 'Аэрофлот Бонус'),
        ('ekp_litres', 'Литрес', 'Единая карта петербуржца'),
        ('mantera_moments', 'Мантера', 'Мантера Моменты'),
        ('flystation_public', 'FlyStation', 'Публичные акции FlyStation'),
    ]
    sources = {s['id']:s for s in json.loads((ROOT/'loyalty/sources_normalized.json').read_text())}
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        for case, partner, program in samples:
            url = sources[case]['url']
            row = {'id':case, 'url':url, 'kind':'new_to_deepseek', 'status':'failed'}
            folder=out/case
            folder.mkdir()
            try:
                async with PublicSource(browser, url) as source:
                    await source.page.set_viewport_size({'width':1024,'height':1024})
                    status, html = await source.navigate(url)
                    row.update(http_status=status, final_url=source.page.url)
                    (folder/'source.html').write_text(html,encoding='utf-8')
                    check_response(status, html)
                    # Trigger ordinary lazy content by scrolling; never click or bypass a gate.
                    for _ in range(40):
                        size=await source.page.evaluate('({y:scrollY,h:innerHeight,total:document.documentElement.scrollHeight})')
                        if size['total']>40960:raise ValueError('image_budget_no_truncation')
                        if size['y']+size['h']>=size['total']-2:break
                        await source.page.evaluate('window.scrollBy(0,900)')
                        await source.page.wait_for_timeout(100)
                    else:raise ValueError('scroll_budget_no_truncation')
                    await source.page.evaluate('window.scrollTo(0,0)')
                    await source.page.wait_for_timeout(700)
                    text=await source.page.locator('body').inner_text(timeout=15000)
                    if not text.strip():raise ValueError('empty_page')
                    html=await source.page.content()
                    (folder/'source.html').write_text(html,encoding='utf-8')
                    raw=await source.page.screenshot(full_page=True,animations='disabled',timeout=30000)
                    (folder/'full.png').write_bytes(raw)
                    target={'partner':partner,'program':program,'as_of':datetime.now(timezone.utc).date().isoformat()}
                    images=tile_png(raw)
                    documents.append(store(out,case,target,text,images,source_url=url))
                    row.update(status='prepared',images=len(images),text_chars=len(text))
            except Exception as exc:
                row.update(error_type=type(exc).__name__,error=str(exc)[:500])
            observations.append(row)
            save(out/'capture-summary.json',{'observed_at':datetime.now(timezone.utc).isoformat(),
                'publication_allowed':False,'observations':observations})
            print(json.dumps(row,ensure_ascii=False),flush=True)
        await browser.close()
    save(out/'manifest.json',{'documents':documents})


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frozen-inputs',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    asyncio.run(prepare(args.frozen_inputs,args.out))


if __name__=='__main__':main()
