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
- **Catalog-run profile** - `control.py` defines `CatalogRunProfile`, the typed selector for catalog execution profiles; the stable `polisyos.core.contracts` facade re-exports the same type.
- **Policy Design Case projections** - typed non-authoritative PDC views carry closeout truth,
  projection gaps, contested records, recourse pointers, deficits, and invariant summaries to API
  and generated-client consumers.
- **Universal Policy Design Case** - W6.A compilation-only PDC facets carry authority envelope,
  concept-spine refs, reuse evidence, audit surface, and candidate-to-authority boundaries before
  obligation/requirement compilers run.
- **Compatibility facades** - analytics refs that migrated into `polisyos.ir.registry.refs` still have stable re-export paths here.
- **Provenance payloads** - shared entity/agent/activity records keep audit and lineage data consistent.
- **Execution planning** - `execution_plan.py` carries preflight, evaluator, and reproducibility artifacts.
- **Execution source identity** - `foundry.py` carries the opt-in `FoundryExecutionInputBasis` and schema 1.4 `SimulationResult` source status. It binds one actual single-step Foundry request and selected source graph; it has no risk, unit, time-validity, refinement, or authority semantics. Feedback composition remains explicitly uncomposed.
- **Bounded liveness** - `bounded_liveness.py` carries governed deadline and retry ceilings for finite producer waits.
- **Scientist artifacts** - scientist-specific refs include decision, checkpoint, sensitivity, stress, and calibration validation bundles.
- **Chronology proof contracts** - `chronology.py` defines the policy-free full-prefix wire
  algebra, owner-qualified native reconciliation, and typed retained limitations. It deliberately
  does not own native denominator completeness, acceptance, authority heads, or custody.
- **Epoch-validity intake contracts** - `decision_validity.py` carries sealed pre-N9 subjects,
  persisted gate evidence, complete pending/completed batch receipts, and the exact persisted
  completion evidence used by downstream owners. Request DTOs never carry status, targets,
  verifier identity, or owner denominators.
- **Epoch-denominator reconciliation contracts** - `decision_validity.py` additively defines the
  exact Scientist impact snapshot, cross-owner mapping receipt, write-once admission binding, and
  Runtime-independent reader port. Existing epoch-validity v1 DTOs retain their bytes and meaning.
- **Scope-adjudication candidates** - `scope_adjudication.py` content-binds one candidate,
  one custody plane, the ratified rule, validity/knowledge times, and the three ordered four-way
  predicate observations. Every artifact is `candidate_only`, has no authority or closure effect,
  and names the unappointed predicate resolver and claim-lifecycle consumer. It is not a scope
  ruling, publication authorization, or claim-head command.

## Public API

`polisyos.core.contracts` also exposes Fabric's `data_snapshot_reference_fields()` and
`data_snapshot_reference_input_roles(field_name)` through the stable lazy facade; both names retain
the function objects owned by `fabric.py`.

It also exposes `acquisition_native_coordinate_role(kind)` through the stable lazy facade. The
typed role is derived from the existing epoch codec registry; `AcquisitionArtifactCodec` retains
its existing six-field tuple shape and constructor behavior.

`polisyos.core.contracts.__all__` expands the chronology export tuple and every
declared symbol resolves through the defining contract module. Wildcard imports
retain the same class objects as explicit imports, including CausalFrontier and
DecisionPacket contracts. The native namespace test derives its checks from the
complete declared surface.

Main ref families:

- `fabric.py`, `foundry.py`, `scientist.py`, `scholar.py`
- `scholar.py` owns the persisted Scholar knowledge-bundle payload, enrichment report, and enrichment result DTOs alongside request/ref/freshness contracts.
  The Scholar root facade re-exports the three persisted/report DTOs. Former deep-module class FQNs are retired and unsupported; this does not establish whether external old-FQN pickle use exists. The persisted JSON contract remains unchanged.
- `trinity.py`, `compiler.py`, `lex.py`, `execution_plan.py`
- `foundry.py` includes the opt-in source-basis artifact/ref alongside existing compile and execute DTOs.
- `runtime.py`, `control.py`, `cursor.py`
- `provenance.py`
- `bounded_liveness.py`
- `chronology.py` (re-exported from the admitted `polisyos.core` root facade)
- `epoch.py` also publishes `epoch_canon_info()` so epoch-frame producers persist the profile of the exact canonical codec.
- `decision_validity.py` (including the typed epoch-batch intake and pre-N9 gate evidence)
- `policy_design_case_projection.py`
- `runtime.py` also exposes `UniversalPolicyDesignCase` and `UniversalAuthorityProfile`
  for the universal grammar compiler.
- compatibility facades: `backtest.py`, `causal.py`, `distributional.py`, `hte.py`, `uncertainty.py`

