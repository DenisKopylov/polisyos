"""Identity and profile-boundary tests for source50 Core/Common routes."""

from __future__ import annotations

import importlib

import pytest

IDENTITY_ROUTES = (
    ("polisyos.common.canonical", "polisyos.common.canonical", "CanonSpec"),
    ("polisyos.common.canonical", "polisyos.common.canonical", "from_canonical_bytes"),
    ("polisyos.common.canonical", "polisyos.common.canonical", "from_canonical_obj"),
    ("polisyos.common.canonical", "polisyos.common.canonical", "to_canonical_bytes"),
    (
        "polisyos.common.canonical_profile",
        "polisyos.common.canonical_profile",
        "CanonicalProfileDeclaration",
    ),
    (
        "polisyos.common.canonical_profile",
        "polisyos.common.canonical_profile",
        "CanonicalProfileRead",
    ),
    (
        "polisyos.common.canonical_profile",
        "polisyos.common.canonical_profile",
        "CanonicalProfileRefusalError",
    ),
    (
        "polisyos.common.canonical_profile",
        "polisyos.common.canonical_profile",
        "CanonicalProfileStatus",
    ),
    (
        "polisyos.common.canonical_profile",
        "polisyos.common.canonical_profile",
        "decode_profiled_canonical_bytes",
    ),
    (
        "polisyos.common.canonical_profile",
        "polisyos.common.canonical_profile",
        "parse_canonical_profile",
    ),
    (
        "polisyos.common.canonical_profile",
        "polisyos.common.canonical_profile",
        "require_declared_profile",
    ),
    ("polisyos.common.hashing", "polisyos.common.hashing", "DeprecatedHashAlgorithm"),
    ("polisyos.common.hashing", "polisyos.common.hashing", "HashAlgorithm"),
    ("polisyos.common.hashing", "polisyos.common.hashing", "content_hash"),
    ("polisyos.common.hashing", "polisyos.common.hashing", "streaming_hash"),
    ("polisyos.common.hashing", "polisyos.common.hashing", "truncated_hash"),
    (
        "polisyos.common.migrations.base",
        "polisyos.common.migrations",
        "ArtifactPayload",
    ),
    (
        "polisyos.core.artifacts.backends.config",
        "polisyos.core.artifacts",
        "ArtifactStoreConfig",
    ),
    (
        "polisyos.core.artifacts.backends.config",
        "polisyos.core.artifacts",
        "build_artifact_store",
    ),
    (
        "polisyos.core.artifacts.canonical_profile",
        "polisyos.common.canonical_profile",
        "CanonicalProfileRead",
    ),
    (
        "polisyos.core.artifacts.canonical_profile",
        "polisyos.common.canonical_profile",
        "CanonicalProfileRefusalError",
    ),
    (
        "polisyos.core.artifacts.canonical_profile",
        "polisyos.core.artifacts",
        "artifact_ref_for_manifest",
    ),
    (
        "polisyos.core.artifacts.canonical_profile",
        "polisyos.core.artifacts",
        "load_core_json_artifact",
    ),
    (
        "polisyos.core.artifacts.canonical_profile",
        "polisyos.core.artifacts",
        "read_core_json_artifact",
    ),
    (
        "polisyos.core.artifacts.canonical_profile",
        "polisyos.core.artifacts",
        "read_core_manifest_profile",
    ),
    ("polisyos.core.artifacts.ids", "polisyos.core.artifacts", "ArtifactID"),
    (
        "polisyos.core.artifacts.manifest",
        "polisyos.core.artifacts",
        "ArtifactAuthorityInfo",
    ),
    ("polisyos.core.artifacts.manifest", "polisyos.core.artifacts", "ArtifactManifest"),
    ("polisyos.core.artifacts.manifest", "polisyos.core.artifacts", "ArtifactRef"),
    (
        "polisyos.core.artifacts.manifest",
        "polisyos.core.artifacts",
        "ArtifactSameInputClosureInfo",
    ),
    (
        "polisyos.core.artifacts.manifest",
        "polisyos.core.artifacts",
        "ArtifactTenantContextInfo",
    ),
    ("polisyos.core.artifacts.manifest", "polisyos.core.artifacts", "InputRef"),
    ("polisyos.core.artifacts.manifest", "polisyos.core.artifacts", "ProducerInfo"),
    ("polisyos.core.artifacts.manifest", "polisyos.core.artifacts", "SchemaInfo"),
    (
        "polisyos.core.artifacts.manifest",
        "polisyos.core.artifacts",
        "artifact_ref_identity_key",
    ),
    (
        "polisyos.core.artifacts.manifest",
        "polisyos.core.artifacts",
        "input_ref_from_artifact_ref",
    ),
    (
        "polisyos.core.artifacts.ownership",
        "polisyos.core.artifacts",
        "OWNERSHIP_INDEX_FORMAT_POINTER_GENERATION_V1",
    ),
    (
        "polisyos.core.artifacts.ownership",
        "polisyos.core.artifacts",
        "OWNERSHIP_INDEX_SCHEMA_VERSION",
    ),
    ("polisyos.core.artifacts.protocol", "polisyos.core.artifacts", "ArtifactStore"),
    (
        "polisyos.core.artifacts.protocol",
        "polisyos.core.artifacts",
        "RootedArtifactStore",
    ),
    (
        "polisyos.core.artifacts.protocol",
        "polisyos.core.artifacts",
        "resolve_manifest_by_profile",
    ),
    (
        "polisyos.core.artifacts.registry",
        "polisyos.core.artifacts",
        "RegistryBundlePayload",
    ),
    (
        "polisyos.core.artifacts.store",
        "polisyos.core.artifacts",
        "ArtifactMemberReceipt",
    ),
    ("polisyos.core.artifacts.store", "polisyos.core.artifacts", "FileSystemCAS"),
    ("polisyos.core.artifacts.store", "polisyos.core.artifacts", "PutOptions"),
    (
        "polisyos.core.artifacts.write_contract",
        "polisyos.core.artifacts",
        "ArtifactWriteOptions",
    ),
    ("polisyos.core.canon.canon_json", "polisyos.core.canon", "CanonSpec"),
    ("polisyos.core.canon.canon_json", "polisyos.core.canon", "to_canonical_bytes"),
    (
        "polisyos.core.contracts.c4_persisted_profiles",
        "polisyos.core.contracts",
        "c4_framed_semantic_projection_digest",
    ),
    ("polisyos.core.contracts.control", "polisyos.core.contracts", "DataNeed"),
    (
        "polisyos.core.contracts.control",
        "polisyos.core.contracts",
        "DecisionValidityEventRequest",
    ),
    ("polisyos.core.contracts.control", "polisyos.core.contracts", "PolicyFlags"),
    (
        "polisyos.core.contracts.control_admission_attempt",
        "polisyos.core.contracts",
        "CONTROL_PRE_ADMISSION_SETTLEMENT_REQUIRED_PROFILES",
    ),
    (
        "polisyos.core.contracts.control_admission_attempt",
        "polisyos.core.contracts",
        "ControlPreAdmissionAttemptEventInfo",
    ),
    (
        "polisyos.core.contracts.control_admission_attempt",
        "polisyos.core.contracts",
        "ControlPreAdmissionAttemptResponse",
    ),
    (
        "polisyos.core.contracts.control_admission_attempt",
        "polisyos.core.contracts",
        "ControlPreAdmissionAttemptStatus",
    ),
    (
        "polisyos.core.contracts.control_admission_attempt",
        "polisyos.core.contracts",
        "ControlPreAdmissionOwnerBinding",
    ),
    (
        "polisyos.core.contracts.control_admission_attempt",
        "polisyos.core.contracts",
        "NO_CALL_REASON_VALUES",
    ),
    (
        "polisyos.core.contracts.control_admission_attempt",
        "polisyos.core.contracts",
        "NoCallReason",
    ),
    (
        "polisyos.core.contracts.control_admission_attempt",
        "polisyos.core.contracts",
        "PRODUCER_CALL_STATE_VALUES",
    ),
    (
        "polisyos.core.contracts.control_admission_attempt",
        "polisyos.core.contracts",
        "ProducerCallState",
    ),
    (
        "polisyos.core.contracts.control_admission_attempt",
        "polisyos.core.contracts",
        "validate_producer_call_observation",
    ),
    ("polisyos.core.contracts.fabric", "polisyos.core.contracts", "DataSnapshot"),
    ("polisyos.core.contracts.fabric", "polisyos.core.contracts", "DataSnapshotRef"),
    ("polisyos.core.contracts.fabric", "polisyos.core.contracts", "DataViewRequestRef"),
    (
        "polisyos.core.contracts.foundry",
        "polisyos.core.contracts",
        "EquilibriumMultiplicityReport",
    ),
    ("polisyos.core.contracts.foundry", "polisyos.core.contracts", "ExecPlan"),
    ("polisyos.core.contracts.foundry", "polisyos.core.contracts", "FeedbackConfig"),
    (
        "polisyos.core.contracts.foundry",
        "polisyos.core.contracts",
        "FeedbackSolveResult",
    ),
    ("polisyos.core.contracts.foundry", "polisyos.core.contracts", "FoundryExecConfig"),
    (
        "polisyos.core.contracts.foundry",
        "polisyos.core.contracts",
        "FoundryExecutionInputBasis",
    ),
    (
        "polisyos.core.contracts.foundry",
        "polisyos.core.contracts",
        "FoundryExecutionInputBasisRef",
    ),
    (
        "polisyos.core.contracts.foundry",
        "polisyos.core.contracts",
        "FoundryInputBindings",
    ),
    ("polisyos.core.contracts.foundry", "polisyos.core.contracts", "Metrics"),
    (
        "polisyos.core.contracts.foundry",
        "polisyos.core.contracts",
        "ParameterOverrideBundle",
    ),
    ("polisyos.core.contracts.foundry", "polisyos.core.contracts", "ProgramGraph"),
    ("polisyos.core.contracts.foundry", "polisyos.core.contracts", "SimulationResult"),
    ("polisyos.core.contracts.foundry", "polisyos.core.contracts", "StateDelta"),
    ("polisyos.core.contracts.runtime", "polisyos.core.contracts", "ApiMeta"),
    ("polisyos.core.contracts.runtime", "polisyos.core.contracts", "RunDetails"),
    (
        "polisyos.core.contracts.scientist",
        "polisyos.core.contracts",
        "DecisionMonitoringContractRef",
    ),
    (
        "polisyos.core.contracts.scientist",
        "polisyos.core.contracts",
        "SourceVerificationReportRef",
    ),
    (
        "polisyos.core.contracts.scientist",
        "polisyos.core.contracts",
        "VerifiedPolicyReportRef",
    ),
    ("polisyos.core.governance.passes.base", "polisyos.core.governance", "PassContext"),
    (
        "polisyos.core.governance.passes.legal_pass",
        "polisyos.core.governance",
        "LegalPass",
    ),
    (
        "polisyos.core.governance.passes.safety_pass",
        "polisyos.core.governance",
        "SafetyPass",
    ),
    (
        "polisyos.core.governance.profiles",
        "polisyos.core.governance",
        "ValidationProfile",
    ),
    ("polisyos.core.llm.response", "polisyos.core.llm", "extract_llm_response_data"),
    ("polisyos.core.llm.response", "polisyos.core.llm", "normalize_llm_cost_evidence"),
    ("polisyos.core.llm.settlement", "polisyos.core.llm", "LLMProducerEvent"),
    ("polisyos.core.llm.traced_client", "polisyos.core.llm", "TracedLLMClient"),
    ("polisyos.core.security.access_scope", "polisyos.core.security", "AccessScope"),
    ("polisyos.core.security.identity", "polisyos.core.security", "PIIAccessLevel"),
    ("polisyos.core.security.identity", "polisyos.core.security", "PolicyOSRole"),
    (
        "polisyos.core.security.quality_gates",
        "polisyos.core.security",
        "SECURITY_ASSURANCE_ARTIFACT_KIND",
    ),
    (
        "polisyos.core.security.quality_gates",
        "polisyos.core.security",
        "SECURITY_ASSURANCE_ARTIFACT_MEDIA_TYPE",
    ),
    (
        "polisyos.core.security.quality_gates",
        "polisyos.core.security",
        "SECURITY_ASSURANCE_ARTIFACT_SCHEMA_NAME",
    ),
    (
        "polisyos.core.security.quality_gates",
        "polisyos.core.security",
        "SECURITY_ASSURANCE_ARTIFACT_SCHEMA_VERSION",
    ),
    (
        "polisyos.core.security.tenant_context",
        "polisyos.core.security",
        "clear_tenant_context",
    ),
    (
        "polisyos.core.security.tenant_context",
        "polisyos.core.security",
        "get_current_access_scope_or_none",
    ),
    (
        "polisyos.core.security.tenant_context",
        "polisyos.core.security",
        "reset_current_access_scope",
    ),
    (
        "polisyos.core.security.tenant_context",
        "polisyos.core.security",
        "set_current_access_scope",
    ),
)


