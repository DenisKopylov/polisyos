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
| `polisyos.common` | `public_stable` | `lazy_facade` | 8 | `team-polisyos` | `src/polisyos/common/README.md` |
| `polisyos.core` | `public_stable` | `lazy_facade` | 134 | `team-polisyos` | `src/polisyos/core/README.md` |
| `polisyos.ir` | `public_stable` | `lazy_facade` | 530 | `team-polisyos` | `src/polisyos/ir/README.md` |
| `polisyos.obligation_rules` | `internal` | `eager_exports` | 22 | `team-policyos-runtime` | `src/polisyos/obligation_rules/README.md` |
| `polisyos.obligation_graph` | `internal` | `eager_exports` | 20 | `team-policyos-runtime` | `src/polisyos/obligation_graph/README.md` |
| `polisyos.method_requirement` | `internal` | `eager_exports` | 14 | `team-policyos-runtime` | `src/polisyos/method_requirement/README.md` |
| `polisyos.participation_requirement` | `internal` | `eager_exports` | 23 | `team-policyos-runtime` | `src/polisyos/participation_requirement/README.md` |
| `polisyos.fabric` | `public_stable` | `unresolved_exports` | unknown (no names proven) | `team-polisyos` | `src/polisyos/fabric/README.md` |
| `polisyos.foundry` | `public_stable` | `lazy_facade` | 31 | `team-polisyos` | `src/polisyos/foundry/README.md` |
| `polisyos.scientist` | `public_stable` | `lazy_facade` | 41 | `team-polisyos` | `src/polisyos/scientist/README.md` |
| `polisyos.evidence` | `internal` | `eager_exports` | 19 | `team-policyos-runtime` | `src/polisyos/evidence/README.md` |
| `polisyos.runtime` | `public_stable` | `lazy_facade` | 10 | `team-polisyos` | `src/polisyos/runtime/README.md` |
| `polisyos.runtime.quality` | `public_experimental` | `eager_exports` | 973 | `team-polisyos` | `src/polisyos/runtime/quality/README.md` |
| `polisyos.lex` | `public_stable` | `lazy_facade` | 61 | `team-polisyos` | `src/polisyos/lex/README.md` |
| `polisyos.scholar` | `public_experimental` | `lazy_facade` | 30 | `team-polisyos` | `src/polisyos/scholar/README.md` |
| `polisyos.data_forge` | `public_experimental` | `lazy_facade` | 49 | `team-data-forge` | `src/polisyos/data_forge/README.md` |
| `polisyos.berl` | `public_experimental` | `eager_exports` | 16 | `team-scientist` | `src/polisyos/berl/README.md` |
| `polisyos.calibration` | `public_experimental` | `lazy_facade` | 17 | `team-scientist` | `src/polisyos/calibration/README.md` |
| `polisyos.ddm` | `internal` | `lazy_facade` | 17 | `team-scientist` | `src/polisyos/ddm/README.md` |
| `polisyos.foundry.agent_sim.world` | `public_experimental` | `eager_exports` | 23 | `team-foundry` | `src/polisyos/foundry/agent_sim/world/README.md` |

## `polisyos.common`

- Classification: `public_stable`
- Supported entrypoints: `polisyos.common`, `polisyos.common.text`, `polisyos.common.config`, `polisyos.common.canonical`, `polisyos.common.canonical_profile`, `polisyos.common.hashing`, `polisyos.common.migrations`
- Facade policy: expected `lazy_facade`, observed `lazy_facade`
- Owner: `team-polisyos`
- README: `src/polisyos/common/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Shared helper boundary for config, logging, serialization, and migrations.
- Summary: Expose side-effect-sensitive common helpers behind a lazy package facade.

### Resolved supported entrypoints

| Entrypoint | Source | Facade | Exports |
| --- | --- | --- | ---: |
| `polisyos.common` | `src/polisyos/common/__init__.py` | `lazy_facade` | 8 |
| `polisyos.common.text` | `src/polisyos/common/text.py` | `eager_exports` | 1 |
| `polisyos.common.config` | `src/polisyos/common/config/__init__.py` | `eager_exports` | 8 |
| `polisyos.common.canonical` | `src/polisyos/common/canonical.py` | `eager_exports` | 10 |
| `polisyos.common.canonical_profile` | `src/polisyos/common/canonical_profile.py` | `eager_exports` | 9 |
| `polisyos.common.hashing` | `src/polisyos/common/hashing.py` | `eager_exports` | 5 |
| `polisyos.common.migrations` | `src/polisyos/common/migrations/__init__.py` | `eager_exports` | 6 |

#### `polisyos.common`

- Source: `src/polisyos/common/__init__.py`
- Facade: `lazy_facade`
- Summary: Expose side-effect-sensitive common helpers behind a lazy package facade.

<details><summary>Entrypoint exports (8)</summary>

```text
async_tools
config
jax_env
logger
migrations
serialization
text
timestamps
```

</details>

#### `polisyos.common.text`

- Source: `src/polisyos/common/text.py`
- Facade: `eager_exports`
- Summary: Pure text normalization helpers shared across PolicyOS packages.

<details><summary>Entrypoint exports (1)</summary>

```text
collapse_ws
```

</details>

#### `polisyos.common.config`

- Source: `src/polisyos/common/config/__init__.py`
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

#### `polisyos.common.canonical`

- Source: `src/polisyos/common/canonical.py`
- Facade: `eager_exports`
- Summary: Shared strict canonical JSON mechanics for the Core and IR profiles.

<details><summary>Entrypoint exports (10)</summary>

```text
ArrayDigestRepresentation
BytesHexRepresentation
CanonSpec
CanonicalError
CanonicalResourceLimits
FloatHexRepresentation
from_canonical_bytes
from_canonical_obj
to_bounded_canonical_bytes
to_canonical_bytes
```

</details>

#### `polisyos.common.canonical_profile`

- Source: `src/polisyos/common/canonical_profile.py`
- Facade: `eager_exports`
- Summary: Shared strict profile-conformance mechanics for persisted JSON.

<details><summary>Entrypoint exports (9)</summary>

```text
CanonicalProfileDeclaration
CanonicalProfileRead
CanonicalProfileRefusalError
CanonicalProfileStatus
decode_profiled_canonical_bytes
parse_canonical_profile
read_canonical_profiled_bytes
read_optional_selected_artifact
require_declared_profile
```

</details>

#### `polisyos.common.hashing`

- Source: `src/polisyos/common/hashing.py`
- Facade: `eager_exports`
- Summary: Shared byte hashing primitives used by the Core and IR canon facades.

<details><summary>Entrypoint exports (5)</summary>

```text
DeprecatedHashAlgorithm
HashAlgorithm
content_hash
streaming_hash
truncated_hash
```

</details>

#### `polisyos.common.migrations`

- Source: `src/polisyos/common/migrations/__init__.py`
- Facade: `eager_exports`
- Summary: Exports the artifact-migration registry used to upgrade stored payload schemas.

<details><summary>Entrypoint exports (6)</summary>

```text
MANIFEST_CURRENT_VERSION
ArtifactPayload
LinearMigrationProfile
migrate_artifact
register_migration
run_linear_migration
```

</details>

<details><summary>Supported exports (8)</summary>

```text
async_tools
config
jax_env
logger
migrations
serialization
text
timestamps
```

</details>

## `polisyos.core`

- Classification: `public_stable`
- Supported entrypoints: `polisyos.core`, `polisyos.core.artifacts`, `polisyos.core.canon`, `polisyos.core.components`, `polisyos.core.contracts`, `polisyos.core.governance`, `polisyos.core.llm`, `polisyos.core.llm.cache_settlement`, `polisyos.core.observability`, `polisyos.core.security`, `polisyos.core.trace`, `polisyos.core.registry`, `polisyos.core.run.worker_lifecycle`
- Facade policy: expected `lazy_facade`, observed `lazy_facade`
- Owner: `team-polisyos`
- README: `src/polisyos/core/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Cross-layer contracts, CAS, registry, observability, and security primitives.
- Summary: Expose the stable Core platform surface with lazy package imports.

### Resolved supported entrypoints

| Entrypoint | Source | Facade | Exports |
| --- | --- | --- | ---: |
| `polisyos.core` | `src/polisyos/core/__init__.py` | `lazy_facade` | 134 |
| `polisyos.core.artifacts` | `src/polisyos/core/artifacts/__init__.py` | `lazy_facade` | 135 |
| `polisyos.core.canon` | `src/polisyos/core/canon/__init__.py` | `eager_exports` | 12 |
| `polisyos.core.components` | `src/polisyos/core/components/__init__.py` | `eager_exports` | 63 |
| `polisyos.core.contracts` | `src/polisyos/core/contracts/__init__.py` | `lazy_facade` | 782 |
| `polisyos.core.governance` | `src/polisyos/core/governance/__init__.py` | `eager_exports` | 5 |
| `polisyos.core.llm` | `src/polisyos/core/llm/__init__.py` | `eager_exports` | 20 |
| `polisyos.core.llm.cache_settlement` | `src/polisyos/core/llm/cache_settlement.py` | `eager_exports` | 8 |
| `polisyos.core.observability` | `src/polisyos/core/observability/__init__.py` | `unresolved_exports` | unknown (no names proven) |
| `polisyos.core.security` | `src/polisyos/core/security/__init__.py` | `lazy_facade` | 113 |
| `polisyos.core.trace` | `src/polisyos/core/trace/__init__.py` | `eager_exports` | 6 |
| `polisyos.core.registry` | `src/polisyos/core/registry/__init__.py` | `lazy_facade` | 12 |
| `polisyos.core.run.worker_lifecycle` | `src/polisyos/core/run/worker_lifecycle.py` | `eager_exports` | 4 |

#### `polisyos.core`

- Source: `src/polisyos/core/__init__.py`
- Facade: `lazy_facade`
- Summary: Expose the stable Core platform surface with lazy package imports.

<details><summary>Entrypoint exports (134)</summary>

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
FileSystemSignedArtifactEvidenceRepository
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

#### `polisyos.core.artifacts`

- Source: `src/polisyos/core/artifacts/__init__.py`
- Facade: `lazy_facade`
- Summary: Publish the stable CAS artifact ABI used by manifests, lineage, and signing.

<details><summary>Entrypoint exports (135)</summary>

```text
AUTHORITY_ENVELOPE_ARTIFACT_KIND
AUTHORITY_ENVELOPE_SCHEMA_NAME
AUTHORITY_ENVELOPE_SCHEMA_VERSION
OWNERSHIP_INDEX_FORMAT_POINTER_GENERATION_V1
OWNERSHIP_INDEX_SCHEMA_VERSION
ArtifactAuthorityInfo
ArtifactBoundedManifestRead
ArtifactBoundedManifestReadError
ArtifactGovernanceInfo
ArtifactID
ArtifactIntegrityError
ArtifactManifest
ArtifactMemberReadBoundsError
ArtifactMemberReadIntegrityError
ArtifactMemberReceipt
ArtifactOwnershipError
ArtifactOwnershipIndex
ArtifactReadBoundsError
ArtifactReadOnlyUnavailableError
ArtifactReader
ArtifactRef
ArtifactSameInputClosureInfo
ArtifactSigner
ArtifactSigningResult
ArtifactStore
ArtifactStoreConfig
ArtifactStoreReadUsage
ArtifactTenantContextInfo
ArtifactUnavailableError
ArtifactVerifier
ArtifactWriteOptions
AsyncArtifactStore
AsyncArtifactStoreAdapter
AsyncFileSystemArtifactStore
AsyncRawManifestBytesReader
AtomicFileDurabilityError
BatchAuthorizationLossSignal
BulkSigningReport
BulkVerificationReport
CASIntegrityReport
CanonInfo
CoreArtifactOwnerProfile
CoreJSONArtifactBoundedInputManifestReader
CoreJSONArtifactBoundedInputManifestReceiptReader
CoreJSONArtifactBoundedManifestReader
CoreJSONArtifactBoundedManifestReceiptReader
CoreJSONArtifactBoundedMemberAttempt
CoreJSONArtifactBoundedMemberReader
CoreJSONArtifactBoundedMemberStream
CoreJSONArtifactMemberStream
CoreJSONArtifactProfileReader
CoreJSONArtifactStore
CoreJSONArtifactStreamingReader
CoreJsonArtifactBoundedRead
CoreJsonManifestBoundedRead
CoreJsonReadBoundsRefusalError
CoreJsonReadLimits
CoreJsonWriterPolicy
CoreOwnedModelRead
CoreToIRArtifactStoreAdapter
DependencyEdge
DependencyGraph
DependencyNode
DetachedSignature
Ed25519Signer
Ed25519Verifier
EnvInfo
ExportReport
FileSystemCAS
GitInfo
ImportReport
InputRef
IntegrityInfo
KeyPair
NodeStatus
ProducerInfo
PutOptions
RawManifestBytesReader
ReadOnlyFileSystemCAS
RegistryBundle
RegistryBundlePayload
RootedArtifactStore
SchemaInfo
SelectedProfileVerificationReader
SignatureStatement
SignatureVerificationResult
SignatureVerificationStatus
SignatureVerifyingArtifactStore
SigningConfig
VerificationReport
WarningRecord
aload_core_json_artifact
artifact_manifest_profile_projection
artifact_manifest_profile_sha256
artifact_ref_for_manifest
artifact_ref_identity_key
artifact_reference_parts
build_artifact_store
build_cas_integrity_report
compute_key_id
declare_core_json_writer_policy
decode_core_json_payload
ensure_async_artifact_store
ensure_directory_durable
ensure_ir_artifact_store
ensure_private_key_permissions
expected_artifact_manifest_for_write
fsync_directory
input_ref_from_artifact_ref
load_core_json_artifact
load_core_json_frame_records
matches_artifact_store_protocol
matches_runtime_protocol
matches_runtime_protocol_definition
profile_bound_ref
put_core_json_artifact_bounded
raise_artifact_read_access_error
read_core_input_manifest_profile_bounded
read_core_json_artifact
read_core_json_artifact_bounded
read_core_json_artifact_bytes
read_core_json_writer_artifact_bounded
read_core_manifest_profile
read_core_manifest_profile_bounded
require_return_selected_profile_writer
resolve_authority_envelope_ref
resolve_dependency_graph
resolve_manifest_by_profile
validate_core_model_bounded_read
validate_core_model_json_artifact
validate_owned_core_model_json_artifact
validate_return_selected_profile
with_ambient_ownership_enforcement_if_supported
write_bytes_atomic
write_bytes_once
```

</details>

#### `polisyos.core.canon`

- Source: `src/polisyos/core/canon/__init__.py`
- Facade: `eager_exports`
- Summary: Exports canonical JSON helpers and hashing utilities for stable artifact identities.

<details><summary>Entrypoint exports (12)</summary>

```text
CanonSpec
CanonViolation
CanonicalResourceLimits
DeprecatedHashAlgorithm
content_hash
fingerprint
from_canonical_bytes
from_canonical_obj
streaming_hash
to_bounded_canonical_bytes
to_canonical_bytes
truncated_hash
```

</details>

#### `polisyos.core.components`

- Source: `src/polisyos/core/components/__init__.py`
- Facade: `eager_exports`
- Summary: Expose the stable component discovery, metadata, compliance, and registry API.

<details><summary>Entrypoint exports (63)</summary>

```text
DEFAULT_ENTRY_POINT_GROUPS
ENTRY_POINT_GROUP
ENTRY_POINT_GROUP_DATA_FORGE_DOMAINS
ENTRY_POINT_GROUP_FABRIC_CONNECTORS
ENTRY_POINT_GROUP_FOUNDRY_METHODS
ENTRY_POINT_GROUP_IR_FRAGMENTS
ENTRY_POINT_GROUP_LEX_EVALUATORS
ENTRY_POINT_GROUP_LEX_EXTRACTORS
ENTRY_POINT_GROUP_LEX_NORMPACKS
ENTRY_POINT_GROUP_NORM_PACK_PROVIDERS
ENTRY_POINT_GROUP_RUNTIME_MIDDLEWARES
ENTRY_POINT_GROUP_SCHOLAR_EXTRACTORS
ENTRY_POINT_GROUP_SCIENTIST_GOVERNANCE_PASSES
ENTRY_POINT_GROUP_SCIENTIST_NODES
EXTENSION_ENTRY_POINT_GROUPS
LEGACY_ENTRY_POINT_GROUP
BootstrapDomainReport
BootstrapReport
BuiltinLoaderSpec
Capabilities
Capability
ComplianceIssue
Component
ComponentDep
ComponentDiscoveryManifest
ComponentEntry
ComponentFactory
ComponentId
ComponentKind
ComponentMetadata
ComponentProvider
ComponentRegistry
ConflictPolicy
DeclaredBuiltinLoader
DiscoveryComponentIdentity
DiscoveryDeclaredBuiltinLoaderIdentity
DiscoveryDevScanFileIdentity
DiscoveryDevScanRootIdentity
DiscoveryEntryPointIdentity
DiscoveryError
DiscoveryPrecedencePolicy
DiscoveryPredicateProvenance
DiscoveryReport
DuplicateComponentIdPolicy
HostAbi
ProviderModuleBinding
ProviderOriginBinding
ResolvePolicy
SemVer
SemverRange
SourcePrecedencePolicy
SupportsValidation
bootstrap_plugin_registries
build_components_index
capabilities_from_flags
compare_semver
discover_components
discover_dev_components
discover_entry_points
flags_from_capabilities
has_errors
validate_component_id
validate_metadata
```

</details>

#### `polisyos.core.contracts`

- Source: `src/polisyos/core/contracts/__init__.py`
- Facade: `lazy_facade`
- Summary: Lazy facade for the stable DTOs shared across PolicyOS subsystem boundaries.

<details><summary>Entrypoint exports (782)</summary>

