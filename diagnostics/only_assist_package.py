"""Bounded download and static inspection of the public Only Assist APK.

Independent diagnostic; no bank/source credentials and no publication of app code.
RuStore flow references: Dynamic-Mobile-Security/mdast-cli rustore.py;
EFForg/apkeep PR226 src/download_sources/rustore.rs, read 2026-09-20.
"""
from __future__ import annotations
import hashlib, io, json, os, re, subprocess, zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urljoin
import requests

PACKAGE = 'com.konsierge.assist.only'
OUT = Path('only-assist-evidence'); OUT.mkdir(exist_ok=True)
REPORT = {'observed_at': datetime.now(timezone.utc).isoformat(), 'package': PACKAGE,
          'source_account_login': False, 'apk_executed': False, 'requests': []}
SESSION = requests.Session(); SESSION.trust_env = False
HEADERS = {'User-Agent': 'OnlyAssistCompatibilityProbe/1.0', 'Accept': 'application/json',
           'ruStoreVerCode': '1000000'}


def allowed(url):
    u = urlsplit(url)
    return (u.scheme == 'https' and not u.username and not u.password
            and u.port in (None, 443) and u.hostname is not None
            and any(u.hostname == d or u.hostname.endswith('.' + d)
                    for d in ('rustore.ru', 'vkuser.net', 'vkuseraudio.net', 'vkcdn.ru')))


def request(method, url, payload=None, maximum=2_000_000, headers=None):
    for _ in range(4):
        if not allowed(url):
            raise RuntimeError('unreviewed_download_origin:' + str(urlsplit(url).hostname))
        u = urlsplit(url)
        with SESSION.request(method, url, json=payload, headers=headers or HEADERS,
                             timeout=(8, 35), allow_redirects=False, stream=True) as r:
            REPORT['requests'].append({'method': method, 'origin': u.scheme + '://' + u.netloc,
                                       'path': u.path, 'status': r.status_code})
            if r.status_code == 429 or r.headers.get('Retry-After'):
                raise RuntimeError('rate_limit_stop')
            if r.status_code in (301, 302, 303, 307, 308):
                if method != 'GET': raise RuntimeError('post_redirect_not_followed')
                url = urljoin(url, r.headers.get('Location', '')); continue
            if r.status_code != 200: raise RuntimeError('http_' + str(r.status_code))
            raw = bytearray()
            for part in r.iter_content(65536):
                raw.extend(part)
                if len(raw) > maximum: raise RuntimeError('response_size_bound')
            return bytes(raw)
    raise RuntimeError('redirect_bound')


def run_tool(path, *args):
    p = subprocess.run([str(path), *args], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=90, text=True)
    if p.returncode: raise RuntimeError('android_tool_failed:' + Path(path).name)
    return p.stdout


