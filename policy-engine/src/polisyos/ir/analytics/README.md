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
`BoundSoundnessLevel` is exposed through this curated analytics facade alongside `BoundMethod` and `BoundsBundle`; it records the declared soundness grade and does not independently establish that grade.


| Entrypoint                                                                                             | Use when                                                                                 | Defined in                                                   |
| ------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| `polisyos.ir.analytics.CausalEffectReport`                                                             | Use the canonical causal effect report with diagnostics and refutations                  | [`causal.py`](./causal.py)                                   |
| `polisyos.ir.analytics.TransportabilityResult`                                                         | Use the result of a transportability/domain-shift analysis                               | [`transportability.py`](./transportability.py)               |
| `polisyos.ir.analytics.HTEResult`                                                                      | Use heterogeneous treatment effects and targeting outputs                                | [`hte.py`](./hte.py)                                         |
| `polisyos.ir.analytics.StructuralCausalModelSpec`                                                      | Use the IR contract for a structural causal model                                        | [`structural_causal_model.py`](./structural_causal_model.py) |
| `polisyos.ir.analytics.recourse_manifold.InterventionCostManifold`, `OptimalRecourseInterventionQuery` | Use the proof-carrying causal recourse surface rather than an explainability-only report | [`recourse_manifold.py`](./recourse_manifold.py)             |
| `polisyos.ir.analytics.StrategicSCM`, `StrategicResponseBundle`, `MeanFieldEquilibriumCertificate`     | Use the strategic-response/performative-analysis surface, including MFG certificates     | [`strategic.py`](./strategic.py)                             |
| `polisyos.ir.analytics.DoWhyGraphBridge`, `EconMLDesignBridge`                                         | Use interoperability bridges for external causal toolchains                              | [`ecosystem_bridges.py`](./ecosystem_bridges.py)             |

## HTE successor artifacts

The selected-profile `HTEOutcome` union links a point candidate or a
profile-qualified native mean interval to its method result, execution
evidence, owner anchor, and physical source-materialization binding. The
point-result artifact stores a selected-row CATE vector when interval inference
is absent or cannot be represented by the legacy interval contract. An admitted
interval uses the existing `HTEResult` 1.0 artifact as its sole vector and
interval carrier, paired with `ATEInferenceBasis`; its original ordered and
point-containment validation remains in force. Native bounds that violate that
contract are retained as rejected inference evidence beside the valid point,
never clamped or recentered.

The materialization binding proves physical array positions, values, and row
order for the selected payload. The current HTE input contract does not map
requested variable identifiers to those arrays, so semantic outcome/treatment
identity, measurement units, query meaning, and population scope remain
unestablished. These artifacts are candidate evidence, not publication
authority or a claim of population coverage.

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

`StructuralCausalModelSpec` defaults to schema 1.2, matching the current
selected producer, schema snapshot and reflection catalog. A selected
`fit_method="gcm"` model requires source-bound training rows and observed
worker provenance. Schema 1.2 fitted `gcm` and `native_hybrid` models also
retain the complete source graph and typed projection disposition. Schema
versions and graph receipts do not establish source custody, graph truth, or
causal authority by themselves.

The current reader directly accepts schema 1.0 and 1.1 and preserves each
artifact's manifest and payload version; it does not migrate historical bytes
or upgrade their backend claims. Historical manifests without a payload version
remain schema 1.0. Older strict 1.0/1.1 readers do not declare forward
compatibility with schema 1.2 artifacts. Historical/manual replay should use
its recorded schema profile explicitly when constructing or rewriting an
artifact.

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
exact ordered draw payload, and content-binds the payload to its source reference. The source owner
refuses parameter/coordinate sets whose stable scalar names collide, rather than
silently overwriting one coordinate; unambiguous scalar, vector, and tensor names retain their
existing spelling.
The adapter persists this summary against selected `scientist.method_evidence`; a fresh reader resolves
the selected manifest profile and recomputes summary fields from the source draw bytes. It reports
weights as not supplied, parameter units as not established, and `gate_eligible=False`. This does
not replace the legacy `summarize_bayesian_calibration_posterior()` path, alter
`UncertaintyEnvelope`, or authorize calibration, causal, or policy conclusions.
The native MethodJob producer returns persisted mean and median summary refs.
The default uncertainty consumer still uses `UncertaintyEnvelope`; selecting a
summary role and binding its parameters to an evaluator requires an owner mapping.

The source parser now accepts only the existing canonical `foundry.bayesian.draws.v1`
format: its six declared source fields, exact layout and exact array records. It has no
weighted or extension-field encoding. Unknown fields, including otherwise benign extension
metadata previously ignored by this reader, now refuse this typed unweighted law profile;
generic artifact inspection remains available. This is an explicit narrowing of permissive
source intake, not a new wire profile or a claim that every historical extra field was invalid.

Source admission freezes one canonical byte string and hashes and decodes those same bytes.
Both `joint_row_values()` and the actual Monte Carlo consumer use a detached recomputed
projection for numerical source values, rows and the named point. Equal-valued substitutions in a caller's mutable
dictionary, or changes to the original source dictionary after capture, cannot supply the
executed law merely by passing ordinary model equality.

Selected evidence provenance has a separate boundary. The fresh
`load_persisted_posterior_summary` adapter resolves the actual store/ref and
requested evidence view (the explicitly selected profile when supplied, otherwise
the default view), the corresponding result edge and credible-mass diagnostic
**at read time**.
The standalone Monte Carlo API has no store; its copied
`source_method_evidence_ref`/profile and linkage of credible mass to that evidence
remain `consumer_asserted` for a direct input or one mutated after that read.
Numerical source reconstruction does not independently verify those linkages.

