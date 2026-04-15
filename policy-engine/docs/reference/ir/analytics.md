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

## Source Modules

| Module | Focus | Key exports |
|--------|-------|-------------|
| `polisyos.ir.analytics.data_views` | Runtime data-view requests for panel, snapshot, and network inspection | `DataViewRequest`, `DataFilter`, `AccessTier`, `DataViewType` |
| `polisyos.ir.analytics.causal` | Core causal effect reports and robustness metadata | `CausalEffectReport`, `RefutationResult`, `DiagnosticTest`, `PlaceboResult` |
| `polisyos.ir.analytics.causal_queries` | Interventional, counterfactual, and soft-intervention query contracts | `CausalQuery`, `InterventionSpec`, `CausalQueryResult` |
| `polisyos.ir.analytics.causal_discovery` | Discovery reports, latent diagnostics, and algebraic constraints | `CausalDiscoveryReport` |
| `polisyos.ir.analytics.causal_ensemble` | Structural uncertainty bundles across graph candidates | `EnsembleMember`, `CausalModelEnsemble` |
| `polisyos.ir.analytics.ecosystem_bridges` | Exchange contracts for DoWhy, EconML, CausalNex, pgmpy, and Tigramite | `DoWhyGraphBridge`, `EconMLDesignBridge`, `PgmpyGraphBridge`, `TigramitePCMCIBridge` |
| `polisyos.ir.analytics.hte` | Heterogeneous treatment effects and targeting outputs | `HTEResult`, `SubgroupEffect`, `FeatureImportance`, `PolicyRecommendation` |
| `polisyos.ir.analytics.backtest` | Historical validation and trust diagnostics | `BacktestReport`, `BacktestScenario`, `SystematicBias` |
| `polisyos.ir.analytics.uncertainty` | Unified interval semantics and propagation metadata | `UncertaintyEnvelope`, `DistributionFamily`, `PropagationMethod` |
| `polisyos.ir.analytics.structural_causal_model` | Structural mechanism declarations | `MechanismFamily`, `MechanismSource`, `NodeMechanism`, `StructuralCausalModelSpec` |
| `polisyos.ir.analytics.distributional` | Cohort-level winners/losers and inequality summaries | `DistributionalReport`, `DimensionBreakdown`, `WinnersLosersTable` |
| `polisyos.ir.analytics.strategic` | Strategic adaptation, equilibria, and performative-shift artifacts | `FiniteStrategicPayoffTable`, `StrategicSCM`, `StrategicResponseBundle` |
| `polisyos.ir.analytics.representation_learning` | Latent confounder and representation-learning contracts | `LatentConfounderContract`, `RepresentationLearningResult`, `RepresentationModelFamily` |
| `polisyos.ir.analytics.invariance` | Multi-environment invariance and shift-aware diagnostics | `MultiEnvironmentCausalContract`, `InvarianceResult`, `EnvironmentSpec` |
| `polisyos.ir.analytics.causal_rl` | Causal MDP/POMDP and counterfactual policy optimization | `CausalRLContract`, `CounterfactualPolicyOptimizationSpec`, `CausalRLResult` |
| `polisyos.ir.analytics.temporal_frontier` | PCMCI/Granger/Hawkes/SDE/regime-switching discovery outputs | `TemporalDiscoveryFrontierReport`, `TemporalDiscoveryEdge`, `EquivalenceClassSummary` |
| `polisyos.ir.analytics.recourse` | Algorithmic recourse, counterfactual and contrastive explanations | `RecourseReport`, `RecoursePlan`, `CounterfactualExplanation` |

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
- `distribution_payload` carries richer posterior shapes:
  `posterior_samples`, `quantile_summary`, `parametric_fit`, and
  `mixture_distribution`.
- `envelope_meets_trust_policy()` is the bridge from uncertainty semantics into
  kernel trust gates.

::: polisyos.ir.analytics.uncertainty

## Structural Causal Models

::: polisyos.ir.analytics.structural_causal_model

## Distributional Analysis

::: polisyos.ir.analytics.distributional

## Strategic Response (New)

`polisyos.ir.analytics.strategic` is not yet re-exported from the root
`polisyos.ir` facade, but it is the canonical home for strategic adaptation
artifacts used by readiness checks, strategic-response runners, and runtime
support evaluation.

::: polisyos.ir.analytics.strategic

## Representation Learning And Latent Confounders

::: polisyos.ir.analytics.representation_learning

## Multi-Environment Invariance

::: polisyos.ir.analytics.invariance

## Causal Reinforcement Learning

::: polisyos.ir.analytics.causal_rl

## Time-Series Discovery Frontier

::: polisyos.ir.analytics.temporal_frontier

## Recourse And Explanations

::: polisyos.ir.analytics.recourse
