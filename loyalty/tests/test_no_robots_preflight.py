"""Public collection must not fetch or enforce robots.txt (owner decision)."""
import ast
import re
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]

class NoRobotsPreflightTests(unittest.TestCase):
    def test_collectors_and_diagnostics_have_no_robots_gates(self):
        prohibited = {'robots', '_load_robots', 'can_fetch', 'robots_document',
                      'RobotFileParser', 'RobotsCache', 'read_policy', 'policy_document',
                      'namespace_allowed'}
        found = []
        for folder in ('loyalty', 'diagnostics'):
            for path in sorted((ROOT / folder).glob('*.py')):
                for node in ast.walk(ast.parse(path.read_text())):
                    if folder=='diagnostics' and isinstance(node,ast.Name) and node.id in ('POLICY','ROBOTS'):
                        found.append(f'{path.relative_to(ROOT)}:{node.lineno}:auxiliary_endpoint')
                    if isinstance(node, ast.Attribute):
                        name=node.attr
                    elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                        name=node.func.id
                    else:
                        continue
                    if name in prohibited:
                        found.append(f'{path.relative_to(ROOT)}:{node.lineno}:{name}')
        self.assertEqual(found, [], '\n'.join(found))

    def test_workflow_inline_scripts_do_not_restore_robots_preflight(self):
        blocked=re.compile(r'Protego|robots_document|read_policy\s*\(|\.robots\s*\(|\.can_fetch\s*\(|X-Robots-Txt|protego==')
        found=[]
        for path in sorted((ROOT/'.github'/'workflows').glob('*.yml')):
            for lineno,line in enumerate(path.read_text().splitlines(),1):
                if blocked.search(line):found.append(f'{path.name}:{lineno}:{line.strip()}')
        self.assertEqual(found,[], '\n'.join(found))

if __name__ == '__main__':
    unittest.main()
