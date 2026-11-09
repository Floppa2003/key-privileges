"""Public Alfa-owned PDF rules: practical Alfa Only benefits without bank authentication."""
from __future__ import annotations
import asyncio
import hashlib
import io
import re
from urllib.parse import urlsplit

import requests
from pypdf import PdfReader

from normalized import make_offer, validate_offer, NUMERIC_TOKEN, literal_number, number_starts_here
from quantity_offers import count_value

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


_WORDS = r'(?:\s*\([^()]{1,150}\))?'


def _money(name):
    return rf'(?P<m_{name}>{NUMERIC_TOKEN}){_WORDS}\s*рубл(?:ей|я|ь)\b'


def _count(name, unit):
    return rf'(?P<n_{name}>{NUMERIC_TOKEN}){_WORDS}\s*(?:{unit})\b'


def _literal_count(name,unit):
    return rf'(?P<w_{name}>{NUMERIC_TOKEN}|[а-яё]+(?:\s+[а-яё]+)?){_WORDS}\s*(?:{unit})\b'


def _until(marker, maximum):
    """Stop at the first owned label, including when its following value is bad."""
    return rf'(?:(?!{marker}).){{0,{maximum}}}?'


def _valid_number(match, group, code, *, integer=False, price_separator=False):
    value=literal_number(match[group])
    prefix=match.string[:match.start(group)]
    # The dash in an already matched "uses — cost" pair is table structure.
    if price_separator:prefix=re.sub(r'[–—-]\s*$','',prefix)
    if (value is None or not number_starts_here(match.string,match.start(group))
            or re.search(r'(?:[+−-]\s*|[–—]|\d\s*[–—-]\s*)$',prefix)
            or (integer and (not value.isdecimal() or int(value)<=0))):
        raise ValueError(code)
    return value


def _owned_match(text, anchor, pattern, code):
    starts=list(re.finditer(r'(?<![\d.])'+anchor,text,re.I))
    if len(starts)!=1:raise ValueError(code)
    match=re.match(pattern,text[starts[0].start():],re.I)
    if match is None:raise ValueError(code)
    for name,value in match.groupdict().items():
        if value is None:continue
        if name.startswith(('m_','n_')):
            _valid_number(match,name,code,integer=name.startswith('n_'))
        elif name.startswith('w_'):
            parsed=count_value(value)
            if parsed is None or parsed<=0:raise ValueError(code)
            if value[0].isdigit():_valid_number(match,name,code,integer=True)
    return match


def _owned(text, anchor, pattern, code):
    return _compact(_owned_match(text,anchor,pattern,code)[0])


def _payout_limit(text,section,subject,code):
    starts=list(re.finditer(r'(?<![\d.])'+section,text,re.I))
    if len(starts)!=1:raise ValueError(code)
    tail=text[starts[0].end():]
    stop=re.search(r'(?<![\d.])\d+(?:\.\d+){1,3}\.(?=\s)',tail)
    owned=text[starts[0].start():starts[0].end()]+(tail[:stop.start()] if stop else tail)
    label=rf'максимальная\s*сумма\s*Выплаты\s*{subject}\s*составляет\s*'
    if len(list(re.finditer(label,owned,re.I)))!=1:raise ValueError(code)
    return _owned(owned,section,section+_until(label,120)+label+_money('cap')
        +r'\s*на\s*'+_literal_count('participants',r'Участник(?:а|ов)?')
        +r'\s*за\s*'+_literal_count('months',r'календарн(?:ый|ых)\s*месяц(?:а|ев)?'),code)


def _insurance_row(text):
    code='alfa_vzr_promo_limit_missing'
    label=r'Услуга\s*по\s*Страхованию\s*ВЗР'
    starts=list(re.finditer(label+r'(?=\s+(?:[+−-]?\d|Не предоставляется))',text,re.I))
    if len(starts)!=1:raise ValueError(code)
    tail=text[starts[0].end():]
    stop=re.search(r'Услуга\s*доступа\s*к\s*контенту|Единовременно\s*Участнику',tail,re.I)
    cells=tail[:stop.start()] if stop else tail
    if len(cells)>3000:raise ValueError(code)
    pair=re.compile(_count('uses',r'раз(?:а)?')+r'\s*[–—-]\s*'+_count('cost',r'Промо\s*-\s*балл(?:а|ов)?'),re.I)
    matches=list(pair.finditer(cells))
    if not matches:raise ValueError(code)
    for match in matches:
        for name in ('n_uses','n_cost'):
            _valid_number(match,name,code,integer=True,price_separator=name=='n_cost')
    remainder=pair.sub('',cells)
    remainder=re.sub(r'Не\s*предоставляется','',remainder,flags=re.I)
    if re.sub(r'[\s.;,]+','',remainder):raise ValueError(code)
    # Every column stays literal; this does not assign a price to every member.
    return _compact(text[starts[0].start():starts[0].end()]+cells).rstrip(' .')


