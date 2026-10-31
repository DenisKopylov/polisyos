# Causal Catalog (`polisyos.foundry.methods.catalog.causal`)

`methods/catalog/causal` - canonical causal-method family for discovery,
estimation, transportability, policy learning, diagnostics and strategic response.

## Purpose

Use this package when a Foundry or Scientist workflow needs a registered causal
method, estimator, diagnostic, or graph-discovery helper. The package is a
catalog family, not a public subsystem facade: stable access flows through
method registration, the exported causal names in `__init__.py`, and the
broader `polisyos.foundry.methods` facade.

Temporal `CausalEngine` results retain the legacy `effect_bundle_artifact_id` and
also carry `effect_bundle_artifact_ref`, the exact selected profile returned by
the producer's bundle write. Fresh consumers should use that full reference and
preserve the selected profiles of its child references. This is persistence and
replay evidence, not proof that the estimated trajectory is causally valid.
Temporal benchmarks use the existing Core-to-IR store adapter and withhold public
claim eligibility when any registered case or required acceptance check fails;
smoke mode does not turn an execution error or numerical failure into a pass.
Scientist's causal-contract compiler keeps the DTR estimator and temporal backend
selections separate, resolves the producer-selected bundle before aggregate
publication, and retains selected profiles in the execution entry and aggregate
lineage. An ID-only legacy producer result cannot establish that trajectory link.

## Role in System

- **Depends on:** `polisyos.foundry.methods`, `polisyos.ir.analytics.causal`
- **Used by:** Foundry method execution, Scientist causal nodes and policy-analysis workflows
- This is the largest method family in the catalog and the main home for causal research/runtime bridges.

## Key Concepts

- **Estimation families** - DiD, RDD, synthetic control, SCM, AIPW, TMLE and related estimators.
- **Discovery and identification** - constraint discovery, DAGMA, query validation and graph reconciliation.
- **Transportability** - transport checks, symbolic identification and parameter transfer helpers.
  The registered `CheckTransportability`, `SymbolicIdentify`, and `SymbolicIdentifyV2` scalar
  routes share a canonical graph-admission guard before sampling, front-door, fallback, native-ID,
  formula, or proof emission. The guard revalidates raw/model-copy profiles and reuses the existing
  static ADMG validator and directed topological check. It admits a validated static DAG or ADMG
  profile, refuses unresolved/unsupported endpoints, lags, cycles, malformed profiles, and graph
  types outside that scalar contract with `unsupported` plus `proof_status="oracle_needed"`.
  Exact live IR model classes are checked from canonical stored structural fields; graph, edge,
  and selection-diagram subclasses are typed-refused before dispatch so an overridden serializer
  cannot substitute a benign graph for the graph the algorithm would consume. Successful admission
  recursively rebuilds a detached `SelectionDiagram` from exact declared Pydantic fields, and the
  admission guard plus all registered consumers and the direct solver use that same snapshot.
  Caller-owned graph/diagram mutation after admission therefore cannot change the admitted input;
  noncanonical field containers (including `model_copy` values that override iteration or
  truthiness) are typed-refused rather than passed through to a consumer.
  PAG/CPDAG completion semantics remain unselected; a sampled candidate fraction is not treated as
  extension-set coverage or probability. Privacy post-processing cannot upgrade a limitation, and
  refusal does not prove non-identification. A compiler-injected effective PAG policy value records
  `origin:not_established`; direct pure-step omission and a present null remain distinct.

### Resolved selection diagrams and S-admissibility

The simplified transport route first checks the generic zero-adjustment
S-admissibility condition on the full resolved DAG/ADMG: augment the graph with
the declared population-selection nodes, apply the actual treatment intervention,
and recompute m-separation from those nodes to the outcome. When separated, the
existing source-domain ID algorithm must identify the effect before the result
is emitted as a source-law transport formula. This preserves bidirected endpoint
semantics through surgery and identification. A hedge, graph-operation failure,
or synthetic selection-node collision is a typed limitation. Non-admissible
ADMG inputs do not reach the endpoint-insensitive legacy heuristic; they remain
unsupported unless this source-law condition proves the bounded case. The
existing DAG mediator route remains available when selection affects the
outcome mechanism, while selected treatment/outcome variables are never reused
as covariates. The direct scalar PAG/CPDAG admission gate remains in front of
this route.

### Locked Y0 ID and TRSO adapter