```text
AcceptanceNonReceipt
AcceptanceOutcome
AcceptanceRejectedNonReceipt
AcceptanceUnavailableNonReceipt
ApplicablePredicateDenominatorArtifactFailure
ApplicablePredicateDenominatorStatement
AnchorAcceptanceAppendSuccessStatement
AnchorAcceptanceEvidenceBundle
AnchorAcceptanceLineageKey
AnchorAcceptanceLineageRepository
AnchorAcceptanceLineageStateStatement
AnchorAcceptanceReceipt
AnchorAcceptanceReceiptStatement
AnchorAcceptanceRecord
AnchorAcceptanceRequest
AnchorAcceptanceStatement
AnchorCustodyReceiptStatement
AnchorCustodyVerification
AnchorReadbackChallengeRepository
AnchorReadbackChallengeStatement
AnchorRetentionObjectGraph
AnchorRetentionPackage
AnchorRetentionStatement
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
EpochAnchorAppointmentResolution
EpochAnchorAppointmentResolver
EpochAnchorAuthorityRegistry
EpochAnchorCustodyProvider
ExpectedCommitmentPrefix
FULL_PREFIX_EVALUATION_TABLE
FULL_PREFIX_FAILURE_DESCRIPTORS
FULL_PREFIX_TERMINAL_BY_RESULT_KIND
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
PersistedSignedArtifactEvidence
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
QueryPredicateDisposition
RejectedAcceptanceOutcome
RejectedRetentionOutcome
RetentionNonReceipt
RetentionOutcome
RetentionRejectedNonReceipt
RetentionUnavailableNonReceipt
ResolvedPredicatePolicyAdmission
SignedArtifactEvidence
SignedArtifactEvidenceRepository
UnavailableAcceptanceAppointment
UnavailableAcceptanceOutcome
UnavailableHolderAppointment
UnavailableRetentionOutcome
VerifiedAcceptanceVerifierAppointment
VerifiedAcceptanceOutcome
VerifiedAnchorAcceptance
VerifiedAnchorRetention
VerifiedHolderVerifierAppointment
VerifiedNativeMemberIdentity
VerifiedNativeSubjectIdentity
VerifiedOwnerPredicateEvidence
VerifiedPolicyOwnerProvenance
VerifiedPredicatePolicyOwnerRelation
VerifiedRetentionOutcome
chronology_bundle_content_hash
AcquisitionArtifactCodec
BOUNDED_LIVENESS_CONFIG_SCHEMA_VERSION
C4_PERSISTED_PROFILE_SPECS
CAPABILITY_DISCOVERY_SCHEMA_VERSION
OPTIONAL_ANALYTIC_NODE_KINDS
OWNED_ATTEMPT_ANCHOR_KIND
OWNED_ATTEMPT_ANCHOR_SCHEMA_NAME
OWNED_ATTEMPT_ANCHOR_SCHEMA_VERSION
POLICY_DESIGN_CASE_PROJECTION_SCHEMA_VERSION
PRODUCER_SPINE_CONSUMER_COMPONENTS
PRODUCER_SPINE_CONTEXT_SCHEMA_VERSION
RECOURSE_POINTER_SCHEMA_VERSION
REQUIREMENT_TO_CAPABILITY_QUERY_SCHEMA_VERSION
SCOPE_ADJUDICATION_AUTHORITY_PURPOSE
SCOPE_ADJUDICATION_CANDIDATE_SCHEMA_VERSION
SCOPE_ADJUDICATION_PROHIBITED_USES
SERIOUS_SKIP_BLOCKER_PROFILES
SKIP_BLOCKER_REQUIRED_FIELDS
SKIP_BLOCKER_SURFACES
ActiveDisambiguationPlanRef
ActivityType
AgentPipelineAttempt
AgentPipelineCostEvent
AgentPipelineResponse
AgentPipelineStep
AgentPipelineUnattributedCostScalar
AgentPipelineView
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
CatalogRunProfile
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
ControlJobCancellationRequest
ControlJobResponse
ControlPreAdmissionAttemptEventInfo
ControlPreAdmissionAttemptResponse
ControlPreAdmissionOwnerBinding
ControlPreAdmissionAttemptStatus
ControlPreAdmissionEventObservation
NoCallReason
ProducerCallState
ControlOutboxEventInfo
ControlOutboxEventsResponse
ControlWorkerLeaseInfo
ControlWorkersResponse
CritiqueRef
CursorPage
DATA_SNAPSHOT_LINEAGE_SCHEMA_VERSION
AcquiredObservationDataSnapshotLineage
DataSnapshot
DataSnapshotOwnerBound
DataSnapshotOwnerLineage
DataSnapshotRef
FabricBridgeDataSnapshotLineage
MeasurementRootDataSnapshotLineage
DataSourceBinding
WorkflowDataSourceBinding
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
DecisionPacketLegacyHTEFeaturePreview
DecisionPacketLegacyHTEPreview
DecisionPacketRef
DecisionTriggerRecord
DecisionTriggerSpec
DecisionTriggerType
DecisionValidityEnvelope
DecisionValidityEpochImpactOwnerRow
DecisionValidityEpochImpactSnapshot
DecisionValidityEpochImpactSnapshotHandle
DecisionValidityEpochImpactTarget
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
EngineeringCapabilityAbsenceView
EntityType
EnrichmentReportV1
EnrichResultV1
EnvironmentManifestRef
EpochBoundaryLineageView
EpochCertificateStalenessView
EpochDenominatorReconciliationAdmissionBinding
EpochDependencyStalenessView
EpochDerivedRecomputeView
EpochOpenWorldRiskComponentView
EpochOpenWorldRiskView
EpochPerturbationClass
EpochPerturbationView
EpochProjectionDenominatorView
EpochProjectionStatus
EpochStalenessProjectionView
EpochTransitionDenominatorMappingRow
EpochTransitionDenominatorReconciliationHandle
EpochTransitionDenominatorReconciliationReader
EpochTransitionDenominatorReconciliationReceipt
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
FORECAST_PROFILE_MEMBER_CONTRACT_VERSION
FORECAST_PROFILE_MEMBER_KIND
FORECAST_PROFILE_MEMBER_SCHEMA
FORECAST_PROFILE_MEMBER_SCHEMA_VERSION
ForecastProfileMemberV1
ForecastingUncertaintyBundleRef
FoundryCompileConfig
FoundryExecConfig
FoundryExecutionInputBasis
FoundryExecutionInputBasisRef
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
InstitutionalAuthorityAbsenceView
IssueSeverity
IterationLifecycleState
IterationState
IterationStateRef
JudgeVerdictRef
KnowledgeBundle
KnowledgeBundlePayloadV1
KnowledgeBundleRef
LegalContext
LegalEvaluationRequest
LegalQueryGenerationBasisKind
LegalQueryGenerationIntentV1
LegalReport
LegalReportRef
LexSearchRequest
LexSearchResponse
LexSearchResultItem
LexSourceRelationRefusal
LinkReportRef
LiteratureCausalPriorRef
LoweredIR
LoweredIRRef
MethodCatalogEntry
MethodCatalogSnapshot
MethodCatalogSnapshotRef
MethodDagEdge
ObservationalRunInput
ObservationalRunMethodSelection
ContentAdmittedObservationalRunIntent
DirectMethodExecutionRequestSummary
DirectMethodExecutionRunProjection
DirectMethodExecutionHTEResourceEvidence
DirectMethodExecutionHTESummary
DirectMethodExecutionHTETargetRelation
DirectMethodExecutionSelection
DirectMethodExecutionTimeRoles
RuntimeSearchHTECompletionDeliveryV1
MethodExecutionCandidateOutcome
GraphMethodExecutionSelection
MethodExecutionPosteriorSummaryRef
MethodExecutionProducerDiagnostic
MethodExecutionProducerEmissionDiagnostic
MethodExecutionSelection
CompletedExAnteCandidateComparisonResponse
CompletedExAnteCandidateSource
CompletedExAnteComparisonRequest
CompletedExAnteCandidateObservation
CompletedExAnteCandidateRanking
MethodMetricCandidateScore
MethodMetricProjectionResponse
MethodMetricProjectionSelection
ObservationalInputResourcePolicy
ObservationalRunIntent
CompletedMethodHTESource
OwnedAttemptAnchor
OwnedAttemptAnchorAssociation
OwnedAttemptAnchorDispatchContext
OwnedAttemptAnchorProjectionAssociation
OwnedAttemptAnchorRef
OwnedAttemptAnchorRefusalAssociation
OwnedAttemptPhysicalSourceBindingRef
OwnedAttemptHTEInputAdmitted
OwnedAttemptHTEInputCapture
OwnedAttemptHTEInputRefusal
OwnedAttemptHTEInputRefused
OwnedAttemptInputAdmission
OwnedAttemptLifecycleEvent
OwnedAttemptPredicateOrigins
OwnedHTERequestContextV1
SelectedArtifactRef
MethodDagNode
MethodArtifactOutputPayload
MethodArtifactOutputRef
MethodExecutionArtifact
MethodExecutionBackendAttempt
MethodExecutionBundle
MethodExecutionBundleRef
MethodExecutionDispatchRecord
MethodExecutionInputRole
MethodExecutionInputSlot
MethodExecutionOccurrence
MethodExecutionOutputSlot
MethodExecutionParameterValue
MethodExecutionReturnedSlot
MethodMetricBinding
MethodMetricBindingRequest
MethodMetricBindingSet
MethodMetricBindingSetRef
MethodMetricInputCapturePayload
MethodMetricInputCaptureRef
MethodOutputPayload
MethodOutputRef
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
PredictiveCoverageDiagnosticPreview
PredictiveCoverageScenarioPreview
NormDiffRef
NormImpactReportRef
NormPack
NormRef
NormRule
OrdinalPovertyReportRef
PeriodicOrbitDiagnostics
PeriodicOrbitDiagnosticsRef
PersistedDecisionValidityEpochImpactSnapshot
PersistedEpochTransitionDenominatorReconciliation
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
RegisteredSQLAdmissionBinding
RegisteredSQLUseContract
PreflightDiagnostic
PreflightReport
PreflightReportRef
PreviewMode
PriorKnowledgeBundleRef
PrivacyAwareTransportCertificateRef
ProblemFrameRef
ProducerSpineBindingFields
ProducerSpineReadContext
ProductionApprovalCurrentnessReceipt
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
RetrievalSummary
ResearchIntent
ResearchIntentRef
RuleBackend
RuleType
RunCandidateSimulationAcquisitionHistoryEntry
RunCandidateSimulationAcquisitionHistoryEntryV3
RunCandidateSimulationRetainedEvaluation
RunCandidateSimulationN5Observation
RunCandidateSimulationProjection
RunDetails
RunConditionalTransportCandidateProjection
RunDetailsResponse
RunErrorView
RunErrorsResponse
RunLaunchResponse
RunLineageResponse
RunNodeRecord
RunNodesResponse
RunRecordV1
RunGenericCycleSimulationN5Horizon
RunGenericCycleSimulationN5ResultBody
RunGenericCycleSimulationN5Trajectory
RunGenericCycleSimulationN5TrajectoryPoint
RunGenericCycleSimulationN6CycleHistoryEntry
RunRecursiveCycleBranchFailure
RunRecursiveCycleCheckpoint
RunSummary
RunTimelineEvent
RunTimelineResponse
RunTimelineSummary
RunTimelineView
RunsListResponse
RuntimeApiError
RuntimeApiProblem
RuntimeApiProblemContext
ScenarioFamilyConstructRow
ScenarioFamilyConstructRows
ScopeAdjudicationCandidate
ScopeAdjudicationPlane
ScopeAdjudicationPredicate
ScopeAdjudicationRuling
ScopePredicateObservation
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
TemporalScope
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
VALUE_DATA_PROFILE_KIND
VALUE_OWNER_PROJECTION_KIND
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
acquisition_artifact_canon_info
acquisition_artifact_codec
acquisition_native_coordinate_role
bounded_liveness_config_from_mapping
build_producer_spine_binding_fields
build_scope_adjudication_candidate
build_skip_blocker_record
c4_canonical_bytes
c4_canonical_mapping
c4_profile
c4_profile_manifest_is_exact
c4_semantic_digest
canonical_external_epoch_statement_bytes
data_snapshot_reference_fields
data_snapshot_reference_input_roles
data_snapshot_owner_input_requirements
data_snapshot_manifest_inputs_match
chronology
classify_optional_analytic_node
construct_for_legacy_family
deserialize_skip_blocker_record
epoch
epoch_staleness_semantic_hash
evaluate_skip_blocker_policy
external_epoch_statement_canon_info
forecast_profile_observed_series_sha256
legacy_family_for_construct
require_production_approval_currentness_receipt
scope_adjudication_candidate_digest
scoped_schema_regime_projection_content_hash
serialize_skip_blocker_record
verify_scope_adjudication_candidate
CONTROL_PRE_ADMISSION_SETTLEMENT_REQUIRED_PROFILES
NO_CALL_REASON_VALUES
PRODUCER_CALL_STATE_VALUES
DataNeed
DecisionMonitoringContractRef
DecisionValidityEventRequest
FeedbackConfig
FeedbackSolveResult
ParameterOverrideBundle
PolicyFlags
SourceVerificationReportRef
VerifiedPolicyReportRef
c4_framed_semantic_projection_digest
validate_producer_call_observation
```

</details>

#### `polisyos.core.governance`

- Source: `src/polisyos/core/governance/__init__.py`
- Facade: `eager_exports`
- Summary: Exports governance validation profiles shared by runtime and control-plane checks.

<details><summary>Entrypoint exports (5)</summary>

```text
ProfileLevel
ValidationProfile
LegalPass
PassContext
SafetyPass
```

</details>

#### `polisyos.core.llm`

- Source: `src/polisyos/core/llm/__init__.py`
- Facade: `eager_exports`
- Summary: Exports LLM pricing, retry, tracing, and response-normalization helpers.

<details><summary>Entrypoint exports (20)</summary>

```text
SECRET_AND_PII_SCAN_SCOPES
SECRET_PII_DETECTOR_VERSION
LLMClientProtocol
LLMResponseData
PromptSanitizer
SanitizationRule
SecretAndPIIScanReport
SecretPIIScanResult
TracedLLMClient
estimate_cost
estimate_cost_from_text
estimate_cost_from_tokens
extract_llm_response_data
retry_async
scan_secret_and_pii
LLMProducerAdmissionGuard
LLMProducerEvent
LLMProducerIntent
LLMSettlementOwnershipError
normalize_llm_cost_evidence
```

</details>

#### `polisyos.core.llm.cache_settlement`

- Source: `src/polisyos/core/llm/cache_settlement.py`
- Facade: `eager_exports`
- Summary: Opaque Core-owned owner boundary for authenticated cache reuse.

<details><summary>Entrypoint exports (8)</summary>

```text
CacheFlightOutcome
CacheFlightRegistration
CacheReuseAttestation
CacheReuseEvidence
CacheSettlementSession
bind_cache_settlement_client
create_cache_settlement_session
session_for_cache_client
```

</details>

#### `polisyos.core.observability`

- Source: `src/polisyos/core/observability/__init__.py`
- Facade: `unresolved_exports`
- Summary: PolicyOS Observability Module — Production-grade telemetry.
- Export resolution incomplete: `Unresolved exported binding: src/polisyos/core/observability/__init__.py:MetricsRegistry`.
- Export scope: `no names proven by the bounded parser; not an empty runtime namespace`
- Candidate scope: `Names in a finite source declaration before effect audit; not proved native exports, not included in known_export_count and not a completeness verdict.`
- Source evidence: 1 measured source reads; full path, byte-length, and SHA-256 receipts are in the companion inventory JSON.

<details><summary>Source-declared candidates (25; native exports unproved)</summary>

```text
DeterminismTier
MetricsRegistry
OTelConfig
PolicyOSTracer
StructuredFormatter
TraceContextFilter
TracedExecutorWrapper
configure_otel_logging_handler
estimate_llm_cost_usd
extract_headers
get_current_trace_context
get_default_config
get_determinism_tier
get_metrics
get_trace_context_dict
get_tracer
inject_headers
is_hpc_observability_enabled
parse_determinism_tier
pricing_table
propagate_context
traced
traced_method
with_context_vars
with_trace_context
```

</details>

#### `polisyos.core.security`

- Source: `src/polisyos/core/security/__init__.py`
- Facade: `lazy_facade`
- Summary: Lazy facade for tenant routing, quota, audit, identity, authz, TEE, and SBOM APIs.

<details><summary>Entrypoint exports (113)</summary>

```text
C3_CANONICAL_CODECS
SECURITY_ASSURANCE_REPORT_REF_KEY
SECURITY_REPORT_FILE
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
InMemoryAnchorReadbackChallengeRepository
InTotoStatement
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
QuotaAccountingError
QuotaEnforcer
QuotaExceededError
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
build_full_prefix_bundle
build_retention_package
build_security_assurance_report
canonical_statement_bytes
clear_tenant_context
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
verify_acceptance_appointment
verify_holder_appointment
verify_signed_evidence
SECURITY_ASSURANCE_ARTIFACT_KIND
SECURITY_ASSURANCE_ARTIFACT_MEDIA_TYPE
SECURITY_ASSURANCE_ARTIFACT_SCHEMA_NAME
SECURITY_ASSURANCE_ARTIFACT_SCHEMA_VERSION
```

</details>

#### `polisyos.core.trace`

- Source: `src/polisyos/core/trace/__init__.py`
- Facade: `eager_exports`
- Summary: Exports trace records and sinks used to persist run-level execution telemetry.

<details><summary>Entrypoint exports (6)</summary>

```text
BatchTraceSink
CompositeTraceSink
JsonlTraceSink
RunTerminality
TraceRecord
TraceSink
```

</details>

#### `polisyos.core.registry`

- Source: `src/polisyos/core/registry/__init__.py`
- Facade: `lazy_facade`
- Summary: Expose registry primitives and lazy bundle builders/loaders.

<details><summary>Entrypoint exports (12)</summary>

```text
BaseRegistry
DuplicateDecision
FragmentPrecedencePolicy
GenericRegistry
GenericRegistrySnapshot
RegistryBundleContent
build_default_registry_bundle
build_registry_bundle
build_registry_bundle_from_components
load_registry_bundle
load_registry_bundle_content
load_registry_bundle_payload
```

</details>

#### `polisyos.core.run.worker_lifecycle`

- Source: `src/polisyos/core/run/worker_lifecycle.py`
- Facade: `eager_exports`
- Summary: Core-owned boundary for staging and admitting run-worker receipts.

<details><summary>Entrypoint exports (4)</summary>

```text
WorkerDispatchBinding
WorkerLifecycleCapability
WorkerRunSnapshot
WorkerRunView
```

</details>

