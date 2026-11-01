"""Run manifest schema persisted for completed, replayed, and tenant-scoped executions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_serializer,
    model_validator,
)

from ..artifacts.manifest import ArtifactRef, EnvInfo, ProducerInfo


def utc_now() -> datetime:
    """Return a second-granularity UTC timestamp for stable run-manifest defaults."""
    return datetime.now(UTC).replace(microsecond=0)


class RunManifest(BaseModel):
    """Canonical summary of one executable run, its provenance, and its produced artifacts."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None

    producer: ProducerInfo | None = None
    env: EnvInfo | None = None

    registry_bundle: ArtifactRef

    inputs: list[ArtifactRef] = Field(default_factory=list)
    outputs: list[ArtifactRef] = Field(default_factory=list)

    status: str = "running"
    errors: list[dict[str, Any]] = Field(default_factory=list)

    trace_ref: ArtifactRef | None = None
    tenant_id: str | None = Field(
        default=None,
        description="Tenant identifier for tenant-scoped runs.",
    )
    cell_id: str | None = Field(
        default=None,
        description="Cell identifier for tenant-scoped runs.",
    )
    seed: int | None = Field(
        default=None,
        description="Deterministic seed for replayable runs.",
    )
    parent_run_id: str | None = Field(
        default=None,
        description="Parent run id for replay/resume lineage.",
    )
    replay_source_ref: ArtifactRef | None = Field(
        default=None,
        description="Original DecisionPacket reference when this run is a replay.",
    )
    execution_profile: str | None = Field(
        default=None,
        description="Effective execution profile used for this run.",
    )
    control_job_id: str | None = Field(
        default=None,
        description="Durable control-plane job identifier that launched this run.",
    )
    capability_manifest_ref: ArtifactRef | None = Field(
        default=None,
        description="Capability manifest captured for the run runtime posture.",
    )
    environment_manifest_ref: ArtifactRef | None = Field(
        default=None,
        description="Captured environment manifest reference.",
    )
    sbom_ref: ArtifactRef | None = Field(
        default=None,
        description="SBOM artifact reference captured for deployment provenance.",
    )
    tee_attestation_ref: ArtifactRef | None = Field(
        default=None,
        description="TEE attestation artifact reference for confidential execution.",
    )


class RunOwnerSnapshotV101(BaseModel):
    """Immutable, selected-profile owner facts needed to resume an incomplete run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0.1"]
    run_manifest: RunManifest
    access_scope_sha256: str | None
    previous_snapshot_ref: ArtifactRef | None

    @field_validator("access_scope_sha256")
    @classmethod
    def _validate_scope_digest(cls, value: str | None) -> str | None:
        """Keep absent scope explicit and reject malformed supplied digests."""
        if value is not None and (
            not isinstance(value, str)
            or len(value) != 71
            or not value.startswith("sha256:")
            or any(char not in "0123456789abcdef" for char in value[7:])
        ):
            raise ValueError("access_scope_sha256 must be sha256:<64 lowercase hex>")
        return value


class RunOwnerSnapshot(BaseModel):
    """Versioned run-owner facts, including the engine invocation-ledger tail."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0.2"]
    run_manifest: RunManifest
    access_scope_sha256: str | None
    previous_snapshot_ref: ArtifactRef | None
    runtime_invocation_tail_ref: ArtifactRef | None

    @field_validator("access_scope_sha256")
    @classmethod
    def _validate_scope_digest(cls, value: str | None) -> str | None:
        """Keep absent scope explicit and reject malformed supplied digests."""
        if value is not None and (
            not isinstance(value, str)
            or len(value) != 71
            or not value.startswith("sha256:")
            or any(char not in "0123456789abcdef" for char in value[7:])
        ):
            raise ValueError("access_scope_sha256 must be sha256:<64 lowercase hex>")
        return value

    @field_validator("runtime_invocation_tail_ref")
    @classmethod
    def _validate_invocation_tail(cls, value: ArtifactRef | None) -> ArtifactRef | None:
        """Require a complete selected-profile edge for any present owner tail."""
        if value is not None and value.manifest_profile_sha256 is None:
            raise ValueError("run_owner_invocation_tail_profile_not_established")
        return value


