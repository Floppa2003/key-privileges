"""Source-to-model regressions. No merchant-name/value whitelist in production."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import merchant_queue as q
import merchant_extract as m
from test_merchant_queue import Clock, HTTP, Response, SCHEMA, EMPTY


def record(native_id='713', name='Unseen partner', **changes):
    value = {'source_id': 'konsierge_public', 'native_id': native_id,
             'partner_name': name, 'program': 'Konsierge — публичные привилегии',
             'source_url': 'https://konsierge.com/benefits', 'record_kind': 'partner_offer',
             'observed_at': '2026-10-30T12:00:00+00:00',
             'locator': 'public benefit id=' + native_id,
             'details': {'public_item': {'id': int(native_id), 'name': name,
                         'offer': 'Особое предложение', 'description': 'Полные условия без пересказа',
                         'rubrics': [{'id': 2}]}}}
    value.update(changes)
    return value


class EvidenceTests(unittest.TestCase):
    def test_catalogue_object_survives_discovery_without_mutating_source(self):
        row = record()
        target = q.discover_targets({'records': [row]}, {}, {})[0]
        self.assertEqual(target.get('source_records'), [row])
        target['source_records'][0]['details']['public_item']['description'] = 'different'
        self.assertEqual(row['details']['public_item']['description'], 'Полные условия без пересказа')

    def test_registry_seed_cannot_shadow_later_source_evidence(self):
        row = record()
        registry = {'seed': {'url': row['source_url'], 'partner': row['partner_name'], 'program': row['program']}}
        target = q.discover_targets({'records': [row]}, registry, {})[0]
        self.assertEqual(target.get('source_records'), [row])
        self.assertEqual(target['source_id'], 'konsierge_public')

    def test_all_distinct_records_for_one_target_are_preserved(self):
        first = record(); second = record('714')
        targets = q.discover_targets({'records': [first, second, copy.deepcopy(first)]}, {}, {})
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].get('source_records'), [first, second])

    def test_missing_catalogue_does_not_erase_saved_evidence(self):
        target = q.discover_targets({'records': [record()]}, {}, {})[0]
        state = q.new_state(); q.merge_targets(state, [target])
        seed = {k:v for k,v in target.items() if k != 'source_records'}
        q.merge_targets(state, [seed])
        self.assertEqual(state['items'][target['id']]['target'].get('source_records'), [record()])

    def test_old_unscoped_negative_requeues_without_erasing_audit_or_good_result(self):
        target = q.discover_targets({'records': [record()]}, {}, {})[0]
        state = q.new_state()
        state['items'][target['id']] = {'target': {k:v for k,v in target.items() if k != 'source_records'},
            'extracted': copy.deepcopy(EMPTY), 'fingerprint': 'old', 'status': 'completed', 'last_checked': 99}
        state['items']['good'] = {'target': {'id':'good'}, 'extracted': {'has_offer':True,'offers':[{}]},
                                  'fingerprint':'good-hash', 'status':'completed'}
        q.merge_targets(state, [target])
        item = state['items'][target['id']]
        self.assertEqual(item['status'], 'needs_source')
        self.assertTrue(item.get('needs_recapture'))
        self.assertEqual(item['extracted'], EMPTY)  # historical response is not deleted
        self.assertEqual(state['items']['good']['fingerprint'], 'good-hash')
        self.assertEqual(q.pending_targets(state)[0]['id'], target['id'])

    def test_explicitly_incomplete_input_is_not_sent_or_cached_as_absence(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); state=q.new_state(); clock=Clock(); client=HTTP([])
            doc={'id':'new_target','target':{'partner':'X','program':'P','as_of':'2026-10-31'},
                 'text':'Navigation and loader','images':[b'png'],
                 'source':{'capture_scope':{'version':1,'target_resolved':False}}}
            result=q.process_documents([doc],state,root/'state.json',root/'out','TEST_SECRET',SCHEMA,'prompt',
                session=client,now=clock.now,sleep=clock.sleep)
            self.assertEqual(client.calls,[])
            self.assertEqual(result['completed'],0)
            self.assertEqual(state['items']['new_target']['status'],'needs_source')
            self.assertNotIn('extracted',state['items']['new_target'])

    def test_cache_cannot_hide_explicit_missing_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); state=q.new_state(); clock=Clock(); client=HTTP([])
            doc={'id':'new_target','target':{'partner':'X','program':'P','as_of':'2026-10-31'},
                 'text':'Loader','images':[b'png'],
                 'source':{'capture_scope':{'version':1,'target_resolved':False}}}
            state['items']['new_target']={'extracted':copy.deepcopy(EMPTY),'fingerprint':q.fingerprint(doc,SCHEMA,'prompt')}
            result=q.process_pool([doc],state,root/'state.json',root/'out',{'orcarouter':'TEST_SECRET'},SCHEMA,'prompt',
                sessions={'orcarouter':client},now=clock.now,sleep=clock.sleep,providers=('orcarouter',))
            self.assertEqual(result['cached'],0)
            self.assertEqual(client.calls,[])
            self.assertIn('new_target',result['pending'])


if __name__ == '__main__': unittest.main()