def main():
    raw = request('GET', 'https://backapi.rustore.ru/applicationData/overallInfo/' + PACKAGE)
    meta = json.loads(raw).get('body', {})
    if meta.get('packageName') != PACKAGE: raise RuntimeError('store_package_mismatch')
    REPORT['store'] = {k: meta[k] for k in ('appId', 'packageName', 'versionName', 'versionCode',
                       'minSdkVersion', 'targetSdkVersion', 'companyName', 'fileSize') if k in meta}
    REPORT['store_metadata_sha256'] = hashlib.sha256(raw).hexdigest()
    # Device compatibility parameters are not login credentials.
    payload = {'appId': meta['appId'], 'firstInstall': True, 'mobileServices': ['GMS'],
               'supportedAbis': ['x86_64', 'arm64-v8a', 'armeabi-v7a'], 'screenDensity': 420,
               'supportedLocales': ['ru_RU'], 'sdkVersion': 35, 'withoutSplits': True,
               'signatureFingerprint': None}
    result = json.loads(request('POST', 'https://backapi.rustore.ru/applicationData/v2/download-link', payload))
    body = result.get('body', {})
    links = body.get('downloadUrls', [])
    REPORT['download_link_count'] = len(links)
    if len(links) != 1 or not isinstance(links[0].get('url'), str):
        raise RuntimeError('single_universal_apk_not_returned')
    link = links[0]['url']
    REPORT['store_version_code'] = body.get('versionCode')
    raw = request('GET', link, maximum=160_000_000,
                  headers={'User-Agent': HEADERS['User-Agent'], 'Accept': '*/*'})
    REPORT['download_sha256'] = hashlib.sha256(raw).hexdigest()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if sum(i.file_size for i in z.infolist()) > 400_000_000:
            raise RuntimeError('expanded_package_bound')
        if 'AndroidManifest.xml' not in z.namelist():
            apks = [i for i in z.infolist() if i.filename.endswith('.apk')]
            if len(apks) != 1: raise RuntimeError('split_package_requires_explicit_selection')
            raw = z.read(apks[0])
    dest = Path(os.environ.get('RUNNER_TEMP', '/tmp')) / 'only-assist.apk'; dest.write_bytes(raw)
    REPORT['apk_sha256'] = hashlib.sha256(raw).hexdigest(); REPORT['apk_bytes'] = len(raw)
    sdk = Path(os.environ['ANDROID_HOME']); tools = sorted(sdk.glob('build-tools/*/apksigner'))
    if not tools: raise RuntimeError('apksigner_missing')
    build = tools[-1].parent
    signature = run_tool(build / 'apksigner', 'verify', '--verbose', '--print-certs', str(dest))
    REPORT['signature_verified'] = True
    REPORT['signing_certificate_sha256'] = re.findall(r'certificate SHA-256 digest: ([a-fA-F0-9]+)', signature)
    badging = run_tool(build / 'aapt', 'dump', 'badging', str(dest))
    pkg = re.search(r"package: name='([^']+)' versionCode='([^']+)' versionName='([^']+)'", badging)
    if not pkg or pkg[1] != PACKAGE: raise RuntimeError('binary_package_identity_mismatch')
    if int(pkg[2]) != int(meta['versionCode']): raise RuntimeError('store_binary_version_mismatch')
    REPORT['binary'] = {'package': pkg[1], 'version_code': pkg[2], 'version_name': pkg[3]}
    activity = re.search(r"launchable-activity: name='([^']+)'", badging)
    REPORT['launcher'] = activity[1] if activity else None
    REPORT['sdk_badging'] = [x for x in badging.splitlines() if x.startswith(('sdkVersion:', 'targetSdkVersion:', 'native-code:'))]
    Path(os.environ.get('RUNNER_TEMP', '/tmp'), 'only-assist-launcher.txt').write_text(REPORT['launcher'] or '')
    routes = set()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        REPORT['native_libraries'] = [i.filename for i in z.infolist() if i.filename.startswith('lib/')]
        REPORT['framework_hints'] = [i.filename for i in z.infolist() if
                re.search(r'index.android.bundle|flutter_assets|assemblies/|assets/www/.*(?:html|js)$', i.filename)][:50]
        for i in z.infolist():
            if i.file_size > 65_000_000 or not (i.filename.endswith(('.dex', '.so', '.js', '.json', '.xml', '.bundle'))): continue
            data = z.read(i)
            for value in re.findall(rb'https?://[a-zA-Z0-9./_:#?=&%+~@-]{5,240}', data):
                try:
                    u = urlsplit(value.decode())
                    if u.username or u.password or not u.hostname: continue
                    if any(t in u.hostname.lower() for t in ('konsierge', 'assist', 'apcg', 'reise', 'quintessentially')):
                        path = u.path if not re.search(r'token|secret|session|password', u.path, re.I) else '/[omitted]'
                        routes.add((i.filename, u.scheme + '://' + u.netloc + path))
                except ValueError: continue
    REPORT['route_literals'] = [{'member': m, 'url': u} for m, u in sorted(routes)]
    REPORT['static_inspection_complete'] = True
    # APK stays on the disposable runner, never in public evidence.
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f: f.write('apk_ready=true\n')


if __name__ == '__main__':
    try: main()
    except Exception as e: REPORT['error'] = str(e) if isinstance(e, RuntimeError) else type(e).__name__
    finally:
        (OUT / 'package_report.json').write_text(json.dumps(REPORT, ensure_ascii=False, indent=2))
        print(json.dumps(REPORT, ensure_ascii=False, indent=2))
