"""An owned PDF template extracts current values rather than reviewed constants."""
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))
import alfa_partner_rules as alfa
from normalized import content_hash, validate_offer
from unified_normalization import normalize_record
from test_alfa_partner_rules import fixture, NOW
from test_alfa_partner_numeric_boundaries import common_input


def source(rate='10', cap='1 500', payout='10 дней', headline_rate=None):
    return (fixture().replace('10%', (rate if headline_rate is None else headline_rate) + '%')
            .replace('по ставке 10 %', 'по ставке ' + rate + ' %')
            .replace('1 500', cap).replace('10 дней', payout))


def parse(text):
    with patch.object(alfa, 'pdf_text', return_value=text):
        return alfa.parse_document(alfa.DOCS[0], b'%PDF-synthetic-value-changes', NOW)


class AlfaPartnerValueChanges(unittest.TestCase):
    def assert_projection(self, text, value, cap, payout):
        try:
            row = parse(text)
        except ValueError as exc:
            self.fail(f'Valid changed PDF terms rejected: {exc}')
        validate_offer(row)
        self.assertEqual(row['title'], f'Alfa Only → Betulla — {value}%')
        self.assertEqual([(r['value'], r['qualifier']) for r in row['rates']], [(value, 'exact')])
        self.assertIn(cap, row['benefit_text'])
        self.assertIn(payout, row['conditions_text'])
        raw = common_input(row)
        before = copy.deepcopy(raw)
        result = normalize_record(raw, as_of='2026-11-08')
        self.assertEqual(raw, before)
        self.assertEqual(result['raw'], before)
        self.assertEqual([(b['kind'], b['value'], b['reward_unit']) for b in result['benefits']],
                         [('earn_rewards', value, 'Альфа-Баллы/ Бонусные Мили')])
        linked = [c for c in result['conditions'] if c['id'] in result['benefits'][0]['condition_ids']]
        self.assertTrue(any(cap in c['evidence']['text'] for c in linked))
        self.assertTrue(any(payout in c['evidence']['text'] for c in linked))
        self.assertTrue(all(c['value'] is None and c['unit'] is None for c in linked))
        return row, raw, result

    def test_rate_cap_and_delay_change_together(self):
        for rate, value, cap, payout in (
                ('7.5', '7.5', '2 750', '21 день'),
                ('12', '12', '9 000', '3 дня'),
                ('12,5', '12.5', '12\u202f345', '17 дней'),
                ('37', '37', '750', '1 день')):
            with self.subTest(rate=rate):
                self.assert_projection(source(rate, cap, payout), value,
                                       cap.replace('\u202f', ' '), payout)

    def test_each_parameter_can_change_independently(self):
        cases = (
            (source(rate='17'), '17', '1 500', '10 дней'),
            (source(cap='3 250'), '10', '3 250', '10 дней'),
            (source(payout='30 дней'), '10', '1 500', '30 дней'),
        )
        for text, value, cap, payout in cases:
            with self.subTest(value=value, cap=cap, payout=payout):
                self.assert_projection(text, value, cap, payout)

    def test_parenthesized_cap_words_remain_literal_conditions(self):
        cap = '2 750 (две тысячи семьсот пятьдесят)'
        self.assert_projection(source('12', cap, '3 дня'), '12', cap, '3 дня')

    def test_headline_upper_bound_does_not_replace_the_exact_body_rate(self):
        self.assert_projection(source('12', headline_rate='20'), '12', '1 500', '10 дней')

    def test_exact_rate_above_headline_bound_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'alfa_partner_pdf_'):
            parse(source('12', headline_rate='10'))

    def test_rate_rejects_malformed_ranges_and_out_of_domain_values(self):
        for rate in ('101', '-5', '1 00', '1.5.0', '1e1', '10%–15', '15%–10', '10%-15%-20'):
            with self.subTest(rate=rate):
                with self.assertRaisesRegex(ValueError, 'alfa_partner_pdf_rate_invalid_or_changed'):
                    parse(source(rate, headline_rate='100'))

    def test_more_than_one_operative_rate_is_not_silently_reduced_to_first(self):
        text = source().replace('по ставке 10 %', 'по ставке 10 %, а затем по ставке 12 %')
        with self.assertRaisesRegex(ValueError, 'alfa_partner_pdf_rate_invalid_or_changed'):
            parse(text)

    def test_cap_rejects_invalid_or_range_values(self):
        for cap in ('0', '-500', '1 00', '1.500.5', '1e3', '100–500'):
            with self.subTest(cap=cap):
                with self.assertRaisesRegex(ValueError, 'alfa_partner_pdf_'):
                    parse(source(cap=cap))

    def test_delay_is_a_positive_whole_day_count(self):
        for payout in ('0 дней', '-3 дня', '1.5 дня', '1e2 дней', '2–3 дня', '1 00 дней'):
            with self.subTest(payout=payout):
                with self.assertRaisesRegex(ValueError, 'alfa_partner_pdf_'):
                    parse(source(payout=payout))

    def test_cached_rates_cannot_override_a_changed_literal_rate(self):
        row, raw, _ = self.assert_projection(source('17'), '17', '1 500', '10 дней')
        raw['rates'] = [{'kind': 'cashback', 'value': '10', 'unit': 'percent',
                         'qualifier': 'exact', 'evidence': 'old cached 10%'}]
        result = normalize_record(raw, as_of='2026-11-08')
        self.assertEqual([b['value'] for b in result['benefits']], ['17'])
        self.assertEqual(result['raw']['rates'], raw['rates'])

    def test_generated_title_must_agree_with_its_operative_rate(self):
        row = parse(source())
        row['title'] = 'Alfa Only → Betulla — 99%'
        row['content_sha256'] = content_hash(row)
        with self.assertRaisesRegex(ValueError, 'alfa_partner_pdf_'):
            validate_offer(row)
        raw = common_input(parse(source()))
        raw['title'] = 'Alfa Only → Betulla — 99%'
        with self.assertRaisesRegex(ValueError, 'alfa_partner_pdf_'):
            normalize_record(raw, as_of='2026-11-08')


if __name__ == '__main__':
    unittest.main()
