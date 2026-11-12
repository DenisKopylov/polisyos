"""Purpose-specific intake for institutionally appointed N5 replay.

This owner verifies existing signed statements against current public deployment
trust. It neither appoints an institution nor launches work. An admitted
appointment is not a protected numerical-use verdict; actual blind execution,
physical accounting and comparison remain separate lifecycle consumers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal, Self, TypeVar, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.common.canonical import to_canonical_bytes
from polisyos.core import FileSystemSignedArtifactEvidenceRepository, artifacts, security

if TYPE_CHECKING:
    from collections.abc import Callable

    from polisyos.runtime.quality.n5_execution_basis import N5ProductionImage
    from polisyos.runtime.quality.n5_execution_profile import N5NativeExecutionProfile

Digest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
ReplayTier = Literal[
    "STRICT_CPU", "LIBRARY_DETERMINISTIC", "STATISTICAL", "NONDETERMINISTIC", "BEST_EFFORT_GPU"
]
ReplayTrustRole = Literal[
    "appointment_issuer",
    "deployment_administrator",
    "appointed_launcher",
    "original_producer",
    "result_user",
]
ConfiguredIndependence = Literal["same_organization_separate_function", "external_organization"]
N5_REPLAY_PREPARED_CONFIGURATION_KIND = "runtime.quality.n5_prepared_configuration"
N5_REPLAY_PRODUCTION_IMAGE_KIND = "runtime.quality.n5_production_image"
N5_REPLAY_EXECUTION_PROFILE_KIND = "runtime.quality.n5_execution_profile"
N5_REPLAY_NUMERICAL_INTENT_KIND = "runtime.quality.n5_replay_numerical_intent"
N5_REPLAY_V1_CORE_SCHEMA_VERSION = "1.0"
N5_REPLAY_INTENT_V2_CORE_SCHEMA_VERSION = "2.0"
N5_REPLAY_ORIGINAL_EXECUTION_KIND = "runtime.quality.n5_original_producer_execution"
N5_REPLAY_ORIGINAL_EXECUTION_SCHEMA_VERSION = "1.0"
N5_REPLAY_ORIGINAL_ACTION_KIND = "runtime.quality.n5_original_producer_action"
N5_REPLAY_ORIGINAL_ACTION_SCHEMA_NAME = "policyos.runtime.n5_replay.original_producer_action.v1"
N5_REPLAY_ORIGINAL_ACTION_SCHEMA_VERSION = "1.0"
_ModelT = TypeVar("_ModelT", bound=BaseModel)


class _FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    @model_validator(mode="after")
    def _selected_refs_and_times(self) -> Self:
        for name in type(self).model_fields:
            value = getattr(self, name)
            if isinstance(value, artifacts.ArtifactRef) and (
                value.manifest_profile_sha256 is None or not value.kind or not value.media_type
            ):
                raise ValueError("n5_replay_selected_profile_required")
            if isinstance(value, datetime) and value.utcoffset() is None:
                raise ValueError("n5_replay_timezone_required")
        valid_from, valid_until = (
            getattr(self, "valid_from", None),
            getattr(self, "valid_until", None),
        )
        if (
            isinstance(valid_from, datetime)
            and isinstance(valid_until, datetime)
            and valid_until <= valid_from
        ):
            raise ValueError("n5_replay_validity_interval_invalid")
        return self


class N5ReplayScope(_FrozenModel):
    """Exact accepting-organizational purpose and runtime scope."""

    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    accepting_organization: str = Field(min_length=1)
    scope_id: str = Field(min_length=1)
    authority_purpose: Literal["protected_n5_replay"] = "protected_n5_replay"


class N5ReplayComparatorProfile(_FrozenModel):
    """A candidate exact-byte comparator, accepted separately by appointment."""

    schema_version: Literal["policyos.n5_replay.comparator.v1"] = "policyos.n5_replay.comparator.v1"
    numerical_projection_schema: str = Field(min_length=1)
    comparison: Literal["exact_numerical_projection_bytes"] = "exact_numerical_projection_bytes"
    excluded_time_identity_paths: tuple[str, ...] = ()
    numerical_mismatch_policy: Literal["final_no_retry"] = "final_no_retry"
    infrastructure_retry_policy: Literal["appointment_limit_actual_work_charged"] = (
        "appointment_limit_actual_work_charged"
    )


class N5OriginalProducerSeal(_FrozenModel):
    """Producer's own component/result binding; never a verifier appointment."""

    schema_version: Literal["policyos.n5_replay.producer_seal.v1"] = (
        "policyos.n5_replay.producer_seal.v1"
    )
    scope: N5ReplayScope
    original_job_id: str = Field(min_length=1)
    original_run_id: str = Field(min_length=1)
    producer_instance_id: str = Field(min_length=1)
    numerical_intent_ref: artifacts.ArtifactRef
    numerical_intent_hash: Digest
    execution_profile_ref: artifacts.ArtifactRef
    numerical_projection_schema: str = Field(min_length=1)
    numerical_result_projection_ref: artifacts.ArtifactRef
    numerical_result_projection_hash: Digest
    seed_schedule_hash: Digest
    produced_at: datetime


class N5OriginalProducerSealV2(N5OriginalProducerSeal):
    """Signed producer seal with a parent-only original execution binding."""

    schema_version: Literal["policyos.n5_replay.producer_seal.v2"] = (
        "policyos.n5_replay.producer_seal.v2"
    )
    original_execution_ref: artifacts.ArtifactRef

    @model_validator(mode="after")
    def _execution_ref_kind(self) -> Self:
        if (
            self.original_execution_ref.kind != N5_REPLAY_ORIGINAL_EXECUTION_KIND
            or self.original_execution_ref.media_type != "application/json"
        ):
            raise ValueError("n5_replay_original_execution_ref_kind_mismatch")
        return self


class N5ReplayNumericalIntentV2(_FrozenModel):
    """Versioned blind action intent bound to one selected candidate V5 input."""

    schema_version: Literal["policyos.n5_replay.numerical_intent.v2"] = (
        "policyos.n5_replay.numerical_intent.v2"
    )
    selected_candidate_simulation_n5_input_ref: artifacts.ArtifactRef
    source_run_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)
    original_run_id: str = Field(min_length=1)
    original_job_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    declared_numerical_intent_content_hash: Digest
    declared_callable_content_hash: Digest
    production_image_ref: artifacts.ArtifactRef
    production_image_content_hash: Digest
    prepared_configuration_ref: artifacts.ArtifactRef
    prepared_configuration_content_hash: Digest
    prepared_configuration_hash: Digest

    @model_validator(mode="after")
    def _check_intent_binding(self) -> Self:
        if (
            self.selected_candidate_simulation_n5_input_ref.kind
            != "runtime.quality.candidate_simulation_n5_input"
            or self.selected_candidate_simulation_n5_input_ref.media_type != "application/json"
            or self.production_image_ref.kind != N5_REPLAY_PRODUCTION_IMAGE_KIND
            or self.production_image_ref.media_type != "application/json"
            or self.prepared_configuration_ref.kind != N5_REPLAY_PREPARED_CONFIGURATION_KIND
            or self.prepared_configuration_ref.media_type != "application/json"
        ):
            raise ValueError("n5_replay_intent_artifact_kind_mismatch")
        return self


