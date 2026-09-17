"""A successful HTTP envelope is not a PDF; one bounded route change may help."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
import coral_pdf_collect as p
from test_coral_pdf_collect import Network, Response, URL, KEY, NOW
import test_coral_pdf_collect as fixtures
from test_document_text import pdf


class Sequence(Network):
    def __init__(self, responses):
        super().__init__()
        self.responses = list(responses)

    def __call__(self, url, **kwargs):
        if url.endswith('/usage'):
            return super().__call__(url, **kwargs)
        self.calls.append((url, kwargs))
        if not self.responses:
            raise AssertionError('unexpected_extra_request')
        return self.responses.pop(0)


def html(body=b'<html><title>Temporary response</title></html>', cost='1'):
    return Response(body, headers={'Content-Type': 'text/html; charset=utf-8', 'Ant-credits-cost': cost})


def binary():
    return Response(pdf(['Fresh source terms, not a stored answer.']), headers={'Ant-credits-cost': '25'})


class HtmlEnvelopeTests(unittest.TestCase):
    def test_html_200_then_real_pdf_uses_one_bounded_alternate_route(self):
        network = Sequence([html(), binary()])
        reader = network.reader(KEY)
        data, receipt = reader.read(URL)
        self.assertTrue(data.startswith(b'%PDF-'))
        self.assertEqual(receipt, 1)
        self.assertEqual([x['proxy'] for x in reader.requests], ['datacenter', 'residential'])
        self.assertEqual(reader.requests[0]['error'], 'cp_pdf_html_response')
        self.assertEqual(reader.reserved, 26)
        self.assertEqual(reader.charged, 26)
        self.assertNotIn('result', reader.requests[0])

    def test_two_html_responses_remain_a_failure_without_a_third_attempt(self):
        reader = Sequence([html(), html(cost='25')]).reader(KEY)
        with self.assertRaisesRegex(ValueError, 'cp_pdf_html_response'):
            reader.read(URL)
        self.assertEqual(len(reader.requests), 2)
        self.assertFalse(any(r.get('result') == 'pdf' for r in reader.requests))

    def test_non_html_wrong_mime_and_bad_pdf_magic_are_not_route_retries(self):
        for response in (Response(b'{}', headers={'Content-Type':'application/json'}), Response(b'not a pdf')):
            reader = Sequence([response]).reader(KEY)
            with self.subTest(response=response), self.assertRaises(ValueError):
                reader.read(URL)
            self.assertEqual(len(reader.requests), 1)

    def test_html_quota_login_and_secret_echo_stop_without_another_route(self):
        for body in (b'<html>Too many requests</html>', b'<html><input type="password"></html>', KEY.encode()):
            reader = Sequence([html(body)]).reader(KEY)
            with self.subTest(body=body), self.assertRaises(ValueError):
                reader.read(URL)
            self.assertEqual(len(reader.requests), 1)
            self.assertTrue(reader.stopped)

    def test_existing_reservation_bound_prevents_an_extra_route(self):
        reader = Sequence([html(), binary()]).reader(KEY)
        reader.reserved = p.MAX_CREDITS - 1
        with self.assertRaisesRegex(ValueError, 'cp_budget_or_stopped'):
            reader.read(URL)
        self.assertEqual(len(reader.requests), 1)
        self.assertEqual(reader.reserved, p.MAX_CREDITS)

    def test_full_collector_and_publisher_reconstruct_recovered_binary(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            bundle = fixtures.PdfTests().collect(root, Sequence([html(), binary()]))
            self.assertEqual(bundle['sources'][-1]['status'], 'ok')
            self.assertEqual(bundle['sources'][-1]['normalized'], 1)
            self.assertEqual(p.validate_bundle(root, '7:1', 'a'*40, NOW), bundle)
            self.assertEqual(len(list((root/'pdf').glob('*.pdf'))), 1)

    def test_reconstruction_rejects_a_route_change_after_terminal_failure(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fixtures.PdfTests().collect(root, Sequence([html(), binary()]))
            audit = json.loads((root/'pdf-report.json').read_text())
            audit['requests'][0]['error'] = 'cp_provider_auth_quota_or_rate_limit'
            (root/'pdf-report.json').write_text(json.dumps(audit))
            with self.assertRaisesRegex(ValueError, 'cp_fallback_reason'):
                p.validate_bundle(root, '7:1', 'a'*40, NOW)

    def test_source_and_provider_rate_limits_keep_the_terminal_contract(self):
        for headers, status in (({'Ant-page-status-code':'429'}, 200), ({'Retry-After':'30'}, 200), ({}, 429)):
            reader = Sequence([Response(b'', status=status, headers=headers)]).reader(KEY)
            with self.subTest(headers=headers, status=status), self.assertRaises(ValueError):
                reader.read(URL)
            self.assertEqual(len(reader.requests), 1)
            self.assertTrue(reader.stopped)


if __name__ == '__main__':
    unittest.main()
