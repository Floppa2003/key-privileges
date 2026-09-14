"""Reject generic bank interest/news and never promote announcements into verified offers."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from announcements import parse_feed,CHANNELS
from normalized import validate_offer,content_hash
NOW='2026-09-14T10:00:00+00:00'
def config(k,ch):return {'id':k,'channel':ch,'url':'https://t.me/s/'+ch,'name':'Public programme','lookback_days':180,'max_pages':60}
def post(ch,n,body,when='2026-09-10T10:00:00+00:00'):
 return f'<div class="tgme_widget_message" data-post="{ch}/{n}"><div class="tgme_widget_message_text">{body}</div><a class="tgme_widget_message_date"><time datetime="{when}"></time></a></div>'
class MoreAnnouncementsTests(unittest.TestCase):
 def cfg(self,k,ch):
  self.assertEqual(CHANNELS.get(k),ch,'Missing explicit public channel registration');return config(k,ch)
 def test_mir_public_offer_keeps_exact_post_and_current_eligibility_unknown(self):
  cfg=self.cfg('mir_announcements','promomir')
  r=parse_feed(post('promomir',2000,'Кешбэк 10% при оплате картой «Мир». <a href="https://vamprivet.ru/promo/test">Правила</a>'),cfg,NOW)['records'][0]
  self.assertEqual(r['source_url'],'https://t.me/promomir/2000');self.assertEqual(r['record_kind'],'announcement');self.assertIsNone(r['benefit_url']);self.assertIsNone(r['valid_until'])
  self.assertEqual(len(r['details']['linked_cards']),1);validate_offer(r)
 def test_mir_statistics_contests_and_old_post_not_promoted(self):
  cfg=self.cfg('mir_announcements','promomir')
  html=post('promomir',1,'Доля карт выросла на 20%.')+post('promomir',2,'Розыгрыш скидки 10%.')+post('promomir',3,'Кешбэк 10% по карте Мир','2025-01-01T10:00:00+00:00')
  self.assertEqual(parse_feed(html,cfg,NOW)['records'],[])
 def test_bank_rewards_not_loan_interest_or_generic_history(self):
  cfg=self.cfg('bspb_announcements','mybspb')
  html=post('mybspb',1,'ЯРКО: кешбэк 5% баллами за покупки.')+post('mybspb',2,'Вклад 20% годовых в банке. ЯРКО.')+post('mybspb',3,'История банка: прирост аудитории 15%.')
  rs=parse_feed(html,cfg,NOW)['records'];self.assertEqual(len(rs),1);self.assertEqual(rs[0]['source_url'],'https://t.me/mybspb/1')
 def test_unconfigured_channel_and_forged_promotion_are_rejected(self):
  cfg=self.cfg('bspb_announcements','mybspb')
  r=parse_feed(post('mybspb',10,'ЕКП: кешбэк 5% за топливо.'),cfg,NOW)['records'][0]
  r.update(link_kind='detail_page',record_kind='partner_offer',source_status='published',benefit_url=r['source_url']);r['content_sha256']=content_hash(r)
  with self.assertRaises(ValueError):validate_offer(r)
  with self.assertRaises(ValueError):parse_feed('',config('mir_announcements','evil'),NOW)

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
