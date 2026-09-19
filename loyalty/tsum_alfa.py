"""Two TSUM loyalty tiers from the merchant's public Alfa Only page.

The advertised percentages are shop loyalty credit, not cash or miles. The
merchant's expandable FAQ is a normal UI component; navigation and scripts are
not offer evidence. Bank fees and eligibility are not inferred from this page.
"""
from __future__ import annotations
import hashlib
import re
from bs4 import BeautifulSoup, Comment
from normalized import make_offer, number

SOURCE_ID = 'alfa_only_tsum'
URL = 'https://www.tsum.ru/lp/alfa-only/'
WARNINGS = ['user_eligibility_not_verified', 'authenticated_partner_catalog_not_read',
            'merchant_loyalty_credit_not_bank_cash_or_miles',
            'offer_dates_not_stated_in_reviewed_html', 'linked_regulations_not_read']
QUESTIONS = (
    'Как начисляется кешбэк в ЦУМе?',
    'Что я получаю в совместной программе лояльности Alfa Only и ЦУМа?',
    'Что будет с кешбэком при возврате покупок?',
    'За какие покупки начисляется кешбэк в ЦУМе?',
    'По каким правилам начисляется и списывается кешбэк?',
    'Какая максимальная сумма кешбэка в ЦУМе?',
    'Начисляется ли кешбэк при покупке с помощью СБП или QR-кода?',
    'Будет ли начисляться кешбэк в рублях или милях при участии в программе?',
    'Какие карты участвуют в совместной программе с ЦУМом?',
    'Я не показал QR-код/не указал номер карты лояльности ЦУМа при покупке, будет ли начислен кешбэк?',
    'Как повысить статус карты ЦУМа?',
    'Я оплатил покупку курьеру, почему нет кешбэка?',
)


def compact(value):
    return re.sub(r'\s+', ' ', value.replace('\x00', '')).strip()


def clean(node):
    soup = BeautifulSoup(str(node), 'html.parser')
    for n in soup.select('script,style,noscript,form,input,textarea,svg,[hidden],[aria-hidden="true"]'):
        if n.parent is not None:
            n.decompose()
    for n in soup.find_all(string=lambda s: isinstance(s, Comment)):
        n.extract()
    return compact(soup.get_text(' ', strip=True))


def one(soup, selector):
    nodes = soup.select(selector)
    if len(nodes) != 1:
        raise ValueError('alfa_tsum_missing_or_duplicate_section')
    return nodes[0]


def derived(e, tier):
    """Reconstruct row fields from source-owned card/FAQ evidence on readback."""
    if (e.get('url') != URL or e.get('reward_currency') != 'TSUM_DLT_loyalty_credit'
            or not re.fullmatch(r'[a-f0-9]{64}', e.get('page_sha256', ''))
            or set(e.get('cards', {})) != {'Black', 'Orange', 'White'}
            or tier not in ('Orange', 'Black')):
        raise ValueError('alfa_tsum_evidence_identity')
    faq = e['faq']
    if set(faq) != set(QUESTIONS) or any(not isinstance(v, str) or not v for v in faq.values()):
        raise ValueError('alfa_tsum_faq_incomplete')
    answer = faq[QUESTIONS[0]]
    if not re.search(r'кешбэк на карту лояльности ЦУМа и ДЛТ', answer, re.I):
        raise ValueError('alfa_tsum_loyalty_currency_changed')
    # Cross-check each visible tier card against the independently worded FAQ.
    # Old baseline rates ("вместо") remain conditions, never promoted benefits.
    for name in ('Orange', 'Black'):
        match = re.fullmatch(re.escape(name) + r' (\d+(?:[.,]\d+)?)%', e['cards'][name])
        clauses = list(re.finditer(r'(\d+(?:[.,]\d+)?)% вместо (\d+(?:[.,]\d+)?)% по карте ' + name + r'\b', answer))
        if not match or len(clauses) != 1 or number(match[1]) != number(clauses[0][1]):
            raise ValueError('alfa_tsum_tier_rate_disagreement')
    card = e['cards'][tier]
    rate = re.fullmatch(re.escape(tier) + r' (\d+(?:[.,]\d+)?)%', card)[1]
    negative = faq[QUESTIONS[7]]
    if not re.fullmatch(r'Нет, начисляется только кешбэк на карту лояльности\.', negative):
        raise ValueError('alfa_tsum_cash_or_miles_answer_changed')
    redemption = e.get('redemption', '')
    if not all(x in redemption for x in ('Alfa Only', 'виджет ЦУМ', 'Повышенный кешбэк в ЦУМе')):
        raise ValueError('alfa_tsum_activation_missing')
    if not e['cards']['White'].startswith('White Повышение до Orange, '):
        raise ValueError('alfa_tsum_white_scope_changed')
    benefit = f'Кешбэк бонусами на карту лояльности ЦУМа и ДЛТ: {rate}% по карте {tier}.'
    conditions = '\n'.join(f'{q}\n{faq[q]}' for q in QUESTIONS)
    return benefit, conditions, redemption


