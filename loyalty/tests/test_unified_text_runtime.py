"""Stored source text must project in the publisher's text-only runtime."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from normalized import make_offer
from sheets_normalized import prepare
from unified_inputs import HEADERS
from unified_normalization import INPUT_TABS
from test_alfa_partner_clauses import NOW, record


class StoredProjectionRuntimeTests(unittest.TestCase):
    def test_plain_and_owned_pdf_text_publish_without_pdf_decoder(self):
        plain = make_offer(
            'moskvich', 'plain', 'Москвич', 'Example',
            'Скидка 12,5%.', 'https://moskvichmag.ru/programma-loyalnosti/', NOW,
            record_kind='partner_offer',
        )
        owned = record()
        rows = [plain, owned]
        reports = [dict(
            source_id=row['source_id'], name=row['program'],
            root=row['source_url'], status='ok', discovered=1,
            normalized=1, failed=0, coverage='fixture', region=None,
            errors=[], observed_at=NOW,
        ) for row in rows]
        bundle = dict(schema_version=2, run_id='fixture:1', observed_at=NOW,
                      records=rows, sources=reports)
        tables = {
            name: [[] for _ in range(header - 1)] +
                  [[{'value':h} for h in HEADERS[name]]]
            for name, (header, _) in INPUT_TABS.items()
        }
        tables['parser_offers'].extend(
            [{'value':v} for v in row]
            for row in prepare(bundle)['parser_offers']
        )
        # A separate interpreter prevents already-imported test dependencies
        # from hiding the missing package in the actual text-only publisher.
        child = '''
import json, sys
sys.path.insert(0, sys.argv[1])
sys.modules['pypdf'] = None
import unified_publish
from unified_inputs import inputs_from_tables
from unified_normalization import normalize_inputs
from unified_views import prepare_views
inputs, _ = inputs_from_tables(json.load(sys.stdin))
result = normalize_inputs(inputs, as_of='2026-09-19')
prepare_views(result)
print(json.dumps(result, ensure_ascii=False))
'''
        run = subprocess.run(
            [sys.executable, '-I', '-c', child, str(ROOT)],
            input=json.dumps(tables, ensure_ascii=False), text=True,
            capture_output=True, timeout=30,
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        projected = {r['id']:r for r in json.loads(run.stdout)['records']}
        self.assertEqual(set(projected), {plain['id'], owned['id']})
        self.assertEqual(
            [(b['kind'], b['value']) for b in projected[plain['id']]['benefits']],
            [('discount', '12.5')],
        )
        rewards = projected[owned['id']]['benefits']
        self.assertEqual([(b['kind'], b['value'], b['qualifier']) for b in rewards],
                         [('earn_rewards', '10', 'exact')])
        self.assertEqual(rewards[0]['reward_unit'], 'Альфа-Баллы/ Бонусные Мили')
        for row in rows:
            self.assertEqual(projected[row['id']]['raw']['observed_at'], NOW)
            self.assertEqual(projected[row['id']]['raw']['benefit'], row['benefit_text'])


if __name__ == '__main__':
    unittest.main()
