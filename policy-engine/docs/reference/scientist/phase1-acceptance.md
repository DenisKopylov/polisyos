# Scientist Phase 1 Acceptance

Related references: [Scientist Reliability Scorecard](reliability-scorecard.md), [Scientist Remediation Status](remediation-status.md).

Owner: `@scientist-owners`
Source of truth: `tools/ci/check_scientist_phase1_gate.py`, `ops/ci/templates/workflows/perf.yml`, `tests/integration/scientist/test_workflow_reliability_scenarios.py`, and the cited Phase 1 regressions on this page

This page is the repo-tracked acceptance surface for the Phase 1 reliability
baseline. Phase 1 is closed only when error semantics, deterministic mutation,
operational evidence, and runtime benchmarks are all enforced by one published
gate story.

## Scope

- `WS-1A` error semantics and degraded-mode policy
- `WS-1B` atomic state mutation, merge semantics, deterministic execution
- `WS-1C` observability, metrics exporter, operational hygiene
- `WS-1D` test and benchmark program

## Exit Criteria

- Critical runtime slices no longer use broad `except Exception` handlers for operational control flow.
- Allowed degraded paths emit structured degraded envelopes plus observable metrics/events.
- Partial mutation failures do not leave half-written state behind.
- Merge conflict and resume semantics are explicit and regression-covered.
- Reliability scenarios, operational signals, and runtime benchmarks remain green together.
- The gate blocks on broad handlers in its selected critical files, missing required JUnit evidence, or missing required reliability and benchmark evidence.
- The full Scientist `model_copy(deep=True)` syntax inventory is a nonblocking diagnostic. It does not classify live hot paths or prove copy necessity, runtime cost, or performance.

## Required State and Mutation Evidence

The gate requires every case in `branch_state_tranche` from
`tools/ci/check_scientist_phase1_gate.py`; these five named JUnit cases are the
blocking state and mutation coverage. It also requires all three
`machine_readable_status` and all fourteen `error_semantics_tranche` case names
declared by that same source of truth.

| Mechanism | Required test | Production source exercised |
| --- | --- | --- |
| Calibration config nested-model ownership | `test_apply_to_config_uses_branch_local_nested_model_clones` in `tests/unit/scientist/methods/autotune/test_calibration_autotune.py` | `src/polisyos/scientist/methods/autotune/calibration.py` |
| Declared-output policy translation branching | `test_policy_translation_uses_branch_state_for_declared_outputs` in `tests/unit/scientist/nodes/builtins/decide/test_policy_translation.py` | `src/polisyos/scientist/nodes/builtins/decide/run_policy_translation.py` |
| Declared-output translator-compliance branching | `test_translator_compliance_uses_branch_state_for_declared_outputs` in `tests/unit/scientist/nodes/builtins/decide/test_policy_translation.py` | `src/polisyos/scientist/nodes/builtins/decide/run_translator_compliance.py` |
| Workflow runner snapshot isolation | `test_workflow_runners_use_branch_local_snapshot_state` in `tests/unit/scientist/orchestration/workflows/test_builder_pinning.py` | `src/polisyos/scientist/orchestration/workflows/builder.py` |
| Budget ledger copy-on-write mutation | `test_ledger_mutation_uses_copy_on_write_budget_state` in `tests/unit/scientist/orchestration/engine/test_budget_middleware.py` | `src/polisyos/scientist/orchestration/engine/budget.py` |

The scorecard also requires these seven benchmark operation families, whose
records come from `tests/performance/test_scientist_runtime_paths.py`:

| Operation | Accepted benchmark test name(s), at least one per operation |
| --- | --- |
| Node-chain latency | `test_scientist_node_chain_latency` |
| Checkpoint I/O | `test_scientist_checkpoint_io_hot_path`, `test_scientist_async_checkpoint_io_hot_path` |
| State serialization | `test_scientist_state_serialization_hot_path` |
| State branching/copy | `test_scientist_state_branch_hot_path` |
| Fan-out merge | `test_scientist_fan_out_merge_hot_path` |
| Failure-index search | `test_scientist_failure_index_search_hot_path` |
| Pareto search | `test_scientist_search_pareto_hot_path` |

The gate checks the supplied JUnit names against their required cases and requires
at least one supplied benchmark name for each operation in the scorecard mapping.
It does not establish which source/backend produced the reports or compare
benchmark timings to a numeric threshold. The CI command below runs the selected
test and benchmark suites; its successful execution remains a separate input to
the gate.

The diagnostic `deep_copy_scan` enumerates visible `src/polisyos/scientist/**/*.py`
files except `src/polisyos/scientist/orchestration/engine/state_branching.py` and
`src/polisyos/scientist/remediation_status.py`, and reports literal copy calls,
unresolved syntax candidates, and any unreadable or unparseable members. The
measurement receipt carries the discovered denominator and scan completeness.
An incomplete diagnostic remains unresolved and does not change the acceptance
verdict. A zero-finding result is not evidence that a runtime hot path is absent.

