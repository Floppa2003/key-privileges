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
JS = Path(__file__).with_name('ekp_public_ui.js').read_text()


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
        (OUT/'executed-ui.js').write_text(JS)
    except Exception as exc:
        value=str(exc);report['error']=value if re.fullmatch('[a-z_0-9]+',value) else type(exc).__name__
    finally:
        report['finished_at']=now();save();(OUT/'executed.py').write_bytes(Path(__file__).read_bytes())


if __name__=='__main__':main()
