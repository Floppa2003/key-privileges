"""Native Sheet migration exercised against its observed formula and headers."""
import copy
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
import ui_freshness as ui

LIVE=json.loads((Path(__file__).parent/'fixtures_live/catalogue-native-formula-2026-11-15.json').read_text())


class NativeUI:
    def __init__(self):
        self.width=14;self.requests=[]
        self.values={ui.FORMULA_RANGE:[[LIVE['formula']]],ui.NOTE_RANGE:[['Existing catalogue note']],
                     "'Скидки'!A9:O9":[LIVE['headers'].copy()]}
    def metadata(self):
        return {ui.UI_TAB:{'sheetId':ui.UI_ID,'gridProperties':{'columnCount':self.width,'rowCount':30010}}}
    def read(self,client,cell):
        if cell==ui.OLD_HEADER_RANGE:cell=ui.HEADER_RANGE
        return copy.deepcopy(self.values.get(cell,[]))
    def request(self,method,suffix='',**kw):
        assert method=='POST'
        for r in kw['json']['requests']:
            self.requests.append(copy.deepcopy(r))
            if 'insertDimension' in r:
                d=r['insertDimension']['range'];self.width+=d['endIndex']-d['startIndex']
            if 'updateCells' in r:
                u=r['updateCells'];start=u['start'];position=(start['rowIndex'],start['columnIndex'])
                cell={(9,0):ui.FORMULA_RANGE,(5,2):ui.NOTE_RANGE,(8,0):"'Скидки'!A9:O9"}.get(position)
                if cell:
                    self.values[cell]=[[next(iter(c['userEnteredValue'].values())) for c in row['values']] for row in u['rows']]
        return {}


class NativeMigrationTests(unittest.TestCase):
    def test_migrate_readback_and_repeat_without_inserting_second_column(self):
        client=NativeUI();old=copy.deepcopy(client.values)
        plan=ui.prepare_ui(client,client.metadata(),client.read)
        ui.apply_ui(client,plan,client.read);ui.verify_ui(client,plan,client.read)
        self.assertEqual(client.width,15)
        self.assertEqual(client.values["'Скидки'!A9:O9"][0][10],'Копия документа')
        formula=client.values[ui.FORMULA_RANGE][0][0]
        self.assertIn("'_ui_catalog'!A2:R",formula)
        self.assertIn('CHOOSECOLS(d;1;2;3;4;5;6;7;8;9;10;18;11;12;13;14)',formula)
        for clause in ('$B$3','$B$4','$B$5','TODAY()-7','normalization_audit!J7'):
            self.assertIn(clause,formula)
        self.assertEqual(client.values["'Скидки'!A9:O9"][0][11:],old["'Скидки'!A9:O9"][0][10:])
        count=len(client.requests)
        again=ui.prepare_ui(client,client.metadata(),client.read)
        ui.apply_ui(client,again,client.read);ui.verify_ui(client,again,client.read)
        self.assertEqual(len(client.requests),count)

    def test_custom_header_or_projection_stops_before_writing(self):
        for change in ('header','formula'):
            client=NativeUI()
            if change=='header':client.values["'Скидки'!A9:O9"][0][10]='Owner field'
            else:client.values[ui.FORMULA_RANGE][0][0]=LIVE['formula'].replace('CHOOSECOLS(d;1;2;3;4;5;6;7;8;9;10;11;12;13;14)','CHOOSECOLS(d;1;2)')
            with self.assertRaises(ValueError):ui.prepare_ui(client,client.metadata(),client.read)
            self.assertEqual(client.requests,[])

    def test_concurrent_header_change_and_readback_corruption_are_detected(self):
        client=NativeUI();plan=ui.prepare_ui(client,client.metadata(),client.read)
        client.values["'Скидки'!A9:O9"][0][0]='Edited'
        with self.assertRaises(ValueError):ui.apply_ui(client,plan,client.read)
        self.assertEqual(client.requests,[])
        client=NativeUI();plan=ui.prepare_ui(client,client.metadata(),client.read)
        ui.apply_ui(client,plan,client.read)
        client.values[ui.FORMULA_RANGE]=[['=1']]
        with self.assertRaises(ValueError):ui.verify_ui(client,plan,client.read)


if __name__=='__main__':unittest.main()