MODULE_ATTRIBUTE_ROUTES = (
    ("polisyos.common", "async_tools"),
    ("polisyos.common", "logger"),
    ("polisyos.common", "migrations"),
    ("polisyos.common", "serialization"),
    ("polisyos.core", "errors"),
    ("polisyos.core", "registry"),
    ("polisyos.core", "run"),
)


@pytest.mark.parametrize(("old_module", "public_module", "name"), IDENTITY_ROUTES)
def test_public_route_preserves_the_exact_owner_object(
    old_module: str, public_module: str, name: str
) -> None:
    """A facade route must resolve to the owner binding, not a same-name copy."""
    old_value = getattr(importlib.import_module(old_module), name)
    public_value = getattr(importlib.import_module(public_module), name)
    assert public_value is old_value


@pytest.mark.parametrize(("root_module", "attribute"), MODULE_ATTRIBUTE_ROUTES)
def test_public_root_module_attribute_is_the_exact_child_module(
    root_module: str, attribute: str
) -> None:
    """Module-attribute rewrites must retain the same module object."""
    root = importlib.import_module(root_module)
    child = importlib.import_module(f"{root_module}.{attribute}")
    assert getattr(root, attribute) is child


def test_core_profile_identity_stays_distinct_from_shared_common_mechanics() -> None:
    """Core keeps its own contract/error behavior while reusing common mechanics."""
    common = importlib.import_module("polisyos.common.canonical")
    core = importlib.import_module("polisyos.core.canon")
    assert core.CanonSpec is not common.CanonSpec
    assert core.CanonViolation is not common.CanonicalError


def test_lifecycle_route_matches_existing_public_profile_digest() -> None:
    """Replacing private class access preserves the selected profile digest."""
    from polisyos.core.artifacts import (
        ArtifactID,
        ArtifactManifest,
        IntegrityInfo,
        artifact_manifest_profile_sha256,
    )
    from polisyos.core.artifacts._manifest_lifecycle import ManifestLifecycle

    manifest = ArtifactManifest(
        artifact_id=ArtifactID.from_sha256_hex("0" * 64),
        kind="test.profile",
        media_type="application/json",
        byte_size=0,
        integrity=IntegrityInfo(sha256="0" * 64),
    )
    assert artifact_manifest_profile_sha256(manifest) == ManifestLifecycle.profile_sha256(manifest)
