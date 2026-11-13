"""Source status and campaign dates through adapters, storage and reader output."""
import copy
import hashlib
import html
import json
import tempfile
import unittest
from pathlib import Path

from adapters import mir_detail
from catalogue_view import build_catalogue
from konsierge_catalog import ROOT, parse_capture
from sheets_normalized import SCHEMAS, prepare
from unified_normalization import make_input, normalize_record


OBSERVED = '2026-11-13T12:00:00+00:00'
AS_OF = '2026-11-13'


def stored_input(bundle):
    row = prepare(bundle)['parser_offers'][0]
    return {'id': row[0], 'origin': 'parser_offers', 'row': 2,
            'fields': {name: {'value': value}
                       for name, value in zip(SCHEMAS['parser_offers'], row)}}


def mir_input(**changes):
    promo = {
        'xml_id': 'synthetic-source-status', 'url': '/promo/synthetic-status/',
        'name': 'Синтетический партнёр', 'owner': {'name': 'Синтетический партнёр'},
        'desc': {'number': {'PREFIX': 'Кешбэк ', 'AMOUNT': '8%'},
                 'text': 'за оплату через СБП'},
        'startDate': '01.11.2026', 'endDate': '30.11.2026', 'status': 'active',
        'promoIsCancelled': False, 'promoIsFinished': False, 'promoIsStarted': True,
        'prizeIsSuspended': False, 'promoBadges': [{'text': 'СБП'}],
        'templates': [{'templateName': 'conditions', 'templateTitle': 'Условия',
                       'templateText': 'Максимальный кешбэк 700 ₽ в месяц.'}],
        'freeFormBlock': 'Оплатите через СБП.',
    }
    promo.update(changes)
    rows = mir_detail({'data': {'content': {'promoDetail': {'promo': {'promoAction': promo}}}}},
                      'https://vamprivet.ru/promo/synthetic-status/', OBSERVED)
    return stored_input({
        'schema_version': 2, 'run_id': '123:1', 'observed_at': OBSERVED, 'records': rows,
        'sources': [{'source_id': 'mir', 'name': 'Мир', 'root': 'https://vamprivet.ru/',
                     'status': 'ok', 'normalized': 1, 'discovered': 1, 'failed': 0,
                     'coverage': 'synthetic_source_record', 'region': None,
                     'errors': [], 'observed_at': OBSERVED}],
    })


def konsierge_input(description, *, offer='Скидка 17%', enabled=True, expiry=None):
    item = {'id': 1, 'name': 'Синтетический партнёр', 'offer': offer,
            'description': description, 'enabled': enabled, 'link': None,
            'date_of_expiry': expiry, 'date_of_release': None,
            'created_at': None, 'updated_at': None, 'rubrics': [{'id': 1}]}
    body = ('<qy-benefit-teaser><div class="BenefitTeaser-Title">Синтетический партнёр</div>'
            '<div class="BenefitTeaser-OfferText">' + html.escape(offer)
            + '</div></qy-benefit-teaser>')
    report = {
        'observed_at': OBSERVED, 'one_off_public_ui_inspection': True,
        'source_account_login': False, 'direct_api_requests': 0,
        'credential_values_read_or_replayed': False, 'published': False, 'errors': [],
        'rubrics': [{'id': 1, 'name': 'Услуги'}], 'catalogues': [], 'network_pages': [],
    }
    with tempfile.TemporaryDirectory() as folder:
        for rid, filename in ((None, 'all.html'), (1, 'rubric-1.html')):
            (Path(folder) / filename).write_text(body, encoding='utf8')
            report['catalogues'].append({
                'url': ROOT + ('?rubric_id=1' if rid else ''), 'file': filename,
                'sha256': hashlib.sha256(body.encode()).hexdigest(),
                'cards': [{'name': item['name'], 'offer': offer}], 'native_item_count': 1,
                'native_pages': 1, 'scroll_stop': 'native_last_page_and_count',
            })
            report['network_pages'].append({
                'path': '/api/client/v1/benefits', 'status': 200,
                'query': {'page': '1', 'per': '12', **({'rubric_id': '1'} if rid else {})},
                'received_at': OBSERVED, 'items': [copy.deepcopy(item)],
                'page': {'current_page': 1, 'total_pages': 1, 'total_count': 1,
                         'count': 1, 'next_page': None},
            })
        return stored_input(parse_capture(report, folder, '123:1'))


def normalized(source, *, as_of=AS_OF):
    return normalize_record(make_input(source), as_of=as_of)


