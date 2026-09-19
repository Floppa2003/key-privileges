"""Public source DOM replay, scope drift and negative canaries; no account access."""
import copy
import json
import sys
import unittest
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0, str(Path(__file__).parents[1]))
from normalized import content_hash, validate_offer
from tsum_alfa import SOURCE_ID, URL, QUESTIONS, extract_tsum
from announcements import parse_feed, checked_config
from adapters import extract

FIX = Path(__file__).parent / 'fixtures_live'
NOW = '2026-09-19T11:54:37+00:00'
CFG = {'id':'alfa_only_announcements', 'channel':'aaa_only', 'url':'https://t.me/s/aaa_only',
       'name':'Alfa Only — публичные объявления', 'lookback_days':180, 'max_pages':60}


def post(body, ident='aaa_only/9000', when='2026-09-17T09:00:00+00:00', forward=False):
    return (f'<div class="tgme_widget_message" data-post="{ident}">' +
            ('<a class="tgme_widget_message_forwarded_from">forward</a>' if forward else '') +
            f'<div class="tgme_widget_message_text">{body}</div>' +
            f'<a class="tgme_widget_message_date"><time datetime="{when}"></time></a></div>')


class TsumTests(unittest.TestCase):
    def setUp(self):
        self.html = (FIX / 'tsum-alfa.html').read_text()
        self.soup = BeautifulSoup(self.html, 'html.parser')

    def rows(self):
        return extract_tsum(SOURCE_ID, self.soup, URL, NOW, {})

    def test_actual_tiers_only_not_baseline_rates(self):
        rows = self.rows()
        self.assertEqual([(r['details']['tsum_tier'], r['rates'][0]['value']) for r in rows], [('Orange','8'), ('Black','20')])
        for r in rows:
            self.assertEqual(len(r['rates']), 1)
            self.assertIn('бонусами', r['benefit_text'])
            self.assertIn('loyalty_credit_not_bank_cash', ' '.join(r['warnings']))
            self.assertIsNone(r['valid_until'])
            self.assertIsNone(r['benefit_url'])

    def test_actual_conditions_and_activation_are_visible_fields(self):
        for r in self.rows():
            self.assertIn('Повышенный кешбэк в ЦУМе', r['redemption_text'])
            for marker in ('СБП', '5% по карте Orange', '10% по карте Black', 'партнёрской службы доставки',
                           'картами Аэрофлот, S7, Апельсин', '15-й день', '1 бонус = 1 рубль', 'Нет, начисляется только',
                           'брендов-исключений', 'А-Клуб', 'Кешбэк за возвращённые товары не начисляется'):
                self.assertIn(marker, r['conditions_text'])
            self.assertNotIn('2990', r['conditions_text'])

    def test_router_uses_the_same_parser(self):
        self.assertEqual(extract(SOURCE_ID, self.html, URL, NOW), self.rows())

    def test_tier_card_and_faq_disagreement_fails(self):
        n = self.soup.select('[class*="AlfaOnly__bounsWrapper___"]')[1]
        n.find(string='8%').replace_with('9%')
        with self.assertRaisesRegex(ValueError, 'disagreement'):
            self.rows()

    def test_consistent_rate_update_is_not_hardcoded_and_keeps_id(self):
        old = self.rows()[0]
        self.soup = BeautifulSoup(self.html.replace('8%', '9%'), 'html.parser')
        new = self.rows()[0]
        self.assertEqual(new['rates'][0]['value'], '9')
        self.assertEqual(old['id'], new['id'])
        self.assertNotEqual(old['content_sha256'], new['content_sha256'])

    def test_required_payment_exception_cannot_silently_disappear(self):
        n = next(n for n in self.soup.select('[data-test-id="accordionWrapper"]') if 'СБП или QR-кода' in n.get_text())
        n.decompose()
        with self.assertRaisesRegex(ValueError, 'required_question_missing'):
            self.rows()

    def test_duplicate_tier_and_question_fail(self):
        for selector in ('[class*="AlfaOnly__bounsWrapper___"]', '[data-test-id="accordionWrapper"]'):
            self.soup = BeautifulSoup(self.html, 'html.parser')
            n = self.soup.select_one(selector)
            n.insert_after(copy.copy(n))
            with self.assertRaises(ValueError):
                self.rows()

    def test_wrong_page_and_missing_redemption_fail(self):
        with self.assertRaises(ValueError):
            extract_tsum(SOURCE_ID, self.soup, URL + '?other=1', NOW, {})
        self.soup.select_one('[class*="AlfaOnly__privelegiesBlock___"]').decompose()
        with self.assertRaises(ValueError):
            self.rows()

    def test_rehash_cannot_hide_scope_or_field_tampering(self):
        base = self.rows()[0]
        for key, value in (('conditions_text',''), ('redemption_text',''), ('valid_until','2099-01-01'), ('partner_name','Wrong'), ('warnings',[])):
            r = copy.deepcopy(base); r[key] = value; r['content_sha256'] = content_hash(r)
            with self.assertRaises(ValueError):
                validate_offer(r)

    def test_unified_view_keeps_one_scoped_loyalty_benefit_and_all_conditions(self):
        from sheets_normalized import prepare, SCHEMAS
        from unified_normalization import make_input, normalize_record
        for r in self.rows():
            report={'source_id':SOURCE_ID,'name':'TSUM','root':URL,'status':'ok','normalized':1,'discovered':1,'failed':0,'coverage':'fixture','errors':[],'region':None,'observed_at':NOW}
            bundle={'schema_version':2,'run_id':'fixture:1','observed_at':NOW,'records':[r],'sources':[report]}
            values=prepare(bundle)['parser_offers'][0]
            raw=make_input({'id':r['id'],'origin':'parser_offers','row':2,'fields':{h:{'value':v} for h,v in zip(SCHEMAS['parser_offers'],values)}})
            n=normalize_record(raw,as_of='2026-09-19')
            self.assertEqual(len(n['benefits']),1)
            b=n['benefits'][0]
            self.assertEqual(b['kind'],'earn_points')
            self.assertEqual(b['reward_unit'],'TSUM_DLT_loyalty_credit')
            self.assertEqual(b['scope']['merchant_tier'],r['details']['tsum_tier'])
            self.assertEqual(b['value'],r['rates'][0]['value'])
            self.assertEqual(len(b['condition_ids']),2)
            self.assertIn('СБП',json.dumps(n['conditions'],ensure_ascii=False))
            self.assertIsNone(n['eligibility_verified'])

    def test_scripts_do_not_become_offer_evidence(self):
        self.soup.select_one('[class*="AlfaOnly__privelegiesBlock___"]').append(BeautifulSoup('<script>Secret 99% discount</script>', 'html.parser'))
        r = self.rows()[0]
        self.assertNotIn('Secret', r['redemption_text'])
        self.assertEqual(r['rates'][0]['value'], '8')


