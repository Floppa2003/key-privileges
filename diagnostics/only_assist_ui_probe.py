"""Read Only Assist on a fresh disposable emulator, never authenticate.

This is a compatibility probe, not a catalogue collector. Do not run this on a
personal device: it intentionally requires a fresh emulator and installs the APK.
"""
from __future__ import annotations
import hashlib, json, os, re, subprocess, time
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone

PACKAGE = 'com.konsierge.assist.only'
SERIAL = 'emulator-5554'
OUT = Path('only-assist-evidence')
REPORT = {'observed_at': datetime.now(timezone.utc).isoformat(), 'package': PACKAGE,
          'account_login_attempted': False, 'credentials_entered': False,
          'catalogue_records': 0, 'screens': []}


def adb(*args, timeout=40, binary=False):
    p = subprocess.run(['adb', '-s', SERIAL, *args], capture_output=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError('adb_failed:' + (args[0] if args else 'unknown'))
    return p.stdout if binary else p.stdout.decode(errors='replace')


def inspect(name):
    adb('shell', 'uiautomator', 'dump', '/sdcard/only-assist-probe.xml', timeout=45)
    raw = adb('shell', 'cat', '/sdcard/only-assist-probe.xml')
    root = ET.fromstring(raw)
    nodes = []
    for node in root.iter('node'):
        if node.get('package') != PACKAGE:
            continue
        # EditText values are never retained, even on a fresh emulator.
        if node.get('password') == 'true' or node.get('class', '').endswith('EditText'):
            continue
        row = {k: node.get(k, '') for k in ('text', 'content-desc', 'resource-id', 'class', 'bounds', 'clickable')}
        if row['text'] or row['content-desc']:
            nodes.append(row)
    words = '\n'.join(n['text'] + ' ' + n['content-desc'] for n in nodes)
    record = {'name': name, 'observed_at': datetime.now(timezone.utc).isoformat(),
              'owned_elements': nodes, 'owned_elements_count': len(nodes),
              'login_marker': bool(re.search(r'alfa\s*id|альфа\s*id|авторизац|войти|вход|номер телефона', words, re.I)),
              'discounts_marker': bool(re.search(r'скидки|discounts', words, re.I)),
              'webview_present': any('WebView' in n.get('class', '') for n in root.iter('node'))}
    # Only these deliberately account-free emulator screens may enter public evidence.
    if nodes:
        png = adb('exec-out', 'screencap', '-p', binary=True)
        file = name + '.png'; (OUT / file).write_bytes(png)
        record['screenshot'] = file
        record['screenshot_sha256'] = hashlib.sha256(png).hexdigest()
    REPORT['screens'].append(record)
    return record


def main():
    if adb('shell', 'getprop', 'ro.kernel.qemu').strip() != '1':
        raise RuntimeError('not_an_emulator')
    if PACKAGE in adb('shell', 'pm', 'list', 'packages', PACKAGE):
        raise RuntimeError('requires_fresh_emulator_no_existing_app_data')
    tmp = Path(os.environ['RUNNER_TEMP'])
    apk = tmp / 'only-assist.apk'
    launcher = (tmp / 'only-assist-launcher.txt').read_text().strip()
    if not re.fullmatch(r'[A-Za-z0-9_.$]+', launcher):
        raise RuntimeError('invalid_launcher')
    REPORT['sdk'] = adb('shell', 'getprop', 'ro.build.version.sdk').strip()
    REPORT['abilist'] = adb('shell', 'getprop', 'ro.product.cpu.abilist').strip()
    install = adb('install', '--no-streaming', str(apk), timeout=120)
    REPORT['install_success'] = 'Success' in install
    if not REPORT['install_success']:
        raise RuntimeError('apk_install_unsuccessful')
    REPORT['apk_sha256'] = hashlib.sha256(apk.read_bytes()).hexdigest()
    adb('shell', 'am', 'start', '-W', '-n', PACKAGE + '/' + launcher)
    REPORT['app_launched'] = True
    time.sleep(15)
    first = inspect('startup')
    if not first['owned_elements_count']:
        time.sleep(20)
        first = inspect('startup-waited')
    # Only the Discounts tab may be opened. No login/registration/form submission.
    discounts = [n for n in first['owned_elements'] if n['text'].strip().casefold() in ('скидки', 'discounts')]
    if len(discounts) == 1 and not first['login_marker']:
        b = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', discounts[0]['bounds'])
        if b:
            x1,y1,x2,y2 = map(int,b.groups())
            adb('shell', 'input', 'tap', str((x1+x2)//2), str((y1+y2)//2))
            time.sleep(10)
            inspect('discounts-tab')
    REPORT['outcome'] = ('login_required' if any(s['login_marker'] for s in REPORT['screens'])
                         else 'ui_readable_not_catalogue_verified' if first['owned_elements_count']
                         else 'ui_not_readable')


if __name__ == '__main__':
    OUT.mkdir(exist_ok=True)
    try:
        main()
    except Exception as e:
        REPORT['error'] = str(e) if isinstance(e, RuntimeError) else type(e).__name__
    finally:
        (OUT / 'ui_report.json').write_text(json.dumps(REPORT, ensure_ascii=False, indent=2))
        print(json.dumps(REPORT, ensure_ascii=False, indent=2))
