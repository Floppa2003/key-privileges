"""Deterministic evaluator for frozen merchant held-out extraction predictions.

Gold labels live only in the corpus. Observed predictions contain no expected
labels. This evaluator measures evidence scope and contract quality; it never
authorizes publication.
"""
from __future__ import annotations
import json
from pathlib import Path
import merchant_blocks as blocks_v1
import merchant_blocks_v2 as blocks_v2
import merchant_general as core

VERSION='merchant-heldout-eval-v1'


def _selected_refs(pred: dict) -> list[str]:
    refs=[]
    offers=pred.get('offers',[]) if isinstance(pred,dict) else []
    if not isinstance(offers,list):
        return refs
    for offer in offers:
        if not isinstance(offer,dict):
            continue
        for key in ('program','audience','benefit','conditions','redemption'):
            value=offer.get(key,[])
            if isinstance(value,list):
                refs.extend(x for x in value if isinstance(x,str))
        code=offer.get('code',{})
        if isinstance(code,dict) and isinstance(code.get('refs'),list):
            refs.extend(x for x in code['refs'] if isinstance(x,str))
        dates=offer.get('dates',[])
        if isinstance(dates,list):
            for date in dates:
                if isinstance(date,dict) and isinstance(date.get('refs'),list):
                    refs.extend(x for x in date['refs'] if isinstance(x,str))
    return list(dict.fromkeys(refs))


def _selected_text(doc: dict, pred: dict) -> str:
    wanted=set(_selected_refs(pred))
    return '\n'.join(b['text'] for b in doc['blocks'] if b['id'] in wanted)


def _offers(pred: dict) -> list[dict]:
    value=pred.get('offers',[]) if isinstance(pred,dict) else []
    return value if isinstance(value,list) else []


def _disposition(pred: dict) -> str:
    offers=_offers(pred)
    state=pred.get('state') if isinstance(pred,dict) else None
    if state=='candidates' and offers:
        return 'reusable_offer'
    if state in ('no_offer','uncertain') and not offers:
        return 'no_reusable_offer'
    return 'invalid'


def _code_ok(expected: str, pred: dict) -> bool:
    offers=_offers(pred)
    if not offers:
        return expected=='not_stated'
    states=[]
    for offer in offers:
        if not isinstance(offer,dict) or not isinstance(offer.get('code'),dict):
            return False
        states.append(offer['code'].get('state'))
    return bool(states) and all(state==expected for state in states)


def _date_roles(pred: dict) -> list[str]:
    result=[]
    for offer in _offers(pred):
        if not isinstance(offer,dict) or not isinstance(offer.get('dates'),list):
            continue
        for date in offer['dates']:
            if isinstance(date,dict) and isinstance(date.get('role'),str):
                result.append(date['role'])
    return result


def _audience_explicit(pred: dict) -> bool:
    offers=_offers(pred)
    return bool(offers) and all(isinstance(o,dict) and isinstance(o.get('audience'),list)
                                and bool(o['audience']) for o in offers)


