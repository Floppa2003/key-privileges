"""Chance-only campaigns stay auditable without becoming ordinary offers."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).parents[1]))
from catalogue_view import record_row, build_catalogue
from unified_normalization import normalize_record
from test_unified_normalization import record


class CampaignChanceFilterTests(unittest.TestCase):
    def project(self,literal):
        raw=record(benefit=literal,conditions='',activation='',kind='campaign')
        before=copy.deepcopy(raw)
        normalized=normalize_record(raw,as_of='2026-11-08')
        self.assertEqual(raw,before)
        self.assertEqual(normalized['raw'],before)
        self.assertTrue(all(not b['standalone_offer'] for b in normalized['benefits']))
        return normalized

    def test_real_promomiles_chance_is_excluded_from_reader(self):
        literal=('Регистрируйтесь в акции, отдыхайте в отелях-партнерах акции и получите шанс '
                 'стать одним из 10 обладателей 50 000 миль и Золотого уровня «Аэрофлот Бонус»')
        result=self.project(literal)
        self.assertEqual(record_row(result,'2026-11-08'),(None,'розыгрыш'))
        catalogue=build_catalogue([result],as_of='2026-11-08')
        self.assertEqual(catalogue['counts']['kept'],0)
        self.assertEqual(catalogue['removed'][0]['reason'],'розыгрыш')

    def test_explicit_chance_to_win_is_excluded(self):
        for literal in ('Получите шанс выиграть 50 000 миль.',
                        'Шанс на победу: 50 000 миль победителю.',
                        'Шансы на победу: 50 000 миль.',
                        'Розыгрыш 50 000 миль.', 'Разыгрываем 50 000 миль.'):
            with self.subTest(literal=literal):
                self.assertEqual(record_row(self.project(literal),'2026-11-08'),(None,'розыгрыш'))

    def test_promotional_word_chance_does_not_hide_a_guaranteed_discount(self):
        result=self.project('Не упустите шанс: скидка 10% каждому участнику.')
        row,reason=record_row(result,'2026-11-08')
        self.assertIsNotNone(row)
        self.assertIsNone(reason)
        self.assertIn('10%',' '.join(row))

    def test_reader_filter_does_not_mutate_campaign_evidence(self):
        result=self.project('Получите шанс выиграть 50 000 миль.')
        before=copy.deepcopy(result)
        build_catalogue([result],as_of='2026-11-08')
        self.assertEqual(result,before)
        self.assertEqual(result['kind'],'campaign')


if __name__=='__main__':
    unittest.main()
