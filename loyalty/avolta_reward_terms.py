"""Numeric Avolta claims with their literal programme and spending currencies.

These are the observed native claim forms, not a foreign-exchange or eligibility
engine. Ambiguous dollars and explicit currency alternatives stay ambiguous.
"""
from __future__ import annotations

import re

from normalized import NUMERIC_TOKEN, literal_number


AMOUNT = '(' + NUMERIC_TOKEN + ')'


def _values(match, *groups):
    if not match:
        return None
    values = tuple(literal_number(match[group]) for group in groups)
    return values if all(value is not None for value in values) else None


def _award(claim, program, value, reward_unit, basis_value=None, basis_unit=None,
           *, miles=False, **scope):
    return dict(kind='earn_miles' if miles else 'earn_points', value=value,
                unit='miles' if miles else 'points', qualifier='exact',
                reward_unit=reward_unit, basis_value=basis_value, basis_unit=basis_unit,
                fragment=claim, scope={'reward_program': program, 'source_clause': claim, **scope})


def primary_terms(claim, conditions, partner):
    """Return only claims whose amount and denominator have owned evidence."""
    avios = re.search(r'накапливать по ' + AMOUNT + r' баллу Avios за каждый потраченный '
                      + AMOUNT + r' (евро|фунт стерлингов)(?: / ' + AMOUNT + r' (евро))?', claim)
    values = _values(avios, 1, 2)
    if values:
        value, basis = values
        if avios[4] is not None:
            alternative = literal_number(avios[4])
            if alternative is None:
                return []
            return [_award(claim, partner, value, 'Avios', basis_alternatives=[
                {'value': basis, 'unit': 'GBP' if avios[3] == 'фунт стерлингов' else 'EUR'},
                {'value': alternative, 'unit': 'EUR'}],
                basis_country_currency_assignment_not_stated=True)]
        return [_award(claim, partner, value, 'Avios', basis,
                       'GBP' if avios[3] == 'фунт стерлингов' else 'EUR')]

    kris = re.search(r'накапливать ' + AMOUNT + r' милю KrisFlyer за каждые потраченные '
                     + AMOUNT + r' доллара США\b', claim)
    values = _values(kris, 1, 2)
    if values:
        return [_award(claim, 'KrisFlyer', values[0], 'miles', values[1], 'USD', miles=True)]

    radisson = re.search(r'Получайте ' + AMOUNT + r' балла за ' + AMOUNT + r'\$', claim)
    explicit_usd = re.search(r'Получите ' + AMOUNT + r' балла за ' + AMOUNT + r' доллар США\b', conditions)
    values = _values(radisson, 1, 2)
    if values and values == _values(explicit_usd, 1, 2) and 'Radisson Rewards' in claim:
        return [_award(claim, 'Radisson Rewards', values[0], 'Radisson_Rewards_points_not_cash',
                       values[1], 'USD', basis_currency_evidence=explicit_usd[0])]

    aeroplan = re.search(r'получить ' + AMOUNT + r' балл Aeroplan за каждые '
                         + AMOUNT + r' доллара, потраченные\b', claim)
    values = _values(aeroplan, 1, 2)
    if values:
        return [_award(claim, 'Aeroplan', values[0], 'Aeroplan_points_not_cash',
                       values[1], 'dollar_unspecified', basis_currency_ambiguous=True)]

    savings = re.match(r'Сэкономьте (до )?' + AMOUNT + r'\s*%', claim)
    values = _values(savings, 2)
    if values:
        return [dict(kind='discount', value=values[0], unit='percent',
                     qualifier='up_to' if savings[1] else 'exact', fragment=claim,
                     scope={'source_clause': claim})]

    dollars = re.match(r'Получите скидку ' + AMOUNT + r' долларов на\b', claim)
    values = _values(dollars, 1)
    if values:
        return [dict(kind='discount', value=values[0], unit='dollar_unspecified',
                     qualifier='exact', fragment=claim,
                     scope={'source_clause': claim, 'currency_ambiguous': True})]
    return []


def supplementary_terms(conditions):
    terms = []
    for line in conditions.splitlines():
        carat = re.search(r'вы получите ' + AMOUNT + r' CARAT за каждые '
                          + AMOUNT + r' тайских батов в чеке\b', line)
        values = _values(carat, 1, 2)
        if values:
            term = _award(line, 'King Power', values[0], 'King_Power_CARAT_not_cash', values[1], 'THB')
            term.update(path='/conditions', standalone_offer=False)
            terms.append(term)
    return terms
