"""Bounded acceptance test, separate from production discovery and scheduling.

Case names/expected values belong only to this regression. The live input is
acquired by the production capture, not made from expected answers.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[1]/'loyalty')]
import merchant_queue as q
import merchant_extract as m
from playwright.async_api import async_playwright

CASES={'Memo':20,'Hide':20,'El Copitas Bar':10,'Po’mestam':10}
ROOT=Path('evidence-acceptance')

async def prepare(catalog_path):
    ROOT.mkdir(exist_ok=True);out=ROOT/'captures';out.mkdir()
    catalog=json.loads(catalog_path.read_text())
    targets=[t for t in q.discover_targets(catalog,{}, {})
             if t['source_id']=='konsierge_public' and t['partner'] in CASES]
    assert {t['partner'] for t in targets}==set(CASES)
    m.save(ROOT/'targets.json',targets)
    docs=[]
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(headless=True)
        try:
            for t in targets:
                spec=await asyncio.wait_for(q.capture_page(browser,t,out),timeout=180)
                docs.append(spec)
                print(json.dumps({'partner':t['partner'],'native_ids':spec['capture_scope']['native_ids'],
                                  'images':len(spec['images']),'scope':spec['capture_scope']},ensure_ascii=False),flush=True)
        finally:await browser.close()
    m.save(out/'manifest.json',{'documents':docs})
    loaded=m.load_manifest(out/'manifest.json')
    assert len(loaded)==len(CASES)
    m.save(ROOT/'input-check.json',{'documents':len(loaded),'images':sum(len(d['images']) for d in loaded),
                                   'full_native_objects':True,'capture_used_expected_values':False})


def infer():
    docs=m.load_manifest(ROOT/'captures/manifest.json')
    state=q.new_state();q.merge_targets(state,json.loads((ROOT/'targets.json').read_text()))
    schema=json.loads((q.HERE/'merchant_offer.schema.json').read_text());prompt=(q.HERE/'merchant_prompt.txt').read_text()
    result=q.process_documents(docs,state,ROOT/'state.json',ROOT/'results',os.environ['EXPERIENTAL_API_KEY'],schema,prompt,
                               max_requests=4,provider='experiential',time_budget=600)
    m.save(ROOT/'summary.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='results'},ensure_ascii=False),flush=True)


def inspect():
    state=q.read_state(ROOT/'state.json');checks=[]
    for t in json.loads((ROOT/'targets.json').read_text()):
        row=state['items'][t['id']];obj=row.get('extracted');checks.append({'partner':t['partner'],'id':t['id'],
            'status':row.get('status'),'output':obj,'usage':row.get('last_result',{}).get('usage')})
    m.save(ROOT/'answers.json',checks);print(json.dumps(checks,ensure_ascii=False,indent=2))
    for row in checks:
        assert row['status']=='completed',row['partner']
        obj=row['output'];assert obj['has_offer'] is True,row['partner']
        offers=obj['offers'];expected=CASES[row['partner']]
        assert any(o['benefit_kind']=='discount' and o['value']==expected for o in offers),row['partner']
        actions=' '.join(a for o in offers for a in o['how_to_get']).lower()
        assert 'консьерж' in actions and 'бронир' in actions,row['partner']
        assert all(o['promo_code'] is None and o['valid_until'] is None for o in offers),row['partner']
        native=json.loads((ROOT/'captures'/row['id']/'native-source.json').read_text())['items']
        if row['partner']!='Po’mestam':
            assert any('приоритетное размещение' in i['description'].lower() for i in native)
            assert any(o['benefit_kind']=='other' and 'приоритет' in (o['basis'] or '').lower() for o in offers),('lost secondary benefit',row['partner'])
        strings=[]
        def collect(x):
            if isinstance(x,str):strings.append(x)
            elif isinstance(x,dict):
                for v in x.values():collect(v)
            elif isinstance(x,list):
                for v in x:collect(v)
        collect(native)
        for offer in offers:
            for quote in offer['evidence']:
                assert any(' '.join(quote.split()) in ' '.join(s.split()) for s in strings),(row['partner'],quote)
    m.save(ROOT/'semantic-check.json',{'cases':len(checks),'main_discount_and_booking_checks_passed':True,
           'all_three_non_monetary_benefits_preserved':True,
           'limits':'Known four-case regression, not a blind full-catalogue accuracy estimate.'})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['prepare','infer','inspect']);p.add_argument('--catalog',type=Path)
    args=p.parse_args()
    if args.phase=='prepare':asyncio.run(prepare(args.catalog))
    elif args.phase=='infer':infer()
    else:inspect()
