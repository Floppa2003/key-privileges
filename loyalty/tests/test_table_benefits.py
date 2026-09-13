"""Table contracts observed in Ural public records; corrupt variants are synthetic."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
from normalized import make_offer, validate_offer, content_hash

NOW = '2026-09-13T10:40:00+00:00'
URL = 'https://www.uralairlines.ru/partners/#partner_test'


def offer(tables):
    return make_offer('ural', 'partner_test', 'Крылья', 'Test hotel',
                      'Скидка при предъявлении карты; исключены специальные тарифы.',
                      URL, NOW, tables=tables, link_kind='page_anchor')


class TableBenefitsTests(unittest.TestCase):
    def parsed(self, tables):
        value = offer(tables)['details'].get('table_benefits')
        self.assertIsInstance(value, dict, 'Table-scoped benefits are not normalized')
        return value

    def test_tier_rate_and_code_come_from_same_row_not_code_digits(self):
        tables = [[['Тип карты', 'Скидка', 'Промокод'],
                   ['Серебряный', '7%', 'КРЫЛЬЯ10']]]
        parsed = self.parsed(tables)
        self.assertEqual(parsed['issues'], [])
        r = parsed['components'][0]
        self.assertEqual(r['scope'], {'kind': 'card_type', 'value': 'Серебряный'})
        self.assertEqual(r['rate'], {'kind': 'discount', 'value': '7', 'unit': 'percent', 'qualifier': 'exact'})
        self.assertEqual(r['promo_codes'], ['КРЫЛЬЯ10'])
        self.assertEqual(r['evidence'], {'table_index': 0, 'row_index': 1,
                         'header': ['Тип карты', 'Скидка', 'Промокод'],
                         'row': ['Серебряный', '7%', 'КРЫЛЬЯ10']})

    def test_room_category_is_not_a_membership_tier(self):
        r = self.parsed([[['Тип номера', 'Скидка'], ['Делюкс, Делюкс твин', '7%']]])['components'][0]
        self.assertEqual(r['scope'], {'kind': 'room_type', 'value': 'Делюкс, Делюкс твин'})
        self.assertEqual(r['promo_codes'], [])

    def test_multiword_code_as_scope_does_not_invent_tier(self):
        r = self.parsed([[['Промокод', 'Скидка'], ['BLUE WINGS', '5%']]])['components'][0]
        self.assertEqual(r['scope'], {'kind': 'promo_code', 'value': 'BLUE WINGS'})
        self.assertEqual(r['promo_codes'], ['BLUE WINGS'])

    def test_column_order_and_latin_c_header(self):
        r = self.parsed([[['Cкидка', 'Вид карты'], ['10%', '«Синяя»']]])['components'][0]
        self.assertEqual(r['scope']['value'], '«Синяя»')
        self.assertEqual(r['rate']['value'], '10')

    def test_tables_are_not_joined_by_row_position(self):
        p = self.parsed([[['Промокод','Скидка'],['BLUE WINGS','5%']],
                         [['Вид карты','Скидка'],['«Золотая»','10%']]])
        self.assertEqual(len(p['components']), 2)
        self.assertEqual(p['components'][1]['promo_codes'], [])
        self.assertEqual(p['components'][1]['rate']['value'], '10')

    def test_qualifier_and_range_are_not_unconditional_maximum(self):
        p = self.parsed([[['Тип карты','Скидка'],['A','до 15%'],['B','5–10%'],['C','от 3,5%']]])
        self.assertEqual([r['rate']['qualifier'] for r in p['components']], ['up_to','range','at_least'])
        self.assertEqual(p['components'][1]['rate']['min_value'], '5')
        self.assertEqual(p['components'][2]['rate']['value'], '3.5')

    def test_missing_cells_never_shift_or_forward_fill(self):
        p = self.parsed([[['Тип карты','Скидка','Промокод'],['A','10%'],['B','5%','B5']]])
        self.assertEqual(len(p['components']), 1)
        self.assertEqual(p['components'][0]['scope']['value'], 'B')
        self.assertEqual(p['issues'][0]['reason'], 'row_width_mismatch')

    def test_blank_scope_and_unknown_rate_keep_explicit_issue(self):
        p = self.parsed([[['Тип карты','Скидка'],['','10%'],['A','по согласованию']]])
        self.assertEqual(p['components'], [])
        self.assertEqual(len(p['issues']), 2)

    def test_invalid_percentages_and_embedded_terms_not_guessed(self):
        p = self.parsed([[['Тип карты','Скидка'],['A','110%'],['B','20–10%'],
                         ['C','10% при предоплате 50%'],['D','-5%']]])
        self.assertEqual(p['components'], [])
        self.assertEqual(len(p['issues']), 4)

    def test_unrecognized_or_ambiguous_headers_are_not_discount_evidence(self):
        for header in [['Тип карты','Оценка'],['Тип карты','Скидка','Скидка'],['Тип карты','Скидка','Цена']]:
            p = self.parsed([[header, ['A'] + ['10%']*(len(header)-1)]])
            self.assertEqual(p['components'], [])
            self.assertEqual(len(p['issues']), 1)

    def test_raw_source_tables_and_global_conditions_are_unchanged(self):
        tables = [[['Тип карты','Скидка'],['Синий','5%']]]
        original = copy.deepcopy(tables)
        r = offer(tables)
        self.assertEqual(r['tables'], original)
        self.assertEqual(tables, original)
        self.assertIn('исключены специальные тарифы',r['benefit_text'])
        # Table rates remain scoped and must not become an unconditional offer rate.
        self.assertEqual(r['rates'], [])

    def test_full_evidence_is_recomputed_before_publication(self):
        r = offer([[['Тип карты','Скидка'],['Синий','5%']]])
        data = r['details'].get('table_benefits')
        self.assertIsInstance(data, dict, 'Missing table benefit evidence validation')
        data['components'][0]['rate']['value'] = '90'
        r['content_sha256'] = content_hash(r)
        with self.assertRaises(ValueError):
            validate_offer(r)

    def test_empty_tables_have_empty_components_without_issues(self):
        p = self.parsed([])
        self.assertEqual(p, {'components': [], 'issues': []})

    def test_instruction_in_code_cell_is_not_a_literal_promocode(self):
        p = self.parsed([[['Тип карты','Скидка','Промокод'],['Синий','5%','Получить в приложении']]])
        self.assertEqual(p['components'][0]['promo_codes'], [])
        self.assertEqual(p['issues'][0]['reason'], 'promo_code_not_literal')

    def test_empty_table_does_not_break_other_table_extraction(self):
        p = self.parsed([[], [['Тип карты','Скидка'],['Синий','5%']]])
        self.assertEqual(len(p['components']), 1)
        self.assertEqual(p['components'][0]['evidence']['table_index'], 1)
