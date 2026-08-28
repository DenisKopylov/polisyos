# Public Surface

> Generated from `architecture/public_surface/contract.toml` and module/package facades under `src/polisyos/**/*.py`.

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
`authority_preserving_public_export`, registers a redacted public-export bundle
route, and emits only the owner-recomputed safe summary or governed refusal.

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

`layer3_gy_generated_artifact_lifecycle_surface` is a generated
MACHINE/EXPERT Policy Design Case lifecycle audit surface documented in
`architecture/policy_design_case/layer3_gy_task0_audit/` and
`docs/reference/generated-artifacts.md`. It publishes the GY-M1 class
invariant for generated-artifact family registration: every committed GY
artifact must resolve to exactly one registered family output, and missing
or duplicate family claims fail closed. PUBLIC/REVIEWER access is audit-only;
the surface does not register a public-export bundle route and does not
publish recommendation, rollout, closeout, or policy-design authority.

| Package | Classification | Facade | Exports | Owner | README |
| --- | --- | --- | ---: | --- | --- |
| `polisyos.common` | `public_stable` | `lazy_facade` | 7 | `team-polisyos` | `src/polisyos/common/README.md` |
| `polisyos.core` | `public_stable` | `lazy_facade` | 133 | `team-polisyos` | `src/polisyos/core/README.md` |
| `polisyos.ir` | `public_stable` | `lazy_facade` | 277 | `team-polisyos` | `src/polisyos/ir/README.md` |
| `polisyos.obligation_rules` | `internal` | `eager_exports` | 22 | `team-policyos-runtime` | `src/polisyos/obligation_rules/README.md` |
| `polisyos.obligation_graph` | `internal` | `eager_exports` | 20 | `team-policyos-runtime` | `src/polisyos/obligation_graph/README.md` |
| `polisyos.method_requirement` | `internal` | `eager_exports` | 14 | `team-policyos-runtime` | `src/polisyos/method_requirement/README.md` |
| `polisyos.participation_requirement` | `internal` | `eager_exports` | 23 | `team-policyos-runtime` | `src/polisyos/participation_requirement/README.md` |
| `polisyos.fabric` | `public_stable` | `lazy_facade` | 39 | `team-polisyos` | `src/polisyos/fabric/README.md` |
| `polisyos.foundry` | `public_stable` | `lazy_facade` | 11 | `team-polisyos` | `src/polisyos/foundry/README.md` |
| `polisyos.scientist` | `public_stable` | `lazy_facade` | 26 | `team-polisyos` | `src/polisyos/scientist/README.md` |
| `polisyos.evidence` | `internal` | `eager_exports` | 19 | `team-policyos-runtime` | `src/polisyos/evidence/README.md` |
| `polisyos.runtime` | `public_stable` | `lazy_facade` | 10 | `team-polisyos` | `src/polisyos/runtime/README.md` |
| `polisyos.runtime.quality` | `public_experimental` | `eager_exports` | 965 | `team-polisyos` | `src/polisyos/runtime/quality/README.md` |
| `polisyos.lex` | `public_stable` | `lazy_facade` | 51 | `team-polisyos` | `src/polisyos/lex/README.md` |
| `polisyos.scholar` | `public_experimental` | `lazy_facade` | 25 | `team-polisyos` | `src/polisyos/scholar/README.md` |
| `polisyos.data_forge` | `public_experimental` | `lazy_facade` | 49 | `team-data-forge` | `src/polisyos/data_forge/README.md` |
| `polisyos.berl` | `public_experimental` | `eager_exports` | 11 | `team-scientist` | `src/polisyos/berl/README.md` |
| `polisyos.calibration` | `public_experimental` | `eager_exports` | 10 | `team-scientist` | `src/polisyos/calibration/README.md` |
| `polisyos.ddm` | `internal` | `eager_exports` | 17 | `team-scientist` | `src/polisyos/ddm/README.md` |
| `polisyos.foundry.agent_sim.world` | `public_experimental` | `eager_exports` | 23 | `team-foundry` | `src/polisyos/foundry/agent_sim/world/README.md` |

## `polisyos.common`

- Classification: `public_stable`
- Supported entrypoints: `polisyos.common`, `polisyos.common.config`
- Facade policy: expected `lazy_facade`, observed `lazy_facade`
- Owner: `team-polisyos`
- README: `src/polisyos/common/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Shared helper boundary for config, logging, serialization, and migrations.
- Summary: Expose side-effect-sensitive common helpers behind a lazy package facade.

### Resolved supported entrypoints

| Entrypoint | Source | Facade | Exports |
| --- | --- | --- | ---: |
| `polisyos.common` | `src/polisyos/common/__init__.py` | `lazy_facade` | 7 |
| `polisyos.common.config` | `src/polisyos/common/config.py` | `eager_exports` | 8 |

#### `polisyos.common`

- Source: `src/polisyos/common/__init__.py`
- Facade: `lazy_facade`
- Summary: Expose side-effect-sensitive common helpers behind a lazy package facade.

<details><summary>Entrypoint exports (7)</summary>

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

#### `polisyos.common.config`

- Source: `src/polisyos/common/config.py`
- Facade: `eager_exports`
- Summary: Explicit process bootstrap helpers for env defaults, validation, and logging.

<details><summary>Entrypoint exports (8)</summary>

```text
EnvVarSpec
ProcessBootstrapConfig
apply_process_bootstrap
build_process_bootstrap_config
configure_logging
current_runtime_toggles
get_env_registry
validate_process_bootstrap_config
```

</details>

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
- Supported entrypoints: `polisyos.core`, `polisyos.core.contracts`, `polisyos.core.security`, `polisyos.core.trace`
- Facade policy: expected `lazy_facade`, observed `lazy_facade`
- Owner: `team-polisyos`
- README: `src/polisyos/core/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Cross-layer contracts, CAS, registry, observability, and security primitives.
- Summary: Expose the stable Core platform surface with lazy package imports.

### Resolved supported entrypoints

| Entrypoint | Source | Facade | Exports |
| --- | --- | --- | ---: |
| `polisyos.core` | `src/polisyos/core/__init__.py` | `lazy_facade` | 133 |
| `polisyos.core.contracts` | `src/polisyos/core/contracts/__init__.py` | `lazy_facade` | 449 |
| `polisyos.core.security` | `src/polisyos/core/security/__init__.py` | `lazy_facade` | 102 |
| `polisyos.core.trace` | `src/polisyos/core/trace/__init__.py` | `eager_exports` | 5 |

#### `polisyos.core`

- Source: `src/polisyos/core/__init__.py`
- Facade: `lazy_facade`
- Summary: Expose the stable Core platform surface with lazy package imports.

<details><summary>Entrypoint exports (133)</summary>

```text
FULL_PREFIX_EVALUATION_TABLE
FULL_PREFIX_FAILURE_DESCRIPTORS
FULL_PREFIX_TERMINAL_BY_RESULT_KIND
SECRET_AND_PII_SCAN_SCOPES
SECRET_PII_DETECTOR_VERSION
AcceptanceRejectedNonReceipt
AcceptanceUnavailableNonReceipt
AnchorAcceptanceRequest
AnchorCustodyVerification
AnchorRetentionPackage
ApplicablePredicateDenominatorArtifactFailure
ApplicablePredicateDenominatorStatement
ChronologyApplicablePredicateDenominatorArtifacts
ChronologyBundleHeader
ChronologyBundleRequest
ChronologyMemberInput
ChronologyPersistenceFailure
ChronologyPersistenceManifestMismatch
ChronologyPersistenceNotEstablished
ChronologyPersistenceStoreIntegrityMismatch
ChronologyPersistenceVerificationMismatch
ChronologyPredicatePolicyArtifacts
ChronologyProofDomain
ChronologyProofPersistenceFailed
ChronologyProofPersistenceResult
Digest
EncodedChronologyBundle
ExpectedCommitmentPrefix
FullPrefixBuildFailureCode
FullPrefixBuildRejected
FullPrefixBuildResult
FullPrefixCheckState
FullPrefixEnvelopeFailureCode
FullPrefixEnvelopeRejected
FullPrefixEvaluationKey
FullPrefixEvaluationState
FullPrefixExpectedPrefixFailureCode
FullPrefixExpectedPrefixRejected
FullPrefixFailureDescriptor
FullPrefixInputMode
FullPrefixInternalConsistencyFailureCode
FullPrefixInternalConsistencyRejected
FullPrefixInvocationFailureCode
FullPrefixInvocationRejected
FullPrefixMemberFailureCode
FullPrefixMemberRejected
FullPrefixRejected
FullPrefixTerminalCheck
FullPrefixVerificationResult
FullPrefixVerificationStatement
FullPrefixVerified
FullPrefixVerifier
MemberPredicateDisposition
NativeApplicablePredicateDenominatorPersistenceFailed
NativeAuthorityHeadNotEstablished
NativeChronologyCandidate
NativeChronologyCandidateRejected
NativeChronologyOwnerContext
NativeChronologyPersistenceFailed
NativeChronologyPolicyResolutionFailed
NativeChronologyQualificationResult
NativeChronologyQualified
NativeChronologyQuery
NativeChronologyReconciliation
NativeExteriorAndAuthorityHeadNotEstablished
NativeExteriorNotEstablished
NativeFullPrefixBuildRejected
NativeFullPrefixProofRejected
NativePredicateRejected
NativeProjectionCustodyGap
NativeSchemaProfileRejected
OwnerQualifiedNativeCandidate
PersistedApplicablePredicateDenominator
PersistedChronologyProof
PersistedPredicateAdmissionPolicy
PersistedPredicatePolicyAdmission
PolicyAdmissionAmbiguousFailure
PolicyAdmissionMissingFailure
PolicyBindingMismatchFailure
PolicyBytesMissingFailure
PolicyOwnerDenominatorMismatchFailure
PolicyOwnerRelationNotEstablished
PolicyOwnerRelationRejected
PolicyQueryBindingMismatchFailure
PredicateAdmissionPolicyStatement
PredicateAdmissionRule
PredicateClass
PredicateDisposition
PredicatePolicyAdmissionIndex
PredicatePolicyAdmissionStatement
PredicatePolicyOwnerProvenanceVerifier
PredicatePolicyOwnerRelationFailure
PredicatePolicyResolutionContext
PredicatePolicyResolutionFailure
PredicatePolicySelectionKey
PromptSanitizer
QueryPredicateDisposition
RejectedAcceptanceOutcome
RejectedRetentionOutcome
ResolvedPredicatePolicyAdmission
RetentionRejectedNonReceipt
RetentionUnavailableNonReceipt
SecretAndPIIScanReport
SecretPIIScanResult
UnavailableAcceptanceOutcome
UnavailableRetentionOutcome
VerifiedAcceptanceOutcome
VerifiedAnchorAcceptance
VerifiedAnchorRetention
VerifiedNativeMemberIdentity
VerifiedNativeSubjectIdentity
VerifiedOwnerPredicateEvidence
VerifiedPolicyOwnerProvenance
VerifiedPredicatePolicyOwnerRelation
VerifiedRetentionOutcome
artifacts
backends
build_full_prefix_bundle
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
scan_secret_and_pii
security
```

</details>

#### `polisyos.core.contracts`

- Source: `src/polisyos/core/contracts/__init__.py`
- Facade: `lazy_facade`
- Summary: Lazy facade for the stable DTOs shared across PolicyOS subsystem boundaries.

<details><summary>Entrypoint exports (449)</summary>

