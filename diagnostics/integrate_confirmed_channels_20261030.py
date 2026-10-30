"""One-time, preimage-checked integration; never used by production runtime."""
from pathlib import Path


def replace(text, old, new, count=1):
    actual = text.count(old)
    if actual != count:
        raise ValueError(f'preimage_count {actual} != {count}: {old[:100]!r}')
    return text.replace(old, new)


path = Path('loyalty/merchant_extract.py')
s = path.read_text()
s = replace(s, 'import requests\n', 'import requests\nimport merchant_channels as channels\n')
s = replace(s, '\n\ndef provider_config(provider: str)', '\nPROVIDERS.update(channels.NEW_PROVIDERS)\n\n\ndef provider_config(provider: str)')
s = replace(s, "        result['max_tokens'] = 16384\n    return result", "        result['max_tokens'] = 16384\n    return channels.adapt_request(result, provider)")
s = replace(s, "    if not isinstance(data, dict): raise ValueError('response_shape')\n    returned", "    data = channels.normalize_response(data, provider)\n    if not isinstance(data, dict): raise ValueError('response_shape')\n    returned")
s = replace(s, "    if not orca_snapshot and not re.fullmatch(r'deepseekv41flash(?:free|[0-9]{4,8})?', normalized):\n        raise ValueError('returned_model_mismatch')", "    if provider in channels.NEW_PROVIDERS:\n        if not channels.accepted_model(provider, returned):\n            raise ValueError('returned_model_mismatch')\n    elif not orca_snapshot and not re.fullmatch(r'deepseekv41flash(?:free|[0-9]{4,8})?', normalized):\n        raise ValueError('returned_model_mismatch')")
s = replace(s, "    if payload.get('model') != route['model']: raise ValueError('unapproved_request_model')\n    allowed = {'model', 'stream', 'temperature', 'max_tokens', 'reasoning', 'messages'}", "    if channels.request_model(payload, provider) != route['model']:\n        raise ValueError('unapproved_request_model')\n    allowed = ({'systemInstruction', 'contents', 'generationConfig'} if provider == 'gemini' else\n               {'model', 'stream', 'temperature', 'max_tokens', 'reasoning', 'messages'})")
s = replace(s, "                response = session.post(route['endpoint'], headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key},\n                    data=body, timeout=(min(10, remaining / 2), min(180 if provider == 'tokenharbor' else 90, remaining / 2)), allow_redirects=False)", "                headers = {'Content-Type': 'application/json'}\n                headers.update({'x-goog-api-key': key} if provider == 'gemini' else {'Authorization': 'Bearer ' + key})\n                response = session.post(route['endpoint'], headers=headers, data=body,\n                    timeout=(min(10, remaining / 2), min(180 if provider != 'orcarouter' else 90, remaining / 2)),\n                    allow_redirects=False)")
s = replace(s, "            if response.status_code == 200:\n                if isinstance(data, dict):\n                    row.update(returned_model=data.get('model'), usage=data.get('usage'))", "            if response.status_code == 200:\n                try:\n                    normalized_data = channels.normalize_response(data, provider)\n                except (ValueError, TypeError, AttributeError):\n                    normalized_data = {}\n                if isinstance(normalized_data, dict):\n                    row.update(returned_model=normalized_data.get('model'), usage=normalized_data.get('usage'))\n                    result['usage'] = normalized_data.get('usage')")
s = replace(s, "returned_model=data['model'],\n                                  usage=data.get('usage'))", "returned_model=normalized_data['model'],\n                                  usage=normalized_data.get('usage'))")
s = replace(s, '                warning = reported_cost_warning(data)', "                warning = (channels.cost_warning(normalized_data, provider) if provider in channels.NEW_PROVIDERS\n                           else reported_cost_warning(data))")
s = replace(s, "    brief = copy.deepcopy(payload)\n    for part in brief['messages'][1]['content']:\n        if part.get('type') == 'image_url':\n            part['image_url']['url'] = '[see ordered image manifest]'", "    brief = channels.redact_images(payload, provider)")
path.write_text(s)

path = Path('loyalty/merchant_queue.py')
s = path.read_text()
s = replace(s, 'import merchant_extract as extractor\n', 'import merchant_extract as extractor\nimport merchant_channels as channels\n')
s = replace(s, "PROVIDER_DAILY_LIMITS = {'orcarouter': DAILY_REQUESTS, 'tokenharbor': 200}", "PROVIDER_DAILY_LIMITS = {'orcarouter': DAILY_REQUESTS, 'tokenharbor': 200, **channels.DAILY_LIMITS}")
s = replace(s, "PROVIDER_INTERVALS = {'orcarouter': REQUEST_INTERVAL, 'tokenharbor': 2}", "PROVIDER_INTERVALS = {'orcarouter': REQUEST_INTERVAL, 'tokenharbor': 2, **channels.INTERVALS}")
s = replace(s, "        # Reserve before IO. An interrupted request must not silently restore its quota.\n        reserved = min(extractor.MAX_ATTEMPTS, remaining)", "        check = channels.admission(provider, payload, key, ledger, now(), session=session)\n        if not check['allowed']:\n            summary.update(status='deferred', stop_reason=check.get('reason', 'allowance_unverified'),\n                           allowance_check=check, not_attempted=[d['id'] for d in documents[index:]])\n            break\n        # New accounts use one POST per item. This also keeps Kilo's hourly pacing\n        # intact and makes the Vercel worst-case reservation cover exactly one call.\n        reserved = min(1 if provider in channels.NEW_PROVIDERS else extractor.MAX_ATTEMPTS, remaining)\n        channels.reserve_budget(ledger, check, now())")
s = replace(s, "        attempts = result['http_attempts']", "        channels.reconcile(provider, ledger, check, result, now())\n        extractor.save(folder / 'direct/summary.json', result)\n        attempts = result['http_attempts']")
s = replace(s, "                 time_budget=4500, providers=('orcarouter', 'tokenharbor'))", "                 time_budget=4500, providers=channels.DEFAULT_PROVIDERS)")
s = replace(s, "        if stop in ('credential_echo', 'nonzero_reported_cost', 'invalid_reported_cost'):", "        if stop in ('credential_echo', 'nonzero_reported_cost', 'invalid_reported_cost',\n                    'missing_reported_cost', 'unexpected_byok', 'credit_cost_bound_exceeded'):")
s = replace(s, "    pool.add_argument('--providers', default='orcarouter,tokenharbor')", "    pool.add_argument('--providers', default=','.join(channels.DEFAULT_PROVIDERS))")
s = replace(s, "                                             'credential_echo','nonzero_reported_cost','invalid_reported_cost')", "                                             'credential_echo','nonzero_reported_cost','invalid_reported_cost',\n                                             'missing_reported_cost','unexpected_byok','credit_cost_bound_exceeded')")
path.write_text(s)
print('Applied only merchant_extract.py and merchant_queue.py; prompt/schema/fingerprint unchanged.')
