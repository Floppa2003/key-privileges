"""Compatibility entrypoint: extract every newly fetched RGO PDF, no visual profile."""
import hashlib
from urllib.parse import urlsplit
from document_text import extract_pdf,document_records
from pdf_archive import capture_if_enabled, original_record


def extract_rgo_pdf(data,url,observed_at,*,label='',parent_sha256=None):
    u=urlsplit(url)
    if u.scheme!='https' or u.netloc!='rgo.ru' or not u.path.lower().endswith('.pdf') or u.query:
        raise ValueError('source_pdf_url_not_allowed')
    capture_if_enabled(data)
    native='pdf:'+hashlib.sha256(url.encode()).hexdigest()[:32]
    try:
        doc=extract_pdf(data)
    except Exception as exc:
        return [original_record('rgo',native,'Программа лояльности членов РГО',None,
            url,observed_at,data,exc,parent_source='https://rgo.ru/membership/loyalty-program/',label=label,
            extra_details={'parent_response_sha256':parent_sha256})]
    return document_records('rgo',native,
        'Программа лояльности членов РГО',None,url,observed_at,doc,
        parent_source='https://rgo.ru/membership/loyalty-program/',label=label,parent_sha256=parent_sha256)
