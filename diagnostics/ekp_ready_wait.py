"""One public EKP readiness test after the alternate route returned an empty app.
No API replay, interaction, account, publication or retry. Reuses the reviewed
Free-plan residential comparison budget (one policy + one root, 150 credits).
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
import re
import time
from pathlib import Path
from bs4 import BeautifulSoup
from free_residential_comparison import ComparisonReader, ProbeError, sanitized_page, now

ROOT = 'https://ekp.spb.ru/capabilities/loyalty/'
OUT = Path('ekp-ready-wait-output')
JS = r"""
const until = Date.now() + 45000;
const checkpoints = [];
let restricted = false;
function cards() {
  return [...new Set([...document.querySelectorAll('main a[href]')].map(a => {
    const u = new URL(a.href, location.href);
    return u.origin === location.origin && /^\/capabilities\/loyalty\/tiles\/[0-9]+\/?$/.test(u.pathname) ? u.origin+u.pathname : null;
  }).filter(Boolean))];
}
while (Date.now() < until) {
  const body = document.body.innerText;
  restricted = /access denied|captcha|доступ к сайту временно ограничен|проверка безопасности/i.test(document.title+' '+body.slice(0,1000));
  const found = cards();
  if (checkpoints.length < 46) checkpoints.push({left:Math.round((until-Date.now())/1000),cards:found.length,appChars:(document.querySelector('#app')?.textContent||'').length});
  if (found.length || restricted) break;
  await new Promise(r => setTimeout(r,1000));
}
document.documentElement.setAttribute('data-loyalty-probe-location',location.href);
const report = document.createElement('pre');
report.id = 'loyalty-readiness-observation';
report.textContent = JSON.stringify({restricted,checkpoints,cardUrls:cards(),readyState:document.readyState,
  scripts:[...document.scripts].map(s=>{try { const u=new URL(s.src,location.href);return u.origin===location.origin?u.pathname:null;}catch{return null;}}).filter(Boolean).slice(0,30),
  resources:performance.getEntriesByType('resource').filter(e=>['script','fetch','xmlhttprequest'].includes(e.initiatorType)).map(e=>{try {const u=new URL(e.name);return u.origin===location.origin?{path:u.pathname,type:e.initiatorType,duration:Math.round(e.duration)}:null;}catch{return null;}}).filter(Boolean).slice(0,80)});
document.body.appendChild(report);
"""


class ReadinessReader(ComparisonReader):
    def _request(self, endpoint, params):
        if endpoint == 'general' and params.get('browser') == 'true':
            params = {**params, 'js_snippet': base64.b64encode(JS.encode()).decode()}
        return super()._request(endpoint, params)


def main():
    from public_transport import robots_document, check_response
    from protego import Protego
    OUT.mkdir(exist_ok=True)
    report = {'run_id':os.getenv('GITHUB_RUN_ID'),'commit':os.getenv('GITHUB_SHA'),'started_at':now(),
              'publication':False,'account_sessions':False,'target_url':ROOT,'max_reserved_credits':150}
    reader = None
    def save():
        if reader: report.update(reserved_credits=reader.reserved,requests=reader.calls,known_cost_headers=reader.known_charged_credits)
        (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    save()
    try:
        reader = ReadinessReader(os.environ.get('SCRAPINGANT_API_KEY',''),[{'url':ROOT}],max_credits=150,max_requests=2)
        reader.preflight(); report['free_plan_confirmed']=True
        status,raw,_=reader.read('https://ekp.spb.ru/robots.txt',browser=False)
        rules,state=robots_document(status,raw);report['policy']={'origin_status':status,'state':state,'sha256':hashlib.sha256(raw.encode()).hexdigest()}
        policy=Protego.parse(rules);rate=policy.request_rate('LoyaltyCatalogResearchBot')
        delay=max(1,policy.crawl_delay('LoyaltyCatalogResearchBot') or 0,rate.seconds/rate.requests if rate else 0)
        if delay>30:raise ProbeError('policy_delay_exceeds_budget')
        if not policy.can_fetch(ROOT,'LoyaltyCatalogResearchBot'):raise ProbeError('robots_disallow')
        time.sleep(delay);save()
        status,raw,_=reader.read(ROOT,browser=True);report['origin_status']=status
        check_response(status,raw)
        soup=BeautifulSoup(raw,'html.parser');observation=soup.select_one('#loyalty-readiness-observation')
        if observation is None:raise ProbeError('readiness_script_not_observed')
        report['readiness']=json.loads(observation.get_text());observation.decompose()
        clean,meta=sanitized_page(str(soup),ROOT);report.update(meta)
        report['source_dom_sha256']=hashlib.sha256(clean.encode()).hexdigest()
        report['status']='cards_loaded_requires_review' if report['readiness']['cardUrls'] else 'application_not_ready_after_wait'
        (OUT/'ekp.html').write_text(clean)
    except Exception as exc:
        value=str(exc);report['error']=value if re.fullmatch('[a-z_0-9]+',value) else type(exc).__name__
    finally:
        report['finished_at']=now();save()
        (OUT/'executed.py').write_bytes(Path(__file__).read_bytes())


if __name__=='__main__':main()"}