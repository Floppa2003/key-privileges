"""Pure candidate parser for source-owned EKP expanded cards, never neighbour text."""
from __future__ import annotations
import re
from urllib.parse import urlsplit, parse_qsl
from bs4 import BeautifulSoup, Tag

LOGIN='Для просмотра подробной информации о программе лояльности авторизуйтесь'


def identity(url):
    u=urlsplit(url);q=parse_qsl(u.query,keep_blank_values=True)
    match=re.fullmatch(r'/capabilities/loyalty/tiles/(\d+)/?',u.path)
    if (u.scheme!='https' or u.netloc!='ekp.spb.ru' or not match or u.fragment
        or len(q)>1 or (q and (q[0][0]!='region' or not re.fullmatch(r'\d+',q[0][1])))):
        raise ValueError('ekp_source_url_invalid')
    return match[1],q[0][1] if q else None


def plain(node):
    copy=BeautifulSoup(str(node),'html.parser')
    for b in copy.select('br'):b.replace_with('\n')
    for n in copy.select('script,style,button,form,input,textarea,iframe'):n.decompose()
    return '\n'.join(' '.join(line.split()) for line in copy.get_text(' ',strip=False).splitlines() if line.strip())


def section(owner,label):
    headings=[p for p in owner.select('p.font-weight-bold,h2,h3,h4') if plain(p)==label]
    if len(headings)>1:raise ValueError('ekp_duplicate_section')
    if not headings:return None
    blocks=[]
    for node in headings[0].next_siblings:
        if isinstance(node,Tag):
            if node.name in ('h2','h3','h4') or 'font-weight-bold' in node.get('class',[]):break
            value=plain(node)
        else:value=' '.join(str(node).split())
        if value:blocks.append(value)
    return '\n'.join(blocks).strip()


def extract(raw,url,expected_title=None):
    ident,region=identity(url);soup=BeautifulSoup(raw,'html.parser')
    owners=soup.find_all(id='partner.'+ident)
    if len(owners)!=1:raise ValueError('ekp_detail_owner_not_unique')
    owner=owners[0]
    if owner.find(id=re.compile(r'^partner\.')):raise ValueError('ekp_nested_partner_owner')
    titles=owner.select('.v-card-title')
    if len(titles)!=1:raise ValueError('ekp_detail_title_not_unique')
    title=plain(titles[0])
    if not title or (expected_title is not None and title!=' '.join(expected_title.split())):
        raise ValueError('ekp_detail_title_changed')
    body=plain(owner)
    if re.search(r'access denied|captcha|проверка безопасности',body,re.I):raise ValueError('access_challenge')
    program=section(owner,'Программа лояльности')
    redemption=section(owner,'Как получить скидку')
    locked=LOGIN in body
    if locked and program is not None:raise ValueError('ekp_conflicting_access_state')
    if not locked and not program:raise ValueError('ekp_public_terms_missing')
    notices=[]
    if locked:
        notices=[plain(n) for n in owner.select('.v-card-text') if LOGIN in plain(n)]
        if len(notices)!=1:raise ValueError('ekp_login_notice_not_unique')
    teasers=list(dict.fromkeys(plain(n) for n in owner.select('.v-chip__content') if plain(n)))
    tags=list(dict.fromkeys(plain(n).lstrip('# ').strip() for n in owner.select('.text-caption .v-list-item__content') if plain(n)))
    return {'native_id':ident,'source_url':url,'source_region_parameter':region,'partner_name':title,
        'read_access':'login_required' if locked else 'public_terms','program_text':program,
        'redemption_text':redemption,'authentication_notice':notices[0] if notices else None,
        'teaser_texts':teasers,'source_tags':tags,'owned_text':body,
        'user_eligibility_verified':False,'all_program_conditions_verified':False,
        'teasers_are_not_verified_discount_rates':True}


def selfcheck():
    template='<div id="partner.{id}"><div class="v-card-title">{name}</div><div class="v-chip__content">Скидка 99%</div><div><p class="font-weight-bold">Как получить скидку</p><p>{redeem}</p></div><div><p class="font-weight-bold">Программа лояльности</p><p>{terms}</p></div></div>'
    for ident,amount in [('11',300),('27',777)]:
        raw=template.format(id=ident,name='Партнёр '+ident,redeem='Предъявить карту',terms=f'Скидка {amount} руб. при покупке от 3000 руб.<br>Не суммируется')
        # Adjacent promotion and a login wall must not contaminate the owned card.
        raw+='<div id="partner.999"><div class="v-card-title">Чужой партнёр</div>'+LOGIN+'</div>'
        item=extract(raw,f'https://ekp.spb.ru/capabilities/loyalty/tiles/{ident}?region=98','Партнёр '+ident)
        assert item['read_access']=='public_terms' and str(amount) in item['program_text'] and '99%' not in item['program_text'] and 'Чужой' not in item['owned_text']
    locked='<div id="partner.5"><div class="v-card-title">Закрытый</div><div class="v-card-text">'+LOGIN+' в личном кабинете.</div></div>'
    result=extract(locked,'https://ekp.spb.ru/capabilities/loyalty/tiles/5')
    assert result['read_access']=='login_required' and result['program_text'] is None
    for url in ['https://other.test/capabilities/loyalty/tiles/5','https://ekp.spb.ru/capabilities/loyalty/tiles/5?token=x']:
        try:extract(locked,url)
        except ValueError:pass
        else:raise AssertionError('unsafe source identity')
    for raw in [locked+locked,locked.replace('partner.5','partner.6')]:
        try:extract(raw,'https://ekp.spb.ru/capabilities/loyalty/tiles/5')
        except ValueError:pass
        else:raise AssertionError('wrong/duplicate owner')
    print('EKP owned terms: changed IDs/amounts, neighbour exclusion, login wall and URL checks passed')


if __name__=='__main__':selfcheck()
