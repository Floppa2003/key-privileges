"""Native screenshots of source-owned HSE sections; no rewritten source DOM."""
from __future__ import annotations

import hashlib
import io
import math
import re

from PIL import Image

SCOPE = 'hse_partner_sections'
OCCLUSION_CHECK = 'outside_positioned_overlap_v1'


def flat_text(value):
    # Browser line wrapping and HTML node boundaries are not source changes.
    return re.sub(r'\s+', ' ', value).strip()


def joined_text(regions):
    return '\n\n'.join(f"[Фрагмент {index}; {region['role']}]\n{region['text']}"
                       for index, region in enumerate(regions, 1))


async def dismiss_overlays(page, diagnostic):
    """Use the page's native dismissal controls; never remove or restyle its DOM."""
    closed = await page.evaluate('''() => {
        const ids = new Set();
        for (const frame of document.querySelectorAll('.tally-popup iframe[src]')) {
            const url = new URL(frame.src);
            const match = url.pathname.match(/^\\/popup\\/([A-Za-z0-9]+)\\/?$/);
            if (url.origin === 'https://tally.so' && match) ids.add(match[1]);
        }
        if (ids.size && typeof window.Tally?.closePopup !== 'function')
            throw new Error('hse_popup_native_close_missing');
        for (const id of ids) window.Tally.closePopup(id);
        return Array.from(ids);
    }''')
    if closed:
        await page.wait_for_function('''() =>
            Array.from(document.querySelectorAll('.tally-popup iframe')).every(node => {
                const box = node.getBoundingClientRect();
                return !box.width || !box.height || getComputedStyle(node).visibility === 'hidden';
            })''', timeout=5000)
        diagnostic.setdefault('native_dismissals', []).extend(
            {'control': 'Tally.closePopup', 'form_id': ident} for ident in closed)
    banner = page.locator('.gdpr_bar')
    if await banner.count():
        if await banner.count() != 1:
            raise ValueError('hse_cookie_close_ambiguous')
        if await banner.is_visible():
            close = banner.locator('.gdpr_bar__close')
            if await close.count() != 1:
                raise ValueError('hse_cookie_native_close_missing')
            await close.click(timeout=5000)
            await banner.wait_for(state='hidden', timeout=5000)
            diagnostic.setdefault('native_dismissals', []).append({'control': 'gdpr_bar__close'})


async def check_occlusion(locator, diagnostic, phase):
    # A clip can have valid dimensions and complete innerText while a floating
    # sibling covers its pixels. Check positioned outsiders before and after it.
    blockers = await locator.evaluate('''root => {
        const box = root.getBoundingClientRect();
        const hseOccluders = [];
        for (const node of document.body.querySelectorAll('*')) {
            if (root.contains(node) || node.contains(root)) continue;
            const style = getComputedStyle(node);
            if (!['fixed', 'sticky', 'absolute'].includes(style.position)
                    || style.visibility === 'hidden' || style.display === 'none'
                    || Number(style.opacity) === 0) continue;
            const r = node.getBoundingClientRect();
            if (r.width > 1 && r.height > 1 && r.right > box.left + 1
                    && r.left < box.right - 1 && r.bottom > box.top + 1
                    && r.top < box.bottom - 1) {
                hseOccluders.push({tag: node.tagName, id: node.id,
                    class: String(node.className).slice(0, 160), position: style.position});
            }
        }
        return hseOccluders;
    }''')
    if blockers:
        diagnostic['occlusion'] = {'phase': phase, 'elements': blockers}
        raise ValueError('hse_scope_region_occluded')


async def prepare_regions(page, plan):
    """Reveal each selected region and its lazy images before freezing the DOM."""
    for region in plan['regions']:
        locator = page.locator(region['locator'])
        if await locator.count() != 1 or not await locator.is_visible():
            raise ValueError('hse_scope_region_missing_or_hidden')
        await locator.scroll_into_view_if_needed(timeout=15000)
        await page.wait_for_function('''selector => {
            const root = document.querySelector(selector);
            return root && Array.from(root.querySelectorAll('img')).every(img =>
                img.complete && img.naturalWidth > 0);
        }''', arg=region['locator'], timeout=15000)