```text
*_CHRONOLOGY_EXPORTS
BOUNDED_LIVENESS_CONFIG_SCHEMA_VERSION
C4_PERSISTED_PROFILE_SPECS
CAPABILITY_DISCOVERY_SCHEMA_VERSION
OPTIONAL_ANALYTIC_NODE_KINDS
POLICY_DESIGN_CASE_PROJECTION_SCHEMA_VERSION
PRODUCER_SPINE_CONSUMER_COMPONENTS
PRODUCER_SPINE_CONTEXT_SCHEMA_VERSION
RECOURSE_POINTER_SCHEMA_VERSION
REQUIREMENT_TO_CAPABILITY_QUERY_SCHEMA_VERSION
SERIOUS_SKIP_BLOCKER_PROFILES
SKIP_BLOCKER_REQUIRED_FIELDS
SKIP_BLOCKER_SURFACES
ActiveDisambiguationPlanRef
ActivityType
AgentType
ApiMeta
ArtifactContentPreview
ArtifactContentResponse
ArtifactLineageEdge
ArtifactLineageNode
ArtifactLineageResponse
ArtifactLineageView
ArtifactManifestResponse
ArtifactManifestView
ArtifactSchemaResponse
ArtifactSchemaView
AttractorAnalysisProvenance
AttractorAnalysisRequest
AttractorAnalysisResponse
AttractorAnalysisResult
AttractorAnalysisResultRef
AttractorBasinEstimate
AttractorCertificate
AttractorObservableSummary
AttractorParameterPoint
AttractorSpectralValue
AttractorStability
AttractorStateProjection
AttractorStateRepresentation
AttractorSummary
AttractorUncertainty
AttractorUncertaintySummary
AuthorityPosture
BacktestReportRef
BasinEstimate
BasinMap
BasinMapRef
BasinMapSample
BifurcationCandidate
BifurcationEvent
BootstrapStabilityReportRef
BoundedLivenessConfig
BoundedLivenessResolution
BudgetSpec
BudgetsV1
C4PersistedProfileSpec
CacheEntryInfo
CacheStatusResponse
CalibrationReportRef
CalibrationValidationBundleRef
CapabilityAuthorityPostureResult
CapabilityAuthorityState
CapabilityBindingLike
CapabilityDiscoveryAudience
CapabilityDiscoveryItem
CapabilityDiscoveryPostureResult
CapabilityDiscoveryRequest
CapabilityDiscoveryResponse
CapabilityDiscoveryState
CapabilityExecutionPostureResult
CapabilityExecutionState
CapabilityFreshness
CapabilityResolverPort
CapabilityResourceKind
CapabilityTimeSemantics
CausalAssumptionCardRef
CausalDiscoveryReportRef
CausalEffectReportRef
CausalFrontierAreaRecord
CausalFrontierEdgeRecord
CausalFrontierExposureRecord
CausalFrontierOutputRefs
CausalFrontierSAEEstimate
CausalFrontierSAERequest
CausalFrontierSAEResponse
CausalGraphModelRef
CausalModelEnsembleRef
CausalQueryResultRef
CausalSensitivityResultRef
ChangeProposal
ChangeProposalRef
CheckpointRef
CompileReportRef
CompileRequest
CompileResult
ComplianceIssue
ConnectorInfo
ConnectorsListResponse
ContinuationBranch
ContinuationBranchPoint
ContinuationBranchRef
ControlFailureEnvelope
ControlOutboxEventInfo
ControlOutboxEventsResponse
ControlWorkerLeaseInfo
ControlWorkersResponse
CritiqueRef
CursorPage
DataSnapshot
DataSnapshotRef
DataSourceBinding
DataTrust
DataViewRequestRef
DatasetFetchSpecRequest
DecisionBasisSection
DecisionCardRef
DecisionDependencyKind
DecisionDependencyRef
DecisionPacketAuthoredBlock
DecisionPacketEffectSize
DecisionPacketMetricComparisonRow
DecisionPacketMetricSignificance
DecisionPacketOutlineEntry
DecisionPacketPreview
DecisionPacketRef
DecisionTriggerRecord
DecisionTriggerSpec
DecisionTriggerType
DecisionValidityEnvelope
DecisionValidityEvaluation
DecisionValidityLifecycleSummary
DecisionValidityPendingReview
DecisionValidityStatus
DecisionValiditySummaryResponse
DerivedArtifact
DiscoveryArtifactBundleRef
DiscoveryAuditBundleRef
DiscoveryPosture
DiscoveryTaskProfileRef
DistributionalBoundsBundleRef
DistributionalDualCertificateRef
DistributionalEffectBundleRef
DistributionalProofArtifactRef
DistributionalReportRef
DownstreamUtilityReportRef
DriftReadinessRef
EdgeConfidenceMatrixRef
EntityType
EnvironmentManifestRef
EpochTransitionVerificationReceipt
EpochTransitionVerifier
EpochValidityAuthorityGate
EpochValidityBatchCompletionStatement
EpochValidityBatchReceipt
EpochValidityBatchRequest
EpochValidityBatchResponse
EpochValidityBatchTarget
EpochValidityCompletedBatchEvidenceDenominator
EpochValidityCompletedBatchEvidenceResolver
EpochValidityGateNonReceipt
EpochValidityGateReceipt
EpochValidityN9EvidenceResolver
EpochValidityN9Projection
EpochValidityPendingBatch
EpochValidityPreN9SubjectAuthority
EquilibriumBasinInterval
EquilibriumBranch
EquilibriumBranchPoint
EquilibriumCandidate
EquilibriumCandidateJacobian
EquilibriumMultiplicityDiagnostics
EquilibriumMultiplicityProvenance
EquilibriumMultiplicityReport
EquilibriumMultiplicityReportRef
EquilibriumSearchProtocol
EvaluatorReport
EvaluatorReportRef
EvaluatorScores
EvaluatorVerdict
EvidenceBundle
EvidenceBundleRef
ExecConfig
ExecConfigRef
ExecPlan
ExecPlanRef
ExecuteRequest
ExecuteResult
ExecutionPlan
ExecutionPlanRef
ExecutionProfile
ExpectedOutputSpec
ExperimentStateRef
ExplanationBundleRef
FabricResult
FabricResultRef
FailureCardRef
ForecastingUncertaintyBundleRef
FoundryCompileConfig
FoundryExecConfig
FoundryInputBindingReportRef
FoundryInputBindingRule
FoundryInputBindingTransform
FoundryInputBindings
FoundryInputBindingsRef
FoundryValidationFlags
FreshnessMetadata
FreshnessStatus
GovernanceConstraint
GovernanceDebugResponse
GovernanceDebugView
GovernanceReportRef
GraphHypothesisRef
GraphHypothesisSetRef
GraphPriorBundleRef
HTEResultRef
ICBackendHint
ICCertificateScope
ICConformanceVerdict
ICImplementationConformanceReport
ICImplementationConformanceReportRef
ICImplementationConformanceRequest
ICImplementationConformanceResult
ICNegativeCertificate
ICNegativeCertificateRef
ICProofAttachmentRef
ICProperty
ICVerificationCertificateRef
ICVerificationMode
ICVerificationReport
ICVerificationReportRef
ICVerificationRequest
ICVerificationResult
IdentifiabilityDiagnosticRef
IncentiveCompatibilityCertificate
IngestRequest
IngestResponse
IssueSeverity
IterationLifecycleState
IterationState
IterationStateRef
JudgeVerdictRef
KnowledgeBundle
KnowledgeBundleRef
LegalContext
LegalEvaluationRequest
LegalReport
LegalReportRef
LinkReportRef
LiteratureCausalPriorRef
LoweredIR
LoweredIRRef
MethodCatalogEntry
MethodCatalogSnapshot
MethodCatalogSnapshotRef
MethodDagEdge
MethodDagNode
MetricObservationBundle
MetricObservationBundleRef
MetricValidationReportRef
Metrics
MetricsRef
MobilityBoundsRequest
MobilityBoundsResponse
MobilityDiagnosticsResponse
MobilityEstimateRequest
MobilityEstimateResponse
MobilityReportResponse
ModelOutputs
ModelSpecRef
NaturalLanguageRunRequest
NodeDebugResponse
NodeDebugView
NodeStatus
NormDiffRef
NormImpactReportRef
NormPack
NormRef
NormRule
OrdinalPovertyReportRef
PeriodicOrbitDiagnostics
PeriodicOrbitDiagnosticsRef
PersistedEpochValidityBatchEvidence
PersistedEpochValidityGateEvidence
PersistedPreN9AdmittedCandidateBatch
PersistedPreN9EpochValiditySubject
PlanDataNeed
PlatformMetaEvaluationReportRef
PolicyDesignCaseAudience
PolicyDesignCaseCloseoutTruth
PolicyDesignCaseContestedRecord
PolicyDesignCaseDeficitProjection
PolicyDesignCaseInvariantSummary
PolicyDesignCaseParticipationRequirementProjection
PolicyDesignCaseProjection
PolicyDesignCaseProjectionBlocker
PolicyDesignCaseProjectionConsumerContract
PolicyDesignCaseProjectionGap
PolicyDesignCaseProjectionLabel
PolicyDesignCaseProjectionOmission
PolicyDesignCaseRecoursePointer
PolicyPortfolioRef
PolicyRecommendationRef
PolicySpecRef
PreN9AdmittedCandidate
PreN9EpochValiditySubjectStatement
PreflightDiagnostic
PreflightReport
PreflightReportRef
PreviewMode
PriorKnowledgeBundleRef
PrivacyAwareTransportCertificateRef
ProblemFrameRef
ProducerSpineBindingFields
ProducerSpineReadContext
ProgramGraph
ProgramGraphRef
ProvenanceActivity
ProvenanceAgent
ProvenanceCoreGraph
ProvenanceCoreRef
ProvenanceEdge
ProvenanceEntity
QueryPlan
QueryPlanRef
RefutationReportRef
RegimeShiftForecastBundleRef
RelationType
ReproducibilityManifest
ReproducibilityManifestRef
ReproducibilityReportRef
RequirementTimeWindow
RequirementToCapabilityQuery
ResearchIntent
ResearchIntentRef
RuleBackend
RuleType
RunDetails
RunDetailsResponse
RunErrorView
RunErrorsResponse
RunLaunchResponse
RunLineageResponse
RunNodeRecord
RunNodesResponse
RunRecordV1
RunSummary
RunTimelineEvent
RunTimelineResponse
RunTimelineSummary
RunTimelineView
RunsListResponse
RuntimeApiError
RuntimeApiProblem
ScenarioFamilyConstructRow
ScenarioFamilyConstructRows
SearchCompletenessStatus
SearchFrontier
SensitivityAnalysisBundleRef
SensitivityResultRef
ShiftDiagnosticReportRef
SimulationResult
SimulationResultRef
SkipBlockerContractError
SkipBlockerPolicyDecision
SkippedNodeBlocker
SourceKind
SourceSpec
StateDelta
StateDeltaRef
StateSnapshot
StateSnapshotRef
StopCriteria
StopReason
StressTestReportRef
StructuralCausalModelSpecRef
ThresholdsV1
TimelineRef
TraceSliceRef
TransportabilityResultRef
TreasurySeed
TreasurySeedRef
TrinityBundle
TrinityBundleRef
TrinityIRRef
TrinityManifest
UncertaintyBounds
UncertaintyBoundsRef
UncertaintyEnvelopeRef
UniversalAuthorityProfile
UniversalGeographyPredicate
UniversalPolicyAuthorityPurpose
UniversalPolicyAuthorityTypeFacet
UniversalPolicyCapabilityRealityLabel
UniversalPolicyDeliveryChannel
UniversalPolicyDeliveryChannelFacet
UniversalPolicyDesignCase
UniversalPolicyDesignCaseAuditSurface
UniversalPolicyFacetName
UniversalPolicyFacets
UniversalPolicyFundingChannel
UniversalPolicyFundingChannelFacet
UniversalPolicyGeographyPredicateFacet
UniversalPolicyGrammarAuthorityEnvelope
UniversalPolicyGrammarBlocker
UniversalPolicyGrammarSourceClassification
UniversalPolicyGrammarStatus
UniversalPolicyInstrumentType
UniversalPolicyInstrumentTypeFacet
UniversalPolicyMethodNeedFacet
UniversalPolicyOutcomeChannelFacet
UniversalPolicyPopulationPredicateFacet
UniversalPolicyRiskFacet
UniversalPolicyRiskFacetRecord
UniversalPolicyTargetingType
UniversalPolicyTargetingTypeFacet
UniversalPolicyTimePredicateFacet
UniversalPopulationPredicate
UniversalTimePredicate
UnresolvedEquilibriumStart
ValidationReportRef
ValueOuterSet
ValueOuterSetAssumptionStatus
ValueOuterSetComparison
ValueOuterSetIdentificationStatus
ValueOuterSetRepresentation
ValueOuterSetRepresentationStatus
ValuePromotionDecision
ValuePromotionDecisionGrade
ValuePromotionDecisionReason
WarningsBundle
WarningsRef
WorkflowRunRequest
bounded_liveness_config_from_mapping
build_producer_spine_binding_fields
build_skip_blocker_record
c4_canonical_bytes
c4_canonical_mapping
c4_profile
c4_profile_manifest_is_exact
c4_semantic_digest
chronology
classify_optional_analytic_node
construct_for_legacy_family
deserialize_skip_blocker_record
epoch
evaluate_skip_blocker_policy
legacy_family_for_construct
serialize_skip_blocker_record
```

</details>

#### `polisyos.core.security`

- Source: `src/polisyos/core/security/__init__.py`
- Facade: `lazy_facade`
- Summary: Lazy facade for tenant routing, audit, identity, authz, TEE, and SBOM security APIs.

<details><summary>Entrypoint exports (102)</summary>

```text
SECURITY_ASSURANCE_REPORT_REF_KEY
SECURITY_REPORT_FILE
C3_CANONICAL_CODECS
TENANT_HEADER
AccessScope
AttestationDeniedError
AttestationPolicy
AttestationReport
AttestationResult
AttestationStatus
AuditActor
AuditCorrelation
AuditEventType
AuditLog
AuditResource
AuthorizationDeniedError
AuthorizationError
AuthzDecision
AuthzInput
AuthzResult
CellAssignment
CellCapacityError
CellRegistry
CellResolution
CellSpec
CellTier
ChainVerificationResult
ChainVerifier
ChainedAuditSink
ChainedLogEntry
ColdTierBackend
CrossTenantAccessError
DatabaseBackend
DelegationContextClaims
DelegationError
DelegationTokenManager
DelegationVerificationError
DuckDBLegacyBackend
ExactAnchorAcceptanceReceiptVerifier
ExactAnchorHolderReceiptVerifier
FileAnchorAcceptanceLineageRepository
FullPrefixVerifier
HotTierBackend
IdentityError
IdentityNotAvailableError
IdentityVerificationError
InTotoStatement
InMemoryAnchorReadbackChallengeRepository
IsolationLevel
LocalJsonlBackend
MFARequiredError
MissingTenantHeaderError
NamespacedArtifactStore
NoOpVerifier
OPAClient
PIIAccessLevel
PolicyOSRole
PostgresBackend
RoutingResult
SBOMGenerator
SBOMMetadata
SBOMVerificationResult
SBOMVerifier
SEVSNPVerifier
SPIFFEIdentityProvider
SecuritySettings
ServiceIdentity
ServiceIdentityInfo
TEEGatekeeper
TEEPlatform
TenantContext
TenantContextNotSetError
TenantIsolationError
TenantNotFoundError
TenantQuotaLimits
TenantQuotaRegistry
TenantRoutingError
TenantSpec
TokenValidationError
UserIdentityClaims
VulnerabilityRecord
VulnerabilitySeverity
build_default_audit_backends_from_env
build_security_assurance_report
build_full_prefix_bundle
build_retention_package
canonical_statement_bytes
get_current_access_scope_or_none
get_current_cell_id
get_current_tenant_id
get_current_tenant_id_or_none
get_security_settings
parse_canonical_statement
raw_content_hash
require_tenant_context
reset_current_access_scope
resolve_routing
security_gates_from_report
semantic_content_hash
set_current_access_scope
tenant_scope
validate_tenant_id
```

</details>

#### `polisyos.core.trace`

- Source: `src/polisyos/core/trace/__init__.py`
- Facade: `eager_exports`
- Summary: Exports trace records and sinks used to persist run-level execution telemetry.

<details><summary>Entrypoint exports (5)</summary>

```text
CompositeTraceSink
JsonlTraceSink
RunTerminality
TraceRecord
TraceSink
```

</details>

<details><summary>Supported exports (133)</summary>

```text
FULL_PREFIX_EVALUATION_TABLE
FULL_PREFIX_FAILURE_DESCRIPTORS
FULL_PREFIX_TERMINAL_BY_RESULT_KIND
SECRET_AND_PII_SCAN_SCOPES
SECRET_PII_DETECTOR_VERSION
AcceptanceRejectedNonReceipt
AcceptanceUnavailableNonReceipt
AnchorAcceptanceRequest
AnchorCustodyVerification
AnchorRetentionPackage
ApplicablePredicateDenominatorArtifactFailure
ApplicablePredicateDenominatorStatement
ChronologyApplicablePredicateDenominatorArtifacts
ChronologyBundleHeader
ChronologyBundleRequest
ChronologyMemberInput
ChronologyPersistenceFailure
ChronologyPersistenceManifestMismatch
ChronologyPersistenceNotEstablished
ChronologyPersistenceStoreIntegrityMismatch
ChronologyPersistenceVerificationMismatch
ChronologyPredicatePolicyArtifacts
ChronologyProofDomain
ChronologyProofPersistenceFailed
ChronologyProofPersistenceResult
Digest
EncodedChronologyBundle
ExpectedCommitmentPrefix
FullPrefixBuildFailureCode
FullPrefixBuildRejected
FullPrefixBuildResult
FullPrefixCheckState
FullPrefixEnvelopeFailureCode
FullPrefixEnvelopeRejected
FullPrefixEvaluationKey
FullPrefixEvaluationState
FullPrefixExpectedPrefixFailureCode
FullPrefixExpectedPrefixRejected
FullPrefixFailureDescriptor
FullPrefixInputMode
FullPrefixInternalConsistencyFailureCode
FullPrefixInternalConsistencyRejected
FullPrefixInvocationFailureCode
FullPrefixInvocationRejected
FullPrefixMemberFailureCode
FullPrefixMemberRejected
FullPrefixRejected
FullPrefixTerminalCheck
FullPrefixVerificationResult
FullPrefixVerificationStatement
FullPrefixVerified
FullPrefixVerifier
MemberPredicateDisposition
NativeApplicablePredicateDenominatorPersistenceFailed
NativeAuthorityHeadNotEstablished
NativeChronologyCandidate
NativeChronologyCandidateRejected
NativeChronologyOwnerContext
NativeChronologyPersistenceFailed
NativeChronologyPolicyResolutionFailed
NativeChronologyQualificationResult
NativeChronologyQualified
NativeChronologyQuery
NativeChronologyReconciliation
NativeExteriorAndAuthorityHeadNotEstablished
NativeExteriorNotEstablished
NativeFullPrefixBuildRejected
NativeFullPrefixProofRejected
NativePredicateRejected
NativeProjectionCustodyGap
NativeSchemaProfileRejected
OwnerQualifiedNativeCandidate
PersistedApplicablePredicateDenominator
PersistedChronologyProof
PersistedPredicateAdmissionPolicy
PersistedPredicatePolicyAdmission
PolicyAdmissionAmbiguousFailure
PolicyAdmissionMissingFailure
PolicyBindingMismatchFailure
PolicyBytesMissingFailure
PolicyOwnerDenominatorMismatchFailure
PolicyOwnerRelationNotEstablished
PolicyOwnerRelationRejected
PolicyQueryBindingMismatchFailure
PredicateAdmissionPolicyStatement
PredicateAdmissionRule
PredicateClass
PredicateDisposition
PredicatePolicyAdmissionIndex
PredicatePolicyAdmissionStatement
PredicatePolicyOwnerProvenanceVerifier
PredicatePolicyOwnerRelationFailure
PredicatePolicyResolutionContext
PredicatePolicyResolutionFailure
PredicatePolicySelectionKey
PromptSanitizer
QueryPredicateDisposition
RejectedAcceptanceOutcome
RejectedRetentionOutcome
ResolvedPredicatePolicyAdmission
RetentionRejectedNonReceipt
RetentionUnavailableNonReceipt
SecretAndPIIScanReport
SecretPIIScanResult
UnavailableAcceptanceOutcome
UnavailableRetentionOutcome
VerifiedAcceptanceOutcome
VerifiedAnchorAcceptance
VerifiedAnchorRetention
VerifiedNativeMemberIdentity
VerifiedNativeSubjectIdentity
VerifiedOwnerPredicateEvidence
VerifiedPolicyOwnerProvenance
VerifiedPredicatePolicyOwnerRelation
VerifiedRetentionOutcome
artifacts
backends
build_full_prefix_bundle
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
scan_secret_and_pii
security
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

### Resolved supported entrypoints

| Entrypoint | Source | Facade | Exports |
| --- | --- | --- | ---: |
| `polisyos.ir` | `src/polisyos/ir/__init__.py` | `lazy_facade` | 277 |
| `polisyos.ir.api` | `src/polisyos/ir/api.py` | `eager_exports` | 11 |

#### `polisyos.ir`

- Source: `src/polisyos/ir/__init__.py`
- Facade: `lazy_facade`
- Summary: Expose the stable IR contract surface through a lazy package facade.

<details><summary>Entrypoint exports (277)</summary>

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
CompiledLexIntervention
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
FailureSeverity
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
TypedFailureCard
UncertaintyEnvelope
UncertaintySource
UncertaintyType
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

#### `polisyos.ir.api`

- Source: `src/polisyos/ir/api.py`
- Facade: `eager_exports`
- Summary: Machine-readable manifest for the documented IR package facades.

<details><summary>Entrypoint exports (11)</summary>

```text
ANALYTICS_FACADE_EXPORTS
IR_NAMING_CONVENTIONS
KERNEL_FACADE_EXPORTS
PACKAGE_FACADE_EXPORTS
PACKAGE_FACADE_IMPORT_POLICY
WORLD_FACADE_EXPORTS
LazyExportMap
RegistryItemId
facade_export_names
lazy_dir
resolve_lazy_export
```

</details>

<details><summary>Supported exports (277)</summary>

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
CompiledLexIntervention
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
FailureSeverity
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
TypedFailureCard
UncertaintyEnvelope
UncertaintySource
UncertaintyType
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

### Resolved supported entrypoints

| Entrypoint | Source | Facade | Exports |
| --- | --- | --- | ---: |
| `polisyos.obligation_rules` | `src/polisyos/obligation_rules/__init__.py` | `eager_exports` | 22 |

#### `polisyos.obligation_rules`

- Source: `src/polisyos/obligation_rules/__init__.py`
- Facade: `eager_exports`
- Summary: Governed obligation rule catalog public module.

<details><summary>Entrypoint exports (22)</summary>

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

### Resolved supported entrypoints

| Entrypoint | Source | Facade | Exports |
| --- | --- | --- | ---: |
| `polisyos.obligation_graph` | `src/polisyos/obligation_graph/__init__.py` | `eager_exports` | 20 |

#### `polisyos.obligation_graph`

- Source: `src/polisyos/obligation_graph/__init__.py`
- Facade: `eager_exports`
- Summary: W6.C obligation graph compiler and ledger contracts.

<details><summary>Entrypoint exports (20)</summary>

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

### Resolved supported entrypoints

| Entrypoint | Source | Facade | Exports |
| --- | --- | --- | ---: |
| `polisyos.method_requirement` | `src/polisyos/method_requirement/__init__.py` | `eager_exports` | 14 |

#### `polisyos.method_requirement`

- Source: `src/polisyos/method_requirement/__init__.py`
- Facade: `eager_exports`
- Summary: Method validity requirement compiler for universal Policy Design Cases.

<details><summary>Entrypoint exports (14)</summary>

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

### Resolved supported entrypoints

| Entrypoint | Source | Facade | Exports |
| --- | --- | --- | ---: |
| `polisyos.participation_requirement` | `src/polisyos/participation_requirement/__init__.py` | `eager_exports` | 23 |

#### `polisyos.participation_requirement`

- Source: `src/polisyos/participation_requirement/__init__.py`
- Facade: `eager_exports`
- Summary: Participation provenance requirement compiler and consumer enforcement.

<details><summary>Entrypoint exports (23)</summary>

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

### Resolved supported entrypoints

| Entrypoint | Source | Facade | Exports |
| --- | --- | --- | ---: |
| `polisyos.fabric` | `src/polisyos/fabric/__init__.py` | `lazy_facade` | 39 |
| `polisyos.fabric.api` | `src/polisyos/fabric/api.py` | `module_doc_only` | 0 |

#### `polisyos.fabric`

- Source: `src/polisyos/fabric/__init__.py`
- Facade: `lazy_facade`
- Summary: Stable Fabric facade for connector ingestion, world-query, and catalog APIs.

<details><summary>Entrypoint exports (39)</summary>

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
SimulationDB
SourceContract
SourceContractRef
TemporalRef
TypedGap
UnitRef
WorldQueryError
WorldQueryRequest
atomic_write_json
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
resolve_world_snapshot
run_connectors_ingestion
stream_processing_contract
world
```

