# Public Surface

> Generated from `architecture/public_surface.toml` and package facades under `src/polisyos/**/__init__.py`.

Canonical regeneration command:

```bash
uv run python tools/devx/architecture/guardrails.py sync --skip-deep-import-baseline
```

Supported entrypoints are intentionally explicit. Any `polisyos.*` path not listed on this page is **internal** and may change without compatibility guarantees.

Classification policy:

- `public_stable`: supported entrypoint with normal compatibility, release-note, and migration expectations.
- `public_experimental`: documented entrypoint that should stay visible in docs and release notes when touched, but it does not promise long-term compatibility.
- `internal`: any `polisyos.*` path not listed here; keep it out of public docs and release notes unless operators must care.

| Package | Classification | Facade | Exports | Owner | README |
| --- | --- | --- | ---: | --- | --- |
| `polisyos.common` | `public_stable` | `lazy_facade` | 7 | `team-polisyos` | `src/polisyos/common/README.md` |
| `polisyos.core` | `public_stable` | `lazy_facade` | 15 | `team-polisyos` | `src/polisyos/core/README.md` |
| `polisyos.ir` | `public_stable` | `lazy_facade` | 273 | `team-polisyos` | `src/polisyos/ir/README.md` |
| `polisyos.fabric` | `public_stable` | `lazy_facade` | 30 | `team-polisyos` | `src/polisyos/fabric/README.md` |
| `polisyos.foundry` | `public_stable` | `lazy_facade` | 3 | `team-polisyos` | `src/polisyos/foundry/README.md` |
| `polisyos.scientist` | `public_stable` | `lazy_facade` | 7 | `team-polisyos` | `src/polisyos/scientist/README.md` |
| `polisyos.runtime` | `public_stable` | `lazy_facade` | 10 | `team-polisyos` | `src/polisyos/runtime/README.md` |
| `polisyos.lex` | `public_stable` | `lazy_facade` | 50 | `team-polisyos` | `src/polisyos/lex/README.md` |
| `polisyos.scholar` | `public_experimental` | `lazy_facade` | 16 | `team-polisyos` | `src/polisyos/scholar/README.md` |
| `polisyos.data_forge` | `public_experimental` | `lazy_facade` | 33 | `team-data-forge` | `src/polisyos/data_forge/README.md` |
| `polisyos.berl` | `public_experimental` | `eager_exports` | 11 | `team-scientist` | `src/polisyos/berl/README.md` |
| `polisyos.calibration` | `public_experimental` | `eager_exports` | 10 | `team-scientist` | `src/polisyos/calibration/README.md` |
| `polisyos.ddm` | `internal` | `eager_exports` | 17 | `team-scientist` | `src/polisyos/ddm/README.md` |
| `polisyos.ddm_15_7` | `compatibility` | `eager_exports` | 17 | `team-architecture` | `src/polisyos/ddm_15_7/README.md` |
| `polisyos.foundry.agent_sim.world` | `public_experimental` | `eager_exports` | 23 | `team-foundry` | `src/polisyos/foundry/agent_sim/world/README.md` |
| `polisyos.synthetic_world` | `compatibility` | `eager_exports` | 23 | `team-foundry` | `src/polisyos/synthetic_world/README.md` |

## `polisyos.common`

- Classification: `public_stable`
- Supported entrypoints: `polisyos.common`
- Facade policy: expected `lazy_facade`, observed `lazy_facade`
- Owner: `team-polisyos`
- README: `src/polisyos/common/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Shared helper boundary for config, logging, serialization, and migrations.
- Summary: Expose side-effect-sensitive common helpers behind a lazy package facade.

<details><summary>Supported exports (7)</summary>

```text
async_tools
config
jax_env
logger
migrations
serialization
timestamps
```

</details>

## `polisyos.core`

- Classification: `public_stable`
- Supported entrypoints: `polisyos.core`
- Facade policy: expected `lazy_facade`, observed `lazy_facade`
- Owner: `team-polisyos`
- README: `src/polisyos/core/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Cross-layer contracts, CAS, registry, observability, and security primitives.
- Summary: Expose the stable Core platform surface with lazy package imports.

<details><summary>Supported exports (15)</summary>

