"""The job must compare observed reports against its actual selected scope."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
from source_lifecycle import health_summary
from test_lifecycle_pipeline import payload
from test_public_reward_sources import kuper

class ExpectedSourceHealth(unittest.TestCase):
    def test_missing_selected_report_is_failure_not_all_of_empty(self):
        b = payload(kuper()); b['sources'] = []; b['records'] = []
        h = health_summary(b, expected_sources=['backit_public'])
        self.assertEqual(len(h), 1)
        self.assertFalse(h[0]['healthy'])
        self.assertEqual(h[0]['status'], 'missing_source_report')

    def test_one_good_report_cannot_hide_another_selected_source(self):
        h = health_summary(payload(kuper()), expected_sources=['backit_public', 'club_avolta_public'])
        self.assertEqual({r['source_id']:r['healthy'] for r in h},
                         {'backit_public':True, 'club_avolta_public':False})

    def test_unselected_programmes_are_not_required(self):
        h = health_summary(payload(kuper()), expected_sources=['backit_public'])
        self.assertEqual(len(h),1); self.assertTrue(h[0]['healthy'])

    def test_duplicate_source_reports_fail_closed(self):
        b=payload(kuper()); b['sources']*=2
        with self.assertRaises(ValueError): health_summary(b, expected_sources=['backit_public'])
