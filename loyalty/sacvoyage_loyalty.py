"""Two hotel-owned loyalty audiences; never substitute them for RZD terms."""
from __future__ import annotations
import re
from bs4 import BeautifulSoup, Comment, Tag
from normalized import make_offer, normalize_rates, text
from content_discovery import label_id, literal_benefits
from partner_pages import content

URL = 'https://sacvoyage.ru/aktsii/'
LEGACY_IDS = {'Программа лояльности': 'member', 'Реферальная программа': 'referred_guest'}


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
    if len(titles) != 1 or not text(titles[0].get_text()) or len(panels) != 1:
        raise ValueError('sacvoyage_sections')
    sections={};common=[];current=None;tail=False
    for node in panels[0].children:
        value=content([node]) if isinstance(node,Tag) else text(str(node))
        if not value:continue
        bold=node.select('strong,b') if isinstance(node,Tag) else []
        heading=(isinstance(node,Tag) and node.name in ('h2','h3','h4')) or (len(bold)==1 and text(bold[0].get_text(' ',strip=True))==value)
        if heading:
            if value in sections:raise ValueError('sacvoyage_duplicate_section')
            sections[value]=[];current=value;tail=False
        elif re.match(r'(?:Общие условия|Условия могут меняться)',value,re.I):
            tail=True;common.append(value)
        elif tail or current is None:common.append(value)
        else:sections[current].append(value)
    if not sections or len(sections)>100:raise ValueError('sacvoyage_missing_sections')
    common_text='\n'.join(common)
    result = []
    for heading,paragraphs in sections.items():
        native=LEGACY_IDS.get(heading) or label_id(heading,'section')
        own = '\n'.join(paragraphs)
        if not own or len(own + common_text) > 36000:
            raise ValueError('sacvoyage_terms_bound')
        # The current page heading can supply a discount label; figures from
        # another section never supply a missing rate in this audience.
        benefit=text(titles[0].get_text())+': '+re.sub(r'\s+',' ',own)
        rates=normalize_rates(benefit)
        claims,_=literal_benefits(own)
        kind='partner_offer' if rates or claims else 'source_observation'
        result.append(make_offer(source, native, cfg['program'], cfg['partner'], benefit,
            url, observed_at, title=heading, category=cfg['category'],
            conditions='\n'.join(filter(None,(own,common_text))), redemption=own,record_kind=kind,
            locator='main .services__text; section ' + heading,
            details={'source_scope': 'hotel_owned_loyalty_not_RZD',
                     'partner_identity_origin': 'reviewed_exact_partner_owned_url',
                     'audience': native, 'source_heading_context': text(titles[0].get_text()),
                     'source_account_used': False, 'personal_referral_link_obtained': False,
                     'gated_catalogue_terms_recovered': False, 'user_eligibility_verified': False},
            warnings=['not_the_separate_RZD_Bonus_offer',
                      'account_actions_not_performed',
                      'published_terms_subject_to_account_confirmation',
                      'published_end_date_not_stated']))
    return result
