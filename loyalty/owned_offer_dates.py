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


def promomiles_period(body):
    """A complete card label shares its stated month/year, never observation time."""
    match = re.fullmatch(
        r'Период\s+проведения\s+акции:\s*с\s+(\d{1,2})'
        r'(?:\s+(' + '|'.join(MONTHS) + r'))?\s+по\s+(\d{1,2})\s+('
        + '|'.join(MONTHS) + r')\s+(\d{4})\s+года', body, re.I)
    if not match:
        return None, None
    start = date(int(match[5]), MONTHS[(match[2] or match[4]).casefold()], int(match[1])).isoformat()
    end = date(int(match[5]), MONTHS[match[4].casefold()], int(match[3])).isoformat()
    return (start, end) if start <= end else (None, None)


def labelled_numeric_campaign_period(body):
    """An unscoped full campaign label; acquisition and crediting labels differ."""
    full = r'(\d{2}\.\d{2}\.\d{4})(?!\d|\.\d|-\d)'
    matches = re.finditer(
        r'(?:^|\n)\s*(?:Срок|Период)\s+проведения\s+акции\s*:\s*(?:[сc]\s+)?'
        + full + r'(?:\s*г\.?)?\s*(?:[-–—]|по|до)\s*' + full, body, re.I)
    periods = {(calendar_date(m[1]), calendar_date(m[2])) for m in matches}
    if len(periods) != 1:
        return None, None
    start, end = next(iter(periods))
    return (start, end) if start <= end else (None, None)


def complete_native_document(details, body, parent_source):
    """Require the whole native document and the exact retained page text."""
    from document_text import page_text, sha
    from normalized import text
    pages = details.get('pages', [])
    return not (details.get('parent_source') != parent_source
            or details.get('live_document_text') is not True
            or details.get('document_part') != {'number': 1, 'total': 1}
            or details.get('document_errors') != [] or details.get('ocr_pages') != 0
            or not pages or len(pages) != details.get('page_count')
            or any(p.get('method') != 'native_pdf_text' or p.get('text_offset', 0) != 0
                   or p.get('sha256') != sha(p.get('text', '').encode()) for p in pages)
            or [p.get('number') for p in pages] != list(range(1, len(pages) + 1))
            or body != text(page_text(pages), markup=False))


def vtb_document_period(details, body):
    """A complete native campaign document, not the parent card's base terms."""
    if (not complete_native_document(details, body,
            'https://www.vtb.ru/privilegia/karty/debetovye/privilegiya-aeroflot/')
            or not re.match(r'^Правила\s+проведения\s+(?:специальной\s+)?акции\b',
                            details['pages'][0]['text'].lstrip(), re.I)):
        return None, None
    return labelled_numeric_campaign_period(body)


