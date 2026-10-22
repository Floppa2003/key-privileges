"""Every registered route is visible; a completed worker is not a healthy source."""
import copy
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
from source_lifecycle import health_summary
from test_lifecycle_pipeline import payload
from test_public_reward_sources import kuper

class AllRouteHealthTests(unittest.TestCase):
    def report(self, sid, status='failed', count=0, errors=None):
        return dict(source_id=sid, status=status, normalized=count, discovered=count,
                    errors=errors if errors is not None else [{'reason':'http_403','phase':'source'}])

    def test_non_lifecycle_sources_cannot_disappear_from_health(self):
        b=payload(kuper());b['sources'].append(self.report('smartavia_rules'))
        h={r['source_id']:r for r in health_summary(b)}
        self.assertIn('smartavia_rules',h)
        self.assertFalse(h['smartavia_rules']['healthy'])

    def test_missing_selected_non_lifecycle_source_is_reported(self):
        b=payload(kuper())
        h={r['source_id']:r for r in health_summary(b,expected_sources=['backit_public','hse_alumni'])}
        self.assertEqual(h['hse_alumni']['status'],'missing_source_report')

    def test_zero_records_and_errors_are_not_partial_success(self):
        b=payload(kuper());b['sources'].append(self.report('mir','partial'))
        r=next(r for r in health_summary(b) if r['source_id']=='mir')
        self.assertFalse(r['healthy'])
        self.assertEqual(r['extraction_state'],'failed')

    def test_probe_is_explicitly_not_an_implemented_collector(self):
        b=payload(kuper());b['sources'].append(self.report('aeroflot'))
        r=next(r for r in health_summary(b) if r['source_id']=='aeroflot')
        self.assertEqual(r['route_kind'],'access_probe')
        self.assertEqual(r['extraction_state'],'not_implemented_in_this_route')
        self.assertFalse(r['healthy'])

    def test_implemented_legacy_special_routes_are_not_probes(self):
        configs={c['id']:c for c in json.loads((Path(__file__).parents[1]/'sources_normalized.json').read_text())}
        for sid in ('utair','alfa_only_public_rules','alfa_only_cashback_rules','alfa_only_partner_pdf_offers'):
            self.assertNotEqual(configs[sid]['mode'],'probe')
            b=payload(kuper());b['sources'].append(self.report(sid))
            row=next(r for r in health_summary(b) if r['source_id']==sid)
            self.assertEqual(row['route_kind'],'collector')
            self.assertEqual(row['extraction_state'],'failed')

    def test_healthy_lifecycle_inventory_contract_is_preserved(self):
        b=payload(kuper());r=health_summary(b)[0]
        self.assertTrue(r['healthy'])
        self.assertTrue(r['inventory_complete'])

    def test_incorrect_report_record_count_is_not_healthy(self):
        b=payload(kuper());b['sources'].append(self.report('noname','ok',3,[]))
        r=next(r for r in health_summary(b) if r['source_id']=='noname')
        self.assertFalse(r['healthy'])
        self.assertEqual(r['extraction_state'],'record_count_mismatch')

if __name__=='__main__':unittest.main()
