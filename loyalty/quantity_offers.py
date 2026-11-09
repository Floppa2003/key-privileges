"""Literal quantity offers shared by source extraction and catalogue admission.

Digit counts have no offer-specific cap. Russian words cover cardinal and
genitive forms through 99; unknown compounds are not interpreted as suffixes.
The original phrase remains the evidence: no percentage or price is inferred.
"""
import re

from normalized import NUMERIC_TOKEN, literal_number, number_starts_here
from reward_context import benefit_denied


_FORMS = {
    0: 'ноль нуля', 1: 'один одна одно одного одной', 2: 'два две двух',
    3: 'три трех', 4: 'четыре четырех', 5: 'пять пяти', 6: 'шесть шести',
    7: 'семь семи', 8: 'восемь восьми', 9: 'девять девяти', 10: 'десять десяти',
    11: 'одиннадцать одиннадцати', 12: 'двенадцать двенадцати',
    13: 'тринадцать тринадцати', 14: 'четырнадцать четырнадцати',
    15: 'пятнадцать пятнадцати', 16: 'шестнадцать шестнадцати',
    17: 'семнадцать семнадцати', 18: 'восемнадцать восемнадцати',
    19: 'девятнадцать девятнадцати', 20: 'двадцать двадцати',
    30: 'тридцать тридцати', 40: 'сорок сорока', 50: 'пятьдесят пятидесяти',
    60: 'шестьдесят шестидесяти', 70: 'семьдесят семидесяти',
    80: 'восемьдесят восьмидесяти', 90: 'девяносто девяноста',
}
_VALUES = {word: n for n, forms in _FORMS.items() for word in forms.split()}
_WORD = '(?:' + '|'.join(sorted(_VALUES, key=len, reverse=True)) + ')'
_COUNT = rf'(?:{NUMERIC_TOKEN}|{_WORD}(?:\s+{_WORD})?)'
_OFFER = re.compile(rf'(?<!\w)(?P<more>{_COUNT})\s+по\s+цене\s+(?P<paid>{_COUNT})(?!\w)', re.I)
_EXTRA_NUMBER = rf'(?:{_WORD}|сто|ста|двести|двухсот|триста|трехсот|четыреста|четырехсот|пятьсот|пятисот|тысяч\w*|миллион\w*|минус|плюс)'


def count_value(token):
    """A complete nonnegative integer, in digits or supported Russian words."""
    token=token.casefold().replace('ё', 'е').strip()
    if not token:return None
    if token[0].isdigit():
        parsed = literal_number(token)
        return int(parsed) if parsed is not None and parsed.isdecimal() else None
    if any(word not in _VALUES for word in token.split()):return None
    values = [_VALUES[word] for word in token.split()]
    if len(values) == 1:
        return values[0]
    if len(values) == 2 and values[0] >= 20 and values[0] % 10 == 0 and 1 <= values[1] <= 9:
        return sum(values)
    return None


def has_quantity_offer(value):
    # Replacing ё keeps offsets intact for the shared local-denial classifier.
    text = value.casefold().replace('ё', 'е')
    for match in _OFFER.finditer(text):
        prefix, tail = text[:match.start()], text[match.end():]
        if (not number_starts_here(text, match.start())
                or re.search(r'(?:[+−–—-]|\d\s*[–—-]\s*)$', prefix)
                or re.search(rf'\b{_EXTRA_NUMBER}\s+$', prefix)):
            continue
        if re.match(rf'(?:[.,]\d|\s*[–—-]\s*(?:\d|{_WORD})|\s+{_EXTRA_NUMBER}\b|\s+с\s+половиной\b)', tail):
            continue
        more, paid = count_value(match['more']), count_value(match['paid'])
        if more is None or paid is None or not more > paid > 0:
            continue
        end = match.end() + len(re.match(r'[»”"\']*', tail)[0])
        suffix = text[end:]
        if re.match(r'\s*(?:₽|\$|€|руб\w*\b|копе\w*\b|usd\b|eur\b|доллар\w*\b|евро\b)', suffix):
            continue
        if benefit_denied(text, match.start(), end):
            continue
        if re.match(r'\s+(?:(?:уже|была)\s+)?(?:отменен\w*|завершен\w*|законч\w*|недействител\w*)\b', suffix):
            continue
        return True
    return False
