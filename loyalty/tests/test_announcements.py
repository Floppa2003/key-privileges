"""Fixtures model public Telegram post markup, with adversarial negative canaries."""
import unittest,sys,asyncio
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
try:
 from announcements import parse_feed, collect_announcements
except ImportError:
 parse_feed=None
 collect_announcements=None
NOW='2026-09-13T10:00:00+00:00'
CFG={'id':'ekp_announcements','channel':'ekpcard','name':'ЕКП — объявления','url':'https://t.me/s/ekpcard','mode':'announcements','lookback_days':180,'max_pages':60}
def post(pid,body,when='2026-09-10T13:00:00+00:00',forward=False):
 return (f'<div class="tgme_widget_message" data-post="{pid}">'+ ('<a class="tgme_widget_message_forwarded_from">foreign</a>' if forward else '')+f'<div class="tgme_widget_message_text">{body}</div><a class="tgme_widget_message_date" href="https://t.me/{pid}"><time datetime="{when}"></time></a></div>')
def card(name='Studio',n=123):return f'<a href="https://ekp.spb.ru/capabilities/loyalty/tiles/{n}?region=78">{name}</a>'
class AnnouncementTests(unittest.TestCase):
 def setUp(self):self.assertIsNotNone(parse_feed,'announcement adapter is not implemented')
 def test_partner_text_is_not_shifted_from_neighbor_post(self):
  html=post('ekpcard/50','Для держателей ЕКП '+card()+' — скидка 15%.')+post('ekpcard/51','Прогноз погоды +20')
  result=parse_feed(html,CFG,NOW)
  self.assertEqual(len(result['records']),1)
  r=result['records'][0];self.assertEqual(r['record_kind'],'announcement');self.assertIsNone(r['benefit_url']);self.assertEqual(r['source_url'],'https://t.me/ekpcard/50')
  self.assertEqual(r['details']['linked_cards'][0]['label'],'Studio');self.assertNotIn('погоды',r['benefit_text']);self.assertEqual(r['rates'][0]['value'],'15')
 def test_publication_date_is_not_expiry_and_changed_offer_keeps_id(self):
  h=post('ekpcard/50','Для держателей ЕКП '+card()+' — скидка 15%.')
  a=parse_feed(h,CFG,NOW)['records'][0];b=parse_feed(h.replace('15%','10%'),CFG,NOW)['records'][0]
  self.assertIsNone(a['valid_until']);self.assertEqual(a['id'],b['id']);self.assertNotEqual(a['content_sha256'],b['content_sha256'])
 def test_multiple_partners_keep_links_not_one_shared_rate_assignment(self):
  r=parse_feed(post('ekpcard/50',card('A',1)+card('B',2)+' Партнёры ЕКП — скидки.'),CFG,NOW)['records'][0]
  self.assertIsNone(r['partner_name']);self.assertEqual(len(r['details']['linked_cards']),2)
 def test_reject_foreign_channel_forwarded_posts_and_credential_links(self):
  r=parse_feed(post('evil/50','Скидка 15% ЕКП')+post('ekpcard/51','Скидка 20% ЕКП',forward=True)+post('ekpcard/52','Скидка 10% ЕКП <a href="https://example.com/?token=secret">secret</a>'),CFG,NOW)
  self.assertEqual(len(r['records']),1);self.assertEqual(r['records'][0]['details']['outgoing_links'],[])
 def test_fpc_footer_does_not_make_general_train_prices_a_loyalty_offer(self):
  cfg={**CFG,'id':'rzd_announcements','channel':'fpcrussia','url':'https://t.me/s/fpcrussia'}
  body='Скидки до 40% на билеты! Обязательно укажите при покупке билета ваш номер «РЖД Бонус», чтобы копить баллы на новые поездки'
  self.assertEqual(parse_feed(post('fpcrussia/50',body),cfg,NOW)['records'],[])
  own='Участникам «РЖД Бонус» скидка 5% на тур. Подробные условия на сайте.'
  self.assertEqual(len(parse_feed(post('fpcrussia/51',own),cfg,NOW)['records']),1)
 def test_no_contest_or_weather_or_image_only_record(self):
  html=post('ekpcard/50','Розыгрыш 10 подарков для держателей ЕКП')+post('ekpcard/51','Погода +15 ЕКП')+post('ekpcard/52','')
  self.assertEqual(parse_feed(html,CFG,NOW)['records'],[])
 def test_pagination_must_stay_within_channel_and_move_back(self):
  html=post('ekpcard/100','Скидка 10% ЕКП')+'<a class="tme_messages_more" href="/s/evil?before=80" data-before="80">more</a>'
  self.assertIsNone(parse_feed(html,CFG,NOW)['next_url'])
  valid=html.replace('/s/evil','/s/ekpcard');self.assertEqual(parse_feed(valid,CFG,NOW)['next_url'],'https://t.me/s/ekpcard?before=80')
 def test_old_post_not_relabelled_as_today(self):
  html=post('ekpcard/40','Скидка 10% ЕКП','2025-01-01T12:00:00+00:00')
  result=parse_feed(html,CFG,NOW);self.assertEqual(result['records'],[]);self.assertTrue(result['reached_cutoff'])
 def test_ambiguous_and_missing_dates_fail_closed(self):
  html=post('ekpcard/50','Скидка 10% ЕКП',when='')
  result=parse_feed(html,CFG,NOW);self.assertEqual(result['records'],[]);self.assertEqual(len(result['errors']),1)
 def test_rate_has_its_full_clause_and_html_breaks_preserved(self):
  html=post('ekpcard/50','Держателям ЕКП '+card()+'<br>Скидка 15% на массаж.<br>Скидка 5% на спа.')
  r=parse_feed(html,CFG,NOW)['records'][0];self.assertEqual(len(r['rates']),2);self.assertNotIn('спа',r['rates'][0]['evidence'])