<details><summary>Supported exports (134)</summary>

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
FileSystemSignedArtifactEvidenceRepository
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
- Supported entrypoints: `polisyos.ir`, `polisyos.ir.analytics`, `polisyos.ir.analytics.calibration_diagnostics`, `polisyos.ir.api`, `polisyos.ir.governance`, `polisyos.ir.observation`, `polisyos.ir.connectors`, `polisyos.ir.kernel`, `polisyos.ir.loading`, `polisyos.ir.model_layer`, `polisyos.ir.registry`, `polisyos.ir.trinity`, `polisyos.ir.world`
- Facade policy: expected `lazy_facade`, observed `lazy_facade`
- Owner: `team-polisyos`
- README: `src/polisyos/ir/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Primary compatibility boundary for policy, governance, analytics, and observation contracts; api.py owns public-surface helper metadata.
- Summary: Expose the stable IR contract surface through a lazy package facade.

### Resolved supported entrypoints

| Entrypoint | Source | Facade | Exports |
| --- | --- | --- | ---: |
| `polisyos.ir` | `src/polisyos/ir/__init__.py` | `lazy_facade` | 530 |
| `polisyos.ir.analytics` | `src/polisyos/ir/analytics/__init__.py` | `lazy_facade` | 320 |
| `polisyos.ir.analytics.calibration_diagnostics` | `src/polisyos/ir/analytics/calibration_diagnostics.py` | `eager_exports` | 6 |
| `polisyos.ir.api` | `src/polisyos/ir/api.py` | `eager_exports` | 14 |
| `polisyos.ir.governance` | `src/polisyos/ir/governance/__init__.py` | `lazy_facade` | 106 |
| `polisyos.ir.observation` | `src/polisyos/ir/observation/__init__.py` | `lazy_facade` | 167 |
| `polisyos.ir.connectors` | `src/polisyos/ir/connectors/__init__.py` | `eager_exports` | 52 |
| `polisyos.ir.kernel` | `src/polisyos/ir/kernel/__init__.py` | `lazy_facade` | 81 |
| `polisyos.ir.loading` | `src/polisyos/ir/loading/__init__.py` | `lazy_facade` | 12 |
| `polisyos.ir.model_layer` | `src/polisyos/ir/model_layer/__init__.py` | `lazy_facade` | 6 |
| `polisyos.ir.registry` | `src/polisyos/ir/registry/__init__.py` | `lazy_facade` | 130 |
| `polisyos.ir.trinity` | `src/polisyos/ir/trinity/__init__.py` | `lazy_facade` | 6 |
| `polisyos.ir.world` | `src/polisyos/ir/world/__init__.py` | `lazy_facade` | 54 |

#### `polisyos.ir`

- Source: `src/polisyos/ir/__init__.py`
- Facade: `lazy_facade`
- Summary: Expose the stable IR contract surface through a lazy package facade.

<details><summary>Entrypoint exports (530)</summary>

```text
GATE_REQUEST_SCHEMA_VERSION
SLOT_ID_PATTERN
ABMAlignmentReportRef
ABMBifurcationReport
ABMIdentifiabilityCertificate
ABMResult
ABMResultRef
ATEInferenceBasis
ATEInferenceBasisRef
AbstractionCertificateRef
AccessTier
AdministrativeMissingnessClass
AdministrativeMissingnessDirection
AdministrativeMissingnessMetadata
AdministrativeMissingnessScenarioFamily
AdministrativeMissingnessUnitScope
AgentConfig
AgentTypeConfig
AlgebraicAssumptionStatus
AlgebraicFalsificationScope
AlignmentCertificate
AlignmentCertificateType
AlignmentCertificationPolicy
ArbitrationOption
ArticleExtractionResult
ArtifactID
ArtifactRefModel
ArtifactSelector
ArtifactStore
AssumptionSpec
AssumptionType
BacktestPlanBundle
BacktestReport
BacktestReportRef
BacktestScenario
BiasDirection
BlockSupportReport
BlockingType
BoundMethod
BoundsBundle
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
CanonSpec
CanonViolation
CausalAssumptionCard
CausalAssumptionCardRef
CausalAttributionSpec
CausalBackendId
CausalBlockBridge
CausalBlockBridgeRef
CausalCapabilityContract
CausalCapabilityContractRef
CausalContrastRegime
CausalContrastSpec
CausalDiscoveryReport
CausalEffectReport
CausalEffectReportRef
CausalEstimatorInterval
CausalExecutionBundle
CausalExecutionBundleRef
CausalGraphModel
CausalGraphModelRef
CausalIdentificationFamily
CausalInterventionSpec
CausalMethod
CausalModelEnsemble
CausalModelEnsembleRef
CausalPanelBundleManifest
CausalQuery
CausalQueryResult
CausalQueryResultRef
CausalReadinessBundle
CausalRegime
CausalResultKind
CausalSensitivityResultRef
ChannelDecompositionTargetKind
CohortDimension
CohortImpact
CompiledLexIntervention
ConnectorCapability
ConnectorMetadataSpec
ConstraintSpec
ConstraintType
ContextProfile
CounterfactualCheckBundle
CouplingDiagnostics
CrossGraphEvidenceProfile
DTRTreatmentSequenceBundleManifest
DataFilter
DataGap
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
DiscreteDistributionSummary
DistributionBin
DistributionDomain
DistributionFamily
DistributionLawQuery
DistributionalBoundUniformity
DistributionalBoundsBundle
DistributionalBoundsBundleRef
DistributionalCouplingStatus
DistributionalDualCertificate
DistributionalDualCertificateRef
DistributionalEffectBundleRef
DistributionalFunctional
DistributionalJustification
DistributionalProofArtifact
DistributionalProofArtifactRef
DistributionalProofTarget
DistributionalReport
DriftReadinessRef
DynamicMicrosimValidationReport
DynamicMicrosimValidationReportRef
EnsembleMember
EntityScope
EnvironmentConfig
EnvironmentParam
EquilibriumMultiplicityWelfareAnnotation
EstimandAST
EstimandASTRef
EstimationStatus
EvidenceBundleRef
EvidenceSourceKind
ExplanationBundleRef
ExposureMappingType
FailureSeverity
FanChartSpec
FeatureImportance
FetchRequest
FetchResult
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
HTEInputSourceRef
HTEIntervalOutcome
HTEOutcome
HTEOutcomeRef
HTEPhysicalSourceMaterializationBindingRef
HTEPointEstimate
HTEPointOutcome
HTEPointResult
HTEPointResultRef
HTERefusalDiagnostic
HTERefusalDiagnosticRef
HTERefusalOutcome
HTEResourceExecutionEvidenceV1
HTEResourcePolicyRef
HTEResult
HTEResultEvidenceRef
HTETargetRelationV1
HardConstraintAuditEntry
HorizonInterval
HorizonPolicySpec
ICVerificationMode
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
InputRef
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
InterventionExpr
InterventionQuery
InterventionSpec
InterventionType
JudgeVerdictRef
KPISpec
KernelEstimatorSpecRef
LatentDiscoveryBundle
LeontiefIOBundle
LeontiefIOInput
LessonRegistrySeedBundle
LinkReport
MAUPInvarianceCertificate
MAUPInvarianceCertificateRef
MAUPPartitionCheck
MeasurementRegistry
MeasurementTrustTier
MechanismBinding
MechanismDesignFamily
MechanismFamily
MechanismFamilySpec
MechanismSource
MethodExecutionEvidenceRef
MethodResultEvidenceRef
MetricBiasDiagnostic
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
ModelQueryDataViewRequest
ModelSpec
MultiplexGraphLayerId
NCMSpec
NCMSpecRef
NativeValueEstimandBinding
NegativeCertificate
NegativeCertificateRef
NegativeControlSpec
NetworkCausalContractBundle
NetworkContractBundle
NetworkInterferenceReport
NodeMechanism
NormPack
NormRef
NormRule
NormativeArbitrationPolicy
NormativeArbitrationResult
NormativeArbitrationResultRef
NormativeAuditStatus
NormativeComparisonTarget
NormativeFrame
NormativeModelCompleteness
NormativeOutcomeChannel
OTCouplingSummary
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
OrdinalPovertyEstimate
OrdinalPovertyReport
OrdinalPovertyReportRef
OutcomeComparison
OuterObjectiveResult
OwnedAttemptAnchorRef
PAGIdentificationPolicy
PanelEconometricBundleManifest
ParameterSpec
Phase4DynamicsGate
Phase4GateStatus
Phase4TemporalPolicyGateVerdict
PlaceboResult
PolicyInteraction
PolicyInterventionSpec
PolicyOutcome
PolicyPortfolio
PolicyRecommendation
PolicySpec
PosteriorParameterSummary
PosteriorPointRole
PosteriorSamplesCarrier
PosteriorSummaryRef
PosteriorSummaryV11
PreparedNCMSpecSelectedValues
ProblemConstraintSpec
ProblemDomain
ProblemFrame
ProofBundle
ProofBundleRef
PropagationMethod
ProxyIdentificationBundle
ProxyMap
QualityTier
QuantileShiftEntry
QuantileShiftSummary
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
RightsAuditEntry
RuleType
SCMFitProvenance
SCMTrainingRows
SNode
SNodeOrigin
SchemaChangepoint
SchemaRegimeRegistry
SchemaRegimeSpec
SearchUncertaintyTaskBindingRef
SelectionDiagram
SensitivityAnalysisBundle
SensitivityAnalysisBundleRef
SensitivityAnalysisIndex
ShiftComponent
ShiftDiagnosticReport
ShiftDiagnosticReportRef
ShockCalendar
SlotFamily
SlotFamilyManifest
SlotLayout
SourceConfidenceTier
SpaceTimeCausalCertificate
SpaceTimeCausalCertificateRef
SparseDenseBridge
SpatialResult
SpecificationCurveBundle
SpecificationCurveInput
StakeholderOutcomeBinding
StakeholderSpec
StakeholderUtilitySummary
StrategicResponseBundleRef
StrategicResponseChannel
StrategicResponseSpecsBundle
StrategicSCMRef
StructuralCausalModelSpec
SubgroupDistributionComparison
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
TailRiskDeltaEntry
TailRiskDeltaSummary
TargetingRule
TemporalDTRExecutionEntry
TemporalDTRTask
TemporalGraphCausalCertificate
TemporalGraphCausalCertificateRef
TemporalInterventionSequence
TemporalInterventionStep
TimeFrequency
TransportMode
TransportPrivacyContext
TransportStatus
TransportabilityCheckBundle
TransportabilityResult
TransportabilityResultRef
TransportabilityStatus
TrinityBundle
TrustLevel
TwinNetworkResult
TypedFailureCard
UncertaintyEnvelope
UncertaintyEnvelopeRef
UncertaintySource
UncertaintyType
UtilityDirection
WelfareBundle
WelfareBundleRef
WelfareIntervalSemantics
WelfareMethod
WelfareSampleBundle
WelfareSampleBundleRef
WelfareStatus
WinnersLosersEntry
WinnersLosersTable
apply_transport_privacy_context
attach_distributional_dual_certificate_ref
build_channel_decomposition_ref
build_slot_family_manifest
build_slot_layout
candidate_ncm_spec_from_declaration
coerce_transport_privacy_context
combine_envelopes
compute_manski_bounds
compute_outer_objective
enumerate_ir_exports
get_ir_schema_catalog
get_ir_type
get_json_artifact
get_json_artifact_with_bytes
inspect_ir_schema
list_ir_types
load_abm_alignment_report
load_abstraction_certificate
load_ate_inference_basis
load_backtest_report
load_bounds_bundle
load_causal_capability_contract
load_causal_effect_report
load_causal_evidence_bundle
load_causal_evidence_bundle_with_admission
load_causal_execution_bundle
load_causal_graph_model
load_causal_model_ensemble
load_channel_decomposition_artifact
load_cross_graph_evidence_profile
load_dependence_structure
load_dependent_sensitivity_result
load_distributional_effect_bundle
load_distributional_report
load_forecasting_uncertainty_bundle
load_ge_uncertainty_bundle
load_hte_outcome
load_hte_point_result
load_hte_refusal_diagnostic
load_hte_result
load_hte_result_v2
load_kernel_estimator_spec
load_mean_field_equilibrium_certificate
load_mean_field_macro_simulation_config
load_mean_field_perturbation_spec
load_ncm_spec
load_ncm_spec_selected_view
load_normative_arbitration_result
load_ordinal_poverty_report
load_performative_shift_summary
load_policy
load_policy_recommendation
load_post_adaptation_policy_value_summary
load_posterior_summary
load_sensitivity_result
load_simulation_result_subject_uncertainty_projection
load_simulation_result_uncertainty_admission
load_strategic_decomposition_failure_card
load_strategic_response_bundle
load_strategic_scm
load_uncertainty_envelope
load_welfare_bundle
load_welfare_sample_bundle
normalize_artifact_ref
persist_ate_inference_basis
persist_backtest_report
persist_causal_assumption_card
persist_causal_capability_contract
persist_causal_effect_report
persist_causal_execution_bundle
persist_dependent_sensitivity_result
persist_discrete_distribution_summary
persist_distributional_bounds_bundle
persist_distributional_dual_certificate
persist_distributional_proof_artifact
persist_estimand_ast
persist_forecasting_uncertainty_bundle
persist_ge_uncertainty_bundle
persist_hte_outcome
persist_hte_point_result
persist_hte_refusal_diagnostic
persist_hte_result_v2
persist_ncm_spec_selected_view
persist_negative_certificate
persist_ordinal_poverty_report
persist_ot_coupling_summary
persist_posterior_summary
persist_proof_bundle
persist_quantile_shift_summary
persist_sensitivity_analysis_bundle
persist_structural_causal_model_spec
persist_subgroup_distribution_comparison
persist_tail_risk_delta_summary
persist_twin_network_result
persist_uncertainty_envelope
persist_welfare_bundle
persist_welfare_sample_bundle
prepare_ncm_spec_selected_values
proof_bundle_from_identification_result
proof_bundle_from_negative_certificate
proof_bundle_from_transportability_result
put_json_artifact
run_outer_search
sensitivity_analysis_bundle_from_result
stable_world_id_from_canon
summarize_posterior_draw_artifact
to_canonical_bytes
transportability_proof_review_grade
```

</details>

#### `polisyos.ir.analytics`

- Source: `src/polisyos/ir/analytics/__init__.py`
- Facade: `lazy_facade`
- Summary: Curated lazy facade for analytics IR contracts.

<details><summary>Entrypoint exports (320)</summary>

```text
ABMBifurcationReport
ABMIdentifiabilityCertificate
ABMResult
ABMResultRef
ATEInferenceBasis
ATEInferenceBasisRef
AccessTier
AdministrativeMissingnessClass
AdministrativeMissingnessDirection
AdministrativeMissingnessMetadata
AdministrativeMissingnessScenarioFamily
AdministrativeMissingnessUnitScope
AdmittedClaimAdjudicationBatch
AlignmentReport
BacktestReport
BacktestScenario
BiasDirection
BlockSupportReport
BoundMethod
BoundSoundnessLevel
BoundsBundle
CausalAttributionSpec
CausalBlockBridge
CausalBlockBridgeRef
CausalBridgeTarget
CausalContrastRegime
CausalContrastSpec
CausalCredibility
CausalDecisionProcessType
CausalDiscoveryReport
CausalEdge
CausalEffectReport
CausalEstimatorInterval
CausalGraphModel
CausalInterventionSpec
CausalMethod
CausalModelEnsemble
CausalNexGraphBridge
CausalQuery
CausalQueryResult
CausalRLContract
CausalRLResult
CausalRegime
CausalResultKind
CausalRunSnapshot
ClaimAdjudicationInputBatch
ClaimAdjudicationInputItem
ClaimAdjudicationResult
ClaimType
ClaimVocabularyAxisStatus
CohortDimension
CohortImpact
ContrastiveExplanation
CounterfactualExplanation
CounterfactualLawEstimate
CounterfactualLawLabel
CounterfactualPolicyOptimizationSpec
DPUtilityManifest
DataFilter
DataViewRequest
DataViewType
DependenceStructure
DependenceStructureRef
DependentSensitivityAnalysisBundle
DependentSensitivityAnalysisBundleRef
DependentSensitivityResult
DependentSensitivityResultRef
DesignFamily
DetectorResult
DiagnosticTest
DimensionBreakdown
DistributionFamily
DistributionalReport
DoWhyGraphBridge
DriftReadinessRef
DynamicMicrosimValidationReport
DynamicMicrosimValidationReportRef
DynamicProcessFamily
EconMLDesignBridge
EdgeMark
EdgeSource
EndogenousGroupDecompositionStatus
EndogenousGroupInequalityDecompositionRef
EndogenousGroupInequalityDecompositionResult
EnsembleMember
EnvironmentShiftType
EquilibriumMultiplicityWelfareAnnotation
EquivalenceClassType
EstimationStatus
EvidenceStrength
ExplanationBundleRef
ExposureMappingType
FairnessAuditReport
FanChartSpec
FeatureImportance
FiniteStrategicPayoffTable
ForecastCalibrationMethod
ForecastCoverageDiagnostic
ForecastIntervalSemantics
ForecastShiftTypeAssessment
ForecastingUncertaintyBundle
ForecastingUncertaintyBundleV2
GEUncertaintyBundle
GEUncertaintyBundleRef
GEUncertaintyRepresentation
GraphType
HTEInputSourceRef
HTEIntervalOutcome
HTEOutcome
HTEOutcomeRef
HTEPhysicalSourceMaterializationBindingRef
HTEPointEstimate
HTEPointOutcome
HTEPointResult
HTEPointResultRef
HTERefusalDiagnostic
HTERefusalDiagnosticRef
HTERefusalOutcome
HTEResourceExecutionEvidenceV1
HTEResourcePolicyRef
HTEResult
HTEResultEvidenceRef
HTETargetRelationV1
HorizonInterval
HorizonPolicySpec
ImpactDirection
InteractionComplex
InteractionComplexRef
InterferenceCertificate
InterferenceCertificateRef
InterferenceEffectDecomposition
InterferenceMethod
IntervalSemantics
InterventionCertificate
InterventionQuery
InterventionSpec
InterventionType
InvarianceMethod
InvarianceResult
InvarianceVerdict
JointDecisionCertificate
JointDecisionStatus
JudgeVerdictRef
KernelEstimatorSpec
KernelEstimatorSpecRef
KernelEstimatorTemplate
KernelLoweringDisposition
KernelSpec
KernelTargetRepresentation
LatentConfounderContract
MAUPInvarianceCertificate
MAUPInvarianceCertificateRef
MAUPPartitionCheck
MeanFieldEquilibriumCertificate
MeanFieldMacroSimulationConfig
MeanFieldPerturbationSpec
MechanismFamily
MechanismSource
MethodExecutionEvidenceRef
MethodResultEvidenceRef
MetricBiasDiagnostic
MetricUnit
MetricValidationReport
MicrosimCalibrationReport
MicrosimCalibrationReportRef
MissingnessAssessmentProvenance
MissingnessAssessmentReport
MissingnessAssessmentStatus
MissingnessEstimandRisk
MissingnessEvidenceItem
MobilityReport
MobilityReportRef
MultiEnvironmentCausalContract
NetworkInterferenceReport
NodeMechanism
OperatingCharacteristicKey
OperatingCharacteristicLibrary
OperatingCharacteristicRecord
OutcomeComparison
OwnedAttemptAnchorRef
PAGIdentificationPolicy
PerformativeInstabilityReason
PerformativeLoopAnalysisScope
PerformativeLoopCertificate
PerformativeLoopProofFamily
PerformativeLoopRecommendedAction
PerformativeLoopStabilityStatus
PerformativeLoopWitnessStrength
PerformativeShiftSummary
PgmpyGraphBridge
Phase4DynamicsGate
Phase4GateStatus
Phase4TemporalPolicyGateVerdict
PlaceboResult
PolicyRecommendation
PosteriorParameterSummary
PosteriorPointRole
PosteriorSummaryRef
PosteriorSummaryV11
PrivacyAwareTransportCertificate
PrivacyAwareTransportCertificateRef
PrivacyObservedMode
ProofKernelInterventionType
PropagationMethod
QueryType
ReadinessImpact
ReconciliationCertificate
ReconciliationMethod
ReconciliationStatus
RecourseAction
RecourseActionType
RecourseFeasibility
RecoursePlan
RecourseReport
RecoverabilityCertificate
RecoverabilityCertificateStatus
ReferencePopulation
RefutationResult
RefutationTestType
RegimeBenchmarkStatus
RegimeForecastCalibrationStatus
RegimeIdentifiabilityStatus
RegimeModelFamily
RegimeShiftForecastBundle
RegimeShiftForecastBundleRef
RegimeShiftIdentificationCertificate
RegimeShiftIdentificationCertificateRef
RepresentationLearningResult
RepresentationModelFamily
RiskOfBias
ScalarEstimandEstimate
SearchUncertaintyTaskBindingRef
SensitivityAnalysisBundle
SensitivityAnalysisBundleRef
SensitivityAnalysisIndex
ShiftComponent
ShiftDiagnosticReport
ShiftDiagnosticReportRef
SourceBasis
SpaceTimeCausalCertificate
SpaceTimeCausalCertificateRef
SpatialResult
StrategicAdmissibilityRecord
StrategicDecompositionCertificate
StrategicDecompositionFailureCard
StrategicDecompositionSemantics
StrategicDecompositionStatus
StrategicEquilibriumConcept
StrategicEquilibriumDescriptor
StrategicFallbackMode
StrategicGameClass
StrategicResponseBundle
StrategicSCM
StrategicSolutionConcept
StrategicTractabilityClass
StructuralCausalModelSpec
SubgroupEffect
SupportStatus
SurveyAssumptionComponent
SurveyAssumptionLayer
SurveyAssumptionStatus
SurveyQualityCertificate
SurveyQualityCertificateRef
SurveyRakingCategoryDiagnostic
SurveyRakingDiagnosticReport
SurveyRakingIteration
SurveyRequestedRegime
SurveyValidatedRegime
SurveyVarianceMode
SystematicBias
TargetingRule
TemporalDiscoveryEdge
TemporalDiscoveryFrontierReport
TemporalDiscoveryMethod
TemporalGraphCausalCertificate
TemporalGraphCausalCertificateRef
TigramiteEdge
TigramitePCMCIBridge
TransportabilityResult
TruthfulnessReceipt
TruthfulnessScope
TruthfulnessStatus
TruthfulnessTier
UncertaintyEnvelope
UncertaintySource
VersionedClaimVocabularyEnvelope
WelfareBundle
WelfareBundleRef
WelfareIntervalSemantics
WelfareMethod
WelfareSampleBundle
WelfareSampleBundleRef
WelfareStatus
WinnersLosersEntry
WinnersLosersTable
adapt_legacy_claim_occurrence_as_v2_absence
extract_truthfulness_receipt
load_ate_inference_basis
load_dependent_sensitivity_result
load_hte_outcome
load_hte_point_result
load_hte_refusal_diagnostic
load_hte_result_v2
parse_truthfulness_scope
parse_truthfulness_status
parse_truthfulness_tier
persist_ate_inference_basis
persist_dependent_sensitivity_result
persist_hte_outcome
persist_hte_point_result
persist_hte_refusal_diagnostic
persist_hte_result_v2
reconcile_truthfulness_tiers
to_causalnex_graph_bridge
to_dowhy_graph_bridge
to_econml_design_bridge
to_pgmpy_graph_bridge
to_tigramite_pcmci_bridge
truthfulness_depth
validate_truthfulness_receipt
```

</details>

#### `polisyos.ir.analytics.calibration_diagnostics`

- Source: `src/polisyos/ir/analytics/calibration_diagnostics.py`
- Facade: `eager_exports`
- Summary: Typed IR contracts for probabilistic calibration diagnostics.

<details><summary>Entrypoint exports (6)</summary>

```text
CalibrationCurveBin
CalibrationDiagnosticIssue
CalibrationDiagnosticsReport
CalibrationMetricInterval
CalibrationMetrics
CalibrationTestResult
```

</details>

#### `polisyos.ir.api`

- Source: `src/polisyos/ir/api.py`
- Facade: `eager_exports`
- Summary: Machine-readable manifest for the documented IR package facades.

<details><summary>Entrypoint exports (14)</summary>

```text
ANALYTICS_FACADE_EXPORTS
IR_NAMING_CONVENTIONS
KERNEL_FACADE_EXPORTS
LOADING_FACADE_EXPORTS
MODEL_LAYER_FACADE_EXPORTS
PACKAGE_FACADE_EXPORTS
PACKAGE_FACADE_IMPORT_POLICY
REGISTRY_FACADE_EXPORTS
WORLD_FACADE_EXPORTS
LazyExportMap
RegistryItemId
facade_export_names
lazy_dir
resolve_lazy_export
```

</details>

#### `polisyos.ir.governance`

- Source: `src/polisyos/ir/governance/__init__.py`
- Facade: `lazy_facade`
- Summary: Expose the governance-side IR contracts for Trinity policy authoring.

<details><summary>Entrypoint exports (106)</summary>

```text
BayesianTypeSpec
CompiledLexIntervention
ConstraintSpec
ConstraintType
ExactJointPriorEntry
ExactPlayerPriorSpec
ExtensiveFormNode
FiniteOutcomeRuleEntry
FiniteOutcomeSpec
FiniteUtilityTableEntry
FiniteValueTableEntry
GateContext
GateDecision
GateEvent
GateEventType
GatePriority
GateRequest
GateVerdict
InterventionSpec
KPISpec
MechanismBinding
MechanismConstraintType
MechanismDesignConstraint
MechanismDesignSpec
MechanismGameRepresentation
MechanismOutcomeMode
MechanismPriorKind
MechanismPriorSpec
MechanismRevelationMode
MechanismSemanticsSpec
MechanismUtilityModelKind
MechanismUtilityModelSpec
NormativeArbitrationPolicy
NormativeComparisonMode
NormativeComparisonTarget
NormativeFrame
NormativeOutcomeChannel
ObjectiveSpec
ParameterSpec
Phase1GateSummary
Phase5GateComponent
Phase5GateWaiver
PolicyCompatibilityConstraint
PolicyCompatibilityMode
PolicyCompositionPlan
PolicyLayerLevel
PolicyLayerSpec
PolicyOverrideMode
PolicyOverrideRule
PolicySearchLevel
PolicySpec
PolicyVersioningMode
ProblemDomain
ProblemFrame
RepeatedGameHorizon
RepeatedGameMetadata
ScheduleSpec
SelectorAggregate
SelectorAggregationFunction
SelectorAll
SelectorAny
SelectorExpr
SelectorNot
SelectorPredicate
SelectorQuantifier
SelectorQuantifierKind
SelectorScalar
SelectorTemporalOperator
SelectorTemporalPredicate
SelectorValue
StakeholderOutcomeBinding
StakeholderRightSpec
StakeholderSpec
StakeholderUtilityTerm
SuccessCriterion
TemporalAll
TemporalAny
TemporalAtom
TemporalBinaryFormula
TemporalBinaryOperator
TemporalBoundedFormula
TemporalEvaluationScope
TemporalExecutionSemantics
TemporalInterventionSequence
TemporalInterventionStep
TemporalLogicExpr
TemporalLogicFamily
TemporalNot
TemporalPathFormula
TemporalPathQuantifier
TemporalPolicyConstraint
TemporalTimeDomain
TemporalUnaryFormula
TemporalUnaryOperator
UtilityDirection
ValidationIssue
ValidationReport
build_phase1_gate_summary
build_validation_report
diff_payloads
issues_from_validation_error
load_phase1_flagship_dataset_ids
load_validation_report
persist_validation_report
schedule_range
summarize_issues
```

</details>

#### `polisyos.ir.observation`

- Source: `src/polisyos/ir/observation/__init__.py`
- Facade: `lazy_facade`
- Summary: Expose the observation contract stack through a lazy package facade.

<details><summary>Entrypoint exports (167)</summary>

```text
BACKTEST_PLAN_TARGET
DEFAULT_GOVERNANCE_PASS_ALIAS_REGISTRY
DEFAULT_GOVERNANCE_PASS_MAPPING_REGISTRY
DEFAULT_OBSERVATION_FAMILY_POLICY_REGISTRY
DYNAMIC_TREATMENT_TARGET
LESSON_CARD_TARGET
MULTIPLEX_NETWORK_TARGET
NETWORK_ANALYSIS_TARGET
NETWORK_DATA_TARGET
OBSERVATION_METHOD_INPUT_KIND
PANEL_ECONOMETRIC_TARGET
PANEL_OBSERVATIONAL_TARGET
PROXY_MEASUREMENT_TARGET
SECTION_15_7_BUNDLE_MODELS
SURVEY_MICRODATA_TARGET
SURVIVAL_DATA_TARGET
AgentFactorEmbeddingsBundleManifest
BacktestPlanBundle
BilevelProblemBundle
BoundsChannelSpec
BoundsEstimationBundle
BoundsEstimationCompileSpec
BoundsEstimationEntry
BoundsEstimationInput
BoundsEstimationTask
BoundsInputCompiler
BundleAxisSemantic
BundleLineageRef
CalibrationSplitLabel
CalibrationSplitPlan
CalibrationSplitWindow
CalibrationSplitter
CalibrationTargetBundleManifest
CausalExecutionBundle
CausalPanelBundleManifest
CausalReadinessBundle
CdiscDatasetBridge
CellPrototypeEmbeddingsBundleManifest
CompiledObservationArtifact
ContractCompatibilityTarget
CounterfactualCheckBundle
CounterfactualCheckEntry
CounterfactualCheckSpec
DTRTreatmentSequenceBundleManifest
DdiVariableBridge
DynamicTreatmentCompileSpec
DynamicTreatmentCompiler
EntityScope
FhirObservationBridge
FhirQuantityBridge
FirmEventRecord
FirmEvents
FirmPanelRow
FirmPanels
GovernancePassAlias
GovernancePassAliasRegistry
GovernancePassAliasStatus
GovernancePassMappingBundle
GovernancePassMappingRegistry
GraphArtifacts
GraphBipartiteEdge
GraphEdge
HeckmanCorrectionBundle
HistoricalValidationCompilation
HistoricalValidationCompileSpec
HistoricalValidationPlanCompiler
IdentificationMode
IdentificationModeRouter
IdentificationRoute
InterferenceLossSpecBundle
InterferenceLossTargetSpec
InterferenceReadinessEntry
LeontiefIOBundle
LeontiefIOCompileSpec
LeontiefIOCompiler
LeontiefIOInput
LessonRegistrySeedBundle
LessonRegistrySeedEntry
MeasurementRegistry
MeasurementTierRule
MeasurementTrustTier
MicrosimSurveyContractBundle
MultiplexGraphLayerId
NegativeControlSpec
NetworkCausalCompileSpec
NetworkCausalContractBundle
NetworkCausalDataCompiler
NetworkContractBundle
NetworkContractCompileSpec
NetworkContractCompiler
ObservationBridgeStandard
ObservationCompilerContext
ObservationContractArtifact
ObservationContractCompileError
ObservationContractCompilerSuite
ObservationContractRoute
ObservationContractSuiteResult
ObservationFamily
ObservationFamilyPolicy
ObservationFamilyPolicyRegistry
ObservationMethodInputEnvelope
ObservationPanel
ObservationRecord
ObservationToContractManifest
PanelEconometricBundleManifest
PanelEconometricCompileSpec
PanelEconometricCompiler
PanelObservationalCompileSpec
PanelObservationalCompiler
ProxyChannelSpec
ProxyIdentificationBundle
ProxyIdentificationEntry
ProxyMap
ProxyMappingRule
ProxyMeasurementCompileSpec
ProxyMeasurementCompiler
RegimeCalendar
RegimeCalendarEntry
RegionSectorFlowRow
RegionSectorPanels
RequiredArraySpec
RequiredColumnSpec
SchemaChangepoint
SchemaRegimeRegistry
SchemaRegimeSpec
SdmxObservationBridge
ShockCalendar
ShockCalendarEntry
SobolDiagnosticsBundle
SourceConfidenceTier
SparseDenseBridge
SpecificationCurveBundle
SpecificationCurveCompileSpec
SpecificationCurveCompiler
SpecificationCurveDiagnosticsBundle
SpecificationCurveInput
SpecificationCurveSource
SpecificationCurveSourceSpec
StrategicResponseChannel
StrategicResponseEntry
StrategicResponseSpec
StrategicResponseSpecsBundle
SurveyMicroDataCompileSpec
SurveyMicroDataCompiler
SurvivalCompileSpec
SurvivalDataBundleManifest
SurvivalDataCompiler
SurvivalHazardBundle
TemporalDTRExecutionEntry
TemporalDTRTask
TransportabilityCheckBundle
TransportabilityCheckEntry
TransportabilityCheckSpec
bridge_observation_panel_to_cdisc
bridge_observation_record_to_ddi
bridge_observation_record_to_fhir
bridge_observation_record_to_sdmx
load_causal_execution_bundle
load_causal_readiness_bundle
load_json_bundle
load_npz_payload
load_parquet_rows
persist_causal_execution_bundle
persist_causal_readiness_bundle
write_json_bundle
write_npz_payload
write_parquet_rows
```

</details>

#### `polisyos.ir.connectors`

- Source: `src/polisyos/ir/connectors/__init__.py`
- Facade: `eager_exports`
- Summary: Canonical connector contracts for the data fabric layer.

<details><summary>Entrypoint exports (52)</summary>

```text
UTC
Any
BaseModel
CapabilitySet
ClassVar
ConfigDict
ConnectorCapability
ConnectorDocumentationSpec
ConnectorGovernanceProfile
ConnectorIdentitySpec
ConnectorMetadataSpec
ConnectorOperationalProfile
ConnectorQualityGovernanceSpec
ConnectorSLASpec
ConnectorSchemaGovernanceSpec
ConnectorSourceSpec
DataT
DataVersion
Enum
EvidenceBundleRef
FetchPaginationEnvelope
FetchProvenanceEnvelope
FetchQualityEnvelope
FetchRequest
FetchResult
FetchSchemaDescriptor
FetchTransferEnvelope
Field
Flag
IntEnum
PIIDetectedEntity
PIIScanSummary
PrivateAttr
Protocol
QualityTier
ResilienceInfo
TrustLevel
TypeVar
VersionStrategy
annotations
auto
cached_property
capabilities_from_flags
content_hash
dataclass
datetime
field
field_validator
flags_from_capabilities
model_validator
overload
to_canonical_bytes
```

</details>

#### `polisyos.ir.kernel`

- Source: `src/polisyos/ir/kernel/__init__.py`
- Facade: `lazy_facade`
- Summary: Stable registry facade for kernel slots, units, metrics, and merge contracts.

<details><summary>Entrypoint exports (81)</summary>

```text
ConflictResolution
ConstraintRegistry
ConstraintSpec
CountUnit
CountValue
DEFAULT_CONSTRAINT_REGISTRY
DEFAULT_MECHANISM_REGISTRY
DEFAULT_MERGE_RULE_REGISTRY
DEFAULT_METRIC_REGISTRY
DEFAULT_SELECTOR_FIELD_REGISTRY
DEFAULT_SLOT_REGISTRY
DEFAULT_TRUST_REGISTRY
DEFAULT_UNITS_REGISTRY
DecimalValue
DimensionlessUnit
DurationUnit
DurationValue
GenericUnit
ID_PATTERN
KernelModel
METHOD_METRIC_DIRECT_OUTPUT_LAW_ID
METHOD_METRIC_DIRECT_OUTPUT_LAW_VERSION
METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_ID
METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_VERSION
METHOD_METRIC_UNIT_ADAPTER_ID
METHOD_METRIC_UNIT_ADAPTER_VERSION
MechanismTypeRegistry
MechanismTypeSpec
MergeOverride
MergeRuleKind
MergeRuleRef
MergeRuleRegistry
MergeRuleSpec
MethodMetricBackendAttempt
MethodMetricCapturedInputArray
MethodMetricExecutionContext
MethodMetricInputContext
MethodMetricInputRole
MethodMetricInputRoleContext
MethodMetricParameterContext
MethodMetricPredicateEvidence
MethodMetricSemanticContract
MethodMetricSourceUnit
MetricRegistry
MetricSpec
MoneyUnit
MoneyValue
NonNegativeDecimal
ParamSpec
ParamType
ParamValue
PositiveDecimal
RateUnit
RateValue
RegisteredMethodMetricLawResult
RegisteredMethodMetricUnitAdapter
RegisteredMethodMetricUnitResult
SLOT_ID_PATTERN
SelectorFieldRegistry
SelectorFieldSpec
SlotKind
SlotRegistry
SlotScope
SlotSpec
SlotValueType
TimeSemantics
TrustPolicySpec
TrustRegistry
UnitKind
UnitRef
UnitSpecType
UnitsRegistry
apply_registered_direct_output_law
apply_registered_ex_ante_mean_change_law
apply_registered_method_metric_unit_adapter
registered_method_metric_input_unit_contract
registered_method_metric_law_metadata
registered_method_metric_law_metadata_for
registered_method_metric_semantics_match
registered_method_metric_unit_adapter_metadata
resolve_registered_method_metric_unit_adapter
```

</details>

#### `polisyos.ir.loading`

- Source: `src/polisyos/ir/loading/__init__.py`
- Facade: `lazy_facade`
- Summary: Owner-curated lazy facade for IR loading and source-citation contracts.

<details><summary>Entrypoint exports (12)</summary>

```text
AnchorKind
CitationRef
DocumentRef
Fact
FactBatch
FactLegal
FactPIIEntity
FactProvenance
FactSegmentManifest
FactTrust
FragmentLocator
build_fact_id
```

</details>

#### `polisyos.ir.model_layer`

- Source: `src/polisyos/ir/model_layer/__init__.py`
- Facade: `lazy_facade`
- Summary: Lazy public facade for shared IR model-layer vocabulary.

<details><summary>Entrypoint exports (6)</summary>

```text
EntityType
OptimizationDirection
SelectorOperator
TimeFrequency
TimeUnit
TranslatableString
```

</details>

#### `polisyos.ir.registry`

- Source: `src/polisyos/ir/registry/__init__.py`
- Facade: `lazy_facade`
- Summary: Lazy public facade for the owner-curated IR typed-reference family.

<details><summary>Entrypoint exports (130)</summary>

```text
ABMAlignmentReportRef
ABMResultRef
ATEInferenceBasisRef
AbstractionCertificateRef
AlignmentReportRef
ArtifactRefModel
BacktestReportRef
BoundsBundleRef
BoundsTighteningLogRef
BridgePlausibilityReportRef
CausalAssumptionCardRef
CausalBlockBridgeRef
CausalCapabilityContractRef
CausalDiscoveryReportRef
CausalEffectReportRef
CausalExecutionBundleRef
CausalGraphModelRef
CausalModelEnsembleRef
CausalQueryResultRef
CausalReadinessBundleRef
CausalSensitivityResultRef
ChannelDecompositionArtifactRef
CompositionCertificateRef
CompositionFailureCardBundleRef
ContextAdaptiveParameterBundleRef
ContinuousTimeQueryRef
CounterfactualResultRef
CrossGraphEvidenceProfileRef
DPRobustnessCertificateRef
DataReadinessReportRef
DependenceStructureRef
DistributionalBoundsBundleRef
DistributionalDualCertificateRef
DistributionalEffectBundleRef
DistributionalProofArtifactRef
DistributionalReportRef
DriftReadinessRef
DualCertificateRef
DynamicMicrosimValidationReportRef
DynamicTreatmentRegimeRef
EffectTrajectoryBundleRef
EndogenousGroupInequalityDecompositionRef
EstimandASTRef
EvidenceBundleRef
ExplanationBundleRef
FairnessAuditReportRef
FiniteStateAbstractionMapRef
FiscalFeedbackLinkRef
ForecastInterventionCertificateRef
ForecastInterventionQueryRef
ForecastingUncertaintyBundleRef
FrontierSketchRef
GEUncertaintyBundleRef
HTEInputSourceRef
HTEOutcomeRef
HTEPhysicalSourceMaterializationBindingRef
HTEPointResultRef
HTERefusalDiagnosticRef
HTEResourcePolicyRef
HTEResultEvidenceRef
HTEResultRef
IncentiveCompatibilityCertificateRef
InteractionComplexRef
InterfaceMappingRef
InterferenceCertificateRef
InterventionCertificateRef
InterventionCostManifoldRef
InterventionQueryRef
JointDecisionCertificateRef
JudgeVerdictRef
KernelEstimatorSpecRef
LatentBridgeHypothesisRef
LiteratureCausalPriorRef
LocalIndependenceWeightingCertificateRef
MAUPInvarianceCertificateRef
MeanFieldEquilibriumCertificateRef
MeanFieldMacroSimulationConfigRef
MeanFieldPerturbationSpecRef
MechanismFamilySpecRef
MechanismWelfareLossBoundRef
MethodExecutionEvidenceRef
MethodResultEvidenceRef
MetricValidationReportRef
MicrosimCalibrationReportRef
MobilityReportRef
NCMSpecRef
NegativeCertificateRef
NormativeArbitrationResultRef
OperatorEffectBundleRef
OptimalRecourseInterventionBundleRef
OptimalRecourseInterventionQueryRef
OptimizationAmbiguityCertificateRef
OrdinalPovertyReportRef
OwnedAttemptAnchorRef
PolicyRecommendationRef
PrivacyAwareTransportCertificateRef
ProofBundleRef
ProofComposabilityCertificateRef
ProofWitnessIndexRef
ProximalIdentificationCertificateRef
RecourseFeasibilityCertificateRef
RecourseProofBundleRef
RecoverabilityCertificateRef
RegimeShiftForecastBundleRef
RegimeShiftIdentificationCertificateRef
RoughPathInterventionCertificateRef
SCMFragmentRef
SearchUncertaintyTaskBindingRef
SensitivityAnalysisBundleRef
ShiftDiagnosticReportRef
SimulationCalibrationReceiptRef
SimulationProofBridgeRef
SocialWeightManifestRef
SpaceTimeCausalCertificateRef
SpatialHodgeDiagnosticsRef
StrategicPayoffTableRef
StrategicResponseBundleRef
StrategicSCMRef
StructuralCausalModelSpecRef
SurveyQualityCertificateRef
TemporalGraphCausalCertificateRef
TemporalIdentificationCertificateRef
TemporalInterventionTrajectoryRef
TransportabilityResultRef
TwinNetworkResultRef
UncertaintyEnvelopeRef
ValidationReportRef
VariableAlignmentCertificateRef
WelfareBundleRef
WelfareSampleBundleRef
```

</details>

#### `polisyos.ir.trinity`

- Source: `src/polisyos/ir/trinity/__init__.py`
- Facade: `lazy_facade`
- Summary: Bundle the three Trinity artifacts as one validated policy payload.

<details><summary>Entrypoint exports (6)</summary>

```text
TRINITY_BUNDLE_SCHEMA_VERSION
ModelSpec
PolicySpec
ProblemFrame
TrinityBundle
load_trinity_bundle_artifact
```

</details>

#### `polisyos.ir.world`

- Source: `src/polisyos/ir/world/__init__.py`
- Facade: `lazy_facade`
- Summary: Lazy public facade for world-model claims, provenance, ids, and quality records.

<details><summary>Entrypoint exports (54)</summary>

```text
Claim
ClaimSourceKind
ConflictKind
ConflictResolution
ConflictResolutionCandidate
ConflictResolutionInputs
ConflictSet
ConflictSetResolution
DocFragment
DocMeta
EdgeKind
EventKind
NodeKind
ProvActivity
ProvActivityType
ProvAgent
ProvAgentType
ProvOActivityRecord
ProvOAgent
ProvODocument
ProvOEntity
ProvORecordType
ProvORelation
ProvORelationType
QualityIssue
QualityIssueSeverity
QualityReport
QualityScope
RESERVED_WORLD_PREFIXES_V1
TrustAssessment
TrustTier
WORLD_ARTIFACT_ID
WORLD_KIND
WORLD_LABEL
WORLD_PROPS_REF
WORLD_REL_PREFIX
WorldEvent
WorldObjectRef
artifact_id_to_world_id
claim_id_from_payload
conflict_set_id_from_key
doc_fragment_id
doc_source_id
doc_version_id_from_raw_artifact
quality_report_id_from_payload
rel
sha256_hex_from_artifact_id
stable_world_id_from_canon
to_prov_o_activity
to_prov_o_agent
to_prov_o_entity
to_prov_o_world_event
trust_assessment_id_from_payload
world_event_id_from_payload
```

</details>

<details><summary>Supported exports (530)</summary>

```text
GATE_REQUEST_SCHEMA_VERSION
SLOT_ID_PATTERN
ABMAlignmentReportRef
ABMBifurcationReport
ABMIdentifiabilityCertificate
ABMResult
ABMResultRef
ATEInferenceBasis
ATEInferenceBasisRef
AbstractionCertificateRef
AccessTier
AdministrativeMissingnessClass
AdministrativeMissingnessDirection
AdministrativeMissingnessMetadata
AdministrativeMissingnessScenarioFamily
AdministrativeMissingnessUnitScope
AgentConfig
AgentTypeConfig
AlgebraicAssumptionStatus
AlgebraicFalsificationScope
AlignmentCertificate
AlignmentCertificateType
AlignmentCertificationPolicy
ArbitrationOption
ArticleExtractionResult
ArtifactID
ArtifactRefModel
ArtifactSelector
ArtifactStore
AssumptionSpec
AssumptionType
BacktestPlanBundle
BacktestReport
BacktestReportRef
BacktestScenario
BiasDirection
BlockSupportReport
BlockingType
BoundMethod
BoundsBundle
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
CanonSpec
CanonViolation
CausalAssumptionCard
CausalAssumptionCardRef
CausalAttributionSpec
CausalBackendId
CausalBlockBridge
CausalBlockBridgeRef
CausalCapabilityContract
CausalCapabilityContractRef
CausalContrastRegime
CausalContrastSpec
CausalDiscoveryReport
CausalEffectReport
CausalEffectReportRef
CausalEstimatorInterval
CausalExecutionBundle
CausalExecutionBundleRef
CausalGraphModel
CausalGraphModelRef
CausalIdentificationFamily
CausalInterventionSpec
CausalMethod
CausalModelEnsemble
CausalModelEnsembleRef
CausalPanelBundleManifest
CausalQuery
CausalQueryResult
CausalQueryResultRef
CausalReadinessBundle
CausalRegime
CausalResultKind
CausalSensitivityResultRef
ChannelDecompositionTargetKind
CohortDimension
CohortImpact
CompiledLexIntervention
ConnectorCapability
ConnectorMetadataSpec
ConstraintSpec
ConstraintType
ContextProfile
CounterfactualCheckBundle
CouplingDiagnostics
CrossGraphEvidenceProfile
DTRTreatmentSequenceBundleManifest
DataFilter
DataGap
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
DiscreteDistributionSummary
DistributionBin
DistributionDomain
DistributionFamily
DistributionLawQuery
DistributionalBoundUniformity
DistributionalBoundsBundle
DistributionalBoundsBundleRef
DistributionalCouplingStatus
DistributionalDualCertificate
DistributionalDualCertificateRef
DistributionalEffectBundleRef
DistributionalFunctional
DistributionalJustification
DistributionalProofArtifact
DistributionalProofArtifactRef
DistributionalProofTarget
DistributionalReport
DriftReadinessRef
DynamicMicrosimValidationReport
DynamicMicrosimValidationReportRef
EnsembleMember
EntityScope
EnvironmentConfig
EnvironmentParam
EquilibriumMultiplicityWelfareAnnotation
EstimandAST
EstimandASTRef
EstimationStatus
EvidenceBundleRef
EvidenceSourceKind
ExplanationBundleRef
ExposureMappingType
FailureSeverity
FanChartSpec
FeatureImportance
FetchRequest
FetchResult
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
HTEInputSourceRef
HTEIntervalOutcome
HTEOutcome
HTEOutcomeRef
HTEPhysicalSourceMaterializationBindingRef
HTEPointEstimate
HTEPointOutcome
HTEPointResult
HTEPointResultRef
HTERefusalDiagnostic
HTERefusalDiagnosticRef
HTERefusalOutcome
HTEResourceExecutionEvidenceV1
HTEResourcePolicyRef
HTEResult
HTEResultEvidenceRef
HTETargetRelationV1
HardConstraintAuditEntry
HorizonInterval
HorizonPolicySpec
ICVerificationMode
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
InputRef
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
InterventionExpr
InterventionQuery
InterventionSpec
InterventionType
JudgeVerdictRef
KPISpec
KernelEstimatorSpecRef
LatentDiscoveryBundle
LeontiefIOBundle
LeontiefIOInput
LessonRegistrySeedBundle
LinkReport
MAUPInvarianceCertificate
MAUPInvarianceCertificateRef
MAUPPartitionCheck
MeasurementRegistry
MeasurementTrustTier
MechanismBinding
MechanismDesignFamily
MechanismFamily
MechanismFamilySpec
MechanismSource
MethodExecutionEvidenceRef
MethodResultEvidenceRef
MetricBiasDiagnostic
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
ModelQueryDataViewRequest
ModelSpec
MultiplexGraphLayerId
NCMSpec
NCMSpecRef
NativeValueEstimandBinding
NegativeCertificate
NegativeCertificateRef
NegativeControlSpec
NetworkCausalContractBundle
NetworkContractBundle
NetworkInterferenceReport
NodeMechanism
NormPack
NormRef
NormRule
NormativeArbitrationPolicy
NormativeArbitrationResult
NormativeArbitrationResultRef
NormativeAuditStatus
NormativeComparisonTarget
NormativeFrame
NormativeModelCompleteness
NormativeOutcomeChannel
OTCouplingSummary
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
OrdinalPovertyEstimate
OrdinalPovertyReport
OrdinalPovertyReportRef
OutcomeComparison
OuterObjectiveResult
OwnedAttemptAnchorRef
PAGIdentificationPolicy
PanelEconometricBundleManifest
ParameterSpec
Phase4DynamicsGate
Phase4GateStatus
Phase4TemporalPolicyGateVerdict
PlaceboResult
PolicyInteraction
PolicyInterventionSpec
PolicyOutcome
PolicyPortfolio
PolicyRecommendation
PolicySpec
PosteriorParameterSummary
PosteriorPointRole
PosteriorSamplesCarrier
PosteriorSummaryRef
PosteriorSummaryV11
PreparedNCMSpecSelectedValues
ProblemConstraintSpec
ProblemDomain
ProblemFrame
ProofBundle
ProofBundleRef
PropagationMethod
ProxyIdentificationBundle
ProxyMap
QualityTier
QuantileShiftEntry
QuantileShiftSummary
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
RightsAuditEntry
RuleType
SCMFitProvenance
SCMTrainingRows
SNode
SNodeOrigin
SchemaChangepoint
SchemaRegimeRegistry
SchemaRegimeSpec
SearchUncertaintyTaskBindingRef
SelectionDiagram
SensitivityAnalysisBundle
SensitivityAnalysisBundleRef
SensitivityAnalysisIndex
ShiftComponent
ShiftDiagnosticReport
ShiftDiagnosticReportRef
ShockCalendar
SlotFamily
SlotFamilyManifest
SlotLayout
SourceConfidenceTier
SpaceTimeCausalCertificate
SpaceTimeCausalCertificateRef
SparseDenseBridge
SpatialResult
SpecificationCurveBundle
SpecificationCurveInput
StakeholderOutcomeBinding
StakeholderSpec
StakeholderUtilitySummary
StrategicResponseBundleRef
StrategicResponseChannel
StrategicResponseSpecsBundle
StrategicSCMRef
StructuralCausalModelSpec
SubgroupDistributionComparison
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
TailRiskDeltaEntry
TailRiskDeltaSummary
TargetingRule
TemporalDTRExecutionEntry
TemporalDTRTask
TemporalGraphCausalCertificate
TemporalGraphCausalCertificateRef
TemporalInterventionSequence
TemporalInterventionStep
TimeFrequency
TransportMode
TransportPrivacyContext
TransportStatus
TransportabilityCheckBundle
TransportabilityResult
TransportabilityResultRef
TransportabilityStatus
TrinityBundle
TrustLevel
TwinNetworkResult
TypedFailureCard
UncertaintyEnvelope
UncertaintyEnvelopeRef
UncertaintySource
UncertaintyType
UtilityDirection
WelfareBundle
WelfareBundleRef
WelfareIntervalSemantics
WelfareMethod
WelfareSampleBundle
WelfareSampleBundleRef
WelfareStatus
WinnersLosersEntry
WinnersLosersTable
apply_transport_privacy_context
attach_distributional_dual_certificate_ref
build_channel_decomposition_ref
build_slot_family_manifest
build_slot_layout
candidate_ncm_spec_from_declaration
coerce_transport_privacy_context
combine_envelopes
compute_manski_bounds
compute_outer_objective
enumerate_ir_exports
get_ir_schema_catalog
get_ir_type
get_json_artifact
get_json_artifact_with_bytes
inspect_ir_schema
list_ir_types
load_abm_alignment_report
load_abstraction_certificate
load_ate_inference_basis
load_backtest_report
load_bounds_bundle
load_causal_capability_contract
load_causal_effect_report
load_causal_evidence_bundle
load_causal_evidence_bundle_with_admission
load_causal_execution_bundle
load_causal_graph_model
load_causal_model_ensemble
load_channel_decomposition_artifact
load_cross_graph_evidence_profile
load_dependence_structure
load_dependent_sensitivity_result
load_distributional_effect_bundle
load_distributional_report
load_forecasting_uncertainty_bundle
load_ge_uncertainty_bundle
load_hte_outcome
load_hte_point_result
load_hte_refusal_diagnostic
load_hte_result
load_hte_result_v2
load_kernel_estimator_spec
load_mean_field_equilibrium_certificate
load_mean_field_macro_simulation_config
load_mean_field_perturbation_spec
load_ncm_spec
load_ncm_spec_selected_view
load_normative_arbitration_result
load_ordinal_poverty_report
load_performative_shift_summary
load_policy
load_policy_recommendation
load_post_adaptation_policy_value_summary
load_posterior_summary
load_sensitivity_result
load_simulation_result_subject_uncertainty_projection
load_simulation_result_uncertainty_admission
load_strategic_decomposition_failure_card
load_strategic_response_bundle
load_strategic_scm
load_uncertainty_envelope
load_welfare_bundle
load_welfare_sample_bundle
normalize_artifact_ref
persist_ate_inference_basis
persist_backtest_report
persist_causal_assumption_card
persist_causal_capability_contract
persist_causal_effect_report
persist_causal_execution_bundle
persist_dependent_sensitivity_result
persist_discrete_distribution_summary
persist_distributional_bounds_bundle
persist_distributional_dual_certificate
persist_distributional_proof_artifact
persist_estimand_ast
persist_forecasting_uncertainty_bundle
persist_ge_uncertainty_bundle
persist_hte_outcome
persist_hte_point_result
persist_hte_refusal_diagnostic
persist_hte_result_v2
persist_ncm_spec_selected_view
persist_negative_certificate
persist_ordinal_poverty_report
persist_ot_coupling_summary
persist_posterior_summary
persist_proof_bundle
persist_quantile_shift_summary
persist_sensitivity_analysis_bundle
persist_structural_causal_model_spec
persist_subgroup_distribution_comparison
persist_tail_risk_delta_summary
persist_twin_network_result
persist_uncertainty_envelope
persist_welfare_bundle
persist_welfare_sample_bundle
prepare_ncm_spec_selected_values
proof_bundle_from_identification_result
proof_bundle_from_negative_certificate
proof_bundle_from_transportability_result
put_json_artifact
run_outer_search
sensitivity_analysis_bundle_from_result
stable_world_id_from_canon
summarize_posterior_draw_artifact
to_canonical_bytes
transportability_proof_review_grade
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
- Supported entrypoints: `polisyos.fabric`, `polisyos.fabric.api`, `polisyos.fabric.connectors`, `polisyos.fabric.data_plane`, `polisyos.fabric.world`, `polisyos.fabric.docs`, `polisyos.fabric.ingestion`, `polisyos.fabric.retrieval`, `polisyos.fabric.product_integration`
- Facade policy: expected `lazy_facade`, observed `unresolved_exports`
- Owner: `team-polisyos`
- README: `src/polisyos/fabric/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Connector-backed ingestion, world queries, and catalog surfaces.
- Summary: Stable Fabric facade for connector ingestion, world-query, and catalog APIs.

### Resolved supported entrypoints

| Entrypoint | Source | Facade | Exports |
| --- | --- | --- | ---: |
| `polisyos.fabric` | `src/polisyos/fabric/__init__.py` | `unresolved_exports` | unknown (no names proven) |
| `polisyos.fabric.api` | `src/polisyos/fabric/api.py` | `eager_exports` | 54 |
| `polisyos.fabric.connectors` | `src/polisyos/fabric/connectors/__init__.py` | `eager_exports` | 134 |
| `polisyos.fabric.data_plane` | `src/polisyos/fabric/data_plane/__init__.py` | `lazy_facade` | 56 |
| `polisyos.fabric.world` | `src/polisyos/fabric/world/__init__.py` | `unresolved_exports` | unknown (no names proven) |
| `polisyos.fabric.docs` | `src/polisyos/fabric/docs/__init__.py` | `eager_exports` | 17 |
| `polisyos.fabric.ingestion` | `src/polisyos/fabric/ingestion/__init__.py` | `lazy_facade` | 11 |
| `polisyos.fabric.retrieval` | `src/polisyos/fabric/retrieval/__init__.py` | `eager_exports` | 16 |
| `polisyos.fabric.product_integration` | `src/polisyos/fabric/product_integration/__init__.py` | `eager_exports` | 3 |

#### `polisyos.fabric`

- Source: `src/polisyos/fabric/__init__.py`
- Facade: `unresolved_exports`
- Summary: Stable Fabric facade for connector ingestion, world-query, and catalog APIs.
- Export resolution incomplete: `Unresolved reflective module-namespace write: src/polisyos/fabric/__init__.py`.
- Export scope: `no names proven by the bounded parser; not an empty runtime namespace`
- Candidate scope: `Names in a finite source declaration before effect audit; not proved native exports, not included in known_export_count and not a completeness verdict.`
- Source evidence: 1 measured source reads; full path, byte-length, and SHA-256 receipts are in the companion inventory JSON.

<details><summary>Source-declared candidates (54; native exports unproved)</summary>

```text
AccessRef
AuthoredText
ConnectorRegistryLike
ConnectorSchemaContract
DataSchema
FabricDecisionData
FabricDecisionDataCoverage
FabricDecisionDataResponse
FabricFetchReceipt
FederatedFetchResult
FederationFetchAudit
FederationFetchRequest
FederationFetchSource
FederationSnapshotProjectionError
FieldSpec
IngestionStoreBindingError
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
TenantSidecarScope
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
fabric_get_fresh_registered_sql_data
file_lock
freeze_federation_request
prepare_federation_core_payload
project_data_requirement_to_catalog_needs
query_claims
query_events
query_world_table
reopen_federated_fetch_result
resolve_connector_registry
resolve_world_snapshot
run_connectors_ingestion
stream_processing_contract
verify_federation_core_payload
world
```

</details>

#### `polisyos.fabric.api`

- Source: `src/polisyos/fabric/api.py`
- Facade: `eager_exports`
- Summary: Explicit public Fabric API facade and connector bridge.

<details><summary>Entrypoint exports (54)</summary>

```text
AccessRef
AuthoredText
ConnectorRegistryLike
ConnectorSchemaContract
DataSchema
FabricDecisionData
FabricDecisionDataCoverage
FabricDecisionDataResponse
FabricFetchReceipt
FederatedFetchResult
FederationFetchAudit
FederationFetchRequest
FederationFetchSource
FederationSnapshotProjectionError
FieldSpec
IngestionStoreBindingError
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
TenantSidecarScope
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
fabric_get_fresh_registered_sql_data
file_lock
freeze_federation_request
prepare_federation_core_payload
project_data_requirement_to_catalog_needs
query_claims
query_events
query_world_table
reopen_federated_fetch_result
resolve_connector_registry
resolve_world_snapshot
run_connectors_ingestion
stream_processing_contract
verify_federation_core_payload
world
```

</details>

#### `polisyos.fabric.connectors`

- Source: `src/polisyos/fabric/connectors/__init__.py`
- Facade: `eager_exports`
- Summary: Data Fabric Connectors - Protocol Foundation & Registry Architecture.

<details><summary>Entrypoint exports (134)</summary>

```text
API_PROTOCOL_CONNECTOR_CONTRACT
CAPABILITY_METHOD_REQUIREMENTS
CONNECTOR_FAMILY_CONTRACTS
DATABASE_CONNECTOR_CONTRACT
FILE_CONNECTOR_CONTRACT
OBJECT_STORAGE_CONNECTOR_CONTRACT
REQUIRED_ATTRIBUTES
REQUIRED_METHODS
SPATIAL_CONNECTOR_CONTRACT
STREAM_CONNECTOR_CONTRACT
AdaptiveRateLimiter
AmbiguousConnectorError
AsyncFetchLease
BaseConnector
CacheFallback
CacheMetadata
CachePolicy
CacheStats
CachedFetchResult
CachingConnectorProxy
CapabilityError
CatalogRegistrySchemaError
CircuitBreaker
CircuitBreakerConfig
CircuitOpenError
CircuitState
ConfigurationError
ConnectionConfig
ConnectionError
ConnectionHandle
ConnectionPool
ConnectorAlreadyRegisteredError
ConnectorCacheStore
ConnectorCapability
ConnectorConfigError
ConnectorDiscovery
ConnectorEntry
ConnectorError
ConnectorFamilyContract
ConnectorGovernanceMetadataIssue
ConnectorGovernanceMetadataReport
ConnectorMetadataSpec
ConnectorNotFoundError
ConnectorPreferences
ConnectorRegistry
DataChunk
DataVersion
DatasetCapabilitySnapshot
DatasetDescriptor
DiscoveryError
DiscoveryResult
FallbackChain
FallbackStrategy
FetchError
FetchRequest
FetchResult
FileTabularConnector
FreshnessResult
FreshnessStatus
HealthStatus
InvalidationEvent
InvalidationOrchestrator
InvalidationStrategy
InvalidationTrigger
LRUPolicy
MockFallback
PolicyRegistry
PoolClosedError
PoolConfig
PoolExhaustedError
PoolStats
PooledConnection
PrefetchJob
PrefetchScheduler
QualityTier
RaiseFallback
RateLimitError
RateLimitStatus
RateLimiter
RateLimiterConfig
RawHTTPResponseObserver
RegistryError
RegistryMetrics
RegistryStats
ResilienceConfig
ResultSerializer
RetryExhaustedError
RetryPolicy
SchemaChangeInvalidationTrigger
SchemaError
SizeBoundedPolicy
SmartExpiryPolicy
SourceConnector
SourceConnectorInstance
SourceConnectorValue
SourceProfile
SourceProfileRegistry
StaticDataPolicy
TTLPolicy
TrustLevel
ValidationIssue
ValidationResult
ValidationSeverity
VersionStrategy
VolatileDataPolicy
apply_resilience
capabilities_from_flags
capabilities_summary
check_capability_at_runtime
coerce_fetch_result_against_schema
contract_for_family
describe_capabilities
discover_connectors
discover_connectors_from_modules
flags_from_capabilities
get_discovery_errors
get_missing_capabilities
get_registry
is_retryable_error
make_schema_hash_provider
normalize_worldbank_records
requires_any_capability
requires_capability
resolve_async_iterator
resolve_connection_config
resolve_execution_policy
resolve_resilience_config
validate_connector_governance_metadata
validate_fetch_result_against_schema
validate_protocol_compliance
with_circuit_breaker
with_fallback
with_rate_limit
with_retry
```

</details>

#### `polisyos.fabric.data_plane`

- Source: `src/polisyos/fabric/data_plane/__init__.py`
- Facade: `lazy_facade`
- Summary: Data Plane facade for orchestration, quarantine, snapshots, shape, and time.

<details><summary>Entrypoint exports (56)</summary>

```text
AppendOnlyEvidenceJournal
EvidenceJournalError
FabricBenchmarkReport
HarnessAuthorizationEvidence
IngestionResult
JournalEventRef
LiveAttemptTerminal
LiveExecutionAuthorization
LiveHttpBudget
LiveMetadataExecutionAuthorization
LiveMetadataHarnessReceipt
LiveTransportTrace
QuarantineRecord
QuarantineReport
QuarantineReprocessResult
StreamDatasetRunResult
StreamOwnerConflictError
StreamRuntimeOptions
StreamingSourceSession
benchmark_partitioned_ingestion
benchmark_query_execution
benchmark_stream_processing
benchmark_world_materialization
build_live_execution_authorization
build_live_metadata_execution_authorization
build_quarantine_report
canonical_json_bytes
compare_historical_rows
content_sha256
derive_harness_authorization_evidence
derive_live_http_budget
ingestion_is_complete
iter_record_batches
list_quarantine_records
load_quarantine_payload
load_quarantine_record
payload_to_dataframe
persist_cdc_schema_change_event
persist_fabric_benchmark_report
persist_historical_semantic_diff_report
persist_quarantine_record
process_stream_dataset
quarantine_index_path
query_world_table
register_quarantine_reprocessor
reprocess_quarantine_records
require_authorized_execution
require_dataframe
resolve_journal_event_ref
resolve_linked_request_event
resolve_live_attempt_terminal
resolve_live_attempt_terminals
resolve_live_transport_trace
resolve_raw_response_body
run_orchestrated_ingestion
verify_journal_event_ref
```

</details>

#### `polisyos.fabric.world`

- Source: `src/polisyos/fabric/world/__init__.py`
- Facade: `unresolved_exports`
- Summary: Facade for emitting, validating, persisting, and materializing world facts.
- Export resolution incomplete: `Unresolved conditional/mutated exports: src/polisyos/fabric/world/__init__.py:__all__`.
- Export scope: `no names proven by the bounded parser; not an empty runtime namespace`
- Candidate scope: `Names in a finite source declaration before effect audit; not proved native exports, not included in known_export_count and not a completeness verdict.`
- Source evidence: 1 measured source reads; full path, byte-length, and SHA-256 receipts are in the companion inventory JSON.

<details><summary>Source-declared candidates (41; native exports unproved)</summary>

```text
SEGMENTS_INDEX_NAME
WorldFactError
WorldIDError
WorldSegmentError
WorldSnapshotBackendUnavailable
WorldSnapshotFactWrite
WorldSnapshotNodeWrite
WorldSnapshotWriteRequest
WorldStoreError
WorldValidationError
append_world_segment_index
emit_attr_fact
emit_claim_facts
emit_doc_fragment_facts
emit_doc_meta_facts
emit_edge_fact
emit_world_event_facts
emit_world_node_facts
event_world_provenance_v1
load_world_fact_manifests
load_world_facts
persist_claim
persist_conflict_set
persist_doc_fragment
persist_doc_meta
persist_fact_segment_manifest
persist_quality_report
persist_trust_assessment
persist_world_event
stable_world_provenance_v1
validate_claim_id
validate_conflict_set_id
validate_doc_fragment_ids
validate_doc_meta_ids
validate_fact_is_world_abi
validate_quality_report_id
validate_trust_assessment_id
validate_world_event_id
validate_world_facts
write_world_fact_segment
write_world_snapshot
```

</details>

#### `polisyos.fabric.docs`

- Source: `src/polisyos/fabric/docs/__init__.py`
- Facade: `eager_exports`
- Summary: Facade for raw-document ingest, normalization, structure, and chunking artifacts.

<details><summary>Entrypoint exports (17)</summary>

```text
DocChunkOptions
DocChunkResult
DocIngestOptions
DocIngestResult
DocNormalizeOptions
DocNormalizeResult
DocNotReadyError
DocPipelineError
DocSourceSpec
DocStructureOptions
DocStructureResult
DocUnsupportedMimeError
DocValidationError
chunk_doc
ingest_doc_bytes
normalize_doc
structure_doc
```

</details>

#### `polisyos.fabric.ingestion`

- Source: `src/polisyos/fabric/ingestion/__init__.py`
- Facade: `lazy_facade`
- Summary: Fabric ingestion runtime and provider dependencies.

<details><summary>Entrypoint exports (11)</summary>

```text
ConnectorManifestSpec
DatasetFetchSpec
IngestionDependencies
PreTransformFetchResultSink
RawFetchResultSink
SourceCollection
SourceCollectionMember
build_filesystem_artifact_store
load_source_collection
resolve_ingestion_dependencies
run_connectors_ingestion
```

</details>

#### `polisyos.fabric.retrieval`

- Source: `src/polisyos/fabric/retrieval/__init__.py`
- Facade: `eager_exports`
- Summary: Hybrid retrieval package.

<details><summary>Entrypoint exports (16)</summary>

```text
DiscoverOutcome
ExecuteOutcome
ExecutePlanResult
ExploreLaneDiscoverResult
ExploreLaneDiscovery
ExploreLaneLimits
FetchCaptureArtifactReferenceView
FetchCaptureLocatorView
FetchCaptureMetricView
FetchCapturePostflightView
FetchCapturePreflightView
FetchExecutor
ResolveOutcome
RetrievalProviders
RetrievalService
resolve_retrieval_providers
```

</details>

#### `polisyos.fabric.product_integration`

- Source: `src/polisyos/fabric/product_integration/__init__.py`
- Facade: `eager_exports`
- Summary: Shared Fabric provenance adapters for downstream product integrations.

<details><summary>Entrypoint exports (3)</summary>

```text
FabricProductEvidencePath
evidence_path_from_fabric_decision_data
evidence_paths_from_fabric_decision_data
```

</details>
Export total is unknown; the static reader cannot resolve the extension.

## `polisyos.foundry`

- Classification: `public_stable`
- Supported entrypoints: `polisyos.foundry`, `polisyos.foundry.api`, `polisyos.foundry.compile`, `polisyos.foundry.analysis`, `polisyos.foundry.calibration`, `polisyos.foundry.data_plane`, `polisyos.foundry.execute`, `polisyos.foundry.methods`, `polisyos.foundry.methods.backends`, `polisyos.foundry.methods.causal`, `polisyos.foundry.uncertainty`, `polisyos.foundry.validation`
- Facade policy: expected `lazy_facade`, observed `lazy_facade`
- Owner: `team-polisyos`
- README: `src/polisyos/foundry/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Stable compile/execute facade over the compute and method stack. Phase 6 keeps root public exports in polisyos.foundry.api and narrow public subpackages. Import compatibility applies only to paths with explicit architecture/shims.toml records; unlisted private FQNs remain internal by default.
- Summary: Expose the stable Foundry compile/execute entrypoints behind lazy imports.

