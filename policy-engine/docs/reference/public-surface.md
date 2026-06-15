# Public Surface

> Generated from `architecture/public_surface/contract.toml` and package facades under `src/polisyos/**/__init__.py`.

Canonical regeneration command:

```bash
uv run python tools/devx/architecture/guardrails.py sync --skip-deep-import-baseline
```

Supported entrypoints are intentionally explicit. Any `polisyos.*` path not listed on this page is **internal** and may change without compatibility guarantees.

Classification policy:

- `public_stable`: supported entrypoint with normal compatibility, release-note, and migration expectations.
- `public_experimental`: documented entrypoint that should stay visible in docs and release notes when touched, but it does not promise long-term compatibility.
- `internal`: any `polisyos.*` path not listed here; keep it out of public docs and release notes unless operators must care.

## Policy Design Case Generated Audit Surfaces

`layer3_g4_shadow_to_governed_promotion_surface` is a generated
PUBLIC/REVIEWER/EXPERT/MACHINE Policy Design Case audit surface documented in
`docs/reference/policy-design-case-layer3-promotion-gate.md`. It is
projection-only for public export: `layer3_g4_public_export_projection_refs.json`
records `out_of_scope_reference_only` rather than a runtime public-export route.

`layer3_g5_first_proving_ground_conversion_surface` is a generated
PUBLIC/REVIEWER/EXPERT/MACHINE Policy Design Case audit surface documented in
`docs/reference/policy-design-case-layer3-proving-ground-conversion.md`. It
publishes conversion-record refs, blocker/limitation refs, and projection-only
public refs; `layer3_g5_public_export_projection_refs.json` records
`out_of_scope_reference_only` and does not register a public-export bundle route.

`layer3_g6_bounded_agent_surface` is a generated PUBLIC/REVIEWER/EXPERT/MACHINE
Policy Design Case audit surface documented in
`docs/reference/policy-design-case-layer3-bounded-agent.md`. It publishes
agent-run refs, policy-grammar projection refs, G5 invocation refs,
search-ledger refs, replay-manifest refs, orchestration-continuity refs,
candidate DesignRecord handoff refs, orchestration-choice audit refs, and
projection-only public refs;
`layer3_g6_public_export_projection_refs.json` records
`out_of_scope_reference_only` and does not register a public-export bundle route.

`layer3_g7_region_widening_surface` is a generated
PUBLIC/REVIEWER/EXPERT/MACHINE Policy Design Case audit surface documented here
until the region-widening reference page graduates. It publishes region
scorecard refs, conversion status matrix refs, S12/S13/S14 projection status,
replay-manifest refs, orchestration-continuity refs, route registry refs, and
projection-only public refs; `layer3_g7_public_export_projection_refs.json`
records `out_of_scope_reference_only`, does not register a public-export bundle
route, and does not publish universal authority.

`layer3_g8_health_metric_governance_surface` is a generated EXPERT/MACHINE
Policy Design Case audit surface documented here until the health-metric
governance reference page graduates. It publishes metric registry refs,
normalized metric signal refs, cross-metric diagnosis refs, D4.4 re-basing
receipt refs, replay-manifest refs, route registry refs, blocker-specific
search-health classifications for seed corpus, pinned request, current blocker,
and production readiness, and
`layer3_g8_closeout_signal_consumer_gate.json` refs. PUBLIC/REVIEWER access is
projection-only through `layer3_g8_public_export_projection_refs.json`, which
records `out_of_scope_reference_only` and does not register a public-export
bundle route.

`layer3_gx_universal_free_growth_hardening_surface` is a generated
EXPERT/MACHINE Policy Design Case hardening audit surface documented here
until the GX reference page graduates. It publishes data-home refs, runtime
literal lint refs, reducer/provenance refs, measurement replay refs, vertical
pinned-route refs, provisional and final Task 12 outcome/audit refs, data
mutation free-growth refs, and expected-red refs. PUBLIC/REVIEWER access is
out of scope until a dedicated GX public-export projection is produced; the
surface does not register a public-export bundle route and does not publish
production, closeout, domain-ceiling, recommendation, or useful-design
authority.

