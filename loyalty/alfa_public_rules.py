"""Public Alfa-owned PDF rules: practical Alfa Only benefits without bank authentication."""
from __future__ import annotations
import asyncio
import hashlib
import io
import re
from urllib.parse import urlsplit

import requests
from pypdf import PdfReader

from normalized import make_offer, validate_offer

CORE_URL = "https://alfabank.servicecdn.ru/site-upload/4b/2c/2366/prog_loyal_v47.pdf"
CASHBACK_URL = "https://alfabank.servicecdn.ru/site-upload/c6/bb/2366/Loyalty_program_rules_revCashBack_25052026.pdf"
ALLOWED = {CORE_URL, CASHBACK_URL}
MAX_BYTES = 8_000_000
PROGRAM = "Alfa Only"
COMMON_WARNINGS = [
    "user_eligibility_not_verified",
    "participant_and_level_not_inferred",
    "authenticated_partner_catalog_not_read",
    "newer_document_revision_not_auto_discovered",
]


def _compact(value: str) -> str:
    value = value.replace("\u00ad", "")
    value = re.sub(r"(?<=\w)-\s+(?=\w)", "", value)
    return re.sub(r"\s+", " ", value).strip()


def _must(text: str, pattern: str, code: str) -> str:
    m = re.search(pattern, text, re.I)
    if not m:
        raise ValueError(code)
    return _compact(m.group(0))


def fetch_pdf(url: str, *, get=requests.get) -> bytes:
    if url not in ALLOWED:
        raise ValueError("alfa_public_rules_url_outside_allowlist")
    try:
        with get(
            url,
            headers={"User-Agent": "LoyaltyCatalogResearchBot/1.0", "Accept": "application/pdf"},
            timeout=(8, 35),
            allow_redirects=False,
            stream=True,
        ) as res:
            if res.status_code == 429 or res.headers.get("Retry-After"):
                raise RuntimeError("alfa_public_rules_rate_limited")
            if res.status_code != 200:
                raise RuntimeError("alfa_public_rules_http_" + str(res.status_code))
            raw = bytearray()
            for block in res.iter_content(65536):
                raw.extend(block)
                if len(raw) > MAX_BYTES:
                    raise RuntimeError("alfa_public_rules_pdf_too_large")
    except RuntimeError:
        raise
    except requests.RequestException:
        raise RuntimeError("alfa_public_rules_transport_failed") from None
    data = bytes(raw)
    if not data.startswith(b"%PDF-"):
        raise RuntimeError("alfa_public_rules_not_pdf")
    return data


def pdf_text(data: bytes) -> str:
    if not data.startswith(b"%PDF-") or len(data) > MAX_BYTES:
        raise ValueError("alfa_public_rules_pdf_identity")
    reader = PdfReader(io.BytesIO(data))
    if not 5 <= len(reader.pages) <= 80:
        raise ValueError("alfa_public_rules_page_bound")
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    result = _compact("\n".join(parts))
    if len(result) < 5000:
        raise ValueError("alfa_public_rules_text_too_short")
    return result


def _offer(source_id: str, native_id: str, title: str, benefit: str, conditions: str,
           url: str, observed_at: str, *, revision: int, effective_from: str, sha: str,
           partner: str | None = "Альфа-Банк"):
    row = make_offer(
        source_id,
        native_id,
        PROGRAM,
        partner,
        benefit,
        url,
        observed_at,
        title=title,
        conditions=conditions,
        link_kind="document_section",
        locator=native_id,
        record_kind="tier_benefit",
        source_status="public_rules_document",
        valid_from=effective_from,
        details={
            "document_revision": revision,
            "document_sha256": sha,
            "document_effective_from": effective_from,
            "evidence_role": "public_alfa_only_rules_not_authenticated_partner_catalog",
            "authenticated_catalogue_equivalence": False,
        },
        warnings=list(COMMON_WARNINGS),
    )
    validate_public_record(row)
    return row


