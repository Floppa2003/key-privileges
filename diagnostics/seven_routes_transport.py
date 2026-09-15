"""Finite access experiment, not a production adapter or source-answer fixture.
Anonymous GETs to seven configured public targets; no login, proxy, challenge
solver, disabled TLS, private input or Google access. DNS pins come only from
current public DNS answers, retain hostname/SNI validation and are never saved
as production configuration. Successful transport is not catalogue completeness.
"""
from __future__ import annotations
import concurrent.futures
import hashlib
import ipaddress
import json
import os
import platform
import re
import socket
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
import curl_cffi
from curl_cffi import CurlOpt
from bs4 import BeautifulSoup

IDS = ('ekp', 'nordwind', 'coral', 'coral_promo', 'rzd', 'aeroflot', 'utair')
OUT = Path('seven-access-output')
CAP = 4_000_000
DENIAL = re.compile(r'access denied|forbidden|unauthorized|доступ.{0,100}(?:ограничен|запрещ[её]н)|verify you are human|проверка браузера', re.I)
TOPIC = re.compile(r'партн[её]р|привилеги|бонус|мили|миль|loyalty', re.I)
SENSITIVE = re.compile(r'token|signature|password|secret|session|auth|key', re.I)
HEADERS = {'content-type', 'server', 'date', 'retry-after', 'via', 'alt-svc', 'www-authenticate', 'cache-control'}


def safe_url(url):
    try:
        u = urlsplit(url)
        if u.scheme != 'https' or not u.hostname or u.username or u.password:
            return None
        if SENSITIVE.search(u.query):
            return u._replace(query='', fragment='').geturl()
        return u._replace(fragment='').geturl()
    except ValueError:
        return None


def describe(raw, status):
    soup = BeautifulSoup(raw, 'html.parser')
    title = soup.title.get_text(' ', strip=True) if soup.title else ''
    scripts = [safe_url(s.get('src', '')) for s in soup.select('script[src]')]
    for tag in soup.select('script,style,form,input,textarea,noscript'):
        tag.decompose()
    text = soup.get_text(' ', strip=True)
    blocked = bool(DENIAL.search(title + ' ' + text[:2500]))
    classification = ('http_refusal' if status >= 400 else 'restriction_document' if blocked
                      else 'content_candidate' if status == 200 and len(text) > 800 and TOPIC.search(text)
                      else 'redirect' if 300 <= status < 400 else 'shell_or_other')
    links = []
    for a in soup.select('a[href]'):
        href = a.get('href', '')
        if TOPIC.search(a.get_text(' ', strip=True) + ' ' + href):
            links.append({'label': a.get_text(' ', strip=True)[:160], 'href': safe_url(href) if '://' in href else href.split('?')[0]})
    return {'classification': classification, 'title': title, 'text_chars': len(text),
            'text': text[:24000], 'text_truncated': len(text) > 24000,
            'links': links[:100], 'scripts': [s for s in scripts if s][:25],
            'raw_sha256': hashlib.sha256(raw).hexdigest(), 'raw_bytes': len(raw)}


def emit(report, row):
    report['reads'].append(row)
    OUT.mkdir(exist_ok=True)
    (OUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({k: row.get(k) for k in ('id', 'mode', 'status', 'error_type')}, ensure_ascii=False), flush=True)
    time.sleep(0.6)


