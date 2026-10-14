# Analytics IR

Related explanation: [Causal Engine](../../explanation/causal-engine.md).

> Causal, heterogeneity, backtest, uncertainty, and strategic-response contracts and artifacts used across Foundry and Scientist.

This page follows the analytics surface that is already exposed from
`polisyos.ir`, and also documents the new `polisyos.ir.analytics.strategic`
module because it is central to the observation-aware policy workflow.

`polisyos.ir.analytics` itself is now a curated lazy facade: it re-exports the
most common analytics contracts, but it is no longer a wildcard mirror of
every analytics implementation module. For advanced/report-specific APIs use
the defining submodule import path.

Freshness: 2026-10-14
Owner: `@ir-owners`
Source of truth: `src/polisyos/ir/analytics/**`, `src/polisyos/ir/registry/refs.py`, `src/polisyos/ir/loading/citations.py`, `schemas/snapshots/ir/*.schema.json`, `tests/unit/ir/analytics/**`, `tests/unit/ir/test_uncertainty.py`, `tests/unit/ir/test_frontier_causal_contracts.py`
Snapshot and evidence level: source pin `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`; this page was reviewed at source level for its stated contract/status boundaries and source references. Test and validation links are coverage pointers; they were not executed for this update.
Source plan phases: D1-L4 Phase 2 estimand/uncertainty normalization, Phase 3 verification, and Phase 5 causal frontier contracts.

## Source Modules

| Module                                          | Focus                                                                                                             | Key exports                                                                                                                                                  |
| ----------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `polisyos.ir.analytics.data_views`              | Runtime data-view requests for panel, snapshot, and network inspection                                            | `DataViewRequest`, `DataFilter`, `AccessTier`, `DataViewType`                                                                                                |
| `polisyos.ir.analytics.causal`                  | Core causal effect reports and robustness metadata                                                                | `CausalEffectReport`, `RefutationResult`, `DiagnosticTest`, `PlaceboResult`                                                                                  |
| `polisyos.ir.analytics.causal_queries`          | Interventional, counterfactual, and soft-intervention query contracts                                             | `CausalQuery`, `InterventionSpec`, `CausalQueryResult`                                                                                                       |
| `polisyos.ir.analytics.causal_discovery`        | Discovery reports, latent diagnostics, and algebraic constraints                                                  | `CausalDiscoveryReport`                                                                                                                                      |
| `polisyos.ir.analytics.causal_ensemble`         | Structural uncertainty bundles across graph candidates                                                            | `EnsembleMember`, `CausalModelEnsemble`                                                                                                                      |
| `polisyos.ir.analytics.ecosystem_bridges`       | Exchange contracts for DoWhy, EconML, CausalNex, pgmpy, and Tigramite                                             | `DoWhyGraphBridge`, `EconMLDesignBridge`, `PgmpyGraphBridge`, `TigramitePCMCIBridge`                                                                         |
| `polisyos.ir.analytics.hte`                     | Heterogeneous treatment effects and targeting outputs                                                             | `HTEResult`, `SubgroupEffect`, `FeatureImportance`, `PolicyRecommendation`                                                                                   |
| `polisyos.ir.analytics.backtest`                | Historical validation and trust diagnostics                                                                       | `BacktestReport`, `MetricBiasDiagnostic`, `BacktestScenario`, `SystematicBias`                                                                               |
| `polisyos.ir.analytics.uncertainty`             | Unified interval semantics and propagation metadata                                                               | `UncertaintyEnvelope`, `DistributionFamily`, `PropagationMethod`                                                                                             |
| `polisyos.ir.analytics.structural_causal_model` | Structural mechanism declarations                                                                                 | `MechanismFamily`, `MechanismSource`, `NodeMechanism`, `StructuralCausalModelSpec`                                                                           |
| `polisyos.ir.analytics.abstraction`             | Micro-to-macro abstraction certificates, exact finite-state verification, and continuous approximate error bounds | `AbstractionCertificate`, `ContinuousApproximateAbstractionConfig`, `verify_finite_state_exact_abstraction`, `verify_continuous_approximate_abstraction`     |
| `polisyos.ir.analytics.distributional`          | Cohort-level winners/losers and inequality summaries                                                              | `DistributionalReport`, `DimensionBreakdown`, `WinnersLosersTable`                                                                                           |
| `polisyos.ir.analytics.strategic`               | Strategic adaptation, equilibria, and performative-shift artifacts                                                | `FiniteStrategicPayoffTable`, `StrategicSCM`, `StrategicResponseBundle`, `PerformativeShiftSummary`                                                          |
| `polisyos.ir.analytics.representation_learning` | Latent confounder and representation-learning contracts                                                           | `LatentConfounderContract`, `RepresentationLearningResult`, `RepresentationModelFamily`                                                                      |
| `polisyos.ir.analytics.invariance`              | Multi-environment invariance and shift-aware diagnostics                                                          | `MultiEnvironmentCausalContract`, `InvarianceResult`, `EnvironmentSpec`                                                                                      |
| `polisyos.ir.analytics.causal_rl`               | Causal MDP/POMDP and counterfactual policy optimization                                                           | `CausalRLContract`, `CounterfactualPolicyOptimizationSpec`, `CausalRLResult`                                                                                 |
| `polisyos.ir.analytics.temporal_frontier`       | PCMCI/Granger/Hawkes/SDE/regime-switching discovery outputs                                                       | `TemporalDiscoveryFrontierReport`, `TemporalDiscoveryEdge`, `EquivalenceClassSummary`                                                                        |
| `polisyos.ir.analytics.dynamic_regime`          | Continuous-time query and effect-trajectory bundle contracts                                                      | `ContinuousTimeQuery`, `EffectTrajectoryBundle`, `TemporalPathRepresentation`                                                                                |
| `polisyos.ir.analytics.rough_path_semantics`    | Rough/signature proof artifacts and bundle-level semantic attachments                                             | `RoughPathInterventionCertificate`, `TemporalPathSemanticsAttachment`                                                                                        |
| `polisyos.ir.analytics.recourse`                | Algorithmic recourse, counterfactual and contrastive explanations                                                 | `RecourseReport`, `RecoursePlan`, `CounterfactualExplanation`                                                                                                |
| `polisyos.ir.analytics.recourse_manifold`       | Proof-carrying causal recourse queries, manifold geometry, proof bundles, and feasibility certificates            | `InterventionCostManifold`, `OptimalRecourseInterventionQuery`, `RecourseProofBundle`, `RecourseFeasibilityCertificate`, `OptimalRecourseInterventionBundle` |

