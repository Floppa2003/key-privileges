"""VTB rules keep HTML line breaks without borrowing another card's terms."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from normalized import validate_offer
from recovered_sources import parse_bank_page

NOW = '2026-09-14T13:00:00+00:00'
IDENTITY = 'Дебетовая карта Привилегия Аэрофлот'
HEADING = 'Как начисляются мили по карте ВТБ'
FORMULA = 'За каждые 90 ₽ вы получите 3 мили.'


def page(*, identity=IDENTITY, heading=HEADING, formula=FORMULA,
         related='Прайм Аэрофлот: 4 мили за 100 ₽', extra_sections=''):
    return (
        f'<section class="xNativeSection"><h1>{identity}</h1></section>'
        f'<section class="xNativeSection"><h2>{heading}</h2><p>{formula}</p></section>'
        f'<section id="how" class="xNativeSection">{related}</section>'
        + extra_sections
    )


class RecoveredBankHtmlBoundariesTests(unittest.TestCase):
    def parsed(self, raw, evidence):
        try:
            row = parse_bank_page('af_vtb_rules', raw, NOW)
        except ValueError as exc:
            self.fail(f'Valid VTB markup was rejected: {exc}')
        row = json.loads(json.dumps(row, ensure_ascii=False))
        validate_offer(row)
        self.assertEqual(row['observed_at'], NOW)
        self.assertEqual(row['details']['earning_rules'], [{
            'value': '3', 'unit': 'miles', 'basis_amount': '90',
            'basis_unit': 'RUB', 'qualifier': 'exact', 'evidence': evidence,
        }])
        self.assertIn(evidence, row['details']['earning_conditions'])
        self.assertIn(evidence, row['conditions_text'])
        self.assertNotIn('Прайм', row['conditions_text'])
        return row

    def test_identity_line_break_preserves_the_same_card(self):
        row = self.parsed(
            page(identity='Дебетовая карта<br>Привилегия Аэрофлот'),
            'За каждые 90 ₽ вы получите 3 мили',
        )
        self.assertIn('Дебетовая карта\nПривилегия Аэрофлот', row['conditions_text'])

    def test_earning_line_break_keeps_literal_evidence(self):
        self.parsed(
            page(formula='За каждые 90 ₽<br>вы получите 3 мили.'),
            'За каждые 90 ₽\nвы получите 3 мили',
        )

    def test_heading_and_combined_line_breaks_keep_owned_rules(self):
        cases = (
            ('heading', page(heading='Как начисляются<br>мили по карте ВТБ'),
             'За каждые 90 ₽ вы получите 3 мили'),
            ('combined', page(
                identity='Дебетовая карта<br>Привилегия Аэрофлот',
                heading='Как начисляются<br>мили по карте ВТБ',
                formula='За каждые 90 ₽<br>вы получите 3 мили.'),
             'За каждые 90 ₽\nвы получите 3 мили'),
        )
        for name, raw, evidence in cases:
            with self.subTest(case=name):
                self.parsed(raw, evidence)

    def test_prime_card_stays_excluded_or_rejects_contaminated_scope(self):
        for prime in ('Прайм Аэрофлот: 4 мили за 100 ₽',
                      'Прайм<br>Аэрофлот: 4 мили за 100 ₽'):
            with self.subTest(location='excluded_how', prime=prime):
                self.parsed(page(related=prime), 'За каждые 90 ₽ вы получите 3 мили')
            with self.subTest(location='included_section', prime=prime):
                raw = page(extra_sections=f'<section class="xNativeSection">{prime}</section>')
                with self.assertRaises(ValueError):
                    parse_bank_page('af_vtb_rules', raw, NOW)

    def test_incomplete_or_ambiguous_sections_do_not_invent_a_rule(self):
        split_identity = (
            '<section class="xNativeSection"><h1>Дебетовая карта</h1></section>'
            '<section class="xNativeSection">Привилегия Аэрофлот</section>'
            '<section class="xNativeSection"><h2>Как начисляются мили по карте ВТБ</h2>'
            '<p>За каждые 90 ₽ вы получите 3 мили.</p></section>'
        )
        cases = (
            ('identity_in_two_sections', split_identity),
            ('rate_in_two_sections', page(
                formula='За каждые 90 ₽',
                extra_sections='<section class="xNativeSection">вы получите 3 мили.</section>')),
            ('duplicate_earning_section', page(extra_sections=(
                '<section class="xNativeSection"><h2>Как начисляются мили по карте ВТБ</h2>'
                '<p>За каждые 100 ₽ вы получите 4 мили.</p></section>'))),
            ('unknown_formula', page(formula='За каждые 90 ₽ начисление по тарифам банка.')),
            ('wrong_reward_unit', page(formula='За каждые 90 ₽ вы получите 3 балла.')),
        )
        for name, raw in cases:
            with self.subTest(case=name):
                with self.assertRaises(ValueError):
                    parse_bank_page('af_vtb_rules', raw, NOW)


class OtherRecoveredBankHtmlBoundariesTests(unittest.TestCase):
    def parsed(self, sid, raw):
        try:
            row = parse_bank_page(sid, raw, NOW)
        except ValueError as exc:
            self.fail(f'Valid bank markup was rejected: {exc}')
        row = json.loads(json.dumps(row, ensure_ascii=False))
        validate_offer(row)
        self.assertEqual(row['observed_at'], NOW)
        return row

    def test_nspk_identity_line_break_keeps_the_supplementary_article(self):
        raw = (
            '<div class="pages-press-center-details-article-slug">'
            '<h1>Держатели ЕКП<br>смогут экономить</h1>'
            '<p>Кешбэк 5%. Необходимо согласиться с условиями на vamprivet.ru.</p>'
            '</div>'
        )
        row = self.parsed('nspk_ekp_rules', raw)
        self.assertIn('Держатели ЕКП\nсмогут экономить', row['conditions_text'])
        self.assertEqual(row['source_status'], 'public_announcement_not_full_rules')
        self.assertIsNone(row['valid_until'])

    def test_uralsib_identity_and_period_breaks_keep_literal_dates(self):
        cases = (
            ('identity', 'Приветственные баллы РЖД<br>за оформление карты',
             'В период с 01.09.2023 по 15.03.2024 оформить заявку',
             'В период с 01.09.2023 по 15.03.2024 оформить заявку'),
            ('period', 'Приветственные баллы РЖД за оформление карты',
             'В период с 01.09.2023<br>по 15.03.2024<br>оформить заявку',
             'В период с 01.09.2023\nпо 15.03.2024\nоформить заявку'),
            ('combined', 'Приветственные баллы РЖД<br>за оформление карты',
             'В период с 01.09.2023<br>по 15.03.2024<br>оформить заявку',
             'В период с 01.09.2023\nпо 15.03.2024\nоформить заявку'),
        )
        for name, identity, period, evidence in cases:
            with self.subTest(case=name):
                raw = f'<h1>{identity}</h1><section id="textBlock">{period} на карту.</section>'
                row = self.parsed('uralsib_rzd_rules', raw)
                self.assertEqual(row['valid_from'], '2023-09-01')
                self.assertEqual(row['valid_until'], '2024-03-15')
                self.assertEqual(row['validity_status'], 'expired_by_published_end')
                self.assertEqual(row['details']['application_period_evidence'], evidence)
                self.assertIn(evidence, row['conditions_text'])

    def test_uralsib_period_cannot_be_joined_across_source_blocks(self):
        raw = (
            '<h1>Приветственные баллы РЖД за оформление карты. В период с 01.09.2023</h1>'
            '<section id="textBlock">по 15.03.2024 оформить заявку на карту.</section>'
        )
        with self.assertRaises(ValueError):
            parse_bank_page('uralsib_rzd_rules', raw, NOW)


if __name__ == '__main__':
    unittest.main()
