"""Checksum-bound correction to the real public article readiness predicate."""
from pathlib import Path
import hashlib
p=Path('loyalty/known_rules.py')
if hashlib.sha256(p.read_bytes()).hexdigest()!='4c64134ab5a642d118e968c7a22e8453e3f7a93d7c178652080a76a50f08ffde':raise ValueError('Unexpected rule baseline')
s=p.read_text();old="                    '(q)=>{const a=document.querySelectorAll(q.selector);return a.length===1 && a[0].innerText.includes(q.text)}',"
assert s.count(old)==1
s=s.replace('async def collect_known_rules(','''ARTICLE_READY_JS=r"(q)=>{const a=document.querySelectorAll(q.selector);const n=(s)=>s.replace(/\\s+/g,' ').replace(/‑/g,'-');return a.length===1 && n(a[0].innerText).includes(n(q.text))}"


async def collect_known_rules(''').replace(old,'                    ARTICLE_READY_JS,')
p.write_text(s)
for name,digest in {'loyalty/known_rules.py':'08ae62c7c17df0998cf796dfefcff6b26a7788cc30449dbaaaf72444b47b20f9','loyalty/tests/test_article_readiness.py':'072ad102b01db08aedd83fcbb9a8f95e917c1b10f283d975f2d3ddd11509206d'}.items():
 if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise ValueError('Transferred file mismatch: '+name)
print('Published Unicode variants accepted by the tested readiness predicate.')