### Resolved supported entrypoints

| Entrypoint | Source | Facade | Exports |
| --- | --- | --- | ---: |
| `polisyos.foundry` | `src/polisyos/foundry/__init__.py` | `lazy_facade` | 31 |
| `polisyos.foundry.api` | `src/polisyos/foundry/api.py` | `eager_exports` | 3 |
| `polisyos.foundry.compile` | `src/polisyos/foundry/compile/__init__.py` | `lazy_facade` | 6 |
| `polisyos.foundry.analysis` | `src/polisyos/foundry/analysis/__init__.py` | `eager_exports` | 19 |
| `polisyos.foundry.calibration` | `src/polisyos/foundry/calibration/__init__.py` | `unresolved_exports` | unknown (no names proven) |
| `polisyos.foundry.data_plane` | `src/polisyos/foundry/data_plane/__init__.py` | `eager_exports` | 23 |
| `polisyos.foundry.execute` | `src/polisyos/foundry/execute/__init__.py` | `lazy_facade` | 23 |
| `polisyos.foundry.methods` | `src/polisyos/foundry/methods/__init__.py` | `eager_exports` | 225 |
| `polisyos.foundry.methods.backends` | `src/polisyos/foundry/methods/backends/__init__.py` | `lazy_facade` | 25 |
| `polisyos.foundry.methods.causal` | `src/polisyos/foundry/methods/causal/__init__.py` | `unresolved_exports` | unknown (no names proven) |
| `polisyos.foundry.uncertainty` | `src/polisyos/foundry/uncertainty/__init__.py` | `unresolved_exports` | unknown (no names proven) |
| `polisyos.foundry.validation` | `src/polisyos/foundry/validation/__init__.py` | `eager_exports` | 11 |

