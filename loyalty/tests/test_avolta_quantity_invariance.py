"""Bundle quantities survive source, common projection and the visible reader."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
import avolta_source as source
from public_reward_projection import make_record
from catalogue_clauses import benefit_claim
from catalogue_view import record_row
from test_public_reward_sources import common, NOW


def record(headline, body='Для активации перейдите в приложение Club Avolta.'):
    evidence = dict(url=source.PREFIX + 'razvlecheniya/test', name='Test',
                    page_sha256='0' * 64, headline=headline,
                    intro='Для участников Club Avolta.', body=body, category='Развлечения')
    return make_record(source.SOURCE, evidence, NOW)


class AvoltaQuantityInvariance(unittest.TestCase):
    def test_changing_quantities_reach_reader_without_invented_percentage(self):
        for phrase in ['Два по цене одного', 'Три по цене двух', 'Пять по цене четырёх',
                       'Двадцать один по цене двадцати', '3 по цене 2', '11 по цене 7',
                       '1 500 по цене 1 000', '125000 по цене 124999']:
            with self.subTest(phrase=phrase):
                text = f'Акция «{phrase}» на аттракционы.'
                try:
                    original = record(text)
                except source.ExcludedOffer as exc:
                    self.fail(f'Valid changed quantity rejected: {exc}')
                normalized = common(original)
                self.assertEqual([(x['kind'], x['value']) for x in normalized['benefits']], [('partner_privilege', None)])
                self.assertEqual(normalized['benefits'][0]['evidence']['text'], text)
                row, reason = record_row(normalized, NOW[:10])
                self.assertIsNone(reason)
                self.assertIn(phrase, row[2])
                self.assertIn('приложение', row[4])

    def test_nonbeneficial_or_incomplete_quantities_are_not_offers(self):
        for phrase in ['Два по цене трёх', 'Два по цене двух', '1 по цене 1', '2 по цене 3',
                       '0 по цене 1', '3 по цене 0', '-3 по цене 2', '−3 по цене 2',
                       '3 по цене -2', '3,5 по цене 2', '3 по цене 2,5',
                       '1–3 по цене 2', '3 по цене 1–2', '1 00 по цене 2',
                       '3 по цене 1 00', '3.5.5 по цене 2', '3 по цене 2.5.5',
                       '3 по цене 2 рубля', '3 по цене 2 ₽', '3 по цене 2 USD',
                       'Три по цене двух с половиной']:
            with self.subTest(phrase=phrase):
                text = f'Акция «{phrase}» на аттракционы.'
                with self.assertRaises(source.ExcludedOffer):
                    record(text)
                self.assertFalse(benefit_claim(text))

    def test_quoted_and_unquoted_denials_do_not_create_offers(self):
        for text in ['Акция «Два по цене одного» не действует.',
                     'Акция «3 по цене 2» не предоставляется.',
                     'Не действует акция «3 по цене 2».',
                     '3 по цене 2 не действует.',
                     'Акция «3 по цене 2» отменена.',
                     'Акция «3 по цене 2» завершена.']:
            with self.subTest(text=text):
                with self.assertRaises(source.ExcludedOffer):
                    record(text)
                self.assertFalse(benefit_claim(text))

    def test_product_exclusions_and_noncombination_keep_actual_offer(self):
        for text in ['Акция «3 по цене 2» не действует на акционные товары.',
                     'Акция «3 по цене 2» не суммируется с другими акциями.']:
            with self.subTest(text=text):
                try:
                    normalized = common(record(text))
                except source.ExcludedOffer as exc:
                    self.fail(f'Offer with a restriction rejected: {exc}')
                row, reason = record_row(normalized, NOW[:10])
                self.assertIsNone(reason)
                self.assertIn(text, '\n'.join(row[2:6]))

    def test_independent_discount_survives_invalid_or_denied_bundle(self):
        for bad in ['Два по цене трёх', '3 по цене 2» не действует', '3 по цене 2 рубля']:
            with self.subTest(bad=bad):
                row = record(f'Акция «{bad}».', 'Скидка 7% на билеты. Перейдите в приложение Club Avolta.')
                self.assertEqual(row['benefit_text'], 'Скидка 7% на билеты.')
                self.assertEqual([(x['kind'], x['value']) for x in common(row)['benefits']], [('discount', '7')])

    def test_additional_quantity_offer_remains_in_conditions(self):
        row = record('Скидка 7% на билеты.', 'Акция «Три по цене двух» на аттракционы. Перейдите в приложение Club Avolta.')
        self.assertIn('Три по цене двух', row['conditions_text'])
        visible, reason = record_row(common(row), NOW[:10])
        self.assertIsNone(reason)
        self.assertIn('Три по цене двух', visible[5])


if __name__ == '__main__':
    unittest.main()
