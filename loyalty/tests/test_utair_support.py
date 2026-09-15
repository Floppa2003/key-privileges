"""Synthetic changed-input tests; no claims about today's source values."""
import copy
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from utair_support import article_blocks,parse_article,ROOT
from normalized import validate_offer,content_hash
from sheets_normalized import prepare

NOW='2026-09-15T11:00:00+00:00'
def leaf(name,body):
    return f'<div class="accordion-tab"><strong><label class="tab-label">{name}</label></strong><div class="tab-content"><p>{body}</p></div></div>'
def fixture(name='Новый партнер',rate=17,extra='',group='Копить мили'):
    return '<h1>Партнеры программы Utair Status</h1><div class="SupportWidgets_content__changed"><div class="accordion-tab"><label class="tab-label">'+group+'</label><div class="tab-content">'+leaf(name,f'<a href="https://partner.example/new?utm_source=a">{name}</a> — до {rate}% милями от стоимости бронирования.')+extra+'</div></div></div>'

class SupportTests(unittest.TestCase):
    def test_new_name_and_rate_are_from_current_leaf(self):
        rows=parse_article(fixture(),NOW)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['partner_name'],'Новый партнер')
        self.assertEqual(rows[0]['rates'][0]['value'],'17');self.assertEqual(rows[0]['rates'][0]['kind'],'miles')
    def test_changed_rate_stable_id_changed_hash(self):
        a=parse_article(fixture(rate=17),NOW)[0];b=parse_article(fixture(rate=23),NOW)[0]
        self.assertEqual(a['id'],b['id']);self.assertNotEqual(a['content_sha256'],b['content_sha256'])
        self.assertEqual(b['rates'][0]['value'],'23')
    def test_changed_membership_and_order_do_not_pair_neighbors(self):
        extra=leaf('Другой партнер','Кешбэк 9% на следующие поездки.')
        rows=parse_article(fixture(extra=extra),NOW)
        self.assertEqual([r['partner_name'] for r in rows],['Новый партнер','Другой партнер'])
        self.assertEqual([r['rates'][0]['value'] for r in rows],['17','9'])
    def test_program_rule_not_mislabelled_partner_discount(self):
        row=parse_article(fixture(group='Приобрести мили'),NOW)[0]
        self.assertEqual(row['record_kind'],'program_rules');self.assertIsNone(row['partner_name'])
        self.assertEqual(row['rates'],[]);self.assertIn('17%',row['conditions_text'])
    def test_public_link_not_certified_as_fetched_detail(self):
        row=parse_article(fixture(),NOW)[0]
        self.assertIsNone(row['benefit_url']);self.assertFalse(row['details']['linked_terms_checked'])
        self.assertEqual(row['details']['public_article_block']['links'][0]['url'],'https://partner.example/new')
    def test_secret_like_link_not_published(self):
        row=parse_article(fixture().replace('utm_source=a','access_token=private'),NOW)[0]
        self.assertEqual(row['details']['public_article_block']['links'],[])
        self.assertEqual(row['details']['public_article_block']['rejected_links'],1)
        self.assertNotIn('private',json.dumps(row))
    def test_menu_footer_and_intro_are_not_partner_leaves(self):
        html=fixture()+leaf('Footer','Скидка 99%')
        self.assertEqual(len(parse_article(html,NOW)),1)
    def test_shell_refusal_and_foreign_heading_fail(self):
        for html in ('<title>Access denied</title>','<h1>Партнеры</h1>',fixture().replace('Utair Status','Other')):
            with self.subTest(html=html[:30]),self.assertRaises(ValueError):parse_article(html,NOW)
    def test_empty_and_duplicate_leaf_fail(self):
        for html in (fixture(extra=leaf('Новый партнер','Другой текст')),fixture().replace('tab-content','other-content')):
            with self.assertRaises(ValueError):parse_article(html,NOW)
    def test_publisher_rejects_scope_promotion_even_with_rehashed_row(self):
        row=parse_article(fixture(),NOW)[0];row['details']['linked_terms_checked']=True;row['content_sha256']=content_hash(row)
        with self.assertRaises(ValueError):validate_offer(row)
    def test_publisher_rejects_text_from_neighbor_with_rehashed_row(self):
        row=parse_article(fixture(),NOW)[0];row['conditions_text']='Условия другой карточки';row['content_sha256']=content_hash(row)
        with self.assertRaises(ValueError):validate_offer(row)
    def test_output_passes_existing_publisher(self):
        rows=parse_article(fixture(),NOW)
        report={'source_id':'utair','name':'Utair','root':ROOT,'status':'ok','discovered':1,'normalized':1,'failed':0,'coverage':'one_article','region':None,'errors':[],'observed_at':NOW}
        result=prepare({'schema_version':2,'run_id':'synthetic','observed_at':NOW,'records':rows,'sources':[report]})
        self.assertEqual(len(result['parser_offers']),1);self.assertEqual(len(result['parser_coverage']),1)
    def test_unreadable_leaf_never_reuses_prior_values(self):
        parse_article(fixture(),NOW)
        with self.assertRaises(ValueError):parse_article('<h1>Utair Status</h1>',NOW)
    def test_no_fixed_partner_count(self):
        for n in (1,3,8):
            rows=parse_article(fixture(extra=''.join(leaf('Partner '+str(i),f'Кешбэк {i+1}%') for i in range(n-1))),NOW)
            self.assertEqual(len(rows),n)
    def test_percent_miles_plural_is_not_cash_discount(self):
        html=fixture().replace('до 17% милями','11% миль')
        row=parse_article(html,NOW)[0]
        self.assertEqual([(r['kind'],r['value']) for r in row['rates']],[('miles','11')])

if __name__=='__main__':unittest.main()
