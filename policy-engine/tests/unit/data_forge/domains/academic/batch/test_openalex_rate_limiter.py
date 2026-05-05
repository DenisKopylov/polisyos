from __future__ import annotations

import asyncio
import time

from polisyos.data_forge.domains.academic.openalex.rate_limiter import OpenAlexRateLimiter


def test_openalex_rate_limiter_respects_rps_budget() -> None:
    limiter = OpenAlexRateLimiter(max_rps=2, max_concurrent=1)

    async def _run() -> float:
        start = time.monotonic()
        await limiter.acquire()
        await limiter.acquire()
        await limiter.acquire()
        return time.monotonic() - start

    elapsed = asyncio.run(_run())
    # Third request should spill over into the next one-second window.
    assert elapsed >= 0.9


def test_openalex_rate_limiter_backoff_on_429() -> None:
    limiter = OpenAlexRateLimiter(max_rps=10, max_concurrent=1)

    async def _run() -> float:
        await limiter.report_429(seconds=0.2)
        start = time.monotonic()
        await limiter.acquire()
        return time.monotonic() - start

    elapsed = asyncio.run(_run())
    assert elapsed >= 0.18
