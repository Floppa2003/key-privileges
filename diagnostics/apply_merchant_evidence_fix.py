"""One-time source transformation for the isolated fix branch; removed before merge."""
from pathlib import Path


def replace(path, old, new):
    p=Path(path); text=p.read_text()
    if text.count(old)!=1:raise RuntimeError('patch_context_mismatch: '+path+' '+old[:65])
    p.write_text(text.replace(old,new))

q='loyalty/merchant_queue.py'
replace(q,'import asyncio\n','import asyncio\nimport copy\n')
replace(q,'import merchant_extract as extractor\n','import merchant_extract as extractor\nimport merchant_evidence as evidence\n')
replace(q,"'program': r.get('program'), 'source_id': r.get('source_id')}\n", "'program': r.get('program'), 'source_id': r.get('source_id'),\n                       'source_records': [copy.deepcopy(r)]}\n")
replace(q,"        result.setdefault(ident, {'id': ident, 'url': url, 'partner': partner.strip(),\n                                  'program': program.strip(), 'source_id': candidate.get('source_id')})", """        target = result.setdefault(ident, {'id': ident, 'url': url, 'partner': partner.strip(),
                                  'program': program.strip(), 'source_id': candidate.get('source_id')})
        for row in candidate.get('source_records', []):
            records = target.setdefault('source_records', [])
            if row not in records:
                records.append(copy.deepcopy(row))
            target['source_id'] = row.get('source_id') or target.get('source_id')""")
replace(q,"        item['target'] = target\n", "        evidence.merge_target(item, target)\n")
replace(q,"        digest = fingerprint(document, schema, system)\n        if item.get('fingerprint') == digest and 'extracted' in item:", """        if not evidence.input_ready(document):
            item.update(status='needs_source', needs_recapture=True, last_checked=now())
            summary['status'] = 'incomplete'
            summary['results'].append({'id': ident, 'status': 'needs_source', 'http_attempts': 0})
            write_state(state_path, state)
            continue
        digest = fingerprint(document, schema, system)
        if evidence.cache_usable(item, document, digest):""")
replace(q,"        if result['status'] == 'completed':\n            item.update(fingerprint=digest,", """        if result['status'] == 'completed':
            item.update(needs_recapture=False,
                        inferred_evidence_version=document.get('source', {}).get('evidence_version', 0),
                        input_scope=copy.deepcopy(document.get('source', {}).get('capture_scope', {})))
            item.update(fingerprint=digest,""")
replace(q,"        return 'extracted' in item and item.get('fingerprint') == fingerprint(document, schema, system)", "        return evidence.cache_usable(item, document, fingerprint(document, schema, system))")
replace(q,"if row['status'] in ('failed_validation', 'transport_error'))", "if row['status'] in ('failed_validation', 'transport_error', 'needs_source'))")
replace(q,"    from public_transport import PublicSource, check_response\n    ident, url = target['id'], target['url']", """    from public_transport import PublicSource, check_response
    from merchant_konsierge_capture import handles, capture
    if handles(target):
        return await capture(browser, target, out)
    ident, url = target['id'], target['url']""")
replace(q,"    return store(out, ident, {'partner': target['partner'], 'program': target['program'],\n                                  'as_of': datetime.now(timezone.utc).date().isoformat()},\n                     text, images, source_url=url)", """    # Keep the live page and the already acquired, explicitly dated collector
    # material in the same model call. Never silently throw away the latter.
    text += evidence.snapshot_text(target)
    spec = store(out, ident, {'partner': target['partner'], 'program': target['program'],
                                  'as_of': datetime.now(timezone.utc).date().isoformat()},
                     text, images, source_url=url)
    return evidence.attach_snapshot(spec, target, out)""")
replace(q,"                    except Exception as exc:\n                        state['items'][ident].update(last_checked=time.time(), capture_status='failed',", """                    except Exception as exc:
                        if isinstance(exc, evidence.InputNotReady):
                            state['items'][ident].update(status='needs_source', needs_recapture=True)
                        state['items'][ident].update(last_checked=time.time(), capture_status='needs_source' if isinstance(exc, evidence.InputNotReady) else 'failed',""")
replace(q,"observations.append({'id': ident, 'status': 'failed', 'error_type': type(exc).__name__,", "observations.append({'id': ident, 'status': 'needs_source' if isinstance(exc, evidence.InputNotReady) else 'failed', 'error_type': type(exc).__name__,")

m='loyalty/merchant_extract.py'
replace(m,"        text = read(text_name).decode('utf-8')", """        for name in spec.get('attachments', []):
            read(name)  # original collector/native source objects share the hash contract
        text = read(text_name).decode('utf-8')""")

e='loyalty/merchant_evidence.py'
replace(e,"        item.update(status='needs_source', needs_recapture=True,", """        if not item.get('needs_recapture'):
            item['last_checked'] = 0  # first recovery joins unseen work; failures rotate normally
        item.update(status='needs_source', needs_recapture=True,""")

print('Applied queue/source fix; no prompt, provider, quota, schedule or publication changes.')