class N5ReplayAppointment(_FrozenModel):
    """Accepting independent-control function's exact methodological appointment."""

    schema_version: Literal["policyos.n5_replay.appointment.v1"] = (
        "policyos.n5_replay.appointment.v1"
    )
    scope: N5ReplayScope
    launcher_identity: str = Field(min_length=1)
    launcher_key_id: str = Field(min_length=1)
    launcher_profile_ref: artifacts.ArtifactRef
    comparator_ref: artifacts.ArtifactRef
    comparator_content_hash: Digest
    supported_tiers: tuple[ReplayTier, ...] = Field(min_length=1)
    allocated_capacity_units: int = Field(ge=1, strict=True)
    attempt_limit: int = Field(ge=1, strict=True)
    valid_from: datetime
    valid_until: datetime
    configured_independence: ConfiguredIndependence


class N5ReplayAppointmentVerification(_FrozenModel):
    """Separate deployment administrator's signed appointment/build check."""

    schema_version: Literal["policyos.n5_replay.appointment_check.v1"] = (
        "policyos.n5_replay.appointment_check.v1"
    )
    scope: N5ReplayScope
    appointment_ref: artifacts.ArtifactRef
    appointment_content_hash: Digest
    current_trust_snapshot_hash: Digest
    deployed_component_provenance_ref: artifacts.ArtifactRef
    launcher_profile_ref: artifacts.ArtifactRef
    valid_from: datetime
    valid_until: datetime
    predicate_class: Literal["independently_reconciled"] = "independently_reconciled"


class N5ReplayPublicKey(_FrozenModel):
    """Current public-key role binding supplied by deployment administration."""

    identity: str = Field(min_length=1)
    organization: str = Field(min_length=1)
    function: str = Field(min_length=1)
    public_key_path: Path
    roles: tuple[ReplayTrustRole, ...] = Field(min_length=1)


class N5ReplayDeploymentConfig(_FrozenModel):
    """Public trust only; an empty production configuration appoints nobody."""

    trusted_keys: tuple[N5ReplayPublicKey, ...] = ()
    authorized_scopes: tuple[N5ReplayScope, ...] = ()
    revoked_key_ids: tuple[str, ...] = ()
    appointment_evidence_ref: artifacts.ArtifactRef | None = None
    verification_evidence_ref: artifacts.ArtifactRef | None = None
    minimum_independence: ConfiguredIndependence = "same_organization_separate_function"
    trust_root_class: Literal["production", "demonstration_test_root"] = "production"


@dataclass(frozen=True, slots=True)
class N5ReplayDeployedComponent:
    """Native assembly observation, unavailable from a request/statement DTO.

    The assembly port must observe the actual loaded component/profile and its
    PolicyOS-owned build provenance. This is not an institutional appointment.
    """

    launcher_profile_ref: artifacts.ArtifactRef
    execution_profile_ref: artifacts.ArtifactRef
    component_provenance_ref: artifacts.ArtifactRef


@dataclass(frozen=True, slots=True)
class N5ReplayDeploymentState:
    """Current native assembly inputs; missing component remains unestablished."""

    config: N5ReplayDeploymentConfig
    component: N5ReplayDeployedComponent | None = None


class N5ReplayUseQuery(_FrozenModel):
    """Comparison-side intent; never pass this original-result context to launcher."""

    scope: N5ReplayScope
    original_producer_evidence_ref: artifacts.ArtifactRef
    execution_profile_ref: artifacts.ArtifactRef
    comparator_ref: artifacts.ArtifactRef
    tier: ReplayTier
    replay_seed_schedule_hash: Digest
    planned_physical_units: int = Field(ge=1, strict=True)
    replay_run_id: str = Field(min_length=1)
    replay_job_id: str = Field(min_length=1)


class N5BlindReplayLaunchSpec(_FrozenModel):
    """Frozen action/input description; no original numerical result or seal."""

    schema_version: Literal["policyos.n5_replay.blind_launch.v1"] = (
        "policyos.n5_replay.blind_launch.v1"
    )
    scope: N5ReplayScope
    numerical_intent_ref: artifacts.ArtifactRef
    numerical_intent_hash: Digest
    execution_profile_ref: artifacts.ArtifactRef
    launcher_profile_ref: artifacts.ArtifactRef
    comparator_ref: artifacts.ArtifactRef
    tier: ReplayTier
    seed_schedule_hash: Digest
    planned_physical_units: int = Field(ge=1, strict=True)
    replay_run_id: str = Field(min_length=1)
    replay_job_id: str = Field(min_length=1)
    invocation_purpose: Literal["diagnostic"] = "diagnostic"


class N5BlindReplayLaunchSpecV2(_FrozenModel):
    """Child-process action contract with selected source and no original result."""

    schema_version: Literal["policyos.n5_replay.blind_launch.v2"] = (
        "policyos.n5_replay.blind_launch.v2"
    )
    scope: N5ReplayScope
    numerical_intent_ref: artifacts.ArtifactRef
    numerical_intent_hash: Digest
    selected_candidate_simulation_n5_input_ref: artifacts.ArtifactRef
    source_run_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)
    original_run_id: str = Field(min_length=1)
    original_job_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    declared_numerical_intent_content_hash: Digest
    declared_callable_content_hash: Digest
    production_image_ref: artifacts.ArtifactRef
    production_image_content_hash: Digest
    prepared_configuration_ref: artifacts.ArtifactRef
    prepared_configuration_content_hash: Digest
    prepared_configuration_hash: Digest
    execution_profile_ref: artifacts.ArtifactRef
    launcher_profile_ref: artifacts.ArtifactRef
    comparator_ref: artifacts.ArtifactRef
    tier: ReplayTier
    seed_schedule_hash: Digest
    planned_physical_units: int = Field(ge=1, strict=True)
    replay_run_id: str = Field(min_length=1)
    replay_job_id: str = Field(min_length=1)
    invocation_purpose: Literal["diagnostic"] = "diagnostic"

    @model_validator(mode="after")
    def _check_child_scope(self) -> Self:
        if (
            self.selected_candidate_simulation_n5_input_ref.kind
            != "runtime.quality.candidate_simulation_n5_input"
            or self.production_image_ref.kind != N5_REPLAY_PRODUCTION_IMAGE_KIND
            or self.prepared_configuration_ref.kind != N5_REPLAY_PREPARED_CONFIGURATION_KIND
            or self.replay_run_id in {self.source_run_id, self.original_run_id}
            or self.replay_job_id in {self.source_job_id, self.original_job_id}
            or self.scope.tenant_id != self.tenant_id
            or self.scope.cell_id != self.cell_id
        ):
            raise ValueError("n5_replay_blind_intent_scope_mismatch")
        return self


