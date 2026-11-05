"""Document link classification must match the reviewed public PDF route."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
import rzd_external as r
from normalized import validate_offer
from test_rzd_external import bank, NOW


class BankDocumentDiscoveryTests(unittest.TestCase):
    def test_uppercase_pdf_suffix_remains_a_published_document_reference(self):
        url = 'https://www.unicreditbank.ru/content/dam/new/reward-rules.PDF'
        row = r.bank_record(bank(url), NOW)
        self.assertEqual(row['details']['public_bank']['documents'], [
            {'url': url, 'label': 'Правила выплаты вознаграждения'},
        ])
        self.assertFalse(row['details']['rzd_exchange_confirmed'])
        validate_offer(row)

    def test_document_classification_keeps_existing_query_restriction(self):
        with self.assertRaises(ValueError):
            r.bank_record(bank('https://www.unicreditbank.ru/content/dam/new/reward-rules.PDF?download=1'), NOW)


if __name__ == '__main__':
    unittest.main()
