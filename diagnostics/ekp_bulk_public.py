"""One bounded Free-credit read to test client-side EKP detail throughput.
No publisher, source login, private data, API replay or scheduled job.
"""
from __future__ import annotations
import base64, hashlib, json, os, re, sys, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'loyalty'))
from bs4 import BeautifulSoup
from free_access_probe import FreeReader, ProbeError, free_plan, now
from ekp_owned_terms import extract
from ekp_inline_batch import namespace_allowed
from ekp_detail_probe import card_url,index_url
ROOT='https://ekp.spb.ru/capabilities/loyalty/'
POLICY='https://ekp.spb.ru/robots.txt'
OUT=Path('ekp-bulk-output')
CONFIG={'shards':2,'shard':0,'maxDetails':600}
JS=Path(__file__).with_suffix('.js').read_text().replace('__EKP_CONFIG__',json.dumps(CONFIG))

def main():
    from public_transport import robots_document, check_response
    from protego import Protego
    OUT.mkdir(exist_ok=True);reader=None
    report={'run_id':os.getenv('GITHUB_RUN_ID'),'attempt':os.getenv('GITHUB_RUN_ATTEMPT'),
        'commit':os.getenv('GITHUB_SHA'),'started_at':now(),'publication':False,'details':[],'errors':[]}
    def save():
        if reader:report.update(requests=reader.calls,reserved=reader.reserved,charged=reader.known_charged_credits)
        (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    try:
        reader=FreeReader(os.environ.get('SCRAPINGANT_API_KEY',''),[{'url':ROOT}],max_credits=150,max_requests=2)
        payload,_=reader._request('usage',{});left=free_plan(payload)
        report['opening_balance']={'remaining':left,'total':payload['plan_total_credits'],'plan':'Free','observed_at':now()}
        if left<440:raise ProbeError('preserve_daily_reserve')
        def read(url,js=None):
            if reader.halted or url not in reader.allowed or reader.calls>=2:raise ProbeError('request_not_allowed')
            cost=125 if js else 25
            if reader.reserved+cost>150:raise ProbeError('budget_reached')
            reader.calls+=1;reader.reserved+=cost;save()
            params={'url':url,'browser':'true' if js else 'false','proxy_type':'residential','proxy_country':'RU','timeout':'60'}
            if js:params.update(js_snippet=base64.b64encode(js.encode()).decode(),block_resource=['image','media','font'])
            raw,meta=reader._request('general',params)
            c=str(meta.get('Ant-credits-cost',''));s=str(meta.get('Ant-page-status-code',''))
            if not c.isdigit() or int(c)>cost or not re.fullmatch(r'[1-5]\d{2}',s):reader.halted=True;raise ProbeError('cost_or_status_invalid')
            reader.known_charged_credits+=int(c)
            if s!='200' or meta.get('ant-original-header-retry-after'):raise ProbeError('source_refusal')
            check_response(200,raw);return raw
        raw=read(POLICY);rules,state=robots_document(200,raw);namespace_allowed(rules);policy=Protego.parse(rules)
        if not policy.can_fetch(ROOT,'LoyaltyCatalogResearchBot'):raise ProbeError('robots_disallow')
        if policy.crawl_delay('LoyaltyCatalogResearchBot') or policy.request_rate('LoyaltyCatalogResearchBot'):raise ProbeError('policy_requires_paced_reader')
        (OUT/'robots.txt').write_text(rules);report['policy']={'state':state,'sha256':hashlib.sha256(raw.encode()).hexdigest()};time.sleep(1.1)
        raw=read(ROOT,JS);node=BeautifulSoup(raw,'html.parser').select_one('#loyalty-bulk-evidence')
        if node is None:raise ProbeError('marker_missing')
        result=json.loads(node.get_text());report['ui']={k:v for k,v in result.items() if k not in ('inventory','details')}
        index_url(result['catalogueUrl'])
        inventory=result['inventory'];by_url={card_url(r['url']):r for r in inventory}
        if not 1<=len(by_url)==len(inventory)<=1800:raise ProbeError('catalogue_inventory_invalid')
        (OUT/'inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2))
        seen=set()
        for entry in result.get('details',[]):
            url=card_url(entry['url'])
            if url in seen or url not in by_url or entry['title']!=by_url[url]['title'] or entry['finalUrl']!=url:raise ProbeError('detail_identity_invalid')
            seen.add(url)
            if not policy.can_fetch(url,'LoyaltyCatalogResearchBot'):raise ProbeError('detail_disallowed')
            doc=BeautifulSoup(entry['html'],'html.parser')
            if doc.select('script,style,iframe,form,input,textarea,button'):raise ProbeError('interactive_data')
            ident=url.split('?')[0].rstrip('/').split('/')[-1]
            if len(doc.find_all(id=re.compile(r'^partner\.\d+$')))!=1:raise ProbeError('owner_not_unique')
            data=entry['html'].encode();filename='partner-'+ident+'.html';(OUT/filename).write_bytes(data)
            item={k:v for k,v in entry.items() if k!='html'}|{'file':filename,'sha256':hashlib.sha256(data).hexdigest()}
            try:item['terms']=extract(entry['html'],url,entry['title'])
            except ValueError as exc:item['parse_error']=str(exc)
            report['details'].append(item)
        report['inventory_count']=len(inventory);report['accepted_detail_documents']=len(seen)
    except Exception as exc:
        code=str(exc);report['error']=code if re.fullmatch('[a-z_0-9]{1,100}',code) else type(exc).__name__
    finally:
        if reader and not reader.halted:
            try:
                payload,_=reader._request('usage',{});left=free_plan(payload)
                report['closing_balance']={'remaining':left,'total':payload['plan_total_credits'],'plan':'Free','observed_at':now()}
            except Exception:report['balance_readback']='unavailable'
        report['finished_at']=now();save()
        (OUT/'executed.py').write_bytes(Path(__file__).read_bytes());(OUT/'executed.js').write_text(JS)
        print(json.dumps({'details':len(report['details']),'error':report.get('error'),'published':False}))

if __name__=='__main__':main()