class N5ReplayVerificationCacheKey(_FrozenModel):
    """Comparison identity only; an identity hit does not grant permission."""

    schema_version: Literal["policyos.n5_replay.cache_key.v1"] = "policyos.n5_replay.cache_key.v1"
    numerical_intent_hash: Digest
    execution_profile_ref: artifacts.ArtifactRef
    comparator_ref: artifacts.ArtifactRef
    tier: ReplayTier
    numerical_result_projection_hash: Digest

    @property
    def content_hash(self) -> str:
        """Hash exactly the declared key, excluding appointment/permission."""
        return security.raw_content_hash(security.canonical_statement_bytes(self))


class N5ReplayVerificationCacheKeyV2(_FrozenModel):
    """Native numerical identity, excluding source labels and appointment state."""

    schema_version: Literal["policyos.n5_replay.cache_key.v2"] = "policyos.n5_replay.cache_key.v2"
    declared_numerical_intent_content_hash: Digest
    declared_callable_content_hash: Digest
    numerical_profile_content_hash: Digest
    production_image_content_hash: Digest
    comparator_ref: artifacts.ArtifactRef
    comparator_content_hash: Digest
    tier: ReplayTier
    seed_schedule_hash: Digest
    numerical_result_projection_hash: Digest

    @model_validator(mode="after")
    def _comparator_binding(self) -> Self:
        if (
            self.comparator_ref.kind != "runtime.quality.n5_replay_comparator_profile"
            or self.comparator_content_hash != str(self.comparator_ref.artifact_id)
        ):
            raise ValueError("n5_replay_cache_comparator_binding_mismatch")
        return self

    @property
    def content_hash(self) -> str:
        """Hash native numerical identity, not appointment/provenance labels."""
        return security.raw_content_hash(security.canonical_statement_bytes(self))


def build_n5_replay_verification_cache_key_v2(
    *,
    declared_numerical_intent_content_hash: str,
    declared_callable_content_hash: str,
    native_profile: N5NativeExecutionProfile,
    production_image: N5ProductionImage,
    comparator_ref: artifacts.ArtifactRef,
    tier: ReplayTier,
    seed_schedule_hash: str,
    numerical_result_projection_hash: str,
) -> N5ReplayVerificationCacheKeyV2:
    """Build a semantic cache identity from already recomputed native inputs.

    Call only after the selected source/request have been rebuilt, ordered seeds
    recomputed, the original projection reprojected from the selected result,
    and current appointment permissions rechecked. This constructor does not
    perform those checks or grant protected use.
    """
    from polisyos.runtime.quality.n5_execution_basis import N5ProductionImage
    from polisyos.runtime.quality.n5_execution_profile import N5NativeExecutionProfile

    if type(native_profile) is not N5NativeExecutionProfile:
        raise TypeError("n5_replay_cache_native_profile_untyped")
    if type(production_image) is not N5ProductionImage:
        raise TypeError("n5_replay_cache_production_image_untyped")
    native_profile = N5NativeExecutionProfile.model_validate(
        native_profile.model_dump(mode="python")
    )
    production_image = N5ProductionImage.model_validate(production_image.model_dump(mode="python"))
    return N5ReplayVerificationCacheKeyV2(
        declared_numerical_intent_content_hash=declared_numerical_intent_content_hash,
        declared_callable_content_hash=declared_callable_content_hash,
        numerical_profile_content_hash=native_profile.numerical_profile_content_hash,
        production_image_content_hash=production_image.content_hash,
        comparator_ref=comparator_ref,
        comparator_content_hash=str(comparator_ref.artifact_id),
        tier=tier,
        seed_schedule_hash=seed_schedule_hash,
        numerical_result_projection_hash=numerical_result_projection_hash,
    )


class N5ReplayAppointmentResolution(_FrozenModel):
    """Current intake admission, never a protected numerical-use verdict."""

    status: Literal["appointed", "verifier_unappointed", "refused"]
    code: str | None = None
    appointment_ref: artifacts.ArtifactRef | None = None
    verification_ref: artifacts.ArtifactRef | None = None
    launch_spec: N5BlindReplayLaunchSpec | None = None
    cache_key: N5ReplayVerificationCacheKey | None = None
    trust_snapshot_hash: Digest | None = None
    configured_independence: ConfiguredIndependence | None = None
    trust_root_class: Literal["production", "demonstration_test_root"] = "production"
    scientific_independence: Literal["not_established"] = "not_established"
    candidate_work_allowed: Literal[True] = True
    protected_use_allowed: Literal[False] = False


class N5ReplayExecutableResolution(_FrozenModel):
    """Separate executable intake; v1 cache identity never grants reuse permission.

    ``cache_key_v2`` remains absent until the child rebuilds the native request,
    recomputes ordered seeds and reprojects the original selected result.
    """

    status: Literal["appointed", "verifier_unappointed", "refused"]
    code: str | None = None
    appointment_resolution: N5ReplayAppointmentResolution
    launch_spec: N5BlindReplayLaunchSpecV2 | None = None
    cache_key_v2: N5ReplayVerificationCacheKeyV2 | None = None
    protected_use_allowed: Literal[False] = False

    @model_validator(mode="after")
    def _resolution_shape(self) -> Self:
        if (
            (self.status == "appointed") != (self.launch_spec is not None)
            or (self.launch_spec is not None and self.appointment_resolution.status != "appointed")
            or (self.cache_key_v2 is not None and self.launch_spec is None)
        ):
            raise ValueError("n5_replay_executable_resolution_shape_mismatch")
        return self


class N5AppointedReplayRecord(_FrozenModel):
    """Launcher's sealed execution statement; physical work needs owner reconciliation."""

    schema_version: Literal["policyos.n5_replay.launcher_record.v1"] = (
        "policyos.n5_replay.launcher_record.v1"
    )
    scope: N5ReplayScope
    appointment_ref: artifacts.ArtifactRef
    launch_spec_hash: Digest
    replay_run_id: str = Field(min_length=1)
    replay_job_id: str = Field(min_length=1)
    launcher_instance_id: str = Field(min_length=1)
    numerical_intent_hash: Digest
    execution_profile_ref: artifacts.ArtifactRef
    comparator_ref: artifacts.ArtifactRef
    tier: ReplayTier
    seed_schedule_hash: Digest
    attempt_number: int = Field(ge=1, strict=True)
    planned_physical_units: int = Field(ge=1, strict=True)
    completed_physical_units: int = Field(ge=0, strict=True)
    outcome: Literal["completed", "infrastructure_error"]
    replay_result_projection_ref: artifacts.ArtifactRef | None = None
    replay_result_projection_hash: Digest | None = None
    started_at: datetime
    finished_at: datetime

    @model_validator(mode="after")
    def _completion_shape(self) -> Self:
        if (
            self.finished_at < self.started_at
            or self.completed_physical_units > self.planned_physical_units
        ):
            raise ValueError("n5_replay_record_work_invalid")
        if self.outcome == "completed" and (
            self.completed_physical_units != self.planned_physical_units
            or self.replay_result_projection_ref is None
            or self.replay_result_projection_hash is None
        ):
            raise ValueError("n5_replay_record_incomplete")
        return self