#### `polisyos.foundry`

- Source: `src/polisyos/foundry/__init__.py`
- Facade: `lazy_facade`
- Summary: Expose the stable Foundry compile/execute entrypoints behind lazy imports.

<details><summary>Entrypoint exports (31)</summary>

```text
DependencyProfileResolutionFailure
EmbedderProtocol
LegalCorrespondenceRequest
LegalCorrespondenceResult
LegalSubjectAnnotationSource
LegalSubjectIdentity
LegalSubjectMembership
LegalSubjectMembershipSource
MethodCatalogDependencyAuthorityRequest
MethodRouteConstraint
InputContractMethodSelection
select_method_for_input_contract
SentenceTransformerEmbedder
TFIDFEmbedder
bind_legal_subject_annotations
build_method_catalog_provenance_manifest
build_method_catalog_runtime_identity
causal_worker_execution_context
compile
compile_program
execute
method_accepts_input_contract
persist_legal_correspondence_result
persist_legal_subject_annotations
persist_legal_subject_membership_source
produce_legal_subject_spine
recognize_legal_correspondence
select_method_candidates_for_requirements
validate_source_bound_causal_estimator_interval
validate_source_bound_causal_worker_response
validate_source_bound_gcm_spec
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

<details><summary>Entrypoint exports (6)</summary>

```text
TreasuryPlan
build_treasury_plan
compile
execution_plan_input_refs
program_graph_input_refs
replay_method_program_graph
```

</details>

#### `polisyos.foundry.analysis`

- Source: `src/polisyos/foundry/analysis/__init__.py`
- Facade: `eager_exports`
- Summary: Re-export Foundry analysis helpers used to interpret simulation outputs.

<details><summary>Entrypoint exports (19)</summary>

```text
TerminalRegime
build_attractor_analysis_result
build_attractor_ensemble_analysis_result
build_distributional_report
build_feedback_attractor_analysis_result
build_geography_breakdown
build_income_quintile_breakdown
build_winners_losers_table
classify_terminal_regime
compute_gini
compute_palma_ratio
finite_difference_map_jacobian
largest_lyapunov_exponent
load_attractor_analysis_result
load_basin_map
load_continuation_branch
persist_attractor_analysis_result
persist_basin_map
persist_continuation_branch
```

</details>

#### `polisyos.foundry.calibration`

- Source: `src/polisyos/foundry/calibration/__init__.py`
- Facade: `unresolved_exports`
- Summary: Expose calibration contracts, loss adapters, and the differentiable calibrator.
- Export resolution incomplete: `Unresolved exported binding: src/polisyos/foundry/calibration/__init__.py:affine_bijector`.
- Export scope: `no names proven by the bounded parser; not an empty runtime namespace`
- Candidate scope: `Names in a finite source declaration before effect audit; not proved native exports, not included in known_export_count and not a completeness verdict.`
- Source evidence: 1 measured source reads; full path, byte-length, and SHA-256 receipts are in the companion inventory JSON.

<details><summary>Source-declared candidates (115; native exports unproved)</summary>

```text
CalibrationSourceRead
CalibrationSourceReadRefusal
CalibrationSourceStatus
classify_calibration_source_error
read_calibration_source
read_calibration_config_source
read_calibration_model_source
read_calibration_registry_source
read_calibration_execution_input_basis_source
read_calibration_report_source
record_calibration_source_error
affine_bijector
aggregate_moment_summary
attach_abm_identifiability_certificate_ref
attach_identifiability_diagnostic_ref
apply_nodes_batch
AuxLossComponent
build_robust_set_spec_from_samples
calibrate_discrete_ci
calibrate_kernel_ci
calibration_report_series_sha256
calibration_report_time_axis_sha256
CALIBRATION_RUNTIME_INPUT_CONTRACT
CALIBRATION_RUNTIME_INPUT_CONTRACT_V1_2
CALIBRATION_RUNTIME_INPUT_NAMES
CALIBRATION_RUNTIME_INPUT_NAMES_V1_2
CalibrationCoordinateProjection
CalibrationExecutionInputBasis
CalibrationOrderedBatchInput
CalibrationOrderedBatchBackendUnavailable
CalibrationOrderedBatchReport
CalibrationOrderedBatchRow
CalibrationFitMetrics
CalibrationFitQuality
CalibrationParameterUnitIdentity
CalibrationReport
CalibrationResolvedParameterInput
CalibrationRuntimeInputBinding
CalibrationSeriesComparison
CalibrationTargetBundle
CalibrationTargetBundleManifest
CalibrationTargetInputIdentity
CalibrationUncertainty
Calibrator
CalibratorInputs
OrderedBatchCalibrationEvaluation
OrderedBatchCalibrationProfile
canonical_input_sha256
chain_bijector
CIFPRInflationBound
CISampleSizeRequirement
CITestCalibration
CITestThresholdPolicy
CITestThresholdPolicySet
coerce_dp_context
compile_program
compute_effective_weight
compute_hessian
DefaultMeasurementAwareLossAdapter
diagnose_identifiability
DPContext
effective_privacy_xi
envelope_from_calibration_param
envelopes_from_calibration
evaluate_ordered_batch_objective
ExecuteResponseBasisCandidate
ExecuteResponseSourceIdentity
fabric_calibration_context_from_decision_data
fabric_calibration_context_from_evidence_paths
FabricCalibrationContext
gaussian_parametric_radius
HessianResult
identifiability_diagnostic
IdentifiabilityDiagnosticConfig
IdentifiabilityDiagnosticResult
IdentifiabilityDiagnosticStatus
IdentifiabilityMomentClass
IdentifiabilityReport
IdentifiabilityStatus
InterferenceLossComponent
inverse_bijector
load_calibration_execution_input_basis
load_execute_response_basis_candidate
load_identifiability_diagnostic_result
log_bijector
logit_bijector
MeasurementAwareLossAdapter
MeasurementAwareLossConfig
MeasurementAwareTarget
MultiStartResult
ParamIdentifiability
persist_posterior_summary_from_method_evidence
propagate_selected_posterior_summary
put_calibration_config
put_calibration_execution_input_basis
put_calibration_report
reconcile_ordered_batch_inputs
put_calibration_ordered_batch_input
resolve_calibration_ordered_batch_input
reconcile_ordered_batch_report_identity
replay_ordered_batch_report_projection
ordered_batch_fit_metrics
reconcile_selected_runtime_input
required_n_chi2
required_n_kernel
resolve_ci_threshold_policy
RobustSetCalibrator
run_pure_scan
RUNTIME_REGISTRY_MEMBER_CONTRACT
RUNTIME_REGISTRY_MEMBER_INPUT_NAMES
select_robust_set_size
SetSizeSelector
SingleRunResult
softplus_bijector
StaticBundle
```

</details>

#### `polisyos.foundry.data_plane`

- Source: `src/polisyos/foundry/data_plane/__init__.py`
- Facade: `eager_exports`
- Summary: Expose input-binding helpers that bridge external data into Foundry state snapshots.

<details><summary>Entrypoint exports (23)</summary>

```text
HTE_PHYSICAL_SOURCE_BINDING_KIND
HTE_PHYSICAL_SOURCE_BINDING_SCHEMA
HTEInputLimits
HTEInputPreparationRefusal
HTEPhysicalArraySlotBinding
HTEPhysicalSourceMaterializationBinding
InputBindingValuesPreparation
InputBindingsBuildResult
InputBindingsPreparation
PreparedHTEObservationalInput
UkraineFoundryIntakeResult
build_input_bindings
extract_feedback_diagnostics
extract_feedback_state
inject_feedback_state
load_input_bindings
load_hte_physical_source_materialization_binding
load_ukraine_foundry_intake
materialize_method_contract
prepare_hte_observational_input
prepare_input_bindings
prepare_json_input_binding_values
resolve_bound_state_snapshot_ref
```

</details>

#### `polisyos.foundry.execute`

- Source: `src/polisyos/foundry/execute/__init__.py`
- Facade: `lazy_facade`
- Summary: Stable execute facade for compiled Foundry plans.

<details><summary>Entrypoint exports (23)</summary>

```text
BoundedNumericNPZError
BoundedStateSnapshotInputs
ExecutionSourceAdmission
ExecutionSourceAdmissionRefusal
BoundedExecutionSourceReader
ExecutionSourceBoundedReadRefusal
ResolvedExecutionPosture
SnapshotStateInputReadRefusal
StateSnapshotInputReadUsage
StateSnapshotInputReadRefusal
SnapshotStateLayoutError
admit_execution_source
admit_execution_source_bounded
execute
read_method_artifact_output_bounded
execution_input_basis_sources
get_state_path
load_state_snapshot
StateSnapshotValueLeaf
state_snapshot_value_projection
read_numeric_npz_bounded
read_state_snapshot_inputs_bounded
resolve_execution_posture
```

</details>

#### `polisyos.foundry.methods`

- Source: `src/polisyos/foundry/methods/__init__.py`
- Facade: `eager_exports`
- Summary: Stable lazy facade for Foundry Methods.

<details><summary>Entrypoint exports (225)</summary>

```text
ADVISOR_EXECUTION_CONTEXT_PARAM
ActiveSetSummary
AdapterPlan
AdvisorExecutionContext
AmbiguityCertificate
ArtifactError
BackendNotAvailableError
BackendSpec
BootstrapExecutionWork
BreakingChange
BreakingChangeError
CalibrationBattery
CalibrationCase
CalibrationResult
ChainArtifact
ChainExecutionResult
ChainNodeRecord
ComparatorKind
CompilationCache
CompilationError
CompiledChainExecutor
CompiledMethod
CompiledMethodChain
ComplexityClass
ComponentsBridgeError
ComponentsBridgeReport
CompositionDAG
ComputeBackend
ConsensusTarget
ContractViolationError
CrossBackendEquivalenceCertificate
CrossMethodConsensus
CyclicDependencyError
DISCOVERY_MODULE_PREFIX
DataCharacteristics
DeprecationAudit
DeprecationInfo
DeviceInfo
DimExpr
DimVar
DiscoveryError
DiscoveryReport
DiscoverySource
DuplicatePolicy
ENTRY_POINT_GROUP
EQUIVALENCE_ATTESTATION_KIND
EQUIVALENCE_ATTESTATION_PREDICATE_TYPE
EQUIVALENCE_ATTESTATION_SCHEMA
EQUIVALENCE_ATTESTATION_SCHEMA_VERSION
EntryPointSource
EquivalenceCertificateResolver
EquivalencePolicy
EquivalenceRuntimeEnvelope
EquivalenceVerdict
EquivalenceVerificationReport
EstimandSpec
ExecutionEvidence
ExecutionKernel
ExecutionPlanOptimizer
FidelityLevel
FieldCalibrationStats
FieldComparison
FieldRequirement
FieldToleranceSpec
FileSystemSource
FoundryMethod
FoundryMethodBase
FoundryMethodError
InMemoryEquivalenceCertificateRegistry
IncompatibilityReason
LawViolationError
LifecycleLog
LifecycleManager
LinkResult
LinkerConfig
MethodAdvisorQuery
MethodAdvisorResult
MethodAlreadyRegisteredError
MethodArtifact
MethodCompiler
MethodComposer
MethodContractError
MethodContracts
MethodCostModel
MethodDefinitionError
MethodDiscovery
MethodDispatcher
MethodEntry
MethodKind
MethodLifecycle
MethodLossProfile
MethodMetadata
MethodNode
MethodNotFoundError
MethodRegistry
MethodResult
MethodRetiredException
MethodRunner
MethodScoreTraceEntry
MethodSelectionCriteria
MethodSelectionReceipt
MethodSignature
MethodTiming
MisspecificationClassification
NodeSchedule
NotComparableYet
OptimizedPlan
OrdinalMultidimensionalPovertyEstimator
PairwiseDisagreement
ParameterSpec
ParameterValidationError
PersistedEquivalenceArtifacts
PlanComplexityClass
RegistrySnapshot
RegistrySnapshotEntry
ReproducibilityInfo
ResolutionError
ResolutionPolicy
ResolvedEquivalenceCertificate
SemanticValidationLevel
Shape
ShapeAdapter
ShapeAdapterKind
ShapeMismatchError
ShapeSpec
SideEffectProfile
SignatureDiff
SlotBinding
SlotBindingRecord
SlotCompatibility
SlotConnectionError
SlotLinker
SlotSchema
SlotSpec
SlotType
SolverStatus
SourceFingerprint
Specialization
TypeAdapter
TypeAdapterKind
Unit
UnitAdapter
UnitAdapterKind
UnitMismatchError
ValidationContext
VersionConstraint
advise_methods
advise_methods_for_analyst
assert_no_breaking_changes
assess_certificate_applicability
attach_advisor_execution_context
attach_equivalence_ref
authoring_catalog_payload
bootstrap_method_registry_from_components
build_advisor_execution_context
build_method_capability_matrix
build_method_catalog_snapshot
build_specialization
calibrate_backend_pair
calibrate_backend_pair_detailed
canonicalize_method_result
causal_worker_execution_context
check_linkable
check_multiple_compatibility
check_protocol_compliance
check_slot_compatibility
compare_field_values
compare_versions
compute_distributional_check
compute_hausman_like_check
compute_pairwise_checks
compute_projection_checks
compute_source_fingerprint
compute_source_hash
compute_static_params_hash
deprecate_method
derive_field_tolerance_spec
derive_pairwise_budget
ensure_all_methods_registered
ensure_forecasting_methods_registered
estimate_method_execution_cost_usd
execute_heterogeneous_chain
find_compatible_slots
find_compatible_versions
foundry_method
get_global_cache
get_mechanism_family_spec
get_registry
get_slot_schema
is_compatible_upgrade
is_foundry_method
is_semantically_compatible
is_valid_semver
link_methods
load_equivalence_certificate
method_selection_payload
parse_fqn
parse_pip_specifier
persist_attested_equivalence_certificate
persist_equivalence_certificate
persist_method_catalog_snapshot
rank_method_catalog_entries
reachable_value_method_fqns
register_slot_schema
registry_scope
reset_global_cache
resolve_by_specifier
resolve_method_version
resolve_version
run_cross_method_consensus
runtime_envelope_from_results
select_value_method_for_problem
specialization_from_signature_and_state
store_chain_artifact
store_execution_evidence
store_method_artifact
suggest_adapter_methods
suggest_alternative_methods
suggest_plan_node_alternatives
tag_deprecated_in_registry
validate_source_bound_causal_estimator_interval
validate_source_bound_causal_worker_response
validate_source_bound_gcm_spec
verify_backend_equivalence
verify_persisted_equivalence_certificate
```

</details>

#### `polisyos.foundry.methods.backends`

- Source: `src/polisyos/foundry/methods/backends/__init__.py`
- Facade: `lazy_facade`
- Summary: Expose Foundry method backends without initializing unrelated runtimes.

<details><summary>Entrypoint exports (25)</summary>

```text
AsyncChainExecutionError
AsyncChainExecutor
AsyncNodeError
BackendCircuitOpenError
BackendNotAvailableError
ChainExecutionResult
CircuitBreaker
CircuitBreakerRegistry
CircuitState
MethodDispatcher
NumpyRunner
MethodResult
MethodRunner
MethodTiming
ReproducibilityInfo
SolverStatus
ValidatedBound
ValidatedExecutionPolicy
ValidatedMethodFamily
ValidatedMode
ValidatedStatus
estimate_method_execution_cost_usd
execute_heterogeneous_chain
get_circuit_breaker_registry
validated_bound_to_envelopes
```

</details>

#### `polisyos.foundry.methods.causal`

- Source: `src/polisyos/foundry/methods/causal/__init__.py`
- Facade: `unresolved_exports`
- Summary: Lazy facade for causal catalog methods.
- Export resolution incomplete: `Unresolved export expression: src/polisyos/foundry/methods/causal/__init__.py:_read_exports()`.
- Export scope: `no names proven by the bounded parser; not an empty runtime namespace`
- Candidate scope: `Names in a finite source declaration before effect audit; not proved native exports, not included in known_export_count and not a completeness verdict.`
- Source evidence: 1 measured source reads; full path, byte-length, and SHA-256 receipts are in the companion inventory JSON.

#### `polisyos.foundry.uncertainty`

- Source: `src/polisyos/foundry/uncertainty/__init__.py`
- Facade: `unresolved_exports`
- Summary: Expose uncertainty propagation helpers used around Foundry simulation outputs.
- Export resolution incomplete: `Unresolved exported binding: src/polisyos/foundry/uncertainty/__init__.py:AggregationStrategy`.
- Export scope: `no names proven by the bounded parser; not an empty runtime namespace`
- Candidate scope: `Names in a finite source declaration before effect audit; not proved native exports, not included in known_export_count and not a completeness verdict.`
- Source evidence: 1 measured source reads; full path, byte-length, and SHA-256 receipts are in the companion inventory JSON.

<details><summary>Source-declared candidates (30; native exports unproved)</summary>

```text
CALIBRATION_COVARIANCE_RECONCILIATION_ATOL_V1
CALIBRATION_COVARIANCE_RECONCILIATION_RTOL_V1
EXCEPTION_CHAIN_EDGE_LIMIT
EXCEPTION_CHAIN_NODE_LIMIT
EvaluationFailureClassification
build_covariance_matrix
calibration_covariance_blocks_agree_v1
classify_evaluation_failure
preserve_singular_covariance
AdaptiveStoppingConfig
AggregationStrategy
FabricUncertaintyContext
MonteCarloPropagator
PropagationConfig
PropagationDispatcher
PropagationResult
PropagationStrategy
PosteriorJointInputMatrix
PosteriorPushforwardFailure
PosteriorPushforwardOutcomeCode
PosteriorPushforwardOutputSummary
PosteriorPushforwardResult
QuasiMCSampler
aggregate_envelopes
aggregate_persisted_envelope_views
load_aggregated_envelope_fresh
persist_aggregated_envelope
compute_first_order_indices
extract_std
fabric_uncertainty_context_from_decision_data
```

</details>

#### `polisyos.foundry.validation`

- Source: `src/polisyos/foundry/validation/__init__.py`
- Facade: `eager_exports`
- Summary: Validation helpers for machine-checking Foundry closure surfaces.

<details><summary>Entrypoint exports (11)</summary>

```text
build_causal_statistical_validity_report
build_foundry_method_report
build_foundry_phase0_closure_report
build_foundry_phase2_closure_report
default_foundry_phase2_closure_report_path
default_foundry_phase2_manifest_path
maybe_load_foundry_phase2_closure_report
normalize_causal_statistical_validity_report
normalize_foundry_method_report
normalize_phase2_artifact_family
persist_causal_statistical_validity_report
```

</details>

<details><summary>Supported exports (31)</summary>

```text
DependencyProfileResolutionFailure
EmbedderProtocol
LegalCorrespondenceRequest
LegalCorrespondenceResult
LegalSubjectAnnotationSource
LegalSubjectIdentity
LegalSubjectMembership
LegalSubjectMembershipSource
MethodCatalogDependencyAuthorityRequest
MethodRouteConstraint
InputContractMethodSelection
select_method_for_input_contract
SentenceTransformerEmbedder
TFIDFEmbedder
bind_legal_subject_annotations
build_method_catalog_provenance_manifest
build_method_catalog_runtime_identity
causal_worker_execution_context
compile
compile_program
execute
method_accepts_input_contract
persist_legal_correspondence_result
persist_legal_subject_annotations
persist_legal_subject_membership_source
produce_legal_subject_spine
recognize_legal_correspondence
select_method_candidates_for_requirements
validate_source_bound_causal_estimator_interval
validate_source_bound_causal_worker_response
validate_source_bound_gcm_spec
```

</details>

## `polisyos.scientist`

- Classification: `public_stable`
- Supported entrypoints: `polisyos.scientist`, `polisyos.scientist.adapters`, `polisyos.scientist.compute`, `polisyos.scientist.governance.continuous`, `polisyos.scientist.methods.backtesting`, `polisyos.scientist.methods.research_dag`, `polisyos.scientist.orchestration.engine`, `polisyos.scientist.replay`, `polisyos.scientist.replay.deterministic`, `polisyos.scientist.validation.policy_verified`, `polisyos.scientist.agent`, `polisyos.scientist.policy_design`
- Facade policy: expected `lazy_facade`, observed `lazy_facade`
- Owner: `team-polisyos`
- README: `src/polisyos/scientist/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Workflow orchestration and policy-verified artifact facades, including typed legal retrieval status on candidate packs.
- Summary: Stable Scientist package facade for workflow execution and run observability.

