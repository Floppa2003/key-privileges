import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from collect_normalized import source_budget

class BudgetTests(unittest.TestCase):
    def test_default_and_explicit_source_budgets(self):
        self.assertEqual(source_budget({'id':'test'}),420)
        self.assertEqual(source_budget({'id':'mir'}),900)
        self.assertEqual(source_budget({'timeout_seconds':900}),900)
    def test_unbounded_or_invalid_budget_is_rejected(self):
        for value in (0,True,1001,'900',-1):
            with self.assertRaises(ValueError):source_budget({'timeout_seconds':value})
