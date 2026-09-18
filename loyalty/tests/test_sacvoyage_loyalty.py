"""Source-owned sections, dynamic values and explicit audience separation."""
import json,sys,unittest
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters import extract
from partner_pages import CONFIG,extract_partner_page
from normalized import validate_offer
SID='sacvoyage_loyalty';URL='https://sacvoyage.ru/aktsii/'
NOW='2026-09-18T00:00:00+00:00'


def page(member='7',friend='12'):
    return ('<html><body><main><h2 class="about__title">Скидки</h2><div class="services__text">'
        '<p><strong>Программа лояльности</strong></p>'
        f'<p>При регистрации получаете скидку {member}% на бронирования на нашем сайте.</p>'
        '<p>Скидка не суммируется с акциями; не действует через агентства и по корпоративным тарифам.</p>'
        '<p><strong>Реферальная программа</strong></p><p>В профиле есть персональная ссылка.</p>'
        f'<p>Друг получает {friend}% на первое проживание.</p>'
        '<p>Рекомендателю подарок после регистрации и выезда друга.</p>'
        '<p>Условия могут меняться. Актуальная скидка в личном кабинете.</p>'
        '</div></main><aside>РЖД Бонус: скидка 91%, промокод OUTSIDE_ONLY.</aside></body></html>')


class SacvoyageTests(unittest.TestCase):
    def test_dynamic_real_dispatch_and_audience_boundaries(self):
        rows=extract(SID,page('7,5','13'),URL,NOW)
        self.assertEqual([r['rates'][0]['value'] for r in rows],['7.5','13'])
        self.assertEqual([r['native_id'] for r in rows],['member','referred_guest'])
        self.assertIn('корпоративным',rows[0]['conditions_text'])
        self.assertNotIn('корпоративным',rows[1]['conditions_text'])
        self.assertNotIn('подарок',rows[0]['conditions_text'])
        self.assertIn('подарок',rows[1]['conditions_text'])
        for r in rows:
            self.assertFalse(r['details']['gated_catalogue_terms_recovered'])
            self.assertIn('личном кабинете',r['conditions_text'])
            self.assertNotIn('OUTSIDE_ONLY',json.dumps(r))
            self.assertEqual(r['promo_codes'],[])
            self.assertIsNone(r['valid_until']);validate_offer(r)

    def test_missing_rate_cannot_come_from_other_audience(self):
        with self.assertRaises(ValueError):extract(SID,page().replace('скидку 7%','привилегию'),URL,NOW)

    def test_multiple_rates_fail_instead_of_cross_offer_blending(self):
        with self.assertRaises(ValueError):extract(SID,page('7% или 9'),URL,NOW)

    def test_duplicate_missing_and_moved_panels_fail(self):
        for raw in (page().replace('services__text','other'),page().replace('Реферальная программа','Other'),
                    page().replace('</main>','<h2 class="about__title">Скидки</h2></main>')):
            with self.subTest(raw=raw),self.assertRaises(ValueError):extract(SID,raw,URL,NOW)

    def test_unexpected_terms_structure_cannot_be_silently_skipped(self):
        for extra in ('<div>Не действует по субботам.</div>', 'Не действует по субботам.'):
            raw=page().replace('</div></main>',extra+'</div></main>')
            with self.assertRaises(ValueError):extract(SID,raw,URL,NOW)

    def test_current_account_notice_is_required(self):
        with self.assertRaises(ValueError):extract(SID,page().replace('Условия могут меняться. Актуальная скидка в личном кабинете.',''),URL,NOW)

    def test_missing_material_restriction_is_not_assumed(self):
        with self.assertRaises(ValueError):extract(SID,page().replace('корпоративным','другим'),URL,NOW)

    def test_hidden_and_comment_rates_do_not_supply_values(self):
        raw=page().replace('При регистрации получаете скидку 7%',
                          '<span hidden>При регистрации скидка 7%</span><!-- скидка 7% -->При регистрации')
        with self.assertRaises(ValueError):extract(SID,raw,URL,NOW)

    def test_exact_url_rejects_other_program_and_tracking(self):
        for url in (URL+'?code=other',URL+'#other','https://sacvoyage.ru/partners/rzhd-bonus/'):
            with self.assertRaises(ValueError):extract(SID,page(),url,NOW)

    def test_source_dom_not_mutated(self):
        dom=BeautifulSoup(page(),'html.parser');before=str(dom)
        extract_partner_page(SID,dom,URL,NOW);self.assertEqual(str(dom),before)

    def test_registration_has_one_matching_source_and_is_not_rzd(self):
        routes=json.loads(Path(__file__).resolve().parents[1].joinpath('sources_normalized.json').read_text())
        selected=[r for r in routes if r['id']==SID]
        self.assertEqual(len(selected),1);self.assertEqual(selected[0]['url'],URL)
        self.assertEqual(CONFIG[SID]['url'],URL)
        self.assertNotIn('РЖД',CONFIG[SID]['program'])

if __name__=='__main__':unittest.main()
