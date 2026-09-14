"""Generalization tests: IDs, rates, titles and captions are runtime inputs."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from announcements import parse_feed
CFG={'id':'mir_announcements','channel':'promomir','name':'Мир','url':'https://t.me/s/promomir','lookback_days':180}
NOW='2026-09-14T10:00:00+00:00'
def media(pid,body):
 return f'<div class="tgme_widget_message_one_media"><a href="https://t.me/promomir/{pid}?single">audio</a><div class="tgme_widget_message_text">{body}</div></div>'
def album(pid,body):
 return f'<div class="tgme_widget_message" data-post="promomir/{pid}">{body}<a class="tgme_widget_message_date"><time datetime="2026-09-10T00:00:00+00:00"></time></a></div>'
class LiveStructureTests(unittest.TestCase):
 def test_album_is_read_for_arbitrary_ids_and_changed_values(self):
  for pid,value in [(98701,8),(98705,17)]:
   html=album(pid,media(pid,f'Кешбэк {value}% на велосипеды.')+media(pid+1,'Скидка 3% на билеты.'))
   parsed=parse_feed(html,CFG,NOW)
   self.assertEqual(parsed['errors'],[])
   self.assertEqual(len(parsed['records']),1)
   r=parsed['records'][0]
   self.assertEqual([p['native_id'] for p in r['details']['message_parts']],[f'promomir/{pid}',f'promomir/{pid+1}'])
   self.assertEqual({x['value'] for x in r['rates']},{str(value),'3'})
 def test_edited_caption_replaces_previous_text_not_a_canned_response(self):
  raw=album(9991,media(9991,'Кешбэк 12% на кофе')+media(9992,'Новые условия'))
  a=parse_feed(raw,CFG,NOW)['records'][0]
  b=parse_feed(raw.replace('12% на кофе','19% на книги'),CFG,NOW)['records'][0]
  self.assertEqual(a['id'],b['id']);self.assertNotEqual(a['content_sha256'],b['content_sha256'])
  self.assertNotIn('кофе',b['benefit_text']);self.assertIn('19%',b['benefit_text'])
 def test_nonnumeric_reward_anchor_remains_unquantified_evidence(self):
  body=media(9991,'<a href="https://clck.ru/Changed">Прокат с кешбэком</a>')+media(9992,'Другой текст')
  r=parse_feed(album(9991,body),CFG,NOW)['records'][0]
  self.assertEqual(r['rates'],[]);self.assertIsNone(r['partner_name']);self.assertIsNone(r['valid_until'])
 def test_multiple_unowned_blocks_are_not_arbitrarily_joined(self):
  body='<div class="tgme_widget_message_text">Скидка 12%</div><div class="tgme_widget_message_text">Скидка 99%</div>'
  r=parse_feed(album(9991,body),CFG,NOW)
  self.assertEqual(r['records'],[]);self.assertEqual(r['errors'][0]['reason'],'ambiguous_message_text')
 def test_foreign_album_identity_and_duplicate_member_fail(self):
  for body in [media(9991,'Кешбэк 10%')+media(9991,'Скидка 4%'),(media(9991,'Кешбэк 10%')+media(9992,'Скидка 4%')).replace('/promomir/9992?','/foreign/9992?')]:
   r=parse_feed(album(9991,body),CFG,NOW)
   self.assertEqual(r['records'],[]);self.assertTrue(r['errors'])
 def test_album_does_not_promote_general_news_or_follow_shortlinks(self):
  r=parse_feed(album(9991,media(9991,'Новый выпуск подкаста')+media(9992,'<a href="https://clck.ru/x">Купить билеты</a>')),CFG,NOW)
  self.assertEqual(r['records'],[])
if __name__=='__main__':unittest.main()
