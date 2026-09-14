"""Official public-channel announcements, not certified current catalogue offers.
Only configured channel archives are fetched. Outgoing links are evidence, never
requests or instructions. One source post remains one record across later edits.
"""
from __future__ import annotations
import asyncio
import html as html_module
import json
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlsplit, parse_qs
from bs4 import BeautifulSoup
from normalized import canonical_url, make_offer

CHANNELS = {'ekp_announcements':'ekpcard', 'rzd_announcements':'fpcrussia',
            'mir_announcements':'promomir', 'bspb_announcements':'mybspb'}
LOYALTY = re.compile(r'\bЕКП\b|един\w*\s+карт\w*\s+петербуржц', re.I)
RZD = re.compile(r'РЖД[\s«»"-]*Бонус', re.I)
NUMERIC_BENEFIT = re.compile(r'\d\s*%|промокод|скидк\w*\s+(?:до\s+)?\d|\d+\s+(?:бонус\w*|балл\w*|мил[ьяиюе]\w*)', re.I)
CONTEST = re.compile(r'розыгрыш|разыгра\w*|победител\w*\s+конкурс', re.I)
GENERIC_RZD_FOOTER = re.compile(r'(?:Обязательно\s+)?(?:Укажите|не забывайте указывать)\s+при покупке билета[^.!?\n]*(?:РЖД[\s«»"-]*Бонус)[^.!?\n]*', re.I)


def checked_config(cfg):
    if CHANNELS.get(cfg.get('id')) != cfg.get('channel') or cfg.get('url') != f"https://t.me/s/{cfg.get('channel')}":
        raise ValueError('unconfigured_public_channel')
    if type(cfg.get('lookback_days',180)) is not int or not 1 <= cfg.get('lookback_days',180) <= 366:
        raise ValueError('invalid_announcement_window')
    if type(cfg.get('max_pages',60)) is not int or not 1 <= cfg.get('max_pages',60) <= 100:
        raise ValueError('invalid_announcement_page_bound')


def relevant(body, cfg, cards):
    if CONTEST.search(body):
        return False
    if cfg['id'] == 'rzd_announcements':
        without_footer = GENERIC_RZD_FOOTER.sub('', body)
        return bool(RZD.search(without_footer) and NUMERIC_BENEFIT.search(without_footer))
    if cfg['id'] in ('mir_announcements','bspb_announcements'):
        # A bank's interest rate or a channel's audience statistics is not a perk.
        reward=re.search(r'скидк|к[еэ]шб[еэ]к|промокод|подар',body,re.I)
        context=(cfg['id']=='mir_announcements' or bool(re.search(r'ЯРКО|ЕКП|лояльност|един\w*\s+карт',body,re.I)))
        return bool(context and reward and (cards or re.search(r'\d\s*%|\d+\s+(?:бонус\w*|балл\w*|мил[ьяиюе]\w*)',body,re.I))
                    and not re.search(r'опрос|голосован|мониторинг\s+активност',body,re.I))
    if cards:
        return True
    if re.search(r'опрос|голосован|мониторинг\s+активност',body,re.I):
        return False
    role=re.search(r'скидк|к[еэ]шб[еэ]к|промокод|балл|подар',body,re.I)
    return bool(LOYALTY.search(body) and role and NUMERIC_BENEFIT.search(body))


