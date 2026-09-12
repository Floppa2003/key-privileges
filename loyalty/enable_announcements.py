"""One-time bounded code-only patch, with pre/post hashes; removed by review CI."""
from pathlib import Path
import hashlib,subprocess
before={'loyalty/normalized.py':'7af1e2d432c31b46020cfebbf17a7f11c52e15e243491ed4113a1e07943537b7','loyalty/announcements.py':'427d37fe5ad2206dd448180123d946a3d087dfa77db8cbac7254676528bbb79d','loyalty/tests/test_announcements.py':'5745a6449511a6d90883a44410f3dc7c8b5d9b870e1b7fe67e215c425d67f315'}
for name,sha in before.items():
 if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=sha:raise ValueError('Unexpected baseline '+name)
p=Path('loyalty/normalized.py');s=p.read_text().replace("    if r['link_kind']=='source_post':","    if r['source_id'] in ('ekp_announcements','rzd_announcements') or r['link_kind']=='source_post':").replace("if not channel or not re.fullmatch('/'+channel+r'/[0-9]+',urlsplit(r['source_url']).path)","if r['link_kind']!='source_post' or not channel or not re.fullmatch('/'+channel+r'/[0-9]+',urlsplit(r['source_url']).path)");p.write_text(s)
p=Path('loyalty/announcements.py');s=p.read_text().replace("    if dated:\n","    if not ids:\n        result['errors'].append({'phase':'pagination','reason':'no_public_messages_in_response'})\n    if dated:\n").replace("    return bool(cards or (LOYALTY.search(body) and NUMERIC_BENEFIT.search(body)))","    if cards:\n        return True\n    if re.search(r'опрос|голосован|мониторинг\\s+активност',body,re.I):\n        return False\n    role=re.search(r'скидк|к[еэ]шб[еэ]к|промокод|балл|подар',body,re.I)\n    return bool(LOYALTY.search(body) and role and NUMERIC_BENEFIT.search(body))");p.write_text(s)
p=Path('loyalty/tests/test_announcements.py');s=p.read_text()+'''

class PublicationBoundaryTests(unittest.TestCase):
 def test_announcement_cannot_be_promoted_by_changing_link_kind(self):
  from normalized import content_hash,validate_offer
  r=parse_feed(post('ekpcard/70','ЕКП скидка 10%'),CFG,NOW)['records'][0]
  r.update(record_kind='partner_offer',link_kind='detail_page',source_status='published',benefit_url=r['source_url'])
  r['content_sha256']=content_hash(r)
  with self.assertRaises(ValueError):validate_offer(r)
 def test_empty_archive_response_is_not_a_confirmed_archive_end(self):
  result=parse_feed('<html><body>Temporary empty page</body></html>',CFG,NOW)
  self.assertTrue(result['errors'])

class RelevanceTests(unittest.TestCase):
 def test_poll_percentages_and_weekly_reward_reminders_are_not_partner_offers(self):
  body='Итоги опроса «Городской диалог» ЕКП: 71% посетили театр. За новый опрос получите 20 баллов.'
  self.assertEqual(parse_feed(post('ekpcard/70',body),CFG,NOW)['records'],[])
 def test_percentage_requires_a_benefit_role_when_no_exact_card_is_linked(self):
  self.assertEqual(parse_feed(post('ekpcard/70','ЕКП: прирост аудитории составил 20%.'),CFG,NOW)['records'],[])
''';p.write_text(s)
after={'loyalty/normalized.py':'baa8d0f4cb3ef9542cd143f187f4075d257b3bb5f3b058b4d1aa748abaabe842','loyalty/announcements.py':'7f61a0c067e462d28b8788961baeaff56f387770b1a824a6dc0f66e956e522dc','loyalty/tests/test_announcements.py':'d1fcea591f14cfb9f686c8f719cd7cfb1e807b2f310567e370fa70bab92afbfe'}
for name,sha in after.items():
 if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=sha:raise ValueError('Final hash mismatch '+name)
subprocess.run(['git','add','--',*after],check=True)
print('All patched files match the locally tested 154-test revision.')
