"""Respect the source document base instead of inventing nested navigation URLs."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
import rzd_external as r
import test_rzd_external as f

class BaseTests(unittest.TestCase):
    def page(self,base):return '<html><head>'+base+'</head><body><a href="kruiznyie-turyi/kruiznyie-poezda/current-tour">Tour</a><a href="o-kompanii">About</a></body></html>'
    def test_source_base_discovers_tour_and_does_not_invent_navigation_targets(self):
        raw=self.page('<base href="https://rzdtour.com/">')
        links,unread=r.tour_links(raw,r.TOUR.rstrip('/')+r.PREFIX)
        self.assertEqual(links,[r.TOUR.rstrip('/')+r.PREFIX+'current-tour']);self.assertEqual(unread,[])
    def test_sanitized_html_preserves_base_semantics(self):
        raw=r.clean_html(self.page('<base href="https://rzdtour.com/">'),r.TOUR.rstrip('/')+r.PREFIX)
        self.assertEqual(r.tour_links(raw,r.TOUR.rstrip('/')+r.PREFIX)[0],[r.TOUR.rstrip('/')+r.PREFIX+'current-tour'])
    def test_foreign_or_ambiguous_base_fails_instead_of_silently_changing_scope(self):
        for base in ('<base href="https://foreign.example/">','<base href="https://rzdtour.com/"><base href="https://rzdtour.com/">','<base href="https://rzdtour.com/?token=x">'):
            with self.subTest(base=base),self.assertRaisesRegex(ValueError,'re_document_base'):
                r.tour_links(self.page(base),r.TOUR.rstrip('/')+r.PREFIX)
    def test_without_base_normal_relative_url_semantics_remain(self):
        raw='<a href="next-tour">Next</a>'
        self.assertEqual(r.tour_links(raw,r.TOUR.rstrip('/')+r.PREFIX)[0],[r.TOUR.rstrip('/')+r.PREFIX+'next-tour'])
    def test_root_relative_base_is_supported(self):
        self.assertEqual(r.tour_links(self.page('<base href="/">'),r.TOUR.rstrip('/')+r.PREFIX)[0],[r.TOUR.rstrip('/')+r.PREFIX+'current-tour'])
    def test_actual_query_links_remain_reported_after_base_resolution(self):
        raw=self.page('<base href="/">').replace('current-tour','current-tour?page=2')
        links,unread=r.tour_links(raw,r.TOUR.rstrip('/')+r.PREFIX)
        self.assertEqual(links,[]);self.assertEqual(unread,[r.TOUR.rstrip('/')+r.PREFIX+'current-tour?page=2'])
    def test_pdf_title_uses_discovered_rule_label_not_bare_page_number(self):
        parent=r.bank_record(f.bank(),f.NOW);entry={'url':f.PDF,'label':'New public reward rules 2027'}
        rows=r.bank_pdf_records(f.pdf(['1\nFull source rules.'],title=''),entry,parent,f.NOW)
        self.assertEqual(rows[0]['title'],entry['label'])
        self.assertIn('Full source rules.',rows[0]['conditions_text'])
