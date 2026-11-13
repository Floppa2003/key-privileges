"""Conservative literal coupon extraction. Delivery instructions are separate evidence.

Input is the normalized source text, not rendered commands to execute. Unknown
codes are not guessed or fetched. Quoted multiword codes retain internal spelling.
"""
from __future__ import annotations
import re

LABEL = re.compile(r'\bпромокод(?:а|у|ом|ы)?\b', re.I)
TOKEN = re.compile(r'[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9_.-]*')
STOP = {'http', 'https', 'промокод', 'промокоды', 'акция', 'скидка', 'скидки', 'мир', 'синий', 'серебряный', 'золотой', 'получите', 'получить', 'дополнительные'} | set(('в во на для по при с со из от до после перед к и или либо не нет '
            'составляет составит действует действителен действительны можно нужно '
            'необходимо предоставляет суммируется является выдаётся выдается придёт '
            'придет приходит активируется вводится будет будут уникальный персональный '
            'ваш свой полученный данный ограничен доступен отображается позволяет '
            'скопировать введите ввести применить как срок сроки получение предоставляется '
            'воспользоваться from the is in of by sms смс').split())
QUOTES = {'«': '»', '“': '”', '"': '"'}
CANCELLATION_WORDS = {'больше', 'уже', 'временно', 'сейчас', 'пока',
                      'недействителен', 'отменён', 'отменен', 'аннулирован'}


def promocode_applicability_heading(value: str, mention: re.Match) -> bool:
    """A relative applicability predicate introduces its products, not a code."""
    return bool(re.search(r'\bна\s+которые\s+действует\s+$', value[:mention.start()], re.I)
                and re.match(r'\s*:', value[mention.end():]))


def promocode_delivery_methods(clause: str) -> list[str]:
    """Keep the channel owned by code availability, not by card/use actions.

    Preserve other existing references when the source does not resolve their
    role. A card from an app, entering a code there, or a discount applying there
    supplies explicit contrary evidence to app/account code issuance.
    """
    methods = []
    for method, pattern in (('sms', r'\b(?:SMS|СМС)\b'),
                            ('account', r'личн\w*\s+кабинет\w*'),
                            ('app', r'приложени\w*')):
        for match in re.finditer(pattern, clause, re.I):
            left = max([0] + [m.end() for m in re.finditer(r'\s+[–—]\s+', clause[:match.start()])])
            boundary = re.search(r'\s+[–—]\s+', clause[match.end():])
            right = match.end() + boundary.start() if boundary else len(clause)
            local = clause[left:right]
            if method != 'sms':
                prefix = clause[left:match.start()]
                if re.search(r'\bкарт\w*\s+из\s+(?:мобильн\w*\s+)?$', prefix, re.I):
                    continue
                issuance = re.search(
                    r'\b(?:получ\w*|выда\w*)\s+[«“"]?промокод\w*\b|'
                    r'\bпромокод\w*\s+(?:будет\s+)?(?:отображ\w*|выда\w*|прид[её]т|приход\w*)\b',
                    local, re.I)
                redemption = LABEL.search(local) and re.search(r'\b(?:введите|ввести)\b', local, re.I)
                applicability = re.search(r'\bпромокод\s+предоставляет\s+скидк\w*\b', local, re.I)
                if not issuance and (redemption or applicability):
                    continue
            methods.append(method)
            break
    return methods


def reconcile_promocode_delivery(method: str, value: str | None) -> bool:
    """Recheck retained references when their original clause identifies a role."""
    if not value or not LABEL.search(value):
        return True
    return any(method in promocode_delivery_methods(clause)
               for clause in re.split(r'[\n;]|(?<=[.!?])\s+', value))


