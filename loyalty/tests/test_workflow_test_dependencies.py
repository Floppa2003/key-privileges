"""Every full-suite job must install Poppler before its PDF tests run."""
import re
import unittest
from pathlib import Path

SUITE = re.compile(r'\bpython(?:3)?\s+-m\s+unittest\s+discover\s+-s\s+loyalty/tests\b')
INSTALL = re.compile(r'\bapt-get\s+install\b[^\n;&|]*\bpoppler-utils\b')


def missing_pdf_setup(raw):
    """Check the repository's block-style job/step layout without extra packages.

    This is an ordering guard, not a general YAML or shell interpreter. Only
    unconditional run steps count; a different job cannot supply the executable.
    """
    jobs = re.split(r'^  ([\w-]+):\s*\n', raw.split('jobs:\n', 1)[-1], flags=re.M)
    checked, missing = [], []
    for name, body in zip(jobs[1::2], jobs[2::2]):
        installed = False
        for step in re.split(r'(?=^      - )', body, flags=re.M):
            run = re.search(r'^(?:      - |        )run:\s*([^\n]*)\n?', step, re.M)
            if not run:
                continue
            commands = run[1]
            if commands in ('|', '|-', '>', '>-'):
                commands = '\n'.join(line[10:] for line in step[run.end():].splitlines()
                                     if line.startswith('          '))
            commands = '\n'.join(line for line in commands.splitlines()
                                 if not line.lstrip().startswith('#'))
            unconditional = not re.search(r'^        (?:if|continue-on-error):', step, re.M)
            for line in commands.splitlines():
                test = SUITE.search(line)
                install = INSTALL.search(line) if unconditional and '||' not in line else None
                if install and (not test or install.start() < test.start()):
                    installed = True
                if test:
                    checked.append(name)
                    if not installed:
                        missing.append(name)
                if install:
                    installed = True
    return checked, missing


def workflow(*steps):
    return 'jobs:\n  regression:\n    steps:\n' + ''.join(steps)


SETUP = '      - name: Install PDF test dependency\n        run: sudo apt-get update -qq && sudo apt-get install -y poppler-utils\n'
TEST = '      - run: python -m unittest discover -s loyalty/tests -v\n'


class WorkflowPdfDependencies(unittest.TestCase):
    def test_all_full_suite_jobs_install_poppler_first(self):
        root = Path(__file__).resolve().parents[2] / '.github/workflows'
        checked = []
        for path in sorted([*root.glob('*.yml'), *root.glob('*.yaml')]):
            jobs, missing = missing_pdf_setup(path.read_text())
            checked.extend((path.name, job) for job in jobs)
            with self.subTest(workflow=path.name):
                self.assertEqual(missing, [], 'Install poppler-utils before the full suite in each listed job')
        self.assertTrue(checked, 'No full-suite jobs were checked')

    def test_setup_before_suite_passes(self):
        self.assertEqual(missing_pdf_setup(workflow(SETUP, TEST)), (['regression'], []))

    def test_original_daily_order_fails(self):
        self.assertEqual(missing_pdf_setup(workflow(TEST, SETUP))[1], ['regression'])

    def test_install_in_another_job_does_not_count(self):
        raw = workflow(SETUP) + '  collect:\n    steps:\n' + TEST
        self.assertEqual(missing_pdf_setup(raw)[1], ['collect'])

    def test_conditional_or_ignored_setup_does_not_count(self):
        for option in ('if: false', 'continue-on-error: true'):
            with self.subTest(option=option):
                setup = SETUP.replace('        run:', '        ' + option + '\n        run:')
                self.assertEqual(missing_pdf_setup(workflow(setup, TEST))[1], ['regression'])

    def test_multiline_setup_and_test_order(self):
        install = 'sudo apt-get install -y poppler-utils'
        test = 'python -m unittest discover -s loyalty/tests -v'
        for lines, expected in (([install, test], []), ([test, install], ['regression']),
                                (['# ' + install, test], ['regression'])):
            with self.subTest(lines=lines):
                step = '      - run: |\n' + ''.join('          ' + line + '\n' for line in lines)
                self.assertEqual(missing_pdf_setup(workflow(step))[1], expected)


if __name__ == '__main__':
    unittest.main()
