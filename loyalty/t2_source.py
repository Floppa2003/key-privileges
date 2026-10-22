"""T2: public catalog objects from the page's own anonymous response, plus exact help blocks.

No login, offer activation, SMS retrieval or direct query-URL crawling is used.
The query-based card URL is not invented; the root URL + native ID locate evidence.
"""
import asyncio,json,re
from datetime import datetime
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from normalized import make_offer,text
from partner_pages import content,MONTHS
from content_discovery import label_id, clean_dom

ROOT='https://msk.t2.ru/bolshe/offers'
REGIONS = {
    'msk': {'region': 'Москва и область', 'source_url': ROOT},
    'spb': {'region': 'Санкт-Петербург и Ленинградская область',
            'source_url': 'https://spb.t2.ru/bolshe/offers'},
}
URLS={
 't2_mixx':'https://msk.t2.ru/help/article/what-included-mixx-m-subscription',
 't2_selection':'https://msk.t2.ru/tariff/premium',
 't2_mixx_s':'https://msk.t2.ru/promotions/article/yandex-station-mixx',
 't2_powerbank':'https://msk.t2.ru/promotions/article/bezlimitnaya-arenda-powerbank'}


def catalog_records(data,observed_at,*,region_key='msk'):
    if region_key not in REGIONS:raise ValueError('unknown_t2_region')
    region=REGIONS[region_key]
    if data.get('meta',{}).get('status')!='OK':raise ValueError('t2_catalog_not_successful')
    offers=data.get('data',{}).get('offers')
    if not isinstance(offers,list) or not offers or len(offers)>1000:raise ValueError('t2_catalog_missing_or_unbounded')
    rows=[];seen=set()
    for obj in offers:
        native=obj.get('id','')
        if not re.fullmatch(r'[A-Fa-f0-9]{32}',native) or native in seen:raise ValueError('t2_duplicate_or_invalid_id')
        seen.add(native)
        agreement=BeautifulSoup(obj.get('agreement') or '', 'html.parser')
        terms=content([agreement]);benefit=text(obj.get('info')) or text(obj.get('name'))
        if not benefit or not terms:raise ValueError('t2_offer_missing_terms')
        expiry=obj.get('dateTo')
        until=datetime.fromisoformat(expiry.replace('Z','+00:00')).date().isoformat() if expiry else None
        company=text(obj.get('companyName')) or text((obj.get('partner') or {}).get('name'))
        flags={key:obj.get(key) for key in ('availableForAll','forAllTariffs','offlineOffer','areaType','offerType','promoCodeType','duration')}
        categories=[{'id':x.get('id'),'name':text(x.get('name'))} for x in obj.get('segments',[])]
        rows.append(make_offer('t2_bolshe',native,'T2 «Больше»',company,benefit,region['source_url'],observed_at,
            conditions=terms,redemption=content(agreement.select('ol')),title=obj.get('name',''),
            category='; '.join(x['name'] for x in categories if x['name']),valid_until=until,
            link_kind='api_record',locator='anonymous page response /api/loyalty/offers data.offers[id='+native+']',
            details={'source_partner_name':text((obj.get('partner') or {}).get('name')),
                     'source_categories':categories,'source_eligibility_flags':flags,'source_date_to':expiry,
                     'region':region['region'],'source_scope':'anonymous_catalog_response_not_personal_account'},
            warnings=['full_terms_are_authoritative','activation_and_personal_code_not_requested','query_card_not_independently_opened']))
    return rows



def period(value):
    months='|'.join(MONTHS)
    pattern=r'Акция действует с\s+(\d{1,2})\s+('+months+r')(?:\s+(\d{4})\s*г\.?)?\s+по\s+(\d{1,2})\s+('+months+r')\s+(\d{4})'
    found=re.search(pattern,re.sub(r'\s+',' ',value),re.I)
    if not found:raise ValueError('t2_article_period_not_recognized')
    start=datetime(int(found[3] or found[6]),MONTHS[found[2].lower()],int(found[1])).date().isoformat()
    end=datetime(int(found[6]),MONTHS[found[5].lower()],int(found[4])).date().isoformat()
    return start,end,found[0]


