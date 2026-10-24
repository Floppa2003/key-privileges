"""One-shot patch application; removed by its verification workflow before merge."""
from pathlib import Path
import hashlib
r = Path('.')
p=r/'loyalty/merchant_extract.py'
s=p.read_text()
s=s.replace('Selected merchant extractor: full prepared pages -> OrcaRouter DeepSeek JSON, review only.', 'Selected merchant extractor: full prepared pages -> free DeepSeek JSON, review only.')
s=s.replace('No publisher, model fallback, output repair or partner-specific extraction rules.', 'No publisher, paid/model fallback, output repair or partner-specific extraction rules.')
s=s.replace("ENDPOINT = BASE_URL + '/chat/completions'", """ENDPOINT = BASE_URL + '/chat/completions'
# Explicit free routes for the same selected model; never accept arbitrary paid IDs.
PROVIDERS = {
    'orcarouter': {'model': MODEL, 'endpoint': ENDPOINT, 'secret': 'ORCAROUTER_API_KEY'},
    'tokenharbor': {'model': 'deepseek-v4.1-flash:free',
                    'endpoint': 'https://tokenharbor.ai/v1/chat/completions',
                    'secret': 'TOKENHARBOR_API_KEY'},
}


def provider_config(provider: str) -> dict:
    try:
        return PROVIDERS[provider]
    except KeyError:
        raise ValueError('unknown_free_provider') from None
""")
s=s.replace('schema: dict, system: str) -> dict:\n    """Same tested OrcaRouter payload:', "schema: dict, system: str, *, provider='orcarouter') -> dict:\n    \"\"\"Same tested provider payload:")
s=s.replace("    return {\n        'model': MODEL, 'stream': False, 'temperature': 1.0, 'max_tokens': 8192,", "    result = {\n        'model': provider_config(provider)['model'], 'stream': False, 'temperature': 1.0, 'max_tokens': 8192,")
s=s.replace("                for b in images]]}]}\n", """                for b in images]]}]}
    if provider == 'tokenharbor':
        # Exactly the previously successful Harbor payload: native default thinking,
        # not OrcaRouter's provider-specific reasoning extension.
        result.pop('reasoning')
    return result
""")
a=s.index("    if not isinstance(usage, dict) or usage.get('cost') is None:")
b=s.index('\n\ndef parse_final',a)
s=s[:a]+"""    if not isinstance(usage, dict):
        return None
    for field in ('cost', 'cost_usd'):
        if usage.get(field) is None:
            continue
        try:
            cost = Decimal(str(usage[field]))
        except InvalidOperation:
            return 'invalid_reported_cost'
        if not cost.is_finite():
            return 'invalid_reported_cost'
        if cost != 0:
            return 'nonzero_reported_cost'
    return None
"""+s[b:]
s=s.replace("returned.rsplit('/', 1)[-1].lower())", "returned.rsplit('/', 1)[-1].lower().removesuffix(':free'))")
s=s.replace("deepseekv41flash(?:free|[0-9]{6,8})?", "deepseekv41flash(?:free|[0-9]{4,8})?")
s=s.replace('jitter=None, max_attempts=MAX_ATTEMPTS) -> dict:', "jitter=None, max_attempts=MAX_ATTEMPTS, provider='orcarouter') -> dict:")
s=s.replace("    if payload.get('model') != MODEL: raise ValueError('unapproved_request_model')", "    route = provider_config(provider)\n    if payload.get('model') != route['model']: raise ValueError('unapproved_request_model')")
s=s.replace("result = {'provider': 'orcarouter', 'requested_model': MODEL, 'endpoint': ENDPOINT,", "result = {'provider': provider, 'requested_model': route['model'], 'endpoint': route['endpoint'],")
s=s.replace("response = session.post(ENDPOINT, headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key},", "response = session.post(route['endpoint'], headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key},")
s=s.replace('def prepare_document(document: dict, out: Path, schema: dict, system: str) -> dict:', "def prepare_document(document: dict, out: Path, schema: dict, system: str, *, provider='orcarouter') -> dict:")
s=s.replace("payload = build_request(document['target'], document['text'], document['images'], schema, system)", "payload = build_request(document['target'], document['text'], document['images'], schema, system, provider=provider)")
p.write_text(s)
p=r/'loyalty/merchant_queue.py';s=p.read_text()
s=s.replace('Persistent progress; no publishing or paid fallback.', 'Persistent progress; independent free quotas, no publishing or paid fallback.')
s=s.replace('REQUEST_INTERVAL = 7', """REQUEST_INTERVAL = 7
# Harbor's 200/day is OUR workload ceiling, not a claim about its weekly allowance.
PROVIDER_DAILY_LIMITS = {'orcarouter': DAILY_REQUESTS, 'tokenharbor': 200}
PROVIDER_INTERVALS = {'orcarouter': REQUEST_INTERVAL, 'tokenharbor': 2}
POOL_REQUESTS = sum(PROVIDER_DAILY_LIMITS.values())
MAX_CAPTURE_PAGES = 300


def provider_state(state: dict, provider: str) -> dict:
    extractor.provider_config(provider)
    # Keep the original Orca ledger in place: no quota reset when upgrading v1.
    if provider == 'orcarouter':
        return state
    return state.setdefault('providers', {}).setdefault(provider, {
        'usage': {'date': '', 'attempts': 0}, 'provider_not_before': 0, 'last_request_at': 0})


def provider_eligible(state: dict, provider: str, timestamp: float) -> bool:
    ledger = provider_state(state, provider)
    day = datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat()
    return ledger.get('provider_not_before', 0) <= timestamp and not (
        ledger['usage']['date'] == day and ledger['usage']['attempts'] >= PROVIDER_DAILY_LIMITS[provider])
""")
s=s.replace('now=time.time, sleep=time.sleep, max_requests=DAILY_REQUESTS, time_budget=1500) -> dict:', "now=time.time, sleep=time.sleep, max_requests=DAILY_REQUESTS, time_budget=1500,\n                      provider='orcarouter') -> dict:")
s=s.replace("    if not 1 <= max_requests <= DAILY_REQUESTS:\n        raise ValueError('daily_request_budget')", "    ledger = provider_state(state, provider)\n    daily_limit = PROVIDER_DAILY_LIMITS[provider]\n    if not 1 <= max_requests <= daily_limit:\n        raise ValueError('daily_request_budget')")
a=s.index('def process_documents(');b=s.index('\n\nasync def capture_page',a)
block=s[a:b]
block=block.replace("state['usage']", "ledger['usage']").replace("state.get('provider_not_before'", "ledger.get('provider_not_before'").replace("state['provider_not_before']", "ledger['provider_not_before']").replace("state.get('last_request_at'", "ledger.get('last_request_at'").replace("state['last_request_at']", "ledger['last_request_at']")
block=block.replace("DAILY_REQUESTS - ledger['usage']['attempts']", "daily_limit - ledger['usage']['attempts']")
block=block.replace("+ REQUEST_INTERVAL - now()", "+ PROVIDER_INTERVALS[provider] - now()")
block=block.replace('extractor.prepare_document(document, folder, schema, system)', 'extractor.prepare_document(document, folder, schema, system, provider=provider)')
block=block.replace('session=session, sleep=sleep, max_attempts=reserved)', 'session=session, sleep=sleep, max_attempts=reserved, provider=provider)')
block=block.replace("inferred_as_of=document['target']['as_of'], inferred_at=now(),", "inferred_as_of=document['target']['as_of'], inferred_at=now(),\n                        inferred_provider=provider, returned_model=result.get('returned_model'),")
block=block.replace("summary.update(daily_usage=", "summary.update(provider=provider, daily_usage=")
s=s[:a]+block+s[b:]
insert='''

def process_pool(documents: list[dict], state: dict, state_path: Path, out: Path,
                 keys: dict, schema: dict, system: str, *, sessions=None,
                 now=time.time, sleep=time.sleep, max_requests=POOL_REQUESTS,
                 time_budget=4500, providers=('orcarouter', 'tokenharbor')) -> dict:
    """Try independent free accounts in order, never regenerate a model answer.

    Both routes share the evidence/contract fingerprint, not serving credentials.
    Exact serving route and returned snapshot remain attached to each accepted result.
    """
    if not 1 <= max_requests <= POOL_REQUESTS:
        raise ValueError('pool_request_budget')
    if not providers or len(set(providers)) != len(providers):
        raise ValueError('invalid_provider_order')
    for provider in providers:
        extractor.provider_config(provider)
    out.mkdir(parents=True, exist_ok=False)
    deadline = now() + time_budget
    def cached(document):
        item = state['items'].get(document['id'], {})
        return 'extracted' in item and item.get('fingerprint') == fingerprint(document, schema, system)
    initially_cached = {d['id'] for d in documents if cached(d)}
    for ident in initially_cached:
        state['items'][ident].update(last_checked=now(), status='cached')
    summary = {'status': 'completed', 'completed': 0, 'cached': len(initially_cached),
               'http_attempts': 0, 'providers': [], 'pending': [], 'publication_allowed': False}
    no_retry = set()
    for provider in providers:
        pending = [d for d in documents if not cached(d) and d['id'] not in no_retry]
        if not pending or summary['http_attempts'] >= max_requests or now() >= deadline:
            break
        key = keys.get(provider, '')
        if not isinstance(key, str) or not key.strip():
            summary['providers'].append({'provider': provider, 'status': 'missing_key', 'http_attempts': 0})
            continue
        result = process_documents(pending, state, state_path, out / provider, key, schema, system,
            provider=provider, session=(sessions or {}).get(provider), now=now, sleep=sleep,
            max_requests=min(PROVIDER_DAILY_LIMITS[provider], max_requests-summary['http_attempts']),
            time_budget=max(0, deadline-now()))
        summary['providers'].append(result)
        summary['completed'] += result['completed']
        summary['http_attempts'] += result['http_attempts']
        # Validation failures are model answers, not quota failures. Unknown network
        # outcomes are also not retried via a second account in this run.
        no_retry.update(row['id'] for row in result['results']
                        if row['status'] in ('failed_validation', 'transport_error'))
        stop = result.get('stop_reason')
        if stop in ('credential_echo', 'nonzero_reported_cost', 'invalid_reported_cost'):
            summary['stop_reason'] = stop
            break
        extractor.save(out/'summary.json', summary)
    summary['pending'] = [d['id'] for d in documents if not cached(d)]
    summary['queue_size'] = len(state['items'])
    if summary.get('stop_reason') or no_retry:
        summary['status'] = 'incomplete'
    elif not documents:
        summary['status'] = 'no_input'
    elif summary['pending']:
        usable = any(isinstance(keys.get(p), str) and keys[p].strip() for p in providers)
        summary['status'] = 'deferred' if usable else 'unavailable'
    write_state(state_path, state)
    extractor.save(out/'summary.json', summary)
    return summary
'''
s=s.replace('\n\nasync def capture_page',insert+'\n\nasync def capture_page')
s=s.replace('async def prepare_queue(state_path: Path, catalog_path: Path, out: Path, max_pages: int) -> dict:', "async def prepare_queue(state_path: Path, catalog_path: Path, out: Path, max_pages: int,\n                        providers=('orcarouter',)) -> dict:")
s=s.replace("if not 1 <= max_pages <= 100: raise ValueError('capture_budget')", "if not 1 <= max_pages <= MAX_CAPTURE_PAGES: raise ValueError('capture_budget')")
s=s.replace("    eligible = state.get('provider_not_before', 0) <= time.time()\n    eligible = eligible and not (state['usage']['date'] == day and state['usage']['attempts'] >= DAILY_REQUESTS)", "    eligible = any(provider_eligible(state, provider, time.time()) for provider in providers)")
s=s.replace("    extract.add_argument('--execute', action='store_true')\n    for command in (prepare, extract):", """    extract.add_argument('--execute', action='store_true')
    pool = sub.add_parser('pool')
    pool.add_argument('--manifest', type=Path, required=True)
    pool.add_argument('--max-requests', type=int, default=POOL_REQUESTS)
    pool.add_argument('--execute', action='store_true')
    pool.add_argument('--providers', default='orcarouter,tokenharbor')
    prepare.add_argument('--providers', default='orcarouter')
    for command in (prepare, extract, pool):""")
