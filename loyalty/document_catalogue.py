"""The Sheet is the document catalogue; original PDFs remain immutable files.

This projection only joins document identity and discovery metadata. It does
not normalize PDF text, manufacture benefits, or establish current eligibility.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import re
from urllib.parse import urlsplit

from catalogue_clauses import TECHNICAL, compact, key
from pdf_archive import archive_url

TAB = 'Документы'
TAB_ID = 2026111501
ARCHIVE_TAB = 'parser_documents_archive'
VERSION = 'source-documents-v1'
HEADERS = ['Партнёр', 'Программа', 'Документ', 'Статус документа', 'Источник',
           'Копия документа', 'Получено UTC', 'Сведения из карточки',
           'SHA256 документа', 'Набор', 'ID записей', 'ID документа']
STATE_RANGE = "'Документы'!N1:O8"
MAX_ROWS = 20000


def document_digest(raw):
    details = raw.get('details') or {}
    value = details.get('document_sha256')
    if isinstance(value, str) and re.fullmatch('[a-f0-9]{64}', value):
        return value
    # Older Цветной brand records called the PDF digest page_sha256. Tier
    # records use the same name for HTML, so only the exact PDF binding counts.
    evidence = details.get('public_reward_evidence') or {}
    document = evidence.get('document') or {}
    filename = document.get('key')
    if (isinstance(filename, str) and re.fullmatch('[A-Za-z0-9_-]+[.]pdf', filename)
            and evidence.get('url') == 'https://tsvetnoy.com/pdf/' + filename
            and raw.get('source_url') == evidence['url']):
        value = evidence.get('page_sha256')
        if isinstance(value, str) and re.fullmatch('[a-f0-9]{64}', value):
            return value
    return ''


def _pdf_url(value):
    return isinstance(value, str) and urlsplit(value).path.lower().endswith('.pdf')


def document_sources(inputs):
    """Metadata only; do not retain extracted text, codes or user comments."""
    result = []
    for raw in inputs:
        digest = document_digest(raw)
        details = raw.get('details') or {}
        urls = {value for value in (raw.get('source_url'), raw.get('benefit_url'))
                if isinstance(value, str) and value}
        if not digest and not any(_pdf_url(value) for value in urls):
            continue
        aliases = details.get('public_aliases') or []
        urls.update(value for value in aliases if isinstance(value, str) and value)
        labels = [details.get('discovery_label')] + (details.get('discovery_labels') or [])
        result.append({
            'id':str(raw['id']), 'origin':str(raw.get('origin') or 'parser_offers'),
            'source_row':str(raw.get('source_row') or ''),
            'program':compact(raw.get('program')), 'partner':compact(raw.get('partner')),
            'title':compact(raw.get('title')), 'sha256':digest, 'urls':sorted(urls),
            'observed_at':str(raw.get('observed_at') or ''),
            'method':str(details.get('extraction_method') or ''),
            'source_status':str(raw.get('source_status') or ''),
            'ocr':bool(details.get('ocr_pages')),
            'incomplete':bool(details.get('document_errors') or details.get('document_text_incomplete')
                or any(page.get('method')=='missing_text' for page in details.get('pages',[]))),
            'labels':sorted({compact(value) for value in labels if isinstance(value,str) and compact(value)})})
    return result


def _time(value):
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Document observation lacks timezone')
    return parsed.astimezone(timezone.utc)


def build_documents(sources):
    groups = defaultdict(list)
    for item in sources:
        identity = item['sha256'] or '\n'.join(item['urls'])
        if not item['program'] or not identity:
            raise ValueError('Incomplete document identity')
        groups[item['program'], identity].append(item)
    rows = []
    for (program, identity), items in groups.items():
        digest = items[0]['sha256']
        names = sorted({i['partner'] for i in items if i['partner'] and not TECHNICAL.fullmatch(i['partner'])}, key=key)
        titles = sorted({i['title'] for i in items if i['title'] and not TECHNICAL.fullmatch(i['title'])}, key=key)
        labels = sorted({label for i in items for label in i['labels']})
        copied = archive_url(digest)
        latest = max(_time(i['observed_at']) for i in items)
        current = [i for i in items if _time(i['observed_at']) == latest]
        if any(i['method']=='source_pdf_original_only' for i in current):
            status = 'Требует просмотра PDF — текст не извлечён'
        elif any(i.get('incomplete') for i in current):
            status = 'Требует просмотра PDF — текст извлечён не полностью'
        elif any(i['ocr'] or i['source_status']=='public_rules_ocr_unverified' for i in current):
            status = 'Требует просмотра PDF — OCR не проверен'
        else:
            status = 'Условия уточняются по PDF'
        if not copied:
            status += '; Копия не сохранена'
        # Explicitly preserve every observed name when one shared document covers
        # multiple merchants. Identity never crosses programme or byte digest.
        rows.append([
            '\n'.join(names) or 'Партнёр не указан', program,
            '\n'.join(titles) or '\n'.join(labels) or 'Документ источника', status,
            '\n'.join(sorted({url for i in items for url in i['urls']})), copied,
            max((i['observed_at'] for i in items),key=_time), '\n'.join(labels), digest,
            '\n'.join(sorted({i['origin'] for i in items})),
            '\n'.join(sorted({i['id'] for i in items})),
            hashlib.sha256(json.dumps([program,identity],ensure_ascii=False).encode()).hexdigest()])
    rows.sort(key=lambda row:(key(row[0]),key(row[1]),row[-1]))
    if any(len(value)>45000 for row in rows for value in row):
        raise ValueError('Document catalogue cell exceeds safe size')
    return rows


def read_archived_documents(client, meta=None):
    """Read only the existing archive's owned metadata, in bounded ranges."""
    from catalogue_publish import read_values
    from unified_inputs import HEADERS as INPUT_HEADERS
    meta = client.metadata() if meta is None else meta
    if ARCHIVE_TAB not in meta:
        return []
    grid = meta[ARCHIVE_TAB]['gridProperties']
    if not 1 <= grid['rowCount'] <= 5000 or grid['columnCount'] != 28:
        raise ValueError('Document source archive dimensions changed')
    expected = INPUT_HEADERS['parser_offers'] + ['Исходная строка parser_offers','Архивировано UTC']
    if read_values(client, "'parser_documents_archive'!A1:AB1") != [expected]:
        raise ValueError('Document source archive header changed')
    end=grid['rowCount']
    if end==1:return []
    blocks=[read_values(client,f"'{ARCHIVE_TAB}'!{start}2:{finish}{end}")
            for start,finish in (('A','F'),('Q','U'),('W','W'))]
    result=[]
    for offset in range(max(map(len,blocks),default=0)):
        def block(which,width):
            values=blocks[which][offset] if offset<len(blocks[which]) else []
            return values+['']*(width-len(values))
        base=block(0,6);links=block(1,5);observed=block(2,1)
        if not any(base+links+observed):continue
        if not isinstance(base[0],str) or not base[0]:
            raise ValueError('Document archive row lacks ID')
        details=json.loads(links[4] or '{}')
        if not isinstance(details,dict):raise ValueError('Document archive details changed')
        raw={'id':base[0],'origin':ARCHIVE_TAB,'source_row':offset+2,
             'program':base[1],'partner':base[2],'title':base[3],'kind':base[5],
             'benefit_url':links[0],'source_url':links[1],'details':details,
             'observed_at':observed[0],'source_status':'archived'}
        result.extend(document_sources([raw]))
    return result


