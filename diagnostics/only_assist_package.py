"""Inspect the exact public Only Assist split APK set without source credentials.

RuStore v2 shape: EFForg/apkeep PR226; actual ARM split response checked in
35473699662. APKs remain on the disposable runner, never public artifacts.
"""
from __future__ import annotations
import hashlib, io, json, os, re, subprocess, time, zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urljoin
import requests
PACKAGE='com.konsierge.assist.only'
OUT=Path('only-assist-evidence'); OUT.mkdir(exist_ok=True)
REPORT={'observed_at':datetime.now(timezone.utc).isoformat(),'package':PACKAGE,
        'source_account_login':False,'apk_executed':False,'requests':[]}
SESSION=requests.Session();SESSION.trust_env=False
HEADERS={'User-Agent':'OnlyAssistCompatibilityProbe/1.0','Accept':'application/json','ruStoreVerCode':'1000000'}


def allowed(url):
    u=urlsplit(url)
    return (u.scheme=='https' and not u.username and not u.password and u.port in (None,443)
            and u.hostname is not None and any(u.hostname==d or u.hostname.endswith('.'+d)
                for d in ('rustore.ru','vk.ru','vkuser.net','vkuseraudio.net','vkcdn.ru')))


def request(method,url,payload=None,maximum=2_000_000,headers=None):
    for _ in range(4):
        if not allowed(url):raise RuntimeError('unreviewed_download_origin:'+str(urlsplit(url).hostname))
        u=urlsplit(url)
        with SESSION.request(method,url,json=payload,headers=headers or HEADERS,
                             timeout=(8,45),allow_redirects=False,stream=True) as r:
            REPORT['requests'].append({'method':method,'origin':u.scheme+'://'+u.netloc,'path':u.path,'status':r.status_code})
            if r.status_code==429 or r.headers.get('Retry-After'):raise RuntimeError('rate_limit_stop')
            if r.status_code in (301,302,303,307,308):
                if method!='GET':raise RuntimeError('post_redirect_not_followed')
                url=urljoin(url,r.headers.get('Location',''));continue
            if r.status_code!=200:raise RuntimeError('http_'+str(r.status_code))
            raw=bytearray()
            for part in r.iter_content(65536):
                raw.extend(part)
                if len(raw)>maximum:raise RuntimeError('response_size_bound')
            return bytes(raw)
    raise RuntimeError('redirect_bound')


def run_tool(path,*args):
    p=subprocess.run([str(path),*args],capture_output=True,timeout=90,text=True)
    if p.returncode:raise RuntimeError('android_tool_failed:'+Path(path).name)
    return p.stdout