`SymbolicIdentify`, `SymbolicIdentifyV2`, the shared transport solver, and the registered `CheckTransportability` route call the locked Y0 0.2.11 algorithm APIs when Y0 is selected. Direct queries consume the expression returned by `identify_outcomes`; transport queries with selection nodes call `identify_target_outcomes` only when the caller supplies `surrogate_data_profile`. The registered `RunTransportabilityNode` carries that same caller input through its resolution loop. Local front-door, do-calculus, and c-component heuristics no longer emit results carrying Y0 or R backend identities.

The optional profile is a strict request input, not an evidence artifact. Its shape is:

```json
{
  "schema_version": "policyos.y0.surrogate-data-profile.v1",
  "populations": [{ "population_id": "pi1", "outcomes": ["Y"], "interventions": ["X"] }]
}
```

Each population declares observed outcomes and interventions for one source population. The bridge checks names against the admitted graph and preserves the exact Y0 expression, operation, package version, profile digest, and candidate source/target quantities. The admitted profile and its nested collections are immutable snapshots. It does not infer a profile from selection nodes. Missing, explicit-null, malformed, and graph-incompatible profiles remain distinct typed limitations; Y0 returning no expression or raising an error is also a limitation, never a non-identification certificate.

The existing `EstimandAST` cannot represent population-indexed Y0 leaves. A returned TRSO expression therefore remains an exact candidate in result metadata with `status=unsupported` and `proof_status=oracle_needed`; it is not promoted into a `TransportFormula` or an identified proof. The profile does not establish that data exist, are current, or are authoritative. A direct Y0 expression can be `identified` as a mathematical candidate under the admitted graph, but carries `requires_expert_review` because data custody is unestablished. The transportability required-pass blocks both direct CAS references and external report paths for such candidates, while the cross-graph pass warns and discovery utility scoring reduces its ranking. These signals do not establish authority or publishability.

Capability output reports only executable Y0 `direct` and `trso` families when their API paths are available. Import/API presence does not imply support for front-door, do-calculus, or c-component families. A bounds result is emitted only when the bounds operation returns; an exception is an `unsupported` limitation and cannot fabricate bounds or a negative-identification certificate. The R `causaleffect` execution adapter remains unimplemented.

- **Strategic response** - `strategic.py` now models solve/bundle/summary flows for response design.
- **Policy learning** - `policy_learning.py` and adjacent estimators support downstream decisioning.
- **Measurement error** - `measurement_error.py` and adapter layers expand noisy-observation handling.
- **Space-time DSCM** - `space_time_dscm.py` adds field-valued DSCM contracts, operator edges,
  controlled diffusion-reaction simulation, finite-element SPDE g-computation, optional
  continuous-time IPW/DR diagnostics, and mesh/time-step sensitivity reports.
- **Capability contracts** - optional backends degrade by contract instead of silently changing semantics.

## Public API

| Type/Function                            | Description                                                 |
| ---------------------------------------- | ----------------------------------------------------------- |
| `ensure_causal_methods_registered()`     | Registers the causal family into a registry.                |
| `register_causal_methods()`              | Returns the canonical list used by the bootstrap.           |
| `CausalEngine`                           | Core engine for causal graph/effect orchestration.          |
| `CausalEstimator`                        | Base protocol for causal estimators.                        |
| `DoWhyIdentifyEstimate`                  | Identification-plus-estimation path.                        |
| `DoWhyRefute`                            | Refutation / placebo diagnostics.                           |
| `StrategicSolveResult`                   | Result model for strategic response solving.                |
| `solve_strategic_response()`             | Solves the strategic response bundle.                       |
| `build_strategic_response_bundle()`      | Builds the strategic response input bundle.                 |
| `OptimalPolicyLearner`                   | Learner for policy-selection oriented causal workflows.     |
| `CheckTransportability`                  | Transportability gate for cross-context use.                |
| `transport_bounds()`                     | Computes transportability bounds.                           |
| `SpaceTimeSPDEGComputation`              | FEM SPDE g-computation for ST-DSCM policy spillovers.       |
| `simulate_reaction_diffusion_response()` | Validation helper for nonlinear reaction-diffusion systems. |

→ Full reference: [docs/reference/foundry/index.md](../../../../../../docs/reference/foundry/index.md)

## Internal Layout

- `__init__.py` exposes the supported causal family import surface and delegates
  registration to `_registry_boot.py`.
- `protocols.py`, `_common.py`, and helper contract modules define shared input
  and result shapes. Keep cross-method payloads here only when multiple causal
  families consume them.
