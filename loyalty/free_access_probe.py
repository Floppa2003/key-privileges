"""Free-plan-only access probe; no Google credentials, accounts or publication.

The provider's documented response/credit contract is checked before collecting the
six configured public roots. This is a retrieval experiment, not an offer adapter.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
import requests
from bs4 import BeautifulSoup

SOURCE_IDS = ('ekp', 'nordwind', 'coral', 'coral_promo', 'rzd', 'aeroflot')
API = 'https://api.scrapingant.com/v2/'
MAX_BYTES = 6_000_000
MAX_CREDITS = 115  # Five plain policies + up to five browser policies + six roots.
MAX_REQUESTS = 16
LOCATION_JS = base64.b64encode(b"document.documentElement.setAttribute('data-loyalty-probe-location', location.href);").decode()


class ProbeError(RuntimeError):
    """Only locally generated, non-sensitive error codes leave the HTTP layer."""


def now():
    return datetime.now(timezone.utc).isoformat()


def public_url(value):
    try:
        u = urlsplit(value)
        if u.scheme != 'https' or not u.hostname or u.username or u.password or u.port not in (None, 443):
            return None
        return urlunsplit((u.scheme, u.netloc, u.path or '/', '', ''))
    except (TypeError, ValueError):
        return None


def configured_roots(path):
    data = json.loads(Path(path).read_text())
    selected = [s for s in data if s.get('id') in SOURCE_IDS]
    if len(selected) != len(SOURCE_IDS) or {s['id'] for s in selected} != set(SOURCE_IDS):
        raise ProbeError('invalid_source_inventory')
    for s in selected:
        u = urlsplit(s['url'])
        if not public_url(s['url']) or u.fragment:
            raise ProbeError('invalid_source_url')
    by_id = {s['id']: s for s in selected}
    return [by_id[sid] for sid in SOURCE_IDS]


def free_plan(payload):
    if not isinstance(payload, dict):
        raise ProbeError('invalid_usage_response')
    name = payload.get('plan_name', '')
    total, left = payload.get('plan_total_credits'), payload.get('remained_credits')
    if not isinstance(name, str) or name.strip().casefold() not in ('free', 'free plan'):
        raise ProbeError('free_plan_not_confirmed')
    if type(total) is not int or type(left) is not int or not 0 <= left <= total <= 10000 or total == 0:
        raise ProbeError('invalid_free_credit_balance')
    if left < MAX_CREDITS:
        raise ProbeError('insufficient_free_credits')
    return left


class FreeReader:
    def __init__(self, key, roots, *, get=requests.get):
        if not isinstance(key, str) or not key.strip() or len(key) > 512 or any(c.isspace() for c in key):
            raise ProbeError('invalid_key_format')
        self.key = key
        self.roots = {s['url'] for s in roots}
        self.allowed = self.roots | {f'https://{urlsplit(u).netloc}/robots.txt' for u in self.roots}
        self.get = get
        self.ready = False
        self.reserved = 0
        self.calls = 0
        self.known_charged_credits = 0
        self.halted = False
        self.deadline = time.monotonic() + 780

    def _request(self, endpoint, params):
        # The query-key form is documented and confirmed in the public API schema.
        # Never log requests, response headers, raw exceptions or provider errors.
        try:
            with self.get(API + endpoint, params={**params, 'x-api-key': self.key},
                          headers={'Accept': 'application/json' if endpoint == 'usage' else 'text/html'}, timeout=(10, 75),
                          allow_redirects=False, stream=True) as r:
                status = r.status_code
                if status in (401, 402, 403, 409, 429) or r.headers.get('Retry-After'):
                    self.halted = True
                    raise ProbeError('provider_auth_quota_or_rate_limit')
                if status != 200:
                    raise ProbeError('provider_http_' + str(status))
                raw = bytearray()
                for block in r.iter_content(65536):
                    raw.extend(block)
                    if len(raw) > MAX_BYTES:
                        self.halted = True
                        raise ProbeError('provider_response_size_limit')
                # Defensive rejection if a provider ever echoes the API credential.
                if self.key.encode() in raw:
                    self.halted = True
                    raise ProbeError('credential_echo_rejected')
                body = raw.decode('utf-8')
                payload = json.loads(body) if endpoint == 'usage' else body
                if self.key in (json.dumps(payload, ensure_ascii=False) if endpoint == 'usage' else payload):
                    self.halted = True
                    raise ProbeError('credential_echo_rejected')
                meta = {name: r.headers.get(name) for name in (
                    'Ant-credits-cost', 'Ant-page-status-code', 'ant-original-header-retry-after')}
                return payload, meta
        except ProbeError:
            raise
        except Exception:
            self.halted = True
            raise ProbeError('provider_transport_or_json_error') from None

    def preflight(self):
        payload, _ = self._request('usage', {})
        free_plan(payload)
        self.ready = True

    def read(self, url, *, browser):
        if time.monotonic() + 80 > self.deadline:
            self.halted = True
            raise ProbeError('probe_time_budget')
        if not self.ready or self.halted:
            raise ProbeError('reader_not_ready_or_stopped')
        if url not in self.allowed:
            raise ProbeError('request_outside_configured_roots')
        cost = 10 if browser else 1
        if self.reserved + cost > MAX_CREDITS or self.calls >= MAX_REQUESTS:
            raise ProbeError('per_run_limit')
        self.reserved += cost  # Reserve even on failure; no retries.
        self.calls += 1
        params = {'url': url, 'browser': str(browser).lower(),
                  'proxy_country': 'RU', 'proxy_type': 'datacenter', 'timeout': '60'}
        if browser:
            params['js_snippet'] = LOCATION_JS
            params['block_resource'] = ['image', 'media', 'font']
        raw, meta = self._request('general', params)
        charged = meta['Ant-credits-cost']
        if charged is None or not re.fullmatch(r'\d+', str(charged)) or int(charged) > cost:
            self.halted = True
            raise ProbeError('credit_cost_contract_unconfirmed')
        self.known_charged_credits += int(charged)
        value = meta['Ant-page-status-code']
        if value is None or not re.fullmatch(r'[1-5][0-9]{2}', str(value)):
            raise ProbeError('origin_status_missing')
        status = int(value)
        if status == 429 or meta['ant-original-header-retry-after'] is not None:
            self.halted = True
            raise ProbeError('origin_rate_limit_or_retry_after')
        # Only three non-sensitive metadata fields are read; all other headers,
        # including Set-Cookie, are discarded. No extended XHR/session payload.
        return status, raw, int(charged)


def sanitized_page(raw, requested_url):
    soup = BeautifulSoup(raw, 'html.parser')
    marker = soup.html.get('data-loyalty-probe-location') if soup.html else None
    actual = public_url(marker)
    requested = public_url(requested_url)
    if actual != requested:
        # The EKP root's SPA destination was observed in earlier live reads.
        equivalent = (requested == 'https://ekp.spb.ru/capabilities/loyalty/' and
                      actual in ('https://ekp.spb.ru/capabilities/loyalty/tiles',
                                 'https://ekp.spb.ru/capabilities/loyalty/tiles/'))
        if not equivalent:
            raise ProbeError('final_location_missing_or_changed')
    base_tag = soup.select_one('base[href]')
    base_url = public_url(urljoin(actual, base_tag['href'])) if base_tag else actual
    if not base_url or urlsplit(base_url).netloc != urlsplit(actual).netloc:
        raise ProbeError('untrusted_document_base')
    for node in soup.select('script,style,noscript,form,input,textarea,iframe,[hidden],[aria-hidden="true"]'):
        node.decompose()
    for node in soup.find_all(True):
        for key in list(node.attrs):
            if key not in ('id', 'class', 'href', 'title', 'role'):
                del node.attrs[key]
        if node.has_attr('href'):
            link = public_url(urljoin(base_url, node['href']))
            if link:
                node['href'] = link
            else:
                del node.attrs['href']
    text = soup.get_text(' ', strip=True)
    return str(soup), {'final_url': actual, 'document_base_url': base_url, 'text_chars': len(text),
                       'links': len(soup.select('a[href]')),
                       'classification': 'public_document_candidate_not_verified',
                       'detail_pages_read': 0, 'catalogue_complete': False}



def read_policy(reader, url, info):
    """Try the browser once only when the provider reports HTTP-route unreachable.

    Provider404 is not an origin404 or permission to ignore robots. The fallback
    must return a real identified document, then normal robots parsing still runs.
    Provider auth/quota/challenge errors are never retried by this helper.
    """
    info['method'] = 'http'
    try:
        return reader.read(url, browser=False)
    except ProbeError as exc:
        if str(exc) != 'provider_http_404' or reader.halted:
            raise
    info.update(method='browser_after_unreachable_http', initial_error='provider_http_404')
    status, raw, credits = reader.read(url, browser=True)
    sanitized_page(raw, url)  # Require the current browser's exact policy URL.
    return status, raw, credits


def run(roots, key, out, *, get=requests.get, sleep=time.sleep):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    # Remove only this probe's known prior page outputs, never unrelated files.
    for sid in SOURCE_IDS:
        (out / (sid + '.html')).unlink(missing_ok=True)
    report = {'started_at': now(), 'run_id': os.getenv('GITHUB_RUN_ID'),
              'commit': os.getenv('GITHUB_SHA'), 'mode': 'free_access_probe',
              'source_ids': list(SOURCE_IDS), 'status': 'not_configured',
              'published_records': 0, 'account_sessions_used': False, 'sources': [],
              'requested_country': 'RU', 'requested_proxy_type': 'datacenter',
              'maximum_estimated_credits': MAX_CREDITS, 'target_requests': 0}
    def save():
        tmp = out / 'report.tmp'
        tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        tmp.replace(out / 'report.json')
    save()
    if not key:
        report['finished_at'] = now()
        save()
        return report
    reader = None
    try:
        # Reuse the same crawl-rule and refusal semantics as the production reader.
        from public_transport import robots_document, check_response
        from protego import Protego
        reader = FreeReader(key, roots, get=get)
        reader.preflight()
        report['status'] = 'checked'; report['free_plan_confirmed'] = True
        policies = {}; intervals = {}; last = {}
        for cfg in roots:
            sid, url = cfg['id'], cfg['url']; host = urlsplit(url).netloc
            item = {'source_id': sid, 'requested_url': public_url(url),
                    'status': 'not_read', 'started_at': now()}
            report['sources'].append(item); save()
            try:
                if host not in policies:
                    policies[host] = None
                    item['phase'] = 'robots'
                    item['robots'] = {'state': 'fetching'}
                    status, raw, _ = read_policy(reader, f'https://{host}/robots.txt', item['robots'])
                    last[host] = time.monotonic()
                    rules, state = robots_document(status, raw)
                    policy = Protego.parse(rules)
                    policies[host] = policy
                    rate = policy.request_rate('LoyaltyCatalogResearchBot')
                    intervals[host] = max(1.0, policy.crawl_delay('LoyaltyCatalogResearchBot') or 0,
                                          rate.seconds / rate.requests if rate else 0)
                    item['robots'].update(state=state, origin_http_status=status)
                policy = policies[host]
                if policy is None:
                    raise ProbeError('robots_unavailable')
                if not policy.can_fetch(url, 'LoyaltyCatalogResearchBot'):
                    raise ProbeError('robots_disallow')
                delay = max(0, intervals[host] - (time.monotonic() - last[host]))
                if delay > 60:
                    raise ProbeError('crawl_delay_exceeds_probe_budget')
                sleep(delay)
                item['phase'] = 'root'
                status, raw, credits = reader.read(url, browser=True)
                last[host] = time.monotonic()
                item['origin_http_status'] = status; item['credits'] = credits
                check_response(status, raw)
                clean, meta = sanitized_page(raw, url)
                item.update(meta)
                item['status'] = 'candidate_requires_review'
                item['sanitized_dom_sha256'] = hashlib.sha256(clean.encode()).hexdigest()
                (out / (sid + '.html')).write_text(clean)
            except ProbeError as exc:
                item['status'] = 'failed'; item['error'] = str(exc)
            except RuntimeError as exc:
                # Existing transport helpers emit these bounded status codes.
                reason = str(exc)
                item['status'] = 'failed'
                item['error'] = reason if re.fullmatch(r'(?:http_\d{3}|robots_[a-z_0-9]+|access_challenge)', reason) else 'source_check_failed'
            except Exception:
                item['status'] = 'failed'; item['error'] = 'source_check_failed'
            item['finished_at'] = now(); save()
            if reader.halted:
                report['status'] = 'stopped'; break
        if len(report['sources']) < len(roots):
            report['unattempted_sources'] = [s['id'] for s in roots[len(report['sources']):]]
    except ProbeError as exc:
        report['status'] = 'stopped'; report['error'] = str(exc)
    except Exception:
        report['status'] = 'stopped'; report['error'] = 'probe_setup_failed'
    finally:
        if reader:
            report['target_requests'] = reader.calls
            report['reserved_credits'] = reader.reserved
            report['known_charged_credits'] = reader.known_charged_credits
            report['failed_request_charges_not_included'] = True
        report['finished_at'] = now(); save()
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', default='free-access-output')
    args = p.parse_args()
    roots = configured_roots(Path(__file__).with_name('sources_normalized.json'))
    report = run(roots, os.environ.get('SCRAPINGANT_API_KEY', ''), args.output)
    # Only our fixed status vocabulary is written to logs.
    print(json.dumps({'status': report['status'], 'target_requests': report['target_requests'],
                      'published_records': 0}))
    return 0 if report['status'] in ('not_configured', 'checked') else 1


if __name__ == '__main__':
    raise SystemExit(main())
