"""Strict evidence vocabulary for the Foundry dependency-profile owner.

The models in this module describe content-bound evidence.  They deliberately
do not carry live owner capabilities and cannot authorize environment use.
"""

from __future__ import annotations

import hashlib
import json
import tomllib
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Annotated, Generic, Literal, Protocol, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    ValidationError,
    field_validator,
    model_validator,
)


class AuthorityScalarRole(StrEnum):
    """Semantic role carried by a scalar at the Foundry authority boundary."""

    DIGEST_WIRE = "digest-wire"
    HEX_BYTES_WIRE = "hex-bytes-wire"
    IDENTITY = "identity"
    VERSION = "version"
    PLATFORM_TAG = "platform-tag"
    ABI_TAG = "abi-tag"
    PYTHON_CONSTRAINT = "python-constraint"
    ENTRYPOINT = "entrypoint"
    ARGUMENT = "argument"
    MARKER_EXPRESSION = "marker-expression"
    BUILD_BACKEND = "build-backend"
    ENVIRONMENT_KEY = "environment-key"
    ENVIRONMENT_VALUE = "environment-value"
    SCHEMA_VERSION = "schema-version"
    REQUEST_PATH = "request-path"
    EXACT_BYTES = "exact-bytes"
    BYTE_LENGTH = "byte-length"
    FILESYSTEM_IDENTITY = "filesystem-identity"


Sha256 = Annotated[
    StrictStr,
    AuthorityScalarRole.DIGEST_WIRE,
    Field(pattern=r"^sha256:[0-9a-f]{64}$"),
]
ArtifactIdWire = Sha256
HexBytes = Annotated[
    StrictStr,
    AuthorityScalarRole.HEX_BYTES_WIRE,
    Field(pattern=r"^(?:[0-9a-f]{2})*00$"),
]
IdentityText = Annotated[StrictStr, AuthorityScalarRole.IDENTITY, Field(min_length=1)]
VersionText = Annotated[StrictStr, AuthorityScalarRole.VERSION, Field(min_length=1)]
PlatformTagText = Annotated[
    StrictStr, AuthorityScalarRole.PLATFORM_TAG, Field(min_length=1)
]
AbiTagText = Annotated[StrictStr, AuthorityScalarRole.ABI_TAG, Field(min_length=1)]
PythonConstraintText = Annotated[
    StrictStr, AuthorityScalarRole.PYTHON_CONSTRAINT, Field(min_length=1)
]
EntrypointText = Annotated[
    StrictStr, AuthorityScalarRole.ENTRYPOINT, Field(min_length=1)
]
ArgumentText = Annotated[StrictStr, AuthorityScalarRole.ARGUMENT]
MarkerExpressionText = Annotated[
    StrictStr, AuthorityScalarRole.MARKER_EXPRESSION, Field(min_length=1)
]
BuildBackendText = Annotated[
    StrictStr, AuthorityScalarRole.BUILD_BACKEND, Field(min_length=1)
]
EnvironmentKeyText = Annotated[
    StrictStr, AuthorityScalarRole.ENVIRONMENT_KEY, Field(min_length=1)
]
EnvironmentValueText = Annotated[StrictStr, AuthorityScalarRole.ENVIRONMENT_VALUE]
SchemaVersionText = Annotated[
    StrictStr,
    AuthorityScalarRole.SCHEMA_VERSION,
    Field(min_length=1),
]
GitCommitId = Annotated[
    StrictStr,
    AuthorityScalarRole.IDENTITY,
    Field(pattern=r"^[0-9a-f]{40}$"),
]
GitTreeId = GitCommitId
ExactBytes = Annotated[bytes, AuthorityScalarRole.EXACT_BYTES]
ByteLength = Annotated[int, AuthorityScalarRole.BYTE_LENGTH, Field(ge=0)]
FilesystemIdentityNumber = Annotated[
    int, AuthorityScalarRole.FILESYSTEM_IDENTITY, Field(ge=0)
]
NonEmptyIdentity = IdentityText


