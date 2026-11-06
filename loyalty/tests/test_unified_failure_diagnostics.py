"""The public CLI exposes safe Sheets failure codes without private data."""
import contextlib
import io
import runpy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class UnifiedFailureDiagnosticsTests(unittest.TestCase):
    def output(self, error):
        output = io.StringIO()
        env = {
            'DISCOUNTS_SPREADSHEET_ID': 'SYNTHETIC_SPREADSHEET_ID',
            'GOOGLE_ACCESS_TOKEN': 'SYNTHETIC_TEST_TOKEN',
        }
        with patch.dict('os.environ', env), patch.object(sys, 'argv', ['unified_publish.py', '--publish']):
            with patch('unified_inputs.read_tables', side_effect=error), contextlib.redirect_stdout(output):
                with self.assertRaises(SystemExit) as failed:
                    runpy.run_path(str(ROOT / 'unified_publish.py'), run_name='__main__')
        self.assertEqual(failed.exception.code, 1)
        result = output.getvalue()
        self.assertIn('publication is not certified', result)
        self.assertNotIn('SYNTHETIC_TEST_TOKEN', result)
        return result

    def test_known_sheets_http_status_is_available_for_diagnosis(self):
        for status in (400, 401, 403, 429, 500, 503):
            with self.subTest(status=status):
                self.assertIn('"sheets_http_status":' + str(status),
                              self.output(RuntimeError('Google Sheets HTTP ' + str(status))))

    def test_known_network_failure_has_a_distinct_safe_marker(self):
        message = 'Google Sheets network failure; commit state must be checked before retry'
        self.assertIn('"sheets_network_failure":true', self.output(RuntimeError(message)))

    def test_other_exception_messages_remain_private(self):
        errors = (
            RuntimeError('Google Sheets HTTP 429 PRIVATE_TEST_VALUE'),
            RuntimeError('Google Sheets HTTP 429\nPRIVATE_TEST_VALUE'),
            RuntimeError('Private cell: PRIVATE_TEST_VALUE'),
            ValueError('Google Sheets HTTP 429'),
            ValueError('PRIVATE_TEST_VALUE'),
        )
        for error in errors:
            with self.subTest(error_type=type(error).__name__):
                result = self.output(error)
                self.assertNotIn('PRIVATE_TEST_VALUE', result)
                self.assertNotIn('sheets_http_status', result)
                self.assertNotIn('sheets_network_failure', result)


if __name__ == '__main__':
    unittest.main()
