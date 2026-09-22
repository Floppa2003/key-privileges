"""Pure parsing of Backit public shop pages; no account actions or network."""
from __future__ import annotations
import hashlib, re
from urllib.parse import urlsplit, urljoin
from bs4 import BeautifulSoup
from normalized import number
from public_reward_projection import plain, one, make_record

SOURCE='backit_public'
ROOT='https://backit.me/ru/cashback/shops'
PROGRAM='Backit — денежный кешбэк'
MAX_CARDS=1200
EXCLUDED_NAME=re.compile(r'банк|bank|дебетов|кредит|займ|вклад|ипотек|инвестиц|расч[её]тн|РКО|супер.?сплит|(?:^|\W)(?:ВТБ|МКБ|ОТП)(?:\W|$)|Яндекс Браузер|ваканси|работа курьер|ставки на спорт|букмек|казино|casino|(?:^|\W)bet(?:\W|$)',re.I)
NUM=r'\d+(?:[ \u00a0\u202f]\d{3})*(?:[.,]\d+)?'
UNIT=r'%|р\.?|p\.?|руб\.?|₽|\$|USD|€|EUR'
RATE=re.compile(rf'(?P<qual>до|от)?\s*(?:(?P<lo>{NUM})\s*(?P<lo_unit>{UNIT})?\s*[-–—]\s*)?(?P<value>{NUM})\s*(?P<unit>{UNIT})',re.I)

class ExcludedOffer(ValueError):
    """Source-disclosed non-offer, not successful extraction or a transport failure."""

def card_url(url):
    p=urlsplit(url)
    if p.scheme!='https' or p.netloc!='backit.me' or p.query or p.fragment or '..' in p.path or not re.fullmatch(r'/ru/cashback/shops/[a-zA-Z0-9][a-zA-Z0-9_.-]*',p.path):raise ValueError('backit_card_url')
    return url

def inventory(raw,page):
    soup=BeautifulSoup(raw,'html.parser');pg=one(soup,'.mu-pagination')
    total,size,actual=(int(pg.get(x,'0')) for x in ('total','pagesize','currentpage'))
    if not 0<total<=MAX_CARDS or not 0<size<=100 or actual!=page:raise ValueError('backit_pagination_identity_or_bound')
    cards=[]
    for a in soup.select('.offers .offer-cards a.mu-store__wrapper[href]'):
        card=dict(url=card_url(urljoin(ROOT,a['href'])),name=plain(one(a,'.mu-store__title')))
        if re.search(r'Временно отключ[её]н',plain(a),re.I):card['inactive']=True
        cards.append(card)
    if len(cards)!=min(size,total-(page-1)*size) or len({c['url'] for c in cards})!=len(cards):raise ValueError('backit_page_count_or_duplicate')
    if any(not c['name'] for c in cards):raise ValueError('backit_empty_name')
    return cards,total,size

def source_fields(e):
    url=card_url(e['url']);name=e.get('name','')
    if not name or EXCLUDED_NAME.search(name) or not re.fullmatch(r'[a-f0-9]{64}',e.get('page_sha256','')):raise ValueError('backit_record_identity')
    valid_from=valid_until=None
    if e.get('promo_period'):
        from promotion_period import promotion_dates
        context=e.get('promotion_context',{})
        try:
            valid_from,valid_until=promotion_dates(e['promo_period'],context.get('page_title',''),context.get('observed_on',''))
        except ValueError as exc:
            reason=str(exc) if str(exc) in ('promotional_period_expired','promotional_period_not_started') else 'dated_promotional_rate_requires_current_confirmation'
            raise ExcludedOffer(reason) from exc
    tariffs=e.get('tariffs',[])
    if not 1<=len(tariffs)<=80:raise ValueError('backit_tariff_count')
    claims=[];terms=[];zero_tariffs=[];coupons=[]
    for row in tariffs:
        if not row['rate'] and re.search(r'промокод',row['scope'],re.I):
            zero_tariffs.append(row['scope'])
            code=re.match(r'([A-Z0-9_-]{3,50})\s+промокод\b',row['scope'],re.I)
            if code:coupons.append('Промокод: '+code[1])
            continue
        m=RATE.fullmatch(row['rate'])
        if not m or not row['scope']:raise ValueError('backit_unparsed_tariff')
        amount=number(m['value']);unit=m['unit']
        if float(amount)<=0:
            zero_tariffs.append('Кешбэк '+row['rate']+' — '+row['scope']);continue
        unit='percent' if unit=='%' else 'USD' if unit in ('$','USD') else 'EUR' if unit in ('€','EUR') else 'RUB'
        if unit=='percent' and float(amount)>100:raise ValueError('backit_invalid_percent')
        if m['lo'] and (float(number(m['lo']))>float(amount) or (m['lo_unit'] and m['lo_unit']!=m['unit'])):raise ValueError('backit_invalid_range')
        display=(m['lo']+'–'+m['value']+m['unit']) if m['lo'] else row['rate']
        display=re.sub(r'p\.?$', 'р.', display, flags=re.I)
        claim='Кешбэк '+display+' — '+row['scope'];claims.append(claim)
        terms.append(dict(kind='cashback',value=amount,unit=unit,qualifier='range' if m['lo'] else {'до':'up_to','от':'at_least'}.get(m['qual'],'exact'),reward_unit='cash_after_merchant_confirmation',fragment=claim,scope={'tariff_condition':row['scope']}))
        if m['lo']:terms[-1]['value_min']=number(m['lo'])
    if not claims:raise ExcludedOffer('no_positive_tariff')
    if not e.get('activation') or not e.get('conditions'):raise ValueError('backit_missing_practical_terms')
    if not re.search(r'зарегистрирован|уч[её]тн|регистрац|Войдите|Вход',e['activation'],re.I):raise ValueError('backit_activation_owner')
    return dict(native=urlsplit(url).path.rsplit('/',1)[-1],program=PROGRAM,partner=name,title='Backit → '+name,
        valid_from=valid_from,valid_until=valid_until,period_year_inferred=any(len(x.split('.'))==2 for x in re.findall(r'\b\d{1,2}\.\d{1,2}(?:\.\d{4})?\b',e.get('promo_period',''))),benefit='\n'.join(claims),conditions='\n'.join([e['conditions'],*zero_tariffs]+(['Период повышенного кешбэка: '+e['promo_period']] if e.get('promo_period') else [])),activation='\n'.join([e['activation'],*coupons]),category='Покупки / услуги / денежный кешбэк',url=url,
        locator='.shop-rates > .row; .shop-conditions; scoped cashback instructions',terms=terms,
        scope={'shop_slug':urlsplit(url).path.rsplit('/',1)[-1],'eligibility_not_verified':True},warnings=['cashback_not_upfront_discount','payout_method_and_minimum_require_account_review']+(['merchant_specific_conditions_not_displayed'] if e.get('merchant_conditions_absent') else []))