class FoundryAuthorityModel(BaseModel):
    """Base for strict, immutable authority and evidence values."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class AbsoluteRequestPath(FoundryAuthorityModel):
    """An absolute request coordinate, not an observed filesystem identity."""

    value: Annotated[Path, AuthorityScalarRole.REQUEST_PATH]

    @field_validator("value")
    @classmethod
    def validate_absolute_request_path(cls, value: Path) -> Path:
        text = str(value)
        if not value.is_absolute() or "\x00" in text:
            raise ValueError("request path must be absolute and NUL-free")
        return value


class RootedRelativePath(FoundryAuthorityModel):
    """Canonical POSIX path relative to an already appointed root."""

    value: Annotated[StrictStr, AuthorityScalarRole.REQUEST_PATH]

    @field_validator("value")
    @classmethod
    def validate_rooted_relative_path(cls, value: str) -> str:
        candidate = PurePosixPath(value)
        if (
            not value
            or "\x00" in value
            or not candidate.parts
            or candidate == PurePosixPath(".")
            or candidate.is_absolute()
            or value != candidate.as_posix()
            or any(part in {"", ".", ".."} for part in candidate.parts)
        ):
            raise ValueError("path must be canonical, relative and root-contained")
        return value


class DigestDomain(StrEnum):
    """Closed digest namespace used by the v1 Foundry contract."""

    RAW_BLOB = "raw-blob"
    CANONICAL_SOURCE = "canonical-source-authority"
    PROFILE_REGISTRY = "dependency-profile-registry"
    AUTHORITY_REGISTRY = "dependency-authority-registry"
    DIGEST_REGISTRY = "digest-domain-registry"
    PROFILE_DECLARATION = "dependency-profile-declaration"
    PROFILE_ADMISSION = "profile-admission"
    PYPROJECT = "pyproject-blob"
    UV_LOCK = "uv-lock-blob"
    TOOLCHAIN_SELECTED = "toolchain-selected-artifact"
    TOOLCHAIN_EXECUTABLE = "toolchain-executable-blob"
    TOOLCHAIN_RUNTIME = "toolchain-runtime-installation"
    TOOLCHAIN_RUNTIME_OBSERVED = "toolchain-runtime-observed"
    TOOLCHAIN_RUNTIME_ROOT = "toolchain-runtime-root-resolution"
    TOOLCHAIN_RUNTIME_ROOT_TOKEN = "toolchain-runtime-root-token"
    TOOLCHAIN_RUNTIME_ROOT_PATH = "toolchain-runtime-root-path"
    TOOLCHAIN_RUNTIME_BINDING = "toolchain-runtime-source-binding"
    TOOLCHAIN_RUNTIME_INSTALLATION = "toolchain-runtime-root-installation-receipt"
    TOOLCHAIN_RUNTIME_VERIFICATION = "toolchain-runtime-verification"
    TRUST_MATERIAL = "trust-material"
    TRUST_REVOCATION = "trust-revocation"
    TRUST_RESOLUTION = "trust-resolution-receipt"
    TRUST_POLICY = "production-data-trust-policy"
    VERIFIER_PROVENANCE = "verifier-provenance"
    PRODUCTION_MANIFEST = "production-data-manifest"
    PRODUCTION_APPOINTMENT = "production-data-appointment"
    PRODUCTION_CUSTODY = "production-data-custody"
    ROOT_NONCE = "root-access-nonce"
    ROOT_CHALLENGE = "root-access-challenge"
    ROOT_MOUNT_REQUEST = "root-mount-request"
    ROOT_MOUNT_RESOLUTION = "root-mount-resolution"
    ROOT_ACCESS = "production-data-root-access"
    LOCKED_SOURCE = "locked-source"
    SELECTED_DISTRIBUTION = "selected-distribution-artifact"
    SELECTED_WHEEL = "selected-wheel-blob"
    SELECTED_SOURCE = "selected-source-artifact"
    WHEEL_RECORD = "wheel-record-manifest"
    SOURCE_TREE = "source-tree-manifest"
    BUILD_PROFILE = "build-profile"
    BUILD_ARGV = "build-argv"
    BUILD_ENVIRONMENT = "build-environment"
    BUILD_LINEAGE = "build-lineage-receipt"
    INSTALLED_STABLE = "installed-tree-stable"
    INSTALLED_INSTANCE = "installed-tree-instance"
    INSTALLED_BINDING = "installed-source-binding"
    DISTRIBUTION_SET = "distribution-set"
    CONTENT_SET_STABLE = "required-content-set-stable"
    CONTENT_SET_INSTANCE = "required-content-set-instance"
    DEPENDENCY_DISCRIMINANT = "dependency-discriminant"
    DEPENDENCY_CLOSURE = "dependency-closure"
    DERIVED_UV_ARGV = "derived-uv-argv"
    ENVIRONMENT_INSTANCE = "environment-instance"
    ENVIRONMENT_MARKER = "dependency-environment-marker"
    ENVIRONMENT_RECEIPT = "dependency-environment-receipt"
    CAPSULE = "dependency-authority-capsule"
    RESOLUTION_REQUEST = "dependency-resolution-request"
    SIGNED_EVIDENCE = "detached-signature-evidence"
    SIGNED_RECORD_BINDING = "signed-record-binding"
    SIGNED_BINDING_INDEX = "signed-binding-index"
    VERIFIER_APPOINTMENT = "verifier-appointment"


class ExternalAuthorityKind(StrEnum):
    """Institutional authorities referenced but never minted by Foundry."""

    INSTITUTIONAL_ROOT = "institutional-root-object"
    PRODUCTION_DATA_CUSTODIAN = "production-data-custodian"


class LauncherNormalizationProfile(StrEnum):
    POSIX_CONSOLE_SCRIPT_V1 = "posix_console_script_v1"


class LauncherExpectedProducerId(StrEnum):
    DISTLIB_POSIX_CONSOLE_V1 = "distlib_posix_console_v1"


class LauncherObservedVerifierId(StrEnum):
    PARSE_DISTLIB_POSIX_CONSOLE_V1 = "parse_distlib_posix_console_v1"


D_co = TypeVar("D_co", bound=DigestDomain, covariant=True)
E_co = TypeVar("E_co", bound=ExternalAuthorityKind, covariant=True)
EnumT = TypeVar("EnumT", bound=StrEnum)


class DomainDigest(FoundryAuthorityModel, Generic[D_co]):
    """Digest tagged by the exact preimage domain."""

    domain: D_co
    value: Sha256


class FoundryRecordRef(FoundryAuthorityModel, Generic[D_co]):
    """CAS wire identity plus its independently typed semantic digest."""

    artifact_id: ArtifactIdWire
    semantic_hash: DomainDigest[D_co]
    schema_version: SchemaVersionText


class ExternalAuthorityRef(FoundryAuthorityModel, Generic[E_co]):
    """Opaque reference resolved only by an appointed external authority."""

    authority_kind: E_co
    value: IdentityText
    resolver_appointment_ref: DomainDigest[Literal[DigestDomain.VERIFIER_APPOINTMENT]]


class DigestPreimageKind(StrEnum):
    CANONICAL_STATEMENT = "canonical_statement"
    RAW_BLOB = "raw_blob"
    TRACKED_TOML = "tracked_toml"
    ORDERED_ROWS = "ordered_rows"
    RELATION = "relation"


class PreimageDerivationRule(StrEnum):
    """Plan-evidence rule that determines one digest preimage kind."""

    STATEMENT_CLASS = "statement_class"
    EXACT_BYTES = "exact_bytes"
    CARRIED_VALUE = "carried_value"
    COMPUTED_RELATION = "computed_relation"
    TRACKED_TOML = "tracked_toml"
    ORDERED_ROWS = "ordered_rows"


class DigestOrderingRule(StrEnum):
    CANON_JSON_V1 = "canon_json_v1"
    RAW_BYTES_IDENTITY = "raw_bytes_identity"
    TOML_UTF8_CANON_V1 = "toml_utf8_canon_v1"
    LEXICOGRAPHIC_FRAMED_ROWS_V1 = "lexicographic_framed_rows_v1"
    ORDERED_FRAMED_RELATION_V1 = "ordered_framed_relation_v1"


class DigestAlgebraId(StrEnum):
    CANONICAL_STATEMENT_V1 = "canonical_statement_v1"
    RAW_BLOB_V1 = "raw_blob_v1"
    TRACKED_TOML_V1 = "tracked_toml_v1"
    ORDERED_ROWS_V1 = "ordered_rows_v1"
    RELATION_V1 = "relation_v1"


class DigestProducerId(StrEnum):
    CANONICAL_STATEMENT_V1 = "canonical_statement_v1"
    RAW_BLOB_V1 = "raw_blob_v1"
    TRACKED_TOML_V1 = "tracked_toml_v1"
    ORDERED_ROWS_V1 = "ordered_rows_v1"
    RELATION_V1 = "relation_v1"


class DigestVerifierId(StrEnum):
    RECOMPUTE_CANONICAL_STATEMENT_V1 = "recompute_canonical_statement_v1"
    REHASH_RAW_BLOB_V1 = "rehash_raw_blob_v1"
    REPARSE_TRACKED_TOML_V1 = "reparse_tracked_toml_v1"
    RECOMPUTE_ORDERED_ROWS_V1 = "recompute_ordered_rows_v1"
    RECOMPUTE_RELATION_V1 = "recompute_relation_v1"


class DigestPhase(StrEnum):
    STABLE = "stable"
    INSTANCE = "instance"
    RESOLUTION = "resolution"


class TrustRole(StrEnum):
    FOUNDRY_TRUST_ROOT = "foundry_trust_root"
    APPOINTMENT_ISSUER = "appointment_issuer"
    CUSTODY_VERIFIER = "custody_verifier"
    ROOT_ACCESS_ATTESTOR = "root_access_attestor"
    BUILD_VERIFIER = "build_verifier"


class ScalarDomain(StrEnum):
    PROFILE_ID = "profile-id"
    GIT_COMMIT = "git-commit"
    VERSION = "version"
    PLATFORM_TAG = "platform-tag"
    PATH_IDENTITY = "path-identity"


class LauncherProfileSpec(FoundryAuthorityModel):
    profile_id: Literal[LauncherNormalizationProfile.POSIX_CONSOLE_SCRIPT_V1]
    supported_platform_family: tuple[Literal["darwin", "linux"], ...]
    python_abi: Literal["cp314"]
    line_ending: Literal["lf"]
    interpreter_occurrences: Literal[1]
    normalized_interpreter_token: Literal["@PYTHON@"]
    expected_producer_id: Literal[LauncherExpectedProducerId.DISTLIB_POSIX_CONSOLE_V1]
    observed_verifier_id: Literal[
        LauncherObservedVerifierId.PARSE_DISTLIB_POSIX_CONSOLE_V1
    ]


class LauncherNormalizationVerified(FoundryAuthorityModel):
    status: Literal["verified"]
    normalized_wrapper_bytes: ExactBytes


class LauncherNormalizationRejected(FoundryAuthorityModel):
    status: Literal["rejected"]
    code: Literal[
        "launcher_grammar_mismatch",
        "launcher_interpreter_count_mismatch",
        "launcher_entrypoint_mismatch",
        "launcher_flags_mismatch",
        "launcher_line_ending_mismatch",
    ]


LauncherNormalizationResult = Annotated[
    LauncherNormalizationVerified | LauncherNormalizationRejected,
    Field(discriminator="status"),
]


class LauncherNormalizationABI(Protocol):
    def build_expected(
        self,
        *,
        spec: LauncherProfileSpec,
        entrypoint_target: EntrypointText,
        interpreter_bytes: ExactBytes,
        normalized_flags: tuple[ArgumentText, ...],
    ) -> bytes: ...

    def verify_and_normalize(
        self,
        *,
        spec: LauncherProfileSpec,
        entrypoint_target: EntrypointText,
        observed_wrapper_bytes: ExactBytes,
        admitted_interpreter_bytes: ExactBytes,
        normalized_flags: tuple[ArgumentText, ...],
    ) -> LauncherNormalizationResult: ...


class CanonicalStatementDigestAlgebra(FoundryAuthorityModel):
    algebra_id: Literal[DigestAlgebraId.CANONICAL_STATEMENT_V1]
    preimage_kind: Literal[DigestPreimageKind.CANONICAL_STATEMENT]
    producer_id: Literal[DigestProducerId.CANONICAL_STATEMENT_V1]
    verifier_id: Literal[DigestVerifierId.RECOMPUTE_CANONICAL_STATEMENT_V1]
    ordering_rule: Literal[DigestOrderingRule.CANON_JSON_V1]


class RawBlobDigestAlgebra(FoundryAuthorityModel):
    algebra_id: Literal[DigestAlgebraId.RAW_BLOB_V1]
    preimage_kind: Literal[DigestPreimageKind.RAW_BLOB]
    producer_id: Literal[DigestProducerId.RAW_BLOB_V1]
    verifier_id: Literal[DigestVerifierId.REHASH_RAW_BLOB_V1]
    ordering_rule: Literal[DigestOrderingRule.RAW_BYTES_IDENTITY]


class TrackedTomlDigestAlgebra(FoundryAuthorityModel):
    algebra_id: Literal[DigestAlgebraId.TRACKED_TOML_V1]
    preimage_kind: Literal[DigestPreimageKind.TRACKED_TOML]
    producer_id: Literal[DigestProducerId.TRACKED_TOML_V1]
    verifier_id: Literal[DigestVerifierId.REPARSE_TRACKED_TOML_V1]
    ordering_rule: Literal[DigestOrderingRule.TOML_UTF8_CANON_V1]


class OrderedRowsDigestAlgebra(FoundryAuthorityModel):
    algebra_id: Literal[DigestAlgebraId.ORDERED_ROWS_V1]
    preimage_kind: Literal[DigestPreimageKind.ORDERED_ROWS]
    producer_id: Literal[DigestProducerId.ORDERED_ROWS_V1]
    verifier_id: Literal[DigestVerifierId.RECOMPUTE_ORDERED_ROWS_V1]
    ordering_rule: Literal[DigestOrderingRule.LEXICOGRAPHIC_FRAMED_ROWS_V1]


class RelationDigestAlgebra(FoundryAuthorityModel):
    algebra_id: Literal[DigestAlgebraId.RELATION_V1]
    preimage_kind: Literal[DigestPreimageKind.RELATION]
    producer_id: Literal[DigestProducerId.RELATION_V1]
    verifier_id: Literal[DigestVerifierId.RECOMPUTE_RELATION_V1]
    ordering_rule: Literal[DigestOrderingRule.ORDERED_FRAMED_RELATION_V1]


DigestAlgebraSpec = Annotated[
    CanonicalStatementDigestAlgebra
    | RawBlobDigestAlgebra
    | TrackedTomlDigestAlgebra
    | OrderedRowsDigestAlgebra
    | RelationDigestAlgebra,
    Field(discriminator="algebra_id"),
]


class DigestDomainSpec(FoundryAuthorityModel):
    domain_id: DigestDomain
    prefix_hex: HexBytes
    algebra: DigestAlgebraSpec
    derivation_rule: PreimageDerivationRule
    derivation_evidence: Annotated[tuple[IdentityText, ...], Field(min_length=1)]
    phase: DigestPhase
    signature_requirement: Literal["unsigned", "signed"]
    required_signer_role: TrustRole | None = None

    @model_validator(mode="after")
    def validate_executable_row(self) -> DigestDomainSpec:
        expected = f"polisyos.foundry.{self.domain_id.value}.v1\0".encode("ascii")
        if bytes.fromhex(self.prefix_hex) != expected:
            raise ValueError("digest prefix does not equal its domain-derived prefix")
        signed = self.signature_requirement == "signed"
        if signed != (self.required_signer_role is not None):
            raise ValueError("signature requirement and signer role must be paired")
        expected_preimage = {
            PreimageDerivationRule.STATEMENT_CLASS: DigestPreimageKind.CANONICAL_STATEMENT,
            PreimageDerivationRule.EXACT_BYTES: DigestPreimageKind.RAW_BLOB,
            PreimageDerivationRule.CARRIED_VALUE: DigestPreimageKind.RAW_BLOB,
            PreimageDerivationRule.COMPUTED_RELATION: DigestPreimageKind.RELATION,
            PreimageDerivationRule.TRACKED_TOML: DigestPreimageKind.TRACKED_TOML,
            PreimageDerivationRule.ORDERED_ROWS: DigestPreimageKind.ORDERED_ROWS,
        }[self.derivation_rule]
        if self.algebra.preimage_kind is not expected_preimage:
            raise ValueError("preimage kind does not follow its plan derivation rule")
        if self.derivation_evidence != tuple(sorted(set(self.derivation_evidence))):
            raise ValueError("preimage derivation evidence must be sorted and unique")
        return self


class AuthorityPredicateId(StrEnum):
    SOURCE_FREEZE = "canonical_source_freeze"
    RUNTIME_SUBTREE_CUTOFF = "owner_enforced_runtime_subtree_cutoff"
    AUTHORITY_REGISTRY = "authority_registry"
    PURPOSE_PROFILE = "purpose_profile_admission"
    TRUST_SIGNATURE = "trust_signature"
    PRODUCTION_APPOINTMENT = "production_data_appointment"
    ROOT_ACCESS = "fresh_root_access"
    PRODUCTION_MANIFEST = "production_data_manifest"
    SELECTED_ARTIFACT = "selected_distribution_artifact"
    BUILD_LINEAGE = "build_lineage"
    PYTHON_RUNTIME = "python_runtime"
    UV_EXECUTABLE = "uv_executable"
    INSTALLED_SOURCE = "installed_source_binding"
    INSTALLED_CONTENT = "installed_content"
    ENVIRONMENT_RECEIPT = "environment_receipt"


class AuthorityFailureCode(StrEnum):
    SOURCE_FREEZE_MISMATCH = "source_freeze_mismatch"
    SOURCE_NOT_ESTABLISHED = "canonical_foundry_source_not_established"
    RUNTIME_SUBTREE_CUTOFF_NOT_ESTABLISHED = (
        "owner_enforced_runtime_subtree_cutoff_not_established"
    )
    REGISTRY_INVALID = "dependency_authority_registry_invalid"
    REGISTRY_NOT_ESTABLISHED = "dependency_authority_registry_not_established"
    PROFILE_MISMATCH = "dependency_profile_input_mismatch"
    PROFILE_NOT_ADMITTED = "dependency_profile_not_admitted_for_purpose"
    SIGNATURE_INVALID = "dependency_trust_signature_invalid"
    TRUST_NOT_ESTABLISHED = "dependency_trust_material_not_established"
    APPOINTMENT_MISMATCH = "production_data_appointment_mismatch"
    APPOINTMENT_NOT_ESTABLISHED = "production_data_appointment_not_established"
    ROOT_ACCESS_MISMATCH = "production_data_root_access_mismatch"
    ROOT_ACCESS_NOT_ESTABLISHED = "production_data_root_access_not_established"
    MANIFEST_MISMATCH = "production_data_manifest_content_mismatch"
    MANIFEST_MISSING = "production_data_manifest_missing"
    ARTIFACT_MISMATCH = "selected_distribution_artifact_mismatch"
    ARTIFACT_NOT_ESTABLISHED = "selected_distribution_artifact_not_established"
    BUILD_LINEAGE_MISMATCH = "build_lineage_mismatch"
    BUILD_LINEAGE_NOT_ESTABLISHED = "build_lineage_not_established"
    PYTHON_RUNTIME_MISMATCH = "python_runtime_manifest_mismatch"
    PYTHON_RUNTIME_NOT_ESTABLISHED = "python_runtime_not_established"
    UV_MISMATCH = "resolver_executable_mismatch"
    UV_NOT_ESTABLISHED = "resolver_executable_not_established"
    SOURCE_BINDING_MISMATCH = "required_distribution_source_mismatch"
    SOURCE_BINDING_NOT_ESTABLISHED = "installed_source_binding_not_established"
    CONTENT_MISMATCH = "required_distribution_content_mismatch"
    CONTENT_NOT_ESTABLISHED = "installed_content_not_established"
    ENVIRONMENT_MISMATCH = "dependency_environment_receipt_mismatch"
    ENVIRONMENT_NOT_ESTABLISHED = "dependency_environment_receipt_not_established"


class DigestPredicateMismatch(FoundryAuthorityModel):
    """A recomputed mismatch whose two values share one semantic domain."""

    kind: Literal["digest_mismatch"]
    predicate_id: AuthorityPredicateId
    code: AuthorityFailureCode
    expected: DomainDigest[DigestDomain]
    observed: DomainDigest[DigestDomain]
    predicate_class: Literal["recomputed", "independently_reconciled"]

    @model_validator(mode="after")
    def validate_comparable_unequal_values(self) -> DigestPredicateMismatch:
        if self.expected.domain is not self.observed.domain:
            raise ValueError("digest mismatch values must share one semantic domain")
        if self.expected.value == self.observed.value:
            raise ValueError("digest mismatch values must differ")
        return self


class DomainScalar(FoundryAuthorityModel):
    """Scalar value tagged by its semantic comparison domain."""

    domain: ScalarDomain
    value: IdentityText


class ScalarPredicateMismatch(FoundryAuthorityModel):
    """A recomputed scalar mismatch with a single comparison domain."""

    kind: Literal["scalar_mismatch"]
    predicate_id: AuthorityPredicateId
    code: AuthorityFailureCode
    expected: DomainScalar
    observed: DomainScalar
    predicate_class: Literal["recomputed", "independently_reconciled"]

    @model_validator(mode="after")
    def validate_comparable_unequal_values(self) -> ScalarPredicateMismatch:
        if self.expected.domain is not self.observed.domain:
            raise ValueError("scalar mismatch values must share one semantic domain")
        if self.expected.value == self.observed.value:
            raise ValueError("scalar mismatch values must differ")
        return self


class DomainEvidenceRequirement(FoundryAuthorityModel):
    requirement_kind: Literal["domain_evidence"]
    evidence_domains: Annotated[tuple[DigestDomain, ...], Field(min_length=1)]


class MissingEvidenceDomainsRequirement(FoundryAuthorityModel):
    requirement_kind: Literal["missing_evidence_domains"]
    missing_domains: Annotated[tuple[DigestDomain, ...], Field(min_length=1)]


class SourceFreezeRelationEvidenceRequirement(FoundryAuthorityModel):
    requirement_kind: Literal["source_freeze_relation"]
    request_commit_path: Literal[
        "result.request.pre_source_request.expected_source_freeze_commit"
    ] = "result.request.pre_source_request.expected_source_freeze_commit"
    request_tree_path: Literal[
        "result.request.expected_source_tree_id"
    ] = "result.request.expected_source_tree_id"
    observed_commit_path: Literal[
        "result.failure.owner_observed_head_commit"
    ] = "result.failure.owner_observed_head_commit"
    observed_tree_path: Literal[
        "result.failure.owner_observed_tree_id"
    ] = "result.failure.owner_observed_tree_id"
    observation_producer: Literal["canonical_module_git_recompute_v1"]
    require_same_owner_root: Literal[True]
    require_commit_or_tree_inequality: Literal[True]


class MissingGateCapabilityEvidenceRequirement(FoundryAuthorityModel):
    requirement_kind: Literal["missing_gate_capability"]
    capability_id: Literal["owner_enforced_runtime_subtree_cutoff"]
    capability_state: Literal["absent/unallocated"]
    candidate_evidence_rule: Literal["orthogonal_present_or_not_requested"]


AuthorityEvidenceRequirement = Annotated[
    DomainEvidenceRequirement
    | MissingEvidenceDomainsRequirement
    | SourceFreezeRelationEvidenceRequirement
    | MissingGateCapabilityEvidenceRequirement,
    Field(discriminator="requirement_kind"),
]


class BidirectionalAuthorityPredicateSpec(FoundryAuthorityModel):
    branch_shape: Literal["bidirectional"]
    predicate_id: AuthorityPredicateId
    admitted_classes: tuple[Literal["recomputed", "independently_reconciled"], ...]
    satisfied_requirement: DomainEvidenceRequirement
    rejected_code: AuthorityFailureCode
    rejected_requirement: AuthorityEvidenceRequirement
    not_established_code: AuthorityFailureCode
    not_established_requirement: AuthorityEvidenceRequirement


class NotEstablishedOnlyAuthorityPredicateSpec(FoundryAuthorityModel):
    branch_shape: Literal["not_established_only"]
    predicate_id: AuthorityPredicateId
    not_established_code: AuthorityFailureCode
    not_established_requirement: AuthorityEvidenceRequirement


AuthorityPredicateSpec = Annotated[
    BidirectionalAuthorityPredicateSpec | NotEstablishedOnlyAuthorityPredicateSpec,
    Field(discriminator="branch_shape"),
]


class SatisfiedAuthorityPredicate(FoundryAuthorityModel):
    branch_shape: Literal["bidirectional"]
    status: Literal["satisfied"]
    predicate_registry_ref: FoundryRecordRef[Literal[DigestDomain.DIGEST_REGISTRY]]
    predicate_spec: BidirectionalAuthorityPredicateSpec
    predicate_id: AuthorityPredicateId
    predicate_class: Literal["recomputed", "independently_reconciled"]
    evidence_refs: Annotated[
        tuple[FoundryRecordRef[DigestDomain], ...], Field(min_length=1)
    ]

    @model_validator(mode="after")
    def validate_bound_branch(self) -> SatisfiedAuthorityPredicate:
        validate_bound_predicate_disposition(self)
        return self


class RejectedAuthorityPredicate(FoundryAuthorityModel):
    branch_shape: Literal["bidirectional"]
    status: Literal["rejected"]
    predicate_registry_ref: FoundryRecordRef[Literal[DigestDomain.DIGEST_REGISTRY]]
    predicate_spec: BidirectionalAuthorityPredicateSpec
    predicate_id: AuthorityPredicateId
    predicate_class: Literal["recomputed", "independently_reconciled"]
    failure_code: AuthorityFailureCode
    evidence_refs: Annotated[
        tuple[FoundryRecordRef[DigestDomain], ...], Field(min_length=1)
    ]

    @model_validator(mode="after")
    def validate_bound_branch(self) -> RejectedAuthorityPredicate:
        validate_bound_predicate_disposition(self)
        return self


class BidirectionalUnestablishedAuthorityPredicate(FoundryAuthorityModel):
    branch_shape: Literal["bidirectional"]
    status: Literal["not_established"]
    predicate_registry_ref: FoundryRecordRef[Literal[DigestDomain.DIGEST_REGISTRY]]
    predicate_spec: BidirectionalAuthorityPredicateSpec
    predicate_id: AuthorityPredicateId
    predicate_class: Literal["not_established"]
    failure_code: AuthorityFailureCode
    missing_domains: Annotated[tuple[DigestDomain, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_bound_branch(self) -> BidirectionalUnestablishedAuthorityPredicate:
        validate_bound_predicate_disposition(self)
        return self


class OneSidedUnestablishedAuthorityPredicate(FoundryAuthorityModel):
    branch_shape: Literal["not_established_only"]
    status: Literal["not_established"]
    predicate_registry_ref: FoundryRecordRef[Literal[DigestDomain.DIGEST_REGISTRY]]
    predicate_spec: NotEstablishedOnlyAuthorityPredicateSpec
    predicate_id: AuthorityPredicateId
    predicate_class: Literal["not_established"]
    failure_code: AuthorityFailureCode
    missing_capability: IdentityText
    missing_capability_state: Literal["absent/unallocated"]

    @model_validator(mode="after")
    def validate_bound_branch(self) -> OneSidedUnestablishedAuthorityPredicate:
        validate_bound_predicate_disposition(self)
        return self


UnestablishedAuthorityPredicate = Annotated[
    BidirectionalUnestablishedAuthorityPredicate
    | OneSidedUnestablishedAuthorityPredicate,
    Field(discriminator="branch_shape"),
]
BidirectionalAuthorityPredicateDisposition = Annotated[
    SatisfiedAuthorityPredicate
    | RejectedAuthorityPredicate
    | BidirectionalUnestablishedAuthorityPredicate,
    Field(discriminator="status"),
]
AuthorityPredicateDisposition = (
    SatisfiedAuthorityPredicate
    | RejectedAuthorityPredicate
    | BidirectionalUnestablishedAuthorityPredicate
    | OneSidedUnestablishedAuthorityPredicate
)


def _require_sorted_unique(keys: tuple[str, ...], *, label: str) -> None:
    if not keys or len(keys) != len(set(keys)) or keys != tuple(sorted(keys)):
        raise ValueError(f"{label} must be non-empty, unique and canonically sorted")


def _require_exact_domains(
    observed: tuple[DigestDomain, ...],
    requirement: AuthorityEvidenceRequirement,
) -> None:
    if isinstance(requirement, DomainEvidenceRequirement):
        expected = requirement.evidence_domains
    elif isinstance(requirement, MissingEvidenceDomainsRequirement):
        expected = requirement.missing_domains
    else:
        return
    if observed != expected:
        raise ValueError("predicate evidence domains do not match the bound requirement")


def validate_bound_predicate_disposition(
    disposition: AuthorityPredicateDisposition,
) -> None:
    """Bind an emitted predicate branch to its embedded exact registry row."""

    spec = disposition.predicate_spec
    if disposition.branch_shape != spec.branch_shape:
        raise ValueError("predicate branch shape is not bound to its registry row")
    if disposition.predicate_id is not spec.predicate_id:
        raise ValueError("predicate id is not bound to its registry row")
    if isinstance(disposition, SatisfiedAuthorityPredicate):
        if disposition.predicate_class not in spec.admitted_classes:
            raise ValueError("satisfied predicate class is not admitted")
        _require_exact_domains(
            tuple(ref.semantic_hash.domain for ref in disposition.evidence_refs),
            spec.satisfied_requirement,
        )
        return
    if isinstance(disposition, RejectedAuthorityPredicate):
        if disposition.predicate_class not in spec.admitted_classes:
            raise ValueError("rejected predicate class is not admitted")
        if disposition.failure_code is not spec.rejected_code:
            raise ValueError("rejected predicate code is not bound to its registry row")
        _require_exact_domains(
            tuple(ref.semantic_hash.domain for ref in disposition.evidence_refs),
            spec.rejected_requirement,
        )
        return
    if disposition.failure_code is not spec.not_established_code:
        raise ValueError("not-established code is not bound to its registry row")
    requirement = spec.not_established_requirement
    if isinstance(disposition, BidirectionalUnestablishedAuthorityPredicate):
        _require_exact_domains(disposition.missing_domains, requirement)
        return
    if not isinstance(requirement, MissingGateCapabilityEvidenceRequirement):
        raise ValueError("one-sided predicate requires a missing capability row")
    if (
        disposition.missing_capability != requirement.capability_id
        or disposition.missing_capability_state != requirement.capability_state
    ):
        raise ValueError("missing capability is not bound to its registry row")


class DigestDomainRegistryStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.digest-domain-registry.v1"]
    domains: tuple[DigestDomainSpec, ...]
    predicates: tuple[AuthorityPredicateSpec, ...]

    @model_validator(mode="after")
    def require_complete_unique_denominators(self) -> DigestDomainRegistryStatement:
        domains = tuple(row.domain_id for row in self.domains)
        predicates = tuple(row.predicate_id for row in self.predicates)
        if len(domains) != len(set(domains)) or set(domains) != set(DigestDomain):
            raise ValueError("digest registry must exactly cover the digest-domain denominator")
        if len(predicates) != len(set(predicates)) or set(predicates) != set(
            AuthorityPredicateId
        ):
            raise ValueError("predicate registry must exactly cover the predicate denominator")
        cutoff = next(
            row
            for row in self.predicates
            if row.predicate_id is AuthorityPredicateId.RUNTIME_SUBTREE_CUTOFF
        )
        if not isinstance(cutoff, NotEstablishedOnlyAuthorityPredicateSpec):
            raise ValueError("runtime cutoff must be not-established-only")
        return self


class VerifierProvenanceStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.verifier-provenance.v1"]
    verifier_id: IdentityText
    source_authority_ref: FoundryRecordRef[Literal[DigestDomain.CANONICAL_SOURCE]]
    configuration_ref: FoundryRecordRef[Literal[DigestDomain.RAW_BLOB]]


class LockedDistributionIdentity(FoundryAuthorityModel):
    normalized_name: IdentityText
    version: VersionText
    source_kind: Literal["registry", "url", "git", "path"]
    selected_artifact_ref: FoundryRecordRef[
        Literal[DigestDomain.SELECTED_DISTRIBUTION]
    ]
    expected_stable_manifest_ref: FoundryRecordRef[
        Literal[DigestDomain.INSTALLED_STABLE]
    ]
    expected_source_binding_ref: FoundryRecordRef[
        Literal[DigestDomain.INSTALLED_BINDING]
    ]
    marker_expression: MarkerExpressionText | None


class StablePayloadFileRow(FoundryAuthorityModel):
    row_kind: Literal["payload"]
    logical_root: Literal["purelib", "platlib", "scripts", "data", "headers"]
    relative_path: RootedRelativePath
    byte_length: ByteLength
    raw_content_hash: DomainDigest[Literal[DigestDomain.RAW_BLOB]]


class StableEntrypointFileRow(FoundryAuthorityModel):
    row_kind: Literal["generated_entrypoint"]
    logical_root: Literal["scripts"]
    relative_path: RootedRelativePath
    entrypoint_target: EntrypointText
    launcher_profile: LauncherNormalizationProfile
    python_abi: AbiTagText
    normalized_flags: tuple[ArgumentText, ...]


StableInstalledFileRow = Annotated[
    StablePayloadFileRow | StableEntrypointFileRow,
    Field(discriminator="row_kind"),
]


class InstalledInstanceFileRow(FoundryAuthorityModel):
    environment_relative_path: RootedRelativePath
    byte_length: ByteLength
    raw_content_hash: DomainDigest[Literal[DigestDomain.RAW_BLOB]]


class StableInstalledDistributionManifestStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.installed-tree-stable.v1"]
    normalized_name: IdentityText
    version: VersionText
    transform_profile: Literal["wheel_install_tree_v1", "source_first_tree_v1"]
    rows: tuple[StableInstalledFileRow, ...]


def _validated_entrypoint_target(entrypoint_target: str) -> tuple[str, str]:
    parts = entrypoint_target.split(":")
    if len(parts) != 2:
        raise ValueError("launcher entrypoint target must be module:function")
    module_name, function_name = parts
    if (
        not module_name
        or not all(part.isidentifier() for part in module_name.split("."))
        or not function_name.isidentifier()
    ):
        raise ValueError("launcher entrypoint target is not importable")
    return module_name, function_name


def _validated_launcher_flags(normalized_flags: tuple[str, ...]) -> str:
    if any(
        type(flag) is not str
        or not flag
        or any(character.isspace() for character in flag)
        for flag in normalized_flags
    ):
        raise ValueError("launcher flags must be non-empty whitespace-free strings")
    return "" if not normalized_flags else " " + " ".join(normalized_flags)


def produce_posix_console_launcher(
    *,
    interpreter: Path,
    entrypoint_target: str,
    normalized_flags: tuple[str, ...],
) -> bytes:
    """Produce the closed POSIX distlib-console candidate wrapper."""

    if not interpreter.is_absolute() or "\n" in str(interpreter):
        raise ValueError("launcher interpreter must be one absolute line")
    module_name, function_name = _validated_entrypoint_target(entrypoint_target)
    flags = _validated_launcher_flags(normalized_flags)
    return (
        f"#!{interpreter}{flags}\n"
        "# -*- coding: utf-8 -*-\n"
        "import re\n"
        "import sys\n"
        f"from {module_name} import {function_name}\n"
        "if __name__ == '__main__':\n"
        "    sys.argv[0] = re.sub(r'(-script\\.pyw|\\.exe)?$', '', sys.argv[0])\n"
        f"    sys.exit({function_name}())\n"
    ).encode()


def verify_posix_console_launcher(
    observed: bytes,
    *,
    admitted_interpreter: Path,
    entrypoint_target: str,
    normalized_flags: tuple[str, ...],
) -> bytes:
    """Independently parse the whole wrapper and normalize only its shebang."""

    if type(observed) is not bytes or b"\r" in observed:
        raise ValueError("launcher must be exact LF-terminated bytes")
    try:
        text = observed.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("launcher must be strict UTF-8") from exc
    if not admitted_interpreter.is_absolute() or text.count(str(admitted_interpreter)) != 1:
        raise ValueError("launcher must contain the admitted interpreter exactly once")
    module_name, function_name = _validated_entrypoint_target(entrypoint_target)
    flags = _validated_launcher_flags(normalized_flags)
    expected_lines = (
        f"#!{admitted_interpreter}{flags}",
        "# -*- coding: utf-8 -*-",
        "import re",
        "import sys",
        f"from {module_name} import {function_name}",
        "if __name__ == '__main__':",
        "    sys.argv[0] = re.sub(r'(-script\\.pyw|\\.exe)?$', '', sys.argv[0])",
        f"    sys.exit({function_name}())",
        "",
    )
    if tuple(text.split("\n")) != expected_lines:
        raise ValueError("launcher body, flags, stub, or trailing bytes differ")
    normalized_lines = (f"#!@PYTHON@{flags}", *expected_lines[1:])
    return "\n".join(normalized_lines).encode("utf-8")


def normalize_installed_file_bytes(
    row: StableInstalledFileRow,
    observed: bytes,
    *,
    admitted_interpreter: Path,
) -> bytes:
    """Verify one stable row without treating payload bytes as launchers."""

    if type(observed) is not bytes:
        raise TypeError("installed file content must be exact bytes")
    if isinstance(row, StablePayloadFileRow):
        if (
            len(observed) != row.byte_length
            or domain_digest(DigestDomain.RAW_BLOB, observed) != row.raw_content_hash
        ):
            raise ValueError("installed payload content does not match its stable row")
        return observed
    return verify_posix_console_launcher(
        observed,
        admitted_interpreter=admitted_interpreter,
        entrypoint_target=row.entrypoint_target,
        normalized_flags=row.normalized_flags,
    )


def build_noneditable_stable_manifest(
    *,
    normalized_name: str,
    version: str,
    rows: tuple[StableInstalledFileRow, ...],
    source_checkout: Path,
) -> StableInstalledDistributionManifestStatement:
    """Build a checkout-invariant root manifest and reject editable markers."""

    if not source_checkout.is_absolute():
        raise ValueError("source checkout must be absolute candidate transport")
    del source_checkout
    for row in rows:
        value = row.relative_path.value
        if value.endswith("/direct_url.json") or value.endswith(".pth"):
            raise ValueError("editable root-install marker is not admitted")
    ordered = tuple(
        sorted(
            rows,
            key=lambda row: (row.logical_root, row.relative_path.value, row.row_kind),
        )
    )
    if len({(row.logical_root, row.relative_path.value) for row in ordered}) != len(
        ordered
    ):
        raise ValueError("stable install rows must have unique logical paths")
    return StableInstalledDistributionManifestStatement(
        schema_version="polisyos.foundry.installed-tree-stable.v1",
        normalized_name=normalized_name,
        version=version,
        transform_profile="source_first_tree_v1",
        rows=ordered,
    )


class InstalledDistributionInstanceManifestStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.installed-tree-instance.v1"]
    environment_creation_nonce: DomainDigest[
        Literal[DigestDomain.ENVIRONMENT_INSTANCE]
    ]
    normalized_name: IdentityText
    version: VersionText
    rows: tuple[InstalledInstanceFileRow, ...]
    recomputed_stable_manifest_ref: FoundryRecordRef[
        Literal[DigestDomain.INSTALLED_STABLE]
    ]


class WheelInstalledSourceBindingStatement(FoundryAuthorityModel):
    binding_kind: Literal["wheel"]
    schema_version: Literal["polisyos.foundry.installed-source-binding.v1"]
    locked_source_ref: DomainDigest[Literal[DigestDomain.LOCKED_SOURCE]]
    selected_evidence_ref: FoundryRecordRef[
        Literal[DigestDomain.SELECTED_DISTRIBUTION]
    ]
    stable_manifest_ref: FoundryRecordRef[Literal[DigestDomain.INSTALLED_STABLE]]
    transform_profile: Literal["wheel_install_tree_v1"]


class BuiltInstalledSourceBindingStatement(WheelInstalledSourceBindingStatement):
    binding_kind: Literal["built_source"]
    build_lineage_ref: FoundryRecordRef[Literal[DigestDomain.BUILD_LINEAGE]]


class SourceFirstInstalledSourceBindingStatement(FoundryAuthorityModel):
    binding_kind: Literal["source_first"]
    schema_version: Literal["polisyos.foundry.installed-source-binding.v1"]
    locked_source_ref: DomainDigest[Literal[DigestDomain.LOCKED_SOURCE]]
    selected_evidence_ref: FoundryRecordRef[
        Literal[DigestDomain.SELECTED_DISTRIBUTION]
    ]
    stable_manifest_ref: FoundryRecordRef[Literal[DigestDomain.INSTALLED_STABLE]]
    transform_profile: Literal["source_first_tree_v1"]
    source_tree_ref: FoundryRecordRef[Literal[DigestDomain.SOURCE_TREE]]


InstalledSourceBindingStatement = Annotated[
    WheelInstalledSourceBindingStatement
    | BuiltInstalledSourceBindingStatement
    | SourceFirstInstalledSourceBindingStatement,
    Field(discriminator="binding_kind"),
]


class WheelRecordManifestStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.wheel-record-manifest.v1"]
    wheel_blob_ref: FoundryRecordRef[Literal[DigestDomain.SELECTED_WHEEL]]
    stable_rows: tuple[StableInstalledFileRow, ...]


class SourceTreeManifestStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.source-tree-manifest.v1"]
    source_freeze_commit: GitCommitId
    rows: tuple[StableInstalledFileRow, ...]


class BuildProfileStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.build-profile.v1"]
    build_backend: BuildBackendText
    python_runtime_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME]]
    build_requirement_refs: tuple[
        FoundryRecordRef[Literal[DigestDomain.SELECTED_DISTRIBUTION]], ...
    ]
    normalized_environment: tuple[
        tuple[EnvironmentKeyText, EnvironmentValueText], ...
    ]


class InstalledDistributionIdentity(FoundryAuthorityModel):
    normalized_name: IdentityText
    version: VersionText
    source_kind: IdentityText
    selected_artifact_ref: FoundryRecordRef[
        Literal[DigestDomain.SELECTED_DISTRIBUTION]
    ]
    observed_stable_manifest_ref: FoundryRecordRef[
        Literal[DigestDomain.INSTALLED_STABLE]
    ]
    observed_instance_manifest_ref: FoundryRecordRef[
        Literal[DigestDomain.INSTALLED_INSTANCE]
    ]
    observed_source_binding_ref: FoundryRecordRef[
        Literal[DigestDomain.INSTALLED_BINDING]
    ]


class BuildLineageStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.build-lineage.v1"]
    source_artifact_ref: FoundryRecordRef[Literal[DigestDomain.SELECTED_SOURCE]]
    builder_toolchain_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME]]
    build_profile_ref: FoundryRecordRef[Literal[DigestDomain.BUILD_PROFILE]]
    normalized_argv_hash: DomainDigest[Literal[DigestDomain.BUILD_ARGV]]
    build_environment_hash: DomainDigest[Literal[DigestDomain.BUILD_ENVIRONMENT]]
    output_wheel_ref: FoundryRecordRef[Literal[DigestDomain.SELECTED_WHEEL]]
    verifier_provenance_ref: FoundryRecordRef[
        Literal[DigestDomain.VERIFIER_PROVENANCE]
    ]
    trust_resolution_receipt_ref: FoundryRecordRef[
        Literal[DigestDomain.TRUST_RESOLUTION]
    ]


class PersistedBuildLineageEvidence(FoundryAuthorityModel):
    record_ref: FoundryRecordRef[Literal[DigestDomain.BUILD_LINEAGE]]
    statement: BuildLineageStatement
    signed_binding_ref: FoundryRecordRef[
        Literal[DigestDomain.SIGNED_RECORD_BINDING]
    ]


class SelectedWheelArtifactEvidence(FoundryAuthorityModel):
    artifact_kind: Literal["wheel"]
    schema_version: Literal["polisyos.foundry.selected-wheel.v1"]
    normalized_name: IdentityText
    version: VersionText
    locked_source_ref: DomainDigest[Literal[DigestDomain.LOCKED_SOURCE]]
    wheel_blob_ref: FoundryRecordRef[Literal[DigestDomain.SELECTED_WHEEL]]
    wheel_record_manifest_ref: FoundryRecordRef[Literal[DigestDomain.WHEEL_RECORD]]
    expected_stable_manifest_ref: FoundryRecordRef[
        Literal[DigestDomain.INSTALLED_STABLE]
    ]


class SelectedBuiltArtifactEvidence(FoundryAuthorityModel):
    artifact_kind: Literal["built_source"]
    schema_version: Literal["polisyos.foundry.selected-built-wheel.v1"]
    normalized_name: IdentityText
    version: VersionText
    locked_source_ref: DomainDigest[Literal[DigestDomain.LOCKED_SOURCE]]
    source_blob_ref: FoundryRecordRef[Literal[DigestDomain.SELECTED_SOURCE]]
    build_lineage: PersistedBuildLineageEvidence
    output_wheel_ref: FoundryRecordRef[Literal[DigestDomain.SELECTED_WHEEL]]
    expected_stable_manifest_ref: FoundryRecordRef[
        Literal[DigestDomain.INSTALLED_STABLE]
    ]


class SelectedSourceTreeEvidence(FoundryAuthorityModel):
    artifact_kind: Literal["source_tree"]
    schema_version: Literal["polisyos.foundry.selected-source-tree.v1"]
    normalized_name: IdentityText
    version: VersionText
    locked_source_ref: DomainDigest[Literal[DigestDomain.LOCKED_SOURCE]]
    tracked_source_commit: GitCommitId
    source_tree_manifest_ref: FoundryRecordRef[Literal[DigestDomain.SOURCE_TREE]]
    expected_stable_manifest_ref: FoundryRecordRef[
        Literal[DigestDomain.INSTALLED_STABLE]
    ]


SelectedDistributionArtifactEvidence = Annotated[
    SelectedWheelArtifactEvidence
    | SelectedBuiltArtifactEvidence
    | SelectedSourceTreeEvidence,
    Field(discriminator="artifact_kind"),
]


class PythonRuntimeRegularFileRow(FoundryAuthorityModel):
    row_kind: Literal["regular_file"]
    relative_path: RootedRelativePath
    role: Literal["launcher", "stdlib", "libpython", "runtime_library"]
    byte_length: ByteLength
    content_hash: DomainDigest[Literal[DigestDomain.RAW_BLOB]]


class PythonRuntimeSymlinkRow(FoundryAuthorityModel):
    row_kind: Literal["symlink"]
    relative_path: RootedRelativePath
    role: Literal["launcher", "stdlib", "libpython", "runtime_library"]
    symlink_target: RootedRelativePath


PythonRuntimeFileRow = Annotated[
    PythonRuntimeRegularFileRow | PythonRuntimeSymlinkRow,
    Field(discriminator="row_kind"),
]


class PythonRuntimeManifestStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.python-runtime.v1"]
    implementation: Literal["cpython"]
    version: VersionText
    platform_tag: PlatformTagText
    abi_tag: AbiTagText
    executable_relative_path: RootedRelativePath
    files: Annotated[tuple[PythonRuntimeFileRow, ...], Field(min_length=1)]


class PythonRuntimeSourceBindingStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.python-runtime-source-binding.v1"]
    selected_artifact_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_SELECTED]
    ]
    runtime_manifest_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME]]
    installation_transform: Literal["python_runtime_installation_v1"]


class PosixRuntimeFilesystemKind(StrEnum):
    APFS = "apfs"
    EXT4 = "ext4"


class PosixRuntimeRootObservation(FoundryAuthorityModel):
    device_id: FilesystemIdentityNumber
    inode: FilesystemIdentityNumber
    mode_type: Literal["directory"]
    ctime_ns: FilesystemIdentityNumber


class PosixRuntimeRootIdentityStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.posix-runtime-root-identity.v1"]
    predicate_class: Literal["candidate_observation"]
    identity_profile: Literal["posix-open-directory-apfs-ext4-v1"]
    platform_family: Literal["darwin", "linux"]
    filesystem_kind: PosixRuntimeFilesystemKind
    environment_creation_nonce: DomainDigest[
        Literal[DigestDomain.ENVIRONMENT_INSTANCE]
    ]
    environment_root_path_hash: DomainDigest[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME_ROOT_PATH]
    ]
    runtime_root_path_hash: DomainDigest[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME_ROOT_PATH]
    ]
    opened_before: PosixRuntimeRootObservation
    opened_after_enumeration: PosixRuntimeRootObservation
    reopened_by_path: PosixRuntimeRootObservation
    first_walk_manifest_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME]
    ]
    second_walk_manifest_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME]
    ]

    @model_validator(mode="after")
    def require_equal_two_pass_observations(self) -> PosixRuntimeRootIdentityStatement:
        if not (
            self.opened_before
            == self.opened_after_enumeration
            == self.reopened_by_path
        ):
            raise ValueError("runtime root identity changed during the two-pass walk")
        if self.first_walk_manifest_ref != self.second_walk_manifest_ref:
            raise ValueError("runtime subtree changed between complete walks")
        return self


class PythonRuntimeResolutionHop(FoundryAuthorityModel):
    source_root_instance: DomainDigest[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME_ROOT_TOKEN]
    ]
    source_relative_path: RootedRelativePath
    target_root_instance: DomainDigest[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME_ROOT_TOKEN]
    ]
    target_relative_path: RootedRelativePath
    raw_link_hash: DomainDigest[Literal[DigestDomain.RAW_BLOB]]


class PythonRuntimeRootResolutionStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.python-runtime-root-resolution.v1"]
    environment_creation_nonce: DomainDigest[
        Literal[DigestDomain.ENVIRONMENT_INSTANCE]
    ]
    installation_receipt_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME_INSTALLATION]
    ]
    environment_python_relative_path: RootedRelativePath
    resolved_executable_relative_path: RootedRelativePath
    resolution_chain: tuple[PythonRuntimeResolutionHop, ...]
    runtime_root_identity: PosixRuntimeRootIdentityStatement
    runtime_root_instance: DomainDigest[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME_ROOT_TOKEN]
    ]
    recomputed_runtime_manifest_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME]
    ]
    recomputed_source_binding_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME_BINDING]
    ]


class PythonRuntimeInstallationStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.python-runtime-installation.v1"]
    source_authority_ref: FoundryRecordRef[Literal[DigestDomain.CANONICAL_SOURCE]]
    selected_artifact_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_SELECTED]
    ]
    runtime_manifest_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME]
    ]
    runtime_source_binding_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME_BINDING]
    ]
    environment_creation_nonce: DomainDigest[
        Literal[DigestDomain.ENVIRONMENT_INSTANCE]
    ]
    runtime_root_identity: PosixRuntimeRootIdentityStatement
    runtime_root_instance: DomainDigest[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME_ROOT_TOKEN]
    ]
    installer_provenance_ref: FoundryRecordRef[
        Literal[DigestDomain.VERIFIER_PROVENANCE]
    ]


class PersistedPythonRuntimeInstallation(FoundryAuthorityModel):
    receipt_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME_INSTALLATION]
    ]
    statement: PythonRuntimeInstallationStatement


class ObservedPythonRuntimeStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.python-runtime-observed.v1"]
    environment_creation_nonce: DomainDigest[
        Literal[DigestDomain.ENVIRONMENT_INSTANCE]
    ]
    expected_runtime_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME]]
    installation_receipt_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME_INSTALLATION]
    ]
    root_resolution_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME_ROOT]
    ]
    recomputed_runtime_manifest_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME]
    ]
    observed_source_binding_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME_BINDING]
    ]
    implementation: Literal["cpython"]
    version: VersionText
    platform_tag: PlatformTagText
    abi_tag: AbiTagText
    files: Annotated[tuple[PythonRuntimeFileRow, ...], Field(min_length=1)]


class PythonRuntimeVerificationReceiptStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.python-runtime-verification.v1"]
    expected_runtime_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME]]
    installation_receipt_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME_INSTALLATION]
    ]
    recomputed_runtime_manifest_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME]
    ]
    expected_source_binding_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME_BINDING]
    ]
    observed_source_binding_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME_BINDING]
    ]
    root_resolution_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME_ROOT]
    ]
    observed_runtime_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME_OBSERVED]
    ]
    verifier_provenance_ref: FoundryRecordRef[
        Literal[DigestDomain.VERIFIER_PROVENANCE]
    ]
    predicate_class: Literal["independently_reconciled"]


class PythonRuntimeAdmission(FoundryAuthorityModel):
    artifact_role: Literal["python_runtime"]
    version: Literal["3.14"]
    platform_tag: PlatformTagText
    selected_artifact_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_SELECTED]
    ]
    executable_blob_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_EXECUTABLE]
    ]
    expected_runtime_manifest_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME]
    ]
    expected_runtime_source_binding_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME_BINDING]
    ]
    verifier_provenance_ref: FoundryRecordRef[
        Literal[DigestDomain.VERIFIER_PROVENANCE]
    ]


class UvExecutableAdmission(FoundryAuthorityModel):
    artifact_role: Literal["uv_executable"]
    version: Literal["0.9.21"]
    platform_tag: PlatformTagText
    selected_artifact_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_SELECTED]
    ]
    executable_blob_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_EXECUTABLE]
    ]
    verifier_provenance_ref: FoundryRecordRef[
        Literal[DigestDomain.VERIFIER_PROVENANCE]
    ]


ToolchainArtifactAdmission = Annotated[
    PythonRuntimeAdmission | UvExecutableAdmission,
    Field(discriminator="artifact_role"),
]


class TrustPublicKey(FoundryAuthorityModel):
    key_id: Sha256
    algorithm: Literal["ed25519"]
    public_key_encoding: Literal["raw-ed25519-32"]
    public_key_bytes: Annotated[
        bytes,
        AuthorityScalarRole.EXACT_BYTES,
        Field(min_length=32, max_length=32),
    ]
    signer_identity: NonEmptyIdentity
    roles: Annotated[tuple[TrustRole, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_identity_and_roles(self) -> TrustPublicKey:
        expected = f"sha256:{hashlib.sha256(self.public_key_bytes).hexdigest()}"
        if self.key_id != expected:
            raise ValueError("key_id must be recomputed from exact raw Ed25519 bytes")
        _require_sorted_unique(
            tuple(role.value for role in self.roles), label="trust roles"
        )
        return self


class TrustRevocationStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.trust-revocation.v1"]
    key_id: Sha256
    signer_identity: NonEmptyIdentity
    revoked_roles: Annotated[tuple[TrustRole, ...], Field(min_length=1)]
    effective_source_freeze_commit: GitCommitId

    @model_validator(mode="after")
    def validate_revoked_roles(self) -> TrustRevocationStatement:
        _require_sorted_unique(
            tuple(role.value for role in self.revoked_roles), label="revoked roles"
        )
        return self


class PersistedTrustRevocation(FoundryAuthorityModel):
    revocation_ref: FoundryRecordRef[Literal[DigestDomain.TRUST_REVOCATION]]
    statement: TrustRevocationStatement
    signed_binding_ref: FoundryRecordRef[
        Literal[DigestDomain.SIGNED_RECORD_BINDING]
    ]


class TrustMaterialStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.trust-material.v1"]
    signature_profile: Literal["polisyos.ed25519.detached.v1"]
    keys: Annotated[tuple[TrustPublicKey, ...], Field(min_length=1)]
    revocation_refs: tuple[
        FoundryRecordRef[Literal[DigestDomain.TRUST_REVOCATION]], ...
    ]
    effective_admission_ref: FoundryRecordRef[
        Literal[DigestDomain.PROFILE_ADMISSION]
    ]

    @model_validator(mode="after")
    def validate_trust_denominator(self) -> TrustMaterialStatement:
        _require_sorted_unique(tuple(key.key_id for key in self.keys), label="trust keys")
        if self.revocation_refs:
            _require_sorted_unique(
                tuple(ref.artifact_id for ref in self.revocation_refs),
                label="revocation refs",
            )
        return self


class PersistedTrustMaterial(FoundryAuthorityModel):
    material_ref: FoundryRecordRef[Literal[DigestDomain.TRUST_MATERIAL]]
    statement: TrustMaterialStatement
    signed_binding_ref: FoundryRecordRef[
        Literal[DigestDomain.SIGNED_RECORD_BINDING]
    ]


class FoundryTrustBootstrapSnapshot(FoundryAuthorityModel):
    source_authority_ref: FoundryRecordRef[Literal[DigestDomain.CANONICAL_SOURCE]]
    source_freeze_commit: GitCommitId
    binding_index_ref: FoundryRecordRef[
        Literal[DigestDomain.SIGNED_BINDING_INDEX]
    ]
    trust_materials: Annotated[tuple[PersistedTrustMaterial, ...], Field(min_length=1)]
    revocations: tuple[PersistedTrustRevocation, ...]

    @model_validator(mode="after")
    def validate_bootstrap_denominators(self) -> FoundryTrustBootstrapSnapshot:
        _require_sorted_unique(
            tuple(row.material_ref.artifact_id for row in self.trust_materials),
            label="bootstrap trust materials",
        )
        if self.revocations:
            _require_sorted_unique(
                tuple(row.revocation_ref.artifact_id for row in self.revocations),
                label="bootstrap revocations",
            )
        return self


class ProductionDataTrustPolicyStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.production-data-trust-policy.v1"]
    appointment_keys_ref: FoundryRecordRef[Literal[DigestDomain.TRUST_MATERIAL]]
    custody_keys_ref: FoundryRecordRef[Literal[DigestDomain.TRUST_MATERIAL]]
    root_access_keys_ref: FoundryRecordRef[Literal[DigestDomain.TRUST_MATERIAL]]
    build_verifier_keys_ref: FoundryRecordRef[Literal[DigestDomain.TRUST_MATERIAL]]
    root_identity_profile: Literal["institutional_root_object_v1"]


class PersistedProductionDataTrustPolicy(FoundryAuthorityModel):
    policy_ref: FoundryRecordRef[Literal[DigestDomain.TRUST_POLICY]]
    statement: ProductionDataTrustPolicyStatement


class ResolvedTrustKey(FoundryAuthorityModel):
    key_id: Sha256
    signer_identity: NonEmptyIdentity
    selected_role: TrustRole


class GitCommitRelation(StrEnum):
    ANCESTOR = "ancestor"
    EQUAL = "equal"
    DESCENDANT = "descendant"
    INCOMPARABLE = "incomparable"


class RevocationCutoffDisposition(FoundryAuthorityModel):
    revocation_ref: FoundryRecordRef[Literal[DigestDomain.TRUST_REVOCATION]]
    relation_to_source_cutoff: GitCommitRelation
    status: Literal["effective", "future", "not_established"]

    @model_validator(mode="after")
    def validate_relation_status(self) -> RevocationCutoffDisposition:
        expected = {
            GitCommitRelation.ANCESTOR: "effective",
            GitCommitRelation.EQUAL: "effective",
            GitCommitRelation.DESCENDANT: "future",
            GitCommitRelation.INCOMPARABLE: "not_established",
        }[self.relation_to_source_cutoff]
        if self.status != expected:
            raise ValueError("revocation status does not match Git ancestry")
        return self


class TrustResolutionReceiptStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.trust-resolution.v1"]
    source_authority_ref: FoundryRecordRef[Literal[DigestDomain.CANONICAL_SOURCE]]
    source_freeze_commit: GitCommitId
    trust_policy_ref: FoundryRecordRef[Literal[DigestDomain.TRUST_POLICY]]
    required_role: TrustRole
    trust_material_ref: FoundryRecordRef[Literal[DigestDomain.TRUST_MATERIAL]]
    eligible_keys: Annotated[tuple[ResolvedTrustKey, ...], Field(min_length=1)]
    revocation_dispositions: tuple[RevocationCutoffDisposition, ...]
    verifier_provenance_ref: FoundryRecordRef[
        Literal[DigestDomain.VERIFIER_PROVENANCE]
    ]

    @model_validator(mode="after")
    def require_comparable_cutoff(self) -> TrustResolutionReceiptStatement:
        if any(row.status == "not_established" for row in self.revocation_dispositions):
            raise ValueError(
                "a positive trust receipt cannot contain incomparable revocation"
            )
        _require_sorted_unique(
            tuple(row.key_id for row in self.eligible_keys), label="eligible trust keys"
        )
        if any(row.selected_role != self.required_role for row in self.eligible_keys):
            raise ValueError("eligible key role must equal the requested trust role")
        if self.revocation_dispositions:
            _require_sorted_unique(
                tuple(
                    row.revocation_ref.artifact_id
                    for row in self.revocation_dispositions
                ),
                label="revocation dispositions",
            )
        return self


class PersistedTrustResolutionReceipt(FoundryAuthorityModel):
    receipt_ref: FoundryRecordRef[Literal[DigestDomain.TRUST_RESOLUTION]]
    statement: TrustResolutionReceiptStatement


class ProductionDataInputAppointmentStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.production-data-appointment.v1"]
    authority_purpose: Literal["n8_method_catalog_reconstruction"]
    appointed_root: ExternalAuthorityRef[
        Literal[ExternalAuthorityKind.INSTITUTIONAL_ROOT]
    ]
    manifest_relative_path: Literal["manifest.json"]
    expected_manifest_ref: FoundryRecordRef[
        Literal[DigestDomain.PRODUCTION_MANIFEST]
    ]
    appointed_custodian: ExternalAuthorityRef[
        Literal[ExternalAuthorityKind.PRODUCTION_DATA_CUSTODIAN]
    ]
    custody_statement_ref: FoundryRecordRef[
        Literal[DigestDomain.PRODUCTION_CUSTODY]
    ]
    trust_policy_ref: FoundryRecordRef[Literal[DigestDomain.TRUST_POLICY]]


class ProductionDataCustodyStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.production-data-custody.v1"]
    institutional_root: ExternalAuthorityRef[
        Literal[ExternalAuthorityKind.INSTITUTIONAL_ROOT]
    ]
    appointed_custodian: ExternalAuthorityRef[
        Literal[ExternalAuthorityKind.PRODUCTION_DATA_CUSTODIAN]
    ]
    manifest_ref: FoundryRecordRef[Literal[DigestDomain.PRODUCTION_MANIFEST]]
    access_mode: Literal["read_only"]
    writer_access_disposition: Literal["denied"]


class ProductionDataMountResolutionStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.production-data-mount.v1"]
    appointment_ref: FoundryRecordRef[
        Literal[DigestDomain.PRODUCTION_APPOINTMENT]
    ]
    institutional_root: ExternalAuthorityRef[
        Literal[ExternalAuthorityKind.INSTITUTIONAL_ROOT]
    ]
    requested_root_token: DomainDigest[Literal[DigestDomain.ROOT_MOUNT_REQUEST]]
    access_mode: Literal["read_only"]


class ProductionDataRootAccessChallenge(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.root-access-challenge.v1"]
    request_ref: FoundryRecordRef[Literal[DigestDomain.RESOLUTION_REQUEST]]
    challenge_nonce: DomainDigest[Literal[DigestDomain.ROOT_NONCE]]
    expected_root: ExternalAuthorityRef[
        Literal[ExternalAuthorityKind.INSTITUTIONAL_ROOT]
    ]
    expected_manifest_ref: FoundryRecordRef[
        Literal[DigestDomain.PRODUCTION_MANIFEST]
    ]
    mount_resolution_ref: FoundryRecordRef[
        Literal[DigestDomain.ROOT_MOUNT_RESOLUTION]
    ]


class RootAccessAttestationStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.root-access-attestation.v1"]
    challenge_ref: FoundryRecordRef[Literal[DigestDomain.ROOT_CHALLENGE]]
    request_ref: FoundryRecordRef[Literal[DigestDomain.RESOLUTION_REQUEST]]
    challenge_nonce: DomainDigest[Literal[DigestDomain.ROOT_NONCE]]
    institutional_root: ExternalAuthorityRef[
        Literal[ExternalAuthorityKind.INSTITUTIONAL_ROOT]
    ]
    observed_manifest_ref: FoundryRecordRef[
        Literal[DigestDomain.PRODUCTION_MANIFEST]
    ]
    mount_resolution_ref: FoundryRecordRef[
        Literal[DigestDomain.ROOT_MOUNT_RESOLUTION]
    ]
    access_mode: Literal["read_only"]
    writer_access_disposition: Literal["denied"]


class ExactSignedArtifactEvidenceStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.signed-artifact-evidence.v1"]
    signed_blob_bytes: ExactBytes
    exact_manifest_bytes: ExactBytes
    detached_signature_bytes: ExactBytes


class SourceAuthorityVerificationBasis(FoundryAuthorityModel):
    kind: Literal["source_authority"]
    source_authority_ref: FoundryRecordRef[Literal[DigestDomain.CANONICAL_SOURCE]]


class ResolvedTrustVerificationBasis(FoundryAuthorityModel):
    kind: Literal["resolved_trust"]
    trust_resolution_receipt_ref: FoundryRecordRef[
        Literal[DigestDomain.TRUST_RESOLUTION]
    ]


SignedRecordVerificationBasis = Annotated[
    SourceAuthorityVerificationBasis | ResolvedTrustVerificationBasis,
    Field(discriminator="kind"),
]


class SignedFoundryRecordBindingStatement(FoundryAuthorityModel, Generic[D_co]):
    schema_version: Literal["polisyos.foundry.signed-record-binding.v1"]
    record_ref: FoundryRecordRef[D_co]
    signed_evidence_ref: FoundryRecordRef[Literal[DigestDomain.SIGNED_EVIDENCE]]
    required_role: TrustRole
    verification_basis: SignedRecordVerificationBasis
    verifier_provenance_ref: FoundryRecordRef[
        Literal[DigestDomain.VERIFIER_PROVENANCE]
    ]

    @model_validator(mode="after")
    def validate_bootstrap_direction(self) -> SignedFoundryRecordBindingStatement[D_co]:
        source_basis = self.verification_basis.kind == "source_authority"
        if (self.required_role is TrustRole.FOUNDRY_TRUST_ROOT) != source_basis:
            raise ValueError(
                "only Foundry trust-root records use source-authority verification"
            )
        return self


class PersistedSignedFoundryRecordBinding(FoundryAuthorityModel, Generic[D_co]):
    binding_ref: FoundryRecordRef[Literal[DigestDomain.SIGNED_RECORD_BINDING]]
    statement: SignedFoundryRecordBindingStatement[D_co]


class SignedRecordBindingIndexStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.signed-binding-index.v1"]
    source_authority_ref: FoundryRecordRef[Literal[DigestDomain.CANONICAL_SOURCE]]
    binding_refs: Annotated[
        tuple[FoundryRecordRef[Literal[DigestDomain.SIGNED_RECORD_BINDING]], ...],
        Field(min_length=1),
    ]


class PersistedSignedRecordBindingIndex(FoundryAuthorityModel):
    index_ref: FoundryRecordRef[Literal[DigestDomain.SIGNED_BINDING_INDEX]]
    statement: SignedRecordBindingIndexStatement


class FoundryDependencyAuthorityCapsuleStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.dependency-capsule.v1"]
    source_authority_ref: FoundryRecordRef[Literal[DigestDomain.CANONICAL_SOURCE]]
    profile_admission_ref: FoundryRecordRef[
        Literal[DigestDomain.PROFILE_ADMISSION]
    ]
    appointment_ref: FoundryRecordRef[
        Literal[DigestDomain.PRODUCTION_APPOINTMENT]
    ]
    signed_binding_index_ref: FoundryRecordRef[
        Literal[DigestDomain.SIGNED_BINDING_INDEX]
    ]
    environment_receipt_ref: FoundryRecordRef[
        Literal[DigestDomain.ENVIRONMENT_RECEIPT]
    ]
    selected_artifact_refs: tuple[
        FoundryRecordRef[Literal[DigestDomain.SELECTED_DISTRIBUTION]], ...
    ]
    build_lineage_refs: tuple[
        FoundryRecordRef[Literal[DigestDomain.BUILD_LINEAGE]], ...
    ]
    trust_material_refs: tuple[
        FoundryRecordRef[Literal[DigestDomain.TRUST_MATERIAL]], ...
    ]

    @model_validator(mode="after")
    def validate_graph_denominators(self) -> FoundryDependencyAuthorityCapsuleStatement:
        for label, refs in (
            ("selected artifacts", self.selected_artifact_refs),
            ("build lineages", self.build_lineage_refs),
            ("capsule trust materials", self.trust_material_refs),
        ):
            if refs:
                _require_sorted_unique(
                    tuple(ref.artifact_id for ref in refs), label=label
                )
        return self


class PersistedFoundryDependencyAuthorityCapsule(FoundryAuthorityModel):
    capsule_ref: FoundryRecordRef[Literal[DigestDomain.CAPSULE]]
    statement: FoundryDependencyAuthorityCapsuleStatement


class DependencyEnvironmentMarkerStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.dependency-environment-marker.v1"]
    environment_creation_nonce: DomainDigest[
        Literal[DigestDomain.ENVIRONMENT_INSTANCE]
    ]
    stable_closure: DomainDigest[Literal[DigestDomain.DEPENDENCY_CLOSURE]]
    source_authority_ref: FoundryRecordRef[
        Literal[DigestDomain.CANONICAL_SOURCE]
    ]
    python_runtime_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME]
    ]
    python_runtime_installation_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME_INSTALLATION]
    ]
    observed_python_runtime_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME_OBSERVED]
    ]
    python_runtime_verification_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME_VERIFICATION]
    ]
    uv_executable_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_EXECUTABLE]
    ]
    derived_uv_argv: DomainDigest[Literal[DigestDomain.DERIVED_UV_ARGV]]
    instance_content_set: DomainDigest[Literal[DigestDomain.CONTENT_SET_INSTANCE]]


class DependencyProfileEnvironmentStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.dependency-environment.v1"]
    admission_ref: FoundryRecordRef[Literal[DigestDomain.PROFILE_ADMISSION]]
    stable_closure: DomainDigest[Literal[DigestDomain.DEPENDENCY_CLOSURE]]
    appointment_ref: FoundryRecordRef[
        Literal[DigestDomain.PRODUCTION_APPOINTMENT]
    ]
    sync_root_access_ref: FoundryRecordRef[Literal[DigestDomain.ROOT_ACCESS]]
    sync_root_access_binding_ref: FoundryRecordRef[
        Literal[DigestDomain.SIGNED_RECORD_BINDING]
    ]
    python_runtime_installation_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME_INSTALLATION]
    ]
    python_runtime_verification_ref: FoundryRecordRef[
        Literal[DigestDomain.TOOLCHAIN_RUNTIME_VERIFICATION]
    ]
    observed_distributions: tuple[InstalledDistributionIdentity, ...]
    stable_content_set: DomainDigest[Literal[DigestDomain.CONTENT_SET_STABLE]]
    instance_content_set: DomainDigest[Literal[DigestDomain.CONTENT_SET_INSTANCE]]
    marker_ref: FoundryRecordRef[Literal[DigestDomain.ENVIRONMENT_MARKER]]


class ProductionDataManifestStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.production-data-manifest.v1"]
    exact_manifest_bytes: ExactBytes


class ProductionDataManifestPresent(FoundryAuthorityModel):
    kind: Literal["present"]
    exact_bytes: ExactBytes


class ProductionDataManifestUnavailable(FoundryAuthorityModel):
    kind: Literal["unavailable"]
    cause: Literal["missing", "unreadable"]


ProductionDataManifestInput = Annotated[
    ProductionDataManifestPresent | ProductionDataManifestUnavailable,
    Field(discriminator="kind"),
]


class ProductionDataManifestMissingFailure(FoundryAuthorityModel):
    kind: Literal["production_data_manifest_missing"]
    predicate_id: Literal[AuthorityPredicateId.PRODUCTION_MANIFEST]
    code: Literal[AuthorityFailureCode.MANIFEST_MISSING]
    cause: Literal["missing", "unreadable"]
    predicate_class: Literal["not_established"]


class MissingPredicateEvidence(FoundryAuthorityModel):
    kind: Literal["not_established"]
    predicate_id: AuthorityPredicateId
    code: AuthorityFailureCode
    missing_domains: Annotated[tuple[DigestDomain, ...], Field(min_length=1)]
    predicate_class: Literal["not_established"]


AuthorityPredicateFailure = Annotated[
    MissingPredicateEvidence
    | ProductionDataManifestMissingFailure
    | DigestPredicateMismatch
    | ScalarPredicateMismatch,
    Field(discriminator="kind"),
]


class DecodedDigestDomainRegistry(FoundryAuthorityModel):
    registry_ref: FoundryRecordRef[Literal[DigestDomain.DIGEST_REGISTRY]]
    statement: DigestDomainRegistryStatement
    canonical_statement_bytes: ExactBytes
    semantic_hash: DomainDigest[Literal[DigestDomain.DIGEST_REGISTRY]]


class FoundryTomlWireModel(BaseModel):
    """Strict TOML transport shape carrying no semantic enum authority."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class DigestAlgebraTomlWire(FoundryTomlWireModel):
    algebra_id: StrictStr
    preimage_kind: StrictStr
    producer_id: StrictStr
    verifier_id: StrictStr
    ordering_rule: StrictStr


