"""Native detail discounts remain scoped components of a concierge privilege."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from konsierge_catalog import ROOT, PROGRAM, METHOD, derived, digest
from promo_codes import extract_promocodes
from unified_normalization import normalize_record, validate_normalized
from test_unified_normalization import record


CASES = json.loads((Path(__file__).parent /
    'fixtures_live/observed-konsierge-component-rates-20261114.json').read_text())['cases']
EXPECTED = {
    'Lotte (Петербург)': [('10', 'exact')],
    'Гармония': [('15', 'exact'), ('20', 'exact')],
    'Олимп клиник (Садовая)': [('10', 'exact'), ('5', 'exact'), ('10', 'exact')],
    'SimplePrivé': [('30', 'exact'), ('15', 'exact'), ('40', 'up_to')],
    'Lacy Bird': [('10', 'exact'), ('5', 'exact')],
}


class ObservedKonsiergeComponentRates(unittest.TestCase):
    def test_detail_rates_stay_attached_to_their_service_and_complete_rules(self):
        for case in CASES:
            item = case['item']
            with self.subTest(partner=item['name']):
                label, body, activation, end, warnings, words = derived(item, case['observed_at'])
                raw = record(program=PROGRAM, partner=item['name'], title=item['name'],
                             source_id='parser_offers', source_url=ROOT, benefit_url=None,
                             link_kind='page_block', benefit=label, conditions=body,
                             activation=activation, valid_until=end, source_warnings=warnings,
                             observed_at=case['observed_at'],
                             codes=extract_promocodes('\n'.join((label, body, activation)))['codes'],
                             details={'retrieval_method': METHOD, 'public_item': item,
                                      'item_sha256': digest(item), 'code_words': words,
                                      'only_assist_equivalence': False})
                before = copy.deepcopy(raw)
                n = normalize_record(raw, as_of='2026-11-14')
                validate_normalized(n)
                self.assertEqual(raw, before)
                self.assertEqual(n['raw'], before)
                components = [b for b in n['benefits'] if b['evidence']['path'] == '/conditions']
                self.assertEqual([(b['value'], b['qualifier']) for b in components], EXPECTED[item['name']])
                for b in components:
                    self.assertEqual(b['kind'], 'discount')
                    self.assertEqual(b['unit'], 'percent')
                    self.assertFalse(b['standalone_offer'])
                    self.assertFalse(b['scope']['headline_label_only'])
                    self.assertEqual(b['scope']['source_clause'], b['evidence']['text'])
                    self.assertIn(b['evidence']['text'], raw['conditions'])
                    self.assertTrue(b['condition_ids'])
                    self.assertEqual(b['condition_linkage'], 'full_owned_record_rules')


if __name__ == '__main__':
    unittest.main()