def read(url, mode, session=None):
    begin = time.monotonic()
    row = {'url': safe_url(url), 'mode': mode, 'tls_verification': True}
    owned = session is None
    try:
        if mode == 'requests':
            client = session or requests.Session()
            client.trust_env = False
            r = client.get(url, allow_redirects=False, timeout=(6, 15), stream=True)
            chunks = bytearray()
            for chunk in r.iter_content(65536):
                chunks.extend(chunk)
                if len(chunks) > CAP:
                    raise ValueError('response_size_limit')
            raw = bytes(chunks)
        else:
            profile = {'plain': None, 'chrome': 'chrome', 'safari': 'safari', 'chrome-h1': 'chrome'}[mode]
            client = session or curl_cffi.Session(impersonate=profile, trust_env=False,
                                                 curl_options={CurlOpt.MAXFILESIZE_LARGE: CAP})
            chunks = bytearray()
            def receive(chunk):
                if len(chunks) + len(chunk) > CAP:
                    return 0
                chunks.extend(chunk)
                return len(chunk)
            options = {'http_version': 'v1'} if mode == 'chrome-h1' else {}
            r = client.get(url, allow_redirects=False, timeout=(6, 15), content_callback=receive, **options)
            raw = bytes(chunks)
            row['http_version'] = int(r.http_version)
            row['remote_ip'] = getattr(r, 'primary_ip', None)
        row['status'] = r.status_code
        row['headers'] = {k.lower(): v[:300] for k, v in r.headers.items() if k.lower() in HEADERS}
        row['location'] = safe_url(urljoin(url, r.headers['location'])) if 'location' in r.headers else None
        row['document'] = describe(raw, r.status_code)
        if len(chunks) >= CAP:
            row['body_limit_reached'] = True
        r.close()
    except Exception as exc:
        row['error_type'] = type(exc).__name__
        # Do not publish arbitrary exception strings containing cookies or URLs.
        row['error_code'] = getattr(exc, 'code', None)
    finally:
        if owned and 'client' in locals():
            client.close()
    row['seconds'] = round(time.monotonic() - begin, 3)
    return row


def dns_one(host, resolver, kind):
    base = {'google': 'https://dns.google/resolve', 'cloudflare': 'https://cloudflare-dns.com/dns-query'}[resolver]
    result = {'host': host, 'resolver': resolver, 'type': kind}
    try:
        with requests.Session() as s:
            s.trust_env = False
            r = s.get(base, params={'name': host, 'type': kind}, headers={'Accept': 'application/dns-json'}, timeout=(5, 8))
            r.raise_for_status()
            data = r.json()
        result.update({k: data.get(k) for k in ('Status', 'AD', 'CD', 'Answer')})
    except Exception as exc:
        result['error_type'] = type(exc).__name__
    return result


def read_dns_edge(url, ip):
    parsed = ipaddress.ip_address(ip)
    if not parsed.is_global:
        raise ValueError('not_a_public_dns_address')
    host = urlsplit(url).hostname
    ip_spec = '[' + ip + ']' if parsed.version == 6 else ip
    row = {'url': url, 'mode': 'current_public_dns_edge', 'edge': ip, 'tls_verification': True}
    with tempfile.TemporaryDirectory() as td:
        body = Path(td) / 'body'
        cmd = ['curl', '-sS', '--noproxy', '*', '--connect-timeout', '6', '--max-time', '15',
               '--max-filesize', str(CAP), '--resolve', f'{host}:443:{ip_spec}',
               '--output', str(body), '--write-out', '%{json}', url]
        try:
            p = subprocess.run(cmd, capture_output=True, timeout=20)
            row['returncode'] = p.returncode
            meta = json.loads(p.stdout.decode('utf8', 'replace'))
            for k in ('http_code', 'http_version', 'remote_ip', 'time_connect', 'time_appconnect', 'time_total', 'ssl_verify_result'):
                row[k] = meta.get(k)
            row['status'] = meta.get('http_code', 0)
            if body.exists():
                row['document'] = describe(body.read_bytes()[:CAP], row['status'])
        except Exception as exc:
            row['error_type'] = type(exc).__name__
    return row


def selfcheck():
    assert describe(b'<title>Forbidden</title>', 403)['classification'] == 'http_refusal'
    assert describe('<title>Доступ ограничен владельцем</title>'.encode(), 200)['classification'] == 'restriction_document'
    assert describe(('<h1>Партнеры</h1><p>' + 'Условия скидки ' * 100 + '</p>').encode(), 200)['classification'] == 'content_candidate'
    assert safe_url('https://example.com/file?token=secret') == 'https://example.com/file'
    assert safe_url('https://user:secret@example.com/') is None
    assert safe_url('http://example.com') is None