## Data View Requests

::: polisyos.ir.analytics.data_views

## Causal Effects And Robustness

::: polisyos.ir.analytics.causal

## Causal Queries

::: polisyos.ir.analytics.causal_queries

The direct static ID family admits a resolved DAG or acyclic ADMG. Cyclic ADMGs
receive a typed static-ID limitation; the validated dynamic-reduction and
sigma/cyclic owners remain separate. Direct scalar ID refuses M-graphs, which
require the full-law recovery owner and explicit missingness inputs. Direct TR
admission also verifies that every S-node target is present in the selection
diagram's base graph.

## Discovery And Structural Uncertainty

`CausalDiscoveryReport` schema 1.1 carries a content-bound graph projection
receipt. DAG-only readers consume the source only when it is a declared DAG or
when the receipt binds an exact canonical projection. Historical reports without
a receipt are upgraded fail-closed: an old resolved graph is admitted only if
replaying the current profile-specific projector reproduces its complete graph
payload; otherwise it remains retained as an unsupported candidate. PAG/CPDAG
completion semantics are not selected by this receipt.

::: polisyos.ir.analytics.causal_discovery

::: polisyos.ir.analytics.causal_ensemble

## Ecosystem Bridges

::: polisyos.ir.analytics.ecosystem_bridges

## Heterogeneous Effects And Targeting

::: polisyos.ir.analytics.hte

## Backtesting And Trust

::: polisyos.ir.analytics.backtest

## Uncertainty Envelopes

`UncertaintyEnvelope` is now the single composition layer for interval-bearing
analytics contracts.

- `numeric_policy` makes float canonicalization explicit and reproducible.
- `combine_envelopes()` is the shared merge API for confidence, credible, and
  deterministic interval families.

- `composition_provenance` records flavour, exactness, certificate kind/radius,
  and the operator history for chained uncertainty transport.

- `join_envelopes()`, `push_forward_envelope()`, `pull_back_envelope()`, and
  `compress_envelope()` separate report-level merging from stage-by-stage
  uncertainty algebra.