def main():
    raw=request('GET','https://backapi.rustore.ru/applicationData/overallInfo/'+PACKAGE)
    meta=json.loads(raw).get('body',{})
    if meta.get('packageName')!=PACKAGE:raise RuntimeError('store_package_mismatch')
    REPORT['store']={k:meta[k] for k in ('appId','packageName','versionName','versionCode','minSdkVersion','targetSdkVersion','companyName','fileSize') if k in meta}
    REPORT['store_metadata_sha256']=hashlib.sha256(raw).hexdigest()
    payload={'appId':meta['appId'],'firstInstall':True,'mobileServices':['GMS','HMS'],
             'supportedAbis':['arm64-v8a'],'screenDensity':420,'supportedLocales':['ru_RU'],
             'sdkVersion':35,'withoutSplits':False,'signatureFingerprint':None}
    result=json.loads(request('POST','https://backapi.rustore.ru/applicationData/v2/download-link',payload))
    body=result.get('body') or {};links=result.get('downloadUrls') or body.get('downloadUrls') or []
    REPORT['distribution_profile']='arm64_split_v2';REPORT['download_link_count']=len(links)
    if result.get('code')!='OK' or not 1<=len(links)<=8 or any(not isinstance(x.get('url'),str) for x in links):
        raise RuntimeError('invalid_split_download_response')
    tmp=Path(os.environ.get('RUNNER_TEMP','/tmp')); parts=tmp/'only-assist-apks';parts.mkdir(exist_ok=True)
    tools=sorted(Path(os.environ['ANDROID_HOME']).glob('build-tools/*/apksigner'))
    if not tools:raise RuntimeError('apksigner_missing')
    build=tools[-1].parent;total=0;certificates=None;base=None;paths=[];routes=set();REPORT['apks']=[]
    for index,entry in enumerate(links):
        time.sleep(1)
        raw=request('GET',entry['url'],maximum=160_000_000,headers={'User-Agent':HEADERS['User-Agent'],'Accept':'*/*'})
        total+=len(raw)
        if total>220_000_000:raise RuntimeError('total_download_bound')
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            if 'AndroidManifest.xml' not in z.namelist() or sum(i.file_size for i in z.infolist())>400_000_000:
                raise RuntimeError('invalid_apk_container')
        dest=parts/f'part-{index}.apk';dest.write_bytes(raw);paths.append(str(dest))
        signature=run_tool(build/'apksigner','verify','--verbose','--print-certs',str(dest))
        certs=re.findall(r'certificate SHA-256 digest: ([a-fA-F0-9]+)',signature)
        if not certs or (certificates is not None and certs!=certificates):raise RuntimeError('split_signers_differ')
        certificates=certs
        badging=run_tool(build/'aapt','dump','badging',str(dest))
        pkg=re.search(r"package: name='([^']+)' versionCode='([^']+)' versionName='([^']*)'",badging)
        if not pkg or pkg[1]!=PACKAGE or int(pkg[2])!=int(meta['versionCode']):raise RuntimeError('binary_package_version_mismatch')
        split=re.search(r"\bsplit='([^']+)'",badging.splitlines()[0])
        activity=re.search(r"launchable-activity: name='([^']+)'",badging)
        if activity:
            if base is not None:raise RuntimeError('multiple_launcher_apks')
            base=str(dest);REPORT['launcher']=activity[1]
        item={'part':index,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'signature_verified':True,
              'split':split[1] if split else None,'package':pkg[1],'version_code':pkg[2],'version_name':pkg[3],
              'sdk_badging':[x for x in badging.splitlines() if x.startswith(('sdkVersion:','targetSdkVersion:','native-code:'))]}
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            item['native_libraries']=[i.filename for i in z.infolist() if i.filename.startswith('lib/')]
            item['framework_hints']=[i.filename for i in z.infolist() if re.search(r'index.android.bundle|flutter_assets|assemblies/|assets/www/.*(?:html|js)$',i.filename)][:50]
            for i in z.infolist():
                if i.file_size>65_000_000 or not i.filename.endswith(('.dex','.so','.js','.json','.xml','.bundle')):continue
                for value in re.findall(rb'https?://[a-zA-Z0-9./_:#?=&%+~@-]{5,240}',z.read(i)):
                    try:
                        u=urlsplit(value.decode())
                        if u.username or u.password or not u.hostname:continue
                        if any(t in u.hostname.lower() for t in ('konsierge','assist','apcg','reise','quintessentially')):
                            path=u.path if not re.search(r'token|secret|session|password',u.path,re.I) else '/[omitted]'
                            routes.add((index,i.filename,u.scheme+'://'+u.netloc+path))
                    except ValueError:continue
        REPORT['apks'].append(item)
    if base is None:raise RuntimeError('launcher_not_found')
    REPORT['signing_certificate_sha256']=certificates;REPORT['apk_total_bytes']=total
    REPORT['route_literals']=[{'part':n,'member':m,'url':u} for n,m,u in sorted(routes)]
    REPORT['static_inspection_complete']=True
    (tmp/'only-assist-install.json').write_text(json.dumps({'files':paths,'base':base,'launcher':REPORT['launcher']}))
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('apk_ready=true\n')


if __name__=='__main__':
    try:main()
    except Exception as e:REPORT['error']=str(e) if isinstance(e,RuntimeError) else type(e).__name__
    finally:
        (OUT/'package_report.json').write_text(json.dumps(REPORT,ensure_ascii=False,indent=2))
        print(json.dumps(REPORT,ensure_ascii=False,indent=2))