class DigestDomainTomlWire(FoundryTomlWireModel):
    domain_id: StrictStr
    prefix_hex: StrictStr
    algebra: DigestAlgebraTomlWire
    derivation_rule: StrictStr
    derivation_evidence: list[StrictStr]
    phase: StrictStr
    signature_requirement: StrictStr
    required_signer_role: StrictStr | None = None


class DomainEvidenceRequirementTomlWire(FoundryTomlWireModel):
    requirement_kind: Literal["domain_evidence"]
    evidence_domains: list[StrictStr]


class MissingEvidenceDomainsRequirementTomlWire(FoundryTomlWireModel):
    requirement_kind: Literal["missing_evidence_domains"]
    missing_domains: list[StrictStr]


class SourceFreezeRelationRequirementTomlWire(FoundryTomlWireModel):
    requirement_kind: Literal["source_freeze_relation"]
    request_commit_path: StrictStr
    request_tree_path: StrictStr
    observed_commit_path: StrictStr
    observed_tree_path: StrictStr
    observation_producer: StrictStr
    require_same_owner_root: bool
    require_commit_or_tree_inequality: bool


class MissingGateCapabilityRequirementTomlWire(FoundryTomlWireModel):
    requirement_kind: Literal["missing_gate_capability"]
    capability_id: StrictStr
    capability_state: StrictStr
    candidate_evidence_rule: StrictStr


