"""The real request script must not dispatch on wrong ref or missing configuration."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).parents[1] / 'request.sh'

class RequestTests(unittest.TestCase):
    def run_script(self, overrides=None, cli_status=0):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            gh = p / 'gh'
            gh.write_text('#!/usr/bin/env python3\nimport json, os, sys\nfrom pathlib import Path\nPath(os.environ["CAPTURE"]).write_text(json.dumps(sys.argv[1:]))\nsys.exit(int(os.environ["CLI_STATUS"]))\n')
            gh.chmod(0o700)
            env = {**os.environ, 'PATH': d + os.pathsep + os.environ['PATH'],
                   'CAPTURE':str(p/'capture.json'), 'CLI_STATUS':str(cli_status),
                   'GITHUB_REPOSITORY':'Floppa2003/key-privileges',
                   'GITHUB_REF':'refs/heads/main', 'LOYALTY_SHEETS_SYNC':'true',
                   'GOOGLE_SERVICE_ACCOUNT':'test@example.iam.gserviceaccount.com',
                   'GOOGLE_WORKLOAD_IDENTITY_PROVIDER':'test-provider',
                   'DISCOUNTS_SPREADSHEET_ID':'private-destination-do-not-print',
                   'GH_TOKEN':'synthetic-token-do-not-print'}
            env.update(overrides or {})
            result = subprocess.run(['bash',str(SCRIPT)], env=env, capture_output=True, text=True)
            calls = json.loads((p/'capture.json').read_text()) if (p/'capture.json').exists() else None
            return result, calls

    def test_valid_configuration_dispatches_only_target_workflow_on_main(self):
        result, args = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(args, ['workflow','run','loyalty.yml','--repo','Floppa2003/key-privileges','--ref','main','-f','limit=200','-f','publish=true'])
        self.assertNotIn('private-destination-do-not-print', result.stdout+result.stderr)
        self.assertNotIn('synthetic-token-do-not-print', result.stdout+result.stderr)

    def test_wrong_branch_never_dispatches(self):
        result, args = self.run_script({'GITHUB_REF':'refs/heads/feature'})
        self.assertNotEqual(result.returncode,0)
        self.assertIsNone(args)

    def test_fork_never_dispatches(self):
        result, args = self.run_script({'GITHUB_REPOSITORY':'somebody/key-privileges'})
        self.assertNotEqual(result.returncode,0)
        self.assertIsNone(args)

    def test_disabled_or_incomplete_configuration_never_dispatches(self):
        for key in ('LOYALTY_SHEETS_SYNC','GOOGLE_SERVICE_ACCOUNT','GOOGLE_WORKLOAD_IDENTITY_PROVIDER','DISCOUNTS_SPREADSHEET_ID','GH_TOKEN'):
            with self.subTest(key=key):
                result, args = self.run_script({key:''})
                self.assertNotEqual(result.returncode,0)
                self.assertIsNone(args)

    def test_cli_error_is_not_claimed_to_be_success(self):
        result, args = self.run_script(cli_status=4)
        self.assertNotEqual(result.returncode,0)
        self.assertIsNotNone(args)
        self.assertNotIn('DISPATCH_ACCEPTED',result.stdout)

if __name__ == '__main__':
    unittest.main()
