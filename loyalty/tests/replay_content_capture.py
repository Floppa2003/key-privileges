"""Offline end-to-end replay of captured public pages; never publishes or fetches."""
from __future__ import annotations
import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
sys.path.insert(0, str(Path(__file__).parents[1]))
import flystation_source as fly
import mantera_source as mantera
import tsvetnoy_source as tsvetnoy
from normalized import validate_offer


async def replay(root: Path) -> dict:
    report=json.loads((root/'report.json').read_text())
    now=report['observed_at'];pages={p['id']:p for p in report['pages']}
    for name in ('flystation','mantera','tsvetnoy'):
        row=pages[name]
        if row['status']!='captured':raise ValueError('source_not_captured:'+name)
        if hashlib.sha256((root/(name+'.html')).read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('capture_hash_mismatch:'+name)
    if hashlib.sha256((root/'tsvetnoy.pdf').read_bytes()).hexdigest()!=pages['tsvetnoy']['pdf_sha256']:
        raise ValueError('pdf_capture_hash_mismatch')
    class Client:
        deadline=float('inf')
        def __init__(self, name):
            self.name=name
            self.page=AsyncMock()
            self.page.content.return_value=(root/(name+'.html')).read_text()
            self.page.locator=MagicMock()
            self.page.locator.return_value.first.wait_for=AsyncMock()
        async def read(self, url, **kwargs):
            if url!=pages[self.name]['url']:raise ValueError('unexpected_replay_url')
            return (root/(self.name+'.html')).read_text()
        async def json(self, url):
            if url!='https://tsvetnoy.com/api/v1/documents':raise ValueError('unexpected_replay_api')
            return json.loads((root/'documents.json').read_text())
        async def read_pdf(self, url):
            doc=tsvetnoy.current_document(json.loads((root/'documents.json').read_text()))
            if url!='https://tsvetnoy.com/pdf/'+doc['key']:raise ValueError('unexpected_replay_pdf')
            return (root/'tsvetnoy.pdf').read_bytes()
    results={};records={}
    for name,module in (('flystation',fly),('tsvetnoy',tsvetnoy)):
        source_report={'source_id':module.SOURCE,'errors':[]}
        rows=await module.collect(Client(name),{'id':module.SOURCE,'url':pages[name]['url']},source_report,now,500)
        if source_report['errors'] or not source_report['native_inventory_v1']['complete']:
            raise ValueError('incomplete_replay:'+name)
        records[name]=rows
        results[name]={'records':len(rows),'inventory':len(source_report['native_inventory_v1']['ids']),
            'excluded':len(source_report['native_inventory_v1']['excluded']),
            'evidence_only':sum(r['record_kind']=='source_observation' for r in rows),'complete_inventory':True}
    records['mantera_faq']=mantera.parse((root/'mantera.html').read_text(),now)
    results['mantera_faq']={'records':len(records['mantera_faq']),'scope':'FAQ only; independent hotel/partner pages not captured'}
    for rows in records.values():
        for row in rows:validate_offer(json.loads(json.dumps(row,sort_keys=True)))
    return {'observed_at':now,'publication_allowed':False,'results':results,'records':records}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('capture',type=Path)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    result=asyncio.run(replay(args.capture))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='records'},ensure_ascii=False))

if __name__=='__main__':main()
