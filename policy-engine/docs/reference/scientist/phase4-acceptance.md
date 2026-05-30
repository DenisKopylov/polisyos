# Scientist Phase 4 Acceptance

Related references: [Frontier runtime](frontier-runtime.md), [Remediation status](remediation-status.md).

Owner: `@scientist-owners`
Source of truth: `src/polisyos/scientist/{frontier_runtime.py,engine/**,search/**}`, `tests/unit/scientist/{test_checkpoint.py,test_frontier_runtime.py,integration/test_checkpoint_resume.py,search/test_benchmark_registry.py}`, and the cited Phase 4 regressions

This page is the repo-tracked acceptance surface for Task 5 of
`SCIENTIST_AUDIT_REMEDIATION_PLAN.md`. The closure claim is intentionally
strict: distributed execution is accepted only when checkpoint, ledger,
rollback, replay, and runner evidence agree on the same recovery contract, and
frontier methods remain explicitly feature-gated until offline evidence exists.

## Closure Matrix

| Workstream | Accepted surface                                                                                                                                                                               | Acceptance signal                                                                                                                                                                          |
| ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `WS-4A`    | `FileBudgetLedger` now persists a canonical multi-host mutation contract with `ledger_id`, `canonical_contract`, `coordination_mode`, `last_writer`, and a bounded `recent_mutations` journal. | Multiple ledger writers can coordinate through one shared revision stream while preserving writer provenance and bounded retention.                                                        |
| `WS-4A`    | Incremental checkpointing is the canonical path when a prior checkpoint exists and a bounded delta can be materialized from it.                                                                | `CheckpointArtifact.metadata.snapshot_mode`, `base_checkpoint_ref`, and `materialize_checkpoint_state(...)` reconstruct the full state without forcing full-state snapshots on every tier. |
| `WS-4A`    | Async fail-fast rollback emits saga compensation hooks before the restored tier state is returned.                                                                                             | `RollbackCompensationEvent` and `RollbackCompensationHook.on_tier_rollback(...)` keep rollback posture explicit and testable.                                                              |
| `WS-4A`    | Distributed failure handling is accepted only when local resume, distributed resume, merge-and-checkpoint, trace injection degradation, and unhealthy probes are all covered together.         | The failure matrix below ties each expected failure mode to a regression test.                                                                                                             |
| `WS-4B`    | Frontier rollout remains machine-readable through `FrontierRuntimeReport.capabilities[*].status`.                                                                                              | Every frontier capability resolves to one of `disabled`, `offline_gated`, `available_offline`, or `experimental_not_wired`.                                                                |
| `WS-4B`    | Frontier benchmark/eval assets are resolved through `BenchmarkRegistry` instead of ad hoc params.                                                                                              | `resolve_family_bundle(...)` and `require_promotion_evidence(...)` gate promotion on hidden-holdout and rotating-challenge evidence.                                                       |

## Distributed Failure Matrix

