#!/usr/bin/env python3
"""Resolution-only Qwen CPU benchmark. Plan by default; --execute performs inference.

Reuses the exact previously tested request templates and run_cpu.infer().
A new private Ollama process tree is used for each attempt, on the same machine.
No model calls, website reads, GitHub writes or publications occur in plan mode.
"""
from __future__ import annotations
import argparse
import base64
import copy
import csv
import hashlib
import io
import json
import os
import platform
import signal
import socket
import subprocess
import time
from pathlib import Path

from PIL import Image
import psutil
import requests
import run_cpu as old

ROOT = Path(__file__).resolve().parent
CASES = ['rzd_museum', 'golden_triangle', 'nevsky']
PORT = 11435  # Dedicated to this experiment; never touch the normal 11434 service.
BASE = f'http://127.0.0.1:{PORT}'
VERSION = '0.34.4'
DIGEST = '2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd'
old.BASE = BASE


def resized_images(images: list[bytes], edge: int) -> list[bytes]:
    """Preserve every page and aspect ratio; 0 means original; never upscale."""
    if edge < 0:
        raise ValueError('negative_image_edge')
    result = []
    for raw in images:
        with Image.open(io.BytesIO(raw)) as im:
            if edge == 0 or max(im.size) <= edge:
                result.append(raw)
                continue
            resized = im.copy()
            resized.thumbnail((edge, edge), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            resized.save(buf, format='PNG')
            result.append(buf.getvalue())
    return result


def make_plan(cases: list[str], sizes: list[int], repeats: int) -> list[dict]:
    plan = []
    for repeat in range(repeats):
        for index, case in enumerate(cases):
            offset = (index + repeat) % len(sizes)
            for edge in sizes[offset:] + sizes[:offset]:
                plan.append({'case': case, 'edge': edge, 'repeat': repeat + 1})
    return plan


def make_request(template: dict, images: list[bytes]) -> dict:
    result = copy.deepcopy(template)
    result['messages'][-1]['images'] = [base64.b64encode(x).decode('ascii') for x in images]
    return result


def verify_inputs() -> None:
    for name, expected in json.loads((ROOT / 'input-sha256.json').read_text()).items():
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f'input_hash_mismatch: {name}')
    for case in CASES:
        path = ROOT / 'inputs' / case
        manifest = json.loads((path / 'input-manifest.json').read_text())
        for page, expected in enumerate(manifest['image_sha256'], 1):
            old.verify((path / f'page-{page}.png').read_bytes(), expected)
        old.verify((path / 'visible-text.txt').read_bytes(), manifest['text_sha256'])
        request = json.loads((path / 'request-without-image-bytes.json').read_text())
        text = (path / 'visible-text.txt').read_bytes().decode('utf-8')
        if not request['messages'][-1]['content'].endswith(text):
            raise ValueError('template_does_not_contain_exact_source_text')


def process_env() -> dict:
    env = os.environ.copy()
    env.update(OLLAMA_HOST=f'127.0.0.1:{PORT}', OLLAMA_NO_CLOUD='1',
               OLLAMA_MODELS=str(ROOT / '.cache' / 'models'), OLLAMA_NUM_PARALLEL='1',
               OLLAMA_MAX_LOADED_MODELS='1', OLLAMA_CONTEXT_LENGTH='16384',
               CUDA_VISIBLE_DEVICES='', ROCR_VISIBLE_DEVICES='')
    return env