- `distribution_payload` carries richer posterior shapes:
  `posterior_samples`, `quantile_summary`, `parametric_fit`, and
  `mixture_distribution`.

- `envelope_meets_trust_policy()` is the bridge from uncertainty semantics into
  kernel trust gates.

::: polisyos.ir.analytics.uncertainty

## Structural Causal Models

::: polisyos.ir.analytics.structural_causal_model

## Abstraction Certificates

`AbstractionCertificate` now distinguishes exact finite-state abstraction from
bounded approximate transport. Exact certificates still require a non-empty
`preserved_queries` tuple and no numeric `error_bound`. Invalid certificates
must not publish preserved queries or an error bound.

Approximate certificates are reserved for faithful micro-to-macro transport over
a query family, not a blanket claim that the macro model preserves every causal
query. They must carry:

- `preservation_type="approximate"`
- at least two `preserved_queries`
- a non-negative `error_bound` for the canonical scalar functional
- `metadata.abstraction_family` in `type_mean_affine`, `spatial_eep_linear`,
  `continuous_linear_gaussian`, or `continuous_lipschitz_dag`

- `metadata.allowed_intervention_family`
- `metadata.intervention_family_verified = true`
- `metadata.proof_obligations_satisfied`
- `metadata.estimand_error_bounds` covering every preserved query
- `metadata.non_preserved_queries`
- `metadata.diagnostics`

Continuous approximate families additionally require a machine-readable
`metadata.error_bound_spec` describing the verified query/intervention scope,
the underlying state and distribution metrics, the propagated global state
bound, the decision margin requirement `2 * error_bound`, and the disclosed
`tightness_status`. Use `verify_continuous_approximate_abstraction()` together
with `ContinuousApproximateAbstractionConfig` for the production-supported
Stage 7.1 paths:

- `continuous_linear_gaussian` for one-to-one affine abstractions of acyclic
  linear-Gaussian SCMs with closed-form interventional Gaussian error bounds

- `continuous_lipschitz_dag` for acyclic Lipschitz SCMs when certified local
  mechanism defects and a contracting gain matrix are available

Use `policy_value_only` when the certificate supports just one scalar welfare or
policy-value query. That mode also requires a non-negative `error_bound`, but it
does not claim a multi-estimand transport family.

::: polisyos.ir.analytics.abstraction

## Distributional Analysis

::: polisyos.ir.analytics.distributional

## Strategic Response (New)

`polisyos.ir.analytics.strategic` is not yet re-exported from the root
`polisyos.ir` facade, but it is the canonical home for strategic adaptation
artifacts used by readiness checks, strategic-response runners, and runtime
support evaluation.

For admissible game classes, tractability tags, and the strategic fallback
registry that normalizes `StrategicSCM.equilibrium_descriptor`, see
[Strategic Admissibility](strategic-admissibility.md).

`PerformativeShiftSummary` schema `1.1` now also carries optional
performative-loop certificates for iterative deployment. The certificate stays
attached to `StrategicResponseBundle.performative_shift_ref` and can record
global contraction bounds, local spectral-radius witnesses, dry-run cycle or
divergence evidence, and the recommended operational action
(`allow_auto_iteration`, `single_shot_only`, `block_auto_iteration`, and related
fallbacks).

Stage 6.4 adds a separate mean-field path instead of overloading
`selected_equilibrium_ref`. `MeanFieldPerturbationSpec` is the typed bridge
from `InterventionSpec` to coefficient/distributional/mixed HJB-FP
perturbations, `MeanFieldMacroSimulationConfig` records the replayable
macro-simulation numerics and Fabric inputs, and
`MeanFieldEquilibriumCertificate` is the leaf artifact attached through
`StrategicResponseBundle.mfg_equilibrium_ref`.

::: polisyos.ir.analytics.strategic

## Representation Learning And Latent Confounders

::: polisyos.ir.analytics.representation_learning

## Multi-Environment Invariance

::: polisyos.ir.analytics.invariance

## Causal Reinforcement Learning

::: polisyos.ir.analytics.causal_rl

## Time-Series Discovery Frontier

::: polisyos.ir.analytics.temporal_frontier

## Temporal Path Semantics (New)

`polisyos.ir.analytics.dynamic_regime` remains the canonical home for
continuous-time query and effect-trajectory contracts.

