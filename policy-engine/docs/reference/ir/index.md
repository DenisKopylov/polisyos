# IR — Intermediate Representation
Related explanation: [Trinity](../../explanation/trinity.md).

> Canonical contract layer for 171 top-level exports covering policy authoring, analytics, observation, and reflection tooling.

`polisyos.ir` holds schema-first contracts, enums, manifests, and typed artifact
references. The package is intentionally execution-free: Scientist and Foundry
consume these models, but business logic lives outside the IR layer.

## Page Map

| Page | Scope | Primary modules |
|------|-------|-----------------|
| [Public Surface](public-surface.md) | Documented package facades, naming rules, and export-audit policy | `ir.analytics`, `ir.kernel`, `ir.world`, `ir.public_surface` |
| [Schema Catalog](schema-catalog.md) | Generated inventory of IR types, fields, refs, docs anchors, and ABI linkage | `ir.schema_catalog`, generated reference pages |
| [Compiler Pipeline](compiler-pipeline.md) | Pass manager, analysis cache, estimand normalization, lineage graph, dead-artifact diagnostics | `ir.passes`, `ir.analytics.estimand`, `ir.artifacts.lineage` |
| [Interoperability](interoperability.md) | Transport contracts, PROV-O mapping, standards bridges, and causal ecosystem exchange | `ir.artifacts.transport`, `ir.world.prov_o`, `ir.observation.bridges`, `ir.analytics.ecosystem_bridges` |
| [Governance](governance.md) | Policy authoring, governance aliases, gate payloads | `ir.governance.*`, `ir.observation.governance` |
| [Analytics](analytics.md) | Causal, HTE, backtest, uncertainty, strategic response | `ir.analytics.*` |
| [Observation](observation.md) | Records, panels, manifests, routing, readiness, execution | `ir.observation.*` |
| [Problem Framing](problem-framing.md) | Goals, KPIs, constraints, stakeholders | `ir.governance.problem_frame` |

## Core Policy And Governance Exports

| Source module | Count | Exports |
|---------------|-------|---------|
| `polisyos.ir.connectors` | 4 | `ConnectorCapability`, `ConnectorMetadataSpec`, `QualityTier`, `TrustLevel` |
| `polisyos.ir.analytics.data_views` | 4 | `AccessTier`, `DataFilter`, `DataViewRequest`, `DataViewType` |
| `polisyos.ir.norm_pack` | 4 | `NormPack`, `NormRule`, `NormRef`, `RuleType` |
| `polisyos.ir.loaders` | 1 | `load_policy` |
| `polisyos.ir.schema_catalog` | 11 | `IRExportInfo`, `IRFieldInfo`, `IRPublicStatus`, `IRSchemaCatalog`, `IRTypeInfo`, `IRTypeKind`, `enumerate_ir_exports`, `get_ir_schema_catalog`, `get_ir_type`, `inspect_ir_schema`, `list_ir_types` |
| `polisyos.ir.governance.problem_frame` | 7 | `ProblemFrame`, `ProblemDomain`, `KPISpec`, `SuccessCriterion`, `ProblemConstraintSpec`, `ConstraintType`, `StakeholderSpec` |
| `polisyos.ir.governance.policy_spec` | 6 | `PolicySpec`, `PolicyInterventionSpec`, `MechanismBinding`, `ParameterSpec`, `TemporalInterventionSequence`, `TemporalInterventionStep` |
| `polisyos.ir.governance.gate` | 7 | `GateContext`, `GateDecision`, `GateEvent`, `GateEventType`, `GatePriority`, `GateRequest`, `GateVerdict` |
| `polisyos.ir.model_spec` | 8 | `ModelSpec`, `FidelityLevel`, `AssumptionSpec`, `AssumptionType`, `AgentConfig`, `AgentTypeConfig`, `EnvironmentConfig`, `EnvironmentParam` |
| `polisyos.ir.portfolio` | 4 | `PolicyPortfolio`, `PolicyInteraction`, `InteractionMatrix`, `InteractionType` |
| `polisyos.ir.refs` | 4 | `CausalQueryResultRef`, `CausalExecutionBundleRef`, `CausalModelEnsembleRef`, `TransportabilityResultRef` |

## Analytics Exports

