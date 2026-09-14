"""One-time branch-only code transfer. Removed before production integration."""
import hashlib,json
from pathlib import Path
patches=Path('.github/live-runtime-edits.json')
if patches.exists():
    replacements={}
    for name,spec in json.loads(patches.read_text()).items():
        path=Path(name);old=path.read_text() if path.exists() else None
        actual=hashlib.sha256(old.encode()).hexdigest() if old is not None else None
        if actual!=spec['old_sha256']:raise ValueError('code baseline changed: '+name)
        value=spec.get('write',old)
        for start,size,new in reversed(spec.get('edits',[])):
            if name=='loyalty/announcements.py':
                new=new.replace("'\n\n'","'\\n\\n'").replace("'\n'","'\\n'")
            value=value[:start]+new+value[start+size:]
        actual=hashlib.sha256(value.encode()).hexdigest() if value is not None else None
        if actual!=spec['new_sha256']:raise ValueError('code result hash mismatch: '+name)
        replacements[path]=value
    for path,value in replacements.items():
        if value is None:path.unlink()
        else:path.write_text(value,encoding='utf8')
    patches.unlink()
    doc=Path('loyalty/document_text.py');s=doc.read_text()
    s=s.replace('ocr_count=0;total=0','ocr_count=0;ocr_attempted=0;total=0')
    s=s.replace('if allow_ocr and ocr_count<10:', 'if allow_ocr and ocr_attempted<10:\n                    ocr_attempted+=1')
    s=s.replace("    d=record['details'];pages=d.get('pages',[])","    from normalized import text\n    d=record['details'];pages=d.get('pages',[])")
    s=s.replace("__import__('normalized').text(page_text(pages))",'text(page_text(pages))')
    doc.write_text(s)
    p=Path('loyalty/NORMALIZED.md');s=p.read_text();s+='\nLive PDF extraction and generic album ownership supersede the historical visual-review profile; see LIVE_EXTRACTION.md.\n';p.write_text(s)
    p=Path('loyalty/RECOVERED_SOURCES.md');s=p.read_text();p.write_text('> Historical 2.8.0 contract; live linked-PDF discovery and extraction are described in LIVE_EXTRACTION.md (2.9.0).\n\n'+s)
p=Path('loyalty/collect_normalized.py');s=p.read_text()
s=s.replace("        for r in records:validate_offer(r)\n        report['normalized']=len(records)","        for r in records:validate_offer(r)\n        # One physical document can create several bounded evidence parts.\n        report['discovered_items']=report['discovered']\n        report['discovered']=max(report['discovered'],len(records))\n        report['normalized']=len(records)")
p.write_text(s)
p=Path('loyalty/document_text.py');s=p.read_text()
if 'def needs_page_ocr' not in s:
    s=s.replace('def extract_pdf(data, *, allow_ocr=True):',"def needs_page_ocr(native_text, image_count):\n    \"\"\"Image-heavy pages may expose only native contact/footer fragments.\n\n    This layout heuristic uses no document name, ID, hash or expected wording.\n    Sparse numeric native-only pages do not need OCR.\n    \"\"\"\n    characters=len(re.findall(r'\\w',native_text))\n    return not native_text or (image_count>0 and characters<40) or (image_count>=10 and characters<500)\n\n\ndef extract_pdf(data, *, allow_ocr=True):")
    s=s.replace("images=any(x.get_object().get('/Subtype')=='/Image' for x in xobjects.values())\n            needs_ocr=(not value or (images and len(re.findall(r'[\\w]',value))<40))", "images=sum(x.get_object().get('/Subtype')=='/Image' for x in xobjects.values())\n            native=value\n            needs_ocr=needs_page_ocr(value,images)")
    s=s.replace("if metrics:item['ocr']=metrics", "if needs_ocr:item['native_text']=native\n            if metrics:item['ocr']=metrics")
p.write_text(s)
