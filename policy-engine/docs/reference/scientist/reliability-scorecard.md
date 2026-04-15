# Scientist Reliability Scorecard

Related reference: [Operations](../operations/index.md).

> Официальный gate для Scientist runtime после WS-1C / WS-1D: один документ,
> один набор обязательных сигналов, одна интерпретация готовности.

## Required Evidence

### Workflow Scenarios

- `happy_path`
- `tool_failure_with_retry`
- `checkpoint_resume`
- `governance_rejection`
- `fairness_calibration_regression`

### Benchmarks

- `node_latency`
- `checkpoint_io`
- `state_serialization`
- `state_copy`
- `fan_out_merge`
- `failure_index_search`
- `search_pareto`

### Operational Signals

- `metrics_exporter`
- `trace_correlation`
- `dlq_replay`
- `bounded_retention`
- `monitoring_alerts`

## Scoring

- Scenario pass rate: `passed scenarios / 5`
- Benchmark coverage rate: `available benchmark proofs / 7`
- Operational readiness rate: `healthy operational signals / 5`
- Weighted score: `0.5 * scenarios + 0.3 * benchmarks + 0.2 * operations`

`passes_all=true` only when every required scenario, benchmark, and operational
signal is present. Partial success is still reported as a weighted score, but it
does not qualify the runtime as production-ready.

## Source Of Truth

- Helper implementation: `polisyos.scientist.reliability_scorecard`
- CI scorecard builder: `tools/ci/check_scientist_reliability.py`
- E2E scenarios: `tests/scientist/integration/test_workflow_reliability_scenarios.py`
- Benchmarks: `tests/performance/test_scientist_runtime_paths.py`
- Operational evidence: `tests/scientist/test_reliability_operational_evidence.py`
- Operational monitor hooks: `polisyos.scientist.engine.operational_monitoring`
- CI workflow lane: `.github/workflows/perf.yml` (`scientist-gate2-evidence`)
