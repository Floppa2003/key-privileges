"""Small, guarded upgrade of the owner-created native search formula.

TODAY() keeps stale observations out even if the entire CI run cannot publish.
No source data, styles, search inputs or unrelated programme filters are changed.
"""
from source_lifecycle import FRESHNESS_DAYS
UI_TAB = 'Скидки'
UI_ID = 2026092001
FORMULA_RANGE = "'Скидки'!A10"
NOTE_RANGE = "'Скидки'!C6"
OLD_HEADER_RANGE = "'Скидки'!A9:N9"
HEADER_RANGE = "'Скидки'!A9:O9"
OLD_HEADERS = ['Партнёр / предложение','Программа','Конкретная выгода','Промокод / получение кода',
               'Как получить','Условия и ограничения','Срок из источника','Категория',
               'Дата источника / получения, UTC','Ссылка на источник','Комментарии',
               'Что за запись','Статус срока','ID — служебное']
HEADERS = OLD_HEADERS[:10]+['Копия документа']+OLD_HEADERS[10:]
LEGACY_PROGRAMMES = ('Backit — денежный кешбэк', 'Club Avolta', 'Мантера Моменты')
from expansion_common import PROGRAMS as EXPANSION_PROGRAMMES
PROGRAMMES = LEGACY_PROGRAMMES + tuple(EXPANSION_PROGRAMMES.values())
NOTE = ('Только конкретные предложения. Реклама и отключённые карточки исключены. '
        'Для Backit, Club Avolta, Мантеры, X5, Магнита, «Города», «Цветного» и FlyStation нужны наблюдения не старше 7 дней; '
        'это предел свежести проверки, а не срок самой акции. '
        'Исходные PDF и документы без разобранных условий — на листе «Документы».')

def upgrade_formula(formula):
    if not isinstance(formula, str) or not formula.startswith('=ARRAYFORMULA('):
        raise ValueError('unexpected_native_search_formula')
    if len(set(FRESHNESS_DAYS.values())) != 1:
        raise ValueError('native_freshness_policy_needs_per_source_upgrade')
    days = next(iter(FRESHNESS_DAYS.values()))
    names = '{'+';'.join('"'+p+'"' for p in PROGRAMMES)+'}'
    observed = 'DATEVALUE(LEFT(INDEX(d;0;9);10))'
    clause = (f'freshRewards;IF((INDEX(d;0;15)="parser_offers")*ISNUMBER(MATCH(INDEX(d;0;2);{names};0));'
              f'IFERROR(({observed}<=TODAY())*({observed}>=TODAY()-{days});0);1);'
              'keep;hits*freshRewards*')
    if 'freshRewards;' in formula:
        if formula.count(clause) == 1:
            return formula
        # Recognize only the two previously deployed exact programme lists.
        prior = (LEGACY_PROGRAMMES, LEGACY_PROGRAMMES + (
            'X5 Клуб — партнёры', 'Магнит Плюс — партнёры', 'Город / Тройка',
            'Цветной — программа лояльности'))
        for programmes in prior:
            legacy_names = '{'+';'.join(chr(34)+p+chr(34) for p in programmes)+'}'
            legacy_clause = clause.replace(names, legacy_names)
            if formula.count(legacy_clause) == 1:
                return formula.replace(legacy_clause, clause)
        raise ValueError('native_freshness_policy_changed')
    if formula.count('keep;hits*') != 1 or not any(r in formula for r in ("'_ui_catalog'!A2:Q","'_ui_catalog'!A2:R")):
        raise ValueError('native_search_layout_changed')
    return formula.replace('keep;hits*', clause)


def upgrade_document_formula(formula):
    old_range="'_ui_catalog'!A2:Q";new_range="'_ui_catalog'!A2:R"
    old_columns='CHOOSECOLS(d;1;2;3;4;5;6;7;8;9;10;11;12;13;14)'
    new_columns='CHOOSECOLS(d;1;2;3;4;5;6;7;8;9;10;18;11;12;13;14)'
    if formula.count(new_range)==1 and formula.count(new_columns)==1 and old_range not in formula and old_columns not in formula:
        return formula
    if formula.count(old_range)!=1 or formula.count(old_columns)!=1 or new_range in formula or new_columns in formula:
        raise ValueError('native_document_projection_changed')
    return formula.replace(old_range,new_range).replace(old_columns,new_columns)

