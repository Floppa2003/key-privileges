"""One-time checksum-bound correction; removed by branch CI after tests."""
from pathlib import Path
import hashlib,subprocess
L=Path('loyalty')
expected={'announcements.py':'43b2a73bde1b24473de0e3f91a70eeec751ab1c2b7054efccaf11a0830e12001','tests/test_more_announcements.py':'3c2806f513b6f18f1dda5651d5a4e2b861bb6dd3fa8141786dbd5f1171e3a277'}
for f,h in expected.items():
 if hashlib.sha256((L/f).read_bytes()).hexdigest()!=h:raise ValueError('unexpected code '+f)
p=L/'announcements.py';s=p.read_text().replace("return bool(context and reward and NUMERIC_BENEFIT.search(body)","return bool(context and reward and (cards or re.search(r'\\d\\s*%|\\d+\\s+(?:бонус\\w*|балл\\w*|мил[ьяиюе]\\w*)',body,re.I))")
s=s.replace("        content = node.select_one('.tgme_widget_message_text')\n        if content is None:","        own_text=[n for n in node.select('.tgme_widget_message_text')\n                  if 'js-message_reply_text' not in n.get('class',[])\n                  and not n.find_parent(class_='tgme_widget_message_reply')\n                  and not n.find_parent(class_='tgme_widget_message_link_preview')]\n        if len(own_text)>1:\n            result['errors'].append({'phase':'post','native_id':native,'reason':'ambiguous_message_text'})\n        content=own_text[0] if len(own_text)==1 else None\n        if content is None:");p.write_text(s)
p=L/'tests/test_more_announcements.py';p.write_text(p.read_text()+'''
class ReplyAndNavigationTests(unittest.TestCase):
 def test_reply_excerpt_does_not_become_new_posts_offer(self):
  cfg=config('mir_announcements','promomir')
  html='<div class="tgme_widget_message" data-post="promomir/1927"><a class="tgme_widget_message_reply"><div class="tgme_widget_message_text js-message_reply_text">Скидка 10% по карте Мир</div></a><div class="tgme_widget_message_text js-message_text">Завтра пойду кататься.</div><a class="tgme_widget_message_date"><time datetime="2026-09-04T14:37:01+00:00"></time></a></div>'
  self.assertEqual(parse_feed(html,cfg,NOW)['records'],[])
 def test_channel_directory_does_not_count_as_a_coupon_offer(self):
  cfg=config('mir_announcements','promomir')
  self.assertEqual(parse_feed(post('promomir',1866,'Четыре канала: здесь акции, скидки, промокоды и кешбэк.'),cfg,NOW)['records'],[])
 def test_actual_nonnumeric_offer_with_card_link_remains_evidence(self):
  cfg=config('mir_announcements','promomir')
  body='Скидка на анализы у партнера <a href="https://vamprivet.ru/promo/clinic">Правила</a>'
  self.assertEqual(len(parse_feed(post('promomir',10,body),cfg,NOW)['records']),1)
''')
after={'announcements.py':'df991c84fce02461f388f66a634badad70fe5b358b98238d71e68bfa39343591','tests/test_more_announcements.py':'aa441cf9257732c5046d9c8e6caf1eeb7eda7b4ea12c92b823726caea9a6e27e'}
for f,h in after.items():
 if hashlib.sha256((L/f).read_bytes()).hexdigest()!=h:raise ValueError('transfer mismatch '+f)
subprocess.run(['git','add','--','loyalty/announcements.py','loyalty/tests/test_more_announcements.py'],check=True)