Notable current exports include `ExecutionPlanRef`, `PreflightReportRef`, `RunDetailsResponse`,
`ControlJobResponse` (the existing control-job DTO used by normative-evidence intake),
`DecisionValidityEnvelope`, `ProvenanceCoreRef`, and `CalibrationValidationBundleRef`.

## Current State

- Last updated: 2026-08-24
- `FoundryExecutionInputBasis` is an identity-only artifact emitted by selected-profile opt-in. `SimulationResult` schema 1.4 distinguishes `single_step_basis` from `feedback_uncomposed`; the latter has no single-step basis. Neither label establishes risk meaning, refinement, unit, valid time, currentness, or authority.
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
- The scope-adjudication candidate contract preserves the absence of its production resolver and
  consumer as typed limitations; no production orchestration or public/audit surface is appointed.
- `ValueOuterSet.lower`/`upper` remain identification bounds. Optional
  `statistical_lower`/`statistical_upper` preserve source-reported statistical uncertainty as a
  separate descriptive channel; those fields do not change identification, comparison, or
  promotion decisions and do not establish an estimand/unit binding or authority.
- The epoch-impact snapshot and reconciliation sidecar contracts are public and content-bound.
  Runtime now produces and exact-reads the relation, and Scientist consumes it through an explicit
  write-once admission port. The capability remains `implemented_but_not_orchestrated`: no
  production verifier, provider, or reconciliation reader is appointed.
- `core.contracts` still acts as the stable import surface for runtime/control payloads while analytics refs continue to be re-exported for compatibility.


## Owned artifact-schema descriptors for source-bound Foundry inputs

The typed source reader compares each selected manifest's `artifact_schema` with the exact descriptor owned by the model producer. The descriptor travels as `ARTIFACT_SCHEMA_NAME` and `ARTIFACT_SCHEMA_VERSION` on these existing model owners; it is not a new central schema registry. The current source-bound quantity uses: `DataSnapshot` 0.2.0; `ProgramGraph` and `ExecPlan` 0.2.0; `FoundryExecutionInputBasis` 1.0; `SimulationResult` 1.4 for a captured single-step basis (legacy 1.3 remains distinct); `FoundryInputBindings`, `FeedbackConfig`, and `ParameterOverrideBundle` 1.0; `StateDelta` and `Metrics` 0.1.0; `TrinityBundle` 1.0; and `PolicyCandidateSchema` 1.0.

These values identify serialization contracts. They do not establish risk meaning, units, a refinement relation, valid time/currentness, issuer authority, or historical supersession. Missing schema on a legacy ID-only reference remains unqualified; no old profile is inferred or backfilled. `ProgramGraph.schema_version` (0.2) is its model field and remains distinct from the artifact-manifest version (0.2.0).

The same typed owner models declare literal `ARTIFACT_KIND` and `ARTIFACT_MEDIA_TYPE` values. The B161 source reader checks both the caller's typed ref and the exact selected manifest against those owner values before decoding bytes. Parent-edge resolution for `WelfareBundle.simulation_result` and `SimulationResult.state_delta` supplies the expected model owner explicitly; it does not treat a kind or media type read from the manifest as its own expected value. Wrong-kind or wrong-media aliases with unchanged bytes, schema, canonical profile, and lineage are refused. These serialization descriptors prove source type identity only; they add no risk, authority, unit, time, or refinement claim. The Ukraine DataSnapshot writer passes its owner media type through the existing `_cas_put_json(media_type=...)` option; its `application/json` default remains unchanged for other callers.

## Semantic epoch owner statement readback

`load_verified_epoch_statement` applies the owner profile to `epoch.semantic_manifest` and
`epoch.production_receipt`: exact kind and media type, absent artifact schema, and the declared
`epoch_canon_info()` Core profile. It decodes the selected/default CAS view through the existing
Core canonical-profile reader, then checks the content-addressed single frame. Semantic manifests
carry no direct CAS input edges; production receipts carry exactly the `epoch_production_input`
edges derived by the producer's shared seven-field contract helper, including each direct ref's
selected-profile digest. `owner_denominator_receipt_refs` remain payload-level verification evidence
for the owner consumer and are not promoted into the direct CAS edge set. A ref without
`manifest_profile_sha256` selects the actual default manifest and is returned unchanged; that view
is accepted when the manifest declares `epoch_canon_info()`. A historical owner manifest missing
Core CanonInfo still raises `CanonicalProfileRefusalError`. The reader neither adds a selector nor
restamps a manifest. This contract does not validate owner-denominator evidence or resolve child refs.
Core CanonInfo checks serialization conformance only; it does not apply an IR law or make a receipt
a native history, currentness, or authority claim.

