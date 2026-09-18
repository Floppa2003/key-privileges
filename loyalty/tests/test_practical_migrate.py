"""Native copy/verify/clear ordering and preservation under interruption."""
import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from practical_migrate import archive_existing,SOURCE,ARCHIVE
from sheets_normalized import SCHEMAS

def native(vals):return [{'userEnteredValue':{'stringValue':v}} if v else {} for v in vals]
def row(ident,detail):
    values=['']*26;values[0]=ident;values[3]='Title';values[5]='program_rules';values[8]='Exact text';values[17]='https://example.test/'+ident;values[20]=detail;values[25]='Manual comment'
    return native(values)

class NativeClient:
    def __init__(self,tamper=False):
        self.sheets={SOURCE:{'properties':{'sheetId':1,'title':SOURCE,'gridProperties':{'rowCount':3,'columnCount':26}},
            'rows':[native(SCHEMAS[SOURCE]+['Ручной комментарий']),row('bulk','{"products_are_exclusions_not_offers":true}'),row('offer','{}')]}}
        self.tamper=tamper;self.clears=0
    def metadata(self):return {k:copy.deepcopy(v['properties']) for k,v in self.sheets.items()}
    def request(self,method,suffix='',**kwargs):
        if method=='GET':
            name=kwargs['params']['ranges'].split("'")[1];s=copy.deepcopy(self.sheets[name])
            if name==ARCHIVE and self.tamper and len(s['rows'])>1:s['rows'][1][0]=native(['tampered'])[0]
            return {'sheets':[{'properties':s['properties'],'data':[{'rowData':[{'values':r} for r in s['rows']]}]}]}
        for request in kwargs['json']['requests']:
            if 'addSheet' in request:
                p=copy.deepcopy(request['addSheet']['properties']);p['sheetId']=2;self.sheets[p['title']]={'properties':p,'rows':[]};continue
            if 'copyPaste' in request:
                q=request['copyPaste'];src=self.by_id(q['source']['sheetId']);dst=self.by_id(q['destination']['sheetId']);at=q['destination']['startRowIndex']
                while len(dst['rows'])<=at:dst['rows'].append([])
                dst['rows'][at]=copy.deepcopy(src['rows'][q['source']['startRowIndex']]);continue
            q=request['updateCells'];loc=q.get('start') or q['range'];s=self.by_id(loc['sheetId']);at=loc.get('rowIndex',loc.get('startRowIndex'));col=loc.get('columnIndex',loc.get('startColumnIndex',0))
            while len(s['rows'])<=at:s['rows'].append([])
            if not q['rows']:
                self.clears+=1;s['rows'][at]=[];continue
            while len(s['rows'][at])<col:s['rows'][at].append({})
            s['rows'][at][col:col+len(q['rows'][0]['values'])]=copy.deepcopy(q['rows'][0]['values'])
        return {}
    def by_id(self,i):return next(s for s in self.sheets.values() if s['properties']['sheetId']==i)

class MigrationTests(unittest.TestCase):
    def test_archive_keeps_manual_comment_and_useful_row_in_original_position(self):
        client=NativeClient();offer=copy.deepcopy(client.sheets[SOURCE]['rows'][2]);bulk=copy.deepcopy(client.sheets[SOURCE]['rows'][1])
        result=archive_existing(client)
        self.assertEqual(result['archived'],1)
        self.assertEqual(client.sheets[ARCHIVE]['rows'][1][:26],bulk)
        self.assertEqual(client.sheets[SOURCE]['rows'][2],offer)
        self.assertEqual(client.sheets[SOURCE]['rows'][1],[])
        self.assertTrue(client.sheets[ARCHIVE]['properties']['hidden'])
        self.assertEqual(archive_existing(client)['archived'],0)
        self.assertEqual(client.clears,1)
    def test_bad_archive_readback_never_clears_source(self):
        client=NativeClient(tamper=True)
        with self.assertRaisesRegex(ValueError,'Archive copy not verified'):archive_existing(client)
        self.assertEqual(client.clears,0)
        self.assertEqual(client.sheets[SOURCE]['rows'][1][0]['userEnteredValue']['stringValue'],'bulk')
    def test_resume_reuses_verified_archive_without_duplicate(self):
        client=NativeClient(tamper=True)
        with self.assertRaises(ValueError):archive_existing(client)
        client.tamper=False
        self.assertEqual(archive_existing(client)['archived'],1)
        self.assertEqual(len(client.sheets[ARCHIVE]['rows']),2)