- `causal_engine/`, `id_engine/`, and `interference/` are split packages. Their
  public entrypoints remain package imports; implementation helpers belong to
  the corresponding leaf modules. `constraint_discovery.py` and
  `invariance_tests.py` remain modules tracked in `architecture/module_size_budget.toml`.
- Method modules are grouped by concept: identification, estimation,
  diagnostics, discovery, transportability, fairness, policy learning,
  recourse, strategic response, and space-time DSCM.
- Optional backend adapters such as `_econml_adapter.py` and
  `_sklearn_compat.py` must degrade by explicit capability contract.
- `_dowhy_worker.py` owns the selected source-resolved cross-interpreter bridge
  inside the existing method job. The separate pinned Python 3.12
  [DoWhy worker profile](../../../../../../workers/dowhy-014/README.md) executes
  actual DoWhy 0.14 linear ATE identification/estimation and explicit GCM fitting;
  it imports no PolicyOS code and owns neither CAS nor scientific authority.
  The Python 3.14 parent requires an actual resolved source context, validates
  aligned input and result bindings, and persists the typed result. Native
  synthetic-DGP tests establish bounded implementation properties; they do not
  establish admitted real-data assumptions or Scientist evaluation authority.
  `DoWhyIdentifyEstimate.report_from_worker_result` is the complete pure report
  projection shared by the actual producer and source-validating consumers.
  It derives parameter defaults from the registered signature and preserves
  default diagnostics, assumptions and absent p-values; it launches no backend
  and grants no authority. The existing class facades retain the same object and
  pickle addresses, and their supported method override reaches the producer.

### CausalEngine Twin result persistence

`CausalEngine.run()` places an actual `TwinNetworkResult` in the returned
`EvidenceBundle` when a typed SCM and artifact store are available. The audit
path persists the typed result through the existing IR CAS adapter, binds its
source/query/SCM lineage to selected manifest profiles, and includes the ref in
the persisted proof trace. Reference-free audit bundles retain the exact strict
`ir.causal_evidence_bundle` 1.0 shape; a bundle carrying the Twin ref is schema
1.1. Current readers accept both versions by the selected manifest view, and
strict 1.0 readers reject 1.1 as unsupported. Existing 1.0 artifacts need no
rewrite. The result link is a persistence bridge; it does not grant causal or
policy authority to the supplied SCM or its output. Selected GCM continues to
require a fully observed declared static DAG; its existing `ValueError` refusal
now exposes the typed `reason_code="graph_not_declared_static_dag"`.

### Bounded ForestDR worker profile

`causal.hte.forest_dr@1.1.0` is the additive single-job ABI for the existing
EconML `ForestDRLearner` producer. It requires the integer parameter
`n_jobs=1`, passes that value to the estimator, and records the effective
setting in both `HTEResult.econml_params` and the method report. The existing
`causal.hte.forest_dr@1.0.0` signature and its historical EconML defaults
remain available unchanged. Historical 1.0.0 intents remain readable under resource-policy
`r1`. A policy that requires estimator `n_jobs` (currently revisions `r2` and `r3`)
requires ForestDR 1.1.0 because the historical 1.0.0 producer call omits that parameter.

The `causal-core` and `causal-full` profiles resolve EconML 0.17 on the
supported Python 3.14 baseline. Provision the selected profile before the
serving process imports the causal facade, or restart that process afterward
because the optional-backend adapter snapshots backend availability at import.
For 1.1, `n_jobs=1` is passed to ForestDRLearner and the existing
`threadpoolctl` mechanism scopes a limit across input preparation, estimator
construction, fit, effect/inference extraction, feature-importance extraction,
and report materialization. This is a cooperative limit for recognized native
thread pools, not an operating-system CPU quota or a deployment-wide cap; the
actual selected runtime must observe the effective pools during a real fit.

The shared EconML adapter reads per-observation uncertainty from the result
object's `stderr`/`pred_stderr` protocol. It omits optional per-row intervals
and standard errors when the estimator does not provide them, and refuses
non-finite, misaligned, or multi-outcome values instead of padding or selecting
a column. ATE p-values are invoked when exposed as methods. The shared adapter
uses one scoped warning boundary for optional native ATE summary accessors and
calls, including confidence-interval providers, p-values, and mean-level
standard errors. A failing p-value or standard-error member is omitted without
discarding an interval already obtained; a failing interval provider moves to
the next supported provider and then to the existing unqualified fallback if
none succeeds. `ATE_OPTIONAL_SUMMARY_MEMBER_UNAVAILABLE` warnings identify only
the member, access or call phase, and exception type. Missing members remain
absent without an error warning, while
present malformed returned values still refuse. SHAP uses the
estimator-native `shap_values` API and accepts one outcome/treatment
explanation for this scalar HTE contract; unavailable or failed SHAP remains
an explicit tree-based fallback, while malformed returned values refuse.

