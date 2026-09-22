"""Counterfactual changes to genuine public DOM; never simulated live observations."""
import copy
import json
import sys
import unittest
from pathlib import Path
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parents[1]))
import mantera_partners as partners
import mantera_source as mantera
import mantera_hotel as hotel
from test_public_reward_sources import html
from test_sync import FakeSheets
from test_lifecycle_pipeline import reader
from sheets_normalized import SCHEMAS, prepare, NormalizedSheets
from source_lifecycle import reconcile_rows, validate_inventories, health_summary

OLD = '2026-09-22T18:00:00+00:00'
NEW = '2026-09-23T18:00:00+00:00'
RESTORED = '2026-09-24T18:00:00+00:00'
REMOVED = 'Риксос Красная Поляна Сочи 5*'


def bundle(at=OLD, remove=None, resort_raw=None):
    raw = html('mantera-partners.html')
    if remove:
        soup = BeautifulSoup(raw, 'html.parser')
        listing = soup.select_one('.accordion__item-content ul')
        node = next(n for n in listing.find_all('li', recursive=False)
                    if partners.compact(n.get_text()) == remove)
        node.decompose()
        raw = str(soup)
    rows, meta = partners.parse_pair(raw, resort_raw or html('mantera-redemption.html'), at)
    rows = mantera.parse(html('mantera-faq.html'), at) + [hotel.parse(html('mantera-congress.html'), at)] + rows
    report = dict(source_id=mantera.SOURCE, name=mantera.PROGRAM, root=mantera.URL,
                  status='ok', normalized=len(rows), discovered=len(rows), failed=0,
                  coverage='counterfactual_named_roster', region=None, errors=[],
                  observed_at=at, mantera_public_inventory=meta)
    return dict(schema_version=2, run_id='test-only:'+at[:10], observed_at=at,
                sources=[report], records=rows)


def memory_and_client(payload):
    rows = prepare(payload)['parser_offers']
    memory = FakeSheets()
    memory.tabs['parser_offers'] = {
        'properties': {'title':'parser_offers', 'sheetId':30,
                       'gridProperties': {'rowCount':5000, 'columnCount':26}},
        'values': [SCHEMAS['parser_offers']+['Ручной комментарий']]
                  + [r+['Личная заметка '+r[0][:8]] for r in rows],
    }
    client = NormalizedSheets('test-only-sheet', 'test-only-token')
    client.request = memory.request
    return memory, client


def apply(memory, client, payload):
    before = copy.deepcopy(memory.tabs['parser_offers']['values'])
    rows = reconcile_rows(payload, before, prepare(payload)['parser_offers'])
    client.upsert('parser_offers', rows, expected_before=[r[:25] for r in before])
    return rows


