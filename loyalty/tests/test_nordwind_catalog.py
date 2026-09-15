import copy
import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
from nordwind_catalog import ROOT, parse_catalog, article_blocks
from normalized import validate_offer, content_hash
from free_catalog_bundle import build
from free_access_probe import configured_roots, SOURCE_IDS
from sheets_normalized import prepare

NOW = '2026-09-15T19:41:00+00:00'
CLOCK = datetime.fromisoformat('2026-09-15T19:43:00+00:00')


def card(anchor='Future42', name='Новый отель', basis='200', miles='7'):
    return f'''<div class="collapse-snippet__item"><div class="collapse-snippet__title" id="{anchor}">{name}</div>
<div class="collapse-snippet__content"><b>Условия:</b><p>Только первое бронирование. Дополнительные услуги исключены.</p>
<b>Мили к начислению:</b><p>За каждые потраченные {basis} ₽ - {miles} миль NORDWIND КЛУБ.</p>
<b>Контакты:</b><p>Телефон 1234567</p><a href="https://hotel.example/book">Официальный сайт</a></div></div>'''


def document(cards=None):
    return '''<html><head><title>Партнёры</title></head><body><h2 class="page-promo__title">Партнеры программы лояльности NORDWIND КЛУБ</h2>
<div id="main_content"><h2 class="routes__title">Отели</h2><section class="collapse-snippet">'''+(cards or card())+'''</section></div><footer>Скидка 99%</footer></body></html>'''


def observation(raw):
    return {'source_id': 'nordwind', 'status': 'candidate_requires_review', 'origin_http_status': 200,
            'final_url': ROOT, 'finished_at': '2026-09-15T19:42:00+00:00',
            'sanitized_dom_sha256': hashlib.sha256(raw.encode()).hexdigest()}


def report(raw):
    return {'run_id': 'fixture-run', 'run_attempt': '2', 'commit': 'fixture-commit', 'started_at': NOW,
        'finished_at': '2026-09-15T19:42:30+00:00', 'mode': 'free_access_probe', 'account_sessions_used': False,
        'free_plan_confirmed': True, 'source_ids': list(SOURCE_IDS), 'sources': [observation(raw)]}


class NordwindCatalogTests(unittest.TestCase):
    def test_native_identity_rate_and_full_conditions(self):
        row = parse_catalog(document(), NOW)[0]
        self.assertEqual(row['native_id'], 'anchor:Future42')
        self.assertEqual(row['source_url'], ROOT+'#Future42')
        self.assertEqual(row['details']['earning_rules'][0]['basis_amount'], '200')
        self.assertEqual(row['details']['earning_rules'][0]['value'], '7')
        self.assertIn('Дополнительные услуги исключены', row['conditions_text'])
        self.assertNotIn('Телефон', row['benefit_text'])
        self.assertNotIn('99%', row['conditions_text'])
        self.assertIsNone(row['valid_until'])
        validate_offer(row)

    def test_changed_ids_names_values_and_card_count_change_output(self):
        first = parse_catalog(document(), NOW)[0]
        altered = parse_catalog(document(card('Changed', 'Другая компания', '50', '4')+card('Second', 'Вторая', '300', '2')), NOW)
        self.assertEqual(len(altered), 2)
        self.assertNotEqual(first['id'], altered[0]['id'])
        self.assertEqual(altered[0]['partner_name'], 'Другая компания')
        self.assertEqual(altered[1]['details']['earning_rules'][0]['basis_amount'], '300')
        self.assertNotIn('Другая компания', altered[1]['conditions_text'])

    def test_same_id_changed_conditions_keeps_id_changes_hash(self):
        a = parse_catalog(document(), NOW)[0]
        b = parse_catalog(document().replace('Дополнительные услуги исключены', 'Новые условия'), NOW)[0]
        self.assertEqual(a['id'], b['id']); self.assertNotEqual(a['content_sha256'], b['content_sha256'])

    def test_shell_wrong_identity_and_missing_sections_rejected(self):
        for raw in ('<title>Партнёры</title>', document().replace('NORDWIND', 'FOREIGN'),
                    document().replace('Мили к начислению:', 'Other:'), document().replace('id="Future42"', 'id=""')):
            with self.subTest(raw=raw[:50]), self.assertRaises(ValueError):
                parse_catalog(raw, NOW)

    def test_duplicate_and_nested_cards_rejected(self):
        for raw in (document(card()+card()), document(card().replace('</p>', '</p>'+card('Nested'), 1))):
            with self.assertRaises(ValueError): parse_catalog(raw, NOW)

    def test_unknown_earning_grammar_is_not_an_old_formula(self):
        raw = document().replace('За каждые потраченные 200 ₽ - 7 миль NORDWIND КЛУБ.', 'До 3 миль по индивидуальным условиям.')
        row = parse_catalog(raw, NOW)[0]
        self.assertEqual(row['details']['earning_rules'], [])
        self.assertIn('earning_formula_not_structurally_parsed', row['warnings'])
        self.assertIn('До 3 миль', row['benefit_text'])

    def test_rehashed_forged_partner_rate_scope_or_conditions_rejected(self):
        row = parse_catalog(document(), NOW)[0]
        for key, value in [('partner_name', 'Neighbor'), ('source_status', 'verified_eligible'),
                           ('conditions_text', 'Nothing'), ('category', 'wrong')]:
            altered = copy.deepcopy(row); altered[key] = value; altered['content_sha256'] = content_hash(altered)
            with self.subTest(key=key), self.assertRaises(ValueError): validate_offer(altered)
        for key, value in [('linked_terms_checked', True), ('full_program_catalog', True), ('earning_rules', [])]:
            altered = copy.deepcopy(row); altered['details'][key] = value; altered['content_sha256'] = content_hash(altered)
            with self.subTest(key=key), self.assertRaises(ValueError): validate_offer(altered)

    def test_source_page_anchor_is_not_the_unread_hotel_page(self):
        row = parse_catalog(document(), NOW)[0]
        self.assertTrue(row['benefit_url'].startswith(ROOT+'#'))
        self.assertEqual(row['details']['public_catalog_block']['links'][0]['url'], 'https://hotel.example/book')
        self.assertFalse(row['details']['linked_terms_checked'])

    def test_source_categories_do_not_cross_accordion_sections(self):
        raw = document().replace('</section></div>', '</section><h2 class="routes__title">Связь</h2><section>'+card('Phone', 'Телеком')+'</section></div>')
        self.assertEqual([r['category'] for r in parse_catalog(raw, NOW)], ['Отели', 'Связь'])