When a native ATE interval is unavailable, the adapter retains the existing
fixed 1.96 normal-Wald fallback. The existing variance guard may also widen or
replace a valid native interval with a symmetric interval based on CATE
dispersion and the same fixed multiplier. Both behaviors remain unqualified;
the multiplier does not become alpha-specific through the selected confidence
level, and neither behavior establishes a calibrated population confidence
claim. The selected alpha is still passed to native interval methods.

These adapter behaviors do not establish causal identification, external
validity, scientific qualification, calibration, or publication authority.

### HTE observational input admission

`polisyos.foundry.methods.catalog.causal.build_hte_data` delegates to the
existing typed HTE observational adapter, preserving its input validation and
array conversions. It constructs method inputs and confers no source,
causal-identification, or publication authority.


`polisyos.foundry.data_plane.prepare_hte_observational_input` is the Foundry
owner for two explicit source protocols: a selected-profile
`ir.observation_method_input` envelope, or an explicitly requested legacy
`ir.observational_data` JSON artifact with no artifact schema. Both paths use
Core's selected-view bounded JSON reader, with a separately pinned manifest
byte limit and payload byte/depth/element limits, before constructing
`HTEObservationalData`; the exact envelope schema, explicit body discriminator,
stable contract ID, and protocol FQN must match. Legacy input is persisted as a
new envelope with a lineage edge bound to the source manifest profile. Its
source governance and tenant context are copied only when present, and
normalization refuses when raw selected governance has no explicit
classification. The prepared worker value carries the effective artifact
schema and observed manifest/payload measurements from this bounded read, so
the method bridge does not need a second manifest lookup.

The HTE DTO enforces `n_obs >= 40`, a binary treatment, aligned finite numeric
arrays, and its current optional-field rules. All four limits are required
from the persisted Runtime resource-policy revision; this producer defines no
numeric fallback. The result's arrays are worker-local, and the handoff retains
only refs and typed admission metadata. These checks establish input shape and
profile provenance, not units/context, method compatibility, external truth,
causal identification, scientific validity, or publishability.
Runtime/SharedExecutor invocation and estimator dispatch remain the end-to-end
acceptance signal.

## Extension Points

### Installed selected-worker profile

The wheel projects the six canonical files from `workers/dowhy-014/` into the
private causal `_dowhy_profile` resource directory. The sdist retains those
same source paths so rebuilding its wheel uses the same mappings. The fixed
worker script and protocol have one source owner; packaging does not create a
second implementation or add DoWhy to the Python 3.14 application dependencies.

Configure `POLISYOS_DOWHY_WORKER_PYTHON` with the server-owned absolute Python
3.12 interpreter containing the separately locked worker dependencies. The
parent validates the complete profile before invoking the worker; missing
resources or interpreter configuration remain typed unavailability. Installed
consumer tests exercise a real method job, CAS persistence and a fresh reader,
then retire and restore a private resource to distinguish execution from a
profile marker. Their known-DGP results establish bounded numerical and ABI
properties; production input admission and scientific authority remain separate.

### DiD diagnostic basis

The dedicated Standard and Staggered DiD producers attach a separate
`diagnostic_contract` and `diagnostic_binding` to computed reports. The contract
binds the complete outcome, treatment membership and `time_treatment`, and the
complete typed diagnostic list under the declared group-mean linear HC1/normal
pretrend profile. These fields are separate from the staggered scalar target:
changing only `time_treatment` can change diagnostics while leaving the fixed
cohort target and its estimate unchanged.

The internal `_diagnostic_contract` class method recomputes this projection for
the Scientist consumer. A consumer must compare both metadata and the actual
typed `report.diagnostics` against current-input recomputation. Hash presence or
matching scalar-target markers alone does not validate a diagnostic. Historical
reports remain readable; a current-input validator must recompute or refuse a
report without its diagnostic contract.

Insufficient preperiods and missing groups remain `not_testable`, with no test
statistic or p-value and `passed=False`. Standard DiD with no preperiod remains
`INPUT_INVALID` before diagnostic computation. Neither diagnostic non-rejection
nor this provenance contract establishes parallel-trends identification.

### Static reconciliation and discovery limitations