AuthorityEvidenceRequirementTomlWire = Annotated[
    DomainEvidenceRequirementTomlWire
    | MissingEvidenceDomainsRequirementTomlWire
    | SourceFreezeRelationRequirementTomlWire
    | MissingGateCapabilityRequirementTomlWire,
    Field(discriminator="requirement_kind"),
]


class BidirectionalAuthorityPredicateTomlWire(FoundryTomlWireModel):
    branch_shape: Literal["bidirectional"]
    predicate_id: StrictStr
    admitted_classes: list[StrictStr]
    satisfied_requirement: DomainEvidenceRequirementTomlWire
    rejected_code: StrictStr
    rejected_requirement: AuthorityEvidenceRequirementTomlWire
    not_established_code: StrictStr
    not_established_requirement: AuthorityEvidenceRequirementTomlWire


class NotEstablishedOnlyAuthorityPredicateTomlWire(FoundryTomlWireModel):
    branch_shape: Literal["not_established_only"]
    predicate_id: StrictStr
    not_established_code: StrictStr
    not_established_requirement: AuthorityEvidenceRequirementTomlWire


AuthorityPredicateTomlWire = Annotated[
    BidirectionalAuthorityPredicateTomlWire
    | NotEstablishedOnlyAuthorityPredicateTomlWire,
    Field(discriminator="branch_shape"),
]


