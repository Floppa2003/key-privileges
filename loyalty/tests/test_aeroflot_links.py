"""Published addresses survive company parsing without granting network access."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import aeroflot_import_catalog as m
from normalized import VERSION, canonical_url, content_hash, validate_offer
from test_aeroflot_import import NOW, category_data, json_observation, partner
from sheets_normalized import prepare
from unified_inputs import HEADERS, inputs_from_tables
from unified_normalization import INPUT_TABS, normalize_inputs, normalize_record, pointer


def record(terms):
    obj = partner()
    obj['earnText'] = terms
    preview = m.catalog(json_observation(category_data()))[71]
    return m.detail(json_observation(obj, 'detail'), preview, NOW)


def common_record(r):
    tables = {key: ([[]] * (value[0] - 1) + [[{'value': x} for x in HEADERS[key]]])
              for key, value in INPUT_TABS.items()}
    payload = {'schema_version': 2, 'run_id': '123:1', 'observed_at': r['observed_at'], 'records': [r],
               'sources': [{'source_id': 'aeroflot', 'name': 'test source', 'root': m.ROOT,
                            'status': 'ok', 'discovered': 1, 'normalized': 1, 'failed': 0,
                            'coverage': 'single test record', 'region': None, 'errors': [], 'observed_at': r['observed_at']}]}
    tables['parser_offers'].append([{'value': x} for x in prepare(payload)['parser_offers'][0]])
    raw, _ = inputs_from_tables(tables)
    return normalize_inputs(raw, as_of='2026-09-16')['records'][0]


class PublishedLinkTests(unittest.TestCase):
    def test_email_address_survives_a_generic_link_label(self):
        r = record('<p>Бронируйте по <a href="mailto:booking@hotel.example">электронной почте</a>.</p>')
        self.assertIn('электронной почте', r['conditions_text'])
        self.assertIn('booking@hotel.example', r['conditions_text'])
        self.assertIn({'field': 'earnText', 'label': 'электронной почте',
                       'url': 'mailto:booking@hotel.example', 'kind': 'email', 'target_read': False},
                      r['details']['public_partner']['outgoing_links'])
        validate_offer(r)

    def test_http_application_path_is_preserved_without_an_https_upgrade(self):
        r = record('<a href="http://booking.example/status-match/?tier=gold#apply">по ссылке</a>')
        address = 'http://booking.example/status-match/?tier=gold#apply'
        self.assertIn(address, r['conditions_text'])
        self.assertIn({'field': 'earnText', 'label': 'по ссылке', 'url': address,
                       'kind': 'web', 'target_read': False},
                      r['details']['public_partner']['outgoing_links'])
        # Retaining an advertised address must not widen the network URL policy.
        with self.assertRaises(ValueError):
            canonical_url(address)

    def test_phone_contact_survives_its_anchor_label(self):
        r = record('<a href="tel:+78001234567">по телефону</a>')
        self.assertIn('по телефону', r['conditions_text'])
        self.assertIn('+78001234567', r['conditions_text'])
        self.assertIn({'field': 'earnText', 'label': 'по телефону', 'url': 'tel:+78001234567',
                       'kind': 'phone', 'target_read': False},
                      r['details']['public_partner']['outgoing_links'])

    def test_encoded_contact_preserves_uri_separators_and_displays_the_address(self):
        address = 'mailto:booking%3Foffers@hotel.example'
        self.assertEqual(m.published_link(address), (address, 'email'))
        r = record(f'<a href="{address}">электронной почте</a>')
        self.assertIn('электронной почте', r['conditions_text'])
        self.assertIn('booking?offers@hotel.example', r['conditions_text'])
        self.assertIn(address, [x['url'] for x in r['details']['public_partner']['outgoing_links']])
        validate_offer(r)

    def test_other_company_fields_and_awards_keep_their_link_ownership(self):
        obj = partner()
        obj['description'] = '<a href="http://partner.example/about">О партнёре</a>'
        obj['shortDescription'] = '17 миль — <a href="https://partner.example/short">условия</a>'
        obj['spendText'] = '<a href="mailto:redeem@hotel.example">списание</a>'
        obj['specialOffersText'] = '<a href="https://partner.example/special">спецпредложения</a>'
        obj['awards']['accumulation'][0]['description'] = '<a href="http://partner.example/rate">полный тариф</a>'
        preview = m.catalog(json_observation(category_data()))[71]
        r = m.detail(json_observation(obj, 'detail'), preview, NOW)
        self.assertEqual(r['benefit_text'], '17 миль — условия')
        for value in ('http://partner.example/about', 'redeem@hotel.example',
                      'https://partner.example/short', 'https://partner.example/special', 'http://partner.example/rate'):
            self.assertIn(value, r['conditions_text'])
        pairs = {(x['field'], x['url']) for x in r['details']['public_partner']['outgoing_links']}
        self.assertTrue({('description', 'http://partner.example/about'),
                         ('shortDescription', 'https://partner.example/short'),
                         ('spendText', 'mailto:redeem@hotel.example'),
                         ('specialOffersText', 'https://partner.example/special'),
                         ('awards.accumulation.0.description', 'http://partner.example/rate')} <= pairs)

    def test_visible_address_is_not_duplicated(self):
        r = record('<a href="mailto:booking@hotel.example">booking@hotel.example</a>')
        self.assertEqual(r['conditions_text'].count('booking@hotel.example'), 1)

    def test_percent_encoded_href_cannot_create_rates_at_either_normalization_stage(self):
        address = 'https://partner.example/%D1%81%D0%BA%D0%B8%D0%B4%D0%BA%D0%B0'
        obj = partner()
        obj['shortDescription'] = f'Скидка <a href="{address}">по ссылке</a>'
        preview = m.catalog(json_observation(category_data()))[71]
        r = m.detail(json_observation(obj, 'detail'), preview, NOW)
        self.assertEqual(r['rates'], [])
        self.assertEqual(r['benefit_text'], 'Скидка по ссылке')
        self.assertIn(address, r['conditions_text'])
        n = common_record(r)
        self.assertFalse(any(b['kind'] in ('discount', 'cashback') for b in n['benefits']))
        self.assertIn(address, n['raw']['conditions'])

    def test_uri_numbers_words_and_query_cannot_create_codes_dates_or_common_rates(self):
        address = 'https://partner.example/промокод:FAKE42/discount/25%25?year=2099-12-31&day=Monday'
        r = record('Скидка 12%; промокод REAL10. Не суммируется с акциями. '
                   f'<a href="{address}">Подробности</a>')
        self.assertEqual(r['promo_codes'], ['REAL10'])
        self.assertIsNone(r['valid_from'])
        self.assertIsNone(r['valid_until'])
        self.assertIn(address, r['conditions_text'])
        n = common_record(r)
        self.assertEqual({b['value'] for b in n['benefits'] if b['kind'] == 'discount'}, {'12'})
        self.assertEqual({b['evidence']['path'] for b in n['benefits'] if b['kind'] == 'discount'},
                         {'/details/semantic_fields/conditions'})
        for group in ('benefits','conditions','codes','costs'):
            for item in n[group]:
                self.assertIn(item['evidence']['text'], str(pointer(n['raw'], item['evidence']['path'])))
        self.assertEqual({c['value'] for c in n['codes'] if c['kind'] == 'promo_code'}, {'REAL10'})
        self.assertFalse(any(c['kind'] == 'timing_condition' for c in n['conditions']))
        self.assertIsNone(n['validity']['until'])

    def test_rehashed_semantic_fields_must_match_the_source_projection(self):
        r = record('<a href="https://partner.example/25%25">Подробности</a>')
        r['details'].setdefault('semantic_fields', {})['conditions'] = 'Скидка 99%'
        r['content_sha256'] = content_hash(r)
        with self.assertRaisesRegex(ValueError, 'af_record_semantic'):
            validate_offer(r)

    def test_common_projection_rejects_a_tampered_semantic_cache(self):
        r = record('<a href="https://partner.example/25%25">Подробности</a>')
        raw = common_record(r)['raw']
        raw['details'].setdefault('semantic_fields', {})['conditions'] = 'Скидка 99%'
        with self.assertRaisesRegex(ValueError, 'af_record_semantic'):
            normalize_record(raw, as_of='2026-09-16')

    def test_unsafe_or_credential_like_destinations_are_not_added_to_text_or_links(self):
        addresses = ['http://user:private@hotel.example/',
                     'https://hotel.example/?token=private',
                     'http://hotel.example/?session=private',
                     'javascript:private()', 'data:text/html,private', 'file:///private',
                     'mailto:booking@hotel.example?body=private',
                     'mailto:booking%0d%0aprivate@hotel.example',
                     'tel:+78001234567;private',
                     'http://hotel.example/\nprivate',
                     'https://hotel.example/\\private']
        r = record(' '.join(f'<a href="{address}">Не сохранять адрес</a>' for address in addresses))
        self.assertNotIn('private', r['conditions_text'])
        self.assertNotIn('private', json.dumps(r['details']['public_partner']['outgoing_links']))

    def test_new_link_evidence_cannot_claim_a_read_target(self):
        r = record('<a href="mailto:booking@hotel.example">электронной почте</a>')
        p = r['details']['public_partner']
        p['outgoing_links'][-1]['target_read'] = True
        r['details']['public_partner_sha256'] = m.digest(p)
        r['content_sha256'] = content_hash(r)
        with self.assertRaisesRegex(ValueError, 'af_record_link'):
            validate_offer(r)

    def test_new_contact_cannot_be_downgraded_to_an_unversioned_projection(self):
        original = record('<a href="mailto:booking@hotel.example">электронной почте</a>')
        for remove_kind in (False, True):
            r = copy.deepcopy(original)
            p = r['details']['public_partner']
            p.pop('link_projection_version')
            if remove_kind:
                for link in p['outgoing_links']:
                    link.pop('kind')
            r['details']['public_partner_sha256'] = m.digest(p)
            r['content_sha256'] = content_hash(r)
            with self.subTest(remove_kind=remove_kind):
                with self.assertRaisesRegex(ValueError, 'af_record_link'):
                    validate_offer(r)

    def test_legacy_record_is_valid_without_claiming_recovered_source_data(self):
        # Synthetic record generated by the pre-fix code; no source values are inferred.
        r = json.loads(Path(__file__).with_name('fixtures').joinpath('aeroflot-links-legacy.json').read_text())
        # Retain the legacy source projection inside the current release envelope.
        r['adapter_version'] = VERSION
        r['content_sha256'] = content_hash(r)
        before = copy.deepcopy(r)
        validate_offer(r)
        self.assertEqual(r, before)
        self.assertNotIn('booking@hotel.example', r['conditions_text'])
        self.assertNotIn('booking.example', r['conditions_text'])
        n = common_record(r)
        self.assertNotIn('semantic_fields', n['raw']['details'])
        for item in n['benefits']:
            self.assertIn(item['evidence']['text'], str(pointer(n['raw'], item['evidence']['path'])))

    def test_plain_text_default_still_matches_historical_airline_projection(self):
        self.assertEqual(m.plain('<a href="https://airline.example/rules">Правила</a>'), 'Правила')


if __name__ == '__main__':
    unittest.main()