def prepare_ui(client, meta, read_values):
    if UI_TAB not in meta or meta[UI_TAB].get('sheetId') != UI_ID:
        return None
    width=meta[UI_TAB].get('gridProperties',{}).get('columnCount')
    if width not in (14,15):
        raise ValueError('native_search_dimensions_changed')
    header_range=OLD_HEADER_RANGE if width==14 else HEADER_RANGE
    headers=read_values(client,header_range)
    if headers!=[OLD_HEADERS if width==14 else HEADERS]:
        raise ValueError('native_search_headers_changed')
    before = read_values(client, FORMULA_RANGE)
    if len(before) != 1 or len(before[0]) != 1:
        raise ValueError('native_search_formula_missing')
    after = upgrade_document_formula(upgrade_formula(before[0][0]))
    if width==14 and after==before[0][0]:
        raise ValueError('native_document_projection_dimensions_mismatch')
    if width==15 and upgrade_document_formula(before[0][0])!=before[0][0]:
        raise ValueError('native_document_projection_dimensions_mismatch')
    note_before = read_values(client, NOTE_RANGE)
    return {'before': before, 'after': [[after]], 'note_before': note_before,
            'headers_before':headers,'header_range':header_range,'width':width}

def apply_ui(client, plan, read_values):
    if plan is None:
        return
    current=client.metadata().get(UI_TAB,{})
    if (read_values(client, FORMULA_RANGE) != plan['before']
            or read_values(client, NOTE_RANGE) != plan['note_before']
            or read_values(client,plan['header_range'])!=plan['headers_before']
            or current.get('sheetId')!=UI_ID
            or current.get('gridProperties',{}).get('columnCount')!=plan['width']):
        raise ValueError('concurrent_native_ui_edit')
    if plan['width']==15 and plan['after'] == plan['before'] and plan['note_before'] == [[NOTE]]:
        return
    requests=[]
    if plan['width']==14:
        # Insert after the source URL so comment/type/status/ID formatting moves
        # with its existing columns. Search inputs and frozen columns stay put.
        requests.extend([
            {'insertDimension':{'range':{'sheetId':UI_ID,'dimension':'COLUMNS','startIndex':10,'endIndex':11},
                                'inheritFromBefore':True}},
            {'copyPaste':{'source':{'sheetId':UI_ID,'startRowIndex':8,'endRowIndex':current['gridProperties']['rowCount'],
                'startColumnIndex':9,'endColumnIndex':10},'destination':{'sheetId':UI_ID,'startRowIndex':8,
                'endRowIndex':current['gridProperties']['rowCount'],'startColumnIndex':10,'endColumnIndex':11},
                'pasteType':'PASTE_FORMAT','pasteOrientation':'NORMAL'}},
            {'updateDimensionProperties':{'range':{'sheetId':UI_ID,'dimension':'COLUMNS','startIndex':10,'endIndex':11},
                'properties':{'pixelSize':300,'hiddenByUser':False},'fields':'pixelSize,hiddenByUser'}}])
    requests.extend([
        {'updateCells':{'start':{'sheetId':UI_ID,'rowIndex':8,'columnIndex':0},
            'rows':[{'values':[{'userEnteredValue':{'stringValue':value}} for value in HEADERS]}],
            'fields':'userEnteredValue'}},
        {'updateCells': {'start': {'sheetId': UI_ID, 'rowIndex': 9, 'columnIndex': 0},
                         'rows': [{'values': [{'userEnteredValue': {'formulaValue': plan['after'][0][0]}}]}],
                         'fields': 'userEnteredValue'}},
        {'updateCells': {'start': {'sheetId': UI_ID, 'rowIndex': 5, 'columnIndex': 2},
                         'rows': [{'values': [{'userEnteredValue': {'stringValue': NOTE}}]}],
                         'fields': 'userEnteredValue'}}])
    client.request('POST', ':batchUpdate', json={'requests':requests})

def verify_ui(client, plan, read_values):
    if plan is not None:
        current=client.metadata().get(UI_TAB,{})
        if (read_values(client, FORMULA_RANGE) != plan['after'] or read_values(client, NOTE_RANGE) != [[NOTE]]
                or read_values(client,HEADER_RANGE)!=[HEADERS]
                or current.get('gridProperties',{}).get('columnCount')!=15):
            raise ValueError('native_ui_freshness_readback_mismatch')