class DigestDomainRegistryTomlWire(FoundryTomlWireModel):
    schema_version: Literal["polisyos.foundry.digest-domain-registry.v1"]
    domains: list[DigestDomainTomlWire]
    predicates: list[AuthorityPredicateTomlWire]


def canonical_json_bytes(value: object) -> bytes:
    """Encode a JSON-compatible value with the v1 deterministic JSON grammar."""

    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha256_wire(raw: bytes) -> str:
    """Return the exact lowercase SHA-256 wire representation."""

    return "sha256:" + hashlib.sha256(raw).hexdigest()


def domain_digest(domain: D_co, raw: bytes) -> DomainDigest[D_co]:
    """Hash bytes under a semantic domain prefix."""

    prefix = f"polisyos.foundry.{domain.value}.v1\0".encode("ascii")
    length_frame = len(raw).to_bytes(8, byteorder="big", signed=False)
    return DomainDigest[D_co](
        domain=domain,
        value=sha256_wire(prefix + length_frame + raw),
    )


def record_ref(
    domain: D_co,
    raw: bytes,
    *,
    schema_version: str,
) -> FoundryRecordRef[D_co]:
    """Build a content-bound reference without persisting or appointing it."""

    semantic_hash = domain_digest(domain, raw)
    return FoundryRecordRef[D_co](
        artifact_id=sha256_wire(raw),
        semantic_hash=semantic_hash,
        schema_version=schema_version,
    )


