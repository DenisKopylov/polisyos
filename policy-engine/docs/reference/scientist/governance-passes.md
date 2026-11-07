# Scientist Governance Passes

Related explanation: [Governance Model](../../explanation/governance-model.md).

Owner: `@scientist-owners`
Source of truth: `src/polisyos/scientist/governance/pass_registry.py`, `src/polisyos/scientist/governance/pass_entrypoints.py`, `src/polisyos/scientist/governance/pipeline.py`, `src/polisyos/scientist/nodes/builtins/governance/run_governance.py`, `src/polisyos/scientist/nodes/builtins/decide/run_policy_funnel_level5.py`, `src/polisyos/scientist/nodes/builtins/decide/decision_packet/validation.py`, `src/polisyos/scientist/nodes/builtins/planning/run_evaluator.py`, `pyproject.toml` entry points for `polisyos.scientist_governance_passes`, and `tests/unit/scientist/governance/**`
Source pin: `codex/docs-refresh-e02-20261014` at `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`.
Evidence level: the registry map and background reflect the inspected source pin. Human-gate behavior is covered by `tests/unit/scientist/orchestration/workflows/test_governance_evaluator_currentness.py`.

All registry-loaded governance validators implement
`validate(ctx: PassContext) -> list[ComplianceIssue]`. The registry loads installed entry points
from `polisyos.scientist_governance_passes` and supplies builtin fallbacks for names that were not
discovered as entry points. An entry point with a builtin name replaces that fallback; duplicate
runtime `pass_id` values fail registry loading. The table below is the complete builtin factory
mapping in `src/polisyos/scientist/governance/pass_entrypoints.py` (one Python file), alongside the
configured entry-point names in `pyproject.toml` (one TOML file). Installed plugins can add entries,
so a deployment's loaded registry may be larger than this builtin map.

## Pipeline Semantics

