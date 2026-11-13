"""Minimal anonymized reproductions of observed owned campaign date clauses."""
import copy
import html
import json
import unittest

from adapters import extract, ural_catalog
from catalogue_view import build_catalogue
from coral_catalog import PROMO, detail
from hse_alumni import parse_catalog
from recovered_sources import parse_bank_page
from test_hse_alumni import card, page, section
from test_source_availability_dates import AS_OF, OBSERVED, stored_input
from unified_normalization import make_input, normalize_record


def retained_input(row):
    """The observed stored projection had blank date cells and date metadata."""
    source = stored_input({
        'schema_version': 2, 'run_id': 'fixture:1', 'observed_at': OBSERVED,
        'records': [row], 'sources': [{
            'source_id': row['source_id'], 'name': 'Fixture', 'root': row['source_url'],
            'status': 'ok', 'normalized': 1, 'discovered': 1, 'failed': 0,
            'coverage': 'owned fixture', 'region': None, 'errors': [],
            'observed_at': OBSERVED,
        }],
    })
    for label in ('Начало', 'Окончание'):
        source['fields'][label]['value'] = ''
    details = json.loads(source['fields']['Детали JSON']['value'])
    if 'public_coral_block' in details:
        details['public_coral_block']['valid_until'] = None
    if 'validity_evidence' in details:
        details['validity_evidence'] = None
    source['fields']['Детали JSON']['value'] = json.dumps(details, ensure_ascii=False)
    return make_input(source)


def coral_record(start, separator, tour_start, tour_end):
    title = 'Дополнительные бонусы на отдых в отеле «Пример»'
    body = (title + '\nУсловия акции:\nДаты бронирования: ' + start + ' – 31.10.2026\n'
            'Даты начала тура: ' + tour_start + ' – ' + tour_end + '\n'
            'Срок действия бонусов:\nдо 31.10.2026\n'
            'Срок проведения акции:\n' + start + separator + '31.10.2026\n'
            'Забронировать тур можно на сайте партнёра.')
    raw = '<section class="article"><h1>' + title + '</h1><p>' + html.escape(body) + '</p></section>'
    return detail(raw, 'coral_promo', {'url': PROMO + 'fixture/', 'title': title}, OBSERVED, {})


URAL_BODY = (
    '<p>Сервис начал свою работу в 2012 году.</p>'
    '<p>1. Скидка 20% на любые анализы по промокоду SAMPLE20:</p>'
    '<p>Оплачивайте до 99% суммы заказа бонусами программы;</p>'
    '<p>Бесплатная расшифровка результатов с врачом. Срок действия до 31.10.2026 г.</p>'
    '<p>2. Скидка 500 руб. на запись к врачу в двух городах.</p>'
    '<p>Каждый пользователь сможет воспользоваться скидкой только 1 раз. '
    'Срок действия до 31.10.2026 г.</p>'
)


def ural_record():
    return ural_catalog({'category': [], 'partners': [{
        'id': 1, 'name': 'Пример медицинского сервиса', 'text': {'detail': URAL_BODY},
    }]}, 'https://www.uralairlines.ru/partners/', OBSERVED)[0]


def article_record():
    raw = ('<div class="pages-press-center-details-article-slug">'
           '<p>16 июля 2026, 10:00</p><h1>Держатели ЕКП смогут экономить</h1>'
           '<p>Кешбэк 5% за оплату. Условия на vamprivet.ru.</p>'
           '<p>Предложение действует до 31 октября 2026 года включительно. '
           'Максимальный размер кешбэка на одного участника — не более 1000 рублей в месяц.</p>'
           '</div>')
    return parse_bank_page('nspk_ekp_rules', raw, OBSERVED)


def alumni_record():
    body = ('<p>Скидка 50% по промокоду SAMPLE50</p>'
            '<p>Лицензия для дома для 1 пользователя на 1 год по промокоду SAMPLE50.</p>'
            '<p>Срок акции: до 30 апреля 2027 года.</p>')
    return parse_catalog(page(card('sample', 'Пример программы'), section('sample', body)), OBSERVED)[0]