## Required Evidence

| Evidence                                               | Current posture                                                                                                                                                                           |
| ------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Closure list for the critical broad-handler slice      | Present via `tools/ci/check_scientist_phase1_gate.py` ratchet targets and direct regressions in the agent, cross-graph, autotune, and funnel lanes                                        |
| Degraded-path metrics and structured-envelope evidence | Present via decision-packet, governance, executor, fan-out, router, fallback-router, and provider-verification regressions plus `emit_degraded_path(...)` usage across the accepted slice |
| Mutation-plan and merge-conflict regressions           | Present via executor/fan-out/checkpoint/workflow-entrypoint/translation/autotune regressions                                                                                              |
| Trace correlation and metrics exporter tests           | Present via `tests/unit/scientist/orchestration/engine/test_reliability_operational_evidence.py`                                                                                                                    |
| E2E reliability scenario suite                         | Present via `tests/integration/scientist/test_workflow_reliability_scenarios.py`                                                                                                          |
| Runtime benchmark evidence                             | Present via `tests/performance/test_scientist_runtime_paths.py` and `tools/ci/check_scientist_phase1_gate.py`                                                                             |
| Repo-tracked automation anchor                         | Present via `ops/ci/templates/workflows/perf.yml` for reliability/benchmark evidence and `tools/ci/check_scientist_phase1_gate.py` for the closure verdict                                |

## Accepted Error-Semantics Surfaces

| Closure area                                                                                                                                   | Evidence                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| ---------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Governance failures emit structured degraded envelopes                                                                                         | `tests/unit/scientist/governance/test_validation_pipeline.py::test_failing_pass_returns_structured_error_envelope`                                                                                                                                                                                                                                                                                                                                                                |
| Tool-loop budget/memory degradation and malformed tool-call parsing stay observable                                                            | `tests/unit/scientist/agent/tools/test_tool_loop.py::{test_budget_probe_failure_is_reported_as_degraded_event,test_persistent_memory_recall_failure_is_reported_as_degraded_event,test_malformed_arguments_json}`                                                                                                                                                                                                                                                                 |
| Corrupted checkpoint metadata raises typed errors                                                                                              | `tests/unit/scientist/orchestration/engine/test_checkpoint.py::{test_checkpoint_head_invalid_json_raises_typed_error,test_checkpoint_history_invalid_json_raises_typed_error}`                                                                                                                                                                                                                                                                                                                         |
| Gateway catalog parsing, fallback routing, and provider verification distinguish degraded runtime failures from programmer/control-flow errors | `tests/unit/scientist/llm/test_gateway_client_retry.py::{test_list_model_ids_invalid_json_degrades_to_empty_list,test_list_model_ids_invalid_shape_degrades_to_empty_list}`, `tests/unit/scientist/llm/test_fallback_router.py::{test_failover_emits_degraded_path,test_keyboard_interrupt_is_not_swallowed}`, `tests/unit/scientist/llm/test_provider_verification.py::{test_load_provider_verification_invalid_json_returns_none,test_run_named_check_does_not_swallow_assertion_errors}` |
| Agent runtime tranche no longer swallows assertion-style helper failures                                                                       | `tests/unit/scientist/agent/test_data_need_extractor.py`, `tests/unit/scientist/agent/test_norm_loader.py`, `tests/unit/scientist/agent/test_drafter_factory.py`, `tests/unit/scientist/agent/test_drafter_formatting.py`, `tests/unit/scientist/agent/test_router.py`, `tests/unit/scientist/agent/test_supervisor.py`, `tests/unit/scientist/agent/test_rag_index.py`, `tests/unit/scientist/agent/test_code_verifier.py`                                                                                                            |
| Cross-graph/autotune/funnel helper tranche no longer broad-swallows assertion-style failures                                                   | `tests/unit/scientist/cross_graph/test_cross_graph_evidence.py`, `tests/unit/scientist/cross_graph/test_gatherers.py`, `tests/unit/scientist/autotune/test_execution_plan_autotune.py`, `tests/unit/scientist/search/funnel/test_level2_causal.py`                                                                                                                                                                                                                                                           |

## Accepted Mutation and Resume Surfaces

