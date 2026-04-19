# Scientist Governance Passes
Related explanation: [Governance Model](../../explanation/governance-model.md).

Owner: `@scientist-owners`
Backup owner: `@platform-owners`
Source of truth: `src/polisyos/scientist/governance/pass_registry.py`, `src/polisyos/scientist/governance/pass_entrypoints.py`, `src/polisyos/scientist/governance/pipeline.py`, `pyproject.toml` entry points for `polisyos.scientist_governance_passes`, and `tests/scientist/governance/**`

> Owner lane: `L6 Scientist`  
> Type: Manual reference (not generated).  
> Source of truth: `src/polisyos/scientist/governance/pass_registry.py`, `src/polisyos/scientist/governance/pass_entrypoints.py`, `src/polisyos/scientist/governance/pipeline.py`, `pyproject.toml` entry points for `polisyos.scientist_governance_passes`, and `tests/scientist/governance/**`.

All registry-loaded governance validators implement
`validate(ctx: PassContext) -> list[ComplianceIssue]`. The default registry is
the union of:

1. `pyproject.toml` entry points under `polisyos.scientist_governance_passes`;
2. builtin fallback factories from `pass_entrypoints.py` when no entry points
   are discovered or when a builtin name was not supplied by a plugin.

## Pipeline Semantics

| Source | Current behavior |
|---|---|
| `ValidationPipeline` | Sorts selected passes by `estimated_cost_ms`, records telemetry for the pipeline and each pass, and optionally short-circuits on the first blocker according to `ValidationProfile.short_circuit_on_blocker`. |
| Pass execution failure | A pass exception becomes a blocker `ComplianceIssue` with code `PASS_EXECUTION_ERROR`, and the degraded-path envelope is recorded in telemetry. |
| `runtime_profile(...)` | Trims an offline/full profile to the runtime-safe pass id subset listed below. |

## Registered Builtin/Entry-Point Passes

These 19 passes are the current builtin registry surface exposed by
`load_governance_passes()`:

| `pass_id` | Class | Estimated cost ms | Runtime allowed |
|---|---|---:|---|
| `budget` | `BudgetPass` | 5 | No |
| `checkpoint` | `CheckpointPass` | 20 | No |
| `confidence` | `ConfidencePass` | 50 | Yes |
| `cross_graph_evidence` | `CrossGraphEvidencePass` | 25 | Yes |
| `equity` | `EquityPass` | 25 | Yes |
| `freshness` | `FreshnessPass` | 15 | No |
| `human_review_required` | `HumanReviewRequiredPass` | 50 | Yes |
| `legal` | `LegalPass` | 100 | No |
| `literature_gate` | `LiteratureGatePass` | 30 | Yes |
| `normative_arbitration` | `NormativeArbitrationPass` | 20 | Yes |
| `pii_check` | `PIICheckPass` | 10 | Yes |
| `privacy` | `PrivacyPass` | 20 | No |
| `quality` | `QualityGatePass` | 500 | No |
| `refutation` | `RefutationPass` | 10 | Yes |
| `safety` | `SafetyPass` | 25 | No |
| `schema` | `SchemaPass` | 15 | No |
| `strategic_response` | `StrategicResponsePass` | 20 | Yes |
| `sutva_check` | `SutvaCheckPass` | 20 | Yes |
| `transportability_required` | `TransportabilityRequiredPass` | 20 | Yes |

## Runtime-Allowed Subset

`runtime_profile()` currently preserves only:

- `confidence`
- `cross_graph_evidence`
- `equity`
- `human_review_required`
- `literature_gate`
- `normative_arbitration`
- `pii_check`
- `refutation`
- `strategic_response`
- `sutva_check`
- `transportability_required`

## Pass Classes That Exist But Are Not In The Default Registry

The repository also contains pass classes with dedicated tests that are not part
of the current default `load_governance_passes()` surface because they are not
registered in `pyproject.toml` and are not returned by
`builtin_governance_pass_factories()`:

| Class module | Current status |
|---|---|
| `passes/citation_validator_pass.py` | Pass class exists and has tests, but is not currently entry-point/builtin registered. |
| `passes/rate_limiter_pass.py` | Pass class exists and has tests, but is not currently entry-point/builtin registered. |

This page intentionally documents the registry as it is loaded today, not every
pass-shaped class present in the tree.

## Phase Evidence

| D1 phase | Governance-facing evidence |
|---|---|
| Phase 0 | Fail-closed pipeline behavior, budget enforcement, and typed degraded envelopes. |
| Phase 1 | Workflow rejection behavior, observability, and structured governance traces. |
| Phase 3 | Accountability, calibration validation, fairness/escalation evidence, and decision-packet surfacing. |
| Phase 4 | Frontier governance/search capabilities remain non-default until rollout evidence exists. |

## Validation

```bash
uv run pytest tests/scientist/governance/test_pass_registry.py tests/scientist/governance/test_validation_pipeline.py tests/scientist/governance/test_validation_pipeline_observability.py -q
uv run pytest tests/scientist/governance/test_accountability.py tests/scientist/governance/test_calibration_validation.py -q
```

## Registry API

::: polisyos.scientist.governance.pass_registry

::: polisyos.scientist.governance.pass_entrypoints

::: polisyos.scientist.governance.pipeline
