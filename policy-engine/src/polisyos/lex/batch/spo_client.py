"""Async Gonka/OpenAI-compatible client primitives for Lex SPO extraction."""

from __future__ import annotations

import asyncio
import json
import math
import random
import time
from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiohttp

from polisyos.common.logger import get_logger
from polisyos.lex.batch.spo_utils import _is_json_mode_invalid_request

logger = get_logger(__name__)
_MAX_RETRY_AFTER_SECONDS = 30.0
_REQUEST_LANE_CONTEXT: ContextVar[tuple[str, float, float]] = ContextVar(
    "lex_spo_request_lane",
    default=("primary", 1.0, 1.0),
)


def _normalize_lane_settings(
    *,
    lane_name: str,
    rate_scale: float,
    concurrency_scale: float,
) -> tuple[str, float, float]:
    normalized_name = str(lane_name or "primary").strip() or "primary"
    normalized_rate_scale = min(1.0, max(0.05, float(rate_scale)))
    normalized_concurrency_scale = min(1.0, max(0.05, float(concurrency_scale)))
    return normalized_name, normalized_rate_scale, normalized_concurrency_scale


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
    """Async sliding-window rate limiter with warm-up ramp and adaptive 429 cooling."""

    __slots__ = (
        "_adaptive_enabled",
        "_adaptive_max_scale",
        "_adaptive_penalty_multiplier",
        "_adaptive_recovery_factor",
        "_adaptive_scale",
        "_backoff_until",
        "_created_at",
        "_jitter_ratio",
        "_lock",
        "_max",
        "_timestamps",
        "_warmup_seconds",
        "_warmup_start_scale",
        "_window",
    )

    def __init__(
        self,
        max_requests: int,
        window: float = 1.0,
        *,
        jitter_ratio: float = 0.0,
        warmup_seconds: float = 0.0,
        warmup_start_scale: float = 1.0,
        adaptive_enabled: bool = False,
        adaptive_recovery_factor: float = 0.97,
        adaptive_penalty_multiplier: float = 1.35,
        adaptive_max_scale: float = 8.0,
    ) -> None:
        self._max = max(1, int(max_requests))
        self._window = max(0.01, float(window))
        self._lock = asyncio.Lock()
        self._timestamps: deque[float] = deque()
        self._backoff_until = 0.0
        self._jitter_ratio = max(0.0, float(jitter_ratio))
        self._warmup_seconds = max(0.0, float(warmup_seconds))
        self._warmup_start_scale = max(1.0, float(warmup_start_scale))
        self._adaptive_enabled = bool(adaptive_enabled)
        self._adaptive_scale = 1.0
        self._adaptive_recovery_factor = min(1.0, max(0.5, float(adaptive_recovery_factor)))
        self._adaptive_penalty_multiplier = max(1.0, float(adaptive_penalty_multiplier))
        self._adaptive_max_scale = max(1.0, float(adaptive_max_scale))
        self._created_at = time.monotonic()

    def _warmup_scale(self, now: float) -> float:
        if self._warmup_seconds <= 0.0 or self._warmup_start_scale <= 1.0:
            return 1.0
        elapsed = max(0.0, now - self._created_at)
        if elapsed >= self._warmup_seconds:
            return 1.0
        remaining = 1.0 - (elapsed / self._warmup_seconds)
        return 1.0 + ((self._warmup_start_scale - 1.0) * remaining)

    def current_scale(self) -> float:
        now = time.monotonic()
        return max(self._warmup_scale(now), self._adaptive_scale)

    def current_effective_rps(self) -> float:
        return max(0.001, self._max / (self._window * self.current_scale()))

    async def acquire(self) -> float:
        waited = 0.0
        while True:
            async with self._lock:
                now = time.monotonic()
                effective_window = self._window * max(1.0, self.current_scale())
                if now < self._backoff_until:
                    wait = self._backoff_until - now
                else:
                    cutoff = now - effective_window
                    while self._timestamps and self._timestamps[0] <= cutoff:
                        self._timestamps.popleft()
                    if len(self._timestamps) < self._max:
                        self._timestamps.append(time.monotonic())
                        return waited
                    wait = self._timestamps[0] + effective_window - now
            if self._jitter_ratio > 0.0 and wait > 0.05:
                wait *= 1.0 + random.uniform(-self._jitter_ratio, self._jitter_ratio)
            started = time.monotonic()
            await asyncio.sleep(max(0.01, wait))
            waited += time.monotonic() - started

    async def penalise(self, penalty_seconds: float = 5.0) -> None:
        async with self._lock:
            future = time.monotonic() + penalty_seconds - self._window
            self._backoff_until = max(
                self._backoff_until, time.monotonic() + max(0.1, penalty_seconds)
            )
            for _ in range(self._max):
                self._timestamps.append(future)
            if self._adaptive_enabled:
                penalty_bump = 1.0 + (
                    min(_MAX_RETRY_AFTER_SECONDS, max(0.0, float(penalty_seconds))) / 6.0
                )
                self._adaptive_scale = min(
                    self._adaptive_max_scale,
                    max(self._adaptive_scale * self._adaptive_penalty_multiplier, penalty_bump),
                )

    def record_success(self) -> None:
        if not self._adaptive_enabled:
            return
        self._adaptive_scale = max(1.0, self._adaptive_scale * self._adaptive_recovery_factor)


