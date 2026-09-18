"""Hotel-owned RZD terms retain their explicit date, without account-code claims."""
import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters import extract
from partner_pages import explicit_period,CONFIG
from normalized import validate_offer
SID='rzd_sacvoyage_public';URL='https://sacvoyage.ru/partners/rzhd-bonus/'
NOW='2026-09-18T00:00:00+00:00'


def page(end='31.12.2025',rate='14'):
    return f'''<html><main><div class="news-content"><h1 class="card-room__title">РЖД-Бонус</h1>
    <p>Скидка {rate}% на проживание в отеле</p><div class="news-content-text">
    <p>Участники РЖД Бонус бронируют на <a href="https://sacvoyage.ru/">wrong-label.example</a> по специальному промокоду.</p>
    <p>Предложение не суммируется с акциями. При заезде предъявить карту.</p>
    <p>Срок действия предложения: до {end}</p></div></div></main>
    <footer>Срок действия предложения: до 31.12.2099. Скидка 99%</footer></html>'''


class SacvoyageRzdTests(unittest.TestCase):
    def test_real_dispatch_retains_expired_date_and_unknown_code(self):
        r,=extract(SID,page(),URL,NOW);validate_offer(r)
        self.assertEqual(r['valid_until'],'2025-12-31')
        self.assertEqual(r['validity_status'],'expired_by_published_end')
        self.assertEqual([v['value'] for v in r['rates']],['14'])
        self.assertEqual(r['promo_codes'],[])
        self.assertIn('wrong-label.example',r['conditions_text'])
        self.assertEqual(r['details']['published_links'],[{'label':'wrong-label.example','href':'https://sacvoyage.ru/'}])
        self.assertNotIn('2099',r['conditions_text'])

    def test_source_rate_and_end_date_are_not_canned(self):
        r,=extract(SID,page('30.11.2027','18'),URL,NOW)
        self.assertEqual(r['rates'][0]['value'],'18')
        self.assertEqual(r['valid_until'],'2027-11-30')
        self.assertEqual(r['validity_status'],'within_published_period')

    def test_missing_date_cannot_borrow_footer_and_fails_closed(self):
        with self.assertRaises(ValueError):extract(SID,page().replace('Срок действия предложения: до 31.12.2025','Другие условия'),URL,NOW)

    def test_duplicate_or_invalid_end_date_fails(self):
        with self.assertRaises(ValueError):explicit_period('Срок действия предложения: до 31.12.2025. Срок действия предложения: до 31.12.2026','end_dmy')
        with self.assertRaises(ValueError):explicit_period('Срок действия предложения: до 31.02.2025','end_dmy')

    def test_page_publication_date_is_not_validity(self):
        self.assertEqual(explicit_period('Новость опубликована 18.09.2026','end_dmy'),(None,None,None))

    def test_existing_configurations_remain_distinct(self):
        routes=json.loads(Path(__file__).resolve().parents[1].joinpath('sources_normalized.json').read_text())
        self.assertEqual(len([r for r in routes if r['id']==SID and r['url']==URL]),1)
        self.assertNotEqual(CONFIG[SID]['program'],CONFIG['sacvoyage_loyalty']['program'])
        self.assertEqual(CONFIG[SID]['date_rule'],'end_dmy')

if __name__=='__main__':unittest.main()
