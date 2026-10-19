# Analytics (`polisyos.ir.analytics`)

## Purpose

`polisyos.ir.analytics` defines the contract layer for analytical results:
causal effects, transportability, HTE, backtests, uncertainty, strategic
response, ecosystem bridges, and frontier causal contracts. The package is the shared
interchange format between `foundry`, `scientist`, `fabric`, and observation-driven
workflows.

The `polisyos.ir.analytics` package facade is intentionally narrower than the
full set of modules in `analytics/`: it re-exports the most common contracts, while
specialized surfaces remain in their defining modules.

## Where to Start

- [`__init__.py`](./__init__.py) — curated lazy facade for the most common analytics import paths.
- [`causal.py`](./causal.py) — core effect-report surface, diagnostics, and refutations.
- [`dynamic_regime.py`](./dynamic_regime.py) — continuous-time query contracts, trajectory bundles, and runtime support gates.
- [`hte.py`](./hte.py) — heterogeneous effects, feature importance, and targeting outputs.
- [`recourse_manifold.py`](./recourse_manifold.py) — typed causal recourse queries, intervention-cost manifolds, proof bundles, and feasibility certificates for Stage 13.4.
- [`rough_path_semantics.py`](./rough_path_semantics.py) — proof-carrying semantics for rough/signature path claims under irregular sampling.
- [`transportability.py`](./transportability.py) — transport between environments and gap diagnostics.
- [`privacy_transportability.py`](./privacy_transportability.py) — privacy-aware layer over transportability/recoverability for DP-distorted multi-domain releases.
- [`uncertainty.py`](./uncertainty.py) — uncertainty algebra, interval semantics, and propagation contracts.
- [`posterior_summary.py`](./posterior_summary.py) — versioned posterior mean/median, equal-tail
  bounds, exact source draw rows, and CAS persistence for candidate summaries.
- [`welfare.py`](./welfare.py) — WelfareBundle schema 1.1 nominal PE/post-GE
  component operands and WelfareSampleBundle schema 1.1 draw vectors, bound to
  the selected applied-weight manifest edge for fresh weighted recomputation.
- [`strategic.py`](./strategic.py) — strategic-response SCM, equilibria, and bundle outputs.
- [`ecosystem_bridges.py`](./ecosystem_bridges.py) — bridges to DoWhy, EconML, CausalNex, pgmpy, and related ecosystems.
- For upstream/downstream context, see [`../observation/README.md`](../observation/README.md) and [`../artifacts/README.md`](../artifacts/README.md).

## Public entrypoints

| Entrypoint                                                                                             | Use when                                                                                 | Defined in                                                   |
| ------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| `polisyos.ir.analytics.CausalEffectReport`                                                             | Use the canonical causal effect report with diagnostics and refutations                  | [`causal.py`](./causal.py)                                   |
| `polisyos.ir.analytics.TransportabilityResult`                                                         | Use the result of a transportability/domain-shift analysis                               | [`transportability.py`](./transportability.py)               |
| `polisyos.ir.analytics.HTEResult`                                                                      | Use heterogeneous treatment effects and targeting outputs                                | [`hte.py`](./hte.py)                                         |
| `polisyos.ir.analytics.StructuralCausalModelSpec`                                                      | Use the IR contract for a structural causal model                                        | [`structural_causal_model.py`](./structural_causal_model.py) |
| `polisyos.ir.analytics.recourse_manifold.InterventionCostManifold`, `OptimalRecourseInterventionQuery` | Use the proof-carrying causal recourse surface rather than an explainability-only report | [`recourse_manifold.py`](./recourse_manifold.py)             |
| `polisyos.ir.analytics.StrategicSCM`, `StrategicResponseBundle`, `MeanFieldEquilibriumCertificate`     | Use the strategic-response/performative-analysis surface, including MFG certificates     | [`strategic.py`](./strategic.py)                             |
| `polisyos.ir.analytics.DoWhyGraphBridge`, `EconMLDesignBridge`                                         | Use interoperability bridges for external causal toolchains                              | [`ecosystem_bridges.py`](./ecosystem_bridges.py)             |

