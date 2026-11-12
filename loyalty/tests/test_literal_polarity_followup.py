"""Bounds and denial survive source phrase extraction and reader projection."""
import unittest

from test_unified_normalization import record
from test_dom_card_boundaries import project
from normalized import make_offer, normalize_rates
from unified_normalization import normalize_record
from content_discovery import literal_benefits, literal_rates
from flystation_source import inventory, SOURCE
from public_reward_projection import make_record
from catalogue_view import record_row

NOW = '2026-11-12T00:00:00+00:00'


def source_row(body):
    html = ('<section class="promotions"><div class="promotions__slider-item-text">'
            '<p>Новое предложение</p><p>' + body + '</p></div></section>')
    evidence, = inventory(html)
    return make_record(SOURCE, evidence, NOW)


class LiteralPolarityFollowup(unittest.TestCase):
    def test_percent_bounds_keep_their_qualifier_at_source_and_common_boundaries(self):
        for body, kind, value, qualifier in [
            ('Скидка не более 12,5%.', 'discount', '12.5', 'up_to'),
            ('Кешбэк не менее 7,25%.', 'cashback', '7.25', 'at_least'),
            ('Скидка не более чем 9%.', 'discount', '9', 'up_to'),
            ('Кешбэк не менее чем 21%.', 'cashback', '21', 'at_least'),
            ('Скидка не  более    17,5%.', 'discount', '17.5', 'up_to'),
        ]:
            with self.subTest(body=body):
                source = make_offer('moskvich', 'bounds-fixture', 'Карта', 'Example', body,
                    'https://moskvichmag.ru/programma-loyalnosti/', NOW)
                common = normalize_record(record(benefit=body, conditions='', activation=''), as_of=NOW[:10])
                expected = [(kind, value, qualifier)]
                self.assertEqual([(r['kind'], r['value'], r['qualifier']) for r in source['rates']], expected)
                self.assertEqual([(r['kind'], r['value'], r['qualifier']) for r in common['benefits']], expected)

    def test_literal_source_bounds_reach_the_reader_with_original_conditions(self):
        for body, value, qualifier in [('Скидка не более 12,5%.', '12.5', 'up_to'),
                                        ('Кешбэк не менее 7,25%.', '7.25', 'at_least')]:
            with self.subTest(body=body):
                row = source_row(body)
                self.assertEqual(row['record_kind'], 'partner_offer')
                self.assertEqual([(r['value'], r['qualifier']) for r in row['rates']], [(value, qualifier)])
                common = project(row)
                self.assertEqual([(b['value'], b['qualifier']) for b in common['benefits']], [(value, qualifier)])
                reader, reason = record_row(common, NOW[:10])
                self.assertIsNone(reason)
                self.assertIn(body, reader[2])
                self.assertEqual(row['conditions_text'], body)

    def test_denial_cannot_be_dropped_by_phrase_slicing(self):
        for body in ['Скидка 10% не предоставляется.', 'Кешбэк 10% не начисляется.',
                     'Не предоставляется скидка 10%.', 'Не начисляется кешбэк 10%.',
                     'Скидка 500 ₽ не предоставляется.', 'Скидка 10% и кешбэк 5% не предоставляются.']:
            with self.subTest(body=body):
                self.assertEqual(literal_benefits(body), ([], []))
                self.assertEqual(literal_rates(body), [])
                row = source_row(body)
                self.assertEqual(row['record_kind'], 'source_observation')
                self.assertEqual(row['rates'], [])
                self.assertEqual(row['conditions_text'], body)
                common = project(row)
                self.assertEqual(common['benefits'], [])
                self.assertIsNone(record_row(common, NOW[:10])[0])

    def test_only_the_live_occurrence_survives_in_a_mixed_sentence(self):
        for body, value, unit in [
            ('Скидка 10% не предоставляется, но скидка 5% действует.', '5', 'percent'),
            ('Скидка 10% не предоставляется, но скидка 10% действует.', '10', 'percent'),
            ('Скидка 10% действует, но скидка 10% не предоставляется.', '10', 'percent'),
            ('Скидка 500 ₽ не предоставляется, но скидка 250 ₽ действует.', '250', 'RUB'),
            ('Скидка не предоставляется; скидка 5% действует.', '5', 'percent'),
            ('Скидка не предоставляется, но скидка 5% действует.', '5', 'percent'),
        ]:
            with self.subTest(body=body):
                terms = literal_benefits(body)[1]
                self.assertEqual([(r['value'], r['unit']) for r in terms], [(value, unit)])
                self.assertEqual(terms[0]['fragment'], body)
                row = source_row(body)
                self.assertEqual([(r['value'], r['unit']) for r in row['rates']], [(value, unit)])
                common = project(row)
                self.assertEqual([(b['value'], b['unit']) for b in common['benefits']], [(value, unit)])
                self.assertIsNotNone(record_row(common, NOW[:10])[0])

    def test_product_exclusions_and_payment_percentages_keep_only_the_owned_reward(self):
        for body in ['Скидка 10% не действует на акционные тарифы.',
                     'Скидка 10% не суммируется с другими акциями.',
                     'Скидка 10% при предоплате 50%.',
                     'Предоплата 50%, скидка 10%.']:
            with self.subTest(body=body):
                row = source_row(body)
                self.assertEqual([(r['kind'], r['value']) for r in row['rates']], [('discount', '10')])
                self.assertEqual(row['conditions_text'], body)

    def test_bound_words_do_not_turn_a_payment_into_a_discount(self):
        body = 'Скидка не более 12,5% при предоплате не менее 50%.'
        expected = [('discount', '12.5', 'up_to')]
        self.assertEqual([(r['kind'], r['value'], r['qualifier']) for r in normalize_rates(body)], expected)
        self.assertEqual([(r['kind'], r['value'], r['qualifier']) for r in literal_rates(body)], expected)

    def test_invalid_bounded_percentages_are_not_shortened_to_valid_values(self):
        for body in ['Скидка не более 112,5%.', 'Скидка не менее 1 00%.',
                     'Скидка не более 1.500.5%.']:
            with self.subTest(body=body):
                self.assertEqual(literal_benefits(body), ([], []))


if __name__ == '__main__':
    unittest.main()