Prior reconciliation, fragment composition and Scientist graph intake share the
existing static DAG/ADMG admission boundary. Declared MGraph/CPDAG/PAG families,
unresolved endpoints and compact lags refuse before filtering or projection.
A supplied reserved `metadata["mgraph"]` contract also refuses under a DAG/ADMG
tag, including malformed/null payloads. Retagging does not reconcile that typed
contract. Clean DAG/ADMG graphs with missingness-looking names and opaque metadata
remain supported; no missingness classification by node names is performed.

Discovery retains an unsupported graph when requested prior/hint reconciliation
cannot apply. Its existing `DiscoveryPipelineReport` carries the warning and
machine-readable reconciliation result; persisted report readers retain them.
The producer emits its declared `discovery_pipeline_report` slot and retains
the existing raw `report` address as an alias of the same report object.
An absent request produces no reconciliation limitation. Neither the retained
graph nor a successful supported reconciliation establishes identification or
scientific authority. See the
[current intake contract](../../../../../../docs/reference/scientist/causal-graph-intake.md).

### Causal engine and interference compatibility surface (LA-020)

The existing `causal_engine` package explicitly exports `CausalEngine` and
`DataReadinessBlockedError`. The engine class is defined in `causal_engine.api`;
the exception belongs to `_causal_engine_contracts`. Direct and star imports
keep those object identities and serialized module addresses.

The `interference` package explicitly exports `BipartiteInterferenceEstimator`,
`NetworkAIPWEstimator`, `PartialInterferenceEstimator`,
`SpatialInterferenceEstimator`, `InterferenceAugmentedGraph`,
`InterferenceIdentificationResult`, `build_block_stratified_network_causal_data`,
`build_interference_topology_contracts`, and `identify_interference_effect`.
Estimator implementations belong to `interference.api`, graph/result contracts
to `_interference_contracts`, and identification helpers to
`interference.identification`.

Historical test callers still use `causal_engine._make_dummy_identification_result`
and patch `causal_engine.mz_id_algorithm`, `id_with_oracle_fallback`,
`id_star_algorithm`, and `idc_star_algorithm`. These bindings remain addressable
outside `__all__`; the identification mixin consumes the patch targets at runtime.
The interference facade similarly retains `_ReductionErrorBoundPlan`,
`_SimplicialSupportGate`, and `_TopologyCertificatePlan` for existing test callers.
New internal tests should import helpers from their leaf owners. Retiring these
compatibility names requires an API-owner decision and a consumer migration;
adding a service import to a leaf does not extend the package API.

The measured compatibility window retains these existing package bindings;
this continuation retires no public or historical patch target. Ordinary
internal helper callers use `causal_engine.artifacts`, while dedicated ABI
controls still exercise the historical facade aliases. The repository public
surface manifest determines which broader entrypoints are `public_stable`;
retained test helpers are not promoted to that classification. A future removal
requires the existing owner/deprecation process and its supported caller basis.

Graph-based interference identification runs ordinary ID on the original graph only
when an explicitly declared complete unit partition is reconciled and no cross-unit
edge is observed. Cross-unit topology, missing or partial partitions, and graph
metadata labels do not define a policy-specific exposure law; those queries return
oracle_needed under result schema 1.1, without an estimand, hedge certificate, or
synthetic exposure nodes. Unknown partition indicators are null in 1.1; false is
reserved for a complete partition with no observed cross-unit edge. Traces and
pairwise, cluster, and full-complex adapter assumptions project both indicators
as explicit true/false/unknown values with the identification status. Benchmark
case rows and JSON retain null; aggregate reports count unknown topology cases
and keep spillover detection null unless a positive is established or every
topology case is known false. The scorecard fails closed when that check is null.
The topology adapter remains a diagnostic candidate surface and records when
interference identification was not established. The legacy result schema 1.0
remains readable; expanded status values require 1.1.


Use qualified package imports and canonical owner FQNs for loader/config/docs
consumers. The former `id_engine.py`, `causal_engine.py`, and `interference.py`
sibling files were already absent at the E02 base; no filename shim is supplied.
`find_spec` and its normal Python loader resolve the nonempty packages. A
`runpy`/`spec_from_file_location` client opening a retired filename receives the
normal missing-file error and must migrate its explicit configuration. These
libraries do not declare command-line `__main__` entrypoints. Runtime method
discovery and third-party plugin loading retain their separate maintained
contracts; a computed import AST candidate is not evidence that such a client
actually invoked this facade. Wheel/sdist tests must run outside the checkout
and bind archive, installed resource and canonical-object identities.

