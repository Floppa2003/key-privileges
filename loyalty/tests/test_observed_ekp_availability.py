"""Actual source payment deadline and suspension, distinct from a repair date."""
import copy
import json
import unittest
from pathlib import Path

from catalogue_view import record_row
from ekp_catalog import make_record
from test_observed_campaign_periods import AS_OF, retained_without_dates
from unified_normalization import normalize_record


CAPTURE = json.loads(Path(__file__).with_name('fixtures_live').joinpath(
    'observed-ekp-availability-20261114.json').read_text())


def source_record(name):
    source = CAPTURE[name]
    return make_record(source['row'], source['observed_at'], request=source['request'],
                       response_sha=source['response_sha'], observed_total=source['observed_total'],
                       completed_at=source['completed_at'])


def retained_record(name):
    raw = retained_without_dates(source_record(name))
    raw['source_status'] = CAPTURE[name]['retained_source_status']
    raw['original']['fields']['Статус источника']['value'] = raw['source_status']
    raw['details'].pop('source_suspension_evidence', None)
    raw['original']['fields']['Детали JSON']['value'] = json.dumps(raw['details'], ensure_ascii=False)
    return raw


class ObservedEKPAvailability(unittest.TestCase):
    def test_native_sole_cashback_payment_deadline_owns_offer_end(self):
        row = source_record('sirius')
        self.assertEqual((row['valid_from'], row['valid_until']), (None, '2026-11-08'))

    def test_native_box_office_suspension_does_not_use_estimated_repair_date_as_expiry(self):
        row = source_record('philharmonia')
        self.assertEqual(row['source_status'], 'disabled')
        self.assertEqual((row['valid_from'], row['valid_until']), (None, None))
        self.assertIn('продажа билетов в кассе Филармонии для детей и молодежи временно не осуществляется.',
                      row['details']['source_suspension_evidence'])
        self.assertIn('Предположительный срок окончания ремонта: 31.12.2026.', row['conditions_text'])

    def test_retained_records_repair_availability_without_changing_source_snapshot(self):
        for name, reason in (('sirius', 'истёкший срок'),
                             ('philharmonia', 'неактивное предложение источника'),
                             ('library_children', 'неактивное предложение источника'),
                             ('library_bateninskaya', 'неактивное предложение источника')):
            with self.subTest(name=name):
                raw = retained_record(name)
                before = copy.deepcopy(raw)
                n = normalize_record(raw, as_of=AS_OF)
                self.assertEqual(record_row(n, AS_OF), (None, reason))
                if name == 'sirius':
                    self.assertEqual(n['validity']['until'], '2026-11-08')
                    self.assertEqual(n['validity']['status'], 'expired')
                else:
                    self.assertIs(n['availability']['source_enabled'], False)
                    self.assertEqual(n['validity']['status'], 'unknown')
                    later = normalize_record(raw, as_of='2027-01-01')
                    self.assertIs(later['availability']['source_enabled'], False)
                self.assertEqual(raw, before)
                self.assertEqual(n['raw'], before)

    def test_native_library_closures_suspend_their_onsite_services_without_inventing_dates(self):
        for name, literal in (
                ('library_children', 'Временно не работает в связи с капитальным ремонтом.'),
                ('library_bateninskaya', 'Временно не работает в связи с производством работ по капитальному ремонту.')):
            with self.subTest(name=name):
                row = source_record(name)
                self.assertEqual(row['source_status'], 'disabled')
                self.assertEqual(row['details']['source_suspension_evidence'], literal)
                self.assertEqual((row['valid_from'], row['valid_until']), (None, None))

    def test_t2_existing_subscriber_exclusion_does_not_suspend_the_whole_offer(self):
        raw = retained_record('t2_audience_control')
        n = normalize_record(raw, as_of=AS_OF)
        self.assertEqual(source_record('t2_audience_control')['source_status'], 'public_catalog_api_terms')
        self.assertIsNot(n['availability'].get('source_enabled'), False)
        self.assertIn('Предложение недоступно для действующих абонентов t2.', raw['conditions'])

    def test_a_website_problem_with_an_explicit_phone_alternative_does_not_close_the_offer(self):
        raw = retained_record('website_only_control')
        n = normalize_record(raw, as_of=AS_OF)
        self.assertEqual(source_record('website_only_control')['source_status'], 'public_catalog_api_terms')
        self.assertIsNot(n['availability'].get('source_enabled'), False)
        self.assertIn('Сайт компании временно не доступен, обращения можно оставлять по телефону.', raw['conditions'])


if __name__ == '__main__':
    unittest.main()
