# Temporal Path Semantics

Related reference: [Analytics IR](analytics.md), [IR Schema Catalog](schema-catalog.md).

Owner: `@ir-owners`, `@causal-owners`
Source of truth: `src/polisyos/ir/analytics/dynamic_regime.py`, `src/polisyos/ir/analytics/rough_path_semantics.py`, `tests/ir/analytics/test_phase_c_contracts.py`, `tests/ir/analytics/test_rough_path_semantics.py`

> Stage 4.1 contract lift for rough-path and irregular-sampling semantics.
> PolicyOS now distinguishes solver-family names from the causal path object
> actually being claimed, and requires theorem-carrying metadata before a
> rough/signature trajectory can be treated as semantically supported.

Freshness: 2026-04-20

## Why This Exists

`EffectTrajectoryBundle.path_representation` originally told us mostly which
numerical family produced a trajectory:

- `linear_sde`
- `ode`
- `discrete_replay`
- `neural_cde`
- `neural_sde`

That was enough for the first continuous-time runtime, but not for irregularly
sampled policy data. Under irregular sampling the crucial question is no longer
just "which solver ran" but:

- what path object is being claimed
- whether the lift/interpolation is adapted
- whether future leakage was ruled out
- whether the claim is about the represented path, the latent path, or only a
  signature-equivalence class

Stage 4.1 adds typed contracts for exactly that boundary.

## New Contract Surface

`TemporalPathRepresentation` now includes rough/signature families:

| Representation         | Intended object                                                 |
| ---------------------- | --------------------------------------------------------------- |
| `geometric_rough_path` | geometric rough lift of irregular observations                  |
| `cadlag_rough_path`    | jump-aware / càdlàg rough representation                        |
| `truncated_signature`  | signature/logsignature witness, not a generic latent-path claim |
| `hybrid_rough_event`   | hybrid rough-state + counting/intensity event representation    |

The corresponding proof artifact lives in
`polisyos.ir.analytics.rough_path_semantics.RoughPathInterventionCertificate`.
It records:

- `semantics_scope`
- `model_family`
- `topology`
- `graph_criterion`
- intervention type and filtration
- well-posedness and identification refs
- whether the final result is `identified`, `identified_representation_only`,
  `partially_identified`, or `blocked`

`EffectTrajectoryBundle` itself stays backward-compatible. Instead of adding new
top-level fields, rough/signature bundles may carry validated
`metadata["path_semantics"]`, normalized by
`TemporalPathSemanticsAttachment`. The attachment now points to a typed
`RoughPathInterventionCertificateRef`, so `proof_artifact_ref` can no longer
silently reference an arbitrary JSON blob.

## Safety Rules

PolicyOS treats rough/signature bundles conservatively.

- Missing `metadata["path_semantics"]` on a rough/signature representation is
  not silently accepted. The bundle remains `blocked_research`.

- Provided `path_semantics` metadata must be well-typed. Invalid scope claims
  fail validation instead of degrading silently.

- `latent_path` scope requires
  `lift_faithfulness_checked = true`. Representation-only claims may omit it.

- `truncated_signature` requires `lift_method = "logsignature"` together with
  an explicit `signature_level`.

- Rough/signature support additionally requires
  `interpolation_is_adapted = true`,
  `future_leakage_ruled_out = true`, and
  `sampling_ignorability_checked = true`.

This keeps Stage 4.1 honest: theorem-backed irregular path claims can now be
typed, but unsupported or underspecified claims are still machine-blocked.

## Disclosure Surface

Stage 4.1 now also exposes the claim scope explicitly at evaluation time.

- `EffectTrajectoryBundle.path_semantics_scope` returns whether a supported
  claim covers the `represented_path`, the `latent_path`, or only a
  `signature_equivalence_class`.

- `EffectTrajectoryBundle.path_semantics_disclosure_notes` gives a short
  machine-readable disclosure such as
  `claim_scope_limited_to_represented_path`.

- Temporal backtesting propagates these values into `gating_checks` so
  user-facing diagnostics do not flatten representation-only identification
  into latent-path claims.

## Runtime Posture

The new contract lift does **not** mean the existing temporal compiler executes
irregular-grid queries end to end today.

- `ContinuousTimeQuery(sampling_scheme="irregular_grid")` remains
  `blocked_research` at compile time.

- `neural_cde` and `neural_sde` remain research-gated in the temporal runtime.
- The new rough/signature path families are supportable only as proof-carrying
  bundle contracts, not yet as a general built-in execution backend.

This is deliberate. Stage 4.1 establishes the semantic and proof boundary first;
backend execution can expand later without weakening the contract.

## Validation

```bash
uv run pytest tests/ir/analytics/test_phase_c_contracts.py tests/ir/analytics/test_rough_path_semantics.py -q
PYTHONPATH=src:. uv run --extra ml python tools/diagnostics/generate_ir_reference_catalog.py
```
