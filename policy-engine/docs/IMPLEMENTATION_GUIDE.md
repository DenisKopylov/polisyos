# Resilience Patterns - Implementation Guide

## Quick Start

### Decorator Stack (recommended)
```python
from polisyos.fabric.connectors.resilience import (
    with_retry,
    with_circuit_breaker,
    with_rate_limit,
    with_fallback,
    CacheFallback,
    MockFallback,
    CircuitBreakerConfig,
    RetryPolicy,
)

@with_fallback([CacheFallback(), MockFallback()])
@with_circuit_breaker(CircuitBreakerConfig(failure_threshold=5))
@with_retry(RetryPolicy(max_attempts=3, base_delay=1.0))
@with_rate_limit(rate_limit_rps=10.0, adaptive=True)
async def fetch(handle, request):
    return await connector.fetch(handle, request)
```

### Connector Metadata (registry auto-wrap)
```python
from polisyos.ir.connectors import ConnectorMetadataSpec

class MyConnector(BaseConnector):
    metadata = ConnectorMetadataSpec(
        connector_id="my_api",
        namespace="example",
        version="1.0.0",
        source_name="Example API",
        source_organization="Example Org",
        resilience_config={
            "retry_policy": {"max_attempts": 3, "base_delay": 1.0},
            "circuit_breaker": {"failure_threshold": 5},
        "rate_limit_rps": 10.0,
        "adaptive_rate_limit": True,
        "fallback": ["CACHE_ONLY", "MOCK"],
        "inherit_connection_config": True,
    },
    )
```

Note: `inherit_connection_config=True` allows `ConnectionConfig` values to fill in missing resilience fields.

## Component Notes

### RetryPolicy
- Uses exponential backoff with jitter
- Honors `FetchRequest.retryable=False`
- Raises `RetryExhaustedError` for retryable failures after the last attempt

### CircuitBreaker
- Sliding window failure counting
- Half-open probes after timeout
- Cancellation does not increment failure counters

### RateLimiter
- Token bucket, monotonic time
- `record_rate_limit(retry_after_seconds=...)` sets cooldown

### FallbackChain
- Accepts a list of strategies in order
- `CacheFallback` uses `ConnectorCacheStore.get_any()` and can enforce max staleness

## Resilience Metadata
`FetchResult` gains optional resilience metadata:
```python
result.resilience.fallback_used
result.resilience.retry_attempts
```

## Testing
Run the resilience tests:
```bash
pytest tests/fabric/connectors/test_resilience.py -v
```

## Operational Guidance
- Prefer circuit IDs scoped to `connector_id + domain (+ dataset)`.
- Rate limiting is typically per domain; use separate limiters per upstream.
- Avoid retries on non-idempotent operations.
