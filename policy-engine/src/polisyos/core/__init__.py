"""Expose the stable Core platform surface with lazy package imports.

The Core package owns CAS artifacts, component discovery, registry assembly,
security/observability primitives, and cross-layer contracts shared by runtime
and domain subsystems. Subpackages are imported lazily so `import polisyos.core`
remains safe in CLI/bootstrap paths that do not need optional heavy dependencies.

Only names listed in `__all__` are considered stable package-level API.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

_SUBPACKAGES = (
    "artifacts",
    "backends",
    "cache",
    "canon",
    "components",
    "contracts",
    "discovery",
    "errors",
    "evaluation",
    "llm",
    "observability",
    "pipeline",
    "registry",
    "resilience",
    "run",
)
_LAZY_EXPORTS = {
    "SECRET_AND_PII_SCAN_SCOPES": ("polisyos.core.llm", "SECRET_AND_PII_SCAN_SCOPES"),
    "SECRET_PII_DETECTOR_VERSION": ("polisyos.core.llm", "SECRET_PII_DETECTOR_VERSION"),
    "PromptSanitizer": ("polisyos.core.llm", "PromptSanitizer"),
    "SecretAndPIIScanReport": ("polisyos.core.llm", "SecretAndPIIScanReport"),
    "SecretPIIScanResult": ("polisyos.core.llm", "SecretPIIScanResult"),
    "scan_secret_and_pii": ("polisyos.core.llm", "scan_secret_and_pii"),
}
_CHRONOLOGY_EXPORTS = (
    "ApplicablePredicateDenominatorArtifactFailure",
    "ApplicablePredicateDenominatorStatement",
    "ChronologyApplicablePredicateDenominatorArtifacts",
    "ChronologyBundleHeader",
    "ChronologyBundleRequest",
    "ChronologyMemberInput",
    "ChronologyPersistenceFailure",
    "ChronologyPersistenceManifestMismatch",
    "ChronologyPersistenceNotEstablished",
    "ChronologyPersistenceStoreIntegrityMismatch",
    "ChronologyPersistenceVerificationMismatch",
    "ChronologyPredicatePolicyArtifacts",
    "ChronologyProofDomain",
    "ChronologyProofPersistenceFailed",
    "ChronologyProofPersistenceResult",
    "Digest",
    "EncodedChronologyBundle",
    "ExpectedCommitmentPrefix",
    "FULL_PREFIX_EVALUATION_TABLE",
    "FULL_PREFIX_FAILURE_DESCRIPTORS",
    "FULL_PREFIX_TERMINAL_BY_RESULT_KIND",
    "FullPrefixBuildFailureCode",
    "FullPrefixBuildRejected",
    "FullPrefixBuildResult",
    "FullPrefixCheckState",
    "FullPrefixEnvelopeFailureCode",
    "FullPrefixEnvelopeRejected",
    "FullPrefixEvaluationKey",
    "FullPrefixEvaluationState",
    "FullPrefixExpectedPrefixFailureCode",
    "FullPrefixExpectedPrefixRejected",
    "FullPrefixFailureDescriptor",
    "FullPrefixInputMode",
    "FullPrefixInternalConsistencyFailureCode",
    "FullPrefixInternalConsistencyRejected",
    "FullPrefixInvocationFailureCode",
    "FullPrefixInvocationRejected",
    "FullPrefixMemberFailureCode",
    "FullPrefixMemberRejected",
    "FullPrefixRejected",
    "FullPrefixTerminalCheck",
    "FullPrefixVerificationResult",
    "FullPrefixVerificationStatement",
    "FullPrefixVerified",
    "MemberPredicateDisposition",
    "NativeApplicablePredicateDenominatorPersistenceFailed",
    "NativeAuthorityHeadNotEstablished",
    "NativeChronologyCandidate",
    "NativeChronologyCandidateRejected",
    "NativeChronologyOwnerContext",
    "NativeChronologyPersistenceFailed",
    "NativeChronologyPolicyResolutionFailed",
    "NativeChronologyQualificationResult",
    "NativeChronologyQualified",
    "NativeChronologyQuery",
    "NativeChronologyReconciliation",
    "NativeExteriorAndAuthorityHeadNotEstablished",
    "NativeExteriorNotEstablished",
    "NativeFullPrefixBuildRejected",
    "NativeFullPrefixProofRejected",
    "NativePredicateRejected",
    "NativeProjectionCustodyGap",
    "NativeSchemaProfileRejected",
    "OwnerQualifiedNativeCandidate",
    "PersistedApplicablePredicateDenominator",
    "PersistedChronologyProof",
    "PersistedPredicateAdmissionPolicy",
    "PersistedPredicatePolicyAdmission",
    "PolicyAdmissionAmbiguousFailure",
    "PolicyAdmissionMissingFailure",
    "PolicyBindingMismatchFailure",
    "PolicyBytesMissingFailure",
    "PolicyOwnerDenominatorMismatchFailure",
    "PolicyOwnerRelationNotEstablished",
    "PolicyOwnerRelationRejected",
    "PolicyQueryBindingMismatchFailure",
    "PredicateAdmissionPolicyStatement",
    "PredicateAdmissionRule",
    "PredicateClass",
    "PredicateDisposition",
    "PredicatePolicyAdmissionIndex",
    "PredicatePolicyAdmissionStatement",
    "PredicatePolicyOwnerProvenanceVerifier",
    "PredicatePolicyOwnerRelationFailure",
    "PredicatePolicyResolutionContext",
    "PredicatePolicyResolutionFailure",
    "PredicatePolicySelectionKey",
    "QueryPredicateDisposition",
    "ResolvedPredicatePolicyAdmission",
    "VerifiedNativeMemberIdentity",
    "VerifiedNativeSubjectIdentity",
    "VerifiedOwnerPredicateEvidence",
    "VerifiedPolicyOwnerProvenance",
    "VerifiedPredicatePolicyOwnerRelation",
)
_LAZY_EXPORTS.update(
    {name: ("polisyos.core.contracts.chronology", name) for name in _CHRONOLOGY_EXPORTS}
)
_LAZY_EXPORTS.update(
    {
        "FullPrefixVerifier": (
            "polisyos.core.security.full_prefix",
            "FullPrefixVerifier",
        ),
        "build_full_prefix_bundle": (
            "polisyos.core.security.full_prefix",
            "build_full_prefix_bundle",
        ),
    }
)

if TYPE_CHECKING:
    from polisyos.core.security.full_prefix import (
        FullPrefixVerifier,
        build_full_prefix_bundle,
    )

__all__ = [
    "FULL_PREFIX_EVALUATION_TABLE",
    "FULL_PREFIX_FAILURE_DESCRIPTORS",
    "FULL_PREFIX_TERMINAL_BY_RESULT_KIND",
    "SECRET_AND_PII_SCAN_SCOPES",
    "SECRET_PII_DETECTOR_VERSION",
    "ApplicablePredicateDenominatorArtifactFailure",
    "ApplicablePredicateDenominatorStatement",
    "ChronologyApplicablePredicateDenominatorArtifacts",
    "ChronologyBundleHeader",
    "ChronologyBundleRequest",
    "ChronologyMemberInput",
    "ChronologyPersistenceFailure",
    "ChronologyPersistenceManifestMismatch",
    "ChronologyPersistenceNotEstablished",
    "ChronologyPersistenceStoreIntegrityMismatch",
    "ChronologyPersistenceVerificationMismatch",
    "ChronologyPredicatePolicyArtifacts",
    "ChronologyProofDomain",
    "ChronologyProofPersistenceFailed",
    "ChronologyProofPersistenceResult",
    "Digest",
    "EncodedChronologyBundle",
    "ExpectedCommitmentPrefix",
    "FullPrefixBuildFailureCode",
    "FullPrefixBuildRejected",
    "FullPrefixBuildResult",
    "FullPrefixCheckState",
    "FullPrefixEnvelopeFailureCode",
    "FullPrefixEnvelopeRejected",
    "FullPrefixEvaluationKey",
    "FullPrefixEvaluationState",
    "FullPrefixExpectedPrefixFailureCode",
    "FullPrefixExpectedPrefixRejected",
    "FullPrefixFailureDescriptor",
    "FullPrefixInputMode",
    "FullPrefixInternalConsistencyFailureCode",
    "FullPrefixInternalConsistencyRejected",
    "FullPrefixInvocationFailureCode",
    "FullPrefixInvocationRejected",
    "FullPrefixMemberFailureCode",
    "FullPrefixMemberRejected",
    "FullPrefixRejected",
    "FullPrefixTerminalCheck",
    "FullPrefixVerificationResult",
    "FullPrefixVerificationStatement",
    "FullPrefixVerified",
    "FullPrefixVerifier",
    "MemberPredicateDisposition",
    "NativeApplicablePredicateDenominatorPersistenceFailed",
    "NativeAuthorityHeadNotEstablished",
    "NativeChronologyCandidate",
    "NativeChronologyCandidateRejected",
    "NativeChronologyOwnerContext",
    "NativeChronologyPersistenceFailed",
    "NativeChronologyPolicyResolutionFailed",
    "NativeChronologyQualificationResult",
    "NativeChronologyQualified",
    "NativeChronologyQuery",
    "NativeChronologyReconciliation",
    "NativeExteriorAndAuthorityHeadNotEstablished",
    "NativeExteriorNotEstablished",
    "NativeFullPrefixBuildRejected",
    "NativeFullPrefixProofRejected",
    "NativePredicateRejected",
    "NativeProjectionCustodyGap",
    "NativeSchemaProfileRejected",
    "OwnerQualifiedNativeCandidate",
    "PersistedApplicablePredicateDenominator",
    "PersistedChronologyProof",
    "PersistedPredicateAdmissionPolicy",
    "PersistedPredicatePolicyAdmission",
    "PolicyAdmissionAmbiguousFailure",
    "PolicyAdmissionMissingFailure",
    "PolicyBindingMismatchFailure",
    "PolicyBytesMissingFailure",
    "PolicyOwnerDenominatorMismatchFailure",
    "PolicyOwnerRelationNotEstablished",
    "PolicyOwnerRelationRejected",
    "PolicyQueryBindingMismatchFailure",
    "PredicateAdmissionPolicyStatement",
    "PredicateAdmissionRule",
    "PredicateClass",
    "PredicateDisposition",
    "PredicatePolicyAdmissionIndex",
    "PredicatePolicyAdmissionStatement",
    "PredicatePolicyOwnerProvenanceVerifier",
    "PredicatePolicyOwnerRelationFailure",
    "PredicatePolicyResolutionContext",
    "PredicatePolicyResolutionFailure",
    "PredicatePolicySelectionKey",
    "PromptSanitizer",
    "QueryPredicateDisposition",
    "ResolvedPredicatePolicyAdmission",
    "SecretAndPIIScanReport",
    "SecretPIIScanResult",
    "VerifiedNativeMemberIdentity",
    "VerifiedNativeSubjectIdentity",
    "VerifiedOwnerPredicateEvidence",
    "VerifiedPolicyOwnerProvenance",
    "VerifiedPredicatePolicyOwnerRelation",
    "artifacts",
    "backends",
    "build_full_prefix_bundle",
    "cache",
    "canon",
    "components",
    "contracts",
    "discovery",
    "errors",
    "evaluation",
    "llm",
    "observability",
    "pipeline",
    "registry",
    "resilience",
    "run",
    "scan_secret_and_pii",
]


def __getattr__(name: str) -> Any:
    """Import one exported Core subpackage on first attribute access.

    Args:
        name: Subpackage name listed in `__all__`.

    Returns:
        The imported module cached on the package namespace.

    Raises:
        AttributeError: If `name` is not part of the stable facade surface.
    """
    if name in _SUBPACKAGES:
        module = importlib.import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    if name in _LAZY_EXPORTS:
        module_name, attr_name = _LAZY_EXPORTS[name]
        value = getattr(importlib.import_module(module_name), attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Return regular globals plus lazily exported subpackage names."""
    return sorted(list(globals().keys()) + __all__)
