"""Complete date labels read only inside an already owned offer or article."""
import re
from datetime import date, datetime
from urllib.parse import urlsplit
from partner_pages import MONTHS


FULL_DATE = r'(?:\d{2}\.\d{2}\.\d{4}|\d{1,2}\s+(?:' + '|'.join(MONTHS) + r')\s+\d{4})'
MIR_START_CONFLICT = 'source_start_conflicts_with_owned_offer'


def calendar_date(value):
    if '.' in value:
        return datetime.strptime(value, '%d.%m.%Y').date().isoformat()
    day, month, year = value.casefold().split()
    return date(int(year), MONTHS[month], int(day)).isoformat()


def mir_start_conflict(templates, start, end):
    """Only the encountered own-offer start disagreement with an agreed end.

    Mir also publishes different code acquisition and redemption ends. Those
    are not contradictory starts and must not be reconciled into one interval.
    Both retained template statements prove the conflict even after the fresh
    adapter has already withheld its structured start.
    """
    if not isinstance(templates, list):
        return False
    periods = set()
    for template in templates:
        if template.get('name') != 'period' or template.get('title') != 'Срок проведения':
            continue
        match = re.fullmatch(
            r'с\s+(\d{1,2})\s+(' + '|'.join(MONTHS) + r')(?:\s+(\d{4}))?\s+по\s+('
            + FULL_DATE + r')', template.get('text', ''), re.I)
        if not match:
            continue
        until = calendar_date(match[4])
        beginning = date(int(match[3] or until[:4]), MONTHS[match[2].casefold()], int(match[1])).isoformat()
        if beginning <= until:
            periods.add((beginning, until))
    if len(periods) != 1:
        return False
    beginning, until = next(iter(periods))
    if (start is not None and start != beginning) or end != until:
        return False
    for template in templates:
        if template.get('name') != 'disclamer':
            continue
        match = re.match(
            r'^Предложение\s+действует\s+с\s+(' + FULL_DATE + r')\s+г\.\s+по\s+('
            + FULL_DATE + r')\s+г\.(?=\s|$)', template.get('text', ''), re.I)
        if match:
            other_start, other_end = calendar_date(match[1]), calendar_date(match[2])
            if other_start != beginning and other_end == until and other_start <= other_end:
                return True
    return False


def retained_mir_start_conflict(raw):
    """Require the exact owned Mir templates behind the retained conditions."""
    source = urlsplit(raw.get('source_url') or '')
    if (raw.get('origin') != 'parser_offers' or raw.get('kind') != 'partner_offer'
            or raw.get('program') != 'Привет! / Мир / СБП'
            or raw.get('link_kind') != 'detail_page'
            or source.hostname != 'vamprivet.ru' or not source.path.startswith('/promo/')):
        return False
    templates = raw.get('details', {}).get('templates')
    if not isinstance(templates, list):
        return False
    conditions = '\n'.join((t.get('title', '') + '\n' + t['text']).strip()
                           for t in templates if t.get('text'))
    return (raw.get('conditions') == conditions
            and mir_start_conflict(templates, raw.get('valid_from'), raw.get('valid_until')))


def labelled_campaign_ends(body):
    """An unscoped, complete own-offer sentence; never a bare date or duration."""
    pattern = (r'(?:^|(?<=[.!?;])\s+|\n)\s*'
               r'((?:Срок\s+акции\s*:|Предложение\s+действует)\s*до\s+'
               r'(' + FULL_DATE + r')(?![\d.-])(?:\s+года)?'
               r'(?:\s+включительно)?)(?=[.!?;]|\s*$|\n)')
    return [(calendar_date(m[2]), m[1]) for m in re.finditer(pattern, body, re.I)]


def numbered_discount_end(benefit, conditions):
    """All numbered own discounts must state the same end, component by component.

    The short bare «Срок действия» label is licensed by its numbered discount
    block, not by an unrelated date elsewhere in the merchant description.
    """
    marker = r'(?<!\S)(\d+)\.\s+Скидка\b'
    own = list(re.finditer(marker, benefit, re.I))
    blocks = list(re.finditer(marker, conditions, re.I))
    numbers = [m[1] for m in own]
    if (len(numbers) < 2 or numbers != [str(i) for i in range(1, len(numbers) + 1)]
            or numbers != [m[1] for m in blocks]):
        return None
    ends = []
    for i, block in enumerate(blocks):
        stop = blocks[i + 1].start() if i + 1 < len(blocks) else len(conditions)
        clause = conditions[block.end():stop]
        dates = {calendar_date(m[1]) for m in re.finditer(
            r'\bСрок\s+действия\s+до\s+(' + FULL_DATE + r')(?![\d.-])\s+г\.', clause, re.I)}
        if len(dates) != 1:
            return None
        ends.extend(dates)
    return ends[0] if len(set(ends)) == 1 else None