async def capture_regions(page, plan, diagnostic):
    from diagnostics.deepseek_acceptance import tile_png, _image_geometry, _check_image_budget, MAX_TILES
    from hse_capture_plan import fragment_evidence

    images, regions = [], []
    for expected in plan['regions']:
        await dismiss_overlays(page, diagnostic)
        locator = page.locator(expected['locator'])
        if await locator.count() != 1 or not await locator.is_visible():
            raise ValueError('hse_scope_region_missing_or_hidden')
        await locator.scroll_into_view_if_needed(timeout=15000)
        before = fragment_evidence(await locator.evaluate('(node) => node.outerHTML'))
        if before != {key: expected[key] for key in ('html_sha256', 'source_text')}:
            raise ValueError('hse_scope_region_changed')
        size = await locator.evaluate('''node => {
            const box = node.getBoundingClientRect();
            return {width: box.width, height: box.height,
                    scrollWidth: node.scrollWidth, scrollHeight: node.scrollHeight};
        }''')
        if (size['width'] <= 0 or size['height'] <= 0
                or size['scrollWidth'] > size['width'] + 2
                or size['scrollHeight'] > size['height'] + 2):
            raise ValueError('hse_scope_region_clipped')
        geometry = _image_geometry(math.ceil(size['width']), math.ceil(size['height']))
        diagnostic['stage'] = 'hse_region_preflight'
        _check_image_budget(diagnostic, geometry)
        if len(images) + geometry['required_tiles'] > MAX_TILES:
            raise ValueError('hse_scope_image_budget_no_truncation')
        text = await locator.inner_text(timeout=15000)
        if ((not text.strip() and expected.get('visual_only') is not True)
                or flat_text(text) != flat_text(expected['source_text'])):
            raise ValueError('hse_scope_visible_text_mismatch')
        diagnostic['stage'] = 'hse_region_screenshot'
        await check_occlusion(locator, diagnostic, 'before_screenshot')
        raw = await locator.screenshot(animations='disabled', timeout=30000)
        await check_occlusion(locator, diagnostic, 'after_screenshot')
        tile_info = {}
        parts = tile_png(raw, diagnostics=tile_info)
        if len(images) + len(parts) > MAX_TILES:
            raise ValueError('hse_scope_image_budget_no_truncation')
        after = fragment_evidence(await locator.evaluate('(node) => node.outerHTML'))
        if after != before:
            raise ValueError('hse_scope_region_changed')
        regions.append({'role': expected['role'], 'locator': expected['locator'], 'text': text,
                        'occlusion_check': OCCLUSION_CHECK,
                        'image_start': len(images), 'image_count': len(parts),
                        'layout': tile_info['image_layout']})
        images.extend(parts)
        diagnostic['scoped_regions'] = regions
    return joined_text(regions), images, regions


def validate_capture(spec, read, text, images):
    """Rebuild ownership from the hashed original DOM before manifest admission."""
    from hse_capture_plan import selection
    # Scope v1 describes 1024px row-major source tiles, as written by tile_png.
    tile_size = 1024

    capture = spec.get('capture', {})
    if capture.get('scope') != SCOPE or not isinstance(spec.get('source_html'), str):
        raise ValueError('hse_scope_source_missing')
    raw = read(spec['source_html']).decode('utf-8')
    target = {**spec['target'], 'url': spec.get('source_url'),
              'source_records': spec.get('source_records', [])}
    plan = selection(raw, target)
    if (capture.get('selection') != plan or capture.get('target_found') is not True
            or capture.get('content_ready') is not True):
        raise ValueError('hse_scope_selection_mismatch')
    regions = capture.get('regions')
    if not isinstance(regions, list) or len(regions) != len(plan['regions']):
        raise ValueError('hse_scope_regions_mismatch')
    cursor = 0
    for region, expected in zip(regions, plan['regions']):
        if region.get('occlusion_check') != OCCLUSION_CHECK:
            raise ValueError('hse_scope_occlusion_check_missing')
        if (region.get('role') != expected['role'] or region.get('locator') != expected['locator']
                or not isinstance(region.get('text'), str)
                or (not region['text'].strip() and expected.get('visual_only') is not True)
                or flat_text(region['text']) != flat_text(expected['source_text'])):
            raise ValueError('hse_scope_text_mismatch')
        layout = region.get('layout', {})
        width, height = layout.get('width'), layout.get('height')
        if type(width) is not int or type(height) is not int or not 1 <= width <= 40960 or not 1 <= height <= 40960:
            raise ValueError('hse_scope_image_geometry')
        tiles = [{'x': left, 'y': top, 'width': min(tile_size, width-left),
                  'height': min(tile_size, height-top)}
                 for top in range(0, height, tile_size) for left in range(0, width, tile_size)]
        if (layout.get('tiles') != tiles
                or layout.get('order') != 'row_major_left_to_right_then_top_to_bottom'
                or region.get('image_start') != cursor or region.get('image_count') != len(tiles)
                or cursor + len(tiles) > len(images)):
            raise ValueError('hse_scope_image_geometry')
        for tile, image in zip(tiles, images[cursor:cursor+len(tiles)]):
            with Image.open(io.BytesIO(image)) as loaded:
                if loaded.size != (tile['width'], tile['height']):
                    raise ValueError('hse_scope_image_geometry')
        cursor += len(tiles)
    if cursor != len(images) or text != joined_text(regions):
        raise ValueError('hse_scope_text_or_images_mismatch')


def attach_source_html(spec, folder, ident):
    name = ident + '/source.html'
    spec['source_html'] = name
    spec['sha256'][name] = hashlib.sha256((folder / 'source.html').read_bytes()).hexdigest()
    return spec
