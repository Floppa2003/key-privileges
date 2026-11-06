"""Nordwind's current partner accordions; no fixed partner inventory or rates."""
from __future__ import annotations
import hashlib
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from html_text import html_text
from normalized import make_offer, text, number
from model import clean_url

ROOT = 'https://nordwindairlines.ru/ru/club/partnerlist'
PROGRAM = 'NORDWIND CLUB'
NUM = r'\d+(?:[ \u00a0]\d{3})*(?:[.,]\d+)?'
EARNING = re.compile(r'За\s+каждые\s+(?:потраченные\s+)?(?P<basis>'+NUM+r')\s*(?:₽|руб(?:лей|ля|ль)?\.?)\s*[-–—=]\s*(?P<value>'+NUM+r')\s*мил(?:я|и|ь)\b', re.I)
WARNINGS = ['user_eligibility_and_stacking_not_verified', 'linked_partner_sites_not_fetched',
            'scope_is_observed_partnerlist_not_entire_loyalty_program']


def earning_rules(clause):
    matches = list(EARNING.finditer(clause))
    if len(matches) != 1:
        return []
    found = matches[0]
    return [{'value': number(found['value']), 'unit': 'miles', 'qualifier': 'exact',
             'basis_amount': number(found['basis']), 'basis_unit': 'RUB', 'evidence': clause}]


def heading_matches(body, label, *, inline=False):
    words = re.sub(r'\s+', ' ', label).strip().rstrip(':').split()
    pattern = r'\s+'.join(re.escape(word) for word in words)
    if inline:
        pattern = r'(?<!\w)' + pattern + r'(?!\w)(?:[^\S\n]*:)?'
    else:
        pattern = r'^[^\S\n]*' + pattern + r'[^\S\n]*:?[^\S\n]*$'
    return list(re.finditer(pattern, body, re.I | re.M))


def earning_section(content, body):
    label = 'Мили к начислению'
    headings = content.find_all(['b', 'strong', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
    owned = [node for node in headings if re.sub(r'\s+', ' ', html_text(node)).rstrip(':').strip().casefold() == label.casefold()]
    owned_ids = {id(node) for node in owned}
    owned = [node for node in owned if not any(id(parent) in owned_ids for parent in node.parents)]
    matches = heading_matches(body, label)
    if not matches and len(owned) == 1:
        matches = heading_matches(body, label, inline=True)
    if len(matches) != 1 or len(owned) > 1:
        raise ValueError('nordwind_earning_section_missing_or_ambiguous')
    start = matches[0].end(); end = len(body)
    for node in headings:
        title = html_text(node)
        if not title or (node.name in ('b', 'strong') and not title.endswith(':')):
            continue
        if re.sub(r'\s+', ' ', title).rstrip(':').strip().casefold() == label.casefold():
            continue
        following = heading_matches(body, title) or heading_matches(body, title, inline=True)
        for found in following:
            if found.start() >= start:
                end = min(end, found.start())
    benefit = body[start:end].strip()
    if not re.search(r'мил(?:я|и|ь)\b', benefit, re.I):
        raise ValueError('nordwind_earning_clause_missing')
    return benefit


def article_blocks(raw):
    soup = BeautifulSoup(raw, 'html.parser')
    mains = soup.select('#main_content')
    headings = soup.select('.page-promo__title')
    if len(mains) != 1 or not any(re.search(r'Партнеры программы лояльности\s+NORDWIND', html_text(h), re.I) for h in headings):
        raise ValueError('nordwind_catalog_not_ready')
    main = mains[0]
    items = main.select('.collapse-snippet__item')
    if not 1 <= len(items) <= 200:
        raise ValueError('nordwind_catalog_size_or_empty')
    blocks = []; seen = set()
    for item in items:
        if item.find_parent(class_='collapse-snippet__item') is not None:
            raise ValueError('nordwind_nested_card')
        labels = item.find_all(class_='collapse-snippet__title', recursive=False)
        contents = item.find_all(class_='collapse-snippet__content', recursive=False)
        if len(labels) != 1 or len(contents) != 1:
            raise ValueError('nordwind_card_structure')
        label = labels[0]; anchor = label.get('id', '')
        title = html_text(label)
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', anchor) or anchor in seen or not title:
            raise ValueError('nordwind_card_identity')
        seen.add(anchor)
        section = item.find_parent('section')
        category = section.find_previous_sibling() if section else None
        if category is None or category.name != 'h2' or 'routes__title' not in category.get('class', []):
            raise ValueError('nordwind_card_category')
        content = BeautifulSoup(str(contents[0]), 'html.parser')
        for node in content.select('script,style,form,input,textarea,iframe'):
            node.decompose()
        body = html_text(content)
        # Keep the original earning span, including wrapped formulas, bounded by
        # the next explicit heading in this card rather than a global line order.
        benefit = earning_section(content, body)
        links = []
        for a in content.select('a[href]'):
            try:
                url = clean_url(urljoin(ROOT, a['href']))
            except (TypeError, ValueError):
                continue
            entry = {'label': html_text(a), 'url': url}
            if entry not in links:
                links.append(entry)
        blocks.append({'anchor': anchor, 'title': title, 'category': html_text(category),
                       'text': body, 'benefit': benefit, 'links': links})
    return blocks


def parse_catalog(raw, observed_at):
    blocks = article_blocks(raw)
    sha = hashlib.sha256(raw.encode()).hexdigest()
    rows = []
    for block in blocks:
        rules = earning_rules(block['benefit'])
        warnings = list(WARNINGS)
        if not rules:
            warnings.append('earning_formula_not_structurally_parsed')
        rows.append(make_offer('nordwind', 'anchor:'+block['anchor'], PROGRAM, block['title'],
            block['benefit'], ROOT+'#'+block['anchor'], observed_at, title=block['title'],
            conditions=block['text'], category=block['category'], link_kind='page_anchor',
            locator='id='+block['anchor'], source_status='public_partner_catalog',
            details={'public_catalog_block': block, 'source_document_sha256': sha,
                     'retrieval_method': 'scrapingant_free_RU_sanitized_live_DOM',
                     'earning_rules': rules, 'linked_terms_checked': False,
                     'full_program_catalog': False, 'scope': 'all_accordions_in_observed_partnerlist'},
            warnings=warnings))
    return rows


def validate_catalog_record(row):
    d = row.get('details', {}); b = d.get('public_catalog_block', {})
    anchor = b.get('anchor', '')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', anchor):
        raise ValueError('nordwind_card_identity')
    if (row['source_url'] != ROOT+'#'+anchor or row['benefit_url'] != row['source_url']
        or row['native_id'] != 'anchor:'+anchor or row['link_kind'] != 'page_anchor'
        or row['record_kind'] != 'partner_offer' or row['program'] != PROGRAM
        or row['partner_name'] != b.get('title') or row['title'] != b.get('title')
        or row['category'] != b.get('category') or row['benefit_text'] != b.get('benefit')
        or row['conditions_text'] != text(b.get('text'), markup=False) or b.get('benefit', '') not in b.get('text', '')
        or d.get('earning_rules') != earning_rules(b.get('benefit', ''))
        or d.get('linked_terms_checked') is not False or d.get('full_program_catalog') is not False
        or row['source_status'] != 'public_partner_catalog'
        or not re.fullmatch('[a-f0-9]{64}', d.get('source_document_sha256', ''))
        or not set(WARNINGS).issubset(row['warnings'])):
        raise ValueError('nordwind_evidence_or_scope_mismatch')
    for link in b.get('links', []):
        clean_url(link['url'])
