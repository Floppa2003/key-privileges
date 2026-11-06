"""Capitalization does not change a table's explicit rate qualifier."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from normalized import make_offer
from table_benefits import extract_table_benefits


class TableQualifierCaseTests(unittest.TestCase):
    def test_titlecase_and_uppercase_qualifiers_keep_their_meaning(self):
        cases = [('До 10%', '10', 'up_to'), ('ДО 10,5%', '10.5', 'up_to'),
                 ('От 5%', '5', 'at_least'), ('ОТ 3,5%', '3.5', 'at_least')]
        for cell, value, qualifier in cases:
            with self.subTest(cell=cell):
                table = [['Тип карты', 'Скидка'], ['Золотой', cell]]
                before = copy.deepcopy(table)
                result = extract_table_benefits([table])
                self.assertEqual(result['issues'], [])
                self.assertEqual(len(result['components']), 1)
                component = result['components'][0]
                self.assertEqual(component['rate'], {'kind': 'discount', 'value': value,
                                                     'unit': 'percent', 'qualifier': qualifier})
                self.assertEqual(component['evidence']['row'], before[1])
                self.assertEqual(table, before)

    def test_published_table_preserves_qualifier_and_original_cell(self):
        tables = [[['Тип карты', 'Скидка'], ['Серебряный', 'До 10%']]]
        offer = make_offer('ural', 'table-case', 'Крылья', 'Отель',
                           'Скидка при предъявлении карты.',
                           'https://www.uralairlines.ru/partners/',
                           '2026-11-06T00:00:00Z', tables=tables)
        self.assertEqual(offer['tables'], tables)
        components = offer['details']['table_benefits']['components']
        self.assertEqual(len(components), 1)
        self.assertEqual(components[0]['rate']['qualifier'], 'up_to')
        self.assertEqual(components[0]['rate']['value'], '10')


if __name__ == '__main__':
    unittest.main()