def _exact_enum(enum_type: type[EnumT], value: object) -> EnumT:
    if type(value) is not str:
        raise ValueError("enum wire value must be an exact string")
    matches = tuple(
        member
        for _name, member in enum_type.__members__.items()
        if member.value == value
    )
    if len(matches) != 1:
        raise ValueError("unknown, aliased or non-exact enum wire value")
    return matches[0]


def _decode_digest_algebra(wire: DigestAlgebraTomlWire) -> DigestAlgebraSpec:
    algebra_id = _exact_enum(DigestAlgebraId, wire.algebra_id)
    variant = {
        DigestAlgebraId.CANONICAL_STATEMENT_V1: CanonicalStatementDigestAlgebra,
        DigestAlgebraId.RAW_BLOB_V1: RawBlobDigestAlgebra,
        DigestAlgebraId.TRACKED_TOML_V1: TrackedTomlDigestAlgebra,
        DigestAlgebraId.ORDERED_ROWS_V1: OrderedRowsDigestAlgebra,
        DigestAlgebraId.RELATION_V1: RelationDigestAlgebra,
    }[algebra_id]
    try:
        return variant(
            algebra_id=algebra_id,
            preimage_kind=_exact_enum(DigestPreimageKind, wire.preimage_kind),
            producer_id=_exact_enum(DigestProducerId, wire.producer_id),
            verifier_id=_exact_enum(DigestVerifierId, wire.verifier_id),
            ordering_rule=_exact_enum(DigestOrderingRule, wire.ordering_rule),
        )
    except ValidationError as error:
        raise ValueError("digest algebra fields are not an inseparable v1 variant") from error


