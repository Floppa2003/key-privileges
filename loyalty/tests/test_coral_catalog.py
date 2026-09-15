import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).parents[1]))
import coral_catalog as c
from free_access_probe import FreeReader, ProbeError, sanitized_page
from normalized import validate_offer, content_hash
NOW = '2026-09-15T21:00:00+00:00'
URL = c.CLUB+'gifts/future/'


def doc(body, url=URL):
    return '<html data-loyalty-probe-location="'+url+'"><head><link rel="canonical" href="'+url+'"/><base href="https://coralbonus.ru/"/></head><body>'+body+'<footer>Скидка 99% соседнего сервиса</footer></body></html>'


def product(amount='17', end='31.08.2026'):
    return doc('<section><div class="order-lg-2"><h1>Скидка '+amount+'% в Новый сервис</h1><p>Условия действуют на первый заказ и не суммируются с соседней акцией.</p><p>Как воспользоваться предложением:</p><ul><li>Введите код при заказе.</li></ul><p>Срок действия предложения до '+end+'</p><p><a href="https://partner.example/">Сайт партнера</a></p></div><div class="product-purchase-box referal"><div class="order-autorize"><h3>Чтобы получить промо-код нужно авторизоваться на сайте</h3></div></div><div class="modal">PRIVATE PLACEHOLDER</div></section>')


def promo():
    url=c.PROMO+'future/'
    return doc('<section class="article"><h1>Бонусы нового путешествия</h1><p>Первая область</p><table><tr><th>Регион</th><th>Бонусы</th></tr><tr><td>Регион А</td><td>1234</td></tr></table><p>Даты поездки: 01.10.2026 — 31.12.2026. Даты заказа: 01.09.2026 — 30.09.2026.</p></section>',url)


def root(sid='coral'):
    title='Клуб привилегий' if sid=='coral' else 'Акции'
    cls='category-box-menu' if sid=='coral' else 'sale-item-description'
    base=c.CLUB if sid=='coral' else c.PROMO
    entries=[('one','Первая'),('two','Вторая')] if sid=='coral' else [('future','Бонусы нового путешествия')]
    return doc('<h1>'+title+'</h1>'+''.join('<div class="'+cls+'"><h5><a href="'+base+key+'/">'+name+'</a></h5></div>' for key,name in entries),base)