`polisyos.ir.analytics.causal_capabilities.CausalIdentificationFamily.TRSO` names the executable
Y0 `identify_target_outcomes` operation. It is a capability label, not a result or authority
claim. Caller-supplied population profiles remain request context; population-indexed expressions
that the existing `EstimandAST` cannot preserve remain typed limitations. It adds an allowed enum
value to the capability contract without changing artifact structure or schema versions.

## Literature CAS selectors

`load_article_extraction_result()` and `load_literature_causal_prior()` normalize their
input at the artifact-store boundary to the shared `ArtifactSelector` contract. A plain
artifact-ID string, native `ArtifactID`, or exact single-field `RootModel[str]` is
validated as a scalar ID and selects the default manifest view; other root-model shapes
are refused. A complete artifact ref is normalized to a strict mapping that preserves
its selected manifest-profile digest. The loaders verify the selected manifest kind,
media type, and schema before reading the payload. This keeps legacy ID-only reads
available without dropping a caller-supplied selected view.

## Causal report CAS persistence

`persist_causal_effect_report` preserves historical default-reference behavior when `return_selected_profile` is omitted or `False`; the default view is profileless, while a write differing from that view may return its selected profile. Pass `True` when a downstream join must bind the exact profile selected by the report write; the typed helper returns that same-write CAS result and does not infer a profile from a later read. A non-boolean value is rejected, and stores without selected-profile write support fail closed. This option changes the reference returned to the caller, not the causal-report payload or schema.

## Structural model schema compatibility

`StructuralCausalModelSpec` defaults to schema 1.1, matching the selected GCM
producer, schema snapshot and reflection catalog. A selected `fit_method="gcm"`
model requires training rows and observed worker provenance; the schema version
alone does not establish source custody or causal authority. The existing
source-bound reader reopens the actual CAS source and validates that provenance.

Current readers also accept schema 1.0. They retain 1.0 when a historical CAS
manifest omits the payload version, rather than inheriting the new constructor
default. Historical/manual fixtures should declare `schema_version="1.0"`
explicitly when replaying that profile. Reading or rewriting them does not
create selected worker provenance. Old 1.0 readers are not declared compatible
with a new 1.1 producer.

## Twin result audit persistence

When `CausalEngine.run()` produces an actual `TwinNetworkResult` and has an
artifact store plus its typed `StructuralCausalModelSpec`, the audit path persists
the result through the IR artifact boundary and adds an optional
`EvidenceBundle.twin_network_result_ref`. Its lineage names the source view when
the SCM retains source-bound training rows, the persisted query/estimand AST, and
the persisted SCM. Each link retains the selected manifest profile. The persisted
proof trace carries the same typed result ref, so a fresh reader can follow the
proof bundle to the trace and then load the result through
`load_twin_network_result()`.

The persisted `ir.causal_evidence_bundle` schema keeps reference-free payloads
at version 1.0 and omits the new key entirely, preserving the strict legacy
shape. A bundle with `twin_network_result_ref` is written as schema 1.1. The
current loader accepts both versions through the selected manifest view, while
a 1.0 payload that contains the 1.1 field is rejected. Existing 1.0 artifacts
need no migration; strict 1.0 readers reject 1.1 at the schema-version
boundary and must be upgraded before consuming Twin-linked traces.
The writer refuses a noncanonical schema name before artifact emission, matching
the loader's fixed `ir.causal_evidence_bundle` identity.

The field remains optional in the domain model, so historical EvidenceBundle
payloads still load with `None`, and runs without a typed twin result or typed
SCM keep the existing audit behavior. This link records the output and its
persisted inputs; it does not establish source admission, model validity,
calibration, or causal authority.

## Causal result interval semantics