def candidate(value: str, position: int, prefix: str) -> tuple[str | None, int]:
    # A label and its value can occupy adjacent source lines without a colon.
    # Do not cross a blank line into a different section.
    gap = re.match(r'[ \t]*(?:(?P<delimiter>[:—–-])[ \t]*)?(?:\r?\n[ \t]*)?', value[position:])
    delimited = bool(gap['delimiter'])
    start = position + gap.end()
    if '\n' in gap[0] and not delimited and not re.search(r'(?:^|\n)[ \t]*$', prefix):
        return None, start
    tail = value[start:]
    quoted = tail[:1] in QUOTES
    if quoted:
        end = tail.find(QUOTES[tail[0]], 1)
        if end < 0 or end > 62:
            return None, start
        code = tail[1:end].strip()
        stop = start + end + 1
    else:
        token = TOKEN.match(tail)
        if not token:
            return None, start
        code = token[0].rstrip('.')
        stop = start + token.end()
        # Only all-uppercase words can extend an unquoted code. Never join an
        # instruction such as "из SMS" or a number/date onto its first word.
        # A final dot ends the sentence even when its next word is uppercase.
        # Internal dots remain literal, as do dots inside quoted codes.
        ended = token[0].endswith('.')
        for _ in range(3):
            if ended:
                break
            extra = re.match(r'[ \t]+[A-ZА-ЯЁ][A-ZА-ЯЁ0-9_.-]{1,29}(?![\w.-])', value[stop:])
            if not extra:
                break
            if extra[0].strip().rstrip('.').casefold() in STOP | CANCELLATION_WORDS:
                break
            code += extra[0].rstrip('.')
            stop += extra.end()
            ended = extra[0].endswith('.')
    words = code.split()
    if not words or not 2 <= len(code) <= 60 or (words[0].casefold() in STOP and not (quoted and words[0].casefold()=='скидка' and len(words)>1 and any(re.search(r'[A-Z0-9]',w) for w in words[1:]))):
        return None, stop
    if not re.fullmatch(r'[\w .-]+', code, re.UNICODE):
        return None, stop
    if re.fullmatch(r'\d+(?:[.,]\d+)+', code):
        return None, stop
    if not quoted:
        # Natural-language Cyrillic words after a mention are instructions, not
        # literal codes. Title-case Cyrillic alone needs explicit punctuation.
        if not (re.search(r'[A-Za-z0-9]',code) or code.isupper() or
                (delimited and len(words)==1 and code.istitle())):
            return None, stop
        if re.fullmatch(r'[А-Яа-яЁё]+',code) and re.search(r'(?:ите|йте|тесь)$',code,re.I):
            return None, stop
        after = value[stop:]
        if re.match(r'\s*(?:%|₽|руб\w*\b|дн\w*\b|день\b|дней\b|час\w*\b|мес\w*\b|раз\b)', after, re.I):
            return None, stop
        if words[0].casefold() in {'скидка', 'скидки', 'срок', 'размер', 'лимит'} and len(words) == 1:
            return None, stop
        if code.isdecimal() and re.search(r'(?:размер|лимит|сумм[аыуе])[^.!?\n]{0,100}$', prefix, re.I):
            return None, stop
    return code, stop


def promocode_occurrences(value: str, mention: re.Match) -> list[tuple[str, int, int]]:
    """Map a label's literal members before resolving their shared predicate.

    Only the existing plural label licenses quoted continuations. Positions
    retain each member's original spelling and evidence boundary, while the
    last member's end is the predicate boundary for the entire list.
    """
    position = mention.end()
    code, stop = candidate(value, position, value[max(0, mention.start()-150):mention.start()])
    if not code:
        return []
    members = [(code, position, stop)]
    if re.fullmatch(r'промокоды\s*(?:[:—–-]\s*)?', mention[0], re.I):
        for _ in range(8):
            separator = re.match(r'[ \t]*(?:,|/|\bи\b|\bили\b)[ \t]*(?=[«“"])', value[stop:])
            if not separator:
                break
            position = stop + separator.end()
            more, end = candidate(value, position, '')
            if not more:
                break
            members.append((more, position, end))
            stop = end
    return members


def coupon_restriction_continuation(value: str, *, labels=(LABEL,)) -> bool:
    """Whether the next source line/comma continues this applicability rule."""
    continuation = re.split(r'[,;\r\n]|[.!?](?:\s|$)', value.lstrip(' \t,\r\n'), maxsplit=1)[0]
    if re.match(r'(?:если|когда)\b', continuation, re.I):
        return True
    return bool(re.match(r'(?:[-–—]\s*)?(?:на|в|во|для|при|по|после|до|кроме)\b', continuation, re.I)
                and not any(label.search(continuation) for label in labels))


