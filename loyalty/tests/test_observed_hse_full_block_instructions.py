"""Full native HSE blocks distinguish discount offers from their instructions."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import hse_alumni
from normalized import validate_offer
from test_source_availability_dates import stored_input
from unified_normalization import make_input, normalize_record


CAPTURE = json.loads(Path(__file__).with_name('fixtures_live').joinpath(
    'observed-hse-full-blocks-20261114.json').read_text())['records']
CASES = {item['block']['anchor']: item for item in CAPTURE}


def source_row(anchor):
    item = CASES[anchor]
    with patch('hse_alumni.blocks', return_value=[copy.deepcopy(item['block'])]):
        row, = hse_alumni.parse_catalog('', item['observed_at'])
    validate_offer(row)
    return row


def retained(row):
    source_row = stored_input({
        'schema_version': 2, 'run_id': '43612232710:1', 'observed_at': row['observed_at'],
        'records': [row], 'sources': [{
            'source_id': 'hse_alumni', 'name': row['program'], 'root': hse_alumni.ROOT,
            'status': 'ok', 'normalized': 1, 'discovered': 1, 'failed': 0,
            'coverage': 'complete_observed_public_native_block', 'region': None,
            'errors': [], 'observed_at': row['observed_at'],
        }],
    })
    return make_input(source_row)


def projected(anchor):
    return normalize_record(retained(source_row(anchor)), as_of='2026-11-14')


class ObservedHseFullBlockInstructions(unittest.TestCase):
    def test_complete_native_mnogolososya_source_has_only_two_offer_rates(self):
        row = source_row('mnogolososya')
        self.assertEqual([(r['value'], r['unit']) for r in row['rates']],
                         [('10', 'percent'), ('20', 'percent')])
        headline = CASES['mnogolososya']['block']['body'].splitlines()[1]
        self.assertTrue(all(rate['evidence'] == headline for rate in row['rates']))
        self.assertIn('Как воспользоваться скидкой 10%?', row['benefit_text'])
        self.assertIn('Введите промокод VYSHKA20 получите скидку 20%', row['benefit_text'])

    def test_common_model_does_not_reintroduce_instruction_rates(self):
        n = projected('mnogolososya')
        self.assertEqual([(b['kind'], b['value'], b['scope'].get('purchase_stage')) for b in n['benefits']],
                         [('discount', '10', 'repeat'), ('discount', '20', 'first')])
        self.assertEqual([(c['value'], c['scope'].get('purchase_stage')) for c in n['codes']],
                         [('VYSHKA10', 'repeat'), ('VYSHKA20', 'first')])

    def test_each_discount_keeps_its_full_headed_instruction_block(self):
        n = projected('mnogolososya')
        global_rules, = [c for c in n['conditions'] if c['kind'] == 'owned_partner_rules']
        instructions = [c for c in n['conditions'] if c['kind'] == 'activation_step']
        self.assertEqual(len(instructions), 2)
        by_stage = {c['scope']['purchase_stage']: c for c in instructions}
        repeat = by_stage['repeat']['evidence']['text']
        first = by_stage['first']['evidence']['text']
        self.assertIn('Сделайте заказ от 3000 ₽', repeat)
        self.assertIn('не более 350 ₽', repeat)
        self.assertIn('VYSHKA10', repeat)
        self.assertNotIn('900', repeat)
        self.assertNotIn('VYSHKA20', repeat)
        self.assertIn('Сделайте заказ от 900₽', first)
        self.assertIn('VYSHKA20', first)
        self.assertNotIn('3000', first)
        self.assertNotIn('350', first)
        self.assertNotIn('VYSHKA10', first)
        for benefit in n['benefits']:
            stage = benefit['scope']['purchase_stage']
            self.assertEqual(set(benefit['condition_ids']), {global_rules['id'], by_stage[stage]['id']})
            self.assertEqual(benefit['condition_linkage'], 'full_owned_record_rules')

    def test_real_unrelated_equal_rates_and_month_component_are_preserved(self):
        self.assertEqual([(b['value'], b['qualifier']) for b in projected('beup')['benefits']],
                         [('10', 'exact'), ('20', 'exact'), ('20', 'up_to')])
        sailing = projected('silavetra')
        self.assertEqual([b['value'] for b in sailing['benefits']], ['10', '10', '20'])
        self.assertIn('августе', sailing['benefits'][-1]['scope']['calendar_constraint_text'])

    def test_instruction_excerpt_without_a_separate_offer_is_not_discarded(self):
        body = CASES['mnogolososya']['block']['body']
        lines = [line for line in body.splitlines()
                 if line.startswith(('Как воспользоваться скидкой', 'Введите промокод'))]
        self.assertEqual(len(lines), 4)
        for line in lines:
            with self.subTest(line=line):
                self.assertEqual(len(hse_alumni.hse_rates(line)), 1)

    def test_all_58_full_native_blocks_keep_source_common_rate_parity_and_originals(self):
        self.assertEqual(len(CASES), 58)
        for anchor, item in CASES.items():
            with self.subTest(anchor=anchor):
                original = copy.deepcopy(item)
                row = source_row(anchor)
                raw = retained(row)
                raw_before = copy.deepcopy(raw)
                n = normalize_record(raw, as_of='2026-11-14')
                self.assertEqual(item, original)
                self.assertEqual(raw, raw_before)
                self.assertEqual(n['raw'], raw_before)
                self.assertEqual(row['details']['public_catalog_block'], original['block'])
                self.assertEqual([(r['kind'], r['value'], r['unit'], r['qualifier']) for r in row['rates']],
                                 [(b['kind'], b['value'], b['unit'], b['qualifier']) for b in n['benefits']])


if __name__ == '__main__':
    unittest.main()
