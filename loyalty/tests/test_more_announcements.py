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
