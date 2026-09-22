"""Checkpoint completed sources and stop the run before the CI hard timeout.

No new transport or publisher: the existing source workers and bundle schema
remain in use. A checkpoint is evidence of completed sources, not a claim that
unfinished sources were read. It never imports a previous run's observations.
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import time
from pathlib import Path

RUN_TIMEOUT = 1000


def failed_result(cfg, observed_at, reason, *, state='finished'):
    return ({'source_id':cfg['id'], 'name':cfg['name'], 'root':cfg['url'],
        'status':'failed', 'discovered':0, 'normalized':0, 'failed':1,
        'coverage':reason, 'region':None, 'errors':[{'phase':'collection','reason':reason}],
        'observed_at':observed_at, 'collection_state':state}, [])


def atomic_json(path, value):
    """A crash during serialization/replacement must leave the last JSON intact."""
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    try:
        with temporary.open('w', encoding='utf8') as stream:
            json.dump(value, stream, ensure_ascii=False, separators=(',',':'), allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


async def collect_batch(configs, run_source, budget_for, save, observed_at,
                        *, run_timeout=RUN_TIMEOUT, concurrency=4):
    """Save after each completed batch; source clocks start after queue admission."""
    if (not configs or len(configs)>128 or len({c['id'] for c in configs})!=len(configs)
            or not math.isfinite(run_timeout) or run_timeout<=0
            or type(concurrency) is not int or not 1<=concurrency<=4):
        raise ValueError('invalid_collection_runtime')
    budgets = [budget_for(c) for c in configs]
    if any(not math.isfinite(b) or b<=0 for b in budgets):
        raise ValueError('invalid_collection_source_budget')
    start = time.monotonic(); deadline = start + run_timeout
    semaphore = asyncio.Semaphore(concurrency)
    completed = {}; started = set(); state = 'running'

    def checkpoint():
        results = [completed.get(i) or failed_result(c, observed_at,
                   'collection_incomplete', state='interrupted' if i in started else 'not_started')
                   for i,c in enumerate(configs)]
        runtime = {'version':1, 'state':state, 'timeout_seconds':run_timeout,
                   'elapsed_seconds':round(time.monotonic()-start,3),
                   'selected_sources':len(configs), 'completed_sources':len(completed)}
        save(results, runtime)
        return results

    async def worker(i):
        cfg = configs[i]
        async with semaphore:
            if time.monotonic()>=deadline:
                return failed_result(cfg, observed_at, 'collection_incomplete', state='not_started')
            started.add(i); admitted = time.monotonic()
            try:
                report, rows = await asyncio.wait_for(run_source(cfg), timeout=budgets[i])
                if (report['source_id']!=cfg['id'] or report['observed_at']!=observed_at
                        or report['normalized']!=len(rows)
                        or any(r['source_id']!=cfg['id'] or r['observed_at']!=observed_at for r in rows)):
                    raise ValueError('collection_result_identity')
                report = dict(report, collection_state='finished')
            except asyncio.TimeoutError:
                report, rows = failed_result(cfg, observed_at, 'source_timeout')
            except Exception as exc:
                # Do not serialize exception text: a source may embed private URLs.
                report, rows = failed_result(cfg, observed_at, 'collection_worker_exception')
                report['errors'][0]['type'] = type(exc).__name__
            report['execution_seconds'] = round(time.monotonic()-admitted,3)
            report['queue_seconds'] = round(admitted-start,3)
            return report, rows

    checkpoint()
    # Start the longest allowed reads early, without changing source/result IDs,
    # source timeouts, per-host transport throttles or four-worker concurrency.
    tasks = {asyncio.create_task(worker(i)):i for i in
             sorted(range(len(configs)), key=lambda i:-budgets[i])}
    pending = set(tasks)
    try:
        while pending:
            done,pending = await asyncio.wait(pending, timeout=max(0,deadline-time.monotonic()),
                                              return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                result = task.result()
                if result[0].get('collection_state')=='finished':
                    completed[tasks[task]] = result
            if done:checkpoint()
            if not done or time.monotonic()>=deadline and pending:
                state = 'deadline'; break
        else:
            state = 'complete' if len(completed)==len(configs) else 'deadline'
    except asyncio.CancelledError:
        state = 'cancelled'
        raise
    finally:
        # Include a worker that finished concurrently with cancellation.
        for task,i in tasks.items():
            if task.done() and not task.cancelled() and task.exception() is None:
                result = task.result()
                if result[0].get('collection_state')=='finished':completed[i] = result
        # Persist before cleanup, which itself can stall or fail.
        try:checkpoint()
        finally:
            unfinished = [t for t in tasks if not t.done()]
            for task in unfinished:task.cancel()
            if unfinished:
                _,left = await asyncio.wait(unfinished, timeout=5)
                if left:
                    for task in left:task.cancel()
                    raise RuntimeError('collection_cleanup_timeout')
                for task in unfinished:
                    if not task.cancelled():task.exception()
    return checkpoint()


def execution_health(bundle, expected_sources):
    """Execution completeness is distinct from source-specific coverage/eligibility."""
    reports = bundle['sources']; ids = [r['source_id'] for r in reports]
    expected = set(expected_sources)
    missing = sorted(expected-set(ids)); unexpected = sorted(set(ids)-expected)
    unfinished = [r['source_id'] for r in reports if r.get('collection_state','finished')!='finished']
    exceptions = [r['source_id'] for r in reports if r.get('coverage')=='collection_worker_exception']
    meta = bundle.get('collection_runtime')
    state = 'legacy_payload' if meta is None else meta.get('state')
    coherent = meta is None or (meta.get('version')==1 and meta.get('selected_sources')==len(expected)
                 and meta.get('completed_sources')==len(reports)-len(unfinished))
    healthy = (coherent and len(ids)==len(set(ids)) and not missing and not unexpected
               and not unfinished and not exceptions and state in ('complete','legacy_payload'))
    return {'healthy':bool(healthy), 'state':state, 'expected_sources':len(expected),
            'reported_sources':len(ids), 'missing_sources':missing, 'unexpected_sources':unexpected,
            'unfinished_sources':unfinished, 'worker_exceptions':exceptions}