class Server:
    """Own only a fresh process group created by this program; always clean it up."""
    def __init__(self, binary: Path, log: Path):
        self.binary, self.log = binary, log
        self.process = self.handle = None
        self.client = requests.Session()
        self.client.trust_env = False

    def __enter__(self):
        try:
            with socket.socket() as sock:
                if sock.connect_ex(('127.0.0.1', PORT)) == 0:
                    raise RuntimeError(f'port_{PORT}_already_used; refusing_to_touch_existing_service')
            self.handle = self.log.open('wb')
            self.process = subprocess.Popen([str(self.binary), 'serve'], env=process_env(),
                                            stdout=self.handle, stderr=subprocess.STDOUT,
                                            start_new_session=True)
            for _ in range(60):
                if self.process.poll() is not None:
                    raise RuntimeError('ollama_start_failed; inspect_ollama.log')
                try:
                    response = self.client.get(BASE + '/api/version', timeout=1)
                    response.raise_for_status()
                    if response.json().get('version') != VERSION:
                        raise ValueError('ollama_version_mismatch')
                    return self
                except requests.RequestException:
                    time.sleep(0.5)
            raise RuntimeError('ollama_start_timeout')
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *args):
        if self.process is not None:
            # Ollama's model worker inherits this newly created session/group.
            for sig in (signal.SIGTERM, signal.SIGKILL):
                try:
                    os.killpg(self.process.pid, sig)
                except ProcessLookupError:
                    break
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
                if sig == signal.SIGTERM:
                    time.sleep(0.2)
            self.process.wait(timeout=5)
        if self.handle is not None:
            self.handle.close()
        self.client.close()


def check_runtime(server: Server) -> dict:
    def get(path):
        response = server.client.get(BASE + path, timeout=10)
        response.raise_for_status()
        return response.json()
    local = old.local_model(get('/api/tags'))
    if local.get('digest', '').removeprefix('sha256:') != DIGEST:
        raise ValueError('model_digest_mismatch; do_not_silently_change_the_model')
    if get('/api/ps').get('models'):
        raise ValueError('fresh_server_already_has_loaded_model')
    response = server.client.post(BASE + '/api/show', json={'model': old.MODEL}, timeout=10)
    response.raise_for_status()
    if 'vision' not in response.json().get('capabilities', []):
        raise ValueError('vision_not_supported')
    return {'version': VERSION, 'local_model': local, 'endpoint': BASE,
            'fresh_process_tree': True, 'cloud_disabled_by_environment': True,
            'publication_allowed': False}


