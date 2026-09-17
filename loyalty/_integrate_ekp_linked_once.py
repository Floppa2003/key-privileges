"""One-time branch repair; removed before release, never a collector input."""
import hashlib
from pathlib import Path

EXPECTED = {'ekp_linked_rules.py': '046b98240deb30f94f98e8261d96aecded96814e',
            'document_text.py': '9fc7690577108befdb7931abd90c73b2638895cb'}
FINAL = {'ekp_linked_rules.py': '733624ad54179cb5a63641b7da96cf87862bf7bb',
         'document_text.py': '82dd3503264d74faea1eb5da5a786699f3bad927'}

def blob(value):
    data = value.encode() if isinstance(value, str) else value
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()

files = {}
for name, expected in EXPECTED.items():
    data = (Path('loyalty')/name).read_bytes()
    assert blob(data) == expected, name
    files[name] = data.decode()

def replace(name, old, new):
    assert files[name].count(old) == 1, (name, old)
    files[name] = files[name].replace(old, new)

replace('ekp_linked_rules.py', "dom=BeautifulSoup(data,'html.parser');actual=",
        "dom=BeautifulSoup(bytes(data),'html.parser');actual=")
replace('document_text.py', "csv.DictReader(io.StringIO(output.decode('utf-8')),delimiter='\\t')",
        "csv.DictReader(io.StringIO(output.decode('utf-8')),delimiter='\\t',quoting=csv.QUOTE_NONE)")
replace('document_text.py', "title=doc['title'].strip() or next((p['text'].split('\\n')[0].strip() for p in doc['pages'] if p['text'].strip()),label or 'Документ источника')",
        "title=doc['title'].strip()\n    if not re.search(r'[^\\W\\d_]',title):\n        title=label.strip() or next((p['text'].split('\\n')[0].strip() for p in doc['pages'] if p['text'].strip()),'Документ источника')")
for name, value in files.items():
    assert blob(value) == FINAL[name], name
for name, value in files.items():
    (Path('loyalty')/name).write_text(value)
print('Applied exact reviewed repairs; no source or destination data used.')
