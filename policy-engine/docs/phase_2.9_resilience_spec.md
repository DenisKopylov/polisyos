# Phase 2.9: Resilience & Reliability Patterns - Technical Specification

## Executive Summary
Phase 2.9 adds an opt-in resilience layer for connector fetch operations. It provides retry policies, circuit breakers, rate limiting, and fallback strategies with consistent observability and safe async behavior.

Key fixes applied to earlier draft issues:
- **RetryExhaustedError semantics**: raised when the last attempt fails with a retryable error.
- **AdaptiveRateLimiter deadlock**: removed re-entrant lock acquisition; no blocking deadlocks.
- **Retry-After handling**: enforced via a `blocked_until` cooldown in `acquire()`.
- **CacheFallback**: real cache integration; correct argument extraction for `fetch(self, handle, request)`.
- **Monotonic time**: used for intervals, backoff, and windows to avoid NTP/time-jump bugs.
- **Cancellation**: `asyncio.CancelledError` is not retried or counted as a circuit failure.

## Components

### RetryPolicy (`retry.py`)
- Exponential backoff with jitter
- Retryable error classification (network errors, 429/502/503/504, etc.)
- **Idempotency-aware**: respects `FetchRequest.retryable=False`
- Raises **RetryExhaustedError** on last retryable failure

### CircuitBreaker (`circuit_breaker.py`)
- CLOSED / OPEN / HALF_OPEN state machine
- Sliding window failure counting (monotonic time)
- Open-state cooldown then HALF_OPEN probes
- Thread-safe; no awaits under lock

### RateLimiter + AdaptiveRateLimiter (`rate_limiter.py`)
- Token bucket rate limiting (monotonic time)
- Retry-After cooldown enforced inside `acquire()`
- AIMD adaptive tuning for 429 responses

### FallbackChain (`fallback.py`)
- Strategy chain: cache -> mock -> raise (configurable)
- **CacheFallback** integrates with `ConnectorCacheStore.get_any()`
- Adds resilience metadata to `FetchResult`

## Data Flow (Default Composition)
Decorators stack in this order (outer -> inner):
1. `FallbackChain`
2. `CircuitBreaker`
3. `RetryPolicy`
4. `RateLimiter`
5. Actual fetch

## Configuration & Integration

### Connector Metadata (opt-in)
`ConnectorMetadataSpec` now supports an optional `resilience_config` dict. Example:

```python
metadata = ConnectorMetadataSpec(
    connector_id="wdi",
    namespace="worldbank",
    version="1.0.0",
    source_name="World Development Indicators",
    source_organization="World Bank",
    resilience_config={
        "retry_policy": {"max_attempts": 3, "base_delay": 1.0},
        "circuit_breaker": {"failure_threshold": 5, "timeout_seconds": 60},
        "rate_limit_rps": 10.0,
        "adaptive_rate_limit": True,
        "fallback": ["CACHE_ONLY", "MOCK"],
        "fallback_max_staleness_seconds": 3600,
        "inherit_connection_config": True,
    },
)
```

`inherit_connection_config` enables ConnectionConfig-level overrides for fields that are not explicitly set in the connector's resilience config.

### Registry Auto-Wrapping
When `resilience_config` is present, the registry wraps `connector.fetch` via `apply_resilience()`.

### ConnectionPool Integration
`ConnectionPool` accepts an optional circuit breaker for fast-fail on `acquire()`.

## Idempotency & Retry
Retries are only safe for idempotent operations. The system supports:
- `FetchRequest.retryable=False` to disable retries for non-idempotent requests

## Cancellation Semantics
`asyncio.CancelledError` is re-raised immediately and does **not** increment failure counters.

## Observability
All components emit spans and logs. Metrics are registered in `polisyos.core.observability`:
- `polisyos_connector_retry_attempts_total`
- `polisyos_connector_retry_delay_seconds`
- `polisyos_connector_circuit_state`
- `polisyos_connector_circuit_trips_total`
- `polisyos_connector_circuit_rejected_requests_total`
- `polisyos_connector_rate_limit_wait_seconds`
- `polisyos_connector_rate_limit_throttled_total`
- `polisyos_connector_rate_limit_tokens`
- `polisyos_connector_fallback_triggered_total`
- `polisyos_connector_fallback_success_total`

## Resilience Metadata
`FetchResult` now supports:
- `resilience: ResilienceInfo | None`

Fields include:
- `fallback_used`, `fallback_strategy`
- `retry_attempts`
- `rate_limited`, `circuit_state`

## Performance & Safety
- **Monotonic clocks** are used for all delays and windows.
- Locks are held only in micro-critical sections; no awaits under locks.

## Known Limitations / Follow-ups
- Circuit breaker state is in-process (not distributed).
- Pool-level breaker and fetch-level breaker are separate instances.
- Metrics are opt-in and require OTel exporters to be configured.

## Verification
See `tests/fabric/connectors/test_resilience.py` for focused coverage of critical behaviors.
