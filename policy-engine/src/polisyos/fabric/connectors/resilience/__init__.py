"""
Resilience & Reliability Patterns for Data Connectors.

This module provides production-grade resilience patterns that protect
external API calls from transient failures, cascade failures, and overload.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from functools import wraps
from typing import Any, Awaitable, Callable, Mapping, TypeVar

from polisyos.common.logger import get_logger

from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitOpenError,
    CircuitState,
    with_circuit_breaker,
)
from .fallback import (
    CacheFallback,
    FallbackChain,
    FallbackStrategy,
    MockFallback,
    RaiseFallback,
    with_fallback,
)
from .rate_limiter import (
    AdaptiveRateLimiter,
    RateLimiter,
    RateLimiterConfig,
    with_rate_limit,
)
from .retry import (
    RetryExhaustedError,
    RetryPolicy,
    is_retryable_error,
    with_retry,
)

logger = get_logger(__name__)

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class ResilienceConfig:
    """Runtime resilience configuration for connector fetch calls."""

    retry_policy: RetryPolicy | None = None
    circuit_breaker: CircuitBreakerConfig | CircuitBreaker | None = None
    rate_limit_rps: float | None = None
    adaptive_rate_limit: bool = False
    fallback_chain: FallbackChain[Any] | None = None
    inherit_connection_config: bool = False


def _build_fallback_chain(
    spec: Any,
    *,
    cache_store: Any | None = None,
    max_staleness_seconds: float | None = None,
) -> FallbackChain[Any] | None:
    if spec is None:
        return None
    if isinstance(spec, FallbackChain):
        return spec
    if isinstance(spec, list):
        items = spec
    elif isinstance(spec, str):
        items = [spec]
    else:
        return None

    strategies: list[FallbackStrategy[Any]] = []
    for item in items:
        if isinstance(item, FallbackStrategy):
            strategies.append(item)
            continue
        if isinstance(item, str):
            name = item.strip().upper()
            if name in {"CACHE", "CACHE_ONLY", "STALE_CACHE"}:
                strategies.append(
                    CacheFallback(
                        cache_store=cache_store,
                        max_staleness_seconds=max_staleness_seconds,
                    )
                )
            elif name in {"MOCK", "STATIC_MOCK"}:
                strategies.append(MockFallback())
            elif name in {"RAISE", "NONE"}:
                strategies.append(RaiseFallback())

    return FallbackChain(strategies) if strategies else None


def resolve_resilience_config(
    raw: ResilienceConfig | Mapping[str, Any] | None,
    *,
    cache_store: Any | None = None,
) -> ResilienceConfig | None:
    """Resolve resilience config."""
    if raw is None:
        return None
    if isinstance(raw, ResilienceConfig):
        return raw

    if not isinstance(raw, Mapping):
        logger.warning("Unknown resilience config type", value=type(raw).__name__)
        return None

    retry_spec = raw.get("retry_policy") or raw.get("retry")
    circuit_spec = raw.get("circuit_breaker") or raw.get("circuit")
    rate_limit_rps = raw.get("rate_limit_rps") or raw.get("rate_limit")
    adaptive = bool(raw.get("adaptive_rate_limit") or raw.get("adaptive"))
    inherit_connection = bool(
        raw.get("inherit_connection_config") or raw.get("use_connection_config")
    )
    fallback_spec = raw.get("fallback") or raw.get("fallback_strategy")
    max_staleness = raw.get("fallback_max_staleness_seconds")

    retry_policy = None
    if isinstance(retry_spec, RetryPolicy):
        retry_policy = retry_spec
    elif isinstance(retry_spec, Mapping):
        retry_policy = RetryPolicy(**retry_spec)

    circuit_breaker = None
    if isinstance(circuit_spec, CircuitBreaker):
        circuit_breaker = circuit_spec
    elif isinstance(circuit_spec, CircuitBreakerConfig):
        circuit_breaker = circuit_spec
    elif isinstance(circuit_spec, Mapping):
        circuit_breaker = CircuitBreakerConfig(**circuit_spec)

    fallback_chain = _build_fallback_chain(
        fallback_spec,
        cache_store=cache_store,
        max_staleness_seconds=max_staleness,
    )

    return ResilienceConfig(
        retry_policy=retry_policy,
        circuit_breaker=circuit_breaker,
        rate_limit_rps=rate_limit_rps,
        adaptive_rate_limit=adaptive,
        fallback_chain=fallback_chain,
        inherit_connection_config=inherit_connection,
    )


def _default_rate_limiter_id(
    func: Callable[..., Awaitable[T]],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> str:
    connector_id = None
    for key in ("handle", "connection", "connection_handle"):
        handle = kwargs.get(key)
        if handle is not None and hasattr(handle, "connector_id"):
            connector_id = getattr(handle, "connector_id")
            break
    if connector_id is None:
        for arg in args:
            if hasattr(arg, "connector_id"):
                connector_id = getattr(arg, "connector_id")
                break

    domain = None
    handle = None
    for key in ("handle", "connection", "connection_handle"):
        handle = kwargs.get(key)
        if handle is not None:
            break
    if handle is None:
        for arg in args:
            if hasattr(arg, "config") and hasattr(arg, "connector_id"):
                handle = arg
                break

    if handle is not None and hasattr(handle, "config"):
        url = getattr(handle.config, "url", None)
        if isinstance(url, str) and "://" in url:
            try:
                from urllib.parse import urlparse

                domain = urlparse(url).netloc or None
            except Exception:
                domain = None

    base = connector_id or f"{func.__module__}.{func.__name__}"
    if domain:
        return f"{base}:{domain}"
    return base


def apply_resilience(
    func: Callable[..., Awaitable[T]],
    *,
    config: ResilienceConfig | Mapping[str, Any] | None,
    cache_store: Any | None = None,
) -> Callable[..., Awaitable[T]]:
    """
    Apply resilience wrappers to a fetch-like coroutine.

    Resilience is opt-in: if config is None, returns func unchanged.
    """
    resolved = resolve_resilience_config(config, cache_store=cache_store)
    if resolved is None:
        return func

    circuit_breakers: dict[str, CircuitBreaker] = {}
    rate_limiters: dict[str, RateLimiter] = {}
    registry_lock = threading.Lock()

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        retry_policy = resolved.retry_policy
        rate_limit_rps = resolved.rate_limit_rps
        adaptive = resolved.adaptive_rate_limit
        breaker_config = resolved.circuit_breaker

        handle = None
        for key in ("handle", "connection", "connection_handle"):
            handle = kwargs.get(key)
            if handle is not None:
                break
        if handle is None:
            for arg in args:
                if hasattr(arg, "config") and hasattr(arg, "connector_id"):
                    handle = arg
                    break

        # Connection-level overrides are explicit opt-in
        if resolved.inherit_connection_config and handle is not None:
            if rate_limit_rps is None:
                rate_limit_rps = getattr(handle.config, "rate_limit_rps", None)

            if retry_policy is None:
                max_retries = getattr(handle.config, "max_retries", None)
                base_delay = getattr(handle.config, "retry_delay_seconds", None)
                if max_retries is not None:
                    retry_policy = RetryPolicy(
                        max_attempts=max_retries,
                        base_delay=base_delay or 1.0,
                    )

        def _get_breaker() -> CircuitBreaker | None:
            if breaker_config is None:
                return None
            if isinstance(breaker_config, CircuitBreaker):
                return breaker_config
            from .circuit_breaker import _default_circuit_id

            breaker_id = _default_circuit_id(func, args, kwargs)
            with registry_lock:
                breaker = circuit_breakers.get(breaker_id)
                if breaker is None:
                    breaker = CircuitBreaker(circuit_id=breaker_id, config=breaker_config)
                    circuit_breakers[breaker_id] = breaker
                return breaker

        def _get_limiter() -> RateLimiter | None:
            if rate_limit_rps is None:
                return None
            limiter_id = _default_rate_limiter_id(func, args, kwargs)
            # Different rate limits get separate limiters
            limiter_key = f"{limiter_id}:{rate_limit_rps}"
            with registry_lock:
                limiter = rate_limiters.get(limiter_key)
                if limiter is None:
                    if adaptive:
                        limiter = AdaptiveRateLimiter(
                            initial_rate_rps=rate_limit_rps,
                            config=RateLimiterConfig(rate_limit_rps=rate_limit_rps),
                            limiter_id=limiter_id,
                        )
                    else:
                        limiter = RateLimiter(
                            rate_limit_rps=rate_limit_rps,
                            limiter_id=limiter_id,
                        )
                    rate_limiters[limiter_key] = limiter
                return limiter

        async def _rate_limited_call(*call_args: Any, **call_kwargs: Any) -> T:
            limiter = _get_limiter()
            if limiter is not None:
                await limiter.acquire()
            return await func(*call_args, **call_kwargs)

        async def _retry_call(*call_args: Any, **call_kwargs: Any) -> T:
            if retry_policy is None:
                return await _rate_limited_call(*call_args, **call_kwargs)
            return await retry_policy.execute(
                _rate_limited_call,
                *call_args,
                **call_kwargs,
            )

        async def _circuit_call(*call_args: Any, **call_kwargs: Any) -> T:
            breaker = _get_breaker()
            if breaker is None:
                return await _retry_call(*call_args, **call_kwargs)
            return await breaker.execute(
                _retry_call,
                *call_args,
                **call_kwargs,
            )

        if resolved.fallback_chain is not None:
            return await resolved.fallback_chain.execute(
                _circuit_call,
                *args,
                **kwargs,
            )
        return await _circuit_call(*args, **kwargs)

    wrapper._resilience_config = resolved  # type: ignore[attr-defined]
    wrapper._resilience_circuit_breakers = circuit_breakers  # type: ignore[attr-defined]
    wrapper._resilience_rate_limiters = rate_limiters  # type: ignore[attr-defined]

    return wrapper


__all__ = [
    # Retry
    "RetryPolicy",
    "RetryExhaustedError",
    "with_retry",
    "is_retryable_error",
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitState",
    "CircuitOpenError",
    "with_circuit_breaker",
    # Rate Limiter
    "RateLimiter",
    "AdaptiveRateLimiter",
    "RateLimiterConfig",
    "with_rate_limit",
    # Fallback
    "FallbackStrategy",
    "FallbackChain",
    "CacheFallback",
    "MockFallback",
    "RaiseFallback",
    "with_fallback",
    # Resilience integration
    "ResilienceConfig",
    "resolve_resilience_config",
    "apply_resilience",
]