def main():
    selfcheck()
    sources = json.loads(Path('loyalty/sources_normalized.json').read_text())
    targets = {s['id']: s['url'] for s in sources if s['id'] in IDS}
    assert set(targets) == set(IDS)
    report = {'observed_at': datetime.now(timezone.utc).isoformat(), 'run_id': os.getenv('GITHUB_RUN_ID'),
              'commit': os.getenv('GITHUB_SHA'), 'runner': os.getenv('RUNNER_LABEL'),
              'platform': platform.platform(), 'requests_version': requests.__version__,
              'curl_cffi_version': curl_cffi.__version__,
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'scope': 'seven_exact_targets_anonymous_get_no_robots_precheck_not_a_crawl',
              'reads': [], 'dns': [], 'native_dns': {}}
    hosts = list(dict.fromkeys(urlsplit(u).hostname for u in targets.values()))
    for host in hosts:
        try:
            report['native_dns'][host] = sorted({a[4][0] for a in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)})
        except OSError as exc:
            report['native_dns'][host] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(dns_one, h, r, t) for h in hosts for r in ('google', 'cloudflare') for t in ('A', 'AAAA')]
        report['dns'] = [f.result() for f in futures]
    control = read('https://example.com/', 'chrome')
    control['id'] = 'control'
    emit(report, control)
    # Baseline and same-machine client comparisons. Not repeated IP roulette.
    for key in IDS:
        url = targets[key]
        baseline = read(url, 'requests'); baseline['id'] = key; emit(report, baseline)
        chrome = read(url, 'chrome'); chrome['id'] = key; emit(report, chrome)
        if baseline.get('status') or chrome.get('status'):
            for mode in ('plain', 'safari', 'chrome-h1'):
                row = read(url, mode); row['id'] = key; emit(report, row)
        else:
            report.setdefault('skips', []).append({'id': key, 'reason': 'no_http_response_skip_redundant_header_variants'})
        # Normal anonymous homepage -> exact target navigation in one session.
        if chrome.get('status') in (200, 301, 302, 401, 403):
            with curl_cffi.Session(impersonate='chrome', trust_env=False,
                                   curl_options={CurlOpt.MAXFILESIZE_LARGE: CAP}) as session:
                root = 'https://' + urlsplit(url).netloc + '/'
                warm = read(root, 'chrome', session); warm.update(id=key, mode='homepage_session'); emit(report, warm)
                if warm.get('status') in (200, 301, 302):
                    row = read(url, 'chrome', session); row.update(id=key, mode='after_homepage'); emit(report, row)
    tested = set()
    for key in IDS:
        url = targets[key]; host = urlsplit(url).hostname
        addresses = []
        for entry in report['dns']:
            if entry['host'] != host: continue
            for ans in entry.get('Answer') or []:
                if ans.get('type') not in (1, 28): continue
                try:
                    ip = ipaddress.ip_address(ans['data'])
                    if ip.is_global and str(ip) not in addresses: addresses.append(str(ip))
                except ValueError: pass
        native = report['native_dns'][host]
        extras = [ip for ip in addresses if ip not in native]
        # If DNS differs, test at most two advertised extra edges per hostname.
        for ip in extras[:2]:
            if (host, ip) in tested: continue
            tested.add((host, ip))
            row = read_dns_edge(url, ip); row['id'] = key; emit(report, row)
    report['finished_at'] = datetime.now(timezone.utc).isoformat()
    report['secrets_or_source_accounts_used'] = False
    (OUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    (OUT / 'executed-script.py').write_bytes(Path(__file__).read_bytes())


if __name__ == '__main__':
    main()