### Resolved supported entrypoints

| Entrypoint | Source | Facade | Exports |
| --- | --- | --- | ---: |
| `polisyos.scientist` | `src/polisyos/scientist/__init__.py` | `lazy_facade` | 41 |
| `polisyos.scientist.adapters` | `src/polisyos/scientist/adapters/__init__.py` | `lazy_facade` | 6 |
| `polisyos.scientist.compute` | `src/polisyos/scientist/compute/__init__.py` | `lazy_facade` | 17 |
| `polisyos.scientist.governance.continuous` | `src/polisyos/scientist/governance/continuous/__init__.py` | `lazy_facade` | 87 |
| `polisyos.scientist.methods.backtesting` | `src/polisyos/scientist/methods/backtesting/__init__.py` | `lazy_facade` | 34 |
| `polisyos.scientist.methods.research_dag` | `src/polisyos/scientist/methods/research_dag/__init__.py` | `eager_exports` | 44 |
| `polisyos.scientist.orchestration.engine` | `src/polisyos/scientist/orchestration/engine/__init__.py` | `lazy_facade` | 115 |
| `polisyos.scientist.replay` | `src/polisyos/scientist/replay/__init__.py` | `lazy_facade` | 25 |
| `polisyos.scientist.replay.deterministic` | `src/polisyos/scientist/replay/deterministic.py` | `eager_exports` | 20 |
| `polisyos.scientist.validation.policy_verified` | `src/polisyos/scientist/validation/policy_verified/__init__.py` | `eager_exports` | 28 |
| `polisyos.scientist.agent` | `src/polisyos/scientist/agent/__init__.py` | `lazy_facade` | 102 |
| `polisyos.scientist.policy_design` | `src/polisyos/scientist/policy_design/__init__.py` | `lazy_facade` | 105 |

#### `polisyos.scientist`

- Source: `src/polisyos/scientist/__init__.py`
- Facade: `lazy_facade`
- Summary: Stable Scientist package facade for workflow execution and run observability.

<details><summary>Entrypoint exports (41)</summary>

