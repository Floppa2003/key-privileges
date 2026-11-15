"""Retain public PDF identity metadata before mutable offer rows are replaced.

The existing private archive is owner-created. Legacy archive rows (including
manual cells) are never rewritten. Explicitly owned metadata rows keep the latest
observation of the same bytes without growing on each daily collection.
Like the other Sheet writers, this relies on the shared workflow lock; Sheets
has no conditional append, so read checks cannot exclude edits after preflight.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json

from document_catalogue import ARCHIVE_TAB, document_sources, _time
from model import cell
from sheets_sync import Sheets
from unified_inputs import HEADERS

ARCHIVE_HEADERS = HEADERS['parser_offers'] + [
    'Исходная строка parser_offers', 'Архивировано UTC']


class DocumentArchiveSheets(Sheets):
    schemas = {ARCHIVE_TAB: ARCHIVE_HEADERS}


def metadata_row(row, source_row, stamp):
    padded = (row + [''] * 25)[:25]
    if not padded[0]:
        return None
    details = json.loads(padded[20] or '{}')
    if not isinstance(details, dict):
        raise ValueError('Document source details changed')
    sources = document_sources([{
        'id': padded[0], 'program': padded[1], 'partner': padded[2],
        'title': padded[3], 'source_url': padded[17], 'benefit_url': padded[16],
        'observed_at': padded[22], 'source_status': padded[15], 'details': details}])
    if not sources:
        return None
    source = sources[0]
    # An explicit allowlist: pages, tables, extracted prose, codes, notes and
    # arbitrary parser details cannot pass through into new archive records.
    retained = {
        'archive_metadata_version': 1,
        'document_sha256': source['sha256'], 'public_aliases': source['urls'],
        'discovery_labels': source['labels'], 'extraction_method': source['method'],
        'ocr_pages': int(source['ocr']), 'document_text_incomplete': source['incomplete']}
    result = [''] * 28
    result[:6] = [padded[0], source['program'], source['partner'], source['title'],
                  padded[4], padded[5]]
    for index in (15, 16, 17, 18, 22):
        result[index] = padded[index]
    result[20] = json.dumps(retained, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    result[26:28] = [str(source_row or ''), stamp]
    for value in result:
        cell(value)
    return (padded[0], source['sha256']), result


def retain_documents(client, before_offers, incoming):
    """Verify immutable identities and current metadata before offer overwrite."""
    stamp = datetime.now(timezone.utc).isoformat()
    candidates = [item for item in
        [metadata_row(row, number, stamp) for number, row in enumerate(before_offers[1:], 2)] +
        [metadata_row(row, '', stamp) for row in incoming] if item is not None]
    if not candidates:
        return 0

    def snapshot():
        meta = client.metadata()
        props = meta.get(ARCHIVE_TAB)
        if '_ui_catalog' not in meta or props is None or not props.get('hidden'):
            raise ValueError('Document source archive ownership changed')
        grid = props['gridProperties']
        if not 1 <= grid['rowCount'] <= 5000 or grid['columnCount'] != 28:
            raise ValueError('Document source archive dimensions changed')
        rows = client.values(ARCHIVE_TAB, props)
        if not rows or rows[0] != ARCHIVE_HEADERS:
            raise ValueError('Document source archive header changed')
        return props, rows

    props, before = snapshot()
    managed = {}
    for number, row in enumerate(before[1:], 1):
        item = metadata_row(row, '', stamp)
        if item is not None and json.loads(row[20]).get('archive_metadata_version') == 1:
            if item[0] in managed:
                raise ValueError('Duplicate owned document metadata identity')
            managed[item[0]] = number
    latest = {}
    for identity, row in candidates:
        if identity not in latest or _time(row[22]) >= _time(latest[identity][22]):
            latest[identity] = row
    appended = []
    updated = []
    expected = [(row + [''] * 28)[:28] for row in before]
    for identity, row in latest.items():
        if identity not in managed:
            appended.append(row)
            continue
        number = managed[identity]
        original = expected[number]
        if _time(row[22]) < _time(original[22]):
            continue
        if row[:25] != original[:25]:
            updated.append((number, row[:25]))
            expected[number][:25] = row[:25]
    if not appended and not updated:
        return 0
    end = len(before) + len(appended)
    if end > 5000:
        raise ValueError('Document source archive capacity exceeded')
    current_props, current = snapshot()
    if current_props != props or current != before:
        raise ValueError('Concurrent archive edit; refusing stale append')
    requests = []
    if end > props['gridProperties']['rowCount']:
        requests.append({'appendDimension': {'sheetId': props['sheetId'],
            'dimension': 'ROWS', 'length': end - props['gridProperties']['rowCount']}})
    for number, row in updated:
        requests.append({'updateCells': {'start': {'sheetId': props['sheetId'],
            'rowIndex': number, 'columnIndex': 0},
            'rows': [{'values': [cell(value) for value in row]}],
            'fields': 'userEnteredValue'}})
    if appended:
        requests.append({'appendCells': {'sheetId': props['sheetId'],
            'rows': [{'values': [cell(value) for value in row]} for row in appended],
            'fields': 'userEnteredValue'}})
    # Bounded by the 5000-row grid and each literal cell's existing 40k bound.
    if len(json.dumps(requests, ensure_ascii=False).encode()) > 8000000:
        raise ValueError('Document source archive append exceeds safe request size')
    client.request('POST', ':batchUpdate', json={'requests': requests})
    after_props, after = snapshot()
    expected_props = dict(props, gridProperties=dict(props['gridProperties'],
        rowCount=max(end, props['gridProperties']['rowCount'])))
    padded = lambda rows: [(row + [''] * 28)[:28] for row in rows]
    if after_props != expected_props or padded(after) != expected + appended:
        raise ValueError('Document source archive readback mismatch; no offers update')
    return len(appended) + len(updated)
