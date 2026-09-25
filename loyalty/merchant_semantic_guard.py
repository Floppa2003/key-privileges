"""Conservative, merchant-independent semantic guards for hydrated block evidence.

This module does not decide that an offer is true. It only rejects structurally
unsupported interpretations before any independent semantic review.
"""
from __future__ import annotations
import re
from datetime import date
from typing import Any

HOLDER = re.compile(
    r"(?:держател\w*|обладател\w*|участник\w*\s+(?:программ\w*|клуб\w*)|"
    r"cardholders?|members?\s+of\s+(?:the\s+)?(?:programme|program|club))", re.I)
BENEFIT = re.compile(
    r"(?:скидк\w*|discount|к[еэ]шб[еэ]к|cashback|балл\w*|points?|мил\w*|miles?|"
    r"подар\w*|gift|бесплат\w*|free|выгод\w*)", re.I)
CODE = re.compile(r"(?:промокод|promo\s*code|coupon\s*code|код\s+скидк)", re.I)
EVENT = re.compile(
    r"(?:мероприяти\w*|событи\w*|школьник\w*|участник\w*\s+акци\w*|"
    r"были\s+вручен\w*|event\s+participants?|were\s+given)", re.I)
EXPLICIT_VALIDITY_END = re.compile(
    r"(?:срок\s+(?:проведения|действия)\s+(?:программы|акции|предложения)|"
    r"(?:программа|акция|предложение)\s+действует)"
    r"[^\n]{0,240}?(?:по|до)\s*"
    r"(\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2})", re.I)

ROLE = {
    "booking": re.compile(r"(?:брониров\w*|заброниров\w*|booking|reservation)", re.I),
    "stay": re.compile(r"(?:проживан\w*|заезд\w*|выезд\w*|stay|check[- ]?in|check[- ]?out)", re.I),
    "publication": re.compile(r"(?:опублик\w*|publication|published|дата\s+публикац)", re.I),
    "offer": re.compile(r"(?:срок\s+действ\w*|акци\w*\s+(?:действ|проход)|действует\s+(?:до|с)|valid\s+(?:until|from)|offer\s+period)", re.I),
}


def _date_value(value: str) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        if re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", value):
            day, month, year = map(int, value.split('.'))
            return date(year, month, day)
        match = re.match(r"^(\d{4}-\d{2}-\d{2})", value)
        return date.fromisoformat(match.group(1)) if match else None
    except ValueError:
        return None

def _explicit_validity_end(text: str) -> date | None:
    match = EXPLICIT_VALIDITY_END.search(text)
    return _date_value(match.group(1)) if match else None

def _joined(blocks: list[dict]) -> str:
    return " ".join(str(b.get("text", "")) for b in blocks)

def assess(target: dict, offer: dict, observed_at: str | None = None) -> dict:
    """Return a conservative precision gate over merchant_blocks.check() output."""
    reasons: list[str] = []
    fields = offer.get("fields", {})
    audience = _joined(fields.get("audience", []))
    benefit = _joined(fields.get("benefit", []))
    context = str(offer.get("source_context", {}).get("text", ""))
    program = " ".join([str(target.get("program", "")), *map(str, target.get("aliases", []))])

    if not audience:
        reasons.append("audience_missing")
    elif not HOLDER.search(audience):
        reasons.append("audience_not_explicit_beneficiary")

    if not benefit or not BENEFIT.search(benefit):
        reasons.append("benefit_not_explicit")

    # A past/event-scoped giveaway must not become a reusable cardholder entitlement.
    if EVENT.search(context) and (not audience or not HOLDER.search(audience)):
        reasons.append("event_not_cardholder_entitlement")

    observed = _date_value(observed_at) if observed_at else None
    validity_end = _explicit_validity_end(context)
    if observed is not None and validity_end is not None and validity_end < observed:
        reasons.append("expired_at_observation")

    code = offer.get("code", {})
    if code.get("state") in ("literal", "app_or_account", "required_not_published"):
        code_text = _joined(code.get("blocks", []))
        if not CODE.search(code_text):
            reasons.append("code_role_not_explicit")

    checked_dates = []
    for d in offer.get("dates", []):
        role = d.get("role")
        text = _joined(d.get("blocks", []))
        verified = role == "unclear"
        if role in ROLE:
            verified = bool(ROLE[role].search(text))
            if not verified:
                reasons.append(f"date_role_not_explicit:{role}")
        checked_dates.append({"role": role, "role_guard_passed": verified})

    # Keep all pre-existing review reasons; this guard can only add caution.
    for reason in offer.get("review_reasons", []):
        if reason not in reasons:
            reasons.append(reason)

    return {
        "version": "merchant-semantic-guard-v1",
        "publication_allowed": False,
        "status": "guard_pass_needs_independent_review" if not reasons else "review_required",
        "reasons": reasons,
        "dates": checked_dates,
        "target_program_evidence": bool(program.strip()),
    }

def assess_result(target: dict, checked: dict) -> dict:
    observed_at = checked.get('observed_at')
    offers = [assess(target, o, observed_at) for o in checked.get("offers", [])]
    return {
        "version": "merchant-semantic-guard-v1",
        "publication_allowed": False,
        "status": "guard_pass_needs_independent_review" if offers and all(o["status"].startswith("guard_pass") for o in offers) else "review_required",
        "offers": offers,
    }