class CoralMappingTests(unittest.TestCase):
    def record(self, raw=None):
        clean,_=sanitized_page(raw or product(),URL)
        return c.detail(clean,'coral',{'url':URL,'category':'Подарки','parent_url':c.CLUB+'gifts/'},NOW,{'method':'fixture'})

    def test_own_conditions_expiry_and_auth_without_issuing_code(self):
        row=self.record()
        self.assertEqual(row['rates'][0]['value'],'17')
        self.assertEqual(row['valid_until'],'2026-08-31')
        self.assertEqual(row['validity_status'],'expired_by_published_end')
        self.assertIn('авторизоваться',row['redemption_text'])
        self.assertNotIn('99%',row['conditions_text'])
        self.assertNotIn('PRIVATE',row['conditions_text'])
        self.assertEqual(row['promo_codes'],[])
        self.assertIsNone(row['partner_name'])
        self.assertFalse(row['details']['private_coupon_issued'])

    def test_changed_amount_date_title_preserves_identity_not_value(self):
        a=self.record();b=self.record(product('23','31.12.2026'))
        self.assertEqual(a['id'],b['id'])
        self.assertNotEqual(a['content_sha256'],b['content_sha256'])
        self.assertEqual(b['rates'][0]['value'],'23')
        self.assertEqual(b['validity_status'],'within_published_period')

    def test_unknown_or_conflicting_date_is_not_copied(self):
        self.assertIsNone(c.explicit_end('Дата тура до 31.12.2026'))
        self.assertIsNone(c.explicit_end('Срок действия предложения до 01.01.2026; Срок действия предложения до 01.02.2026'))

    def test_promotion_tables_and_date_roles_preserved(self):
        raw,_=sanitized_page(promo(),c.PROMO+'future/')
        row=c.detail(raw,'coral_promo',{'url':c.PROMO+'future/','title':'Бонусы нового путешествия'},NOW,{})
        self.assertEqual(row['tables'][0][1],['Регион А','1234'])
        self.assertEqual(row['details']['public_coral_block']['table_contexts'],['Первая область'])
        self.assertIn('Даты заказа',row['conditions_text'])
        self.assertIsNone(row['valid_until'])

    def test_source_identity_not_guessed_from_headline(self):
        for raw in (product().replace('product-purchase-box referal','product-purchase-box base'),product().replace('order-lg-2','other')):
            with self.assertRaises(ValueError):self.record(raw)
        with self.assertRaises(ValueError):c.detail(promo(),'coral_promo',{'url':c.PROMO+'future/','title':'Different'},NOW,{})

    def test_rehashed_evidence_mutations_rejected(self):
        a=self.record()
        for field,value in [('benefit_text','Скидка 90%'),('conditions_text','none'),('partner_name','Invented'),('valid_until','2028-01-01'),('category','Other')]:
            b=copy.deepcopy(a);b[field]=value;b['content_sha256']=content_hash(b)
            with self.subTest(field=field),self.assertRaises(ValueError):validate_offer(b)

    def test_same_canonical_http_is_explicitly_not_browser_location(self):
        clean,meta=sanitized_page(product().replace('data-loyalty-probe-location','unused'),URL,canonical_identity=True)
        self.assertIsNone(meta['final_url']);self.assertEqual(meta['canonical_url'],URL)
        self.assertNotIn('unused',clean)
        for raw in (product().replace('rel="canonical"','rel="other"'),product().replace('href="'+URL+'"','href="https://foreign.example/"'),product().replace('</head>','<link rel="canonical" href="'+URL+'"/></head>')):
            with self.assertRaises(ProbeError):sanitized_page(raw,URL,canonical_identity=True)

    def test_index_discovery_changed_membership_and_foreign_urls(self):
        self.assertEqual(len(c.listing(root(),'coral')),2)
        self.assertEqual(c.listing(root('coral_promo'),'coral_promo')[0]['url'],c.PROMO+'future/')
        with self.assertRaises(ValueError):c.listing(root().replace(c.CLUB+'one/','https://foreign.example/one/'),'coral')
        with self.assertRaises(ValueError):c.listing(root()+'<div class="pagination"><a href="/page2">2</a></div>','coral')

    def test_rendered_category_owner_and_non_referral_exclusion(self):
        entry={'url':c.CLUB+'gifts/','title':'Подарки'}
        raw=doc('<section class="ng-scope"><h1>Подарки</h1><div id="categoryProductsList"><div class="product-box referal"><a href="'+URL+'">x</a><a href="'+URL+'">x</a></div><div class="product-box base">Merchandise</div></div></section>',entry['url'])
        rows,excluded=c.category_cards(raw,entry)
        self.assertEqual(len(rows),1);self.assertEqual(excluded,1)
        with self.assertRaises(ValueError):c.category_cards(raw.replace(URL,c.CLUB+'foreign/item/'),entry)
        with self.assertRaises(ValueError):c.category_cards(raw.replace('Merchandise','{{vm.loading}}'),entry)

    def test_separate_reader_bounds_retain_default_limits(self):
        a=FreeReader('fixture',[{'url':c.CLUB}]);b=FreeReader('fixture',[{'url':c.CLUB}],max_credits=175,max_requests=100)
        self.assertEqual((a.max_credits,a.max_requests),(115,16))
        self.assertEqual((b.max_credits,b.max_requests),(175,100))
        for limit in (176,0,True):
            with self.assertRaises(ProbeError):FreeReader('fixture',[{'url':c.CLUB}],max_credits=limit)


try:
    import protego
    HAS_PROTEGO=True
except ImportError:
    HAS_PROTEGO=False


@unittest.skipUnless(HAS_PROTEGO,'Production dependency unavailable locally; required in Actions')
class CoralCollectionTests(unittest.TestCase):
    def test_actual_traversal_preserves_successful_details_after_failure(self):
        roots={sid:root(sid) for sid in ('coral','coral_promo')}
        reads=[]
        class Reader:
            def __init__(self,*a,**kw):
                self.allowed=set();self.reserved=0;self.calls=0;self.known_charged_credits=0;self.halted=False
            def preflight(self):pass
            def read(self,url,*,browser):
                reads.append((url,browser));self.calls+=1;self.reserved+=10 if browser else 1
                if url.endswith('/robots.txt'):return 200,'User-agent: *\nAllow: /',1
                if url==c.PROMO+'future/':return 200,promo(),1
                raise ProbeError('provider_http_404')
        with tempfile.TemporaryDirectory() as tmp:
            observations=[]
            for sid,raw in roots.items():
                Path(tmp,sid+'.html').write_text(raw)
                observations.append({'source_id':sid,'status':'candidate_requires_review','origin_http_status':200,
                    'final_url':c.CLUB if sid=='coral' else c.PROMO,'sanitized_dom_sha256':hashlib.sha256(raw.encode()).hexdigest()})
            report={'sources':observations,'run_id':'fixture','commit':'fixture'}
            with patch.object(c,'FreeReader',Reader):out=c.collect(report,tmp,'fixture',NOW,sleep=lambda _:None)
            self.assertEqual(len(out['coral_promo']['records']),1)
            self.assertTrue(out['coral_promo']['meta']['all_observed_promo_details_read'])
            self.assertTrue(out['coral']['errors'])
            self.assertTrue(all(url.startswith('https://coralbonus.ru/') for url,_ in reads))
            self.assertFalse(any('лич' in url or 'coupon' in url for url,_ in reads))


if __name__=='__main__':unittest.main()
