# Observation IR
Related explanation: [Observation Contracts](../../explanation/observation-contracts.md).

> Observation records, family policies, bundle manifests, compiler-facing contracts, and causal readiness/execution artifacts.

The observation layer is the largest new IR surface in this documentation pass.
It turns heterogeneous evidence into typed records and panels, routes that
evidence through governance and measurement-aware rules, and materializes the
bundle manifests that Scientist and Foundry exchange.

## Source Modules

| Module | Focus | Top-level IR exports |
|--------|-------|----------------------|
| `polisyos.ir.observation.contracts` | Core record and panel contracts | `ObservationFamily`, `EntityScope`, `IdentificationMode`, `ObservationRecord`, `ObservationPanel` |
| `polisyos.ir.observation.governance` | Family-level governance defaults and alias registries | `GovernancePassAlias*`, `ObservationFamilyPolicy*`, `GovernancePassMappingRegistry` |
| `polisyos.ir.observation.measurement` | Measurement-aware trust tiers, calendars, and routing | `MeasurementRegistry`, `MeasurementTrustTier`, `RegimeCalendar`, `SchemaRegimeRegistry`, `IdentificationModeRouter` |
| `polisyos.ir.observation.bundles` | Persisted manifests and contract bundles | `BacktestPlanBundle`, `BoundsEstimationBundle`, `CausalPanelBundleManifest`, `StrategicResponseSpecsBundle`, `GovernancePassMappingBundle` |
| `polisyos.ir.observation.compiler` | Calibration split and negative-control planning | `CalibrationSplitLabel`, `CalibrationSplitPlan`, `NegativeControlSpec` |
| `polisyos.ir.observation.contract_compilers` | IR-facing compiler inputs and helper contracts | `BoundsEstimationInput`, `GraphArtifacts`, `ProxyMap`, `ObservationContractCompilerSuite`, `SparseDenseBridge` |
| `polisyos.ir.observation.causal_readiness` | Pre-execution causal checks | `CausalReadinessBundle` |
| `polisyos.ir.observation.causal_execution` | Executable tasks and persisted results | `BoundsEstimationTask`, `TemporalDTRTask`, `CausalExecutionBundle` |

## Core Contracts

::: polisyos.ir.observation.contracts

## Governance And Family Policies

::: polisyos.ir.observation.governance

## Measurement-Aware Routing

::: polisyos.ir.observation.measurement

## Bundles And Manifests

::: polisyos.ir.observation.bundles

## Compiler-Facing IR Contracts

This section focuses on the IR-facing inputs and orchestration contracts that
are re-exported from `polisyos.ir`. Implementation-only helper compilers are
still documented primarily in source.

::: polisyos.ir.observation.compiler

::: polisyos.ir.observation.contract_compilers

## Causal Readiness And Execution

::: polisyos.ir.observation.causal_readiness

::: polisyos.ir.observation.causal_execution
