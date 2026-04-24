# Latent Discovery Producer Paths

Freshness: 2026-04-20
Owner: `@scientist-owners`, `@causal-owners`
Source of truth: `src/polisyos/scientist/discovery/latent_producers.py`, `src/polisyos/scientist/latent_separation.py`
Research rationale: Phase 2 stages `9.1` and `9.2` in `docs/archive/plans/CAUSAL_ENGINE_RESEARCH_RESULT_PLAN.md`

## Purpose

The discovery runtime now contains automatic producer paths for the two Phase 2
latent tracks that were previously only represented as contracts and governance
consumers:

- Stage `9.1`: theorem-backed latent-cardinality production for the narrow
  `ME-LiNGLaH-S` / `ME-LiNGLaH-S-Int` envelope.

- Stage `9.2`: automatic latent-separation input assembly and deterministic
  diagnostic recomputation from structured upstream evidence blocks.

The producers run during `CausalDiscoveryReport -> GraphHypothesis`
normalization, before latent merge, governance, readiness, and judge-stack
evaluation.

## Metadata Contracts

`LatentDiscoveryBundle.metadata` may now carry the following machine-readable
keys:

- `latent_cardinality_evidence`
  - typed `LatentCardinalityEvidencePayload`
  - producer input for Stage `9.1`
- `latent_cardinality_failure_reasons`
  - normalized fail-closed reason strings emitted by the Stage `9.1` producer
- `separation_diagnostic_inputs`
  - typed `LatentSeparationDiagnosticInputs`
  - raw Stage `9.2` payload used for deterministic recomputation
- `separation_diagnostics`
  - normalized diagnostic output derived from `separation_diagnostic_inputs`

Backwards compatibility is preserved:

- `LatentDiscoveryBundle` keeps the same public top-level fields.
- legacy `separation_diagnostics_inputs` / `latent_separation_inputs` are still
  accepted as aliases for the new canonical key.

## Supported Theorem Families

### Stage 9.1

The v1 producer is intentionally narrow.

- supported model class: `ME-LiNGLaH-S`
- moderator extension: `ME-LiNGLaH-S-Int` only
- required prerequisites for identified blocks:
  - localized environment shift
  - sufficient pure-child support
  - rank support for the claimed block size
  - minimal decomposition support
  - graph-placement support for confounder/mediator claims
  - interaction signature support for moderator claims

If any prerequisite is missing, the producer does not emit a stronger readiness
claim. It keeps the bundle `proof_only`, records
`latent_cardinality_failure_reasons`, and leaves human review mandatory.

### Stage 9.2

The producer accepts two input modes:

- raw `data` + `design`, which are recomputed with the existing numeric
  diagnostic path

- structured upstream evidence blocks
  - `measurement_block`
  - `proxy_block`
  - `environment_block`

The runtime remains fail-closed:

- `measurement_error`, `proxy_mismatch`, and `latent_confounding` are emitted
  only when the required blocks are present and non-conflicting

- `mixed` and `unresolved` remain the default when evidence is incomplete or
  contradictory

- trust may rise to `conditional` or `validated`, but readiness stays
  `proof_only`

## Non-goals

These producers do **not** do the following:

- widen latent readiness above `proof_only`
- make broad heuristic latent claims outside the declared theorem envelope
- treat identified marginals or separation labels as automatic promotion
- invent strong latent-cardinality conclusions when prerequisites are absent

Outside the supported class, the runtime is expected to remain
`research` / `proof_only` and to surface explicit missing-prerequisite reasons.