| Source                 | Current behavior                                                                                                                                                                                              |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ValidationPipeline`   | Sorts selected passes by `estimated_cost_ms`, records telemetry for the pipeline and each pass, and optionally short-circuits on the first blocker according to `ValidationProfile.short_circuit_on_blocker`. |
| Pass execution failure | A pass exception becomes a blocker `ComplianceIssue` with code `PASS_EXECUTION_ERROR`, and the degraded-path envelope is recorded in telemetry.                                                               |
| `runtime_profile(...)` | Trims an offline/full profile to the runtime-safe pass id subset listed below.                                                                                                                                |

The pipeline returns pass issues and a trace; it does not itself issue a policy signature or
establish publication authority. `ComplianceIssue` uses local `info`, `warning`, and `blocker`
severities. Unless an earlier `reject` or `human_gate` verdict takes precedence, a blocker makes
`RunGovernanceNode` report `reject`; a warning by itself does not become a universal
`review_required` state. Human review is a separate typed path: under `STRICT`,
`HumanReviewRequiredPass` emits an `info` issue with code
`HUMAN_REVIEW_REQUESTED`, and the node creates a separate review request and sets `human_gate`
unless the verdict is already `reject`. A typed decision for the governance gate does not resolve
the separate review request or establish reviewer authority.

The node persists a `GovernanceReport` and returns `NodeOutcome(status="ok")` even when the report
verdict is `reject` or `human_gate`. The node outcome describes successful execution and report
materialization; it is not the verdict. Consumers must inspect the report when their contract
requires a control effect. For example, `run_policy_funnel_level5.py` turns `reject` and
`human_gate` into a critical promotion vulnerability, and decision-packet validation adds a
human-review trigger for `human_gate`; `run_evaluator.py` reads the report verdict into its
iteration-evaluation path. The negative witness
`tests/unit/scientist/nodes/builtins/governance/test_run_governance_claims.py::test_governance_rejects_selected_workflow_with_decision_artifact_without_claims_ref`
asserts `outcome.status == "ok"` together with `report["verdict"] == "reject"`. These paths do not
prove that every DAG consumer enforces every verdict (`P01`, `P02`, `P05`).

Statuses such as `limited`, `contested`, and `review_required` belong to other local contracts;
severity or matching words do not compose them automatically. Claim publishability, monitor
validity, admission, and publication each have their own consumer-owned rules. The cross-axis
composition and owned warning lifecycle remain normative targets, not a universal property of this
pipeline (`P04`, `P09`).

## Builtin Registry Map

The builtin registry map contains the following entries at the evidence pin:

| `pass_id`                   | Class                          | Estimated cost ms | Runtime allowed |
| --------------------------- | ------------------------------ | ----------------: | --------------- |
| `budget`                    | `BudgetPass`                   | 5                 | No              |
| `causal_frontier_leakage`   | `CausalFrontierLeakagePass`    | 15                | Yes             |
| `checkpoint`                | `CheckpointPass`               | 20                | No              |
| `confidence`                | `ConfidencePass`               | 50                | Yes             |
| `cross_graph_evidence`      | `CrossGraphEvidencePass`       | 25                | Yes             |
| `equity`                    | `EquityPass`                   | 25                | Yes             |
| `fabric_trust`              | `FabricTrustGatePass`          | 50                | Yes             |
| `freshness`                 | `FreshnessPass`                | 15                | No              |
| `human_review_required`     | `HumanReviewRequiredPass`      | 50                | Yes             |
| `incentive_compatibility`   | `IncentiveCompatibilityPass`   | 40                | No              |
| `legal`                     | `LegalPass`                    | 100               | No              |
| `literature_gate`           | `LiteratureGatePass`           | 30                | Yes             |
| `normative_arbitration`     | `NormativeArbitrationPass`     | 20                | Yes             |
| `pii_check`                 | `PIICheckPass`                 | 10                | Yes             |
| `privacy`                   | `PrivacyPass`                  | 20                | No              |
| `quality`                   | `QualityGatePass`              | 500               | No              |
| `refutation`                | `RefutationPass`               | 10                | Yes             |
| `safety`                    | `SafetyPass`                   | 25                | No              |
| `schema`                    | `SchemaPass`                   | 15                | No              |
| `strategic_response`        | `StrategicResponsePass`        | 20                | Yes             |
| `sutva_check`               | `SutvaCheckPass`               | 20                | Yes             |
| `transportability_required` | `TransportabilityRequiredPass` | 20                | Yes             |

## Runtime-Allowed Subset

`runtime_profile()` preserves the following complete ID literal from
`src/polisyos/scientist/governance/pass_registry.py` (one Python file):

- `confidence`
- `causal_frontier_leakage`
- `cross_graph_evidence`
- `equity`
- `fabric_trust`
- `human_review_required`
- `literature_gate`
- `normative_arbitration`
- `pii_check`
- `refutation`
- `strategic_response`
- `sutva_check`
- `transportability_required`

## Examples Outside The Builtin Registry Map

The following pass-shaped classes have dedicated tests but do not appear in the builtin factory
mapping or the configured entry-point table. These are examples from the inspected files, not an
exhaustive inventory of every pass-shaped class in the repository:

| Class module                        | Current status                                                                        |
| ----------------------------------- | ------------------------------------------------------------------------------------- |
| `passes/citation_validator_pass.py` | Pass class exists and has tests, but is not currently entry-point/builtin registered. |
| `passes/rate_limiter_pass.py`       | Pass class exists and has tests, but is not currently entry-point/builtin registered. |

This page documents the pinned builtin map and its runtime extension rule; it does not claim to
enumerate plugin-provided passes in a deployed environment.

## Phase References

Phase and workstream labels are roadmap vocabulary, not evidence that every associated governance
capability is complete. Use the pinned implementation and consumer paths above to assess runtime
behavior.

## Incentive Compatibility

`IncentiveCompatibilityPass` reads declared mechanism claims from
`PolicySpec.mechanism_design.constraints` and routes them into the exact IC
verification service. Supported exact fragments currently include:

- `finite_exact` for finite direct mechanisms with explicit utilities
- `envelope_1d` for single-player one-dimensional direct mechanisms
- `cycmon_lp` for single-player multidimensional finite grids

The pass writes `scientist.ic_report`, `scientist.ic_certificate`, and
`scientist.ic_negative_certificate` artifacts into the run-local
`artifacts_index`. Positive certificates are semantic by default; runtime scope
requires a separate implementation-conformance report.

## Relevant Tests

The following test modules were inspected as source evidence; they were not run for this
documentation update.

```bash
uv run pytest tests/unit/scientist/governance/test_pass_registry.py tests/unit/scientist/governance/test_validation_pipeline.py tests/unit/scientist/governance/test_validation_pipeline_observability.py -q
uv run pytest tests/unit/scientist/governance/test_accountability.py tests/unit/scientist/governance/test_calibration_validation.py -q
uv run pytest tests/unit/scientist/governance/test_incentive_compatibility_pass.py tests/unit/scientist/governance/test_ic_verification.py -q
```

## Registry API

::: polisyos.scientist.governance.pass_registry

::: polisyos.scientist.governance.pass_entrypoints

::: polisyos.scientist.governance.pipeline
