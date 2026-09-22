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
EXCLUDED_NAME=re.compile(r'банк|bank|кредит|займ|вклад|ипотек|инвестиц|расч[её]тн|РКО|супер.?сплит|Яндекс Браузер|ваканси|работа курьер|ставки на спорт|букмек|казино|casino|(?:^|\W)bet(?:\W|$)',re.I)
RATE=re.compile(r'(?P<qual>до|от)?\s*(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>%|р\.?|руб\.?|₽|\$|USD|€|EUR)',re.I)

class ExcludedOffer(ValueError):
    """Source-disclosed non-offer, not successful extraction or a transport failure."""

def card_url(url):
    p=urlsplit(url)
    if p.scheme!='https' or p.netloc!='backit.me' or p.query or p.fragment or not re.fullmatch(r'/ru/cashback/shops/[a-zA-Z0-9_-]+',p.path):raise ValueError('backit_card_url')
    return url

def inventory(raw,page):
    soup=BeautifulSoup(raw,'html.parser');pg=one(soup,'.mu-pagination')
    total,size,actual=(int(pg.get(x,'0')) for x in ('total','pagesize','currentpage'))
    if not 0<total<=MAX_CARDS or not 0<size<=100 or actual!=page:raise ValueError('backit_pagination_identity_or_bound')
    cards=[dict(url=card_url(urljoin(ROOT,a['href'])),name=plain(one(a,'.mu-store__title'))) for a in soup.select('.offers .offer-cards a.mu-store__wrapper[href]')]
    if len(cards)!=min(size,total-(page-1)*size) or len({c['url'] for c in cards})!=len(cards):raise ValueError('backit_page_count_or_duplicate')
    if any(not c['name'] for c in cards):raise ValueError('backit_empty_name')
    return cards,total,size

def source_fields(e):
    url=card_url(e['url']);name=e.get('name','')
    if not name or EXCLUDED_NAME.search(name) or not re.fullmatch(r'[a-f0-9]{64}',e.get('page_sha256','')):raise ValueError('backit_record_identity')
    if e.get('promo_period'):raise ExcludedOffer('dated_promotional_rate_requires_current_confirmation')
    tariffs=e.get('tariffs',[])
    if not 1<=len(tariffs)<=80:raise ValueError('backit_tariff_count')
    claims=[];terms=[]
    for row in tariffs:
        m=RATE.fullmatch(row['rate'])
        if not m or not row['scope']:raise ValueError('backit_unparsed_tariff')
        amount=number(m['value']);unit=m['unit']
        if float(amount)<=0:continue
        unit='percent' if unit=='%' else 'USD' if unit in ('$','USD') else 'EUR' if unit in ('€','EUR') else 'RUB'
        if unit=='percent' and float(amount)>100:raise ValueError('backit_invalid_percent')
        claim='Кешбэк '+row['rate']+' — '+row['scope'];claims.append(claim)
        terms.append(dict(kind='cashback',value=amount,unit=unit,qualifier={'до':'up_to','от':'at_least'}.get(m['qual'],'exact'),reward_unit='cash_after_merchant_confirmation',fragment=claim,scope={'tariff_condition':row['scope']}))
    if not claims:raise ExcludedOffer('no_positive_tariff')
    if not e.get('activation') or not e.get('conditions'):raise ValueError('backit_missing_practical_terms')
    if not re.search(r'зарегистрирован|уч[её]тн|регистрац|Войдите',e['activation'],re.I):raise ValueError('backit_activation_owner')
    return dict(native=urlsplit(url).path.rsplit('/',1)[-1],program=PROGRAM,partner=name,title='Backit → '+name,
        benefit='\n'.join(claims),conditions=e['conditions'],activation=e['activation'],category='Покупки / услуги / денежный кешбэк',url=url,
        locator='.shop-rates > .row; .shop-conditions; scoped cashback instructions',terms=terms,
        scope={'shop_slug':urlsplit(url).path.rsplit('/',1)[-1],'eligibility_not_verified':True},warnings=['cashback_not_upfront_discount','payout_method_and_minimum_require_account_review'])

def parse_detail(raw,card,observed_at):
    soup=BeautifulSoup(raw,'html.parser');card_url(card['url']);name=plain(one(soup,'span.mobile.name'))
    if name!=card['name']:raise ValueError('backit_detail_name_disagrees_with_inventory')
    table=one(soup,'.shop-rates');tariffs=[]
    for node in table.select(':scope > .row'):
        label=plain(one(node,'.name'));values=node.select('.rate > span:not(.rate--old)')
        if len(values)!=1:raise ValueError('backit_current_rate_not_unique')
        tariffs.append({'rate':plain(values[0]),'scope':label})
    period='\n'.join(plain(n) for n in table.select(':scope > .info') if plain(n))
    restriction=plain(one(soup,'.shop-conditions'));actions=[]
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
    e=dict(url=card['url'],name=name,tariffs=tariffs,promo_period=period,conditions=restriction,activation='\n'.join(actions),page_sha256=hashlib.sha256(raw.encode()).hexdigest())
    return make_record(SOURCE,e,observed_at)
