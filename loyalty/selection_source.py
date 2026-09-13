"""Public Selection preview cards only; never enter the authenticated catalogue."""
from __future__ import annotations
import hashlib
import json
import re
from datetime import date
from bs4 import BeautifulSoup
from normalized import content_hash, make_offer, text
from public_transport import PublicSource
from read_budget import within_source_budget
from t2_regions import regional_comparison

REGIONS = {
    'msk': {'region': 'Москва и область', 'source_url': 'https://msk.t2.ru/bolshe/selection'},
    'spb': {'region': 'Санкт-Петербург и Ленинградская область', 'source_url': 'https://spb.t2.ru/bolshe/selection'},
}
CARD = '.loyalty-short-offers-offer-card'
TITLE = CARD + '__info-title'
PARTNER = CARD + '__info-text'
MONTHS = {v:i for i,v in enumerate(('января','февраля','марта','апреля','мая','июня',
    'июля','августа','сентября','октября','ноября','декабря'),1)}


def preview_record(snapshot, region, observed_at):
    if region not in REGIONS:
        raise ValueError('unknown_selection_region')
    card = BeautifulSoup(snapshot['card_html'], 'html.parser')
    titles, names = card.select(TITLE), card.select(PARTNER)
    if len(titles) != 1 or len(names) != 1:
        raise ValueError('ambiguous_selection_card')
    title, partner = text(titles[0].get_text(' ',strip=True)), text(names[0].get_text(' ',strip=True))
    if not title or not partner:
        raise ValueError('empty_selection_identity')
    popup = BeautifulSoup(snapshot['popup_html'], 'html.parser')
    panels = popup.select('[data-element="Popup"]')
    if len(panels) != 1:
        raise ValueError('ambiguous_selection_popup')
    headers, bodies = panels[0].select('h2'), panels[0].select('.more-offer-info-popup')
    if len(headers) != 1 or len(bodies) != 1 or text(headers[0].get_text()).casefold() != title.casefold():
        raise ValueError('selection_popup_does_not_match_card')
    body = bodies[0]
    descriptions = body.select('[data-element="Text"]')
    if len(descriptions) != 1:
        raise ValueError('missing_selection_public_description')
    description = text(descriptions[0].get_text('\n',strip=True))
    if not description:
        raise ValueError('empty_selection_public_description')
    evidence = text(body.get_text('\n',strip=True))
    hints = [text(x.get_text(' ',strip=True)) for x in body.select('.more-offer-info-popup__hint')]
    ends = set()
    for hint in hints:
        match = re.fullmatch(r'Акция действует до (\d{1,2}) ([а-яё]+) (\d{4})',hint,re.I)
        if match and match[2].lower() in MONTHS:
            ends.add(date(int(match[3]), MONTHS[match[2].lower()], int(match[1])).isoformat())
    if len(ends) > 1:
        raise ValueError('contradictory_selection_expiry')
    # No native vendor offer ID is visible in these anonymous preview cards.
    # The semantic label is stable across reorder/expiry/amount edits, not a fake API ID.
    native = 'public-card:' + hashlib.sha256(partner.casefold().encode()).hexdigest()[:32]
    return make_offer('t2_selection_public', native, 'T2 Selection', partner,
        title+'\n'+description, REGIONS[region]['source_url'], observed_at,
        title=title, conditions=evidence,
        link_kind='page_block', locator=f'{CARD} partner={partner}; matching public popup',
        valid_until=next(iter(ends),None), source_status='public_preview_requires_login',
        record_kind='tier_benefit', details={
            'required_program':'T2 Selection', 'public_scope':'landing_card_and_public_popup_only',
            'identity_method':'synthetic_partner_label_not_vendor_id', 'region':REGIONS[region]['region'],
            'popup_title':text(headers[0].get_text()), 'published_hints':hints,
            'full_catalog_access':'authentication_required',
        }, warnings=['not_full_personalized_offer_rules','user_selection_status_not_verified',
                     'private_code_not_requested','listing_region_is_not_a_guarantee_of_eligibility'])