</details>

#### `polisyos.fabric.api`

- Source: `src/polisyos/fabric/api.py`
- Facade: `module_doc_only`
- Summary: Explicit public Fabric API facade and connector bridge.

<details><summary>Supported exports (39)</summary>

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
SimulationDB
SourceContract
SourceContractRef
TemporalRef
TypedGap
UnitRef
WorldQueryError
WorldQueryRequest
atomic_write_json
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
resolve_world_snapshot
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
- Notes: Stable lazy facade over compile/execute and three generic text-embedding surfaces. Phase 6 keeps public exports on declared facades; moved legacy FQN are compatibility shims registered in architecture/shims.toml.
- Summary: Expose the stable Foundry compile/execute entrypoints behind lazy imports.

### Resolved supported entrypoints

| Entrypoint | Source | Facade | Exports |
| --- | --- | --- | ---: |
| `polisyos.foundry` | `src/polisyos/foundry/__init__.py` | `lazy_facade` | 11 |
| `polisyos.foundry.api` | `src/polisyos/foundry/api.py` | `eager_exports` | 3 |
| `polisyos.foundry.compile` | `src/polisyos/foundry/compile/__init__.py` | `lazy_facade` | 1 |
| `polisyos.foundry.execute` | `src/polisyos/foundry/execute/__init__.py` | `lazy_facade` | 3 |

#### `polisyos.foundry`

- Source: `src/polisyos/foundry/__init__.py`
- Facade: `lazy_facade`
- Summary: Expose the stable Foundry compile/execute entrypoints behind lazy imports.

<details><summary>Entrypoint exports (11)</summary>

```text
DependencyProfileResolutionFailure
EmbedderProtocol
MethodCatalogDependencyAuthorityRequest
SentenceTransformerEmbedder
TFIDFEmbedder
build_method_catalog_provenance_manifest
build_method_catalog_runtime_identity
compile
compile_program
execute
select_method_candidates_for_requirements
```

</details>

#### `polisyos.foundry.api`

- Source: `src/polisyos/foundry/api.py`
- Facade: `eager_exports`
- Summary: Stable Foundry public facade for compile and execute entrypoints.

<details><summary>Entrypoint exports (3)</summary>

```text
compile
compile_program
execute
```

</details>

#### `polisyos.foundry.compile`

- Source: `src/polisyos/foundry/compile/__init__.py`
- Facade: `lazy_facade`
- Summary: Expose the compile facade without importing the Trinity compiler eagerly.

<details><summary>Entrypoint exports (1)</summary>

```text
compile
```

</details>

#### `polisyos.foundry.execute`

- Source: `src/polisyos/foundry/execute/__init__.py`
- Facade: `lazy_facade`
- Summary: Stable execute facade for compiled Foundry plans.

<details><summary>Entrypoint exports (3)</summary>

```text
ResolvedExecutionPosture
execute
resolve_execution_posture
```

</details>

<details><summary>Supported exports (11)</summary>

```text
DependencyProfileResolutionFailure
EmbedderProtocol
MethodCatalogDependencyAuthorityRequest
SentenceTransformerEmbedder
TFIDFEmbedder
build_method_catalog_provenance_manifest
build_method_catalog_runtime_identity
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

### Resolved supported entrypoints

| Entrypoint | Source | Facade | Exports |
| --- | --- | --- | ---: |
| `polisyos.scientist` | `src/polisyos/scientist/__init__.py` | `lazy_facade` | 26 |
| `polisyos.scientist.methods.research_dag` | `src/polisyos/scientist/methods/research_dag/__init__.py` | `eager_exports` | 44 |

#### `polisyos.scientist`

- Source: `src/polisyos/scientist/__init__.py`
- Facade: `lazy_facade`
- Summary: Stable Scientist package facade for workflow execution and run observability.

<details><summary>Entrypoint exports (26)</summary>

```text
BudgetState
ClaimLedgerCurrentHeadProjection
ClaimLedgerOwnerPort
ClaimLifecycleBridgeAdvanced
EpochClaimLifecycleBridgeService
ExperimentState
KnowledgeToolkit
ScientistLegalBenchmarkRunner
ScientistRetrievalBenchmarkOutcome
ToolContractSummary
ToolDefinition
ToolLoopResult
ToolRegistry
build_governance_pipeline
build_default_claim_ledger_owner
build_epoch_claim_lifecycle_bridge
build_knowledge_tool_registry
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

#### `polisyos.scientist.methods.research_dag`

- Source: `src/polisyos/scientist/methods/research_dag/__init__.py`
- Facade: `eager_exports`
- Summary: Research DAG public API for Scientist best-in-class Phase 1.2.

<details><summary>Entrypoint exports (44)</summary>

```text
REQUIRE_RESEARCH_DAG_FOR_PUBLICATION_FLAG
RESEARCH_DAG_FEATURE_FLAG
RESEARCH_DAG_KIND
ReplayMode
ResearchDAGArtifact
ResearchDAGBuilder
ResearchDAGEdge
ResearchDAGDiff
ResearchDAGNode
ResearchDAGReplay
ResearchEdgeType
ResearchNodeType
ResearchReplayPlan
ResearchReplayStep
ResearchTrajectoryComparisonReport
SELECTED_RESEARCH_DAG_WORKFLOWS
SourceInvalidationEvent
SourceInvalidationImpact
append_invalidation_events_to_ledger
claim_lifecycle_events_for_invalidation
compare_research_trajectories
comparison_report_from_diff
diff_research_dags
is_research_dag_enabled
is_research_dag_required_for_publication
legacy_replay_status
legacy_research_dag_status
load_research_dag
plan_research_replay
persist_research_dag
project_reflexive_memory_events_to_research_dag
project_tool_call_result_to_research_node
project_tool_loop_result_to_research_dag
project_web_evidence_bundle_to_research_dag
project_workflow_execution_to_research_dag
propagate_source_invalidation
public_comparison_export
public_replay_export
replay_research_path
sanitize_public_metadata
stable_fingerprint
untrusted_content_summary
validate_memory_influence_dag_attribution
validate_source_invalidation_event
```

</details>

<details><summary>Supported exports (26)</summary>

```text
BudgetState
ClaimLedgerCurrentHeadProjection
ClaimLedgerOwnerPort
ClaimLifecycleBridgeAdvanced
EpochClaimLifecycleBridgeService
ExperimentState
KnowledgeToolkit
ScientistLegalBenchmarkRunner
ScientistRetrievalBenchmarkOutcome
ToolContractSummary
ToolDefinition
ToolLoopResult
ToolRegistry
build_governance_pipeline
build_default_claim_ledger_owner
build_epoch_claim_lifecycle_bridge
build_knowledge_tool_registry
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

### Resolved supported entrypoints

| Entrypoint | Source | Facade | Exports |
| --- | --- | --- | ---: |
| `polisyos.evidence` | `src/polisyos/evidence/__init__.py` | `eager_exports` | 19 |

#### `polisyos.evidence`

- Source: `src/polisyos/evidence/__init__.py`
- Facade: `eager_exports`
- Summary: Cross-producer evidence graph artifacts for PolicyOS.

<details><summary>Entrypoint exports (19)</summary>

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
- Supported entrypoints: `polisyos.runtime`
- Facade policy: expected `lazy_facade`, observed `lazy_facade`
- Owner: `team-polisyos`
- README: `src/polisyos/runtime/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Replay and runtime-facing contracts. HTTP subpackages stay internal unless separately documented.
- Summary: Expose replay/runtime contracts without importing heavy implementations eagerly.

### Resolved supported entrypoints

| Entrypoint | Source | Facade | Exports |
| --- | --- | --- | ---: |
| `polisyos.runtime` | `src/polisyos/runtime/__init__.py` | `lazy_facade` | 10 |

#### `polisyos.runtime`

- Source: `src/polisyos/runtime/__init__.py`
- Facade: `lazy_facade`
- Summary: Expose replay/runtime contracts without importing heavy implementations eagerly.

<details><summary>Entrypoint exports (10)</summary>

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

## `polisyos.runtime.quality`

