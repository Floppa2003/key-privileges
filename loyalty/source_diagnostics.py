"""Bounded machine-readable failures; never include arbitrary exception text."""
from __future__ import annotations
import hashlib
import re
from urllib.parse import urlsplit

_CODE = re.compile(r'[a-z][a-z0-9_-]{0,159}')
_MARKER = re.compile(r'\bERR_[A-Z_]+\b')

class ParseError(ValueError):
    def __init__(self, code, *, selector=None, matches=None):
        if not _CODE.fullmatch(code):
            raise ValueError('invalid_diagnostic_code')
        super().__init__(code)
        self.diagnostic = {}
        # Selectors come from checked-in configuration, not a response body.
        if selector is not None and len(selector) <= 240 and '\n' not in selector:
            self.diagnostic['selector'] = selector
        if type(matches) is int and matches >= 0:
            self.diagnostic['matches'] = matches

class ReadError(RuntimeError):
    def __init__(self, code, *, status=None, body=None, error_type=None):
        if not _CODE.fullmatch(code):
            raise ValueError('invalid_diagnostic_code')
        super().__init__(code)
        self.diagnostic = {}
        if type(status) is int and 100 <= status <= 599:
            self.diagnostic['http_status'] = status
        if isinstance(body, str):
            raw = body.encode('utf-8')
            self.diagnostic.update(response_sha256=hashlib.sha256(raw).hexdigest(),
                                   response_bytes=len(raw))
        if error_type and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,79}', error_type):
            self.diagnostic['upstream_error_type'] = error_type


def category(reason):
    reason = str(reason)
    if 'authentication' in reason or 'auth_redirect' in reason:
        return 'authentication_required'
    if 'CERT_' in reason or 'certificate' in reason or 'ssl' in reason.lower():
        return 'tls_verification'
    if reason in ('no_reviewed_adapter', 'extraction_not_implemented'):
        return 'adapter_missing'
    if 'robots_disallow' in reason or 'outside' in reason or 'unexpected_redirect' in reason:
        return 'access_policy'
    if re.search(r'(?:http_|status_)(?:401|403|451)\b', reason) or 'challenge' in reason:
        return 'access_denied'
    if '429' in reason or 'rate_limit' in reason or 'retry_after' in reason:
        return 'rate_limited'
    if re.search(r'http_(?:404|410)\b', reason):
        return 'not_found'
    if reason.startswith('robots_'):
        return 'robots_unavailable'
    if 'Timeout' in reason or 'timeout' in reason.lower() or 'time_budget' in reason:
        return 'timeout'
    if re.search(r'http_5\d\d\b', reason):
        return 'upstream_unavailable'
    if any(v in reason.lower() for v in ('transport','connection','name_not_resolved','empty_response')):
        return 'transport'
    return 'extraction'


def error_record(exc, phase, url=''):
    value = str(exc)
    reason = value if _CODE.fullmatch(value) else type(exc).__name__
    marker = _MARKER.search(value)
    if marker:
        reason = marker[0]
    result = {'phase':phase, 'path':urlsplit(url).path, 'reason':reason,
              'error_type':type(exc).__name__, 'category':category(reason)}
    result.update(getattr(exc, 'diagnostic', {}))
    status = re.search(r'(?:^|_)http_([1-5]\d\d)$', reason)
    if status:
        result['http_status'] = int(status[1])
    return result


def final_status(records, errors):
    if errors:
        return 'partial' if records else 'failed'
    return 'ok' if records else 'no_normalized_records'
