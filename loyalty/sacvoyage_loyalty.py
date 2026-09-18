"""Two hotel-owned loyalty audiences; never substitute them for RZD terms."""
from __future__ import annotations
import re
from bs4 import BeautifulSoup, Comment, Tag
from normalized import make_offer, normalize_rates, text

URL = 'https://sacvoyage.ru/aktsii/'
HEADINGS = {'Программа лояльности': 'member', 'Реферальная программа': 'referred_guest'}


def extract_sacvoyage(source, soup, url, observed_at, cfg):
    if url != URL or url != cfg['url']:
        raise ValueError('sacvoyage_exact_url')
    dom = BeautifulSoup(str(soup), 'html.parser')
    for node in dom.select('script,style,noscript,form,input,nav,header,footer,[hidden],[aria-hidden="true"]'):
        node.decompose()
    for node in dom.find_all(string=lambda value: isinstance(value, Comment)):
        node.extract()
    titles = dom.select('main h2.about__title')
    panels = dom.select('main .services__text')
    if len(titles) != 1 or text(titles[0].get_text()) != 'Скидки' or len(panels) != 1:
        raise ValueError('sacvoyage_sections')
    for node in panels[0].children:
        if isinstance(node, Tag) and node.name != 'p' and text(node.get_text()):
            raise ValueError('sacvoyage_unparsed_terms')
        if not isinstance(node, Tag) and text(str(node)):
            raise ValueError('sacvoyage_unparsed_terms')
    sections = {}; common = []; current = None; tail = False
    for node in panels[0].find_all('p', recursive=False):
        value = text(node.get_text(' ', strip=True))
        if not value:
            continue
        if value in HEADINGS:
            if value in sections or tail:
                raise ValueError('sacvoyage_duplicate_section')
            sections[value] = []; current = value
        elif value.startswith('Условия могут меняться.'):
            tail = True; common.append(value)
        elif tail:
            common.append(value)
        elif current:
            sections[current].append(value)
        else:
            raise ValueError('sacvoyage_unowned_text')
    if set(sections) != set(HEADINGS) or not common:
        raise ValueError('sacvoyage_missing_section_or_notice')
    common_text = '\n'.join(common)
    if not re.search(r'личном кабинете', common_text, re.I):
        raise ValueError('sacvoyage_current_terms_boundary')
    result = []
    for heading, native in HEADINGS.items():
        own = '\n'.join(sections[heading])
        if not own or len(own + common_text) > 5000:
            raise ValueError('sacvoyage_terms_bound')
        requirements = ('регистрац', 'не суммируется', 'агентств', 'корпоративн') if native == 'member' else ('персональная ссылка', 'первое проживание')
        if not all(re.search(term, own, re.I) for term in requirements):
            raise ValueError('sacvoyage_redemption_boundary')
        # The source's page heading supplies the type; only this audience supplies values.
        benefit = text(titles[0].get_text()) + ': ' + re.sub(r'\s+', ' ', own)
        rates = normalize_rates(benefit)
        if len(rates) != 1 or rates[0]['kind'] != 'discount':
            raise ValueError('sacvoyage_rate_ambiguous')
        result.append(make_offer(source, native, cfg['program'], cfg['partner'], benefit,
            url, observed_at, title=heading, category=cfg['category'],
            conditions=own + '\n' + common_text, redemption=own,
            locator='main .services__text; section ' + heading,
            details={'source_scope': 'hotel_owned_loyalty_not_RZD',
                     'partner_identity_origin': 'reviewed_exact_partner_owned_url',
                     'audience': native, 'source_heading_context': text(titles[0].get_text()),
                     'source_account_used': False, 'personal_referral_link_obtained': False,
                     'gated_catalogue_terms_recovered': False, 'user_eligibility_verified': False},
            warnings=['not_the_separate_RZD_Bonus_offer',
                      'personal_referral_link_required_not_obtained' if native == 'referred_guest' else 'registration_required_not_performed',
                      'published_terms_subject_to_account_confirmation',
                      'published_end_date_not_stated']))
    return result
