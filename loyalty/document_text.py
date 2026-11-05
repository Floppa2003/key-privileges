"""Live PDF extraction. No stored answers, expected hashes, titles or page counts.

Native text is preferred. OCR runs only for pages without usable native text;
its output remains explicitly uncertain and is never manually corrected here.
"""
from __future__ import annotations
import csv
import hashlib
import io
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

MAX_PAGES=80
MAX_BYTES=20_000_000
MAX_TEXT=240_000
PART_CHARS=14_000
MAX_CONTENT_STREAM_BYTES=4_000_000
MAX_FORM_DEPTH=32
MAX_XOBJECT_REFERENCES=10_000
MAX_FORM_INVOCATIONS=5_000


def sha(data):
    return hashlib.sha256(data).hexdigest()


def ocr_pages(pdf_path, numbers, temp):
    """One bounded OCR invocation per document, preserving page identities."""
    if not shutil.which('pdftoppm') or not shutil.which('tesseract'):
        raise RuntimeError('pdf_ocr_engine_unavailable')
    if not numbers or numbers!=sorted(set(numbers)) or not 1<=numbers[0]<=numbers[-1]<=MAX_PAGES:
        raise ValueError('invalid_ocr_page_selection')
    prefix=Path(temp)/'ocr'
    # Render the bounded page interval once, then OCR only the selected images.
    subprocess.run(['pdftoppm','-f',str(numbers[0]),'-l',str(numbers[-1]),'-r','180',
        '-scale-to','2400','-png',str(pdf_path),str(prefix)],
        check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=60)
    images={int(p.stem.split('-')[-1]):p for p in Path(temp).glob('ocr-*.png')}
    if set(numbers)-set(images):raise RuntimeError('pdf_rendered_page_missing')
    if sum(p.stat().st_size for p in images.values())>180_000_000:
        raise RuntimeError('pdf_rendered_image_size_limit')
    selected=Path(temp)/'images.txt'
    selected.write_text('\n'.join(str(images[n]) for n in numbers)+'\n',encoding='utf8')
    # Single-threaded workers avoid OpenMP oversubscription on shared runners.
    output=subprocess.run(['tesseract',str(selected),'stdout','-l','rus+eng','--psm','3','tsv'],
        check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180,
        env={**os.environ,'OMP_THREAD_LIMIT':'1'}).stdout
    if len(output)>20_000_000:raise RuntimeError('pdf_ocr_output_size_limit')
    groups={n:{'lines':{},'conf':[],'numeric':[]} for n in numbers};observed=set()
    for word in csv.DictReader(io.StringIO(output.decode('utf-8')),delimiter='\t',quoting=csv.QUOTE_NONE):
        index=int(word['page_num'])-1
        if not 0<=index<len(numbers):raise ValueError('ocr_page_identity_mismatch')
        n=numbers[index]
        if word.get('level')=='1':observed.add(n)
        if word.get('level')!='5' or not word.get('text','').strip():continue
        confidence=float(word['conf'])
        if not 0<=confidence<=100:raise ValueError('invalid_ocr_confidence')
        group=groups[n];group['conf'].append(confidence)
        if re.search(r'\d',word['text']):group['numeric'].append(confidence)
        key=tuple(word[k] for k in ('block_num','par_num','line_num'))
        group['lines'].setdefault(key,[]).append(word['text'])
    if observed!=set(numbers):raise RuntimeError('ocr_page_count_mismatch')
    result={}
    for n,group in groups.items():
        confidences=group['conf'];numeric=group['numeric']
        value='\n'.join(' '.join(words) for words in group['lines'].values())
        result[n]=(value,{'engine':'tesseract','languages':'rus+eng','psm':3,
            'image_sha256':sha(images[n].read_bytes()),'tsv_sha256':sha(output),
            'batch_page_number':numbers.index(n)+1,'batch_pages':len(numbers),'omp_thread_limit':1,
            'words':len(confidences),'low_confidence_words':sum(x<80 for x in confidences),
            'minimum_numeric_confidence':min(numeric) if numeric else None,
            'mean_word_confidence':round(sum(confidences)/len(confidences),2) if confidences else None})
    return result


def needs_page_ocr(native_text, image_count):
    """Image-heavy pages may expose only native contact/footer fragments.

    This layout heuristic uses no document name, ID, hash or expected wording.
    Sparse numeric native-only pages do not need OCR.
    """
    characters=len(re.findall(r'\w',native_text))
    return not native_text or (image_count>0 and characters<40) or (image_count>=10 and characters<500)