- Classification: `public_experimental`
- Supported entrypoints: `polisyos.runtime.quality`
- Facade policy: expected `eager_exports`, observed `eager_exports`
- Owner: `team-polisyos`
- README: `src/polisyos/runtime/quality/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Experimental runtime-quality contract facade; compatibility changes require an explicit release fragment and inventory review.
- Summary: Runtime quality evaluation helpers.

### Resolved supported entrypoints

| Entrypoint | Source | Facade | Exports |
| --- | --- | --- | ---: |
| `polisyos.runtime.quality` | `src/polisyos/runtime/quality/__init__.py` | `eager_exports` | 965 |

#### `polisyos.runtime.quality`

- Source: `src/polisyos/runtime/quality/__init__.py`
- Facade: `eager_exports`
- Summary: Runtime quality evaluation helpers.

<details><summary>Entrypoint exports (965)</summary>

```text
ACQUISITION_PLANNER_GATE_LAYER
ACQUISITION_PLANNER_GATE_PHASE
ACQUISITION_PLANNER_KIND
ACQUISITION_PLANNER_REPORT_KEY
ACQUISITION_PLANNER_SCHEMA_NAME
ACQUISITION_PLANNER_SCHEMA_VERSION
ACQUISITION_STRATEGY_SCHEMA_VERSION
ARGUMENT_GRAPH_CONTRACT_ID
ARGUMENT_GRAPH_EXPORT_SCHEMA_VERSION
ARGUMENT_GRAPH_INSPECTION_SCHEMA_VERSION
ARGUMENT_GRAPH_KIND
ARGUMENT_GRAPH_SCHEMA_VERSION
AUTHORITY_CANDIDATE_FIREWALL_NAME
AUTHORITY_FACTOR_NAMES
C33_RULE_CHANGE_CLASS_TABLE
CALIBRATION_LEDGER_CONTRACT_ID
CALIBRATION_LEDGER_KIND
CALIBRATION_LEDGER_SCHEMA_VERSION
CAPABILITY_AUTHORITY_RULE_VERSION
CAPABILITY_AUTHORITY_SCHEMA_VERSION
CAPABILITY_FAILURE_MODE_SCHEMA_VERSION
CAPABILITY_INDEX_COMPILER_VERSION
CAPABILITY_INDEX_SCHEMA_VERSION
CAPABILITY_RATCHET_CONTRACT_ID
CAPABILITY_RATCHET_SCHEMA_VERSION
CAPABILITY_SOURCE_ASSET_SCHEMA_VERSION
CASE_LIFECYCLE_CONTRACT_ID
CASE_LIFECYCLE_SCHEMA_VERSION
CASE_MATURITY_PROFILE_RECORD_FAMILY
CASE_MATURITY_PROFILE_RECORD_KEY
CASE_MATURITY_PROFILE_SCHEMA_VERSION
CASE_MATURITY_PROFILE_SCORECARD_GATE
CLAIM_ARGUMENT_CONTRACT_ID
CLAIM_ARGUMENT_MAPPING_SCHEMA_VERSION
CLAIM_ARGUMENT_NODE_MAPPING
CLAIM_ARGUMENT_VALIDATION_SCHEMA_VERSION
CLAIM_EVIDENCE_SLOT_KEYS
CLOSEOUT_READER_CONTRACT_ID
CLOSEOUT_READER_CONTRACT_VERSION
CLOSEOUT_READER_SCHEMA_VERSION
COMMITMENT_PROFILE_SCHEMA_VERSION
COMPLEXITY_GOVERNANCE_CONTRACT_ID
COMPLEXITY_GOVERNANCE_CONTROL_ID
COMPLEXITY_GOVERNANCE_FILENAME
COMPLEXITY_GOVERNANCE_REPORT_KEY
COMPLEXITY_GOVERNANCE_SCHEMA_VERSION
CONCEPT_SPINE_BRIDGE_AUTHORITY_SCHEMA_VERSION
CONCEPT_SPINE_HANDSHAKE_LEDGER_SCHEMA_VERSION
CONCEPT_SPINE_HANDSHAKE_RECORD_SCHEMA_VERSION
CONCEPT_SPINE_HYBRID_CARRIER_SCHEMA_VERSION
CONFIG_RELEASE_HARDENING_CONTRACT_ID
CONFIG_RELEASE_HARDENING_PDD_IDS
CONFIG_RELEASE_HARDENING_RECORD_FAMILY
CONFIG_RELEASE_HARDENING_SCHEMA_VERSION
CONFLICT_RECORD_SCHEMA_VERSION
CONSTRUCT_REGISTRY_DEFAULT_PATH
CONSTRUCT_REGISTRY_ID
CONSTRUCT_REGISTRY_RULE_VERSION
CONSTRUCT_REGISTRY_SCHEMA_VERSION
CONSTRUCT_REGISTRY_VERSION
CORE_FORBIDDEN_CURRENT_USES
COST_DEGRADATION_TELEMETRY_CONTRACT_ID
COST_DEGRADATION_TELEMETRY_FILENAME
COST_DEGRADATION_TELEMETRY_REPORT_KEY
COST_DEGRADATION_TELEMETRY_SCHEMA_VERSION
DDM_EVENT_GROUPS
DEFAULT_CAPABILITY_INDEX_REF
DEFAULT_CLOSEOUT_MODULE_READERS
DEFAULT_SOFT_GATE_ESCALATION_SECONDS
DEFAULT_SOFT_GATE_TTL_SECONDS
DESIGN_PROBLEM_SCHEMA_VERSION
DISCONFIRMING_EVIDENCE_LEDGER_CONTRACT_ID
DISCONFIRMING_EVIDENCE_LEDGER_SCHEMA_VERSION
DORMANT_CAPABILITY_INVENTORY_RECORD_KEY
DORMANT_CAPABILITY_INVENTORY_SCHEMA_VERSION
EVIDENCE_CAPABILITY_SCHEMA_VERSION
EVIDENCE_GRAPH_THREATS
EVIDENCE_GRAPH_THREAT_MODEL_RECORD_FAMILY
EVIDENCE_GRAPH_THREAT_MODEL_RECORD_KEY
EVIDENCE_GRAPH_THREAT_MODEL_SCHEMA_VERSION
EVIDENCE_LINE_CONTRACT_ID
EVIDENCE_LINE_SCHEMA_VERSION
EVIDENCE_SYNTHESIS_REPORT_CONTRACT_ID
EVIDENCE_SYNTHESIS_REPORT_SCHEMA_VERSION
EXTERNAL_AUDIT_RECORD_FAMILY
EXTERNAL_AUDIT_RECORD_SCHEMA_VERSION
EX_POST_LEARNING_CONTRACT_ID
EX_POST_LEARNING_SCHEMA_VERSION
FRESHNESS_POLICY_TIME_SEMANTICS_RECORD_KEY
FRESHNESS_POLICY_TIME_SEMANTICS_SCHEMA_VERSION
FULL_MODE_CAPABILITY_FLOORS
GRADED_INDEPENDENCE_FEATURE_FLAG
HIGH_COST_LOW_IMPACT_COST_USD
HIGH_COST_LOW_IMPACT_ELAPSED_SECONDS
HIGH_COST_LOW_IMPACT_REVIEW_HOURS
HISTORICAL_PRIOR_INFLUENCE_SCHEMA_VERSION
HYPOTHESIS_LEDGER_FILENAME
HYPOTHESIS_LEDGER_KIND
HYPOTHESIS_LEDGER_REF_KEY
HYPOTHESIS_LEDGER_REPORT_KEY
HYPOTHESIS_LEDGER_SCHEMA_VERSION
IMPLEMENTATION_MONITORING_EVALUATION_CONTRACT_ID
IMPLEMENTATION_MONITORING_EVALUATION_SCHEMA_VERSION
INDEPENDENCE_MAP_CONTRACT_ID
INDEPENDENCE_MAP_SCHEMA_VERSION
IR_ANALYTICS_CLAIM_BRIDGE_KIND
IR_ANALYTICS_CLAIM_BRIDGE_REF_KEY
IR_ANALYTICS_CLAIM_BRIDGE_SCHEMA_VERSION
LAYER2_S3_SUBSTRATE_ACQUISITION_SCHEMA_VERSION
LAYER2_S4_EPISTEMIC_REGIME_SCHEMA_VERSION
LAYER2_S5_COUPLING_COMPOSITION_SCHEMA_VERSION
LAYER2_S6_BLIND_SPOT_FIREWALLS_SCHEMA_VERSION
LAYER2_S7_DELEGATION_SCHEMA_VERSION
LAYER2_S8_VALUE_CHOICE_RULE_VERSION
LAYER2_S8_VALUE_CHOICE_SCHEMA_VERSION
LAYER2_S9_PROJECTION_LOWERING_RULE_VERSION
LAYER2_S9_PROJECTION_LOWERING_SCHEMA_VERSION
LAYER2_S10_OUTCOME_PREDICTION_RULE_VERSION
LAYER2_S10_OUTCOME_PREDICTION_SCHEMA_VERSION
LAYER2_S11_PREDICTIVE_KNOWLEDGE_RULE_VERSION
LAYER2_S11_PREDICTIVE_KNOWLEDGE_SCHEMA_VERSION
LAYER2_S12_RESOURCE_ECONOMICS_RULE_VERSION
LAYER2_S12_RESOURCE_ECONOMICS_SCHEMA_VERSION
LAYER2_S13_POST_DEPLOY_ACCOUNTABILITY_RULE_VERSION
LAYER2_S13_POST_DEPLOY_ACCOUNTABILITY_SCHEMA_VERSION
LAYER2_S14_UNIVERSALITY_ASSURANCE_RULE_VERSION
LAYER2_S14_UNIVERSALITY_ASSURANCE_SCHEMA_VERSION
LEGACY_MIGRATION_SEMANTIC_LOSS
MEMORY_INFLUENCE_ADR_REF
MEMORY_INFLUENCE_RECORD_KIND
MEMORY_INFLUENCE_REF_PREFIXES
MEMORY_INFLUENCE_SCHEMA_VERSION
MISSING_REALITY_STATES
MULTIVERSE_SPECIFICATION_CURVE_CONTRACT_ID
MULTIVERSE_SPECIFICATION_CURVE_SCHEMA_VERSION
NET_MAV_FORMULA
PASS1B_HARDENING_READINESS_CHECK
PASS1B_HARDENING_SCORECARD_GATE
PASS1B_PDD_REQUIRED_SURFACES
PASS1B_REQUIRED_CASE_BINDING_FIELDS
PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_CONTRACT_ID
PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_PDDS
PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_RECORD_KEY
PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_SCHEMA_VERSION
PERFORMANCE_BUDGET_SECONDS
POLICY_BENCHMARKING_RECORD_CONTRACT_ID
POLICY_BENCHMARKING_RECORD_FAMILY
POLICY_BENCHMARKING_RECORD_SCHEMA_VERSION
POLICY_DESIGN_CAPABILITY_DUTY_STATES
POLICY_DESIGN_CAPABILITY_LEDGER_SCHEMA_VERSION
POLICY_DESIGN_CASE_CORE_NODE_TYPES
POLICY_DESIGN_CASE_MINIMUM_RECORD_FAMILIES
POLICY_DESIGN_CASE_OWNER
POLICY_DESIGN_CASE_PROFILE
POLICY_DESIGN_CASE_PROFILE_METADATA
POLICY_DESIGN_CASE_PROJECTION_SCHEMA_VERSION
POLICY_DESIGN_CASE_REGISTRY_ENTRY_SCHEMA_VERSION
POLICY_DESIGN_CASE_RESERVED_NODE_FAMILIES
POLICY_DESIGN_CASE_SCHEMA_VERSION
POLICY_DESIGN_CONCEPT_SPINE_CONTRACT_ID
POLICY_DESIGN_CONCEPT_SPINE_REQUIRED_CLOSURE_FIELDS
POLICY_DESIGN_CONCEPT_SPINE_SCHEMA_VERSION
POLICY_DESIGN_JURISDICTION_AUTHORITY_LEVELS
POLICY_DESIGN_JURISDICTION_SPINE_SCHEMA_VERSION
POLICY_DESIGN_REQUIRED_CAPABILITIES
POLICY_DESIGN_WALKING_SKELETON_CONTRACT_ID
POLICY_DESIGN_WALKING_SKELETON_SCHEMA_VERSION
POLICY_EVIDENCE_CAPABILITY_REPLAY_REF_KEYS
POLICY_EVIDENCE_CAPABILITY_REPLAY_REF_SCHEMA_VERSION
POLICY_INTENT_ENVELOPE_SCHEMA_VERSION
POSTURE_THRESHOLDS
PRE_PUBLICATION_CHALLENGE_NODE_SCHEMA_VERSION
PRODUCER_PIPELINE_FEATURE_FLAG
PRODUCER_PIPELINE_SCHEMA_VERSION
PRODUCER_SPINE_CONSUMER_COMPONENTS
PRODUCER_SPINE_CONTEXT_SCHEMA_VERSION
PROJECTION_STATES
PURPOSE_MULTIPLIERS
REALITY_STATES
REALITY_STATE_BASE_POINTS
RECORD_FAMILY_MATURITY_LEVELS
RECORD_REGISTRY_READINESS_CHECK
RECORD_REGISTRY_SCHEMA_VERSION
REQUIRED_MULTIVERSE_SOURCE_KINDS
REQUIRED_POLICY_BENCHMARK_METRICS
REQUIREMENT_TO_CAPABILITY_QUERY_SCHEMA_VERSION
REQUIREMENT_TO_CAPABILITY_RESOLVER_RULE_VERSION
RULE_EVOLUTION_CONTRACT_ID
RULE_EVOLUTION_PUBLIC_ANNOTATION_SCHEMA_VERSION
RULE_EVOLUTION_RECORD_FAMILY
RULE_EVOLUTION_REGISTRY_KIND
RULE_EVOLUTION_REGISTRY_SCHEMA_VERSION
RULE_EVOLUTION_REPLAY_SCHEMA_VERSION
RULE_REPLAY_COMPARISON_SCHEMA_VERSION
RULE_REPLAY_EXECUTION_SCHEMA_VERSION
RULE_REPLAY_PUBLIC_REPORT_SCHEMA_VERSION
RUN_COST_GATE_CONTRACT_ID
RUN_COST_GATE_FILENAME
RUN_COST_GATE_REPORT_KEY
RUN_COST_GATE_SCHEMA_VERSION
RUN_COST_PROPORTIONALITY_LEDGER_CONTRACT_ID
RUN_COST_PROPORTIONALITY_LEDGER_SCHEMA_VERSION
S1_GRADED_OUTCOME_SCHEMA_VERSION
S8_VALUE_CHOICE_CELL_REF
S8_VALUE_CHOICE_FLOOR_ID
S9_PROJECTION_FLOOR_ID
S10_CALIBRATION_FLOOR_ID
S10_FALSE_CLEAR_FIELDS
S11_AXIS_CALIBRATION_FLOOR_ID
S11_FALSE_CLEAR_FIELDS
S11_PREDICTIVE_AXES
S12_FALSE_CLEAR_FIELDS
S12_GROWTH_THERMOMETERS_FLOOR_ID
S12_TYPED_BUDGETS
S12_VOI_SITES
S13_ACCOUNTABILITY_FLOOR_ID
S13_FALSE_CLEAR_FIELDS
S14_FALSE_CLEAR_FIELDS
S14_SKEPTIC_DEFEATER_IDS
S14_UNIVERSALITY_FLOOR_ID
SEMANTIC_BINDING_SCHEMA_VERSION
SEMANTIC_EVALUATION_PACK_CONTRACT_ID
SEMANTIC_EVALUATION_PACK_SCHEMA_VERSION
SEMANTIC_GOLD_CARD_CONTRACT_ID
SEMANTIC_GOLD_CARD_SCHEMA_VERSION
SKIP_CAUSALITY_LEDGER_RECORD_KEY
SKIP_CAUSALITY_LEDGER_SCHEMA_VERSION
SOFT_GATE_TELEMETRY_SCHEMA_VERSION
SUPPORTED_EVIDENCE_LINE_STRANDS
WAVE2_I2_MANIFEST_SCHEMA_VERSION
WAVE2_I2_SCHEMA_VERSION
AcquisitionActionRecord
AcquisitionDisposition
AcquisitionGap
AcquisitionGapType
AcquisitionNextAction
AcquisitionPlannerReport
AcquisitionRequirementGap
AcquisitionState
AcquisitionStrategy
AcquisitionStrategyRecord
AcquisitionTaskRecord
ActionItemStatus
AggregationClaimLevel
AggregationScopeRow
AggregationValidityDisposition
AggregationValidityRecord
AllocationPriorityRow
ArgumentGraphError
AssuranceCaseChange
AssuranceCaseDelta
AttributionStatus
AuthorityCandidateInventoryRow
AuthorityEnvelope
AuthorityEnvelopeError
AuthorityEnvelopeViolation
AuthorityLevel
AuthorityProfile
AuthorityReconciliationError
AuthorityReconciliationReport
AuthorizedValueSchedule
AxisFailClosedDisposition
BlindSpotAxis
BlindSpotBridgeConsumerRecord
BlindSpotConstraintStoreUpdate
BlindSpotFirewallReport
BlindSpotOverallPosture
BoundaryCouplingClassification
BudgetKind
CalibrationHistoryPolicy
CalibrationLedger
CalibrationLedgerContractError
CalibrationLedgerEntry
CandidateAuthorityEnvelope
CandidateFirewallError
CandidateLever
CandidateLeverSpace
CanonicalDesignRecord
CapabilityAuthorityError
CapabilityAuthorityFactor
CapabilityAuthorityFactorName
CapabilityBindingResult
CapabilityBindingStatus
CapabilityConflictRecord
CapabilityIndependenceFactor
CapabilityIndex
CapabilityIndexAcquisitionStrategy
CapabilityIndexBuildResult
CapabilityIndexCompilerConfig
CapabilityLifecycle
CapabilityScope
CapabilitySourceAsset
CapacityBuildingObligation
CapacityDimension
CapacityDimensionAssessment
CapacityDisposition
CapacityFeasibilityRecord
CaseMaturityIssue
CaseMaturityValidationResult
CertifiedEnvelopeDelta
ClaimArgumentIssue
ClaimArgumentValidationResult
ClaimBindingRecord
CloseoutModuleReaderSpec
ClusterAuthorityDimensionRecord
ColumnBinding
CommitmentProfileRecord
ComplexityGovernanceError
CompositionAuthorityMode
CompositionDisposition
CompositionLawCheck
CompositionReceipt
ComputationalTractabilityBudget
ConceptNamespaceRef
ConceptRelation
ConfigReleaseHardeningIssue
ConstraintRefinementRoute
ConstraintStatus
ConstructAliasDeprecation
ConstructAuthorityRequirement
ConstructCompatibilityAlias
ConstructCorpusBinding
ConstructDemandLedger
ConstructEntry
ConstructExpression
ConstructMeasurabilityRow
ConstructMeasurabilityStatus
ConstructRegistry
ConstructRegistryError
ConstructValidityRequirements
CostDegradationTelemetryError
CouplingEdge
CouplingGraph
CouplingRegime
CouplingRegimeClassification
CoverageBinding
D4CorpusTrackCoverage
D4CorpusTrackRow
DecisionAction
DecisionNeedReason
DecisionOption
DecisionRightsMatrix
DecisionRightsMatrixRow
DecisionRole
DecompositionResult
DegradationLedgerContractError
DegradationLedgerRecord
DegradationPolicyDecision
DelegationContract
DelegationDisposition
DelegationIntegrityReport
DelegationInteractionMode
DelegationNegativeControlResult
DelegationReferenceClass
DeploymentDossier
DeploymentReadinessDisposition
DerivedFeatureBinding
DesignConstraint
DesignInterfaceContract
DesignObjective
DesignProblem
DesignProblemAuthorityError
DesignRecordMaturityReport
DesignStakeholder
DesignStrategy
DiagnosticEventPayloadPolicy
DisconfirmingEvidenceLedgerError
DivergenceAttributionClass
DivergenceRecord
DynamicsRequirementLevel
EffectiveModeLedger
EnvelopeGrowthEntry
EnvelopeGrowthLedger
EnvelopeRevision
EnvelopeRevisionDirection
EnvelopeRevisionDynamicsRecord
EpistemicRegimeClaim
EvalSafetyAdmissionChallenge
EvalSafetyVerifierPort
EvaluationExecutionContext
EvaluationStatusCompositionRecord
EvaluationStatusCompositionRow
EvidenceAcquisitionNeeds
EvidenceAuthorityEnvelope
EvidenceCapability
EvidenceIndependenceError
EvidenceLineError
EvidenceNeed
EvidenceSynthesisReportError
ExpertOracleBootstrapRecord
ExpertOracleLayerRow
ExploreExploitPosture
ExternalAuditRecordError
FabricBindingRecord
FailureModeNode
FeedbackIntensity
FirewallStatus
FiveRightsCheck
FiveRightsDimension
FiveRightsRequirement
FloorBand
ForecastAuthorityDisposition
ForecastCalibrationRecord
ForecastClaimScope
ForecastMethodFamily
ForecastQualityDisposition
ForecastSupport
ForecastSupportBaseOrigin
ForecastSupportIntegrityReport
ForecastSupportScope
FoundryBindingRecord
FreshnessEnvelope
FrozenClosedCase
GovernanceMetadata
GradedOutcomeDecision
GradedOutcomeEvidenceInput
GradedOutcomeInputError
GroundedAuthorityCoverageRecord
GrowthCountingDisposition
GrowthThermometerRecord
HumanDecisionRecord
HumanDecisionRequest
HypothesisLedger
HypothesisLedgerEntry
IRAnalyticsClaimBinding
ImplementationMonitoringEvaluationError
IntentBindingRecord
InteractionStrength
JurisdictionTimeSemantics
KnowledgeGovernanceMode
KnowledgeGovernanceThroughputLedger
LearningChangeControlClass
LearningUpdateProposal
LearningUpdateTarget
LegitimacyDisposition
LexBindingRecord
LifecycleReissueDisposition
LifecycleStage
LoweringAppendReceipt
LoweringArtifactRecord
LoweringAuthorityGateRecord
LoweringRequestRecord
MandateBasis
MandateLegitimacyRecord
MandateSourceRecord
MandatoryGateState
MeasurabilityAdequacyRecord
MechanismGeneralityReport
MemoryInfluenceRecord
MetricBinding
ModePolicyError
ModePolicyViolation
ModuleDiscoveryResult
MultiverseSpecificationCurveError
NLProvenance
ObjectiveFunctionProvenanceRecord
ObservableSubsetCalibrationStatus
OutcomeDistributionRecord
OutcomeOfInterest
OversightLinkedAccountabilityState
P16OverconfidenceError
P16PrecautionLaunderingError
P17BoundarySpoofError
P17FalseModularityError
P17SyntacticCompositionError
P17SystemDynamicsRequiredError
P18StreetlightMeasurabilityError
P19AggregationLaunderingError
P20NormativeChoiceError
P21CapacityFeasibilityError
P22MandateLegitimacyError
P23StakesFloorError
P24StrategicResponseError
P26ResponsibilityIntegrityError
ParetoArchive
ParticipationProvenanceRow
PhaseBarrierBlocker
PhaseBarrierId
PhaseBarrierLedger
PhaseBarrierRecord
PhaseBarrierStatus
PhaseBarrierViolation
PolicyBenchmarkingError
PolicyBenchmarkingIssue
PolicyBenchmarkingValidationResult
PolicyDesignCaseAuthorityError
PolicyDesignCaseIntegrityIssue
PolicyDesignCaseProjectionError
PolicyDesignCaseRecordApplicability
PolicyDesignCaseRecordFamily
PolicyDesignCaseRecordRegistryIssue
PolicyDesignCaseRecordRegistryValidationResult
PolicyDesignCaseSemanticEvaluationPack
PolicyDesignCaseSemanticGoldCardFixture
PolicyDesignLifecycleError
PolicyDesignLifecycleIssue
PolicyDesignObservabilityStaticAuditIssue
PolicyDesignPass1BHardeningError
PolicyDesignPass1BHardeningIssue
PostDeployAccountabilitySummary
PostDeployMapeKPhase
PostDeployMapeKTrace
PostInterventionDGPUpdate
PredictionAuthorityEnvelope
PredictiveAxis
PredictiveAxisCalibrationRecord
PredictiveAxisUpgradeRecord
PredictiveMaturity
ProducerHandshakeBinding
ProducerHandshakeValidationError
ProducerIdentity
ProducerPipelineBinding
ProducerPipelineProducer
ProducerSpineReadContext
ProducerWaitCondition
ProductionApprovalCurrentnessProjection
ProductionApprovalIssuanceInput
ProductionApprovalPacketResolver
ProductionApprovalResolutionError
ProjectionAlgebraRequest
ProjectionFaithfulnessRecord
ProjectionLoweringIntegrityReport
ProjectionRenderRecord
PromptToolParserAuthorityLedger
PromptToolParserAuthorityValidation
ProofCarryingAnalyticsRecord
ProofComposabilityStatus
ProofStatus
ProxyValidityDisposition
ProxyValidityRecord
PublicExportRedactionError
QualityScore
RankingMode
ReconciledConcept
RecordFamilyMaturity
RecursiveDesignGraph
RegimeEvidenceBasis
RelaxationDecision
RequirementGapFamily
RequirementTimeWindow
RequirementToCapabilityQuery
RequirementToCapabilityResolver
RerunClosureReceipt
ResourceAllocationPolicy
ResourceAuthorityDisposition
ResourceEconomicsAuthorityEnvelope
ResourceEconomicsIntegrityReport
ResponsibilityIntegrityCheck
ResponsibilityIntegrityStatus
Reversibility
RightsEnvelope
RunCostGateError
RunCostProportionalityError
RunIntentBinding
RunState
RunStateMachine
RunStateSnapshot
RunStateTransitionError
RuntimeDiagnosticEventLog
S11CalibrationStatus
S11PredictiveKnowledgeAuthorityEnvelope
S11PredictiveKnowledgeIntegrityReport
S12ResourceReferenceResolution
SameInputClosure
ScholarBindingRecord
SealedUniversalityBatteryRun
SemanticBindingEvaluation
SemanticBindingIssue
SemanticBindingLedger
SkepticDefeaterRecord
SourceAuthority
SourceContract
SourceDiscoveryCandidate
SourceFacetBinding
StakesBand
StrategicResponseChannel
StrategicResponseChannelAssessment
StrategicResponseDisposition
StrategicResponseRecord
SubstrateAcquisitionLoop
SubstrateCoverageSnapshot
SystemDynamicsRequirement
SystemEffectSupportLabel
ThermometerTrend
ThroughputRow
TypedBudgetRow
UniversalityAssuranceSummary
UniversalityAxisScoreRow
UniversalityAxisScorecard
UniversalityBaselineComparison
UniversalityBaselineRow
UniversalityBreadthFloorConfig
UniversalityClaimAssuranceCase
UniversalityClaimGateRecord
ValueChoiceIntegrityReport
ValueChoiceProvenanceRecord
ValueDisposition
ValueLossDisclosure
ValueOfInformationAllocation
ValueScheduleReviewStatus
ValueSourceClass
ValueTradeoffDisclosureRecord
VoiAllocationRow
VoiSite
WelfareComparisonRecord
WelfareComparisonStatus
WorldModelRecord
acquisition_planner_reports_from_quality_evidence
acquisition_planner_scorecard_gates
acquisition_report_deficit_records
acquisition_report_inputs
allocate_value_of_information
append_verified_lowering_artifact
assert_approval_readiness_projection_allowed
assert_authority_bearing
assert_authority_purpose_allowed
assert_barrier_closed
assert_barrier_passed
assert_canary_bundle_closeout_allowed
assert_candidate_positive_firewall_boundary
assert_capability_binding_purpose_allowed
assert_composition_laws_hold
assert_final_decision_artifact_allowed
assert_memory_influence_not_claim_evidence
assert_no_candidate_authority_laundering
assert_policy_design_projection_not_authority
assert_public_artifact_allowed
assert_public_export_official_use_limits
assert_runtime_emitted
assert_same_input_closure
assert_scenario_family_name_alone_does_not_grant_authority
assert_serious_fallback_allowed
assert_serious_mode_allowed
assert_stakes_floor_consistency
authority_envelope_json_schema
authority_envelopes_missing_semantic_binding_ref
best_in_class_benchmarking_record_id
build_argument_graph
build_argument_graph_quality_evidence_surfaces
build_assurance_case_delta
build_assurance_case_for_scorecard
build_authority_candidate_inventory_rows
build_authorized_value_schedule
build_berl_warrant_reliability_record
build_calibration_ledger
build_canary_performance_budget
build_canonical_design_record
build_capability_duty_record
build_capability_reality_report
build_capability_selection_ledger
build_case_lifecycle_record
build_case_maturity_profile
build_certified_envelope_delta
build_closeout_reader_skeleton
build_closeout_reader_skeleton_from_bundle_dir
build_commitment_profile
build_complexity_governance_report
build_composition_receipt
build_computational_tractability_budget
build_concept_spine_bridge_authority_record
build_cost_degradation_telemetry_from_quality_context
build_coupling_graph
build_d4_corpus_track_coverage
build_decision_rights_matrix
build_degradation_record
build_delegation_contract
build_deployment_dossier
build_design_record_maturity_report
build_diagnostic_slo_report
build_diagnostic_slo_report_from_quality_context
build_disconfirming_evidence_ledger
build_dormant_capability_inventory_record
build_envelope_growth_ledger
build_envelope_revision
build_envelope_revision_dynamics_record
build_evaluation_status_composition_record
build_evidence_independence_map
build_evidence_synthesis_report
build_ex_post_learning_record
build_expert_oracle_bootstrap_record
build_forecast_calibration_record
build_forecast_support
build_freshness_policy_time_semantics_record
build_governance_decision_class_registry
build_grounded_authority_coverage_record
build_growth_thermometers
build_human_decision_request
build_human_review_calibration_report
build_hybrid_concept_spine_carrier
build_hypothesis_ledger_from_prompt_tool_ledger
build_implementation_monitoring_evaluation_record
build_ir_analytics_claim_bridge
build_knowledge_governance_throughput_ledger
build_learning_update_proposal
build_legacy_migration_sandbox
build_mechanism_generality_report
build_memory_influence_record
build_multiverse_specification_curve_record
build_objective_function_provenance
build_pareto_archive
build_pass1b_tenant_cas_approval_governance_record
build_policy_design_case_concept_spine
build_policy_design_case_profile
build_policy_design_case_projection_contract_fixture
build_policy_design_case_projection_semantics
build_policy_design_case_record_registry_report
build_policy_design_case_registry_entry
build_policy_design_case_walking_skeleton
build_policy_design_jurisdiction_spine
build_policy_intent_envelope
build_post_deploy_mape_k_trace
build_pre_publication_challenge_node
build_pre_publication_challenge_node_from_scientist_outputs
build_prediction_authority_boundary
build_predictive_axis_calibration_record
build_predictive_axis_upgrade_record
build_producer_handshake_ledger
build_producer_handshake_record
build_producer_pipeline_quality_evidence_surfaces
build_producer_spine_read_context
build_production_approval_packet
build_production_data_quality_report
build_projection_algebra_request
build_projection_render_record
build_proof_carrying_analytics_record
build_public_audit_archive_record
build_public_export_bundle
build_quality_scorecard
build_replay_manifest
build_resolved_production_approval_packet
build_resource_allocation_policy
build_rule_evolution_registry
build_rule_evolution_replay_context
build_rule_replay_comparison_report
build_run_cost_gate_report
build_run_cost_proportionality_ledger_from_quality_context
build_s6_blind_spot_firewall_report
build_s11_predictive_authority_boundary
build_s11_predictive_knowledge_posture
build_s12_resource_authority_boundary
build_s12_resource_economics_posture
build_s13_accountability_authority_boundary
build_s13_post_deploy_accountability_posture
build_s14_cae_scorecard
build_s14_capability_reality_axis_rows
build_s14_mechanism_generality_from_growth_thermometer
build_s14_universality_assurance_projection
build_s14_universality_authority_boundary
build_semantic_binding_ledger
build_shadow_scenario_value_schedule
build_skeptic_defeater_records
build_skip_causality_ledger_record
build_soft_gate_telemetry_report
build_system_dynamics_requirement
build_system_effect_support
build_universality_assurance_case
build_universality_axis_scorecard
build_universality_baseline_comparison
build_universality_breadth_floor_config
build_universality_claim_assurance_case
build_value_choice_provenance_record
build_wave2_policy_design_case_walking_skeleton
build_welfare_comparison_record
calibration_influence_for_scope
calibration_ledger_public_export
candidate_firewall_issues_for_payload
candidate_refs_from_payload
capability_binding_purpose_blockers
classify_authority_role
classify_coupling
classify_post_deploy_divergence
classify_regime
coerce_social_weight_provenance_for_s8
comparison_failure_codes
compile_capability_index
complexity_governance_scorecard_gates
compose_capability_authority
compose_graded_outcome
composition_to_axis_positions
compute_net_mav
compute_sealed_battery_freeze_hash
construct_for_legacy_family
construct_refs_for_alias
construct_registry_concept_spine_entries
construct_registry_public_surface
cost_degradation_scorecard_gates
cost_gate_scorecard_gates
coupling_accuracy
create_capability_index_fixture_inputs
critical_path_regime
decompose_design
default_diagnostic_slo_targets
derive_recursive_design_graph
deserialize_authority_envelope
deserialize_degradation_record
deserialize_hypothesis_ledger
deserialize_semantic_binding_ledger
deterministic_review_fixtures
diagnostic_slo_gates
discover_design_modules
effective_independence_factor_for_capability
evaluate_aggregation_validity
evaluate_blocking_frontier_control
evaluate_capability_claim
evaluate_capacity_feasibility
evaluate_degradation_policy
evaluate_delegation_for_case
evaluate_mandate_legitimacy
evaluate_measurability_adequacy
evaluate_review_packet
evaluate_schema_compatibility
evaluate_semantic_binding_ledger
evaluate_semantic_evaluation_pack
evaluate_semantic_gold_card_fixture
evaluate_strategic_response
evaluation_safety_consumer_admission_is_verified
evidence_line_record_id
evidence_synthesis_refs_by_claim
explain_mode_mismatch
explain_replay_drift
export_argument_graph
export_claim_argument_case_mapping
gate_lowering_request
gate_universality_claim
graded_outcome_closeout_record
gy_content_hash
historical_prior_claim_evidence_issues
human_review_public_export
inspect_argument_graph
ir_analytics_bridge_issues_for_claims
ir_analytics_claim_bindings_by_claim
is_historical_prior_ref
is_memory_influence_ref
is_production_claim_admissible
legacy_compatible_payload
legacy_family_for_construct
load_acquisition_planner_report
load_construct_registry
logic_hash_for_rule
max_admissible_posture
memory_influence_claim_evidence_issues
merge_argument_graph_quality_evidence_surfaces
merge_ir_analytics_binding_into_registry_entry
merge_producer_pipeline_quality_evidence_surfaces
mode_policy_failure_code
non_ukraine_bound_constructs
normalize_ir_analytics_claim_bridge
normalize_quality_evidence
normalize_runtime_privacy_compliance_report
pass1b_tenant_cas_approval_governance_issues
persist_acquisition_planner_report
persist_argument_graph
persist_calibration_ledger
persist_drift_explanation
persist_human_review_calibration_report
persist_hypothesis_ledger
persist_legacy_migration_sandbox_report
persist_production_approval_packet
persist_projection_lowering_bundle
persist_prompt_tool_ledger
persist_replay_manifest
persist_rule_evolution_registry
persist_rule_replay_comparison_report
persist_value_choice_provenance_bundle
persist_wave2_policy_design_case_walking_skeleton
plan_evidence_acquisition
plan_requirement_gap_acquisition
policy_design_case_maturity_scorecard_gates
policy_design_case_record_registry_payload
policy_design_case_record_registry_scorecard_gates
policy_design_concept_spine_json_schema
policy_design_jurisdiction_spine_json_schema
policy_design_pass1b_hardening_scorecard_gates
producer_spine_read_context_for
project_cae_defeaters_to_s14_skeptic_records
project_value_tradeoff_disclosure
public_rule_evolution_annotation
ratchet_templates
reader_schema_ranges
reconcile_authority_event
reconcile_authority_ref
record_human_decision
regime_accuracy
regime_claim_to_axis_position
regime_design_strategy
replay_under_new_rules
replay_under_original_rules
requirement_gaps_from_compiled_specs
resolve_evaluation_mode
resolve_expression
resolve_s12_resource_refs
review_controls_for_pruning
run_cost_budget_policy_from_performance_budget
run_cost_ledger_record_id
run_eight_stage_producer_pipeline
run_requirement_spec_producer_pipeline
s6_fail_closed_coverage
s6_firewall_report_to_axis_positions
s6_firewall_report_to_c3_dimension_records
s6_firewall_report_to_constraint_store_updates
s7_delegation_integrity
s8_value_provenance_integrity
s9_projection_lowering_integrity
select_floor
semantic_evaluation_pack_json_schema
semantic_gold_card_json_schema
serialize_authority_envelope
serialize_degradation_record
serialize_hypothesis_ledger
severity_for_points
skip_blocker_gate_from_payloads
summarize_forecast_support_integrity
summarize_post_deploy_accountability
summarize_resource_economics_integrity
summarize_s11_predictive_knowledge_integrity
summarize_universality_assurance
synthesis_report_record_id
validate_capability_authority
validate_capability_selection_ledger
validate_case_lifecycle_record
validate_case_maturity_profile
validate_claim_argument_case_surfaces
validate_config_release_deployment_migration_hardening_record
validate_construct_registry_coverage
validate_cost_degradation_telemetry
validate_disconfirming_evidence_ledger_record
validate_evidence_graph_threat_model_record
validate_evidence_independence_map_record
validate_evidence_line_record
validate_evidence_line_records
validate_evidence_synthesis_report_record
validate_ex_post_learning_record
validate_hybrid_concept_spine_carrier
validate_implementation_monitoring_evaluation_record
validate_multiverse_specification_curve_record
validate_obligation_rule_construct_refs
validate_observability_orchestration_static_audit_records
validate_pass1b_tenant_cas_approval_governance_record
validate_policy_benchmarking_record
validate_policy_design_best_in_class_benchmarking_records
validate_policy_design_case_concept_spine
validate_policy_design_case_profile
validate_policy_design_case_record_registry_payload
validate_policy_design_jurisdiction_spine
validate_policy_design_lifecycle_records
validate_policy_evidence_capability_replay_refs
validate_policy_intent_envelope
validate_prompt_tool_parser_authority
validate_public_audit_archive_record
validate_run_cost_gate_report
validate_run_cost_proportionality_blocker
validate_run_cost_proportionality_ledger
verify_policy_design_case_projection_consumer_contract
verify_post_deploy_learning_authority
verify_prediction_authority_envelope
verify_projection_faithfulness
verify_resource_authority_envelope
verify_s9_projection_faithfulness_for_pdc_consumer_contract
verify_s10_forecast_projection_consumer_contract
verify_s11_predictive_knowledge_authority_envelope
verify_sealed_battery_integrity
verify_universality_claim_authority
warning_lifecycle_summaries
world_model_record_content_hash
write_authority_envelope_json_schema
```

</details>

<details><summary>Supported exports (965)</summary>

```text
ACQUISITION_PLANNER_GATE_LAYER
ACQUISITION_PLANNER_GATE_PHASE
ACQUISITION_PLANNER_KIND
ACQUISITION_PLANNER_REPORT_KEY
ACQUISITION_PLANNER_SCHEMA_NAME
ACQUISITION_PLANNER_SCHEMA_VERSION
ACQUISITION_STRATEGY_SCHEMA_VERSION
ARGUMENT_GRAPH_CONTRACT_ID
ARGUMENT_GRAPH_EXPORT_SCHEMA_VERSION
ARGUMENT_GRAPH_INSPECTION_SCHEMA_VERSION
ARGUMENT_GRAPH_KIND
ARGUMENT_GRAPH_SCHEMA_VERSION
AUTHORITY_CANDIDATE_FIREWALL_NAME
AUTHORITY_FACTOR_NAMES
C33_RULE_CHANGE_CLASS_TABLE
CALIBRATION_LEDGER_CONTRACT_ID
CALIBRATION_LEDGER_KIND
CALIBRATION_LEDGER_SCHEMA_VERSION
CAPABILITY_AUTHORITY_RULE_VERSION
CAPABILITY_AUTHORITY_SCHEMA_VERSION
CAPABILITY_FAILURE_MODE_SCHEMA_VERSION
CAPABILITY_INDEX_COMPILER_VERSION
CAPABILITY_INDEX_SCHEMA_VERSION
CAPABILITY_RATCHET_CONTRACT_ID
CAPABILITY_RATCHET_SCHEMA_VERSION
CAPABILITY_SOURCE_ASSET_SCHEMA_VERSION
CASE_LIFECYCLE_CONTRACT_ID
CASE_LIFECYCLE_SCHEMA_VERSION
CASE_MATURITY_PROFILE_RECORD_FAMILY
CASE_MATURITY_PROFILE_RECORD_KEY
CASE_MATURITY_PROFILE_SCHEMA_VERSION
CASE_MATURITY_PROFILE_SCORECARD_GATE
CLAIM_ARGUMENT_CONTRACT_ID
CLAIM_ARGUMENT_MAPPING_SCHEMA_VERSION
CLAIM_ARGUMENT_NODE_MAPPING
CLAIM_ARGUMENT_VALIDATION_SCHEMA_VERSION
CLAIM_EVIDENCE_SLOT_KEYS
CLOSEOUT_READER_CONTRACT_ID
CLOSEOUT_READER_CONTRACT_VERSION
CLOSEOUT_READER_SCHEMA_VERSION
COMMITMENT_PROFILE_SCHEMA_VERSION
COMPLEXITY_GOVERNANCE_CONTRACT_ID
COMPLEXITY_GOVERNANCE_CONTROL_ID
COMPLEXITY_GOVERNANCE_FILENAME
COMPLEXITY_GOVERNANCE_REPORT_KEY
COMPLEXITY_GOVERNANCE_SCHEMA_VERSION
CONCEPT_SPINE_BRIDGE_AUTHORITY_SCHEMA_VERSION
CONCEPT_SPINE_HANDSHAKE_LEDGER_SCHEMA_VERSION
CONCEPT_SPINE_HANDSHAKE_RECORD_SCHEMA_VERSION
CONCEPT_SPINE_HYBRID_CARRIER_SCHEMA_VERSION
CONFIG_RELEASE_HARDENING_CONTRACT_ID
CONFIG_RELEASE_HARDENING_PDD_IDS
CONFIG_RELEASE_HARDENING_RECORD_FAMILY
CONFIG_RELEASE_HARDENING_SCHEMA_VERSION
CONFLICT_RECORD_SCHEMA_VERSION
CONSTRUCT_REGISTRY_DEFAULT_PATH
CONSTRUCT_REGISTRY_ID
CONSTRUCT_REGISTRY_RULE_VERSION
CONSTRUCT_REGISTRY_SCHEMA_VERSION
CONSTRUCT_REGISTRY_VERSION
CORE_FORBIDDEN_CURRENT_USES
COST_DEGRADATION_TELEMETRY_CONTRACT_ID
COST_DEGRADATION_TELEMETRY_FILENAME
COST_DEGRADATION_TELEMETRY_REPORT_KEY
COST_DEGRADATION_TELEMETRY_SCHEMA_VERSION
DDM_EVENT_GROUPS
DEFAULT_CAPABILITY_INDEX_REF
DEFAULT_CLOSEOUT_MODULE_READERS
DEFAULT_SOFT_GATE_ESCALATION_SECONDS
DEFAULT_SOFT_GATE_TTL_SECONDS
DESIGN_PROBLEM_SCHEMA_VERSION
DISCONFIRMING_EVIDENCE_LEDGER_CONTRACT_ID
DISCONFIRMING_EVIDENCE_LEDGER_SCHEMA_VERSION
DORMANT_CAPABILITY_INVENTORY_RECORD_KEY
DORMANT_CAPABILITY_INVENTORY_SCHEMA_VERSION
EVIDENCE_CAPABILITY_SCHEMA_VERSION
EVIDENCE_GRAPH_THREATS
EVIDENCE_GRAPH_THREAT_MODEL_RECORD_FAMILY
EVIDENCE_GRAPH_THREAT_MODEL_RECORD_KEY
EVIDENCE_GRAPH_THREAT_MODEL_SCHEMA_VERSION
EVIDENCE_LINE_CONTRACT_ID
EVIDENCE_LINE_SCHEMA_VERSION
EVIDENCE_SYNTHESIS_REPORT_CONTRACT_ID
EVIDENCE_SYNTHESIS_REPORT_SCHEMA_VERSION
EXTERNAL_AUDIT_RECORD_FAMILY
EXTERNAL_AUDIT_RECORD_SCHEMA_VERSION
EX_POST_LEARNING_CONTRACT_ID
EX_POST_LEARNING_SCHEMA_VERSION
FRESHNESS_POLICY_TIME_SEMANTICS_RECORD_KEY
FRESHNESS_POLICY_TIME_SEMANTICS_SCHEMA_VERSION
FULL_MODE_CAPABILITY_FLOORS
GRADED_INDEPENDENCE_FEATURE_FLAG
HIGH_COST_LOW_IMPACT_COST_USD
HIGH_COST_LOW_IMPACT_ELAPSED_SECONDS
HIGH_COST_LOW_IMPACT_REVIEW_HOURS
HISTORICAL_PRIOR_INFLUENCE_SCHEMA_VERSION
HYPOTHESIS_LEDGER_FILENAME
HYPOTHESIS_LEDGER_KIND
HYPOTHESIS_LEDGER_REF_KEY
HYPOTHESIS_LEDGER_REPORT_KEY
HYPOTHESIS_LEDGER_SCHEMA_VERSION
IMPLEMENTATION_MONITORING_EVALUATION_CONTRACT_ID
IMPLEMENTATION_MONITORING_EVALUATION_SCHEMA_VERSION
INDEPENDENCE_MAP_CONTRACT_ID
INDEPENDENCE_MAP_SCHEMA_VERSION
IR_ANALYTICS_CLAIM_BRIDGE_KIND
IR_ANALYTICS_CLAIM_BRIDGE_REF_KEY
IR_ANALYTICS_CLAIM_BRIDGE_SCHEMA_VERSION
LAYER2_S3_SUBSTRATE_ACQUISITION_SCHEMA_VERSION
LAYER2_S4_EPISTEMIC_REGIME_SCHEMA_VERSION
LAYER2_S5_COUPLING_COMPOSITION_SCHEMA_VERSION
LAYER2_S6_BLIND_SPOT_FIREWALLS_SCHEMA_VERSION
LAYER2_S7_DELEGATION_SCHEMA_VERSION
LAYER2_S8_VALUE_CHOICE_RULE_VERSION
LAYER2_S8_VALUE_CHOICE_SCHEMA_VERSION
LAYER2_S9_PROJECTION_LOWERING_RULE_VERSION
LAYER2_S9_PROJECTION_LOWERING_SCHEMA_VERSION
LAYER2_S10_OUTCOME_PREDICTION_RULE_VERSION
LAYER2_S10_OUTCOME_PREDICTION_SCHEMA_VERSION
LAYER2_S11_PREDICTIVE_KNOWLEDGE_RULE_VERSION
LAYER2_S11_PREDICTIVE_KNOWLEDGE_SCHEMA_VERSION
LAYER2_S12_RESOURCE_ECONOMICS_RULE_VERSION
LAYER2_S12_RESOURCE_ECONOMICS_SCHEMA_VERSION
LAYER2_S13_POST_DEPLOY_ACCOUNTABILITY_RULE_VERSION
LAYER2_S13_POST_DEPLOY_ACCOUNTABILITY_SCHEMA_VERSION
LAYER2_S14_UNIVERSALITY_ASSURANCE_RULE_VERSION
LAYER2_S14_UNIVERSALITY_ASSURANCE_SCHEMA_VERSION
LEGACY_MIGRATION_SEMANTIC_LOSS
MEMORY_INFLUENCE_ADR_REF
MEMORY_INFLUENCE_RECORD_KIND
MEMORY_INFLUENCE_REF_PREFIXES
MEMORY_INFLUENCE_SCHEMA_VERSION
MISSING_REALITY_STATES
MULTIVERSE_SPECIFICATION_CURVE_CONTRACT_ID
MULTIVERSE_SPECIFICATION_CURVE_SCHEMA_VERSION
NET_MAV_FORMULA
PASS1B_HARDENING_READINESS_CHECK
PASS1B_HARDENING_SCORECARD_GATE
PASS1B_PDD_REQUIRED_SURFACES
PASS1B_REQUIRED_CASE_BINDING_FIELDS
PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_CONTRACT_ID
PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_PDDS
PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_RECORD_KEY
PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_SCHEMA_VERSION
PERFORMANCE_BUDGET_SECONDS
POLICY_BENCHMARKING_RECORD_CONTRACT_ID
POLICY_BENCHMARKING_RECORD_FAMILY
POLICY_BENCHMARKING_RECORD_SCHEMA_VERSION
POLICY_DESIGN_CAPABILITY_DUTY_STATES
POLICY_DESIGN_CAPABILITY_LEDGER_SCHEMA_VERSION
POLICY_DESIGN_CASE_CORE_NODE_TYPES
POLICY_DESIGN_CASE_MINIMUM_RECORD_FAMILIES
POLICY_DESIGN_CASE_OWNER
POLICY_DESIGN_CASE_PROFILE
POLICY_DESIGN_CASE_PROFILE_METADATA
POLICY_DESIGN_CASE_PROJECTION_SCHEMA_VERSION
POLICY_DESIGN_CASE_REGISTRY_ENTRY_SCHEMA_VERSION
POLICY_DESIGN_CASE_RESERVED_NODE_FAMILIES
POLICY_DESIGN_CASE_SCHEMA_VERSION
POLICY_DESIGN_CONCEPT_SPINE_CONTRACT_ID
POLICY_DESIGN_CONCEPT_SPINE_REQUIRED_CLOSURE_FIELDS
POLICY_DESIGN_CONCEPT_SPINE_SCHEMA_VERSION
POLICY_DESIGN_JURISDICTION_AUTHORITY_LEVELS
POLICY_DESIGN_JURISDICTION_SPINE_SCHEMA_VERSION
POLICY_DESIGN_REQUIRED_CAPABILITIES
POLICY_DESIGN_WALKING_SKELETON_CONTRACT_ID
POLICY_DESIGN_WALKING_SKELETON_SCHEMA_VERSION
POLICY_EVIDENCE_CAPABILITY_REPLAY_REF_KEYS
POLICY_EVIDENCE_CAPABILITY_REPLAY_REF_SCHEMA_VERSION
POLICY_INTENT_ENVELOPE_SCHEMA_VERSION
POSTURE_THRESHOLDS
PRE_PUBLICATION_CHALLENGE_NODE_SCHEMA_VERSION
PRODUCER_PIPELINE_FEATURE_FLAG
PRODUCER_PIPELINE_SCHEMA_VERSION
PRODUCER_SPINE_CONSUMER_COMPONENTS
PRODUCER_SPINE_CONTEXT_SCHEMA_VERSION
PROJECTION_STATES
PURPOSE_MULTIPLIERS
REALITY_STATES
REALITY_STATE_BASE_POINTS
RECORD_FAMILY_MATURITY_LEVELS
RECORD_REGISTRY_READINESS_CHECK
RECORD_REGISTRY_SCHEMA_VERSION
REQUIRED_MULTIVERSE_SOURCE_KINDS
REQUIRED_POLICY_BENCHMARK_METRICS
REQUIREMENT_TO_CAPABILITY_QUERY_SCHEMA_VERSION
REQUIREMENT_TO_CAPABILITY_RESOLVER_RULE_VERSION
RULE_EVOLUTION_CONTRACT_ID
RULE_EVOLUTION_PUBLIC_ANNOTATION_SCHEMA_VERSION
RULE_EVOLUTION_RECORD_FAMILY
RULE_EVOLUTION_REGISTRY_KIND
RULE_EVOLUTION_REGISTRY_SCHEMA_VERSION
RULE_EVOLUTION_REPLAY_SCHEMA_VERSION
RULE_REPLAY_COMPARISON_SCHEMA_VERSION
RULE_REPLAY_EXECUTION_SCHEMA_VERSION
RULE_REPLAY_PUBLIC_REPORT_SCHEMA_VERSION
RUN_COST_GATE_CONTRACT_ID
RUN_COST_GATE_FILENAME
RUN_COST_GATE_REPORT_KEY
RUN_COST_GATE_SCHEMA_VERSION
RUN_COST_PROPORTIONALITY_LEDGER_CONTRACT_ID
RUN_COST_PROPORTIONALITY_LEDGER_SCHEMA_VERSION
S1_GRADED_OUTCOME_SCHEMA_VERSION
S8_VALUE_CHOICE_CELL_REF
S8_VALUE_CHOICE_FLOOR_ID
S9_PROJECTION_FLOOR_ID
S10_CALIBRATION_FLOOR_ID
S10_FALSE_CLEAR_FIELDS
S11_AXIS_CALIBRATION_FLOOR_ID
S11_FALSE_CLEAR_FIELDS
S11_PREDICTIVE_AXES
S12_FALSE_CLEAR_FIELDS
S12_GROWTH_THERMOMETERS_FLOOR_ID
S12_TYPED_BUDGETS
S12_VOI_SITES
S13_ACCOUNTABILITY_FLOOR_ID
S13_FALSE_CLEAR_FIELDS
S14_FALSE_CLEAR_FIELDS
S14_SKEPTIC_DEFEATER_IDS
S14_UNIVERSALITY_FLOOR_ID
SEMANTIC_BINDING_SCHEMA_VERSION
SEMANTIC_EVALUATION_PACK_CONTRACT_ID
SEMANTIC_EVALUATION_PACK_SCHEMA_VERSION
SEMANTIC_GOLD_CARD_CONTRACT_ID
SEMANTIC_GOLD_CARD_SCHEMA_VERSION
SKIP_CAUSALITY_LEDGER_RECORD_KEY
SKIP_CAUSALITY_LEDGER_SCHEMA_VERSION
SOFT_GATE_TELEMETRY_SCHEMA_VERSION
SUPPORTED_EVIDENCE_LINE_STRANDS
WAVE2_I2_MANIFEST_SCHEMA_VERSION
WAVE2_I2_SCHEMA_VERSION
AcquisitionActionRecord
AcquisitionDisposition
AcquisitionGap
AcquisitionGapType
AcquisitionNextAction
AcquisitionPlannerReport
AcquisitionRequirementGap
AcquisitionState
AcquisitionStrategy
AcquisitionStrategyRecord
AcquisitionTaskRecord
ActionItemStatus
AggregationClaimLevel
AggregationScopeRow
AggregationValidityDisposition
AggregationValidityRecord
AllocationPriorityRow
ArgumentGraphError
AssuranceCaseChange
AssuranceCaseDelta
AttributionStatus
AuthorityCandidateInventoryRow
AuthorityEnvelope
AuthorityEnvelopeError
AuthorityEnvelopeViolation
AuthorityLevel
AuthorityProfile
AuthorityReconciliationError
AuthorityReconciliationReport
AuthorizedValueSchedule
AxisFailClosedDisposition
BlindSpotAxis
BlindSpotBridgeConsumerRecord
BlindSpotConstraintStoreUpdate
BlindSpotFirewallReport
BlindSpotOverallPosture
BoundaryCouplingClassification
BudgetKind
CalibrationHistoryPolicy
CalibrationLedger
CalibrationLedgerContractError
CalibrationLedgerEntry
CandidateAuthorityEnvelope
CandidateFirewallError
CandidateLever
CandidateLeverSpace
CanonicalDesignRecord
CapabilityAuthorityError
CapabilityAuthorityFactor
CapabilityAuthorityFactorName
CapabilityBindingResult
CapabilityBindingStatus
CapabilityConflictRecord
CapabilityIndependenceFactor
CapabilityIndex
CapabilityIndexAcquisitionStrategy
CapabilityIndexBuildResult
CapabilityIndexCompilerConfig
CapabilityLifecycle
CapabilityScope
CapabilitySourceAsset
CapacityBuildingObligation
CapacityDimension
CapacityDimensionAssessment
CapacityDisposition
CapacityFeasibilityRecord
CaseMaturityIssue
CaseMaturityValidationResult
CertifiedEnvelopeDelta
ClaimArgumentIssue
ClaimArgumentValidationResult
ClaimBindingRecord
CloseoutModuleReaderSpec
ClusterAuthorityDimensionRecord
ColumnBinding
CommitmentProfileRecord
ComplexityGovernanceError
CompositionAuthorityMode
CompositionDisposition
CompositionLawCheck
CompositionReceipt
ComputationalTractabilityBudget
ConceptNamespaceRef
ConceptRelation
ConfigReleaseHardeningIssue
ConstraintRefinementRoute
ConstraintStatus
ConstructAliasDeprecation
ConstructAuthorityRequirement
ConstructCompatibilityAlias
ConstructCorpusBinding
ConstructDemandLedger
ConstructEntry
ConstructExpression
ConstructMeasurabilityRow
ConstructMeasurabilityStatus
ConstructRegistry
ConstructRegistryError
ConstructValidityRequirements
CostDegradationTelemetryError
CouplingEdge
CouplingGraph
CouplingRegime
CouplingRegimeClassification
CoverageBinding
D4CorpusTrackCoverage
D4CorpusTrackRow
DecisionAction
DecisionNeedReason
DecisionOption
DecisionRightsMatrix
DecisionRightsMatrixRow
DecisionRole
DecompositionResult
DegradationLedgerContractError
DegradationLedgerRecord
DegradationPolicyDecision
DelegationContract
DelegationDisposition
DelegationIntegrityReport
DelegationInteractionMode
DelegationNegativeControlResult
DelegationReferenceClass
DeploymentDossier
DeploymentReadinessDisposition
DerivedFeatureBinding
DesignConstraint
DesignInterfaceContract
DesignObjective
DesignProblem
DesignProblemAuthorityError
DesignRecordMaturityReport
DesignStakeholder
DesignStrategy
DiagnosticEventPayloadPolicy
DisconfirmingEvidenceLedgerError
DivergenceAttributionClass
DivergenceRecord
DynamicsRequirementLevel
EffectiveModeLedger
EnvelopeGrowthEntry
EnvelopeGrowthLedger
EnvelopeRevision
EnvelopeRevisionDirection
EnvelopeRevisionDynamicsRecord
EpistemicRegimeClaim
EvalSafetyAdmissionChallenge
EvalSafetyVerifierPort
EvaluationExecutionContext
EvaluationStatusCompositionRecord
EvaluationStatusCompositionRow
EvidenceAcquisitionNeeds
EvidenceAuthorityEnvelope
EvidenceCapability
EvidenceIndependenceError
EvidenceLineError
EvidenceNeed
EvidenceSynthesisReportError
ExpertOracleBootstrapRecord
ExpertOracleLayerRow
ExploreExploitPosture
ExternalAuditRecordError
FabricBindingRecord
FailureModeNode
FeedbackIntensity
FirewallStatus
FiveRightsCheck
FiveRightsDimension
FiveRightsRequirement
FloorBand
ForecastAuthorityDisposition
ForecastCalibrationRecord
ForecastClaimScope
ForecastMethodFamily
ForecastQualityDisposition
ForecastSupport
ForecastSupportBaseOrigin
ForecastSupportIntegrityReport
ForecastSupportScope
FoundryBindingRecord
FreshnessEnvelope
FrozenClosedCase
GovernanceMetadata
GradedOutcomeDecision
GradedOutcomeEvidenceInput
GradedOutcomeInputError
GroundedAuthorityCoverageRecord
GrowthCountingDisposition
GrowthThermometerRecord
HumanDecisionRecord
HumanDecisionRequest
HypothesisLedger
HypothesisLedgerEntry
IRAnalyticsClaimBinding
ImplementationMonitoringEvaluationError
IntentBindingRecord
InteractionStrength
JurisdictionTimeSemantics
KnowledgeGovernanceMode
KnowledgeGovernanceThroughputLedger
LearningChangeControlClass
LearningUpdateProposal
LearningUpdateTarget
LegitimacyDisposition
LexBindingRecord
LifecycleReissueDisposition
LifecycleStage
LoweringAppendReceipt
LoweringArtifactRecord
LoweringAuthorityGateRecord
LoweringRequestRecord
MandateBasis
MandateLegitimacyRecord
MandateSourceRecord
MandatoryGateState
MeasurabilityAdequacyRecord
MechanismGeneralityReport
MemoryInfluenceRecord
MetricBinding
ModePolicyError
ModePolicyViolation
ModuleDiscoveryResult
MultiverseSpecificationCurveError
NLProvenance
ObjectiveFunctionProvenanceRecord
ObservableSubsetCalibrationStatus
OutcomeDistributionRecord
OutcomeOfInterest
OversightLinkedAccountabilityState
P16OverconfidenceError
P16PrecautionLaunderingError
P17BoundarySpoofError
P17FalseModularityError
P17SyntacticCompositionError
P17SystemDynamicsRequiredError
P18StreetlightMeasurabilityError
P19AggregationLaunderingError
P20NormativeChoiceError
P21CapacityFeasibilityError
P22MandateLegitimacyError
P23StakesFloorError
P24StrategicResponseError
P26ResponsibilityIntegrityError
ParetoArchive
ParticipationProvenanceRow
PhaseBarrierBlocker
PhaseBarrierId
PhaseBarrierLedger
PhaseBarrierRecord
PhaseBarrierStatus
PhaseBarrierViolation
PolicyBenchmarkingError
PolicyBenchmarkingIssue
PolicyBenchmarkingValidationResult
PolicyDesignCaseAuthorityError
PolicyDesignCaseIntegrityIssue
PolicyDesignCaseProjectionError
PolicyDesignCaseRecordApplicability
PolicyDesignCaseRecordFamily
PolicyDesignCaseRecordRegistryIssue
PolicyDesignCaseRecordRegistryValidationResult
PolicyDesignCaseSemanticEvaluationPack
PolicyDesignCaseSemanticGoldCardFixture
PolicyDesignLifecycleError
PolicyDesignLifecycleIssue
PolicyDesignObservabilityStaticAuditIssue
PolicyDesignPass1BHardeningError
PolicyDesignPass1BHardeningIssue
PostDeployAccountabilitySummary
PostDeployMapeKPhase
PostDeployMapeKTrace
PostInterventionDGPUpdate
PredictionAuthorityEnvelope
PredictiveAxis
PredictiveAxisCalibrationRecord
PredictiveAxisUpgradeRecord
PredictiveMaturity
ProducerHandshakeBinding
ProducerHandshakeValidationError
ProducerIdentity
ProducerPipelineBinding
ProducerPipelineProducer
ProducerSpineReadContext
ProducerWaitCondition
ProductionApprovalCurrentnessProjection
ProductionApprovalIssuanceInput
ProductionApprovalPacketResolver
ProductionApprovalResolutionError
ProjectionAlgebraRequest
ProjectionFaithfulnessRecord
ProjectionLoweringIntegrityReport
ProjectionRenderRecord
PromptToolParserAuthorityLedger
PromptToolParserAuthorityValidation
ProofCarryingAnalyticsRecord
ProofComposabilityStatus
ProofStatus
ProxyValidityDisposition
ProxyValidityRecord
PublicExportRedactionError
QualityScore
RankingMode
ReconciledConcept
RecordFamilyMaturity
RecursiveDesignGraph
RegimeEvidenceBasis
RelaxationDecision
RequirementGapFamily
RequirementTimeWindow
RequirementToCapabilityQuery
RequirementToCapabilityResolver
RerunClosureReceipt
ResourceAllocationPolicy
ResourceAuthorityDisposition
ResourceEconomicsAuthorityEnvelope
ResourceEconomicsIntegrityReport
ResponsibilityIntegrityCheck
ResponsibilityIntegrityStatus
Reversibility
RightsEnvelope
RunCostGateError
RunCostProportionalityError
RunIntentBinding
RunState
RunStateMachine
RunStateSnapshot
RunStateTransitionError
RuntimeDiagnosticEventLog
S11CalibrationStatus
S11PredictiveKnowledgeAuthorityEnvelope
S11PredictiveKnowledgeIntegrityReport
S12ResourceReferenceResolution
SameInputClosure
ScholarBindingRecord
SealedUniversalityBatteryRun
SemanticBindingEvaluation
SemanticBindingIssue
SemanticBindingLedger
SkepticDefeaterRecord
SourceAuthority
SourceContract
SourceDiscoveryCandidate
SourceFacetBinding
StakesBand
StrategicResponseChannel
StrategicResponseChannelAssessment
StrategicResponseDisposition
StrategicResponseRecord
SubstrateAcquisitionLoop
SubstrateCoverageSnapshot
SystemDynamicsRequirement
SystemEffectSupportLabel
ThermometerTrend
ThroughputRow
TypedBudgetRow
UniversalityAssuranceSummary
UniversalityAxisScoreRow
UniversalityAxisScorecard
UniversalityBaselineComparison
UniversalityBaselineRow
UniversalityBreadthFloorConfig
UniversalityClaimAssuranceCase
UniversalityClaimGateRecord
ValueChoiceIntegrityReport
ValueChoiceProvenanceRecord
ValueDisposition
ValueLossDisclosure
ValueOfInformationAllocation
ValueScheduleReviewStatus
ValueSourceClass
ValueTradeoffDisclosureRecord
VoiAllocationRow
VoiSite
WelfareComparisonRecord
WelfareComparisonStatus
WorldModelRecord
acquisition_planner_reports_from_quality_evidence
acquisition_planner_scorecard_gates
acquisition_report_deficit_records
acquisition_report_inputs
allocate_value_of_information
append_verified_lowering_artifact
assert_approval_readiness_projection_allowed
assert_authority_bearing
assert_authority_purpose_allowed
assert_barrier_closed
assert_barrier_passed
assert_canary_bundle_closeout_allowed
assert_candidate_positive_firewall_boundary
assert_capability_binding_purpose_allowed
assert_composition_laws_hold
assert_final_decision_artifact_allowed
assert_memory_influence_not_claim_evidence
assert_no_candidate_authority_laundering
assert_policy_design_projection_not_authority
assert_public_artifact_allowed
assert_public_export_official_use_limits
assert_runtime_emitted
assert_same_input_closure
assert_scenario_family_name_alone_does_not_grant_authority
assert_serious_fallback_allowed
assert_serious_mode_allowed
assert_stakes_floor_consistency
authority_envelope_json_schema
authority_envelopes_missing_semantic_binding_ref
best_in_class_benchmarking_record_id
build_argument_graph
build_argument_graph_quality_evidence_surfaces
build_assurance_case_delta
build_assurance_case_for_scorecard
build_authority_candidate_inventory_rows
build_authorized_value_schedule
build_berl_warrant_reliability_record
build_calibration_ledger
build_canary_performance_budget
build_canonical_design_record
build_capability_duty_record
build_capability_reality_report
build_capability_selection_ledger
build_case_lifecycle_record
build_case_maturity_profile
build_certified_envelope_delta
build_closeout_reader_skeleton
build_closeout_reader_skeleton_from_bundle_dir
build_commitment_profile
build_complexity_governance_report
build_composition_receipt
build_computational_tractability_budget
build_concept_spine_bridge_authority_record
build_cost_degradation_telemetry_from_quality_context
build_coupling_graph
build_d4_corpus_track_coverage
build_decision_rights_matrix
build_degradation_record
build_delegation_contract
build_deployment_dossier
build_design_record_maturity_report
build_diagnostic_slo_report
build_diagnostic_slo_report_from_quality_context
build_disconfirming_evidence_ledger
build_dormant_capability_inventory_record
build_envelope_growth_ledger
build_envelope_revision
build_envelope_revision_dynamics_record
build_evaluation_status_composition_record
build_evidence_independence_map
build_evidence_synthesis_report
build_ex_post_learning_record
build_expert_oracle_bootstrap_record
build_forecast_calibration_record
build_forecast_support
build_freshness_policy_time_semantics_record
build_governance_decision_class_registry
build_grounded_authority_coverage_record
build_growth_thermometers
build_human_decision_request
build_human_review_calibration_report
build_hybrid_concept_spine_carrier
build_hypothesis_ledger_from_prompt_tool_ledger
build_implementation_monitoring_evaluation_record
build_ir_analytics_claim_bridge
build_knowledge_governance_throughput_ledger
build_learning_update_proposal
build_legacy_migration_sandbox
build_mechanism_generality_report
build_memory_influence_record
build_multiverse_specification_curve_record
build_objective_function_provenance
build_pareto_archive
build_pass1b_tenant_cas_approval_governance_record
build_policy_design_case_concept_spine
build_policy_design_case_profile
build_policy_design_case_projection_contract_fixture
build_policy_design_case_projection_semantics
build_policy_design_case_record_registry_report
build_policy_design_case_registry_entry
build_policy_design_case_walking_skeleton
build_policy_design_jurisdiction_spine
build_policy_intent_envelope
build_post_deploy_mape_k_trace
build_pre_publication_challenge_node
build_pre_publication_challenge_node_from_scientist_outputs
build_prediction_authority_boundary
build_predictive_axis_calibration_record
build_predictive_axis_upgrade_record
build_producer_handshake_ledger
build_producer_handshake_record
build_producer_pipeline_quality_evidence_surfaces
build_producer_spine_read_context
build_production_approval_packet
build_production_data_quality_report
build_projection_algebra_request
build_projection_render_record
build_proof_carrying_analytics_record
build_public_audit_archive_record
build_public_export_bundle
build_quality_scorecard
build_replay_manifest
build_resolved_production_approval_packet
build_resource_allocation_policy
build_rule_evolution_registry
build_rule_evolution_replay_context
build_rule_replay_comparison_report
build_run_cost_gate_report
build_run_cost_proportionality_ledger_from_quality_context
build_s6_blind_spot_firewall_report
build_s11_predictive_authority_boundary
build_s11_predictive_knowledge_posture
build_s12_resource_authority_boundary
build_s12_resource_economics_posture
build_s13_accountability_authority_boundary
build_s13_post_deploy_accountability_posture
build_s14_cae_scorecard
build_s14_capability_reality_axis_rows
build_s14_mechanism_generality_from_growth_thermometer
build_s14_universality_assurance_projection
build_s14_universality_authority_boundary
build_semantic_binding_ledger
build_shadow_scenario_value_schedule
build_skeptic_defeater_records
build_skip_causality_ledger_record
build_soft_gate_telemetry_report
build_system_dynamics_requirement
build_system_effect_support
build_universality_assurance_case
build_universality_axis_scorecard
build_universality_baseline_comparison
build_universality_breadth_floor_config
build_universality_claim_assurance_case
build_value_choice_provenance_record
build_wave2_policy_design_case_walking_skeleton
build_welfare_comparison_record
calibration_influence_for_scope
calibration_ledger_public_export
candidate_firewall_issues_for_payload
candidate_refs_from_payload
capability_binding_purpose_blockers
classify_authority_role
classify_coupling
classify_post_deploy_divergence
classify_regime
coerce_social_weight_provenance_for_s8
comparison_failure_codes
compile_capability_index
complexity_governance_scorecard_gates
compose_capability_authority
compose_graded_outcome
composition_to_axis_positions
compute_net_mav
compute_sealed_battery_freeze_hash
construct_for_legacy_family
construct_refs_for_alias
construct_registry_concept_spine_entries
construct_registry_public_surface
cost_degradation_scorecard_gates
cost_gate_scorecard_gates
coupling_accuracy
create_capability_index_fixture_inputs
critical_path_regime
decompose_design
default_diagnostic_slo_targets
derive_recursive_design_graph
deserialize_authority_envelope
deserialize_degradation_record
deserialize_hypothesis_ledger
deserialize_semantic_binding_ledger
deterministic_review_fixtures
diagnostic_slo_gates
discover_design_modules
effective_independence_factor_for_capability
evaluate_aggregation_validity
evaluate_blocking_frontier_control
evaluate_capability_claim
evaluate_capacity_feasibility
evaluate_degradation_policy
evaluate_delegation_for_case
evaluate_mandate_legitimacy
evaluate_measurability_adequacy
evaluate_review_packet
evaluate_schema_compatibility
evaluate_semantic_binding_ledger
evaluate_semantic_evaluation_pack
evaluate_semantic_gold_card_fixture
evaluate_strategic_response
evaluation_safety_consumer_admission_is_verified
evidence_line_record_id
evidence_synthesis_refs_by_claim
explain_mode_mismatch
explain_replay_drift
export_argument_graph
export_claim_argument_case_mapping
gate_lowering_request
gate_universality_claim
graded_outcome_closeout_record
gy_content_hash
historical_prior_claim_evidence_issues
human_review_public_export
inspect_argument_graph
ir_analytics_bridge_issues_for_claims
ir_analytics_claim_bindings_by_claim
is_historical_prior_ref
is_memory_influence_ref
is_production_claim_admissible
legacy_compatible_payload
legacy_family_for_construct
load_acquisition_planner_report
load_construct_registry
logic_hash_for_rule
max_admissible_posture
memory_influence_claim_evidence_issues
merge_argument_graph_quality_evidence_surfaces
merge_ir_analytics_binding_into_registry_entry
merge_producer_pipeline_quality_evidence_surfaces
mode_policy_failure_code
non_ukraine_bound_constructs
normalize_ir_analytics_claim_bridge
normalize_quality_evidence
normalize_runtime_privacy_compliance_report
pass1b_tenant_cas_approval_governance_issues
persist_acquisition_planner_report
persist_argument_graph
persist_calibration_ledger
persist_drift_explanation
persist_human_review_calibration_report
persist_hypothesis_ledger
persist_legacy_migration_sandbox_report
persist_production_approval_packet
persist_projection_lowering_bundle
persist_prompt_tool_ledger
persist_replay_manifest
persist_rule_evolution_registry
persist_rule_replay_comparison_report
persist_value_choice_provenance_bundle
persist_wave2_policy_design_case_walking_skeleton
plan_evidence_acquisition
plan_requirement_gap_acquisition
policy_design_case_maturity_scorecard_gates
policy_design_case_record_registry_payload
policy_design_case_record_registry_scorecard_gates
policy_design_concept_spine_json_schema
policy_design_jurisdiction_spine_json_schema
policy_design_pass1b_hardening_scorecard_gates
producer_spine_read_context_for
project_cae_defeaters_to_s14_skeptic_records
project_value_tradeoff_disclosure
public_rule_evolution_annotation
ratchet_templates
reader_schema_ranges
reconcile_authority_event
reconcile_authority_ref
record_human_decision
regime_accuracy
regime_claim_to_axis_position
regime_design_strategy
replay_under_new_rules
replay_under_original_rules
requirement_gaps_from_compiled_specs
resolve_evaluation_mode
resolve_expression
resolve_s12_resource_refs
review_controls_for_pruning
run_cost_budget_policy_from_performance_budget
run_cost_ledger_record_id
run_eight_stage_producer_pipeline
run_requirement_spec_producer_pipeline
s6_fail_closed_coverage
s6_firewall_report_to_axis_positions
s6_firewall_report_to_c3_dimension_records
s6_firewall_report_to_constraint_store_updates
s7_delegation_integrity
s8_value_provenance_integrity
s9_projection_lowering_integrity
select_floor
semantic_evaluation_pack_json_schema
semantic_gold_card_json_schema
serialize_authority_envelope
serialize_degradation_record
serialize_hypothesis_ledger
severity_for_points
skip_blocker_gate_from_payloads
summarize_forecast_support_integrity
summarize_post_deploy_accountability
summarize_resource_economics_integrity
summarize_s11_predictive_knowledge_integrity
summarize_universality_assurance
synthesis_report_record_id
validate_capability_authority
validate_capability_selection_ledger
validate_case_lifecycle_record
validate_case_maturity_profile
validate_claim_argument_case_surfaces
validate_config_release_deployment_migration_hardening_record
validate_construct_registry_coverage
validate_cost_degradation_telemetry
validate_disconfirming_evidence_ledger_record
validate_evidence_graph_threat_model_record
validate_evidence_independence_map_record
validate_evidence_line_record
validate_evidence_line_records
validate_evidence_synthesis_report_record
validate_ex_post_learning_record
validate_hybrid_concept_spine_carrier
validate_implementation_monitoring_evaluation_record
validate_multiverse_specification_curve_record
validate_obligation_rule_construct_refs
validate_observability_orchestration_static_audit_records
validate_pass1b_tenant_cas_approval_governance_record
validate_policy_benchmarking_record
validate_policy_design_best_in_class_benchmarking_records
validate_policy_design_case_concept_spine
validate_policy_design_case_profile
validate_policy_design_case_record_registry_payload
validate_policy_design_jurisdiction_spine
validate_policy_design_lifecycle_records
validate_policy_evidence_capability_replay_refs
validate_policy_intent_envelope
validate_prompt_tool_parser_authority
validate_public_audit_archive_record
validate_run_cost_gate_report
validate_run_cost_proportionality_blocker
validate_run_cost_proportionality_ledger
verify_policy_design_case_projection_consumer_contract
verify_post_deploy_learning_authority
verify_prediction_authority_envelope
verify_projection_faithfulness
verify_resource_authority_envelope
verify_s9_projection_faithfulness_for_pdc_consumer_contract
verify_s10_forecast_projection_consumer_contract
verify_s11_predictive_knowledge_authority_envelope
verify_sealed_battery_integrity
verify_universality_claim_authority
warning_lifecycle_summaries
world_model_record_content_hash
write_authority_envelope_json_schema
```

</details>

## `polisyos.lex`

- Classification: `public_stable`
- Supported entrypoints: `polisyos.lex`, `polisyos.lex.knowledge`
- Facade policy: expected `lazy_facade`, observed `lazy_facade`
- Owner: `team-polisyos`
- README: `src/polisyos/lex/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Stable runtime Lex facade for NormPack assembly, legal evaluation, simulator, interventions, and read-only legal knowledge APIs. Offline legal preprocessing is owned by polisyos.data_forge.domains.legal.
- Summary: Stable Lex facade for runtime legal evaluation, NormPack assembly, and interventions.

