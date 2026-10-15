"""Adapters for connector methods that produce asynchronous iterators."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable
from inspect import isawaitable


async def resolve_async_iterator[T](
    candidate: AsyncIterator[T] | Awaitable[AsyncIterator[T]],
) -> AsyncIterator[T]:
    """Resolve either an async generator or an awaitable async iterator."""
    if isawaitable(candidate):
        return await candidate
    return candidate
