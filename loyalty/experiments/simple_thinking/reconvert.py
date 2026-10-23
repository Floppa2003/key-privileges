"""Isolate converter thinking on the unchanged think-on descriptions from the first run."""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import probe

SOURCE_SHA = '49339414cc352907c7c3542e9dc979ad4e96a401'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--ollama', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists() or not args.ollama.is_file():
        parser.error('existing_output_or_missing_ollama')
    specs = {c['id']: c for c in json.loads((probe.HERE / 'plan.json').read_text())['cases']}
    if args.case not in specs or (args.source / 'commit.txt').read_text().strip() != SOURCE_SHA:
        parser.error('source_identity_mismatch')
    files = json.loads((args.source / 'SHA256SUMS.json').read_text())
    prefix = 'results/think_on/'
    names = [prefix + 'description/answer.txt', prefix + 'description/measurement.json', prefix + 'structure/request.json']
    raw = {name: probe.frozen_io.checked_bytes(args.source, name, files[name]) for name in names}
    if json.loads(raw[names[1]])['status'] != 'completed':
        raise ValueError('source_description_failed')
    baseline = json.loads(raw[names[2]])
    description = raw[names[0]].decode('utf-8')
    if baseline['think'] is not False or 'images' in baseline['messages'][-1]:
        raise ValueError('unexpected_converter_input')
    if json.loads(baseline['messages'][-1]['content'])['description'] != description:
        raise ValueError('description_not_preserved')
    args.out.mkdir(parents=True)
    probe.common.save(args.out / 'source.json', {'source_execution': SOURCE_SHA,
        'source_files': {n: files[n] for n in names}, 'only_request_change': '/think',
        'case': args.case, 'publication_allowed': False})
    (args.out / 'description.txt').write_bytes(raw[names[0]])
    rows = []
    for think in specs[args.case]['order']:
        request = copy.deepcopy(baseline)
        request['think'] = think
        mode = 'converter_on' if think else 'converter_off'
        print('START', args.case, mode, flush=True)
        row = probe.infer(request, args.ollama.resolve(), args.out / mode)
        row.update(case=args.case, mode=mode, stage='structure')
        rows.append(row)
        probe.common.save(args.out / 'summary.json', rows)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    return 0 if all(r['status'] == 'completed' for r in rows) else 2


if __name__ == '__main__':
    raise SystemExit(main())
