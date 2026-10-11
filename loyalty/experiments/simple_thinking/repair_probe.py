"""Diagnose missing prompt schema and a capped description; no source-specific extraction."""
from __future__ import annotations
import argparse
import base64
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
    parser.add_argument('--stage', choices=['converter', 'budget'], required=True)
    args = parser.parse_args()
    specs = {c['id']: c for c in json.loads((probe.HERE / 'plan.json').read_text())['cases']}
    if args.case not in specs or args.out.exists() or not args.ollama.is_file():
        parser.error('unknown_case_existing_output_or_missing_binary')
    if (args.source / 'commit.txt').read_text().strip() != SOURCE_SHA:
        parser.error('source_execution_mismatch')
    manifest = json.loads((args.source / 'SHA256SUMS.json').read_text())
    used = {}

    def read(name):
        used[name] = manifest[name]
        return probe.frozen_io.checked_bytes(args.source, name, manifest[name])

    args.out.mkdir(parents=True)
    prefix = 'results/think_on/description/'
    measurement = json.loads(read(prefix + 'measurement.json'))
    rows = []
    if args.stage == 'converter':
        if measurement['status'] != 'completed':
            raise ValueError('description_not_completed')
        description = read(prefix + 'answer.txt').decode('utf-8')
        original = json.loads(read('results/think_on/structure/request.json'))
        if json.loads(original['messages'][-1]['content'])['description'] != description:
            raise ValueError('description_changed')
        request = probe.with_visible_schema(original)
        probe.common.save(args.out / 'original-request.json', original)
    else:
        if measurement.get('done_reason') != 'length':
            raise ValueError('source_was_not_token_capped')
        request = json.loads(read(prefix + 'request.json'))
        if request['options']['num_predict'] != 4096 or request['think'] is not True or 'format' in request:
            raise ValueError('unexpected_description_request')
        probe.common.save(args.out / 'original-description-request.json', request)
        spec = json.loads(read('results/frozen-input.json'))
        images = []
        for index, source_name in enumerate(spec['images'], 1):
            raw = read(f'results/page-{index}.png')
            probe.common.verify(raw, spec['sha256'][source_name])
            (args.out / f'page-{index}.png').write_bytes(raw)
            images.append(base64.b64encode(raw).decode('ascii'))
        request['messages'][-1]['images'] = images
        request['options']['num_predict'] = 8192
        row = probe.infer(request, args.ollama.resolve(), args.out / 'description', max_seconds=1800)
        row.update(case=args.case, stage='description_extended_budget')
        rows.append(row)
        probe.common.save(args.out / 'summary.json', rows)
        if row['status'] != 'completed':
            probe.common.save(args.out / 'source.json', {'execution': SOURCE_SHA, 'sha256': used,
                              'conversion_skipped': True, 'publication_allowed': False})
            return 2
        description = (args.out / 'description/answer.txt').read_text()
        target_line = request['messages'][-1]['content'].split('\n', 1)[0]
        target = json.loads(target_line.removeprefix('TARGET: '))
        schema = json.loads(read('code/practical_schema.json'))
        request = probe.structure_request(request, target, description, schema)
        request['options']['num_predict'] = 4096
    (args.out / 'description.txt').write_text(description, encoding='utf-8')
    probe.common.save(args.out / 'source.json', {'execution': SOURCE_SHA, 'sha256': used,
                      'stage': args.stage, 'publication_allowed': False})
    for think in specs[args.case]['order']:
        payload = copy.deepcopy(request)
        payload['think'] = think
        mode = 'converter_on' if think else 'converter_off'
        print('START', args.case, mode, flush=True)
        row = probe.infer(payload, args.ollama.resolve(), args.out / mode)
        row.update(case=args.case, stage=mode)
        rows.append(row)
        probe.common.save(args.out / 'summary.json', rows)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    return 0 if all(r['status'] == 'completed' for r in rows) else 2


if __name__ == '__main__':
    raise SystemExit(main())
