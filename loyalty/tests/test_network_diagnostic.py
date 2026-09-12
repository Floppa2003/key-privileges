"""Reject false successes, unsafe targets and misleading robots conclusions."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'diagnostics'))
try:
    import network_probe as n
except ImportError:
    n = None

class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(n, 'network diagnostic not implemented')

    def test_robots_403_does_not_imply_target_403(self):
        self.assertEqual(n.robots_result(403, 'Forbidden'), 'unavailable_4xx')
        self.assertEqual(n.robots_result(503, 'Unavailable'), 'unreachable')
        self.assertEqual(n.robots_result(None, ''), 'unreachable')
        self.assertEqual(n.robots_result(429, ''), 'rate_limited')

    def test_html_200_is_not_a_robots_policy(self):
        self.assertEqual(n.robots_result(200, '<html>Access denied</html>'), 'invalid_document')
        self.assertEqual(n.robots_result(200, 'User-agent: *\nDisallow: /private'), 'parseable')

    def test_title_challenge_precedes_benefit_keywords(self):
        x=n.document_summary('<title>Access denied</title><main>скидка 10%</main>', 'https://example.org/a')
        self.assertTrue(x['challenge'])
        self.assertFalse(x['benefit_evidence'])

    def test_no_full_success_from_http200_shell(self):
        x=n.document_summary('<title>Каталог</title><div id="app"></div>', 'https://example.org/a')
        self.assertFalse(x['benefit_evidence'])

    def test_success_keeps_same_host_discovered_links(self):
        x=n.document_summary('<title>Предложения</title><main>Скидка 10% для участников программы</main><a href="/card/7">Партнёр</a><a href="https://evil.test">external</a>', 'https://example.org/a')
        self.assertTrue(x['benefit_evidence'])
        self.assertEqual(x['links'], [{'url':'https://example.org/card/7','label':'Партнёр'}])

    def test_credentials_nonhttps_and_private_hosts_are_rejected(self):
        for url in ['http://example.org', 'https://a:b@example.org/', 'https://127.0.0.1/', 'https://example.org/?token=x', 'https://example.org/login', 'https://example.org:444/']:
            self.assertFalse(n.safe_url(url, {'example.org'}),url)
        self.assertTrue(n.safe_url('https://example.org/card/7?region=78', {'example.org'}))

    def test_oversized_summary_has_explicit_capture_limit(self):
        x=n.document_summary('<main>'+'скидка 10% ' * 10000+'</main>', 'https://example.org/a')
        self.assertLessEqual(len(x['excerpt']), 600)
        self.assertTrue(x['excerpt_is_partial'])

    def test_exception_chain_retains_cert_reason_not_only_timeout(self):
        import ssl
        err=ssl.SSLCertVerificationError(1, 'certificate has expired')
        x=n.error_info(err)
        self.assertIn('certificate has expired',x['message'])

if __name__ == '__main__': unittest.main()
