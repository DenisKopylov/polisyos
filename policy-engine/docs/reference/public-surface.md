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

| Package                   | Classification        | Facade            | Exports | Owner             | README                                  |
| ------------------------- | --------------------- | ----------------- | ------: | ----------------- | --------------------------------------- |
| `polisyos.common`         | `public_stable`       | `lazy_facade`     | 7       | `team-polisyos`   | `src/polisyos/common/README.md`         |
| `polisyos.core`           | `public_stable`       | `lazy_facade`     | 15      | `team-polisyos`   | `src/polisyos/core/README.md`           |
| `polisyos.ir`             | `public_stable`       | `lazy_facade`     | 228     | `team-polisyos`   | `src/polisyos/ir/README.md`             |
| `polisyos.fabric`         | `public_stable`       | `lazy_facade`     | 9       | `team-polisyos`   | `src/polisyos/fabric/README.md`         |
| `polisyos.foundry`        | `public_stable`       | `lazy_facade`     | 3       | `team-polisyos`   | `src/polisyos/foundry/README.md`        |
| `polisyos.scientist`      | `public_stable`       | `lazy_facade`     | 4       | `team-polisyos`   | `src/polisyos/scientist/README.md`      |
| `polisyos.runtime`        | `public_stable`       | `lazy_facade`     | 10      | `team-polisyos`   | `src/polisyos/runtime/README.md`        |
| `polisyos.lex`            | `public_stable`       | `lazy_facade`     | 58      | `team-polisyos`   | `src/polisyos/lex/README.md`            |
| `polisyos.scholar`        | `public_experimental` | `lazy_facade`     | 14      | `team-polisyos`   | `src/polisyos/scholar/README.md`        |
| `polisyos.data_forge`     | `public_experimental` | `eager_exports`   | 1       | `team-data-forge` | `src/polisyos/data_forge/README.md`     |
| `polisyos.academic`       | `public_experimental` | `module_doc_only` | 0       | `team-polisyos`   | `src/polisyos/academic/README.md`       |
| `polisyos.datasets`       | `public_experimental` | `module_doc_only` | 0       | `team-polisyos`   | `src/polisyos/datasets/README.md`       |
| `polisyos.batch_common`   | `public_experimental` | `eager_exports`   | 17      | `team-polisyos`   | `src/polisyos/batch_common/README.md`   |
| `polisyos.batch_snapshot` | `public_experimental` | `module_doc_only` | 0       | `team-polisyos`   | `src/polisyos/batch_snapshot/README.md` |

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
evaluation
errors
llm
observability
pipeline
resilience
registry
run
```

</details>

## `polisyos.ir`

- Classification: `public_stable`
- Supported entrypoints: `polisyos.ir`
- Facade policy: expected `lazy_facade`, observed `lazy_facade`
- Owner: `team-polisyos`
- README: `src/polisyos/ir/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Primary compatibility boundary for policy, governance, analytics, and observation contracts.
- Summary: Expose the stable IR contract surface through a lazy package facade.

<details><summary>Supported exports (228)</summary>