class SourceAvailabilityTests(unittest.TestCase):
    def test_mir_cancellation_and_completion_override_future_schedule(self):
        for changes, status in (
            ({'promoIsCancelled': True}, 'cancelled'),
            ({'promoIsFinished': True}, 'finished'),
            ({'status': 'disabled'}, 'disabled'),
        ):
            with self.subTest(status=status):
                n = normalized(mir_input(**changes))
                before = copy.deepcopy(n)
                self.assertEqual(n['provenance']['source_status'], status)
                self.assertEqual(n['validity']['until'], '2026-11-30')
                self.assertEqual(n['validity']['status'], 'within_stated_period')
                result = build_catalogue([n], as_of=AS_OF)
                self.assertEqual(result['rows'], [])
                self.assertEqual(result['removed'], [
                    {'id': n['id'], 'reason': 'неактивное предложение источника'}])
                self.assertEqual(n, before)

    def test_active_unknown_and_unrelated_mir_flags_do_not_mean_disabled(self):
        for changes in (
            {'status': 'active'}, {'status': 'unknown'}, {'status': 'false'},
            {'status': 'finished_catalogue_refresh'}, {'status': 'False'},
            {'promoIsStarted': False}, {'prizeIsSuspended': True}, {'enabled': False},
        ):
            with self.subTest(changes=changes):
                n = normalized(mir_input(**changes))
                result = build_catalogue([n], as_of=AS_OF)
                self.assertEqual(len(result['rows']), 1)
                self.assertEqual(result['rows'][0][6], '2026-11-01 — 2026-11-30')

    def test_konsierge_disabled_is_excluded_without_erasing_source(self):
        source = konsierge_input('Срок действия предложения: до 30.11.2026.', enabled=False)
        n = normalized(source)
        before = copy.deepcopy(n)
        self.assertIs(n['availability']['source_enabled'], False)
        self.assertEqual(n['validity']['until'], '2026-11-30')
        result = build_catalogue([n], as_of=AS_OF)
        self.assertEqual(result['rows'], [])
        self.assertEqual(result['removed'], [
            {'id': n['id'], 'reason': 'неактивное предложение источника'}])
        self.assertEqual(n, before)

    def test_only_boolean_source_enabled_false_is_disabled(self):
        for value in (True, None, '', 'false', 'False', 0, [], {}):
            with self.subTest(value=value):
                n = normalized(mir_input())
                n['availability']['source_enabled'] = value
                self.assertEqual(len(build_catalogue([n], as_of=AS_OF)['rows']), 1)


