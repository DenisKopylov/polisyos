# Observation IR

Related explanation: [Observation Contracts](../../explanation/observation-contracts.md).

> Observation records, family policies, bundle manifests, compiler-facing contracts, and causal readiness/execution artifacts.

The observation layer is the largest new IR surface in this documentation pass.
It turns heterogeneous evidence into typed records and panels, routes that
evidence through governance and measurement-aware rules, and materializes the
bundle manifests that Scientist and Foundry exchange.

Freshness: 2026-04-17
Owner: `@ir-owners`
Source of truth: `src/polisyos/ir/observation/**`, `src/polisyos/ir/references/`, `schemas/snapshots/ir/*.schema.json`, `tests/unit/ir/observation/**`
Source plan phases: D1-L4 Phase 2 lineage/analysis contracts and Phase 4 transport/interoperability.

## Contract Layers

- Raw observations: `ObservationRecord` and `ObservationPanel` hold normalized
  source measurements plus entity/time locators and explicit identification
  metadata. They are the evidence rows before family policy or readiness
  preflight is applied.

- Observation family policy: `ObservationFamilyPolicy*` declares default
  identification modes, fallback semantics, and mandatory governance passes per
  family. `GovernancePassAlias*` maps stable IR pass ids to runtime pass names.

- Measurement trust and routing: `MeasurementRegistry` converts raw source
  confidence, coverage, bias flags, and proxy metadata into
  `MeasurementTrustTier`; `IdentificationModeRouter` then resolves the effective
  mode and fallback reason that compilers/readiness checks should honor.

- Readiness manifests: `CausalReadinessBundle` records proxy,
  transportability, counterfactual, interference, and strategic-response
  preflight outcomes before execution is allowed.

- Execution manifests: `BoundsEstimationTask`, `TemporalDTRTask`, and
  `CausalExecutionBundle` represent the task/result boundary after readiness
  passes and are the artifacts that downstream governance/reporting should read.

## Source Modules

| Module                                       | Focus                                                 | Top-level IR exports                                                                                                                       |
| -------------------------------------------- | ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `polisyos.ir.observation.contracts`          | Core record and panel contracts                       | `ObservationFamily`, `EntityScope`, `IdentificationMode`, `ObservationRecord`, `ObservationPanel`                                          |
| `polisyos.ir.observation.bridges`            | External data-standard bridge contracts               | `SdmxObservationBridge`, `DdiVariableBridge`, `FhirObservationBridge`, `CdiscDatasetBridge`                                                |
| `polisyos.ir.observation.governance`         | Family-level governance defaults and alias registries | `GovernancePassAlias*`, `ObservationFamilyPolicy*`, `GovernancePassMappingRegistry`                                                        |
| `polisyos.ir.observation.measurement`        | Measurement-aware trust tiers, calendars, and routing | `MeasurementRegistry`, `MeasurementTrustTier`, `RegimeCalendar`, `SchemaRegimeRegistry`, `IdentificationModeRouter`                        |
| `polisyos.ir.observation.bundles`            | Persisted manifests and contract bundles              | `BacktestPlanBundle`, `BoundsEstimationBundle`, `CausalPanelBundleManifest`, `StrategicResponseSpecsBundle`, `GovernancePassMappingBundle` |
| `polisyos.ir.observation.compiler`           | Calibration split and negative-control planning       | `CalibrationSplitLabel`, `CalibrationSplitPlan`, `NegativeControlSpec`                                                                     |
| `polisyos.ir.observation.contract_compilers` | IR-facing compiler inputs and helper contracts        | `BoundsEstimationInput`, `GraphArtifacts`, `ProxyMap`, `ObservationContractCompilerSuite`, `SparseDenseBridge`                             |
| `polisyos.ir.observation.causal_readiness`   | Pre-execution causal checks                           | `CausalReadinessBundle`                                                                                                                    |
| `polisyos.ir.observation.causal_execution`   | Executable tasks and persisted results                | `BoundsEstimationTask`, `TemporalDTRTask`, `CausalExecutionBundle`                                                                         |

## Core Contracts

::: polisyos.ir.observation.contracts

## Standards Bridges

::: polisyos.ir.observation.bridges

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

## Validation Hooks

| Claim                                                                       | Source of truth                                             | Evidence                                                                                                                                              |
| --------------------------------------------------------------------------- | ----------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| Observation records, panels, and family policies are ABI-visible contracts  | `src/polisyos/ir/observation/contracts.py`, `governance.py` | `schemas/snapshots/ir/observation_record.schema.json`, `schemas/snapshots/ir/observation_panel.schema.json`, `tests/unit/ir/observation/test_contracts.py` |
| Measurement routing selects trust tiers and identification modes explicitly | `src/polisyos/ir/observation/measurement.py`                | `tests/unit/ir/observation/test_measurement.py`, `tests/unit/ir/observation/test_causal_readiness.py`                                                           |
| Bundle manifests preserve downstream contract targets and lineage           | `src/polisyos/ir/observation/bundles.py`                    | `tests/unit/ir/observation/test_bundle_schemas.py`, [JSON Schema Catalog](../schemas.md)                                                                   |
| Observation bridge contracts remain dependency-light                        | `src/polisyos/ir/observation/bridges.py`                    | `tests/unit/ir/test_interoperability_bridges.py`                                                                                                           |
| Execution bundles feed compiler-pipeline lineage analysis                   | `src/polisyos/ir/observation/causal_execution.py`           | `tests/unit/ir/test_phase2_passes.py`                                                                                                                      |
