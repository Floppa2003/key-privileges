"""Bounded public-read experiment; no credentials, production or Sheets writes."""
from __future__ import annotations
import hashlib
import json
import os
import platform
import re
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import requests
from bs4 import BeautifulSoup

OUT = Path('frontier-output')
OUT.mkdir(exist_ok=True)
IDS = {'ekp', 'nordwind', 'coral', 'coral_promo', 'rzd', 'aeroflot', 'utair'}
BLOCK = re.compile(r'access.denied|доступ.{0,35}(?:ограничен|запрещен)|captcha|just a moment|request rejected|не робот|провер.{0,15}браузер|forbidden', re.I)
MAX_BYTES = 3000000
MARKERS = {
    'ekp': r'лояльност|петербурж', 'nordwind': r'партнер|партнёр|partner',
    'coral': r'привилег|CoralBonus', 'coral_promo': r'акци|CoralBonus',
    'rzd': r'РЖД|Бонус', 'aeroflot': r'Аэрофлот|Aeroflot', 'utair': r'Status|партнер|партнёр',
}


def read(url, sid, suffix='target'):
    row = {'source_id': sid, 'url': url, 'observed_at': datetime.now(timezone.utc).isoformat()}
    start = time.monotonic()
    try:
        row['dns'] = sorted({v[4][0] for v in socket.getaddrinfo(urlsplit(url).hostname, 443, type=socket.SOCK_STREAM)})
        with requests.Session() as session:
            session.trust_env = False
            # Identical client on all runner types, and no cross-host redirects.
            session.headers['User-Agent'] = 'Mozilla/5.0 (compatible; PublicCatalogDiagnostic/1.0)'
            with session.get(url, timeout=(10, 20), allow_redirects=False, stream=True) as response:
                row['status'] = response.status_code
                row['content_type'] = response.headers.get('Content-Type', '')
                row['location'] = response.headers.get('Location')
                chunks = []; size = 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > MAX_BYTES or time.monotonic() - start > 35:
                        raise RuntimeError('response_budget_exceeded')
                    chunks.append(chunk)
                raw = b''.join(chunks)
                row['bytes'] = len(raw)
                row['sha256'] = hashlib.sha256(raw).hexdigest()
                encoding = response.encoding
                if not encoding or encoding.lower() == 'iso-8859-1':
                    encoding = 'utf-8'
                html = raw.decode(encoding, 'replace')
                soup = BeautifulSoup(html, 'html.parser')
                row['title'] = soup.title.get_text(' ', strip=True) if soup.title else None
                for tag in soup(['script', 'style', 'noscript']):
                    tag.decompose()
                visible = soup.get_text(' ', strip=True)
                row['text_sample'] = visible[:900]
                row['text_length'] = len(visible)
                row['classification'] = ('http_error' if response.status_code != 200 else
                    'access_challenge' if BLOCK.search(visible) else
                    'content_candidate' if len(visible) > 300 and re.search(MARKERS[sid], visible, re.I) else
                    'unknown_or_empty')
                # Preserve public source bytes, not cookies, authorization or session storage.
                filename = sid + '-' + suffix + '.html'
                (OUT / filename).write_bytes(raw)
                row['body_file'] = filename
                original = BeautifulSoup(html, 'html.parser')
                row['advertised_resources'] = list(dict.fromkeys(
                    urljoin(url, tag.get('href') or tag.get('src'))
                    for tag in original.select('a[href], script[src], link[href]')
                    if re.search(r'partner|loyal|api|bonus|\.js(?:\?|$)|sitemap|rss|feed|json',
                                 tag.get('href') or tag.get('src') or '', re.I)
                ))[:200]
    except Exception as exc:
        row['error'] = type(exc).__name__
        row['error_detail'] = str(exc)[:220]
        row['classification'] = 'read_failure'
    row['seconds'] = round(time.monotonic() - start, 3)
    print(json.dumps({k: row.get(k) for k in ['source_id', 'status', 'classification', 'bytes', 'error', 'seconds']}), flush=True)
    return row


def main():
    cfgs = json.loads(Path('loyalty/sources_normalized.json').read_text())
    results = []
    for cfg in cfgs:
        if cfg['id'] in IDS:
            results.append(read(cfg['url'], cfg['id']))
            time.sleep(1)
    report = {'run_id': os.getenv('GITHUB_RUN_ID'), 'commit': os.getenv('GITHUB_SHA'),
              'runner': os.getenv('RUNNER_LABEL'), 'platform': platform.platform(),
              'client': requests.__version__, 'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'scope': 'finite exact public GETs; target access separate from robots; not a production collection',
              'results': results}
    (OUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

if __name__ == '__main__':
    main()