The native
`tests/unit/foundry/methods/catalog/causal/test_installed_facade_contract.py`
checks public and retained exports, canonical object identity, import behavior,
incidental-name rejection, reload cleanup, and rendered documentation.
`tests/unit/foundry/methods/catalog/causal/test_facade_consumers.py` exercises a
real Scientist identification consumer, engine/result serialization, supported
patch execution and restoration, leaf FQNs, and runtime documentation
generation. These are bounded ABI witnesses, not DoWhy/EconML backend or
real-data validity receipts.

### Method registration

- External causal methods use the parent `polisyos.foundry_methods` extension
  point declared in
  [architecture/extension_points.toml](../../../../../../architecture/extension_points.toml).
- Builtin causal methods must register through `_registry_boot.py` and provide
  method metadata compatible with the parent registry snapshot and capability
  matrix.
- Authoring rules live in [AUTHORING.md](AUTHORING.md) and the parent
  [catalog/AUTHORING.md](../AUTHORING.md).

## Tests

- Package-local tests live in
  [tests/unit/foundry/methods/catalog/causal/](../../../../../../tests/unit/foundry/methods/catalog/causal/).
- Use characterization tests before splitting high-complexity modules, for
  example `test_id_engine_characterization.py` for symbolic ID behavior.
- Run the parent Foundry Methods suite when changing registration metadata:

```bash
uv run pytest tests/unit/foundry/methods/catalog/causal -q
uv run pytest tests/unit/foundry/methods/test_registry.py tests/unit/foundry/methods/test_testing_infra.py -q
```

## Operability Links

- [Foundry component SLO](../../../../../../ops/components/foundry/slo.yaml)
- [Foundry component runbooks](../../../../../../ops/components/foundry/runbooks.md)
- [Causal engine architecture](../../../../../../docs/reference/foundry/causal-engine-architecture.md)
- [Run causal analysis how-to](../../../../../../docs/how-to/run-causal-analysis.md)
- [Benchmark regression triage runbook](../../../../../../docs/runbooks/benchmark-regression-triage.md)

## Known Shims/Deprecations

- There are no package-local compatibility shims for `catalog/causal` in
  `architecture/shims.toml` as of 2026-05-06.
- High-complexity modules in this family are covered by
  [architecture/module_size_budget.toml](../../../../../../architecture/module_size_budget.toml)
  with owner `team-foundry` and sunset `2026-12-31`.
- Renaming a method ID, moving an import path, or extracting one of the
  budgeted modules requires a deprecation record, compatibility tests, and a
  registry snapshot check before deletion.

## RDD Runtime Support Boundary

The runtime `RegressionDiscontinuity` method supports both the ordinary
uncorrected local-polynomial estimator and one bounded native corrected profile.
The corrected profile is sharp RDD with explicit fixed `bandwidth` and
`bias_bandwidth`, `bias_polynomial_order = polynomial_order + 1`, a supported
kernel, `vce="hc0"`, `masspoints="off"`, and no automatic bandwidth selector.
It reports the profile as `sharp_cct_rbc_hc0_fixed`, computes the correction,
and includes the bias-estimation variance and covariance in its robust standard
error. The omitted `bias_correction` value remains equivalent to explicit
`False` and selects the separate conventional estimator.

Requests outside that boundary (including fuzzy design without treatment data,
mass-point adjustment, automatic bandwidth selection, or other variance
estimators) return a typed non-success rather than being relabelled as corrected.
This native bounded profile does not imply parity with every option of
`rdrobust`, validity for data-dependent bandwidth selection, or a universal
finite-sample coverage guarantee.

Local WLS uses vector weighting and a small Gram matrix rather than materializing
an observation-sized diagonal matrix. This preserves the existing residual
covariance convention and point/standard-error semantics while keeping the
fixed-order fit linear in the number of observations. Synthetic finite-design
regression evidence for the corrected profile must not be generalized to other
laws, populations, selectors, kernels, orders, variance estimators, or designs.

## Current State

- Last updated: 2026-10-14
- The source inventory is the Python module tree below this directory,
  including subpackages; the public export surface is `__all__` in
  `__init__.py`. Fixed totals are omitted because these use different
  denominators and change independently.

### Native causal value output slots

The registered DiD and synthetic-control methods declare their existing
`CausalEffectReport` result slot through `SlotSpec.for_output_contract`. This
connects the real method result to the shared typed output-contract registry; a
callable method label or an empty result does not satisfy it. The N8 candidate
producer persists the exact selected profile, explicit run intent, runner input,
and report in CAS before the fresh value consumer resolves the run basis.