| Closure area                                                                                              | Evidence                                                                                                                                                                                                                                                                                                                                                                                                                                |
| --------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Declared write-path branching isolates caller state                                                       | `tests/unit/scientist/orchestration/engine/test_engine_executor_v0.py::test_executor_branch_state_isolates_declared_nested_writes`                                                                                                                                                                                                                                                                                                                                |
| Fan-out no longer commits partial merged state on fail-fast paths                                         | `tests/unit/scientist/orchestration/engine/test_fan_out.py::test_stop_on_failure_does_not_commit_partial_merged_state`, `tests/unit/scientist/orchestration/engine/test_fan_out_async.py::test_async_stop_on_failure_does_not_commit_partial_merged_state`                                                                                                                                                                                                                    |
| Summary persistence degradation happens after staged merge without rolling state back                     | `tests/unit/scientist/orchestration/engine/test_fan_out.py::test_summary_persist_failure_emits_degraded_event`, `tests/unit/scientist/orchestration/engine/test_fan_out_async.py::test_async_summary_persist_failure_emits_degraded_event`                                                                                                                                                                                                                                    |
| Resume enforces repair-or-fail checkpoint reconciliation                                                  | `tests/unit/scientist/orchestration/engine/test_checkpoint.py::{test_resolve_latest_checkpoint_repairs_history_when_head_is_newer,test_resolve_latest_checkpoint_rejects_head_history_conflict,test_resolve_latest_checkpoint_rejects_divergent_latest_history_entries,test_resolve_latest_checkpoint_rejects_head_artifact_metadata_mismatch}`                                                                                                                   |
| Distributed resume/merge/checkpoint path is explicit and regression-covered                               | `tests/integration/scientist/test_checkpoint_resume.py`, `tests/unit/scientist/orchestration/engine/runner/test_activity_worker.py::test_run_merge_checkpoint_tier_in_worker_restores_checkpoint_contract`, `tests/unit/scientist/orchestration/engine/runner/test_temporal_runner.py::test_temporal_runner_executes_remote_checkpoint_merge_activity`, `tests/unit/scientist/orchestration/engine/runner/test_ray_runner.py::test_ray_runner_executes_remote_checkpoint_merge_task`             |
| Workflow entrypoints, translation nodes, and calibration meta overrides use bounded branch-local mutation | `tests/unit/scientist/orchestration/workflows/test_builder_pinning.py::test_workflow_runners_use_branch_local_snapshot_state`, `tests/unit/scientist/nodes/builtins/decide/test_policy_translation.py::{test_policy_translation_uses_branch_state_for_declared_outputs,test_translator_compliance_uses_branch_state_for_declared_outputs}`, `tests/unit/scientist/autotune/test_calibration_autotune.py::test_apply_to_config_uses_branch_local_nested_model_clones` |
| Budget ledger updates retain copy-on-write state ownership                                                | `tests/unit/scientist/orchestration/engine/test_budget_middleware.py::test_ledger_mutation_uses_copy_on_write_budget_state`                                                                                                                                                                                                                                                                                                               |
| Full Scientist explicit deep-copy syntax inventory                                                       | Reported as a nonblocking diagnostic by `tools/ci/check_scientist_phase1_gate.py`; it does not classify hotness, necessity, or cost                                                                                                                                                                                                                                                                                                       |

## Gate Command

Phase 1 closure is enforced by:

```bash
uv run pytest \
  tests/unit/scientist/facade/test_remediation_status.py \
  tests/unit/scientist/governance/test_reliability_scorecard.py \
  tests/unit/scientist/orchestration/engine/test_reliability_operational_evidence.py \
  tests/integration/scientist/test_workflow_reliability_scenarios.py \
  tests/unit/scientist/agent/test_data_need_extractor.py \
  tests/unit/scientist/agent/test_norm_loader.py \
  tests/unit/scientist/agent/test_drafter_factory.py \
  tests/unit/scientist/agent/test_drafter_formatting.py \
  tests/unit/scientist/agent/test_router.py \
  tests/unit/scientist/agent/test_supervisor.py \
  tests/unit/scientist/agent/test_rag_index.py \
  tests/unit/scientist/cross_graph/test_cross_graph_evidence.py \
  tests/unit/scientist/cross_graph/test_gatherers.py \
  tests/unit/scientist/autotune/test_execution_plan_autotune.py \
  tests/unit/scientist/autotune/test_calibration_autotune.py \
  tests/unit/scientist/search/funnel/test_level2_causal.py \
  tests/unit/scientist/agent/test_code_verifier.py \
  tests/unit/scientist/nodes/builtins/decide/test_policy_translation.py \
  tests/unit/scientist/orchestration/engine/test_budget_middleware.py \
  tests/unit/scientist/orchestration/workflows/test_builder_pinning.py \
  -q --junitxml=_build/.tmp/test-reports/scientist-phase1.xml

uv run pytest \
  tests/performance/test_scientist_runtime_paths.py \
  --benchmark-only \
  --benchmark-json=_build/.tmp/test-reports/scientist-phase1-benchmarks.json \
  --benchmark-warmup=on \
  --benchmark-min-rounds=5 \
  -q

uv run python tools/ci/check_scientist_phase1_gate.py \
  --benchmark-json _build/.tmp/test-reports/scientist-phase1-benchmarks.json \
  --junit-xml _build/.tmp/test-reports/scientist-phase1.xml \
  --output _build/.tmp/test-reports/scientist-phase1-gate.json \
  --output-format json \
  --require-passing
```

## Signoff

Phase 1 is accepted. The repo-tracked reliability scorecard, direct workstream
regressions, mutation/error-semantic ratchets, operational evidence, and
runtime-path benchmarks now agree on one enforced closure contract.