```text
artifacts
backends
cache
canon
components
contracts
discovery
errors
evaluation
llm
observability
pipeline
registry
resilience
run
```

</details>

## `polisyos.ir`

- Classification: `public_stable`
- Supported entrypoints: `polisyos.ir`, `polisyos.ir.api`
- Facade policy: expected `lazy_facade`, observed `lazy_facade`
- Owner: `team-polisyos`
- README: `src/polisyos/ir/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Primary compatibility boundary for policy, governance, analytics, and observation contracts; api.py owns public-surface helper metadata.
- Summary: Expose the stable IR contract surface through a lazy package facade.

<details><summary>Supported exports (273)</summary>

```text
ABMBifurcationReport
ABMIdentifiabilityCertificate
ABMResult
ABMResultRef
AccessTier
AdministrativeMissingnessClass
AdministrativeMissingnessDirection
AdministrativeMissingnessMetadata
AdministrativeMissingnessScenarioFamily
AdministrativeMissingnessUnitScope
AgentConfig
AgentTypeConfig
AssumptionSpec
AssumptionType
BacktestPlanBundle
BacktestReport
BacktestScenario
BiasDirection
BlockSupportReport
BoundsEstimationBundle
BoundsEstimationEntry
BoundsEstimationInput
BoundsEstimationTask
CalibrationConfig
CalibrationSplitLabel
CalibrationSplitPlan
CalibrationSplitWindow
CalibrationTarget
CalibrationTargetBundleManifest
CausalBlockBridge
CausalBlockBridgeRef
CausalDiscoveryReport
CausalEffectReport
CausalExecutionBundle
CausalExecutionBundleRef
CausalInterventionSpec
CausalMethod
CausalModelEnsemble
CausalModelEnsembleRef
CausalPanelBundleManifest
CausalQuery
CausalQueryResult
CausalQueryResultRef
CausalReadinessBundle
CohortDimension
CohortImpact
ConnectorCapability
ConnectorMetadataSpec
ConstraintType
CounterfactualCheckBundle
DTRTreatmentSequenceBundleManifest
DataFilter
DataViewRequest
DataViewType
DependenceStructure
DependenceStructureRef
DependentSensitivityAnalysisBundle
DependentSensitivityAnalysisBundleRef
DependentSensitivityResult
DependentSensitivityResultRef
DetectorResult
DiagnosticTest
DimensionBreakdown
DistributionFamily
DistributionalReport
DriftReadinessRef
DynamicMicrosimValidationReport
DynamicMicrosimValidationReportRef
EnsembleMember
EntityScope
EnvironmentConfig
EnvironmentParam
EquilibriumMultiplicityWelfareAnnotation
EstimationStatus
ExplanationBundleRef
ExposureMappingType
FanChartSpec
FeatureImportance
FidelityLevel
FirmEvents
FirmPanels
ForecastCalibrationMethod
ForecastCoverageDiagnostic
ForecastIntervalSemantics
ForecastShiftTypeAssessment
ForecastingUncertaintyBundle
ForecastingUncertaintyBundleRef
ForecastingUncertaintyBundleV2
GEUncertaintyBundle
GEUncertaintyBundleRef
GEUncertaintyRepresentation
GateContext
GateDecision
GateEvent
GateEventType
GatePriority
GateRequest
GateVerdict
GovernancePassAlias
GovernancePassAliasRegistry
GovernancePassAliasStatus
GovernancePassMappingBundle
GovernancePassMappingRegistry
GraphArtifacts
HTEResult
HorizonInterval
HorizonPolicySpec
IRExportInfo
IRFieldInfo
IRPublicStatus
IRSchemaCatalog
IRTypeInfo
IRTypeKind
IdentificationMode
IdentificationModeRouter
IdentificationRoute
ImpactDirection
InteractionComplex
InteractionComplexRef
InteractionMatrix
InteractionType
InterferenceCertificate
InterferenceCertificateRef
InterferenceEffectDecomposition
InterferenceLossSpecBundle
InterferenceMethod
IntervalSemantics
InterventionSpec
InterventionType
JudgeVerdictRef
KPISpec
LeontiefIOBundle
LeontiefIOInput
LessonRegistrySeedBundle
MAUPInvarianceCertificate
MAUPInvarianceCertificateRef
MAUPPartitionCheck
MeasurementRegistry
MeasurementTrustTier
MechanismBinding
MechanismFamily
MechanismSource
MetricUnit
MicrosimCalibrationReport
MicrosimCalibrationReportRef
MicrosimSurveyContractBundle
MissingnessAssessmentProvenance
MissingnessAssessmentReport
MissingnessAssessmentStatus
MissingnessEstimandRisk
MissingnessEvidenceItem
MobilityReport
MobilityReportRef
ModelSpec
MultiplexGraphLayerId
NegativeControlSpec
NetworkCausalContractBundle
NetworkContractBundle
NetworkInterferenceReport
NodeMechanism
NormPack
NormRef
NormRule
ObservationContractCompilerSuite
ObservationFamily
ObservationFamilyPolicy
ObservationFamilyPolicyRegistry
ObservationPanel
ObservationRecord
ObservationToContractManifest
OperatingCharacteristicKey
OperatingCharacteristicLibrary
OperatingCharacteristicRecord
OutcomeComparison
PanelEconometricBundleManifest
ParameterSpec
Phase4DynamicsGate
Phase4GateStatus
Phase4TemporalPolicyGateVerdict
PlaceboResult
PolicyInteraction
PolicyInterventionSpec
PolicyPortfolio
PolicyRecommendation
PolicySpec
ProblemConstraintSpec
ProblemDomain
ProblemFrame
PropagationMethod
ProxyIdentificationBundle
ProxyMap
QualityTier
QueryType
ReadinessImpact
ReconciliationCertificate
ReconciliationMethod
ReconciliationStatus
RefutationResult
RefutationTestType
RegimeBenchmarkStatus
RegimeCalendar
RegimeForecastCalibrationStatus
RegimeIdentifiabilityStatus
RegimeModelFamily
RegimeShiftForecastBundle
RegimeShiftForecastBundleRef
RegionSectorPanels
RuleType
SchemaChangepoint
SchemaRegimeRegistry
SchemaRegimeSpec
SensitivityAnalysisBundle
SensitivityAnalysisBundleRef
SensitivityAnalysisIndex
ShiftComponent
ShiftDiagnosticReport
ShiftDiagnosticReportRef
ShockCalendar
SourceConfidenceTier
SpaceTimeCausalCertificate
SpaceTimeCausalCertificateRef
SparseDenseBridge
SpatialResult
SpecificationCurveBundle
SpecificationCurveInput
StakeholderSpec
StrategicResponseChannel
StrategicResponseSpecsBundle
StructuralCausalModelSpec
SubgroupEffect
SuccessCriterion
SurveyAssumptionComponent
SurveyAssumptionLayer
SurveyAssumptionStatus
SurveyQualityCertificate
SurveyQualityCertificateRef
SurveyRequestedRegime
SurveyValidatedRegime
SurveyVarianceMode
SurvivalDataBundleManifest
SystematicBias
TargetingRule
TemporalDTRExecutionEntry
TemporalDTRTask
TemporalGraphCausalCertificate
TemporalGraphCausalCertificateRef
TemporalInterventionSequence
TemporalInterventionStep
TransportabilityCheckBundle
TransportabilityResult
TransportabilityResultRef
TrustLevel
UncertaintyEnvelope
UncertaintySource
WelfareBundle
WelfareBundleRef
WelfareIntervalSemantics
WelfareMethod
WelfareSampleBundle
WelfareSampleBundleRef
WelfareStatus
WinnersLosersEntry
WinnersLosersTable
enumerate_ir_exports
get_ir_schema_catalog
get_ir_type
inspect_ir_schema
list_ir_types
load_causal_execution_bundle
load_dependent_sensitivity_result
load_policy
persist_causal_execution_bundle
persist_dependent_sensitivity_result
```

</details>

## `polisyos.fabric`

- Classification: `public_stable`
- Supported entrypoints: `polisyos.fabric`, `polisyos.fabric.api`
- Facade policy: expected `lazy_facade`, observed `lazy_facade`
- Owner: `team-polisyos`
- README: `src/polisyos/fabric/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Connector-backed ingestion, world queries, and catalog surfaces.
- Summary: Stable Fabric facade for connector ingestion, world-query, and catalog APIs.

