"""Values and repeated rows are inputs, never snapshots of a past offer."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from known_pdf import parse_pdf_pages
from test_known_pdf import FIN, PRIM, NOW
from t2_source import page_records

FIXTURES = Path(__file__).parent / 'fixtures_live'


class LiveValueContracts(unittest.TestCase):
    def test_changed_powerbank_session_limit_is_read_from_new_text(self):
        source = (FIXTURES / 't2-powerbank.html').read_text().replace('\u00a0', ' ')
        for days in (2, 5, 8):
            with self.subTest(days=days):
                raw = source.replace('3 суток', f'{days} суток')
                row = page_records('t2_powerbank', raw, NOW)[0]
                self.assertEqual(row['details']['max_session_duration_days'], days)
                self.assertIn(f'{days} суток', row['details']['session_duration_evidence'])

    def test_missing_powerbank_limit_does_not_reuse_three_days(self):
        raw = (FIXTURES / 't2-powerbank.html').read_text().replace('\u00a0', ' ').replace('3 суток', 'срока, указанного в приложении')
        row = page_records('t2_powerbank', raw, NOW)[0]
        self.assertIsNone(row['details']['max_session_duration_days'])
        self.assertIsNone(row['details']['session_duration_evidence'])

    def test_finuslugi_new_number_of_tiers_is_not_rejected(self):
        for count in (2, 4):
            with self.subTest(count=count):
                tiers = []
                for i in range(count):
                    tiers.append(f'• {1700+i*777} баллов только за первый вклад, на сумму от {10000+i*100000} (суммы) до {99999+i*100000} (суммы) рублей, срок банковского вклада не менее чем на 2 (два) календарный месяца;')
                pages = [FIN[0], '7.1.10. Участник может получить\n'+ '\n'.join(tiers) + '\n7.1.11. Ограничения.', FIN[-1]]
                row = parse_pdf_pages('rzd_finuslugi_rules', pages, NOW, document_sha256='d'*64)
                self.assertEqual(len(row['details']['deposit_reward_tiers']), count)
                self.assertEqual(row['details']['deposit_reward_tiers'][-1]['points'], str(1700+(count-1)*777))

    def test_duplicate_finuslugi_tiers_are_not_silently_deduplicated(self):
        pages = FIN.copy()
        pages[1] = pages[1].replace('от 200 000', 'от 10 000')
        with self.assertRaises(ValueError):
            parse_pdf_pages('rzd_finuslugi_rules', pages, NOW, document_sha256='d'*64)

    def test_primbank_added_tier_and_reflowed_pages_are_read(self):
        pages = PRIM.copy()
        pages[0] = pages[0].replace('500 приветственных', '• 4 мили при сумме покупок по карте в месяц от 300 000 руб. до 500 000 руб.\n500 приветственных')
        split = pages[0].index('За каждые')
        pages = [pages[0][:split], pages[0][split:]] + pages[1:]
        row = parse_pdf_pages('af_primbank_rules', pages, NOW, document_sha256='a'*64)
        self.assertEqual(len(row['details']['spend_reward_tiers']), 4)
        self.assertEqual(row['details']['spend_reward_tiers'][-1]['miles'], '4')

    def test_unrecognized_primbank_tier_is_not_dropped(self):
        pages = PRIM.copy()
        pages[0] = pages[0].replace('3 мили при сумме', 'три мили при сумме')
        with self.assertRaises(ValueError):
            parse_pdf_pages('af_primbank_rules', pages, NOW, document_sha256='a'*64)

    def test_runtime_has_no_snapshot_pdf_answer_or_post_id(self):
        root = Path(__file__).parents[1]
        pdf_source = (root / 'reviewed_pdf.py').read_text()
        announcements = (root / 'announcements.py').read_text()
        self.assertNotIn('RGO_BEELINE_SHA256', pdf_source)
        self.assertNotIn('make_beeline_offer', pdf_source)
        self.assertNotIn('1635', announcements)
        self.assertFalse((root / 'utair_documents.json').exists())


if __name__ == '__main__':
    unittest.main()