The remaining provenance boundary is assigned to the existing S3 selected-store/ref
reader-to-consumer wrapper route, using an independently selected ref/context. Its
concrete falsifiers are UNRUN: change an already-read model's well-formed evidence
ref/profile before consumption; or change credible mass from 0.9 to 0.8 for source rows
`(0, 1, 2, 3)`, whose finite bounds remain `[0,3]`, without changing the selected
evidence diagnostic. The wrapper must refuse or re-resolve those changes before
any effect and consume only that independently revalidated selection. This route
has not established S3/B31, E-M1, G acceptance or closure.

The profile-1.1 owner parser derives the entire scalar coordinate set, exact source rows and
functionals from the frozen source payload before any owned summary write. A constructed,
truncated or subsequently mutated DTO cannot replace that denominator with its retained
entries. Construction and owner admission use the same non-recursive recomputation; fresh
selected-evidence readers still resolve the actual producer result/evidence view. Historical
ambiguous or incomplete summaries refuse when read. Valid unambiguous 1.1 meanings, the
historical 1.0 envelope route and generic envelope containment remain unchanged. These checks
do not establish units, mixing, ESS, calibration validity or policy authority.

The typed parameter projection is reconstructed from the admitted source components after
validation. Thus a CAN.2 JSON round-trip cannot replace retained IEEE draw values such as
signed zero with an equal-valued declaration before an explicit numerical consumer uses them.
This uses the existing exact base64 draw payload, not a second codec or a CAN.3 writer rollout.

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


## Source-bound HTE successor artifacts

The registered HTE successors (`causal.hte.causal_forest@2.0.0`,
`causal.hte.double_ml@2.0.0`, `causal.hte.meta_learner@2.0.0`, and
`causal.hte.forest_dr@2.0.0`) return a private writer-ready candidate. The
Scientist bridge joins that candidate to the Runtime-owned pre-output anchor,
selected method result/evidence, and resource-policy manifest before writing
profiled IR artifacts. The public discriminated `HTEOutcome` is candidate-only.

`HTEPointResult` owns the selected-row CATE vector when no admitted interval
exists. A point outcome carries that ref and an explicit reason when interval
inference is not requested, unsupported, unavailable, invalid, or unqualified.
An admitted native interval reuses `ir.hte_result@1.0` as the sole CATE-vector
and interval carrier, paired with `ATEInferenceBasis`; the strict v1
point-containment rule remains in force. If valid native bounds cannot be
represented by that contract, the producer keeps the valid point and persists
the raw rejected bounds in its inference basis instead of clamping or
recentering them. Native extraction is available only for the registered
EconML 0.17 CausalForestDML and ForestDR profiles. DML and MetaLearner remain
point-only. The legacy HTEResult model and method identities keep their prior
validation and payload contracts.

These artifacts preserve requested scope and guarantee separately from the
selected-row computation. An interval is conditional on the selected backend
profile and stated assumptions; it does not establish identification,
population coverage, measurement units, source authority, or publishability.
The optional `search_uncertainty_task_binding_ref` is preserved only when the
owner supplied and selected its typed CAS ref; it is never synthesized from an
identifier or caller label.

Use `load_hte_outcome`, `load_hte_point_result`, `load_hte_result_v2`,
`load_ate_inference_basis`, and `load_hte_refusal_diagnostic` for strict
profile-selected reads. The runtime summary is scalar-only; consumers resolve
full per-row values from the bounded point-result artifact when that content is
within their authorized read path.

## Phase-4 ABM owner admission

phase4_dynamics.py declares the four source-owned ABMResult tuples explicitly:
the ir.abm_result and polisyos.ir.ABMResult manifest identities, each at payload
versions 1.3 and 1.4. The shared analytics owner helper binds those rows to the
same strict ABMResult parser and identity-preserving consumer projection. The
existing FULL planning rule for outer schema 1.0 retains its exact note; it
does not admit an undeclared manifest schema version or payload representation.
The existing source-captured canonical profile callback and historical payload
bytes remain unchanged.

abm_bridge.py uses the same owner declaration and JSON admission path for
ABMAlignmentReport. Typed readers refuse unknown manifest history before
payload reads, while the generic JSON reader remains available for opaque
inspection. Resource references remain typed payload data and are not selected
through a central resource allowlist. These checks establish typed
representation admission, not resource existence, provenance, or authority.


## Phase-4 report and causal certificate owner admission

The dynamic microsimulation report, temporal graph certificate, and space-time
certificate use the shared analytics owner helper for both persistence and
typed reads. Each owner registers only the producer-selected 1.0 manifest and
embedded payload versions, with its existing FULL planning rule and exact
schema-registry note. A FULL planning rule does not grant typed access to an
undeclared payload version or outer schema version. Generic JSON inspection
remains available for opaque history.

The owner validates the actual declared schema_version field before CAS writes,
binds reads to the exact owner row and canonical profile, and returns the same
strict DTO type. References carried inside reports and certificates are
preserved as typed payload data; the owner does not enumerate resource IDs or
claim those resources exist.

## Native backtest reads

`load_backtest_report` refuses selected native trajectory reports because IR
cannot verify their Foundry execution. `load_backtest_report_candidate` admits
the typed report bytes for a higher-layer verifier; it is not an authority or
prediction-verification result. Scientist's guarded report reader performs the
native trajectory and workflow checks before its consumers use the report.
