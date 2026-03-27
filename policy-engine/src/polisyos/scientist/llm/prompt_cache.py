"""Prompt-level response cache for LLM calls."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import OrderedDict
from typing import Any, Protocol

from .gateway_client import GatewayLLMResponse


class PromptCacheProtocol(Protocol):
    """Protocol for prompt cache implementations."""

    def get(self, cache_key: str) -> GatewayLLMResponse | None: ...
    def put(self, cache_key: str, response: GatewayLLMResponse, ttl_s: float) -> None: ...


def compute_cache_key(
    *,
    system: str | None = None,
    user: str | None = None,
    model: str = "",
    tools: list[dict[str, Any]] | None = None,
    temperature: float | None = None,
    response_format: dict[str, Any] | None = None,
) -> str:
    """Compute a deterministic cache key from prompt parameters.

    The key is a SHA-256 hex digest of a canonical JSON representation
    of the input parameters.
    """
    canonical = json.dumps(
        {
            "system": system or "",
            "user": user or "",
            "model": model,
            "tools": tools or [],
            "temperature": temperature,
            "response_format": response_format,
        },
        sort_keys=True,
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class InMemoryPromptCache:
    """Thread-safe in-memory LRU prompt cache with TTL.

    Entries are evicted either when the cache exceeds ``maxsize`` (oldest
    first) or when their TTL expires.
    """

    def __init__(self, *, maxsize: int = 128, default_ttl_s: float = 300.0) -> None:
        if maxsize < 1:
            raise ValueError("maxsize must be >= 1")
        self._maxsize = maxsize
        self._default_ttl_s = max(default_ttl_s, 0.0)
        self._lock = threading.Lock()
        self._store: OrderedDict[str, tuple[GatewayLLMResponse, float]] = OrderedDict()

    def get(self, cache_key: str) -> GatewayLLMResponse | None:
        """Return cached response or ``None`` if miss/expired."""
        with self._lock:
            entry = self._store.get(cache_key)
            if entry is None:
                return None
            response, expires_at = entry
            if time.monotonic() > expires_at:
                del self._store[cache_key]
                return None
            # Move to end (most recently used)
            self._store.move_to_end(cache_key)
            return response

    def put(
        self,
        cache_key: str,
        response: GatewayLLMResponse,
        ttl_s: float | None = None,
    ) -> None:
        """Cache *response* under *cache_key* with optional TTL override."""
        effective_ttl = ttl_s if ttl_s is not None else self._default_ttl_s
        expires_at = time.monotonic() + effective_ttl
        with self._lock:
            if cache_key in self._store:
                self._store.move_to_end(cache_key)
            self._store[cache_key] = (response, expires_at)
            while len(self._store) > self._maxsize:
                self._store.popitem(last=False)

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._store)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


__all__ = [
    "PromptCacheProtocol",
    "InMemoryPromptCache",
    "compute_cache_key",
]