def utair_merch_document_end(details, body):
    """The two published merch coupons must each state the same expiry.

    The document's damaged issue-period start is not repaired or assigned to
    the friends' discount. Both explicitly owned redemption ends are intact.
    """
    if (not complete_native_document(details, body, 'https://media.utair.ru/status')
            or not re.match(r'^Персональная\s+скидка\s+на\s+мерч\s+Utair(?:\s|$)',
                            details['pages'][0]['text'].lstrip())):
        return None
    owners = list(re.finditer(r'^Условия применения промокода ([^\n]+):\s*$', body, re.M))
    if [m[1] for m in owners] != ['участниками уровня Platinum', 'друзьями участника уровня Platinum']:
        return None
    ends = []
    for index, owner in enumerate(owners):
        stop = owners[index + 1].start() if index + 1 < len(owners) else len(body)
        dates = {calendar_date(m[1]) for m in re.finditer(
            r'\bсрок\s+действия\s+промокода\s+до\s+(' + FULL_DATE + r')(?![\d.-])',
            body[owner.end():stop], re.I)}
        if len(dates) != 1:
            return None
        ends.extend(dates)
    return ends[0] if len(set(ends)) == 1 else None


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
    """Recover owned dates, including selection within an explicit period list."""
    if raw['origin'] != 'parser_offers' or raw['kind'] in ('raw_page', 'source_observation'):
        return
    details = raw.get('details', {})
    start = end = None
    if (raw.get('program') == 'РЖД Бонус' and raw.get('kind') == 'partner_offer'
            and raw.get('source_url') == 'https://taivashotel.ru/akcii_rzdbonus'
            and raw.get('partner') == 'Taivas' and raw.get('source_status') == 'published'
            and raw.get('link_kind') == 'detail_page'
            and raw.get('benefit') == raw.get('conditions')
            and details.get('source_scope') == 'reviewed_partner_page_not_program_catalog'
            and details.get('partner_identity_origin') == 'reviewed_exact_partner_owned_url'):
        from partner_pages import shared_year_periods, explicit_period
        try:
            periods, _ = shared_year_periods(raw.get('conditions', ''))
            # The old collector retained the first complete interval. Replace
            # only that source-owned selection, never an unrelated conflict.
            if len(periods) > 1 and (validity['from'], validity['until']) in [*periods, (None, None)]:
                start, end, _ = explicit_period(raw['conditions'], 'shared_year_dmy', validity['as_of'])
                validity.update({'from': start, 'until': end})
        except ValueError:
            pass
        return
    block = details.get('public_coral_block')
    if (block and raw.get('program') in ('CoralBonus — Клуб', 'CoralBonus — Акции')
            and raw.get('conditions') == block.get('body')):
        from coral_catalog import explicit_period
        start, end = explicit_period(block['body'])
    elif (raw.get('program') == 'Аэрофлот Бонус — Promo Miles'
          and raw.get('kind') == 'campaign' and raw.get('link_kind') == 'catalog_link'
          and raw.get('source_url') == 'https://promomiles.aeroflot.ru/'
          and re.fullmatch(r'https://promomiles\.aeroflot\.ru/act/[A-Za-z0-9_-]+',
                           details.get('detail_url', ''))):
        start, end = promomiles_period(raw.get('conditions', ''))
    elif (raw.get('program') == 'РЖД Бонус'
          and details.get('retrieval_method') == 'google_import_public_text_v1'):
        from rzd_import_catalog import source_fields, explicit_period, ROOT
        observation = details.get('import_observation')
        try:
            title, body, partner, benefit = source_fields(observation)
            if (raw.get('title') == title and raw.get('conditions') == body
                    and raw.get('benefit') == benefit and raw.get('partner') == partner
                    and raw.get('source_url') == observation['url']
                    and raw.get('link_kind') == 'detail_page'
                    and raw.get('source_status') == 'public_google_import_text'
                    and details.get('catalogue_root') == ROOT
                    and all(details.get(k) is False for k in
                            ('account_used', 'coupon_issued', 'origin_response_bytes_retained',
                             'origin_cache_age_verified', 'linked_terms_read', 'full_eligibility_verified'))):
                start, end = explicit_period(observation)
        except (ValueError, KeyError, TypeError):
            return
    elif (raw.get('kind') == 'program_rules' and raw.get('program') == 'Utair Status'
          and raw.get('source_status') == 'public_rules_text'
          and urlsplit(raw.get('source_url') or '').hostname in ('ut0.ru', 'media.utair.ru')):
        end = utair_merch_document_end(details, raw.get('conditions', ''))
    elif (raw.get('kind') == 'program_rules' and raw.get('program') == 'Аэрофлот Бонус'
          and raw.get('source_status') == 'public_rules_text'
          and urlsplit(raw.get('source_url') or '').hostname == 'www.vtb.ru'
          and urlsplit(raw.get('source_url') or '').path.lower().endswith('.pdf')):
        start, end = vtb_document_period(details, raw.get('conditions', ''))
    elif (raw.get('kind') == 'program_rules'
          and raw.get('program') == 'ЕКП — связанные публичные условия'
          and details.get('retrieval_method') == 'ekp_source_linked_rules_v1'
          and raw.get('source_status') == 'public_linked_rules_text'
          and raw.get('source_url') == 'https://vamprivet.ru/supreme-restaurants'
          and raw.get('conditions') == details.get('public_rule_text')
          and all(details.get(k) is False for k in
                  ('source_account_used', 'eligibility_verified', 'recursive_links_read'))):
        parents = details.get('parent_references', [])
        if parents and all(p.get('source_url') == 'https://ekp.spb.ru/api/portal/loyalty/partners'
                           and p.get('original_link') == raw['source_url'] for p in parents):
            start, end = labelled_numeric_campaign_period(raw['conditions'])
    elif (raw.get('program') == 'Единая карта петербуржца'
          and details.get('method') == 'anonymous_source_catalogue_api'):
        from ekp_catalog import retained_row, explicit_end
        row = retained_row(raw)
        if row is not None:
            try:
                end = explicit_end(row)
            except ValueError:
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
