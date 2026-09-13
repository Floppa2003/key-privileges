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


def candidate(value: str, position: int, prefix: str) -> tuple[str | None, int]:
    gap = re.match(r'[ \t]*(?:(?P<delimiter>[:—–-])[ \t]*(?:\n[ \t]*)?)?', value[position:])
    delimited = bool(gap['delimiter'])
    start = position + gap.end()
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
        extra = re.match(r'(?:[ \t]+[A-ZА-ЯЁ][A-ZА-ЯЁ0-9_.-]{1,29}(?![\w.-])){1,3}', value[stop:])
        if extra:
            code += extra[0].rstrip('.')
            stop += extra.end()
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


def extract_promocodes(value: str, tables: list | None = None) -> dict:
    codes, evidence, delivery = [], [], []
    mentions = list(LABEL.finditer(value))
    for match in mentions:
        if match[0].casefold()=='промокода' and re.search(r'(?:\bдва|\bтри|\bчетыре|\d+)\s+$',value[max(0,match.start()-40):match.start()],re.I):
            continue
        code, stop = candidate(value, match.end(), value[max(0, match.start()-150):match.start()])
        if code and code not in codes:
            codes.append(code)
            evidence.append({'code': code, 'evidence': value[match.start():stop].strip()})
        # Only a plural label licenses a list; do not treat arbitrary following
        # quoted UI labels or phrases as more coupons.
        if match[0].casefold() == 'промокоды' and code:
            for _ in range(8):
                separator = re.match(r'[ \t]*(?:,|/|\bи\b|\bили\b)[ \t]*(?=[«“"])', value[stop:])
                if not separator:
                    break
                position = stop + separator.end()
                more, stop = candidate(value, position, '')
                if more and more not in codes:
                    codes.append(more)
                    evidence.append({'code': more, 'evidence': value[match.start():stop].strip()})
                if not more:
                    break
        if match[0].casefold() == 'промокоды' and code:
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
        methods = []
        if re.search(r'\b(?:SMS|СМС)\b', clause, re.I):
            methods.append('sms')
        if re.search(r'личн\w*\s+кабинет\w*', clause, re.I):
            methods.append('account')
        if re.search(r'приложени\w*', clause, re.I):
            methods.append('app')
        for method in methods:
            item = {'kind': 'delivery_reference', 'method': method, 'evidence': clause}
            if item not in delivery:
                delivery.append(item)
    return {'codes': codes, 'evidence': evidence, 'delivery': delivery,
            'status': 'explicit_codes_extracted' if codes else 'mentioned_not_extracted' if mentions or table_mention else 'not_mentioned'}
