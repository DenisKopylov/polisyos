"""OpenAlex async rate limiter with backoff support."""

from __future__ import annotations

import asyncio
import time
from collections import deque


class OpenAlexRateLimiter:
    """Polite-pool limiter for OpenAlex requests.

    Uses a 1-second sliding window and supports global backoff after 429.
    """

    def __init__(self, max_rps: int = 10, max_concurrent: int = 5) -> None:
        self._max_rps = max(1, int(max_rps))
        self._semaphore = asyncio.Semaphore(max(1, int(max_concurrent)))
        self._window: deque[float] = deque()
        self._lock = asyncio.Lock()
        self._backoff_until: float = 0.0

    @property
    def semaphore(self) -> asyncio.Semaphore:
        return self._semaphore

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()

                if now < self._backoff_until:
                    sleep_for = self._backoff_until - now
                else:
                    while self._window and self._window[0] <= now - 1.0:
                        self._window.popleft()
                    if len(self._window) < self._max_rps:
                        self._window.append(now)
                        return
                    sleep_for = max(0.01, 1.0 - (now - self._window[0]))

            await asyncio.sleep(sleep_for)

    async def report_429(self, seconds: float = 5.0) -> None:
        async with self._lock:
            self._backoff_until = max(self._backoff_until, time.monotonic() + max(0.1, seconds))
