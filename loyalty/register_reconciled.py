"""One-time checksum-bound transfer of locally red/green-tested correction."""
from pathlib import Path
import hashlib,subprocess
root=Path('loyalty')
expected={'announcements.py':'df991c84fce02461f388f66a634badad70fe5b358b98238d71e68bfa39343591','tests/test_more_announcements.py':'aa441cf9257732c5046d9c8e6caf1eeb7eda7b4ea12c92b823726caea9a6e27e'}
for name,sha in expected.items():
 if hashlib.sha256((root/name).read_bytes()).hexdigest()!=sha:raise ValueError('Unexpected baseline '+name)
p=root/'announcements.py';s=p.read_text();old="                  and not n.find_parent(class_='tgme_widget_message_link_preview')]"
assert s.count(old)==1
p.write_text(s.replace(old,"                  and not n.find_parent(class_='tgme_widget_message_link_preview')\n                  and not n.find_parent(class_='tgme_widget_message_text')]"))
p=root/'tests/test_more_announcements.py';p.write_text(p.read_text()+'''

class NestedMessageTests(unittest.TestCase):
 def test_nested_native_text_wrapper_is_one_message_not_ambiguous(self):
  cfg=config('mir_announcements','promomir')
  body='<div class="tgme_widget_message_text js-message_text">Скидка 10% по карте Мир.</div>'
  result=parse_feed(post('promomir',2001,body),cfg,NOW)
  self.assertEqual(result['errors'],[])
  self.assertEqual(len(result['records']),1)
  self.assertEqual(result['records'][0]['benefit_text'],'Скидка 10% по карте Мир.')
 def test_disjoint_text_blocks_are_still_rejected_not_concatenated(self):
  cfg=config('mir_announcements','promomir')
  html=post('promomir',2001,'Скидка 10% по карте Мир.').replace('<a class="tgme_widget_message_date"','<div class="tgme_widget_message_text">Другой партнер: скидка 99%</div><a class="tgme_widget_message_date"')
  result=parse_feed(html,cfg,NOW)
  self.assertEqual(result['records'],[])
  self.assertEqual(result['errors'][0]['reason'],'ambiguous_message_text')
''')
after={'announcements.py':'526c917a651fb547ed8e4a153cd2b18aa68a1a289a03d332b50e6552a2e792fd','tests/test_more_announcements.py':'1bca1f24436048052636cab71ac386da9811756562d4ca39fc61987e60d38202'}
for name,sha in after.items():
 if hashlib.sha256((root/name).read_bytes()).hexdigest()!=sha:raise ValueError('Transfer mismatch '+name)
subprocess.run(['git','add','--','loyalty/announcements.py','loyalty/tests/test_more_announcements.py'],check=True)
