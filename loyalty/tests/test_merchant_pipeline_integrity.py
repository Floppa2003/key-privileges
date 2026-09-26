"""Cross-stage contracts: real source checker -> guard -> atomic review tasks."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import merchant_blocks as v1
import merchant_blocks_v2 as v2
import merchant_claims as claims
import merchant_semantic_guard as guard

TARGET = {'merchant': 'Synthetic', 'program': 'Example Club', 'aliases': ['EC']}
TEXT = '## Example Club\n\nДержателям EC скидка 20%.\n'


def fixture(module=v2, completeness='provider_markdown', duplicate=False):
    doc = module.build(TEXT, url='https://example.test/', observed_at='2026-09-26', completeness=completeness)
    offer = {'program': ['b0000'], 'audience': ['b0001'], 'benefit': ['b0001'],
             'conditions': [], 'redemption': [],
             'code': {'state': 'not_stated', 'value': '', 'refs': []},
             'dates': [], 'uncertainties': []}
    raw = {'source_sha256': doc['source_sha256'], 'state': 'candidates',
           'notes': '', 'offers': [offer, copy.deepcopy(offer)] if duplicate else [offer]}
    return doc, module.check(TARGET, doc, raw)


class PipelineIntegrity(unittest.TestCase):
    def test_upstream_duplicate_error_cannot_become_guard_pass(self):
        _, checked = fixture(duplicate=True)
        self.assertEqual(checked['problems'], ['duplicate_offer_variant'])
        self.assertEqual(len(checked['offers']), 1)  # Real partially validated receipt.
        result = guard.assess_result(TARGET, checked)
        self.assertEqual(result['status'], 'review_required')
        self.assertIn('block_check_problem:duplicate_offer_variant', result['reasons'])
        self.assertFalse(result['publication_allowed'])

    def test_upstream_missing_status_cannot_become_guard_pass(self):
        _, checked = fixture()
        del checked['status']
        result = guard.assess_result(TARGET, checked)
        self.assertEqual(result['status'], 'review_required')
        self.assertFalse(result['publication_allowed'])

    def test_forged_hydrated_quote_is_not_given_source_provenance(self):
        doc, checked = fixture()
        checked['offers'][0]['fields']['benefit'][0] = dict(checked['offers'][0]['fields']['benefit'][0])
        checked['offers'][0]['fields']['benefit'][0]['text'] = 'Держателям EC скидка 99%.'
        with self.assertRaisesRegex(ValueError, 'checked_evidence_changed'):
            claims.generate(TARGET, doc, checked)

    def test_old_receipt_cannot_reuse_ids_on_another_source_snapshot(self):
        doc, checked = fixture()
        newer = v2.build(TEXT.replace('20%', '10%'), url=doc['url'], observed_at=doc['observed_at'])
        with self.assertRaisesRegex(ValueError, 'checked_evidence_changed'):
            claims.generate(TARGET, newer, checked)

    def test_clearing_excerpt_review_flags_does_not_upgrade_receipt(self):
        doc, checked = fixture(completeness='source_excerpt')
        checked['offers'][0]['review_reasons'] = []
        checked['status'] = 'references_checked_needs_semantic_review'
        with self.assertRaisesRegex(ValueError, 'checked_evidence_changed'):
            claims.generate(TARGET, doc, checked)

    def test_source_context_cannot_be_replaced_to_hide_restrictions(self):
        doc, checked = fixture()
        checked['offers'][0]['source_context']['text'] = 'A fabricated context'
        with self.assertRaisesRegex(ValueError, 'checked_evidence_changed'):
            claims.generate(TARGET, doc, checked)

    def test_partial_failed_receipt_generates_no_review_claims(self):
        doc, checked = fixture(duplicate=True)
        result = claims.generate(TARGET, doc, checked)
        self.assertEqual(result['status'], 'review_required')
        self.assertEqual(result['claims'], [])
        self.assertIn('block_check_problem:duplicate_offer_variant', result['reasons'])

    def test_receipt_is_bound_even_when_only_an_unselected_section_changes(self):
        doc, checked = fixture()
        newer = v2.build(TEXT + '\n## Other Club\n\nUnrelated new text.\n',
                         url=doc['url'], observed_at=doc['observed_at'])
        with self.assertRaisesRegex(ValueError, 'checked_evidence_changed'):
            claims.generate(TARGET, newer, checked)

    def test_receipt_without_snapshot_hash_is_not_upgraded(self):
        doc, checked = fixture()
        checked.pop('source_sha256', None)
        with self.assertRaisesRegex(ValueError, 'checked_evidence_changed'):
            claims.generate(TARGET, doc, checked)

    def test_unmodified_v1_and_v2_receipts_remain_reviewable(self):
        for module in (v1, v2):
            with self.subTest(module=module.VERSION):
                doc, checked = fixture(module)
                result = claims.generate(TARGET, doc, checked)
                self.assertEqual(result['status'], 'claims_ready_for_independent_review')
                self.assertEqual([c['kind'] for c in result['claims']], ['audience', 'benefit'])
                self.assertFalse(result['publication_allowed'])


if __name__ == '__main__':
    unittest.main()
