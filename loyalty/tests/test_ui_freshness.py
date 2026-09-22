"""Native freshness filtering is scoped, idempotent, and cannot stomp a user edit."""
import sys, unittest
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).parents[1]))
import ui_freshness as u
F='=ARRAYFORMULA(LET(d;FILTER(\'_ui_catalog\'!A2:Q;1);keep;hits*IF($B$4="";1;1);FILTER(d;keep)))'
class NativeFreshnessTests(unittest.TestCase):
    def test_only_keep_predicate_is_extended_and_existing_search_preserved(self):
        new=u.upgrade_formula(F)
        self.assertIn('TODAY()-7',new)
        self.assertTrue(new.endswith('IF($B$4="";1;1);FILTER(d;keep)))'))
        self.assertIn('IFERROR(',new)
        for name in u.PROGRAMMES:self.assertIn(name,new)
        self.assertEqual(u.upgrade_formula(new),new)
    def test_unreviewed_or_modified_formula_rejected(self):
        for f in ('hello','=A1',F.replace('keep;hits*','other;hits*'),u.upgrade_formula(F).replace('TODAY()-7','TODAY()-70')):
            with self.assertRaises(ValueError):u.upgrade_formula(f)
    def test_no_new_ui_is_created(self):
        self.assertIsNone(u.prepare_ui(None,{},None))
    def test_concurrent_edit_rejected_before_write(self):
        client=Mock();read=lambda c,r:[[F]] if r==u.FORMULA_RANGE else [['old']]
        plan=u.prepare_ui(client,{u.UI_TAB:{'sheetId':u.UI_ID}},read)
        with self.assertRaises(ValueError):u.apply_ui(client,plan,lambda c,r:[['edited']])
        client.request.assert_not_called()
    def test_only_formula_and_note_are_written_and_readback_required(self):
        client=Mock();read=lambda c,r:[[F]] if r==u.FORMULA_RANGE else [['old']]
        plan=u.prepare_ui(client,{u.UI_TAB:{'sheetId':u.UI_ID}},read)
        u.apply_ui(client,plan,read)
        req=client.request.call_args.kwargs['json']['requests']
        self.assertEqual([(r['updateCells']['start']['rowIndex'],r['updateCells']['start']['columnIndex']) for r in req],[(9,0),(5,2)])
        with self.assertRaises(ValueError):u.verify_ui(client,plan,read)
        u.verify_ui(client,plan,lambda c,r:plan['after'] if r==u.FORMULA_RANGE else [[u.NOTE]])
