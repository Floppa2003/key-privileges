"""One-time checksum-bound registry patch; review CI removes this helper."""
from pathlib import Path
import hashlib,json,subprocess
before={'loyalty/normalized.py':'b017e2d93685a7bbfc0bde885ad4f67e5678192a7791f32b963053c16a7fb0a1','loyalty/collect_normalized.py':'4e08ddacee91b5d0fbafe64e6de7a34631beaad34c4a4da76a296b11d46c98c2','loyalty/sources_normalized.json':'920eef525f48a741a73a24ce47badc5db4434e6511f3a754537cf45f424313d3','loyalty/offer.schema.json':'581fa184b48ab038d0889714225d9ac8b83a3bf0747478f6fc09839af0b5acde'}
for p,h in before.items():
 if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h:raise ValueError('Unexpected baseline '+p)
p=Path('loyalty/normalized.py');s=p.read_text()
s=s.replace("VERSION = '2.7.0'","VERSION = '2.8.0'").replace('from table_benefits import extract_table_benefits\n','from table_benefits import extract_table_benefits\nfrom recovered_contract import SOURCES as RECOVERED_SOURCES, http_url, validate_recovered\n')
s=s.replace("BLOCKED = re.compile", "for _sid,_spec in RECOVERED_SOURCES.items():\n    HOSTS[_sid]=[urlsplit(_spec['url']).hostname]\nBLOCKED = re.compile")
s=s.replace('    fragment = urlsplit(value).fragment\n','    fragment = urlsplit(value).fragment\n    if urlsplit(value).scheme == \'http\':\n        return http_url(value)\n')
s=s.replace("    canonical_url(r['source_url'])\n","    canonical_url(r['source_url'])\n    validate_recovered(r)\n    if r['source_id']=='loyals':\n        post=r['details']['public_post']\n        if (r['benefit_text'] != text(post['content']['rendered'])\n                or r['title'] != text(post['title']['rendered'])\n                or r['conditions_text'] != (r['benefit_text'] or r['title'])):\n            raise ValueError('Loyals post text evidence mismatch')\n")
p.write_text(s)
p=Path('loyalty/collect_normalized.py');s=p.read_text().replace('from utair_documents import collect_documents\n','from utair_documents import collect_documents\nfrom recovered_sources import collect_recovered\n').replace("        if cfg['mode']=='key':records=await collect_key(report,now)\n","        if cfg['mode']=='key':records=await collect_key(report,now)\n        elif cfg['mode']=='recovered':records=await collect_recovered(cfg,report,now,limit)\n");p.write_text(s)
from recovered_contract import SOURCES
p=Path('loyalty/sources_normalized.json');items=json.loads(p.read_text())
for cfg in items:
 if cfg['id']=='loyals':cfg.update(mode='recovered',url=SOURCES['loyals']['url'],access_profile=SOURCES['loyals']['profile'],timeout_seconds=240)
for sid,name in [('af_vtb_rules','ВТБ — карта Привилегия Аэрофлот'),('nspk_ekp_rules','НСПК — объявление о кешбэке ЕКП'),('uralsib_rzd_rules','Уралсиб — архивные правила акции РЖД')]:
 items.append({'id':sid,'name':name,'mode':'recovered','url':SOURCES[sid]['url'],'access_profile':SOURCES[sid]['profile'],'timeout_seconds':240})
p.write_text(json.dumps(items,ensure_ascii=False,indent=2)+'\n')
p=Path('loyalty/offer.schema.json');s=json.loads(p.read_text());s['properties']['source_url']['pattern']=r'^(https://|http://loyals\.ru/wp-json/wp/v2/posts\?)';s['properties']['record_kind']['enum'].append('source_observation')
s['allOf']=[{'if':{'properties':{'source_id':{'const':'loyals'}}},'then':{'properties':{'source_status':{'const':'public_http_unverified'},'link_kind':{'const':'api_record'},'benefit_url':{'type':'null'}}},'else':{'properties':{'source_url':{'pattern':'^https://'}}}}]
p.write_text(json.dumps(s,ensure_ascii=False,separators=(',',':'))+'\n')
after={'loyalty/normalized.py':'3b1b2d34f653f84501e68da41ecaf462acae2955f39db5b727516c9af422a44f','loyalty/collect_normalized.py':'41e341ad46567355b2e107ada803e90e228d858a4f3e2e67f342e82b70fa7df2','loyalty/sources_normalized.json':'b8513e0fcc8dd49f6c71694d463f6e7a995299dfa38b01ff3a0173b6a3f5f4e7','loyalty/offer.schema.json':'02fb3f7e553fd26067cc0d0246512f7d18980ccf5a733218aa9e21cee6c841b4','loyalty/recovered_sources.py':'88585dc9bc030ef6f9a8beb074ea149e8ef5e4409032a92bdf690e5bb88a48fc','loyalty/recovered_contract.py':'73ce56a80b1c30d7be124ab68fd950e0cb8143b08c25e0528a3da2e1e856b489','loyalty/tests/test_recovered_sources.py':'93e419297b9a774bc87fec671f11a2cfbabcb32a455c13a527343ddf4c27ad9a'}
for p,h in after.items():
 if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h:raise ValueError('Final code hash mismatch '+p)
subprocess.run(['git','add','--',*before],check=True)
print('Seven reviewed integration files match tested local bytes.')
