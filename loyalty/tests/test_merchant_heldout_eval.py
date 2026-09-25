import sys
import json
import tempfile
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
        self.assertEqual(report['block_contract_valid'],2)
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
        self.assertIn('block_contract',by['grandkarat-rzd-booking-window']['failures'])
        self.assertIn('duplicate_offer_variant',by['grandkarat-rzd-booking-window']['block_problems'])
        self.assertIn('unexpected_date_role',by['grandkarat-rzd-booking-window']['failures'])
        self.assertTrue(by['losevo-ekp-partnership-only']['passed'])
        self.assertFalse(report['publication_allowed'])

    def test_expected_labels_are_not_read_from_observation_file(self):
        report=e.evaluate(ROOT/'heldout-v1.json',ROOT/'heldout-v1-observed.json')
        self.assertTrue(report['labels_frozen_before_predictions'])
        self.assertFalse(report['expected_labels_sent_to_model'])

    def test_independent_v2_corpus_uses_same_metrics_without_label_leakage(self):
        corpus={
            'version':'merchant-heldout-v2',
            'cases':[{
                'id':'negative',
                'target':{'merchant':'X','program':'Example Club','aliases':['EC']},
                'source':{'url':'https://example.test/','completeness':'provider_markdown',
                          'observed_at':'2026-09-25','markdown':'# Награда EC\\n\\nПартнер получил благодарность.\\n'},
                'expected':{'disposition':'no_reusable_offer','offer_variants':0,
                            'required_phrases':[],'forbidden_borrowing':[],
                            'code_state':'not_stated','date_roles':[]},
            }],
        }
        observed={'version':'merchant-heldout-observed-v1-on-v2',
                  'block_version':'merchant-blocks-v2',
                  'labels_frozen_before_predictions':True,
                  'expected_labels_sent_to_model':False,
                  'publication_allowed':False,
                  'trials':[{'id':'negative','raw_answer':
                      '{"source_sha256":"PLACEHOLDER","state":"no_offer","offers":[],"notes":""}'}]}
        import merchant_blocks_v2 as b
        s=corpus['cases'][0]['source']
        d=b.build(s['markdown'],url=s['url'],observed_at=s['observed_at'],completeness=s['completeness'])
        observed['trials'][0]['raw_answer']=observed['trials'][0]['raw_answer'].replace('PLACEHOLDER',d['source_sha256'])
        with tempfile.TemporaryDirectory() as td:
            cp=Path(td)/'c.json';op=Path(td)/'o.json'
            cp.write_text(json.dumps(corpus,ensure_ascii=False),encoding='utf-8')
            op.write_text(json.dumps(observed,ensure_ascii=False),encoding='utf-8')
            report=e.evaluate(cp,op)
        self.assertEqual(report['cases'],1)
        self.assertEqual(report['passed_cases'],1)
        self.assertTrue(report['labels_frozen_before_predictions'])
        self.assertFalse(report['expected_labels_sent_to_model'])
        self.assertFalse(report['publication_allowed'])

    def test_transport_failure_is_separate_from_semantic_failure(self):
        corpus={
            'version':'merchant-heldout-v3',
            'cases':[{
                'id':'transport-failed',
                'target':{'merchant':'X','program':'Example Club','aliases':['EC']},
                'source':{'url':'https://example.test/','completeness':'source_excerpt',
                          'observed_at':'2026-09-25','markdown':'# Example Club\\n\\nДержателям EC скидка 20%.\\n'},
                'expected':{'disposition':'reusable_offer','offer_variants':1,
                            'required_phrases':['скидка 20%'],'forbidden_borrowing':[],
                            'code_state':'not_stated','date_roles':[]},
            }],
        }
        observed={'version':'merchant-heldout-observed-v3',
                  'block_version':'merchant-blocks-v2',
                  'labels_frozen_before_predictions':True,
                  'expected_labels_sent_to_model':False,
                  'publication_allowed':False,
                  'trials':[{'id':'transport-failed','transport':{
                      'status':'failed','error':'ERR_TUNNEL_CONNECTION_FAILED'},
                      'raw_answer':None}]}
        with tempfile.TemporaryDirectory() as td:
            cp=Path(td)/'c.json';op=Path(td)/'o.json'
            cp.write_text(json.dumps(corpus,ensure_ascii=False),encoding='utf-8')
            op.write_text(json.dumps(observed,ensure_ascii=False),encoding='utf-8')
            report=e.evaluate(cp,op)
        self.assertEqual(report['cases'],1)
        self.assertEqual(report['transport_attempts'],1)
        self.assertEqual(report['transport_successes'],0)
        self.assertEqual(report['transport_failures'],1)
        self.assertEqual(report['semantic_cases'],0)
        self.assertEqual(report['semantic_passed_cases'],0)
        row=report['results'][0]
        self.assertEqual(row['evaluation_status'],'transport_failure')
        self.assertEqual(row['failures'],['transport'])
        self.assertIsNone(row['actual_disposition'])
        self.assertFalse(report['publication_allowed'])

    def test_v4_version_uses_same_frozen_eval_contract(self):
        corpus={
            'version':'merchant-heldout-v4',
            'cases':[{
                'id':'negative-v4',
                'target':{'merchant':'X','program':'Example Club','aliases':['EC']},
                'source':{'url':'https://example.test/','completeness':'source_excerpt',
                          'observed_at':'2026-09-25','markdown':'# Example Club\\n\\nПартнёрство без выгоды.\\n'},
                'expected':{'disposition':'no_reusable_offer','offer_variants':0,
                            'required_phrases':[],'forbidden_borrowing':[],
                            'code_state':'not_stated','date_roles':[]},
            }],
        }
        observed={'version':'merchant-heldout-observed-v4',
                  'block_version':'merchant-blocks-v2',
                  'labels_frozen_before_predictions':True,
                  'expected_labels_sent_to_model':False,
                  'publication_allowed':False,
                  'trials':[{'id':'negative-v4','raw_answer':
                      '{"source_sha256":"PLACEHOLDER","state":"no_offer","offers":[],"notes":""}'}]}
        import merchant_blocks_v2 as b
        s=corpus['cases'][0]['source']
        d=b.build(s['markdown'],url=s['url'],observed_at=s['observed_at'],completeness=s['completeness'])
        observed['trials'][0]['raw_answer']=observed['trials'][0]['raw_answer'].replace('PLACEHOLDER',d['source_sha256'])
        with tempfile.TemporaryDirectory() as td:
            cp=Path(td)/'c.json';op=Path(td)/'o.json'
            cp.write_text(json.dumps(corpus,ensure_ascii=False),encoding='utf-8')
            op.write_text(json.dumps(observed,ensure_ascii=False),encoding='utf-8')
            report=e.evaluate(cp,op)
        self.assertEqual(report['cases'],1)
        self.assertEqual(report['passed_cases'],1)
        self.assertEqual(report['semantic_cases'],1)
        self.assertEqual(report['semantic_passed_cases'],1)
        self.assertFalse(report['publication_allowed'])

if __name__=='__main__':unittest.main()
