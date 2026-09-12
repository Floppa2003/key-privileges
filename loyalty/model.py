"""Conservative records and non-destructive Sheets write planning."""
from __future__ import annotations
import hashlib
import re
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

BLOCKED = re.compile(r'access denied|forbidden|just a moment|проверка безопасности|captcha|доступ ограничен', re.I)
BENEFIT = re.compile(r'скидк|кешб[эе]к|кэшб[эе]к|подар|привилег|мил[ьи]|бонус|\d\s*%', re.I)


def clean_url(url: str) -> str:
    u = urlsplit(url)
    if u.scheme != 'https' or not u.hostname or u.username or u.password or u.port not in (None, 443):
        raise ValueError('Only public HTTPS URLs without credentials are accepted')
    query = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True)
             if not k.lower().startswith('utm_') and k not in ('gclid', 'fbclid', 'yclid')]
    if any(re.search(r'token|secret|password|auth|session|signature', k, re.I) for k, _ in query):
        raise ValueError('Credential-like query is not accepted')
    return urlunsplit(('https', u.hostname.lower(), u.path or '/', urlencode(query), ''))


def is_offer(url: str, cfg: dict) -> bool:
    try:
        u = urlsplit(clean_url(url))
        return u.hostname == cfg['host'] and re.fullmatch(cfg['offer_pattern'], u.path) is not None
    except (ValueError, TypeError):
        return False


def make_record(source: str, url: str, title: str, terms: str, observed_at: str) -> dict | None:
    title, terms = title.strip(), terms.strip()
    if len(terms) > 40000 or len(title) > 500:
        raise ValueError('Oversized source text; refusing to truncate conditions')
    if not title or len(terms) < 40 or BLOCKED.search(title) or BLOCKED.search(terms[:160]):
        return None
    if not BENEFIT.search(terms):
        return None
    if datetime.fromisoformat(observed_at).tzinfo is None:
        raise ValueError('Observation timestamp must include timezone')
    url = clean_url(url)
    return {'id': hashlib.sha256((source + '\n' + url).encode()).hexdigest(),
            'source': source, 'url': url, 'title': title, 'terms': terms,
            'observed_at': observed_at, 'status': 'needs_review',
            'content_sha256': hashlib.sha256(terms.encode()).hexdigest()}


def cell(value: str) -> dict:
    if not isinstance(value, str) or len(value) > 40000:
        raise ValueError('Cells must be bounded literal strings')
    return {'userEnteredValue': {'stringValue': value}}


def plan_rows(existing: list[list], incoming: list[list[str]], width: int) -> list[tuple[int, list[str]]]:
    """Zero-based target indexes. Keep absent records, holes and manual columns."""
    index, incoming_ids = {}, set()
    for n, row in enumerate(existing[1:], 1):
        if not any(row):
            continue
        if not row[0] or row[0] in index:
            raise ValueError('Existing sheet has missing or duplicate stable IDs')
        index[row[0]] = n
    result, next_row = [], max(1, len(existing))
    for row in incoming:
        if len(row) != width or not row[0] or row[0] in incoming_ids:
            raise ValueError('Incoming rows have invalid width or duplicate IDs')
        for value in row:
            cell(value)
        incoming_ids.add(row[0])
        n = index.get(row[0])
        if n is None:
            n, next_row = next_row, next_row + 1
            result.append((n, row))
        elif (existing[n][:width] + [''] * width)[:width] != row:
            result.append((n, row))
    return result


def verify_rows(actual: list[list], expected: list[tuple[int, list[str]]], width: int) -> None:
    for n, row in expected:
        found = actual[n] if n < len(actual) else []
        if (found[:width] + [''] * width)[:width] != row:
            raise ValueError('Google Sheets readback mismatch; publication is NOT verified')
