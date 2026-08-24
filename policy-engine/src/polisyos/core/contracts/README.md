# Contracts (`polisyos.core.contracts`)

`core.contracts` is the typed ABI layer of PolicyOS. It defines the shared refs, request/response
models, and provenance payloads that let `fabric`, `foundry`, `scientist`, `lex`, `runtime`, and
`scholar` talk to each other without ad hoc JSON shapes.

## Role in System

- **Depends on:** `core.artifacts` for CAS-backed `ArtifactRef` and `polisyos.ir.registry.refs` for canonical analytics refs.
- **Used by:** runtime HTTP routes, control-plane orchestration, domain pipelines, and audit/provenance tooling.
- **Boundary function:** prevents each domain package from inventing its own incompatible payload schema.

## Key Concepts

- **Typed refs** - every artifact family uses explicit `kind` and `media_type` checks.
- **Runtime/control DTOs** - HTTP and orchestration payloads live here so routes stay thin.
- **Policy Design Case projections** - typed non-authoritative PDC views carry closeout truth,
  projection gaps, contested records, recourse pointers, deficits, and invariant summaries to API
  and generated-client consumers.
- **Universal Policy Design Case** - W6.A compilation-only PDC facets carry authority envelope,
  concept-spine refs, reuse evidence, audit surface, and candidate-to-authority boundaries before
  obligation/requirement compilers run.
- **Compatibility facades** - analytics refs that migrated into `polisyos.ir.registry.refs` still have stable re-export paths here.
- **Provenance payloads** - shared entity/agent/activity records keep audit and lineage data consistent.
- **Execution planning** - `execution_plan.py` carries preflight, evaluator, and reproducibility artifacts.
- **Bounded liveness** - `bounded_liveness.py` carries governed deadline and retry ceilings for finite producer waits.
- **Scientist artifacts** - scientist-specific refs include decision, checkpoint, sensitivity, stress, and calibration validation bundles.
- **Chronology proof contracts** - `chronology.py` defines the policy-free full-prefix wire
  algebra, owner-qualified native reconciliation, and typed retained limitations. It deliberately
  does not own native denominator completeness, acceptance, authority heads, or custody.

## Public API

Main ref families:

- `fabric.py`, `foundry.py`, `scientist.py`, `scholar.py`
- `trinity.py`, `compiler.py`, `lex.py`, `execution_plan.py`
- `runtime.py`, `control.py`, `cursor.py`
- `provenance.py`
- `bounded_liveness.py`
- `chronology.py` (re-exported from the admitted `polisyos.core` root facade)
- `policy_design_case_projection.py`
- `runtime.py` also exposes `UniversalPolicyDesignCase` and `UniversalAuthorityProfile`
  for the universal grammar compiler.
- compatibility facades: `backtest.py`, `causal.py`, `distributional.py`, `hte.py`, `uncertainty.py`

Notable current exports include `ExecutionPlanRef`, `PreflightReportRef`, `RunDetailsResponse`,
`DecisionValidityEnvelope`, `ProvenanceCoreRef`, and `CalibrationValidationBundleRef`.

## Current State

- Last updated: 2026-08-24
- The fixed `full_prefix_canon_json_0_2_0_sha256_256_v1` contract carries only commitment
  integrity. Family policy and authority remain outside the common header and verifier.
- `FullPrefixVerificationStatement` is compact audit data, not a self-validating receipt;
  consumers must replay `FullPrefixVerifier` over the referenced bundle bytes. Parsing the
  statement can never promote a verification result.
- The Universal Policy Design Case contract is now available for W6.A universal grammar compiler
  artifacts and audit surfaces.
- The bounded-liveness contract family now carries governed deadline and retry ceilings for runtime producer waits.
- The Policy Design Case projection contract is now a strict shared DTO for runtime/control
  responses, OpenAPI, and generated clients.
- `core.contracts` still acts as the stable import surface for runtime/control payloads while analytics refs continue to be re-exported for compatibility.
