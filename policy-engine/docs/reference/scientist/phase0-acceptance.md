# Scientist Phase 0 Acceptance

Related references: [Scientist Remediation Status](remediation-status.md), [Phase 1 Acceptance](phase1-acceptance.md).

Owner: `@scientist-owners`
Source of truth: `tools/ci/check_scientist_phase0_gate.py` and the cited Phase 0 Scientist regressions on this page

This page is the repo-tracked acceptance surface for Phase 0 of
`SCIENTIST_AUDIT_REMEDIATION_PLAN.md`. Phase 0 is closed only when the code,
direct regressions, repo-tracked evidence, and the published gate command all
agree on the same containment contract.

## Scope

- `WS-0A` async, locking, lifecycle correctness
- `WS-0B` budget, request correctness, security, and scientific hotfixes

## Exit Criteria

- Critical async/lifecycle paths surface typed failures without masking control-flow exits.
- Worker pools, retries, verifier workers, and lock probes pass teardown regressions without stale permits or silent probe degradation.
- Request-attempt retries reuse stable idempotency keys and preserve deterministic idempotency inputs.
- Budget reservation accounting remains consistent across success, failure, cancellation, and post-record reconciliation.
- Masking bypasses fail closed with typed validation errors.
- Foundry TEE env propagation sanitizes and restores environment state.
- Default-path statistical hotfixes keep direct regression coverage.

## Required Evidence

| Evidence                                                   | Current posture                                                                                                                                                         |
| ---------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Fault-injection tests for sibling/runtime failure surfaces | Present via `tests/unit/scientist/engine/test_retry.py`, `tests/unit/scientist/engine/runner/test_worker_pool.py`, and lock probe regressions                                     |
| Concurrency and permit-accounting regressions              | Present via `tests/unit/scientist/engine/runner/test_worker_pool.py` and `tests/unit/scientist/llm/test_budget_enforcer.py::test_parallel_calls_do_not_overspend_reserved_budget` |
| Lock ownership, heartbeat, and metadata atomicity coverage | Present via `tests/unit/scientist/engine/locks/test_fcntl_lock.py`, `test_lock_metrics.py`, `test_dynamodb_lock.py`, and `test_redis_lock.py`                                |
| Timeout cleanup and worker lifecycle regressions           | Present via `tests/unit/scientist/engine/test_retry.py::test_timeout_worker_does_not_swallow_system_exit`                                                                    |
| Idempotency and budget regression pack                     | Present via `tests/unit/scientist/llm/test_gateway_client_retry.py`, `tests/unit/scientist/engine/test_idempotency.py`, and `tests/unit/scientist/llm/test_budget_enforcer.py`                |
| Statistical hotfix regressions for the default path        | Present via `tests/unit/scientist/backtesting/test_bootstrap.py`, `test_ipw.py`, `test_distributional.py`, and `tests/unit/scientist/search/test_cheap_stage_autotune.py`         |
| Repo-tracked gate command                                  | Present via `tools/ci/check_scientist_phase0_gate.py`; any live CI wiring for this evidence is operational/manual rather than versioned under `.github/workflows/`      |

## Acceptance Matrix