class RunInvocationImplementationIdentity(BaseModel):
    """Engine-observed identity of a selected in-process node implementation.

    This binds a run-owned start record to the concrete builtin class, executable
    methods, node specification, binding parameters, and bound instance state. It
    does not attest transitive imports, plugins, deployment artifacts, or a build.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    scope: Literal["in_process_selected_implementation"] = "in_process_selected_implementation"
    component_id: str = Field(min_length=1)
    owner_module: str = Field(min_length=1)
    owner_qualname: str = Field(min_length=1)
    runtime_class_token: str = Field(min_length=1)
    runtime_process_id: int = Field(ge=1)
    runtime_process_nonce: str = Field(pattern=r"^[0-9a-f]{32}$")
    runtime_execute_token: str = Field(min_length=1)
    runtime_bind_token: str | None = None
    runtime_spec_accessor_token: str = Field(min_length=1)
    module_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    execute_code_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bind_code_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    spec_accessor_code_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    node_spec_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bound_state_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dispatch_params_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class RunInvocationStarted(BaseModel):
    """Persist the exact engine input basis immediately before one node attempt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0", "1.1", "1.2", "1.3"] = "1.1"
    record_type: Literal["started"] = "started"
    run_id: str = Field(min_length=1)
    attempt_id: str = Field(
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    )
    attempt_number: int = Field(ge=1)
    workflow_spec_ref: ArtifactRef
    node_alias: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    component_id: str = Field(min_length=1)
    input_state_ref: ArtifactRef
    previous_record_ref: ArtifactRef | None
    implementation_identity: RunInvocationImplementationIdentity | None = None
    execution_budget_contract: Literal["admitted_workflow_budget_v1"] | None = None
    execution_deadline_at: datetime | None = None
    budget_middleware_active: bool | None = None
    budget_owner_identity: tuple[str, str, str] | None = None
    budget_start_revision: int | None = Field(default=None, ge=0)
    workflow_execution_admission_ref: ArtifactRef | None = None
    budget_resource_identity: tuple[int, int, str, int, int] | None = None
    budget_start_snapshot_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    invocation_settlement_profile: Literal["single_owner_local_v1"] | None = None
    started_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="before")
    @classmethod
    def _refuse_legacy_budget_fields(cls, value: Any) -> Any:
        if (
            isinstance(value, dict)
            and value.get("schema_version", "1.1") in {"1.0", "1.1", "1.2"}
            and any(
                key in value
                for key in (
                    "workflow_execution_admission_ref",
                    "budget_resource_identity",
                    "budget_start_snapshot_sha256",
                    "invocation_settlement_profile",
                )
            )
        ):
            raise ValueError("run_invocation_legacy_admission_fields_forbidden")
        if (
            isinstance(value, dict)
            and value.get("schema_version", "1.1") in {"1.0", "1.1"}
            and (
                "execution_budget_contract" in value
                or "execution_deadline_at" in value
                or "budget_middleware_active" in value
                or "budget_owner_identity" in value
                or "budget_start_revision" in value
            )
        ):
            raise ValueError("run_invocation_legacy_budget_fields_forbidden")
        return value

    @model_serializer(mode="wrap")
    def _serialize_versioned_budget(self, handler: Any) -> dict[str, Any]:
        payload = handler(self)
        if self.schema_version in {"1.0", "1.1", "1.2"}:
            payload.pop("workflow_execution_admission_ref", None)
            payload.pop("budget_resource_identity", None)
            payload.pop("budget_start_snapshot_sha256", None)
            payload.pop("invocation_settlement_profile", None)
        if self.schema_version in {"1.0", "1.1"}:
            payload.pop("execution_budget_contract", None)
            payload.pop("execution_deadline_at", None)
            payload.pop("budget_middleware_active", None)
            payload.pop("budget_owner_identity", None)
            payload.pop("budget_start_revision", None)
        if self.schema_version == "1.0" and "implementation_identity" not in self.model_fields_set:
            payload.pop("implementation_identity", None)
        return payload

    @model_validator(mode="after")
    def _validate_selected_input_profiles(self) -> RunInvocationStarted:
        """Bind a start record to full selected profiles and aware engine time."""
        if (
            self.workflow_spec_ref.manifest_profile_sha256 is None
            or self.input_state_ref.manifest_profile_sha256 is None
            or (
                self.previous_record_ref is not None
                and self.previous_record_ref.manifest_profile_sha256 is None
            )
        ):
            raise ValueError("run_invocation_start_selected_profile_missing")
        if self.started_at.tzinfo is None or self.started_at.utcoffset() is None:
            raise ValueError("run_invocation_start_time_not_aware")
        if self.schema_version in {"1.2", "1.3"} and self.execution_budget_contract is None:
            raise ValueError("run_invocation_budget_not_established")
        if self.schema_version in {"1.2", "1.3"} and self.budget_middleware_active is None:
            raise ValueError("run_invocation_budget_middleware_not_established")
        if self.budget_middleware_active is False and self.budget_owner_identity is not None:
            raise ValueError("run_invocation_unconfigured_budget_has_owner")
        if self.budget_middleware_active is False and self.budget_start_revision is not None:
            raise ValueError("run_invocation_unconfigured_budget_has_revision")
        if (self.budget_resource_identity is None) != (self.budget_start_snapshot_sha256 is None):
            raise ValueError("run_invocation_budget_resource_binding_incomplete")
        if self.budget_resource_identity is not None and (
            not self.budget_middleware_active
            or self.budget_owner_identity is None
            or self.budget_start_revision is None
            or self.invocation_settlement_profile != "single_owner_local_v1"
        ):
            raise ValueError("run_invocation_budget_resource_without_owner")
        if self.invocation_settlement_profile is not None and self.budget_resource_identity is None:
            raise ValueError("run_invocation_budget_profile_without_resource")
        if self.workflow_execution_admission_ref is not None and (
            self.workflow_execution_admission_ref.manifest_profile_sha256 is None
            or self.workflow_execution_admission_ref.kind
            != "scientist.workflow_execution_admission"
            or self.workflow_execution_admission_ref.media_type != "application/json"
        ):
            raise ValueError("run_invocation_execution_admission_ref_invalid")
        if self.execution_deadline_at is not None and (
            self.execution_deadline_at.tzinfo is None
            or self.execution_deadline_at.utcoffset() != timedelta(0)
        ):
            raise ValueError("run_invocation_deadline_must_be_utc")
        if self.schema_version == "1.0" and self.implementation_identity is not None:
            raise ValueError("run_invocation_v10_identity_not_supported")
        if (
            self.implementation_identity is not None
            and self.implementation_identity.component_id != self.component_id
        ):
            raise ValueError("run_invocation_implementation_component_mismatch")
        return self