def project_retained_validity(raw, validity):
    """Repair blank retained date cells from the same owned source text."""
    if raw['origin'] != 'parser_offers' or raw['kind'] in ('raw_page', 'source_observation'):
        return
    details = raw.get('details', {})
    start = end = None
    block = details.get('public_coral_block')
    if (block and raw.get('program') in ('CoralBonus — Клуб', 'CoralBonus — Акции')
            and raw.get('conditions') == block.get('body')):
        from coral_catalog import explicit_period
        start, end = explicit_period(block['body'])
    elif (raw.get('program') == 'Единая карта петербуржца'
          and details.get('method') == 'anonymous_source_catalogue_api'):
        from ekp_catalog import public_row, fields, explicit_end, sha, API, ROOT, REGION, query
        row = details.get('public_partner', {})
        try:
            if (public_row(row) == row and details.get('public_partner_sha256') == sha(row)
                    and details.get('api_url') == API and raw.get('source_url') == API
                    and details.get('protected_terms_retained') is False
                    and details.get('catalogue_root') == ROOT
                    and details.get('source_region_parameter') == REGION
                    and details.get('origin_http_status') == 200
                    and details.get('source_active') is row['active']
                    and details.get('request') == query(details.get('request', {}).get('pagination', {}).get('offset'))
                    and re.fullmatch(r'[a-f0-9]{64}', details.get('source_response_sha256', ''))
                    and details.get('public_detail_url') == ROOT+'tiles/'+row['id']+'?region='+REGION
                    and all(details.get(k) is False for k in
                            ('detail_url_individually_opened', 'linked_terms_read', 'user_eligibility_verified'))):
                f = fields(row)
                checks = {'partner': 'partner_name', 'title': 'title', 'kind': 'record_kind',
                          'benefit': 'benefit_text', 'conditions': 'conditions_text',
                          'activation': 'redemption_text', 'source_status': 'source_status'}
                if all(raw.get(k) == f[v] for k, v in checks.items()):
                    end = explicit_end(row)
        except (ValueError, KeyError, TypeError):
            return
    elif details.get('public_reward_source') == 'magnit_partners_public':
        from public_reward_projection import fields
        try:
            f = fields('magnit_partners_public', details['public_reward_evidence'])
            checks = {'program': 'program', 'partner': 'partner', 'title': 'title',
                      'source_url': 'url', 'benefit': 'benefit', 'conditions': 'conditions',
                      'activation': 'activation'}
            if (details.get('account_used') is False
                    and raw.get('kind') == f.get('kind', 'partner_offer')
                    and all(raw.get(k) == f[v] for k, v in checks.items())):
                start, end = f.get('valid_from'), f.get('valid_until')
        except (ValueError, KeyError, TypeError):
            return
    elif details.get('scope') == 'only_cards_in_current_public_partner_inventory':
        block = details.get('public_catalog_block', {})
        if raw.get('conditions') == block.get('body'):
            from hse_alumni import explicit_end
            end, _ = explicit_end(block['body'])
    elif (raw.get('kind') == 'program_rules'
          and details.get('scope') == 'published_article_not_complete_offer_catalogue'
          and raw.get('conditions') == '\n'.join(details.get('sections', []))):
        ends = {value for value, _ in labelled_campaign_ends(raw['conditions'])}
        if len(ends) == 1:
            end = next(iter(ends))
    elif (raw.get('program') == 'Уральские авиалинии — «Крылья»'
          and raw.get('kind') == 'partner_offer'):
        end = numbered_discount_end(raw.get('benefit', ''), raw.get('conditions', ''))
    # Existing structured dates remain authoritative. Only compatible missing
    # bounds can be repaired; do not combine two contradictory source periods.
    if any(old and new and old != new for old, new in ((validity['from'], start), (validity['until'], end))):
        return
    if start and not validity['from']:
        validity['from'] = start
    if end and not validity['until']:
        validity['until'] = end
