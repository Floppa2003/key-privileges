"""Observed public markup with negative canaries outside the target card."""
import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from adapters import extract
from normalized import normalize_rates,validate_offer
NOW='2026-09-12T18:00:00+00:00'

class ExpansionTests(unittest.TestCase):
    def rows(self,source,raw,url):
        try: return extract(source,raw,url,NOW)
        except ValueError as e:self.fail('Source-specific extraction unavailable: '+str(e))

    def test_percent_paid_in_miles_is_not_cash_discount(self):
        rates=normalize_rates('Скидка 10%; до 13% милями от стоимости брони')
        self.assertEqual([(r['kind'],r['value'],r['unit'],r['qualifier']) for r in rates],
                         [('discount','10','percent','exact'),('miles','13','percent','up_to')])

    def test_mileage_denominator_survives_accrual_verb(self):
        rates=normalize_rates('1 миля начисляется за каждые потраченные 60 рублей')
        self.assertEqual([(r['value'],r['basis_amount'],r['basis_unit']) for r in rates],[('1','60','RUB')])

    def test_reversed_mileage_phrase_keeps_spending_denominator(self):
        rates=normalize_rates('За каждые потраченные 60 руб начисляется 1 миля')
        self.assertEqual([(r['value'],r['basis_amount'],r['basis_unit']) for r in rates],[('1','60','RUB')])

    def test_redemption_percentage_is_not_earned_miles(self):
        self.assertEqual(normalize_rates('Использовать мили можно на половину стоимости услуги (50%)'),[])

    def test_utair_partner_rate_and_name_use_the_same_link(self):
        raw='''<div id="rec774882292" class="t-rec uc-showmore3">
        <div class="tn-atom"><a href="https://utair.tvil.ru/">13% милями за бронирование для всех уровней Status</a></div>
        <div class="tn-atom"><a href="https://otello.2gis.ru/d/utair">15% милями от стоимости бронирования для уровней Bronze, Silver, Gold и Platinum. Для уровня Start и Basic — 13% милями</a></div>
        <div class="tn-atom"><a href="https://msk.gruzovichkof.ru/">Реклама. ООО «АйВэй Трансфер».</a></div>
        </div><a href="https://evil.example/">Скидка 99%</a>'''
        rows=self.rows('utair_media',raw,'https://media.utair.ru/status')
        by={r['partner_name']:r for r in rows}
        self.assertEqual(set(by),{'ТВИЛ.РУ','Otello'})
        self.assertEqual(by['ТВИЛ.РУ']['rates'][0]['value'],'13')
        self.assertNotIn('99',by['Otello']['benefit_text'])
        self.assertEqual(by['Otello']['details']['tier_rates'][0]['tiers'],['Bronze','Silver','Gold','Platinum'])
        self.assertEqual(by['Otello']['details']['tier_rates'][1]['tiers'],['Start','Basic'])
        for r in rows:validate_offer(r)

    def test_museum_external_partners_do_not_inherit_museum_program_discount(self):
        raw='''<div class="product-card__heading"><h3>Друг музея</h3><div class="h4">5 000 ₽</div></div>
        <div class="museum-friend"><div class="museum-friend-adv">Скидка 10% на программы музея</div><div class="museum-friend-adv">Скидка 10% в кафе и магазине «Подписные в музее»</div><div class="museum-friend-adv">Скидка 10% в кафе «Бейджанс», кондитерской «На Большевике» и у партнеров программы</div></div>
        <div class="product-card__heading"><h3>Друзья музея</h3><div class="h4">7 500 ₽</div></div>
        <div class="museum-friend"><div class="museum-friend-adv">Скидка 15% на программы музея</div><div class="museum-friend-adv">Скидка 10% в кафе и магазине «Подписные в музее»</div><div class="museum-friend-adv">Скидка 10% в кафе «Бейджанс», кондитерской «На Большевике» и у партнеров программы</div></div>'''
        rows=self.rows('rusimp',raw,'https://www.rusimp.su/membership/friends')
        external=[r for r in rows if r['record_kind']=='partner_offer']
        self.assertEqual({r['partner_name'] for r in external},{'Подписные в музее','Бейджанс','На Большевике'})
        self.assertEqual(len(rows),5)
        for r in external:
            self.assertEqual([x['value'] for x in r['rates']],['10'])
            self.assertEqual(r['details']['eligible_plans'],['Друг музея','Друзья музея'])

    def test_partner_article_excludes_adjacent_promotions(self):
        raw='''<section class="rzhd"><h1>РЖД Бонус</h1><h2>Скидка 15%</h2><span>от любого «Базового» тарифа</span><p>Отель «Дипломат». Невозвратный тариф, предоплата первых суток</p></section><section class="offers-other">РЖД Бонус: скидка 99% по соседней акции</section>'''
        r=self.rows('rzd_diplomat',raw,'https://diplomat-hotel.spb.ru/predlozhenija/rzhd-bonus/')[0]
        self.assertNotIn('99%',r['conditions_text'])
        self.assertIn('Невозвратный',r['conditions_text'])
        self.assertEqual(r['rates'][0]['value'],'15')

    def test_medsi_explicit_interval_is_typed(self):
        raw='''<section class="med-actions-promo-detail__content"><h2>Аэрофлот Бонус в МЕДСИ</h2><div class="med-middle__container"><h2>Условия акции:</h2><p>Предложение действует с 01.09.2026 по 30.09.2026</p><p>1 миля начисляется за каждые 60 ₽</p><p>Мили не начисляются при оплате стационарных услуг</p></div></section>'''
        r=self.rows('af_medsi',raw,'https://medsi.ru/actions/aeroflot-bonus-v-klinikakh-medsi/')[0]
        self.assertEqual((r['valid_from'],r['valid_until']),('2026-09-01','2026-09-30'))
        self.assertEqual(r['validity_status'],'within_published_period')
        self.assertIn('стационарных',r['conditions_text'])

    def test_wrong_program_page_is_rejected(self):
        with self.assertRaises(ValueError):
            extract('af_medsi','<section class="med-actions-promo-detail__content">Другая программа: скидка 30%</section>','https://medsi.ru/actions/aeroflot-bonus-v-klinikakh-medsi/',NOW)

    def test_askona_lapsed_multiplier_is_separate_from_base_offer(self):
        raw='''<div id="popup-rules">Правила Аэрофлот Бонус: Участники могут начислять 1 милю за каждые 100 рублей в Askona. В период с 01.08.2026 по 31.08.2026 за каждые потраченные 100 рублей начисляется 2 мили в Askona и Askona Home. Мили не начисляются за покупки в интернет-магазине.</div>'''
        rows=self.rows('af_askona',raw,'https://www.askona.ru/landing/aeroflot/')
        self.assertEqual(len(rows),2)
        base=next(r for r in rows if r['record_kind']=='partner_offer')
        promo=next(r for r in rows if r['record_kind']=='campaign')
        self.assertEqual(base['rates'][0]['value'],'1')
        self.assertEqual(promo['validity_status'],'expired_by_published_end')
        self.assertIn('интернет-магазине',promo['conditions_text'])

    def test_rostelecom_new_and_existing_are_separate_and_article_date_is_not_expiry(self):
        raw='''<section class="content_section"><h1>Ростелеком — Единая карта петербуржца</h1><div class="news-detail"><span class="newsdata">16.12.2025</span><p>В рамках партнерства новые клиенты могут подключить услугу «Домашний интернет» всего за 1 рубль и получить скидку 20% на абонентскую плату, которая будет действовать на протяжении всего срока пользования. Для действующих абонентов «Ростелекома», являющихся держателями ЕКП, предусмотрена скидка 10% на услугу «Домашний интернет» или пакет «Интернет + ТВ». Подробная информация о программе лояльности доступна в карточке партнера.</p></div></section>'''
        rows=self.rows('ekp_rostelecom',raw,'https://www.company.rt.ru/press/news_fill/d476187/')
        self.assertEqual(len(rows),2)
        self.assertEqual({r['details']['audience'] for r in rows},{'new_customers','existing_customers'})
        self.assertTrue(all(r['valid_until'] is None for r in rows))
        self.assertTrue(all(r['details']['article_published_at']=='2025-12-16' for r in rows))
        existing=next(r for r in rows if r['details']['audience']=='existing_customers')
        self.assertNotIn('всего срока',existing['benefit_text'])


    def test_inline_price_markup_does_not_break_mileage_basis(self):
        raw='''<article><div class="entry-content">Шефмаркет — партнер Аэрофлот Бонус.<p>За каждые потраченные <strong>60 руб</strong> начисляется <strong>1 миля</strong>.</p></div></article>'''
        r=self.rows('af_chefmarket',raw,'https://www.chefmarket.ru/blog/letat-i-gotovit-eshhe-vygodnee/')[0]
        self.assertEqual(r['rates'][0]['basis_amount'],'60')

    def test_future_period_and_source_typo_are_not_corrected_away(self):
        raw='''<div id="rec580842861"><h1>Что такое «Аэрофлот Бонус»</h1></div><div id="rec580842863">Условия начислений: 1 милz за 100 рублей</div><div id="rec925972101">Использование миль Аэрофлот Бонус.</div><div id="rec580842866">Условия начисления и использования миль. За каждые потраченные 100 рублей начисляется 1 милz. Срок проведения акции с 1 по 31 декабря 2026 года.</div>'''
        r=self.rows('af_grether',raw,'https://gretherwells.ru/aeroflot-bonus')[0]
        self.assertEqual(r['validity_status'],'not_started')
        self.assertEqual(r['valid_from'],'2026-12-01')
        self.assertIn('милz',r['conditions_text'])
        self.assertEqual(r['rates'],[])

if __name__=='__main__':unittest.main()