def _prepare_pdf_page(page):
    """Inspect Form resources before native extraction can recurse into them.

    Shared resource dictionaries may refer back to their own Forms. Visit
    their objects once; only a cycle of actual Do calls is recursive drawing.
    Legacy Forms without Resources use this page's resources, including when
    the same Form is used on another page with different fonts or XObjects.
    """
    from copy import copy
    from pypdf.generic import ContentStream,DictionaryObject,NameObject
    images=set();seen=set();seen_resources=set();references=0
    resources={};forms={}

    def resolve(value):
        return value.get_object() if hasattr(value,'get_object') else value

    def xobjects(resources):
        resources=resolve(resources)
        if not isinstance(resources,dict):raise ValueError('pdf_xobject_resource_shape')
        result=resolve(resources.get('/XObject',{}))
        if not isinstance(result,dict):raise ValueError('pdf_xobject_resource_shape')
        return result

    page_resources=resolve(page.get('/Resources',{}))
    pending=[page_resources]
    while pending:
        resource=resolve(pending.pop())
        objects=xobjects(resource)
        resources[id(resource)]=(resource,objects)
        if id(objects) in seen_resources:continue
        seen_resources.add(id(objects))
        for reference in objects.values():
            references+=1
            if references>MAX_XOBJECT_REFERENCES:raise ValueError('pdf_xobject_reference_limit')
            obj=resolve(reference)
            if not isinstance(obj,dict):raise ValueError('pdf_xobject_resource_shape')
            ident=id(obj)
            if ident in seen:continue
            seen.add(ident)
            if obj.get('/Subtype')=='/Image':
                images.add(ident)
            elif obj.get('/Subtype')=='/Form':
                if not hasattr(obj,'get_data'):raise ValueError('pdf_xobject_resource_shape')
                forms[ident]=obj
                pending.append(obj.get('/Resources',page_resources))

    if any('/Resources' not in form for form in forms.values()):
        # Copy only the bounded resource graph. Stream bytes and non-Form
        # objects stay shared; page-specific bindings never mutate the reader.
        bound_forms={ident:copy(form) for ident,form in forms.items()}
        bound_resources={}
        for ident,(resource,objects) in resources.items():
            bound=DictionaryObject(resource)
            bound_objects=DictionaryObject(objects)
            for name,reference in objects.items():
                form=bound_forms.get(id(resolve(reference)))
                if form is not None:bound_objects[name]=form
            bound[NameObject('/XObject')]=bound_objects
            bound_resources[ident]=bound
        for ident,form in forms.items():
            resource=resolve(form.get('/Resources',page_resources))
            bound_forms[ident][NameObject('/Resources')]=bound_resources[id(resource)]
        page=copy(page)
        page[NameObject('/Resources')]=bound_resources[id(page_resources)]

    calls={};active=set();invocations=0;inline_images=0

    def drawing(obj,stream,depth):
        nonlocal invocations,inline_images
        if depth>MAX_FORM_DEPTH:raise ValueError('pdf_xobject_depth_limit')
        key=id(obj)
        if key not in calls:
            calls[key]=[]
            if stream is not None:
                if len(stream.get_data())>MAX_CONTENT_STREAM_BYTES:raise ValueError('pdf_content_stream_limit')
                objects=xobjects(obj.get('/Resources',{}))
                for operands,operator in ContentStream(stream,page.pdf,'bytes').operations:
                    if operator==b'INLINE IMAGE':
                        # Each stream is parsed once, including reused Forms.
                        inline_images+=1
                        continue
                    if operator!=b'Do':continue
                    if len(operands)!=1 or not isinstance(operands[0],str):raise ValueError('pdf_xobject_resource_shape')
                    target=resolve(objects.get(operands[0]))
                    if not isinstance(target,dict):raise ValueError('pdf_xobject_resource_shape')
                    if target.get('/Subtype')=='/Form':calls[key].append(target)
        for form in calls[key]:
            invocations+=1
            if invocations>MAX_FORM_INVOCATIONS:raise ValueError('pdf_xobject_invocation_limit')
            ident=id(form)
            if ident in active:raise ValueError('pdf_xobject_cycle')
            active.add(ident)
            drawing(form,form,depth+1)
            active.remove(ident)

    drawing(page,page.get_contents(),0)
    return page,len(images)+inline_images


def page_image_count(page):
    return _prepare_pdf_page(page)[1]


def extract_pdf(data, *, allow_ocr=True):
    if not isinstance(data,bytes) or not data.startswith(b'%PDF-') or not 100<=len(data)<=MAX_BYTES:
        raise ValueError('invalid_or_oversized_pdf')
    from pypdf import PdfReader
    reader=PdfReader(io.BytesIO(data),strict=True)
    if reader.is_encrypted or not 1<=len(reader.pages)<=MAX_PAGES:
        raise ValueError('pdf_encrypted_or_page_limit')
    pages=[];errors=[];ocr_count=0;total=0;needed=[]
    with tempfile.TemporaryDirectory() as temp:
        pdf_path=Path(temp)/'document.pdf';pdf_path.write_bytes(data)
        for number,page in enumerate(reader.pages,1):
            page,images=_prepare_pdf_page(page)
            value=(page.extract_text() or '').strip()
            item={'number':number,'text':value,'sha256':sha(value.encode()),'method':'native_pdf_text'}
            if needs_page_ocr(value,images):
                needed.append(number);item['native_text']=value;item['method']='missing_text'
            total+=len(value)
            if total>MAX_TEXT:raise ValueError('pdf_total_text_limit')
            pages.append(item)
        if needed:
            if allow_ocr:
                try:
                    found=ocr_pages(pdf_path,needed,temp)
                    if set(found)!=set(needed):raise RuntimeError('ocr_page_count_mismatch')
                    for n in needed:
                        value,metrics=found[n];item=pages[n-1]
                        item.update(text=value,sha256=sha(value.encode()),method='ocr_unverified',ocr=metrics)
                        ocr_count+=1
                except (RuntimeError,subprocess.SubprocessError,OSError,ValueError) as exc:
                    reason=str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__
                    errors.extend({'page':n,'reason':reason} for n in needed)
            else:errors.extend({'page':n,'reason':'ocr_disabled'} for n in needed)
        for page in pages:
            if not page['text']:errors.append({'page':page['number'],'reason':'empty_page_no_inferred_text'})
        if sum(len(p['text']) for p in pages)>MAX_TEXT:raise ValueError('pdf_total_text_limit')
    title=str(reader.metadata.title or '') if reader.metadata else ''
    return {'document_sha256':sha(data),'page_count':len(pages),'pages':pages,
            'title':title[:300],'errors':errors,'ocr_pages':ocr_count}