<details><summary>Supported exports (30)</summary>

```text
AccessRef
AuthoredText
ConnectorRegistryLike
FabricDecisionData
FabricDecisionDataCoverage
FabricDecisionDataResponse
LineageRef
ProcessingGuarantee
ProcessingGuaranteeContract
QualityRef
ReplayRef
SourceContractRef
TemporalRef
TypedGap
UnitRef
WorldQueryError
WorldQueryRequest
batch_processing_contract
execute_world_query
fabric_claim_to_authored_text
fabric_event_to_authored_text
fabric_fact_to_quantity_value
fabric_get_data
query_claims
query_events
query_world_table
resolve_connector_registry
run_connectors_ingestion
stream_processing_contract
world
```

</details>

## `polisyos.foundry`

- Classification: `public_stable`
- Supported entrypoints: `polisyos.foundry`, `polisyos.foundry.api`, `polisyos.foundry.compile`, `polisyos.foundry.execute`
- Facade policy: expected `lazy_facade`, observed `lazy_facade`
- Owner: `team-polisyos`
- README: `src/polisyos/foundry/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Stable compile/execute facade over the compute and method stack. Phase 6 keeps root public exports in polisyos.foundry.api and narrow public subpackages; moved legacy FQN are compatibility shims registered in architecture/shims.toml.
- Summary: Expose the stable Foundry compile/execute entrypoints behind lazy imports.

<details><summary>Supported exports (3)</summary>

```text
compile
compile_program
execute
```

</details>

## `polisyos.scientist`

- Classification: `public_stable`
- Supported entrypoints: `polisyos.scientist`
- Facade policy: expected `lazy_facade`, observed `lazy_facade`
- Owner: `team-polisyos`
- README: `src/polisyos/scientist/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Workflow orchestration facade for experiment execution and shared observability hooks.
- Summary: Stable Scientist package facade for workflow execution and run observability.