s=s.replace("result = asyncio.run(prepare_queue(args.state, args.catalog, args.out, args.max_pages))", "result = asyncio.run(prepare_queue(args.state, args.catalog, args.out, args.max_pages,\n                                          providers=tuple(args.providers.split(','))))")
s=s.replace("documents = extractor.load_manifest(args.manifest, max_documents=100) if manifest['documents'] else []", "documents = extractor.load_manifest(args.manifest, max_documents=MAX_CAPTURE_PAGES) if manifest['documents'] else []")
a=s.index('        result = process_documents(documents, state, args.state, args.out,')
b=s.index('        # Quota deferral',a)
s=s[:a]+'''        schema = extractor.strict_json((HERE/'merchant_offer.schema.json').read_text())
        system = (HERE/'merchant_prompt.txt').read_text()
        if args.command == 'pool':
            providers = tuple(args.providers.split(','))
            keys = {p: os.environ.get(extractor.provider_config(p)['secret'], '') for p in providers}
            result = process_pool(documents, state, args.state, args.out, keys, schema, system,
                                  max_requests=args.max_requests, providers=providers)
        else:
            result = process_documents(documents, state, args.state, args.out,
                os.environ.get('ORCAROUTER_API_KEY', ''), schema, system, max_requests=args.max_requests)
'''+s[b:]
s=s.replace('        if not documents:\n', "        if not documents and args.command == 'extract':\n")
p.write_text(s)
p=r/'.github/workflows/merchant-llm-daily.yml';s=p.read_text()
s=s.replace('Maximum real API attempts in this run (1-50; persistent daily cap also applies)', 'Maximum total attempts (1-250); Orca 50/day, Harbor local ceiling 200/day')
s=s.replace("default: '50'", "default: '250'")
s=s.replace('Maximum current public pages to capture (1-100)', 'Maximum current public pages to capture (1-300)')
s=s.replace("default: '100'", "default: '300'").replace('timeout-minutes: 60','timeout-minutes: 120')
s=s.replace("MAX_PAGES: ${{ inputs.max_pages || '100' }}", "MAX_PAGES: ${{ inputs.max_pages || '300' }}")
s=s.replace(' --max-pages "$MAX_PAGES" \\', ' --max-pages "$MAX_PAGES" --providers orcarouter,tokenharbor \\')
s=s.replace('Process changed documents with DeepSeek, persist quota and progress', 'Process changed documents through independent free DeepSeek routes')
s=s.replace("          MAX_REQUESTS: ${{ inputs.max_requests || '50' }}", "          TOKENHARBOR_API_KEY: ${{ secrets.TOKENHARBOR_API_KEY }}\n          MAX_REQUESTS: ${{ inputs.max_requests || '250' }}")
s=s.replace('python loyalty/merchant_queue.py extract --manifest', 'python loyalty/merchant_queue.py pool --manifest')
s=s.replace('DeepSeek V4.1 Flash / OrcaRouter; free route only; no Sheets publication.', 'DeepSeek V4.1 Flash / OrcaRouter + Token Harbor; free routes only; no Sheets publication.')
p.write_text(s)
p=r/'loyalty/DAILY_LLM.md';s=p.read_text().replace('up to 100 least-recently-checked', 'up to 300 least-recently-checked')
a=s.index('Limits are **50 HTTP attempts');b=s.index('\n\nA normal quota',a)
s=s[:a]+'''Two explicit free routes serve the same selected DeepSeek V4.1 Flash: OrcaRouter
`deepseek/deepseek-v4.1-flash-free` first, then Token Harbor
`deepseek-v4.1-flash:free`. Existing `ORCAROUTER_API_KEY` and
`TOKENHARBOR_API_KEY` are injected only in inference, never source capture.

The Orca queue limit remains **50 HTTP attempts per UTC day**, at least **7 seconds**
between document calls. Token Harbor has an independent ledger and a local engineering
ceiling of **200 attempts/day**, at least **2 seconds** between document calls.
**200 is not a published or guaranteed free entitlement**: Harbor's actual allowance
is a personal 7-day value-based budget. Server quota refusals/Retry-After take precedence.
The combined run ceiling is 250 attempts, including retries; inference admission is
bounded at 75 minutes and the workflow at 120 minutes. Capture still has a 20-minute
admission budget. None of these ceilings promise that many successes per day.

The existing v1 Orca usage/cooldown/history is preserved. Harbor's accounting and cooldown
are stored independently under `providers.tokenharbor`. An Orca cooldown no longer stops
capture when Harbor is eligible. A server's seven-day hint is not replaced by a midnight
reset. Missing credentials or access refusal on one route do not stop the other.
Before IO up to three attempts are reserved; unused reservations are returned. Other
experiments on the same provider can consume quota outside this queue's counters.

Successful JSON is shared by complete-evidence/target/prompt/schema fingerprint, so the
second provider does not repeat the first provider's completed work and a Harbor answer
is reused on later Orca runs. This deliberately treats the selected model family as the
same extraction contract; the exact provider and returned model snapshot remain in
`inferred_provider`, `returned_model`, and `last_result`. Orca uses the tested high-reasoning
extension; Harbor uses its previously tested native-default payload. The original Orca
fingerprint remains the canonical contract fingerprint, retaining previous cache entries.

Fallback is for work not processed or rejected by provider capacity/input limits, not
model-answer repair. A validation failure or unknown network execution outcome is not
regenerated on the other provider in the same run. Billing anomalies or credential echoes
halt the entire pool while preserving valid results. Paid route names, arbitrary endpoints,
web search/tools, and account/key rotation to multiply the same workspace quota are absent.
''' +s[b:]
p.write_text(s)
p=r/'loyalty/MERCHANT_DEEPSEEK.md';s=p.read_text()
s=s.replace('No search tools, plugins, URL retrieval, agent loop, server-side response_format requirement, catalog/capability preflight, paid route or automatic fallback.', 'No search tools, plugins, URL retrieval, agent loop, server-side response_format requirement, catalog/capability preflight, paid route or model fallback. The daily queue can use the separately budgeted Token Harbor free route of the same model; see DAILY_LLM.md.')
s=s.replace('no switching keys/providers to bypass the limit.', "no rotating keys to multiply a provider quota. The daily pool can continue using a different provider's legitimately separate free allowance.")
p.write_text(s)
expected = {
 'loyalty/merchant_extract.py':'235d37f589f90582cf37aa17ce46e6fee98fae12202b5e554a3edb946319676f',
 'loyalty/merchant_queue.py':'bc0feab869a03f14965ef254bac5d705424b7ea28d235bf211ce9c1e909be346',
 'loyalty/tests/test_merchant_capacity.py':'134c9a48c585ae988701a364bddeb5261c54a1f3d788ea1203d12364f3764c1e',
 '.github/workflows/merchant-llm-daily.yml':'f207b81029bee62c7fba558fbcaeea536e3c7fd72e5db6ad19ada2c0fe733ba2',
 'loyalty/DAILY_LLM.md':'6ee8e5b5d016a37aad3ce3127f49089fbc66bc2dfbd44ffbf4856ee410340d83',
 'loyalty/MERCHANT_DEEPSEEK.md':'4a0f126a92e50ab337a05a06b67fcc5a55575372d22a9ef5de4925a26a704e03',
}
for name, digest in expected.items():
    assert hashlib.sha256((r/name).read_bytes()).hexdigest() == digest, name
print('All six source files match the locally tested bytes.')
