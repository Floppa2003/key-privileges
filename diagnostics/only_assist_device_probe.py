"""Inspect an already-open Only Assist screen on an explicitly authorized Android.

No install, launch, taps, login, root, app-data reads, logs or network capture.
Default: readiness summary only. --capture requires an exact top-screen title.
Private captures stay outside Git working trees; stdout never contains UI text.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
import unicodedata
import uuid
import xml.etree.ElementTree as ET

PACKAGE = 'com.konsierge.assist.only'
FIELDS = ('text', 'content-desc', 'resource-id', 'class', 'bounds', 'clickable', 'selected')


class ProbeError(RuntimeError):
    pass


def compact(value: str) -> str:
    return ' '.join(unicodedata.normalize('NFKC', value).split())


def bounds(value: str) -> tuple[int, int, int, int]:
    match = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', value)
    if not match:
        raise ProbeError('invalid_screen_bounds')
    return tuple(map(int, match.groups()))


def select_device(output: str, requested: str | None) -> str:
    devices = {}
    for line in output.splitlines():
        if line.startswith(('List of devices', '*')) or not line.strip():
            continue
        parts = line.split()
        if len(parts) >= 2:
            devices[parts[0]] = parts[1]
    if requested is not None:
        if requested not in devices:
            raise ProbeError('selected_device_not_connected')
        if devices[requested] != 'device':
            raise ProbeError('selected_device_' + devices[requested])
        return requested
    if len(devices) != 1:
        raise ProbeError('no_device' if not devices else 'multiple_devices_select_explicitly')
    serial, state = next(iter(devices.items()))
    if state != 'device':
        raise ProbeError('device_' + state)
    return serial


def resumed_package(output: str) -> str | None:
    lines = [line for line in output.splitlines()
             if re.match(r'\s*(?:mResumedActivity|topResumedActivity)\s*[:=]', line)]
    packages = {m[1] for line in lines
                if (m := re.search(r'\bu\d+\s+([A-Za-z0-9_.]+)/', line))}
    return next(iter(packages)) if len(packages) == 1 else None


def screen_labels(xml: str, expected_title: str) -> dict:
    if len(xml.encode('utf-8')) > 2_000_000 or '<!DOCTYPE' in xml or '<!ENTITY' in xml:
        raise ProbeError('invalid_or_large_screen_xml')
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        raise ProbeError('screen_xml_parse_failed') from None
    visible = [n for n in root.iter('node') if n.get('visible-to-user') != 'false']
    owned = [n for n in visible if n.get('package') == PACKAGE]
    if not owned:
        raise ProbeError('no_only_assist_elements')
    # A system dialog, keyboard or another app invalidates a content capture.
    if any(n.get('package') not in ('', None, PACKAGE) for n in visible):
        raise ProbeError('another_package_in_screen_tree')
    texts = {compact(n.get('text', '')).casefold() for n in owned}
    if texts & {'alfa id', 'альфа id', 'войти', 'авторизация', 'добро пожаловать'}:
        raise ProbeError('login_required')
    sensitive = {id(n) for n in owned
                 if n.get('password') == 'true' or n.get('class', '').endswith('EditText')}
    if any(n.get('password') == 'true' for n in owned):
        raise ProbeError('password_element_present')
    frames = [bounds(n.get('bounds', '')) for n in owned]
    top, bottom = min(b[1] for b in frames), max(b[3] for b in frames)
    if bottom <= top:
        raise ProbeError('invalid_screen_extent')
    expected = compact(expected_title)
    if not expected or len(expected) > 150:
        raise ProbeError('invalid_expected_title')
    titles = [n for n in owned if compact(n.get('text', '')) == expected
              and bounds(n.get('bounds', ''))[1] <= top + (bottom - top) * 0.22]
    if not titles:
        raise ProbeError('expected_top_title_not_visible')
    labels = []
    for node in owned:
        # Never retain input values, or an ancestor's aggregated input description.
        if any(id(child) in sensitive for child in node.iter()):
            continue
        if not (node.get('text') or node.get('content-desc')):
            continue
        x1, y1, x2, y2 = bounds(node.get('bounds', ''))
        if x2 <= x1 or y2 <= y1:
            continue
        labels.append({key: node.get(key, '') for key in FIELDS})
    return {'elements': labels, 'element_count': len(labels),
            'webview_present': any('WebView' in n.get('class', '') for n in owned),
            'screen_scope': 'one_visible_screen_only', 'catalogue_complete': False}


class Adb:
    def __init__(self, executable: str, serial: str | None = None):
        self.executable, self.serial = executable, serial

    def run(self, *args: str, timeout: int = 30) -> str:
        command = [self.executable]
        if self.serial:
            command += ['-s', self.serial]
        try:
            result = subprocess.run(command + list(args), capture_output=True,
                                    text=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            raise ProbeError('adb_timeout') from None
        except OSError:
            raise ProbeError('adb_not_executable') from None
        if result.returncode:
            raise ProbeError('adb_command_failed')
        return result.stdout

    def capture(self, expected_title: str) -> dict:
        def foreground():
            if resumed_package(self.run('shell', 'dumpsys', 'activity', 'activities')) != PACKAGE:
                raise ProbeError('only_assist_not_unambiguously_foreground')
        foreground()
        remote = '/data/local/tmp/only-assist-probe-' + uuid.uuid4().hex + '.xml'
        try:
            self.run('shell', 'uiautomator', 'dump', '--compressed', remote, timeout=45)
            xml = self.run('shell', 'cat', remote)
            foreground()
            return screen_labels(xml, expected_title)
        finally:
            # Delete only the unique temporary file created by this invocation.
            self.run('shell', 'rm', '-f', remote)


def save_private(report: dict, directory: Path) -> Path:
    directory = directory.expanduser()
    if directory.is_symlink():
        raise ProbeError('output_symlink_rejected')
    directory = directory.resolve()
    if any((parent / '.git').exists() for parent in (directory, *directory.parents)):
        raise ProbeError('private_output_inside_git_worktree')
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == 'posix' and directory.stat().st_mode & 0o077:
        raise ProbeError('private_output_directory_permissions')
    target = directory / ('screen-' + uuid.uuid4().hex + '.json')
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', default='adb')
    parser.add_argument('--serial', help='Select one authorized device; never written to reports')
    parser.add_argument('--capture', action='store_true')
    parser.add_argument('--expected-title', help='Exact title at the top of the already-open screen')
    parser.add_argument('--out-dir', type=Path, default=Path.home() / '.only-assist-private-probe')
    args = parser.parse_args()
    if args.capture and not args.expected_title:
        parser.error('--capture requires --expected-title')
    report = {'observed_at': datetime.now(timezone.utc).isoformat(), 'package': PACKAGE,
              'mode': 'capture' if args.capture else 'readiness', 'outcome': 'not_started',
              'login_attempted': False, 'device_actions': [], 'catalogue_records': 0,
              'catalogue_complete': False}
    try:
        executable = shutil.which(args.adb)
        if not executable:
            raise ProbeError('adb_not_installed')
        adb = Adb(executable)
        adb.serial = select_device(adb.run('devices'), args.serial)
        report['authorized_device_connected'] = True
        report['application_installed'] = adb.run('shell', 'pm', 'path', PACKAGE).startswith('package:')
        if not report['application_installed']:
            raise ProbeError('only_assist_not_installed')
        package = adb.run('shell', 'dumpsys', 'package', PACKAGE)
        version = re.search(r'\bversionName=([^\s]+)', package)
        if version:
            report['version_name'] = version[1]
        report['application_foreground'] = resumed_package(adb.run('shell', 'dumpsys', 'activity', 'activities')) == PACKAGE
        report['outcome'] = 'ready_for_explicit_screen_capture'
        if args.capture:
            report.update(adb.capture(args.expected_title))
            report['outcome'] = 'single_screen_captured_not_full_catalogue'
            path = save_private(report, args.out_dir)
            report['private_output'] = str(path)
        print(json.dumps({k: v for k, v in report.items() if k != 'elements'}, ensure_ascii=False, indent=2))
        return 0
    except ProbeError as exc:
        # Do not print XML, subprocess stderr, serial numbers or any account content.
        report.pop('elements', None)
        report['outcome'] = str(exc)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2


if __name__ == '__main__':
    sys.exit(main())
