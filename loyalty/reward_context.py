"""Local action ownership for literal reward spans in unchanged source text.

This module classifies context only. Numeric validation and the decision to
project a bare amount belong to the source/common parsers.
"""
import re


_BOUNDARY = r'[.!?](?:\s|$)|[;\n]|\b(?:но|зато|однако)\b|\bа(?=\s+за\s+кажды[еий]\b)'
_EARN = r'получ\w*|начисл\w*|заработ\w*'
_SPEND = r'спис\w*|спиш\w*|потрат\w*|трат\w*|оплат(?:и|я)\w*|оплач(?:ива|у)\w*|обмен(?:я|ива)\w*|конвертир\w*'
_ACTION = re.compile(r'\b(?:(?P<earn>' + _EARN + r')|(?P<spend>' + _SPEND + r'))\b', re.I)
_BENEFIT_ACTION = re.compile(r'\b(?:(?P<earn>' + _EARN +
                             r'|предостав\w*|предусмотр\w*|доступ(?:ен|на|но|ны)'
                             r'|выда\w*|действ\w*|верн\w*|возвращ\w*)|'
                             r'(?P<denied>отмен[её]н(?:а|о|ы)?|аннулирован(?:а|о|ы)?|'
                             r'недоступ(?:ен|на|но|ны)))\b', re.I)
_DENIAL = r'(?:не|нельзя|невозможно)(?:\s+(?:буд\w*|мож\w*|смож\w*|вам|мы|вы)){0,2}'
_MODIFIER = r'(?:буд\w*|уже|больше|временно|сейчас|пока|вам|нам|им|ему|ей|мне|тебе)'
_MODIFIERS = r'(?:'+_MODIFIER+r'\s+){0,3}'
_RESTRICTION = re.compile(r'\s*\b'+_MODIFIERS+_DENIAL+r'\s+'+_MODIFIERS
                          +r'(?:предоставля\w*|действ\w*|распространя\w*)\b',re.I)
_PURCHASE = (r'(?:(?:на|за|при|после)\s+(?:(?:перв\w*|повторн\w*|кажд\w*)\s+)?'
             r'(?:заказ\w*|покупк\w*|визит\w*|посещени\w*|регистраци\w*|проживани\w*)\s+)?')
# These spans only connect a shared action across a plain amount list. They do
# not create or validate a quantity, and cannot cross another action/condition.
_MENTION = re.compile(r'\d[\d., \t\u00a0\u202f]*\s+'
                      r'(?:(?:дополнительн\w*|бонусн\w*)\s+){0,2}'
                      r'(?:балл\w*|бонус(?:ов|а)?|мил[ьяиюе]\w*)\b', re.I)
_BALANCE = re.compile(r'\b(?:баланс\w*|номинал\w*|на\s+(?:(?:вашем|ваш)\s+)?сч[её]т[еу])\b', re.I)
_PAYMENT_NOUN = re.compile(r'\b(?:оплат[ауыое]|стоимост\w*|цен[аыуе])\b', re.I)
_MONTHLY_MILEAGE_PAYOUT_CAP = (r'\bлимит\s+выплат\w*\s+'
                               r'(?:к[еэ]шб[еэ]к\w*\s*/\s*)?мил[ьяиюе]\w*\s+'
                               r'в\s+месяц[⁰¹²³⁴⁵⁶⁷⁸⁹]*')


def monthly_mileage_payout_cap(text, start):
    """A nominal monthly payout limit owns this quantity, not a past award."""
    return bool(re.search(_MONTHLY_MILEAGE_PAYOUT_CAP+r'\s*$', text[:start], re.I))


def benefit_context_text(value):
    """Keep explicit owner continuations together without changing offsets."""
    marker=r'(?:скидк\w*|к[еэ]шб[еэ]к\w*|бесплат\w*|подар\w*)'
    result=value
    # Native PDF wrapping can divide the payout-limit label itself. Keep only
    # that explicit nominal owner together in the temporary context buffer;
    # unrelated lines and the preserved evidence remain unchanged.
    for cap in re.finditer(_MONTHLY_MILEAGE_PAYOUT_CAP,value,re.I):
        result=result[:cap.start()]+result[cap.start():cap.end()].replace('\n',' ')+result[cap.end():]
    for boundary in re.finditer(r'\n',value):
        before=re.split(r'[.!?](?:\s|$)|[;\n]',value[:boundary.start()])[-1]
        after=re.split(r'[.!?](?:\s|$)|[;\n]',value[boundary.end():])[0]
        if (re.search(r'\b(?:если|когда|при|после)\b',before,re.I)
                and not re.search(r'\b'+marker,before,re.I)
                and re.match(r'[ \t]*'+marker+r'\b',after,re.I)
                and any(a.lastgroup=='denied' for a in _BENEFIT_ACTION.finditer(after))):
            result=result[:boundary.start()]+' '+result[boundary.end():]
    return result