class N5AppointedReplayRecordV2(N5AppointedReplayRecord):
    """Signed launcher statement bound to the completed parent reconciliation."""

    schema_version: Literal["policyos.n5_replay.launcher_record.v2"] = (
        "policyos.n5_replay.launcher_record.v2"
    )
    publication_id: str = Field(min_length=1)
    original_producer_evidence_ref: artifacts.ArtifactRef
    original_execution_ref: artifacts.ArtifactRef
    appointment_evidence_ref: artifacts.ArtifactRef
    appointment_verification_evidence_ref: artifacts.ArtifactRef
    candidate_comparison_ref: artifacts.ArtifactRef
    child_execution_ref: artifacts.ArtifactRef
    diagnostic_ledger_snapshot_ref: artifacts.ArtifactRef

    @model_validator(mode="after")
    def _completed_refs(self) -> Self:
        if (
            self.outcome != "completed"
            or self.replay_result_projection_ref is None
            or self.replay_result_projection_ref.kind
            != "runtime.quality.n5_numerical_result_projection_bytes"
            or self.replay_result_projection_ref.media_type != "application/octet-stream"
            or str(self.replay_result_projection_ref.artifact_id)
            != self.replay_result_projection_hash
            or self.candidate_comparison_ref.kind
            != "runtime.quality.n5_replay_candidate_comparison"
            or self.child_execution_ref.kind != "runtime.quality.n5_blind_replay_execution"
            or self.diagnostic_ledger_snapshot_ref.kind
            != "runtime.quality.n5_diagnostic_ledger_snapshot"
            or self.candidate_comparison_ref.media_type != "application/json"
            or self.child_execution_ref.media_type != "application/json"
            or self.diagnostic_ledger_snapshot_ref.media_type != "application/octet-stream"
        ):
            raise ValueError("n5_replay_record_completed_binding_invalid")
        return self


class N5ReplayRecordVerification(_FrozenModel):
    """Authenticated launcher statement, distinct from comparison/accounting proof."""

    status: Literal["authenticated_record", "not_established"]
    code: str | None = None
    appointment: N5ReplayAppointmentResolution
    record_ref: artifacts.ArtifactRef | None = None
    physical_work_reconciled: Literal[False] = False
    comparison_status: Literal["not_performed"] = "not_performed"
    protected_use_allowed: Literal[False] = False


@dataclass(frozen=True, slots=True)
class _Trust:
    by_key: dict[str, N5ReplayPublicKey]
    verifiers: dict[str, artifacts.Ed25519Verifier]
    snapshot_hash: str


def _trust(config: N5ReplayDeploymentConfig) -> _Trust:
    by_key, verifiers, snapshot = {}, {}, []
    for row in config.trusted_keys:
        public_bytes = row.public_key_path.read_bytes()
        probe = artifacts.Ed25519Verifier(strict_identity=True)
        key_id = probe.load_trusted_key_pem(public_bytes, identity=row.identity)
        if key_id in by_key:
            raise ValueError("n5_replay_public_key_role_alias")
        by_key[key_id] = row
        for role in row.roles:
            verifier = verifiers.setdefault(role, artifacts.Ed25519Verifier(strict_identity=True))
            verifier.load_trusted_key_pem(public_bytes, identity=row.identity)
        snapshot.append(
            {
                "key_id": key_id,
                "identity": row.identity,
                "organization": row.organization,
                "function": row.function,
                "roles": sorted(row.roles),
            }
        )
    for verifier in verifiers.values():
        for key_id in config.revoked_key_ids:
            verifier.add_revoked_key_id(key_id)
    raw = {
        "version": "policyos.n5_replay.public_trust.v1",
        "keys": sorted(snapshot, key=lambda x: x["key_id"]),
        "authorized_scopes": sorted(
            (scope.model_dump(mode="json") for scope in config.authorized_scopes),
            key=lambda scope: (
                scope["tenant_id"],
                scope["cell_id"],
                scope["accepting_organization"],
                scope["scope_id"],
            ),
        ),
        "revoked_key_ids": sorted(config.revoked_key_ids),
        "minimum_independence": config.minimum_independence,
        "trust_root_class": config.trust_root_class,
    }
    return _Trust(by_key, verifiers, security.raw_content_hash(to_canonical_bytes(raw)))


def _read_n5_versioned_core_json[T: BaseModel](
    store: artifacts.ArtifactStore,
    ref: artifacts.ArtifactRef,
    model: type[T],
    *,
    kind: str,
    schema_version: str,
    schema_name: str | None = None,
) -> tuple[T, bytes]:
    """Read one selected typed Core JSON profile with exact kind/schema/CAS binding."""
    if ref.kind != kind or ref.media_type != "application/json":
        raise ValueError("n5_replay_core_artifact_kind_mismatch")
    manifest, _ = artifacts.read_core_manifest_profile(store, ref)
    schema = manifest.artifact_schema
    if (
        manifest.kind != kind
        or manifest.media_type != "application/json"
        or schema is None
        or schema.name != (schema_name or kind)
        or schema.version != schema_version
        or not store.verify(ref).ok
    ):
        raise ValueError("n5_replay_core_artifact_schema_mismatch")
    raw = store.get_bytes(ref)
    if security.raw_content_hash(raw) != str(ref.artifact_id):
        raise ValueError("n5_replay_core_artifact_content_hash_mismatch")
    return artifacts.validate_core_model_json_artifact(
        model, store, ref, raw_payload_bytes=raw
    ), raw


def n5_replay_trust_snapshot_hash(config: N5ReplayDeploymentConfig) -> str:
    """Recompute public roles/key fingerprints/revocations from current key bytes."""
    return _trust(config).snapshot_hash


