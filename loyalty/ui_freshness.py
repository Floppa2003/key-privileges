"""Small, guarded upgrade of the owner-created native search formula.

TODAY() keeps stale observations out even if the entire CI run cannot publish.
No source data, styles, search inputs or unrelated programme filters are changed.
"""
from source_lifecycle import FRESHNESS_DAYS
UI_TAB = 'Скидки'
UI_ID = 2026092001
FORMULA_RANGE = "'Скидки'!A10"
NOTE_RANGE = "'Скидки'!C6"
LEGACY_PROGRAMMES = ('Backit — денежный кешбэк', 'Club Avolta', 'Мантера Моменты')
from expansion_common import PROGRAMS as EXPANSION_PROGRAMMES
PROGRAMMES = LEGACY_PROGRAMMES + tuple(EXPANSION_PROGRAMMES.values())
NOTE = ('Только конкретные предложения. Реклама и отключённые карточки исключены. '
        'Для Backit, Club Avolta, Мантеры, X5, Магнита, «Города», «Цветного» и FlyStation нужны наблюдения не старше 7 дней; '
        'это предел свежести проверки, а не срок самой акции.')

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
    if formula.count('keep;hits*') != 1 or "'_ui_catalog'!A2:Q" not in formula:
        raise ValueError('native_search_layout_changed')
    return formula.replace('keep;hits*', clause)

def prepare_ui(client, meta, read_values):
    if UI_TAB not in meta or meta[UI_TAB].get('sheetId') != UI_ID:
        return None
    before = read_values(client, FORMULA_RANGE)
    if len(before) != 1 or len(before[0]) != 1:
        raise ValueError('native_search_formula_missing')
    after = upgrade_formula(before[0][0])
    note_before = read_values(client, NOTE_RANGE)
    return {'before': before, 'after': [[after]], 'note_before': note_before}

def apply_ui(client, plan, read_values):
    if plan is None:
        return
    if read_values(client, FORMULA_RANGE) != plan['before'] or read_values(client, NOTE_RANGE) != plan['note_before']:
        raise ValueError('concurrent_native_ui_edit')
    if plan['after'] == plan['before'] and plan['note_before'] == [[NOTE]]:
        return
    client.request('POST', ':batchUpdate', json={'requests':[
        {'updateCells': {'start': {'sheetId': UI_ID, 'rowIndex': 9, 'columnIndex': 0},
                         'rows': [{'values': [{'userEnteredValue': {'formulaValue': plan['after'][0][0]}}]}],
                         'fields': 'userEnteredValue'}},
        {'updateCells': {'start': {'sheetId': UI_ID, 'rowIndex': 5, 'columnIndex': 2},
                         'rows': [{'values': [{'userEnteredValue': {'stringValue': NOTE}}]}],
                         'fields': 'userEnteredValue'}}]})

def verify_ui(client, plan, read_values):
    if plan is not None and (read_values(client, FORMULA_RANGE) != plan['after'] or read_values(client, NOTE_RANGE) != [[NOTE]]):
        raise ValueError('native_ui_freshness_readback_mismatch')
