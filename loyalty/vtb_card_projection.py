"""Owned VTB summary clauses from preserved source sections, without I/O."""
from __future__ import annotations

from decimal import Decimal
import re

SOURCE_ID = 'af_vtb_rules'
SOURCE_URL = 'https://www.vtb.ru/privilegia/karty/debetovye/privilegiya-aeroflot/'
CARD_PRODUCT = 'Привилегия Аэрофлот'
ROLE = 'supplementary_rules_not_incremental_discount'
HSPACE = r'[^\S\r\n]'
INTEGER = r'\d+(?:[ \u00a0\u202f]\d{3})*'
DETAIL = re.compile(r'За\s+каждые\s+([\d ]+)\s*₽.*?получите\s+(\d+)\s+мили', re.I | re.S)
HERO_MILES = re.compile(
    rf'^(?P<value>\d+){HSPACE}+мил(?:я|и|ь){HSPACE}*\n'
    rf'За{HSPACE}+каждые{HSPACE}+потраченные{HSPACE}+(?P<basis>{INTEGER}){HSPACE}*₽'
    rf'{HSPACE}+по{HSPACE}+карте{HSPACE}+Привилегия{HSPACE}+Аэрофлот{HSPACE}*$',
    re.I | re.M,
)
RESTAURANT_CASHBACK = re.compile(
    rf'^(?P<value>\d+(?:[.,]\d+)?){HSPACE}*%{HSPACE}*\n'
    rf'(?P<label>К[еэ]шб[еэ]к{HSPACE}+в{HSPACE}+ресторанах:{HSPACE}+[^\r\n]*\S){HSPACE}*$',
    re.I | re.M,
)


def _integer(value):
    try:
        return int(''.join(value.split()))
    except ValueError:
        return None


def project_stored_card(raw):
    """Return only a proven summary alias and its local restaurant benefit.

    A missing or conflicting contract leaves the existing consumer unchanged.
    Source text and persisted details are never repaired or enriched in place.
    """
    if (raw.get('origin') != 'parser_offers' or raw.get('source_id') != SOURCE_ID
            or raw.get('source_url') != SOURCE_URL or raw.get('kind') != 'program_rules'
            or raw.get('source_status') != 'public_rules_text'):
        return None
    details = raw.get('details')
    if not isinstance(details, dict):
        return None
    identity = details.get('_source')
    if (not isinstance(identity, dict) or identity.get('source_id') != SOURCE_ID
            or details.get('evidence_role') != ROLE or details.get('pages')):
        return None
    sections = details.get('sections')
    if (not isinstance(sections, list) or not sections
            or any(not isinstance(block, str) for block in sections)):
        return None
    body = '\n'.join(sections)
    if raw.get('benefit') != body or raw.get('conditions') != body:
        return None
    labels = [' '.join(block.split()) for block in sections]
    if (not any('Дебетовая карта Привилегия Аэрофлот' in label for label in labels)
            or any('Прайм Аэрофлот' in label for label in labels)):
        return None

    earning = [block for block, label in zip(sections, labels)
               if label.startswith('Как начисляются мили')]
    if len(earning) != 1 or details.get('earning_conditions') != earning[0]:
        return None
    matches = list(DETAIL.finditer(earning[0]))
    if len(matches) != 1:
        return None
    match = matches[0]
    basis_number = _integer(match[1])
    miles_number = _integer(match[2])
    if basis_number is None or miles_number is None:
        return None
    basis = str(basis_number)
    expected = {
        'value': match[2], 'unit': 'miles', 'basis_amount': basis,
        'basis_unit': 'RUB', 'qualifier': 'exact', 'evidence': match[0],
    }
    if (details.get('earning_rules') != [expected]
            or basis_number <= 0 or miles_number <= 0):
        return None

    aliases = [(index, candidate) for index, block in enumerate(sections)
               for candidate in HERO_MILES.finditer(block)]
    if len(aliases) != 1:
        return None
    section_index, alias = aliases[0]
    if (_integer(alias['value']) != miles_number
            or _integer(alias['basis']) != basis_number):
        return None
    cashback = list(RESTAURANT_CASHBACK.finditer(sections[section_index]))
    if len(cashback) != 1:
        return None
    cashback = cashback[0]
    amount = Decimal(cashback['value'].replace(',', '.'))
    if not 0 <= amount <= 100:
        return None
    value = format(amount, 'f')
    if '.' in value:
        value = value.rstrip('0').rstrip('.')
    return {
        # These two fields were bound to sections above. Activation has no
        # such ownership and must retain even an identical independent quote.
        'covered_quotes': {path: [alias[0]] for path in ('/benefit', '/conditions')},
        'cashback': {
            'path': f'/details/sections/{section_index}', 'evidence': cashback[0],
            'value': value, 'unit': 'percent', 'qualifier': 'exact',
            'scope': {'merchant_scope_text': cashback['label'], 'card_product': CARD_PRODUCT},
        },
    }
