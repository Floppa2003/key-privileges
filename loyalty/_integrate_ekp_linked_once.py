"""One-time tested branch repair, removed before release."""
from pathlib import Path
import hashlib
p=Path('loyalty/ekp_linked_rules.py')
def blob(data):
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
data=p.read_bytes()
assert blob(data)=='733624ad54179cb5a63641b7da96cf87862bf7bb'
s=data.decode()
changes=[
 ('return str(soup)\n\ndef html_fields','return str(soup.html)\n\ndef html_fields'),
 ("if len(set(headings))!=1:raise ValueError('el_html_needs_render_or_scope_review')", "if not headings and soup.title and soup.title.get_text(strip=True):\n        headings=[text(soup.title.get_text(' ',strip=True))]\n    if len(set(headings))!=1:raise ValueError('el_html_needs_render_or_scope_review')"),
 ("raw=clean_html(raw).encode();html_fields(raw)","raw=clean_html(raw).encode()\n                dom=BeautifulSoup(raw,'html.parser');body=dom.find('main') or dom.body\n                receipt['html_structure']={'h1_count':len(body.select('h1')) if body else 0,\n                    'text_chars':len(text(body.get_text('\\n',strip=True))) if body else 0}\n                html_fields(raw)")]
for old,new in changes:
    assert s.count(old)==1,old
    s=s.replace(old,new)
assert blob(s.encode())=='1d94673bd3fd71d2286a500331e77337c67df7a1'
p.write_text(s)
print('Applied bounded HTML roundtrip and identity repairs.')
