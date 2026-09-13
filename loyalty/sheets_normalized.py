"""Publish normalized offers only to the two dedicated parser tabs."""
from __future__ import annotations
import argparse
import json
import os
from collections import Counter
from pathlib import Path
from normalized import validate_offer, VERSION
from model import plan_rows
from sheets_sync import Sheets

SCHEMAS = {
 'parser_offers':['ID','Программа','Партнёр','Заголовок','Категория','Тип записи','Типы выгод',
  'Выгода','Условия','Как получить','Промокоды JSON','Ставки JSON','Начало','Окончание',
  'Статус сроков','Статус источника','Ссылка на бенефит','Источник','Тип ссылки','Локатор',
  'Детали JSON','Ограничения JSON','Получено UTC','SHA256','Запуск'],
 'parser_coverage':['ID','Запуск','Источник','Программа','Корневая страница','Статус сбора',
  'Найдено','Нормализовано','Ошибок','Охват','Регион','Ошибки JSON','Получено UTC','Версия парсера'],
}


def dump(value) -> str:
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))


def prepare(bundle: dict) -> dict[str,list[list[str]]]:
    if bundle.get('schema_version')!=2 or not isinstance(bundle.get('run_id'),str) or not bundle['run_id'] or len(bundle['run_id'])>100:
        raise ValueError('Invalid normalized bundle identity')
    if not bundle.get('sources') or len(bundle['sources'])>128 or len(bundle.get('records',[]))>3000:
        raise ValueError('Bundle outside publication bounds')
    sources={r['source_id']:r for r in bundle['sources']}
    if len(sources)!=len(bundle['sources']):
        raise ValueError('Duplicate source report')
    counts=Counter();ids=set();offers=[]
    for r in bundle['records']:
        validate_offer(r)
        if r['id'] in ids or r['source_id'] not in sources or r['observed_at']!=bundle['observed_at']:
            raise ValueError('Duplicate or foreign observation')
        ids.add(r['id']);counts[r['source_id']]+=1
        offers.append([r['id'],r['program'],r['partner_name'] or '',r['title'],r['category'] or '',
          r['record_kind'],dump(r['benefit_types']),r['benefit_text'],r['conditions_text'],r['redemption_text'],
          dump(r['promo_codes']),dump(r['rates']),r['valid_from'] or '',r['valid_until'] or '',
          r['validity_status'],r['source_status'],r['benefit_url'] or '',r['source_url'],r['link_kind'],r['locator'],
          dump({'tables':r['tables'],**r['details']}),dump(r['warnings']),r['observed_at'],r['content_sha256'],bundle['run_id']])
    reports=[]
    for sid,r in sources.items():
        if r['normalized']!=counts[sid] or r['discovered']<counts[sid] or r['observed_at']!=bundle['observed_at']:
            raise ValueError('Source counts/time contradict normalized records')
        reports.append([bundle['run_id']+':'+sid,bundle['run_id'],sid,r['name'],r['root'],r['status'],
          str(r['discovered']),str(r['normalized']),str(r['failed']),r['coverage'],r['region'] or '',
          dump(r['errors']),r['observed_at'],VERSION])
    output={'parser_offers':offers,'parser_coverage':reports}
    for name,rows in output.items():
        plan_rows([SCHEMAS[name]],rows,len(SCHEMAS[name]))
    return output


class NormalizedSheets(Sheets):
    schemas=SCHEMAS


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',default='loyalty-output/normalized.json');p.add_argument('--publish',action='store_true');args=p.parse_args()
    path=Path(args.input)
    if path.stat().st_size>25000000:
        raise ValueError('Normalized bundle exceeds 25 MB')
    rows=prepare(json.loads(path.read_text()))
    if not args.publish:
        print(dump({'mode':'normalized_dry_run','rows':{k:len(v) for k,v in rows.items()}}));return
    client=NormalizedSheets(os.environ.get('DISCOUNTS_SPREADSHEET_ID',''),os.environ.get('GOOGLE_ACCESS_TOKEN',''))
    counts={name:client.upsert(name,values) for name,values in rows.items()}
    print(dump({'mode':'normalized_published_readback_verified','changed_rows':counts}))

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(f'Normalized publication failed ({type(exc).__name__}); not a verified sync.')
        raise SystemExit(1)
