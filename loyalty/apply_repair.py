"""Temporary code transfer; strict pre/post hashes, removed before merging."""
import hashlib,re,subprocess
from pathlib import Path
before={'loyalty/mir_ui.py':'b38e7683ca13fdb1e59ef35c4a8f9d23c219623f86c05703685314f0455f1875','loyalty/collect_normalized.py':'9489d4e7a05a74b8d74302aec77cda225495b7723d76eeabf623a192e10f25eb','loyalty/normalized.py':'baa8d0f4cb3ef9542cd143f187f4075d257b3bb5f3b058b4d1aa748abaabe842','loyalty/tests/test_mir_repair.py':'85c68cde17f23e5e95e10575190f4719e5b4cdb3432cee00642dc4687c7bc69f'}
after={'loyalty/mir_ui.py':'b15e6f994176b63b1fe4b483a7857bb92a4a9575376951a61c795cf43ee94e75','loyalty/collect_normalized.py':'8f6083e10169d27e6ed9f09bcb7bdc0c7a6de53f17d6ac5064130b64174c123a','loyalty/normalized.py':'a44a605ea66d487ffbe40520c4a67b65ba5cd1648d2b98dcb0d237407d0eb115','loyalty/tests/test_mir_repair.py':'bf5bf53b61d5567161d98c912ea1c4b649ee0493a0429b31f45df633095682c4'}
for p,h in before.items():
 if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h:raise ValueError('baseline mismatch '+p)
p=Path('loyalty/repair.patch');original=p.read_text();s=original
s=s.replace('@@ -11,7 +11,7 @@\n from model import clean_url','@@ -11,7 +11,7 @@\n from bs4 import BeautifulSoup\n from model import clean_url')
s=re.sub(r'^--- a/([^\n]+)\n\+\+\+ b/\1\n',lambda m:'diff --git a/'+m[1]+' b/'+m[1]+'\n'+m[0],s,flags=re.M)
p.write_text(s)
subprocess.run(['git','apply','--check',str(p)],check=True)
subprocess.run(['git','apply',str(p)],check=True)
p.write_text(original)
for p,h in after.items():
 if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h:raise ValueError('tested byte mismatch '+p)
subprocess.run(['git','add','--',*after],check=True)
