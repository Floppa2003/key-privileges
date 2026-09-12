import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from public_transport import check_response,allowed_request
class PublicTransportTests(unittest.TestCase):
 def test_success_status_with_access_denial_is_not_data(self):
  with self.assertRaises(RuntimeError):check_response(200,'<html><title>Доступ к сайту временно ограничен</title></html>')
 def test_forbidden_and_server_errors_are_not_empty_catalogs(self):
  for status in (401,403,429,503):
   with self.assertRaises(RuntimeError):check_response(status,'Service unavailable')
 def test_non_public_or_login_requests_are_never_replayed(self):
  for url in ['http://example.com/promo','https://evil.example/promo','https://vamprivet.ru/personal/','https://vamprivet.ru/auth/login','https://vamprivet.ru/api/accept?token=x']:
   self.assertFalse(allowed_request(url,'vamprivet.ru'))
  self.assertTrue(allowed_request('https://vamprivet.ru/api/moskva-i-mo/promo/filter-json?page_catalog_list=2','vamprivet.ru'))
 def test_normal_public_html_passes(self):
  check_response(200,'<h1>Партнёры</h1><p>Скидка10%</p>')
if __name__=='__main__':unittest.main()
