"""Reviewed PDF rates survive the real publisher-to-common-reader boundary."""
import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import alfa_partner_rules as alfa
from sheets_normalized import prepare, SCHEMAS
from test_alfa_partner_rules import fixture, NOW
from unified_normalization import make_input, normalize_record, pointer, validate_normalized


CASES = (
    ('betulla_0126', 'ООО «ЛИНДЕН»', 'всех'),
    ('r14_0126', 'ООО «ЗЕН»', 'первой'),
    ('takhauli_0226', 'ООО «ОЛИВЬЕ»', 'всех'),
    ('fresa_0226', 'ООО «СОМ»', 'первой'),
    ('mamatuta_probka_spb_0126', 'ООО «Пробка-Север»', 'первой'),
)


def published_input(native_id='betulla_0126', legal='ООО «ЛИНДЕН»', scope='всех'):
    spec = alfa.BY_ID[native_id]
    source = fixture(legal=legal, ogrn=spec['ogrn'], address=spec['address_marker'],
                     scope=scope, first=scope == 'первой')
    # PDF decoding is the external boundary; parsing, validation, publication,
    # and the production common reader all run normally.
    with patch.object(alfa, 'pdf_text', return_value=source):
        row = alfa.parse_document(spec, b'%PDF-fixture-' + native_id.encode(), NOW)
    report = dict(source_id=alfa.SOURCE_ID, name='Alfa', root='https://alfabank.servicecdn.ru/',
                  status='ok', discovered=1, normalized=1, failed=0, coverage='fixture',
                  region=None, errors=[], observed_at=NOW)
    bundle = dict(schema_version=2, run_id='fixture:1', observed_at=NOW,
                  records=[row], sources=[report])
    values = prepare(bundle)['parser_offers'][0]
    raw = make_input(dict(id=row['id'], origin='parser_offers', row=2,
        fields={h: {'value': v} for h, v in zip(SCHEMAS['parser_offers'], values)}))
    return row, raw


