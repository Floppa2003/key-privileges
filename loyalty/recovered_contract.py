"""Reviewed exceptions: exact public endpoints, never a general TLS/HTTP downgrade."""
from __future__ import annotations
import re
from urllib.parse import urlsplit, parse_qsl, urlencode

CA_FILES = (
    ('https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt',
     '936a43fea6e8e525bcc0f81acd9c3d21b4fc4b9b68acea7906d698005afc6504'),
    ('https://gu-st.ru/content/lending/russian_trusted_sub_ca_pem.crt',
     'f0ae589f36774f29ef3648f7984b08d42fcce6f1ffeeb6236d773daeb2744ea6'),
)
CA_PROFILE = 'russian_nuc_pinned_2026_09'
HTTP_PROFILE = 'loyals_public_http_explicit_2026_09_14'
HTTP_WARNING = 'transport_unencrypted_and_unauthenticated'
API = 'http://loyals.ru/wp-json/wp/v2/posts'
WP_FIELDS = 'id,date_gmt,modified_gmt,link,title,content,excerpt,status,type,slug,categories,tags'
SOURCES = {
    'loyals': {'url': 'http://loyals.ru/', 'profile': HTTP_PROFILE},
    'af_vtb_rules': {'url': 'https://www.vtb.ru/privilegia/karty/debetovye/privilegiya-aeroflot/', 'profile': CA_PROFILE},
    'nspk_ekp_rules': {'url': 'https://www.nspk.ru/press-center/details/00d06ff9-ac6f-41fd-9aad-39965b9762cd', 'profile': CA_PROFILE},
    'uralsib_rzd_rules': {'url': 'https://uralsib.ru/aktsii/privetstvennye-bally-rzhd-za-oformlenie-karty', 'profile': CA_PROFILE},
}


def http_url(url: str) -> str:
    """Only the public Loyals collection; no arbitrary HTTP links or operations."""
    u = urlsplit(url)
    if u.scheme != 'http' or u.netloc != 'loyals.ru' or u.fragment:
        raise ValueError('http_source_not_allowlisted')
    if u.path in ('/', '/robots.txt') and not u.query:
        return url
    if u.path != '/wp-json/wp/v2/posts':
        raise ValueError('http_path_not_allowlisted')
    pairs = parse_qsl(u.query, keep_blank_values=True)
    q = dict(pairs)
    if (len(q) != len(pairs) or set(q) != {'per_page','page','orderby','order','_fields'}
            or q['per_page'] != '50' or q['orderby'] != 'id' or q['order'] != 'asc'
            or q['_fields'] != WP_FIELDS or not re.fullmatch(r'[1-9][0-9]*', q['page'])
            or int(q['page']) > 10):
        raise ValueError('http_query_not_allowlisted')
    return API + '?' + urlencode(pairs)


def collection_url(page: int) -> str:
    return http_url(API + '?' + urlencode({'per_page':'50','page':str(page),
        'orderby':'id','order':'asc','_fields':WP_FIELDS}))


def checked_config(cfg: dict) -> dict:
    spec = SOURCES.get(cfg.get('id'))
    if not spec or cfg.get('url') != spec['url'] or cfg.get('access_profile') != spec['profile']:
        raise ValueError('unreviewed_recovered_source_configuration')
    return spec


def transport_evidence(source_id: str) -> dict:
    if source_id == 'loyals':
        return {'profile':HTTP_PROFILE,'scheme':'http','authenticated':False,
                'encrypted':False,'anonymous':True}
    if source_id not in SOURCES:
        raise ValueError('unknown_recovered_source')
    return {'profile':CA_PROFILE,'scheme':'https','authenticated':True,'encrypted':True,
            'anonymous':True,'hostname_and_expiry_verified':True,'system_trust_changed':False,
            'additional_ca_sha256':[sha for _,sha in CA_FILES]}


def validate_recovered(r: dict) -> None:
    sid = r['source_id']
    if sid not in SOURCES:
        if r['source_url'].startswith('http:'):
            raise ValueError('HTTP is exclusive to the reviewed Loyals source')
        return
    if r['details'].get('transport') != transport_evidence(sid):
        raise ValueError('recovered_source_transport_evidence_mismatch')
    if sid != 'loyals':
        if (r['source_url'] != SOURCES[sid]['url'] or r['record_kind'] != 'program_rules'
                or r['details'].get('evidence_role') != 'supplementary_rules_not_incremental_discount'
                or r['source_status'] != ('public_announcement_not_full_rules' if sid == 'nspk_ekp_rules' else 'public_rules_text')):
            raise ValueError('recovered_rules_cannot_be_promoted')
        return
    if (http_url(r['source_url']) != r['source_url'] or not r['source_url'].startswith(API+'?')
            or r['source_status'] != 'public_http_unverified' or r['link_kind'] != 'api_record'
            or r['benefit_url'] is not None or HTTP_WARNING not in r['warnings']
            or r['valid_from'] is not None or r['valid_until'] is not None):
        raise ValueError('Loyals HTTP observation cannot be promoted to verified evidence')
    post = r['details'].get('public_post', {})
    if (type(post.get('id')) is not int or str(post['id']) != r['native_id']
            or post.get('status') != 'publish' or post.get('type') != 'post'
            or post.get('content', {}).get('protected') is not False
            or not re.fullmatch(r'/[0-9]+', r['locator'])
            or r['details'].get('response_json_pointer') != r['locator']
            or not re.fullmatch(r'[a-f0-9]{64}',r['details'].get('response_sha256',''))):
        raise ValueError('invalid_public_post_identity')
    expected = 'partner_offer' if r['benefit_text'] else 'source_observation'
    if r['record_kind'] != expected or (not r['benefit_text'] and r['conditions_text'] != r['title']):
        raise ValueError('empty_Loyals_post_is_not_an_offer')