`CausalQueryResult` schema 1.2 and `TwinNetworkResult` schema 1.1 distinguish
fixed-model outcome/ITE distributions from conditional Gaussian posterior
credible intervals. Their historical `result_ci` / `ite_ci` fields carry central
quantile spans; they do not assert estimator confidence intervals. The current
shared uncertainty schema 1.1 represents ordinary distribution spans as a
non-gating `HEURISTIC_RANGE`, and exact model posteriors as non-gating
`CREDIBLE_INTERVAL`. This change does not ratify a new global uncertainty schema.

`CausalEstimatorInterval` separately records iid-observation-row resampling,
complete model refits, source/row/graph/target hashes, seeds, and replicate effect
estimates. Its confidence interval describes approximate sampling inference for
the fixed identified graph and declared iid law. Source custody and empirical
causal identification require separate admission. Fresh CAS readers preserve the
result kind; historical causal result schemas 1.0/1.1 and twin schema 1.0 remain
decodable as limited distributions and cannot inherit old CI/gating markers.

The public types `CausalResultKind` and `CausalEstimatorInterval` are available
from both `polisyos.ir` and `polisyos.ir.analytics`.
See [structural causal models](../../../../docs/reference/foundry/structural-causal-models.md)
for selected backend, historical replay and refit-bootstrap limitations.

## Posterior summary profile 1.1

`posterior_summary.py` defines a separate candidate artifact for source-reported Bayesian draws.
It keeps the selected posterior mean or median distinct from the equal-tail interval, retains the
exact ordered draw payload, and content-binds the payload to its source reference. The explicit HMC
adapter persists this summary against selected `scientist.method_evidence`; a fresh reader resolves
the selected manifest profile and recomputes summary fields from the source draw bytes. It reports
weights as not supplied, parameter units as not established, and `gate_eligible=False`. This does
not replace the legacy `summarize_bayesian_calibration_posterior()` path, alter
`UncertaintyEnvelope`, or authorize calibration, causal, or policy conclusions.
The native MethodJob producer returns persisted mean and median summary refs.
The default uncertainty consumer still uses `UncertaintyEnvelope`; selecting a
summary role and binding its parameters to an evaluator requires an owner mapping.

## Depends on / depended on by

- Depends on: [`../artifacts/README.md`](../artifacts/README.md), [`../world/README.md`](../world/README.md), [`../observation/README.md`](../observation/README.md), `polisyos.ir.kernel`.
- Depended on by: `polisyos.foundry.methods`, `polisyos.foundry.calibration`, `polisyos.scientist`, `polisyos.fabric`, `polisyos.core`.

## Common commands

Run from the repository root (`policy-engine/`).

Smoke-tested on `2026-04-17`.

```bash
uv run python -c "import polisyos.ir.analytics as analytics; from polisyos.ir.analytics import CausalEffectReport, HTEResult; print(len(analytics.__all__), CausalEffectReport.__name__, HTEResult.__name__)"
```

## Test/verification commands

Run from the repository root (`policy-engine/`).

Conceptual in this README refresh; run these targeted analytics checks before
landing IR result-contract changes.

```bash
uv run pytest tests/unit/ir/analytics/test_shared_invariants.py tests/unit/ir/analytics/test_estimand_normalization.py tests/unit/ir/test_uncertainty.py tests/unit/ir/test_frontier_causal_contracts.py -q
uv run pytest tests/unit/ir/test_interoperability_bridges.py -q
```

## Reference docs

- Mean-field path now uses three typed artifacts in [`strategic.py`](./strategic.py):
  `MeanFieldPerturbationSpec` compiles `InterventionSpec` into coefficient/distributional/mixed MFG perturbations, `MeanFieldMacroSimulationConfig` records replayable Fabric numerics, and `MeanFieldEquilibriumCertificate` is the audit leaf referenced by `StrategicResponseBundle.mfg_equilibrium_ref`.

- Stage 13.4 causal recourse lives in [`recourse_manifold.py`](./recourse_manifold.py):
  `InterventionCostManifold` defines the quotient cost geometry, `OptimalRecourseInterventionQuery`
  is the kernel-facing query contract, and the proof/feasibility/planning bundles carry the
  identify-or-bound and solver outputs.

