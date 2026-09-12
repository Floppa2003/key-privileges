"""Temporary checksum-bound transfer; runs before tests and is removed by CI."""
import hashlib,subprocess
from pathlib import Path
before={'loyalty/public_transport.py':'3bc472539bed36e1e0c546d088fd80f57c072b5f9c8a6f8130020c82c6b46f08','loyalty/mir_ui.py':'235bdd2ce0b09fed2276b50350baa2dc3db73c62710905f8ed4428905f7ca9b0'}
after={'loyalty/public_transport.py':'fbd4f31186ae1a9ef9bde456822d2f7899bebee4988d37f866ba46d27168f349','loyalty/mir_ui.py':'b38e7683ca13fdb1e59ef35c4a8f9d23c219623f86c05703685314f0455f1875'}
for p,h in before.items():
 if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h:raise ValueError('baseline mismatch '+p)
subprocess.run(['git','apply','--check','loyalty/repair.patch'],check=True)
subprocess.run(['git','apply','loyalty/repair.patch'],check=True)
for p,h in after.items():
 if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h:raise ValueError('tested source mismatch '+p)
