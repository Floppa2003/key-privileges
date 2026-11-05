"""Select source-owned HSE regions without rewriting the source DOM."""
import copy
import sys
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

sys.path[:0] = [str(Path(__file__).parents[1]), str(Path(__file__).parent)]
import hse_capture_plan as capture
from hse_alumni import ROOT, PROGRAM, parse_catalog
from test_hse_alumni import card, page, section, NOW


def fixture():
    cards = card('a', 'Alpha') + card('b', 'Beta')
    details = section('a', '<h2>Alpha</h2><p>Скидка 13% по коду ALPHA_ONLY.</p>')
    details += '<div class="builder-section"><p>Предъявить карту; дополнительное ограничение.</p></div>'
    details += section('retired', '<h2>Retired</h2><p>OLD_ONLY скидка 99%.</p>')
    details += section('b', '<h2>Beta</h2><p>BETA_ONLY скидка 7%.</p>')
    value = page(cards, details).replace(
        '<div class="post__text builder_content">',
        '<div class="post__text builder_content"><div class="builder-section">'
        '<p>Общие условия: предъявить действующую карту.</p></div>', 1)
    return '<html><head></head><body>' + value + '</body></html>'


def target(name='Alpha', url=ROOT, records=None):
    value = {'url': url, 'partner': name, 'program': PROGRAM}
    if records is not None:
        value['source_records'] = records
    return value


