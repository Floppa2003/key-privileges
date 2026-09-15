"""Follow-up to the recorded DNS/client matrix. No historical IP inventory.
Test Aeroflot's currently advertised public A records with unchanged hostname,
SNI and verified TLS. Test HTTP/3 separately (a UDP transport, not a browser-UA
change), with an independent control. Refusals and timeouts stay explicit.
"""
import hashlib
import ipaddress
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
import curl_cffi
from curl_cffi import CurlOpt
from seven_routes_transport import IDS, CAP, HEADERS, describe, dns_one, read, read_dns_edge, selfcheck

OUT = Path('seven-edge-output')


def cffi_get(url, http_version='v2', ip=None):
    row = {'url': url, 'mode': 'chrome_http3_only' if http_version == 'v3only' else 'chrome_public_dns_edge',
           'tls_verification': True}
    options = {CurlOpt.MAXFILESIZE_LARGE: CAP}
    if ip:
        if not ipaddress.ip_address(ip).is_global:
            raise ValueError('not_global')
        options[CurlOpt.RESOLVE] = [f'{urlsplit(url).hostname}:443:{ip}'.encode()]
        row['edge'] = ip
    begin = time.monotonic()
    try:
        with curl_cffi.Session(impersonate='chrome', trust_env=False, curl_options=options) as session:
            data = bytearray()
            def accept(chunk):
                if len(data) + len(chunk) > CAP: return 0
                data.extend(chunk)
                return len(chunk)
            r = session.get(url, timeout=(5, 12), allow_redirects=False,
                            http_version=http_version, content_callback=accept)
            row.update(status=r.status_code, http_version=int(r.http_version),
                       document=describe(bytes(data), r.status_code),
                       headers={k.lower():v[:250] for k,v in r.headers.items() if k.lower() in HEADERS})
    except Exception as exc:
        row.update(error_type=type(exc).__name__, error_code=getattr(exc, 'code', None))
    row['seconds'] = round(time.monotonic()-begin, 3)
    return row


def main():
    selfcheck()
    source_list = json.loads(Path('loyalty/sources_normalized.json').read_text())
    targets = {s['id']: s['url'] for s in source_list if s['id'] in IDS}
    report = {'observed_at': datetime.now(timezone.utc).isoformat(), 'run_id': os.getenv('GITHUB_RUN_ID'),
              'commit': os.getenv('GITHUB_SHA'), 'runner': os.getenv('RUNNER_LABEL'),
              'reads': [], 'dns': [], 'script_hashes': {n:hashlib.sha256((Path('diagnostics')/n).read_bytes()).hexdigest()
                  for n in ('seven_routes_edges.py','seven_routes_transport.py')}}
    OUT.mkdir(exist_ok=True)
    def save(row):
        report['reads'].append(row)
        (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps({k:row.get(k) for k in ('id','mode','edge','status','error_type')}),flush=True)
        time.sleep(1)
    host = urlsplit(targets['aeroflot']).hostname
    for resolver in ('google','cloudflare'):
        report['dns'].append(dns_one(host,resolver,'A'))
    addresses = sorted({a['data'] for d in report['dns'] for a in d.get('Answer') or []
                        if a.get('type')==1 and ipaddress.ip_address(a['data']).is_global})
    report['dns_edge_count'] = len(addresses)
    report['dns_edge_test_limit'] = 8
    for ip in addresses[:8]:
        row=read_dns_edge(targets['aeroflot'],ip);row['id']='aeroflot';save(row)
        if row.get('status')==429:break
        row=cffi_get(targets['aeroflot'],ip=ip);row['id']='aeroflot';save(row)
        if row.get('status')==429:break
    control=cffi_get('https://www.google.com/robots.txt',http_version='v3only');control['id']='http3_control';save(control)
    for key,url in targets.items():
        row=cffi_get(url,http_version='v3only');row['id']=key;save(row)
        if row.get('status')==429:break
    report['finished_at']=datetime.now(timezone.utc).isoformat()
    report['scope']='anonymous_target_reads_current_public_dns_only_no_source_crawl_or_publication'
    (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    for n in report['script_hashes']:(OUT/n).write_bytes((Path('diagnostics')/n).read_bytes())

if __name__=='__main__': main()