```text
AccessTier
ConnectorCapability
ConnectorMetadataSpec
DataFilter
DataViewRequest
DataViewType
QualityTier
TrustLevel
NormPack
NormRule
NormRef
RuleType
load_policy
IRExportInfo
IRFieldInfo
IRPublicStatus
IRSchemaCatalog
IRTypeInfo
IRTypeKind
enumerate_ir_exports
get_ir_schema_catalog
get_ir_type
inspect_ir_schema
list_ir_types
CalibrationConfig
CalibrationTarget
ProblemFrame
ProblemDomain
KPISpec
SuccessCriterion
ProblemConstraintSpec
ConstraintType
StakeholderSpec
PolicySpec
PolicyInterventionSpec
MechanismBinding
ParameterSpec
PolicyPortfolio
PolicyInteraction
InteractionMatrix
InteractionType
ModelSpec
FidelityLevel
GovernancePassAlias
GovernancePassAliasRegistry
GovernancePassAliasStatus
GovernancePassMappingRegistry
GovernancePassMappingBundle
AssumptionSpec
AssumptionType
AgentConfig
AgentTypeConfig
EnvironmentConfig
EnvironmentParam
GateContext
GateDecision
GateEvent
GateEventType
GatePriority
GateRequest
GateVerdict
DistributionFamily
ForecastCalibrationMethod
ForecastCoverageDiagnostic
ForecastIntervalSemantics
ForecastingUncertaintyBundle
ForecastingUncertaintyBundleRef
GEUncertaintyBundle
GEUncertaintyBundleRef
GEUncertaintyRepresentation
FanChartSpec
HorizonInterval
HorizonPolicySpec
IntervalSemantics
PropagationMethod
UncertaintyEnvelope
UncertaintySource
WelfareBundle
WelfareBundleRef
WelfareIntervalSemantics
WelfareMethod
WelfareSampleBundle
WelfareSampleBundleRef
WelfareStatus
CausalMethod
EstimationStatus
RefutationTestType
RefutationResult
CausalEffectReport
QueryType
InterventionType
InterventionSpec
CausalInterventionSpec
CausalQuery
CausalQueryResult
CausalQueryResultRef
CausalExecutionBundleRef
BlockSupportReport
CausalBlockBridge
CausalBlockBridgeRef
ExposureMappingType
InteractionComplex
InteractionComplexRef
InterferenceCertificate
InterferenceCertificateRef
InterferenceEffectDecomposition
InterferenceMethod
MAUPInvarianceCertificate
MAUPInvarianceCertificateRef
MAUPPartitionCheck
NetworkInterferenceReport
SpatialResult
EnsembleMember
CausalModelEnsemble
CausalModelEnsembleRef
TransportabilityResult
TransportabilityResultRef
CausalDiscoveryReport
DiagnosticTest
MechanismFamily
MechanismSource
NodeMechanism
StructuralCausalModelSpec
PlaceboResult
CohortDimension
ImpactDirection
MetricUnit
CohortImpact
DimensionBreakdown
WinnersLosersEntry
WinnersLosersTable
DistributionalReport
SubgroupEffect
FeatureImportance
HTEResult
TargetingRule
PolicyRecommendation
BiasDirection
OutcomeComparison
SystematicBias
BacktestScenario
BacktestReport
AdministrativeMissingnessClass
AdministrativeMissingnessDirection
AdministrativeMissingnessMetadata
AdministrativeMissingnessScenarioFamily
AdministrativeMissingnessUnitScope
MissingnessAssessmentProvenance
MissingnessAssessmentReport
MissingnessAssessmentStatus
MissingnessEstimandRisk
MissingnessEvidenceItem
SurveyAssumptionComponent
SurveyAssumptionLayer
SurveyAssumptionStatus
SurveyRequestedRegime
SurveyValidatedRegime
SurveyVarianceMode
SurveyQualityCertificate
SurveyQualityCertificateRef
MicrosimCalibrationReport
MicrosimCalibrationReportRef
DependenceStructure
DependenceStructureRef
MobilityReport
MobilityReportRef
BacktestPlanBundle
BoundsEstimationBundle
CalibrationTargetBundleManifest
CalibrationSplitLabel
CalibrationSplitPlan
CalibrationSplitWindow
CausalPanelBundleManifest
DTRTreatmentSequenceBundleManifest
EntityScope
IdentificationMode
LessonRegistrySeedBundle
LeontiefIOBundle
MicrosimSurveyContractBundle
MultiplexGraphLayerId
NetworkCausalContractBundle
NetworkContractBundle
ObservationFamily
ObservationFamilyPolicy
ObservationFamilyPolicyRegistry
IdentificationModeRouter
IdentificationRoute
MeasurementRegistry
MeasurementTrustTier
NegativeControlSpec
ObservationPanel
ObservationRecord
ObservationToContractManifest
BoundsEstimationInput
FirmEvents
FirmPanels
GraphArtifacts
LeontiefIOInput
ObservationContractCompilerSuite
PanelEconometricBundleManifest
ProxyMap
ProxyIdentificationBundle
TransportabilityCheckBundle
CounterfactualCheckBundle
InterferenceLossSpecBundle
CausalReadinessBundle
BoundsEstimationTask
BoundsEstimationEntry
TemporalDTRTask
TemporalDTRExecutionEntry
CausalExecutionBundle
load_causal_execution_bundle
persist_causal_execution_bundle
RegionSectorPanels
SourceConfidenceTier
SpecificationCurveInput
SparseDenseBridge
SpecificationCurveBundle
StrategicResponseChannel
StrategicResponseSpecsBundle
SurvivalDataBundleManifest
RegimeCalendar
SchemaChangepoint
SchemaRegimeRegistry
SchemaRegimeSpec
ShockCalendar
TemporalInterventionSequence
TemporalInterventionStep
```

</details>

## `polisyos.fabric`

- Classification: `public_stable`
- Supported entrypoints: `polisyos.fabric`
- Facade policy: expected `lazy_facade`, observed `lazy_facade`
- Owner: `team-polisyos`
- README: `src/polisyos/fabric/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Connector-backed ingestion, world queries, and catalog surfaces.
- Summary: Stable Fabric facade for connector ingestion, world-query, and catalog APIs.

<details><summary>Supported exports (9)</summary>

```text
fabric_get_data
execute_world_query
query_claims
query_events
query_world_table
run_connectors_ingestion
WorldQueryError
WorldQueryRequest
world
```

</details>

## `polisyos.foundry`

- Classification: `public_stable`
- Supported entrypoints: `polisyos.foundry`
- Facade policy: expected `lazy_facade`, observed `lazy_facade`
- Owner: `team-polisyos`
- README: `src/polisyos/foundry/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Stable compile/execute facade over the compute and method stack.
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

<details><summary>Supported exports (4)</summary>