### Resolved supported entrypoints

| Entrypoint | Source | Facade | Exports |
| --- | --- | --- | ---: |
| `polisyos.lex` | `src/polisyos/lex/__init__.py` | `lazy_facade` | 51 |
| `polisyos.lex.knowledge` | `src/polisyos/lex/knowledge/__init__.py` | `lazy_facade` | 11 |

#### `polisyos.lex`

- Source: `src/polisyos/lex/__init__.py`
- Facade: `lazy_facade`
- Summary: Stable Lex facade for runtime legal evaluation, NormPack assembly, and interventions.

<details><summary>Entrypoint exports (51)</summary>

```text
ActiveVersionResult
ActiveVersionStrategy
AffectedKPI
ChangeProposalRef
ComplianceDelta
ComplianceTransition
HierarchicalPolicySearchPlan
InterventionKnobDictionaryEntry
InterventionKnobSpec
LegalEvaluationRequest
LegalKnowledgeGraph
LegalReportRef
LexBenchmarkOutcome
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
TemporalInterventionSequencer
TemporalInterventionStepInput
assemble_norm_pack
build_legal_authority_report
build_legal_authority_requirement_artifact
build_normative_applicability_report
diff_norm_packs
evaluate_legality
lex_evidence_from_fabric_decision_data
propose_changes
resolve_active_version
run_legal_benchmark
```

