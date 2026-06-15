# Run-Cost Enforcement Gate

Owner: `@runtime-owners`

W10.D adds authority-level enforcement on top of W2.C cost/degradation
telemetry. The runtime artifact is `quality_evidence/run_cost_gate.json` with
schema version `policyos.runtime.policy_design_case.run_cost_gate.v1`.

Source of truth:

- `src/polisyos/runtime/quality/cost_gate.py`
- `src/polisyos/runtime/quality/performance_budget.py`
- `tests/unit/runtime/quality/test_cost_gate.py`

## Semantics

The gate reads W2.C observations for provider API calls, tokens, compute-dollar
spend, embeddings/searches, wall-clock time, retries, and acquisition spend.
Thresholds come from governed run-cost policy records; hard blocking requires
an `authority_policy_ref`.

Production-like authority levels may emit typed blockers when a governed
blocking policy is exceeded. Research-like authority levels emit limitations
only, even for the same over-budget observations. Cost gates never downgrade
evidence quality or substitute for claim evidence.

## Surfaces

The scorecard gate is `policy_design_w10d_run_cost_gate`. Canary evidence
bundles persist `run_cost_gate.json` when the report can be built. The closeout
reader consumes the report as module-owned runtime evidence: blocker issues
block closeout, while research limitations surface as closeout limitations.

`performance_budget.run_cost_budget_policy_from_performance_budget()` can
project a governed `wall_clock_seconds` policy from canary performance budget
evidence without double-counting nested queue/execution phases when
`control.job_total` is present.