| Package | Classification | Facade | Exports | Owner | README |
| --- | --- | --- | ---: | --- | --- |
| `polisyos.common` | `public_stable` | `lazy_facade` | 7 | `team-polisyos` | `src/polisyos/common/README.md` |
| `polisyos.core` | `public_stable` | `lazy_facade` | 15 | `team-polisyos` | `src/polisyos/core/README.md` |
| `polisyos.ir` | `public_stable` | `lazy_facade` | 273 | `team-polisyos` | `src/polisyos/ir/README.md` |
| `polisyos.obligation_rules` | `internal` | `eager_exports` | 22 | `team-policyos-runtime` | `src/polisyos/obligation_rules/README.md` |
| `polisyos.obligation_graph` | `internal` | `eager_exports` | 20 | `team-policyos-runtime` | `src/polisyos/obligation_graph/README.md` |
| `polisyos.method_requirement` | `internal` | `eager_exports` | 14 | `team-policyos-runtime` | `src/polisyos/method_requirement/README.md` |
| `polisyos.participation_requirement` | `internal` | `eager_exports` | 23 | `team-policyos-runtime` | `src/polisyos/participation_requirement/README.md` |
| `polisyos.fabric` | `public_stable` | `lazy_facade` | 36 | `team-polisyos` | `src/polisyos/fabric/README.md` |
| `polisyos.foundry` | `public_stable` | `lazy_facade` | 4 | `team-polisyos` | `src/polisyos/foundry/README.md` |
| `polisyos.scientist` | `public_stable` | `lazy_facade` | 15 | `team-polisyos` | `src/polisyos/scientist/README.md` |
| `polisyos.evidence` | `internal` | `eager_exports` | 19 | `team-policyos-runtime` | `src/polisyos/evidence/README.md` |
| `polisyos.runtime` | `public_stable` | `lazy_facade` | 10 | `team-polisyos` | `src/polisyos/runtime/README.md` |
| `polisyos.lex` | `public_stable` | `lazy_facade` | 53 | `team-polisyos` | `src/polisyos/lex/README.md` |
| `polisyos.scholar` | `public_experimental` | `lazy_facade` | 25 | `team-polisyos` | `src/polisyos/scholar/README.md` |
| `polisyos.data_forge` | `public_experimental` | `lazy_facade` | 49 | `team-data-forge` | `src/polisyos/data_forge/README.md` |
| `polisyos.berl` | `public_experimental` | `eager_exports` | 11 | `team-scientist` | `src/polisyos/berl/README.md` |
| `polisyos.calibration` | `public_experimental` | `eager_exports` | 10 | `team-scientist` | `src/polisyos/calibration/README.md` |
| `polisyos.ddm` | `internal` | `eager_exports` | 17 | `team-scientist` | `src/polisyos/ddm/README.md` |
| `polisyos.foundry.agent_sim.world` | `public_experimental` | `eager_exports` | 23 | `team-foundry` | `src/polisyos/foundry/agent_sim/world/README.md` |

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

## `polisyos.obligation_rules`

- Classification: `internal`
- Supported entrypoints: `polisyos.obligation_rules`
- Facade policy: expected `eager_exports`, observed `eager_exports`
- Owner: `team-policyos-runtime`
- README: `src/polisyos/obligation_rules/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Wave 6 governed obligation rule catalog for universal Policy Design Case compilation; internal until W6-W8 external surfaces graduate.
- Summary: Governed obligation rule catalog public module.

<details><summary>Supported exports (22)</summary>

```text
OBLIGATION_RULE_CATALOG_CONTRACT_ID
OBLIGATION_RULE_CATALOG_KIND
OBLIGATION_RULE_CATALOG_SCHEMA
OBLIGATION_RULE_CATALOG_SCHEMA_VERSION
ObligationRule
ObligationRuleCandidate
ObligationRuleCatalog
ObligationRuleCatalogSummary
ObligationRuleFamily
ObligationRuleGovernanceError
ObligationRuleScope
ObligationRuleSourceClass
ObligationRuleStatus
PublicRevalidationEffect
RuleDeprecationPolicy
RuleGovernanceDecision
build_rule_evolution_registry_for_catalog
build_seed_obligation_rule_catalog
govern_rule_candidate
governed_rule_catalog_public_surface
persist_obligation_rule_catalog
select_governed_rules
```

</details>

## `polisyos.obligation_graph`

- Classification: `internal`
- Supported entrypoints: `polisyos.obligation_graph`
- Facade policy: expected `eager_exports`, observed `eager_exports`
- Owner: `team-policyos-runtime`
- README: `src/polisyos/obligation_graph/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Wave 6.C obligation graph compiler and ledger contracts; internal until graph audit and runtime projection surfaces graduate.
- Summary: W6.C obligation graph compiler and ledger contracts.

