"""Test schema-in-prompt without decoder constraints; preserve every returned byte."""
import argparse
import copy
import json
from pathlib import Path
import probe

SOURCE_SHA = '49339414cc352907c7c3542e9dc979ad4e96a401'


def without_decoder_constraint(request):
    if request.get('think') is not True or not isinstance(request.get('format'), dict):
        raise ValueError('expected_thinking_schema_request')
    result = copy.deepcopy(request)
    result.pop('format')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--ollama', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists() or not args.ollama.is_file():
        parser.error('output_exists_or_binary_missing')
    if (args.source/'commit.txt').read_text().strip() != SOURCE_SHA:
        parser.error('source_execution_mismatch')
    manifest = json.loads((args.source/'SHA256SUMS.json').read_text())
    used = {}
    def read(name):
        used[name] = manifest[name]
        return probe.frozen_io.checked_bytes(args.source, name, manifest[name])
    prefix = 'results/think_on/'
    measurement = json.loads(read(prefix+'description/measurement.json'))
    if measurement['status'] != 'completed':
        raise ValueError('description_incomplete')
    description = read(prefix+'description/answer.txt').decode('utf-8')
    source_request = json.loads(read(prefix+'structure/request.json'))
    if json.loads(source_request['messages'][-1]['content'])['description'] != description:
        raise ValueError('description_changed')
    reference = probe.with_visible_schema(source_request)
    reference['think'] = True
    request = without_decoder_constraint(reference)
    args.out.mkdir(parents=True)
    probe.common.save(args.out/'reference-request.json', reference)
    probe.common.save(args.out/'source.json', {'execution':SOURCE_SHA, 'sha256':used,
                      'difference_from_visible_schema_thinking_request':'remove /format only',
                      'publication_allowed':False})
    (args.out/'description.txt').write_text(description, encoding='utf-8')
    result = probe.infer(request, args.ollama.resolve(), args.out/'unconstrained')
    if result['status'] == 'completed':
        try:
            raw = json.loads((args.out/'unconstrained/response.json').read_text())
            parsed = probe.common.parse_response(raw, reference['format'])
            probe.common.save(args.out/'unconstrained/extracted.json', parsed)
            result['schema_valid'] = True
        except ValueError as exc:
            result.update(status='json_validation_failed', schema_valid=False, validation_error=str(exc))
    probe.common.save(args.out/'summary.json', result)
    return 0 if result['status']=='completed' and result.get('schema_valid') else 2

if __name__ == '__main__':
    raise SystemExit(main())
