"""Original collector evidence must survive target discovery, merging and reload."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import merchant_queue as q


def record(name='Independent merchant', native='731', offer='Скидка 17%'):
    return {'source_id': 'example_public', 'native_id': native,
            'partner_name': name, 'program': 'Public programme',
            'source_url': 'https://example.org/benefits', 'benefit_url': None,
            'link_kind': 'page_block', 'locator': 'public benefit id=' + native,
            'record_kind': 'partner_offer', 'observed_at': '2026-10-31T09:00:00Z',
            'benefit_text': offer, 'conditions_text': 'Полные исходные условия.',
            'redemption_text': 'Бронирование через консьерж-сервис.',
            'details': {'public_item': {'id': int(native), 'name': name,
                'offer': offer, 'description': '<p>Полные исходные условия.</p>',
                'enabled': True, 'unknown_source_field': ['retain', {'tail': 19}]}}}


class EvidenceDiscoveryTests(unittest.TestCase):
    def test_original_record_and_unknown_nested_fields_reach_durable_target(self):
        original = record()
        target = q.discover_targets({'records': [original]}, {}, {})[0]
        self.assertEqual(target.get('source_records'), [original],
                         'Discovery discarded the existing offer instead of passing original evidence')
        original['details']['public_item']['description'] = 'mutated later'
        self.assertEqual(target['source_records'][0]['details']['public_item']['description'],
                         '<p>Полные исходные условия.</p>')
        state = q.new_state()
        q.merge_targets(state, [target])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            q.write_state(path, state)
            restored = q.read_state(path)
        self.assertEqual(restored['items'][target['id']]['target']['source_records'][0]
                         ['details']['public_item']['unknown_source_field'], ['retain', {'tail': 19}])

    def test_registry_seed_cannot_overwrite_catalogue_evidence_and_siblings_are_kept(self):
        first = record()
        second = record(native='732', offer='Подарок по предварительному бронированию')
        seed = {'seed': {'url': first['source_url'], 'partner': first['partner_name'],
                         'program': first['program']}}
        targets = q.discover_targets({'records': [first, second, copy.deepcopy(first)]}, seed, {})
        self.assertEqual(len(targets), 1)
        self.assertEqual([r['native_id'] for r in targets[0].get('source_records', [])], ['731', '732'])

    def test_different_programme_never_receives_neighbour_record(self):
        first = record()
        neighbour = {**record(native='742'), 'program': 'Different programme'}
        targets = q.discover_targets({'records': [first, neighbour]}, {}, {})
        self.assertEqual(len(targets), 2)
        for target in targets:
            self.assertEqual(len(target.get('source_records', [])), 1)
            self.assertEqual(target['source_records'][0]['program'], target['program'])

    def test_registry_only_refresh_does_not_erase_saved_original_record(self):
        first = record()
        targets = q.discover_targets({'records': [first]}, {}, {})
        state = q.new_state()
        q.merge_targets(state, targets)
        seeds = q.discover_targets(None, {'seed': {'url': first['source_url'],
            'partner': first['partner_name'], 'program': first['program']}}, {})
        q.merge_targets(state, seeds)
        self.assertEqual(state['items'][targets[0]['id']]['target'].get('source_records'), [first])


if __name__ == '__main__':
    unittest.main()
