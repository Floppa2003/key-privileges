"""One-time reviewed source registration; removed by branch CI before merge."""
from pathlib import Path
import hashlib,json
BEFORE={'loyalty/known_rules.py':'d82dbcfd9d15d18def396b65273b7be032c00189ea65201fd06ac28d93b23510','loyalty/known_rules.json':'2f2efeef64c09cbf16359cfcc38ffef3e5e8629de71fee1e092e7bddefbff5ae','loyalty/sources_normalized.json':'168bd32f6c3716fabc75b111a8d55cb2618725aa590e0f550179063778fa5de4','loyalty/requirements.txt':'86a947029106217e4c79ef7114b54d46c35cdea3eddb61945bbcc48f4a4d333b'}
for name,digest in BEFORE.items():
 if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise ValueError('Unexpected baseline: '+name)
p=Path('loyalty/known_rules.py');s=p.read_text();start=s.index('async def collect_known_rules(')
s=s[:start]+'''async def collect_known_rules(client,cfg,report,now,limit):
    settings=CONFIG[cfg['id']]
    if settings.get('format')=='pdf':
        from known_pdf import collect_pdf_rule
        rows=await collect_pdf_rule(client,cfg,now)
    else:
        raw=await within_source_budget(client,lambda:client.read(cfg['url'],render=settings.get('render',True)))
        if settings.get('ready_text'):
            selector=settings['selectors'][0]
            async def ready_article():
                await client.page.wait_for_function(
                    '(q)=>{const a=document.querySelectorAll(q.selector);return a.length===1 && a[0].innerText.includes(q.text)}',
                    arg={'selector':selector,'text':settings['ready_text']},timeout=8000)
                if canonical_url(client.page.url)!=canonical_url(cfg['url']):
                    raise RuntimeError('known_rule_redirect_during_readiness')
                return await client.page.content()
            raw=await within_source_budget(client,ready_article)
        rows=parse_known_rule(cfg['id'],raw,cfg['url'],now)
    report['discovered']=len(rows)
    report['coverage']='reviewed_known_public_rule_sections; supplementary evidence, not full programme catalogue'
    if len(rows)>limit:report['errors'].append({'phase':'rules','reason':'record_limit','limit':limit})
    return rows[:limit]
''';p.write_text(s)
extra={'rzd_finuslugi_rules':{'url':'https://assets.finuslugi.ru/sc-disclosure/293d2bf4-16c4-46c6-87a5-0a2d35d18ad8','program':'РЖД Бонус','partner':'Финуслуги','title':'Правила начисления баллов за первый вклад','format':'pdf'},'af_primbank_rules':{'url':'https://www.primbank.ru/d/tariffs-aeroflot-bonus','program':'Аэрофлот Бонус','partner':'Банк Приморье','title':'Тариф карты: начисление миль и ограничения','format':'pdf'}}
p=Path('loyalty/known_rules.json');d=json.loads(p.read_text());d.update(extra);d['t2_sim_rules']['ready_text']='Дополнительно оплачивается замена SIM-карты';p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
p=Path('loyalty/sources_normalized.json');d=json.loads(p.read_text());d.extend({'id':k,'name':v['program']+' → '+v['partner']+' — PDF','url':v['url'],'mode':'known_rules'} for k,v in extra.items());p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
p=Path('loyalty/requirements.txt');p.write_text(p.read_text()+'pypdf==6.18.1\n')
AFTER={'loyalty/known_rules.py':'4c64134ab5a642d118e968c7a22e8453e3f7a93d7c178652080a76a50f08ffde','loyalty/known_rules.json':'18597ae3fda93dc6c9b16ba6e6e504a823bf25b3c5b474a4e574c9c8d9a93d50','loyalty/sources_normalized.json':'ead4671930c91534049c326829fb949d85ffb90f61fe37e2b8f42b2720abc728','loyalty/requirements.txt':'10261415499fe4755d38bea614b9039cff77a84627b86c19a514bb0dd62228bf','loyalty/known_pdf.py':'d2eedd6c977ac6d29d3c5e0125f3d9a514f1ec45d584cb052eb70fca6bebcce3','loyalty/tests/test_known_pdf.py':'15dfb8a675bc43b118433d338f793d972a7860065f6de5479c9e43c4454d9d54','loyalty/tests/test_known_rule_routing.py':'b9f06951de10fdc0c5a15bc43b44a819f070d0606f8579f367060501cdd6b004'}
for name,digest in AFTER.items():
 if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise ValueError('Registration integrity mismatch: '+name)
print('All seven changed files match the locally tested revision.')