def coupon_owned_prefix(value: str, start: int, *, labels=(LABEL,)) -> str:
    """Original prefix for this occurrence, retaining wrapped antecedents."""
    prefix = re.split(r'[.!?;]|\r?\n[ \t]*\r?\n', value[:start])[-1]
    # A sibling after a coupon-directed instruction or an adversative owns
    # its own conditions. Other commas can be part of a conditional antecedent.
    owned_start = component_start = 0
    for boundary in re.finditer(r'(?:,\s*|\r?\n[ \t]*)(?:(а|но|однако)\b)?', prefix, re.I):
        component = prefix[component_start:boundary.start()]
        mentions = [mention for label in labels for mention in label.finditer(component)]
        instruction = any(
            re.search(r'\b(?:используйте|примените|введите)\s*$', component[:mention.start()], re.I)
            for mention in mentions)
        adversative = boundary[1] and any(label.search(prefix, 0, boundary.start()) for label in labels)
        # A real antecedent may wrap around a reference to another literal.
        # Once that literal's main clause has its own predicate, its condition
        # ends with the line. The predicate itself can occupy a wrapped line.
        independent_line = False
        if '\n' in boundary[0]:
            context = prefix[owned_start:boundary.start()]
            for mention in (m for label in labels for m in label.finditer(context)):
                members = promocode_occurrences(context, mention)
                if not members:
                    continue
                before = context[:mention.start()]
                complete = re.match(r'\s+(?:действу(?:ет|ют)|действител(?:ен|ьны))\b',
                                    context[members[-1][2]:], re.I)
                open_if = re.search(r'\bесли\b[^,]*$', before, re.I)
                if (not re.search(r'\b(?:если|после|при)\b', before, re.I)
                        or complete and not open_if):
                    independent_line = True
                    break
        if instruction or adversative or independent_line:
            owned_start = boundary.end()
        component_start = boundary.end()
    return prefix[owned_start:]


def promocode_cancelled(value: str, start: int, stop: int, *, labels=(LABEL,)) -> bool:
    """Only an unconditional predicate owned by this literal cancels it.

    Product/calendar exclusions and after-use/future conditions are not proof
    of current cancellation. In particular, a colon can introduce a multiline
    exclusion list rather than terminate an unconditional denial.
    """
    prefix = coupon_owned_prefix(value, start, labels=labels)
    if re.search(r'\b(?:если|после|при)\b', prefix, re.I):
        return False
    tail = '' if value[max(0, stop-1):stop] == '.' else value[stop:]
    postfix = re.split(r'[.!?;]', tail, maxsplit=1)[0]
    modifier = r'(?:(?:больше|уже|временно|сейчас|пока)\s+)?'
    denial = re.match(r'\s*(?P<annotation>\(\s*)?' + modifier + r'(?:не\s+действу(?:ет|ют)|недействител(?:ен|ьны)|отмен[её]н(?:ы)?|аннулирован(?:ы)?)\b', postfix, re.I)
    if denial:
        remainder = postfix[denial.end():]
        if denial['annotation']:
            remainder = re.sub(r'^\s*\)', '', remainder, count=1)
    elif re.search(r'\bне\s+(?:используйте|применяйте)\s*$', prefix, re.I):
        remainder = postfix
    else:
        return False
    if not remainder.strip():
        return True
    if re.match(r'[ \t]*[,\r\n]', remainder):
        # A comma or source line wrap can continue the applicability
        # predicate. A separate literal's clause cannot rescue this one.
        return not coupon_restriction_continuation(remainder, labels=labels)
    # A replacement or an explanation continues a complete cancellation.
    # Other trailing prose remains conservative, including dates and product
    # exclusions even when they are parenthesized or introduced by a dash.
    explanation = r'(?:поскольку|потому\s+что|из-за|по\s+(?:причине|решению))\b'
    return bool(re.match(
        r'\s*(?:и\s+замен[её]н(?:ы)?\b|[-–—]\s*(?:примените|используйте|введите)\b|'
        + explanation + r'|\(\s*(?:' + explanation
        + r'|(?:акци\w*|предложени\w*)\s+(?:заверш\w*|законч\w*)\b|вместо\b))',
        remainder, re.I))


