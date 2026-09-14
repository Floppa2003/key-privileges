"""Identity for live public Utair document links, excluding transient signatures."""
import hashlib
import re
from urllib.parse import unquote, urlsplit

ROOT='https://media.utair.ru/status'
ORIGIN='https://eu-s3.beelinecloud.ru'


def direct_resource(url):
    """Only the existing publisher bucket and PDF class; return no query values."""
    u=urlsplit(url)
    path=unquote(u.path)
    if (u.scheme!='https' or u.netloc!='eu-s3.beelinecloud.ru' or u.fragment
            or not path.startswith('/utair-log/') or not path.lower().endswith('.pdf')
            or len(u.path)>2200 or any(x in path for x in ('\\','?','#','\x00','\r','\n'))
            or any(p in ('.','..') for p in path.split('/'))):
        raise ValueError('unreviewed_direct_document_link')
    return {'origin':ORIGIN,'path':u.path,
            'resource_id':hashlib.sha256((ORIGIN+u.path).encode()).hexdigest()}


def validate_utair_document(record):
    d=record['details'];native=record['native_id'].split(':part:')[0]
    if not d.get('live_document_text') or d.get('parent_source')!=ROOT:
        raise ValueError('Public document must originate from the live Utair listing')
    resources=d.get('direct_document_resources',[])
    for resource in resources:
        if (not isinstance(resource,dict) or set(resource)!={'origin','path','resource_id'}
                or resource['origin']!=ORIGIN or '?' in resource['path'] or '#' in resource['path']
                or direct_resource(resource['origin']+resource['path'])!=resource):
            raise ValueError('invalid_direct_document_resource')
    if native.startswith('direct-document:'):
        key=native.removeprefix('direct-document:')
        if (not re.fullmatch('[a-f0-9]{64}',key)
                or record['source_url']!=ROOT or record['link_kind']!='page_block'
                or record['benefit_url'] is not None
                or not any(r['resource_id']==key for r in resources)
                or 'temporary_document_url_not_persisted_use_parent_locator' not in record['warnings']
                or not re.fullmatch('[a-f0-9]{64}',d.get('parent_response_sha256',''))):
            raise ValueError('invalid_direct_document_provenance')
    elif (not re.fullmatch(r'document:[A-Za-z0-9_-]{1,80}',native)
            or record['source_url']!='https://ut0.ru/'+native.removeprefix('document:')):
        raise ValueError('invalid_shortlink_document_provenance')