class AlfaPartnerCommonTests(unittest.TestCase):
    def test_all_five_published_pdfs_keep_one_exact_rate_and_alternative_reward_units(self):
        for native_id, legal, transaction_scope in CASES:
            with self.subTest(native_id=native_id):
                row, raw = published_input(native_id, legal, transaction_scope)
                self.assertEqual(raw['source_id'], 'parser_offers')
                before = copy.deepcopy(raw)
                result = normalize_record(raw, as_of='2026-11-06')
                validate_normalized(json.loads(json.dumps(result)))
                self.assertEqual(raw, before)
                self.assertEqual(result['raw'], before)
                self.assertEqual(result['id'], row['id'])
                self.assertEqual(result['provenance']['observed_at'], NOW)
                self.assertEqual(result['provenance']['source_url'], row['source_url'])
                self.assertEqual([(b['kind'], b['value'], b['unit'], b['qualifier'], b['reward_unit'])
                                  for b in result['benefits']],
                                 [('earn_rewards', '10', 'percent', 'exact', 'Альфа-Баллы/ Бонусные Мили')])
                benefit = result['benefits'][0]
                self.assertEqual(benefit['method'], 'structured_source')
                expected_scope = ('first_transaction_each_calendar_month' if transaction_scope == 'первой'
                                  else 'all_transactions_in_calendar_month')
                self.assertEqual(benefit['scope']['transaction_scope'], expected_scope)
                self.assertEqual(benefit['evidence']['path'], '/benefit')
                self.assertTrue(benefit['evidence']['text'].startswith('3.2.'))
                self.assertNotIn('Кэшбэк до', benefit['evidence']['text'])
                self.assertIn('1 500 Альфа-Баллов/ Бонусных Миль', benefit['evidence']['text'])
                self.assertIsNone(result['eligibility_verified'])

    def test_complete_conditions_activation_and_cap_are_linked_without_invented_cash_limit(self):
        row, raw = published_input(*CASES[3])
        result = normalize_record(raw, as_of='2026-11-06')
        self.assertEqual(len(result['benefits']), 1)
        benefit = result['benefits'][0]
        linked = [c for c in result['conditions'] if c['id'] in benefit.get('condition_ids', [])]
        self.assertEqual({c['id'] for c in linked}, {c['id'] for c in result['conditions']})
        self.assertIn(row['conditions_text'], [c['evidence']['text'] for c in linked])
        self.assertIn(row['redemption_text'], [c['evidence']['text'] for c in linked])
        kinds = {c['kind']: c['evidence']['text'] for c in linked}
        self.assertEqual(kinds.get('activation'), row['redemption_text'])
        self.assertEqual(kinds.get('limitations'), row['details']['limitations'])
        self.assertTrue(any('1 500 Альфа-Баллов/ Бонусных Миль' in c['evidence']['text'] for c in linked))
        self.assertTrue(all(c['value'] is None and c['unit'] is None for c in linked))
        self.assertEqual(benefit.get('condition_linkage'), 'full_owned_record_rules')
        self.assertTrue(benefit.get('remaining_record_rules_require_review'))
        for group in ('benefits', 'conditions', 'costs', 'codes'):
            for term in result[group]:
                evidence = term['evidence']
                self.assertIn(evidence['text'], pointer(result['raw'], evidence['path']))
                self.assertEqual(term['method'], 'structured_source')

    def test_serialized_rates_cannot_override_the_document_clause(self):
        _, raw = published_input()
        raw['rates'] = [{'kind': 'cashback', 'value': '99', 'unit': 'percent',
                         'qualifier': 'exact', 'evidence': 'invented 99%'}]
        result = normalize_record(raw, as_of='2026-11-06')
        self.assertEqual([(b['value'], b['qualifier']) for b in result['benefits']], [('10', 'exact')])
        self.assertEqual(result['raw']['rates'], raw['rates'])

    def test_known_document_projection_rejects_broken_source_binding(self):
        _, raw = published_input()
        mutations = {
            'id': lambda r: r.update(id='0' * 64),
            'url': lambda r: r.update(source_url=r['source_url'] + '?unreviewed=1'),
            'program': lambda r: r.update(program='Another program'),
            'partner': lambda r: r.update(partner='Another partner'),
            'source_id': lambda r: r.update(source_id='other_source'),
            'status': lambda r: r.update(source_status='published'),
            'kind': lambda r: r.update(kind='program_rules'),
            'link_kind': lambda r: r.update(link_kind='offer_page'),
            'benefit_url': lambda r: r.update(benefit_url=r['source_url']),
            'ogrn': lambda r: r['details'].update(partner_ogrn='0000000000000'),
            'sha': lambda r: r['details'].update(document_sha256='unverified'),
            'conditions': lambda r: r.update(conditions='Truncated rules'),
            'activation': lambda r: r.update(activation='Different card'),
            'scope': lambda r: r['details'].update(transaction_scope='first_transaction_each_calendar_month'),
            'warnings': lambda r: r.update(source_warnings=[]),
            'benefit': lambda r: r.update(benefit='Акции «Кэшбэк до 10% за покупки Alfa Only»'),
        }
        for name, mutate in mutations.items():
            with self.subTest(field=name):
                bad = copy.deepcopy(raw)
                mutate(bad)
                with self.assertRaisesRegex(ValueError, 'alfa_partner_pdf_'):
                    normalize_record(bad, as_of='2026-11-06')

    def test_unrelated_record_with_copied_wording_does_not_get_owned_projection(self):
        _, raw = published_input()
        raw.update(id='unrelated', source_url='https://example.test/other.pdf', source_status='published')
        result = normalize_record(raw, as_of='2026-11-06')
        self.assertFalse(any(b.get('condition_linkage') == 'full_owned_record_rules' for b in result['benefits']))
        self.assertFalse(any(b['qualifier'] == 'exact' for b in result['benefits']))


if __name__ == '__main__':
    unittest.main()
