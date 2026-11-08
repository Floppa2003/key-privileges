"""An explicitly denied points amount must not become an earned reward."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from unified_normalization import normalize_inputs, normalize_record, validate_normalized
from unified_views import SCHEMAS, prepare_views
from test_unified_normalization import record


class PointsNegationTests(unittest.TestCase):
    def project(self, literal, **updates):
        source = record(**{'benefit': literal, 'conditions': '', 'activation': '', **updates})
        before = copy.deepcopy(source)
        result = normalize_record(source, as_of='2026-11-08')
        self.assertEqual(source, before)
        self.assertEqual(result['raw'], before)
        validate_normalized(json.loads(json.dumps(result)))
        for term in result['benefits']:
            self.assertIn(term['evidence']['text'], source[term['evidence']['path'].lstrip('/')])
        return result

    def rewards(self, literal, **updates):
        return [(b['kind'], b['value'], b['unit'])
                for b in self.project(literal, **updates)['benefits']]

    def test_explicit_prefix_and_suffix_denials_award_no_points(self):
        for literal in (
                'Не начисляем 500 баллов.',
                'Не получите 500 бонусов.',
                'Нельзя получить 500 баллов.',
                'Невозможно получить 500 бонусов.',
                'Не будут начислены 500 баллов.',
                'Не будем начислять 500 бонусов.',
                '500 баллов не начисляются.',
                '500 бонусов не будут начислены.',
                '500 баллов получить нельзя.',
                'Получить 500 бонусов невозможно.',
                'Не начисляем 500 дополнительных баллов.',
                '500 дополнительных бонусов не начисляются.'):
            with self.subTest(literal=literal):
                self.assertEqual(self.rewards(literal), [])

    def test_neighbouring_positive_award_keeps_its_own_amount(self):
        for literal in (
                'Не начисляем 500 баллов, но получите 100 бонусов.',
                'Получите 100 бонусов, но 500 баллов не начисляются.',
                'Не начисляем 500 баллов и получите 100 бонусов.',
                'Получите 100 бонусов и не получите 500 баллов.',
                'Не начисляем 500 баллов, 100 бонусов получите.',
                '100 бонусов начисляются, 500 баллов не начисляются.',
                'Не начисляем 500 баллов. Получите 100 бонусов.',
                'Получите 100 бонусов. 500 баллов не начисляются.',
                'Не начисляем 500 баллов; получите 100 бонусов.',
                'Не начисляем 500 баллов\nПолучите 100 бонусов.'):
            with self.subTest(literal=literal):
                self.assertEqual(self.rewards(literal), [('earn_points', '100', 'points')])

    def test_shared_denied_award_does_not_create_any_listed_amount(self):
        for literal in (
                'Не начисляем 500 баллов и 100 бонусов.',
                'Не начисляем 500 баллов, 100 бонусов.',
                'Нельзя получить 500 баллов или 100 бонусов.',
                '500 баллов и 100 бонусов не начисляются.',
                '500 баллов, 100 бонусов получить нельзя.',
                '500 баллов или 100 бонусов нельзя получить.'):
            with self.subTest(literal=literal):
                self.assertEqual(self.rewards(literal), [])

    def test_affirmative_wording_and_unrelated_negation_are_preserved(self):
        for literal in (
                'Получите 500 баллов.',
                '500 бонусов начисляются за покупку.',
                'Получите в подарок 500 баллов.',
                'Получите не менее 500 бонусов.',
                'Начисляем не более 500 баллов.',
                'Не только получите 500 баллов, но и доступ к каталогу.',
                'Получите 500 баллов, если не оформляли заказ ранее.',
                'Не забудьте зарегистрироваться и получите 500 баллов.',
                'Получите 500 баллов. Не получите бумажный чек.',
                'Начислим 500 баллов, 100 бонусов не начисляются.',
                'Получите 500 баллов и 100 бонусов не начисляются.',
                'Если вы не получили письмо, 500 баллов будут начислены автоматически.',
                'Не получили письмо, 500 баллов уже начислены.'):
            with self.subTest(literal=literal):
                points = [item for item in self.rewards(literal) if item[0] == 'earn_points']
                self.assertEqual(points, [('earn_points', '500', 'points')])

    def test_denial_in_another_field_cannot_cancel_positive_award(self):
        result = self.project('Получите 100 бонусов.', conditions='Не начисляем 500 баллов.')
        self.assertEqual([(b['kind'], b['value']) for b in result['benefits']], [('earn_points', '100')])
        self.assertEqual(result['benefits'][0]['evidence'],
                         {'path': '/benefit', 'text': 'Получите 100 бонусов.'})
        self.assertTrue(any(c['evidence'] == {'path': '/conditions', 'text': 'Не начисляем 500 баллов.'}
                            for c in result['conditions']))

    def test_common_views_publish_only_the_affirmative_award(self):
        source = record(benefit='Не начисляем 500 баллов, но получите 100 бонусов.',
                        conditions='', activation='')
        before = copy.deepcopy(source)
        bundle = normalize_inputs([source], as_of='2026-11-08')
        rows = prepare_views(bundle)['normalized_benefits']
        values = [dict(zip(SCHEMAS['normalized_benefits'], row)) for row in rows]
        self.assertEqual(len(values), 1)
        self.assertEqual((values[0]['Тип выгоды'], values[0]['Значение']), ('earn_points', '100'))
        self.assertEqual(bundle['records'][0]['benefits'][0]['value'], '100')
        self.assertEqual(bundle['records'][0]['raw'], before)
        self.assertEqual(source, before)


if __name__ == '__main__':
    unittest.main()
