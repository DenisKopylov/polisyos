# Analytics IR

Related explanation: [Causal Engine](../../explanation/causal-engine.md).

> Causal, heterogeneity, backtest, uncertainty, and strategic-response artifacts emitted by Foundry and Scientist.

This page follows the analytics surface that is already exposed from
`polisyos.ir`, and also documents the new `polisyos.ir.analytics.strategic`
module because it is central to the observation-aware policy workflow.

`polisyos.ir.analytics` itself is now a curated lazy facade: it re-exports the
most common analytics contracts, but it is no longer a wildcard mirror of
every analytics implementation module. For advanced/report-specific APIs use
the defining submodule import path.

Freshness: 2026-04-20
Owner: `@ir-owners`
Source of truth: `src/polisyos/ir/analytics/**`, `src/polisyos/ir/refs.py`, `schemas/snapshots/ir/*.schema.json`, `tests/unit/ir/analytics/**`, `tests/unit/ir/test_uncertainty.py`, `tests/unit/ir/test_frontier_causal_contracts.py`
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
| `polisyos.ir.analytics.backtest`                | Historical validation and trust diagnostics                                                                       | `BacktestReport`, `BacktestScenario`, `SystematicBias`                                                                                                       |
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

## Discovery And Structural Uncertainty

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

| Claim                                                                                             | Source of truth                            | Evidence                                                                                                     |
| ------------------------------------------------------------------------------------------------- | ------------------------------------------ | ------------------------------------------------------------------------------------------------------------ |
| Estimand normalization produces semantic content hashes                                           | `src/polisyos/ir/analytics/estimand.py`    | `tests/unit/ir/analytics/test_estimand_normalization.py`                                                          |
| Uncertainty algebra is explicit and trust-policy aware                                            | `src/polisyos/ir/analytics/uncertainty.py` | `tests/unit/ir/test_uncertainty.py`, `docs/adr/0012-uncertainty-envelope-ir-contract.md`                          |
| Causal, HTE, distributional, backtest, and transportability contracts are ABI-backed where public | `schemas/abi_models.py`                    | [JSON Schema Catalog](../schemas.md), `tests/unit/ir/analytics/test_shared_invariants.py`                         |
| Frontier causal reports are typed research contracts, not runtime support promises                | frontier analytics modules                 | `tests/unit/ir/test_frontier_causal_contracts.py`, `docs/adr/0110-ir-frontier-governance-and-causal-contracts.md` |
| Package facade counts and lazy import behavior stay ratcheted                                     | `src/polisyos/ir/public_surface.py`        | `tests/unit/ir/test_public_surface.py`                                                                            |
