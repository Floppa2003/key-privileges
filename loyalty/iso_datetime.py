"""ISO datetime parsing without normalization of invalid offset components."""
import re
from datetime import datetime


_OFFSET = re.compile(
    r'[+-]([0-9]{2})(?::?([0-9]{2}))?(?::?([0-9]{2}))?(?:[.,][0-9]+)?\Z')


def parse_iso_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    # The standard parser normalizes offsets such as +03:60 and +030060.
    # Inspect an actual offset only; date-only endings are not timezones.
    if parsed.tzinfo is not None:
        offset = _OFFSET.search(value)
        if offset and any(component is not None and int(component) >= limit
                          for component, limit in zip(offset.groups(), (24, 60, 60))):
            raise ValueError('Invalid ISO timezone offset component')
    return parsed
