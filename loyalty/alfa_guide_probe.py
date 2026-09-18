"""One-time partner-guide inventory; no automatic promotion of guide previews to bank terms."""
from __future__ import annotations
import hashlib,json,re,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin,urlsplit
import requests
from bs4 import BeautifulSoup
from protego import Protego
from alfa_inventory_probe import read

OUT=Path('alfa-inventory-check');ROOTS=['https://greatlist.ru/msk/alfa-only/','https://greatlist.ru/spb/alfa-only/']
def main():
    OUT.mkdir(exist_ok=True);report={'roots':[],'cards':[],'errors':[]};total=0
    with requests.Session() as s:
        s.trust_env=False
        status,raw=read(s,'https://greatlist.ru/robots.txt',bound=200000,timeout=12)
        if status!=200:raise RuntimeError('robots_not_200')
        policy=Protego.parse(raw.decode());seen=set()
        for root in ROOTS:
            if not policy.can_fetch(root,'LoyaltyCatalogResearchBot'):raise RuntimeError('root_robots_disallow')
            status,raw=read(s,root,bound=2000000);total+=len(raw)
            if status!=200:raise RuntimeError('root_not_200')
            soup=BeautifulSoup(raw,'html.parser');city=urlsplit(root).path.split('/')[1];items=[]
            for card in soup.select('.js_get_cards a.place_card[data-objectid][href]'):
                url=urljoin(root,card['href']);name=card.select_one('.h2')
                if not re.fullmatch(r'https://greatlist\.ru/'+city+r'/restaurant/[a-z0-9-]+/',url) or not name:raise RuntimeError('card_identity')
                if url in seen:raise RuntimeError('duplicate_card')
                seen.add(url);items.append({'url':url,'name':name.get_text(' ',strip=True),'city':city,'native_id':card['data-objectid']})
            if not 1<=len(items)<=70:raise RuntimeError('catalog_bound')
            report['roots'].append({'url':root,'observed_at':datetime.now(timezone.utc).isoformat(),'sha256':hashlib.sha256(raw).hexdigest(),'listed':len(items),'script_urls':[urljoin(root,x['src']) for x in soup.select('script[src]') if 'greatlist.ru/' in urljoin(root,x['src'])]})
            for item in items:
                try:
                    if total>240000000:raise RuntimeError('total_read_budget')
                    if not policy.can_fetch(item['url'],'LoyaltyCatalogResearchBot'):raise RuntimeError('card_robots_disallow')
                    time.sleep(0.5);s.cookies.clear()
                    status,raw=read(s,item['url'],bound=9000000);total+=len(raw)
                    item.update(observed_at=datetime.now(timezone.utc).isoformat(),http_status=status,sha256=hashlib.sha256(raw).hexdigest())
                    if status!=200:raise RuntimeError('detail_not_200')
                    soup=BeautifulSoup(raw,'html.parser');blocks=soup.select('.alfa-section')
                    if len(blocks)!=1:raise RuntimeError('one_alfa_block_required')
                    block=blocks[0];title=block.select_one('.alfa-section-title');text=block.select_one('.alfa-section-text');link=block.select_one('a.alfa-section-link[href]')
                    if title is None or text is None or 'Alfa Only' not in title.get_text():raise RuntimeError('alfa_title_identity')
                    item.update(status='read',title=title.get_text(' ',strip=True),benefits=text.get_text('\n',strip=True),more_url=link['href'] if link else None)
                    addr=soup.select_one('.contacts_item_address');item['address']=addr.get_text(' ',strip=True) if addr else None
                    item['cashback_mentioned']=bool(re.search(r'к[еэ]шб[еэ]к',item['benefits'],re.I))
                    (OUT/(city+'-'+item['native_id']+'.html')).write_text(str(block),encoding='utf8')
                except Exception as e:item['error']=str(e) if isinstance(e,RuntimeError) else type(e).__name__;item['status']='failed'
                report['cards'].append(item)
    report['total_response_bytes']=total
    (OUT/'guide_inventory.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({'listed':len(report['cards']),'read':sum(x['status']=='read' for x in report['cards']),'cashback_mentioned':sum(x.get('cashback_mentioned',False) for x in report['cards']),'bytes':total}))
if __name__=='__main__':main()
