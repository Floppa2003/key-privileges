"""Leave time to return completed records before the enclosing source is cancelled."""
from __future__ import annotations
import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar('T')


async def within_source_budget(client, operation: Callable[[], Awaitable[T]]) -> T:
    """Bound only this read; caller owns and retains previously validated records.

    Five seconds are reserved for source validation and browser-context cleanup.
    A leaf TimeoutError is not confused with expiration of the overall budget.
    The factory prevents creating an unawaited coroutine when time is already up.
    """
    deadline = getattr(client, 'deadline', float('inf'))
    if deadline == float('inf'):
        return await operation()
    remaining = deadline - time.monotonic() - 5
    if remaining <= 0:
        raise RuntimeError('source_time_budget_reached')
    timeout = asyncio.timeout(remaining)
    try:
        async with timeout:
            return await operation()
    except TimeoutError as exc:
        if timeout.expired():
            raise RuntimeError('source_time_budget_reached') from exc
        raise


def stops_catalog(exc: Exception) -> bool:
    """Do not continue sending new card requests after a rate limit or deadline."""
    return isinstance(exc, RuntimeError) and str(exc) in (
        'source_time_budget_reached', 'http_429')