class AlfaAnnouncementTests(unittest.TestCase):
    def test_source_owned_simpleprive_caption_does_not_turn_market_return_into_discount(self):
        r = parse_feed((FIX / 'alfa-simpleprive-post.html').read_text(), CFG, NOW)
        self.assertEqual(r['errors'], [])
        self.assertEqual(len(r['records']), 1)
        row = r['records'][0]
        self.assertEqual([x['value'] for x in row['rates']], ['25','15','40'])
        self.assertIn('15,8%', row['benefit_text'])
        self.assertEqual(row['rates'][-1]['qualifier'], 'up_to')
        self.assertIsNone(row['partner_name'])
        self.assertEqual(row['source_status'], 'announced_unverified')

    def test_lottery_wheel_poll_and_plain_finance_are_not_perks(self):
        for body in ('Alfa Only: разыгрываем билеты и комплимент в баре.',
                     'Барабан привилегий Alfa Only: кешбэк до 100%.',
                     'Alfa Only: вклад под 20%.', 'Alfa Only: итоги опроса, 25%.',
                     'Alfa Only: шампанское подорожало на 15,8%.'):
            self.assertEqual(parse_feed(post(body), CFG, NOW)['records'], [])

    def test_compliment_without_percentage_is_preserved(self):
        rs = parse_feed(post('Клиентам Alfa Only — коктейль в качестве комплимента. Покажите карту.'), CFG, NOW)['records']
        self.assertEqual(len(rs), 1)
        self.assertEqual(rs[0]['rates'], [])

    def test_channel_and_forwarded_identity_remain_guarded(self):
        body = 'Alfa Only — скидка 10%.'
        self.assertEqual(parse_feed(post(body, ident='evil/90') + post(body, forward=True), CFG, NOW)['records'], [])
        with self.assertRaises(ValueError):
            checked_config({**CFG, 'channel':'other'})

    def test_date_and_cross_partner_scope_are_not_inferred(self):
        r = parse_feed(post('Alfa Only: скидка 10% в A и 20% в B до 10 августа.'), CFG, NOW)['records'][0]
        self.assertIsNone(r['partner_name'])
        self.assertIsNone(r['valid_until'])
        self.assertEqual(r['details']['validity_extraction'], 'not_inferred_from_publication_date')
        self.assertEqual(parse_feed(post('Alfa Only — скидка 10%.', when='2025-01-01T00:00:00+00:00'), CFG, NOW)['records'], [])

    def test_publication_kind_cannot_be_promoted_after_rehash(self):
        r = parse_feed(post('Alfa Only — скидка 10%.'), CFG, NOW)['records'][0]
        r.update(record_kind='partner_offer', source_status='published', link_kind='detail_page', benefit_url=r['source_url'])
        r['content_sha256'] = content_hash(r)
        with self.assertRaises(ValueError):
            validate_offer(r)

    def test_actual_sources_are_registered(self):
        entries = {x['id']:x for x in json.loads((Path(__file__).parents[1] / 'sources_normalized.json').read_text())}
        self.assertEqual(entries[SOURCE_ID]['url'], URL)
        self.assertEqual(entries[CFG['id']]['channel'], CFG['channel'])