class N5ReplayAppointmentResolver:
    """Verify purpose-specific evidence against native assembly on every use.

    ``current_deployment`` and ``clock`` are trusted native composition ports,
    not deserialized request inputs. No signing operation/key is accepted here.
    No admission or cache-key object is reused as current permission.
    """

    def __init__(
        self,
        *,
        store: artifacts.ArtifactStore,
        current_deployment: Callable[[], N5ReplayDeploymentState] | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._store = store
        self._current = current_deployment or (
            lambda: N5ReplayDeploymentState(N5ReplayDeploymentConfig())
        )
        self._clock = clock

    def _signed(
        self, ref: artifacts.ArtifactRef, model: type[_ModelT], role: ReplayTrustRole, trust: _Trust
    ) -> tuple[_ModelT, artifacts.ArtifactRef, str, N5ReplayPublicKey]:
        if ref.manifest_profile_sha256 is None:
            raise ValueError("n5_replay_selected_profile_required")
        evidence = FileSystemSignedArtifactEvidenceRepository(self._store).read_exact(
            evidence_record_ref=ref
        )
        verifier = trust.verifiers.get(role)
        if verifier is None or not security.verify_signed_evidence(evidence, verifier=verifier):
            raise ValueError("n5_replay_signature_untrusted_or_revoked")
        signature = artifacts.DetachedSignature.model_validate_json(
            evidence.detached_signature_bytes
        )
        # Identity/organization/function come from CURRENT key configuration,
        # never the unsigned sidecar's optional signer-identity label.
        row = trust.by_key[signature.key_id]
        statement_ref = artifacts.artifact_ref_for_manifest(
            artifacts.ArtifactManifest.model_validate_json(evidence.exact_manifest_bytes)
        )
        expected_kind = {
            N5ReplayAppointment: "runtime.quality.n5_replay_appointment",
            N5ReplayAppointmentVerification: "runtime.quality.n5_replay_appointment_verification",
            N5OriginalProducerSeal: "runtime.quality.n5_original_producer_seal",
            N5OriginalProducerSealV2: "runtime.quality.n5_original_producer_seal",
            N5AppointedReplayRecord: "runtime.quality.n5_appointed_replay_record",
            N5AppointedReplayRecordV2: "runtime.quality.n5_appointed_replay_record",
        }.get(model)
        if expected_kind is None or statement_ref.kind != expected_kind:
            raise ValueError("n5_replay_signed_statement_kind_mismatch")
        statement_model = model
        if model is N5OriginalProducerSeal:
            try:
                parsed_v2 = security.parse_canonical_statement(
                    evidence.blob_bytes, N5OriginalProducerSealV2
                )
            except ValueError:
                pass
            else:
                return (
                    cast("_ModelT", parsed_v2),
                    statement_ref,
                    signature.key_id,
                    row,
                )
        if model is N5AppointedReplayRecord:
            try:
                parsed_v2_record = security.parse_canonical_statement(
                    evidence.blob_bytes, N5AppointedReplayRecordV2
                )
            except ValueError:
                pass
            else:
                return cast("_ModelT", parsed_v2_record), statement_ref, signature.key_id, row
        return (
            cast(
                "_ModelT",
                security.parse_canonical_statement(evidence.blob_bytes, statement_model),
            ),
            statement_ref,
            signature.key_id,
            row,
        )

    def _current_state(self) -> N5ReplayDeploymentState:
        state = self._current()
        if (
            type(state) is not N5ReplayDeploymentState
            or type(state.config) is not N5ReplayDeploymentConfig
        ):
            raise TypeError("native deployment state is untyped")
        config = N5ReplayDeploymentConfig.model_validate(state.config.model_dump(mode="python"))
        component = state.component
        if component is not None:
            if type(component) is not N5ReplayDeployedComponent:
                raise TypeError("native deployed component is untyped")
            component = N5ReplayDeployedComponent(
                *(
                    artifacts.ArtifactRef.model_validate(ref.model_dump(mode="python"))
                    for ref in (
                        component.launcher_profile_ref,
                        component.execution_profile_ref,
                        component.component_provenance_ref,
                    )
                )
            )
        return N5ReplayDeploymentState(config, component)

    def resolve(self, query: N5ReplayUseQuery) -> N5ReplayAppointmentResolution:
        """Admit an appointment for launch preparation, without executing replay."""
        try:
            state = self._current_state()
            if type(query) is not N5ReplayUseQuery:
                raise TypeError("replay query is untyped")
            query = N5ReplayUseQuery.model_validate(query.model_dump(mode="python"))
        except (OSError, RuntimeError, TypeError, ValueError):
            return N5ReplayAppointmentResolution(
                status="verifier_unappointed", code="n5_replay_deployment_not_established"
            )
        config = state.config
        root = config.trust_root_class
        if (
            not config.trusted_keys
            or config.appointment_evidence_ref is None
            or config.verification_evidence_ref is None
        ):
            return N5ReplayAppointmentResolution(
                status="verifier_unappointed", code="verifier_unappointed", trust_root_class=root
            )
        if query.scope not in config.authorized_scopes:
            return N5ReplayAppointmentResolution(
                status="refused",
                code="n5_replay_current_deployment_scope_unappointed",
                trust_root_class=root,
            )
        if state.component is None:
            return N5ReplayAppointmentResolution(
                status="verifier_unappointed",
                code="deployed_component_not_established",
                trust_root_class=root,
            )
        try:
            return self._resolve(query, state, _trust(config))
        except artifacts.ArtifactOwnershipError:
            raise
        except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            return N5ReplayAppointmentResolution(
                status="refused",
                code=str(exc) or "n5_replay_admission_error",
                trust_root_class=root,
            )

    def resolve_executable(self, query: N5ReplayUseQuery) -> N5ReplayExecutableResolution:
        """Resolve only a typed v2 intent into a blind child-process spec.

        The full v1 appointment path runs first and remains non-executable on
        its own. This method then reopens the signed producer seal, typed V5
        input, prepared native configuration, and fixed comparator under the
        same current trust snapshot. Original result and seal refs never enter
        the returned child spec.
        """
        admission = self.resolve(query)
        if admission.status != "appointed":
            return N5ReplayExecutableResolution(
                status=admission.status,
                code=admission.code,
                appointment_resolution=admission,
            )
        try:
            state = self._current_state()
            if type(query) is not N5ReplayUseQuery:
                raise TypeError("replay query is untyped")
            query = N5ReplayUseQuery.model_validate(query.model_dump(mode="python"))
            config = state.config
            trust = _trust(config)
            if (
                admission.trust_snapshot_hash != trust.snapshot_hash
                or state.component is None
                or admission.appointment_ref is None
                or admission.verification_ref is None
            ):
                raise ValueError("n5_replay_deployment_changed_during_admission")
            base = admission.launch_spec
            if base is None:
                raise ValueError("n5_replay_appointment_launch_spec_not_established")
            producer, _, _, _ = self._signed(
                query.original_producer_evidence_ref,
                N5OriginalProducerSeal,
                "original_producer",
                trust,
            )
            if type(producer) is not N5OriginalProducerSealV2:
                raise ValueError("n5_replay_original_execution_binding_not_established")
            intent_ref = producer.numerical_intent_ref
            intent_payload, intent_bytes = _read_n5_versioned_core_json(
                self._store,
                intent_ref,
                N5ReplayNumericalIntentV2,
                kind=N5_REPLAY_NUMERICAL_INTENT_KIND,
                schema_version=N5_REPLAY_INTENT_V2_CORE_SCHEMA_VERSION,
            )
            if security.raw_content_hash(intent_bytes) != producer.numerical_intent_hash:
                raise ValueError("n5_replay_numerical_intent_content_hash_mismatch")
            intent = intent_payload
            if (
                intent.original_run_id != producer.original_run_id
                or intent.original_job_id != producer.original_job_id
                or intent.tenant_id != query.scope.tenant_id
                or intent.cell_id != query.scope.cell_id
                or producer.scope != query.scope
            ):
                raise ValueError("n5_replay_intent_source_scope_mismatch")

            from polisyos.runtime.quality.n5_replay_execution import (
                N5OriginalProducerAction,
                N5OriginalProducerExecution,
            )

            original_execution, _execution_bytes = _read_n5_versioned_core_json(
                self._store,
                producer.original_execution_ref,
                N5OriginalProducerExecution,
                kind=N5_REPLAY_ORIGINAL_EXECUTION_KIND,
                schema_version=N5_REPLAY_ORIGINAL_EXECUTION_SCHEMA_VERSION,
            )
            if (
                original_execution.source_input_ref
                != intent.selected_candidate_simulation_n5_input_ref
                or original_execution.source_run_id != intent.source_run_id
                or original_execution.source_job_id != intent.source_job_id
                or original_execution.producer_run_id != producer.original_run_id
                or original_execution.producer_job_id != producer.original_job_id
                or original_execution.numerical_intent_ref != intent_ref
                or original_execution.execution_profile_ref != producer.execution_profile_ref
                or original_execution.execution_profile_ref != base.execution_profile_ref
                or original_execution.tenant_id != intent.tenant_id
                or original_execution.cell_id != intent.cell_id
                or original_execution.authority_purpose != "candidate_original_n5_only"
                or original_execution.protected_use_allowed
            ):
                raise ValueError("n5_replay_original_execution_binding_mismatch")
            if (
                not self._store.verify(original_execution.result_ref).ok
                or not self._store.verify(original_execution.ledger_snapshot_ref).ok
            ):
                raise ValueError("n5_replay_original_execution_artifacts_unavailable")
            ledger_bytes = self._store.get_bytes(original_execution.ledger_snapshot_ref)
            if security.raw_content_hash(
                ledger_bytes
            ) != original_execution.ledger_hash or security.raw_content_hash(ledger_bytes) != str(
                original_execution.ledger_snapshot_ref.artifact_id
            ):
                raise ValueError("n5_replay_original_ledger_snapshot_mismatch")
            original_action, action_bytes = _read_n5_versioned_core_json(
                self._store,
                original_execution.action_ref,
                N5OriginalProducerAction,
                kind=N5_REPLAY_ORIGINAL_ACTION_KIND,
                schema_name=N5_REPLAY_ORIGINAL_ACTION_SCHEMA_NAME,
                schema_version=N5_REPLAY_ORIGINAL_ACTION_SCHEMA_VERSION,
            )
            if (
                security.raw_content_hash(action_bytes) != original_execution.action_hash
                or security.raw_content_hash(action_bytes)
                != str(original_execution.action_ref.artifact_id)
                or original_action.source_input_ref != original_execution.source_input_ref
                or original_action.source_run_id != original_execution.source_run_id
                or original_action.source_job_id != original_execution.source_job_id
                or original_action.producer_run_id != original_execution.producer_run_id
                or original_action.producer_job_id != original_execution.producer_job_id
                or original_action.tenant_id != original_execution.tenant_id
                or original_action.cell_id != original_execution.cell_id
                or original_action.authority_purpose != "candidate_original_n5_only"
            ):
                raise ValueError("n5_replay_original_action_binding_mismatch")

            from polisyos.runtime.quality.candidate_simulation import (
                CandidateSimulationN5InputV5,
            )
            from polisyos.runtime.quality.generation_source import GenerationSourceRepository
            from polisyos.runtime.quality.joint_simulation_horizon import (
                PreparedJointSimulationConfiguration,
            )
            from polisyos.runtime.quality.n5_execution_basis import N5ProductionImage

            selected_input_ref = intent.selected_candidate_simulation_n5_input_ref
            if (
                selected_input_ref.manifest_profile_sha256 is None
                or not self._store.verify(selected_input_ref).ok
            ):
                raise ValueError("n5_replay_selected_candidate_input_unavailable")
            input_record = GenerationSourceRepository(self._store).resolve_candidate_simulation_v5(
                ref=selected_input_ref,
                expected_run_id=intent.source_run_id,
                expected_job_id=intent.source_job_id,
                expected_tenant_id=intent.tenant_id,
                expected_cell_id=intent.cell_id,
            )
            if (
                type(input_record) is not CandidateSimulationN5InputV5
                or input_record.authority_purpose != "candidate_scenario_n5_only"
                or input_record.run_id != intent.source_run_id
                or input_record.job_id != intent.source_job_id
                or input_record.tenant_id != intent.tenant_id
                or input_record.cell_id != intent.cell_id
            ):
                raise ValueError("n5_replay_selected_candidate_input_not_established")

            image_ref = intent.production_image_ref
            image, image_bytes = _read_n5_versioned_core_json(
                self._store,
                image_ref,
                N5ProductionImage,
                kind=N5_REPLAY_PRODUCTION_IMAGE_KIND,
                schema_version=N5_REPLAY_V1_CORE_SCHEMA_VERSION,
            )
            if (
                security.raw_content_hash(image_bytes) != intent.production_image_content_hash
                or security.raw_content_hash(image_bytes) != str(image_ref.artifact_id)
                or not image.python_sources
                or image.lock_content_hash is None
                or image.selected_profile_content is None
                or image.reason_codes
            ):
                raise ValueError("n5_replay_production_image_content_not_established")

            prepared_ref = intent.prepared_configuration_ref
            prepared, prepared_bytes = _read_n5_versioned_core_json(
                self._store,
                prepared_ref,
                PreparedJointSimulationConfiguration,
                kind=N5_REPLAY_PREPARED_CONFIGURATION_KIND,
                schema_version=N5_REPLAY_V1_CORE_SCHEMA_VERSION,
            )
            from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_hash

            if (
                security.raw_content_hash(prepared_bytes)
                != intent.prepared_configuration_content_hash
                or security.raw_content_hash(prepared_bytes) != str(prepared_ref.artifact_id)
                or exact_n5_content_hash(prepared) != intent.prepared_configuration_hash
            ):
                raise ValueError("n5_replay_prepared_configuration_content_hash_mismatch")

            profile_ref = base.execution_profile_ref
            from polisyos.runtime.quality.n5_execution_profile import N5NativeExecutionProfile

            _native_profile, _profile_bytes = _read_n5_versioned_core_json(
                self._store,
                profile_ref,
                N5NativeExecutionProfile,
                kind=N5_REPLAY_EXECUTION_PROFILE_KIND,
                schema_version=N5_REPLAY_V1_CORE_SCHEMA_VERSION,
            )

            comparator_payload = artifacts.load_core_json_artifact(
                self._store, query.comparator_ref
            )
            comparator = N5ReplayComparatorProfile.model_validate(comparator_payload)
            from polisyos.runtime.quality.n5_replay_numerical_projection import (
                require_supported_n5_replay_comparator,
            )

            require_supported_n5_replay_comparator(comparator)
            if comparator.numerical_projection_schema != producer.numerical_projection_schema:
                raise ValueError("n5_replay_projection_schema_mismatch")

            from polisyos.runtime.quality.n5_replay_execution import _reopen_verified_original

            verified_execution, _original_request, _original_result = _reopen_verified_original(
                store=self._store,
                original_execution_ref=producer.original_execution_ref,
                scope=query.scope,
            )
            if verified_execution != original_execution:
                raise ValueError("n5_replay_original_execution_reconciliation_mismatch")

            latest_admission = self.resolve(query)
            if (
                latest_admission.status != "appointed"
                or latest_admission.appointment_ref != admission.appointment_ref
                or latest_admission.verification_ref != admission.verification_ref
                or latest_admission.trust_snapshot_hash != admission.trust_snapshot_hash
                or latest_admission.launch_spec != base
            ):
                raise ValueError("n5_replay_deployment_changed_during_admission")
            launch = N5BlindReplayLaunchSpecV2(
                scope=query.scope,
                numerical_intent_ref=intent_ref,
                numerical_intent_hash=producer.numerical_intent_hash,
                selected_candidate_simulation_n5_input_ref=(
                    intent.selected_candidate_simulation_n5_input_ref
                ),
                source_run_id=intent.source_run_id,
                source_job_id=intent.source_job_id,
                original_run_id=intent.original_run_id,
                original_job_id=intent.original_job_id,
                tenant_id=intent.tenant_id,
                cell_id=intent.cell_id,
                declared_numerical_intent_content_hash=(
                    intent.declared_numerical_intent_content_hash
                ),
                declared_callable_content_hash=intent.declared_callable_content_hash,
                production_image_ref=image_ref,
                production_image_content_hash=intent.production_image_content_hash,
                prepared_configuration_ref=prepared_ref,
                prepared_configuration_content_hash=intent.prepared_configuration_content_hash,
                prepared_configuration_hash=intent.prepared_configuration_hash,
                execution_profile_ref=profile_ref,
                launcher_profile_ref=base.launcher_profile_ref,
                comparator_ref=base.comparator_ref,
                tier=base.tier,
                seed_schedule_hash=base.seed_schedule_hash,
                planned_physical_units=base.planned_physical_units,
                replay_run_id=base.replay_run_id,
                replay_job_id=base.replay_job_id,
            )
            return N5ReplayExecutableResolution(
                status="appointed",
                appointment_resolution=admission,
                launch_spec=launch,
            )
        except artifacts.ArtifactOwnershipError:
            raise
        except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            return N5ReplayExecutableResolution(
                status="refused",
                code=str(exc) or "n5_replay_executable_intent_not_established",
                appointment_resolution=admission,
            )

    def _resolve(
        self, query: N5ReplayUseQuery, state: N5ReplayDeploymentState, trust: _Trust
    ) -> N5ReplayAppointmentResolution:
        config, component, now = state.config, state.component, self._clock()
        if now.utcoffset() is None:
            raise ValueError("n5_replay_current_clock_invalid")
        appointment, appointment_ref, issuer_key, issuer = self._signed(
            config.appointment_evidence_ref, N5ReplayAppointment, "appointment_issuer", trust
        )
        check, check_ref, admin_key, admin = self._signed(
            config.verification_evidence_ref,
            N5ReplayAppointmentVerification,
            "deployment_administrator",
            trust,
        )
        producer, _, producer_key, producer_role = self._signed(
            query.original_producer_evidence_ref, N5OriginalProducerSeal, "original_producer", trust
        )
        launcher = trust.by_key.get(appointment.launcher_key_id)
        if (
            launcher is None
            or "appointed_launcher" not in launcher.roles
            or appointment.launcher_key_id in config.revoked_key_ids
        ):
            raise ValueError("n5_replay_launcher_not_currently_trusted")
        keys = (issuer_key, admin_key, producer_key, appointment.launcher_key_id)
        actors = (issuer.identity, admin.identity, producer_role.identity, launcher.identity)
        if len(set(keys)) != 4 or len(set(actors)) != 4:
            raise ValueError("n5_replay_actor_or_key_not_independent")
        if issuer.organization != query.scope.accepting_organization:
            raise ValueError("n5_replay_issuer_organization_mismatch")
        for row, required_role in (
            (issuer, "appointment_issuer"),
            (admin, "deployment_administrator"),
            (launcher, "appointed_launcher"),
        ):
            if set(row.roles) != {required_role}:
                raise ValueError("n5_replay_control_key_role_overlap")
        result_users = [row for row in trust.by_key.values() if "result_user" in row.roles]
        if not result_users:
            raise ValueError("n5_replay_result_user_role_not_established")
        control_actor_identities = {issuer.identity, admin.identity, launcher.identity}
        control_key_ids = {issuer_key, admin_key, appointment.launcher_key_id}
        if any(
            row.identity in control_actor_identities or key_id in control_key_ids
            for key_id, row in trust.by_key.items()
            if "result_user" in row.roles
        ):
            raise ValueError("n5_replay_control_result_user_principal_overlap")
        excluded = [producer_role, *result_users]
        if any(
            (admin.organization, admin.function) == (row.organization, row.function)
            for row in [launcher, *excluded]
        ):
            raise ValueError("n5_replay_administrator_function_not_separate")
        if any(
            (issuer.organization, issuer.function) == (row.organization, row.function)
            for row in [admin, launcher, *excluded]
        ):
            raise ValueError("n5_replay_control_function_not_separate")
        if any(
            (launcher.organization, launcher.function) == (row.organization, row.function)
            for row in excluded
        ):
            raise ValueError("n5_replay_launcher_function_not_separate")
        independence = (
            "external_organization"
            if all(launcher.organization != row.organization for row in excluded)
            else "same_organization_separate_function"
        )
        if appointment.configured_independence != independence or (
            config.minimum_independence == "external_organization"
            and independence != "external_organization"
        ):
            raise ValueError("n5_replay_configured_independence_insufficient")
        if (
            appointment.scope != query.scope
            or check.scope != query.scope
            or producer.scope != query.scope
        ):
            raise ValueError("n5_replay_scope_mismatch")
        if producer.produced_at > now:
            raise ValueError("n5_replay_original_production_time_unestablished")
        if not (
            appointment.valid_from <= now < appointment.valid_until
            and check.valid_from <= now < check.valid_until
        ):
            raise ValueError("n5_replay_appointment_expired_or_not_yet_valid")
        if (
            check.appointment_ref != appointment_ref
            or check.appointment_content_hash != str(appointment_ref.artifact_id)
            or check.current_trust_snapshot_hash != trust.snapshot_hash
            or check.launcher_profile_ref != component.launcher_profile_ref
            or check.deployed_component_provenance_ref != component.component_provenance_ref
            or appointment.launcher_profile_ref != component.launcher_profile_ref
            or appointment.launcher_identity != launcher.identity
        ):
            raise ValueError("n5_replay_appointment_deployment_binding_mismatch")
        if (
            producer.execution_profile_ref != query.execution_profile_ref
            or query.execution_profile_ref != component.execution_profile_ref
        ):
            raise ValueError("n5_replay_execution_profile_mismatch")
        if (
            appointment.comparator_ref != query.comparator_ref
            or appointment.comparator_content_hash != str(query.comparator_ref.artifact_id)
        ):
            raise ValueError("n5_replay_comparator_not_frozen")
        if query.comparator_ref.kind != "runtime.quality.n5_replay_comparator_profile":
            raise ValueError("n5_replay_comparator_kind_mismatch")
        for bound_ref in (
            component.launcher_profile_ref,
            component.execution_profile_ref,
            component.component_provenance_ref,
            producer.numerical_intent_ref,
            producer.numerical_result_projection_ref,
        ):
            if bound_ref.manifest_profile_sha256 is None or not self._store.verify(bound_ref).ok:
                raise ValueError("n5_replay_component_or_producer_artifact_unavailable")
        if (
            security.raw_content_hash(self._store.get_bytes(producer.numerical_intent_ref))
            != producer.numerical_intent_hash
        ):
            raise ValueError("n5_replay_numerical_intent_content_hash_mismatch")
        if (
            security.raw_content_hash(
                self._store.get_bytes(producer.numerical_result_projection_ref)
            )
            != producer.numerical_result_projection_hash
        ):
            raise ValueError("n5_replay_numerical_result_content_hash_mismatch")
        comparator = artifacts.load_core_json_artifact(self._store, query.comparator_ref)
        profile = N5ReplayComparatorProfile.model_validate(comparator)
        if profile.numerical_projection_schema != producer.numerical_projection_schema:
            raise ValueError("n5_replay_projection_schema_mismatch")
        if query.tier not in appointment.supported_tiers or query.tier in {
            "NONDETERMINISTIC",
            "BEST_EFFORT_GPU",
        }:
            raise ValueError("n5_replay_tier_unsupported")
        if producer.seed_schedule_hash != query.replay_seed_schedule_hash:
            raise ValueError("n5_replay_different_seed_inference_profile_not_established")
        if query.planned_physical_units > appointment.allocated_capacity_units:
            raise ValueError("n5_replay_capacity_insufficient")
        if (
            query.replay_run_id == producer.original_run_id
            or query.replay_job_id == producer.original_job_id
        ):
            raise ValueError("n5_replay_requires_separate_diagnostic_job")
        latest = self._current_state()
        if (
            latest.component != component
            or _trust(latest.config).snapshot_hash != trust.snapshot_hash
            or latest.config != config
        ):
            raise ValueError("n5_replay_deployment_changed_during_admission")
        if not (
            appointment.valid_from <= self._clock() < appointment.valid_until
            and check.valid_from <= self._clock() < check.valid_until
        ):
            raise ValueError("n5_replay_appointment_expired_during_admission")
        launch = N5BlindReplayLaunchSpec(
            scope=query.scope,
            numerical_intent_ref=producer.numerical_intent_ref,
            numerical_intent_hash=producer.numerical_intent_hash,
            execution_profile_ref=query.execution_profile_ref,
            launcher_profile_ref=component.launcher_profile_ref,
            comparator_ref=query.comparator_ref,
            tier=query.tier,
            seed_schedule_hash=query.replay_seed_schedule_hash,
            planned_physical_units=query.planned_physical_units,
            replay_run_id=query.replay_run_id,
            replay_job_id=query.replay_job_id,
        )
        return N5ReplayAppointmentResolution(
            status="appointed",
            appointment_ref=appointment_ref,
            verification_ref=check_ref,
            launch_spec=launch,
            cache_key=N5ReplayVerificationCacheKey(
                numerical_intent_hash=producer.numerical_intent_hash,
                execution_profile_ref=query.execution_profile_ref,
                comparator_ref=query.comparator_ref,
                tier=query.tier,
                numerical_result_projection_hash=producer.numerical_result_projection_hash,
            ),
            trust_snapshot_hash=trust.snapshot_hash,
            configured_independence=independence,
            trust_root_class=config.trust_root_class,
        )

    def verify_launcher_record(
        self, query: N5ReplayUseQuery, evidence_ref: artifacts.ArtifactRef
    ) -> N5ReplayRecordVerification:
        """Re-admit current appointment and authenticate a launcher record only."""
        query = N5ReplayUseQuery.model_validate(query.model_dump(mode="python"))
        evidence_ref = artifacts.ArtifactRef.model_validate(evidence_ref.model_dump(mode="python"))
        admission = self.resolve(query)
        if admission.status != "appointed":
            return N5ReplayRecordVerification(
                status="not_established", code=admission.code, appointment=admission
            )
        try:
            state = self._current_state()
            trust = _trust(state.config)
            record, record_ref, key, _ = self._signed(
                evidence_ref, N5AppointedReplayRecord, "appointed_launcher", trust
            )
            appointment, _, _, _ = self._signed(
                state.config.appointment_evidence_ref,
                N5ReplayAppointment,
                "appointment_issuer",
                trust,
            )
            producer, _, _, _ = self._signed(
                query.original_producer_evidence_ref,
                N5OriginalProducerSeal,
                "original_producer",
                trust,
            )
            launch = admission.launch_spec
            if isinstance(record, N5AppointedReplayRecordV2):
                executable = self.resolve_executable(query)
                if executable.status != "appointed" or executable.launch_spec is None:
                    raise ValueError("n5_replay_executable_record_not_admitted")
                launch = executable.launch_spec
            if (
                trust.snapshot_hash != admission.trust_snapshot_hash
                or key != appointment.launcher_key_id
                or record.scope != query.scope
                or record.appointment_ref != admission.appointment_ref
                or record.launch_spec_hash
                != security.raw_content_hash(security.canonical_statement_bytes(launch))
                or record.numerical_intent_hash != launch.numerical_intent_hash
                or record.execution_profile_ref != launch.execution_profile_ref
                or record.comparator_ref != launch.comparator_ref
                or record.tier != launch.tier
                or record.seed_schedule_hash != launch.seed_schedule_hash
                or record.replay_run_id != launch.replay_run_id
                or record.replay_job_id != launch.replay_job_id
                or record.launcher_instance_id == producer.producer_instance_id
                or record.planned_physical_units != launch.planned_physical_units
                or record.attempt_number > appointment.attempt_limit
                or not (
                    appointment.valid_from
                    <= record.started_at
                    <= record.finished_at
                    < appointment.valid_until
                )
                or record.finished_at > self._clock()
            ):
                raise ValueError("n5_replay_launcher_record_binding_mismatch")
            if self.resolve(query) != admission:
                raise ValueError("n5_replay_permission_changed_during_record_verification")
            return N5ReplayRecordVerification(
                status="authenticated_record", appointment=admission, record_ref=record_ref
            )
        except artifacts.ArtifactOwnershipError:
            raise
        except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            return N5ReplayRecordVerification(
                status="not_established",
                code=str(exc) or "n5_replay_record_unavailable",
                appointment=admission,
            )
