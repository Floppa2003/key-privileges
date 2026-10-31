"""One-time, assertion-checked source transformation; removed before merge."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
p = root / 'loyalty/merchant_queue.py'
s = p.read_text()

def replace(old, new, count=1):
    global s
    assert s.count(old) == count, (old[:100], s.count(old), count)
    s = s.replace(old, new)

replace('import asyncio\n', 'import asyncio\nimport copy\n')
replace('import merchant_extract as extractor\n', 'import merchant_extract as extractor\nimport merchant_evidence as evidence\n')
replace("'program': r.get('program'), 'source_id': r.get('source_id')}",
        "'program': r.get('program'), 'source_id': r.get('source_id'),\n                       'source_record': r}")
replace("""        result.setdefault(ident, {'id': ident, 'url': url, 'partner': partner.strip(),
                                  'program': program.strip(), 'source_id': candidate.get('source_id')})""",
"""        target = result.setdefault(ident, {'id': ident, 'url': url, 'partner': partner.strip(),
                                  'program': program.strip(), 'source_id': candidate.get('source_id')})
        row = candidate.get('source_record')
        if row is not None:
            records = target.setdefault('source_records', [])
            if row not in records:
                records.append(copy.deepcopy(row))
            target['source_id'] = row.get('source_id')""")
replace("""        item['target'] = target""", """        previous = item.get('target', {})
        merged = copy.deepcopy(target)
        if 'source_records' not in merged and 'source_records' in previous:
            merged['source_records'] = copy.deepcopy(previous['source_records'])
        item['target'] = merged
        # Repair the old incomplete-input negative once, without deleting history
        # or resetting any provider quota. Corrected inputs get their own hash.
        if (item.get('extracted', {}).get('has_offer') is False
                and merged.get('source_records')
                and item.get('source_repair_version') != evidence.INPUT_CONTRACT_VERSION
                and item.get('input_contract_version') != evidence.INPUT_CONTRACT_VERSION):
            item.update(status='needs_source', last_checked=0,
                        source_repair_version=evidence.INPUT_CONTRACT_VERSION)""")
replace("payload = extractor.build_request(target, document['text'], document['images'], schema, system)",
        "payload = extractor.build_request(target, evidence.request_text(document, for_cache=True), document['images'], schema, system)")
replace("if item.get('fingerprint') == digest and 'extracted' in item:",
        "if item.get('fingerprint') == digest and evidence.cache_usable(item, document):")
replace("""        item.update(status=result['status'], last_checked=now(), last_result=result)
        if result['status'] == 'completed':
            item.update(fingerprint=digest,
                        extracted=extractor.strict_json((folder / 'direct/extracted.json').read_text()),
                        inferred_as_of=document['target']['as_of'], inferred_at=now(),
                        inferred_provider=provider, returned_model=result.get('returned_model'),
                        publication_allowed=False)
            summary['completed'] += 1
        else:
            summary['status'] = 'incomplete'""",
"""        answer = None
        if result['status'] == 'completed':
            answer = extractor.strict_json((folder / 'direct/extracted.json').read_text())
            unresolved = evidence.negative_status(document, answer)
            if unresolved:
                # Keep the actual model answer and completed API result intact.
                # Only the queue's readiness decision changes; do not fabricate an offer.
                result = {**result, 'generation_status': 'completed', 'status': unresolved,
                          'input_resolution': unresolved}
                item['unresolved_extraction'] = answer
                extractor.save(folder / 'queue-decision.json', result)
        item.update(status=result['status'], last_checked=now(), last_result=result)
        if result['status'] == 'completed':
            item.update(fingerprint=digest, extracted=answer,
                        inferred_as_of=document['target']['as_of'], inferred_at=now(),
                        inferred_provider=provider, returned_model=result.get('returned_model'),
                        input_contract_version=document.get('source', {}).get('capture', {}).get('input_contract_version'),
                        publication_allowed=False)
            item.pop('unresolved_extraction', None)
            summary['completed'] += 1
        else:
            summary['status'] = 'incomplete'""")
replace("return 'extracted' in item and item.get('fingerprint') == fingerprint(document, schema, system)",
        "return evidence.cache_usable(item, document) and item.get('fingerprint') == fingerprint(document, schema, system)")
replace("if row['status'] in ('failed_validation', 'transport_error'))",
        "if row['status'] in ('failed_validation', 'transport_error', 'needs_source', 'needs_review'))")
replace("ident, url = target['id'], target['url']", "ident, url = target['id'], evidence.capture_url(target)")
replace("    folder.mkdir()\n    async with PublicSource(browser, url) as source:",
        "    folder.mkdir()\n    capture = {'scope': 'pdf', 'target_found': False, 'content_ready': True}\n    async with PublicSource(browser, url) as source:")
replace("            if not text.strip(): text = '[PDF without embedded text; use all attached rendered pages.]'",
        "            capture['target_found'] = evidence.has_target(text, target['partner'])\n            if not text.strip(): text = '[PDF without embedded text; use all attached rendered pages.]'")
replace("""            check_response(status, html)
            # Reveal native HTML disclosures; no form submissions or account interaction.""",
"""            check_response(status, html)
            capture = await evidence.prepare_public_page(source.page, target)
            # Reveal native HTML disclosures; no form submissions or account interaction.""")
replace("""        return store(out, ident, {'partner': target['partner'], 'program': target['program'],
                                  'as_of': datetime.now(timezone.utc).date().isoformat()},
                     text, images, source_url=url)""",
"""        spec = store(out, ident, {'partner': target['partner'], 'program': target['program'],
                                  'as_of': datetime.now(timezone.utc).date().isoformat()},
                     text, images, source_url=url)
        spec = evidence.attach(spec, target, capture)
        extractor.save(folder / 'source-records.json', spec['source_records'])
        extractor.save(folder / 'capture-readiness.json', capture)
        return spec""")
p.write_text(s)

p = root / 'loyalty/merchant_extract.py'
s = p.read_text()
replace('import merchant_channels as channels\n',
        'import merchant_channels as channels\nimport merchant_evidence as evidence\n')
replace("""        try: datetime.strptime(target['as_of'], '%Y-%m-%d')
        except ValueError: raise ValueError('invalid_as_of') from None""",
"""        try: datetime.strptime(target['as_of'], '%Y-%m-%d')
        except ValueError: raise ValueError('invalid_as_of') from None
        evidence.validate_source_records(spec, target)""")
replace("""    payload = build_request(document['target'], document['text'], document['images'], schema, system, provider=provider)""",
"""    model_text = evidence.request_text(document)
    (out / 'model-input-text.txt').write_text(model_text, encoding='utf-8')
    payload = build_request(document['target'], model_text, document['images'], schema, system, provider=provider)""")
p.write_text(s)
print('Applied scoped evidence handoff and queue-decision changes')
