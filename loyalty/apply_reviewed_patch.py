"""Temporary exact-byte source transfer. Removed by the verification workflow."""
from pathlib import Path
import hashlib,subprocess
before={"loyalty/normalized.py":"6a6fb83eb166a7516fdbe6e01aec6f60e83e86021bc703d69ad31e1adb8b566c","loyalty/promo_codes.py":"cf1307cabd1425c1be731f1f498f54b735f7f464dbda271e2a43028da3c8e274","loyalty/collect_normalized.py":"8f6083e10169d27e6ed9f09bcb7bdc0c7a6de53f17d6ac5064130b64174c123a","loyalty/tests/test_promo_evidence.py":"240fe9d16e92046a571482705138deb031b3b7175705c15ae536f5fb08508014"}
after={"loyalty/normalized.py":"a4bcecb8855ee1f9f2cae1eae5e5431b116769e946ff26f5d6f76a9fbf76edb6","loyalty/promo_codes.py":"b57f7e33f008ac02eabf48493ac32af80777d8cc5f4b159bc1bc159b337f1d15","loyalty/collect_normalized.py":"6f94683277270f737a4051440c257fbf98ac7e551f480cfec93a9f39e1469011","loyalty/tests/test_promo_evidence.py":"b6c1feeabd2cdfea285204bc7553efd4cbc1f93460be59225135b0d71af426dc","loyalty/table_benefits.py":"7f1e59da66c0900dbd89a1fbe078c8ef82386c1cec641f26645b72a2997e6e2b","loyalty/read_budget.py":"9a755acbc054c4455f9d25fc890644a4e175ea71659e833f375eabbadfb33e96","loyalty/tests/test_table_benefits.py":"5908b5c6d236b5a3340ad22e73c43d9fe99e7cfa28c3c35a6b38e4eaeaca8f5c","loyalty/tests/test_catalog_read_budget.py":"f3e8da67222590103d96c2e7baa8907f0ea9b784c98292f3860362bd05455d30"}
for name,sha in before.items():
 if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=sha:raise ValueError('Unexpected baseline '+name)
p=Path('loyalty/repaired-source.patch')
if hashlib.sha256(p.read_bytes()).hexdigest()!='15af801a81d4deb9408d1650b268431ae67a3ebefd0277dca0ac543d746d0ca4':raise ValueError('Patch byte mismatch')
subprocess.run(['git','apply','--check',str(p)],check=True)
subprocess.run(['git','apply',str(p)],check=True)
for name,sha in after.items():
 if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=sha:raise ValueError('Tested source mismatch '+name)
subprocess.run(['git','add','--',*after],check=True)
print('All eight source/test files match the locally tested bytes.')