Stage 4.1 adds a second, proof-oriented layer in
`polisyos.ir.analytics.rough_path_semantics` so that irregular-sampling path
claims can say whether they identify:

- the represented lifted path
- the latent path itself
- only a signature-equivalence class

For the full safety rules and runtime posture, see
[Temporal Path Semantics](temporal-path-semantics.md).

## Recourse Manifold (New)

`polisyos.ir.analytics.recourse_manifold` is the typed-query surface for Stage
13.4 causal algorithmic recourse. It is intentionally separate from
`polisyos.ir.analytics.recourse`:

- `recourse` remains the explanation/report layer for user-facing recourse and
  counterfactual explanation payloads.

- `recourse_manifold` is the proof-carrying kernel-facing layer for
  manifold-scoped action geometry, recoverability-aware recourse queries, proof
  bundles, feasibility certificates, and planner results.

Use the module directly when you need:

- `InterventionCostManifold` to declare mutable/immutable nodes, action
  channels, admissible domains, and quotient cost semantics.

- `OptimalRecourseInterventionQuery` to encode the target outcome, threshold,
  semantics regime, success mode, and support budget.

- `RecourseProofBundle` / `RecourseFeasibilityCertificate` /
  `OptimalRecourseInterventionBundle` as the persisted proof, feasibility, and
  planning artifacts returned by the solver.

The package facade `polisyos.ir.analytics` stays curated, so these Stage 13.4
contracts should be imported from the defining module path rather than assumed
to exist on the facade root.

::: polisyos.ir.analytics.recourse_manifold

## Recourse And Explanations

::: polisyos.ir.analytics.recourse

## Validation Hooks

| Claim                                                                                             | Source of truth                            | Evidence                                                                                                          |
| ------------------------------------------------------------------------------------------------- | ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| Estimand normalization produces semantic content hashes                                           | `src/polisyos/ir/analytics/estimand.py`    | `tests/unit/ir/analytics/test_estimand_normalization.py`                                                          |
| Uncertainty algebra is explicit and trust-policy aware                                            | `src/polisyos/ir/analytics/uncertainty.py` | `tests/unit/ir/test_uncertainty.py`, `docs/adr/0012-uncertainty-envelope-ir-contract.md`                          |
| Causal, HTE, distributional, backtest, and transportability contracts are ABI-backed where public | `src/polisyos/schemas/abi_models.py`       | [JSON Schema Catalog](../schemas.md), `tests/unit/ir/analytics/test_shared_invariants.py`                         |
| Frontier causal reports are typed research contracts, not runtime support promises                | frontier analytics modules                 | `tests/unit/ir/test_frontier_causal_contracts.py`, `docs/adr/0110-ir-frontier-governance-and-causal-contracts.md` |
| Package facade counts and lazy import behavior stay ratcheted                                     | `src/polisyos/ir/api.py`                   | `tests/unit/ir/test_public_surface.py`                                                                            |

## Native causal reports in value search

The existing public `CausalEffectReport` model now declares the Foundry output
contract for its typed native causal result and can project its estimate and
statistical interval through `to_value_uncertainty()` when the caller supplies a
matching `NativeValueEstimandBinding`. This is only a typed non-gating
projection: `gate_eligible` remains false, and a failed, heuristic, or
coordinate-mismatched report cannot project a value interval. The report fields,
IR schema snapshot, and `polisyos.ir` exports do not change.

The N8 producer persists a v2 owner-method run basis that binds selected
profile bytes, typed owner run intent, assignment, panel input, method request,
a post-run execution receipt, and actual report. Its fresh consumer resolves the
selected manifest profile and compares each full input multiset before projecting
a ValueOuterSet. The receipt binds canonical submitted request intent, runner-returned
seed/backend/fingerprint, and exact persisted report bytes. Request values are
reconciled only when the native report directly exposes them; full used-parameter
coverage remains `not_established` because the current methods and runner do not
expose every effective parameter. Profileless historical/default views,
malformed estimand arrays, extra or duplicate lineage edges, and reused reports
under changed exposed request values are refused.
It keeps assignment/identification bounds separate from the method's statistical
CI. The current default owner gateway supplies no treatment assignment; absent
that external input, N8 remains blocked. Controlled DID and synthetic-control
tests show candidate-only implementation behavior and do not establish empirical
authority or production currentness. Historical basis v1 is not upgraded into a
v2 receipt-bearing run. V5 also rejects coercive JSON boolean, string, float, and null
values at the typed integer fields, and rejects boolean, string, and null assignment
bounds before any fresh projection.