def parse_core(data: bytes, observed_at: str) -> list[dict]:
    text = pdf_text(data)
    sha = hashlib.sha256(data).hexdigest()
    _must(text, r"Редакция\s*№\s*47", "alfa_core_revision_missing")
    _must(
        text,
        r"Версия\s*№\s*47\s*Правил\s*введена\s*в\s*действие\s*с\s*01\.05\.2026",
        "alfa_core_effective_date_missing",
    )

    taxi_benefit = _must(
        text,
        r"Выплата.{0,160}?денежные\s*средства.{0,800}?такси,\s*трансфер\s*и\s*каршеринг.{0,180}?2\s*500.{0,120}?рублей",
        "alfa_taxi_benefit_missing",
    )
    taxi_conditions = "\n".join([
        _must(
            text,
            r"Операция\s*становится\s*доступной\s*для\s*получения\s*Выплаты\s*в\s*течение\s*2\s*рабочих\s*дней.{0,320}?такси,\s*трансфер\s*и\s*каршеринг",
            "alfa_taxi_availability_missing",
        ),
        _must(
            text,
            r"Получить\s*Выплату\s*по\s*Операции\s*по\s*Карте\s*можно\s*только\s*по\s*лимитам\s*Поощрения\s*того\s*месяца,\s*в\s*котором\s*была\s*оформлена\s*заявка\s*на\s*получение\s*Выплаты",
            "alfa_taxi_month_limit_missing",
        ),
    ])

    lounge_benefit = _must(
        text,
        r"6\.6\.3\..{0,650}?не\s*более\s*2\s*500.{0,120}?рублей\s*за\s*доступ\s*одного\s*лица",
        "alfa_lounge_benefit_missing",
    )
    lounge_limit = _must(
        text,
        r"6\.6\.7\..{0,120}?максимальная\s*сумма\s*Выплаты\s*БЗ\s*составляет\s*20\s*000.{0,120}?рублей\s*на\s*одного\s*Участника\s*за\s*один\s*календарный\s*месяц",
        "alfa_lounge_limit_missing",
    )

    restaurant_benefit = _must(
        text,
        r"Выплата\s*за\s*посещение\s*ресторанов/\s*кафе/\s*баров.{0,700}?не\s*более\s*2\s*500.{0,130}?при\s*списании\s*1.{0,130}?не\s*более\s*5\s*000.{0,130}?при\s*списании\s*2",
        "alfa_restaurant_benefit_missing",
    )
    restaurant_limit = _must(
        text,
        r"6\.7\.7\..{0,120}?максимальная\s*сумма\s*Выплаты\s*РКБ\s*составляет\s*20\s*000.{0,120}?рублей\s*на\s*одного\s*Участника\s*за\s*один\s*календарный\s*месяц",
        "alfa_restaurant_limit_missing",
    )

    qr_benefit = _must(
        text,
        r"6\.8\.2\..{0,500}?количество\s*лиц,\s*сопровождающих\s*Участника\s*\(не\s*более\s*3.{0,220}?нажать\s*на\s*кнопку\s*[«\"]Выпустить\s*QR-код[»\"]",
        "alfa_qr_lounge_missing",
    )
    qr_conditions = _must(
        text,
        r"6\.8\.3\..{0,900}?в\s*течение\s*24\s*часов.{0,500}?Вернуть.{0,350}?24\s*часов",
        "alfa_qr_return_missing",
    )

    rbc_benefit = _must(
        text,
        r"Промо-баллы\s*могут\s*быть\s*использованы.{0,520}?Подписк[еи]\s*на\s*РБК.{0,420}?от\s*6\s*000\s*000\s*рублей",
        "alfa_rbc_benefit_missing",
    )
    rbc_conditions = _must(
        text,
        r"6\.5\.1\..{0,500}?раздел\s*[«\"]Alfa\s*Only[»\"].{0,120}?РБК.{0,350}?Alfa\s*ID",
        "alfa_rbc_conditions_missing",
    )

    return [
        _offer("alfa_only_public_rules", "core47:taxi-transfer-carsharing", "Alfa Only — такси, трансфер и каршеринг",
               taxi_benefit, taxi_conditions, CORE_URL, observed_at, revision=47,
               effective_from="2026-05-01", sha=sha),
        _offer("alfa_only_public_rules", "core47:lounge-reimbursement", "Alfa Only — возмещение бизнес-залов",
               lounge_benefit, lounge_limit, CORE_URL, observed_at, revision=47,
               effective_from="2026-05-01", sha=sha),
        _offer("alfa_only_public_rules", "core47:airport-restaurants", "Alfa Only — рестораны, кафе и бары в аэропортах РФ",
               restaurant_benefit, restaurant_limit, CORE_URL, observed_at, revision=47,
               effective_from="2026-05-01", sha=sha),
        _offer("alfa_only_public_rules", "core47:qr-lounges", "Alfa Only — QR-доступ в бизнес-залы",
               qr_benefit, qr_conditions, CORE_URL, observed_at, revision=47,
               effective_from="2026-05-01", sha=sha),
        _offer("alfa_only_public_rules", "core47:rbc", "Alfa Only — подписка РБК",
               rbc_benefit, rbc_conditions, CORE_URL, observed_at, revision=47,
               effective_from="2026-05-01", sha=sha, partner="РБК"),
    ]