| Closure area                                                                                            | Evidence                                                                                                                                                                                                                                                                                                                        |
| ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Retry timeout worker keeps control-flow exits visible                                                   | `tests/unit/scientist/engine/test_retry.py::test_timeout_worker_does_not_swallow_system_exit`                                                                                                                                                                                                                                        |
| Local worker-pool runtime failure surfaces through the future contract                                  | `tests/unit/scientist/engine/runner/test_worker_pool.py::test_worker_runtime_error_surfaces_on_future`                                                                                                                                                                                                                               |
| Lock metrics wrapper no longer swallows assertion-style failures                                        | `tests/unit/scientist/engine/locks/test_lock_metrics.py::test_measure_acquire_does_not_swallow_assertion_errors`                                                                                                                                                                                                                     |
| DynamoDB and Redis stale/liveness probes fail closed instead of silently swallowing runtime faults      | `tests/unit/scientist/engine/locks/test_dynamodb_lock.py::test_detect_stale_runtime_probe_error_returns_false`, `tests/unit/scientist/engine/locks/test_redis_lock.py::test_detect_stale_returns_false_on_runtime_probe_error`                                                                                                            |
| Gateway retries reuse one request-attempt idempotency key                                               | `tests/unit/scientist/llm/test_gateway_client_retry.py::test_retry_after_header_and_idempotency_key_are_reused`                                                                                                                                                                                                                      |
| Gateway calls without retry budget still get a stable idempotency key                                   | `tests/unit/scientist/llm/test_gateway_client_retry.py::test_idempotency_key_is_added_even_without_retry_budget`                                                                                                                                                                                                                     |
| Engine-level idempotency input hashing remains deterministic and artifact-sensitive                     | `tests/unit/scientist/engine/test_idempotency.py::test_compute_idempotency_key_stable_for_same_inputs`, `test_compute_idempotency_key_changes_on_artifact_change`                                                                                                                                                                           |
| Budget reservations are released on runtime error or cancellation and reconcile actual-vs-reserved cost | `tests/unit/scientist/llm/test_budget_enforcer.py::{test_releases_reservation_when_generate_raises,test_releases_reservation_when_task_is_cancelled,test_actual_cost_commit_reconciles_estimate_delta,test_post_record_falls_back_to_reserved_cost_when_accounting_breaks}`                                                          |
| Parallel budget reservations cannot overspend the reserved budget                                       | `tests/unit/scientist/llm/test_budget_enforcer.py::test_parallel_calls_do_not_overspend_reserved_budget`                                                                                                                                                                                                                             |
| Masking fails closed on missing targets and invalid horizons                                            | `tests/unit/scientist/backtesting/test_masking.py::{test_masking_raises_when_target_metric_is_missing,test_masking_raises_when_intervention_step_exceeds_metric_horizon}`                                                                                                                                                            |
| Foundry TEE environment values are sanitized and restored                                               | `tests/unit/scientist/adapters/test_foundry_bridge.py::{test_rejects_control_characters_in_env_values,test_sets_and_restores_sanitized_env_values}`                                                                                                                                                                                  |
| RMSE CI, Ljung-Box, IPW, and Spearman tie handling stay regression-covered                              | `tests/unit/scientist/backtesting/test_bootstrap.py::test_rmse_ci_bootstraps_rmse_directly`, `tests/unit/scientist/backtesting/test_distributional.py::test_iid_data`, `tests/unit/scientist/backtesting/test_ipw.py::test_equal_propensity`, `tests/unit/scientist/search/test_cheap_stage_autotune.py::test_spearman_uses_average_ranks_for_ties` |

## Gate Command

Phase 0 closure is enforced by:

```bash
uv run pytest \
  tests/unit/scientist/engine/test_retry.py \
  tests/unit/scientist/engine/runner/test_worker_pool.py \
  tests/unit/scientist/engine/locks/test_fcntl_lock.py \
  tests/unit/scientist/engine/locks/test_lock_metrics.py \
  tests/unit/scientist/engine/locks/test_dynamodb_lock.py \
  tests/unit/scientist/engine/locks/test_redis_lock.py \
  tests/unit/scientist/llm/test_gateway_client_retry.py \
  tests/unit/scientist/engine/test_idempotency.py \
  tests/unit/scientist/llm/test_budget_enforcer.py \
  tests/unit/scientist/backtesting/test_masking.py \
  tests/unit/scientist/adapters/test_foundry_bridge.py \
  tests/unit/scientist/backtesting/test_bootstrap.py \
  tests/unit/scientist/backtesting/test_ipw.py \
  tests/unit/scientist/backtesting/test_distributional.py \
  tests/unit/scientist/search/test_cheap_stage_autotune.py \
  -q --junitxml=_build/.tmp/test-reports/scientist-phase0.xml

uv run python tools/ci/check_scientist_phase0_gate.py \
  --junit-xml _build/.tmp/test-reports/scientist-phase0.xml \
  --output _build/.tmp/test-reports/scientist-phase0-gate.json \
  --output-format json \
  --require-passing
```

## Signoff

Phase 0 is accepted. The repo-tracked code, direct reproducer tests, acceptance
ledger, and published gate command now agree that the remaining Task 0
containment work is closed.