### Scalar query graph admission

A scalar ID query consumes a strict detached snapshot of the complete causal
graph and edge fields. Public scalar entry points refuse PAG/CPDAG source tags
with a typed limitation while equivalence-class completion semantics remain
not adjudicated. Directed endpoints alone, a PAG policy field, or a previous
identified result do not authorize a completion. Direct TR admission rebuilds the
typed selection diagram and its S-node set together with the graph snapshot, then
consumes that returned object. Structural endpoint inspection remains separate;
valid resolved DAG/ADMG queries and their existing native cyclic, sigma, temporal,
and full-law owners are not redefined here.

### Graph-derived discovery diagnostics

A discovery audit derives CI and automatic trek-rank candidate diagnostics only
from its content-bound identity DAG snapshot. Each violated graph-derived
constraint carries assumption_status=unknown and
scope_of_falsification=ranking_only; automatic trek-rank diagnostics do not
become blockers from a graph-declared assumption regime alone. The persisted
DownstreamUtilityReport schema 1.2 carries those typed values on each
HypothesisUtilityScore, and GraphPriorBundle schema 1.2 carries them through
per-hypothesis evidence to cross-graph needs. Both writers bind payload and
manifest versions, and source-identification replay requires matching 1.2
artifacts before recomputing support. Exact manifest-bound schema-1.1 utility
and prior artifacts remain labeled 1.1 and are adapted only to routing with
unknown assumptions and ranking-only scope; they cannot enter current
source-proof replay. Unknown and future versions, or manifest/payload
mismatches, fail closed. Source completeness, population,
temporal scope, selection, and the distribution Markov assumption remain
unknown, so this signal is limited to candidate ranking and is not accepted by
the separate protected-promotion gate. PAG/CPDAG and other non-identity profiles
retain a typed skipped-family limitation. Partial-graph CI completion semantics
remain held for the G decision.

## Welfare nominal and Monte Carlo outputs with selected weights

`WelfareBundle` schema 1.1 carries the nominal PE and post-GE component vectors
returned by the real evaluator in the same label order as its selected
`ir.welfare_weights` ref. A fresh candidate-only reader recomputes the nominal
PE, GE, and total scalars from those vectors and the selected raw weight payload;
old schema 1.0 bundles remain readable but cannot support this source-bound
check.

`WelfareSampleBundle` schema 1.1 retains the actual response-component and
post-GE component vectors for each successful Monte Carlo draw, in the label
order carried by the same producer's `ir.welfare_weights` artifact. The
existing scalar welfare, PE and GE draw arrays remain available. A fresh
candidate-only welfare reader resolves the typed `WelfareBundle` refs against
its exact selected manifest roles and recomputes each weighted PE/total draw
from those persisted vectors and the selected raw weight vector. It also checks
the bundle's nominal PE/GE/total outputs against the separately persisted
nominal component operands; MC draw means remain distinct from nominal values.
The sample
manifest also carries that exact selected weight ref as a `welfare_weights`
input, which the fresh reader reconciles to the bundle's typed weight source. It
applies the stored weights as produced; this check does not normalize them or
assign units.
The welfare context materializer requests the same-write selected profile for a
newly persisted social-weight manifest; `ensure_social_weight_manifest_artifact()`
and `persist_social_weight_manifest()` keep a false-by-default opt-in for other
callers. That manifest is reconciled as a typed source role, not claimed to be
the vector applied by the welfare loop: application is recomputed only from the
separate `ir.welfare_weights` artifact. When the existing single-component
path defaults to `[1.0]`, a source-basis welfare producer persists that exact
existing vector and selected profile; ordinary calls keep the legacy no-ref
default. A supplied profileless manifest handle remains unqualified.

Historical WelfareBundle schema 1.0 and sample schema 1.0 remain readable by
the IR loader, but lack the typed nominal operands or raw draw vectors needed by
the source-bound reader's weight-application check. No old bundle or sample is
backfilled. The source-bound risk
observation remains candidate-only, with risk meaning, refinement, units,
valid time/currentness, independence and authority `not_established`.