def parse_detail(raw,card,observed_at):
    if card.get('inactive'):raise ExcludedOffer('source_disclosed_temporarily_disabled')
    soup=BeautifulSoup(raw,'html.parser');card_url(card['url'])
    if not soup.select('span.mobile.name,.shop-rates,.shop-conditions') and soup.select('a.mu-store__wrapper[href]') and plain(soup.title)=='Backit':
        raise ExcludedOffer('detail_page_replaced_by_catalogue')
    name=plain(one(soup,'span.mobile.name'))
    if name!=card['name']:raise ValueError('backit_detail_name_disagrees_with_inventory')
    table=one(soup,'.shop-rates');tariffs=[]
    for node in table.select(':scope > .row'):
        label=plain(one(node,'.name'));values=node.select('.rate > span:not(.rate--old)')
        if len(values)!=1:raise ValueError('backit_current_rate_not_unique')
        tariffs.append({'rate':plain(values[0]),'scope':label})
    period='\n'.join(plain(n) for n in table.select(':scope > .info') if plain(n))
    custom=soup.select('.shop-conditions')
    if len(custom)>1:raise ValueError('backit_duplicate_merchant_conditions')
    general=plain(one(soup,'.shop-rules'))
    if not general:raise ValueError('backit_purchase_rules_missing')
    restriction='\n'.join(filter(None,[plain(custom[0]) if custom else '',general]));actions=[]
    for block in soup.select('.shop-markdown.markdown'):
        h=block.find('h2')
        if h is None or not re.match(r'Как получить к[еэ]шб[еэ]к',plain(h),re.I):continue
        for node in h.find_next_siblings():
            if node.name in ('h2','h3','h4'):break
            value=plain(node)
            if not value:continue
            if re.match(r'Сделав|Именно поэтому|Подробнее об интернет|Купер|Спортмастер',value):break
            if re.search(r'зарегистрирован|уч[её]тн|регистрац|войдите|активиру|после активации|переход',value,re.I):actions.append(value)
            else:break
        if actions:break
    if not actions:
        # The page's own account and cashback controls are sufficient instructions
        # even when the optional SEO article is absent. No button is clicked.
        login=plain(one(soup,'.mu-auth__login_desktop'))
        activate=plain(one(soup,'#activate-button'))
        if not re.search(r'Вход.*Регистрац',login,re.I|re.S) or not re.fullmatch(r'Купить с к[еэ]шб[еэ]ком',activate,re.I):raise ValueError('backit_purchase_controls_changed')
        actions=[login.replace('\n',' / ')+' → '+activate]
    e=dict(merchant_conditions_absent=not custom,url=card['url'],name=name,tariffs=tariffs,promo_period=period,conditions=restriction,activation='\n'.join(actions),page_sha256=hashlib.sha256(raw.encode()).hexdigest())
    if period:e['promotion_context']={'page_title':plain(soup.title),'observed_on':observed_at[:10]}
    return make_record(SOURCE,e,observed_at)
