"""Reversible same-workbook migration, with no source data in public logs.

Archive identified bulk rows natively before clearing their old values. Keep
stable source-row addresses, all offer data, and the original manual comments.
"""
from __future__ import annotations
import json,os
from datetime import datetime,timezone
from practical_scope import row_exclusion
from sheets_normalized import SCHEMAS
from unified_publish import UnifiedSheets,publish_all
from model import cell

SOURCE='parser_offers'
ARCHIVE='parser_documents_archive'
WIDTH=26


def read_native(client,title):
    props=client.metadata().get(title)
    if not props:raise ValueError('Missing migration sheet')
    grid=props['gridProperties'];n=grid['rowCount'];width=grid['columnCount']
    if not 1<=n<=5000 or width not in (26,28):raise ValueError('Migration dimensions changed')
    col='Z' if width==26 else 'AB'
    data=client.request('GET',params={'ranges':"'"+title+"'!A1:"+col+str(n),'includeGridData':'true',
        'fields':'sheets(properties(sheetId,title,hidden,gridProperties),data(startRow,startColumn,rowData.values(userEnteredValue,note,dataValidation,chipRuns,userEnteredFormat)))'})
    sheets=data.get('sheets',[])
    if len(sheets)!=1 or sheets[0]['properties']['title']!=title:raise ValueError('Wrong migration sheet')
    rows=[]
    for block in sheets[0].get('data',[]):
        if block.get('startColumn',0)!=0:raise ValueError('Migration grid offset')
        start=block.get('startRow',0)
        while len(rows)<start:rows.append([])
        for row in block.get('rowData',[]):rows.append(row.get('values',[]))
    while rows and not any(c.get('userEnteredValue') for c in rows[-1]):rows.pop()
    return sheets[0]['properties'],rows


def values(row,width=WIDTH):
    result=[]
    for c in (row+[{}]*width)[:width]:
        u=c.get('userEnteredValue',{})
        if u and set(u)!={'stringValue'}:raise ValueError('Migration requires literal source cells')
        result.append(u.get('stringValue',''))
    return result


def archive_existing(client):
    source,original=read_native(client,SOURCE)
    expected=SCHEMAS[SOURCE]+['Ручной комментарий']
    if not original or values(original[0])!=expected:raise ValueError('Source schema changed')
    selected=[(i,row) for i,row in enumerate(original[1:],1) if row_exclusion(values(row))]
    if not selected:return {'archived':0,'source_rows_unchanged':len(original)-1}
    ids=[values(r)[0] for _,r in selected]
    if len(set(ids))!=len(ids):raise ValueError('Duplicate migration source IDs')
    meta=client.metadata()
    if ARCHIVE not in meta:
        client.request('POST',':batchUpdate',json={'requests':[{'addSheet':{'properties':{
            'title':ARCHIVE,'hidden':True,'gridProperties':{'rowCount':5000,'columnCount':28,'frozenRowCount':1}}}}]})
        target=client.metadata()[ARCHIVE]
        client.request('POST',':batchUpdate',json={'requests':[
            {'copyPaste':{'source':{'sheetId':source['sheetId'],'startRowIndex':0,'endRowIndex':1,'startColumnIndex':0,'endColumnIndex':WIDTH},
                'destination':{'sheetId':target['sheetId'],'startRowIndex':0,'endRowIndex':1,'startColumnIndex':0,'endColumnIndex':WIDTH},'pasteType':'PASTE_NORMAL'}},
            {'updateCells':{'start':{'sheetId':target['sheetId'],'rowIndex':0,'columnIndex':WIDTH},
                'rows':[{'values':[cell('Исходная строка parser_offers'),cell('Архивировано UTC')]}],'fields':'userEnteredValue'}}]})
    target,archived=read_native(client,ARCHIVE)
    if not archived or values(archived[0])!=expected or not target.get('hidden'):raise ValueError('Archive identity changed')
    existing={values(r)[0]:(i,r) for i,r in enumerate(archived[1:],1) if values(r)[0]}
    if len(existing)!=sum(bool(values(r)[0]) for r in archived[1:]):raise ValueError('Duplicate archive IDs')
    requests=[];checks={};nextrow=len(archived);stamp=datetime.now(timezone.utc).isoformat()
    for i,row in selected:
        ident=values(row)[0]
        if ident in existing:
            at,prior=existing[ident]
            if values(prior)!=values(row):raise ValueError('Archive/source conflict; refusing clear')
        else:
            at=nextrow;nextrow+=1
            requests.append({'copyPaste':{'source':{'sheetId':source['sheetId'],'startRowIndex':i,'endRowIndex':i+1,'startColumnIndex':0,'endColumnIndex':WIDTH},
                'destination':{'sheetId':target['sheetId'],'startRowIndex':at,'endRowIndex':at+1,'startColumnIndex':0,'endColumnIndex':WIDTH},'pasteType':'PASTE_NORMAL'}})
            requests.append({'updateCells':{'start':{'sheetId':target['sheetId'],'rowIndex':at,'columnIndex':WIDTH},
                'rows':[{'values':[cell(str(i+1)),cell(stamp)]}],'fields':'userEnteredValue'}})
        checks[at]=values(row)
    if nextrow>5000:raise ValueError('Archive capacity exceeded')
    if requests:client.request('POST',':batchUpdate',json={'requests':requests})
    _,actual=read_native(client,ARCHIVE)
    if any(at>=len(actual) or values(actual[at])!=row for at,row in checks.items()):raise ValueError('Archive copy not verified; no source clear')
    _,current=read_native(client,SOURCE)
    if [[c.get('userEnteredValue',{}) for c in r] for r in current]!=[[c.get('userEnteredValue',{}) for c in r] for r in original]:
        raise ValueError('Source changed during archive; no source clear')
    client.request('POST',':batchUpdate',json={'requests':[{'updateCells':{'range':{
        'sheetId':source['sheetId'],'startRowIndex':i,'endRowIndex':i+1,'startColumnIndex':0,'endColumnIndex':WIDTH},
        'rows':[],'fields':'userEnteredValue'}} for i,_ in selected]})
    _,after=read_native(client,SOURCE);_,final_archive=read_native(client,ARCHIVE)
    selected_positions={i for i,_ in selected}
    for i,row in enumerate(original):
        got=after[i] if i<len(after) else []
        if values(got)!=(['']*WIDTH if i in selected_positions else values(row)):
            raise ValueError('Final source preservation check failed')
    if any(values(final_archive[at])!=row for at,row in checks.items()):raise ValueError('Final archive check failed')
    return {'archived':len(selected),'source_rows_unchanged':len(original)-1-len(selected),'archive_hidden':True}


def main():
    client=UnifiedSheets(os.environ.get('DISCOUNTS_SPREADSHEET_ID',''),os.environ.get('GOOGLE_ACCESS_TOKEN',''))
    result=archive_existing(client)
    publish_all(client=client)
    print(json.dumps({'mode':'practical_scope_migration_verified',**result}))

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('Practical migration stopped ('+type(exc).__name__+'); inspect current state before retrying.')
        raise SystemExit(1)
