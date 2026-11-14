"""An explicit whole-restaurant closure overrides an enabled catalogue card."""
import copy
import hashlib
import html
import json
import tempfile
import unittest
from pathlib import Path

from catalogue_view import record_row
from konsierge_catalog import ROOT, parse_capture
from test_observed_campaign_periods import AS_OF, retained_without_dates
from unified_normalization import normalize_record


CAPTURE = json.loads(Path(__file__).with_name('fixtures_live').joinpath(
    'observed-konsierge-closure-20261114.json').read_text())


def source_record(name):
    source = CAPTURE[name]
    item = source['item']
    body = ('<qy-benefit-teaser><div class="BenefitTeaser-Title">'
            + html.escape(item['name']) + '</div><div class="BenefitTeaser-OfferText">'
            + html.escape(item['offer']) + '</div></qy-benefit-teaser>')
    report = {
        'observed_at': source['observed_at'], 'one_off_public_ui_inspection': True,
        'source_account_login': False, 'direct_api_requests': 0,
        'credential_values_read_or_replayed': False, 'published': False, 'errors': [],
        'rubrics': [{'id': c['id'], 'name': c['name']} for c in source['categories']],
        'catalogues': [], 'network_pages': [],
    }
    with tempfile.TemporaryDirectory() as folder:
        for category in [None, *source['categories']]:
            rid = category['id'] if category else None
            filename = f'rubric-{rid}.html' if rid else 'all.html'
            (Path(folder) / filename).write_text(body, encoding='utf8')
            report['catalogues'].append({
                'url': category['url'] if category else ROOT, 'file': filename,
                'sha256': hashlib.sha256(body.encode()).hexdigest(),
                'cards': [{'name': item['name'], 'offer': item['offer']}],
                'native_item_count': 1, 'native_pages': 1,
                'scroll_stop': 'native_last_page_and_count',
            })
            report['network_pages'].append({
                'path': '/api/client/v1/benefits', 'status': 200,
                'query': {'page': '1', 'per': '12', **({'rubric_id': str(rid)} if rid else {})},
                'received_at': source['observed_at'], 'items': [copy.deepcopy(item)],
                'page': {'current_page': 1, 'total_pages': 1, 'total_count': 1,
                         'count': 1, 'next_page': None},
            })
        return parse_capture(report, folder, source['source_run'])['records'][0]


class ObservedKonsiergeClosure(unittest.TestCase):
    def test_native_whole_restaurant_closure_suspends_offer_without_guessing_reopening(self):
        row = source_record('closed')
        self.assertEqual(row['source_status'], 'disabled')
        self.assertEqual((row['valid_from'], row['valid_until']), (None, None))
        self.assertTrue(row['details']['public_item']['enabled'])

    def test_retained_closure_overrides_enabled_flag_and_is_excluded_by_reader(self):
        raw = retained_without_dates(source_record('closed'))
        raw['source_status'] = 'public_catalogue_terms_unverified_eligibility'
        raw['original']['fields']['Статус источника']['value'] = raw['source_status']
        before = copy.deepcopy(raw)
        n = normalize_record(raw, as_of=AS_OF)
        self.assertIs(n['availability']['source_enabled'], False)
        self.assertEqual(n['availability']['source_suspension_evidence'],
                         'Ресторан закрыт до нового летнего сезона.')
        self.assertEqual(n['validity']['status'], 'unknown')
        self.assertEqual(record_row(n, AS_OF), (None, 'неактивное предложение источника'))
        self.assertEqual(raw, before)
        self.assertEqual(n['raw'], before)

    def test_access_to_closed_events_is_not_a_closure(self):
        row = source_record('closed_events_control')
        self.assertIn('Закрытые дегустации', row['conditions_text'])
        self.assertEqual(row['source_status'], 'public_catalogue_terms_unverified_eligibility')
        n = normalize_record(retained_without_dates(row), as_of=AS_OF)
        self.assertIs(n['availability']['source_enabled'], True)
        self.assertNotIn('source_suspension_evidence', n['availability'])


if __name__ == '__main__':
    unittest.main()
