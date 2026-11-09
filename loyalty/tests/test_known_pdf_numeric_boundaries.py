"""Reviewed PDF clauses consume whole literal numbers or reject the document."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from known_pdf import parse_pdf_pages
from test_known_pdf import FIN, PRIM, NOW
from test_dom_card_boundaries import project


def parse(source, pages):
    return parse_pdf_pages(source, pages, NOW, document_sha256='f' * 64)


def changed(pages, old, new):
    return [page.replace(old, new) for page in pages]


class KnownPdfNumericBoundaries(unittest.TestCase):
    def test_card_miles_and_welcome_never_use_a_malformed_number_suffix(self):
        for old, new in (
            ('1 миля при', '1.500.5 миля при'),
            ('1 миля при', '1,5,5 миля при'),
            ('500 приветственных', '1.500.5 приветственных'),
            ('500 приветственных', '1 00 приветственных'),
        ):
            with self.subTest(new=new), self.assertRaises(ValueError):
                parse('af_primbank_rules', changed(PRIM, old, new))

    def test_card_spend_threshold_cap_and_basis_reject_invalid_groups(self):
        for old, new in (
            ('10 000 руб. до', '1 00 руб. до'),
            ('до 75 000 руб.', 'до 7 50 00 руб.'),
            ('9 000 миль', '1 00 миль'),
            ('на покупки 100 руб.', 'на покупки 1.500.5 руб.'),
        ):
            with self.subTest(new=new), self.assertRaises(ValueError):
                parse('af_primbank_rules', changed(PRIM, old, new))

    def test_deposit_rewards_and_interval_reject_incomplete_number_tokens(self):
        for old, new in (
            ('1850 баллов только', '1.850.5 баллов только'),
            ('1850 баллов только', '1 85 0 баллов только'),
            ('от 10 000 (', 'от 1 00 ('),
            ('до 199 999 (', 'до 19 99 99 ('),
        ):
            with self.subTest(new=new), self.assertRaises(ValueError):
                parse('rzd_finuslugi_rules', changed(FIN, old, new))

    def test_required_month_and_day_counts_remain_whole_integers(self):
        for old, new in (
            ('на 1 (один)', 'на 1.5 (один)'),
            ('В течение 90 календарных', 'В течение 9 0 календарных'),
            ('период по 2 (второй)', 'период по 2.5 (второй)'),
        ):
            with self.subTest(new=new), self.assertRaises(ValueError):
                parse('rzd_finuslugi_rules', changed(FIN, old, new))

    def test_valid_card_grouped_amounts_keep_full_values_and_original_evidence(self):
        pages = changed(PRIM, '1 миля при', '1\u202f000 миля при')
        pages = changed(pages, '500 приветственных', '1 500 приветственных')
        pages = changed(pages, '10 000 руб. до', '10\u00a0000 руб. до')
        pages = changed(pages, '9 000 миль', '9\u202f000 миль')
        row = parse('af_primbank_rules', pages)
        details = row['details']
        self.assertEqual(details['spend_reward_tiers'][0]['miles'], '1000')
        self.assertEqual(details['spend_reward_tiers'][0]['monthly_spend_from_rub'], '10000')
        self.assertEqual(details['monthly_miles_cap'], '9000')
        self.assertEqual(details['welcome_miles'], '1500')
        self.assertTrue(details['spend_reward_tiers'][0]['evidence'].startswith('1 000 миля при'))
        self.assertIn('1 500 приветственных миль', row['conditions_text'])
        common = project(row)
        self.assertEqual(common['raw']['details']['spend_reward_tiers'][0]['miles'], '1000')
        self.assertEqual(common['raw']['details']['welcome_miles'], '1500')

    def test_valid_deposit_grouped_reward_and_unicode_threshold_keep_their_tier(self):
        pages = changed(FIN, '1850 баллов только', '1\u202f850 баллов только')
        pages = changed(pages, 'от 10 000 (', 'от 10\u00a0000 (')
        row = parse('rzd_finuslugi_rules', pages)
        first = row['details']['deposit_reward_tiers'][0]
        self.assertEqual((first['points'], first['deposit_min_rub'], first['deposit_max_rub']),
                         ('1850', '10000', '199999'))
        self.assertEqual(first['term_min_months'], 1)
        self.assertTrue(first['evidence'].startswith('1 850 баллов только'))
        self.assertEqual(row['id'], parse('rzd_finuslugi_rules', FIN)['id'])
        common = project(row)
        self.assertEqual(common['raw']['details']['deposit_reward_tiers'][0]['points'], '1850')
        self.assertEqual(common['raw']['conditions'], row['conditions_text'])


if __name__ == '__main__':
    unittest.main()
