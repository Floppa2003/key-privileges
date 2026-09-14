"""Fixed normalized views. The final two managed columns are state and snapshot."""
from unified_normalization import dump,digest,VERSION

TAIL=['Статус нормализации','Снимок']
SCHEMAS={
 'normalized_records':['ID','Программа','Партнёр','Заголовок','Тип записи','Категория','Набор данных','Строка источника','Приватность','Проверка','Статус источника','Доступность JSON','Дата источника','Начало','Окончание','Статус срока','URL источника','Прямая карточка','Выгод','Условий','Издержек','Записей кодов','Проблемы JSON','Неразобранных фрагментов','SHA256 входа','Версия']+TAIL,
 'normalized_benefits':['ID','ID записи','Программа','Партнёр','Тип выгоды','Значение','Нижняя граница','Единица','Квалификатор','База начисления','Единица базы','Единица вознаграждения','Область применения JSON','Связанные условия JSON','Указатель источника','Исходная формулировка','Метод извлечения','Требует проверки','Тип исходной записи','URL источника']+TAIL,
 'normalized_conditions':['ID','ID записи','Программа','Партнёр','Роль','Тип условия','Значение','Единица','Квалификатор','Область применения JSON','Указатель источника','Исходная формулировка','Метод извлечения','URL источника']+TAIL,
 'normalized_codes':['ID','ID записи','Программа','Партнёр','Код','Получение кода','Аудитория и область JSON','Указатель источника','Исходная формулировка','URL источника']+TAIL,
 'normalization_audit':['ID','Раздел','Источник','Входных записей','Результат','Подробности JSON','Дата оценки','Версия']+TAIL,
}


def strings(row):return ['' if x is None else str(x) for x in row]


def prepare_views(bundle):
    views={k:[] for k in SCHEMAS};generation=digest([bundle['audit']['source_snapshot_sha256'],bundle['as_of'],VERSION])
    tail=['current',generation]
    for r in bundle['records']:
        p=r['provenance'];q=r['quality'];v=r['validity'];program=r['program']['name'];partner=r['partner']['name']
        views['normalized_records'].append(strings([r['id'],program,partner,r['title'],r['kind'],r.get('category'),p['origin'],p['source_row'],r['privacy'],q['verification'],p['source_status'],dump(r.get('availability',{})),p['observed_at'],v['from'],v['until'],v['status'],p['source_url'],p['benefit_url'],len(r['benefits']),len(r['conditions']),len(r['costs']),len(r['codes']),dump(q['issues']),q['unparsed_clause_count'],digest(r['raw']),VERSION]+tail))
        for b in r['benefits']:
            views['normalized_benefits'].append(strings([b['id'],r['id'],program,partner,b['kind'],b['value'],b.get('value_min'),b['unit'],b['qualifier'],b['basis_value'],b['basis_unit'],b['reward_unit'],dump(b['scope']),dump(b.get('condition_ids',[])),b['evidence']['path'],b['evidence']['text'],b['method'],'yes',r['kind'],p['source_url']]+tail))
        for group in ('conditions','costs'):
            for c in r[group]:
                views['normalized_conditions'].append(strings([c['id'],r['id'],program,partner,group,c['kind'],c['value'],c['unit'],c['qualifier'],dump(c['scope']),c['evidence']['path'],c['evidence']['text'],c['method'],p['source_url']]+tail))
        for c in r['codes']:
            views['normalized_codes'].append(strings([c['id'],r['id'],program,partner,c['value'],c['delivery'],dump(c['scope']),c['evidence']['path'],c['evidence']['text'],p['source_url']]+tail))
    for origin,count in bundle['audit']['by_input'].items():
        views['normalization_audit'].append(strings([digest(['input',origin]),'input',origin,count,'processed',dump({'source_text_preserved':True,'same_record_count':True}),bundle['as_of'],VERSION]+tail))
    views['normalization_audit'].append(strings(['manifest','snapshot','all_inputs',len(bundle['records']),'normalized',dump(bundle['audit']),bundle['as_of'],VERSION]+tail))
    views['normalization_audit'].append(strings(['interpretation_boundary','contract','all_inputs','','not_a_savings_calculator',dump({'all_terms_need_scope_review':True,'unknown_is_not_false':True,'source_clauses_not_exhaustively_understood':True,'legacy_not_reverified':True,'no_cross_source_value_merging':True,'eight_input_tabs_unchanged':True}),bundle['as_of'],VERSION]+tail))
    for name,rows in views.items():
        ids=set()
        for row in rows:
            if len(row)!=len(SCHEMAS[name]) or row[0] in ids:raise ValueError('View shape/identity mismatch')
            ids.add(row[0])
            if any(len(cell)>40000 for cell in row):raise ValueError('Oversized view cell; no truncation')
    return views


def retire_missing(existing,incoming,width):
    """Old derived terms remain auditable, but stop being current normalization.
    This does not expire/delete the original offer or overwrite its source row.
    """
    current={row[0] for row in incoming};result=list(incoming)
    for row in existing[1:]:
        if not row or not row[0] or row[0] in current:continue
        prior=(list(row[:width])+['']*width)[:width]
        if prior[-2]=='current':
            prior[-2]='retired_from_normalization';result.append(prior)
    return result
