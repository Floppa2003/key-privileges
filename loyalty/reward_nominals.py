"""Observed nominal point declarations, without inventing a monetary value."""
import re

from reward_context import reward_equivalence_prefix


POINT_LIST_HEADING = (r'количество\s+бонусов\s+к\s+(?:начислению|списанию)|'
                      r'за\s+покупку\s+квартиры\s+вам\s+будет\s+начислены|'
                      r'баллы\s+программы\s+«[^»]+»\s+будут\s+начислены\b|'
                      r'^получайте\s*:$')


def shared_point_card_options(value, *, declared_type):
    """A closed card-option declaration shares its own final point unit.

    The native field is explicitly typed as points. Its final aggregate card
    limit supplies the unit, never an additional award or an option's amount.
    No unit is borrowed from another record or from a monetary purchase rule.
    """
    if declared_type!='Баллы':return None
    # A runtime import avoids the normalizer's shared heading dependency.
    from normalized import NUMERIC_TOKEN, literal_number
    parts=[part.strip() for part in value.split(';')]
    if len(parts)<3:return None
    cap=re.fullmatch(r'максимум\s+при\s+нескольких\s+участвующих\s+картах\s*[—–-]\s*'
                     rf'(?P<value>{NUMERIC_TOKEN})\s+баллов\s*\.?',parts[-1],re.I)
    if not cap:return None
    maximum=literal_number(cap['value'])
    if maximum is None:return None
    options=[]
    for part in parts[:-1]:
        match=re.fullmatch(r'(?P<label>[^;\n]+?)\s+[—–-]\s*'
                           rf'(?P<value>{NUMERIC_TOKEN})',part)
        if not match:return None
        amount=literal_number(match['value'])
        if amount is None:return None
        options.append({'label':match['label'],'value':amount})
    return {'options':options,'cap':maximum,'cap_evidence':parts[-1]}


def demo_topup_bonuses(value):
    """The observed affirmative top-up action owns its bonus and event deadline.

    A ruble-denominated bonus does not assert withdrawable cash. A neighbouring
    virtual demo balance is not part of this action or an additional award.
    """
    from normalized import NUMERIC_TOKEN, literal_number
    pattern=(rf'\bПополните\s+сч[её]т\s+на\s+(?P<topup>{NUMERIC_TOKEN})\s*₽\s+'
             r'(?P<timing>до\s+окончания\s+демопериода)\s*[—–-]\s+и\s+'
             rf'заберите\s+дополнительный\s+бонус\s+(?P<bonus>{NUMERIC_TOKEN})\s*₽')
    for match in re.finditer(pattern,value,re.I):
        topup=literal_number(match['topup']);bonus=literal_number(match['bonus'])
        if topup is not None and bonus is not None:
            yield match,topup,bonus


def bonus_price_band(prefix):
    """An explicit inline bonus table labels its immediately following rate."""
    headings=list(re.finditer(r'Количество бонусов зависит от стоимости [^:;.!?\n]+:',prefix,re.I))
    if not headings:return False
    return bool(re.search(r'(?:^|[–—])\s*(?:от|до)\s+\d[\d., \t\u00a0\u202f]*\s*'
                          r'(?:₽|руб\w*\.?|RUB)\s*[—–-]\s*$',prefix[headings[-1].end():],re.I))


def point_declaration_role(clause,start,end,*,role,basis,heading='',declared=False,previous_award_end=None):
    """Resolve only a literal declaration not already owned by an action."""
    if role in ('unknown','reference') and bonus_price_band(clause[:start]):return 'earn'
    if role!='unknown':return role
    prefix=clause[:start]
    suffix=clause[end:]
    if reward_equivalence_prefix(clause,start) or re.match(r'\s*(?:[A-Za-z]+\s+)*[=–—]\s*\d',suffix):return 'reference'
    if re.search(r'бонусов\s+к\s+списанию',heading,re.I):return 'redemption_allowance'
    if re.search(POINT_LIST_HEADING,heading,re.I):return 'earn'
    if re.search(r'×\s*$',prefix) and not basis.get('basis_unit'):return 'multiplier'
    if basis.get('basis_unit'):return 'earn'
    if declared and not re.search(r'\b(?:или|нужно|порог|накопить|накоплено)\b',prefix,re.I):return 'earn'
    if re.search(r'приветственн',clause[start:end],re.I):return 'earn'
    local_prefix=re.split(r'[.!?](?:\s|$)|[;\n]',prefix)[-1]
    at_start=bool(re.fullmatch(r'[^\w]*|\s*[-–—•]?\s*(?:до|от)\s+',local_prefix,re.I))
    # Explicit purchase/reward occasions after a nominal quantity distinguish
    # these offers from status thresholds (nights/year) and prices in points.
    tail=re.sub(r'^\s*(?:«(?:РЖД Бонус|Крылья)»|CoralBonus)\s*',' ',suffix,flags=re.I)
    award_tail=(r'\s*[–—-]?\s*(?:за\s+(?:покупк\w*|заказ\w*|проживани\w*|'
                r'студи\w*|[1-4]-(?:к(?:омнатн\w*)?)\b)|'
                r'при\s+покупк\w*|на\s+(?:(?:первую|каждую)\s+)?(?:поездк\w*|путешеств\w*|карту\b)|'
                r'(?:в\s+день|ко\s+дню)\s+рождения\b)')
    if re.match(award_tail,tail,re.I):return 'earn'
    if at_start and re.match(r'\s*,\s*которыми\s+можно\s+оплатить\b',suffix,re.I):return 'earn'
    if previous_award_end is not None and re.search(r'\bи\s*$',prefix[previous_award_end:],re.I):return 'earn'
    return role


def percent_point_ceiling(prefix):
    """An amount closing an explicit percentage formula is its nominal cap."""
    return bool(re.search(r'\d[\d., ]*%[^;\n.!?]*(?:баллами|бонусами)[^;\n.!?]*,\s*до\s*$'
                          r'|\d[\d., ]*%\s+бонусов\s+за\s+оплату\s+[^();.!?\n\d%]{1,100}'
                          r'\(\s*не\s+более\s*$',prefix,re.I))