class KonsiergeCampaignDateTests(unittest.TestCase):
    def test_registration_booking_and_payment_dates_are_conditions(self):
        for body in (
            'Скидка 17% для клиентов, зарегистрировавшихся до 01.11.2026.',
            'Скидка 17% предоставляется при бронировании до 03.11.2026.',
            'Скидка 17% при оплате до 05.11.2026.',
            'Срок оплаты заказа: до 07.11.2026. Скидка 17%.',
            'Акция для клиентов, зарегистрировавшихся до 09.11.2026.',
            'Условия акции: зарегистрируйтесь до 10.11.2026.',
            'Акция действует для клиентов, зарегистрировавшихся до 11.11.2026.',
            'Предложение действительно при бронировании до 06.11.2026.',
        ):
            with self.subTest(body=body):
                n = normalized(konsierge_input(body))
                self.assertIsNone(n['validity']['until'])
                self.assertEqual(n['validity']['status'], 'unknown')
                self.assertIn(body, n['conditions'][0]['evidence']['text'])
                result = build_catalogue([n], as_of=AS_OF)
                self.assertEqual(len(result['rows']), 1)
                self.assertEqual(result['rows'][0][6], '')
                self.assertEqual(result['rows'][0][12], 'Срок не указан')

    def test_explicit_campaign_end_survives_an_unrelated_earlier_date(self):
        for body, end, status in (
            ('Срок действия предложения: до 12.11.2026.\n'
             'Скидка 17% для клиентов, зарегистрировавшихся до 01.11.2026.',
             '2026-11-12', 'expired'),
            ('Скидка 17% для клиентов, зарегистрировавшихся до 02.11.2026. '
             'Срок действия предложения: до 15.11.2026.',
             '2026-11-15', 'within_stated_period'),
            ('Оплатите заказ до 05.11.2026. Предложение действительно до 18.11.2026.',
             '2026-11-18', 'within_stated_period'),
        ):
            with self.subTest(body=body):
                n = normalized(konsierge_input(body))
                self.assertEqual(n['validity']['until'], end)
                self.assertEqual(n['validity']['status'], status)
                result = build_catalogue([n], as_of=AS_OF)
                if status == 'expired':
                    self.assertEqual(result['rows'], [])
                else:
                    self.assertEqual(result['rows'][0][6], 'до ' + end)

    def test_explicit_validity_forms_and_customer_date_boundary_are_preserved(self):
        for body, end in (
            ('Срок действия спец предложения до 17.11.2026г', '2026-11-17'),
            ('Сроки предоставления акции: до 18.11.2026г', '2026-11-18'),
            ('Предложение действительно на размещение до 20.11.2026', '2026-11-20'),
            ('Акция действует с 01.11.2026 до 21.11.2026.', '2026-11-21'),
            ('Привилегия действует до 23.11.2026.', '2026-11-23'),
            ('Скидка 17% действует до 24.11.2026.', '2026-11-24'),
        ):
            with self.subTest(body=body):
                source = konsierge_input(body)
                n = normalized(source, as_of=end)
                self.assertEqual(n['validity']['until'], end)
                self.assertEqual(n['validity']['status'], 'within_stated_period')
                self.assertEqual(build_catalogue([n], as_of=end)['rows'][0][6], 'до ' + end)
        source = konsierge_input('Срок действия предложения: до 13.11.2026.')
        self.assertEqual(normalized(source)['validity']['status'], 'within_stated_period')
        self.assertEqual(normalized(source, as_of='2026-11-14')['validity']['status'], 'expired')

    def test_offer_label_can_state_the_campaign_end(self):
        n = normalized(konsierge_input(
            'Для клиентов, зарегистрировавшихся до 01.11.2026.',
            offer='Скидка 23%. Предложение действительно до 19.11.2026.'))
        self.assertEqual(n['validity']['until'], '2026-11-19')
        self.assertEqual(n['benefits'][0]['value'], '23')
        self.assertEqual(build_catalogue([n], as_of=AS_OF)['rows'][0][6], 'до 2026-11-19')

    def test_one_component_end_does_not_expire_other_privileges(self):
        body = ('Скидка 12% на ужины действует до 04.11.2026. '
                'Бесплатная парковка предоставляется постоянно.')
        n = normalized(konsierge_input(body, offer='Привилегия'))
        self.assertIsNone(n['validity']['until'])
        self.assertIn(body, n['conditions'][0]['evidence']['text'])
        self.assertEqual(len(build_catalogue([n], as_of=AS_OF)['rows']), 1)

    def test_date_of_scoped_extra_campaign_does_not_expire_headline_discount(self):
        for body in (
            'Скидка 17% предоставляется постоянно. Дополнительная акция действует до 04.11.2026.',
            'Скидка 17% предоставляется постоянно. Для спа привилегия действует до 06.11.2026.',
            'Скидка 17% предоставляется постоянно. В ресторане предложение действительно до 08.11.2026.',
        ):
            with self.subTest(body=body):
                n = normalized(konsierge_input(body))
                self.assertIsNone(n['validity']['until'])
                self.assertEqual(n['benefits'][0]['value'], '17')
                self.assertEqual(len(build_catalogue([n], as_of=AS_OF)['rows']), 1)

    def test_scope_after_end_date_does_not_expire_a_live_sibling(self):
        for offer, body, expected_rate, live_clause in (
            ('Скидка 17%',
             'Скидка 17% действует до 01.11.2026 только на СПА. '
             'Скидка 17% в ресторане действует постоянно.',
             '17', 'Скидка 17% в ресторане действует постоянно.'),
            ('Скидка 23,5%',
             'Скидка 23,5% действует до 04.11.2026 исключительно на массаж. '
             'Скидка 23,5% на меню действует постоянно.',
             '23.5', 'Скидка 23,5% на меню действует постоянно.'),
            ('Скидка 17%',
             'Скидка 17% действует до 03.11.2026 включительно только на завтраки. '
             'Скидка 17% на ужины действует постоянно.',
             '17', 'Скидка 17% на ужины действует постоянно.'),
            ('Скидка 23,5%',
             'Скидка 23,5% действует до 06.11.2026 г. только в салоне. '
             'Скидка 23,5% онлайн действует постоянно.',
             '23.5', 'Скидка 23,5% онлайн действует постоянно.'),
            ('Скидка 17%',
             'Скидка 17% действует до 08.11.2026, только для новых клиентов. '
             'Скидка 17% постоянным клиентам предоставляется без ограничения срока.',
             '17', 'Скидка 17% постоянным клиентам предоставляется без ограничения срока.'),
        ):
            with self.subTest(body=body):
                source = konsierge_input(body, offer=offer)
                raw = make_input(source)
                before = copy.deepcopy(raw)
                n = normalize_record(raw, as_of=AS_OF)
                self.assertIsNone(n['validity']['until'])
                self.assertEqual(n['validity']['status'], 'unknown')
                self.assertEqual(n['benefits'][0]['value'], expected_rate)
                self.assertIn(body, n['conditions'][0]['evidence']['text'])
                result = build_catalogue([n], as_of=AS_OF)
                self.assertEqual(len(result['rows']), 1)
                self.assertEqual(result['rows'][0][6], '')
                self.assertIn(live_clause, '\n'.join(result['rows'][0][2:6]))
                self.assertEqual(raw, before)
                self.assertEqual(n['raw'], before)

    def test_complete_offer_period_keeps_date_suffixes(self):
        for body in (
            'Скидка 17% действует до 05.11.2026.',
            'Скидка 17% действует до 05.11.2026 включительно.',
            'Срок действия предложения: до 05.11.2026г.',
            'Срок действия предложения: до 05.11.2026 года включительно.',
            'Срок действия предложения: до 05.11.2026 г. Предъявите карту.',
            'Срок действия предложения: до 05.11.2026. скидка действует на все услуги.',
        ):
            with self.subTest(body=body):
                n = normalized(konsierge_input(body))
                self.assertEqual(n['validity']['until'], '2026-11-05')
                self.assertEqual(n['validity']['status'], 'expired')
                self.assertEqual(build_catalogue([n], as_of=AS_OF)['rows'], [])

    def test_conflicting_campaign_dates_remain_unknown(self):
        n = normalized(konsierge_input(
            'Срок действия предложения: до 12.11.2026. '
            'Предложение действительно до 25.11.2026.'))
        self.assertIsNone(n['validity']['until'])
        self.assertEqual(n['validity']['status'], 'unknown')

    def test_expiry_timestamp_is_not_promoted_to_customer_calendar_date(self):
        for expiry, status in (
            ('2026-11-30T21:00:00.000Z', 'unknown'),
            ('2026-11-12T21:00:00.000Z', 'source_expiry_elapsed_customer_period_unknown'),
        ):
            with self.subTest(expiry=expiry):
                n = normalized(konsierge_input('Скидка 17% на услуги.', expiry=expiry))
                self.assertIsNone(n['validity']['until'])
                self.assertEqual(n['validity']['status'], status)
                self.assertEqual(n['availability']['source_expiry_utc'], expiry)

    def test_expiry_timestamp_tolerance_and_conflict_ignore_registration_date(self):
        body = ('Срок действия предложения: до 25.11.2026. '
                'Скидка 17% для клиентов, зарегистрировавшихся до 01.11.2026.')
        for expiry, end, status in (
            ('2026-11-24T21:00:00.000Z', '2026-11-25', 'within_stated_period'),
            ('2026-12-30T21:00:00.000Z', None, 'source_date_conflict'),
        ):
            with self.subTest(expiry=expiry):
                n = normalized(konsierge_input(body, expiry=expiry))
                self.assertEqual(n['validity']['until'], end)
                self.assertEqual(n['validity']['status'], status)
                self.assertIn(expiry, n['conditions'][0]['evidence']['text'])

    def test_invalid_explicit_campaign_date_still_fails_validation(self):
        with self.assertRaises(ValueError):
            konsierge_input('Срок действия предложения: до 31.02.2027.')