def page_records(source,raw,observed_at):
    soup=clean_dom(raw);rows=[]
    programs={'t2_mixx':'MiXX M','t2_selection':'T2 Selection','t2_mixx_s':'MiXX S — акции салонов T2','t2_powerbank':'T2 — акции тарифов Black / Premium'}
    def add(native,name,claim,terms,**kwargs):
        rows.append(make_offer(source,native,programs[source],name,claim,URLS[source],observed_at,
            conditions=terms,**kwargs))
    if source=='t2_mixx':
        article=soup.select_one('.article-content')
        if not article:raise ValueError('t2_mixx_article_missing')
        terms=content([article]);lists=article.find_all('ul',recursive=False)
        slots=re.search(r'\b(\d+)\s+настраиваем',terms,re.I)
        if not lists or len(lists)>100:raise ValueError('t2_mixx_section_contract_changed')
        # Legacy display/ID aliases only; never admission or extraction branches.
        mapping=[('+50 ГБ','Трафик 50 ГБ'),('Яндекс Плюс','Яндекс Плюс'),('от X5','X5 «Пакет»'),('Wink','Wink'),('PREMIER','PREMIER'),('VK Музыка','VK Музыка'),('Выгодно вместе','Выгодно вместе'),('КИОН','КИОН'),('RUTUBE','RUTUBE'),('Ozon Premium','Ozon Premium'),('Магнит Плюс Премиум','Магнит Плюс Премиум'),('Литрес','Литрес'),('Юрент','Юрент'),('GPTMobile','GPTMobile'),('Kaspersky Standard','Kaspersky Standard')]
        fixed=[];seen=set()
        for n,ul in enumerate(lists):
            preceding=ul.find_previous_sibling('p')
            section_text=text(preceding.get_text(' ',strip=True)) if preceding else ''
            section_component=('selectable_replacement' if re.search(r'изменить|заменить',section_text,re.I) else
                'prepared_selection' if re.search(r'готовую|состоящ',section_text,re.I) else 'selection_context_unresolved')
            for li in ul.find_all('li',recursive=False):
                claim=text(li.get_text(' ',strip=True))
                if 'всегда в составе' in claim:
                    fixed.append(claim);continue
                matched=[name for marker,name in mapping if marker in claim]
                if not claim:raise ValueError('t2_mixx_empty_service')
                name=matched[0] if len(matched)==1 else claim.split(':',1)[0]
                native=name if len(matched)==1 else label_id(name,'service')
                if native in seen:raise ValueError('t2_mixx_duplicate_service')
                seen.add(native)
                component='included_automatically' if re.search(r'подключится автоматически',claim,re.I) else section_component
                add(native,name,claim,terms,link_kind='page_block',locator='.article-content li = '+claim,
                    details={'membership_component':component,'selection_slots':int(slots[1]) if slots else None},warnings=['not_all_optional_services_are_included_simultaneously'])
        for paragraph in fixed:
            # The actual enumeration supplies the current fixed inventory.
            body=paragraph.split(':',1)[-1]
            for claim in re.split(r',\s+|\s+и\s+(?=\+\d+\s+категор)',body):
                claim=claim.strip(' .;')
                if not claim:continue
                m=re.search(r'скидк[а-яё]*\s+\d+(?:[.,]\d+)?\s*(?:%|руб\.)\s+на\s+(.+)$',claim,re.I)
                name=m[1] if m else claim
                native=name if m else label_id(name,'fixed-service')
                if native in seen:raise ValueError('t2_mixx_duplicate_service')
                seen.add(native)
                add(native,name,claim,terms,link_kind='page_block',locator='.article-content fixed-services paragraph',
                    details={'membership_component':'fixed'},warnings=['source_fixed_inventory_preserved_not_a_guaranteed_personal_bundle'])
    elif source=='t2_selection':
        cards=[c for c in soup.select('.tariff-detail-t2-subscription-premium-card') if 'T2 SELECTION' in text(c.get_text(' ',strip=True)).upper()]
        if len(cards)!=1:raise ValueError('t2_selection_card_missing_or_ambiguous')
        card=cards[0];claim=text(card.select_one('.card-kit-t2__text').get_text(' ',strip=True))
        add('premium-participation','T2',claim,content([card]),link_kind='page_block',locator='.tariff-detail-t2-subscription-premium-card containing T2 SELECTION',
            details={'required_tariff':'Premium','source_scope':'program_summary_not_full_selection_catalog'},warnings=['yandex_discount_rates_not_stated'])
    elif source in ('t2_mixx_s','t2_powerbank'):
        article=soup.select_one('.product-article')
        if not article:raise ValueError('t2_product_article_missing')
        terms=content([article]);start,end,evidence=period(terms)
        if source=='t2_powerbank':
            durations=list(re.finditer(r'Период\s+одной\s+аренды\s+не\s+более\s+(\d+)\s+(?:суток|дней|дня)',terms,re.I))
            if len(durations)>1:raise ValueError('t2_session_limit_ambiguous')
            duration=durations[0] if durations else None
            add('stayin-touch-2025-2026','StayInTouch',terms,terms,valid_from=start,valid_until=end,
                details={'validity_evidence':evidence,
                         'max_session_duration_days':int(duration[1]) if duration else None,
                         'session_duration_evidence':duration[0] if duration else None},
                record_kind='campaign',locator='.product-article')
        else:
            matches=[]
            for clause in re.split(r'[;\n]',terms):
                clause=re.sub(r'\s+',' ',clause).strip()
                m=re.search(r'при покупке подписки (.+?) на (\d+) месяц\w*\s*[-–—]\s*(скидку \d+(?:[.,]\d+)?% на (.+))',clause,re.I)
                if m:matches.append((m[1],m[2],m[3].rstrip('.'),m[4].rstrip('.')))
            if not matches:raise ValueError('t2_speaker_model_conditions_missing')
            seen=set()
            for subscription,months,claim,name in matches:
                if name in seen:raise ValueError('t2_duplicate_model_conditions')
                seen.add(name)
                add(name,name,claim,terms,valid_from=start,valid_until=end,record_kind='campaign',locator='.product-article model-specific clause',
                    details={'required_subscription_months':int(months),'required_subscription':subscription,'validity_evidence':evidence},
                    warnings=['subscription_cost_is_additional_no_net_savings_inferred'])
    else:raise ValueError('unknown_t2_page_source')
    return rows
