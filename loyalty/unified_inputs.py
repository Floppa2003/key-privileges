"""Five explicitly supported source sheets. Native CellData, not guessed schemas."""
from __future__ import annotations
import copy
import re
from decimal import Decimal
from unified_normalization import INPUT_TABS, make_input, digest

HEADERS = {
 'parser_offers':['ID','Программа','Партнёр','Заголовок','Категория','Тип записи','Типы выгод','Выгода','Условия','Как получить','Промокоды JSON','Ставки JSON','Начало','Окончание','Статус сроков','Статус источника','Ссылка на бенефит','Источник','Тип ссылки','Локатор','Детали JSON','Ограничения JSON','Получено UTC','SHA256','Запуск','Ручной комментарий'],
 'parser_inbox':['ID','Источник','Заголовок страницы','Ссылка на карточку','Текст страницы — требует разбора','Статус','Получено UTC','SHA256 текста','Запуск','Ручной комментарий'],
 'loyalty_partner_benefits':['Программа','Организатор','Доступ / стоимость','Партнёр / сервис','Категория','Тип выгоды','Выгода','Требуемый уровень / условия','Как получить','Статус','Ссылка на бенефит','Проверено','Комментарий'],
 'yandex_discounts_complete_all':['Service Name','Category','Link','Discount','Promo Code','Validity','Notes'],
 'VG_community_offers':['City','Service Name','Category','Link','Discount','Promo Code','Validity','Notes'],
}


def _number_format_sections(pattern):
    """Keep operators and metadata; quoted, escaped and spacing tokens are literal."""
    if not isinstance(pattern,str):return None
    sections=[];tokens=[];meta=[];i=0
    while i<len(pattern):
        char=pattern[i]
        if char=='"':
            end=pattern.find('"',i+1)
            if end<0:return None
            i=end+1;continue
        if char in ('\\','_','*'):
            if i+1==len(pattern):return None
            i+=2;continue
        if char=='[':
            end=pattern.find(']',i+1)
            if end<0:return None
            meta.append(pattern[i+1:end]);i=end+1;continue
        if char==';':
            sections.append((''.join(tokens),meta));tokens=[];meta=[]
        else:tokens.append(char)
        i+=1
    sections.append((''.join(tokens),meta))
    return sections if len(sections)<=4 else None


def _percent_format(pattern,value):
    """Recognize percent units, without rendering or rounding the native number."""
    sections=_number_format_sections(pattern)
    if not sections:return False
    if len(sections)==4 or (len(sections)>1 and '@' in sections[-1][0]):
        sections=sections[:-1]
    conditions=[]
    for _,meta in sections:
        condition=None
        for item in meta:
            match=re.fullmatch(r'(<=|>=|<>|=|<|>)([+-]?(?:\d+(?:\.\d*)?|\.\d+))',item)
            if match:
                if condition is not None:return False
                condition=(match[1],Decimal(match[2]))
            elif not (re.fullmatch(r'(?:Black|Blue|Cyan|Green|Magenta|Red|White|Yellow|Color\d+)',item,re.I)
                      or item.startswith('$')):
                return False
        conditions.append(condition)
    percent=lambda section:'%' in section[0] and '@' not in section[0]
    if any(conditions):
        if len(conditions)>2 and conditions[2] is not None:return False
        number=Decimal(str(value))
        for section,condition in zip(sections[:2],conditions[:2]):
            if condition is None:
                # Mixed conditional/default selection is not guessed. Uniform
                # numeric sections still declare the same percent units.
                return all(percent(s) for s in sections)
            operator,threshold=condition
            matches={'<':number<threshold,'<=':number<=threshold,
                     '>':number>threshold,'>=':number>=threshold,
                     '=':number==threshold,'<>':number!=threshold}
            if matches[operator]:return percent(section)
        return len(sections)==3 and percent(sections[2])
    if len(sections)<=2:index=1 if len(sections)==2 and value<0 else 0
    else:index=0 if value>0 else (1 if value<0 else 2)
    return percent(sections[index])


def clean_atom(c):
    # Ignore display-only metadata in deterministic hashes: a UI's locale-specific
    # rendering is not a change to a stored amount, formula, or original text.
    result = {k:c[k] for k in ('value','formula','error') if k in c and c[k] is not None}
    value=c.get('value')
    if isinstance(value,(int,float)) and not isinstance(value,bool) and _percent_format(c.get('format',''),value):
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
    fmt=(cell.get('effectiveFormat',{}).get('numberFormat')
         or cell.get('userEnteredFormat',{}).get('numberFormat',{}))
    pattern=fmt.get('pattern')
    # Date/time formats have their own tokens; an unquoted '%' is literal there.
    if fmt.get('type') not in ('DATE','TIME','DATE_TIME'):
        if pattern:result['format']=pattern
        elif fmt.get('type')=='PERCENT':result['format']='%'
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
            'fields':'sheets(properties(title),data(startRow,startColumn,rowData.values(userEnteredValue,effectiveValue,userEnteredFormat.numberFormat,effectiveFormat.numberFormat)))'})
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
