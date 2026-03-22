"""Async Gonka/OpenAI-compatible client primitives for Lex SPO extraction."""

from __future__ import annotations

import asyncio
import random
import time
from collections import deque
from typing import Any

import aiohttp

from polisyos.common.logger import get_logger
from polisyos.lex.batch.spo_utils import _is_json_mode_invalid_request

logger = get_logger(__name__)
_MAX_RETRY_AFTER_SECONDS = 30.0


def _retry_delay_seconds(*, attempt: int, retry_after: str | None) -> float:
    """Compute retry delay honoring Retry-After header when present."""
    if retry_after:
        try:
            parsed = float(retry_after.strip())
            if parsed > 0:
                return min(parsed, _MAX_RETRY_AFTER_SECONDS) * random.uniform(0.85, 1.2)
        except ValueError:
            pass
    return min(2 ** (attempt - 1) + 0.5, _MAX_RETRY_AFTER_SECONDS) * random.uniform(0.85, 1.25)


class _SlidingWindowLimiter:
    """Async sliding-window rate limiter with optional jitter and 429 cooldown."""

    __slots__ = ("_max", "_window", "_lock", "_timestamps", "_backoff_until", "_jitter_ratio")

    def __init__(self, max_requests: int, window: float = 1.0, *, jitter_ratio: float = 0.0) -> None:
        self._max = max(1, int(max_requests))
        self._window = max(0.01, float(window))
        self._lock = asyncio.Lock()
        self._timestamps: deque[float] = deque()
        self._backoff_until = 0.0
        self._jitter_ratio = max(0.0, float(jitter_ratio))

    async def acquire(self) -> float:
        waited = 0.0
        while True:
            async with self._lock:
                now = time.monotonic()
                if now < self._backoff_until:
                    wait = self._backoff_until - now
                else:
                    cutoff = now - self._window
                    while self._timestamps and self._timestamps[0] <= cutoff:
                        self._timestamps.popleft()
                    if len(self._timestamps) < self._max:
                        self._timestamps.append(time.monotonic())
                        return waited
                    wait = self._timestamps[0] + self._window - now
            if self._jitter_ratio > 0.0 and wait > 0.05:
                wait *= 1.0 + random.uniform(-self._jitter_ratio, self._jitter_ratio)
            started = time.monotonic()
            await asyncio.sleep(max(0.01, wait))
            waited += time.monotonic() - started

    async def penalise(self, penalty_seconds: float = 5.0) -> None:
        async with self._lock:
            future = time.monotonic() + penalty_seconds - self._window
            self._backoff_until = max(self._backoff_until, time.monotonic() + max(0.1, penalty_seconds))
            for _ in range(self._max):
                self._timestamps.append(future)


