"""Source-linked public Gorod partner/coupon inventories, preserving reward units."""
from __future__ import annotations
import json,re
from urllib.parse import urlencode
from bs4 import BeautifulSoup
from normalized import number
from public_reward_projection import plain,make_record
from expansion_common import compact,sha,identity,iso,check_period,exclusion,ExcludedOffer,reported,add_error,PROGRAMS,next_store,links

SOURCE='gorod_public';HOST='https://gorodtroika.ru';ROOT=HOST+'/bonus-plus/coupons'
CURRENCIES={'roubles':'рубли','bonuses':'бонусы «Город»','coins':'жетоны «Город»'}

def slim_partner(d):
    # Select only anonymous offer fields, not optional session/favourite/contact state.
    p=d['partnerData'];earn=d.get('partnerBonusesEarn') or {}
    return {'partner':{k:p.get(k)for k in ('id','name','categoriesAsText','specialConditions','howTo','presenceType','bubbles','rulesFile')},
        'earn':{k:earn.get(k)for k in ('hold','rulesFile','bonusValueType','bonusByLevel','bonusConditions')},
        'spend':d.get('partnerBonusesSpend')}

def source_fields(e):
    identity(e,SOURCE)
    kind=e['kind'];d=e['data'];native=e['native'];url=e['url']
    if kind=='coupon':
        if native!='coupon:'+str(d['id']) or url!=HOST+'/bonus-plus/coupons/'+str(d['id']):raise ValueError('gorod_coupon_identity')
        if d.get('available') is not True or d.get('partner',{}).get('available') is not True:raise ExcludedOffer('source_unavailable')
        if e.get('catalogue_partner_id') is not None and e['catalogue_partner_id']!=d['partner']['id']:raise ValueError('gorod_coupon_catalogue_drift')
        name=compact(d['name']);p=d['partner'];price=d['price'];currencies=price.get('currencies')
        # A full-price souvenir is not a discount merely because the shop calls it a coupon.
        if (re.match(r'Карта «Тройка» с дизайном',name) and not d.get('cashback')
            and price.get('old') is None):raise ExcludedOffer('no_concrete_partner_benefit')
        if not isinstance(currencies,list) or not set(currencies)<=set(CURRENCIES) or type(price.get('new')) not in (int,float):raise ValueError('gorod_coupon_cost')
        amount=price['new']
        if amount<0 or (amount>0 and not currencies):raise ValueError('gorod_coupon_cost_currency_missing')
        cost='Получение купона бесплатно.' if amount==0 else f'Цена купона: {amount:g}; допустимые средства оплаты: '+', '.join(CURRENCIES[x]for x in currencies)+'.'
        message=d.get('message') or {}
        cost+='\n'+plain(message.get('title',''))+' '+plain(message.get('body',''))
        dates=[iso(d.get(k)) for k in ('endAt','couponEndAt','countdown') if d.get(k)]
        # Earliest explicit end prevents sale/end-of-use disagreements extending an offer.
        end=min(dates) if dates else None
        dates_text='\n'.join(k+': '+str(d[k])for k in ('endAt','couponEndAt','countdown') if d.get(k))
        conditions=plain(d.get('terms',''));activation='\n'.join(plain(x)for x in (d.get('howToAsList')or[]))
        presentation_unknown=False
        if not activation:
            automatic=re.search(r'Бустер начинает действовать автоматически после покупки\. Дополнительно вводить его данные никуда не требуется\.',conditions)
            if automatic:activation=automatic[0]
            elif ((d.get('address')or{}).get('details') and 'Нажимая «Купить»' in conditions):
                onsite=re.search(r'Купон дает скидку[^.\n]{0,400}с доплатой на месте:[^.\n]{1,400}',compact(conditions))
                if onsite:
                    activation=onsite[0]+'\nПорядок предъявления купона на публичной карточке не раскрыт.'
                    presentation_unknown=True
        if not conditions or not activation:raise ValueError('gorod_coupon_terms_missing')
        cb=d.get('cashback') or {}
        extra='\nВознаграждение за покупку купона: '+plain(cb.get('text',''))+' '+CURRENCIES.get(cb.get('currency'),'единица не указана') if cb else ''
        address=d.get('address') or {}
        if address.get('details'):conditions+='\nАдрес: '+plain(address['details'])
        refs=links(d.get('terms',''))
        if refs:conditions+='\nПолные правила: '+'; '.join(refs)
        return dict(native=native,program=PROGRAMS[SOURCE],partner=compact(p['name']),title=name,benefit=name,
            conditions=cost.strip()+extra+'\n'+dates_text+'\n'+conditions,activation=activation,url=url,
            category=compact(p.get('subtitle')) or 'Купоны',valid_until=end,locator='couponViewStore.couponData',
            terms=[dict(kind='partner_privilege',fragment=name)],scope={'coupon_id':d['id'],'coupon_purchase_or_activation_not_performed':True},
            warnings=['coupon_price_separate_from_discount','coins_are_tokens_not_roubles']+(['coupon_presentation_method_not_disclosed']if presentation_unknown else [])+(['different_sale_and_coupon_end_dates_preserved']if len(set(dates))>1 else []))
    if kind!='partner':raise ValueError('gorod_unreviewed_record_kind')
    p=d['partner'];earn=d['earn']
    if native!='partner:'+str(p['id']) or url!=HOST+'/partners/'+str(p['id']):raise ValueError('gorod_partner_identity')
    bylevel=earn.get('bonusByLevel') or [];conds=earn.get('bonusConditions') or []
    labels={str(x['id']):compact(x['name'])for x in conds};lines=[];terms=[];level_ids=set()
    for row in bylevel:
        lv=row['level'];lid=lv['id'];label=str(lv['number'])+' — '+lv['name']
        if lid in level_ids:raise ValueError('gorod_duplicate_level')
        level_ids.add(lid);rates=row.get('conditions')
        if rates:
            if not isinstance(rates,dict) or set(rates)!=set(labels):raise ValueError('gorod_customer_conditions_mismatch')
            pairs=[(labels[k],v)for k,v in rates.items()]
        else:pairs=[('',{k:row[k]for k in ('percent','amount')if row.get(k)is not None})]
        for audience,value in pairs:
            if not value or not set(value)<= {'amount','percent'}:raise ValueError('gorod_rate_shape')
            for unit,v in value.items():
                if type(v) not in (int,float) or v<0 or (unit=='percent' and v>100):raise ValueError('gorod_rate_value')
                if v==0:continue
                line=f'Уровень {label}'+(' / '+audience if audience else '')+': '+str(number(str(v)))+('% бонусами'if unit=='percent'else' бонусов')
                lines.append(line);terms.append(dict(kind='earn_points',value=number(str(v)),unit='percent'if unit=='percent'else'points',
                    qualifier='exact',reward_unit='Gorod_bonus_not_cash',fragment=line,scope={'member_level_id':lid,'member_level':label,'purchase_condition':audience}))
    # A headline-only redemption cap is retained as such, not as a cash discount.
    spend=[b['label']for b in p.get('bubbles') or [] if b.get('type')=='spend_bonuses' and b.get('label')]
    for s in spend:
        line='Оплата накопленными бонусами: '+s;lines.append(line);terms.append(dict(kind='redeem_points',fragment=line,reward_unit='Gorod_bonus_not_cash'))
    if not lines:raise ExcludedOffer('no_concrete_partner_benefit')
    activation='\n'.join(plain(x['name'])for x in (p.get('howTo')or{}).get('items',[])if x.get('name'))
    conditions=plain(p.get('specialConditions')or'')
    hold=plain((earn.get('hold')or{}).get('description',''))
    if hold:conditions+='\n'+hold
    if spend and not d.get('spend'):conditions+='\nПодробные условия списания бонусов на этой карточке не раскрыты; сохранён только опубликованный предел.'
    if d.get('spend'):
        spend_text='\n'.join(plain(d['spend'].get(k,'')) for k in ('title','body','description','footnote'))
        if not spend_text.strip():raise ValueError('gorod_spend_conditions_unreviewed')
        conditions+='\nУсловия списания: '+spend_text
    refs=[v['url']for v in (p.get('rulesFile'),earn.get('rulesFile'))if isinstance(v,dict) and v.get('url')]
    if refs:conditions+='\nПравила партнёра: '+'; '.join(dict.fromkeys(refs))
    if not activation:raise ValueError('gorod_partner_activation_missing')
    missing_conditions=not conditions.strip()
    if missing_conditions:conditions='Дополнительные условия начисления на публичной карточке не раскрыты.'
    regions=e.get('catalogue_regions',[])
    conditions+='\nПартнёр найден в публичных каталогах регионов: '+', '.join(regions)+'. Это не проверка доступности по личному адресу.'
    warnings=['Gorod_bonus_not_money_to_bank_card','loyalty_level_uplift_not_partner_rate']+(['additional_conditions_not_disclosed']if missing_conditions else [])
    days=set(re.findall(r'(\d+)\s+(?:рабочих\s+)?дн',activation+'\n'+hold,re.I))
    if len(days)>1:warnings.append('source_conflicting_accrual_times_preserved')
    return dict(native=native,program=PROGRAMS[SOURCE],partner=compact(p['name']),title='Город → '+compact(p['name']),benefit='\n'.join(lines),
        conditions=conditions.strip(),activation=activation,url=url,category=compact(p.get('categoriesAsText'))or'Партнёры',
        locator='partnerViewStore; bonusByLevel and owned conditions',terms=terms,
        scope={'membership_required':True,'catalogue_regions_not_personal_availability':regions},warnings=warnings)

