"""A source line break must not hide an otherwise explicit literal coupon."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from unified_normalization import make_input, normalize_record
from test_unified_normalization import record


class UnifiedMultilineCodes(unittest.TestCase):
    def test_legacy_input_retains_code_and_first_order_scope_across_line_break(self):
        literal = 'Для первого заказа промокод:\nFIRST10'
        raw = make_input({
            'id': 'legacy:multiline', 'origin': 'loyalty_partner_benefits',
            'row': 5, 'fields': {
                'Программа': {'value': 'S7 Priority'},
                'Партнёр / сервис': {'value': 'Example'},
                'Выгода': {'value': literal},
            },
        })
        before = copy.deepcopy(raw)
        result = normalize_record(raw, as_of='2026-11-06')
        self.assertEqual(raw, before)
        self.assertEqual(result['raw'], before)
        self.assertEqual(len(result['codes']), 1)
        code = result['codes'][0]
        self.assertEqual((code['value'], code['scope']),
                         ('FIRST10', {'purchase_stage': 'first'}))
        self.assertEqual(code['evidence'], {'path': '/benefit', 'text': literal})

    def test_owned_fields_keep_literal_code_and_local_scope(self):
        cases = (
            ('benefit', 'Промокод\nSUMMER26', 'SUMMER26', {}),
            ('conditions', 'Промокод:\nMEMBER20', 'MEMBER20', {}),
            ('activation', 'Введите промокод:\r\nREPEAT20 для повторного заказа.',
             'REPEAT20', {'purchase_stage': 'repeat'}),
        )
        for field, literal, value, scope in cases:
            with self.subTest(field=field):
                raw = record(benefit='', conditions='', activation='', codes=[])
                raw[field] = literal
                result = normalize_record(raw, as_of='2026-11-06')
                self.assertEqual([(c['value'], c['scope']) for c in result['codes']],
                                 [(value, scope)])
                self.assertEqual(result['codes'][0]['evidence'],
                                 {'path': '/' + field, 'text': literal})
                self.assertEqual(result['raw'], raw)

    def test_blank_sections_and_mid_sentence_mentions_do_not_license_codes(self):
        for literal in ('Промокод:\n\nSUMMER26',
                        'В поле промокод\nFIRST10 — название другой акции.'):
            with self.subTest(literal=literal):
                result = normalize_record(record(benefit=literal, conditions=''),
                                          as_of='2026-11-06')
                self.assertEqual(result['codes'], [])

    def test_does_not_join_label_and_value_from_different_fields(self):
        result = normalize_record(record(benefit='Промокод:', conditions='SUMMER26'),
                                  as_of='2026-11-06')
        self.assertEqual(result['codes'], [])

    def test_existing_audience_code_does_not_gain_an_unscoped_duplicate(self):
        details = {'audiences': [{'audience': 'youth', 'promo_code': 'FIRST10',
                                 'evidence': 'FIRST10 for youth'}]}
        result = normalize_record(record(benefit='Промокод:\nFIRST10',
                                         conditions='', details=details,
                                         codes=['FIRST10']), as_of='2026-11-06')
        self.assertEqual(len(result['codes']), 1)
        self.assertEqual(result['codes'][0]['scope'], {'audience': 'youth'})

    def test_repeated_literal_with_ambiguous_scope_is_not_assigned_to_one_occurrence(self):
        literal = ('Для первого заказа промокод:\nSAME20\n\n'
                   'Для повторного заказа промокод:\nSAME20')
        result = normalize_record(record(benefit=literal, conditions=''),
                                  as_of='2026-11-06')
        self.assertEqual(result['codes'], [])

    def test_evidence_only_inbox_remains_unprojected(self):
        result = normalize_record(record(origin='parser_inbox', kind='raw_page',
                                         benefit='Промокод:\nSUMMER26',
                                         conditions='', privacy='unclassified'),
                                  as_of='2026-11-06')
        self.assertEqual(result['codes'], [])
        self.assertEqual(result['quality']['level'], 'evidence_only')


if __name__ == '__main__':
    unittest.main()
