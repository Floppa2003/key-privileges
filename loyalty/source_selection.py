"""Select registered public routes; never accept arbitrary URLs or silent fallbacks."""
from __future__ import annotations
import argparse,json,re
from pathlib import Path


def select_sources(configs,spec=''):
    if not isinstance(spec,str):raise ValueError('source_selection_not_text')
    if not spec:return list(configs)
    ids=spec.split(',');known=[c['id'] for c in configs]
    if (not 1<=len(ids)<=128 or len(ids)!=len(set(ids))
        or any(not re.fullmatch(r'[a-z][a-z0-9_]{0,79}',i) for i in ids)
        or len(known)!=len(set(known)) or not set(ids)<=set(known)):
        raise ValueError('invalid_or_unregistered_source_selection')
    return [c for c in configs if c['id'] in ids]


def request_spec(path):
    ids=json.loads(Path(path).read_text(encoding='utf8')).get('source_ids',[])
    if not isinstance(ids,list) or any(not isinstance(i,str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,79}',i) for i in ids):
        raise ValueError('request_source_ids_not_string_list')
    return ','.join(ids)


if __name__=='__main__':
    parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--sources');group.add_argument('--request')
    args=parser.parse_args();spec=request_spec(args.request) if args.request else args.sources
    configs=json.loads(Path(__file__).with_name('sources_normalized.json').read_text())
    select_sources(configs,spec)
    print(spec)
