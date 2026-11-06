"""Formatting outside an XML location cannot hide a discovered Coral offer."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import coral_import as coral
from test_coral_import import CATEGORY, NOW, PROMO, URL, Source, obs, page, source_map, targets


class CoralSitemapBoundariesTests(unittest.TestCase):
    def test_outer_xml_whitespace_keeps_the_same_candidate_identity(self):
        expected = [URL, PROMO]
        for wrapped in (' ' + URL + ' ', '\n  ' + URL + '\n', '\r\n\t' + URL + '\r\n\t'):
            with self.subTest(location=wrapped):
                entries, categories, promotions = targets([wrapped])
                self.assertEqual([entry['url'] for _, entry in entries], expected)
                self.assertEqual((categories, promotions), (1, 1))
                self.assertEqual(entries[0][1]['parent_url'], CATEGORY)

    def test_wrapped_location_cannot_make_a_partial_inventory_look_complete(self):
        second = CATEGORY + 'second-course/'

        class SavedPages(Source):
            def read(self, url):
                if url == coral.SITEMAP:
                    observation = obs(url, source_map([URL, '\n  ' + second + '\n']))
                elif url == second:
                    observation = obs(url, page(second, 23))
                else:
                    return super().read(url)
                self.observations.append(observation)
                return observation

        bundle = coral.collect(SavedPages(), 'test:1', NOW)
        records = [row for row in bundle['records'] if row['source_id'] == 'coral']
        self.assertEqual([row['source_url'] for row in records], [URL, second])
        report = next(row for row in bundle['sources'] if row['source_id'] == 'coral')
        self.assertEqual((report['discovered'], report['normalized'], report['status']), (2, 2, 'ok'))
        self.assertEqual(json.loads(report['coverage'])['unresolved'], 0)
        coral.prepare(bundle)

    def test_duplicate_locations_after_outer_trim_still_fail(self):
        with self.assertRaisesRegex(ValueError, 'cg_sitemap_duplicate_or_bound'):
            targets([URL, '\n  ' + URL + '\n'])

    def test_inner_url_whitespace_is_not_removed_or_silently_ignored(self):
        for separator in (' ', '\t', '\r', '\n'):
            for bad in (URL.replace('new-course', 'new-' + separator + 'course'),
                        URL.replace('coralbonus', 'coral' + separator + 'bonus')):
                with self.subTest(location=bad):
                    with self.assertRaisesRegex(ValueError, 'cg_sitemap_url'):
                        coral.sanitize(source_map([bad]), coral.SITEMAP)

    def test_outer_trim_does_not_relax_url_scope_or_length(self):
        for bad in (URL.replace('https://', 'http://'),
                    URL.replace('coralbonus.ru', 'example.test'),
                    URL.replace('coralbonus.ru', 'user@coralbonus.ru'),
                    URL + '?extra=1', URL + '#fragment',
                    ' ' * 800 + URL):
            with self.subTest(location=bad):
                with self.assertRaisesRegex(ValueError, 'cg_sitemap_url'):
                    coral.sanitize(source_map(['\n ' + bad + '\n']), coral.SITEMAP)


if __name__ == '__main__':
    unittest.main()