<details><summary>Supported exports (7)</summary>

```text
ExperimentState
build_governance_pipeline
discover_scientist_nodes
get_metrics
get_tracer
load_governance_passes
run_experiment
```

</details>

## `polisyos.runtime`

- Classification: `public_stable`
- Supported entrypoints: `polisyos.runtime`
- Facade policy: expected `lazy_facade`, observed `lazy_facade`
- Owner: `team-polisyos`
- README: `src/polisyos/runtime/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Replay and runtime-facing contracts. HTTP subpackages stay internal unless separately documented.
- Summary: Expose replay/runtime contracts without importing heavy implementations eagerly.

<details><summary>Supported exports (10)</summary>

```text
CompletenessLevel
CompletenessReport
ReplayPlan
ReplayStrategy
VerificationConfig
VerificationMode
VerificationResult
build_replay_plan
completeness_check
verify_replay
```

</details>

## `polisyos.lex`

- Classification: `public_stable`
- Supported entrypoints: `polisyos.lex`
- Facade policy: expected `lazy_facade`, observed `lazy_facade`
- Owner: `team-polisyos`
- README: `src/polisyos/lex/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Stable runtime Lex facade for NormPack assembly, legal evaluation, simulator, interventions, and read-only legal knowledge APIs. Offline legal preprocessing is owned by polisyos.data_forge.domains.legal.
- Summary: Stable Lex facade for runtime legal evaluation, NormPack assembly, and interventions.

<details><summary>Supported exports (50)</summary>

```text
ActiveVersionResult
ActiveVersionStrategy
AffectedKPI
ChangeProposalRef
ComplianceDelta
ComplianceTransition
HierarchicalPolicySearchAdapter
HierarchicalPolicySearchPlan
InterventionKnobDictionaryEntry
InterventionKnobSpec
LegalEvaluationRequest
LegalKnowledgeGraph
LegalReportRef
LexError
LexFabricEvidencePath
LexIndexError
LexIngestError
LexInterventionCompiler
LexInterventionMapEntry
LexNotReadyError
LexPolicyBundleInput
LexProvisionDirective
LexProvisionMappingRegistry
LexStructureError
LexValidationError
LexVersioningError
MutationIntent
NormChange
NormChangeType
NormDiff
NormImpactAnalyzer
NormImpactReport
NormPackBudgets
NormPackBuildRequest
NormPackBuildResult
NormPackMutator
ProvisionProgramCrosswalkEntry
StrategicResponseRegistryEntry
StrategicResponseSpecRegistry
TemporalInterventionSequenceCompileResult
TemporalInterventionSequenceCompiler
TemporalInterventionSequencer
TemporalInterventionStepInput
WorldEventRefLike
assemble_norm_pack
diff_norm_packs
evaluate_legality
lex_evidence_from_fabric_decision_data
propose_changes
resolve_active_version
```

