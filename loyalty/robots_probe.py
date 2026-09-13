"""Bounded diagnostics: direct origin and independent anonymous public reader.
No Google credentials, no personal sessions, and no production publication.
"""
import asyncio,json,hashlib,time
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlsplit
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from public_transport import PublicSource

OUT=Path('robots-output')
TARGETS=[('coral','https://coralbonus.ru/klub-privilegii/zdorov-e/medsi/'),('rzd','https://www.rzd-bonus.ru/?accessible=true'),('ekp','https://ekp.spb.ru/capabilities/loyalty/'),('nordwind','https://nordwindairlines.ru/ru/club/partnerlist'),('aeroflot','https://www.aeroflot.ru/ru-ru/afl_bonus/partners')]
def save(name,body):
    OUT.joinpath(name).write_text(body,encoding='utf8')
    return {'file':name,'bytes':len(body.encode()),'sha256':hashlib.sha256(body.encode()).hexdigest()}
async def direct(browser,key,url):
    info={'source':key,'url':url,'method':'direct'};client=None
    try:
        async with asyncio.timeout(110):
            async with PublicSource(browser,url) as client:
                await client.robots()
                body=await client.read(url,render=True)
                soup=BeautifulSoup(body,'html.parser')
                info['title']=soup.title.get_text(' ',strip=True) if soup.title else ''
                info['status']='page_read'
                # Source HTML is public and anonymous. Do not persist session data.
                for node in soup.select('script,form,input,textarea'):node.decompose()
                info.update(save(key+'-direct.html',str(soup)))
    except Exception as exc:
        info['status']='failed';info['reason']=str(exc)[:250] if isinstance(exc,RuntimeError) else type(exc).__name__
    info['robots']=getattr(client,'robots_info',None)
    return info

def reader():
    reports=[]
    # Only exact approved public URLs; never pass a Sheet URL, account cookie or token.
    for key,url in TARGETS[:4]:
        info={'source':key,'url':url,'method':'jina_public_reader','requested_cache':'disabled'}
        try:
            res=requests.get('https://r.jina.ai/'+url,headers={'Accept':'application/json','X-Respond-With':'html','X-No-Cache':'true','X-Robots-Txt':'LoyaltyCatalogResearchBot'},timeout=75)
            info['http_status']=res.status_code
            if res.status_code!=200:
                info['status']='failed';info['reason']=res.text[:400]
            elif len(res.content)>6000000:
                info['status']='too_large'
            else:
                info['status']='response_received_not_yet_validated'
                info.update(save(key+'-reader.json',res.text))
        except requests.RequestException as exc:info['status']='failed';info['reason']=type(exc).__name__
        reports.append(info)
        if info.get('http_status') in (429,401,402):break
        time.sleep(4)
    return reports
async def main():
    OUT.mkdir(exist_ok=True)
    report={'observed_at':datetime.now(timezone.utc).isoformat(),'direct':[],'reader':[]}
    async with async_playwright() as p:
        b=await p.chromium.launch()
        try:
            for key,url in TARGETS:
                r=await direct(b,key,url);report['direct'].append(r);print(json.dumps(r,ensure_ascii=False),flush=True)
        finally:await b.close()
    report['reader']=await asyncio.to_thread(reader)
    OUT.joinpath('report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
if __name__=='__main__':asyncio.run(main())