```text
decision_packet_invocation_input_refs
require_canonical_decision_packet_invocation
DECISION_PACKET_INVOCATION_KIND
DecisionPacketInvocationRecord
CanonicalDecisionPacketInvocation
CompletedDecisionPacketExecution
EpochCertificateIssuanceNonReceipt
EpochCertificateIssuanceOwner
PersistedEpochCertificateIssuancePreparation
require_canonical_decision_packet_execution
DecisionValidityService
GOVERNANCE_MONITOR_EVENT_KIND
resolve_governance_monitor_event
BudgetState
CritiqueReport
DraftResult
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

#### `polisyos.scientist.adapters`

- Source: `src/polisyos/scientist/adapters/__init__.py`
- Facade: `lazy_facade`
- Summary: Stable adapter facade for default Foundry and Fabric runtime ports.

<details><summary>Entrypoint exports (6)</summary>

```text
DefaultFabricPort
DefaultFoundryPort
RegisteredSQLCapture
RegisteredSQLViewContract
parse_data_view_request
registered_sql_capture_input_refs
```

</details>

#### `polisyos.scientist.compute`

- Source: `src/polisyos/scientist/compute/__init__.py`
- Facade: `lazy_facade`
- Summary: Scientist compute surface for job execution contracts.

<details><summary>Entrypoint exports (17)</summary>

```text
C7AdvancedInputs
C7AdvancedSuiteResult
C7PersistedArtifact
BoundedMethodMetricSourceReader
MAX_METHOD_METRIC_SOURCE_BYTES
MethodMetricSourceReadBudget
VerifiedRestrictedExAnteCall
read_bounded_method_metric_artifact
selected_method_metric_ref
JobKey
JobResult
JobSpec
MethodExecutionCaptureProvenance
MethodBackend
read_job_result_method_execution_capture
run_c7_advanced_suite
run_job
```

</details>

#### `polisyos.scientist.governance.continuous`

- Source: `src/polisyos/scientist/governance/continuous/__init__.py`
- Facade: `lazy_facade`
- Summary: Continuous governance and reissue loop for Scientist decision artifacts.

<details><summary>Entrypoint exports (87)</summary>

```text
GovernedPublicCustodyBinding
GovernedPublicRecord
GovernedPublicRecordDraft
GovernedPublicRecordError
GovernedPublicRecordOwner
GovernedPublicRecordProjection
GovernedPublicRecordVerificationResponse
PublicationMandateStatement
PublicationSigningSlot
PublicationTrustedKey
publication_trust_epoch
CONTINUOUS_GOVERNANCE_FLAG
ENABLE_REISSUE_WORKFLOW_FLAG
ENABLE_WITHDRAWAL_STATUS_FLAG
GOVERNANCE_MONITOR_EVENT_KIND
AppealPerturbation
CorrectionPerturbation
ContinuousInvalidationResult
DecisionValidityReport
DecisionValidityStatus
DetectorConfig
DriftDetectionResult
DiscoveredBiasPerturbation
FairnessDriftSignal
GovernanceMonitorEvent
GovernanceMonitorRecommendation
IncidentReport
IncidentSeverity
IncidentPerturbation
LegalChangePerturbation
LifecycleBridgeBlocker
LifecycleBridgeResult
PartialPublicationState
PolicyContextSignal
PersistedGovernanceMonitorEvent
PersistedPublicSignaturePopulation
PersistedPublishedSignatureCustodyScan
PublicSignaturePopulationMember
PublicSignaturePopulationNonReceipt
PublicSignaturePopulationProvider
PublicSignaturePopulationSnapshot
PublicRecordPopulationInspection
PublicVerificationRecordObservation
PublicVerificationRecordPopulationProvider
PublicVerificationRecordSource
PublishedSignatureCustodyResult
PublishedSignatureCustodyScan
PublishedSignatureCustodyWatcher
PublicRevisionDiff
ReissuePacket
RetractionPerturbation
SparseHistoryPolicy
WithdrawalRecord
aggregate_validity_status
build_drift_monitor_event
bridge_governance_events_to_claim_lifecycle
build_partial_scope_reissue_packet
build_reissue_packet
build_validity_report
build_withdrawal_record
detect_calibration_drift
detect_fairness_drift
detect_policy_context_drift
detect_source_invalidation
export_public_validity_report
governance_event_from_source_invalidation
incident_monitor_event
load_incident_report
load_lifecycle_bridge_result
load_reissue_packet
load_validity_report
load_withdrawal_record
mark_dependent_claims_stale
monitor_event_id
persist_incident_report
persist_lifecycle_bridge_result
persist_reissue_packet
persist_validity_report
persist_withdrawal_record
recommend_validity_action
reissue_scope_from_monitor_events
resolve_governance_monitor_event
resolve_public_signature_population
StaticPublicSignaturePopulationProvider
UnappointedPublicSignaturePopulationProvider
persist_public_signature_population
persist_published_signature_custody_scan
```

</details>

#### `polisyos.scientist.methods.backtesting`

- Source: `src/polisyos/scientist/methods/backtesting/__init__.py`
- Facade: `lazy_facade`
- Summary: Stable backtesting facade for replay, masking, challenge suites, and trust scoring.

<details><summary>Entrypoint exports (34)</summary>

```text
ABSTRACTION_LEAKAGE_SUITE_ID
MULTIPLICITY_DISCLOSURE_SUITE_ID
PHASE_D4_ROTATION_GROUP
STRATEGIC_GAMING_SUITE_ID
AdversarialGenerator
AdversarialScenario
BacktestOrchestrator
ChallengeCase
ChallengeCaseResult
ChallengeSuiteResult
CALIBRATION_RULE_ID
CalibrationRuleBinding
ForecastMethodParams
ForecastOwner
ForecastOwnerRequest
ForecastOwnerResult
ForecastTemporalRoles
TrainHoldoutSplit
run_forecast_owner
CompositionReplayResult
HistoricalValidationPlan
MaskingStrategy
OutcomeMasker
PredictionEvaluator
PredictionSource
TemporalEvaluationResult
TemporalThresholds
TrustScorer
build_temporal_backtest_report
evaluate_temporal_safe_rejection
evaluate_temporal_trajectory
replay_fragment_composition_case
run_phase_d4_challenge_suites
summarize_temporal_evaluations
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

#### `polisyos.scientist.orchestration.engine`

- Source: `src/polisyos/scientist/orchestration/engine/__init__.py`
- Facade: `lazy_facade`
- Summary: Scientist workflow engine public facade with lazy exports.

<details><summary>Entrypoint exports (115)</summary>

```text
ATTR_CACHE_HIT
ATTR_CELL_ID
ATTR_DURATION_MS
ATTR_ERROR_POLICY
ATTR_NODE_ALIAS
ATTR_NODE_ID
ATTR_NODE_STATUS
ATTR_RETRY_COUNT
ATTR_RUN_ID
ATTR_TENANT_ID
ATTR_TIER_INDEX
ATTR_WORKFLOW_ID
CHECKPOINT_HEAD_FILENAME
CHECKPOINT_KIND
CHECKPOINT_SCHEMA_VERSION
IDEMPOTENCY_CONTRACT_VERSION
AsyncWorkflowExecutor
BudgetExhaustedError
BudgetLedger
BudgetLedgerMutation
BudgetLedgerCacheReuseAdmission
BudgetLedgerProducerRecord
BudgetLedgerProducerRunBinding
BudgetLedgerSnapshot
BudgetLedgerWriter
BudgetLimit
BudgetMiddleware
BudgetState
CASCheckpointHook
CheckpointArtifact
CheckpointCorruptedError
CheckpointError
CheckpointHead
CheckpointMetadata
CheckpointNotFoundError
CheckpointPolicy
CheckpointScopeMismatchError
CheckpointSnapshotMode
CheckpointWriteResult
CircuitBreaker
CircuitBreakerConfig
CircuitBreakerOpenError
ConditionSyntaxError
ConvergenceConfig
ConvergenceDetector
ConvergenceObservation
ConvergenceState
ConvergenceStrategy
CreatedCheckpoint
CycleDetectedError
DuplicateAliasError
EngineError
EngineMetricsCollector
ExperimentState
FanOutConfig
FanOutNode
FanOutResult
FileBudgetLedger
MergeConflictPolicy
MetricsExporterHealth
MissingDependencyError
Node
NodeCacheEntry
NodeCondition
NodeError
NodeEvent
NodeExecutionError
NodeInvocation
NodeOutcome
NodeOutputRule
OutputAwareNodeSpec
NodeOutputDisposition
NodeOutputRefusal
OutputAwareNodeOutcome
decode_node_outcome
NodeRegistry
NodeResultCache
NodeSpec
NodeStatus
NodeTimeoutError
NoopEngineMetrics
OTelEngineMetrics
RemoteNodeExecutor
RetryExhaustedError
RollbackCompensationEvent
RollbackCompensationHook
RunLockError
StateMapping
SubWorkflowConfig
SubWorkflowNode
TraceCorrelationRecord
UnknownNodeError
WorkflowExecutor
WorkflowMismatchError
WorkflowRunnerBackend
WorkflowRunnerConfig
WorkflowSpec
WorkflowSpecError
WorkflowTimeoutError
acquire_run_lock
build_engine_metrics
build_node_span_attributes
build_workflow_runner
compute_idempotency_key
compute_idempotency_payload
compute_workflow_fingerprint
discover_nodes
enrich_node_span_result
evaluate_condition
extract_state_slice
get_metrics_exporter_health
materialize_checkpoint_state
normalize_checkpoint_policy
resolve_latest_checkpoint
resume_from_checkpoint
```

</details>

#### `polisyos.scientist.replay`

- Source: `src/polisyos/scientist/replay/__init__.py`
- Facade: `lazy_facade`
- Summary: Scientist replay hub for dead-letter, diff, and verification helpers.

<details><summary>Entrypoint exports (25)</summary>

```text
ComparatorRegistry
DeadLetterCorruptedError
DeadLetterError
DeadLetterNotFoundError
DeadLetterRecord
DiffToleranceConfig
FieldDiff
REPLAY_VERIFICATION_REPORT_SCHEMA_NAME
ReplayBackendResult
ReplayDiffInputError
ReplayDiffResult
ReplayRegistry
ReplayRegistryEntry
ReplayRegistrySnapshot
ReplayVerificationReport
build_replay_verification_report
compute_replay_diff
list_dead_letters
load_dead_letter
load_replay_verification_report
persist_replay_verification_report
replay_dead_letter
replay_packet
save_diff_report
verify_and_persist_replay_bundle
```

</details>

#### `polisyos.scientist.replay.deterministic`

- Source: `src/polisyos/scientist/replay/deterministic.py`
- Facade: `eager_exports`
- Summary: Plan, measure, and verify deterministic replay from CAS decision packets.

<details><summary>Entrypoint exports (20)</summary>

```text
CompletenessLevel
CompletenessReport
MissingArtifact
ReplayBundleMeasurement
ReplayPlan
ReplayStrategy
SeedResolution
VerificationConfig
VerificationMode
VerificationResult
build_replay_plan
compare_current_environment
completeness_check
determine_replay_strategy
measure_replayable_audit_bundle
normalize_artifact_id
resolve_effective_seed
set_global_seeds
try_parse_artifact_id
verify_replay
```

</details>

#### `polisyos.scientist.validation.policy_verified`

- Source: `src/polisyos/scientist/validation/policy_verified/__init__.py`
- Facade: `eager_exports`
- Summary: Stable policy-verification facade for request frames, legal packs, and verified reports.

<details><summary>Entrypoint exports (28)</summary>

```text
LegalCandidatePack
LegalRetrievalStatus
LegalSourcePack
PolicyEvidenceLink
PolicyOption
PolicyOptionSet
PolicyRequestFrame
SourceCoverageGap
SourceVerificationReport
VerifiedLegalClaim
VerifiedPolicyReport
load_legal_candidate_pack
load_legal_source_pack
load_policy_option_set
load_policy_request_frame
load_source_verification_report
load_verified_policy_report
persist_legal_candidate_pack
persist_legal_source_pack
persist_policy_option_set
persist_policy_request_frame
persist_source_verification_report
persist_verified_policy_report
VERIFIED_POLICY_REPORT_SOURCE_BASIS_ID
VERIFIED_POLICY_REPORT_SOURCE_READ_PATHS
VerifiedPolicyReportAdmission
VerifiedPolicyReportCurrentness
resolve_current_verified_policy_report
```

</details>

#### `polisyos.scientist.agent`

- Source: `src/polisyos/scientist/agent/__init__.py`
- Facade: `lazy_facade`
- Summary: Scientist Agent Layer

<details><summary>Entrypoint exports (102)</summary>

```text
AGENT_PROTOCOLS
AgentRole
AgentRouter
BaseAgent
CASNormPackLoader
CASRAGIndex
CodeVerificationSandbox
ConstitutionGenerator
CriticAgent
CriticKnowledgeBase
CritiqueCategory
CritiqueIssue
CritiqueReport
CritiqueSeverity
DataNeedExtractorAgent
DataNeedSpec
DelegationResult
DraftResult
DrafterAgent
DuckDBFeasibilityProbe
FailurePatternIndex
FeasibilityProbe
FormalizerAgent
InformedCriticAgent
InformedCriticConfig
KnownPitfall
LATSAgentSearch
LATSConfig
LLMCriticAgent
LLMDataNeedExtractorAgent
LLMDrafterAgent
LLMFormalizerAgent
LLMPIAgent
MockAgent
MockCriticAgent
MockDataNeedExtractorAgent
MockDrafterAgent
MockFormalizerAgent
MockLLM
MockPIAgent
MultiPassConfig
MultiPassLLMDrafter
NormPackLoader
NullFeasibilityProbe
PIAgent
PolicyConstitution
ProblemFrame
RAGConfig
ReasoningAction
ReasoningNode
ReasoningPolicyGate
ReasoningSearchReport
ReasoningStatus
ReflexionConfig
ReflexionDecision
ReflexionEvaluatorConfig
ReflexionOrchestrator
ReflexionReplayCase
ReflexionReplayEvaluation
ReflexionScorecard
ReflexionTrajectoryStep
RoutingState
RubricReflexionEvaluator
SandboxConfig
ScientistAgentFabric
ScientistAgentFabricConfig
ScientistAgentFabricRequest
ScientistAgentFabricResponse
ScientistSupervisorAgent
ScientistSupervisorConfig
ShortTermMemory
StateSnapshotFeasibilityProbe
StaticNormPackLoader
SubTask
SupervisorRunResult
SupervisorSynthesisMode
TaskPriority
TaskStatus
TreeOfThoughtConfig
TreeOfThoughtPlanner
TurnRole
WorkerBudgetHints
WorkerCitation
WorkerExecutionMode
WorkerResultPayload
WorkerSourcePolicy
WorkerTaskEnvelope
WorkerTaskResult
build_reflexion_evaluator_worker_handler
build_scholar_search_worker_handler
build_sectioned_worker_envelopes
build_self_moa_worker_envelopes
build_worker_tool_registry
create_critic_agent
create_drafter_agent
create_mock_draft
create_mock_problem_frame
drafter_node
evaluate_reflexion_replay_cases
get_protocol_for_role
is_valid_agent
register_worker_tool
```

</details>

#### `polisyos.scientist.policy_design`

- Source: `src/polisyos/scientist/policy_design/__init__.py`
- Facade: `lazy_facade`
- Summary: Policy design typed schema and objective stack.

<details><summary>Entrypoint exports (105)</summary>

```text
AdversarialScenarioBundle
AdversarialScenarioProposal
AdversaryExecutionResult
BaselineComparisonCompiler
BaselineComparisonInput
BudgetAllocationEntry
ChampionPolicyDossier
ClaimDecompositionCompiler
ClaimDecompositionFacet
ClaimDecompositionInput
ClaimDecompositionNamedAlternative
ClaimDecompositionObligation
ConstraintCritic
ConstraintCriticInput
ConstraintCritique
ConstraintFinding
ConstraintSatisfactionReport
ConstraintStatus
ConstraintTrace
CriticConsensusCandidate
CriticConsensusReport
CriticDiversitySummary
CriticDiversityWarning
CriticEnsembleReport
CriticEnvelope
CriticVerdict
DeterministicPolicyTranslator
FallbackVariant
FormulatorCandidate
GovernanceGatePacket
HarmEnvelope
HierarchicalSearchConfig
HierarchicalSearchCoordinator
HierarchicalSearchResult
HierarchicalSearchState
ImplementationPlan
InMemoryHypothesisLedger
LLMFormulator
LLMFormulatorInput
LLMFormulatorOutput
MethodMetricObservation
MethodMetricPredicateEvidence
MethodMetricSourceUnit
MonitoringSignalSpec
MultiCriticEnsemble
NarrativeVariant
ObjectiveChannelValue
ObjectiveDirection
ObjectiveKind
ObjectiveStack
ParameterScheduleEntry
ParameterSearchSpec
PolicyArtifactBuildInput
PolicyArtifactBuilder
PolicyArtifactBundle
PolicyAssumptionSpec
PolicyBrief
PolicyCandidateSchema
PolicyEvaluationBundle
PolicyEvaluationVector
PolicyFrontierReport
PolicyParameterCodec
PolicyRiskNote
PolicySearchLevel
PolicyTranslatorConfig
PolicyTranslatorWorker
RecommendedAction
RejectedAlternativesSummary
ReplayableAuditBundle
RolloutStep
ScenarioAdversaryConfig
ScenarioAdversaryWorker
ScenarioAttackSurface
SelectedMethodMetricArtifactRef
StructureCandidate
SubgroupImpactReport
TargetPopulationSpec
TradeoffRow
TranslatorComplianceFinding
TranslatorCompliancePass
TranslatorComplianceResult
TranslatorInputBundle
TransportAssumptionSpec
TransportabilityReport
UncertaintyReport
baseline_comparison_audit_surface
build_critic_candidate
compile_baseline_comparisons
compile_claim_decomposition
compile_participation_requirements_from_claim_ledger
critic_consensus_to_obligation_candidates
critic_verdict
critique_to_failure_cards
critique_to_lesson_cards
derive_phase2_parameter_bounds
load_adversarial_scenario_bundle
load_policy_artifact_bundle
load_policy_brief
load_policy_candidate_schema
persist_adversarial_scenario_bundle
persist_policy_artifact_bundle
persist_policy_brief
persist_policy_candidate_schema
project_critic_consensus
trace_to_mutation_hints
```

</details>

<details><summary>Supported exports (41)</summary>

```text
decision_packet_invocation_input_refs
require_canonical_decision_packet_invocation
DECISION_PACKET_INVOCATION_KIND
DecisionPacketInvocationRecord
CanonicalDecisionPacketInvocation
CompletedDecisionPacketExecution
EpochCertificateIssuanceNonReceipt
EpochCertificateIssuanceOwner
PersistedEpochCertificateIssuancePreparation
require_canonical_decision_packet_execution
DecisionValidityService
GOVERNANCE_MONITOR_EVENT_KIND
resolve_governance_monitor_event
BudgetState
CritiqueReport
DraftResult
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
| `polisyos.runtime.quality` | `src/polisyos/runtime/quality/__init__.py` | `eager_exports` | 973 |

#### `polisyos.runtime.quality`

- Source: `src/polisyos/runtime/quality/__init__.py`
- Facade: `eager_exports`
- Summary: Runtime quality evaluation helpers.

<details><summary>Entrypoint exports (973)</summary>

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
AcquisitionRequirementBasisBinding
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
RealValueOwnerGateway
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
ValueOwnerSourceProjectionRequestV1
ValueOwnerSourceVariableProjectionV1
ValueScheduleReviewStatus
ValueSourceClass
ValueTradeoffDisclosureRecord
ValueTransportRunReceiptV1
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
gy_content_hash_rows
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
resolve_production_approval_currentness_receipt
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
validate_persisted_acquisition_planner_report
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

<details><summary>Supported exports (973)</summary>

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
AcquisitionRequirementBasisBinding
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
RealValueOwnerGateway
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
ValueOwnerSourceProjectionRequestV1
ValueOwnerSourceVariableProjectionV1
ValueScheduleReviewStatus
ValueSourceClass
ValueTradeoffDisclosureRecord
ValueTransportRunReceiptV1
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
gy_content_hash_rows
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
resolve_production_approval_currentness_receipt
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
validate_persisted_acquisition_planner_report
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
| `polisyos.lex` | `src/polisyos/lex/__init__.py` | `lazy_facade` | 61 |
| `polisyos.lex.knowledge` | `src/polisyos/lex/knowledge/__init__.py` | `lazy_facade` | 15 |

#### `polisyos.lex`

- Source: `src/polisyos/lex/__init__.py`
- Facade: `lazy_facade`
- Summary: Stable Lex facade for runtime legal evaluation, NormPack assembly, and interventions.

<details><summary>Entrypoint exports (61)</summary>

```text
ActiveVersionResult
ActiveVersionStrategy
AffectedKPI
ChangeProposalRef
ComplianceDelta
ComplianceTransition
ConstraintSeverity
HierarchicalPolicySearchPlan
InterventionKnobDictionaryEntry
InterventionKnobSpec
LegalConstraint
LegalConstraintBridge
LegalConstraintSet
LegalEvaluationRequest
LegalKnowledgeGraph
LegalReportRef
LegalSourceRelationRefusal
LegalSourceRelationVerificationMissingError
LegalToDAGMapping
LegalToDAGMappingType
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
evaluate_transport_constraints
is_transport_blocked
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

<details><summary>Entrypoint exports (15)</summary>

```text
LegalEntity
LegalFact
LegalFactResult
LegalKnowledgeGraph
LegalKnowledgeStore
LegalProvision
LegalProvisionResult
LegalQueryInput
LegalQueryProfile
LegalQueryProfileError
LegalRuleThresholdRow
LegalSearchResult
LegalTemporalCompetence
LegalThresholdEvaluation
search_legal_knowledge
```

</details>

<details><summary>Supported exports (61)</summary>

```text
ActiveVersionResult
ActiveVersionStrategy
AffectedKPI
ChangeProposalRef
ComplianceDelta
ComplianceTransition
ConstraintSeverity
HierarchicalPolicySearchPlan
InterventionKnobDictionaryEntry
InterventionKnobSpec
LegalConstraint
LegalConstraintBridge
LegalConstraintSet
LegalEvaluationRequest
LegalKnowledgeGraph
LegalReportRef
LegalSourceRelationRefusal
LegalSourceRelationVerificationMissingError
LegalToDAGMapping
LegalToDAGMappingType
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
evaluate_transport_constraints
is_transport_blocked
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
| `polisyos.scholar` | `src/polisyos/scholar/__init__.py` | `lazy_facade` | 30 |

#### `polisyos.scholar`

- Source: `src/polisyos/scholar/__init__.py`
- Facade: `lazy_facade`
- Summary: Expose Scholar enrichment entrypoints and contracts via lazy imports.

<details><summary>Entrypoint exports (30)</summary>

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
SourceSnippet
WebEvidenceBundle
build_scholar_academic_evidence_report
build_scholar_academic_evidence_report_from_web_bundle
build_scholar_spine_evidence_binding
enrich_topic
normalize_scholar_academic_evidence_report
persist_knowledge_bundle_payload
sanitize_untrusted_text
scholar_academic_evidence_required
scholar_citation_from_fabric_decision_data
validate_source_snippet_spans
validate_web_evidence_source_binding
```

</details>

<details><summary>Supported exports (30)</summary>

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
SourceSnippet
WebEvidenceBundle
build_scholar_academic_evidence_report
build_scholar_academic_evidence_report_from_web_bundle
build_scholar_spine_evidence_binding
enrich_topic
normalize_scholar_academic_evidence_report
persist_knowledge_bundle_payload
sanitize_untrusted_text
scholar_academic_evidence_required
scholar_citation_from_fabric_decision_data
validate_source_snippet_spans
validate_web_evidence_source_binding
```

</details>

## `polisyos.data_forge`

- Classification: `public_experimental`
- Supported entrypoints: `polisyos.data_forge`, `polisyos.data_forge.read_api`, `polisyos.data_forge.read_api.academic`, `polisyos.data_forge.read_api.catalog`, `polisyos.data_forge.read_api.legal`, `polisyos.data_forge.read_api.ukraine`
- Facade policy: expected `lazy_facade`, observed `lazy_facade`
- Owner: `team-data-forge`
- README: `src/polisyos/data_forge/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Experimental asset-centric build-time Data Forge facade. The top-level package lazily exports build-time artifact, asset, schema, snapshot, provenance, quality, and migration-test contracts; read_api is the only runtime import surface and includes the explicit Legal runtime-material and Ukraine source-snapshot and demographic reader facades.
- Summary: Data Forge public facade for build-time artifact contracts and read APIs.