def write_summary(rows: list[dict], out: Path) -> None:
    """Timeouts are not valid timings for computing an exact speedup."""
    fields = ['repeat','case','edge','status','seconds','input_s','generation_s','load_s',
              'work_s','peak_rss_GiB','input_tokens','output_tokens','cached_tokens',
              'speedup_work_vs_original','speedup_total_vs_original','quality_review']
    baseline = {(r['repeat'], r['case']): r for r in rows
                if r['edge'] == 0 and r['status'] == 'completed'}
    table = []
    for row in rows:
        record = {k: row.get(k) for k in fields}
        record['edge'] = row['edge'] or 'original'
        base = baseline.get((row['repeat'], row['case']))
        if (base and row['status'] == 'completed'
                and isinstance(base.get('work_s'), (int, float))
                and isinstance(row.get('work_s'), (int, float)) and row['work_s'] > 0):
            record['speedup_work_vs_original'] = round(base['work_s'] / row['work_s'], 3)
        if (base and row['status'] == 'completed'
                and isinstance(base.get('seconds'), (int, float))
                and isinstance(row.get('seconds'), (int, float)) and row['seconds'] > 0):
            record['speedup_total_vs_original'] = round(base['seconds'] / row['seconds'], 3)
        record['quality_review'] = 'pending'
        table.append(record)
    old.save(out / 'summary.json', {'publication_allowed': False, 'attempts': rows})
    with (out / 'summary.csv').open('w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fields)
        writer.writeheader()
        writer.writerows(table)


def execute_attempt(args, item: dict, out: Path) -> dict:
    edge, case = item['edge'], item['case']
    path = ROOT / 'inputs' / case
    template = json.loads((path / 'request-without-image-bytes.json').read_text())
    manifest = json.loads((path / 'input-manifest.json').read_text())
    originals = [(path / f'page-{n}.png').read_bytes() for n in range(1, manifest['pages'] + 1)]
    images = resized_images(originals, edge)
    request = make_request(template, images)
    trial = out / f"r{item['repeat']}-{case}-{edge or 'original'}"
    trial.mkdir()
    image_info = []
    for n, raw in enumerate(images, 1):
        (trial / f'page-{n}.png').write_bytes(raw)
        with Image.open(io.BytesIO(raw)) as im:
            image_info.append({'page': n, 'size': list(im.size),
                               'sha256': hashlib.sha256(raw).hexdigest()})
    old.save(trial / 'input.json', {'source_manifest': manifest, 'images': image_info,
                                  'all_pages_sent': True, 'only_request_change': 'image_bytes'})
    with Server(args.ollama, trial / 'ollama.log') as server:
        old.save(trial / 'runtime.json', check_runtime(server))
        result = old.infer(server.client, request, trial, server.process.pid)
    status = 'completed' if result.get('schema_valid') else 'failed'
    if result.get('error_type') in ('ReadTimeout', 'Timeout'):
        status = 'timeout'
    if result.get('returned_model') not in (None, old.MODEL):
        status = 'model_mismatch'
    if status == 'completed' and result.get('vram_bytes') != [0]:
        status = 'cpu_not_verified'
    cached = None
    if (trial / 'response.json').exists():
        try:
            cached = json.loads((trial / 'response.json').read_bytes()).get('prompt_eval_cached_count')
        except (ValueError, UnicodeDecodeError):
            pass
    if cached not in (None, 0):
        status = 'unexpected_cache_hit'
    row = {**item, 'status': status, 'seconds': result['seconds'], 'cached_tokens': cached,
           'peak_rss_GiB': result['peak_sum_rss_bytes'] / 2**30,
           'input_tokens': result.get('returned_prompt_eval_count'),
           'output_tokens': result.get('returned_eval_count'),
           'publication_allowed': False}
    for metric, key in [('input_s','prompt_eval_duration'),('generation_s','eval_duration'),('load_s','load_duration')]:
        value = result.get('returned_' + key)
        row[metric] = value / 1e9 if isinstance(value, (int, float)) else None
    row['work_s'] = (row['input_s'] + row['generation_s']) if row['input_s'] is not None and row['generation_s'] is not None else None
    old.save(trial / 'measurement.json', row)
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', help='Run inference; otherwise print the plan only')
    parser.add_argument('--sizes', nargs='+', default=['original','1024','768'])
    parser.add_argument('--repeats', type=int, default=1)
    parser.add_argument('--out', type=Path, default=ROOT/'results')
    parser.add_argument('--ollama', type=Path, default=ROOT/'.tools/ollama/bin/ollama')
    args = parser.parse_args()
    sizes = [0 if value == 'original' else int(value) for value in args.sizes]
    if not sizes or any(x not in (0,1024,768) for x in sizes) or len(set(sizes)) != len(sizes) or not 1 <= args.repeats <= 3:
        parser.error('sizes: original/1024/768, distinct; repeats: 1..3')
    verify_inputs()
    plan = make_plan(CASES, sizes, args.repeats)
    if not args.execute:
        print(json.dumps({'inference_executed':False,'requests':len(plan),'plan':plan}, ensure_ascii=False, indent=2))
        return 0
    if platform.system() != 'Linux':
        parser.error('This controlled CPU runner targets Linux')
    if not args.ollama.is_file():
        parser.error('Ollama binary missing: run bash setup.sh first')
    if args.out.exists():
        parser.error('Output path exists; choose a NEW --out to preserve prior attempts')
    args.out.mkdir(parents=True)
    old.save(args.out/'plan.json', plan)
    old.save(args.out/'host.json', {'platform':platform.platform(), 'cpu_count':os.cpu_count(),
                                  'ram_bytes':psutil.virtual_memory().total, 'repeats':args.repeats,
                                  'policy':'fresh_process_per_attempt; process/model caches reset; OS cache not flushed',
                                  'publication_allowed':False})
    rows=[]
    try:
        for item in plan:
            print('START', item, flush=True)
            row=execute_attempt(args,item,args.out)
            rows.append(row)
            write_summary(rows,args.out)
            print(json.dumps(row,ensure_ascii=False),flush=True)
    except Exception as exc:
        old.save(args.out/'error.json', {'error_type':type(exc).__name__, 'error':str(exc),
                                       'completed_attempts':len(rows), 'publication_allowed':False})
        write_summary(rows,args.out)
        raise
    return 0 if all(x['status']=='completed' for x in rows) else 2

if __name__=='__main__':
    raise SystemExit(main())
