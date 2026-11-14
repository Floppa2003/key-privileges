"""Literal percentage rewards and spending permissions, with local ownership."""
import re

from reward_context import benefit_denied, reward_role
from reward_nominals import bonus_price_band


_UNIT = re.compile(r'\b(?P<points>балл(?:ами|ах|ов|ы|а)?|бонус(?:ами|ах|ов|ы))\b'
                   r'|\b(?P<miles>мил(?:ями|ям|ях|и|ь))\b'
                   r'|\b(?P<cash>рублями|деньгами)\b'
                   r'|\b(?P<coins>монет(?:ами|ах|ы)?)\b'
                   r'|\b(?P<shpaly>шпалы|шпалами)\b'
                   r'|\b(?P<generic>бонус)\b', re.I)
_BOUNDARY = r'[.!?](?:\s|$)|[;\n]'
_SPEND = r'спис\w*|спиш\w*|оплат(?:[аыуе]|ить|ите|ы|ой)|оплач(?:ива\w*|у)|компенсир\w*|использ(?:ов\w*|уйте)|погас\w*|расход\w*'
_ACTION = re.compile(r'\b(?:(?P<spend>'+_SPEND+r')|(?P<earn>получ\w*|начисл\w*|верн\w*|возвращ\w*|копите|накаплива\w*))\b',re.I)
_BLOCK = re.compile(r'\b(?:предоплат\w*|НДС|налог\w*|комисси\w*|штраф\w*)\b', re.I)