<details><summary>Supported exports (20)</summary>

```text
OBLIGATION_GRAPH_CONTRACT_ID
OBLIGATION_GRAPH_SCHEMA_VERSION
BundleKey
CandidateLedgerEntry
ComplexityBudget
DeadlineBinding
DeferredObligationRecord
DeferredState
FacetSnapshot
FrontierItem
GovernedObligationRule
ObligationBundle
ObligationCandidateInput
ObligationGraph
ObligationGraphCompileError
PriorityClass
SourceClass
compile_obligation_graph
obligation_graph_audit_surface
write_obligation_graph_artifact
```

</details>

## `polisyos.method_requirement`

- Classification: `internal`
- Supported entrypoints: `polisyos.method_requirement`
- Facade policy: expected `eager_exports`, observed `eager_exports`
- Owner: `team-policyos-runtime`
- README: `src/polisyos/method_requirement/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Wave 7.C method validity requirement compiler consumed by Foundry selection and IR analytics bridges; internal until W7-W8 external surfaces graduate.
- Summary: Method validity requirement compiler for universal Policy Design Cases.

<details><summary>Supported exports (14)</summary>

```text
AssumptionValidationNeed
FairnessDecompositionNeed
MethodIdentificationClass
MethodTransportabilityRequirement
MethodUncertaintyClass
MethodValidityRequirementArtifact
MethodValidityRequirementCompiler
MethodValidityRequirementSpec
SimulationDGPRequirement
StrategicResponseSensitivity
compile_method_validity_requirements
method_validity_requirement_audit_surface
normalize_method_requirements
write_method_validity_requirement_artifact
```

</details>

## `polisyos.participation_requirement`

- Classification: `internal`
- Supported entrypoints: `polisyos.participation_requirement`
- Facade policy: expected `eager_exports`, observed `eager_exports`
- Owner: `team-policyos-runtime`
- README: `src/polisyos/participation_requirement/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Wave 7.E participation provenance requirement compiler and claim-use ceiling evaluator; internal until W7-W8 external surfaces graduate.
- Summary: Participation provenance requirement compiler and consumer enforcement.

<details><summary>Supported exports (23)</summary>

```text
PARTICIPATION_EVALUATION_SCHEMA_VERSION
PARTICIPATION_REQUIREMENT_BUNDLE_SCHEMA_VERSION
PARTICIPATION_REQUIREMENT_SPEC_SCHEMA_VERSION
ParticipationAuthorityBoundary
ParticipationAuthorityLevel
ParticipationClaimPurpose
ParticipationClaimUse
ParticipationDeficitRecord
ParticipationPopulationScope
ParticipationProvenanceClass
ParticipationProvenanceCompiler
ParticipationProvenanceRecord
ParticipationProvenanceRequirementSpec
ParticipationPublicProjectionRow
ParticipationRepresentativenessClass
ParticipationRepresentativenessConfig
ParticipationRequirementBundle
ParticipationRequirementEvaluation
ParticipationSourceKind
compile_participation_requirements
evaluate_participation_requirement
participation_requirement_bundle_audit_surface
write_participation_requirement_bundle
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

<details><summary>Supported exports (36)</summary>

```text
AccessRef
AuthoredText
ConnectorRegistryLike
ConnectorSchemaContract
DataSchema
FabricDecisionData
FabricDecisionDataCoverage
FabricDecisionDataResponse
FieldSpec
LineageRef
ProcessingGuarantee
ProcessingGuaranteeContract
QualityRef
ReplayRef
SchemaType
SourceContract
SourceContractRef
TemporalRef
TypedGap
UnitRef
WorldQueryError
WorldQueryRequest
batch_processing_contract
build_source_contract_requirement_bindings
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

<details><summary>Supported exports (4)</summary>

```text
compile
compile_program
execute
select_method_candidates_for_requirements
```

</details>

## `polisyos.scientist`

