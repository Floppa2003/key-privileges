"""The real Sheets metadata mask must expose hidden document tabs to readback."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

sys.path.insert(0, str(Path(__file__).parents[1]))
from document_catalogue import HEADERS, TAB, TAB_ID, verify_documents
from sheets_normalized import NormalizedSheets
from test_document_retention import WorkbookHTTP


class DocumentVisibilityTests(unittest.TestCase):
    def test_hidden_catalogue_fails_final_readback_through_real_metadata_client(self):
        memory = WorkbookHTTP()
        memory.add(TAB, TAB_ID, 15, [HEADERS], hidden=True)
        memory.tabs[TAB]['properties']['gridProperties']['rowCount'] = 1000
        plan = {'row_count': 1000, 'rows': [HEADERS], 'state': []}
        def request(_session, method, url, **kwargs):
            return memory.request(method, url, **kwargs)
        with patch.object(requests.sessions.Session, 'request', request):
            client = NormalizedSheets('fixture-sheet', 'fixture-token')
            with self.assertRaisesRegex(ValueError, 'properties readback mismatch'):
                verify_documents(client, plan)


if __name__ == '__main__':
    unittest.main()
