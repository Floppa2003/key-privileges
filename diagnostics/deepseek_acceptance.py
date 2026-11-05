"""Prepare frozen controls and new public pages for the selected extractor.

This is acceptance-data preparation, not a second extractor. No model secrets,
search, account cookies, publishing, OCR or source-specific extraction rules.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
from contextlib import contextmanager
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


TILE_SIZE = 1024
MAX_TILES = 40
MAX_HEIGHT = TILE_SIZE * MAX_TILES
SCROLL_STEP = 900
# Forty screenshots and forty overlapping scroll movements are different limits.
# The final position is checked after the last permitted movement as well.
MAX_SCROLL_STEPS = (MAX_HEIGHT + SCROLL_STEP - 1) // SCROLL_STEP
PAGE_GEOMETRY_JS = '''({x:scrollX,y:scrollY,w:innerWidth,h:innerHeight,
    width:Math.max(innerWidth,document.documentElement.scrollWidth,document.body?.scrollWidth||0,
        document.documentElement.offsetWidth,document.body?.offsetWidth||0,
        document.documentElement.clientWidth,document.body?.clientWidth||0),
    total:Math.max(innerHeight,document.documentElement.scrollHeight,document.body?.scrollHeight||0,
        document.documentElement.offsetHeight,document.body?.offsetHeight||0,
        document.documentElement.clientHeight,document.body?.clientHeight||0)})'''


@contextmanager
def capture_diagnostics(folder: Path, url: str, *, transport_snapshot=None):
    """Keep failed acquisition evidence separate from manifest admission."""
    info = {'version': 1, 'status': 'acquiring', 'stage': 'navigate', 'source_url': url,
            'started_at': datetime.now(timezone.utc).isoformat(), 'files': {},
            'limits': {'tile_width': TILE_SIZE, 'tile_height': TILE_SIZE, 'max_tiles': MAX_TILES,
                       'max_height': MAX_HEIGHT, 'max_pixels': TILE_SIZE * TILE_SIZE * MAX_TILES,
                       'scroll_step': SCROLL_STEP, 'max_scroll_steps': MAX_SCROLL_STEPS}}
    try:
        yield info
    except BaseException as exc:
        # Cancellation by the existing per-capture deadline must leave a failed
        # diagnostic too; it must never turn into a successful document.
        info.update(status='failed', error_type=type(exc).__name__, error=str(exc)[:500])
        raise
    else:
        info.update(status='complete', stage='complete')
    finally:
        if transport_snapshot:
            transport = transport_snapshot()
            if transport:
                info['transport'] = transport
        info['finished_at'] = datetime.now(timezone.utc).isoformat()
        save(folder / 'capture-diagnostics.json', info)


def record_capture_text(folder: Path, name: str, value: str, info: dict) -> None:
    """Persist already-read public evidence even if a later bounded step fails."""
    raw = value.encode('utf-8')
    (folder / name).write_bytes(raw)
    info['files'][name] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                           'stage': info['stage']}


def _image_geometry(width: int, height: int) -> dict:
    columns = (width + TILE_SIZE - 1) // TILE_SIZE
    rows = (height + TILE_SIZE - 1) // TILE_SIZE
    return {'width': width, 'height': height, 'columns': columns, 'rows': rows,
            'required_tiles': columns * rows, 'pixels': width * height}


def _image_budget_error(info: dict, geometry: dict, reason: str) -> None:
    info['budget_failure'] = {'code': 'image_budget_no_truncation', 'stage': info['stage'],
                              'reason': reason, **geometry, 'max_tiles': MAX_TILES,
                              'max_height': MAX_HEIGHT}
    raise ValueError('image_budget_no_truncation: '
                     f"stage={info['stage']} reason={reason} width={geometry['width']} "
                     f"height={geometry['height']} required_tiles={geometry['required_tiles']} "
                     f'max_tiles={MAX_TILES}')


def _check_image_budget(info: dict, geometry: dict) -> None:
    # Check headers/DOM dimensions before decoding or requesting an oversized
    # screenshot. A wide page is allowed only within the same forty-tile budget.
    if geometry['height'] > MAX_HEIGHT:
        _image_budget_error(info, geometry, 'height')
    if geometry['width'] > TILE_SIZE * MAX_TILES:
        _image_budget_error(info, geometry, 'width')
    if geometry['required_tiles'] > MAX_TILES:
        _image_budget_error(info, geometry, 'tile_count')


def _record_page_geometry(info: dict, size: dict) -> None:
    info['viewport'] = {'width': size['w'], 'height': size['h']}
    info['document'] = {'width': size['width'], 'height': size['total']}


async def scroll_full_page(page, info: dict) -> None:
    """Visit the complete allowed vertical extent, including the final position."""
    info['stage'] = 'scroll'
    await page.evaluate('window.scrollTo({left:0,top:0,behavior:"instant"})')
    for steps in range(MAX_SCROLL_STEPS + 1):
        size = await page.evaluate(PAGE_GEOMETRY_JS)
        _record_page_geometry(info, size)
        bottom = size['y'] + size['h'] >= size['total'] - 2
        info['scroll'] = {'steps': steps, 'x': size['x'], 'y': size['y'], 'bottom_reached': bottom}
        if size['total'] > MAX_HEIGHT:
            _image_budget_error(info, _image_geometry(size['width'], size['total']), 'height')
        if bottom:
            return
        if steps == MAX_SCROLL_STEPS:
            info['budget_failure'] = {'code': 'scroll_budget_no_truncation', 'stage': 'scroll',
                                      'reason': 'scroll_steps', 'max_steps': MAX_SCROLL_STEPS}
            raise ValueError(f"scroll_budget_no_truncation: steps={steps} y={size['y']} "
                             f"viewport_height={size['h']} document_height={size['total']}")
        # Native instant scrolling also works on pages with scroll-behavior:smooth;
        # it does not change CSS, hide content or skip any screenshot pixels.
        await page.evaluate(f'window.scrollBy({{left:0,top:{SCROLL_STEP},behavior:"instant"}})')
        await page.wait_for_timeout(100)


def tile_png(raw: bytes, *, diagnostics: dict | None = None) -> list[bytes]:
    """Lossless row-major tiles; every source pixel survives, with at most 40 PNGs."""
    info = diagnostics if diagnostics is not None else {}
    info['stage'] = 'screenshot'
    with Image.open(io.BytesIO(raw)) as image:
        geometry = _image_geometry(image.width, image.height)
        info['screenshot'] = {**geometry, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        _check_image_budget(info, geometry)
        image.load()
        result, layout = [], []
        for top in range(0, image.height, TILE_SIZE):
            for left in range(0, image.width, TILE_SIZE):
                right, bottom = min(left + TILE_SIZE, image.width), min(top + TILE_SIZE, image.height)
                buffer = io.BytesIO()
                with image.crop((left, top, right, bottom)) as part:
                    part.save(buffer, format='PNG')
                result.append(buffer.getvalue())
                layout.append({'x': left, 'y': top, 'width': right - left, 'height': bottom - top})
        info['image_layout'] = {'order': 'row_major_left_to_right_then_top_to_bottom',
                                'width': image.width, 'height': image.height, 'tiles': layout}
        return result


async def screenshot_tiles(page, info: dict, *, full_png: Path | None = None) -> list[bytes]:
    info['stage'] = 'screenshot_preflight'
    size = await page.evaluate(PAGE_GEOMETRY_JS)
    _record_page_geometry(info, size)
    expected = _image_geometry(max(size['w'], size['width']), max(size['h'], size['total']))
    info['expected_screenshot'] = expected
    _check_image_budget(info, expected)
    info['stage'] = 'screenshot'
    raw = await page.screenshot(full_page=True, animations='disabled', timeout=30000)
    # The actual PNG is checked again: DOM dimensions may change after preflight.
    images = tile_png(raw, diagnostics=info)
    if full_png is not None:
        full_png.write_bytes(raw)
        info['files'][full_png.name] = {'bytes': len(raw), 'sha256': info['screenshot']['sha256'],
                                       'stage': 'screenshot'}
    return images


def store(out: Path, case: str, target: dict, text: str, images: list[bytes], *, source_url=None,
          image_layout=None) -> dict:
    folder = out / case
    folder.mkdir(exist_ok=True)
    (folder / 'visible-text.txt').write_text(text, encoding='utf-8')
    names = []
    for n, raw in enumerate(images, 1):
        name = f'{case}/page-{n}.png'
        (out / name).write_bytes(raw)
        names.append(name)
    text_name = f'{case}/visible-text.txt'
    spec = {'id': case, 'target': target, 'text': text_name, 'images': names,
            'source_url': source_url,
            'sha256': {n: hashlib.sha256((out/n).read_bytes()).hexdigest() for n in [text_name, *names]}}
    if image_layout is not None:
        if len(image_layout['tiles']) != len(names):
            raise ValueError('capture_image_layout_count')
        spec['image_layout'] = {**image_layout,
                                'tiles': [{'image': name, **rect} for name, rect in zip(names, image_layout['tiles'])]}
    return spec


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
                with capture_diagnostics(folder, url) as diagnostic:
                    async with PublicSource(browser, url) as source:
                        await source.page.set_viewport_size({'width':1024,'height':1024})
                        status, html = await source.navigate(url)
                        diagnostic.update(http_status=status, final_url=source.page.url)
                        record_capture_text(folder, 'source.html', html, diagnostic)
                        with source.observe_navigation(include_current=True) as latest:
                            check_response(status, html)
                            # Ordinary scrolling only; never click or bypass a gate.
                            await scroll_full_page(source.page, diagnostic)
                            await source.page.evaluate('window.scrollTo({left:0,top:0,behavior:"instant"})')
                            await source.page.wait_for_timeout(700)
                            diagnostic['stage'] = 'transport_readiness'
                            finish = getattr(source, 'finish_capture', None)
                            before = await finish() if finish else None
                            generation = before['resource_generation'] if before else None
                            if before:
                                diagnostic['transport_generation_before'] = generation
                            diagnostic['stage'] = 'final_document'
                            status, html = await source.document_content(latest)
                            diagnostic.update(http_status=status, final_url=source.page.url)
                            check_response(status, html)
                            current_response, current_url = latest[-1], source.page.url
                            record_capture_text(folder, 'source.html', html, diagnostic)
                            diagnostic['stage'] = 'text'
                            text = await source.page.locator('body').inner_text(timeout=15000)
                            if not text.strip(): raise ValueError('empty_page')
                            record_capture_text(folder, 'visible-text.txt', text, diagnostic)
                            images = await screenshot_tiles(source.page, diagnostic, full_png=folder/'full.png')
                            diagnostic['stage'] = 'transport_validation'
                            transport = await finish() if finish else None
                            if transport:
                                diagnostic['transport'] = transport
                            if before and (not transport or transport['resource_generation'] != generation):
                                raise ValueError('capture_resources_changed')
                            if latest[-1] is not current_response or source.page.url != current_url:
                                raise ValueError('page_navigation_unstable')
                        diagnostic['stage'] = 'store'
                        target = {'partner':partner,'program':program,'as_of':datetime.now(timezone.utc).date().isoformat()}
                        spec = store(out, case, target, text, images, source_url=url,
                                     image_layout=diagnostic.get('image_layout'))
                documents.append(spec)
                row.update(status='prepared', images=len(images), text_chars=len(text),
                           http_status=status, final_url=diagnostic['final_url'])
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