class RetainedKonsiergeDateTests(unittest.TestCase):
    def test_retained_component_expiry_is_removed_without_losing_live_conditions(self):
        for offer, body, old_end, live_clause in (
            ('Скидка 17%',
             'Скидка 17% действует до 01.11.2026 только на СПА. '
             'Скидка 17% в ресторане действует постоянно.',
             '2026-11-01', 'Скидка 17% в ресторане действует постоянно.'),
            ('Скидка 23,5%',
             'Скидка 23,5% действует до 04.11.2026 исключительно на массаж. '
             'Скидка 23,5% на меню действует постоянно.',
             '2026-11-04', 'Скидка 23,5% на меню действует постоянно.'),
        ):
            with self.subTest(body=body):
                source = konsierge_input(body, offer=offer)
                source['fields']['Окончание']['value'] = old_end
                warnings = json.loads(source['fields']['Ограничения JSON']['value'])
                source['fields']['Ограничения JSON']['value'] = json.dumps(
                    [value for value in warnings if value != 'customer_validity_not_established'])
                raw = make_input(source)
                before = copy.deepcopy(raw)
                n = normalize_record(raw, as_of=AS_OF)
                self.assertIsNone(n['validity']['until'])
                self.assertEqual(n['validity']['status'], 'unknown')
                row = build_catalogue([n], as_of=AS_OF)['rows'][0]
                self.assertEqual(row[6], '')
                self.assertIn(live_clause, '\n'.join(row[2:6]))
                self.assertEqual(raw, before)
                self.assertEqual(n['raw'], before)

    def test_retained_registration_expiry_is_reprojected_without_changing_raw(self):
        source = konsierge_input('Скидка 17% для клиентов, зарегистрировавшихся до 01.11.2026.')
        source['fields']['Окончание']['value'] = '2026-11-01'
        warnings = json.loads(source['fields']['Ограничения JSON']['value'])
        source['fields']['Ограничения JSON']['value'] = json.dumps(
            [value for value in warnings if value != 'customer_validity_not_established'])
        raw = make_input(source)
        before = copy.deepcopy(raw)
        n = normalize_record(raw, as_of=AS_OF)
        self.assertIsNone(n['validity']['until'])
        self.assertEqual(n['validity']['status'], 'unknown')
        self.assertIn('customer_validity_not_established', n['quality']['issues'])
        self.assertEqual(raw, before)
        self.assertEqual(n['raw'], before)
        row = build_catalogue([n], as_of=AS_OF)['rows'][0]
        self.assertEqual(row[6], '')
        self.assertEqual(row[12], 'Срок не указан')
        self.assertIn('зарегистрировавшихся до 01.11.2026', row[5])
        self.assertEqual(n['raw'], before)

    def test_retained_missing_campaign_end_is_reprojected_without_changing_raw(self):
        for end, expected_end, status, expected_count in (
            ('12.11.2026', '2026-11-12', 'expired', 0),
            ('25.11.2026', '2026-11-25', 'within_stated_period', 1),
        ):
            with self.subTest(end=end):
                source = konsierge_input(
                    'Срок действия предложения: до ' + end + '. '
                    'Скидка 17% для клиентов, зарегистрировавшихся до 01.11.2026.')
                source['fields']['Окончание']['value'] = ''
                warnings = json.loads(source['fields']['Ограничения JSON']['value'])
                source['fields']['Ограничения JSON']['value'] = json.dumps(
                    list(dict.fromkeys(warnings + ['customer_validity_not_established'])))
                raw = make_input(source)
                before = copy.deepcopy(raw)
                n = normalize_record(raw, as_of=AS_OF)
                self.assertEqual(n['validity']['until'], expected_end)
                self.assertEqual(n['validity']['status'], status)
                self.assertNotIn('customer_validity_not_established', n['quality']['issues'])
                self.assertEqual(raw, before)
                self.assertEqual(n['raw'], before)
                result = build_catalogue([n], as_of=AS_OF)
                self.assertEqual(len(result['rows']), expected_count)
                if expected_count:
                    self.assertEqual(result['rows'][0][6], 'до 2026-11-25')
                self.assertEqual(n['raw'], before)

    def test_retained_false_date_conflict_no_longer_taints_reader_status(self):
        source = konsierge_input(
            'Скидка 17% для клиентов, зарегистрировавшихся до 01.11.2026.',
            expiry='2026-11-30T21:00:00.000Z')
        source['fields']['Окончание']['value'] = ''
        warnings = json.loads(source['fields']['Ограничения JSON']['value'])
        source['fields']['Ограничения JSON']['value'] = json.dumps(list(dict.fromkeys(
            warnings + ['source_expiry_conflicts_with_description', 'customer_validity_not_established'])))
        raw = make_input(source)
        before = copy.deepcopy(raw)
        n = normalize_record(raw, as_of=AS_OF)
        self.assertEqual(n['validity']['status'], 'unknown')
        self.assertNotIn('source_expiry_conflicts_with_description', n['quality']['issues'])
        self.assertEqual(n['raw'], before)
        row = build_catalogue([n], as_of=AS_OF)['rows'][0]
        self.assertEqual(row[6], '')
        self.assertEqual(row[12], 'Срок не указан')
        self.assertEqual(n['raw'], before)

    def test_retained_reprojection_does_not_accept_unexplained_dates_or_item_tampering(self):
        source = konsierge_input('Скидка 17% для клиентов, зарегистрировавшихся до 01.11.2026.')
        source['fields']['Окончание']['value'] = '2099-01-01'
        with self.assertRaises(ValueError):
            normalized(source)
        source['fields']['Окончание']['value'] = '2026-11-01'
        details = json.loads(source['fields']['Детали JSON']['value'])
        details['public_item']['description'] = 'Срок действия предложения: до 30.11.2026.'
        source['fields']['Детали JSON']['value'] = json.dumps(details)
        with self.assertRaises(ValueError):
            normalized(source)


if __name__ == '__main__':
    unittest.main()
