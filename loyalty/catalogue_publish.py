"""Replace only the generated reader catalogue, never the five source datasets.

Called within the existing serialized private normalization publication. It
writes no local files, exposes no private contents in logs and performs full
readback. A failed rebuild leaves normalization unpublished, not a fresh success.
"""
from __future__ import annotations
import hashlib
import json
from urllib.parse import quote
from catalogue_view import build_catalogue, HEADERS, VERSION

TAB = '_ui_catalog'
STATE_RANGE = "'_ui_catalog'!Y1:Z8"
MAX_ROWS = 30001


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def literal(value):
    # Not USER_ENTERED: even a source string starting '=' remains literal text.
    return {'userEnteredValue': {'stringValue': str(value)}}


def read_values(client, a1):
    return client.request('GET', '/values/' + quote(a1, safe=''),
                          params={'valueRenderOption':'FORMULA'}).get('values', [])


def padded(rows, width):
    return [list(row) + [''] * (width-len(row)) for row in rows]


def prepare_catalogue(client, records, *, as_of, source_fingerprint, generation):
    meta = client.metadata()
    if TAB not in meta:
        return None  # A workbook without this owner-created UI is out of scope.
    props = meta[TAB]
    grid = props['gridProperties']
    if not 18 <= grid['columnCount'] <= 26 or not 9 <= grid['rowCount'] <= MAX_ROWS:
        raise ValueError('Unexpected reader catalogue dimensions')
    if grid['columnCount'] < 26:
        raise ValueError('Reader catalogue state columns missing')
    old = read_values(client, "'_ui_catalog'!A1:Q1")
    if old != [HEADERS]:
        raise ValueError('Unexpected reader catalogue header')
    result = build_catalogue(records, as_of=as_of)
    rows = [HEADERS] + result['rows']
    if len(rows) > grid['rowCount'] or not result['rows']:
        raise ValueError('Refusing empty or oversized reader catalogue')
    for row in rows:
        if len(row) != 17 or any(not isinstance(v,str) or len(v)>45000 for v in row):
            raise ValueError('Reader catalogue cell contract')
    state = [['Каталог',VERSION], ['Статус','verified'], ['Дата пересчёта',as_of],
             ['Записей',str(len(result['rows']))], ['Поколение',generation],
             ['SHA256',digest(rows)], ['Исходный снимок',source_fingerprint],
             ['Исключено',str(len(result['removed']))]]
    from ui_freshness import prepare_ui
    return {'properties':props,'rows':rows,'state':state,'counts':result['counts'],
            'ui':prepare_ui(client,meta,read_values)}


def verify_catalogue(client, plan):
    if plan is None:return
    from ui_freshness import verify_ui
    verify_ui(client,plan.get('ui'),read_values)
    actual = read_values(client, f"'_ui_catalog'!A1:Q{plan['properties']['gridProperties']['rowCount']}")
    if padded(actual,17) != plan['rows']:
        raise ValueError('Reader catalogue full readback mismatch')
    if read_values(client, STATE_RANGE) != plan['state']:
        raise ValueError('Reader catalogue state readback mismatch')
    if read_values(client, f"'_ui_catalog'!R1:X{plan['properties']['gridProperties']['rowCount']}"):
        raise ValueError('Obsolete raw catalogue helper remains')


def publish_catalogue(client, plan):
    if plan is None:return
    props = plan['properties']; sid = props['sheetId']
    # This is solely a generated projection. The outer manifest is publishing.
    client.request('POST',':batchUpdate',json={'requests':[{
        'updateCells':{'range':{'sheetId':sid,'startRowIndex':0,
            'endRowIndex':props['gridProperties']['rowCount'],
            'startColumnIndex':0,'endColumnIndex':26},
            'rows':[], 'fields':'userEnteredValue'}}]})
    batch=[]; size=0
    for i,row in enumerate(plan['rows']):
        operation={'updateCells':{'start':{'sheetId':sid,'rowIndex':i,'columnIndex':0},
                    'rows':[{'values':[literal(v) for v in row]}], 'fields':'userEnteredValue'}}
        weight=len(json.dumps(operation,ensure_ascii=False).encode())
        if batch and size+weight>800000:
            client.request('POST',':batchUpdate',json={'requests':batch})
            batch=[];size=0
        batch.append(operation);size+=weight
    if batch:client.request('POST',':batchUpdate',json={'requests':batch})
    client.request('POST',':batchUpdate',json={'requests':[{
        'updateCells':{'start':{'sheetId':sid,'rowIndex':0,'columnIndex':24},
            'rows':[{'values':[literal(v) for v in row]} for row in plan['state']],
            'fields':'userEnteredValue'}}]})
    from ui_freshness import apply_ui
    apply_ui(client,plan.get('ui'),read_values)
    verify_catalogue(client,plan)
