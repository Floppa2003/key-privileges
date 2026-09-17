"""Read the next observed programme-link layer, not every merchant hyperlink."""
import concurrent.futures, json, re, time
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urljoin,urlsplit,urldefrag
from bs4 import BeautifulSoup
import linked_conditions_probe as p

p.OUT=Path('linked-depth-output');p.OUT.mkdir(exist_ok=True)
base=Path('prior');old=json.loads((base/'report.json').read_text())
known={x['url'] for x in old['responses'] if x.get('parents')}
existing=json.loads(Path('loyalty/partner_pages.json').read_text())
already={x['url'].rstrip('/') for x in existing.values()}
entries={};exclusions=[]
for item in old['responses']:
    if not item.get('parents'):continue
    if item.get('redirect') and item['url']=='https://parkingsvo.ru/vazhno-znat/pravila-ispolzovaniya.html':
        target=item['redirect'];u=urlsplit(target)
        if u.netloc=='parking.svo.aero' and u.path.startswith('/storage/') and u.path.endswith('.pdf') and p.safe(target):
            entries[target]=[{'parent_url':item['url'],'parent_observed_at':item['finished_at'],'catalogue_parents':item['parents'],'relation':'observed_public_pdf_redirect'}]
    if not item.get('file','').endswith('.html'):continue
    soup=BeautifulSoup((base/item['file']).read_text(),'html.parser')
    af=item['parents'][0]['source_id']=='aeroflot'
    pattern=r'аэрофлот|aeroflot|afl[-_]bonus' if af else r'\bекп\b|edinaya-karta|един\w* карт\w* петербур'
    for a in soup.select('a[href]'):
        target=urldefrag(urljoin(item['url'],a['href']))[0];u=urlsplit(target)
        if u.hostname!=urlsplit(item['url']).hostname or u.query or target in known:continue
        if not re.search(pattern,target+' '+a.get_text(' ',strip=True),re.I):continue
        if re.search(r'/catalog/|/product|/personal|/login|/booking|/cart',u.path) or not p.safe(target):continue
        if target.rstrip('/') in already:
            exclusions.append({'url':target,'reason':'existing_exact_partner_adapter'});continue
        ref={'parent_url':item['url'],'parent_observed_at':item['finished_at'],'parent_saved_sha256':item['saved_sha256'],
             'label':a.get_text(' ',strip=True),'catalogue_parents':item['parents'],'relation':'observed_same_host_programme_link'}
        if ref not in entries.setdefault(target,[]):entries[target].append(ref)
if len(entries)>60:raise ValueError('depth_target_bound')
groups=defaultdict(list)
for url,refs in entries.items():groups[urlsplit(url).hostname].append((url,refs))
started=p.now();deadline=time.monotonic()+600;results=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    futures=[pool.submit(p.host_read,host,targets,deadline) for host,targets in groups.items()]
    for future in concurrent.futures.as_completed(futures):results.extend(future.result())
report={'run_id':p.os.environ['GITHUB_RUN_ID']+':'+p.os.environ['GITHUB_RUN_ATTEMPT'],'commit':p.os.environ['GITHUB_SHA'],
        'started_at':started,'finished_at':p.now(),'previous_probe_run':old['run_id'],
        'target_count':len(entries),'excluded':exclusions,'responses':results,'publication_performed':False,
        'source_accounts_used':False,'provider_credits':0,'parent_catalogue_refreshed':False}
(p.OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({'targets':len(entries),'results':dict(Counter(x.get('reason','policy_read') for x in results))}))