A typed interval still has `gate_eligible=False`. The bounded synthetic owner
assignment used by the producer tests is a candidate fixture only. The default
owner gateway does not derive treatment assignment from an intervention or
method result and remains blocked when that owner input is absent. Neither real
DiD/SCM execution nor the new slot declaration establishes identification,
external owner authority, calibration, or production currentness.

The fresh N8 run-basis v2 reader compares exact selected-profile input multisets
and requires a post-run execution receipt. The receipt records the submitted request parameter object as intent and the
NumpyRunner result's seed, backend, and fingerprint, then binds the exact
persisted report bytes. This catches a reissued seed request and a reissued
parameter when the report directly exposes that value. The methods do not expose
every resolved/used parameter, so full parameter-use reconciliation remains
`not_established`; request intent is not treated as method evidence.
The whole source-to-result relation stays candidate-only and fails closed when
any selected manifest profile or receipt link is unresolved.

## Y0 proof pairing and review grade

The registered `CheckTransportability`, `SymbolicIdentify`, and `SymbolicIdentifyV2` result/proof pairs use the shared ProofBundle projection. An actual scoped direct Y0 expression remains `identified` as conditional graph mathematics; its A2/sound-incomplete bundle and computed `review_required` grade preserve that source-data existence, currentness, and authority remain unestablished. Other identified results remain mathematical candidates, but their grade is `unknown` until a source-resolved, content-bound, verifier-provenance basis is available. Native and simplified backend labels alone cannot clear the protected pass. The projector preserves an available theorem/AST while marking the bundle sound-incomplete; the strict pass blocks both `review_required` and `unknown`. This is a review boundary, not a data, legal, publication, or institutional authority claim. The accepted meaning of A1 completeness remains open in the G decision packet.

### Source-preserving DAG admission

`polisyos.ir.analytics.causal_graph.project_graph_to_dag` is the canonical
profile-specific projection used by DAG-only discovery consumers. Its
`GraphProjectionDisposition` binds the source graph type and complete source and
resolved graph hashes. Discovery reports and graph hypotheses carry that typed
receipt; supported analysis readers consume only a source DAG or a projection
that can be recomputed from the same source. A missing historical receipt is
upgraded to a fail-closed limitation unless a stored projection replays exactly.
FCI failure/timeout remains `unavailable` with no resolved graph, distinct from
an empty graph returned by a successful run. Every projector and analysis reader
rebuilds the complete declared graph and disposition fields before branching;
only class-declared cached-property storage is excluded from the content digest.
The accepted result is the detached canonical snapshot itself, so a later caller
mutation cannot replace the graph already admitted to an analysis consumer.
A malformed `model_copy` or extra stored field is rejected before DAG identity or
projection is selected. The report/hypothesis adapter is limited to unversioned
and schema-1.0 receipts; schema-1.1 payloads must carry their required typed
receipt. The projection does not choose PAG/CPDAG completion semantics or assign
probability to completions.

### Scalar identification admission

Direct scalar identification and the registered transport routes share one
canonical graph-snapshot boundary. It rebuilds the complete live IR field set,
including nested edges and declared cache storage, then the consumer uses that
returned immutable snapshot. PAG and CPDAG tags are typed `oracle_needed` /
unsupported until the open G decision selects a completion-set contract; a
fully oriented endpoint row or policy label is not a selected extension.
Static ID accepts resolved DAG and acyclic ADMG profiles; a cyclic ADMG receives
a typed refusal at that owner. Direct scalar ID refuses M-graphs because those
queries need the full-law owner and explicit missingness-recovery inputs. The
M-graph recoverability owner validates its source and derives each proxy-stripped
or substantive internal DAG/ADMG profile from the retained edge endpoint marks.
It preserves bidirected and reverse-stored directed edges, uses the existing
static profile and cycle validator, and typed-refuses unresolved marks rather
than assigning PAG or guessing a completion. The source remains MGRAPH; the
existing CausalEngine validated dynamic reduction, sigma/cyclic, and full-law
M-graph paths retain their separate owners.
Direct TR calls rebuild the entire typed selection diagram, require every S-node
target to name a base-graph variable, and pass that same detached object to the
identifier. Raw endpoint/orientation inspection stays descriptive; it does not
authorize a scalar proof. This does not estimate completion probabilities,
establish graph truth, or close B214.

### Shared static-cache intake and candidate diagnostics