def merge_previews(regional_snapshots, observed_at):
    rows, comparisons, seen_regions = {}, {}, set()
    meta = {'method':'public_preview_not_personal_catalog','profiles':[],
            'shared_observations_merged':0,'errors':[]}
    for key,snapshots in regional_snapshots:
        if key not in REGIONS or key in seen_regions:
            raise ValueError('invalid_or_duplicate_selection_region')
        seen_regions.add(key)
        seen_ids = set()
        profile = {'key':key, 'observed_previews':len(snapshots), 'accepted':0}
        meta['profiles'].append(profile)
        for snapshot in snapshots:
            row=preview_record(snapshot,key,observed_at)
            native=row['native_id']
            if native in seen_ids:
                raise ValueError('duplicate_selection_partner_label')
            seen_ids.add(native)
            comparison=regional_comparison(row)
            if native in rows:
                if comparison!=comparisons[native]:
                    meta['errors'].append({'phase':'regional_union','region':key,
                        'native_id':native,'reason':'regional_terms_conflict'})
                    continue
                rows[native]['details']['catalog_regions'].append({'key':key,**REGIONS[key]})
                meta['shared_observations_merged']+=1
            else:
                comparisons[native]=comparison
                row['details']['catalog_regions']=[{'key':key,**REGIONS[key]}]
                rows[native]=row
            profile['accepted']+=1
    for row in rows.values():row['content_sha256']=content_hash(row)
    return list(rows.values()),meta


async def _read_previews(client, region, limit):
    root=REGIONS[region]['source_url']
    await within_source_budget(client,client.robots)
    await within_source_budget(client,lambda:client.read(root,render=True))
    cards=client.page.locator(CARD)
    await cards.first.wait_for(state='visible',timeout=8000)
    count=await cards.count()
    if not 1<=count<=30:
        raise RuntimeError('selection_preview_card_count_invalid')
    snapshots=[]
    meta={'discovered':count,'errors':[]}
    if count>limit:meta['errors'].append({'phase':'preview','reason':'record_limit','limit':limit})
    for index in range(min(count,limit)):
        try:
            async def read_popup():
                card=cards.nth(index)
                card_html=await card.evaluate('(el)=>el.outerHTML')
                await card.click(timeout=4000)
                popup=client.page.locator('[data-element="Popup"]').filter(
                    has=client.page.locator('.more-offer-info-popup'))
                await popup.wait_for(state='visible',timeout=5000)
                popup_html=await popup.evaluate('(el)=>el.outerHTML')
                value={'card_html':card_html,'popup_html':popup_html}
                # Capture only this opened popup, then close it before the next card.
                await popup.locator('[data-element="PopupClose"]').click(timeout=3000)
                await popup.wait_for(state='hidden',timeout=3000)
                return value
            snapshots.append(await within_source_budget(client,read_popup))
        except Exception as exc:
            meta['errors'].append({'phase':'preview','index':index,
                'reason':str(exc)[:180] if isinstance(exc,RuntimeError) else type(exc).__name__})
            break  # The UI state is uncertain; keep earlier evidence, no further clicks.
    return snapshots,meta


async def read_region_previews(client, region, limit):
    if region not in REGIONS:
        raise ValueError('unknown_selection_region')
    if region=='msk':
        return await _read_previews(client,region,limit)
    async with PublicSource(client.browser,REGIONS[region]['source_url']) as regional:
        regional.deadline=getattr(client,'deadline',float('inf'))
        return await _read_previews(regional,region,limit)


async def collect_selection(client,cfg,report,now,limit):
    snapshots=[]
    reads=[]
    for key in REGIONS:
        try:
            values,meta=await read_region_previews(client,key,limit)
            accepted=[]
            for index,value in enumerate(values):
                try:
                    preview_record(value,key,now)
                    accepted.append(value)
                except ValueError as exc:
                    report['errors'].append({'phase':'preview_validation','region':key,
                        'index':index,'reason':str(exc)[:180]})
            # Duplicate identities within a region remain a source-level error.
            merge_previews([(key,accepted)],now)
            snapshots.append((key,accepted));reads.append({'region':key,**meta})
            report['errors'].extend({'region':key,**e} for e in meta['errors'])
        except Exception as exc:
            report['errors'].append({'phase':'preview_region','region':key,
                'reason':str(exc)[:180] if isinstance(exc,RuntimeError) else type(exc).__name__})
    rows,meta=merge_previews(snapshots,now)
    report['errors'].extend(meta['errors'])
    report['discovered']=len(rows)
    report['region']='; '.join(REGIONS[key]['region'] for key,_ in snapshots)
    if len(rows)>limit:report['errors'].append({'phase':'preview_union','reason':'record_limit','limit':limit})
    meta.update(reads=reads, full_catalog_complete=False, private_offer_activation=False)
    report['coverage']=json.dumps(meta,ensure_ascii=False)
    return rows[:limit]
