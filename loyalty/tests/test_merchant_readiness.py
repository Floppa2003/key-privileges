"""Exercise the actual readiness predicate during a transient empty document."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import merchant_evidence as evidence


class ReadinessTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_body_is_pending_then_hydrated_target_is_ready(self):
        class Page:
            async def evaluate(self, expression):
                return None

            async def wait_for_function(self, expression, *, arg, timeout):
                script = (
                    'const predicate=(' + expression + ');'
                    'global.document={body:null};'
                    'const pending=predicate(' + json.dumps(arg) + ');'
                    'document.body={innerText:"Independent merchant\\nСкидка 17%"};'
                    'const ready=predicate(' + json.dumps(arg) + ');'
                    'process.stdout.write(JSON.stringify([pending,ready]));'
                )
                result = subprocess.run(['node', '-e', script], capture_output=True, text=True)
                if result.returncode:
                    raise AssertionError('Readiness crashed on transient DOM: ' + result.stderr)
                if json.loads(result.stdout) != [False, True]:
                    raise AssertionError('Readiness must wait for the named target')

        result = await evidence.prepare_public_page(Page(), {
            'url': 'https://fixture.example/offer', 'partner': 'Independent merchant'})
        self.assertTrue(result['target_found'])
        self.assertTrue(result['content_ready'])


if __name__ == '__main__':
    unittest.main()
