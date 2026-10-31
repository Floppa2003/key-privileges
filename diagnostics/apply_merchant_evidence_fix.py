"""One-time cache boundary refinement; removed before merge."""
from pathlib import Path


def replace(path,old,new):
    p=Path(path);text=p.read_text()
    if text.count(old)!=1:raise RuntimeError('patch_context_mismatch '+path+' '+old[:60])
    p.write_text(text.replace(old,new))

q='loyalty/merchant_queue.py';e='loyalty/merchant_evidence.py'
replace(q,"extractor.build_request(target, document['text'], document['images'], schema, system)",
          "extractor.build_request(target, evidence.fingerprint_text(document), document['images'], schema, system)")
replace(q,"    text += evidence.snapshot_text(target)\n    spec = store", "    context_start = len(text)\n    text += evidence.snapshot_text(target)\n    spec = store")
replace(q,"    return evidence.attach_snapshot(spec, target, out)", "    if target.get('source_records'):\n        spec['collector_context_start'] = context_start\n    return evidence.attach_snapshot(spec, target, out)")
replace(e,"VERSION = 1", """VERSION = 1
SNAPSHOT_HEADER = ('\\n\\nCOLLECTOR_SNAPSHOT — ранее полученные данные, дата наблюдения указана в observed_at.\\n'
                   'Это контекст сборщика, не новая проверка актуальности. Нормализованные поля не являются дословными цитатами; '
                   'исходные объекты находятся в details. При расхождении с текущим источником сохрани неопределённость.\\n')""")
replace(e,"""    return ('\n\nCOLLECTOR_SNAPSHOT — ранее полученные данные, дата наблюдения указана в observed_at.\n'
            'Это контекст сборщика, не новая проверка актуальности. Нормализованные поля не являются дословными цитатами; '
            'исходные объекты находятся в details. При расхождении с текущим источником сохрани неопределённость.\n'
            + json.dumps(rows, ensure_ascii=False, indent=2, allow_nan=False))""".replace("'\n\nCOLLECTOR", "'\\n\\nCOLLECTOR").replace("observed_at.\n'","observed_at.\\n'").replace("неопределённость.\n'","неопределённость.\\n'"),
        "    return SNAPSHOT_HEADER + json.dumps(rows, ensure_ascii=False, indent=2, allow_nan=False, sort_keys=True)")
replace(e,"json.dumps(items, ensure_ascii=False, indent=2, allow_nan=False)","json.dumps(items, ensure_ascii=False, indent=2, allow_nan=False, sort_keys=True)")
p=Path(e)
p.write_text(p.read_text()+'''

def fingerprint_text(document: dict) -> str:
    """Ignore collection bookkeeping only in our explicitly bounded JSON appendix.

    Actual input/attachments retain every original field. Source dates, IDs,
    conditions, normalized values and the complete live page still invalidate
    the cache. A malformed boundary conservatively uses the exact original.
    """
    text = document['text']
    start = document.get('source', {}).get('collector_context_start')
    if type(start) is not int or not 0 <= start <= len(text):
        return text
    suffix = text[start:]
    if not suffix.startswith(SNAPSHOT_HEADER):
        return text
    try:
        rows = json.loads(suffix[len(SNAPSHOT_HEADER):])
        if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
            return text
        for row in rows:
            row.pop('observed_at', None)
            details = row.get('details')
            if isinstance(details, dict):
                for key in ('source_run', 'capture_sha256'):
                    details.pop(key, None)
        return text[:start] + SNAPSHOT_HEADER + json.dumps(rows, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
    except (ValueError, TypeError):
        return text
''')
print('Canonical fingerprints preserve original model inputs and source dates.')