def coupon(raw,card,now):
    d=next_store(raw,'couponViewStore')['couponData']
    if int(card['id'])!=d['id'] or (card.get('partner_id')is not None and card['partner_id']!=d.get('partner',{}).get('id')):
        raise ValueError('gorod_coupon_catalogue_drift')
    # The listing deliberately uses shorter labels. Identity is the stable coupon
    # ID and its source-linked partner; keep both names instead of requiring equality.
    safe={k:d.get(k)for k in ('id','name','available','price','terms','endAt','couponEndAt','countdown','howToAsList','cashback','message','address')}
    safe['partner']={k:d['partner'].get(k) for k in ('id','name','subtitle','available')}
    e=dict(native='coupon:'+str(d['id']),kind='coupon',url=HOST+'/bonus-plus/coupons/'+str(d['id']),data=safe,catalogue_title=compact(card['name']),catalogue_partner_id=card.get('partner_id'),page_sha256=sha(raw))
    f=source_fields(e);check_period(None,f.get('valid_until'),now)
    return make_record(SOURCE,e,now)

async def collect(client,cfg,report,now,limit):
    from read_budget import within_source_budget,stops_catalog
    if cfg['id']!=SOURCE or cfg['url']!=ROOT:raise ValueError('gorod_config')
    async def read(u):return await within_source_budget(client,lambda:client.read(u))
    async def get(path,params):return await within_source_budget(client,lambda:client.json(HOST+path+'?'+urlencode(params)))
    regions=(await get('/api/system/regions',{'region_id':1}))['elements']
    if not 1<=len(regions)<=30 or len({r['id']for r in regions})!=len(regions):raise ValueError('gorod_regions_inventory')
    partners={};pages=[]
    for region in regions:
        params={'limit':30,'spend_bonuses':0,'region_id':region['id']};seen=set()
        for page in range(100):
            d=await get('/api/bonus_plus/partners',params);items=d.get('elements');more=d.get('hasMore')
            if not isinstance(items,list) or type(more)is not bool or (more and not items):raise ValueError('gorod_partners_page_shape')
            ids=[x['id']for x in items]
            if len(set(ids))!=len(ids)or set(ids)&seen:raise ValueError('gorod_repeated_partner_page')
            seen.update(ids);pages.append({'region':region['id'],'ids':ids,'hasMore':more,'sha256':sha(json.dumps(d,sort_keys=True))})
            for x in items:
                if x['id']in partners and compact(partners[x['id']]['name'])!=compact(x['name']):raise ValueError('gorod_region_name_conflict')
                p=partners.setdefault(x['id'],{'id':x['id'],'name':x['name'],'regions':[]});p['regions'].append(region['name'])
            if not more:break
            params={**params,'element_id':ids[-1]}
            if d.get('searchId'):params['search_id']=d['searchId']
        else:raise ValueError('gorod_partner_page_bound')
    if not partners or len(partners)>limit:raise ValueError('gorod_partner_limit')
    rows=[];excluded={};inventory=['partner:'+str(i)for i in partners];coupons={};pending_groups=[];stopped=False
    # Coupon groups can include promotions from partners not present in cashback.
    for region in regions:
        params={'limit':10,'region_id':region['id']};seen=set()
        for page in range(100):
            d=await get('/api/bonus_plus/coupons/partners',params);groups=d.get('elements');more=d.get('hasMore')
            if not isinstance(groups,list)or type(more)is not bool or(more and not groups):raise ValueError('gorod_coupon_group_page')
            ids=[]
            for g in groups:
                if 'id'in g:
                    if g['id']in seen:raise ValueError('gorod_duplicate_coupon_group')
                    seen.add(g['id']);ids.append(g['id'])
                data=g['coupons']
                for c in data['elements']:
                    if c['id']in coupons and compact(coupons[c['id']]['name'])!=compact(c['name']):raise ValueError('gorod_coupon_name_conflict')
                    previous=coupons.get(c['id'],{})
                    partner_id=g.get('id')
                    if previous.get('partner_id')is not None and partner_id is not None and previous['partner_id']!=partner_id:
                        raise ValueError('gorod_coupon_partner_conflict')
                    coupons[c['id']]={'id':c['id'],'name':c['name'],'partner_id':partner_id if partner_id is not None else previous.get('partner_id')}
                if data.get('hasMore') and g.get('id') not in pending_groups:pending_groups.append(g.get('id'))
            pages.append({'coupon_region':region['id'],'ids':ids,'hasMore':more,'sha256':sha(json.dumps(d,sort_keys=True))})
            if not more:break
            if not ids:raise ValueError('gorod_group_cursor_missing')
            params={**params,'element_id':ids[-1]}
        else:raise ValueError('gorod_coupon_group_bound')
    # Partner pages expose complete inner coupon lists (e.g. 10 rather than the
    # catalogue's first seven). Never call a truncated inner list complete.
    for i in pending_groups:
        if i is None:raise ValueError('gorod_inner_inventory_without_partner')
        partners.setdefault(i,{'id':i,'name':None,'regions':[]})
    for i,p in partners.items():
        native='partner:'+str(i)
        if native not in inventory:inventory.append(native)
        try:
            raw=await read(HOST+'/partners/'+str(i));store=next_store(raw,'partnerViewStore');d=slim_partner(store)
            if d['partner']['id']!=i or(p['name'] and compact(d['partner']['name'])!=compact(p['name'])):raise ValueError('gorod_partner_detail_drift')
            inner=store.get('partnerCouponsData')or{}
            if inner.get('hasMore') or inner.get('total',len(inner.get('elements',[])))!=len(inner.get('elements',[])):
                raise ValueError('gorod_inner_coupon_pagination_unresolved')
            for c in inner.get('elements',[]):
                if coupons.get(c['id'],{}).get('partner_id') not in (None,i):raise ValueError('gorod_coupon_partner_conflict')
                coupons[c['id']]={'id':c['id'],'name':c['name'],'partner_id':i}
            e=dict(native=native,kind='partner',url=HOST+'/partners/'+str(i),data=d,catalogue_regions=p['regions'],page_sha256=sha(raw))
            why=exclusion(d['partner']['name'])
            if why:raise ExcludedOffer(why)
            rows.append(make_record(SOURCE,e,now))
        except ExcludedOffer as exc:excluded[native]=str(exc)
        except Exception as exc:
            add_error(report,exc,native)
            if stops_catalog(exc):stopped=True;break
    if len(coupons)+len(partners)>min(limit,2500):raise ValueError('gorod_total_detail_limit')
    inventory.extend('coupon:'+str(i) for i in coupons)
    for i,card in coupons.items():
        if stopped:break
        native='coupon:'+str(i)
        why=exclusion(card['name'])
        if why:excluded[native]=why;continue
        try:rows.append(coupon(await read(HOST+'/bonus-plus/coupons/'+str(i)),card,now))
        except ExcludedOffer as exc:excluded[native]=str(exc)
        except Exception as exc:
            add_error(report,exc,native)
            if stops_catalog(exc):break
    reported(report,rows,inventory,excluded,regions=[{'id':r['id'],'name':r['name']}for r in regions],pages=pages,
        scope='all_public_region_partner_and_coupon_inventories;not_news_deals_personal_accounts_or_actual_redemption')
    return rows