def prepare_documents(client, sources, *, generation, as_of, meta=None):
    from catalogue_publish import read_values, digest
    meta=client.metadata() if meta is None else meta
    # Restrict creation to the known owner-created catalogue workbook.
    if '_ui_catalog' not in meta:return None
    rows=[HEADERS]+build_documents(sources)
    props=meta.get(TAB)
    if len(rows)==1 and props is None:return None
    if len(rows)==1 or len(rows)>MAX_ROWS:
        raise ValueError('Refusing empty or oversized document catalogue')
    if props:
        grid=props['gridProperties']
        if (props['sheetId']!=TAB_ID or grid['columnCount']!=15
                or not 9<=grid['rowCount']<=MAX_ROWS):
            raise ValueError('Document catalogue ownership changed')
        if read_values(client,"'Документы'!A1:L1")!=[HEADERS]:
            raise ValueError('Document catalogue header changed')
    elif any(p['sheetId']==TAB_ID for p in meta.values()):
        raise ValueError('Document catalogue sheet ID occupied')
    desired=max(1000,len(rows)+50) if props is None else max(props['gridProperties']['rowCount'],len(rows))
    state=[['Каталог',VERSION],['Статус','verified'],['Дата пересчёта',as_of],
           ['Документов',str(len(rows)-1)],['Поколение',generation],['SHA256',digest(rows)],
           ['Исходный снимок',digest(sources)],['Сроки и доступ','Уточняются по документу и текущему источнику']]
    return {'properties':props,'rows':rows,'row_count':desired,'state':state}


def verify_documents(client, plan):
    if plan is None:return
    from catalogue_publish import read_values, padded
    meta=client.metadata()
    props=meta.get(TAB,{})
    if (props.get('sheetId')!=TAB_ID or props.get('hidden')
            or props.get('gridProperties',{}).get('columnCount')!=15
            or props.get('gridProperties',{}).get('rowCount')!=plan['row_count']):
        raise ValueError('Document catalogue properties readback mismatch')
    if padded(read_values(client,f"'Документы'!A1:L{plan['row_count']}"),len(HEADERS))!=plan['rows']:
        raise ValueError('Document catalogue full readback mismatch')
    if read_values(client,STATE_RANGE)!=plan['state']:
        raise ValueError('Document catalogue state readback mismatch')
    if read_values(client,f"'Документы'!M1:M{plan['row_count']}"):
        raise ValueError('Unexpected document catalogue helper')


