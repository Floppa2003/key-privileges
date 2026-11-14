"""Anonymized encountered mileage prices and overdraft labels are not awards."""
import copy
import unittest

from catalogue_view import build_catalogue
from normalized import normalize_rates
from unified_normalization import normalize_record, validate_normalized
from test_unified_normalization import record

PRICE = 'повышение класса обслуживания на борту за 5 000 ₽ или 5 000 миль'
DEBT = 'мильная задолженность до 10 000 миль'
EXPLANATION = ('Можно потратить на 10 000 миль больше, чем есть на счете, '
               'при повышении класса обслуживания на борту.')


class ObservedMileageSpendTests(unittest.TestCase):
    def common(self, text, rates):
        raw = record(benefit=text, conditions='', activation='', rates=rates,
                     program='Example', details={})
        before = copy.deepcopy(raw)
        result = normalize_record(raw, as_of='2026-11-13')
        self.assertEqual(raw, before)
        self.assertEqual(result['raw'], before)
        validate_normalized(result)
        return result

    def test_price_alternative_is_not_fresh_mileage_earning(self):
        self.assertEqual(normalize_rates(PRICE), [])

    def test_debt_limit_is_not_fresh_mileage_earning(self):
        self.assertEqual(normalize_rates(DEBT + '\n' + EXPLANATION), [])

    def test_retained_price_and_debt_rates_do_not_resurrect_earning(self):
        for text, value, qualifier in ((PRICE, '5000', 'exact'), (DEBT, '10000', 'up_to')):
            with self.subTest(text=text):
                result = self.common(text, [dict(kind='miles', value=value, unit='miles',
                    qualifier=qualifier, basis_amount=None, basis_unit=None, evidence=text)])
                self.assertEqual(result['benefits'], [])

    def test_multi_benefit_source_and_reader_keep_other_privileges(self):
        text = ('выбор места 0 ₽\n' + PRICE + '\n' + DEBT + '\n' + EXPLANATION
                + '\nодно повышение класса обслуживания в год\nпровоз ручной клади 10 кг')
        result = self.common(text, [])
        self.assertFalse(any(b['kind'] == 'earn_miles' for b in result['benefits']))
        reader = build_catalogue([result], as_of='2026-11-13')
        self.assertEqual(reader['rows'][0][2], 'выбор места 0 ₽ ' + PRICE + ' ' + DEBT)
        self.assertIn('провоз ручной клади 10 кг', result['raw']['benefit'])

    def test_actual_earning_wording_survives(self):
        text = ('Возвращайте до 7% милями от суммы покупки на любом тарифе билета '
                'и получайте премиальные сервисы с 10 000 ₽, потраченных на полеты.')
        self.assertEqual([(r['kind'], r['value']) for r in normalize_rates(text)], [('miles', '7')])
        result = self.common(text, [])
        self.assertEqual([(b['kind'], b['value']) for b in result['benefits']], [('earn_miles', '7')])