- [IR analytics reference](../../../../docs/reference/ir/analytics.md)
- [Temporal path semantics reference](../../../../docs/reference/ir/temporal-path-semantics.md)
- [IR interoperability reference](../../../../docs/reference/ir/interoperability.md)
- [IR schema catalog](../../../../docs/reference/ir/schema-catalog.md)
- [IR root README](../README.md)
- [Observation README](../observation/README.md)
- [Artifacts README](../artifacts/README.md)

## Last updated

`2026-04-20`

## Selected social-weight manifests

`persist_social_weight_manifest()` and `ensure_social_weight_manifest_artifact()`
retain the legacy profile behavior by default. A producer that must bind a
WelfareBundle social-weight role to the exact manifest profile selected by the
write can pass `return_selected_profile=True`; stores without that write result
fail closed. This ref is a source-role identity only. The sampled welfare vector
is separately persisted as `ir.welfare_weights` and is verified against both
producer-persisted nominal operands and raw Monte Carlo component draws; a
social-weight manifest is not treated as the applied vector.
For the existing one-component `[1.0]` fallback, the source-basis welfare
producer writes that same value as a selected-profile artifact; ordinary legacy
calls keep the old no-ref fallback.

## Candidate causal value projection

`CausalEffectReport` declares the existing Foundry output-contract shape and
provides `to_value_uncertainty()` for a typed `NativeValueEstimandBinding`. The
projection preserves a successful method's native point estimate and statistical
confidence interval as a non-gating causal interval. It returns no interval for a
refused report, heuristic CI, or binding that does not match the report's typed
method output. The projection is not a causal-identification, calibration, owner,
or production-currentness finding. Its JSON schema is unchanged because the
contract declaration and projector are class-level/runtime behavior, not report
fields.

The runtime's B31 candidate path keeps invocation lineage outside the public
CausalEffectReport ABI: an N8 run-basis v2 joins the selected request, a
producer-captured execution receipt, and exact report bytes. The receipt does
not grant causal identification, owner authority, calibration, or production
currentness; the report schema and public exports remain unchanged.

## Transport proof purpose and review grade

`proof_bundle_from_transportability_result()` is the shared result-to-proof projection. It preserves the typed transport status and carries a `TransportabilityProofReviewGrade`. A scoped Y0 direct operation remains an identified mathematical candidate with unresolved source-data predicates and `review_required`; every other result is `unknown` until a source-resolved, content-bound, verifier-provenance basis is available. Native and simplified backend labels alone do not produce `NO_ADDITIONAL_REVIEW` or clear the protected pass. The projection keeps an identified theorem/AST visible but marks the candidate `sound_incomplete`; it does not establish data authority. The ProofBundle schema remains unchanged while the typed purpose and migration semantics are considered in the open G decision packet.

## ABM execution-source projection

The candidate Core-to-IR bridge preserves `execution_input_basis_ref` and
`execution_source_status` from the complete `SimulationResult` JSON payload.
The IR reference has its own neutral type and retains artifact ID, kind, media
type, and selected manifest profile. A basis ref is not a source admission or
authority receipt. Current strict readers accept the historical missing fields
as `None` / `not_recorded`; they validate the copied Core 1.4 status/basis/feedback
constraints when those fields are present.

Three existing version coordinates remain distinct in this candidate: the
payload `schema_version` is copied from Core, the IR reflection default is 1.3,
and `persist_abm_result` still uses the outer `ir.abm_result` artifact schema 1.0.
The typed projection repairs conversion; it does not adjudicate those version
namespaces. Old strict readers may reject the extra fields. Upgrade readers
before emitting those fields into their persisted input stream, preserve
historical bytes, and regenerate and inspect ABI snapshots/catalogs.

The publication alternatives and required independent G decision are recorded in
[the E02 ABM version packet](../../../../docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/decisions/r1237-abm-version-namespace-and-reader-migration-proposal-20261013.md).
This candidate is not a declaration of production rollout or a completed
compatibility window.