class FreshBundleTests(unittest.TestCase):
    def build(self, r, folder):
        roots = configured_roots(Path(__file__).parents[1]/'sources_normalized.json')
        return build(r, roots, folder, run_id='fixture-run', attempt='2', commit='fixture-commit', clock=CLOCK)

    def test_real_publication_contract_with_one_supported_source(self):
        raw = document()
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'nordwind.html').write_text(raw)
            bundle = self.build(report(raw), tmp)
            self.assertEqual(len(bundle['records']), 1); self.assertEqual(len(bundle['sources']), 6)
            self.assertEqual(bundle['run_id'], 'fixture-run:2')
            self.assertEqual(len(prepare(bundle)['parser_offers']), 1)
            self.assertEqual(next(s for s in bundle['sources'] if s['source_id']=='nordwind')['status'], 'ok')

    def test_old_attempt_wrong_commit_stale_future_and_account_data_rejected(self):
        raw = document()
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'nordwind.html').write_text(raw)
            for field, value in [('run_attempt', '1'), ('commit', 'old'), ('account_sessions_used', True),
                ('started_at', '2026-09-14T19:41:00+00:00'), ('finished_at', '2026-09-16T19:41:00+00:00'),
                ('free_plan_confirmed', False)]:
                r = report(raw); r[field] = value
                with self.subTest(field=field), self.assertRaises(ValueError): self.build(r, tmp)

    def test_replaced_document_rejected(self):
        raw = document()
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'nordwind.html').write_text(raw+'tamper')
            with self.assertRaises(ValueError): self.build(report(raw), tmp)

    def test_unimplemented_coral_is_not_a_new_offer(self):
        raw = document(); r = report(raw)
        r['sources'] = [{'source_id':'coral','status':'candidate_requires_review'}]
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'nordwind.html').write_text(raw)
            b = self.build(r, tmp)
            self.assertFalse(b['records'])
            c = next(x for x in b['sources'] if x['source_id']=='coral')
            self.assertNotEqual(c['status'], 'ok')

    def test_later_provider_failure_keeps_real_earlier_records(self):
        raw = document(); r = report(raw); r['status'] = 'stopped'
        r['sources'].append({'source_id':'rzd','status':'failed','error':'provider_http_423'})
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'nordwind.html').write_text(raw)
            b = self.build(r, tmp)
            self.assertEqual(len(b['records']), 1)
            self.assertEqual(next(x for x in b['sources'] if x['source_id']=='rzd')['status'], 'failed')

    def test_duplicate_source_and_wrong_origin_status_rejected(self):
        raw = document()
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'nordwind.html').write_text(raw)
            r = report(raw); r['sources'] *= 2
            with self.assertRaises(ValueError): self.build(r, tmp)
            r = report(raw); r['sources'][0]['origin_http_status'] = 403
            with self.assertRaises(ValueError): self.build(r, tmp)


if __name__ == '__main__': unittest.main()
