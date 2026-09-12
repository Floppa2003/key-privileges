"""Opt-in Google Sheets publisher. Only parser_inbox/parser_runs are writable.
Requires an OAuth access token obtained outside the browser collection job.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from urllib.parse import quote
import requests
from model import cell, make_record, is_offer, plan_rows, verify_rows

SCHEMAS = {
    'parser_inbox': ['ID', 'Источник', 'Заголовок страницы', 'Ссылка на карточку',
                     'Текст страницы — требует разбора', 'Статус', 'Получено UTC', 'SHA256 текста', 'Запуск'],
    'parser_runs': ['ID', 'Запуск', 'Источник', 'Статус сбора', 'Найдено ссылок',
                    'Сохранено страниц', 'Охват', 'Ошибки', 'Получено UTC'],
}


def prepare(bundle: dict) -> dict[str, list[list[str]]]:
    if bundle.get('schema_version') != 1 or not isinstance(bundle.get('run_id'), str) or len(bundle['run_id']) > 100:
        raise ValueError('Invalid bundle schema/run ID')
    cfgs = {c['id']: c for c in json.loads(Path(__file__).with_name('sources.json').read_text())}
    reports = {r['source']: r for r in bundle['sources']}
    if len(reports) != len(bundle['sources']) or set(reports) - set(cfgs):
        raise ValueError('Unexpected/duplicate source report')
    if len(bundle['records']) > 300:
        raise ValueError('Record bound exceeded')
    rows, ids, counts = [], set(), dict.fromkeys(reports, 0)
    for r in bundle['records']:
        cfg = cfgs.get(r['source'])
        if not cfg or not is_offer(r['url'], cfg) or r['source'] not in reports:
            raise ValueError('Record URL/source not allowlisted')
        checked = make_record(r['source'], r['url'], r['title'], r['terms'], r['observed_at'])
        if checked != r or r['id'] in ids or r['observed_at'] != bundle['observed_at']:
            raise ValueError('Inconsistent, duplicate or modified record')
        ids.add(r['id'])
        counts[r['source']] += 1
        rows.append([r['id'], cfg['name'], r['title'], r['url'], r['terms'],
                     'Автосбор: условия и актуальность требуют проверки', r['observed_at'], r['content_sha256'], bundle['run_id']])
    runs = []
    for source, r in reports.items():
        if r['record_count'] != counts[source] or (counts[source] and r['status'] != 'sample_collected'):
            raise ValueError('Report counts/status do not match records')
        runs.append([bundle['run_id'] + ':' + source, bundle['run_id'], cfgs[source]['name'], r['status'],
                     str(r['candidate_count']), str(r['record_count']), r['coverage'],
                     json.dumps(r['errors'], ensure_ascii=False), bundle['observed_at']])
    output = {'parser_inbox': rows, 'parser_runs': runs}
    for title, records in output.items():
        plan_rows([SCHEMAS[title]], records, len(SCHEMAS[title]))
    return output


class Sheets:
    def __init__(self, spreadsheet_id: str, token: str):
        if not spreadsheet_id or not token or any(x not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for x in spreadsheet_id):
            raise ValueError('Missing/invalid spreadsheet ID or Google access token')
        self.root = f'https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}'
        self.session = requests.Session()
        self.session.headers['Authorization'] = 'Bearer ' + token

    def request(self, method: str, suffix: str = '', **kwargs) -> dict:
        try:
            r = self.session.request(method, self.root + suffix, timeout=45, **kwargs)
        except requests.RequestException:
            raise RuntimeError('Google Sheets network failure; commit state must be checked before retry') from None
        if r.status_code >= 400:
            # Do not put bearer tokens, private sheet URLs or API response bodies in public CI logs.
            raise RuntimeError(f'Google Sheets HTTP {r.status_code}')
        return r.json()

    def metadata(self) -> dict:
        d = self.request('GET', params={'fields': 'sheets.properties(sheetId,title,gridProperties)'})
        return {s['properties']['title']: s['properties'] for s in d['sheets']}

    def values(self, title: str, props: dict) -> list[list]:
        n = props['gridProperties']['rowCount']
        if n > 5000 or props['gridProperties']['columnCount'] < 9:
            raise ValueError('Managed sheet outside safe dimensions')
        a1 = f"'{title}'!A1:I{n}"
        return self.request('GET', '/values/' + quote(a1, safe=''), params={'valueRenderOption': 'FORMULA'}).get('values', [])

    def ensure_tab(self, title: str) -> dict:
        if title not in SCHEMAS:
            raise ValueError('Refusing to write to a non-parser sheet')
        meta = self.metadata()
        if title not in meta:
            self.request('POST', ':batchUpdate', json={'requests': [{'addSheet': {'properties': {
                'title': title, 'gridProperties': {'rowCount': 1000, 'columnCount': 10, 'frozenRowCount': 1}}}}]})
            meta = self.metadata()
        props = meta[title]
        existing = self.values(title, props)
        if existing and existing[0] != SCHEMAS[title]:
            raise ValueError('Existing parser sheet has an unexpected schema; refusing overwrite')
        if not existing:
            sid = props['sheetId']
            self.request('POST', ':batchUpdate', json={'requests': [
                {'updateCells': {'range': {'sheetId':sid,'startRowIndex':0,'endRowIndex':1,'startColumnIndex':0,'endColumnIndex':10},
                                 'rows':[{'values':[cell(x) for x in SCHEMAS[title] + ['Ручной комментарий']]}], 'fields':'userEnteredValue'}},
                {'repeatCell': {'range': {'sheetId':sid,'startRowIndex':0,'endRowIndex':1,'startColumnIndex':0,'endColumnIndex':10},
                                'cell': {'userEnteredFormat': {'textFormat': {'bold':True},'wrapStrategy':'WRAP'}}, 'fields':'userEnteredFormat'}},
                {'updateDimensionProperties': {'range': {'sheetId':sid,'dimension':'COLUMNS','startIndex':0,'endIndex':10},
                                                'properties': {'pixelSize':180},'fields':'pixelSize'}},
                {'updateDimensionProperties': {'range': {'sheetId':sid,'dimension':'COLUMNS','startIndex':4,'endIndex':5},
                                                'properties': {'pixelSize':420},'fields':'pixelSize'}}]})
            if self.values(title, props)[0] != SCHEMAS[title]:
                raise ValueError('Header creation readback failed')
        return props

    def upsert(self, title: str, incoming: list[list[str]]) -> int:
        props = self.ensure_tab(title)
        before = self.values(title, props)
        changes = plan_rows(before, incoming, 9)
        if not changes:
            return 0
        end = max(n for n, _ in changes) + 1
        if end > 5000:
            raise ValueError('Managed sheet row bound exceeded')
        if self.values(title, props) != before:
            raise ValueError('Concurrent edit detected; refusing stale write')
        if end > props['gridProperties']['rowCount']:
            self.request('POST', ':batchUpdate', json={'requests':[{'appendDimension': {'sheetId':props['sheetId'],'dimension':'ROWS','length':end-props['gridProperties']['rowCount']}}]})
            props = self.metadata()[title]
        # Bounded requests; no clear/delete and no write to manual column J.
        batch, size = [], 0
        for n, row in changes:
            req = {'updateCells': {'range': {'sheetId':props['sheetId'],'startRowIndex':n,'endRowIndex':n+1,'startColumnIndex':0,'endColumnIndex':9},
                                   'rows':[{'values':[cell(x) for x in row]}], 'fields':'userEnteredValue'}}
            weight = len(json.dumps(req, ensure_ascii=False).encode())
            if batch and size + weight > 1000000:
                self.request('POST', ':batchUpdate', json={'requests':batch})
                batch, size = [], 0
            batch.append(req)
            size += weight
        if batch:
            self.request('POST', ':batchUpdate', json={'requests':batch})
        verify_rows(self.values(title, props), changes, 9)
        self.request('POST', ':batchUpdate', json={'requests':[{'setBasicFilter': {'filter': {'range': {
            'sheetId':props['sheetId'],'startRowIndex':0,'endRowIndex':max(len(before),end),'startColumnIndex':0,'endColumnIndex':10}}}}]})
        # Final value readback after the last material operation.
        verify_rows(self.values(title, props), changes, 9)
        return len(changes)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--input', default='loyalty-output/bundle.json')
    p.add_argument('--publish', action='store_true')
    args = p.parse_args()
    data = Path(args.input)
    if data.stat().st_size > 20000000:
        raise ValueError('Bundle size bound exceeded')
    rows = prepare(json.loads(data.read_text(encoding='utf-8')))
    if not args.publish:
        print(json.dumps({'mode':'dry_run','rows':{k:len(v) for k,v in rows.items()}}))
        return
    client = Sheets(os.environ.get('DISCOUNTS_SPREADSHEET_ID', ''), os.environ.get('GOOGLE_ACCESS_TOKEN', ''))
    verified = {name:client.upsert(name, values) for name,values in rows.items()}
    print(json.dumps({'mode':'published_and_readback_verified','changed_rows':verified}))

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Publication failed ({type(exc).__name__}); do not treat this run as a verified sync.')
        raise SystemExit(1)
