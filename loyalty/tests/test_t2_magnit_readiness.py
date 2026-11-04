"""Wait for the owned T2 article before parsing; never accept an HTTP-200 shell.

The ready DOM is extracted from the original page in run 41931973515. The
empty initial DOM is a controlled delay, matching the absent-selector failure
reported by collection runs 41454716914 and 41834875353; those failed DOMs
were not archived and their exact timing is not asserted here.
"""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).parents[1]), str(Path(__file__).parent)]
import collect_normalized as collector
from test_html_hydration import HydratingPage, ReplaySource

URL='https://msk.t2.ru/help/article/magnit-plus-premium'
NOW='2026-11-04T23:14:12.440964+00:00'
SELECTORS=['.support-article__article-title', '.article-content']
READY=(Path(__file__).with_name('fixtures_live')/'t2-magnit-20261104.html').read_text()
SHELL='<html><head><title>Магнит Плюс Премиум - служба поддержки T2</title></head><body></body></html>'
CFG=next(c for c in json.loads((Path(__file__).parents[1]/'sources_normalized.json').read_text())
         if c['id']=='t2_magnit_rules')


class T2MagnitReadiness(unittest.IsolatedAsyncioTestCase):
    async def collect(self, page):
        with patch.object(collector, 'PublicSource', ReplaySource):
            return await collector.one(page, CFG, NOW, 500)

    async def test_actual_source_waits_for_both_owned_blocks_before_parsing(self):
        page=HydratingPage(initial=SHELL, hydrated=READY, final_url=URL)
        report, rows=await self.collect(page)
        self.assertEqual(report['status'], 'ok', report['errors'])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['record_kind'], 'program_rules')
        self.assertTrue(rows[0]['details']['activation']['same_phone_required'])
        for term in ('MiXX S', 'MiXX M', 'MiXX Max', 'Воспользоваться'):
            self.assertIn(term, rows[0]['conditions_text'])
        self.assertEqual([call[1] for call in page.ready_calls], [SELECTORS])
        self.assertEqual(page.gotos, 1)
        self.assertEqual(page.listeners, {})

    async def test_missing_or_empty_owned_block_remains_failed(self):
        for hydrated in (None,
                         READY.replace('support-article__article-title', 'missing-heading'),
                         READY.replace('class="article-content"', 'class="missing-article"')):
            with self.subTest(hydrated=hydrated is None):
                page=HydratingPage(initial=SHELL, hydrated=hydrated, final_url=URL)
                report, rows=await self.collect(page)
                self.assertEqual(report['status'], 'failed')
                self.assertEqual(rows, [])
                self.assertEqual(report['errors'][0]['reason'], 'page_content_not_ready')
                self.assertEqual(page.ready_calls[0][2], 10000)
                self.assertEqual(page.gotos, 1)
                self.assertEqual(page.listeners, {})

    async def test_access_denial_is_not_retried_as_hydration(self):
        page=HydratingPage(initial=SHELL, hydrated=READY, status=403, final_url=URL)
        report, rows=await self.collect(page)
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(rows, [])
        self.assertEqual(report['errors'][0]['reason'], 'http_403')
        self.assertEqual(page.ready_calls, [])
        self.assertEqual(page.gotos, 1)


if __name__=='__main__':unittest.main()
