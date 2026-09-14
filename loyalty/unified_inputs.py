"""Five explicitly supported source sheets. Native CellData, not guessed schemas."""
from __future__ import annotations
import copy
from unified_normalization import INPUT_TABS, make_input, digest

HEADERS = {
 'parser_offers':['ID','Программа','Партнёр','Заголовок','Категория','Тип записи','Типы выгод','Выгода','Условия','Как получить','Промокоды JSON','Ставки JSON','Начало','Окончание','Статус сроков','Статус источника','Ссылка на бенефит','Источник','Тип ссылки','Локатор','Детали JSON','Ограничения JSON','Получено UTC','SHA256','Запуск','Ручной комментарий'],
 'parser_inbox':['ID','Источник','Заголовок страницы','Ссылка на карточку','Текст страницы — требует разбора','Статус','Получено UTC','SHA256 текста','Запуск','Ручной комментарий'],
 'loyalty_partner_benefits':['Программа','Организатор','Доступ / стоимость','Партнёр / сервис','Категория','Тип выгоды','Выгода','Требуемый уровень / условия','Как получить','Статус','Ссылка на бенефит','Проверено','Комментарий'],
 'yandex_discounts_complete_all':['Service Name','Category','Link','Discount','Promo Code','Validity','Notes'],
 'VG_community_offers':['City','Service Name','Category','Link','Discount','Promo Code','Validity','Notes'],
}


def clean_atom(c):
    # Ignore display-only metadata in deterministic hashes: a UI's locale-specific
    # rendering is not a change to a stored amount, formula, or original text.
    result = {k:c[k] for k in ('value','formula','error') if k in c and c[k] is not None}
    if isinstance(c.get('value'), (int,float)) and '%' in c.get('format',''):
        result['format']='%'
    return result


def inputs_from_tables(tables, public_records=None):
    result=[];index={r['id']:r for r in public_records or []};stats={}
    for name,(header,width) in INPUT_TABS.items():
        if name not in tables:raise ValueError('Required source sheet missing: '+name)
        rows=list(tables[name])
        while len(rows)>header and not any(c.get('value') not in (None,'') or c.get('formula') for c in rows[-1]):rows.pop()
        if len(rows)>5000:raise ValueError('Source row bound exceeded')
        if any(c.get('value') not in (None,'') or c.get('formula') for row in rows for c in row[width:]):
            raise ValueError('Unmapped populated source column')
        actual=[c.get('value','') for c in rows[header-1][:width]]
        expected=HEADERS[name]
        if actual!=expected:raise ValueError('Unexpected input header: '+name)
        accepted=0;blank=0
        for i,cells in enumerate(rows[header:],header+1):
            cells=[clean_atom(c) for c in cells[:width]]
            if not any(c.get('value') not in (None,'') or c.get('formula') for c in cells):blank+=1;continue
            if any(c.get('error') for c in cells):raise ValueError('Source error cell requires review')
            fields={h:(cells[j] if j<len(cells) else {}) for j,h in enumerate(expected)}
            key=fields.get('ID',{}).get('value')
            # Private legacy rows have no vendor ID; namespace+row is declared,
            # not passed off as an offer ID or used for semantic deduplication.
            ident=str(key) if key else digest([name,'row',i])
            raw={'id':ident,'origin':name,'row':i,'fields':fields}
            r=make_input(raw)
            current=index.get(ident)
            if current and name=='parser_offers' and fields.get('SHA256',{}).get('value')==current['content_sha256']:
                r['source_id']=current['source_id']
            result.append(r);accepted+=1
        stats[name]={'rows':accepted,'blank_rows_ignored':blank,'header_row':header}
    return result,stats


def atom_from_cell(cell):
    u=cell.get('userEnteredValue',{});e=cell.get('effectiveValue',{})
    result={}
    if 'formulaValue' in u:result['formula']=u['formulaValue']
    value=next((u[k] for k in ('stringValue','numberValue','boolValue') if k in u),None)
    if value is None:value=next((e[k] for k in ('stringValue','numberValue','boolValue') if k in e),None)
    if value is not None:result['value']=value
    if 'errorValue' in e:result['error']=True
    fmt=cell.get('userEnteredFormat',{}).get('numberFormat',{}).get('pattern')
    if fmt:result['format']=fmt
    return result


def read_tables(client):
    meta=client.metadata();tables={}
    for name,(header,width) in INPUT_TABS.items():
        if name not in meta:raise ValueError('Missing input tab')
        grid=meta[name]['gridProperties'];n=grid['rowCount']
        if not header<=n<=5000 or not width<=grid['columnCount']<=128:raise ValueError('Input dimensions changed')
        col='';x=grid['columnCount']
        while x:x,r=divmod(x-1,26);col=chr(65+r)+col
        data=client.request('GET',params={'ranges':f"'{name}'!A1:{col}{n}",'includeGridData':'true',
            'fields':'sheets(properties(title),data(startRow,startColumn,rowData.values(userEnteredValue,effectiveValue,userEnteredFormat.numberFormat)))'})
        sheet=data.get('sheets',[])
        if len(sheet)!=1 or sheet[0]['properties']['title']!=name:raise ValueError('Wrong source sheet response')
        rows=[]
        for block in sheet[0].get('data',[]):
            start=block.get('startRow',0)
            if block.get('startColumn',0)!=0:raise ValueError('Unexpected source column offset')
            while len(rows)<start:rows.append([])
            for j,row in enumerate(block.get('rowData',[]),start):
                while len(rows)<=j:rows.append([])
                rows[j]=[atom_from_cell(c) for c in row.get('values',[])]
        tables[name]=rows
    return tables
