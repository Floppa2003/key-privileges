"""General source-layout repair, no fixed lounge prices, partner IDs or dates."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
import coral_catalog as c
from normalized import validate_offer, content_hash
from test_coral_catalog import doc, NOW
URL=c.CLUB+'travel/new-purchase/'


def purchase(price='4567', end='31.12.2026'):
    return doc('<section><div class="col-lg"><h1>Услуга нового партнёра</h1><p>Оплачивайте бонусами до 93% стоимости посещения. Стоимость '+price+' руб.</p><p>Как воспользоваться предложением:</p><ul><li>Отправить заявку заранее.</li></ul><p>Срок действия предложения до '+end+'</p><div class="order-autorize"><h3>Чтобы совершить покупку нужно авторизоваться на сайте</h3><button>PRIVATE LOGIN CONTROL</button></div></div><div class="modal"><input value="PRIVATE"/></div></section>', URL)


def editorial():
    return doc('<section><div class="order-lg-2"><h1>Новый подарочный продукт</h1><div><h1>Подробное описание</h1><p>Купите электронный сертификат для друга, выбрав номинал. Это описание платного продукта, а не отдельная скидка.</p><h1>Как пользоваться</h1><p>Сертификат действует 9 месяцев с даты приобретения.</p></div></div><div class="product-purchase-box referal"><a href="https://example.test/">Купить</a></div></section>',URL)


class PurchaseLayoutTests(unittest.TestCase):
    def read(self,raw):
        return c.detail(raw,'coral',{'url':URL,'category':'Услуги','parent_url':c.CLUB+'travel/'},NOW,{'method':'fixture'})

    def test_public_request_terms_are_not_free_coupon(self):
        r=self.read(purchase());validate_offer(r)
        self.assertEqual(r['source_status'],'public_conditions_purchase_requires_login')
        self.assertEqual(r['details']['redemption_mode'],'purchase_request')
        self.assertIn('4567',r['conditions_text']);self.assertIn('93%',r['conditions_text'])
        self.assertEqual(r['rates'],[]);self.assertEqual(r['promo_codes'],[])
        self.assertNotIn('PRIVATE',r['conditions_text']);self.assertIn('Отправить заявку',r['redemption_text'])
        self.assertEqual(r['valid_until'],'2026-12-31')

    def test_changed_price_and_end_are_source_data(self):
        a=self.read(purchase());b=self.read(purchase('9876','30.06.2027'))
        self.assertEqual(a['id'],b['id']);self.assertNotEqual(a['content_sha256'],b['content_sha256'])
        self.assertIn('9876',b['conditions_text']);self.assertEqual(b['valid_until'],'2027-06-30')

    def test_other_account_form_or_external_heading_is_rejected(self):
        for raw in (purchase().replace('Чтобы совершить покупку','Чтобы оформить кредит'),purchase().replace('class="col-lg"','class="unrelated"'),editorial()+'<h1>Чужая карточка</h1>'):
            with self.subTest(raw=raw[:50]),self.assertRaises(ValueError):self.read(raw)

    def test_nested_editorial_is_evidence_not_discount(self):
        r=self.read(editorial());validate_offer(r)
        self.assertEqual(r['record_kind'],'source_observation')
        self.assertTrue(r['details']['public_editorial_information'])
        self.assertIn('9 месяцев',r['conditions_text']);self.assertIsNone(r['valid_until'])
        self.assertEqual(r['rates'],[])

    def test_rehashed_purchase_and_editorial_relabelling_rejected(self):
        for r,field,value in ((self.read(purchase()),'source_status','public_source_terms'),(self.read(editorial()),'record_kind','partner_offer')):
            r[field]=value;r['content_sha256']=content_hash(r)
            with self.assertRaises(ValueError):validate_offer(r)


if __name__=='__main__':unittest.main()