</details>

#### `polisyos.lex.knowledge`

- Source: `src/polisyos/lex/knowledge/__init__.py`
- Facade: `lazy_facade`
- Summary: Legal knowledge graph: SPO entities, facts, and semantic search.

<details><summary>Entrypoint exports (11)</summary>

```text
LegalEntity
LegalFact
LegalFactResult
LegalKnowledgeGraph
LegalProvision
LegalProvisionResult
LegalRuleThresholdRow
LegalSearchResult
LegalTemporalCompetence
LegalThresholdEvaluation
search_legal_knowledge
```

</details>

<details><summary>Supported exports (51)</summary>

```text
ActiveVersionResult
ActiveVersionStrategy
AffectedKPI
ChangeProposalRef
ComplianceDelta
ComplianceTransition
HierarchicalPolicySearchPlan
InterventionKnobDictionaryEntry
InterventionKnobSpec
LegalEvaluationRequest
LegalKnowledgeGraph
LegalReportRef
LexBenchmarkOutcome
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
TemporalInterventionSequencer
TemporalInterventionStepInput
assemble_norm_pack
build_legal_authority_report
build_legal_authority_requirement_artifact
build_normative_applicability_report
diff_norm_packs
evaluate_legality
lex_evidence_from_fabric_decision_data
propose_changes
resolve_active_version
run_legal_benchmark
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

### Resolved supported entrypoints

| Entrypoint | Source | Facade | Exports |
| --- | --- | --- | ---: |
| `polisyos.scholar` | `src/polisyos/scholar/__init__.py` | `lazy_facade` | 25 |

#### `polisyos.scholar`

- Source: `src/polisyos/scholar/__init__.py`
- Facade: `lazy_facade`
- Summary: Expose Scholar enrichment entrypoints and contracts via lazy imports.

<details><summary>Entrypoint exports (25)</summary>

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

### Resolved supported entrypoints

| Entrypoint | Source | Facade | Exports |
| --- | --- | --- | ---: |
| `polisyos.data_forge` | `src/polisyos/data_forge/__init__.py` | `lazy_facade` | 49 |
| `polisyos.data_forge.read_api` | `src/polisyos/data_forge/read_api/__init__.py` | `lazy_facade` | 16 |

#### `polisyos.data_forge`

- Source: `src/polisyos/data_forge/__init__.py`
- Facade: `lazy_facade`
- Summary: Data Forge public facade for build-time artifact contracts and read APIs.

<details><summary>Entrypoint exports (49)</summary>

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

#### `polisyos.data_forge.read_api`

- Source: `src/polisyos/data_forge/read_api/__init__.py`
- Facade: `lazy_facade`
- Summary: Stable runtime-safe Data Forge read APIs.

<details><summary>Entrypoint exports (16)</summary>

```text
READ_API_SURFACES
OfficialSnapshotAnswer
ReadApiSurface
academic
available_surfaces
build_privacy_compliance_report
catalog
compliance
get_surface
legal
load_surface
normalize_privacy_compliance_report
provenance
surface_module
surfaces
ukraine
```

</details>

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

### Resolved supported entrypoints

| Entrypoint | Source | Facade | Exports |
| --- | --- | --- | ---: |
| `polisyos.berl` | `src/polisyos/berl/__init__.py` | `eager_exports` | 11 |

#### `polisyos.berl`

- Source: `src/polisyos/berl/__init__.py`
- Facade: `eager_exports`
- Summary: Bounded Explanation Reliability Layer public API.

<details><summary>Entrypoint exports (11)</summary>

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

### Resolved supported entrypoints

| Entrypoint | Source | Facade | Exports |
| --- | --- | --- | ---: |
| `polisyos.calibration` | `src/polisyos/calibration/__init__.py` | `eager_exports` | 10 |

#### `polisyos.calibration`

- Source: `src/polisyos/calibration/__init__.py`
- Facade: `eager_exports`
- Summary: Calibration diagnostics public entrypoints.

<details><summary>Entrypoint exports (10)</summary>

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

### Resolved supported entrypoints

| Entrypoint | Source | Facade | Exports |
| --- | --- | --- | ---: |
| `polisyos.ddm` | `src/polisyos/ddm/__init__.py` | `eager_exports` | 17 |

#### `polisyos.ddm`

- Source: `src/polisyos/ddm/__init__.py`
- Facade: `eager_exports`
- Summary: Drift-and-Degradation Monitor for Phase 5 Problem 15.7.

<details><summary>Entrypoint exports (17)</summary>

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

### Resolved supported entrypoints

| Entrypoint | Source | Facade | Exports |
| --- | --- | --- | ---: |
| `polisyos.foundry.agent_sim.world` | `src/polisyos/foundry/agent_sim/world/__init__.py` | `eager_exports` | 23 |

#### `polisyos.foundry.agent_sim.world`

- Source: `src/polisyos/foundry/agent_sim/world/__init__.py`
- Facade: `eager_exports`
- Summary: Synthetic-world family with truth-centric generation and evaluation.

<details><summary>Entrypoint exports (23)</summary>

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