def percentage_rewards(clause, spans, *, heading_context=''):
    """Return only percent occurrences with a literal reward owner and unit.

    A singular marketing bonus or account balance does not establish a cash or
    points unit. A literal spending action owns the same percentage locally.
    """
    result = {}
    previous = None
    for index, span in enumerate(spans):
        start, end = span['start'], span['end']
        left = max((m.end() for m in re.finditer(_BOUNDARY, clause[:start])), default=0)
        stop = re.search(_BOUNDARY, clause[end:])
        right = end + stop.start() if stop else len(clause)
        if index + 1 < len(spans):right = min(right, spans[index + 1]['start'])
        prefix, suffix = clause[left:start], clause[end:right]
        if _BLOCK.search(prefix[-55:]) or re.match(r'\s*'+_BLOCK.pattern, suffix, re.I):
            previous = None
            continue
        owner = None
        owner_end = end
        # An alternative points/miles label does not establish one currency.
        # Source-owned bank projectors retain that combined native programme.
        if re.search(r'балл\w*\s*/\s*(?:бонусн\w*\s+)?мил\w*[^%]*$',prefix,re.I):
            previous = None
            continue
        post = _UNIT.search(suffix)
        post_bridge = suffix[:post.start()] if post else ''
        direct_post = bool(post and re.fullmatch(r'\s*(?:\(\s*)?(?:(?:дополнительн\w*|премиальн\w*|больше|к)\s+){0,2}', post_bridge,re.I))
        if direct_post:
            owner,owner_end = post.lastgroup,end+post.end()
        pre = list(_UNIT.finditer(prefix))
        if owner is None and pre:
            last = pre[-1]
            bridge = prefix[last.end():]
            program_name = (last.lastgroup=='generic' and
                            (re.search(r'\b(?:РЖД|Аэрофлот)\s*$',prefix[:last.start()],re.I)
                             or re.search(r'\b(?:программ[аыуе]|названи\w*)\b',prefix[:last.start()][-35:],re.I)))
            if (len(bridge) <= 110 and not program_name
                    and not re.search(r'\d|%|[«»"+]|скидк|к[еэ]шб[еэ]к',bridge,re.I)):
                owner = last.lastgroup
        if (owner is None and post and post.start() <= 120
                and re.fullmatch(r'(?:баллами|бонусами|милями|рублями|деньгами|монетами)',post[0],re.I)
                and not re.search(r'\d|скидк|к[еэ]шб[еэ]к|получ|начисл|спис|Дополнительно|не\s|[,+;!?]',post_bridge,re.I)
                and re.search(r'сумм|стоимост|покупк|номинал|договор',post_bridge,re.I)):
            owner,owner_end = post.lastgroup,end+post.end()
        if owner is None and re.match(r'\s+на\s+баланс\b',suffix,re.I) and re.search(r'начисл',suffix,re.I):
            owner = 'generic'
        if (owner is None and re.search(r'\b(?:вернуть|возвращается|возвращать)\s*$',prefix,re.I)
                and re.match(r'\s+от\s+(?:суммы(?:\s+покупки)?\s+при\s+оплате|стоимости\s+поездки)\b',suffix,re.I)):
            owner = 'cash'
        if owner is None and bonus_price_band(clause[:start]):owner='points'
        if (owner is None and re.match(r'\s*Компенсируйте\s+ими\b',prefix,re.I)
                and re.search(r'\bБонусы\s+поступят\s+на\s+баланс[^.!?]+\.\s*$',clause[:left],re.I)):
            owner='points'
        heading_owner = None
        if re.search(r'балл|бонус|статусное начисление|повышенное начисление',heading_context,re.I):heading_owner='points'
        elif re.search(r'мил[ьяиюе]',heading_context,re.I):heading_owner='miles'
        elif re.search(r'к[еэ]шб[еэ]к',heading_context,re.I):heading_owner='cash'
        if owner is None and heading_owner and not re.search(r'скидк|к[еэ]шб[еэ]к',prefix+suffix,re.I):
            owner = heading_owner
        if owner is None and previous and previous['right'] > start:
            bridge = clause[previous['end']:start]
            if not re.search(r'\b(?:скидк\w*|к[еэ]шб[еэ]к\w*|НДС|налог\w*|комисси\w*)\b',bridge,re.I):owner=previous['owner']
        if owner is None:
            previous = None
            continue
        amounts=[(s['start'],s['end']) for s in spans]
        role=reward_role(clause,start,owner_end,amounts=amounts)
        if benefit_denied(clause,start,owner_end,amounts=amounts):
            previous = None
            continue
        actions=list(_ACTION.finditer(prefix))
        postfix_actions=list(_ACTION.finditer(post_bridge)) if owner_end>end else []
        spending=(postfix_actions[-1].lastgroup=='spend' if postfix_actions else
                  actions[-1].lastgroup=='spend' if actions else role=='spend')
        if role=='denied' or role=='reference' and not spending and not bonus_price_band(clause[:start]):
            previous = None
            continue
        if (re.match(r'\s+на\s+баланс\b',suffix,re.I)
                and re.search(r'\bне\s+начисл\w*',suffix,re.I)):
            previous = None
            continue
        if (not spending and re.search(r'\b(?:максимальн\w*|максимум|минимальн\w*|не\s+(?:может\s+)?превыш\w*)\b',prefix,re.I)):
            previous = None
            continue
        if spending and owner not in ('points','miles','coins','shpaly'):
            previous = None
            continue
        kind=('redeem_rewards' if spending else
              {'points':'earn_points','miles':'earn_miles','cash':'cashback',
               'coins':'earn_rewards','shpaly':'earn_rewards','generic':'earn_rewards'}[owner])
        item={'kind':kind,'reward_unit':{'points':'points','miles':'miles','coins':'coins','shpaly':'шпалы'}.get(owner)}
        incremental=(owner in ('points','miles') and not spending and
                     (re.search(r'\bбольше\s+баллов|дополнительн\w*\s+(?:премиальн\w*\s+)?(?:баллов|миль)',suffix,re.I)
                      or re.search(r'\bдополнительно\s*$',prefix,re.I)
                      or re.search(r'статусное начисление|повышенное начисление|дополнительные баллы на уровнях',heading_context,re.I)))
        if incremental:item.update(basis_amount='100',basis_unit=owner,additional_reward=True)
        result[index]=item
        sentence_stop=re.search(_BOUNDARY,clause[end:])
        previous={'owner':owner,'end':end,'right':end+sentence_stop.start() if sentence_stop else len(clause)+1}
    return result
