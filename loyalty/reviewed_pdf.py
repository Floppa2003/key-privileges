"""Compatibility entrypoint: extract every newly fetched RGO PDF, no visual profile."""
import hashlib
from urllib.parse import urlsplit
from document_text import extract_pdf,document_records


def extract_rgo_pdf(data,url,observed_at):
    u=urlsplit(url)
    if u.scheme!='https' or u.netloc!='rgo.ru' or not u.path.lower().endswith('.pdf') or u.query:
        raise ValueError('source_pdf_url_not_allowed')
    doc=extract_pdf(data)
    return document_records('rgo','pdf:'+hashlib.sha256(url.encode()).hexdigest()[:32],
        'Программа лояльности членов РГО',None,url,observed_at,doc,
        parent_source='https://rgo.ru/membership/loyalty-program/')