class OwnedCampaignSourceTests(unittest.TestCase):
    def test_labelled_coral_ranges_ignore_later_travel_dates(self):
        for start, separator, tour_start, tour_end, expected_start in (
            ('01.04.2026', ' – ', '02.04.2026', '09.11.2026', '2026-04-01'),
            ('09.06.2026', '-', '10.06.2026', '30.11.2026', '2026-06-09'),
        ):
            with self.subTest(start=start):
                row = coral_record(start, separator, tour_start, tour_end)
                self.assertEqual(row['valid_from'], expected_start)
                self.assertEqual(row['valid_until'], '2026-10-31')
                self.assertEqual(row['validity_status'], 'expired_by_published_end')
                self.assertIn(tour_end, row['conditions_text'])

    def test_each_numbered_ural_benefit_has_the_same_end(self):
        api = ural_record()
        raw = ('<li id="partner_1"><div class="uk-accordion-title">Пример медицинского сервиса</div>'
               '<div class="uk-accordion-content"><div class="uan-styled-text">' + URAL_BODY + '</div></div></li>')
        dom = extract('ural', raw, 'https://www.uralairlines.ru/partners/', OBSERVED)[0]
        for row in (api, dom):
            with self.subTest(locator=row['locator']):
                self.assertEqual(row['valid_until'], '2026-10-31')
                self.assertIn('20%', row['benefit_text'])
                self.assertIn('500 руб.', row['benefit_text'])

    def test_article_uses_owned_written_end_and_not_publication_date(self):
        row = article_record()
        self.assertIsNone(row['valid_from'])
        self.assertEqual(row['valid_until'], '2026-10-31')
        self.assertEqual(row['record_kind'], 'program_rules')

    def test_alumni_written_campaign_end_is_known(self):
        row = alumni_record()
        self.assertEqual(row['valid_until'], '2027-04-30')
        self.assertEqual(row['details']['validity_evidence'], 'Срок акции: до 30 апреля 2027 года')


class RetainedOwnedCampaignTests(unittest.TestCase):
    def test_unchanged_retained_rows_gain_validity_and_reader_status(self):
        for row, expected_start, expected_end in (
            (coral_record('01.04.2026', ' – ', '02.04.2026', '09.11.2026'), '2026-04-01', '2026-10-31'),
            (coral_record('09.06.2026', '-', '10.06.2026', '30.11.2026'), '2026-06-09', '2026-10-31'),
            (ural_record(), None, '2026-10-31'),
            (article_record(), None, '2026-10-31'),
            (alumni_record(), None, '2027-04-30'),
        ):
            with self.subTest(source=row['source_id'], start=expected_start):
                raw = retained_input(row)
                before = copy.deepcopy(raw)
                normalized = normalize_record(raw, as_of=AS_OF)
                self.assertEqual(normalized['validity']['from'], expected_start)
                self.assertEqual(normalized['validity']['until'], expected_end)
                catalogue = build_catalogue([normalized], as_of=AS_OF)
                if expected_end < AS_OF:
                    self.assertEqual(normalized['validity']['status'], 'expired')
                    self.assertEqual(catalogue['rows'], [])
                    self.assertEqual(catalogue['removed'][0]['reason'], 'истёкший срок')
                else:
                    self.assertEqual(normalized['validity']['status'], 'within_stated_period')
                    self.assertEqual(catalogue['rows'][0][6], 'до ' + expected_end)
                    self.assertEqual(catalogue['rows'][0][12], 'В пределах срока')
                self.assertEqual(raw, before)
                self.assertEqual(normalized['raw'], before)
                self.assertEqual(normalized['provenance']['source_row'], before['source_row'])


if __name__ == '__main__':
    unittest.main()
