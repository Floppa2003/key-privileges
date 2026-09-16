"""Fresh failure reports must reach coverage without refreshing old offers."""
import copy
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]))
import free_catalog_bundle as module
from sheets_normalized import prepare
from model import plan_rows


def report():
    now=datetime.now(timezone.utc)
    ids=[sid for sid in module.SOURCE_IDS if sid!='ekp']
    return {'run_id':'current-run','run_attempt':'1','commit':'current-commit',
            'mode':'free_access_probe','account_sessions_used':False,'free_plan_confirmed':True,
            'status':'checked','source_ids':ids,
            'started_at':(now-timedelta(seconds=5)).isoformat(),
            'finished_at':(now-timedelta(seconds=1)).isoformat(),
            'sources':[{'source_id':sid,'status':'failed','error':'provider_http_404'} for sid in ids]}


class FailurePublicationTests(unittest.TestCase):
    def invoke(self,value,*,collect=False,seed=True):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        root=Path(folder.name);source=root/'source';source.mkdir();target=root/'target';target.mkdir()
        (source/'report.json').write_text(json.dumps(value))
        payload=target/'normalized.json'
        if seed:payload.write_text('STALE_PRIOR_PAYLOAD')
        output=root/'outputs'
        args=['free_catalog_bundle.py','--input',str(source),'--out',str(target),'--separate-ekp']
        if collect:args.append('--collect')
        env={'GITHUB_RUN_ID':'current-run','GITHUB_RUN_ATTEMPT':'1','GITHUB_SHA':'current-commit','GITHUB_OUTPUT':str(output)}
        with patch.object(sys,'argv',args),patch.dict(os.environ,env),patch.object(module,'run',return_value=copy.deepcopy(value)) as reader:
            if collect:
                import coral_catalog
                with patch.object(coral_catalog,'collect',return_value={}):module.main()
                self.assertEqual(reader.call_count,1)
            else:module.main();reader.assert_not_called()
        return payload,output

    def test_five_fresh_failure_reports_are_published_without_offers(self):
        value=report();path,output=self.invoke(value)
        self.assertTrue(path.is_file(),'fresh failure-only coverage was silently discarded')
        bundle=json.loads(path.read_text());rows=prepare(bundle)
        self.assertFalse(rows['parser_offers']);self.assertEqual(len(rows['parser_coverage']),5)
        self.assertTrue(all(row[5]=='failed' for row in rows['parser_coverage']))
        self.assertEqual(bundle['observed_at'],value['started_at'])
        self.assertIn('has_payload=true',output.read_text());self.assertIn('has_records=false',output.read_text())

    def test_live_collector_empty_result_uses_current_report_not_old_payload(self):
        path,output=self.invoke(report(),collect=True)
        self.assertTrue(path.is_file());self.assertNotIn('STALE',path.read_text())
        self.assertEqual(json.loads(path.read_text())['run_id'],'current-run:1')
        self.assertIn('has_payload=true',output.read_text())

    def test_globally_stopped_reader_keeps_failure_report_without_more_requests(self):
        value=report();value['status']='stopped'
        path,output=self.invoke(value)
        self.assertTrue(path.is_file());self.assertEqual(len(json.loads(path.read_text())['sources']),5)
        self.assertIn('has_payload=true',output.read_text())

    def test_unconfirmed_free_plan_never_reuses_previous_payload(self):
        for update in ({'free_plan_confirmed':False},{'status':'not_configured'}):
            with self.subTest(update=update):
                path,output=self.invoke({**report(),**update})
                self.assertFalse(path.exists());self.assertIn('has_payload=false',output.read_text())

    def test_wrong_run_attempt_commit_or_stale_report_stays_rejected(self):
        for update in ({'run_id':'old'},{'run_attempt':'0'},{'commit':'wrong'},
                       {'started_at':(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()}):
            with self.subTest(update=update),self.assertRaises(ValueError):self.invoke({**report(),**update})

    def test_no_offer_rows_means_no_offer_writes(self):
        from sheets_normalized import SCHEMAS
        existing=[SCHEMAS['parser_offers'],['old-id']+['old evidence']*24+['manual comment']]
        original=copy.deepcopy(existing)
        self.assertEqual(plan_rows(existing,[],25),[]);self.assertEqual(existing,original)

    def test_workflow_routes_by_payload_not_offer_count(self):
        workflow=(Path(__file__).resolve().parents[2]/'.github/workflows/loyalty-free-access.yml').read_text()
        self.assertIn('has_payload: ${{ steps.collect.outputs.has_payload }}',workflow)
        self.assertIn("needs.probe.outputs.has_payload == 'true'",workflow)
        self.assertNotIn("needs.probe.outputs.has_records == 'true'",workflow)
        self.assertIn("cron: '3 6 * * 1,2,4,5'",workflow)

if __name__=='__main__':unittest.main()
