"""Offer contract preserves qualitative benefits and qualified numeric rates."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import merchant_extract as extractor
from test_merchant_extract import answer

HERE = Path(__file__).resolve().parents[1]


def offer(**overrides):
    result = {'benefit_kind': 'discount', 'benefit_text': 'Скидка до 20% на клубную карту',
              'value': 20, 'value_qualifier': 'up_to', 'unit': '%', 'basis': 'Клубная карта',
              'audience': 'Участники программы', 'restrictions': [], 'how_to_get': [],
              'promo_code': None, 'valid_until': None, 'accrual_timing': None,
              'evidence': ['Скидка до 20% на клубную карту'], 'practical_advice': []}
    result.update(overrides)
    return result


class OfferContractTests(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads((HERE / 'merchant_offer.schema.json').read_text())

    def parse(self, offers, restrictions=None):
        body = {'has_offer': bool(offers), 'offers': offers,
                'program_restrictions': restrictions or [], 'unknowns': []}
        return extractor.parse_final(answer(json.dumps(body, ensure_ascii=False)), self.schema)

    def test_discount_and_qualitative_benefit_remain_separate(self):
        offers = [offer(), offer(benefit_kind='other', benefit_text='Приоритетное размещение',
                                value=None, value_qualifier=None, unit=None, basis='Размещение',
                                evidence=['Приоритетное размещение'])]
        self.assertEqual(self.parse(offers)['offers'], offers)

    def test_missing_benefit_or_rate_qualifier_is_not_a_complete_offer(self):
        for field in ('benefit_text', 'value_qualifier'):
            with self.subTest(field=field):
                item = offer(); item.pop(field)
                with self.assertRaises(ValueError): self.parse([item])

    def test_unqualified_number_and_qualifier_without_number_are_rejected(self):
        for item in (offer(value_qualifier=None), offer(value=None)):
            with self.subTest(item=item):
                with self.assertRaises(ValueError): self.parse([item])

    def test_rules_only_page_keeps_restriction_without_inventing_offer(self):
        rules = [{'text': 'На игры по подарочным сертификатам скидки не распространяются.',
                  'evidence': ['На игры по подарочным сертификатам скидки не распространяются.']}]
        actual = self.parse([], rules)
        self.assertFalse(actual['has_offer'])
        self.assertEqual(actual['program_restrictions'], rules)

    def test_blank_benefit_is_rejected(self):
        for text in ('', '  '):
            with self.subTest(text=text):
                with self.assertRaises(ValueError): self.parse([offer(benefit_text=text)])


if __name__ == '__main__':
    unittest.main()