| Source module | Count | Exports |
|---------------|-------|---------|
| `polisyos.ir.analytics.calibration` | 2 | `CalibrationConfig`, `CalibrationTarget` |
| `polisyos.ir.analytics.causal` | 7 | `CausalMethod`, `EstimationStatus`, `RefutationTestType`, `RefutationResult`, `CausalEffectReport`, `DiagnosticTest`, `PlaceboResult` |
| `polisyos.ir.analytics.causal_discovery` | 1 | `CausalDiscoveryReport` |
| `polisyos.ir.analytics.causal_ensemble` | 2 | `EnsembleMember`, `CausalModelEnsemble` |
| `polisyos.ir.analytics.causal_queries` | 6 | `QueryType`, `InterventionType`, `InterventionSpec`, `CausalInterventionSpec`, `CausalQuery`, `CausalQueryResult` |
| `polisyos.ir.analytics.transportability` | 1 | `TransportabilityResult` |
| `polisyos.ir.analytics.structural_causal_model` | 4 | `MechanismFamily`, `MechanismSource`, `NodeMechanism`, `StructuralCausalModelSpec` |
| `polisyos.ir.analytics.uncertainty` | 5 | `DistributionFamily`, `IntervalSemantics`, `PropagationMethod`, `UncertaintyEnvelope`, `UncertaintySource` |
| `polisyos.ir.analytics.distributional` | 8 | `CohortDimension`, `ImpactDirection`, `MetricUnit`, `CohortImpact`, `DimensionBreakdown`, `WinnersLosersEntry`, `WinnersLosersTable`, `DistributionalReport` |
| `polisyos.ir.analytics.hte` | 5 | `SubgroupEffect`, `FeatureImportance`, `HTEResult`, `TargetingRule`, `PolicyRecommendation` |
| `polisyos.ir.analytics.backtest` | 5 | `BiasDirection`, `OutcomeComparison`, `SystematicBias`, `BacktestScenario`, `BacktestReport` |

## Observation Exports

| Source module | Count | Exports |
|---------------|-------|---------|
| `polisyos.ir.observation.contracts` | 8 | `EntityScope`, `IdentificationMode`, `MultiplexGraphLayerId`, `ObservationFamily`, `ObservationPanel`, `ObservationRecord`, `SourceConfidenceTier`, `StrategicResponseChannel` |
| `polisyos.ir.observation.governance` | 6 | `GovernancePassAlias`, `GovernancePassAliasRegistry`, `GovernancePassAliasStatus`, `GovernancePassMappingRegistry`, `ObservationFamilyPolicy`, `ObservationFamilyPolicyRegistry` |
| `polisyos.ir.observation.measurement` | 9 | `IdentificationModeRouter`, `IdentificationRoute`, `MeasurementRegistry`, `MeasurementTrustTier`, `RegimeCalendar`, `SchemaChangepoint`, `SchemaRegimeRegistry`, `SchemaRegimeSpec`, `ShockCalendar` |
| `polisyos.ir.observation.bundles` | 20 | `GovernancePassMappingBundle`, `BacktestPlanBundle`, `BoundsEstimationBundle`, `CalibrationTargetBundleManifest`, `CausalPanelBundleManifest`, `DTRTreatmentSequenceBundleManifest`, `LessonRegistrySeedBundle`, `LeontiefIOBundle`, `MicrosimSurveyContractBundle`, `NetworkCausalContractBundle`, `NetworkContractBundle`, `ObservationToContractManifest`, `PanelEconometricBundleManifest`, `ProxyIdentificationBundle`, `TransportabilityCheckBundle`, `CounterfactualCheckBundle`, `InterferenceLossSpecBundle`, `SpecificationCurveBundle`, `StrategicResponseSpecsBundle`, `SurvivalDataBundleManifest` |
| `polisyos.ir.observation.compiler` | 4 | `CalibrationSplitLabel`, `CalibrationSplitPlan`, `CalibrationSplitWindow`, `NegativeControlSpec` |
| `polisyos.ir.observation.contract_compilers` | 10 | `BoundsEstimationInput`, `FirmEvents`, `FirmPanels`, `GraphArtifacts`, `LeontiefIOInput`, `ObservationContractCompilerSuite`, `ProxyMap`, `RegionSectorPanels`, `SpecificationCurveInput`, `SparseDenseBridge` |
| `polisyos.ir.observation.causal_readiness` | 1 | `CausalReadinessBundle` |
| `polisyos.ir.observation.causal_execution` | 7 | `BoundsEstimationTask`, `BoundsEstimationEntry`, `TemporalDTRTask`, `TemporalDTRExecutionEntry`, `CausalExecutionBundle`, `load_causal_execution_bundle`, `persist_causal_execution_bundle` |

## Notes

- The root facade now exposes 171 unique names, including the reflection API in `polisyos.ir.schema_catalog`.
- `docs/reference/ir/schema-catalog.md` is generated from the same reflection layer that powers export/schema inspection.
- `docs/reference/ir/compiler-pipeline.md` documents the execution-free pass layer introduced for compiler-grade IR validation and normalization.
- `docs/reference/ir/analytics.md` also documents `polisyos.ir.analytics.strategic`, which is new in code but not yet re-exported from the root `polisyos.ir` facade.
- Package-level facades are audited separately from the root boundary; see [Public Surface](public-surface.md) for lazy-facade policy and naming conventions.
