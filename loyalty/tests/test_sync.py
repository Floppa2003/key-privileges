"""Exercise the publisher against an in-memory implementation of its HTTP boundary."""
import copy
import sys
import unittest
from pathlib import Path
from urllib.parse import unquote
sys.path.insert(0, str(Path(__file__).parents[1]))
from sheets_sync import Sheets

class FakeSheets(Sheets):
    def __init__(self):
        self.tabs = {'loyalty_partner_benefits': {'properties': {'title':'loyalty_partner_benefits', 'sheetId':1, 'gridProperties':{'rowCount':1000,'columnCount':13}}, 'values':[['DO NOT TOUCH']]}}
        self.corrupt = False
    def request(self, method, suffix='', **kwargs):
        if method == 'GET' and not suffix:
            return {'sheets':[{'properties':x['properties']} for x in self.tabs.values()]}
        if method == 'GET':
            title = unquote(suffix.split('/values/')[1]).split('!')[0].strip("'")
            a1 = unquote(suffix.split('/values/')[1]).split('!')[1]
            import re
            col = re.search(r':([A-Z]+)', a1)[1]
            width = 0
            for ch in col: width = width*26 + ord(ch)-64
            rows = [r[:width] for r in copy.deepcopy(self.tabs[title]['values'])]
            if self.corrupt and len(rows) > 1:
                rows[1][1] = 'CORRUPTED'
            return {'values':rows}
        for req in kwargs['json']['requests']:
            if 'addSheet' in req:
                props = copy.deepcopy(req['addSheet']['properties'])
                props['sheetId'] = len(self.tabs)+1
                self.tabs[props['title']] = {'properties':props,'values':[]}
            elif 'updateCells' in req:
                data = req['updateCells']; rg = data['range']
                table = next(x for x in self.tabs.values() if x['properties']['sheetId'] == rg['sheetId'])
                self.assert_owned(table)
                if len(data['rows']) != rg['endRowIndex'] - rg['startRowIndex']: raise AssertionError('Invalid row dimensions')
                for n, row in enumerate(data['rows'], rg['startRowIndex']):
                    values = row['values']
                    if len(values) != rg['endColumnIndex'] - rg['startColumnIndex']: raise AssertionError('Invalid column dimensions')
                    while len(table['values']) <= n: table['values'].append([])
                    target = table['values'][n]
                    target.extend(['']*max(0,rg['endColumnIndex']-len(target)))
                    target[rg['startColumnIndex']:rg['endColumnIndex']] = [v['userEnteredValue']['stringValue'] for v in values]
            elif 'appendDimension' in req:
                d=req['appendDimension']; table=next(x for x in self.tabs.values() if x['properties']['sheetId']==d['sheetId'])
                self.assert_owned(table); table['properties']['gridProperties']['rowCount'] += d['length']
        return {}
    @staticmethod
    def assert_owned(table):
        if not table['properties']['title'].startswith('parser_'): raise AssertionError('Write escaped parser tabs')

class IntegrationTests(unittest.TestCase):
    def test_upsert_creates_headers_preserves_manual_notes_and_does_not_touch_primary(self):
        s = FakeSheets()
        row = ['x','ekp','=literal','https://example.com','terms','needs_review','2026-09-12','hash','run']
        self.assertEqual(s.upsert('parser_inbox',[row]),1)
        s.tabs['parser_inbox']['values'][1].append('manual note')
        self.assertEqual(s.upsert('parser_inbox',[row]),0)
        newer = row.copy(); newer[4]='new terms'
        self.assertEqual(s.upsert('parser_inbox',[newer]),1)
        self.assertEqual(s.tabs['parser_inbox']['values'][1][9], 'manual note')
        self.assertEqual(s.tabs['loyalty_partner_benefits']['values'], [['DO NOT TOUCH']])
    def test_cannot_choose_primary_tab(self):
        with self.assertRaises(ValueError): FakeSheets().upsert('loyalty_partner_benefits',[])
    def test_corrupted_readback_raises(self):
        s=FakeSheets(); s.corrupt=True
        with self.assertRaises(ValueError): s.upsert('parser_inbox',[['x']*9])
    def test_existing_unrelated_schema_is_not_overwritten(self):
        s=FakeSheets(); s.ensure_tab('parser_inbox')
        s.tabs['parser_inbox']['values'][0][0] = 'Manually managed'
        with self.assertRaises(ValueError): s.upsert('parser_inbox',[])

if __name__ == '__main__': unittest.main()