class RunInvocationCompleted(BaseModel):
    """Bind engine-observed status and returned outputs, not external authority.

    Optional budget snapshot fields record a matching returned receipt and
    ledger observation. They do not independently establish the issuer or
    attribute an external charge to this attempt.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0", "1.1"] = "1.0"
    record_type: Literal["completed"] = "completed"
    run_id: str = Field(min_length=1)
    attempt_id: str = Field(
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    )
    attempt_number: int = Field(ge=1)
    basis_ref: ArtifactRef
    previous_record_ref: ArtifactRef
    status: Literal["ok", "fail", "skip", "unknown"]
    outcome_state_ref: ArtifactRef | None
    output_refs: list[ArtifactRef] = Field(default_factory=list)
    budget_owner_identity: tuple[str, str, str] | None = None
    budget_snapshot_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    budget_snapshot_revision: int | None = Field(default=None, ge=0)
    budget_snapshot_canon: Literal["polisyos.canon.json/0.2.0;forbid_floats=false"] | None = None
    budget_receipt_ref: ArtifactRef | None = None
    completed_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="before")
    @classmethod
    def _refuse_legacy_budget_fields(cls, value: Any) -> Any:
        if (
            isinstance(value, dict)
            and value.get("schema_version", "1.0") == "1.0"
            and any(
                key in value
                for key in (
                    "budget_owner_identity",
                    "budget_snapshot_sha256",
                    "budget_snapshot_revision",
                    "budget_snapshot_canon",
                    "budget_receipt_ref",
                )
            )
        ):
            raise ValueError("run_invocation_legacy_budget_fields_forbidden")
        return value

    @model_serializer(mode="wrap")
    def _serialize_versioned_budget(self, handler: Any) -> dict[str, Any]:
        payload = handler(self)
        if self.schema_version == "1.0":
            payload.pop("budget_owner_identity", None)
            payload.pop("budget_snapshot_sha256", None)
            payload.pop("budget_snapshot_revision", None)
            payload.pop("budget_snapshot_canon", None)
            payload.pop("budget_receipt_ref", None)
        return payload

    @model_validator(mode="after")
    def _validate_completion_binding(self) -> RunInvocationCompleted:
        """Require an aware completion time and consistent outcome references."""
        if (
            self.basis_ref.manifest_profile_sha256 is None
            or self.previous_record_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("run_invocation_completion_basis_invalid")
        if self.schema_version == "1.1" and (
            self.budget_owner_identity is None
            or self.budget_snapshot_sha256 is None
            or self.budget_snapshot_revision is None
            or self.budget_snapshot_canon is None
            or self.budget_receipt_ref is None
        ):
            raise ValueError("run_invocation_completion_budget_not_established")
        if self.budget_receipt_ref is not None and self.budget_receipt_ref not in self.output_refs:
            raise ValueError("run_invocation_completion_receipt_not_returned")
        if self.completed_at.tzinfo is None or self.completed_at.utcoffset() is None:
            raise ValueError("run_invocation_completion_time_not_aware")
        if (self.status == "unknown") != (self.outcome_state_ref is None):
            raise ValueError("run_invocation_completion_outcome_state_invalid")
        return self
