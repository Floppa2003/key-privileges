"""Public iLocked EKP quest clauses and the separate short certificate restriction.

Only the quest's introductory section may supply a benefit. Birthday packages,
reviews and recommendations must not contribute rates or coupons. The existing
collector remains responsible for network policy, receipts and source freshness.
"""
from __future__ import annotations
import re
from urllib.parse import urlsplit
from bs4 import BeautifulSoup, NavigableString, Tag, Comment
from html_text import html_text
from normalized import make_offer, normalize_rates
from promo_codes import extract_promocodes

PROGRAM = re.compile(r'Единая\s+Карта\s+Петербуржца', re.I)
CARD = re.compile(r'Перед\s+игрой\s+необходимо\s+предъявить\s+саму\s+карту\s*[!.]', re.I)


def extract_ilocked_ekp(source, soup, url, observed_at, cfg):
    if cfg.get('parser') == 'ilocked_certificate':
        return extract_certificate_restriction(source, soup, url, observed_at, cfg)
    u = urlsplit(url)
    if (url != cfg['url'] or u.scheme != 'https' or u.netloc != 'ilocked.ru'
            or u.query or u.fragment or not re.fullmatch(r'/quest/[a-z0-9_-]+', u.path)):
        raise ValueError('ilocked_ekp_url')
    dom = BeautifulSoup(str(soup), 'html.parser')
    for node in dom.select('script,style,noscript,nav,header,footer,aside,form,input,[hidden],[aria-hidden="true"]'):
        node.decompose()
    headings = dom.find_all('h1')
    if len(headings) != 1:
        raise ValueError('ilocked_ekp_title')
    h1 = headings[0]
    title = html_text(h1)
    if not title:
        raise ValueError('ilocked_ekp_title')
    pieces = set()
    boundary = False
    for node in h1.next_elements:
        if isinstance(node, Tag) and node.name in ('h1', 'h2', 'h3'):
            boundary = True
            break
        if isinstance(node, NavigableString) and not isinstance(node, Comment) and h1 not in node.parents:
            pieces.add(id(node))
    # Missing heading means changed markup, not permission to read recommendations.
    if not boundary:
        raise ValueError('ilocked_ekp_section_boundary')
    # Keep exactly the same owned text-node range, retaining its inline and
    # block structure rather than inserting spaces between every text node.
    for node in list(dom.find_all(string=True)):
        if id(node) not in pieces:
            node.extract()
    intro = html_text(dom, br_separator=' ')
    matches = list(PROGRAM.finditer(intro))
    if len(matches) != 1:
        raise ValueError('ilocked_ekp_program_ambiguous')
    end = CARD.search(intro, matches[0].end())
    if end is None:
        raise ValueError('ilocked_ekp_card_requirement')
    starts = list(re.finditer(r'Для\s+владельцев', intro[:matches[0].start()]))
    if not starts:
        raise ValueError('ilocked_ekp_claim_start')
    start = starts[-1].start()
    claim = intro[start:end.end()]
    if len(claim) > 2000:
        raise ValueError('ilocked_ekp_claim_bound')
    # Read rate and literal code from this clause, never today's observed values.
    rates = normalize_rates(claim)
    promo = extract_promocodes(claim)
    if (len(re.findall(r'\d+(?:[.,]\d+)?\s*%', claim)) != 1 or len(rates) != 1
            or rates[0].get('kind') != 'discount' or len(promo['codes']) != 1):
        raise ValueError('ilocked_ekp_benefit_or_code_ambiguous')
    important = re.search(r'\bВАЖНО\s*:\s*(.+)$', intro[end.end():], re.I | re.S)
    conditions = claim + ('\n' + important[0] if important else '')
    details = {
        'source_scope': 'exact_quest_public_ekp_clause',
        'partner_identity_origin': 'reviewed_exact_partner_owned_url',
        'quest_title': title,
        'applies_to_entire_catalogue': False,
        'source_account_used': False,
        'user_eligibility_verified': False,
        'supplements_gated_catalogue': True,
        'gated_catalogue_terms_recovered': False,
        'linked_documents': [{'url': 'https://ilocked.ru/certificate',
                              'label': 'Separate gift-certificate restriction',
                              'source_id': 'ilocked_certificate_terms', 'same_observation': False}],
    }
    return [make_offer(source, 'ekp', cfg['program'], cfg['partner'], claim,
        url, observed_at, title=title, category=cfg['category'], conditions=conditions,
        redemption=claim, locator='unique h1 intro before next h2/h3; own EKP clause',
        details=details, warnings=['publication_is_not_confirmation_of_current_user_eligibility',
        'exact_quest_only_not_all_packages_or_extras',
        'consult_ilocked_certificate_terms_before_redemption',
        'published_end_date_not_extracted'])]


def extract_certificate_restriction(source, soup, url, observed_at, cfg):
    """A short displayed restriction, never the complete gift-card contract."""
    if url != cfg['url'] or url != 'https://ilocked.ru/certificate':
        raise ValueError('ilocked_certificate_url')
    dom = BeautifulSoup(str(soup), 'html.parser')
    for node in dom.select('script,style,noscript,form,input,[hidden],[aria-hidden="true"]'):
        node.decompose()
    titles = dom.find_all('h1')
    if len(titles) != 1 or not re.search(r'сертификат', html_text(titles[0]), re.I):
        raise ValueError('ilocked_certificate_title')
    candidates = []
    for node in dom.select('.t165__textwrapper .t165__btn-container p'):
        value = html_text(node)
        if re.search(r'подарочн\w*\s+сертификат', value, re.I) and re.search(r'скидк', value, re.I):
            candidates.append(value)
    if (len(candidates) != 1 or len(candidates[0]) > 500
            or not re.search(r'скидки\s+не\s+распространяются', candidates[0], re.I)):
        raise ValueError('ilocked_certificate_restriction_changed')
    return [make_offer(source, 'discount-restriction', cfg['program'], cfg['partner'], '',
        url, observed_at, title=html_text(titles[0]),
        category=cfg['category'], record_kind='program_rules', link_kind='page_block',
        conditions=candidates[0], locator='.t165__textwrapper .t165__btn-container p; gift-certificate restriction',
        details={'evidence_role': 'supplementary_rules_not_incremental_discount',
                 'source_scope': 'short_public_certificate_discount_restriction',
                 'source_account_used': False, 'full_contract_collected': False},
        warnings=['restriction_not_additional_discount', 'published_end_date_not_extracted'])]