Every cached scalar adjacency read canonicalizes the complete live graph, refuses unadmitted graph tags and validates endpoint marks, lag, and metadata before lookup, including empty-query and no-op consumers. Reuse is keyed by the SHA-256 digest of the complete strictly revalidated canonical graph content, so an equivalent fresh graph can hit the same entry and any changed field produces a different key. The adjacency and c-component caches are separate least-recently-used maps, each capped at 128 entries; their values retain a detached canonical graph or component tuple, never the caller object. Cache capacity is an entry-count bound, not a byte-size claim. Resolved DAG and static ADMG operations remain available, while cyclic sigma and M-graph full-law work keep their existing dedicated owners.

A content-bound identity DAG may produce graph-derived CI and automatic
trek-rank diagnostics for candidate ranking. Their assumptions remain typed
unknown and their falsification scope remains ranking_only through the
DownstreamUtilityReport scorecard; the scorecard records that source
completeness, population, temporal scope, selection, and the distribution
Markov assumption are unknown. Automatic trek-rank diagnostics cannot become
blockers from a graph-declared assumption regime alone. These candidate
signals do not pass the separate protected-promotion gate. PAG/CPDAG sources,
projected DAGs, and other non-identity graph profiles remain skipped with a
typed limitation; explicit algebraic blocks remain independently auditable.
Partial-graph CI stays held for the G decision, with no completion probability
or causal authority inferred.


### HTE successor producer profiles

Four additive `@2.0.0` methods use a context-aware entry that accepts the
Runtime-owned `OwnedAttemptAnchorDispatchContext` as a separate typed
`runtime_context` argument; the context is never inserted into scientific
method parameters. The legacy registrations retain their existing call shape.
The dispatch path rejects a legacy FQN, cross-profile anchor, or method without
the successor hook. The selected input capture is recomputed from the actual
prepared arrays and reconciled to the persisted anchor before fitting.

CausalForestDML and ForestDR may produce a conditional native interval only
when the exact EconML 0.17 native `ate_inference.conf_int_mean` route, selected
rows, contrast, alpha, parameters, and observed resource profile reconcile.
DoubleML and MetaLearner publish point-only candidates. The DML/Meta profiles
run inside a method-local `joblib.parallel_config(n_jobs=1)` scope, preserving
EconML's selected nuisance algorithms; CF/ForestDR record the instantiated
estimator's live `n_jobs` configuration. These observations do not bound
BLAS/OpenMP threads, RSS, or deployment-wide CPU usage.

The method returns `hte_outcome_write_ready`, a private, strict candidate value
inside the ordinary `MethodResult`. It does not create owner refs or write CAS
artifacts itself. The Scientist bridge validates it against the owner anchor,
actual MethodResult and MethodExecutionEvidence, then persists the selected IR
chain. Failed input preparation follows the Runtime's separate typed refusal
path; no success result, row count, or evidence ref is fabricated for that path.

### Conditional PAG member candidates

The finite no-selection PAG sensitivity route keeps generation and persistence in the
resolver, then evaluates each admitted, content-bound DAG or ADMG member with
evaluate_pag_member_candidate. The helper rechecks source graph, member, query and
context bindings, rebuilds the selection diagram from fresh source and target contexts,
and delegates to the existing solve_transportability path. Completed rows retain the
solver's typed status and full result; solver failures and binding refusals remain distinct.

This is candidate sensitivity over the explicitly selected finite member family. It
does not turn a PAG or CPDAG into a direct scalar graph, assign probabilities to members,
or promote candidate outcomes into transport authority. A caller verifies selected-profile
CAS references and persists admitted members before invoking the helper.

### Learned dynamic policy preservation

Q-learning and DR-DTR retain every fitted float64 Q model in the existing
`DynamicTreatmentRegime` 1.1 artifact. The selected `linear_q_action.v1` or
`linear_q_current_interactions.v1` profile specifies the history/action feature
order. G-computation replays both full predictions and selects action one only
when `Q(1) > Q(0)`, including the producer's floating-point tie behavior. A
treated-cohort median or majority is not a substitute for that policy.

A-learning retains each stage's actual constant action as an explicit schedule.
OWL currently has no typed SVC policy representation: its finite learning value
remains a candidate diagnostic, while its report is `assumption_failed` and has
no executable `DTRResult`. Historical unbound `linear_blip`, unknown profiles,
missing stages and incompatible dimensions refuse execution. These checks
preserve the learned rule; they do not establish optimality, causal identification
or the adequacy of fitted state-transition models.