class HseCapturePlanTests(unittest.TestCase):
    def test_all_owned_sections_prefix_and_category_are_kept_in_dom_order(self):
        actual = capture.selection(fixture(), target())
        self.assertEqual(actual['version'], 1)
        self.assertEqual([b['anchor'] for b in actual['blocks']], ['a'])
        self.assertEqual([r['role'] for r in actual['regions']],
                         ['context', 'context', 'card', 'detail', 'detail'])
        self.assertEqual([r['source_text'] for r in actual['regions']], [
            'Общие условия: предъявить действующую карту.', 'Synthetic category',
            'Alpha Скидка 91% — только превью',
            'Alpha Скидка 13% по коду ALPHA_ONLY.',
            'Предъявить карту; дополнительное ограничение.'])
        joined = ' '.join(r['source_text'] for r in actual['regions'])
        self.assertNotIn('BETA_ONLY', joined)
        self.assertNotIn('OLD_ONLY', joined)

    def test_source_record_ids_disambiguate_equal_current_partner_names(self):
        raw = page(card('a', 'Twin') + card('b', 'Twin'),
                   section('a', '<h2>Twin</h2><p>FIRST_ONLY скидка 3%.</p>') +
                   section('b', '<h2>Twin</h2><p>SECOND_ONLY скидка 8%.</p>'))
        with self.assertRaisesRegex(ValueError, 'hse_capture_ambiguous_target'):
            capture.selection(raw, target('Twin'))
        row = parse_catalog(raw, NOW)[1]
        actual = capture.selection(raw, target('Twin', records=[row]))
        self.assertEqual([b['anchor'] for b in actual['blocks']], ['b'])
        self.assertIn('SECOND_ONLY', ' '.join(r['source_text'] for r in actual['regions']))
        self.assertNotIn('FIRST_ONLY', ' '.join(r['source_text'] for r in actual['regions']))

    def test_native_id_does_not_allow_another_partner_name(self):
        beta = parse_catalog(fixture(), NOW)[1]
        with self.assertRaisesRegex(ValueError, 'hse_capture_identity'):
            capture.selection(fixture(), target(records=[beta]))

    def test_existing_url_fragment_binds_exact_current_name(self):
        actual = capture.selection(fixture(), target('Beta', ROOT + '#b'))
        self.assertEqual([b['anchor'] for b in actual['blocks']], ['b'])
        with self.assertRaisesRegex(ValueError, 'hse_capture_identity'):
            capture.selection(fixture(), target('Beta', ROOT + '#a'))

    def test_only_the_exact_public_catalogue_url_is_accepted(self):
        for url in (ROOT.replace('https:', 'http:'), ROOT + '?view=1',
                    ROOT.replace('alumni.hse.ru', 'other.example'), ROOT + 'other/',
                    ROOT + '#bad/anchor'):
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, 'hse_capture_url'):
                capture.selection(fixture(), target(url=url))

    def test_fresh_source_terms_can_change_without_overwriting_old_record(self):
        old = parse_catalog(fixture(), NOW)[0]
        saved = copy.deepcopy(old)
        raw = fixture().replace('Скидка 13%', 'Скидка 17%')
        actual = capture.selection(raw, target(records=[old]))
        self.assertIn('Скидка 17%', actual['blocks'][0]['body'])
        self.assertNotIn('Скидка 13%', actual['blocks'][0]['body'])
        self.assertEqual(old, saved)

    def test_missing_empty_and_ambiguous_detail_never_become_full_capture(self):
        cases = [page(card('a', 'Alpha'), ''),
                 page(card('a', 'Alpha'), section('a', '')),
                 page(card('a', 'Alpha'), '<div class="builder-section"><h2>Alpha</h2>'
                      '<p>Скидка 3%</p></div><div class="builder-section"><h2>Alpha</h2>'
                      '<p>Скидка 8%</p></div>')]
        for raw in cases:
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, 'hse_detail_missing'):
                capture.selection(raw, target())

    def test_substantive_unassigned_section_is_not_inferred_to_be_global_terms(self):
        details = section('a', '<h2>Alpha</h2><p>Скидка 3%</p>')
        details += '<div class="builder-section"><div class="nom"><h1>Category</h1></div></div>'
        details += '<div class="builder-section"><h2>Unlisted business</h2><p>UNKNOWN_ONLY</p></div>'
        with self.assertRaisesRegex(ValueError, 'hse_unowned_context'):
            capture.selection(page(card('a', 'Alpha'), details), target())

    def test_standalone_category_heading_is_not_an_unknown_partner(self):
        details = section('a', '<h2>Alpha</h2><p>Скидка 3%</p>')
        details += '<div class="builder-section"><div class="nom"><h1>Category</h1></div></div>'
        actual = capture.selection(page(card('a', 'Alpha'), details), target())
        self.assertEqual([r['role'] for r in actual['regions']], ['context', 'card', 'detail'])

    def test_locators_point_to_original_nodes_despite_ignored_siblings(self):
        raw = fixture().replace('<div class="fa-card__group">',
              '<div hidden><p>HIDDEN_ONLY</p></div><script>sourceOnly()</script>'
              '<style>.fixture { color: red }</style><div class="fa-card__group">', 1)
        original = BeautifulSoup(raw, 'html.parser')
        actual = capture.selection(raw, target())
        for region in actual['regions']:
            nodes = original.select(region['locator'])
            self.assertEqual(len(nodes), 1)
            evidence = capture.fragment_evidence(str(nodes[0]))
            self.assertEqual(evidence['html_sha256'], region['html_sha256'])
            self.assertEqual(evidence['source_text'], region['source_text'])
        self.assertNotIn('HIDDEN_ONLY', ' '.join(r['source_text'] for r in actual['regions']))

    def test_fragment_hash_keeps_original_html_while_text_omits_ignored_content(self):
        raw = '<div><p>Visible   text</p><span hidden>Hidden</span><!-- comment --></div>'
        first = capture.fragment_evidence(raw)
        second = capture.fragment_evidence(raw.replace('Hidden', 'Changed'))
        self.assertEqual(first['source_text'], 'Visible text')
        self.assertEqual(second['source_text'], 'Visible text')
        self.assertNotEqual(first['html_sha256'], second['html_sha256'])

    def test_inline_markup_does_not_insert_spaces_into_a_literal_code(self):
        joined = capture.fragment_evidence('<p>Код <b>AB</b>CD</p>')
        separated = capture.fragment_evidence('<p>Код AB CD</p>')
        self.assertEqual(joined['source_text'], 'Код ABCD')
        self.assertEqual(separated['source_text'], 'Код AB CD')

    def test_inline_split_word_and_block_boundaries_keep_their_distinct_meaning(self):
        raw = '<div><p>С<span>кид</span>ка 7%</p><p>Код AB<br>CD</p></div>'
        self.assertEqual(capture.fragment_evidence(raw)['source_text'], 'Скидка 7% Код AB CD')

    def test_owned_image_only_section_is_kept_without_changing_public_block(self):
        image = '<div class="builder-section"><img src="/source-terms.png" alt="" width="400" height="300"></div>'
        details = section('a', '<h2>Alpha</h2><p>Скидка 7%</p>')
        raw = page(card('a', 'Alpha') + card('b', 'Beta'), details + image +
                   section('b', '<h2>Beta</h2><p>OTHER_ONLY</p>'))
        original_block = parse_catalog(raw, NOW)[0]['details']['public_catalog_block']
        actual = capture.selection(raw, target())
        self.assertEqual(actual['blocks'], [original_block])
        details = [r for r in actual['regions'] if r['role'] == 'detail']
        self.assertEqual(len(details), 2)
        self.assertEqual(details[1]['source_text'], '')
        self.assertIs(details[1]['visual_only'], True)
        node = BeautifulSoup(raw, 'html.parser').select_one(details[1]['locator'])
        self.assertEqual(node.select_one('img')['src'], '/source-terms.png')

    def test_image_only_anchor_does_not_promote_a_missing_text_detail(self):
        raw = page(card('a', 'Alpha'), section('a', '<img src="/source-terms.png" alt="">'))
        with self.assertRaisesRegex(ValueError, 'hse_detail_missing'):
            capture.selection(raw, target())

    def test_unowned_image_only_section_is_not_silently_discarded(self):
        details = section('a', '<h2>Alpha</h2><p>Скидка 3%</p>')
        details += '<div class="builder-section"><div class="nom"><h1>Category</h1></div></div>'
        details += '<div class="builder-section"><img src="/unassigned-terms.png" alt=""></div>'
        with self.assertRaisesRegex(ValueError, 'hse_unowned_context'):
            capture.selection(page(card('a', 'Alpha'), details), target())


if __name__ == '__main__':
    unittest.main()
