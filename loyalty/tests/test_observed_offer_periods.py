"""Anonymized reproductions of five encountered labelled offer periods."""
import copy
import unittest

import coral_catalog as coral
import ekp_catalog as ekp
import magnit_partners as magnit
from catalogue_view import build_catalogue
from normalized import validate_offer
from public_reward_projection import make_record
from test_coral_catalog import doc, URL
from test_ekp_api import raw as ekp_row
from test_owned_campaign_dates import retained_input
from unified_normalization import normalize_record

NOW = '2026-11-13T12:00:00+00:00'
CLAUSES = (
    ('Сроки проведения акции: 08.09.2026-08.11.2026', '2026-09-08', '2026-11-08'),
    ('Сроки проведения акции: 26.05.2026 по 31.12.2026', '2026-05-26', '2026-12-31'),
    ('Cрок действия бонусов: бонусы действительны в течение 18 месяцев с момента начисления\n'
     'Срок действия акции: 01.01.2026-31.12.2026', '2026-01-01', '2026-12-31'),
)


def coral_record(clause):
    raw = doc('<section><div class="order-lg-2"><h1>Скидка 10% в Пример</h1><p>'
              + 'Правила и сроки проведения:\n' + clause + '</p></div><div class="product-purchase-box referal"></div></section>')
    return coral.detail(raw, 'coral', {'url': URL, 'category': 'Подарки',
                        'parent_url': coral.CLUB+'gifts/'}, NOW, {})


def magnit_record():
    title = 'Бонусы за выполнение условий'
    e = dict(native='1', url=magnit.ROOT+'/1', title=title, catalogue_title=title,
             partner='Пример', category='Другое', page_sha256='a'*64, rule_links=[],
             content='<p>Совершите минимум 3 поисковых запроса в течение 14 календарных дней, '
                     'следующих за днем установки поиска.</p><p>Бонусы будут начислены в течение '
                     '30 дней после выполнения всех условий акции</p>'
                     '<p>Срок проведения акции: 01 сентября – 30 ноября 2026</p>',
             steps='Выполните условия акции', disclaimer='')
    return make_record(magnit.SOURCE, e, NOW)


class ObservedOfferPeriods(unittest.TestCase):
    def assert_period(self, row, start, end):
        validate_offer(row)
        self.assertEqual((row['valid_from'], row['valid_until']), (start, end))
        self.assert_retained_period(row, start, end)

    def assert_retained_period(self, row, start, end):
        raw = retained_input(row)
        before = copy.deepcopy(raw)
        n = normalize_record(raw, as_of='2026-11-13')
        self.assertEqual((n['validity']['from'], n['validity']['until']), (start, end))
        expired = end < '2026-11-13'
        self.assertEqual(n['validity']['status'], 'expired' if expired else 'within_stated_period')
        catalogue = build_catalogue([n], as_of='2026-11-13')
        self.assertEqual(bool(catalogue['rows']), not expired)
        self.assertEqual(raw, before)
        self.assertEqual(n['raw'], before)

    def test_coral_plural_dash(self):
        self.assert_period(coral_record(CLAUSES[0][0]), *CLAUSES[0][1:])

    def test_coral_plural_po(self):
        self.assert_period(coral_record(CLAUSES[1][0]), *CLAUSES[1][1:])

    def test_coral_action_lifetime_keeps_bonus_lifetime(self):
        row = coral_record(CLAUSES[2][0])
        self.assertIn('18 месяцев', row['conditions_text'])
        self.assert_period(row, *CLAUSES[2][1:])

    def test_ekp_explicit_public_action_end(self):
        source = ekp_row()
        source['loyaltyDescription'] += '<p>Акция действует по 31.12.2026.</p>'
        before = copy.deepcopy(source)
        row = ekp.make_record(source, NOW, request=ekp.query(0), response_sha='a'*64,
                              observed_total=1, completed_at=NOW)
        self.assertEqual(source, before)
        self.assert_period(row, None, '2026-12-31')

    def test_retained_five_owned_periods(self):
        source = ekp_row()
        source['loyaltyDescription'] += '<p>Акция действует по 31.12.2026.</p>'
        ekp_offer = ekp.make_record(source, NOW, request=ekp.query(0), response_sha='a'*64,
                                    observed_total=1, completed_at=NOW)
        rows = [(coral_record(clause), start, end) for clause, start, end in CLAUSES]
        rows += [(ekp_offer, None, '2026-12-31'),
                 (magnit_record(), '2026-09-01', '2026-11-30')]
        for row, start, end in rows:
            with self.subTest(source=row['source_id'], start=start):
                self.assert_retained_period(row, start, end)

    def test_retained_ownership_and_structured_date_controls(self):
        from owned_offer_dates import project_retained_validity
        source = ekp_row()
        source['loyaltyDescription'] += '<p>Акция действует по 31.12.2026.</p>'
        row = ekp.make_record(source, NOW, request=ekp.query(0), response_sha='a'*64,
                              observed_total=1, completed_at=NOW)
        for offer in (row, magnit_record()):
            raw = retained_input(offer)
            for key in ('conditions', 'benefit', 'title', 'partner', 'activation', 'source_url'):
                changed = copy.deepcopy(raw)
                changed[key] = 'changed'
                validity = {'from': None, 'until': None}
                project_retained_validity(changed, validity)
                self.assertEqual(validity, {'from': None, 'until': None}, key)
            validity = {'from': None, 'until': '2027-01-01'}
            project_retained_validity(raw, validity)
            self.assertEqual(validity, {'from': None, 'until': '2027-01-01'})

    def test_ekp_protected_and_inactive_controls_never_gain_dates(self):
        for source in (ekp_row(locked=True), ekp_row(active=False)):
            source['loyaltyDescription'] += '<p>Акция действует по 31.12.2026.</p>'
            row = ekp.make_record(source, NOW, request=ekp.query(0), response_sha='a'*64,
                                  observed_total=1, completed_at=NOW)
            validate_offer(row)
            self.assertIsNone(row['valid_until'])
            raw = retained_input(row)
            n = normalize_record(raw, as_of='2026-11-13')
            self.assertIsNone(n['validity']['until'])
            if source['description_authorized']:
                self.assertNotIn('loyaltyDescription', row['details']['public_partner'])

    def test_magnit_shared_year_keeps_qualification_and_crediting(self):
        row = magnit_record()
        self.assertIn('14 календарных дней', row['conditions_text'])
        self.assertIn('30 дней', row['conditions_text'])
        self.assert_period(row, '2026-09-01', '2026-11-30')
