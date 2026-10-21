"""Current merchant-owned EKP cards; neighboring promotions are never evidence."""
from __future__ import annotations
import hashlib
import re
from urllib.parse import urljoin
from bs4 import Tag
from normalized import make_offer, text
from model import clean_url
from content_discovery import clean_dom, literal_benefits, action_clauses

PROGRAM = re.compile(r"\bЕКП\b|Един\w*\s+карт\w*\s+петербуржца", re.I)
# An identity alias for the previously published card, not a discovery allowlist.
LEGACY_PRODUCT_IDS = {'1775716014651': 'ekp'}
GIFT = re.compile(
    r"При бронировании от (?P<days>\d+)(?:-?[хx])? суток любого из домов "
    r"(?P<hours>\d+) час(?:а|ов)? проката "
    r"(?P<bikes>\d+)(?:-?[хx])? велосипедов или "
    r"(?P<sups>\d+)(?:-?[хx])? сапбордов на выбор в ПОДАРОК\s*!", re.I)


def compact(node):
    return text(node.get_text(' ', strip=True))


def extract_stay(source, soup, url, observed_at, cfg):
    if source != 'ekp_ladoga_public' or url != cfg['url'] or url != 'https://ladogabaza.ru/':
        raise ValueError('ekp_ladoga_exact_source_url')
    dom = clean_dom(str(soup))
    cards = []
    for card in dom.select('.js-product[data-product-lid]'):
        titles = card.select('.js-product-name')
        if any(PROGRAM.search(compact(n)) for n in titles):
            if len(titles) != 1:
                raise ValueError('ekp_ladoga_ambiguous_card_title')
            cards.append(card)
    if not cards or len(cards) > 2500:
        raise ValueError('ekp_ladoga_card_inventory_bound')
    rows, seen = [], set()
    for card in cards:
        product_id = card['data-product-lid']
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', product_id) or product_id in seen:
            raise ValueError('ekp_ladoga_duplicate_or_invalid_card_id')
        seen.add(product_id)
        descriptions = card.select('.t778__descr')
        if len(descriptions) != 1:
            raise ValueError('ekp_ladoga_description_boundary')
        description = compact(descriptions[0])
        if not description:
            raise ValueError('ekp_ladoga_empty_description')
        claims, _ = literal_benefits(description)
        matches = list(GIFT.finditer(description))
        # Optional structured detail for a recognized clause. A new gift item or
        # wording is retained literally, never filled with historical quantities.
        match = matches[0] if len(matches) == 1 else None
        if match and any(int(match[k]) <= 0 for k in ('days', 'hours', 'bikes', 'sups')):
            raise ValueError('ekp_ladoga_invalid_gift_quantity')
        title = compact(card.select_one('.js-product-name'))
        links, unsafe_links = set(), 0
        for anchor in card.select('a[href]'):
            try:
                links.add(clean_url(urljoin(url, anchor['href'])))
            except (ValueError, TypeError):
                unsafe_links += 1
        notes = []
        record = card.find_parent(id=lambda value: value and re.fullmatch(r'rec\d+', value))
        if record:
            for sibling in record.next_siblings:
                if not isinstance(sibling, Tag):
                    continue
                note = compact(sibling)
                if not note.startswith('*ВНИМАНИЕ!'):
                    break
                if note not in notes:
                    notes.append(note)
                if len(notes) > 200:
                    raise ValueError('ekp_ladoga_notes_resource_bound')
        details = {
            'source_scope': 'current_merchant_owned_EKP_card',
            'partner_identity_origin': 'reviewed_exact_partner_owned_url',
            'authenticated_catalogue_equivalence': False,
            'source_account_used': False, 'coupon_issued': False,
            'user_eligibility_verified': False,
            'published_links': sorted(links), 'linked_page_read': False,
            'source_product_id': product_id,
            'minimum_stay': {'value': int(match['days']), 'unit': 'days', 'evidence': match[0]} if match else None,
            'gift': {'duration_hours': int(match['hours']), 'choice': 'one_of',
                     'options': [{'item': 'bicycle', 'quantity': int(match['bikes'])},
                                 {'item': 'SUP_board', 'quantity': int(match['sups'])}],
                     'evidence': match[0]} if match else None,
            'general_page_notes': notes,
            'general_page_notes_apply_to_EKP': 'not_established',
            'page_sha256': hashlib.sha256(str(soup).encode()).hexdigest(),
            'hash_basis': 'BeautifulSoup_HTML_serialization',
        }
        warnings = ['independent_public_partner_page_not_authenticated_EKP_card',
                    'user_eligibility_not_verified', 'published_end_date_not_stated',
                    'regional_card_equivalence_not_verified']
        if notes:
            warnings.append('general_promotions_note_scope_not_established_for_EKP')
        if unsafe_links:
            warnings.append('unsafe_source_links_omitted')
        if not claims:
            warnings.append('unclassified_block_retained_as_evidence')
        rows.append(make_offer(source, LEGACY_PRODUCT_IDS.get(product_id, 'ekp:' + product_id),
            cfg['program'], cfg['partner'], '\n'.join(claims), url, observed_at,
            title=cfg['partner'] + ' — ' + title, category=cfg['category'],
            conditions=title + '\n' + description,
            redemption=action_clauses(description) or (match[0] if match else ''),
            record_kind='partner_offer' if claims else 'source_observation', link_kind='page_block',
            locator='.js-product[data-product-lid="' + product_id + '"] .t778__descr',
            details=details, warnings=warnings))
    return rows