</details>

## `polisyos.scholar`

- Classification: `public_experimental`
- Supported entrypoints: `polisyos.scholar`
- Facade policy: expected `lazy_facade`, observed `lazy_facade`
- Owner: `team-polisyos`
- README: `src/polisyos/scholar/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Topic enrichment service facade; API is user-facing but still evolving.
- Summary: Expose Scholar enrichment entrypoints and contracts via lazy imports.

<details><summary>Supported exports (16)</summary>

```text
EnrichResultV1
EnrichmentReportV1
KnowledgeBundlePayloadV1
ScholarAcquireError
ScholarBundleError
ScholarClaimsError
ScholarDiscoverError
ScholarDocsError
ScholarError
ScholarFabricCitation
ScholarPolicy
ScholarReconcileError
ScholarService
ScholarValidationError
enrich_topic
scholar_citation_from_fabric_decision_data
```

</details>

## `polisyos.data_forge`

- Classification: `public_experimental`
- Supported entrypoints: `polisyos.data_forge`, `polisyos.data_forge.read_api`
- Facade policy: expected `lazy_facade`, observed `lazy_facade`
- Owner: `team-data-forge`
- README: `src/polisyos/data_forge/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Experimental asset-centric build-time Data Forge facade. The top-level package lazily exports build-time artifact, asset, schema, snapshot, quality, and migration-test contracts; read_api is the only runtime import surface.
- Summary: Data Forge public facade for build-time artifact contracts and read APIs.

<details><summary>Supported exports (33)</summary>

```text
ArtifactRef
AssetDefinition
AssetGroup
AssetKey
AssetSpec
CompatibilityMode
DataForgeError
DataForgeValidationError
DifferentialComparison
GoldenArtifact
GoldenCase
MaterializationContext
PIILevel
ProducerVersion
QCCheck
QCReport
RetentionClass
SchemaCompatibilityError
SchemaRegistry
SchemaVersion
SnapshotCommitError
SnapshotTransaction
SnapshotTransactionStatus
__version__
asset
capture_golden_file
compare_file_sha256
compare_json_files
evaluate_fail_fast
merkle_root
plan_asset_specs
read_api
verify_golden_file
```

</details>

## `polisyos.berl`

- Classification: `public_experimental`
- Supported entrypoints: `polisyos.berl`
- Facade policy: expected `eager_exports`, observed `eager_exports`
- Owner: `team-scientist`
- README: `src/polisyos/berl/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Active Bounded Explanation Reliability Layer facade for Scientist validation and explanation reliability evidence. API is experimental.
- Summary: Bounded Explanation Reliability Layer public API.

<details><summary>Supported exports (11)</summary>

```text
EmpiricalBoundResult
ExplanationBundle
ExplanationOrchestrator
ExplanationRequest
ExplanationValidationResult
ValidationThresholds
empirical_bernstein_upper_bound
estimate_local_infidelity
hoeffding_upper_bound
summarize_explanation_response
validate_explanation_bundle
```

</details>

## `polisyos.calibration`

- Classification: `public_experimental`
- Supported entrypoints: `polisyos.calibration`
- Facade policy: expected `eager_exports`, observed `eager_exports`
- Owner: `team-scientist`
- README: `src/polisyos/calibration/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Canonical shared calibration diagnostics, recalibration, and validation-report API. Foundry and DDM calibration contexts remain package-specific.
- Summary: Calibration diagnostics public entrypoints.

<details><summary>Supported exports (10)</summary>

```text
CalibrationPoint
CalibrationResult
apply_calibrator
compare_calibrators
compute_calibration_curve
evaluate_binary
evaluate_continuous
evaluate_multiclass
fit_calibrator
to_validation_report
```

