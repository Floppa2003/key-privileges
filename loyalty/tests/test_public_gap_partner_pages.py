"""Public partner terms supplement, never overwrite, gated EKP identities."""
import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters import extract
from normalized import validate_offer
from partner_pages import CONFIG
NOW='2026-09-18T12:00:00+00:00'


def artflora(rate=7,date='12.06.2023'):
    return f'''<html><body><article class="node-news"><header><span class="submitted">{date}</span></header>
    <div class="field-name-body"><div class="field-items"><div class="field-item">
    <p>АртФлора — партнёр программы Единая карта петербуржца.</p>
    <p>Держателям ЕКП скидка {rate}%.</p><p>Промокод доступен на портале ЕКП.</p>
    <ol><li>В пункте выдачи показать ЕКП или назвать промокод.</li><li>Интернет-заказ: ввести промокод в корзине.</li></ol>
    <p>Промокод многоразовый.</p><p>Нельзя списать или начислить балы по системе лояльности АртФлора.</p>
    </div></div></div><div id="comments">Скидка 81% по коду WRONGCOMMENT</div></article>
    <aside>Новым клиентам скидка 99% по промокоду WRONGNEIGHBOUR</aside></body></html>'''


def litres(rate=20,count=2):
    return f'''<html><body><h1 id="pageTitle">{count} книги из подборки в подарок и скидка {rate}% от ЕКП и Литрес</h1>
    <div class="Collection-module-scss-module__changed__description"><div>
    <p>На этой странице можно выбрать {count} книги в подарок.</p><p>Нажать кнопку «Взять себе».</p>
    <p>Скидка {rate}% на основной каталог (уже активирована).</p><p>На 1 покупку в течение 3-х дней с момента активации.</p>
    </div></div><div class="Collection-module-scss-module__changed__products">Скидка 91% по промокоду WRONGPRODUCT</div></body></html>'''


class PublicGapPartnerTests(unittest.TestCase):
    def row(self,sid,raw):
        rows=extract(sid,raw,CONFIG[sid]['url'],NOW)
        self.assertEqual(len(rows),1);validate_offer(rows[0]);return rows[0]

    def test_artflora_rate_is_from_own_claim_not_comments_or_recommendations(self):
        for rate in (7,13):
            r=self.row('ekp_artflora',artflora(rate))
            self.assertEqual([x['value'] for x in r['rates']],[str(rate)])
            self.assertNotIn('WRONG',r['conditions_text']);self.assertNotIn('99%',r['benefit_text'])
            self.assertEqual(r['promo_codes'],[])

    def test_artflora_keeps_both_redemption_paths_and_loyalty_incompatibility(self):
        r=self.row('ekp_artflora',artflora())
        self.assertIn('показать ЕКП',r['redemption_text'])
        self.assertIn('ввести промокод',r['redemption_text'])
        self.assertIn('многоразовый',r['conditions_text'])
        self.assertIn('Нельзя списать или начислить балы',r['conditions_text'])

    def test_old_publication_is_separate_from_unknown_offer_validity(self):
        r=self.row('ekp_artflora',artflora(date='04.05.2021'))
        self.assertEqual(r['details']['article_published_at'],'2021-05-04')
        self.assertTrue(r['details']['publication_date_is_not_validity'])
        self.assertIsNone(r['valid_from']);self.assertIsNone(r['valid_until'])
        self.assertEqual(r['validity_status'],'not_stated');self.assertEqual(r['observed_at'],NOW)
        with self.assertRaises(ValueError):self.row('ekp_artflora',artflora(date='unknown'))

    def test_litres_preserves_gift_and_relative_activation_restrictions(self):
        for rate,count in ((20,2),(17,3)):
            r=self.row('ekp_litres',litres(rate,count))
            self.assertEqual([x['value'] for x in r['rates']],[str(rate)])
            self.assertIn(f'{count} книги',r['benefit_text'])
            self.assertIn('1 покупку',r['redemption_text']);self.assertIn('3-х дней',r['conditions_text'])
            self.assertIn('public_landing_copy_is_not_user_account_activation',r['warnings'])
            self.assertIsNone(r['valid_until']);self.assertEqual(r['promo_codes'],[])
            self.assertNotIn('WRONGPRODUCT',json.dumps(r,ensure_ascii=False))

    def test_missing_or_foreign_campaign_boundaries_fail_instead_of_using_whole_page(self):
        for sid,raw in [('ekp_artflora',artflora().replace('field-name-body','unrelated')),
                        ('ekp_litres',litres().replace('pageTitle','otherTitle')),
                        ('ekp_litres',litres().replace('ЕКП','ДРУГАЯ ПРОГРАММА'))]:
            with self.assertRaises(ValueError):extract(sid,raw,CONFIG[sid]['url'],NOW)
        with self.assertRaises(ValueError):extract('ekp_litres',litres(),CONFIG['ekp_litres']['url']+'elsewhere',NOW)

    def test_registered_for_existing_regular_html_collection_with_separate_ids(self):
        cfg=json.loads(Path(__file__).resolve().parents[1].joinpath('sources_normalized.json').read_text())
        for sid,raw in [('ekp_artflora',artflora()),('ekp_litres',litres())]:
            matches=[c for c in cfg if c['id']==sid]
            self.assertEqual(len(matches),1);self.assertEqual(matches[0]['mode'],'html')
            self.assertEqual(matches[0]['url'],CONFIG[sid]['url'])
            r=self.row(sid,raw);self.assertNotEqual(r['source_id'],'ekp')
            self.assertEqual(r['details']['source_scope'],'reviewed_partner_page_not_program_catalog')

if __name__=='__main__':unittest.main()
