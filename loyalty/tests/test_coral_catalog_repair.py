"""Changed-input checks for the actual failures seen in the first live crawl."""
import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).parents[1]))
import coral_catalog as c
import free_catalog_bundle as bundle
from free_access_probe import sanitized_page
from normalized import validate_offer, content_hash
from test_coral_catalog import doc, NOW, product, HAS_PROTEGO


def ticket(title='Новая экскурсия', price='4321', months='7'):
    return doc('<section><div class="col-lg"><h1>'+title+'</h1><p>Оплачивайте бонусами до 90% стоимости экскурсии. Это расход бонусов, не денежная скидка.</p><p>Стоимость '+price+' руб. Срок действия сертификата '+months+' месяцев с даты приобретения.</p><p>Как воспользоваться предложением:</p><ul><li>Ознакомьтесь с условиями.</li></ul><ul><li>Запишитесь заранее.</li></ul><div class="order-autorize"><h3>Чтобы купить билеты нужно авторизоваться на сайте</h3></div><div class="order-canvas"><h2>Заполните форму ниже для покупки билетов</h2><p>{{main.user.bonus_available}} PRIVATE PLACEHOLDER</p><button>Оплатить билеты</button></div></div></section>', c.CLUB+'trips/future/')


def category():
    return doc('<section><h1>Для детей</h1><div id="categoryProductsList"><div class="product-box referal"><a href="'+c.CLUB+'fun/new/">Карточка</a></div></div></section>',c.CLUB+'kids/')


class DiscoveredCategoryTests(unittest.TestCase):
    def test_cross_category_card_requires_current_root_category_identity(self):
        entry={'url':c.CLUB+'kids/','title':'Для детей'}
        known={c.CLUB+'kids/':'Для детей',c.CLUB+'fun/':'Развлечения'}
        rows,n=c.category_cards(category(),entry,known)
        self.assertEqual(n,0); self.assertEqual(rows[0]['category'],'Развлечения')
        self.assertEqual(rows[0]['parent_url'],entry['url'])
        with self.assertRaises(ValueError):c.category_cards(category(),entry,{entry['url']:entry['title']})
        with self.assertRaises(ValueError):c.category_cards(category().replace('coralbonus.ru/klub-privilegii/fun','foreign.example/klub-privilegii/fun'),entry,known)

    def test_changed_category_slug_and_label_not_old_inventory(self):
        entry={'url':c.CLUB+'kids/','title':'Для детей'}
        rows,_=c.category_cards(category().replace('/fun/','/fresh/'),entry,{entry['url']:entry['title'],c.CLUB+'fresh/':'Новая категория'})
        self.assertEqual(rows[0]['category'],'Новая категория')
        self.assertIn('/fresh/new/',rows[0]['url'])


class PublicTicketTests(unittest.TestCase):
    def read(self,raw=None):
        url=c.CLUB+'trips/future/'
        clean,_=sanitized_page(raw or ticket(),url)
        return c.detail(clean,'coral',{'url':url,'category':'Прогулки','parent_url':c.CLUB+'trips/'},NOW,{})

    def test_public_ticket_terms_without_payment_controls(self):
        row=self.read()
        self.assertEqual(row['source_status'],'public_conditions_purchase_requires_login')
        self.assertEqual(row['details']['redemption_mode'],'ticket_purchase')
        self.assertIn('4321',row['conditions_text']);self.assertIn('7 месяцев',row['conditions_text'])
        self.assertIn('Запишитесь заранее',row['redemption_text'])
        self.assertNotIn('PRIVATE',row['conditions_text']);self.assertNotIn('{{',row['conditions_text'])
        self.assertNotIn('Оплатить билеты',row['conditions_text'])
        self.assertFalse(row['details']['private_coupon_issued']);self.assertIsNone(row['valid_until'])
        self.assertEqual(row['promo_codes'],[])
        validate_offer(row)

    def test_ticket_changes_are_parsed_not_hardcoded(self):
        a=self.read();b=self.read(ticket('Другая прогулка','9999','13'))
        self.assertEqual(a['id'],b['id']);self.assertNotEqual(a['content_sha256'],b['content_sha256'])
        self.assertIn('9999',b['conditions_text']);self.assertIn('13 месяцев',b['conditions_text'])

    def test_unrelated_order_form_is_not_a_supported_ticket(self):
        for raw in (ticket().replace('Чтобы купить билеты','Чтобы оформить кредит'),ticket().replace('order-canvas','other'),ticket().replace('class="col-lg"','class="other"')):
            with self.assertRaises(ValueError):self.read(raw)

    def test_purchase_status_cannot_be_promoted_to_free_coupon(self):
        row=self.read();row['source_status']='public_conditions_coupon_requires_login';row['content_sha256']=content_hash(row)
        with self.assertRaises(ValueError):validate_offer(row)


