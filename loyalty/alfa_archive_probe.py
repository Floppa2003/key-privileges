"""Bounded historical URL discovery only; archived terms are never published."""
from __future__ import annotations
import gzip,hashlib,io,json,re,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin,urlsplit,urlencode
import requests
from bs4 import BeautifulSoup

OUT=Path('alfa-inventory-check'); BOT='LoyaltyCatalogResearchBot/1.0'
TARGETS=['https://alfabank.ru/actions/rules/','https://alfabank.ru/retail/tariffs/']
MAX_COMPRESSED=3000000;MAX_RAW=25000000

def get(s,url,*,params=None,headers=None,bound=3000000,expected=(200,)):
    with s.get(url,params=params,headers={'User-Agent':BOT,**(headers or {})},timeout=(7,25),allow_redirects=False,stream=True) as r:
        if r.status_code not in expected or r.headers.get('Retry-After'):raise RuntimeError('http_'+str(r.status_code))
        body=bytearray();deadline=time.monotonic()+28
        for c in r.iter_content(65536):
            body.extend(c)
            if len(body)>bound or time.monotonic()>deadline:raise RuntimeError('response_bound')
        return bytes(body)

def links_from(raw,original):
    soup=BeautifulSoup(raw,'html.parser');out={}
    for a in soup.select('a[href]'):
        u=urljoin(original,a['href']);p=urlsplit(u)
        if p.scheme!='https' or p.hostname not in ('alfabank.servicecdn.ru','alfabank.st') or p.query or p.fragment or p.username:continue
        if not p.path.endswith('.pdf') or not p.path.startswith('/site-upload/'):continue
        label=a.get_text(' ',strip=True)
        if re.search(r'\bOnly\b|prog_loyal|revCashBack',label+' '+p.path,re.I):out[u]=label
    return [{'url':k,'label':v} for k,v in out.items()]

def main():
    OUT.mkdir(exist_ok=True);report={'observed_at':datetime.now(timezone.utc).isoformat(),'purpose':'historical_URL_discovery_only','attempts':[],'candidates':[]}
    with requests.Session() as s:
        s.trust_env=False
        try:
            indexes=json.loads(get(s,'https://index.commoncrawl.org/collinfo.json',bound=1000000))
            selected=[x for x in indexes if str(x.get('id','')).startswith('CC-MAIN-2026')][:3]
            for index in selected:
                endpoint=index.get('cdx-api','')
                if not re.fullmatch(r'https://index\.commoncrawl\.org/CC-MAIN-2026-\d+-index',endpoint):raise RuntimeError('index_endpoint_identity')
                for target in TARGETS:
                    row={'index':index['id'],'target':target}
                    try:
                        body=get(s,endpoint,params={'url':target,'matchType':'exact','output':'json','filter':'status:200'},bound=1000000)
                        records=[json.loads(x) for x in body.decode().splitlines() if x.strip()]
                        row['captures']=len(records)
                        accepted=[x for x in records if x.get('url')==target and x.get('status')=='200' and x.get('mime')=='text/html']
                        if accepted:
                            rec=sorted(accepted,key=lambda x:x['timestamp'],reverse=True)[0]
                            path=rec['filename'];off=int(rec['offset']);length=int(rec['length'])
                            if not re.fullmatch(r'crawl-data/CC-MAIN-2026-\d+/segments/[0-9.]+/warc/[A-Za-z0-9.-]+\.warc\.gz',path) or off<0 or not 1<=length<=MAX_COMPRESSED:raise RuntimeError('warc_record_bound')
                            packed=get(s,'https://data.commoncrawl.org/'+path,headers={'Range':f'bytes={off}-{off+length-1}'},bound=length,expected=(206,))
                            if len(packed)!=length:raise RuntimeError('warc_range_length')
                            with gzip.GzipFile(fileobj=io.BytesIO(packed)) as f:raw=f.read(MAX_RAW+1)
                            if len(raw)>MAX_RAW:raise RuntimeError('warc_uncompressed_bound')
                            if ('WARC-Target-URI: '+target).encode() not in raw[:2000]:raise RuntimeError('warc_target_identity')
                            parts=raw.split(b'\r\n\r\n',2)
                            if len(parts)!=3:raise RuntimeError('warc_http_shape')
                            links=links_from(parts[2],target)
                            row.update(timestamp=rec['timestamp'],sha256=hashlib.sha256(raw).hexdigest(),links=links)
                            report['candidates'].extend(links)
                    except Exception as e:row['error']=str(e) if isinstance(e,RuntimeError) else type(e).__name__
                    report['attempts'].append(row);time.sleep(1)
                if report['candidates']:break
        except Exception as e:report['commoncrawl_error']=str(e) if isinstance(e,RuntimeError) else type(e).__name__
        if not report['candidates']:
            # Only exact source-index availability metadata; never personal/bank-account URLs.
            try:
                data=json.loads(get(s,'https://archive.org/wayback/available',params={'url':TARGETS[0]},bound=1000000))
                snap=data.get('archived_snapshots',{}).get('closest',{})
                report['wayback']={k:snap.get(k) for k in ('available','status','timestamp','url')}
            except Exception as e:report['wayback_error']=str(e) if isinstance(e,RuntimeError) else type(e).__name__
    (OUT/'archive_discovery.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({'attempts':len(report['attempts']),'candidates':len(report['candidates']),'commoncrawl_error':report.get('commoncrawl_error'),'wayback':report.get('wayback'),'wayback_error':report.get('wayback_error')}))
if __name__=='__main__':main()