def publish_documents(client, plan):
    if plan is None:return
    from catalogue_publish import literal
    requests=[]
    if plan['properties'] is None:
        requests.append({'addSheet':{'properties':{'sheetId':TAB_ID,'title':TAB,'index':1,
            'gridProperties':{'rowCount':plan['row_count'],'columnCount':15,'frozenRowCount':1,
                              'frozenColumnCount':2,'hideGridlines':True}}}})
    else:
        requests.append({'updateSheetProperties':{'properties':{'sheetId':TAB_ID,'hidden':False,
            'gridProperties':{'rowCount':plan['row_count']}},'fields':'hidden,gridProperties.rowCount'}})
    publishing=[list(row) for row in plan['state']];publishing[1][1]='publishing'
    def state_request(state):
        return {'updateCells':{'start':{'sheetId':TAB_ID,'rowIndex':0,'columnIndex':13},
                'rows':[{'values':[literal(v) for v in row]} for row in state],
                'fields':'userEnteredValue'}}
    requests.extend([
        {'updateCells':{'range':{'sheetId':TAB_ID,'startRowIndex':0,'endRowIndex':plan['row_count'],
            'startColumnIndex':0,'endColumnIndex':13},'rows':[],'fields':'userEnteredValue'}},
        state_request(publishing)])
    # Header and creation belong to one transaction, so a retry can identify a
    # partially published but owner-created sheet without accepting user data.
    requests.append({'updateCells':{'start':{'sheetId':TAB_ID,'rowIndex':0,'columnIndex':0},
        'rows':[{'values':[literal(v) for v in HEADERS]}],'fields':'userEnteredValue'}})
    client.request('POST',':batchUpdate',json={'requests':requests})
    batch=[];size=0
    for number,row in enumerate(plan['rows'][1:],1):
        operation={'updateCells':{'start':{'sheetId':TAB_ID,'rowIndex':number,'columnIndex':0},
            'rows':[{'values':[literal(v) for v in row]}],'fields':'userEnteredValue'}}
        weight=len(json.dumps(operation,ensure_ascii=False).encode())
        if batch and size+weight>800000:
            client.request('POST',':batchUpdate',json={'requests':batch});batch=[];size=0
        batch.append(operation);size+=weight
    if batch:client.request('POST',':batchUpdate',json={'requests':batch})
    full={'sheetId':TAB_ID,'startRowIndex':0,'endRowIndex':plan['row_count'],'startColumnIndex':0,'endColumnIndex':12}
    requests=[
        {'repeatCell':{'range':full,'cell':{'userEnteredFormat':{'verticalAlignment':'TOP','wrapStrategy':'WRAP',
            'textFormat':{'fontFamily':'Arial','fontSize':10}}},'fields':'userEnteredFormat'}},
        {'repeatCell':{'range':{**full,'endRowIndex':1},'cell':{'userEnteredFormat':{
            'backgroundColor':{'red':0.12,'green':0.19,'blue':0.29},
            'textFormat':{'bold':True,'foregroundColor':{'red':1,'green':1,'blue':1},'fontFamily':'Arial','fontSize':10}}},
            'fields':'userEnteredFormat.backgroundColor,userEnteredFormat.textFormat'}},
        {'setBasicFilter':{'filter':{'range':{**full,'endRowIndex':len(plan['rows'])}}}},
        {'updateDimensionProperties':{'range':{'sheetId':TAB_ID,'dimension':'COLUMNS','startIndex':8,'endIndex':15},
            'properties':{'hiddenByUser':True},'fields':'hiddenByUser'}},
        {'updateCells':{'start':{'sheetId':TAB_ID,'rowIndex':0,'columnIndex':6},'rows':[{'values':[{'note':
            'Дата наблюдения исходного документа, а не срок действия предложения. Копия не подтверждает актуальность или право участия.'}]}],'fields':'note'}},
        state_request(plan['state'])]
    for start,end,width in ((0,2,230),(2,3,300),(3,4,270),(4,6,320),(6,7,205),(7,8,360)):
        requests.append({'updateDimensionProperties':{'range':{'sheetId':TAB_ID,'dimension':'COLUMNS',
            'startIndex':start,'endIndex':end},'properties':{'pixelSize':width},'fields':'pixelSize'}})
    client.request('POST',':batchUpdate',json={'requests':requests})
    verify_documents(client,plan)