def decode_digest_domain_registry_toml(raw_toml_bytes: bytes) -> DecodedDigestDomainRegistry:
    """Decode and independently bind the complete tracked digest registry."""

    wire = tomllib.loads(raw_toml_bytes.decode("utf-8"))
    if set(wire) != {"schema_version", "domains", "predicates"}:
        raise ValueError("digest registry has unknown or missing top-level fields")
    domains: list[DigestDomainSpec] = []
    for row in wire["domains"]:
        if set(row) != {
            "domain_id",
            "prefix_hex",
            "algebra_id",
            "preimage_kind",
            "producer_id",
            "verifier_id",
            "ordering_rule",
            "derivation_rule",
            "derivation_evidence",
            "phase",
            "signature_requirement",
            "required_signer_role",
        }:
            raise ValueError("digest-domain row has an unknown or missing field")
        role = row["required_signer_role"]
        domains.append(
            DigestDomainSpec(
                domain_id=_exact_enum(DigestDomain, row["domain_id"]),
                prefix_hex=row["prefix_hex"],
                algebra=_decode_digest_algebra(
                    DigestAlgebraTomlWire(
                        algebra_id=row["algebra_id"],
                        preimage_kind=row["preimage_kind"],
                        producer_id=row["producer_id"],
                        verifier_id=row["verifier_id"],
                        ordering_rule=row["ordering_rule"],
                    )
                ),
                derivation_rule=_exact_enum(
                    PreimageDerivationRule,
                    row["derivation_rule"],
                ),
                derivation_evidence=tuple(row["derivation_evidence"]),
                phase=_exact_enum(DigestPhase, row["phase"]),
                signature_requirement=row["signature_requirement"],
                required_signer_role=(
                    None if role == "none" else _exact_enum(TrustRole, role)
                ),
            )
        )
    predicates: list[AuthorityPredicateSpec] = []
    for row in wire["predicates"]:
        branch = row.get("branch_shape")
        predicate_id = _exact_enum(AuthorityPredicateId, row.get("predicate_id"))
        if branch == "not_established_only":
            if set(row) != {
                "branch_shape",
                "predicate_id",
                "not_established_code",
                "capability_id",
                "capability_state",
                "candidate_evidence_rule",
            }:
                raise ValueError("one-sided predicate has alternate branch fields")
            predicates.append(
                NotEstablishedOnlyAuthorityPredicateSpec(
                    branch_shape=branch,
                    predicate_id=predicate_id,
                    not_established_code=_exact_enum(
                        AuthorityFailureCode, row["not_established_code"]
                    ),
                    not_established_requirement=MissingGateCapabilityEvidenceRequirement(
                        requirement_kind="missing_gate_capability",
                        capability_id=row["capability_id"],
                        capability_state=row["capability_state"],
                        candidate_evidence_rule=row["candidate_evidence_rule"],
                    ),
                )
            )
            continue
        if branch != "bidirectional":
            raise ValueError("unknown predicate branch shape")
        exact_fields = {
            "branch_shape",
            "predicate_id",
            "admitted_classes",
            "satisfied_evidence_domains",
            "rejected_code",
            "rejected_requirement_kind",
            "rejected_evidence_domains",
            "not_established_code",
            "not_established_evidence_domains",
        }
        if set(row) != exact_fields:
            raise ValueError("bidirectional predicate has unknown or missing fields")
        admitted_classes = row["admitted_classes"]
        satisfied_domains = row["satisfied_evidence_domains"]
        rejected_domains = row["rejected_evidence_domains"]
        not_established_domains = row["not_established_evidence_domains"]
        if any(
            type(value) is not list or not value
            for value in (
                admitted_classes,
                satisfied_domains,
                rejected_domains,
                not_established_domains,
            )
        ):
            raise ValueError("predicate evidence denominators must be non-empty lists")
        rejected_requirement_kind = row["rejected_requirement_kind"]
        if rejected_requirement_kind == "source_freeze_relation":
            if predicate_id is not AuthorityPredicateId.SOURCE_FREEZE:
                raise ValueError("only source freeze may use the Git relation requirement")
            rejected_requirement: (
                SourceFreezeRelationEvidenceRequirement | DomainEvidenceRequirement
            ) = SourceFreezeRelationEvidenceRequirement(
                requirement_kind="source_freeze_relation",
                observation_producer="canonical_module_git_recompute_v1",
                require_same_owner_root=True,
                require_commit_or_tree_inequality=True,
            )
        elif rejected_requirement_kind == "domain_evidence":
            rejected_requirement = DomainEvidenceRequirement(
                requirement_kind="domain_evidence",
                evidence_domains=tuple(
                    _exact_enum(DigestDomain, value) for value in rejected_domains
                ),
            )
        else:
            raise ValueError("unknown rejected evidence requirement")
        predicates.append(
            BidirectionalAuthorityPredicateSpec(
                branch_shape="bidirectional",
                predicate_id=predicate_id,
                admitted_classes=tuple(admitted_classes),
                satisfied_requirement=DomainEvidenceRequirement(
                    requirement_kind="domain_evidence",
                    evidence_domains=tuple(
                        _exact_enum(DigestDomain, value) for value in satisfied_domains
                    ),
                ),
                rejected_code=_exact_enum(
                    AuthorityFailureCode, row["rejected_code"]
                ),
                rejected_requirement=rejected_requirement,
                not_established_code=_exact_enum(
                    AuthorityFailureCode,
                    row["not_established_code"],
                ),
                not_established_requirement=MissingEvidenceDomainsRequirement(
                    requirement_kind="missing_evidence_domains",
                    missing_domains=tuple(
                        _exact_enum(DigestDomain, value)
                        for value in not_established_domains
                    ),
                ),
            )
        )
    statement = DigestDomainRegistryStatement(
        schema_version=wire["schema_version"],
        domains=tuple(domains),
        predicates=tuple(predicates),
    )
    canonical = canonical_json_bytes(statement.model_dump(mode="json"))
    semantic = domain_digest(DigestDomain.DIGEST_REGISTRY, canonical)
    ref = FoundryRecordRef[Literal[DigestDomain.DIGEST_REGISTRY]](
        artifact_id=sha256_wire(raw_toml_bytes),
        semantic_hash=semantic,
        schema_version=statement.schema_version,
    )
    return DecodedDigestDomainRegistry(
        registry_ref=ref,
        statement=statement,
        canonical_statement_bytes=canonical,
        semantic_hash=semantic,
    )


def load_digest_domain_registry(path: Path) -> DecodedDigestDomainRegistry:
    """Read the tracked registry once and decode its exact bytes."""

    return decode_digest_domain_registry_toml(path.read_bytes())


__all__ = [
    "AbsoluteRequestPath",
    "ArtifactIdWire",
    "AuthorityFailureCode",
    "AuthorityPredicateId",
    "DecodedDigestDomainRegistry",
    "DigestDomain",
    "DigestDomainRegistryStatement",
    "DomainDigest",
    "ExactBytes",
    "FoundryAuthorityModel",
    "FoundryRecordRef",
    "GitCommitId",
    "GitTreeId",
    "IdentityText",
    "canonical_json_bytes",
    "decode_digest_domain_registry_toml",
    "domain_digest",
    "load_digest_domain_registry",
    "record_ref",
    "sha256_wire",
]
