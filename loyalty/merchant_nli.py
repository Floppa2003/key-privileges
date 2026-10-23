"""Independent, pinned NLI classifier experiment. A support signal is not approval.

Only premise/hypothesis tokens enter the model; labels are used afterwards.
This is not an LLM extractor, completeness checker, or eligibility oracle.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

MODEL = 'MoritzLaurer/mDeBERTa-v3-base-mnli-xnli'
REVISION = '8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c'
WEIGHT_SHA256 = '27c39e884c14b03cf46cfc5485971b6db70ff330220d93dfe729c63fde43af0e'
LABELS = ('entailment', 'neutral', 'contradiction')
THRESHOLD = 0.90  # Fixed before evaluation, not tuned to these cases.
MAX_TOKENS = 512


def signal(scores: dict) -> str:
    if set(scores) != set(LABELS) or any(type(x) not in (int, float) or not math.isfinite(x) or not 0 <= x <= 1 for x in scores.values()):
        raise ValueError('probability_schema')
    if abs(sum(scores.values()) - 1) > 1e-5:
        raise ValueError('probability_sum')
    if scores['entailment'] >= THRESHOLD:
        return 'support_signal'
    if scores['contradiction'] >= THRESHOLD:
        return 'contradiction_signal'
    return 'review_required'


def evaluate(cases: list[dict], results: list[dict]) -> dict:
    if len(cases) != len(results) or [c['id'] for c in cases] != [r['id'] for r in results]:
        raise ValueError('evaluation_alignment')
    positive = [i for i, c in enumerate(cases) if c['expected_entailment']]
    negative = [i for i, c in enumerate(cases) if not c['expected_entailment']]
    tp = sum(results[i]['signal'] == 'support_signal' for i in positive)
    fp = sum(results[i]['signal'] == 'support_signal' for i in negative)
    missing = sum(r.get('scores') is None for r in results)
    return {'positives': len(positive), 'negatives': len(negative),
            'supported_positives': tp, 'false_supports': fp, 'unscored': missing,
            'positive_recall': tp / len(positive) if positive else None,
            'passed': bool(positive and negative and not fp and not missing and tp / len(positive) >= .8),
            'publication_allowed': False}


def load_cases(path: Path) -> list[dict]:
    cases = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(cases, list) or not 2 <= len(cases) <= 30:
        raise ValueError('case_count')
    seen = set()
    for c in cases:
        if set(c) != {'id', 'premise', 'hypothesis', 'expected_entailment', 'provenance'}:
            raise ValueError('case_schema')
        if not isinstance(c['id'], str) or c['id'] in seen:
            raise ValueError('case_id')
        seen.add(c['id'])
        if type(c['expected_entailment']) is not bool:
            raise ValueError('label_schema')
        if any(not isinstance(c[k], str) or not 1 <= len(c[k]) <= 8000 for k in ('premise', 'hypothesis', 'provenance')):
            raise ValueError('case_text')
    return cases


def run(cases: list[dict]) -> tuple[list[dict], dict]:
    import numpy as np
    import onnxruntime as ort
    from tokenizers import Tokenizer
    from huggingface_hub import hf_hub_download
    paths = {name: Path(hf_hub_download(MODEL, name, revision=REVISION, token=False))
             for name in ('tokenizer.json', 'config.json', 'onnx/model_quantized.onnx')}
    hashes = {name: hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()
              for name, path in paths.items()}
    if hashes['onnx/model_quantized.onnx'] != WEIGHT_SHA256:
        raise ValueError('model_digest_mismatch')
    cfg = json.loads(paths['config.json'].read_text())
    if tuple(cfg['id2label'][str(i)] for i in range(3)) != LABELS:
        raise ValueError('model_label_mismatch')
    tokenizer = Tokenizer.from_file(str(paths['tokenizer.json']))
    tokenizer.no_truncation(); tokenizer.no_padding()
    opts = ort.SessionOptions(); opts.intra_op_num_threads = 2; opts.inter_op_num_threads = 1
    model = ort.InferenceSession(str(paths['onnx/model_quantized.onnx']),
                                sess_options=opts, providers=['CPUExecutionProvider'])
    names = {i.name for i in model.get_inputs()}
    if not {'input_ids', 'attention_mask'} <= names or not names <= {'input_ids', 'attention_mask', 'token_type_ids'}:
        raise ValueError('model_inputs')
    results = []
    for c in cases:
        # Deliberately do not give the model IDs, expected labels, provenance or prior verdicts.
        enc = tokenizer.encode(c['premise'], c['hypothesis'])
        row = {'id': c['id'], 'token_count': len(enc.ids), 'truncated': False,
               'scores': None, 'signal': 'review_required', 'publication_allowed': False}
        if len(enc.ids) > MAX_TOKENS:
            row['reason'] = 'context_limit_no_truncation'
        else:
            arrays = {'input_ids': enc.ids, 'attention_mask': enc.attention_mask,
                      'token_type_ids': enc.type_ids}
            feed = {k: np.array([arrays[k]], dtype=np.int64) for k in names}
            logits = model.run(None, feed)[0][0].astype(np.float64)
            if logits.shape != (3,) or not np.isfinite(logits).all():
                raise ValueError('invalid_logits')
            probs = np.exp(logits - logits.max()); probs /= probs.sum()
            row['scores'] = dict(zip(LABELS, map(float, probs)))
            row['signal'] = signal(row['scores'])
        results.append(row)
    return results, {'id': MODEL, 'revision': REVISION, 'file_sha256': hashes,
                     'runtime': 'onnxruntime_cpu', 'quantized': True, 'max_tokens': MAX_TOKENS,
                     'independent_of_firecrawl_review_call': True,
                     'statistical_error_independence_claimed': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cases', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(); cases = load_cases(a.cases)
    if a.out.exists():
        raise FileExistsError('report_exists')
    report = {'started_at': datetime.now(timezone.utc).isoformat(), 'threshold': THRESHOLD,
              'cases_sha256': hashlib.sha256(a.cases.read_bytes()).hexdigest(),
              'publication_allowed': False, 'expected_labels_sent_to_model': False}
    try:
        results, model = run(cases)
        report.update(results=results, model=model, evaluation=evaluate(cases, results), execution='completed')
    except Exception as exc:
        report.update(execution='failed', error=type(exc).__name__)
    report['finished_at'] = datetime.now(timezone.utc).isoformat()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open('x', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in report.items() if k not in ('results', 'model')}))
    raise SystemExit(0 if report.get('evaluation', {}).get('passed') else 1)

if __name__ == '__main__':
    main()