class GonkaClient:
    """Async OpenAI-compatible chat completion client with rate limiting."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        disable_json_mode: bool = False,
        max_concurrent: int = 50,
        rate_limit_rps: float = 100.0,
        temperature: float = 0.1,
        max_retries: int = 7,
        shared_limiter: _SlidingWindowLimiter | None = None,
        circuit_failures: int = 3,
        circuit_reset_seconds: float = 12.0,
    ) -> None:
        self._api_key = api_key
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._model = model
        self._temperature = temperature
        self._max_retries = max_retries
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._shared_limiter = shared_limiter
        self._circuit_failures = max(1, int(circuit_failures))
        self._circuit_reset_seconds = max(1.0, float(circuit_reset_seconds))
        self._consecutive_failures = 0
        self._circuit_open_until = 0.0
        self._limiter = _SlidingWindowLimiter(
            max_requests=1,
            window=(1.0 / max(0.001, float(rate_limit_rps))),
        )
        self._session: aiohttp.ClientSession | None = None
        self._json_mode_disabled = disable_json_mode
        if disable_json_mode:
            logger.info("Gonka JSON-mode disabled by configuration; sending plain chat completions.")

    @property
    def model_id(self) -> str:
        return self._model

    @property
    def json_mode_disabled(self) -> bool:
        return self._json_mode_disabled

    def disable_json_mode(self) -> None:
        self._json_mode_disabled = True

    def set_cache(self, cache: object | None) -> None:
        self._cache = cache  # type: ignore[attr-defined]

    def is_available(self) -> bool:
        return time.monotonic() >= self._circuit_open_until

    def backoff_until(self) -> float:
        return self._circuit_open_until

    def _record_success(self) -> None:
        self._consecutive_failures = 0
        self._circuit_open_until = 0.0

    def _record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures < self._circuit_failures:
            return
        jitter = random.uniform(0.85, 1.25)
        self._circuit_open_until = max(
            self._circuit_open_until,
            time.monotonic() + (self._circuit_reset_seconds * jitter),
        )

    async def __aenter__(self) -> "GonkaClient":
        self._session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=aiohttp.ClientTimeout(total=180),
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        response_format: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        assert self._session is not None, "Use 'async with GonkaClient(...)'"

        payload_base: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
        }

        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            if self._shared_limiter is not None:
                await self._shared_limiter.acquire()
            await self._limiter.acquire()
            async with self._semaphore:
                payload = dict(payload_base)
                if response_format and not self._json_mode_disabled:
                    payload["response_format"] = response_format
                try:
                    async with self._session.post(self._url, json=payload) as resp:
                        if resp.status == 200:
                            self._record_success()
                            return await resp.json()

                        body = await resp.text()
                        if (
                            "response_format" in payload
                            and _is_json_mode_invalid_request(resp.status, body)
                        ):
                            if not self._json_mode_disabled:
                                logger.warning(
                                    "Gonka 400 invalid_request with response_format; "
                                    "retrying without JSON-mode for subsequent requests."
                                )
                            self.disable_json_mode()
                            payload.pop("response_format", None)
                            continue

                        if resp.status < 500 and resp.status not in (429,):
                            logger.warning("Gonka {} (non-retryable): {}", resp.status, body[:200])
                            raise RuntimeError(
                                f"Gonka non-retryable error: HTTP {resp.status}: {body[:500]}"
                            )

                        delay = _retry_delay_seconds(
                            attempt=attempt,
                            retry_after=resp.headers.get("Retry-After"),
                        )
                        if resp.status == 429:
                            self._record_failure()
                            await self._limiter.penalise(delay)
                            if self._shared_limiter is not None:
                                await self._shared_limiter.penalise(min(delay, _MAX_RETRY_AFTER_SECONDS))
                        elif resp.status >= 500:
                            self._record_failure()

                        logger.warning(
                            "Gonka {} (attempt {}/{}), retry in {:.1f}s: {}",
                            resp.status,
                            attempt,
                            self._max_retries,
                            delay,
                            body[:200],
                        )
                        last_error = RuntimeError(
                            f"Gonka retryable HTTP {resp.status}: {body[:200]}"
                        )
                        await asyncio.sleep(delay)
                        continue

                except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                    exc_str = str(exc)
                    if "413" in exc_str:
                        logger.warning("Gonka client error (non-retryable): {}", exc)
                        raise RuntimeError(f"Gonka non-retryable error: {exc}") from exc

                    last_error = exc
                    self._record_failure()
                    delay = min(2 ** (attempt - 1) + 0.5, 30.0)
                    logger.warning(
                        "Gonka network error (attempt {}/{}), retry in {:.1f}s: {}",
                        attempt,
                        self._max_retries,
                        delay,
                        exc,
                    )
                    await asyncio.sleep(delay)

        raise RuntimeError(f"Gonka request failed after {self._max_retries} attempts") from last_error


class GonkaClientPool:
    """Least-loaded pool of Gonka clients, one per API key."""

    def __init__(
        self,
        *,
        api_keys: list[str],
        base_url: str,
        model: str,
        disable_json_mode: bool = False,
        max_concurrent: int = 50,
        rate_limit_rps: float = 100.0,
        temperature: float = 0.1,
        max_retries: int = 7,
    ) -> None:
        cleaned = [str(key).strip() for key in api_keys if str(key).strip()]
        if not cleaned:
            raise ValueError("GonkaClientPool requires at least one API key")
        total_rps = max(0.001, float(rate_limit_rps) * max(1, len(cleaned)))
        self._shared_limiter = _SlidingWindowLimiter(
            max_requests=1,
            window=(1.0 / total_rps),
            jitter_ratio=0.12,
        )
        self._clients = [
            GonkaClient(
                api_key=key,
                base_url=base_url,
                model=model,
                disable_json_mode=disable_json_mode,
                max_concurrent=max_concurrent,
                rate_limit_rps=rate_limit_rps,
                temperature=temperature,
                max_retries=max_retries,
                shared_limiter=self._shared_limiter,
            )
            for key in cleaned
        ]
        self._in_flight = [0 for _ in self._clients]
        self._selection_lock = asyncio.Lock()
        self._json_mode_disabled = disable_json_mode
        self._rr_cursor = 0

    @property
    def model_id(self) -> str:
        return self._clients[0].model_id

    @property
    def key_count(self) -> int:
        return len(self._clients)

    def set_cache(self, cache: object | None) -> None:
        for client in self._clients:
            client.set_cache(cache)

    def disable_json_mode(self) -> None:
        if self._json_mode_disabled:
            return
        self._json_mode_disabled = True
        for client in self._clients:
            client.disable_json_mode()

    async def __aenter__(self) -> "GonkaClientPool":
        for client in self._clients:
            await client.__aenter__()
        return self

    async def __aexit__(self, *exc: object) -> None:
        for client in self._clients:
            await client.__aexit__(*exc)

    async def _acquire_client_index(self) -> int:
        while True:
            async with self._selection_lock:
                available = [i for i, client in enumerate(self._clients) if client.is_available()]
                if available:
                    min_load = min(self._in_flight[i] for i in available)
                    tied = [i for i in available if self._in_flight[i] == min_load]
                    tied.sort()
                    offset = self._rr_cursor % len(tied)
                    idx = tied[offset]
                    self._rr_cursor = (self._rr_cursor + 1) % max(1, len(self._clients))
                    self._in_flight[idx] += 1
                    return idx
                earliest = min((client.backoff_until() for client in self._clients), default=time.monotonic() + 0.25)
            wait_for = max(0.05, earliest - time.monotonic())
            await asyncio.sleep(wait_for * random.uniform(0.85, 1.2))

    async def _release_client_index(self, idx: int) -> None:
        async with self._selection_lock:
            self._in_flight[idx] = max(0, self._in_flight[idx] - 1)

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        response_format: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        idx = await self._acquire_client_index()
        try:
            effective_response_format = None if self._json_mode_disabled else response_format
            result = await self._clients[idx].chat_completion(
                messages,
                response_format=effective_response_format,
            )
            if self._clients[idx].json_mode_disabled:
                self.disable_json_mode()
            return result
        finally:
            await self._release_client_index(idx)


__all__ = [
    "GonkaClient",
    "GonkaClientPool",
    "_SlidingWindowLimiter",
    "_retry_delay_seconds",
]
