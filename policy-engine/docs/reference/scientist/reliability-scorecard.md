# Scientist Reliability Scorecard

Related reference: [Operations](../operations/index.md).

Owner: `@scientist-owners`
Backup owner: `@platform-owners`
Source of truth: `src/polisyos/scientist/reliability_scorecard.py`, `tools/ci/check_scientist_reliability.py`, `tools/ci/check_scientist_phase0_gate.py`, `tools/ci/check_scientist_phase1_gate.py`, `tools/ci/check_scientist_phase2_ratchet.py`, `tests/unit/scientist/governance/test_reliability_scorecard.py`, and `tests/tools/test_scientist_reliability_gate.py`

> Owner lane: `L6 Scientist`  
> Type: Manual reference (not generated).  
> Source of truth: `src/polisyos/scientist/reliability_scorecard.py`, `tools/ci/check_scientist_reliability.py`, `tools/ci/check_scientist_phase0_gate.py`, `tools/ci/check_scientist_phase1_gate.py`, `tools/ci/check_scientist_phase2_ratchet.py`, `tests/unit/scientist/governance/test_reliability_scorecard.py`, and `tests/tools/test_scientist_reliability_gate.py`.

The Scientist reliability scorecard is the repo-tracked gate for runtime
readiness. The canonical helper is
`build_scientist_reliability_scorecard(...)`, and the canonical evidence-based
builder is `build_scientist_reliability_scorecard_from_evidence(...)`.

## Required Evidence Sets

### Scenarios

| Scorecard key                     | Required passing test case(s)                                                       |
| --------------------------------- | ----------------------------------------------------------------------------------- |
| `happy_path`                      | `test_linear_scientist_workflow_happy_path`                                         |
| `tool_failure_with_retry`         | `test_linear_scientist_workflow_tool_failure_retries_and_succeeds`                  |
| `checkpoint_resume`               | `test_linear_scientist_workflow_checkpoint_resume_skips_completed_nodes`            |
| `governance_rejection`            | `test_linear_scientist_workflow_governance_rejection_stops_decision_publication`    |
| `fairness_calibration_regression` | `test_linear_scientist_workflow_post_deploy_regression_triggers_alerts_and_reissue` |

### Benchmarks

| Scorecard key          | Required benchmark name(s)                                                             |
| ---------------------- | -------------------------------------------------------------------------------------- |
| `node_latency`         | `test_scientist_node_chain_latency`                                                    |
| `checkpoint_io`        | `test_scientist_checkpoint_io_hot_path`, `test_scientist_async_checkpoint_io_hot_path` |
| `state_serialization`  | `test_scientist_state_serialization_hot_path`                                          |
| `state_copy`           | `test_scientist_state_branch_hot_path`                                                 |
| `fan_out_merge`        | `test_scientist_fan_out_merge_hot_path`                                                |
| `failure_index_search` | `test_scientist_failure_index_search_hot_path`                                         |
| `search_pareto`        | `test_scientist_search_pareto_hot_path`                                                |

### Operational Signals

| Scorecard key       | Required passing test case(s)               |
| ------------------- | ------------------------------------------- |
| `metrics_exporter`  | `test_metrics_exporter_operational_signal`  |
| `trace_correlation` | `test_trace_correlation_operational_signal` |
| `dlq_replay`        | `test_dlq_replay_operational_signal`        |
| `bounded_retention` | `test_bounded_retention_operational_signal` |
| `monitoring_alerts` | `test_monitoring_alerts_operational_signal` |

## Scoring Rules

Current score computation in `ScientistReliabilityScorecard`:

- scenario pass rate = passed scenarios / 5
- benchmark coverage rate = available benchmark proofs / 7
- operational readiness rate = healthy operational signals / 5
- weighted score = `0.5 * scenario_pass_rate + 0.3 * benchmark_coverage_rate + 0.2 * operational_readiness_rate`
- `passes_all=true` only when no scenario, benchmark, or operational gaps remain

Missing evidence is recorded as:

- `scenario_missing:<name>`
- `benchmark_missing:<name>`
- `operational_gap:<name>`

## Gate Mapping

| Gate                                         | Current role                                                                                                                    |
| -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `tools/ci/check_scientist_reliability.py`    | Builds the scorecard from benchmark JSON plus JUnit XML evidence.                                                               |
| `tools/ci/check_scientist_phase0_gate.py`    | Separate Phase 0 acceptance barrier for async/lifecycle, idempotency, budget, masking, env hardening, and statistical hotfixes. |
| `tools/ci/check_scientist_phase1_gate.py`    | Phase 1 barrier that embeds the reliability scorecard and adds error-semantics/branch-state ratchets.                           |
| `tools/ci/check_scientist_phase2_ratchet.py` | Maintainability debt ratchet for selected Scientist hot paths.                                                                  |

## Minimum Evidence Build Commands

```bash
uv run pytest tests/integration/scientist/test_workflow_reliability_scenarios.py \
  --junitxml=_build/.tmp/test-reports/scientist-reliability-scenarios.xml -q

uv run pytest tests/unit/scientist/engine/test_reliability_operational_evidence.py \
  --junitxml=_build/.tmp/test-reports/scientist-reliability-operational.xml -q

uv run pytest tests/performance/test_scientist_runtime_paths.py \
  --benchmark-only \
  --benchmark-json=_build/.tmp/test-reports/scientist-runtime-benchmarks.json \
  --benchmark-warmup=on \
  --benchmark-min-rounds=5 \
  -q

uv run python tools/ci/check_scientist_reliability.py \
  --benchmark-json _build/.tmp/test-reports/scientist-runtime-benchmarks.json \
  --junit-xml _build/.tmp/test-reports/scientist-reliability-scenarios.xml \
  --junit-xml _build/.tmp/test-reports/scientist-reliability-operational.xml \
  --output-format json \
  --require-passing
```

## Validation

```bash
uv run pytest tests/unit/scientist/governance/test_reliability_scorecard.py tests/tools/test_scientist_reliability_gate.py -q
```
