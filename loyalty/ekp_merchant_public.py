"""Three reviewed merchant-owned EKP publications, not authenticated card recovery."""
from __future__ import annotations
import hashlib
import re
from datetime import datetime
from bs4 import BeautifulSoup, Comment, Tag
from normalized import make_offer, text

WARNINGS = ['independent_public_partner_page_not_authenticated_EKP_card',
            'regional_card_equivalence_not_verified', 'user_eligibility_not_verified',
            'published_end_date_not_stated']


def compact(node):
    return text(node.get_text(' ', strip=True))


def one(soup, selector):
    found = soup.select(selector)
    if len(found) != 1:
        raise ValueError('ekp_merchant_missing_or_duplicate_section:' + selector)
    return found[0]


def extract_merchant(source, soup, url, observed_at, cfg):
    if url != cfg['url']:
        raise ValueError('ekp_merchant_exact_url')
    dom = BeautifulSoup(str(soup), 'html.parser')
    for node in dom.select('script,style,noscript,form,input,textarea,nav,header,footer,[hidden],[aria-hidden="true"]'):
        if node.parent is not None:
            node.decompose()
    for node in dom.find_all(string=lambda value: isinstance(value, Comment)):
        node.extract()
    details = {'source_scope': 'reviewed_merchant_owned_EKP_terms',
               'partner_identity_origin': 'reviewed_exact_partner_owned_url',
               'authenticated_catalogue_equivalence': False,
               'source_account_used': False, 'coupon_issued': False,
               'page_sha256': hashlib.sha256(str(soup).encode()).hexdigest(),
               'hash_basis': 'BeautifulSoup_HTML_serialization'}

    def make(native, benefit, terms, redemption, locator, **kwargs):
        return make_offer(source, native, cfg['program'], cfg['partner'], benefit,
            url, observed_at, title=cfg['partner'] + ' — ' + native,
            category=cfg['category'], conditions=terms, redemption=redemption,
            link_kind='page_block', locator=locator, details={**details, **kwargs.pop('details', {})},
            warnings=list(WARNINGS), **kwargs)

    if source == 'ekp_artparking_public':
        block = one(dom, '#main > .container')
        if compact(one(block, 'h1')) != 'Единая карта петербуржца':
            raise ValueError('ekp_artparking_identity')
        ps = [compact(p) for p in block.find_all('p', recursive=False) if compact(p)]
        offers = [p for p in ps if p.startswith('Скидки предоставляются на следующие услуги')]
        if len(offers) != 1:
            raise ValueError('ekp_artparking_offer_block')
        offer = offers[0]
        pairs = re.findall(r'(Концерты www\.artparking\.org|Детские программы www\.gorodmus\.ru)\s*[–—-]\s*(\d+(?:[.,]\d+)?%)\s+Промокод\s+([A-Za-z0-9_-]+)', offer)
        if len(pairs) != 2 or len({p[0] for p in pairs}) != 2 or len(re.findall(r'\d+(?:[.,]\d+)?%', offer)) != 2:
            raise ValueError('ekp_artparking_product_rates')
        common = [p for p in ps if p != offer and not p.startswith(('Программа лояльности', 'Детские программы Центра'))]
        children = [p for p in ps if p.startswith('Детские программы Центра')]
        joined = '\n'.join(common)
        if len(children) != 1 or not all(x in joined for x in ('предварительной брони', 'при наличии свободных мест',
                'двумя способами', 'необходимо предъявить Единую карту', 'Зеленогорской кирхе')):
            raise ValueError('ekp_artparking_redemption_or_exclusion')
        rows = []
        for label, rate, code in pairs:
            kid = label.startswith('Детские')
            own = ('Скидка на ' + label + ': ' + rate + '. Промокод ' + code)
            terms = '\n'.join([own, *common, *(children if kid else [])])
            rows.append(make('детские программы' if kid else 'концерты', own, terms,
                '\n'.join(p for p in common if 'способами' in p or 'Важное условие' in p) + ('\n' + children[0] if kid else ''),
                '#main > .container; ' + label, details={'product_scope': label, 'public_literal_code': True}))
        return rows

    if source == 'ekp_domknigi_public':
        block = one(dom, 'article.page-single__article')
        ps = [compact(p) for p in block.find_all('p') if compact(p)]
        terms = '\n'.join(ps)
        if not ps or not ps[0].startswith('Дом книги и Единая карта петербуржца'):
            raise ValueError('ekp_domknigi_identity')
        rates = re.findall(r'скидка\s+(\d+(?:[.,]\d+)?%)', terms, re.I)
        if len(rates) != 2 or len(set(rates)) != 1:
            raise ValueError('ekp_domknigi_rate_disagreement')
        period = re.findall(r'Срок проведения:\s*с (\d{2}\.\d{2}\.\d{4})\s*[—–-]\s*до распоряжения отдела маркетинга', terms)
        if len(period) != 1 or not all(x in terms for x in ('не суммируется', 'Оплатить покупку бонусами также нельзя',
                'Интернет', 'назвать промокод на кассе')):
            raise ValueError('ekp_domknigi_conditions')
        start = datetime.strptime(period[0], '%d.%m.%Y').date().isoformat()
        links = sorted(set(a['href'] for a in block.select('a[href]')))
        return [make('весь ассортимент', ps[0], terms,
            '\n'.join(p for p in ps if 'назвать промокод на кассе' in p or 'Интернет' in p),
            'article.page-single__article', valid_from=start,
            details={'published_links': links, 'validity_evidence': 'Срок проведения: с ' + period[0] + ' — до распоряжения отдела маркетинга',
                     'public_literal_code': False, 'publication_date_is_not_validity': True})]

    if source == 'ekp_itc_public':
        block = one(dom, '#bx_3218110189_78981')
        if not compact(block).startswith('Единая карта петербуржца (ЕКП)'):
            raise ValueError('ekp_itc_identity')
        # Browser HTML repair may move nested <p> nodes after the owning news-item.
        # Stop at the next news-item, never borrow another association's discount.
        parts = [compact(block)]
        for sibling in block.next_siblings:
            if not isinstance(sibling, Tag):
                continue
            if 'news-item' in sibling.get('class', []):
                break
            if compact(sibling):
                parts.append(compact(sibling))
        terms = '\n'.join(parts)
        claims = re.findall(r'Теперь обладатели карты.*?(\d+(?:[.,]\d+)?%)\s+при оплате ЕКП!', terms, re.S)
        if len(claims) != 1 or len(re.findall(r'\d+(?:[.,]\d+)?%', terms)) != 1 or 'обучении на наших программах' not in terms:
            raise ValueError('ekp_itc_payment_scope')
        clause = re.search(r'Теперь обладатели карты.*?при оплате ЕКП!', terms, re.S)[0]
        return [make('обучение', 'Скидка: ' + clause, terms, clause,
            '#bx_3218110189_78981 and following paragraphs until next .news-item',
            details={'payment_instrument': 'ЕКП', 'public_literal_code': False})]
    raise ValueError('ekp_merchant_unknown_source')
