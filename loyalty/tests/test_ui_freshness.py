"""Native freshness filtering is scoped, idempotent, and cannot stomp a user edit."""
import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
import ui_freshness as u
from test_document_ui_migration import NativeUI
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
        client=NativeUI();plan=u.prepare_ui(client,client.metadata(),client.read)
        client.values[u.NOTE_RANGE]=[['edited']]
        with self.assertRaises(ValueError):u.apply_ui(client,plan,client.read)
        self.assertEqual(client.requests,[])
    def test_only_catalogue_ui_cells_are_written_and_readback_required(self):
        client=NativeUI();plan=u.prepare_ui(client,client.metadata(),client.read)
        with self.assertRaises(ValueError):u.verify_ui(client,plan,client.read)
        u.apply_ui(client,plan,client.read)
        cells=[r['updateCells']['start'] for r in client.requests if 'updateCells' in r]
        self.assertEqual([(r['rowIndex'],r['columnIndex']) for r in cells],[(8,0),(9,0),(5,2)])
        self.assertTrue(all(r['sheetId']==u.UI_ID for r in cells))
        u.verify_ui(client,plan,client.read)