- Classification: `public_stable`
- Supported entrypoints: `polisyos.scientist`, `polisyos.scientist.methods.research_dag`
- Facade policy: expected `lazy_facade`, observed `lazy_facade`
- Owner: `team-polisyos`
- README: `src/polisyos/scientist/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Workflow orchestration facade for experiment execution and shared observability hooks.
- Summary: Stable Scientist package facade for workflow execution and run observability.

<details><summary>Supported exports (15)</summary>

```text
ExperimentState
ToolContractSummary
ToolDefinition
ToolLoopResult
ToolRegistry
build_governance_pipeline
create_traced_gateway_client
discover_scientist_nodes
get_metrics
get_tracer
load_governance_passes
run_experiment
run_tool_loop
summarize_tool_contracts
tool_contract_default_blockers
```

</details>

## `polisyos.evidence`

- Classification: `internal`
- Supported entrypoints: `polisyos.evidence`
- Facade policy: expected `eager_exports`, observed `eager_exports`
- Owner: `team-policyos-runtime`
- README: `src/polisyos/evidence/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Wave 8 internal portfolio evidence records for Policy Design Case graph compilation; not a stable public API.
- Summary: Cross-producer evidence graph artifacts for PolicyOS.

<details><summary>Supported exports (19)</summary>

```text
CONFLICT_PORTFOLIO_INDEX_SCHEMA_VERSION
CONFLICT_RECORD_SCHEMA_VERSION
EFFECTIVE_INDEPENDENCE_GRAPH_CONTRACT_ID
EFFECTIVE_INDEPENDENCE_GRAPH_SCHEMA_VERSION
PAIRWISE_MODEL_FORMULA
ConflictRecordError
ConflictResolutionRoute
EffectiveIndependenceGraphError
PortfolioConflictType
annotate_pdc_graph_with_effective_independence
apply_runtime_claim_registry_to_claim
build_conflict_portfolio_index
build_conflict_record
build_effective_independence_graph
claim_registry_rows_by_id
conflict_refs_by_claim
normalize_runtime_claim_registry
validate_conflict_record
validate_effective_independence_graph_record
```

</details>

## `polisyos.runtime`

- Classification: `public_stable`
- Supported entrypoints: `polisyos.runtime`, `polisyos.runtime.quality`
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

<details><summary>Supported exports (53)</summary>

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
build_legal_authority_report
build_legal_authority_requirement_artifact
build_normative_applicability_report
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

<details><summary>Supported exports (25)</summary>

```text
SCHOLAR_ACADEMIC_EVIDENCE_FILENAME
SCHOLAR_ACADEMIC_EVIDENCE_REF_KEY
SCHOLAR_ACADEMIC_EVIDENCE_SCHEMA_VERSION
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
build_scholar_academic_evidence_report
build_scholar_academic_evidence_report_from_web_bundle
build_scholar_spine_evidence_binding
enrich_topic
normalize_scholar_academic_evidence_report
sanitize_untrusted_text
scholar_academic_evidence_required
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
- Notes: Experimental asset-centric build-time Data Forge facade. The top-level package lazily exports build-time artifact, asset, schema, snapshot, provenance, quality, and migration-test contracts; read_api is the only runtime import surface.
- Summary: Data Forge public facade for build-time artifact contracts and read APIs.

<details><summary>Supported exports (49)</summary>

```text
ArtifactRef
AssetDefinition
AssetGroup
AssetKey
AssetSpec
COMPLIANCE_OVERRIDE_REQUIRED_FIELDS
CompatibilityMode
DATA_FORGE_PROVENANCE_MANIFEST_FILE
DATA_FORGE_PROVENANCE_MANIFEST_SCHEMA_VERSION
DataForgeError
DataForgeValidationError
DifferentialComparison
GoldenArtifact
GoldenCase
MaterializationContext
OfficialSnapshotAnswer
PIILevel
PRIVACY_COMPLIANCE_REPORT_SCHEMA_VERSION
ProducerVersion
QCCheck
QCReport
RetentionClass
SchemaCompatibilityError
SchemaRegistry
SchemaVersion
SnapshotClaimRequirementBinding
SnapshotCommitError
SnapshotProvenanceLedgerEntry
SnapshotProvenanceManifest
SnapshotQualityGate
SnapshotTransaction
SnapshotTransactionStatus
TransformLineageStep
__version__
asset
build_privacy_compliance_report
build_snapshot_provenance_manifest
capture_golden_file
compare_file_sha256
compare_json_files
evaluate_fail_fast
load_snapshot_provenance_manifest
merkle_root
normalize_privacy_compliance_report
official_snapshot_answer_from_binding
plan_asset_specs
read_api
verify_golden_file
write_snapshot_provenance_manifest
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
