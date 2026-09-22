"""Narrow, auditable interpretation of Backit's date-labelled promotion panel."""
import re
from datetime import date

MONTHS = {name: i for i, name in enumerate(
    ('январь','февраль','март','апрель','май','июнь','июль','август','сентябрь','октябрь','ноябрь','декабрь'), 1)}
DATE = r'(\d{2})\.(\d{2})(?:\.(\d{4}))?'

def promotion_dates(period, page_title, observed_on):
    """Return current source period. Yearless dates require a current page month.

    This is a labelled contextual inference, not a claim that DD.MM includes a
    written year. Cross-year ambiguity and obsolete labels are withheld.
    """
    observed = date.fromisoformat(observed_on)
    title = re.search(r'\(('+'|'.join(MONTHS)+r')\s+(\d{4})\)\s*$', page_title, re.I)
    def calendar(parts):
        day, month, year = parts
        if year is None:
            if not title or (int(title[2]), MONTHS[title[1].casefold()]) != (observed.year, observed.month):
                raise ValueError('dated_promotional_rate_requires_current_confirmation')
            year = title[2]
        return date(int(year), int(month), int(day))
    text = re.sub(r'\s+', ' ', period).strip()
    until = re.fullmatch(r'(?:Повышение\s+)?до\s+'+DATE, text, re.I)
    interval = re.fullmatch(r'(?:Повышение\s+)?(?:с\s+)?'+DATE+r'\s*(?:по|[-–—])\s*'+DATE, text, re.I)
    if until:
        start, end = None, calendar(until.groups())
    elif interval:
        start, end = calendar(interval.groups()[:3]), calendar(interval.groups()[3:])
        if end < start or (end-start).days > 93:
            raise ValueError('dated_promotional_rate_requires_current_confirmation')
    else:
        raise ValueError('dated_promotional_rate_requires_current_confirmation')
    if observed > end:
        raise ValueError('promotional_period_expired')
    if start and observed < start:
        raise ValueError('promotional_period_not_started')
    return start.isoformat() if start else None, end.isoformat()
