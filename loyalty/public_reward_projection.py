"""Source-owned projection for the three explicitly approved public programmes.

No generic marketing-rate inference, account access or cross-programme merging.
"""
from __future__ import annotations
import re
from bs4 import BeautifulSoup, Comment

SOURCES = {'backit_public', 'club_avolta_public', 'mantera_moments'}
WARNINGS = ['public_terms_not_personal_eligibility', 'account_activation_not_performed',
            'source_dates_not_inferred', 'linked_external_terms_not_exhaustively_read']


def plain(node):
    soup = BeautifulSoup(str(node), 'html.parser')
    for n in soup.select('script,style,noscript,svg,iframe,input,textarea,form'):
        if n.parent is not None: n.decompose()
    for n in soup.find_all(string=lambda x: isinstance(x, Comment)): n.extract()
    for n in soup.select('br'): n.replace_with('\n')
    for n in soup.select('p,li,h1,h2,h3,h4'): n.append('\n')
    return '\n'.join(re.sub(r'\s+', ' ', x).strip() for x in soup.get_text('', strip=False).splitlines() if x.strip())


def one(soup, selector):
    nodes = soup.select(selector)
    if len(nodes) != 1: raise ValueError('public_rewards_missing_or_duplicate_section:' + selector)
    return nodes[0]


def fields(source, evidence):
    if source == 'backit_public':
        from backit_source import source_fields
    elif source == 'club_avolta_public':
        from avolta_source import source_fields
    elif source == 'mantera_moments':
        from mantera_source import source_fields
    else: raise ValueError('unknown_public_reward_source')
    return source_fields(evidence)


def make_record(source, evidence, observed_at):
    from normalized import make_offer
    f = fields(source, evidence)
    return make_offer(source, f['native'], f['program'], f['partner'], f['benefit'], f['url'], observed_at,
        title=f['title'], conditions=f['conditions'], redemption=f['activation'], category=f['category'],
        record_kind=f.get('kind', 'partner_offer'), link_kind=f.get('link_kind', 'detail_page'),
        locator=f['locator'], details={'public_reward_evidence': evidence, 'public_reward_source': source,
            'retrieval_method': 'source_owned_public_rewards_v1', 'account_used': False},
        warnings=WARNINGS + f.get('warnings', []))


def validate_record(row):
    source = row['source_id']; d = row.get('details', {})
    if d.get('public_reward_source') != source or d.get('account_used') is not False:
        raise ValueError('public_rewards_identity_changed')
    f = fields(source, d.get('public_reward_evidence', {}))
    checks = {'native_id': f['native'], 'program': f['program'], 'partner_name': f['partner'],
              'title': f['title'], 'source_url': f['url'], 'benefit_text': f['benefit'],
              'conditions_text': f['conditions'], 'redemption_text': f['activation'],
              'category': f['category'], 'record_kind': f.get('kind', 'partner_offer'),
              'link_kind': f.get('link_kind', 'detail_page'), 'locator': f['locator'],
              'source_status': 'published', 'valid_from': None, 'valid_until': None}
    if any(row.get(k) != v for k, v in checks.items()) or not set(WARNINGS + f.get('warnings', [])).issubset(row.get('warnings', [])):
        raise ValueError('public_rewards_record_evidence_mismatch')


def project_common(raw, n, benefit, condition, code):
    from unified_normalization import digest, validate_normalized
    d = raw['details']; source = d['public_reward_source']
    f = fields(source, d['public_reward_evidence'])
    checks = {'program': f['program'], 'partner': f['partner'], 'title': f['title'],
              'source_url': f['url'], 'benefit': f['benefit'], 'conditions': f['conditions'],
              'activation': f['activation'], 'kind': f.get('kind', 'partner_offer')}
    if any(raw.get(k) != v for k, v in checks.items()): raise ValueError('public_rewards_common_evidence_mismatch')
    scope = f.get('scope', {})
    conditions = []
    if f['conditions']: conditions.append(condition('owned_programme_rules', '/conditions', scope=scope)['id'])
    if f['activation']: conditions.append(condition('activation_step', '/activation', scope=scope)['id'])
    for term in f['terms']:
        term = dict(term); local = {**scope, **term.pop('scope', {})}; fragment = term.pop('fragment')
        obj = benefit(term.pop('kind'), '/benefit', scope=local, fragment=fragment, **term)
        obj.update(condition_ids=conditions, condition_linkage='full_owned_record_rules', remaining_record_rules_require_review=True)
    for i, value in enumerate(raw['codes']): code(value, '/codes/' + str(i), scope)
    n['quality']['level'] = 'structured_with_review'
    n['quality']['issues'].append('source_owned_reward_currency_and_audience_preserved')
    n['content_sha256'] = digest({k: v for k, v in n.items() if k != 'content_sha256'})
    validate_normalized(n)
    return n
