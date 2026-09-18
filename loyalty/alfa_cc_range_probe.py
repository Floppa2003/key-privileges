"""Throwaway exact-source URL discovery using public CC byte ranges, no AWS account."""
from __future__ import annotations
import gzip,io,json,re,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
import requests

BASE='https://data.commoncrawl.org/cc-index/collections/CC-MAIN-2026-34/indexes/'
OUT=Path('alfa-inventory-check')
MAX_CALLS=44;MAX_BYTES=18000000

class Reader:
    def __init__(self):
        self.s=requests.Session();self.s.trust_env=False;self.calls=0;self.bytes=0
    def read(self,url,start,length):
        if self.calls>=MAX_CALLS or self.bytes+length>MAX_BYTES:raise RuntimeError('range_budget')
        if not (url.startswith(BASE) or re.fullmatch(r'https://data\.commoncrawl\.org/crawl-data/CC-MAIN-2026-34/segments/[0-9.]+/warc/[A-Za-z0-9.-]+\.warc\.gz',url)):raise RuntimeError('range_url_scope')
        time.sleep(0.4);self.calls+=1
        with self.s.get(url,headers={'Range':f'bytes={start}-{start+length-1}','User-Agent':'LoyaltyCatalogResearchBot/1.0'},timeout=(6,20),stream=True,allow_redirects=False) as r:
            if r.status_code!=206 or r.headers.get('Retry-After'):raise RuntimeError('range_http_'+str(r.status_code))
            h=re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',r.headers.get('Content-Range',''))
            if not h or int(h[1])!=start or int(h[2])>=start+length:raise RuntimeError('range_header')
            data=bytearray()
            for b in r.iter_content(65536):
                data.extend(b)
                if len(data)>length:raise RuntimeError('range_overrun')
            if len(data)!=int(h[2])-start+1:raise RuntimeError('range_short')
            self.bytes+=len(data);return bytes(data),int(h[3])

def parse_line(line):
    parts=line.split(b'\t')
    if len(parts)<4:raise RuntimeError('cluster_shape')
    key=parts[0].split(b' ')[0]
    name=parts[1].decode('ascii');off=int(parts[2]);length=int(parts[3])
    if not re.fullmatch(r'cdx-\d+\.gz',name) or off<0 or not 1<=length<=3000000:raise RuntimeError('block_identity')
    return key,name,off,length

def seek(reader,target):
    url=BASE+'cluster.idx';raw,total=reader.read(url,0,16384)
    low,high=0,total;best=None
    # Every request is a bounded window; never download the full multi-GB index.
    for _ in range(24):
        if high-low<32768:break
        mid=(low+high)//2;chunk,_=reader.read(url,mid,16384)
        begin=chunk.find(b'\n')+1;end=chunk.find(b'\n',begin)
        if not begin or end<0:raise RuntimeError('index_line_bound')
        line=chunk[begin:end];key,*_=parse_line(line)
        if key<=target:best=line;low=mid+end+1
        else:high=mid
    begin=max(0,low-16384);chunk,_=reader.read(url,begin,min(65536,total-begin))
    lines=chunk.splitlines()[0 if begin==0 else 1:]
    for line in lines[:-1]:
        key,*_=parse_line(line)
        if key<=target:best=line
        elif best is not None:break
    if best is None:raise RuntimeError('no_cluster_predecessor')
    return best

def unpack(data,bound=16000000):
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as f:raw=f.read(bound+1)
    if len(raw)>bound:raise RuntimeError('inflate_bound')
    return raw

def main():
    from bs4 import BeautifulSoup
    OUT.mkdir(exist_ok=True);reader=Reader();report={'crawl':'CC-MAIN-2026-34','observed_at':datetime.now(timezone.utc).isoformat(),'historical_discovery_only':True,'targets':[],'pdf_candidates':[]}
    try:
        for key in (b'ru,alfabank)/actions/rules/',b'ru,servicecdn,alfabank)/site-upload/'):
            line=seek(reader,key);k,name,off,length=parse_line(line)
            packed,_=reader.read(BASE+name,off,length);raw=unpack(packed)
            records=[]
            for row in raw.splitlines():
                parts=row.split(b' ',2)
                if len(parts)!=3 or not parts[0].startswith(key):continue
                rec=json.loads(parts[2]);rec['timestamp']=parts[1].decode();records.append(rec)
            report['targets'].append({'surt':key.decode(),'cluster':line.decode(),'records':records})
            for rec in records:
                url=rec.get('url','')
                if re.search(r'only|prog_loyal|revCashBack',url,re.I) and url.endswith('.pdf'):
                    report['pdf_candidates'].append({'url':url,'capture_time':rec['timestamp']})
                if rec.get('url')=='https://alfabank.ru/actions/rules/' and rec.get('status')=='200':
                    size=int(rec['length']);offset=int(rec['offset'])
                    if not 1<=size<=3000000:continue
                    data,_=reader.read('https://data.commoncrawl.org/'+rec['filename'],offset,size)
                    warc=unpack(data);parts=warc.split(b'\r\n\r\n',2)
                    if len(parts)!=3:continue
                    soup=BeautifulSoup(parts[2],'html.parser')
                    for a in soup.select('a[href]'):
                        url=a['href'];label=a.get_text(' ',strip=True)
                        if re.match(r'https://alfabank\.(?:servicecdn\.ru|st)/site-upload/',url) and url.endswith('.pdf') and re.search(r'only|prog_loyal|revCashBack',url+' '+label,re.I):
                            report['pdf_candidates'].append({'url':url,'label':label,'capture_time':rec['timestamp']})
    except Exception as e:report['error']=str(e) if isinstance(e,RuntimeError) else type(e).__name__
    report.update(range_calls=reader.calls,range_bytes=reader.bytes)
    (OUT/'cc_range_discovery.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({'candidates':len(report['pdf_candidates']),'calls':reader.calls,'bytes':reader.bytes,'error':report.get('error')}))
if __name__=='__main__':main()