class GlobalStopTests(unittest.TestCase):
    def test_root_stop_preserves_good_bundle_without_new_provider_preflight(self):
        record={'id':'saved-by-fixture'}
        report={'status':'stopped','free_plan_confirmed':True,'started_at':NOW}
        result={'records':[record], 'sources':[], 'observed_at':NOW}
        with tempfile.TemporaryDirectory() as temp:
            inp=Path(temp)/'input';inp.mkdir();out=Path(temp)/'output'
            with patch.object(sys,'argv',['free_catalog_bundle.py','--collect','--input',str(inp),'--out',str(out)]),patch.object(bundle,'run',return_value=report),patch.object(bundle,'configured_roots',return_value=[]),patch.object(bundle,'build',return_value=copy.deepcopy(result)),patch.object(c,'collect',side_effect=AssertionError('must not start another reader')),patch.dict(os.environ,{'GITHUB_OUTPUT':str(Path(temp)/'output-status')}):
                bundle.main()
            actual=json.loads((out/'normalized.json').read_text())
            self.assertEqual(actual['records'],[record])

    def test_healthy_root_flow_still_dispatches_coral(self):
        report={'status':'checked','free_plan_confirmed':True,'started_at':NOW}
        result={'records':[{'id':'prior'}], 'sources':[], 'observed_at':NOW}
        with tempfile.TemporaryDirectory() as temp:
            inp=Path(temp)/'input';inp.mkdir();out=Path(temp)/'output'
            with patch.object(sys,'argv',['free_catalog_bundle.py','--collect','--input',str(inp),'--out',str(out)]),patch.object(bundle,'run',return_value=report),patch.object(bundle,'configured_roots',return_value=[]),patch.object(bundle,'build',return_value=copy.deepcopy(result)),patch.object(bundle,'prepare'),patch.object(c,'collect',return_value={}) as collect,patch.dict(os.environ,{'GITHUB_OUTPUT':str(Path(temp)/'output-status')}):
                bundle.main();collect.assert_called_once()


if __name__ == '__main__':unittest.main()


@unittest.skipUnless(HAS_PROTEGO, 'Production dependency required in Actions')
class DuplicateTraversalTests(unittest.TestCase):
    def test_discovered_cross_category_card_is_fetched_once(self):
        import hashlib
        roots = c.CLUB
        titles = {roots+x+'/': x.upper() for x in ('aa','bb','cc','dd')}
        raw = doc('<h1>Клуб привилегий</h1>'+''.join('<div class="category-box-menu"><h5><a href="'+url+'">'+title+'</a></h5></div>' for url,title in titles.items()), roots)
        target=roots+'bb/future/'
        detail=product().replace(c.CLUB+'gifts/future/', target)
        reads=[]
        class Reader:
            def __init__(self,*a,**kw):
                self.allowed=set();self.reserved=0;self.calls=0;self.known_charged_credits=0;self.halted=False
            def preflight(self):pass
            def read(self,url,*,browser):
                reads.append((url,browser));self.calls+=1;self.reserved+=10 if browser else 1
                if url.endswith('/robots.txt'):return 200,'User-agent: *\nAllow: /',1
                if url==target:return 200,detail,1
                if url in titles:
                    body='<section><h1>'+titles[url]+'</h1><div id="categoryProductsList"><div class="product-box referal"><a href="'+target+'">x</a></div></div></section>'
                    return 200,doc(body,url),10
                raise AssertionError('Unconfigured request')
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp,'coral.html').write_text(raw)
            report={'sources':[{'source_id':'coral','status':'candidate_requires_review','origin_http_status':200,'final_url':roots,'sanitized_dom_sha256':hashlib.sha256(raw.encode()).hexdigest()}],'run_id':'fixture','commit':'fixture'}
            with patch.object(c,'FreeReader',Reader):result=c.collect(report,tmp,'fixture',NOW,sleep=lambda _:None)
            self.assertEqual(len(result['coral']['records']),1)
            self.assertEqual(result['coral']['meta']['duplicate_detail_links'],1)
            self.assertEqual(result['coral']['meta']['discovered_details'],1)
            self.assertEqual(reads.count((target,False)),1)