### Resolved supported entrypoints

| Entrypoint | Source | Facade | Exports |
| --- | --- | --- | ---: |
| `polisyos.data_forge` | `src/polisyos/data_forge/__init__.py` | `lazy_facade` | 49 |
| `polisyos.data_forge.read_api` | `src/polisyos/data_forge/read_api/__init__.py` | `lazy_facade` | 30 |
| `polisyos.data_forge.read_api.academic` | `src/polisyos/data_forge/read_api/academic.py` | `lazy_facade` | 110 |
| `polisyos.data_forge.read_api.catalog` | `src/polisyos/data_forge/read_api/catalog.py` | `lazy_facade` | 156 |
| `polisyos.data_forge.read_api.legal` | `src/polisyos/data_forge/read_api/legal.py` | `lazy_facade` | 61 |
| `polisyos.data_forge.read_api.ukraine` | `src/polisyos/data_forge/read_api/ukraine.py` | `lazy_facade` | 75 |

#### `polisyos.data_forge`

- Source: `src/polisyos/data_forge/__init__.py`
- Facade: `lazy_facade`
- Summary: Data Forge public facade for build-time artifact contracts and read APIs.

<details><summary>Entrypoint exports (49)</summary>

```text
COMPLIANCE_OVERRIDE_REQUIRED_FIELDS
DATA_FORGE_PROVENANCE_MANIFEST_FILE
DATA_FORGE_PROVENANCE_MANIFEST_SCHEMA_VERSION
PRIVACY_COMPLIANCE_REPORT_SCHEMA_VERSION
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
OfficialSnapshotAnswer
PIILevel
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

<details><summary>Entrypoint exports (30)</summary>

```text
READ_API_SURFACES
UKRAINE_D4_SOURCE_JSON_SNAPSHOT_ROLE_BY_CONTRACT
GenerationBasis
OfficialSnapshotAnswer
ReadApiSurface
UkraineD4GovernanceRequest
UkraineIdentityResolutionCohort
UkraineIdentityResolutionCohortRow
academic
available_surfaces
build_generation_basis
build_privacy_compliance_report
catalog
compliance
finalize_snapshot
get_surface
legal
load_surface
normalize_privacy_compliance_report
pipeline_binding_surface
prepare_publish_manifest
prepare_snapshot_binding_meaning
provenance
read_manifest
read_snapshot_binding_meaning
surface_module
surfaces
ukraine
ukraine_d4_json_snapshot_model_type
write_publish_manifest
```

</details>

#### `polisyos.data_forge.read_api.academic`

- Source: `src/polisyos/data_forge/read_api/academic.py`
- Facade: `lazy_facade`
- Summary: Runtime-safe read API for academic Data Forge artifacts.

<details><summary>Entrypoint exports (110)</summary>

```text
ACADEMIC_ASSET_GROUP
ACADEMIC_ASSET_SCHEMA_CONTRACTS
ACADEMIC_BATCH_SCHEMA_CONTRACTS
ACADEMIC_BATCH_STAGE_DEPENDENCIES
ACADEMIC_BATCH_STAGE_ID_PATTERN
ACADEMIC_BATCH_STAGE_ORDER
ACADEMIC_CLAIMS_KEY
ACADEMIC_EXTRACTED_CLAIMS_KEY
ACADEMIC_FULLTEXT_KEY
ACADEMIC_NORMALIZED_WORKS_KEY
ACADEMIC_PUBLISHED_CLAIMS_KEY
ACADEMIC_RAW_WORKS_KEY
ACADEMIC_READINESS_KEY
ACADEMIC_SCHEMA_CONTRACTS
ACADEMIC_SKG_KEY
AcademicBatchConfig
AcademicBatchRunProfile
AcademicBatchStagePlan
AcademicBatchStageSpec
AcademicBenchmarkReport
AcademicQCReport
AcademicReadinessPackage
AcademicReadinessSummary
AcademicSKGSummary
AcademicSKGTableSummary
AcademicShadowArtifact
AcademicShadowBundle
AcademicShadowDiff
AcademicStageManifest
CANONICAL_VARIABLES
CORE_ACADEMIC_BATCH_STAGES
CanonicalVariableResolver
CausalClaimResult
CausalClaimResultV1
CausalClaimResultV2
ClaimAdjudicationRules
ClaimAdjudicationVerifier
ClaimConsensusRule
ClaimLineageAuditPage
ClaimLineageAuditRecord
ClaimLineageCursorError
ClaimTableSchemaError
ClaimVocabularyLimitation
ClaimVocabularyProjectionBinding
ClaimVocabularySourceRowBinding
ConfidenceLayerVintage
EstimateCandidate
GonkaMultiKeyPool
OpenAlexClient
OpenAlexRequest
ParameterCandidate
ParameterPrior
ParameterSelector
PreparedSKGCredalSourceRows
PreparedSKGRead
PreparedSKGReadReceipt
RUNTIME_CANONICAL_REGISTRY
RUNTIME_CANONICAL_REGISTRY_VERSION
RetainedSKGSnapshot
RetainedSKGSnapshotChunk
RetainedSKGSnapshotError
RetainedSKGSnapshotRecord
RetainedSKGSnapshotV10
RetainedSKGSnapshotV11
RetainedSKGSourceBinding
SKGQuery
STRONG_DESIGN_FAMILIES
ScholarKnowledgeGraph
SourceIdentityBundle
SourceIdentitySelection
SourceReferencePopulation
SourceSnapshot
WorkRecord
WorkSearchResult
aggregate_claim_rows
audit_academic_claim_lineage
build_academic_batch_asset_group
build_academic_schema_registry
claim_guardrails
claim_metrics
claim_policy_publishable
claim_promotion_policy
compare_academic_shadow_bundles
confidence_layer_vintage_for_snapshot_digest
iter_causal_claim_results_v2
load_academic_benchmark_report
load_academic_qc_report
load_academic_readiness_package
load_academic_shadow_bundle
load_academic_skg_summary
load_causal_claim_results_v2
load_retained_skg_snapshot
materialize_claim_adjudication_result
metric_is_improved
plan_academic_batch_stages
produce_claim_adjudication_input
produce_source_identity_bundle
read_claim_promotion_predecessor
read_source_reference_population
replay_source_identity_bundle
require_selected_artifact_ref
retained_skg_source_binding
run_edge_synthesize
runtime_approved_synonyms
runtime_canonical_entries
runtime_canonical_names
same_selected_artifact_ref
select_academic_batch_stages
selected_artifact_ref_for_input
validate_claim_adjudication_input_batch
```

</details>

#### `polisyos.data_forge.read_api.catalog`

- Source: `src/polisyos/data_forge/read_api/catalog.py`
- Facade: `lazy_facade`
- Summary: Runtime-safe read API for catalog Data Forge artifacts.

<details><summary>Entrypoint exports (156)</summary>

```text
AcquisitionAuthorityEntry
AcquisitionAuthorityError
AcquisitionAuthorityProvision
AcquisitionAuthorityRegistry
AcquisitionDatasetRegistration
ActivatedAcquisitionObservationProjection
AuthoritySchemaColumn
BaselineIdentity
BaselineMutationError
CATALOG_ASSET_GROUP
CATALOG_BASE_SCHEMA_CONTRACTS
CATALOG_BASE_SCHEMA_IDS
CATALOG_INDEX_KEY
CATALOG_NORMALIZED_DATASETS_KEY
CATALOG_OBSERVATIONS_KEY
CATALOG_RAW_SOURCES_KEY
CATALOG_READINESS_KEY
CATALOG_SCHEMA_CONTRACTS
CATALOG_SOURCE_MODULES_KEY
CATALOG_SOURCE_PREFLIGHT_KEY
CATALOG_SOURCE_SCHEMA_CONTRACTS
CORE_CATALOG_SOURCE_MODULES
CanonicalAcquisitionAuthority
CanonicalAcquisitionObservation
CatalogAcquisitionEpochProjection
CatalogAcquisitionEventProjection
CatalogAcquisitionOverlay
CatalogAcquisitionPassportProjection
CatalogAcquisitionStateProjection
CatalogBenchmarkReport
CatalogContentIdentity
CatalogEmbeddingProfile
CatalogExecutionTier
CatalogFetchBinding
CatalogFetchRequest
CatalogFetchResolution
CatalogHistoryPolicy
CatalogQCReport
CatalogQueryGenerationContext
CatalogReadSourceError
CatalogReadinessPackage
CatalogReadinessSummary
CatalogRunLane
CatalogRunProfile
CatalogSelectionCandidateEvaluation
CatalogSelectionCandidateEvidence
CatalogSelectionError
CatalogSelectionPolicyConfig
CatalogSelectionRejectionCode
CatalogSelectionRoleConfig
CatalogShadowArtifact
CatalogShadowBundle
CatalogShadowDiff
CatalogSourceAssetKeys
CatalogSourceModulePlan
CatalogSourceModuleSpec
CatalogSourceRegistryEntry
CatalogSourceRegistrySpec
CatalogSourceStage
CatalogSourceStageContract
CatalogSourceSummary
CatalogStageManifest
DEFAULT_ACQUISITION_AUTHORITY_PROVISION
DEFAULT_ACQUISITION_OVERLAY_PATH
DEFAULT_LOCAL_RIGHTS_TRUST_REGISTRY
DatasetCatalogGraph
DatasetCatalogStore
DatasetRegistry
DatasetSearchResponse
DatasetSearchResult
DerivationCatalogSelectionOwner
EmbeddingGenerationRef
GENERATION_SELECTOR_FILENAME
LEGACY_ADMISSION_PASSPORT_SCHEMA_VERSION
LegacyAdmissionPassport
LiveHarnessReceiptProvisionEntry
LiveSourceExecutionEvidence
LocalRightsTrustRegistry
LocalRightsTrustedAuthority
LocalSourceRightsDeclaration
LocalSourceRightsReceipt
MetricBindingMatch
MetricFieldBinding
ObservationProvenanceClass
OverlayAdmissionError
OverlayAdmissionReceipt
PStarZResult
ProxyCandidate
ProxyChain
ResolvedAcquisitionAuthority
ResolvedFetchTarget
ResolvedL5Trust
ResolvedLiveHarnessReceipt
SearchFilters
VariableAlignment
WVSIndicatorRegistryError
WVSIndicatorRegistryReadError
acquisition_overlay_admission_fence
acquisition_overlay_admission_lock_path
build_acquisition_authority_provision
build_authority_entry
build_authority_registry
build_catalog_schema_registry
build_catalog_source_asset_group
build_live_source_execution_evidence
build_local_rights_trust_registry
build_local_source_rights_declaration
build_metric_field_binding
build_production_data_contract_catalog_graph
build_slice0_fixture_catalog_graph
catalog_default_resource_path
catalog_selection_candidate_rank
catalog_selection_policies_for_purpose
catalog_source_modules_from_registry
compare_catalog_shadow_bundles
compose_confidence_chain
compose_confidence_harmonic
confidence_layer_vintage_for_snapshot_digest
default_acquisition_overlay_path
default_catalog_source_registry_path
default_seed_alignments_path
derive_canonical_observations
derive_catalog_unit_from_text
derive_license_disposition
embedding_generation_manifest
embedding_generation_matches_encoder
evaluate_catalog_selection_candidate
generation_basis_matches_members
iso2_to_iso3
load_catalog_benchmark_report
load_catalog_qc_report
load_catalog_readiness_package
load_catalog_shadow_bundle
load_catalog_source_registry
load_derivation_catalog_selection
load_seed_alignments
normalize_acquisition_unit
normalize_country_code
normalized_acquisition_source_body
open_catalog_read_session
parse_profile_input_coverage
plan_catalog_source_modules
plan_catalog_source_stage_contracts
profile_input_coverage_currentness
project_catalog_acquisition_state
read_wvs_indicator_registry
resolve_catalog_selection_policy
resolve_embedding_generation
resolve_live_temporal_bounds
resolve_proxy
score_variable_pair
select_catalog_source_modules
validate_catalog_run_profile
validate_overlay_admission_receipt
validate_proxy
verify_local_source_rights
```

</details>

#### `polisyos.data_forge.read_api.legal`

- Source: `src/polisyos/data_forge/read_api/legal.py`
- Facade: `lazy_facade`
- Summary: Runtime-safe read and material-owner API for Legal Data Forge artifacts.

<details><summary>Entrypoint exports (61)</summary>

```text
BatchConfig
CURRENT_LEGAL_SOURCE_RELATION_DISPOSITION
DocSourcePropsV1
EmbeddingGenerationRef
GenerationIdentity
GonkaClientPool
LEGAL_BATCH_RUNTIME_MODULE
LEGAL_EMBEDDING_PROJECTION_RULE_VERSION
LEGAL_RUNTIME_MATERIAL_RULE_VERSION
LEGAL_SOURCE_RELATION_REFUSAL
LEGAL_SOURCE_RELATION_REFUSAL_CODE
LegalCandidateTrustTier
LegalKnowledgeGraphFact
LegalRuntimeMaterialError
LegalRuntimeMaterialHandle
LegalRuntimeMaterialOwner
LegalSearchBenchmarkCase
LegalShadowArtifact
LegalShadowBundle
LegalShadowDiff
LegalSourceRelationDisposition
LegalSourceRelationRefusal
LegalSourceRelationRefusalCode
LegalSourceRelationStatus
LegalSourceRelationVerificationMissingError
LegalStageManifest
NPADocument
ProgressTracker
ProvisionEntryV1
ProvisionIndexV1
SPO_LIGHT_BATCH_SYSTEM_PROMPT
SPO_LIGHT_SYSTEM_PROMPT
ThresholdAtom
VersionEntryV1
VersionIndexV1
_group_items_by_request_budget
build_spo_light_batch_user_prompt
build_spo_light_user_prompt
collect_amendment_quality_metrics
compare_lex_shadow_bundles
current_legal_source_relation_disposition
derive_encoder_identity
embedding_generation_matches_encoder
entity_embedding_text
export_normative_claim_sets
fact_embedding_text
generation_basis_matches_members
hnsw_index_matches_vectors
iter_documents
legal_embedding_generator_rule_version
legal_search_benchmark_cases
load_doc_source_props
load_lex_shadow_bundle
load_provision_index
load_version_index
provision_embedding_text
require_legal_source_relation_verification
resolve_active_version
resolve_embedding_generation
run_batch_pipeline
search_legal_knowledge_graph
```

</details>

#### `polisyos.data_forge.read_api.ukraine`

- Source: `src/polisyos/data_forge/read_api/ukraine.py`
- Facade: `lazy_facade`
- Summary: Runtime-safe read API for Ukraine source snapshots and demographic artifacts.

<details><summary>Entrypoint exports (75)</summary>

```text
ArtifactRecord
CalibrationBundleManifest
D5ReleaseHandoffRequest
DemographyRoleProjection
DemographySourceEvidence
DemographySourceRequest
HistoricalLayoutRequest
HouseholdDiagnosticPanelBasis
InventorySourceRequest
NormalizedArtifactManifest
REAL_BACKTEST_BUNDLE_CONTRACT_FQN
RealBacktestBundleContract
ReleaseManifest
SourceResolutionRefusalError
SourceSnapshotManifest
UKRAINE_ASSET_GROUP
UKRAINE_D4_SOURCE_JSON_SNAPSHOT_ROLE_BY_CONTRACT
UKRAINE_DEMOGRAPHY_DONOR_POOL_KEY
UKRAINE_DEMOGRAPHY_PRIORS_KEY
UKRAINE_DEMOGRAPHY_SOURCE_INVENTORY_KEY
UKRAINE_DEMOGRAPHY_TARGETS_KEY
UKRAINE_NORMALIZED_SOURCES_KEY
UKRAINE_PERIOD_PROJECTION_VERSION
UKRAINE_RAW_SOURCES_KEY
UKRAINE_READINESS_KEY
UKRAINE_SOURCE_CONFIG_KEY
UKRAINE_STATIC_AGING_INPUTS_KEY
UkraineD4GovernanceRequest
UkraineDemographyArtifacts
UkraineIdentityResolutionCohort
UkraineIdentityResolutionCohortRow
UkraineJSONSnapshotProvenance
UkraineJSONSnapshotRead
UkraineJSONSnapshotRefusalError
UkraineLexPreShardDiff
UkraineLexPreShardSummary
UkraineLexShardEntry
UkraineLexShardPassSummary
UkraineReadinessSummary
UkraineShadowArtifact
UkraineShadowBundle
UkraineShadowDiff
UkraineSourceSummary
UkraineStageArtifactVerificationError
VerifiedUkraineReleaseArtifact
VerifiedUkraineReleaseArtifacts
VerifiedUkraineStageArtifact
VerifiedUkraineStageArtifacts
build_household_diagnostic_panel
build_static_aging_state
compare_lex_pre_shard_summaries
compare_ukraine_shadow_bundles
directory_tree_entries
infer_lex_snapshot_label
lex_pre_shard_index
lex_pre_shard_pass_name
load_demography_artifacts
load_demography_candidate_artifacts
load_donor_pool
load_lex_pre_shard_summary
load_manifest
load_reconciled_targets
load_transition_priors
load_ukraine_shadow_bundle
load_verified_release_artifact_bytes
load_verified_release_artifacts
load_verified_release_json_artifact
load_verified_release_manifest_json
load_verified_stage_artifacts
load_verified_stage_json_output
load_verified_stage_manifest_json
load_verified_stage_output_bytes
project_ukraine_observation_periods
read_ukraine_json_snapshot
ukraine_d4_json_snapshot_model_type
```

</details>

<details><summary>Supported exports (49)</summary>

```text
COMPLIANCE_OVERRIDE_REQUIRED_FIELDS
DATA_FORGE_PROVENANCE_MANIFEST_FILE
DATA_FORGE_PROVENANCE_MANIFEST_SCHEMA_VERSION
PRIVACY_COMPLIANCE_REPORT_SCHEMA_VERSION
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
OfficialSnapshotAnswer
PIILevel
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
| `polisyos.berl` | `src/polisyos/berl/__init__.py` | `eager_exports` | 16 |

#### `polisyos.berl`

- Source: `src/polisyos/berl/__init__.py`
- Facade: `eager_exports`
- Summary: Bounded Explanation Reliability Layer public API.

<details><summary>Entrypoint exports (16)</summary>

```text
EmpiricalBoundResult
ExplanationBundle
ExplanationBundleStoreReadError
ExplanationOrchestrator
ExplanationRequest
ExplanationValidationResult
ValidationThresholds
empirical_bernstein_upper_bound
estimate_local_infidelity
explain_and_persist
hoeffding_upper_bound
load_explanation_bundle
persist_explanation_bundle
summarize_explanation_response
validate_explanation_bundle
validate_persisted_explanation_bundle_payload
```

</details>

<details><summary>Supported exports (16)</summary>

```text
EmpiricalBoundResult
ExplanationBundle
ExplanationBundleStoreReadError
ExplanationOrchestrator
ExplanationRequest
ExplanationValidationResult
ValidationThresholds
empirical_bernstein_upper_bound
estimate_local_infidelity
explain_and_persist
hoeffding_upper_bound
load_explanation_bundle
persist_explanation_bundle
summarize_explanation_response
validate_explanation_bundle
validate_persisted_explanation_bundle_payload
```

</details>

## `polisyos.calibration`

- Classification: `public_experimental`
- Supported entrypoints: `polisyos.calibration`
- Facade policy: expected `eager_exports`, observed `lazy_facade`
- Owner: `team-scientist`
- README: `src/polisyos/calibration/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Canonical shared calibration diagnostics, recalibration, and validation-report API. Foundry and DDM calibration contexts remain package-specific.
- Summary: Calibration diagnostics public entrypoints.

### Resolved supported entrypoints

| Entrypoint | Source | Facade | Exports |
| --- | --- | --- | ---: |
| `polisyos.calibration` | `src/polisyos/calibration/__init__.py` | `lazy_facade` | 17 |

#### `polisyos.calibration`

- Source: `src/polisyos/calibration/__init__.py`
- Facade: `lazy_facade`
- Summary: Calibration diagnostics public entrypoints.

<details><summary>Entrypoint exports (17)</summary>

```text
REFERENCE_PROFILES
CalibrationPoint
CalibrationResult
EmpiricalCalibrationContext
EmpiricalCalibrationEvidenceRef
EvidenceArtifactRef
apply_calibrator
compare_calibrators
compute_calibration_curve
evaluate_binary
evaluate_continuous
evaluate_multiclass
fit_calibrator
load_empirical_calibration_evidence
persist_empirical_calibration_evidence
produce_empirical_calibration_evidence
to_validation_report
```

</details>

<details><summary>Supported exports (17)</summary>

```text
REFERENCE_PROFILES
CalibrationPoint
CalibrationResult
EmpiricalCalibrationContext
EmpiricalCalibrationEvidenceRef
EvidenceArtifactRef
apply_calibrator
compare_calibrators
compute_calibration_curve
evaluate_binary
evaluate_continuous
evaluate_multiclass
fit_calibrator
load_empirical_calibration_evidence
persist_empirical_calibration_evidence
produce_empirical_calibration_evidence
to_validation_report
```

</details>

## `polisyos.ddm`

- Classification: `internal`
- Supported entrypoints: `polisyos.ddm`
- Facade policy: expected `lazy_facade`, observed `lazy_facade`
- Owner: `team-scientist`
- README: `src/polisyos/ddm/README.md`
- Reference doc: `docs/reference/public-surface.md`
- Notes: Canonical unversioned drift/degradation monitor surface. It is registered to prevent accidental deep-import promotion, not as a stable public API.
- Summary: Drift-and-Degradation Monitor for Phase 5 Problem 15.7.

### Resolved supported entrypoints

| Entrypoint | Source | Facade | Exports |
| --- | --- | --- | ---: |
| `polisyos.ddm` | `src/polisyos/ddm/__init__.py` | `lazy_facade` | 17 |

#### `polisyos.ddm`

- Source: `src/polisyos/ddm/__init__.py`
- Facade: `lazy_facade`
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