def extract_tsum(source, soup, url, observed_at, cfg):
    if source != SOURCE_ID or url != URL:
        raise ValueError('alfa_tsum_requested_url_mismatch')
    heading = clean(one(soup, '[class*="AlfaOnly__logoTitle___"]'))
    if 'Alfa Only' not in heading or 'картой лояльности ЦУМ' not in heading:
        raise ValueError('alfa_tsum_program_identity')
    faq_root = one(soup, '[class*="AlfaOnly__faqBlock___"]')
    all_faq = {}
    for n in faq_root.select('[data-test-id="accordionWrapper"]'):
        q = clean(one(n, '[class*="AlfaOnly__faqBlockHeaderTitle___"]'))
        a = clean(one(n, '[class*="AlfaOnly__faqBlockAnswer___"]'))
        if q in all_faq:
            raise ValueError('alfa_tsum_duplicate_question')
        all_faq[q] = a
    if any(q not in all_faq for q in QUESTIONS):
        raise ValueError('alfa_tsum_required_question_missing')
    cards = {}
    for n in soup.select('[class*="AlfaOnly__bounsWrapper___"]'):
        label = clean(one(n, '[class*="AlfaOnly__leftSide___"]'))
        if label in cards:
            raise ValueError('alfa_tsum_duplicate_tier')
        cards[label] = clean(n)
    block = one(soup, '[class*="AlfaOnly__privelegiesBlock___"]')
    evidence = {'url': URL, 'heading': heading, 'cards': cards,
                'faq': {q: all_faq[q] for q in QUESTIONS}, 'redemption': clean(block),
                'page_sha256': hashlib.sha256(str(soup).encode()).hexdigest(),
                'reward_currency': 'TSUM_DLT_loyalty_credit',
                'hash_basis': 'BeautifulSoup_HTML_serialization'}
    rows = []
    for tier in ('Orange', 'Black'):
        benefit, conditions, redemption = derived(evidence, tier)
        rows.append(make_offer(SOURCE_ID, 'loyalty-cashback:' + tier.lower(), 'Alfa Only',
            'ЦУМ / ДЛТ', benefit, URL, observed_at, title='ЦУМ / ДЛТ — ' + tier,
            conditions=conditions, redemption=redemption, category='Покупки',
            link_kind='page_block', locator='AlfaOnly__bounsWrapper / tier=' + tier,
            details={'source_scope': 'reviewed_merchant_page_not_program_catalog',
                     'tsum_tier': tier, 'tsum_evidence': evidence,
                     'authenticated_catalogue_equivalence': False}, warnings=WARNINGS))
    return rows


def validate_record(row):
    d = row.get('details', {})
    tier = d.get('tsum_tier')
    benefit, conditions, redemption = derived(d.get('tsum_evidence', {}), tier)
    if (row.get('source_id') != SOURCE_ID or row.get('source_url') != URL
            or row.get('native_id') != 'loyalty-cashback:' + tier.lower()
            or row.get('program') != 'Alfa Only' or row.get('partner_name') != 'ЦУМ / ДЛТ'
            or row.get('record_kind') != 'partner_offer' or row.get('source_status') != 'published'
            or row.get('link_kind') != 'page_block' or row.get('benefit_url') is not None
            or row.get('benefit_text') != benefit or row.get('conditions_text') != conditions
            or row.get('redemption_text') != redemption or row.get('valid_from') is not None
            or row.get('valid_until') is not None or d.get('authenticated_catalogue_equivalence') is not False
            or not set(WARNINGS).issubset(row.get('warnings', []))):
        raise ValueError('alfa_tsum_record_evidence_mismatch')