def _cashback_row(text):
    code='alfa_cashback_only_row_missing'
    anchor=r'УЛК\s*\(с\s*оформлением\s*ПУ\s*[«\"]Alfa\s*Only[»\"]\)'
    starts=list(re.finditer(anchor,text,re.I))
    if len(starts)!=1:raise ValueError(code)
    tail=text[starts[0].start():]
    stop=re.search(r'ПУ\s*[«\"]А-Клуб[»\"]|\b2\.2\.',tail,re.I)
    row=(tail[:stop.start()] if stop else tail).strip().rstrip(' .')
    if len(row)>3000:raise ValueError(code)
    category=list(re.finditer(_count('category',r'Категори(?:й|я|и)'),row,re.I))
    points=list(re.finditer(rf'(?P<amount>{NUMERIC_TOKEN})\s*Альфа\s*-?\s*Балл(?:ов|а)?\b',row,re.I))
    money=list(re.finditer(_money('operation'),row,re.I))
    if (len(category)!=1 or len(points)<2 or len(money)!=1
            or len(points)!=len(re.findall(r'Альфа\s*-?\s*Балл(?:ов|а)?\b',row,re.I))
            or len(category)!=len(re.findall(r'\bКатегори(?:й|я|и)\b',row,re.I))):
        raise ValueError(code)
    _valid_number(category[0],'n_category',code,integer=True)
    for match in points:_valid_number(match,'amount',code)
    _valid_number(money[0],'m_operation',code)
    if not category[0].end()<=points[0].start()<points[-1].end()<=money[0].start():
        raise ValueError(code)
    if row[money[0].end():].strip(' .;'):raise ValueError(code)
    return row


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
    text = _compact(pdf_text(data))
    sha = hashlib.sha256(data).hexdigest()
    _must(text, r"Редакция\s*№\s*47", "alfa_core_revision_missing")
    _must(
        text,
        r"Версия\s*№\s*47\s*Правил\s*введена\s*в\s*действие\s*с\s*01\.05\.2026",
        "alfa_core_effective_date_missing",
    )

    maximum=r'не\s*более\s*'
    taxi_anchor=r'Выплата\s*[–—-]\s*денежные\s*средства'
    taxi_benefit = _owned(
        text,
        taxi_anchor,
        taxi_anchor+r'.{0,800}?такси,\s*трансфер\s*и\s*каршеринг'+_until(maximum,180)+maximum+_money('cap'),
        "alfa_taxi_benefit_missing",
    )
    taxi_conditions = "\n".join([
        _owned(
            text,
            r'Операция\s*становится\s*доступной\s*для\s*получения\s*Выплаты\s*в\s*течение',
            r'Операция\s*становится\s*доступной\s*для\s*получения\s*Выплаты\s*в\s*течение\s*'
            +_count('days',r'рабоч(?:их|его)\s*дн(?:ей|я)')+r'.{0,320}?такси,\s*трансфер\s*и\s*каршеринг',
            "alfa_taxi_availability_missing",
        ),
        _must(
            text,
            r"Получить\s*Выплату.{0,220}?лимитам\s*Поощрения\s*того\s*месяца.{0,160}?был\s*а\s*оформлена\s*заявка\s*на\s*получение\s*Выплаты",
            "alfa_taxi_month_limit_missing",
        ),
    ])

    lounge_benefit = _owned(
        text,
        r'6\.6\.3\.',
        r'6\.6\.3\.'+_until(r'не\s*более\b(?!\s*следующих\s*сумм\b)',650)
        +maximum+_money('cap')+r'\s*за\s*доступ\s*'+_literal_count('people',r'лиц(?:а|о)?'),
        "alfa_lounge_benefit_missing",
    )
    lounge_limit = _payout_limit(text,r'6\.6\.7\.',r'БЗ',"alfa_lounge_limit_missing")

    restaurant_anchor=r'Выплата\s*за\s*посещение\s*ресторанов/\s*кафе/\s*баров'
    points=r'(?:Альфа\s*-\s*)?Балл(?:а|ов)?'
    restaurant_benefit = _owned(
        text,
        restaurant_anchor,
        restaurant_anchor+_until(maximum,700)+maximum+_money('first')
        +r'\s*при\s*списании\s*'+_count('first',points)+r'\s*(?:или|и)\s*'
        +maximum+_money('second')+r'\s*при\s*списании\s*'+_count('second',points),
        "alfa_restaurant_benefit_missing",
    )
    restaurant_limit = _payout_limit(text,r'6\.7\.7\.',r'РКБ',"alfa_restaurant_limit_missing")

    qr_benefit = _owned(
        text,
        r'6\.8\.2\.',
        r'6\.8\.2\..{0,500}?количество\s*лиц,\s*сопровождающих\s*Участника\s*\('+maximum
        +rf'(?P<n_companions>{NUMERIC_TOKEN})'+_WORDS+r'(?=\s*(?:лиц(?:о|а)?\b|[,)]))'
        +r'.{0,220}?нажать\s*на\s*кнопку\s*[«\"]Выпустить\s*QR\s*-\s*код[»\"]',
        "alfa_qr_lounge_missing",
    )
    qr_conditions = "\n".join([
        _owned(
            text,
            r'6\.8\.3\.',
            r'6\.8\.3\..{0,520}?не\s*смогут\s*посетить'+_until(r'в\s*течение',220)
            +r'в\s*течение\s*'+_count('hours',r'час(?:ов|а)?')+r'.{0,280}?подлежат\s*восстановлению',
            "alfa_qr_restore_missing",
        ),
        _owned(
            text,
            r'нажать\s*на\s*кнопку\s*[«\"]Вернуть[»\"]',
            r'нажать\s*на\s*кнопку\s*[«\"]Вернуть[»\"]\s*в\s*течение\s*'+_count('hours',r'час(?:ов|а)?'),
            "alfa_qr_return_action_missing",
        ),
    ])

    rbc_anchor=r'Промо-баллы\s*могут\s*быть\s*использованы.{0,520}?Подписк[еи]\s*на\s*РБК'
    rbc_benefit = _owned(
        text,
        rbc_anchor,
        rbc_anchor+_until(r'\bот\s',420)+r'\bот\s*'+_money('minimum'),
        "alfa_rbc_benefit_missing",
    )
    rbc_conditions = _must(
        text,
        r"6\.5\.1\..{0,500}?раздел\s*[«\"]Alfa\s*Only[»\"].{0,120}?РБК.{0,350}?Alfa\s*ID",
        "alfa_rbc_conditions_missing",
    )

    participants=rf'Участнику\s+{NUMERIC_TOKEN}(?:\s*(?:,|и)\s*Участнику\s+{NUMERIC_TOKEN})*'
    concierge_match = _owned_match(
        text,
        r'6\.2\.',
        r'6\.2\.\s*'+participants+r'\s*доступна\s*Услуга\s*[«\"]Консьерж\s*сервис[»\"]',
        "alfa_concierge_benefit_missing",
    )
    for participant in re.finditer(rf'Участнику\s+(?P<id>{NUMERIC_TOKEN})',concierge_match[0],re.I):
        _valid_number(participant,'id','alfa_concierge_participant_invalid',integer=True)
    concierge_benefit=_compact(concierge_match[0])
    phone_anchor=r'Телефон\s*Партнера\s*[–—-]'
    phone_match=_owned_match(text,phone_anchor,
        phone_anchor+r'[^+\d]{0,120}?(?P<phone>\+?\d[\d ()–-]{5,32}\d)(?![\d ()–-]*\d)'
        +_until(r'Консьерж\s*сервис',220)+r'Консьерж\s*сервис','alfa_concierge_phone_missing')
    phone=phone_match['phone']
    if not 8<=len(re.sub(r'\D','',phone))<=15 or phone.count('(')!=phone.count(')'):
        raise ValueError('alfa_concierge_phone_invalid')
    concierge_conditions = "\n".join([
        _must(
            text,
            r"Для\s*получения\s*Услуги\s*[«\"]Консьерж\s*сервис[»\"].{0,650}?мобильного\s*номера\s*телефона.{0,650}?обратиться\s*по\s*Телефону\s*Партнера",
            "alfa_concierge_activation_missing",
        ),
        _compact(phone_match[0]),
    ])

    simple_benefit = _must(
        text,
        r"6\.3\..{0,260}?доступен\s*статус\s*Silver\s*в\s*программе\s*SimplePrivé",
        "alfa_simple_benefit_missing",
    )
    simple_conditions = "\n".join([
        _must(
            text,
            r"Для\s*получения\s*статуса\s*Silver\s*в\s*программе\s*SimplePrivé.{0,900}?уникальной\s*ссылке.{0,700}?мобильный\s*номер\s*телефона.{0,650}?персональному\s*менеджеру",
            "alfa_simple_activation_missing",
        ),
        _must(
            text,
            r"Статус\s*Silver\s*в\s*программе\s*SimplePrivé\s*[–—-].{0,260}?https://simplewine\.ru",
            "alfa_simple_definition_missing",
        ),
    ])

    smart_benefit = _must(
        text,
        r"6\.4\.1\..{0,520}?раздел\s*[«\"]Alfa\s*Only[»\"].{0,220}?1001\+\s*книг\s*в\s*Smart\s*Reading",
        "alfa_smart_benefit_missing",
    )
    smart_conditions = _must(
        text,
        r"6\.4\.1\..{0,500}?раздел\s*[«\"]Alfa\s*Only[»\"].{0,140}?1001\+\s*книг\s*в\s*Smart\s*Reading.{0,600}?Alfa\s*ID",
        "alfa_smart_activation_missing",
    )

    vzr_benefit = _must(
        text,
        r"Страхование\s*ВЗР\s*[–—-]\s*страхование\s*выезжающих\s*за\s*рубеж.{0,120}?АльфаСтрахование",
        "alfa_vzr_benefit_missing",
    )
    vzr_conditions = "\n".join([
        _insurance_row(text),
        _owned(
            text,
            r'Единовременно\s*Участнику\s*Программы',
            r'Единовременно\s*Участнику\s*Программы\s*может\s*предоставляться\s*'+maximum
            +rf'(?P<w_count>{NUMERIC_TOKEN}|[а-яё]+(?:\s+[а-яё]+)?)\s*услуг(?:и|а)?\s*по\s*Страхованию\s*ВЗР',
            "alfa_vzr_concurrent_limit_missing",
        ),
    ])

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
        _offer("alfa_only_public_rules", "core47:concierge", "Alfa Only — консьерж-сервис",
               concierge_benefit, concierge_conditions, CORE_URL, observed_at, revision=47,
               effective_from="2026-05-01", sha=sha, partner="Quintessentially Nova"),
        _offer("alfa_only_public_rules", "core47:simpleprive-silver", "Alfa Only — статус Silver в SimplePrivé",
               simple_benefit, simple_conditions, CORE_URL, observed_at, revision=47,
               effective_from="2026-05-01", sha=sha, partner="Simple"),
        _offer("alfa_only_public_rules", "core47:smart-reading", "Alfa Only — Smart Reading",
               smart_benefit, smart_conditions, CORE_URL, observed_at, revision=47,
               effective_from="2026-05-01", sha=sha, partner="Smart Reading"),
        _offer("alfa_only_public_rules", "core47:travel-insurance", "Alfa Only — страхование ВЗР",
               vzr_benefit, vzr_conditions, CORE_URL, observed_at, revision=47,
               effective_from="2026-05-01", sha=sha, partner="АльфаСтрахование"),
    ]


def parse_cashback(data: bytes, observed_at: str) -> list[dict]:
    text = _compact(pdf_text(data))
    sha = hashlib.sha256(data).hexdigest()
    _must(text, r"Редакция\s*№\s*101", "alfa_cashback_revision_missing")
    _must(
        text,
        r"Редакция\s*№\s*101\s*Правил\s*введена\s*в\s*действие\s*с\s*25\.05\.2026",
        "alfa_cashback_effective_date_missing",
    )
    evidence = _cashback_row(text)
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
    report["coverage"] = "nine_practical_benefits_from_public_core_rules_revision_47; authenticated_partner_catalog_not_read"
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