def page_groups(pages):
    """Bound each Sheets record without truncating any extracted source text."""
    groups=[];group=[];length=0
    for page in pages:
        # A very dense individual page is split with an explicit character offset.
        value=page['text']
        fragments=[{**page,'text':value[i:i+PART_CHARS], 'text_offset':i,
                    'sha256':sha(value[i:i+PART_CHARS].encode())}
                   for i in range(0,max(1,len(value)),PART_CHARS)]
        for fragment in fragments:
            n=len(fragment['text'])+60
            if group and length+n>PART_CHARS:
                groups.append(group);group=[];length=0
            group.append(fragment);length+=n
    if group:groups.append(group)
    return groups


def page_text(pages):
    return '\n\n'.join(f"[Страница {p['number']}; позиция {p.get('text_offset',0)}]\n{p['text']}" for p in pages)


def document_records(source_id,native_prefix,program,partner,url,observed_at,doc,*,parent_source,label='',parent_sha256=None,extra_details=None,link_kind='detail_page',locator=''):
    from normalized import make_offer
    groups=page_groups(doc['pages']);rows=[]
    title=doc['title'].strip()
    if not re.search(r'[^\W\d_]',title):
        title=label.strip() or next((p['text'].split('\n')[0].strip() for p in doc['pages'] if p['text'].strip()),'Документ источника')
    for index,pages in enumerate(groups,1):
        full=page_text(pages)
        has_text=any(p['text'].strip() for p in pages)
        warnings=['rule_bundle_not_additive_discount','user_eligibility_not_verified',
                  'pdf_table_relationships_not_inferred','document_dates_not_automatically_offer_validity']
        if link_kind=='page_block':warnings.append('temporary_document_url_not_persisted_use_parent_locator')
        if doc['ocr_pages']:warnings.append('ocr_text_unverified_no_manual_corrections')
        if doc['errors']:warnings.append('document_text_extraction_partial')
        details={'evidence_role':'supplementary_rules_not_incremental_discount',
            'extraction_method':'live_pdf_native_text_or_ocr','document_sha256':doc['document_sha256'],
            'parent_source':parent_source,'parent_response_sha256':parent_sha256,
            'discovery_label':label,'page_count':doc['page_count'],'pages':pages,
            'document_part':{'number':index,'total':len(groups)},'document_errors':doc['errors'],
            'public_aliases':[url] if link_kind=='detail_page' else [],'ocr_pages':doc['ocr_pages'],'live_document_text':True}
        details={**(extra_details or {}),**details}
        rows.append(make_offer(source_id,native_prefix+(f':part:{index}' if len(groups)>1 else ''),
            program,partner,title[:300] if has_text else '',url,observed_at,title=title[:300],
            conditions=full,record_kind='program_rules' if has_text else 'source_observation',
            source_status='public_rules_ocr_unverified' if doc['ocr_pages'] else 'public_rules_text',
            link_kind=link_kind,locator=(locator+'; ' if locator else '')+'PDF '+','.join(str(p['number']) for p in pages),details=details,warnings=warnings))
    return rows


def validate_document_record(record):
    """Publisher verifies source-text bindings too, not just the final row hash."""
    from normalized import text
    d=record['details'];pages=d.get('pages',[])
    if (record['record_kind'] not in ('program_rules','source_observation')
        or d.get('evidence_role')!='supplementary_rules_not_incremental_discount'
        or not re.fullmatch('[a-f0-9]{64}',d.get('document_sha256',''))
        or not pages or record['conditions_text']!=text(page_text(pages),markup=False)):
        raise ValueError('live_document_identity_or_text_mismatch')
    for page in pages:
        if (type(page.get('number')) is not int or not 1<=page['number']<=d['page_count']
            or page.get('sha256')!=sha(page['text'].encode())):
            raise ValueError('live_document_page_evidence_mismatch')
    if d.get('ocr_pages') and (record['source_status']!='public_rules_ocr_unverified'
            or 'ocr_text_unverified_no_manual_corrections' not in record['warnings']):
        raise ValueError('OCR_cannot_be_promoted_to_native_text')