def parse_cashback(data: bytes, observed_at: str) -> list[dict]:
    text = pdf_text(data)
    sha = hashlib.sha256(data).hexdigest()
    _must(text, r"Редакция\s*№\s*101", "alfa_cashback_revision_missing")
    _must(
        text,
        r"Редакция\s*№\s*101\s*Правил\s*введена\s*в\s*действие\s*с\s*25\.05\.2026",
        "alfa_cashback_effective_date_missing",
    )
    evidence = _must(
        text,
        r"УЛК\s*\(с\s*оформлением\s*ПУ\s*[«\"]Alfa\s*Only[»\"]\).{0,450}?5\s*Категорий.{0,280}?30\s*000\s*Альфа-Баллов.{0,180}?50\s*000\s*Альфа-Баллов.{0,100}?500\s*000\s*рублей",
        "alfa_cashback_only_row_missing",
    )
    row = _offer(
        "alfa_only_cashback_rules",
        "cashback101:alfa-only-limits",
        "Alfa Only — лимиты программы кэшбэка",
        evidence,
        "Ставки конкретных категорий выбираются и отображаются в «Кэшбэк и сервисы»; публичный документ фиксирует минимальное количество категорий и общие лимиты, но не персональные ставки.",
        CASHBACK_URL,
        observed_at,
        revision=101,
        effective_from="2026-05-25",
        sha=sha,
    )
    return [row]


async def collect_core(cfg, report, observed_at, limit):
    if cfg["url"] != CORE_URL:
        raise ValueError("alfa_core_config_url_changed")
    data = await asyncio.to_thread(fetch_pdf, CORE_URL)
    rows = parse_core(data, observed_at)
    rows = rows[:limit]
    report["discovered"] = len(rows)
    report["coverage"] = "five_practical_benefits_from_public_core_rules_revision_47; authenticated_partner_catalog_not_read"
    return rows


async def collect_cashback(cfg, report, observed_at, limit):
    if cfg["url"] != CASHBACK_URL:
        raise ValueError("alfa_cashback_config_url_changed")
    data = await asyncio.to_thread(fetch_pdf, CASHBACK_URL)
    rows = parse_cashback(data, observed_at)
    rows = rows[:limit]
    report["discovered"] = len(rows)
    report["coverage"] = "alfa_only_cashback_limits_from_public_reverse_cashback_rules_revision_101; personal_category_rates_not_read"
    return rows


def validate_public_record(row: dict) -> None:
    sid = row.get("source_id")
    if sid not in ("alfa_only_public_rules", "alfa_only_cashback_rules"):
        raise ValueError("alfa_public_record_wrong_source")
    expected_url = CORE_URL if sid == "alfa_only_public_rules" else CASHBACK_URL
    expected_revision = 47 if sid == "alfa_only_public_rules" else 101
    expected_from = "2026-05-01" if sid == "alfa_only_public_rules" else "2026-05-25"
    details = row.get("details", {})
    if (
        row.get("source_url") != expected_url
        or row.get("source_status") != "public_rules_document"
        or row.get("record_kind") != "tier_benefit"
        or row.get("link_kind") != "document_section"
        or row.get("benefit_url") is not None
        or details.get("document_revision") != expected_revision
        or details.get("document_effective_from") != expected_from
        or details.get("authenticated_catalogue_equivalence") is not False
        or details.get("evidence_role") != "public_alfa_only_rules_not_authenticated_partner_catalog"
        or not re.fullmatch(r"[a-f0-9]{64}", details.get("document_sha256", ""))
        or not set(COMMON_WARNINGS).issubset(row.get("warnings", []))
    ):
        raise ValueError("alfa_public_record_evidence_mismatch")
