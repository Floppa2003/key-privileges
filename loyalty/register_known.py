"""Apply the reviewed text patch, verify exact resulting code, then remove this helper."""
import hashlib,subprocess
from pathlib import Path
BEFORE={'loyalty/public_transport.py':'fcdefa809b6f55c17fca9c7c63f56630e3ce183f7570feb6184584f982b835e7','loyalty/known_rules.py':'08ae62c7c17df0998cf796dfefcff6b26a7788cc30449dbaaaf72444b47b20f9','loyalty/known_rules.json':'18597ae3fda93dc6c9b16ba6e6e504a823bf25b3c5b474a4e574c9c8d9a93d50','loyalty/known_pdf.py':'d2eedd6c977ac6d29d3c5e0125f3d9a514f1ec45d584cb052eb70fca6bebcce3','loyalty/normalized.py':'e20c37103fce7f13c7bb4ac0ebbf1db71804513795638e2ffb1cb924cf140773','loyalty/collect_normalized.py':'b416c4ab6ef257b09c850c9e731ed9fc4cb80d4cb6b8d5ca20f6988e8420c671','loyalty/sources_normalized.json':'ead4671930c91534049c326829fb949d85ffb90f61fe37e2b8f42b2720abc728'}
AFTER={'loyalty/public_transport.py':'051cb6f262b061d50eec9026a1e4d619b1f39a8935e12c6c172e5784253ff7c8','loyalty/known_rules.py':'d2d77bc7fdda2585d5b3175ec49ba753b4ab0566ecfcea3faf7b146a2fdc8930','loyalty/known_rules.json':'e5e365bb942ed67132e347c72196c575008219b9e72187e020022050d41d59ed','loyalty/known_pdf.py':'56d52f5773e6c2421d7530d447b9b2aa36b2122c4c9782b68e32f9b5391ea41f','loyalty/normalized.py':'68114641c6410b016dd1e4f5099292b9707b532000e98a4039e3fe4bcef9d0cc','loyalty/collect_normalized.py':'4e08ddacee91b5d0fbafe64e6de7a34631beaad34c4a4da76a296b11d46c98c2','loyalty/sources_normalized.json':'e79e416e30a3624fb7339848b6077d51dd78346b329d8f5b815d58e15ce211c4','loyalty/utair_documents.py':'38fc683709740129963869a9280d252f92e83e07a7e383c706e526662d5bfa3b','loyalty/utair_documents.json':'4b3e2a167ff5222cd81eedf1b6bd51fd1caf31b8d7b27f4c1a42ce020fe51ae1','loyalty/tests/test_public_product_rules.py':'ced3250ba6620d1ffcdf57ecd84d3e9dd56a19ae05b2d62c1a16b6f5524a7d79','loyalty/tests/test_utair_documents.py':'ebaf5a5b3882c36888d987751b7d16b0739018be875e9b4362871aa646d3ba6f'}
for name,digest in BEFORE.items():
 if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise ValueError('Unexpected baseline '+name)
diff=Path('loyalty/register_known.patch').read_bytes()
subprocess.run(['git','apply','--check','-'],input=diff,check=True)
subprocess.run(['git','apply','-'],input=diff,check=True)
for name,digest in AFTER.items():
 if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise ValueError('Code transfer mismatch '+name)
subprocess.run(['git','add','--',*AFTER],check=True)
subprocess.run(['git','rm','--','loyalty/register_known.patch'],check=True)
print('All eleven files match the locally tested revision.')