class ManteraLifecycle(unittest.TestCase):
    def setUp(self):
        self.original = bundle()
        self.before = [SCHEMAS['parser_offers']] + prepare(self.original)['parser_offers']
        self.removed_id = partners.record_id(partners.native_id(REMOVED))

    def test_complete_roster_absence_withholds_one_hotel_without_deleting_it(self):
        memory, client = memory_and_client(self.original)
        before = copy.deepcopy(memory.tabs['parser_offers']['values'])
        newer = bundle(NEW, remove=REMOVED)
        self.assertTrue(health_summary(newer)[0]['healthy'])
        changes = apply(memory, client, newer)
        held = next(r for r in changes if r[0] == self.removed_id)
        original = next(r for r in before[1:] if r[0] == self.removed_id)
        self.assertEqual(held[:20], original[:20])
        self.assertEqual(held[21:25], original[21:25])
        state = json.loads(held[20])['_lifecycle']
        self.assertEqual(state['reason'], 'not_in_complete_inventory')
        self.assertEqual(state['checked_at'], NEW)
        self.assertEqual(state['last_offer_observed_at'], OLD)
        self.assertIsNone(reader(held, NEW[:10])[0])
        after = memory.tabs['parser_offers']['values']
        self.assertEqual(len(after), len(before))
        self.assertEqual([r[0] for r in after], [r[0] for r in before])
        self.assertEqual([r[25:] for r in after], [r[25:] for r in before])
        self.assertEqual(sum(reader(r, NEW[:10])[0] is not None for r in after[1:]), 15)

    def test_fresh_return_restores_same_row_and_manual_note(self):
        memory, client = memory_and_client(self.original)
        positions = [r[0] for r in memory.tabs['parser_offers']['values']]
        notes = [r[25:] for r in memory.tabs['parser_offers']['values']]
        apply(memory, client, bundle(NEW, remove=REMOVED))
        apply(memory, client, bundle(RESTORED))
        after = memory.tabs['parser_offers']['values']
        self.assertEqual([r[0] for r in after], positions)
        self.assertEqual([r[25:] for r in after], notes)
        row = next(r for r in after if r[0] == self.removed_id)
        self.assertNotIn('_lifecycle', json.loads(row[20]))
        self.assertIsNone(reader(row, RESTORED[:10])[1])
        self.assertEqual(row[22], RESTORED)

    def test_partial_component_keeps_old_hotels_and_refreshes_only_successes(self):
        memory, client = memory_and_client(self.original)
        partial = bundle(NEW)
        partial['records'] = partial['records'][:6]
        r = partial['sources'][0]
        r.update(status='partial', normalized=6, discovered=7, failed=1,
                 errors=[{'phase':'public_partner_inventory','reason':'http_403'}])
        r.pop('mantera_public_inventory')
        changes = apply(memory, client, partial)
        self.assertEqual(len(changes), 6)
        after = memory.tabs['parser_offers']['values'][1:]
        self.assertEqual([row[22] for row in after], [NEW]*6+[OLD]*10)
        self.assertFalse(any('_lifecycle' in json.loads(row[20]) for row in after))
        self.assertFalse(health_summary(partial)[0]['healthy'])

    def test_incomplete_or_untrusted_snapshots_cannot_withhold(self):
        for mode in ('failed','partial','errors','missing','empty_names','duplicate_names',
                     'wrong_ids','missing_record','wrong_source','wrong_evidence'):
            with self.subTest(mode=mode):
                b = bundle(NEW, remove=REMOVED)
                report = b['sources'][0]
                meta = report['mantera_public_inventory']
                if mode in ('failed','partial'): report['status'] = mode
                elif mode == 'errors': report['errors'] = [{'reason':'timeout'}]
                elif mode == 'missing': report.pop('mantera_public_inventory')
                elif mode == 'empty_names': meta['names'] = []
                elif mode == 'duplicate_names': meta['names'].append(meta['names'][0])
                elif mode == 'wrong_ids': meta['record_ids'] = [self.removed_id]
                elif mode == 'missing_record': b['records'].pop(); report['normalized'] -= 1
                elif mode == 'wrong_source': meta['roster_url'] = 'https://example.invalid/'
                else: b['records'][-1]['details']['public_reward_evidence']['name'] = REMOVED
                self.assertNotIn(mantera.SOURCE, validate_inventories(b))
                self.assertEqual(reconcile_rows(b, self.before, []), [])

    def test_foreign_batch_timestamp_cannot_authorize_holds(self):
        b = bundle(NEW, remove=REMOVED)
        b['observed_at'] = RESTORED
        with self.assertRaisesRegex(ValueError, 'inventory_observation_mismatch'):
            validate_inventories(b)

    def test_only_roster_derived_records_are_reconciled(self):
        b = bundle(NEW, remove=partners.CONGRESS)
        # The roster no longer names Congress, but its own hotel page still does.
        changes = reconcile_rows(b, self.before, prepare(b)['parser_offers'])
        self.assertEqual(len(changes), 16)
        self.assertFalse(any('_lifecycle' in json.loads(r[20]) for r in changes))
        base = self.before[:7]
        self.assertEqual(reconcile_rows(bundle(NEW, remove=REMOVED), base, []), [])

    def test_older_inventory_cannot_overwrite_a_newer_hotel_or_hold(self):
        memory, client = memory_and_client(bundle(RESTORED))
        before = copy.deepcopy(memory.tabs['parser_offers']['values'])
        self.assertEqual(apply(memory, client, bundle(NEW, remove=REMOVED)), [])
        self.assertEqual(memory.tabs['parser_offers']['values'], before)
        memory, client = memory_and_client(self.original)
        apply(memory, client, bundle(RESTORED, remove=REMOVED))
        held_before = copy.deepcopy(memory.tabs['parser_offers']['values'])
        self.assertEqual(apply(memory, client, bundle(NEW)), [])
        self.assertEqual(memory.tabs['parser_offers']['values'], held_before)

    def test_corrupted_old_identity_cannot_withhold_another_hotel(self):
        target = next(r for r in self.before if r[0] == self.removed_id)
        for mode in ('id','source_url','evidence_url','name'):
            with self.subTest(mode=mode):
                row = copy.deepcopy(target)
                if mode == 'id': row[0] = 'a'*64
                elif mode == 'source_url': row[17] = 'https://example.invalid/'
                else:
                    d = json.loads(row[20])
                    d['public_reward_evidence']['url' if mode == 'evidence_url' else 'name'] = 'bad'
                    row[20] = json.dumps(d)
                with self.assertRaisesRegex(ValueError, 'lifecycle_stored_'):
                    reconcile_rows(bundle(NEW, remove=REMOVED), [self.before[0],row], [])

    def test_changed_spending_rights_replace_old_components_not_whole_hotel(self):
        raw = html('mantera-redemption.html').replace('Долина 960, Кортьярд и Марриотт',
                                                     'Долина 960 и Марриотт')
        newer = bundle(NEW, resort_raw=raw)
        memory, client = memory_and_client(self.original)
        apply(memory, client, newer)
        full_name = partners.REDEMPTION_ALIASES['Кортьярд']
        row = next(r for r in memory.tabs['parser_offers']['values'][1:] if r[2] == full_name)
        result, reason = reader(row, NEW[:10])
        self.assertIsNone(reason)
        self.assertNotIn('Оплата накопленными бонусами', result[2])
        self.assertIn('отдельно не подтверждена', result[5])
        self.assertNotIn('_lifecycle', json.loads(row[20]))

    def test_mixed_page_versions_cannot_authorize_a_complete_inventory(self):
        from public_reward_projection import make_record
        b = bundle(NEW, remove=REMOVED)
        row = b['records'][-1]
        evidence = copy.deepcopy(row['details']['public_reward_evidence'])
        evidence['resort']['page_sha256'] = 'f'*64
        b['records'][-1] = make_record(mantera.SOURCE, evidence, NEW)
        # Each record is valid by itself; the pair was not one observed snapshot.
        self.assertFalse(health_summary(b)[0]['healthy'])
        self.assertNotIn(mantera.SOURCE, validate_inventories(b))
        self.assertEqual(reconcile_rows(b, self.before, []), [])

    def test_rehashed_fields_without_matching_record_hash_are_unhealthy(self):
        b = bundle(NEW, remove=REMOVED)
        b['records'][-1]['content_sha256'] = '0'*64
        self.assertFalse(health_summary(b)[0]['healthy'])
        self.assertEqual(reconcile_rows(b, self.before, []), [])

    def test_missing_card_then_failed_fetch_keeps_the_existing_hold(self):
        memory, client = memory_and_client(self.original)
        apply(memory, client, bundle(NEW, remove=REMOVED))
        before = copy.deepcopy(memory.tabs['parser_offers']['values'])
        failed = bundle(RESTORED)
        failed['records'] = []
        failed['sources'][0].update(status='failed', errors=[{'reason':'http_403'}],
                                    normalized=0, discovered=0, failed=1)
        failed['sources'][0].pop('mantera_public_inventory')
        self.assertEqual(apply(memory, client, failed), [])
        self.assertEqual(memory.tabs['parser_offers']['values'], before)
        row = next(r for r in before[1:] if r[0] == self.removed_id)
        self.assertIn('не подтвердил', reader(row, RESTORED[:10])[1])

    def test_unchanged_real_shape_yields_no_hold_and_keeps_existing_ids(self):
        b = bundle(NEW)
        incoming = prepare(b)['parser_offers']
        self.assertEqual(reconcile_rows(b,self.before,incoming),incoming)
        self.assertEqual({r[0] for r in incoming},{r[0] for r in self.before[1:]})


if __name__ == '__main__':
    unittest.main()