class FakeClient:
 def __init__(self,pages):self.pages=list(pages);self.calls=[]
 async def read(self,url,**kwargs):
  self.calls.append(url);v=self.pages.pop(0)
  if isinstance(v,Exception):raise v
  return v
class WalkTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):self.assertIsNotNone(collect_announcements,'announcement traversal is not implemented')
 async def test_later_failure_preserves_collected_posts(self):
  html=post('ekpcard/100','ЕКП — скидка 10%')+'<a class="tme_messages_more" href="/s/ekpcard?before=100" data-before="100">more</a>'
  report={'errors':[]};client=FakeClient([html,RuntimeError('http_503')]);rs=await collect_announcements(client,CFG,report,NOW,200)
  self.assertEqual(len(rs),1);self.assertEqual(len(report['errors']),1)
 async def test_page_and_record_caps_are_explicit_and_no_duplicates(self):
  html=post('ekpcard/100','ЕКП — скидка 10%')+post('ekpcard/101','ЕКП — скидка 15%')+'<a class="tme_messages_more" href="/s/ekpcard?before=100" data-before="100">more</a>'
  report={'errors':[]};rs=await collect_announcements(FakeClient([html]),CFG,report,NOW,1)
  self.assertEqual(len(rs),1);self.assertIn('record_limit',report['coverage'])

class AdditionalEvidenceTests(unittest.TestCase):
 def test_escaped_query_separator_is_not_a_new_parameter_name(self):
  h=post('ekpcard/70','Держателям ЕКП скидка 10% '+card().replace('?region=78','?region=78&amp;amp;categories=food'))
  r=parse_feed(h,CFG,NOW)['records'][0]
  self.assertEqual(r['details']['linked_cards'][0]['url'],'https://ekp.spb.ru/capabilities/loyalty/tiles/123?region=78&categories=food')
 def test_emoji_only_line_is_not_the_title(self):
  h=post('ekpcard/70','⚡️<br><b>Скидка 10% держателям ЕКП</b>')
  self.assertIn('Скидка',parse_feed(h,CFG,NOW)['records'][0]['title'])

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