def reconcile_promocode(code: str, texts: list[str], *, labels=None) -> str | None:
    """Reconcile a native literal only against matching original occurrences.

    Missing evidence leaves the native assertion intact. A separately live
    occurrence of the same value survives; callers supply component evidence
    when the native literal has an audience/card owner. Source-specific label
    patterns are opt-in; they do not broaden generic coupon extraction.
    """
    labels = (LABEL,) if labels is None else labels
    matches = []
    for value in texts:
        for mention in (match for label in labels for match in label.finditer(value)):
            members = promocode_occurrences(value, mention)
            if not members:
                continue
            cancelled = (promocode_applicability_heading(value, mention)
                         or promocode_cancelled(value, mention.start(), members[-1][2], labels=labels))
            for parsed, position, _ in members:
                # Do not trim a native multiword value merely because it contains
                # instruction words: the entire old literal must occur in source.
                tail = value[position:]
                same = parsed == code
                contaminated = (code.startswith(parsed + ' ')
                                and re.match(r'\s*(?:[:—–-]\s*)?' + re.escape(code) + r'(?=$|[^\w.-]|\.(?:\s|$))', tail))
                if same or contaminated:
                    matches.append(None if cancelled else parsed)
    live = [value for value in matches if value is not None]
    if code in live:
        return code
    return live[0] if live else None if matches else code


def extract_promocodes(value: str, tables: list | None = None) -> dict:
    return extract_promocodes_with_context(value, tables)


def extract_promocodes_with_context(value: str, tables: list | None = None, *, labels=(LABEL,)) -> dict:
    """Extract generic literals with the source's licensed sibling context.

    Extra labels classify occurrence ownership only; their literal extraction
    remains source-owned. Independent table occurrences retain their evidence.
    """
    codes, evidence, delivery = [], [], []
    mentions = list(LABEL.finditer(value))
    for match in mentions:
        if match[0].casefold()=='промокода' and re.search(r'(?:\bдва|\bтри|\bчетыре|\d+)\s+$',value[max(0,match.start()-40):match.start()],re.I):
            continue
        members = promocode_occurrences(value, match)
        cancelled = bool(members) and (promocode_applicability_heading(value, match)
                                      or promocode_cancelled(value, match.start(), members[-1][2], labels=labels))
        for code, _, stop in members:
            if code not in codes and not cancelled:
                codes.append(code)
                evidence.append({'code': code, 'evidence': value[match.start():stop].strip()})
        if match[0].casefold() == 'промокоды' and members:
            # Explicit 'CODE - percentage; CODE - percentage' offer lists only.
            # A later section or an unrelated word after a semicolon is not a code.
            section = re.split(r'\n\s*\n|(?<=[.!?])\s+(?=[А-ЯA-Z])', value[match.end():], maxsplit=1)[0]
            for item in re.finditer(r';[ \t]*(?P<code>[A-ZА-ЯЁ0-9][A-Za-zА-Яа-яЁё0-9_.-]{1,59})[ \t]+[-—–][ \t]+(?:до[ \t]+)?\d+(?:[.,]\d+)?[ \t]*%', section):
                more, _ = candidate(section, item.start('code'), '')
                if more and more not in codes:
                    codes.append(more)
                    evidence.append({'code':more, 'evidence':value[match.start():match.end()+item.end()].strip()})
    table_mention = False
    for table_index, table in enumerate(tables or []):
        if not isinstance(table,list) or not table or not isinstance(table[0],list):
            continue
        headers = table[0]
        columns = [i for i,h in enumerate(headers) if isinstance(h,str) and h.strip().casefold() in ('промокод','промокоды')]
        if len(columns) != 1:
            continue
        table_mention = True
        column = columns[0]
        for row_index, row in enumerate(table[1:],1):
            if not isinstance(row,list) or len(row)!=len(headers) or not all(isinstance(x,str) for x in row):
                continue
            raw = row[column].strip()
            code, _ = candidate('«'+raw+'»',0,'')
            if code and code==raw and code not in codes:
                codes.append(code)
                evidence.append({'code':code,'kind':'source_table','table_index':table_index,
                    'row_index':row_index,'code_column':column,'headers':headers,'row':row,
                    'evidence':' | '.join(f'{k}: {v}' for k,v in zip(headers,row))})
    for clause in re.split(r'[\n;]|(?<=[.!?])\s+', value):
        clause = clause.strip()
        if not LABEL.search(clause):
            continue
        for method in promocode_delivery_methods(clause):
            item = {'kind': 'delivery_reference', 'method': method, 'evidence': clause}
            if item not in delivery:
                delivery.append(item)
    return {'codes': codes, 'evidence': evidence, 'delivery': delivery,
            'status': 'explicit_codes_extracted' if codes else 'mentioned_not_extracted' if mentions or table_mention else 'not_mentioned'}
