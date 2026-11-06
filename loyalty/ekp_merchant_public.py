"""Three reviewed merchant-owned EKP publications, not authenticated card recovery."""
from __future__ import annotations
import hashlib
import re
from datetime import datetime
from bs4 import BeautifulSoup, Comment, Tag
from html_text import html_text
from normalized import make_offer
from content_discovery import label_id, action_clauses

WARNINGS = ['independent_public_partner_page_not_authenticated_EKP_card',
            'regional_card_equivalence_not_verified', 'user_eligibility_not_verified',
            'published_end_date_not_stated']


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
        if re.sub(r'\s+', ' ', html_text(one(block, 'h1'))) != 'Единая карта петербуржца':
            raise ValueError('ekp_artparking_identity')
        ps = [html_text(p) for p in block.find_all('p', recursive=False) if html_text(p)]
        pairs=[];offer_nodes=[]
        for node in block.find_all('p',recursive=False):
            local=[]
            for line in html_text(node).splitlines():
                m=re.fullmatch(r'(.+?\s+(?:www\.|https?://)[^\s]+)\s*[–—-]\s*(\d+(?:[.,]\d+)?%)\s+Промокод\s+([A-Za-z0-9_-]+)',line)
                if m:local.append(m.groups())
            if local:pairs.extend(local);offer_nodes.append(html_text(node))
        if not pairs or len({p[0] for p in pairs})!=len(pairs):raise ValueError('ekp_artparking_product_rates')
        labels={label:re.split(r'\s+(?:www\.|https?://)',label,1)[0] for label,_,_ in pairs}
        remaining=[p for p in ps if p not in offer_nodes and not re.match(r'Программа\s+лояльности',p)]
        scoped={label:[p for p in remaining if re.sub(r'\s+',' ',p).startswith(prefix)] for label,prefix in labels.items()}
        common=[p for p in remaining if not any(p in owned for owned in scoped.values())]
        rows=[]
        legacy_ids={'Концерты':'концерты','Детские программы':'детские программы'}
        for label,rate,code in pairs:
            own='Скидка на '+label+': '+rate+'. Промокод '+code
            terms='\n'.join([own,*common,*scoped[label]])
            activation='\n'.join(p for p in [*common,*scoped[label]] if re.search(r'получен|предъяв|оплачив|способ|промокод',p,re.I))
            rows.append(make(legacy_ids.get(labels[label]) or label_id(label,'service'),own,terms,activation,
                '#main > .container; '+label,details={'product_scope':label,'public_literal_code':True}))
        return rows

    if source == 'ekp_domknigi_public':
        block = one(dom, 'article.page-single__article')
        ps = [html_text(p,br_separator=' ') for p in block.find_all('p') if html_text(p)]
        terms = '\n'.join(ps)
        if not ps or not re.match(r'Дом\s+книги\s+и\s+Единая\s+карта\s+петербуржца',ps[0]):
            raise ValueError('ekp_domknigi_identity')
        rates = re.findall(r'скидка\s+(\d+(?:[.,]\d+)?%)', terms, re.I)
        if not rates or len(set(rates)) != 1:
            raise ValueError('ekp_domknigi_rate_disagreement')
        period=re.findall(r'Срок\s+проведения:\s*с\s+(\d{2}\.\d{2}\.\d{4})',terms)
        if len(set(period))>1:raise ValueError('ekp_domknigi_conditions')
        start=datetime.strptime(period[0],'%d.%m.%Y').date().isoformat() if period else None
        links = sorted(set(a['href'] for a in block.select('a[href]')))
        return [make('весь ассортимент', ps[0], terms,
            '\n'.join(p for p in ps if re.search(r'назвать\s+промокод\s+на\s+кассе|Интернет',p)),
            'article.page-single__article', valid_from=start,
            details={'published_links': links, 'validity_evidence': next((p for p in ps if re.match(r'Срок\s+проведения:',p)),None),
                     'public_literal_code': False, 'publication_date_is_not_validity': True})]

    if source == 'ekp_itc_public':
        block = one(dom, '#bx_3218110189_78981')
        if not re.match(r'Единая\s+карта\s+петербуржца\s+\(ЕКП\)',html_text(block)):
            raise ValueError('ekp_itc_identity')
        # Browser HTML repair may move nested <p> nodes after the owning news-item.
        # Stop at the next news-item, never borrow another association's discount.
        parts = [html_text(block,br_separator=' ')]
        for sibling in block.next_siblings:
            if not isinstance(sibling, Tag):
                continue
            if 'news-item' in sibling.get('class', []):
                break
            if html_text(sibling):
                parts.append(html_text(sibling,br_separator=' '))
        terms = '\n'.join(parts)
        claims = re.findall(r'Теперь\s+обладатели\s+карты.*?(\d+(?:[.,]\d+)?%)\s+при\s+оплате\s+ЕКП!', terms, re.S)
        if len(claims) != 1 or len(re.findall(r'\d+(?:[.,]\d+)?%', terms)) != 1 or not re.search(r'обучении\s+на\s+наших\s+программах',terms):
            raise ValueError('ekp_itc_payment_scope')
        clause = re.search(r'Теперь\s+обладатели\s+карты.*?при\s+оплате\s+ЕКП!', terms, re.S)[0]
        return [make('обучение', 'Скидка: ' + clause, terms, clause,
            '#bx_3218110189_78981 and following paragraphs until next .news-item',
            details={'payment_instrument': 'ЕКП', 'public_literal_code': False})]
    raise ValueError('ekp_merchant_unknown_source')
