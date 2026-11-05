"""Pure ownership plan for native HSE screenshots, not a rewritten source page."""
from __future__ import annotations

import hashlib
import re
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, NavigableString, Tag

from hse_alumni import ROOT, _clean_dom, _has_visual, _owned_blocks


_TEXT_BREAKS = frozenset(('address','article','aside','blockquote','div','dl','dt','dd',
                        'fieldset','figcaption','figure','footer','h1','h2','h3','h4','h5','h6',
                        'header','hr','li','main','nav','ol','p','pre','section','table','td','th',
                        'tr','ul'))


def _plain(node):
    # Inline markup may split a literal code or word without inserting a space.
    # Block boundaries and explicit line breaks are the only added separators.
    pieces = []
    def visit(item):
        if isinstance(item, NavigableString):
            pieces.append(str(item))
        elif isinstance(item, Tag):
            boundary = item.name in _TEXT_BREAKS
            if boundary or item.name == 'br':
                pieces.append(' ')
            for child in item.children:
                visit(child)
            if boundary:
                pieces.append(' ')
    visit(node)
    return re.sub(r'\s+', ' ', ''.join(pieces)).strip()


def fragment_evidence(raw_html: str) -> dict:
    """Hash original canonical HTML; compare only source-visible text separately."""
    dom = BeautifulSoup(raw_html, 'html.parser')
    nodes = dom.find_all(recursive=False)
    if len(nodes) != 1:
        raise ValueError('hse_capture_fragment_shape')
    digest = hashlib.sha256(str(nodes[0]).encode('utf-8')).hexdigest()
    _clean_dom(dom)
    return {'html_sha256': digest, 'source_text': _plain(dom)}


def _locator(node):
    """Absolute path counted before removing ignored siblings or descendants."""
    parts = []
    while isinstance(node, Tag) and node.name != '[document]':
        siblings = node.parent.find_all(node.name, recursive=False)
        index = next(i for i, sibling in enumerate(siblings, 1) if sibling is node)
        parts.append(f'{node.name}:nth-of-type({index})')
        node = node.parent
    return ' > '.join(reversed(parts))


def _requested(entries, target, fragment):
    name = target.get('partner')
    if not isinstance(name, str) or not name.strip():
        raise ValueError('hse_capture_identity')
    name = name.strip()
    records = target.get('source_records', [])
    if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
        raise ValueError('hse_capture_identity')
    ids = set()
    for row in records:
        if row.get('source_id') != 'hse_alumni':
            continue
        native = row.get('native_id', '')
        if (not isinstance(native, str) or not re.fullmatch(r'anchor:[A-Za-z0-9_-]{1,100}', native)
                or row.get('partner_name', name) != name
                or ('program' in row and 'program' in target and row['program'] != target['program'])):
            raise ValueError('hse_capture_identity')
        ids.add(native.split(':', 1)[1])
    if ids and fragment and fragment not in ids:
        raise ValueError('hse_capture_identity')
    if not ids and fragment:
        ids.add(fragment)
    if not ids:
        matches = [entry for entry in entries if entry[0]['name'] == name]
        if len(matches) > 1:
            raise ValueError('hse_capture_ambiguous_target')
        if not matches:
            raise ValueError('hse_capture_identity')
        ids.add(matches[0][0]['anchor'])
    selected = [entry for entry in entries if entry[0]['anchor'] in ids]
    if len(selected) != len(ids) or any(entry[0]['name'] != name for entry in selected):
        raise ValueError('hse_capture_identity')
    if any(entry[0]['detail_state'] != 'detail' for entry in selected):
        raise ValueError('hse_detail_missing')
    return selected


def selection(raw: str, target: dict) -> dict:
    """Bind current source-owned nodes; retained collector values may be older."""
    try:
        url = urlsplit(target['url'])
    except (KeyError, TypeError, ValueError):
        raise ValueError('hse_capture_url') from None
    root_url = urlsplit(ROOT)
    if ((url.scheme, url.netloc, url.path) != (root_url.scheme, root_url.netloc, root_url.path)
            or url.query or url.fragment and not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', url.fragment)):
        raise ValueError('hse_capture_url')
    dom = BeautifulSoup(raw, 'html.parser')
    order = {id(node): index for index, node in enumerate(dom.find_all(True))}
    # Snapshot paths and raw fragments first. Ownership sanitization must never
    # shift a locator from the original browser DOM to its cleaned sibling.
    originals = {}
    for root in dom.select('.post__text.builder_content'):
        nodes = root.find_all(recursive=False) + root.select('.fa-person__item,.builder-section__title')
        for node in nodes:
            originals[id(node)] = {'locator': _locator(node), **fragment_evidence(str(node))}
    root, entries, reserved = _owned_blocks(dom)
    selected = _requested(entries, target, url.fragment)
    owned = {id(node) for _, _, parts, _ in entries for node in parts}
    children = root.find_all(recursive=False)
    first_inventory = next(i for i, node in enumerate(children) if node.select('.fa-person__item'))
    regions = {}

    def add(node, role):
        original = originals[id(node)]
        if original['source_text'] or _has_visual(node):
            regions[id(node)] = {'role': role, **original}
            if not original['source_text']:
                regions[id(node)]['visual_only'] = True

    for index, node in enumerate(children):
        if (id(node) in owned or id(node) in reserved or node.select('.fa-person__item')
                or not (_plain(node) or _has_visual(node))):
            continue
        if index < first_inventory:
            add(node, 'context')
            continue
        headings = node.select('.nom h1')
        if headings and _plain(node) == ' '.join(_plain(heading) for heading in headings):
            continue  # Standalone category navigation, not missing terms.
        raise ValueError('hse_unowned_context')
    for _, card, parts, heading in selected:
        add(heading, 'context')
        add(card, 'card')
        for part in parts:
            add(part, 'detail')
    return {'version': 1, 'blocks': [entry[0] for entry in selected],
            'regions': [regions[key] for key in sorted(regions, key=order.__getitem__)]}
