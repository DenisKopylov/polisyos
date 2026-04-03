"""Bridge async coroutines into synchronous entrypoints safely."""
from __future__ import annotations

import asyncio
import concurrent.futures
from typing import Awaitable, TypeVar

T = TypeVar("T")


def run_coro_sync(coro: Awaitable[T]) -> T:
    """Run a coroutine from sync code, safely handling active event loops."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()

    return asyncio.run(coro)