def purchase_requirement_denied(prefix, suffix):
    """Whether a local purchase phrase owns a negative requirement predicate."""
    mandatory = r'обязател(?:ен|ьн\w*)'
    requirement = r'(?:(?:по)?треб(?:у|ова)\w*|нуж(?:ен|н\w*)|'+mandatory+r')'
    negative = (_MODIFIERS+r'(?:не\s+'+_MODIFIERS+requirement
                +r'|не'+mandatory+r')\b'
                +r'(?:\s+'+_MODIFIER+r'){0,3}')
    if re.search(r'\b'+negative+r'\s+'
                 r'(?:(?:оформля\w*|дела\w*|соверша\w*)\s+)?'+_MODIFIERS
                 +r'(?:(?:ваш\w*|сво\w*|перв\w*|повторн\w*|последующ\w*)\s+){0,3}$',
                 prefix, re.I):
        return True
    # A closing predicate owns the purchase phrase. A subsequent instruction
    # with its own argument, e.g. "больше не требуется предъявлять карту", does
    # not close that phrase and must not cancel its actual threshold.
    return bool(re.match(r'\s*(?:[–—:-]\s*)?'+negative+r'(?=\s*(?:[,.!?;]|$))',
                         suffix, re.I))


def _action_role(action, prefix, suffix=''):
    negated = (re.search(r'\b' + _DENIAL + r'\s*$', prefix, re.I)
               or re.match(r'\s+(?:нельзя|невозможно|не\s+буд\w*)\b', suffix, re.I))
    if action.lastgroup == 'denied':
        return 'earn' if negated else 'denied'
    if negated:return 'denied'
    return 'earn' if action.lastgroup == 'earn' else 'spend'


def _owned_role(text, start, end, *, amounts=(), actions=_ACTION,
                references=True, partial_exclusion=None, mixed_list=False):
    """Return the action/reference owned by the source span ``[start:end]``.

    A direct postfix action wins over an unrelated preceding action. A shared
    postfix action can cross only an otherwise bare coordinated amount list.
    """
    text=benefit_context_text(text)
    boundary=_BOUNDARY+(r'|\bа\b' if mixed_list else '')
    left = max((m.end() for m in re.finditer(boundary, text[:start], re.I)), default=0)
    stop = re.search(boundary, text[end:], re.I)
    right = end + stop.start() if stop else len(text)
    prefix, suffix = text[left:start], text[end:right]
    spans = amounts or [(m.start(), m.end()) for m in _MENTION.finditer(text)]
    antecedent_start=left
    antecedent_end=start
    for a,b in reversed(spans):
        if not left<=a<b<=antecedent_end:continue
        separator=r'\s*(?:,|\+|и|или)\s*'+(r'(?:\w+\s+){0,3}' if mixed_list else '')
        if not re.fullmatch(separator,text[b:antecedent_end],re.I):
            antecedent_start=max(b,text.rfind(',',b,antecedent_end)+1)
            break
        antecedent_end=a
    conditional=bool(partial_exclusion and re.search(r'\b(?:если|когда|при|после)\b',
                                                    text[antecedent_start:antecedent_end],re.I))
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
        action = actions.fullmatch(following['action'])
        role = _action_role(action, following['denial'] or '',
                            following_suffix[following.end():])
        if role == 'denied':
            if conditional and action.lastgroup=='denied':return 'earn'
            if (mixed_list and shared_following and
                    not re.search(r'(?:[уюя]т(?:ся)?|[её]м|им|[а-яё]ны)$',following['action'],re.I)):
                return 'unknown'
            if partial_exclusion and partial_exclusion(following_suffix[following.end():],following['action']):
                return 'earn'
        return role

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
        role = _action_role(action, prefix[:action.start()], prefix[action.end():])
        return 'earn' if role=='denied' and conditional and action.lastgroup=='denied' else role
    return 'unknown'


