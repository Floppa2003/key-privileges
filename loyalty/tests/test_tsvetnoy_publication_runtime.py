"""Replay public source rows in the publisher's runtime without PDF parsing."""
import json
from pathlib import Path
import subprocess
import sys
import unittest


class TsvetnoyPublicationRuntime(unittest.TestCase):
    def test_public_source_projection_does_not_load_pdf_reader(self):
        loyalty = Path(__file__).parents[1]
        fixture = Path(__file__).parent / 'fixtures/tsvetnoy_publication_20261102.json'
        script = '''
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
# The publisher installs requests/BeautifulSoup and consumes saved source rows.
# Removing this optional collector dependency must not block their projection.
sys.modules['pypdf'] = None
from unified_normalization import normalize_inputs
fixture = json.loads(Path(sys.argv[2]).read_text())
result = normalize_inputs(fixture['inputs'], as_of=fixture['as_of'])
print(json.dumps([{
    'title': r['title'],
    'observed_at': r['provenance']['observed_at'],
    'benefits': [{'kind': b['kind'], 'value': b['value'], 'tier': b['scope'].get('member_tier')}
                 for b in r['benefits']],
    'conditions': r['raw']['conditions'],
} for r in result['records']], ensure_ascii=False))
'''
        process = subprocess.run(
            [sys.executable, '-c', script, str(loyalty), str(fixture)],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        rows = json.loads(process.stdout)
        self.assertEqual(len(rows), 2)
        brand = next(r for r in rows if r['title'] == 'Цветной → АТЕЛЬЕ NIKKO (-1 этаж)')
        self.assertEqual(brand['benefits'], [
            {'kind': 'discount', 'value': '10', 'tier': 'Старт'},
            {'kind': 'discount', 'value': '10', 'tier': 'Стандарт'},
            {'kind': 'discount', 'value': '10', 'tier': 'Плюс'},
        ])
        self.assertIn('не суммируются', brand['conditions'])
        self.assertIn('предъявлении карты лояльности', brand['conditions'])
        self.assertTrue(all(r['observed_at'].startswith('2026-11-02T') for r in rows))


if __name__ == '__main__':
    unittest.main()
