"""Deterministic atomic claims derived from source-bound merchant block evidence.

Claims are review tasks, not verified facts. They never permit publication.
"""
from __future__ import annotations

import merchant_blocks as blocks_v1
import merchant_blocks_v2 as blocks_v2
import merchant_general as core

VERSION = 'merchant-claims-v1'
BLOCKS_BY_VERSION = {blocks_v1.VERSION: blocks_v1, blocks_v2.VERSION: blocks_v2}

BLOCK_MODULES = {
    blocks_v1.VERSION: blocks_v1,
    blocks_v2.VERSION: blocks_v2,
}


def _block_module(doc: dict):
    try:
        return BLOCK_MODULES[doc.get('version')]
    except KeyError as exc:
        raise ValueError('unsupported_block_version') from exc


DATE_TEXT = {
    'booking': 'Указанная дата или период относится к сроку бронирования: ',
    'stay': 'Указанная дата или период относится к сроку проживания: ',
    'offer': 'Указанная дата или период относится к сроку действия предложения: ',
    'publication': 'Указанная дата является датой публикации материала: ',
    'unclear': 'Источник содержит дату или период с неясной ролью: ',
}


def _refs(values: list[dict]) -> list[str]:
    return [value['id'] for value in values]


def _plain(value: str) -> str:
    return core.text(value)


def _premise(*groups: list[dict]) -> tuple[str, list[str]]:
    """Build a claim-local premise from cited offer anchors and claim evidence."""
    by_id: dict[str, dict] = {}
    for group in groups:
        for value in group:
            by_id[value['id']] = value
    ordered = sorted(by_id.values(), key=lambda value: value['start'])
    return ' '.join(_plain(value['text']) for value in ordered), _refs(ordered)


def _claim(source_sha256: str, offer_index: int, kind: str, number: int,
           premise: str, hypothesis: str, evidence_refs: list[str],
           premise_refs: list[str], **extra) -> dict:
    return {
        'id': f'o{offer_index}:{kind}:{number}',
        'kind': kind,
        'source_sha256': source_sha256,
        'premise': premise,
        'hypothesis': hypothesis,
        'evidence_refs': evidence_refs,
        'premise_refs': premise_refs,
        'publication_allowed': False,
        **extra,
    }


def generate(target: dict, doc: dict, checked: dict) -> dict:
    """Convert hydrated block fields into atomic semantic-review claims."""
    _block_module(doc).validate_document(doc)
    claims: list[dict] = []
    reasons: list[str] = []

    for problem in checked.get('problems', []):
        reasons.append(f'block_check_problem:{problem}')

    for offer_index, offer in enumerate(checked.get('offers', [])):
        fields = offer['fields']

        if not fields.get('audience'):
            reasons.append('audience_missing')

        for field_reason in offer.get('review_reasons', []):
            if field_reason not in reasons:
                reasons.append(field_reason)

        for number, value in enumerate(fields.get('audience', [])):
            evidence = _plain(value['text'])
            premise, premise_refs = _premise(
                fields.get('program', []), [value], fields.get('benefit', []))
            claims.append(_claim(
                doc['source_sha256'], offer_index, 'audience', number, premise,
                f'Предложение программы «{target["program"]}» предназначено для аудитории: {evidence}',
                [value['id']], premise_refs,
            ))

        for number, value in enumerate(fields.get('benefit', [])):
            evidence = _plain(value['text'])
            premise, premise_refs = _premise(
                fields.get('program', []), fields.get('audience', []), [value])
            claims.append(_claim(
                doc['source_sha256'], offer_index, 'benefit', number, premise,
                f'Целевая аудитория предложения программы «{target["program"]}» получает следующую выгоду: {evidence}',
                [value['id']], premise_refs,
            ))

        for number, value in enumerate(fields.get('conditions', [])):
            evidence = _plain(value['text'])
            premise, premise_refs = _premise(
                fields.get('program', []), fields.get('audience', []),
                fields.get('benefit', []), [value])
            claims.append(_claim(
                doc['source_sha256'], offer_index, 'condition', number, premise,
                f'Для предложения действует условие: {evidence}',
                [value['id']], premise_refs,
            ))

        for number, value in enumerate(fields.get('redemption', [])):
            evidence = _plain(value['text'])
            premise, premise_refs = _premise(
                fields.get('program', []), fields.get('audience', []),
                fields.get('benefit', []), [value])
            claims.append(_claim(
                doc['source_sha256'], offer_index, 'redemption', number, premise,
                f'Для получения предложения указано действие: {evidence}',
                [value['id']], premise_refs,
            ))

        code = offer.get('code', {})
        code_blocks = code.get('blocks', [])
        if code.get('state') != 'not_stated' and code_blocks:
            code_refs = _refs(code_blocks)
            if code['state'] == 'literal':
                hypothesis = f'Для предложения используется промокод «{code["value"]}».'
            elif code['state'] == 'app_or_account':
                hypothesis = 'Для предложения требуется промокод, который получают в приложении или аккаунте программы.'
            else:
                hypothesis = 'Для предложения требуется промокод, но его значение не опубликовано в источнике.'
            premise, premise_refs = _premise(
                fields.get('program', []), fields.get('audience', []),
                fields.get('benefit', []), code_blocks)
            claims.append(_claim(
                doc['source_sha256'], offer_index, 'code_delivery', 0, premise,
                hypothesis, code_refs, premise_refs, code_state=code['state'],
            ))

        for number, date in enumerate(offer.get('dates', [])):
            evidence = ' '.join(_plain(value['text']) for value in date['blocks'])
            role = date['role']
            premise, premise_refs = _premise(
                fields.get('program', []), fields.get('audience', []),
                fields.get('benefit', []), date['blocks'])
            claims.append(_claim(
                doc['source_sha256'], offer_index, 'date_role', number, premise,
                DATE_TEXT[role] + evidence, _refs(date['blocks']), premise_refs,
                role=role,
            ))

    reasons = list(dict.fromkeys(reasons))
    ready = bool(claims) and not reasons and checked.get('status') == 'references_checked_needs_semantic_review'
    return {
        'version': VERSION,
        'source_sha256': doc['source_sha256'],
        'status': 'claims_ready_for_independent_review' if ready else 'review_required',
        'reasons': reasons,
        'claims': claims,
        'publication_allowed': False,
    }
