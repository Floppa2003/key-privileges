import re
import sys
import unittest
from pathlib import Path
from urllib.parse import unquote
sys.path.insert(0,str(Path(__file__).parents[1]))
from catalogue_publish import prepare_catalogue,publish_catalogue,verify_catalogue,HEADERS
from test_catalogue_view import record,NOW

class MemorySheets:
    def __init__(self):
        self.cells={(0,i):v for i,v in enumerate(HEADERS)}
        self.cells[(15,0)]='obsolete tail'
        self.cells[(1,19)]='old raw helper'
        self.source={'original':'DO NOT TOUCH'}
        self.requests=[]
    def metadata(self):
        return {'_ui_catalog':{'sheetId':23,'gridProperties':{'rowCount':30,'columnCount':26}},
                'parser_offers':{'sheetId':91,'gridProperties':{'rowCount':20,'columnCount':26}}}
    def request(self,method,suffix='',**kw):
        self.requests.append((method,suffix))
        if method=='GET':
            a1=unquote(suffix.split('/values/')[1]);bounds=a1.split('!')[1]
            a,b=bounds.split(':')
            def loc(v):
                m=re.fullmatch(r'([A-Z]+)(\d+)',v);col=0
                for ch in m[1]:col=col*26+ord(ch)-64
                return int(m[2])-1,col-1
            r,c=loc(a);end,col=loc(b);assert end<30 and col<26
            rows=[]
            for i in range(r,end+1):
                row=[self.cells.get((i,j),'') for j in range(c,col+1)]
                while row and row[-1]=='':row.pop()
                rows.append(row)
            while rows and not rows[-1]:rows.pop()
            return {'values':rows}
        for operation in kw['json']['requests']:
            u=operation['updateCells'];assert u['fields']=='userEnteredValue'
            origin=u.get('start',u.get('range'));assert origin['sheetId']==23
            if 'range' in u:
                assert not u['rows'];self.cells.clear()
            else:
                r=origin['rowIndex'];c=origin['columnIndex']
                for i,row in enumerate(u['rows'],r):
                    for j,cell in enumerate(row['values'],c):
                        self.cells[i,j]=cell['userEnteredValue']['stringValue']
        return {}

class PublisherTests(unittest.TestCase):
    def plan(self,client):
        return prepare_catalogue(client,[record()],as_of=NOW,source_fingerprint='source',generation='gen')
    def test_full_replace_readback_removes_old_helpers_only(self):
        client=MemorySheets();plan=self.plan(client)
        publish_catalogue(client,plan);verify_catalogue(client,plan)
        self.assertEqual(client.source,{'original':'DO NOT TOUCH'})
        self.assertNotIn('obsolete tail',client.cells.values())
        self.assertNotIn('old raw helper',client.cells.values())
        self.assertEqual(client.cells[1,25],'verified')
        self.assertEqual(client.cells[4,25],'gen')
    def test_final_readback_detects_tampering(self):
        client=MemorySheets();plan=self.plan(client);publish_catalogue(client,plan)
        client.cells[1,2]='wrong value'
        with self.assertRaises(ValueError):verify_catalogue(client,plan)
    def test_wrong_header_fails_before_write(self):
        client=MemorySheets();client.cells[0,0]='user owned'
        with self.assertRaises(ValueError):self.plan(client)
        self.assertTrue(all(m=='GET' for m,_ in client.requests))
    def test_no_ui_no_creation(self):
        client=MemorySheets();client.metadata=lambda:{}
        self.assertIsNone(self.plan(client));self.assertEqual(client.requests,[])
    def test_empty_projection_fails(self):
        client=MemorySheets()
        with self.assertRaises(ValueError):
            prepare_catalogue(client,[record(kind='announcement')],as_of=NOW,source_fingerprint='s',generation='g')
        self.assertTrue(all(m=='GET' for m,_ in client.requests))
    def test_failed_write_does_not_return_success(self):
        client=MemorySheets();plan=self.plan(client);request=client.request
        def fail(method,*a,**kw):
            if method=='POST':raise RuntimeError('network failure')
            return request(method,*a,**kw)
        client.request=fail
        with self.assertRaises(RuntimeError):publish_catalogue(client,plan)
    def test_state_generation_tampering_fails(self):
        client=MemorySheets();plan=self.plan(client);publish_catalogue(client,plan)
        client.cells[4,25]='old generation'
        with self.assertRaises(ValueError):verify_catalogue(client,plan)
if __name__=='__main__':unittest.main()
