"""One reviewed Ladoga EKP gift card; no whole-page rates or private catalogue."""
from __future__ import annotations
import hashlib
import re
from bs4 import BeautifulSoup, Comment, Tag
from normalized import make_offer, text

PROGRAM = re.compile(r"\bЕКП\b|Един\w*\s+карт\w*\s+петербуржца", re.I)
GIFT = re.compile(
    r"При бронировании от (?P<days>[1-9]\d*)(?:-?[хx])? суток любого из домов "
    r"(?P<hours>[1-9]\d*) час(?:а|ов)? проката "
    r"(?P<bikes>[1-9]\d*)(?:-?[хx])? велосипедов или "
    r"(?P<sups>[1-9]\d*)(?:-?[хx])? сапбордов на выбор в ПОДАРОК\s*!", re.I)


def compact(node):
    return text(node.get_text(" ", strip=True))


def extract_stay(source, soup, url, observed_at, cfg):
    if source != "ekp_ladoga_public" or url != cfg["url"] or url != "https://ladogabaza.ru/":
        raise ValueError("ekp_ladoga_exact_source_url")
    dom = BeautifulSoup(str(soup), "html.parser")
    for n in dom.select('script,style,noscript,form,input,textarea,nav,header,footer,[hidden],[aria-hidden="true"]'):
        if n.parent is not None:
            n.decompose()
    for n in dom.find_all(string=lambda value: isinstance(value, Comment)):
        n.extract()
    # Review the currently served product-card layout, not the older accordion.
    cards = []
    for card in dom.select('.js-product[data-product-lid]'):
        titles = card.select('.js-product-name')
        if any(PROGRAM.search(compact(n)) for n in titles):
            if len(titles) != 1:
                raise ValueError("ekp_ladoga_ambiguous_card_title")
            cards.append(card)
    if len(cards) != 1:
        raise ValueError("ekp_ladoga_missing_or_duplicate_card")
    card = cards[0]
    descriptions = card.select('.t778__descr')
    if len(descriptions) != 1:
        raise ValueError("ekp_ladoga_description_boundary")
    description = compact(descriptions[0])
    matches = list(GIFT.finditer(description))
    if len(matches) != 1 or matches[0].start() != 0:
        raise ValueError("ekp_ladoga_gift_terms_changed")
    match = matches[0]
    # Any new percentage belongs to a newly changed offer and needs a scope review.
    if '%' in description:
        raise ValueError("ekp_ladoga_unreviewed_percentage")
    title = compact(card.select_one('.js-product-name'))
    links = sorted({a['href'] for a in card.select('a[href]')})
    if links != ['https://ekp.spb.ru/capabilities?capability=offer']:
        raise ValueError("ekp_ladoga_eligibility_link_changed")
    # These two responsive notes follow the whole promotions record. The EKP
    # title has no asterisk: preserve the note separately, do not assert its scope.
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
            if len(notes) > 2:
                raise ValueError("ekp_ladoga_unreviewed_general_notes")
    details = {
        'source_scope': 'reviewed_merchant_owned_EKP_gift_card',
        'partner_identity_origin': 'reviewed_exact_partner_owned_url',
        'authenticated_catalogue_equivalence': False,
        'source_account_used': False, 'coupon_issued': False,
        'user_eligibility_verified': False,
        'published_links': links, 'linked_page_read': False,
        'minimum_stay': {'value': int(match['days']), 'unit': 'days', 'evidence': match[0]},
        'gift': {'duration_hours': int(match['hours']), 'choice': 'one_of',
                 'options': [{'item': 'bicycle', 'quantity': int(match['bikes'])},
                             {'item': 'SUP_board', 'quantity': int(match['sups'])}],
                 'evidence': match[0]},
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
    return [make_offer(source, 'ekp', cfg['program'], cfg['partner'], match[0],
        url, observed_at, title=cfg['partner'] + ' — подарок по ЕКП',
        category=cfg['category'], conditions=title + '\n' + description,
        redemption=match[0], link_kind='page_block',
        locator='.js-product[data-product-lid="' + card['data-product-lid'] + '"] .t778__descr',
        details=details, warnings=warnings)]