def parse_feed(html: str, cfg: dict, observed_at: str) -> dict:
    checked_config(cfg)
    now = datetime.fromisoformat(observed_at)
    if now.tzinfo is None:
        raise ValueError('observation_requires_timezone')
    cutoff = now - timedelta(days=cfg.get('lookback_days',180))
    soup = BeautifulSoup(html,'html.parser')
    result = {'records':[], 'errors':[], 'next_url':None, 'scanned':0,
              'reached_cutoff':False, 'oldest_publication':None, 'newest_publication':None}
    dated, ids, seen = [], [], set()
    for node in soup.select('.tgme_widget_message[data-post]'):
        native = node.get('data-post','')
        if not re.fullmatch(re.escape(cfg['channel'])+r'/[0-9]+', native) or native in seen:
            continue
        seen.add(native); ids.append(int(native.split('/')[-1])); result['scanned'] += 1
        own_text=[n for n in node.select('.tgme_widget_message_text')
                  if 'js-message_reply_text' not in n.get('class',[])
                  and not n.find_parent(class_='tgme_widget_message_reply')
                  and not n.find_parent(class_='tgme_widget_message_link_preview')]
        if len(own_text)>1:
            result['errors'].append({'phase':'post','native_id':native,'reason':'ambiguous_message_text'})
        content=own_text[0] if len(own_text)==1 else None
        if content is None:
            continue
        for br in content.select('br'):
            br.replace_with('\n')
        body = content.get_text('',strip=False).strip()
        outgoing, cards = [], []
        for a in content.select('a[href]'):
            try:
                url = canonical_url(html_module.unescape(a['href']))
            except (TypeError, ValueError):
                continue
            link={'label':a.get_text(' ',strip=True), 'url':url}
            if link not in outgoing:
                outgoing.append(link)
            u=urlsplit(url)
            if u.hostname in ('ekp.spb.ru','www.ekp.spb.ru') and re.fullmatch(r'/capabilities/loyalty/tiles/[0-9]+/?',u.path):
                cards.append(link)
            elif cfg['id']=='mir_announcements' and u.hostname in ('vamprivet.ru','privetmir.ru'):
                cards.append(link)
            elif u.hostname in ('rzd-bonus.ru','www.rzd-bonus.ru'):
                cards.append(link)
        clock=node.select_one('.tgme_widget_message_date time[datetime]')
        try:
            published=datetime.fromisoformat(clock['datetime'].replace('Z','+00:00'))
            if published.tzinfo is None:
                raise ValueError('missing_timezone')
        except (TypeError, KeyError, ValueError):
            if relevant(body,cfg,cards):
                result['errors'].append({'phase':'post','native_id':native,'reason':'missing_publication_time'})
            continue
        dated.append(published)
        if published < cutoff or published > now or node.select_one('.tgme_widget_message_forwarded_from'):
            continue
        if not relevant(body,cfg,cards):
            continue
        # A collection may mention several partners with different conditions. Do
        # not assign all its rates to any single brand or infer names from URLs.
        warnings=['announcement_not_full_partner_rules','eligibility_and_current_offer_not_verified','outgoing_links_not_fetched']
        detail={'channel':cfg['channel'], 'published_at':published.isoformat(),
                'feed_url':cfg['url'], 'outgoing_links':outgoing, 'linked_cards':cards,
                'scope':'one_public_announcement', 'validity_extraction':'not_inferred_from_publication_date'}
        result['records'].append(make_offer(cfg['id'],native,cfg['name'],None,body,
            'https://t.me/'+native,observed_at,title=next((line.strip() for line in body.split('\n') if len(re.findall(r'[A-Za-zА-Яа-яЁё]',line))>=5),body)[:300],
            record_kind='announcement',link_kind='source_post',locator='data-post='+native,
            source_status='announced_unverified',details=detail,warnings=warnings))
    if not ids:
        result['errors'].append({'phase':'pagination','reason':'no_public_messages_in_response'})
    if dated:
        result['oldest_publication']=min(dated).isoformat()
        result['newest_publication']=max(dated).isoformat()
        result['reached_cutoff']=max(dated)<cutoff
    more=soup.select_one('a.tme_messages_more[data-before]')
    if more is not None:
        u=urlsplit(urljoin(cfg['url'],more.get('href','')))
        query=parse_qs(u.query)
        before=query.get('before',[])
        if (u.scheme=='https' and u.netloc=='t.me' and u.path==f"/s/{cfg['channel']}"
            and set(query)=={'before'} and len(before)==1 and before[0].isdigit()
            and before[0]==more.get('data-before') and ids and 0<int(before[0])<=min(ids)):
            result['next_url']=f"https://t.me/s/{cfg['channel']}?before={before[0]}"
        else:
            result['errors'].append({'phase':'pagination','reason':'untrusted_or_non_decreasing_cursor'})
    return result


async def collect_announcements(client,cfg,report,now,limit):
    checked_config(cfg)
    records,seen,visited={},set(),set()
    current=cfg['url'];scanned=0;pages=0;oldest=None;newest=None;stop='page_limit'
    for _ in range(cfg.get('max_pages',60)):
        if current in visited:
            report['errors'].append({'phase':'pagination','reason':'repeated_page_url'});stop='pagination_error';break
        visited.add(current)
        try:
            # Public server-rendered archive; no interactive login or API replay.
            parsed=parse_feed(await client.read(current),cfg,now)
        except Exception as exc:
            report['errors'].append({'phase':'feed','reason':str(exc)[:180] if isinstance(exc,RuntimeError) else type(exc).__name__})
            stop='read_error';break
        pages+=1;scanned+=parsed['scanned'];report['errors'].extend(parsed['errors'])
        if parsed['oldest_publication']:oldest=min(oldest or parsed['oldest_publication'],parsed['oldest_publication'])
        if parsed['newest_publication']:newest=max(newest or parsed['newest_publication'],parsed['newest_publication'])
        for r in parsed['records']:
            seen.add(r['id'])
            if len(records)<limit:records.setdefault(r['id'],r)
        if len(records)>=limit:stop='record_limit';break
        if parsed['reached_cutoff']:stop='lookback_boundary_reached';break
        if any(e['phase']=='pagination' for e in parsed['errors']):stop='pagination_error';break
        if not parsed['next_url']:stop='archive_end';break
        current=parsed['next_url']
        await asyncio.sleep(max(0.5,getattr(client,'request_interval',0.25)))
    report['discovered']=len(seen)
    report['coverage']=json.dumps({'kind':'public_announcement_window_not_catalog',
        'channel':cfg['channel'],'lookback_days':cfg.get('lookback_days',180),'pages':pages,
        'posts_scanned':scanned,'oldest_publication':oldest,'newest_publication':newest,
        'stop_reason':stop,'record_limit':limit,'linked_details_checked':False},ensure_ascii=False)
    return list(records.values())
