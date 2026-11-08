"""Local action ownership for literal reward spans in unchanged source text.

This module classifies context only. Numeric validation and the decision to
project a bare amount belong to the source/common parsers.
"""
import re


_BOUNDARY = r'[.!?](?:\s|$)|[;\n]|\b(?:но|зато|однако)\b'
_EARN = r'получ\w*|начисл\w*|заработ\w*'
_SPEND = r'спис\w*|спиш\w*|потрат\w*|трат\w*|оплат(?:и|я)\w*|оплач(?:ива|у)\w*|обмен(?:я|ива)\w*|конвертир\w*'
_ACTION = re.compile(r'\b(?:(?P<earn>' + _EARN + r')|(?P<spend>' + _SPEND + r'))\b', re.I)
_BENEFIT_ACTION = re.compile(r'\b(?P<earn>' + _EARN +
                             r'|предостав\w*|выда\w*|действ\w*|верн\w*|возвращ\w*)\b', re.I)
_DENIAL = r'(?:не|нельзя|невозможно)(?:\s+(?:буд\w*|мож\w*|смож\w*|вам|мы|вы)){0,2}'
_MODIFIERS = r'(?:(?:буд\w*|уже|вам|нам|им|ему|ей|мне|тебе)\s+){0,3}'
_PURCHASE = (r'(?:(?:на|за|при|после)\s+(?:(?:перв\w*|повторн\w*|кажд\w*)\s+)?'
             r'(?:заказ\w*|покупк\w*|визит\w*|посещени\w*|регистраци\w*|проживани\w*)\s+)?')
# These spans only connect a shared action across a plain amount list. They do
# not create or validate a quantity, and cannot cross another action/condition.
_MENTION = re.compile(r'\d[\d., \t\u00a0\u202f]*\s+'
                      r'(?:(?:дополнительн\w*|бонусн\w*)\s+){0,2}'
                      r'(?:балл\w*|бонус(?:ов|а)?|мил[ьяиюе]\w*)\b', re.I)
_BALANCE = re.compile(r'\b(?:баланс\w*|номинал\w*|на\s+(?:(?:вашем|ваш)\s+)?сч[её]т[еу])\b', re.I)
_PAYMENT_NOUN = re.compile(r'\b(?:оплат[ауыое]|стоимост\w*|цен[аыуе])\b', re.I)


def _action_role(action, prefix, suffix=''):
    if re.search(r'\b' + _DENIAL + r'\s*$', prefix, re.I):
        return 'denied'
    if re.match(r'\s+(?:нельзя|невозможно|не\s+буд\w*)\b', suffix, re.I):
        return 'denied'
    return 'earn' if action.lastgroup == 'earn' else 'spend'