</details>

## `polisyos.ddm`

- Classification: `internal`
- Supported entrypoints: `polisyos.ddm`
- Facade policy: expected `eager_exports`, observed `eager_exports`
- Owner: `team-scientist`
- README: `src/polisyos/ddm/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Canonical unversioned drift/degradation monitor surface. It is registered to prevent accidental deep-import promotion, not as a stable public API.
- Summary: Drift-and-Degradation Monitor for Phase 5 Problem 15.7.

<details><summary>Supported exports (17)</summary>

```text
AffectedFeature
AffectedSlice
CalibrationAudit
DDMWindowResult
DataQualitySignal
DriftAndDegradationMonitor
IncidentPayload
MetricDirection
ModelRegistryReadinessRecord
MonitoringWindow
PerformanceDegradationEvent
ReadinessState
ReadinessStateEvent
RegistryGateDecision
RootCauseBundle
ShiftDetectedEvent
ShiftRiskEvent
```

</details>

## `polisyos.ddm_15_7`

- Classification: `compatibility`
- Supported entrypoints: `polisyos.ddm_15_7`
- Facade policy: expected `eager_exports`, observed `eager_exports`
- Owner: `team-architecture`
- README: `src/polisyos/ddm_15_7/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Wrapper-only compatibility facade for polisyos.ddm until 2026-10-01; tracked by ddm-15-7-rename and ADR-RSR-0135, with facade smoke coverage only.
- Summary: Compatibility facade for :mod:`polisyos.ddm`.

<details><summary>Supported exports (17)</summary>

```text
AffectedFeature
AffectedSlice
CalibrationAudit
DDMWindowResult
DataQualitySignal
DriftAndDegradationMonitor
IncidentPayload
MetricDirection
ModelRegistryReadinessRecord
MonitoringWindow
PerformanceDegradationEvent
ReadinessState
ReadinessStateEvent
RegistryGateDecision
RootCauseBundle
ShiftDetectedEvent
ShiftRiskEvent
```

</details>

## `polisyos.foundry.agent_sim.world`

- Classification: `public_experimental`
- Supported entrypoints: `polisyos.foundry.agent_sim.world`
- Facade policy: expected `eager_exports`, observed `eager_exports`
- Owner: `team-foundry`
- README: `src/polisyos/foundry/agent_sim/world/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Truth-centric synthetic world generation and evaluation surface under the Foundry agent simulation owner.
- Summary: Synthetic-world family with truth-centric generation and evaluation.

<details><summary>Supported exports (23)</summary>

```text
BenchmarkSuiteBinding
EvaluationRun
EvaluationSpec
InterventionSpec
InterventionStyle
MeasurementErrorKind
MeasurementErrorSpec
MissingnessMechanism
MissingnessSpec
SamplingDesignKind
SamplingDesignSpec
SyntheticWorld
SyntheticWorldDGP
SyntheticWorldSample
TruthComputationMode
TruthManifest
TruthQuery
TruthSpec
WorldArtifact
WorldFamily
WorldSpec
phase0_seed_benchmark_binding
phase0_seed_world_specs
```

</details>

## `polisyos.synthetic_world`

- Classification: `compatibility`
- Supported entrypoints: `polisyos.synthetic_world`
- Facade policy: expected `eager_exports`, observed `eager_exports`
- Owner: `team-foundry`
- README: `src/polisyos/synthetic_world/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Wrapper-only compatibility facade for polisyos.foundry.agent_sim.world until 2026-10-01.
- Summary: Compatibility facade for :mod:`polisyos.foundry.agent_sim.world`.

<details><summary>Supported exports (23)</summary>

```text
BenchmarkSuiteBinding
EvaluationRun
EvaluationSpec
InterventionSpec
InterventionStyle
MeasurementErrorKind
MeasurementErrorSpec
MissingnessMechanism
MissingnessSpec
SamplingDesignKind
SamplingDesignSpec
SyntheticWorld
SyntheticWorldDGP
SyntheticWorldSample
TruthComputationMode
TruthManifest
TruthQuery
TruthSpec
WorldArtifact
WorldFamily
WorldSpec
phase0_seed_benchmark_binding
phase0_seed_world_specs
```

</details>
