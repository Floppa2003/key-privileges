import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import merchant_heldout_eval as e

ROOT=Path(__file__).resolve().parents[1]/'experiments/merchant_general'

class HeldoutEval(unittest.TestCase):
    def test_frozen_baseline_exposes_current_failure_modes(self):
        report=e.evaluate(ROOT/'heldout-v1.json',ROOT/'heldout-v1-observed.json')
        self.assertEqual(report['cases'],5)
        self.assertEqual(report['passed_cases'],0)
        self.assertEqual(report['block_contract_valid'],2)
        self.assertEqual(report['explicit_audience_reusable'],1)
        self.assertEqual(report['expected_reusable'],4)
        self.assertEqual(report['exact_variant_count'],4)
        self.assertEqual(report['required_evidence_phrases_found'],18)
        self.assertEqual(report['required_evidence_phrases_total'],19)
        self.assertEqual(report['forbidden_borrowing_hits'],3)
        self.assertEqual(report['required_date_roles_found'],1)
        self.assertEqual(report['required_date_roles_total'],2)
        self.assertFalse(report['publication_allowed'])

    def test_case_reasons_are_specific_not_one_aggregate_score(self):
        report=e.evaluate(ROOT/'heldout-v1.json',ROOT/'heldout-v1-observed.json')
        by={x['id']:x for x in report['results']}
        self.assertIn('variant_count',by['rostelecom-ekp-segments']['failures'])
        self.assertIn('audience_missing',by['rostelecom-ekp-segments']['failures'])
        self.assertIn('block_contract',by['domknigi-ekp']['failures'])
        self.assertIn('forbidden_borrowing',by['itc-ekp-list-scope']['failures'])
        self.assertIn('date_role',by['grandkarat-rzd-booking-window']['failures'])
        self.assertIn('disposition',by['losevo-ekp-partnership-only']['failures'])

    def test_v2_regression_improves_but_still_fails_critical_cases(self):
        report=e.evaluate(ROOT/'heldout-v1.json',ROOT/'heldout-v1-observed-v2.json')
        self.assertEqual(report['cases'],5)
        self.assertEqual(report['passed_cases'],2)
        self.assertEqual(report['block_contract_valid'],3)
        self.assertEqual(report['explicit_audience_reusable'],3)
        self.assertEqual(report['exact_variant_count'],3)
        self.assertEqual(report['required_evidence_phrases_found'],19)
        self.assertEqual(report['required_evidence_phrases_total'],19)
        self.assertEqual(report['forbidden_borrowing_hits'],2)
        self.assertEqual(report['required_date_roles_found'],2)
        self.assertEqual(report['required_date_roles_total'],2)
        self.assertEqual(report['unexpected_material_date_roles'],1)
        self.assertEqual(report['code_state_correct'],4)
        by={x['id']:x for x in report['results']}
        self.assertTrue(by['rostelecom-ekp-segments']['passed'])
        self.assertIn('code_state',by['domknigi-ekp']['failures'])
        self.assertIn('forbidden_borrowing',by['itc-ekp-list-scope']['failures'])
        self.assertIn('unexpected_date_role',by['grandkarat-rzd-booking-window']['failures'])
        self.assertTrue(by['losevo-ekp-partnership-only']['passed'])
        self.assertFalse(report['publication_allowed'])

    def test_expected_labels_are_not_read_from_observation_file(self):
        report=e.evaluate(ROOT/'heldout-v1.json',ROOT/'heldout-v1-observed.json')
        self.assertTrue(report['labels_frozen_before_predictions'])
        self.assertFalse(report['expected_labels_sent_to_model'])

if __name__=='__main__':unittest.main()
