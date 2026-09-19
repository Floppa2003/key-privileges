"""Only Assist UI smoke test on a fresh disposable emulator, never authenticate.

Requires an empty emulator; not intended for a personal device. No credentials,
account logs, session exports or existing app data are read.
"""
from __future__ import annotations
import hashlib,json,os,re,subprocess,time
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime,timezone
PACKAGE='com.konsierge.assist.only';SERIAL='emulator-5554';OUT=Path('only-assist-evidence')
REPORT={'observed_at':datetime.now(timezone.utc).isoformat(),'package':PACKAGE,
        'account_login_attempted':False,'credentials_entered':False,'catalogue_records':0,'screens':[]}


def adb(*args,timeout=40,binary=False):
    p=subprocess.run(['adb','-s',SERIAL,*args],capture_output=True,timeout=timeout)
    if p.returncode:
        marker=re.search(rb'INSTALL_FAILED_[A-Z_]+',p.stdout+p.stderr)
        raise RuntimeError(marker[0].decode() if marker else 'adb_failed:'+(args[0] if args else 'unknown'))
    return p.stdout if binary else p.stdout.decode(errors='replace')


def inspect(name):
    adb('shell','uiautomator','dump','/sdcard/only-assist-probe.xml',timeout=45)
    root=ET.fromstring(adb('shell','cat','/sdcard/only-assist-probe.xml'));nodes=[]
    for node in root.iter('node'):
        if node.get('package')!=PACKAGE or node.get('password')=='true' or node.get('class','').endswith('EditText'):continue
        row={k:node.get(k,'') for k in ('text','content-desc','resource-id','class','bounds','clickable')}
        if row['text'] or row['content-desc']:nodes.append(row)
    words='\n'.join(n['text']+' '+n['content-desc'] for n in nodes)
    record={'name':name,'observed_at':datetime.now(timezone.utc).isoformat(),'owned_elements':nodes,
            'owned_elements_count':len(nodes),'login_marker':bool(re.search(r'alfa\s*id|альфа\s*id|авторизац|войти|вход|номер телефона',words,re.I)),
            'discounts_marker':bool(re.search(r'скидки|discounts',words,re.I)),
            'webview_present':any('WebView' in n.get('class','') for n in root.iter('node')),
            'visible_packages':sorted({n.get('package','') for n in root.iter('node')})}
    # This fresh emulator has never received account/user input, so even a system
    # permission dialog or launcher image has no personal account content.
    png=adb('exec-out','screencap','-p',binary=True);file=name+'.png';(OUT/file).write_bytes(png)
    record['screenshot']=file;record['screenshot_sha256']=hashlib.sha256(png).hexdigest()
    REPORT['screens'].append(record);return record


def main():
    if adb('shell','getprop','ro.kernel.qemu').strip()!='1':raise RuntimeError('not_an_emulator')
    if PACKAGE in adb('shell','pm','list','packages',PACKAGE):raise RuntimeError('requires_fresh_emulator_no_existing_app_data')
    tmp=Path(os.environ['RUNNER_TEMP']);install=json.loads((tmp/'only-assist-install.json').read_text())
    paths=[Path(x) for x in install['files']];launcher=install['launcher']
    if not 1<=len(paths)<=8 or any(p.parent!=tmp/'only-assist-apks' or not re.fullmatch(r'part-\d+\.apk',p.name) for p in paths):
        raise RuntimeError('unexpected_install_files')
    if not re.fullmatch(r'[A-Za-z0-9_.$]+',launcher):raise RuntimeError('invalid_launcher')
    REPORT['sdk']=adb('shell','getprop','ro.build.version.sdk').strip()
    REPORT['abilist']=adb('shell','getprop','ro.product.cpu.abilist').strip()
    result=adb('install-multiple','--no-streaming',*(str(p) for p in paths),timeout=150)
    REPORT['install_success']='Success' in result
    if not REPORT['install_success']:raise RuntimeError('apk_install_unsuccessful')
    REPORT['apk_sha256']=[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
    adb('shell','am','start','-W','-n',PACKAGE+'/'+launcher);REPORT['app_launched']=True
    time.sleep(15);first=inspect('startup')
    if not first['owned_elements_count']:
        time.sleep(20);first=inspect('startup-waited')
    discounts=[n for n in first['owned_elements'] if n['text'].strip().casefold() in ('скидки','discounts')]
    if len(discounts)==1 and not first['login_marker']:
        b=re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',discounts[0]['bounds'])
        if b:
            x1,y1,x2,y2=map(int,b.groups());adb('shell','input','tap',str((x1+x2)//2),str((y1+y2)//2))
            time.sleep(10);inspect('discounts-tab')
    REPORT['outcome']=('login_required' if any(s['login_marker'] for s in REPORT['screens']) else
                       'ui_readable_not_catalogue_verified' if first['owned_elements_count'] else 'ui_not_readable')


if __name__=='__main__':
    OUT.mkdir(exist_ok=True)
    try:main()
    except Exception as e:REPORT['error']=str(e) if isinstance(e,RuntimeError) else type(e).__name__
    finally:
        (OUT/'ui_report.json').write_text(json.dumps(REPORT,ensure_ascii=False,indent=2))
        print(json.dumps(REPORT,ensure_ascii=False,indent=2))
