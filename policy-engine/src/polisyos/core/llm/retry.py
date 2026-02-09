from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


async def retry_async(
    operation: Callable[[], Awaitable[T]],
    *,
    attempts: int,
    delay_seconds: float = 0.0,
    on_error: Callable[[Exception, int, int], None] | None = None,
) -> T:
    if attempts <= 0:
        raise ValueError("attempts must be >= 1")

    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await operation()
        except Exception as exc:
            last_error = exc
            if on_error is not None:
                on_error(exc, attempt, attempts)
            if attempt >= attempts:
                break
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds)

    if last_error is None:
        raise RuntimeError("retry_async exhausted attempts without captured exception")
    raise last_error