```text
ExperimentState
get_metrics
get_tracer
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
ReplayStrategy
ReplayPlan
CompletenessLevel
CompletenessReport
VerificationMode
VerificationConfig
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
- Notes: Stable legal-ingestion, normpack, and intervention facade.
- Summary: Stable Lex facade for legal corpus ingestion, NormPack assembly, and intervention APIs.

<details><summary>Supported exports (58)</summary>

```text
ActiveVersionResult
ActiveVersionStrategy
ChangeProposalRef
LegalDocSource
LegalEvaluationRequest
LegalReportRef
LexError
LexIndexError
LexIngestError
LexIngestOptions
LexIngestResult
LexNotReadyError
LexStructureError
LexStructureOptions
LexStructureResult
LexValidationError
LexVersionIndexOptions
LexVersionIndexResult
LexVersioningError
LexInterventionCompiler
LexProvisionDirective
NormPackBuildRequest
NormPackBuildResult
NormPackBudgets
MutationIntent
NormPackMutator
NormChangeType
NormChange
NormDiff
NormImpactAnalyzer
NormImpactReport
ComplianceTransition
ComplianceDelta
AffectedKPI
diff_norm_packs
LegalKnowledgeGraph
InterventionKnobDictionaryEntry
HierarchicalPolicySearchAdapter
HierarchicalPolicySearchPlan
InterventionKnobSpec
LexInterventionMapEntry
StrategicResponseRegistryEntry
StrategicResponseSpecRegistry
LexPolicyBundleInput
TemporalInterventionSequenceCompiler
TemporalInterventionSequenceCompileResult
TemporalInterventionSequencer
TemporalInterventionStepInput
LexProvisionMappingRegistry
ProvisionProgramCrosswalkEntry
WorldEventRefLike
assemble_norm_pack
build_legal_structure
build_version_index
evaluate_legality
ingest_legal_doc_bytes
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

<details><summary>Supported exports (14)</summary>

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
ScholarPolicy
ScholarReconcileError
ScholarService
ScholarValidationError
enrich_topic
```

</details>

## `polisyos.data_forge`

- Classification: `public_experimental`
- Supported entrypoints: `polisyos.data_forge`, `polisyos.data_forge.read_api`
- Facade policy: expected `eager_exports`, observed `eager_exports`
- Owner: `team-data-forge`
- README: `src/polisyos/data_forge/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Experimental asset-centric build-time data forge facade. The top-level package currently re-exports read_api eagerly; kernel/domains remain internal and read_api is the only runtime import surface.
- Summary: Minimal Data Forge public surface for runtime-safe read APIs.

<details><summary>Supported exports (1)</summary>

```text
read_api
```

</details>

## `polisyos.academic`

- Classification: `public_experimental`
- Supported entrypoints: `polisyos.academic`
- Facade policy: expected `module_doc_only`, observed `module_doc_only`
- Owner: `team-polisyos`
- README: `src/polisyos/academic/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Academic ingestion and SKG utilities remain available but are not release-stable library surface.
- Summary: Academic literature ingestion and SKG search package.

This package does not expose a package-level `__all__` facade. Treat the module root itself as the only documented entrypoint.

## `polisyos.datasets`

- Classification: `public_experimental`
- Supported entrypoints: `polisyos.datasets`
- Facade policy: expected `module_doc_only`, observed `module_doc_only`
- Owner: `team-polisyos`
- README: `src/polisyos/datasets/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Dataset discovery and ETL helpers are available to engineers but evolve with pipeline phases.
- Summary: Dataset catalog and batch ETL package for external statistical source discovery.

This package does not expose a package-level `__all__` facade. Treat the module root itself as the only documented entrypoint.

## `polisyos.batch_common`

- Classification: `public_experimental`
- Supported entrypoints: `polisyos.batch_common`
- Facade policy: expected `eager_exports`, observed `eager_exports`
- Owner: `team-polisyos`
- README: `src/polisyos/batch_common/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Shared offline-pipeline helpers used by Lex, Scholar, and dataset batches.
- Summary: Expose stable batch-pipeline helpers for manifests, QC, and thermal pacing.

<details><summary>Supported exports (17)</summary>

```text
QCCheck
QCReport
Phase0QualityCheck
Phase0QualityReport
Phase0QualityThresholds
ThermalProfile
cooldown
evaluate_phase0_quality
evaluate_fail_fast
pause_between_batches
sha256_file
sha256_jsonl
snapshot_component_dir
write_publish_manifest
write_qc_report
write_raw_manifest
write_stage_manifest
```

</details>

## `polisyos.batch_snapshot`

- Classification: `public_experimental`
- Supported entrypoints: `polisyos.batch_snapshot`
- Facade policy: expected `module_doc_only`, observed `module_doc_only`
- Owner: `team-polisyos`
- README: `src/polisyos/batch_snapshot/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Snapshot finalization helpers for offline pipeline publishing.
- Summary: Finalize unified snapshot manifests.

This package does not expose a package-level `__all__` facade. Treat the module root itself as the only documented entrypoint.
