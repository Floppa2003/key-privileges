"""The CI hard timeout must leave the collector its entire bounded run.

A real acceptance job spent about fourteen minutes installing packages before
collection. The daily job must budget setup separately, not kill a valid
collector run at the old twenty-minute wall clock limit.
"""
import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SETUP_AND_ARTIFACT_SECONDS = 15 * 60


def daily_collection_budget(raw):
    jobs = re.split(r'^  ([\w-]+):\s*\n', raw.split('jobs:\n', 1)[-1], flags=re.M)
    blocks = dict(zip(jobs[1::2], jobs[2::2]))
    value = re.search(r'^    timeout-minutes:\s*(\d+)\s*$', blocks['collect'], re.M)
    return int(value[1]) * 60 if value else 0


def collector_budget():
    module = ast.parse((ROOT/'loyalty/collection_runtime.py').read_text())
    return next(ast.literal_eval(n.value) for n in module.body
                if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name)
                    and t.id == 'RUN_TIMEOUT' for t in n.targets))


class CollectionWorkflowBudget(unittest.TestCase):
    def test_daily_job_has_setup_collection_and_artifact_budget(self):
        raw = (ROOT/'.github/workflows/loyalty.yml').read_text()
        self.assertGreaterEqual(daily_collection_budget(raw),
                                collector_budget() + SETUP_AND_ARTIFACT_SECONDS)

    def test_original_twenty_minute_job_is_insufficient(self):
        raw = 'jobs:\n  collect:\n    timeout-minutes: 20\n  publish:\n    timeout-minutes: 60\n'
        self.assertLess(daily_collection_budget(raw),
                        collector_budget() + SETUP_AND_ARTIFACT_SECONDS)


if __name__ == '__main__':
    unittest.main()
