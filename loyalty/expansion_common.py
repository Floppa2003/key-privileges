"""Small shared guards for the four reviewed public catalogue additions."""
from __future__ import annotations
import hashlib, json, re
from datetime import date
from bs4 import BeautifulSoup
from public_reward_projection import plain

SOURCES = {'x5_partners_public', 'magnit_partners_public', 'gorod_public', 'tsvetnoy_public', 'flystation_public'}
PROGRAMS = {'x5_partners_public':'X5 Клуб — партнёры',
            'magnit_partners_public':'Магнит Плюс — партнёры',
            'gorod_public':'Город / Тройка', 'tsvetnoy_public':'Цветной — программа лояльности',
            'flystation_public':'FlyStation — публичные акции'}
EXCLUSIONS = {'financial_or_acquisition_ad', 'gambling_or_lottery', 'expired_offer',
              'not_started_offer', 'no_concrete_partner_benefit', 'source_unavailable',
              'accumulation_only_no_discount', 'card_not_applicable'}
class ExcludedOffer(ValueError): pass

def compact(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip()

def sha(raw):
    return hashlib.sha256(raw.encode() if isinstance(raw,str) else raw).hexdigest()

def identity(e, source):
    if source not in SOURCES or not re.fullmatch('[a-f0-9]{64}', e.get('page_sha256','')):
        raise ValueError('expansion_evidence_identity')
    if not isinstance(e.get('native'),str) or not 1<=len(e['native'])<=500:
        raise ValueError('expansion_native_identity')

def iso(value):
    if not value: return None
    value=compact(value)
    if re.match(r'^\d{4}-\d{2}-\d{2}',value): s=value[:10]
    elif re.fullmatch(r'\d{2}\.\d{2}\.\d{4}',value):s='-'.join(reversed(value.split('.')))
    else:raise ValueError('unreviewed_source_date')
    date.fromisoformat(s);return s

def check_period(start,end,now):
    if end and end<now[:10]:raise ExcludedOffer('expired_offer')
    if start and start>now[:10]:raise ExcludedOffer('not_started_offer')

def exclusion(title):
    if re.search(r'лотере|лотерейн|казино|букмекер',title,re.I):return 'gambling_or_lottery'
    if re.search(r'Деньги на любые цели|банковск\w*\s+карт|микрозайм|\bзайм\b|\bкредит\b|кредитн\w*\s+карт|оформ\w*.{0,30}(?:кредит|карт)|образовательн\w*\s+кредит|потребительск\w*\s+кредит|\bНПФ\b|долгосрочн\w*\s+сбереж|СберКарт|детск\w*\s+карт',title,re.I):return 'financial_or_acquisition_ad'
    return None

def next_store(raw, store):
    soup=BeautifulSoup(raw,'html.parser');nodes=soup.select('script#__NEXT_DATA__')
    if len(nodes)!=1:raise ValueError('missing_next_public_state')
    value=json.loads(nodes[0].get_text())['props']['pageProps']['initialStoreState'][store]
    if not isinstance(value,dict):raise ValueError('invalid_next_public_store')
    return value

def links(node):
    return list(dict.fromkeys(a['href'] for a in BeautifulSoup(str(node),'html.parser').select('a[href]')
        if a['href'].startswith('https://')))

def reported(report, rows, inventory, excluded, **coverage):
    if len(inventory)!=len(set(inventory)) or not inventory or len(inventory)>2500:
        raise ValueError('expansion_inventory_identity')
    accepted=[r['native_id'] for r in rows]
    if len(accepted)!=len(set(accepted)) or set(accepted)&set(excluded):raise ValueError('expansion_duplicate_result')
    if not set(accepted)|set(excluded)<=set(inventory):raise ValueError('expansion_foreign_result')
    report['native_inventory_v1']={'source_id':report['source_id'], 'ids':sorted(inventory),
        'excluded':excluded, 'complete':not report['errors'] and set(accepted)|set(excluded)==set(inventory)}
    report['discovered']=len(inventory)
    report['coverage']=json.dumps({'listed':len(inventory),'accepted':len(rows),'excluded':excluded,**coverage},ensure_ascii=False)

def snapshot(report,records,observed):
    snap=report.get('native_inventory_v1')
    if snap is None:return None
    sid=report['source_id']; ids=snap.get('ids',[]);ex=snap.get('excluded',{})
    if (sid not in SOURCES or snap.get('source_id')!=sid or not isinstance(ids,list)
        or not 1<=len(ids)<=2500 or any(not isinstance(x,str) or not x for x in ids)
        or ids!=sorted(set(ids)) or not isinstance(ex,dict) or not set(ex)<=set(ids)
        or not set(ex.values())<=EXCLUSIONS):raise ValueError('expansion_snapshot_identity')
    if report['errors'] or report['status'] not in ('ok','no_normalized_records') or not snap.get('complete'):return None
    if report['observed_at']!=observed:raise ValueError('expansion_snapshot_time')
    accepted=[r['native_id'] for r in records]
    if (len(records)!=report['normalized'] or len(accepted)!=len(set(accepted)) or set(accepted)&set(ex)
        or set(accepted)|set(ex)!=set(ids) or any(r['observed_at']!=observed for r in records)):
        raise ValueError('expansion_snapshot_accounting')
    return snap

def hold_reason(row,details,snap):
    from public_reward_projection import fields
    sid=details['public_reward_source'];f=fields(sid,details['public_reward_evidence']);native=f['native']
    if row[0]!=sha(sid+'\n'+native) or row[17]!=f['url']:raise ValueError('expansion_stored_identity')
    return snap['excluded'].get(native) if native in snap['ids'] else 'not_in_complete_inventory'

def add_error(report,exc,native):
    report['errors'].append({'phase':'detail','native':native,'reason':str(exc)[:160] if isinstance(exc,(ValueError,RuntimeError)) else type(exc).__name__})
