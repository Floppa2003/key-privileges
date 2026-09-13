"""Scoped rates from explicit discount tables, never from unrelated percentages.

Raw tables stay authoritative. Rows from distinct tables are not joined: their
surrounding conditions or redemption channels may differ. Unknown layouts remain
unparsed rather than manufacturing a rate, card tier, or coupon.
"""
from __future__ import annotations
import re
from decimal import Decimal
from promo_codes import extract_promocodes

SCOPES = {'тип карты': 'card_type', 'вид карты': 'card_type',
          'тип номера': 'room_type', 'промокод': 'promo_code'}
DISCOUNTS = {'скидка', 'размер скидки', 'cкидка'}
PERCENT = re.compile(r'(?:(до|от)\s+)?(\d+(?:[.,]\d+)?)\s*'
                     r'(?:[–—-]\s*(\d+(?:[.,]\d+)?)\s*)?%')


def _decimal(value: str) -> str:
    normalized = format(Decimal(value.replace(',', '.')), 'f')
    return normalized.rstrip('0').rstrip('.') if '.' in normalized else normalized


def extract_table_benefits(tables: list) -> dict:
    """Keep exact scope spelling, complete row evidence, and unresolved rows."""
    if not isinstance(tables, list):
        raise ValueError('Source tables must be a list')
    components, issues = [], []
    for ti, table in enumerate(tables):
        def issue(reason, row_index=None):
            issues.append({'table_index': ti, 'row_index': row_index, 'reason': reason})

        if not isinstance(table, list) or not table:
            issue('empty_or_invalid_table')
            continue
        header = table[0]
        if not isinstance(header, list) or not all(isinstance(c, str) for c in header):
            issue('invalid_table_header')
            continue
        normalized = [re.sub(r'\s+', ' ', c).strip().casefold() for c in header]
        discounts = [i for i, h in enumerate(normalized) if h in DISCOUNTS]
        # A coupon column can accompany a card/room scope. Otherwise the coupon
        # itself is the scope, not an inferred card color hidden in its spelling.
        scopes = [i for i, h in enumerate(normalized) if h in SCOPES and h != 'промокод']
        codes = [i for i, h in enumerate(normalized) if h == 'промокод']
        if not scopes:
            scopes = codes[:]
        supported = set(SCOPES) | DISCOUNTS
        if (len(discounts) != 1 or len(scopes) != 1 or len(codes) > 1
                or len(set(normalized)) != len(normalized)
                or any(h not in supported for h in normalized)):
            issue('unsupported_or_ambiguous_header')
            continue
        si, di = scopes[0], discounts[0]
        for ri, row in enumerate(table[1:], 1):
            if not isinstance(row, list) or len(row) != len(header):
                issue('row_width_mismatch', ri)
                continue
            if not all(isinstance(c, str) for c in row):
                issue('non_text_cell', ri)
                continue
            scope = row[si].strip()
            match = PERCENT.fullmatch(row[di].strip())
            if not scope:
                issue('empty_scope', ri)
                continue
            if not match:
                issue('rate_not_recognized', ri)
                continue
            lower = Decimal(match[2].replace(',', '.'))
            upper = Decimal((match[3] or match[2]).replace(',', '.'))
            if not 0 <= lower <= upper <= 100 or (match[1] and match[3]):
                issue('invalid_rate_range', ri)
                continue
            rate = {'kind': 'discount', 'value': _decimal(match[3] or match[2]),
                    'unit': 'percent', 'qualifier': 'range' if match[3] else
                    'up_to' if match[1] == 'до' else 'at_least' if match[1] == 'от' else 'exact'}
            if match[3]:
                rate['min_value'] = _decimal(match[2])
            literal_codes = []
            if codes:
                ci = codes[0]
                literal_codes = extract_promocodes('', [[['Промокод'], [row[ci]]]])['codes']
                if row[ci].strip() and not literal_codes:
                    issue('promo_code_not_literal', ri)
                    if si == ci:
                        continue
            components.append({'scope': {'kind': SCOPES[normalized[si]], 'value': scope},
                               'rate': rate, 'promo_codes': literal_codes,
                               'evidence': {'table_index': ti, 'row_index': ri,
                                            'header': header[:], 'row': row[:]}})
    return {'components': components, 'issues': issues}