| Failure or recovery path                                                                          | Evidence                                                                                                                                                                                                                                                            |
| ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Incremental checkpoint delta materializes the full state                                          | `tests/unit/scientist/orchestration/engine/test_checkpoint.py::test_incremental_checkpoint_materializes_full_state`                                                                                                                                                                           |
| Checkpoint GC failure does not roll back an already committed checkpoint                          | `tests/unit/scientist/orchestration/engine/test_checkpoint.py::test_checkpoint_hook_gc_failure_does_not_rollback_commit_bookkeeping`                                                                                                                                                          |
| Async fail-fast rollback emits saga compensation before returning restored state                  | `tests/unit/scientist/orchestration/engine/test_async_executor_hardening.py::TestTierSavepoints::test_rollback_compensation_hook_receives_fail_fast_event`                                                                                                                             |
| Strict resume preserves merged parallel-tier state                                                | `tests/integration/scientist/test_checkpoint_resume.py::test_async_executor_parallel_tier_checkpoints_merged_state_for_resume`                                                                                                                                      |
| Resume uses local fallback only when the distributed runner cannot be built                       | `tests/integration/scientist/test_checkpoint_resume.py::test_resume_falls_back_to_local_runner_when_distributed_backend_is_configured`                                                                                                                              |
| Resume keeps the distributed runner on the canonical pruned-workflow path when available          | `tests/integration/scientist/test_checkpoint_resume.py::test_resume_uses_configured_distributed_runner_with_pruned_workflow`                                                                                                                                        |
| Temporal remote merge/checkpoint path completes end-to-end                                        | `tests/unit/scientist/orchestration/engine/runner/test_temporal_runner.py::test_temporal_runner_executes_remote_checkpoint_merge_activity`                                                                                                                                             |
| Ray remote merge/checkpoint path completes end-to-end                                             | `tests/unit/scientist/orchestration/engine/runner/test_ray_runner.py::test_ray_runner_executes_remote_checkpoint_merge_task`                                                                                                                                                           |
| Distributed tier merge persists cache entries and the non-default write set                       | `tests/unit/scientist/orchestration/engine/runner/test_distributed_tier.py::test_merge_and_checkpoint_tier_persists_cache_entry_and_non_default_write`                                                                                                                                 |
| Trace-carrier degradation stays observable instead of silently dropping distributed trace context | `tests/unit/scientist/orchestration/engine/runner/test_temporal_runner.py::test_temporal_inject_trace_carrier_records_degraded_path_on_runtime_error`, `tests/unit/scientist/orchestration/engine/runner/test_ray_runner.py::test_ray_runner_inject_trace_carrier_records_degraded_path_on_runtime_error` |
| Distributed runner probes fail closed into unhealthy status                                       | `tests/unit/scientist/orchestration/engine/runner/test_temporal_runner.py::test_temporal_health_check_returns_unhealthy_on_probe_error`, `tests/unit/scientist/orchestration/engine/runner/test_ray_runner.py::test_ray_runner_health_check_returns_unhealthy_on_probe_error`                             |
| Multi-host ledger provenance remains canonical and bounded                                        | `tests/unit/scientist/orchestration/engine/test_budget_middleware.py::{test_ledger_snapshot_exposes_canonical_multi_host_contract,test_ledger_journal_tracks_cross_host_mutation_provenance,test_ledger_journal_retention_stays_bounded}`                                              |

## Frontier Capability Matrix

| Status                   | Meaning                                                                                                                                         |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `disabled`               | The feature flag is off and the capability cannot affect runtime behavior.                                                                      |
| `offline_gated`          | The capability is wired enough to run offline, but it is still blocked until offline validation and benchmark refs are present.                 |
| `available_offline`      | The capability has the evidence required for offline evaluation, but it still cannot replace the baseline by default without explicit approval. |
| `experimental_not_wired` | The capability exists in the contract surface, but runtime wiring or eval support is intentionally incomplete.                                  |

## Frontier Evidence Surfaces

| Surface                 | Evidence                                                                                                                                                              |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Runtime rollout report  | `src/polisyos/scientist/orchestration/engine/frontier_runtime.py` and `tests/unit/scientist/search/test_frontier_runtime.py`                                                                           |
| Benchmark/eval registry | `src/polisyos/scientist/search/benchmark_registry.py`, `src/polisyos/scientist/search/registry_contracts.py`, and `tests/unit/scientist/search/test_benchmark_registry.py` |
| Runtime promotion gate  | `src/polisyos/scientist/nodes/builtins/decide/run_policy_blueprint_runtime.py`                                                                                        |

## Reproduce

```bash
uv run pytest tests/unit/scientist/orchestration/engine/test_budget_middleware.py -q
uv run pytest tests/unit/scientist/orchestration/engine/test_checkpoint.py tests/integration/scientist/test_checkpoint_resume.py -q
uv run pytest tests/unit/scientist/orchestration/engine/test_async_executor_hardening.py tests/unit/scientist/orchestration/engine/runner/test_temporal_runner.py tests/unit/scientist/orchestration/engine/runner/test_ray_runner.py tests/unit/scientist/orchestration/engine/runner/test_distributed_tier.py -q
uv run pytest tests/unit/scientist/search/test_frontier_runtime.py tests/unit/scientist/search/test_benchmark_registry.py -q
```

## Claim Discipline

- Distributed safety is accepted only when replay, resume, rollback, and runner degradation tests all remain green together.
- The file-backed ledger is accepted as the canonical shared-ledger contract only for deployments that honor the documented shared POSIX lock semantics.
- Frontier methods remain non-default even when `available_offline`; baseline replacement still requires explicit approval and evidence refs.
