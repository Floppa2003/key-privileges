"""Bank-scoped verified-TLS availability probe; never an account/cashback reader."""
from __future__ import annotations
import asyncio
import hashlib
import json
import tempfile
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import certifi
import requests
from recovered_contract import CA_FILES

ROOT='https://web.alfabank.ru/partner-offers/'
AUTH_HOST='private.auth.alfabank.ru'
AUTH_PATH='/passport/cerberus-mini/dashboard/cross_auth'


def inspect_access(url):
    """Download one pinned public CA, then HEAD exactly ROOT without following redirects."""
    if url!=ROOT:raise ValueError('alfa_probe_url_outside_reviewed_scope')
    ca_url,digest=CA_FILES[0]
    audit={'method':'HEAD','account_used':False,'response_body_read':False,
           'redirect_followed':False,'activation_performed':False,
           'catalogue_collected':False,'trust_scope':'temporary_bank_request_only'}
    try:
        with requests.Session() as session, tempfile.TemporaryDirectory() as folder:
            session.trust_env=False
            with session.get(ca_url,verify=True,timeout=(5,10),allow_redirects=False,stream=True) as res:
                if res.status_code==429 or res.headers.get('Retry-After'):raise RuntimeError('official_ca_rate_limited')
                if res.status_code!=200:raise RuntimeError('official_ca_unavailable')
                data=bytearray();deadline=time.monotonic()+10
                for chunk in res.iter_content(4096):
                    data.extend(chunk)
                    if len(data)>16384 or time.monotonic()>deadline:raise RuntimeError('official_ca_response_bound')
            if hashlib.sha256(data).hexdigest()!=digest:raise RuntimeError('official_ca_digest_changed')
            bundle=Path(folder)/'bank-ca.pem'
            bundle.write_bytes(Path(certifi.where()).read_bytes()+b'\n'+data)
            session.cookies.clear()
            with session.head(ROOT,verify=str(bundle),timeout=(5,10),allow_redirects=False,
                              headers={'User-Agent':'LoyaltyCatalogResearchBot/1.0'}) as res:
                audit.update(status=res.status_code,tls_verified=True,official_root_sha256=digest)
                if res.status_code==429 or res.headers.get('Retry-After'):raise RuntimeError('alfa_rate_limited')
                if res.status_code in (301,302,303,307,308):
                    target=urlsplit(urljoin(ROOT,res.headers.get('Location','')))
                    # Record only known auth identity, never arbitrary query/path/header data.
                    if (target.scheme=='https' and target.netloc==AUTH_HOST and target.path==AUTH_PATH
                            and target.username is None):
                        audit.update(access_state='bank_authentication_redirect',
                                     redirect_host=AUTH_HOST,redirect_path=AUTH_PATH)
                    else:audit['access_state']='unexpected_redirect_not_followed'
                elif res.status_code==200:audit['access_state']='head_200_catalogue_body_not_read'
                else:audit['access_state']='head_status_'+str(res.status_code)
            return audit
    except requests.exceptions.SSLError:raise RuntimeError('alfa_certificate_verification_failed') from None
    except requests.RequestException:raise RuntimeError('alfa_probe_transport_failed') from None


async def collect_access(cfg,report):
    audit=await asyncio.to_thread(inspect_access,cfg['url'])
    report['coverage']=json.dumps(audit,ensure_ascii=False,sort_keys=True)
    # A completed availability probe is not collected offers or successful coverage.
    raise RuntimeError('alfa_'+audit['access_state'])
