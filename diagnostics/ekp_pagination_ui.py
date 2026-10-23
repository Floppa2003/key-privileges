"""Public EKP UI continuation on the proven network; no fixed partner IDs.
One browser read, max125 Free credits. No account, private
session, guessed API, request replay or publication. Only visible UI controls.
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
from free_residential_comparison import ComparisonReader, ProbeError, now

ROOT = 'https://ekp.spb.ru/capabilities/loyalty/'
OUT = Path('ekp-pagination-output')
JS = r"""
const started = Date.now();
const actionsUntil = started + 38000;
const stopUntil = started + 47000;
const report = {snapshots:[],actions:[],complete:false,detailChecked:false};
const pause = ms => new Promise(r=>setTimeout(r,ms));
const allowed = u => u.origin === 'https://ekp.spb.ru' && /^\/capabilities\/loyalty\/tiles\/[0-9]+\/?$/.test(u.pathname);
const blocked = () => /access denied|captcha|доступ к сайту временно ограничен|проверка безопасности/i.test(document.title+' '+document.body.innerText.slice(0,1000));
const visible = e => !!(e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden');
function cards(){
 const out=new Map();
 for(const a of document.querySelectorAll('main a[href]')){
  const u=new URL(a.href,location.href), box=a.closest('.v-card');
  if(allowed(u)&&box&&!out.has(u.href)) out.set(u.href,{url:u.href,title:box.querySelector('.v-card-title')?.innerText||'',login:box.innerText.includes('Требуется авторизация')});
 }
 return [...out.values()];
}
function snapshot(label){
 const main=document.querySelector('main');
 if(!main) throw new Error('main_missing');
 const clone=main.cloneNode(true);
 for(const e of clone.querySelectorAll('script,style,noscript,form,input,textarea,iframe,[hidden],[aria-hidden="true"]'))e.remove();
 for(const e of clone.querySelectorAll('*')){
  for(const a of [...e.attributes])if(!['id','class','href','title','role'].includes(a.name))e.removeAttribute(a.name);
  if(e.hasAttribute('href')){
   try {const u=new URL(e.getAttribute('href'),location.href);if(u.protocol!=='https:'||u.username||u.password)e.removeAttribute('href');else{u.search='';u.hash='';e.setAttribute('href',u.href);}}
   catch{e.removeAttribute('href');}
  }
 }
 if(clone.outerHTML.length>4000000)throw new Error('snapshot_limit');
 report.snapshots.push({label,url:location.origin+location.pathname,observedAt:new Date().toISOString(),cards:cards(),html:clone.outerHTML});
}
try{
 while(!cards().length && Date.now()<Math.min(actionsUntil,started+12000)&&!blocked())await pause(500);
 if(blocked())throw new Error('restriction_document');
 if(!cards().length)throw new Error('cards_not_ready');
 snapshot('initial');
 const size=[...document.querySelectorAll('main button')].filter(b=>b.innerText.trim()==='120'&&visible(b)&&!b.disabled);
 if(size.length===1){
  const before=cards().length;size[0].click();await pause(1100);
  const end=Math.min(actionsUntil,Date.now()+5000);
  while(cards().length<=before&&Date.now()<end&&!blocked())await pause(300);
  report.actions.push({action:'visible_page_size_120',before,after:cards().length});
 }
 for(let i=0;i<40&&Date.now()<actionsUntil;i++){
  if(blocked())throw new Error('restriction_document');
  const more=[...document.querySelectorAll('main button')].filter(b=>b.innerText.trim()==='Показать еще'&&visible(b)&&!b.disabled);
  if(more.length===0){report.complete=true;break;}
  if(more.length!==1)throw new Error('ambiguous_load_more');
  const before=cards();if(before.length>1800)throw new Error('card_bound');
  more[0].click();await pause(1100);
  const end=Math.min(actionsUntil,Date.now()+5000);
  while(cards().length<=before.length&&Date.now()<end&&!blocked())await pause(300);
  const after=cards(), urls=new Set(after.map(c=>c.url));
  if(before.some(c=>!urls.has(c.url)))throw new Error('previous_cards_lost');
  report.actions.push({action:'visible_load_more',before:before.length,after:after.length});
  if(after.length<=before.length)throw new Error('load_more_no_growth');
 }
 snapshot('expanded');
 const selected=cards().find(c=>!c.login&&c.title);
 if(selected&&Date.now()<stopUntil-3000){
  report.selected=selected;
  const link=[...document.querySelectorAll('main a[href]')].find(a=>a.href===selected.url&&visible(a));
  if(link){
   await pause(1100);link.click();
   while(Date.now()<stopUntil){
    await pause(400);if(blocked())throw new Error('restriction_document');
    const m=document.querySelector('main');
    if(location.origin+location.pathname===selected.url&&m&&m.innerText.length>300&&!cards().length){report.detailChecked=true;break;}
   }
   snapshot('selected_detail');
  }
 }
}catch(e){report.error=['main_missing','snapshot_limit','restriction_document','cards_not_ready','ambiguous_load_more','card_bound','previous_cards_lost','load_more_no_growth'].includes(e.message)?e.message:e.name;}
report.finishedAt=new Date().toISOString();
report.finalUrl=location.origin+location.pathname;
const pre=document.createElement('pre');pre.id='loyalty-public-ui-evidence';pre.textContent=JSON.stringify(report);
document.body.replaceChildren(pre);
"""


class UIReader(ComparisonReader):
    def _request(self, endpoint, params):
        if endpoint=='general' and params.get('browser')=='true':
            params={**params,'js_snippet':base64.b64encode(JS.encode()).decode()}
        return super()._request(endpoint,params)


def main():
    OUT.mkdir(exist_ok=True)
    report={'run_id':os.getenv('GITHUB_RUN_ID'),'commit':os.getenv('GITHUB_SHA'),'started_at':now(),
            'publication':False,'source_account_session':False,'max_reserved_credits':125,'root':ROOT}
    reader=None
    def save():
        if reader:report.update(reserved_credits=reader.reserved,requests=reader.calls,known_cost_headers=reader.known_charged_credits)
        (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    save()
    try:
        reader=UIReader(os.environ.get('SCRAPINGANT_API_KEY',''),[{'url':ROOT}],max_credits=125,max_requests=1)
        reader.preflight();report['free_plan_confirmed']=True
        time.sleep(1.1);save()
        status,raw,_=reader.read(ROOT,browser=True);report['initial_document_status']=status
        if status!=200:raise ProbeError('origin_document_not_ok')
        soup=BeautifulSoup(raw,'html.parser');node=soup.select_one('#loyalty-public-ui-evidence')
        if node is None:raise ProbeError('ui_evidence_missing')
        ui=json.loads(node.get_text());report['ui']={k:v for k,v in ui.items() if k!='snapshots'}
        report['snapshots']=[]
        for snap in ui.get('snapshots',[]):
            label=snap['label']
            if label not in ('initial','expanded','selected_detail'):raise ProbeError('unknown_snapshot')
            html=snap.pop('html');data=html.encode();snap['sha256']=hashlib.sha256(data).hexdigest();snap['file']=label+'.html'
            (OUT/snap['file']).write_bytes(data);report['snapshots'].append(snap)
        report['detail_status_not_independently_verified']=True
    except Exception as exc:
        value=str(exc);report['error']=value if re.fullmatch('[a-z_0-9]+',value) else type(exc).__name__
    finally:
        report['finished_at']=now();save();(OUT/'executed.py').write_bytes(Path(__file__).read_bytes())


if __name__=='__main__':main()
