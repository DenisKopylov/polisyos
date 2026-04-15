# Scientist Phase 0 Acceptance

Related reference: [Scientist Remediation Status](remediation-status.md).

> Acceptance contract for Phase 0 of `SCIENTIST_AUDIT_REMEDIATION_PLAN.md`.
> This page does not claim closure by itself; it records what must be true
> before Phase 0 can be signed off.

## Scope

- `WS-0A` async, locking, lifecycle correctness
- `WS-0B` budget, request correctness, security, and scientific hotfixes

## Exit Criteria

- Every critical `asyncio.gather()` call site either uses `return_exceptions=True` or has documented sibling-failure semantics.
- Worker pools, retries, verifier processes, and lock heartbeats pass teardown tests without permit drift, stale locks, orphan threads, or orphan processes.
- Request-attempt retries reuse stable idempotency keys.
- Budget reservation accounting remains consistent across success, failure, and post-record adjustment paths.
- Empty input, invalid depth, and zero-budget paths fail with typed errors.
- Masking bypasses fail closed.
- Statistical hotfixes on the default path have explicit regression coverage.

## Required Evidence

| Evidence | Current posture |
|----------|-----------------|
| Fault-injection tests for sibling failure and task cancellation | Partial |
| Concurrency stress tests for pool shrink/expand and permit accounting | Partial |
| Lock ownership and metadata atomicity tests | Partial |
| Timeout cleanup tests for verifier/retry worker lifecycle | Partial |
| Idempotency and budget regression tests | Partial |
| Statistical regression tests for default-path hotfixes | Partial |

## Finding Matrix

| Finding | Reproducer | Fixed surface | Direct test |
|---------|------------|---------------|-------------|
| `retry_timeout_worker_masks_system_exit` | Forked timeout worker catches `BaseException` and converts control-flow exits into generic runtime payloads. | `src/polisyos/scientist/engine/retry.py` | `tests/scientist/engine/test_retry.py::test_timeout_worker_does_not_swallow_system_exit` |
| `local_pool_worker_failure_swallow` | Local worker-pool runner catches broad worker errors instead of surfacing them through the future contract. | `src/polisyos/scientist/engine/runner/local_pool.py` | `tests/scientist/engine/runner/test_worker_pool.py::test_worker_runtime_error_surfaces_on_future` |
| `redis_lock_probe_swallow` | Redis liveness/stale probes fall through broad handlers and silently report `False` without observable degraded semantics. | `src/polisyos/scientist/engine/locks/redis_lock.py` | `tests/scientist/engine/locks/test_redis_lock.py::test_is_alive_returns_false_on_runtime_probe_error`; `tests/scientist/engine/locks/test_redis_lock.py::test_detect_stale_returns_false_on_runtime_probe_error` |
| `dynamodb_lock_probe_swallow` | DynamoDB liveness/stale probes and heartbeat extension use broad handlers that hide backend runtime failures. | `src/polisyos/scientist/engine/locks/dynamodb_lock.py` | `tests/scientist/engine/locks/test_dynamodb_lock.py::test_is_alive_runtime_probe_error_returns_false`; `tests/scientist/engine/locks/test_dynamodb_lock.py::test_detect_stale_runtime_probe_error_returns_false` |
| `llm_fallback_router_broad_failover_catch` | Endpoint failover catches broad runtime failures and hides the degraded path behind silent state mutation. | `src/polisyos/scientist/llm/fallback_router.py` | `tests/scientist/llm/test_fallback_router.py::test_failover_emits_degraded_path`; `tests/scientist/llm/test_fallback_router.py::test_keyboard_interrupt_is_not_swallowed` |
| `provider_verification_artifact_load_swallow` | Invalid provider-verification JSON degrades through a broad handler instead of typed load semantics. | `src/polisyos/scientist/llm/provider_verification.py` | `tests/scientist/llm/test_provider_verification.py::test_load_provider_verification_invalid_json_returns_none` |
| `provider_verification_named_check_swallow` | Smoke-check wrapper catches all exceptions, including programmer errors, and converts them into failed checks. | `src/polisyos/scientist/llm/provider_verification.py` | `tests/scientist/llm/test_provider_verification.py::test_run_named_check_does_not_swallow_assertion_errors` |

## Current Blocking Themes

- The full finding-to-reproducer matrix is not yet captured in one acceptance artifact.
- Some fixes exist in code, but their Phase 0 closure evidence is still scattered across separate tests and modules; the table above is only the beginning of the required ledger.
- Statistical validity fixes need a more explicit acceptance ledger before Phase 0 can be declared done.

## Signoff Rule

Phase 0 is accepted only when every listed criterion has:

1. Code landed on the target surface.
2. At least one direct reproducer or regression test.
3. A repo-tracked reference to the acceptance evidence.
4. A CI or release gate that prevents silent regression.