class GonkaRequestError(RuntimeError):
    """Structured provider failure so higher layers can reason about retries."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool,
        error_class: str,
        http_status: int = 0,
        provider_key_index: int | None = None,
        retry_count: int = 0,
        limiter_wait_ms: float = 0.0,
        backoff_sleep_ms: float = 0.0,
    ) -> None:
        super().__init__(message)
        self.retryable = bool(retryable)
        self.error_class = str(error_class or "")
        self.http_status = int(http_status or 0)
        self.provider_key_index = provider_key_index
        self.retry_count = max(0, int(retry_count or 0))
        self.limiter_wait_ms = float(limiter_wait_ms or 0.0)
        self.backoff_sleep_ms = float(backoff_sleep_ms or 0.0)


@dataclass(slots=True)
class _AttemptOutcome:
    payload: dict[str, Any] | None = None
    retryable: bool = False
    error_class: str = ""
    error_message: str = ""
    http_status: int = 0
    retry_after: str | None = None
    disable_json_mode: bool = False
    provider_key_index: int | None = None
    latency_ms: float = 0.0
    raw_content: str = ""

    @property
    def ok(self) -> bool:
        return self.payload is not None


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _payload_summary(payload: dict[str, Any]) -> dict[str, Any]:
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    choices = payload.get("choices") if isinstance(payload.get("choices"), list) else []
    first = choices[0] if choices else {}
    message = first.get("message") if isinstance(first, dict) else {}
    raw_content = str(message.get("content") or "") if isinstance(message, dict) else ""
    finish_reason = str(first.get("finish_reason") or "") if isinstance(first, dict) else ""
    parse_status = "ok" if raw_content.strip() else "empty"
    return {
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
        "finish_reason": finish_reason,
        "parse_status": parse_status,
        "truncated_output": finish_reason == "length",
    }


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
        connect_timeout_seconds: int = 15,
        read_timeout_seconds: int = 120,
        total_timeout_seconds: int = 180,
        provider_watchdog_seconds: float | None = None,
        client_index: int = 1,
        rate_warmup_seconds: float = 45.0,
        rate_warmup_start_scale: float = 3.0,
        adaptive_rate_enabled: bool = True,
        adaptive_rate_recovery_factor: float = 0.97,
        adaptive_rate_penalty_multiplier: float = 1.35,
        adaptive_rate_max_scale: float = 8.0,
    ) -> None:
        self._api_key = api_key
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._model = model
        self._temperature = temperature
        self._max_retries = max_retries
        self._max_concurrent = max(1, int(max_concurrent))
        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        self._shared_limiter = shared_limiter
        self._circuit_failures = max(1, int(circuit_failures))
        self._circuit_reset_seconds = max(1.0, float(circuit_reset_seconds))
        self._consecutive_failures = 0
        self._circuit_open_until = 0.0
        self._rate_limit_rps = max(0.001, float(rate_limit_rps))
        self._limiter = _SlidingWindowLimiter(
            max_requests=1,
            window=(1.0 / self._rate_limit_rps),
            jitter_ratio=0.08,
            warmup_seconds=rate_warmup_seconds,
            warmup_start_scale=rate_warmup_start_scale,
            adaptive_enabled=adaptive_rate_enabled,
            adaptive_recovery_factor=adaptive_rate_recovery_factor,
            adaptive_penalty_multiplier=adaptive_rate_penalty_multiplier,
            adaptive_max_scale=adaptive_rate_max_scale,
        )
        self._session: aiohttp.ClientSession | None = None
        self._json_mode_disabled = disable_json_mode
        self._request_log_path: Path | None = None
        self._provider_watchdog_seconds = provider_watchdog_seconds
        self._client_index = max(1, int(client_index))
        self._lane_shared_limiters: dict[tuple[str, float], _SlidingWindowLimiter] = {}
        self._lane_limiters: dict[tuple[str, float], _SlidingWindowLimiter] = {}
        self._lane_semaphores: dict[tuple[str, float], asyncio.Semaphore] = {}
        self._timeout = aiohttp.ClientTimeout(
            total=max(10, int(total_timeout_seconds)),
            connect=max(1, int(connect_timeout_seconds)),
            sock_read=max(1, int(read_timeout_seconds)),
        )
        if disable_json_mode:
            logger.info(
                "Gonka JSON-mode disabled by configuration; sending plain chat completions."
            )

    @property
    def model_id(self) -> str:
        return self._model

    @property
    def json_mode_disabled(self) -> bool:
        return self._json_mode_disabled

    @property
    def key_count(self) -> int:
        return 1

    @property
    def per_key_rate_limit_rps(self) -> float:
        return self._rate_limit_rps

    @property
    def theoretical_aggregate_rps(self) -> float:
        return self._rate_limit_rps

    @property
    def dispatch_worker_hint(self) -> int:
        return self._max_concurrent

    @property
    def max_parallel_requests(self) -> int:
        return self._max_concurrent

    @property
    def provider_key_index(self) -> int:
        return self._client_index

    @property
    def current_rate_scale(self) -> float:
        return self._limiter.current_scale()

    @property
    def current_effective_rps(self) -> float:
        return self._limiter.current_effective_rps()

    def disable_json_mode(self) -> None:
        self._json_mode_disabled = True

    def set_cache(self, cache: object | None) -> None:
        self._cache = cache  # type: ignore[attr-defined]

    def set_request_log_path(self, path: str | Path | None) -> None:
        self._request_log_path = Path(path) if path else None

    @contextmanager
    def request_lane(
        self,
        *,
        lane_name: str = "primary",
        rate_scale: float = 1.0,
        concurrency_scale: float = 1.0,
    ):
        token = _REQUEST_LANE_CONTEXT.set(
            _normalize_lane_settings(
                lane_name=lane_name,
                rate_scale=rate_scale,
                concurrency_scale=concurrency_scale,
            )
        )
        try:
            yield self
        finally:
            _REQUEST_LANE_CONTEXT.reset(token)

    def _current_lane_settings(self) -> tuple[str, float, float]:
        return _REQUEST_LANE_CONTEXT.get()

    def _lane_limiter(self, lane_name: str, rate_scale: float) -> _SlidingWindowLimiter | None:
        if rate_scale >= 0.999:
            return None
        key = (lane_name, round(rate_scale, 4))
        limiter = self._lane_limiters.get(key)
        if limiter is None:
            effective_rps = max(0.001, self._rate_limit_rps * rate_scale)
            limiter = _SlidingWindowLimiter(
                max_requests=1,
                window=(1.0 / effective_rps),
                jitter_ratio=0.08,
            )
            self._lane_limiters[key] = limiter
        return limiter

    def _lane_shared_limiter(
        self, lane_name: str, rate_scale: float
    ) -> _SlidingWindowLimiter | None:
        if self._shared_limiter is None or rate_scale >= 0.999:
            return None
        key = (lane_name, round(rate_scale, 4))
        limiter = self._lane_shared_limiters.get(key)
        if limiter is None:
            effective_rps = max(0.001, self.theoretical_aggregate_rps * rate_scale)
            limiter = _SlidingWindowLimiter(
                max_requests=1,
                window=(1.0 / effective_rps),
                jitter_ratio=0.08,
            )
            self._lane_shared_limiters[key] = limiter
        return limiter

    def _lane_semaphore(self, lane_name: str, concurrency_scale: float) -> asyncio.Semaphore | None:
        if concurrency_scale >= 0.999:
            return None
        key = (lane_name, round(concurrency_scale, 4))
        semaphore = self._lane_semaphores.get(key)
        if semaphore is None:
            cap = max(1, round(self._max_concurrent * concurrency_scale))
            semaphore = asyncio.Semaphore(cap)
            self._lane_semaphores[key] = semaphore
        return semaphore

    def is_available(self) -> bool:
        return time.monotonic() >= self._circuit_open_until

    def backoff_until(self) -> float:
        return self._circuit_open_until

    def _record_success(self) -> None:
        self._consecutive_failures = 0
        self._circuit_open_until = 0.0
        self._limiter.record_success()
        if self._shared_limiter is not None:
            self._shared_limiter.record_success()

    def _record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures < self._circuit_failures:
            return
        jitter = random.uniform(0.85, 1.25)
        self._circuit_open_until = max(
            self._circuit_open_until,
            time.monotonic() + (self._circuit_reset_seconds * jitter),
        )

    async def __aenter__(self) -> GonkaClient:
        self._session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=self._timeout,
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def _request_once(
        self,
        messages: list[dict[str, str]],
        *,
        response_format: dict[str, str] | None = None,
        extra_shared_limiter: _SlidingWindowLimiter | None = None,
        lane_name: str = "primary",
        lane_rate_scale: float = 1.0,
        lane_concurrency_scale: float = 1.0,
    ) -> tuple[_AttemptOutcome, float]:
        assert self._session is not None, "Use 'async with GonkaClient(...)'"

        limiter_wait = 0.0
        if extra_shared_limiter is not None:
            limiter_wait += await extra_shared_limiter.acquire()
        if self._shared_limiter is not None:
            limiter_wait += await self._shared_limiter.acquire()
        lane_limiter = self._lane_limiter(lane_name, lane_rate_scale)
        if lane_limiter is not None:
            limiter_wait += await lane_limiter.acquire()
        limiter_wait += await self._limiter.acquire()

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
        }
        if response_format and not self._json_mode_disabled:
            payload["response_format"] = response_format

        lane_semaphore = self._lane_semaphore(lane_name, lane_concurrency_scale)
        semaphore_context = self._semaphore if lane_semaphore is None else lane_semaphore
        async with semaphore_context, self._semaphore:
            started = time.monotonic()
            try:
                async with self._session.post(self._url, json=payload) as resp:
                    body = await resp.text()
                    latency_ms = (time.monotonic() - started) * 1000.0
                    if resp.status == 200:
                        try:
                            payload_json = json.loads(body) if body else {}
                        except json.JSONDecodeError as exc:
                            return (
                                _AttemptOutcome(
                                    retryable=True,
                                    error_class="json_parse",
                                    error_message=str(exc),
                                    provider_key_index=self._client_index,
                                    latency_ms=latency_ms,
                                    raw_content=body[:4000],
                                ),
                                limiter_wait,
                            )
                        if not isinstance(payload_json, dict):
                            payload_json = {}
                        return (
                            _AttemptOutcome(
                                payload=payload_json,
                                provider_key_index=self._client_index,
                                latency_ms=latency_ms,
                                raw_content=body[:4000],
                            ),
                            limiter_wait,
                        )

                    if "response_format" in payload and _is_json_mode_invalid_request(
                        resp.status, body
                    ):
                        return (
                            _AttemptOutcome(
                                retryable=True,
                                disable_json_mode=True,
                                error_class="response_format_invalid",
                                error_message=body[:500],
                                http_status=resp.status,
                                provider_key_index=self._client_index,
                                latency_ms=latency_ms,
                                raw_content=body[:4000],
                            ),
                            limiter_wait,
                        )

                    retry_after = str(resp.headers.get("Retry-After") or "").strip() or None
                    if resp.status == 429:
                        return (
                            _AttemptOutcome(
                                retryable=True,
                                error_class="provider_http_429",
                                error_message=body[:500],
                                http_status=resp.status,
                                retry_after=retry_after,
                                provider_key_index=self._client_index,
                                latency_ms=latency_ms,
                                raw_content=body[:4000],
                            ),
                            limiter_wait,
                        )
                    if resp.status >= 500:
                        return (
                            _AttemptOutcome(
                                retryable=True,
                                error_class="provider_http_5xx",
                                error_message=body[:500],
                                http_status=resp.status,
                                retry_after=retry_after,
                                provider_key_index=self._client_index,
                                latency_ms=latency_ms,
                                raw_content=body[:4000],
                            ),
                            limiter_wait,
                        )
                    return (
                        _AttemptOutcome(
                            retryable=False,
                            error_class=f"provider_http_{resp.status}",
                            error_message=body[:500],
                            http_status=resp.status,
                            provider_key_index=self._client_index,
                            latency_ms=latency_ms,
                            raw_content=body[:4000],
                        ),
                        limiter_wait,
                    )

            except TimeoutError as exc:
                return (
                    _AttemptOutcome(
                        retryable=True,
                        error_class="timeout",
                        error_message=str(exc),
                        provider_key_index=self._client_index,
                        latency_ms=(time.monotonic() - started) * 1000.0,
                    ),
                    limiter_wait,
                )
            except aiohttp.ClientError as exc:
                exc_str = str(exc)
                retryable = "413" not in exc_str
                return (
                    _AttemptOutcome(
                        retryable=retryable,
                        error_class=("network_error" if retryable else "client_error"),
                        error_message=exc_str,
                        provider_key_index=self._client_index,
                        latency_ms=(time.monotonic() - started) * 1000.0,
                    ),
                    limiter_wait,
                )

    def _log_request(
        self,
        *,
        request_meta: dict[str, Any] | None,
        http_status: int,
        retry_count: int,
        limiter_wait_ms: float,
        backoff_sleep_ms: float,
        total_latency_ms: float,
        error_class: str,
        provider_key_index: int | None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        if self._request_log_path is None:
            return
        summary = _payload_summary(payload or {})
        completed_at = datetime.now(UTC)
        lane_name, lane_rate_scale, lane_concurrency_scale = self._current_lane_settings()
        row = {
            "completed_at": completed_at.isoformat(),
            "completed_at_epoch_ms": int(completed_at.timestamp() * 1000),
            "model_id": self._model,
            "provider_key_index": provider_key_index,
            "http_status": int(http_status or 0),
            "retry_count": int(retry_count or 0),
            "limiter_wait_ms": round(float(limiter_wait_ms or 0.0), 3),
            "backoff_sleep_ms": round(float(backoff_sleep_ms or 0.0), 3),
            "total_latency_ms": round(float(total_latency_ms or 0.0), 3),
            "provider_rate_scale": round(self._limiter.current_scale(), 3),
            "provider_effective_rps": round(self._limiter.current_effective_rps(), 3),
            "shared_rate_scale": round(self._shared_limiter.current_scale(), 3)
            if self._shared_limiter is not None
            else 1.0,
            "shared_effective_rps": (
                round(self._shared_limiter.current_effective_rps(), 3)
                if self._shared_limiter is not None
                else round(self._rate_limit_rps, 3)
            ),
            "prompt_tokens": int(summary.get("prompt_tokens") or 0),
            "completion_tokens": int(summary.get("completion_tokens") or 0),
            "finish_reason": str(summary.get("finish_reason") or ""),
            "parse_status": str(summary.get("parse_status") or "empty"),
            "error_class": str(error_class or ""),
            "truncated_output": bool(summary.get("truncated_output", False)),
            "request_lane": lane_name,
            "request_lane_rate_scale": round(lane_rate_scale, 3),
            "request_lane_concurrency_scale": round(lane_concurrency_scale, 3),
        }
        if request_meta:
            row.update(request_meta)
        _append_jsonl(self._request_log_path, row)

    async def _chat_completion_inner(
        self,
        messages: list[dict[str, str]],
        *,
        response_format: dict[str, str] | None = None,
        request_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        last_outcome = _AttemptOutcome(
            retryable=True,
            error_class="empty_response",
            provider_key_index=self._client_index,
        )
        total_backoff_sleep = 0.0
        total_limiter_wait = 0.0
        lane_name, lane_rate_scale, lane_concurrency_scale = self._current_lane_settings()
        extra_shared_limiter = self._lane_shared_limiter(lane_name, lane_rate_scale)

        for attempt in range(1, self._max_retries + 1):
            outcome, limiter_wait = await self._request_once(
                messages,
                response_format=response_format,
                extra_shared_limiter=extra_shared_limiter,
                lane_name=lane_name,
                lane_rate_scale=lane_rate_scale,
                lane_concurrency_scale=lane_concurrency_scale,
            )
            total_limiter_wait += limiter_wait
            last_outcome = outcome

            if outcome.disable_json_mode:
                if not self._json_mode_disabled:
                    logger.warning(
                        "Gonka 400 invalid_request with response_format; retrying without JSON-mode."
                    )
                self.disable_json_mode()
                continue

            if outcome.ok:
                self._record_success()
                self._log_request(
                    request_meta=request_meta,
                    http_status=200,
                    retry_count=attempt - 1,
                    limiter_wait_ms=total_limiter_wait * 1000.0,
                    backoff_sleep_ms=total_backoff_sleep * 1000.0,
                    total_latency_ms=outcome.latency_ms,
                    error_class="",
                    provider_key_index=outcome.provider_key_index,
                    payload=outcome.payload,
                )
                return outcome.payload or {}

            if not outcome.retryable:
                self._record_failure()
                self._log_request(
                    request_meta=request_meta,
                    http_status=outcome.http_status,
                    retry_count=attempt - 1,
                    limiter_wait_ms=total_limiter_wait * 1000.0,
                    backoff_sleep_ms=total_backoff_sleep * 1000.0,
                    total_latency_ms=outcome.latency_ms,
                    error_class=outcome.error_class,
                    provider_key_index=outcome.provider_key_index,
                )
                raise GonkaRequestError(
                    f"Gonka non-retryable error: {outcome.error_class}: {outcome.error_message}",
                    retryable=False,
                    error_class=outcome.error_class,
                    http_status=outcome.http_status,
                    provider_key_index=outcome.provider_key_index,
                    retry_count=attempt - 1,
                    limiter_wait_ms=total_limiter_wait * 1000.0,
                    backoff_sleep_ms=total_backoff_sleep * 1000.0,
                )

            self._record_failure()
            delay = _retry_delay_seconds(attempt=attempt, retry_after=outcome.retry_after)
            if outcome.http_status == 429:
                await self._limiter.penalise(delay)
                if self._shared_limiter is not None:
                    await self._shared_limiter.penalise(min(delay, _MAX_RETRY_AFTER_SECONDS))
            total_backoff_sleep += delay
            logger.warning(
                "Gonka {} (attempt {}/{}), retry in {:.1f}s: {}",
                outcome.http_status or outcome.error_class,
                attempt,
                self._max_retries,
                delay,
                outcome.error_message[:200],
            )
            await asyncio.sleep(delay)

        self._log_request(
            request_meta=request_meta,
            http_status=last_outcome.http_status,
            retry_count=self._max_retries,
            limiter_wait_ms=total_limiter_wait * 1000.0,
            backoff_sleep_ms=total_backoff_sleep * 1000.0,
            total_latency_ms=last_outcome.latency_ms,
            error_class=last_outcome.error_class,
            provider_key_index=last_outcome.provider_key_index,
        )
        raise GonkaRequestError(
            f"Gonka request failed after {self._max_retries} attempts",
            retryable=last_outcome.retryable,
            error_class=last_outcome.error_class or "empty_response",
            http_status=last_outcome.http_status,
            provider_key_index=last_outcome.provider_key_index,
            retry_count=self._max_retries,
            limiter_wait_ms=total_limiter_wait * 1000.0,
            backoff_sleep_ms=total_backoff_sleep * 1000.0,
        )

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        response_format: dict[str, str] | None = None,
        request_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        watchdog_seconds = self._provider_watchdog_seconds
        if watchdog_seconds is None:
            return await self._chat_completion_inner(
                messages,
                response_format=response_format,
                request_meta=request_meta,
            )
        try:
            return await asyncio.wait_for(
                self._chat_completion_inner(
                    messages,
                    response_format=response_format,
                    request_meta=request_meta,
                ),
                timeout=watchdog_seconds,
            )
        except TimeoutError as exc:
            self._record_failure()
            self._log_request(
                request_meta=request_meta,
                http_status=0,
                retry_count=0,
                limiter_wait_ms=0.0,
                backoff_sleep_ms=0.0,
                total_latency_ms=0.0,
                error_class="watchdog_timeout",
                provider_key_index=self._client_index,
            )
            raise GonkaRequestError(
                f"Gonka request watchdog timeout after {watchdog_seconds:.1f}s",
                retryable=True,
                error_class="watchdog_timeout",
                provider_key_index=self._client_index,
            ) from exc


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
        connect_timeout_seconds: int = 15,
        read_timeout_seconds: int = 120,
        total_timeout_seconds: int = 180,
        provider_watchdog_seconds: float | None = None,
        global_concurrent_cap: int | None = None,
        rate_warmup_seconds: float = 45.0,
        rate_warmup_start_scale: float = 3.0,
        adaptive_rate_enabled: bool = True,
        adaptive_rate_recovery_factor: float = 0.97,
        adaptive_rate_penalty_multiplier: float = 1.35,
        adaptive_rate_max_scale: float = 8.0,
    ) -> None:
        cleaned = [str(key).strip() for key in api_keys if str(key).strip()]
        if not cleaned:
            raise ValueError("GonkaClientPool requires at least one API key")
        total_rps = max(0.001, float(rate_limit_rps) * max(1, len(cleaned)))
        self._shared_limiter = _SlidingWindowLimiter(
            max_requests=1,
            window=(1.0 / total_rps),
            jitter_ratio=0.12,
            warmup_seconds=rate_warmup_seconds,
            warmup_start_scale=rate_warmup_start_scale,
            adaptive_enabled=adaptive_rate_enabled,
            adaptive_recovery_factor=adaptive_rate_recovery_factor,
            adaptive_penalty_multiplier=adaptive_rate_penalty_multiplier,
            adaptive_max_scale=adaptive_rate_max_scale,
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
                connect_timeout_seconds=connect_timeout_seconds,
                read_timeout_seconds=read_timeout_seconds,
                total_timeout_seconds=total_timeout_seconds,
                provider_watchdog_seconds=None,
                client_index=index + 1,
                rate_warmup_seconds=rate_warmup_seconds,
                rate_warmup_start_scale=rate_warmup_start_scale,
                adaptive_rate_enabled=adaptive_rate_enabled,
                adaptive_rate_recovery_factor=adaptive_rate_recovery_factor,
                adaptive_rate_penalty_multiplier=adaptive_rate_penalty_multiplier,
                adaptive_rate_max_scale=adaptive_rate_max_scale,
            )
            for index, key in enumerate(cleaned)
        ]
        self._per_key_cap = max(1, int(max_concurrent))
        auto_global_cap = max(1, round(len(self._clients) * self._per_key_cap * 0.9))
        self._global_concurrent_cap = (
            auto_global_cap
            if global_concurrent_cap is None or int(global_concurrent_cap) <= 0
            else max(1, int(global_concurrent_cap))
        )
        self._in_flight = [0 for _ in self._clients]
        self._selection_lock = asyncio.Lock()
        self._json_mode_disabled = disable_json_mode
        self._rr_cursor = 0
        self._request_log_path: Path | None = None
        self._provider_watchdog_seconds = provider_watchdog_seconds
        self._global_sem = asyncio.Semaphore(self._global_concurrent_cap)
        self._rate_limit_rps = max(0.001, float(rate_limit_rps))
        self._max_retries = max(1, int(max_retries))
        self._model = model
        self._lane_shared_limiters: dict[tuple[str, float], _SlidingWindowLimiter] = {}

    @property
    def model_id(self) -> str:
        return self._clients[0].model_id

    @property
    def key_count(self) -> int:
        return len(self._clients)

    @property
    def per_key_rate_limit_rps(self) -> float:
        return self._rate_limit_rps

    @property
    def theoretical_aggregate_rps(self) -> float:
        return self.key_count * self.per_key_rate_limit_rps

    @property
    def dispatch_worker_hint(self) -> int:
        return self.current_global_concurrency_cap

    @property
    def current_global_concurrency_cap(self) -> int:
        scale = max(1.0, self._shared_limiter.current_scale())
        return max(
            1,
            min(
                self._global_concurrent_cap,
                round(self._global_concurrent_cap / math.sqrt(scale)),
            ),
        )

    @contextmanager
    def request_lane(
        self,
        *,
        lane_name: str = "primary",
        rate_scale: float = 1.0,
        concurrency_scale: float = 1.0,
    ):
        token = _REQUEST_LANE_CONTEXT.set(
            _normalize_lane_settings(
                lane_name=lane_name,
                rate_scale=rate_scale,
                concurrency_scale=concurrency_scale,
            )
        )
        try:
            yield self
        finally:
            _REQUEST_LANE_CONTEXT.reset(token)

    def _current_lane_settings(self) -> tuple[str, float, float]:
        return _REQUEST_LANE_CONTEXT.get()

    def _scaled_global_concurrency_cap(self, concurrency_scale: float = 1.0) -> int:
        lane_scale = min(1.0, max(0.05, float(concurrency_scale)))
        target = max(1, round(self.current_global_concurrency_cap * lane_scale))
        return max(1, min(self._global_concurrent_cap, target))

    def _effective_per_key_cap(self, idx: int, *, concurrency_scale: float = 1.0) -> int:
        client = self._clients[idx]
        scale = max(1.0, client.current_rate_scale)
        target = max(
            1,
            round(
                (self._per_key_cap / math.sqrt(scale))
                * min(1.0, max(0.05, float(concurrency_scale)))
            ),
        )
        return max(1, min(self._per_key_cap, target))

    def _lane_shared_limiter(
        self, lane_name: str, rate_scale: float
    ) -> _SlidingWindowLimiter | None:
        if rate_scale >= 0.999:
            return None
        key = (lane_name, round(rate_scale, 4))
        limiter = self._lane_shared_limiters.get(key)
        if limiter is None:
            effective_rps = max(0.001, self.theoretical_aggregate_rps * rate_scale)
            limiter = _SlidingWindowLimiter(
                max_requests=1,
                window=(1.0 / effective_rps),
                jitter_ratio=0.12,
            )
            self._lane_shared_limiters[key] = limiter
        return limiter

    def set_cache(self, cache: object | None) -> None:
        for client in self._clients:
            client.set_cache(cache)

    def set_request_log_path(self, path: str | Path | None) -> None:
        self._request_log_path = Path(path) if path else None

    def disable_json_mode(self) -> None:
        if self._json_mode_disabled:
            return
        self._json_mode_disabled = True
        for client in self._clients:
            client.disable_json_mode()

    async def __aenter__(self) -> GonkaClientPool:
        for client in self._clients:
            await client.__aenter__()
        return self

    async def __aexit__(self, *exc: object) -> None:
        for client in self._clients:
            await client.__aexit__(*exc)

    async def _acquire_client_index(self, *, concurrency_scale: float = 1.0) -> int:
        while True:
            await self._global_sem.acquire()
            async with self._selection_lock:
                active_total = sum(self._in_flight)
                lane_global_cap = self._scaled_global_concurrency_cap(concurrency_scale)
                if active_total >= lane_global_cap:
                    available = []
                else:
                    available = [
                        i
                        for i, client in enumerate(self._clients)
                        if client.is_available()
                        and self._in_flight[i]
                        < self._effective_per_key_cap(i, concurrency_scale=concurrency_scale)
                    ]
                if available:
                    min_load = min(self._in_flight[i] for i in available)
                    tied = [i for i in available if self._in_flight[i] == min_load]
                    tied.sort()
                    offset = self._rr_cursor % len(tied)
                    idx = tied[offset]
                    self._rr_cursor = (self._rr_cursor + 1) % max(1, len(self._clients))
                    self._in_flight[idx] += 1
                    return idx
                earliest = min(
                    (client.backoff_until() for client in self._clients),
                    default=time.monotonic() + 0.25,
                )
            self._global_sem.release()
            wait_for = max(0.05, earliest - time.monotonic())
            await asyncio.sleep(wait_for * random.uniform(0.85, 1.2))

    async def _release_client_index(self, idx: int) -> None:
        async with self._selection_lock:
            self._in_flight[idx] = max(0, self._in_flight[idx] - 1)
        self._global_sem.release()

    def _log_request(
        self,
        *,
        request_meta: dict[str, Any] | None,
        http_status: int,
        retry_count: int,
        limiter_wait_ms: float,
        backoff_sleep_ms: float,
        total_latency_ms: float,
        error_class: str,
        provider_key_index: int | None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        if self._request_log_path is None:
            return
        summary = _payload_summary(payload or {})
        completed_at = datetime.now(UTC)
        lane_name, lane_rate_scale, lane_concurrency_scale = self._current_lane_settings()
        row = {
            "completed_at": completed_at.isoformat(),
            "completed_at_epoch_ms": int(completed_at.timestamp() * 1000),
            "model_id": self._model,
            "provider_key_index": provider_key_index,
            "http_status": int(http_status or 0),
            "retry_count": int(retry_count or 0),
            "limiter_wait_ms": round(float(limiter_wait_ms or 0.0), 3),
            "backoff_sleep_ms": round(float(backoff_sleep_ms or 0.0), 3),
            "total_latency_ms": round(float(total_latency_ms or 0.0), 3),
            "shared_rate_scale": round(self._shared_limiter.current_scale(), 3),
            "shared_effective_rps": round(self._shared_limiter.current_effective_rps(), 3),
            "effective_global_concurrency_cap": int(
                self._scaled_global_concurrency_cap(lane_concurrency_scale)
            ),
            "prompt_tokens": int(summary.get("prompt_tokens") or 0),
            "completion_tokens": int(summary.get("completion_tokens") or 0),
            "finish_reason": str(summary.get("finish_reason") or ""),
            "parse_status": str(summary.get("parse_status") or "empty"),
            "error_class": str(error_class or ""),
            "truncated_output": bool(summary.get("truncated_output", False)),
            "request_lane": lane_name,
            "request_lane_rate_scale": round(lane_rate_scale, 3),
            "request_lane_concurrency_scale": round(lane_concurrency_scale, 3),
        }
        if provider_key_index is not None and 1 <= int(provider_key_index) <= len(self._clients):
            client = self._clients[int(provider_key_index) - 1]
            row["provider_rate_scale"] = round(client.current_rate_scale, 3)
            row["provider_effective_rps"] = round(client.current_effective_rps, 3)
            row["effective_per_key_concurrency_cap"] = int(
                self._effective_per_key_cap(
                    int(provider_key_index) - 1,
                    concurrency_scale=lane_concurrency_scale,
                )
            )
        if request_meta:
            row.update(request_meta)
        _append_jsonl(self._request_log_path, row)

    async def _chat_completion_inner(
        self,
        messages: list[dict[str, str]],
        *,
        response_format: dict[str, str] | None = None,
        request_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        last_outcome = _AttemptOutcome(
            retryable=True,
            error_class="empty_response",
        )
        total_backoff_sleep = 0.0
        total_limiter_wait = 0.0
        lane_name, lane_rate_scale, lane_concurrency_scale = self._current_lane_settings()
        extra_shared_limiter = self._lane_shared_limiter(lane_name, lane_rate_scale)

        for attempt in range(1, self._max_retries + 1):
            idx = await self._acquire_client_index(concurrency_scale=lane_concurrency_scale)
            client = self._clients[idx]
            try:
                effective_response_format = None if self._json_mode_disabled else response_format
                outcome, limiter_wait = await client._request_once(
                    messages,
                    response_format=effective_response_format,
                    extra_shared_limiter=extra_shared_limiter,
                    lane_name=lane_name,
                    lane_rate_scale=lane_rate_scale,
                    lane_concurrency_scale=lane_concurrency_scale,
                )
            finally:
                await self._release_client_index(idx)

            total_limiter_wait += limiter_wait
            last_outcome = outcome

            if outcome.disable_json_mode:
                if not self._json_mode_disabled:
                    logger.warning(
                        "Gonka 400 invalid_request with response_format in pool; retrying without JSON-mode."
                    )
                self.disable_json_mode()
                continue

            if outcome.ok:
                client._record_success()
                self._log_request(
                    request_meta=request_meta,
                    http_status=200,
                    retry_count=attempt - 1,
                    limiter_wait_ms=total_limiter_wait * 1000.0,
                    backoff_sleep_ms=total_backoff_sleep * 1000.0,
                    total_latency_ms=outcome.latency_ms,
                    error_class="",
                    provider_key_index=outcome.provider_key_index,
                    payload=outcome.payload,
                )
                return outcome.payload or {}

            client._record_failure()
            if not outcome.retryable:
                self._log_request(
                    request_meta=request_meta,
                    http_status=outcome.http_status,
                    retry_count=attempt - 1,
                    limiter_wait_ms=total_limiter_wait * 1000.0,
                    backoff_sleep_ms=total_backoff_sleep * 1000.0,
                    total_latency_ms=outcome.latency_ms,
                    error_class=outcome.error_class,
                    provider_key_index=outcome.provider_key_index,
                )
                raise GonkaRequestError(
                    f"Gonka non-retryable error: {outcome.error_class}: {outcome.error_message}",
                    retryable=False,
                    error_class=outcome.error_class,
                    http_status=outcome.http_status,
                    provider_key_index=outcome.provider_key_index,
                    retry_count=attempt - 1,
                    limiter_wait_ms=total_limiter_wait * 1000.0,
                    backoff_sleep_ms=total_backoff_sleep * 1000.0,
                )

            delay = _retry_delay_seconds(attempt=attempt, retry_after=outcome.retry_after)
            if outcome.http_status == 429:
                await client._limiter.penalise(delay)
                await self._shared_limiter.penalise(min(delay, _MAX_RETRY_AFTER_SECONDS))
            total_backoff_sleep += delay
            logger.warning(
                "Gonka pool {} key={} (attempt {}/{}), retry in {:.1f}s: {}",
                outcome.http_status or outcome.error_class,
                outcome.provider_key_index,
                attempt,
                self._max_retries,
                delay,
                outcome.error_message[:200],
            )
            await asyncio.sleep(delay)

        self._log_request(
            request_meta=request_meta,
            http_status=last_outcome.http_status,
            retry_count=self._max_retries,
            limiter_wait_ms=total_limiter_wait * 1000.0,
            backoff_sleep_ms=total_backoff_sleep * 1000.0,
            total_latency_ms=last_outcome.latency_ms,
            error_class=last_outcome.error_class,
            provider_key_index=last_outcome.provider_key_index,
        )
        raise GonkaRequestError(
            f"Gonka request failed after {self._max_retries} attempts",
            retryable=last_outcome.retryable,
            error_class=last_outcome.error_class or "empty_response",
            http_status=last_outcome.http_status,
            provider_key_index=last_outcome.provider_key_index,
            retry_count=self._max_retries,
            limiter_wait_ms=total_limiter_wait * 1000.0,
            backoff_sleep_ms=total_backoff_sleep * 1000.0,
        )

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        response_format: dict[str, str] | None = None,
        request_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        watchdog_seconds = self._provider_watchdog_seconds
        if watchdog_seconds is None:
            return await self._chat_completion_inner(
                messages,
                response_format=response_format,
                request_meta=request_meta,
            )
        try:
            return await asyncio.wait_for(
                self._chat_completion_inner(
                    messages,
                    response_format=response_format,
                    request_meta=request_meta,
                ),
                timeout=watchdog_seconds,
            )
        except TimeoutError as exc:
            self._log_request(
                request_meta=request_meta,
                http_status=0,
                retry_count=0,
                limiter_wait_ms=0.0,
                backoff_sleep_ms=0.0,
                total_latency_ms=0.0,
                error_class="watchdog_timeout",
                provider_key_index=None,
            )
            raise GonkaRequestError(
                f"Gonka pool request watchdog timeout after {watchdog_seconds:.1f}s",
                retryable=True,
                error_class="watchdog_timeout",
            ) from exc


__all__ = [
    "GonkaClient",
    "GonkaClientPool",
    "GonkaRequestError",
    "_SlidingWindowLimiter",
    "_retry_delay_seconds",
]
