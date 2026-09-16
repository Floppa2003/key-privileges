"""One-context API comparison, max150 Free credits, no Google publication."""
from __future__ import annotations
import base64,hashlib,json,os,re,sys,time
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'loyalty'))
from free_access_probe import FreeReader,ProbeError,free_plan,now
from ekp_catalog import ROOT,API,POLICY,query,page,public_row,make_record
from ekp_detail_probe import index_url
OUT=Path('ekp-session-output')


def main():
    from public_transport import robots_document,check_response
    from protego import Protego
    OUT.mkdir(exist_ok=True);r=None;rows=[];seen=set()
    report={'run_id':os.environ['GITHUB_RUN_ID']+':'+os.environ['GITHUB_RUN_ATTEMPT'],'commit':os.environ['GITHUB_SHA'],
        'started_at':now(),'publication':False,'source_account_used':False,'pages':[],'errors':[]}
    def save():
        if r:report.update(requests=r.calls,reserved_credits=r.reserved,known_charged_credits=r.known_charged_credits)
        report['accepted_records']=len(rows)
        (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    try:
        r=FreeReader(os.environ.get('SCRAPINGANT_API_KEY',''),[{'url':ROOT}],max_credits=150,max_requests=2)
        usage,_=r._request('usage',{});report['opening_balance']=free_plan(usage)
        if report['opening_balance']<1000:raise ProbeError('preserve_free_reserve')
        def read(url,browser=False):
            cost=125 if browser else 25
            if r.halted or r.calls>=2 or r.reserved+cost>150 or url not in (ROOT,POLICY):raise ProbeError('request_limit')
            r.calls+=1;r.reserved+=cost;save()
            params={'url':url,'browser':str(browser).lower(),'proxy_country':'RU','proxy_type':'residential','timeout':'60'}
            if browser:params.update(js_snippet=base64.b64encode(Path(__file__).with_suffix('.js').read_bytes()).decode(),block_resource=['image','media','font'])
            raw,meta=r._request('general',params)
            c=str(meta.get('Ant-credits-cost',''));s=str(meta.get('Ant-page-status-code',''))
            if not c.isdigit() or int(c)>cost:raise ProbeError('cost_unconfirmed')
            r.known_charged_credits+=int(c)
            if s!='200' or meta.get('ant-original-header-retry-after'):raise ProbeError('origin_refusal')
            check_response(200,raw);return raw
        raw=read(POLICY);rules,_=robots_document(200,raw);policy=Protego.parse(rules)
        if not all(policy.can_fetch(u,'LoyaltyCatalogResearchBot') for u in (ROOT,API)):raise ProbeError('robots_disallow')
        if policy.crawl_delay('LoyaltyCatalogResearchBot') or policy.request_rate('LoyaltyCatalogResearchBot'):raise ProbeError('pacing_rule_requires_review')
        (OUT/'robots.txt').write_text(rules);time.sleep(1.1)
        raw=read(ROOT,True);node=BeautifulSoup(raw,'html.parser').select_one('#loyalty-session-api')
        if node is None:raise ProbeError('session_marker_missing')
        obj=json.loads(node.get_text());index_url(obj['initialUrl']);index_url(obj['finalUrl'])
        report['session']={k:v for k,v in obj.items() if k!='pages'}
        total=None;offset=0
        for src in obj['pages']:
            if src['request']!=query(offset) or src['status']!=200 or src['url']!=API or not re.fullmatch('[a-f0-9]{64}',src['sourceSha']):raise ProbeError('page_identity_invalid')
            ids=page(src,offset)
            if total is None:total=src['total']
            if src['total']!=total or seen.intersection(ids) or len(ids)!=min(120,total-offset):raise ProbeError('page_count_changed')
            public=[]
            for original in src['partners']:
                x=public_row(original);row=make_record(x,report['started_at'],request=src['request'],response_sha=src['sourceSha'],observed_total=total,completed_at=src['completedAt'])
                public.append(x);rows.append(row)
            seen.update(ids);file=f'page-{offset:04d}.json';(OUT/file).write_text(json.dumps({'total':total,'offset':offset,'partners':public},ensure_ascii=False,indent=2))
            report['pages'].append({'file':file,'request':src['request'],'source_count':len(ids),'accepted':len(public),'origin_status':200,
                'completed_at':src['completedAt'],'source_response_sha256':src['sourceSha'],'public_projection_sha256':hashlib.sha256((OUT/file).read_bytes()).hexdigest()})
            offset+=len(ids);save()
        report['reported_total']=total;report['complete']=bool(obj.get('complete')) and len(seen)==total and not obj['errors']
    except Exception as exc:
        text=str(exc);report['errors'].append(text if re.fullmatch('[a-z_0-9]{1,100}',text) else type(exc).__name__)
    finally:
        if r and not r.halted:
            try:usage,_=r._request('usage',{});report['closing_balance']=free_plan(usage)
            except Exception:pass
        report['finished_at']=now();save()
        (OUT/'records.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
        (OUT/'executed.py').write_bytes(Path(__file__).read_bytes());(OUT/'executed.js').write_bytes(Path(__file__).with_suffix('.js').read_bytes())
        print(json.dumps({'records':len(rows),'complete':report.get('complete',False),'published':False}))

if __name__=='__main__':main()