def evaluate(corpus_path: Path, observed_path: Path) -> dict:
    corpus=json.loads(corpus_path.read_text(encoding='utf-8'))
    observed=json.loads(observed_path.read_text(encoding='utf-8'))
    if corpus.get('version') not in ('merchant-heldout-v1','merchant-heldout-v2','merchant-heldout-v3'):
        raise ValueError('corpus_version')
    version=observed.get('version')
    if version not in ('merchant-heldout-observed-v1','merchant-heldout-observed-v2-on-v1','merchant-heldout-observed-v1-on-v2','merchant-heldout-observed-v3'):
        raise ValueError('observed_version')
    block_version=observed.get('block_version','merchant-blocks-v1')
    if block_version=='merchant-blocks-v1':
        blocks=blocks_v1
    elif block_version=='merchant-blocks-v2':
        blocks=blocks_v2
    else:
        raise ValueError('block_version')
    if not observed.get('labels_frozen_before_predictions'):
        raise ValueError('labels_not_frozen')
    if observed.get('expected_labels_sent_to_model') is not False:
        raise ValueError('labels_leaked_to_model')
    if any('expected' in trial for trial in observed.get('trials',[])):
        raise ValueError('labels_in_observations')

    cases=corpus.get('cases')
    trials=observed.get('trials')
    if not isinstance(cases,list) or not isinstance(trials,list):
        raise ValueError('heldout_shape')
    if [c.get('id') for c in cases] != [t.get('id') for t in trials]:
        raise ValueError('heldout_alignment')

    aggregate={
        'version':VERSION,'cases':len(cases),'passed_cases':0,
        'block_contract_valid':0,'expected_reusable':0,
        'explicit_audience_reusable':0,'exact_variant_count':0,
        'required_evidence_phrases_found':0,'required_evidence_phrases_total':0,
        'forbidden_borrowing_hits':0,'required_date_roles_found':0,
        'required_date_roles_total':0,'unexpected_material_date_roles':0,
        'code_state_correct':0,'transport_attempts':0,'transport_successes':0,
        'transport_failures':0,'semantic_cases':0,'semantic_passed_cases':0,
        'labels_frozen_before_predictions':True,
        'expected_labels_sent_to_model':False,'publication_allowed':False,'results':[]
    }

    for case,trial in zip(cases,trials):
        source=case['source']; expected=case['expected']
        doc=blocks.build(source['markdown'],url=source['url'],
                         observed_at=source['observed_at'],completeness=source['completeness'])
        failures=[]
        transport=trial.get('transport') if isinstance(trial,dict) else None
        if transport is not None:
            aggregate['transport_attempts']+=1
            status=transport.get('status') if isinstance(transport,dict) else None
            if status!='success':
                aggregate['transport_failures']+=1
                aggregate['results'].append({
                    'id':case['id'],'passed':False,'failures':['transport'],
                    'evaluation_status':'transport_failure','block_version':block_version,
                    'actual_disposition':None,'expected_disposition':expected['disposition'],
                    'actual_variants':None,'expected_variants':expected['offer_variants'],
                    'block_problems':[],'block_status':None,
                    'required_found':[],'required_missing':expected['required_phrases'],
                    'forbidden_hits':[],'actual_code_states':[],
                    'actual_date_roles':[],'parse_error':None,
                    'transport':transport,'publication_allowed':False,
                })
                continue
            aggregate['transport_successes']+=1
        aggregate['semantic_cases']+=1
        try:
            pred=core.model_output({'answer':trial['raw_answer']})
            if not isinstance(pred,dict):
                raise ValueError('prediction_shape')
        except Exception as exc:
            pred={}
            failures.append('parse')
            parse_error=type(exc).__name__
        else:
            parse_error=None

        checked=blocks.check(case['target'],doc,pred) if pred else {
            'problems':['prediction_shape'],'offers':[],'status':'review_required'}
        contract_valid=not checked.get('problems')
        aggregate['block_contract_valid']+=int(contract_valid)
        if not contract_valid:
            failures.append('block_contract')

        actual_disposition=_disposition(pred)
        if actual_disposition != expected['disposition']:
            failures.append('disposition')

        variants=len(_offers(pred))
        variants_ok=variants==expected['offer_variants']
        aggregate['exact_variant_count']+=int(variants_ok)
        if not variants_ok:
            failures.append('variant_count')

        reusable=expected['disposition']=='reusable_offer'
        if reusable:
            aggregate['expected_reusable']+=1
            audience_ok=_audience_explicit(pred)
            aggregate['explicit_audience_reusable']+=int(audience_ok)
            if not audience_ok:
                failures.append('audience_missing')

        selected=_selected_text(doc,pred).casefold()
        required=expected['required_phrases']
        found=[phrase for phrase in required if phrase.casefold() in selected]
        aggregate['required_evidence_phrases_found']+=len(found)
        aggregate['required_evidence_phrases_total']+=len(required)
        if len(found)!=len(required):
            failures.append('required_evidence')

        forbidden=[phrase for phrase in expected['forbidden_borrowing']
                   if phrase.casefold() in selected]
        aggregate['forbidden_borrowing_hits']+=len(forbidden)
        if forbidden:
            failures.append('forbidden_borrowing')

        code_ok=_code_ok(expected['code_state'],pred)
        aggregate['code_state_correct']+=int(code_ok)
        if not code_ok:
            failures.append('code_state')

        roles=_date_roles(pred)
        needed=expected['date_roles']
        found_roles=[role for role in needed if role in roles]
        aggregate['required_date_roles_found']+=len(found_roles)
        aggregate['required_date_roles_total']+=len(needed)
        if len(found_roles)!=len(needed):
            failures.append('date_role')
        extras=sorted({role for role in roles if role not in needed and role!='publication'})
        aggregate['unexpected_material_date_roles']+=len(extras)
        if extras:
            failures.append('unexpected_date_role')

        failures=list(dict.fromkeys(failures))
        passed=not failures
        aggregate['passed_cases']+=int(passed)
        aggregate['semantic_passed_cases']+=int(passed)
        aggregate['results'].append({
            'id':case['id'],'passed':passed,'failures':failures,
            'evaluation_status':'semantic_pass' if passed else 'semantic_failure',
            'block_version':block_version,
            'actual_disposition':actual_disposition,'expected_disposition':expected['disposition'],
            'actual_variants':variants,'expected_variants':expected['offer_variants'],
            'block_problems':checked.get('problems',[]),'block_status':checked.get('status'),
            'required_found':found,'required_missing':[p for p in required if p not in found],
            'forbidden_hits':forbidden,'actual_code_states':[
                o.get('code',{}).get('state') for o in _offers(pred) if isinstance(o,dict)],
            'actual_date_roles':roles,'parse_error':parse_error,
            'publication_allowed':False,
        })
    return aggregate
