"""Immutable public PDF originals; the Google Sheet owns document metadata.

Capture is opt-in for collectors. A content-addressed path is not evidence of
publication: reader links are emitted only for locally verified archive files.
No sidecar index, model output, source text, or signed download URL is stored.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import tempfile

MAX_BYTES = 20_000_000
DEFAULT_ARCHIVE_DIR = Path(__file__).resolve().parents[1] / 'source-documents'
URL_ROOT = 'https://raw.githubusercontent.com/Floppa2003/key-privileges/main/source-documents/'
ORIGINAL_ONLY = 'source_pdf_original_only'
NOTICE = 'Требует просмотра PDF: автоматический разбор не завершён.'


def validated_sha(data):
    if (not isinstance(data, bytes) or not 100 <= len(data) <= MAX_BYTES
            or not data.startswith(b'%PDF-') or b'%%EOF' not in data[-1024:]):
        raise ValueError('archive_invalid_pdf_bytes')
    # Check the structural boundary independently of page/text parsing. A
    # truncated response can retain both magic markers but point outside itself.
    trailers = list(re.finditer(rb'startxref\s+([0-9]{1,12})\s+%%EOF', data[-1024:]))
    if not trailers:
        raise ValueError('archive_pdf_trailer_missing')
    offset = int(trailers[-1][1])
    target = data[offset:offset + 64]
    if (not 8 <= offset < len(data)
            or not (target.startswith(b'xref') or re.match(rb'\d+\s+\d+\s+obj\b', target))):
        raise ValueError('archive_pdf_cross_reference_invalid')
    return hashlib.sha256(data).hexdigest()


def _verify(path, expected):
    if path.is_symlink() or not path.is_file() or not 100 <= path.stat().st_size <= MAX_BYTES:
        raise ValueError('archive_copy_not_regular_pdf')
    if validated_sha(path.read_bytes()) != expected:
        raise ValueError('archive_copy_digest_mismatch')


def capture_pdf(data, *, directory=None):
    """Keep exact bytes once, without ever replacing a differing existing file."""
    digest = validated_sha(data)
    directory = directory if directory is not None else os.environ.get('PDF_CAPTURE_DIR')
    if not directory:
        return digest
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    target = root / (digest + '.pdf')
    if target.exists() or target.is_symlink():
        _verify(target, digest)
        return digest
    # Link a complete file into place atomically. Unlike os.replace, this cannot
    # overwrite a concurrently created file or silently repair corrupted data.
    with tempfile.NamedTemporaryFile(prefix='.capture-', dir=root, delete=False) as output:
        temporary = Path(output.name)
        try:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        try:
            os.link(temporary, target)
        except FileExistsError:
            pass
        _verify(target, digest)
    finally:
        temporary.unlink(missing_ok=True)
    return digest


def capture_if_enabled(data):
    """Existing parser/transport contracts stay unchanged outside capture runs."""
    if os.environ.get('PDF_CAPTURE_DIR'):
        capture_pdf(data)


def archive_url(document_sha256, *, directory=None):
    if not isinstance(document_sha256, str) or not re.fullmatch('[a-f0-9]{64}', document_sha256):
        return ''
    root = Path(directory if directory is not None else os.environ.get('PDF_ARCHIVE_DIR') or DEFAULT_ARCHIVE_DIR)
    path = root / (document_sha256 + '.pdf')
    if not path.exists() and not path.is_symlink():
        return ''
    _verify(path, document_sha256)
    return URL_ROOT + document_sha256 + '.pdf'


def original_record(source_id, native_prefix, program, partner, url, observed_at,
                    data, error, *, parent_source=None, label='',
                    extra_details=None, link_kind='detail_page', locator=''):
    """A fetched PDF remains findable even when no page could be interpreted."""
    from normalized import make_offer
    digest = capture_pdf(data)
    details = {**(extra_details or {}), 'document_sha256':digest,
               'extraction_method':ORIGINAL_ONLY, 'document_notice':NOTICE,
               'document_errors':[{'reason':type(error).__name__}],
               'parent_source':parent_source or url, 'discovery_label':label,
               'public_aliases':[url] if link_kind=='detail_page' else []}
    warnings = ['pdf_original_requires_viewing', 'user_eligibility_not_verified',
                'no_document_terms_inferred']
    if link_kind == 'page_block':
        warnings.append('temporary_document_url_not_persisted_use_parent_locator')
    return make_offer(source_id, native_prefix + ':original:' + digest,
        program, partner, '', url, observed_at, title=label or partner or 'Документ источника',
        details=details, warnings=warnings, record_kind='source_observation',
        source_status='public_document_requires_viewing', link_kind=link_kind, locator=locator)


def validate_original_record(record):
    """This exception carries document identity, never a verified offer claim."""
    d = record.get('details', {})
    digest = d.get('document_sha256')
    if (d.get('extraction_method') != ORIGINAL_ONLY
            or record.get('record_kind') != 'source_observation'
            or record.get('source_status') != 'public_document_requires_viewing'
            or not isinstance(digest, str) or not re.fullmatch('[a-f0-9]{64}', digest)
            or not record.get('native_id', '').endswith(':original:' + digest)
            or d.get('document_notice') != NOTICE
            or not d.get('document_errors')
            or d.get('live_document_text') or 'pages' in d or 'page_count' in d
            or any(record.get(k) for k in ('benefit_text', 'conditions_text', 'redemption_text',
                'rates', 'benefit_types', 'promo_codes', 'tables', 'valid_from', 'valid_until'))
            or record.get('validity_status') != 'not_stated'
            or 'pdf_original_requires_viewing' not in record.get('warnings', [])):
        raise ValueError('original_pdf_observation_cannot_claim_terms')