def forward_reward_basis(text, end, *, miles=False):
    """Match existing forward denominator forms, preserving original offsets.

    Numeric validity belongs to the caller. Consume malformed explicit tokens
    too, so a bad denominator cannot silently become a denominator-free reward.
    Mileage labels are accepted only for an already recognized miles quantity.
    """
    numeric=r'(?:от\s+)?[−+-]?\d[\w., \t\u00a0\u202f–—−-]*?'
    unit=r'(?:₽|руб\w*\.?|RUB|(?:бонусн\w*\s+)?балл\w*|бонус(?:ов|а)?|дней|день|дня|месяц\w*)'
    amount=rf'(?P<basis>{numeric})\s*(?P<unit>{unit})(?=\W|$)'
    label=(r'(?:\s+S7\b(?:\s+Airlines)?(?=\s+(?:за|в)\b))?' if miles else '')
    brand=r'(?:«Аэрофлот\s+Бонус»\s+)?' if miles else ''
    return re.match(label+r'\s+(?:(?:начисля\w+\s+)?'+brand
                    +r'за\s+(?:кажды[еий]\s+)?(?:потраченн\w+\s+)?'+amount
                    +r'|(?P<month>в\s+месяц)\b|(?P<day>за\s+каждые\s+сутки)\b)',
                    text[end:],re.I)


def mileage_formula_end(text, end):
    """Extend a miles quantity through its forward denominator, not its predicate."""
    tail=forward_reward_basis(text,end,miles=True)
    return end+tail.end() if tail else end


def reward_role(text, start, end, *, amounts=()):
    """Action/reference owned by a literal points or miles quantity."""
    return _owned_role(text, start, end, amounts=amounts)


def benefit_phrase_end(text, end):
    """Complete a short nonnumeric marker's plain noun phrase, before its action."""
    for _ in range(3):
        word=re.match(r'\s+(?P<word>[^\W\d_]+)\b',text[end:])
        if not word:break
        token=word['word']
        # Never cross an action, polarity, condition or sibling connector to
        # borrow a later statement's denial. The shared grammar owns predicates.
        if (_BENEFIT_ACTION.fullmatch(token) or re.fullmatch(_DENIAL,token,re.I)
                or re.fullmatch(_MODIFIERS,token+' ',re.I)
                or re.fullmatch(r'и|или|а|но|зато|однако|если|когда|на|для|при|за|'
                                r'с|со|в|во|от|до|по|после|кроме',token,re.I)):
            break
        end+=word.end()
    return end


def benefit_phrase_spans(text, start, end):
    """Plain nonnumeric components sharing a potential coordinated predicate."""
    gifts=gift_spans(text)
    def component_end(pos):
        pos=benefit_phrase_end(text,pos)
        for marker in gifts:
            if pos<=marker.start() and re.fullmatch(r'\s*',text[pos:marker.start()]):
                return marker.end()
        return pos
    spans=[(start,component_end(end))]
    for _ in range(2):
        end=spans[-1][1]
        connector=re.match(r'\s+(?:и|или)(?=\s)',text[end:],re.I)
        if not connector:break
        after=end+connector.end()
        following=component_end(after)
        if following==after:break
        start=after+len(re.match(r'\s*',text[after:])[0])
        spans.append((start,following))
    return spans


def benefit_restriction_follows(text, end):
    """A negative restriction predicate at this marker, with shared modifiers."""
    return bool(_RESTRICTION.match(text,end))


def benefit_exclusion_spans(text):
    """Relative clauses describing excluded products, not offered benefits."""
    for predicate in _RESTRICTION.finditer(text):
        tail=predicate.end()
        relative=re.match(r'\s+(?:на|для|при|за)\s+[^,;.!?\n]+,\s*'
                          r'(?:(?:на|для|с|по|в|при|за)\s+)?котор\w*\b',text[tail:],re.I)
        if not relative:continue
        start=tail+relative.end()
        # A new comma/clause closes this relative clause. Decimal punctuation is
        # part of a quoted quantity and must not turn its discount into a live offer.
        boundary=re.search(_BOUNDARY+r'|\bа\b|,(?!\d)',text[start:],re.I)
        yield start,start+boundary.start() if boundary else len(text)


def benefit_denied(text, start, end, *, amounts=(), gift=False):
    """An explicit owned denial, preserving product/cash-equivalent exclusions."""
    if any(left<=start and end<=right for left,right in benefit_exclusion_spans(text)):
        return True
    if not re.search(r'\d',text[start:end]):
        components=benefit_phrase_spans(text,start,end)
        end=components[0][1]
        amounts=sorted(set(list(amounts)+components))
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
