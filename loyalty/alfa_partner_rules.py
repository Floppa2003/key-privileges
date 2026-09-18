"""Reviewed public Alfa Only partner-promotion PDFs from Alfa-owned CDN.

This is a bounded, source-owned complement to the authenticated partner-offers
catalogue. Exact PDF URLs are reviewed configuration; the parser derives dates,
legal partner identity, rate/cap and transaction scope from the fetched document.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import re
from datetime import date
from urllib.parse import urlsplit

import requests
from pypdf import PdfReader

from normalized import make_offer, validate_offer

SOURCE_ID = "alfa_only_partner_pdf_offers"
PROGRAM = "Alfa Only"
MAX_BYTES = 4_000_000
MAX_PAGES = 12

DOCS = [
    {
        "native_id": "betulla_0126",
        "display_name": "Betulla",
        "url": "https://alfabank.servicecdn.ru/site-upload/ea/cc/1007/betulla_only_0126.pdf",
        "ogrn": "1207800041833",
        "address_marker": "9-я Советская",
    },
    {
        "native_id": "r14_0126",
        "display_name": "Р14",
        "url": "https://alfabank.servicecdn.ru/site-upload/22/58/1007/r14_only_0126.pdf",
        "ogrn": "1047855044203",
        "address_marker": "Академика Павлова",
    },
    {
        "native_id": "takhauli_0226",
        "display_name": "Такахули",
        "url": "https://alfabank.servicecdn.ru/site-upload/e6/79/1007/tkh_only_02.26.pdf",
        "ogrn": "1227700078726",
        "address_marker": "Малая Бронная",
    },
]
BY_URL = {x["url"]: x for x in DOCS}
BY_ID = {x["native_id"]: x for x in DOCS}

MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
    "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}

WARNINGS = [
    "user_eligibility_not_verified",
    "authenticated_partner_catalog_not_read",
    "public_partner_pdf_inventory_not_exhaustive",
    "search_discovery_is_not_source_inventory",
]


def compact(value: str) -> str:
    value = value.replace("\u00ad", "")
    value = re.sub(r"(?<=\w)-\s+(?=\w)", "", value)
    return re.sub(r"\s+", " ", value).strip()


def fetch_pdf(url: str, *, get=requests.get) -> bytes:
    if url not in BY_URL:
        raise ValueError("alfa_partner_pdf_url_outside_allowlist")
    try:
        with get(
            url,
            headers={"User-Agent": "LoyaltyCatalogResearchBot/1.0", "Accept": "application/pdf"},
            timeout=(8, 30),
            allow_redirects=False,
            stream=True,
        ) as res:
            if res.status_code == 429 or res.headers.get("Retry-After"):
                raise RuntimeError("alfa_partner_pdf_rate_limited")
            if res.status_code != 200:
                raise RuntimeError("alfa_partner_pdf_http_" + str(res.status_code))
            raw = bytearray()
            for block in res.iter_content(65536):
                raw.extend(block)
                if len(raw) > MAX_BYTES:
                    raise RuntimeError("alfa_partner_pdf_size_bound")
    except RuntimeError:
        raise
    except requests.RequestException:
        raise RuntimeError("alfa_partner_pdf_transport_failed") from None
    data = bytes(raw)
    if not data.startswith(b"%PDF-"):
        raise RuntimeError("alfa_partner_pdf_not_pdf")
    return data


def pdf_text(data: bytes) -> str:
    if not data.startswith(b"%PDF-") or len(data) > MAX_BYTES:
        raise ValueError("alfa_partner_pdf_identity")
    reader = PdfReader(io.BytesIO(data))
    if not 4 <= len(reader.pages) <= MAX_PAGES:
        raise ValueError("alfa_partner_pdf_page_bound")
    result = compact("\n".join(page.extract_text() or "" for page in reader.pages))
    if len(result) < 3500:
        raise ValueError("alfa_partner_pdf_text_too_short")
    return result


def must(text: str, pattern: str, code: str) -> str:
    match = re.search(pattern, text, re.I)
    if not match:
        raise ValueError(code)
    return compact(match.group(0))


def source_date(day: str, month: str, year: str) -> str:
    m = MONTHS.get(month.casefold())
    if not m:
        raise ValueError("alfa_partner_pdf_unknown_month")
    return date(int(year), m, int(day)).isoformat()


def validity(text: str) -> tuple[str, str]:
    match = re.search(
        r"Акция\s*Партнера.{0,420}?период\s*с\s*[«\"](?P<d1>\d{1,2})[»\"]\s*"
        r"(?P<m1>[А-Яа-яё]+)\s*(?P<y1>20\d{2})\s*г?\.?\s*"
        r"(?:[-–—]|по)\s*[«\"](?P<d2>\d{1,2})[»\"]\s*"
        r"(?P<m2>[А-Яа-яё]+)\s*(?P<y2>20\d{2})\s*г?",
        text,
        re.I,
    )
    if not match:
        raise ValueError("alfa_partner_pdf_validity_missing")
    return (
        source_date(match["d1"], match["m1"], match["y1"]),
        source_date(match["d2"], match["m2"], match["y2"]),
    )


def parse_document(spec: dict, data: bytes, observed_at: str) -> dict:
    if spec.get("url") not in BY_URL or BY_URL[spec["url"]] != spec:
        raise ValueError("alfa_partner_pdf_spec_identity")
    text = pdf_text(data)
    sha = hashlib.sha256(data).hexdigest()

    title = must(
        text,
        r"Акци[ия]\s*[«\"]К[еэ]шб[еэ]к\s*до\s*10%\s*за\s*(?:первую\s*)?покупк[уи]\s*Alfa\s*Only[»\"]",
        "alfa_partner_pdf_title_missing",
    )
    valid_from, valid_until = validity(text)

    legal = re.search(
        r"Партнер\s*[–—-]\s*(?P<legal>ООО\s*[«\"][^»\"]+[»\"]).{0,80}?ОГРН\s*[:№]?\s*(?P<ogrn>\d{13})",
        text,
        re.I,
    )
    if not legal or legal["ogrn"] != spec["ogrn"]:
        raise ValueError("alfa_partner_pdf_legal_identity")

    eligibility = must(
        text,
        r"Участник\s*Акции\s*[–—-]\s*Клиент.{0,260}?обслуживающ[ийе][йся]*\s*в\s*рамках\s*Пакета\s*услуг\s*[«\"]Alfa\s*Only[»\"].{0,260}?присоединился\s*к\s*участию\s*в\s*Акции",
        "alfa_partner_pdf_eligibility_missing",
    )
    territory = must(
        text,
        r"2\.2\..{0,260}?Акция\s*Партнера\s*проводится.{0,260}?(?:г\.|город)[А-Яа-яё .-]+",
        "alfa_partner_pdf_territory_missing",
    )
    benefit_clause = must(
        text,
        r"3\.2\..{0,420}?получают\s*Альфа-Баллы/.{0,120}?по\s*ставке\s*10\s*%.{0,220}?не\s*более\s*1\s*500.{0,260}?от\s*суммы\s*(?:всех|первой)\s*Расходн[а-я]+\s*операц[а-я]+.{0,220}?календарного\s*месяца",
        "alfa_partner_pdf_benefit_missing",
    )
    scope = "first_transaction_each_calendar_month" if re.search(
        r"от\s*суммы\s*первой\s*Расходн", benefit_clause, re.I
    ) else "all_transactions_in_calendar_month"

    stacking = must(
        text,
        r"Альфа-Баллы/.{0,260}?не\s*суммируются.{0,420}?с\s*наибольшим\s*значением",
        "alfa_partner_pdf_stacking_missing",
    )
    payout = must(
        text,
        r"Начисление.{0,360}?производится\s*Банком\s*в\s*течение\s*10\s*дней\s*с\s*даты\s*окончания\s*календарного\s*месяца",
        "alfa_partner_pdf_payout_missing",
    )
    appendix = must(
        text,
        r"Список\s*ТСП\s*Партнера\s*:.{0,700}$",
        "alfa_partner_pdf_appendix_missing",
    )
    if spec["address_marker"].casefold() not in appendix.casefold():
        raise ValueError("alfa_partner_pdf_tsp_identity")

    benefit = title + ". " + benefit_clause
    conditions = "\n".join([eligibility, territory, stacking, payout, appendix])

    row = make_offer(
        SOURCE_ID,
        spec["native_id"],
        PROGRAM,
        spec["display_name"],
        benefit,
        spec["url"],
        observed_at,
        title=f"Alfa Only → {spec['display_name']} — 10%",
        conditions=conditions,
        link_kind="document_section",
        locator="partner_rules:3.2",
        record_kind="partner_offer",
        source_status="public_partner_rules_document",
        valid_from=valid_from,
        valid_until=valid_until,
        details={
            "document_sha256": sha,
            "legal_partner": compact(legal["legal"]),
            "partner_ogrn": legal["ogrn"],
            "transaction_scope": scope,
            "authenticated_catalogue_equivalence": False,
            "search_discovery_inventory_complete": False,
            "tsp_appendix": appendix,
        },
        warnings=list(WARNINGS),
    )
    validate_partner_record(row)
    return row


def validate_partner_record(row: dict) -> None:
    if row.get("source_id") != SOURCE_ID:
        raise ValueError("alfa_partner_pdf_wrong_source")
    spec = BY_ID.get(row.get("native_id"))
    if not spec:
        raise ValueError("alfa_partner_pdf_unknown_record")
    details = row.get("details", {})
    if (
        row.get("source_url") != spec["url"]
        or row.get("program") != PROGRAM
        or row.get("partner_name") != spec["display_name"]
        or row.get("source_status") != "public_partner_rules_document"
        or row.get("record_kind") != "partner_offer"
        or row.get("link_kind") != "document_section"
        or row.get("benefit_url") is not None
        or details.get("partner_ogrn") != spec["ogrn"]
        or details.get("authenticated_catalogue_equivalence") is not False
        or details.get("search_discovery_inventory_complete") is not False
        or details.get("transaction_scope") not in (
            "first_transaction_each_calendar_month",
            "all_transactions_in_calendar_month",
        )
        or not re.fullmatch(r"[a-f0-9]{64}", details.get("document_sha256", ""))
        or spec["address_marker"].casefold() not in str(details.get("tsp_appendix", "")).casefold()
        or not set(WARNINGS).issubset(row.get("warnings", []))
    ):
        raise ValueError("alfa_partner_pdf_evidence_mismatch")


async def collect(cfg, report, observed_at: str, limit: int) -> list[dict]:
    if cfg.get("url") != "https://alfabank.servicecdn.ru/" or cfg.get("id") != SOURCE_ID:
        raise ValueError("alfa_partner_pdf_config_identity")
    rows = []
    errors = []
    for spec in DOCS[:limit]:
        try:
            data = await asyncio.to_thread(fetch_pdf, spec["url"])
            rows.append(parse_document(spec, data, observed_at))
        except Exception as exc:
            reason = str(exc) if isinstance(exc, (ValueError, RuntimeError)) else type(exc).__name__
            errors.append({"phase": "partner_pdf", "native_id": spec["native_id"], "reason": reason[:160]})
    report["discovered"] = len(DOCS)
    report["coverage"] = (
        "three_reviewed_public_alfa_only_partner_rule_pdfs; "
        "search_discovery_inventory_not_exhaustive; authenticated_partner_catalog_not_read"
    )
    report["errors"].extend(errors)
    return rows
