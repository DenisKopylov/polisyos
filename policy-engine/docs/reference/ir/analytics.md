# Analytics IR
Related explanation: [Causal Engine](../../explanation/causal-engine.md).

> Causal, heterogeneity, backtest, uncertainty, and strategic-response artifacts emitted by Foundry and Scientist.

This page follows the analytics surface that is already exposed from
`polisyos.ir`, and also documents the new `polisyos.ir.analytics.strategic`
module because it is central to the observation-aware policy workflow.

## Source Modules

| Module | Focus | Key exports |
|--------|-------|-------------|
| `polisyos.ir.analytics.data_views` | Runtime data-view requests for panel, snapshot, and network inspection | `DataViewRequest`, `DataFilter`, `AccessTier`, `DataViewType` |
| `polisyos.ir.analytics.causal` | Core causal effect reports and robustness metadata | `CausalEffectReport`, `RefutationResult`, `DiagnosticTest`, `PlaceboResult` |
| `polisyos.ir.analytics.causal_queries` | Interventional, counterfactual, and soft-intervention query contracts | `CausalQuery`, `InterventionSpec`, `CausalQueryResult` |
| `polisyos.ir.analytics.causal_discovery` | Discovery reports, latent diagnostics, and algebraic constraints | `CausalDiscoveryReport` |
| `polisyos.ir.analytics.causal_ensemble` | Structural uncertainty bundles across graph candidates | `EnsembleMember`, `CausalModelEnsemble` |
| `polisyos.ir.analytics.hte` | Heterogeneous treatment effects and targeting outputs | `HTEResult`, `SubgroupEffect`, `FeatureImportance`, `PolicyRecommendation` |
| `polisyos.ir.analytics.backtest` | Historical validation and trust diagnostics | `BacktestReport`, `BacktestScenario`, `SystematicBias` |
| `polisyos.ir.analytics.uncertainty` | Unified interval semantics and propagation metadata | `UncertaintyEnvelope`, `DistributionFamily`, `PropagationMethod` |
| `polisyos.ir.analytics.structural_causal_model` | Structural mechanism declarations | `MechanismFamily`, `MechanismSource`, `NodeMechanism`, `StructuralCausalModelSpec` |
| `polisyos.ir.analytics.distributional` | Cohort-level winners/losers and inequality summaries | `DistributionalReport`, `DimensionBreakdown`, `WinnersLosersTable` |
| `polisyos.ir.analytics.strategic` | Strategic adaptation, equilibria, and performative-shift artifacts | `FiniteStrategicPayoffTable`, `StrategicSCM`, `StrategicResponseBundle` |

## Data View Requests

::: polisyos.ir.analytics.data_views

## Causal Effects And Robustness

::: polisyos.ir.analytics.causal

## Causal Queries

::: polisyos.ir.analytics.causal_queries

## Discovery And Structural Uncertainty

::: polisyos.ir.analytics.causal_discovery

::: polisyos.ir.analytics.causal_ensemble

## Heterogeneous Effects And Targeting

::: polisyos.ir.analytics.hte

## Backtesting And Trust

::: polisyos.ir.analytics.backtest

## Uncertainty Envelopes

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