def _owned_role(text, start, end, *, amounts=(), actions=_ACTION,
                references=True, partial_exclusion=None, mixed_list=False):
    """Return the action/reference owned by the source span ``[start:end]``.

    A direct postfix action wins over an unrelated preceding action. A shared
    postfix action can cross only an otherwise bare coordinated amount list.
    """
    boundary=_BOUNDARY+(r'|\bа\b' if mixed_list else '')
    left = max((m.end() for m in re.finditer(boundary, text[:start], re.I)), default=0)
    stop = re.search(boundary, text[end:], re.I)
    right = end + stop.start() if stop else len(text)
    prefix, suffix = text[left:start], text[end:right]
    spans = amounts or [(m.start(), m.end()) for m in _MENTION.finditer(text)]
    # Reference markers own the entire otherwise bare coordinated list.
    # A new action or an affirmative contrast breaks the walk backwards.
    reference_start=start
    for other_start,other_end in reversed(spans):
        if other_end>reference_start or other_start<left:
            continue
        if not re.fullmatch(r'\s*(?:,|\+|и|или)\s*',text[other_end:reference_start],re.I):
            break
        reference_start=other_start
    # Replacement/reference words own this amount, even if the next amount is
    # positively awarded: "не 500 баллов, а 100 баллов начислим".
    if re.search(r'\b(?:не|вместо|кроме)\s*$', text[left:reference_start], re.I):
        return 'reference' if references else 'denied'
    if references and re.search(r'\bза\s+(?:кажды[еий]\s+)?$', prefix, re.I):
        return 'reference'

    preceding = list(actions.finditer(prefix))
    following_suffix = suffix
    shared_following=False
    own_prefix = bool(preceding and ',' not in prefix[preceding[-1].end():]
                      and not any(left + preceding[-1].end() <= a < b <= start for a,b in spans))
    if not own_prefix:
        cursor = end
        for other_start, other_end in spans:
            if other_start < end or other_end > right:
                continue
            separator=r'\s*(?:,|\+|и|или)\s*'+(r'(?:\w+\s+){0,3}' if mixed_list else '')
            if not re.fullmatch(separator, text[cursor:other_start], re.I):
                break
            cursor = other_end
        shared_following=cursor>end
        following_suffix = text[cursor:right]
    if re.match(r'\s*(?:нельзя|невозможно)\b', following_suffix, re.I):
        return 'denied'
    following = re.match(r'\s*' + _PURCHASE + _MODIFIERS + r'(?P<denial>' + _DENIAL + r'\s+)?'
                         + _MODIFIERS + r'(?P<action>' + actions.pattern + r')',
                         following_suffix, re.I)
    if following:
        if following['denial']:
            if (mixed_list and shared_following and
                    not re.search(r'(?:[уюя]т(?:ся)?|[её]м|им|ены|лены)$',following['action'],re.I)):
                return 'unknown'
            if partial_exclusion and partial_exclusion(following_suffix[following.end():],following['action']):
                return 'earn'
            return 'denied'
        action = actions.fullmatch(following['action'])
        return _action_role(action, '', following_suffix[following.end():])

    # Account amounts describe a state/threshold until a new earning action.
    # A comma prevents an earlier balance condition owning the later reward.
    local_start = prefix.rfind(',') + 1
    balances = list(_BALANCE.finditer(prefix, local_start))
    if references and balances and (not preceding or balances[-1].start() > preceding[-1].start()):
        return 'reference'
    if (references and _PAYMENT_NOUN.search(prefix,local_start)
            and not any(a.start() >= local_start for a in preceding)):
        return 'reference'
    if preceding:
        action = preceding[-1]
        return _action_role(action, prefix[:action.start()], prefix[action.end():])
    return 'unknown'


def reward_role(text, start, end, *, amounts=()):
    """Action/reference owned by a literal points or miles quantity."""
    return _owned_role(text, start, end, amounts=amounts)


def benefit_denied(text, start, end, *, amounts=(), gift=False):
    """An explicit owned denial, preserving product/cash-equivalent exclusions."""
    def partial_exclusion(tail,action):
        if gift and re.match(r'\s+в\s+денежном\s+эквиваленте\b', tail, re.I):
            return True
        restriction=re.match(r'\s+(?P<preposition>на|для|при|за)\s+(?P<object>[^.!?;]+)',tail,re.I)
        if not restriction:return False
        # A payout destination is part of the denied credit, not an excluded
        # product/category/payment method. Do not whitelist product names.
        destination=(r'(?:(?:ваш\w*|сво\w*|личн\w*|бонусн\w*|банковск\w*|расч[её]тн\w*)\s+){0,3}'
                     r'(?:сч[её]т\w*|баланс\w*|карт[уы]\b|карточк\w*|кошел[её]к\w*)')
        denied_credit=(restriction['preposition'].casefold()=='на'
                       and not re.match(r'действ',action,re.I)
                       and re.match(destination,restriction['object'],re.I))
        return not bool(denied_credit)
    return _owned_role(text, start, end, amounts=amounts, actions=_BENEFIT_ACTION,
                       references=False, partial_exclusion=partial_exclusion,mixed_list=True) == 'denied'


def gift_spans(text, *, boundaries_only=False):
    """Literal gift markers; ambiguous complementary spelling is boundary-only."""
    adjective = r'компл[ие]ментар\w*' if boundaries_only else r'комплиментар\w*'
    obj = r'(?:\s+(?!(?:не|на|при|для|с|и|или)\b)\w+)?'
    return list(re.finditer(r'\b(?:в\s+подарок|' + adjective + obj
                            + r'|подарок(?=\s+при)|gift(?=\s+(?:with|on|for))|complimentary'
                            + obj + r')(?=\W|[0-9]|$)', text, re.I))
