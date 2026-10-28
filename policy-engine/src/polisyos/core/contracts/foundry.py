"""Stable Foundry contracts for compile-time graphs, execution plans, and simulation outputs."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Any, ClassVar, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

from polisyos.core.artifacts.registry import RegistryBundlePayload
from polisyos.ir.kernel import MethodMetricSemanticContract, MethodMetricSourceUnit, UnitSpecType
from polisyos.ir.registry.refs import WelfareBundleRef

from ..artifacts.environment import EnvironmentManifestRef as EnvironmentManifestRef
from ..artifacts.manifest import ArtifactRef, InputRef
from .distributional import DistributionalReportRef
from .execution_plan import ExecutionPlanRef
from .scientist import FairnessAuditReportRef, MetricValidationReportRef
from .uncertainty import UncertaintyEnvelopeRef

_AttractorAnalysisMode = Literal["attractors", "continuation", "basin_map", "lyapunov"]

# Shared intake bound for method-metric binding inventories.
METHOD_METRIC_BINDING_LIMIT = 128


def _default_attractor_analysis_modes() -> list[_AttractorAnalysisMode]:
    return ["attractors"]


class FoundryExecutionInputBasisRef(ArtifactRef):
    """Selected CAS reference for the exact inputs passed to one Foundry step."""

    kind: Literal["foundry.execution_input_basis"] = "foundry.execution_input_basis"
    media_type: Literal["application/json"] = "application/json"


class ProgramGraphRef(ArtifactRef):
    """Artifact reference for the compiled program graph a Foundry run will execute."""

    kind: str = "foundry.program_graph"
    media_type: str = "application/json"


class LoweredIRRef(ArtifactRef):
    """Artifact reference for the lowered IR produced before execution planning."""

    kind: str = "foundry.lowered_ir"
    media_type: str = "application/json"


class ExecPlanRef(ArtifactRef):
    """Artifact reference for the resolved Foundry execution plan and runtime posture."""

    kind: str = "foundry.exec_plan"
    media_type: str = "application/json"


class StateSnapshotRef(ArtifactRef):
    """Artifact reference for a persisted state snapshot emitted by a simulation."""

    kind: str = "foundry.state_snapshot"
    media_type: str = "application/json"


class FoundryInputBindingsRef(ArtifactRef):
    """Artifact reference for the slot-binding bundle used to seed a Foundry execution."""

    kind: str = "foundry.input_bindings"
    media_type: str = "application/json"


class FoundryInputBindingReportRef(ArtifactRef):
    """Artifact reference for the report describing how external data was bound to slots."""

    kind: str = "foundry.input_binding_report"
    media_type: str = "application/json"


class FeedbackConfigRef(ArtifactRef):
    """Artifact reference for feedback fixed-point configuration."""

    kind: str = "foundry.feedback_config"
    media_type: str = "application/json"


class FeedbackTraceRef(ArtifactRef):
    """Artifact reference for the feedback iteration trace."""

    kind: str = "foundry.feedback_trace"
    media_type: str = "application/json"


class FeedbackJacobianDiagnosticsRef(ArtifactRef):
    """Artifact reference for Jacobian diagnostics around the solved fixed point."""

    kind: str = "foundry.feedback_jacobian_diagnostics"
    media_type: str = "application/json"


class FeedbackConvergenceCertificateRef(ArtifactRef):
    """Artifact reference for the feedback convergence certificate."""

    kind: str = "foundry.feedback_convergence_certificate"
    media_type: str = "application/json"


class FeedbackResultRef(ArtifactRef):
    """Artifact reference for the top-level feedback solve result."""

    kind: str = "foundry.feedback_result"
    media_type: str = "application/json"


class EquilibriumMultiplicityReportRef(ArtifactRef):
    """Artifact reference for a structured fixed-point multiplicity report."""

    kind: str = "foundry.equilibrium_multiplicity_report"
    media_type: str = "application/json"


class IdentifiabilityDiagnosticRef(ArtifactRef):
    """Artifact reference for aggregate-moment identifiability diagnostics."""

    kind: str = "foundry.identifiability_diagnostic"
    media_type: str = "application/json"


class AttractorAnalysisResultRef(ArtifactRef):
    """Artifact reference for a multi-attractor analysis summary."""

    kind: Literal["foundry.attractor_analysis_result"] = "foundry.attractor_analysis_result"
    media_type: Literal["application/json"] = "application/json"


class BasinMapRef(ArtifactRef):
    """Artifact reference for dense basin membership samples."""

    kind: Literal["foundry.basin_map"] = "foundry.basin_map"
    media_type: Literal["application/json"] = "application/json"


class ContinuationBranchRef(ArtifactRef):
    """Artifact reference for an equilibrium, cycle, or bifurcation continuation branch."""

    kind: Literal["foundry.continuation_branch"] = "foundry.continuation_branch"
    media_type: Literal["application/json"] = "application/json"


class PeriodicOrbitDiagnosticsRef(ArtifactRef):
    """Artifact reference for periodic-orbit diagnostics such as Floquet multipliers."""

    kind: str = "foundry.periodic_orbit_diagnostics"
    media_type: str = "application/json"


class TreasurySeedRef(ArtifactRef):
    """Artifact reference for deterministic random-stream seeds used during execution."""

    kind: str = "foundry.treasury_seed"
    media_type: str = "application/json"


class ExecConfigRef(ArtifactRef):
    """Artifact reference for the executor configuration applied to a simulation run."""

    kind: str = "foundry.exec_config"
    media_type: str = "application/json"


class MethodArtifactRef(ArtifactRef):
    """Method artifact ref data model."""

    kind: str = "foundry.method_artifact"
    media_type: str = "application/json"


class ChainArtifactRef(ArtifactRef):
    """Chain artifact ref data model."""

    kind: str = "foundry.chain_artifact"
    media_type: str = "application/json"


class ExecutionEvidenceRef(ArtifactRef):
    """Execution evidence ref data model."""

    kind: str = "foundry.execution_evidence"
    media_type: str = "application/json"


class MethodMetricBindingSetRef(ArtifactRef):
    """Selected CAS reference for compiled method-to-objective bindings."""

    kind: Literal["foundry.method_metric_binding_set"] = "foundry.method_metric_binding_set"
    media_type: Literal["application/json"] = "application/json"


class MethodExecutionBundleRef(ArtifactRef):
    """Selected CAS reference for actual graph invocation and output capture."""

    kind: Literal["foundry.method_execution_bundle"] = "foundry.method_execution_bundle"
    media_type: Literal["application/json"] = "application/json"


class MethodOutputRef(ArtifactRef):
    """Selected JSON output payload for one method invocation and declared slot."""

    kind: Literal["foundry.method_output"] = "foundry.method_output"
    media_type: Literal["application/json"] = "application/json"


class MethodMetricInputCaptureRef(ArtifactRef):
    """Selected CAS reference for law-required actual method input values."""

    kind: Literal["foundry.method_metric_input_capture"] = "foundry.method_metric_input_capture"
    media_type: Literal["application/json"] = "application/json"


class MethodArtifactOutputRef(ArtifactRef):
    """Selected JSON sidecar output from one method invocation."""

    kind: Literal["foundry.method_artifact_output"] = "foundry.method_artifact_output"
    media_type: Literal["application/json"] = "application/json"


class MethodMetricBindingRequest(BaseModel):
    """Explicit objective/node/slot selection for compile-time method metric binding."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    objective_id: StrictStr = Field(min_length=1)
    node_id: StrictStr = Field(min_length=1)
    output_slot_id: StrictStr = Field(min_length=1)


class MethodMetricBinding(BaseModel):
    """Exact selected objective, method ABI output, semantic contract, and unit law."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    binding_id: StrictStr = Field(min_length=1, max_length=256)
    objective_id: StrictStr = Field(min_length=1, max_length=256)
    metric_id: StrictStr = Field(min_length=1, max_length=256)
    node_id: StrictStr = Field(min_length=1, max_length=256)
    method_fqn: StrictStr = Field(min_length=1, max_length=512)
    method_version: StrictStr = Field(min_length=1, max_length=128)
    method_abi_digest: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    method_abi_digest_algorithm: Literal["blake2b"] = "blake2b"
    method_build_digest: StrictStr | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    method_build_digest_scope: Literal["class_source_only", "unavailable"] = "unavailable"
    output_slot_id: StrictStr = Field(min_length=1, max_length=256)
    output_value_path: tuple[StrictStr, ...] = Field(default_factory=tuple, max_length=16)
    output_contract_id: StrictStr | None = None
    output_shape: Literal["scalar", "non_scalar", "unknown"] = "unknown"
    semantics: MethodMetricSemanticContract | None = None
    source_unit: MethodMetricSourceUnit
    target_unit: UnitSpecType
    law_id: StrictStr
    law_version: StrictStr
    law_code_digest: StrictStr = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    adapter_id: StrictStr
    adapter_version: StrictStr
    adapter_code_digest: StrictStr = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    conversion_operation: Literal["identity", "ratio_to_percent", "percent_to_ratio", "unsupported"]
    conversion_factor_numerator: StrictInt | None = None
    conversion_factor_denominator: StrictInt | None = None
    availability: Literal["available", "unavailable"]
    limitation: StrictStr | None = None

    @model_validator(mode="after")
    def validate_binding(self) -> MethodMetricBinding:
        if (self.method_build_digest is None) != (
            self.method_build_digest_scope != "class_source_only"
        ):
            raise ValueError("method_metric_binding_build_identity_scope_mismatch")
        if any(not segment.strip() for segment in self.output_value_path):
            raise ValueError("method_metric_binding_output_value_path_must_be_non_empty")
        if (
            self.semantics is not None
            and self.output_value_path != self.semantics.output_value_path
        ):
            raise ValueError("method_metric_binding_output_path_differs_from_semantics")
        if self.availability == "available":
            if (
                self.semantics is None
                or self.output_shape != "scalar"
                or self.limitation is not None
                or self.conversion_operation == "unsupported"
                or self.conversion_factor_numerator is None
                or self.conversion_factor_denominator is None
                or self.conversion_factor_denominator <= 0
                or self.method_build_digest is None
            ):
                raise ValueError("available_method_metric_binding_requires_complete_law")
        elif not self.limitation:
            raise ValueError("unavailable_method_metric_binding_requires_limitation")
        return self


class MethodMetricBindingSet(BaseModel):
    """Compile-time binding set selected by an execution plan."""

    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.core.MethodMetricBindingSet"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"
    ARTIFACT_KIND: ClassVar[Literal["foundry.method_metric_binding_set"]] = (
        "foundry.method_metric_binding_set"
    )
    ARTIFACT_MEDIA_TYPE: ClassVar[Literal["application/json"]] = "application/json"

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    program_graph_ref: ProgramGraphRef
    policy_ref: ArtifactRef
    registry_bundle_ref: ArtifactRef
    metric_registry_ref: ArtifactRef
    units_registry_ref: ArtifactRef
    bindings: list[MethodMetricBinding] = Field(
        default_factory=list, max_length=METHOD_METRIC_BINDING_LIMIT
    )

    @model_validator(mode="after")
    def validate_unique_bindings(self) -> MethodMetricBindingSet:
        if len(self.bindings) > METHOD_METRIC_BINDING_LIMIT:
            raise ValueError("method_metric_binding_inventory_exceeds_capture_limit")
        ids = [item.binding_id for item in self.bindings]
        selections = [
            (item.objective_id, item.node_id, item.output_slot_id) for item in self.bindings
        ]
        output_selections = [(item.node_id, item.output_slot_id) for item in self.bindings]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate_method_metric_binding_id")
        if len(selections) != len(set(selections)):
            raise ValueError("duplicate_method_metric_binding_selection")
        if len(output_selections) != len(set(output_selections)):
            raise ValueError("duplicate_method_metric_selected_output_slot")
        return self


class MethodOutputPayload(BaseModel):
    """One actual finite numeric method slot output, captured without coercion."""

    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.core.MethodOutputPayload"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"
    ARTIFACT_KIND: ClassVar[Literal["foundry.method_output"]] = "foundry.method_output"
    ARTIFACT_MEDIA_TYPE: ClassVar[Literal["application/json"]] = "application/json"

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    occurrence_id: StrictStr = Field(min_length=1)
    invocation_id: StrictStr = Field(min_length=1)
    node_id: StrictStr = Field(min_length=1)
    slot_id: StrictStr = Field(min_length=1, max_length=256)
    value_path: tuple[StrictStr, ...] = Field(default_factory=tuple, max_length=16)
    value: StrictInt | StrictFloat

    @field_validator("value")
    @classmethod
    def finite_number(cls, value: float | int) -> float | int:
        import math

        if isinstance(value, bool) or (isinstance(value, float) and not math.isfinite(value)):
            raise ValueError("method_output_requires_finite_numeric_scalar")
        return value


class MethodMetricInputCaptureSlot(BaseModel):
    """Metadata for one law-required slot stored in its selected state snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    slot_id: StrictStr = Field(min_length=1)
    dtype: StrictStr = Field(min_length=1)
    shape: tuple[StrictInt, ...] = Field(min_length=1, max_length=1)
    value_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    unit: MethodMetricSourceUnit

    @model_validator(mode="after")
    def validate_capture_layout(self) -> MethodMetricInputCaptureSlot:
        if self.shape[0] <= 0:
            raise ValueError("method_metric_input_capture_requires_nonempty_vector")
        if self.dtype.lstrip("<>=|")[:1] not in {"i", "u", "f"}:
            raise ValueError("method_metric_input_capture_requires_numeric_dtype")
        return self


class MethodMetricInputCapturePayload(BaseModel):
    """One bounded metadata record over the actual sparse pre-dispatch state."""

    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.core.MethodMetricInputCapture"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.1"
    ARTIFACT_KIND: ClassVar[Literal["foundry.method_metric_input_capture"]] = (
        "foundry.method_metric_input_capture"
    )
    ARTIFACT_MEDIA_TYPE: ClassVar[Literal["application/json"]] = "application/json"

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.1"] = "1.1"
    retention_purpose: Literal["registered_metric_recomputation_only"] = (
        "registered_metric_recomputation_only"
    )
    program_graph_ref: ProgramGraphRef
    exec_plan_ref: ExecPlanRef
    method_metric_binding_set_ref: MethodMetricBindingSetRef
    occurrence_id: StrictStr = Field(min_length=1)
    invocation_id: StrictStr = Field(min_length=1)
    node_id: StrictStr = Field(min_length=1)
    prestate_identity_algorithm: Literal["policyos.method_dispatch_input_map.sha256.v1"]
    prestate_identity_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    pre_dispatch_state_ref: StateSnapshotRef
    slots: tuple[MethodMetricInputCaptureSlot, ...] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_capture(self) -> MethodMetricInputCapturePayload:
        slot_ids = [item.slot_id for item in self.slots]
        if len(slot_ids) != len(set(slot_ids)):
            raise ValueError("duplicate_method_metric_input_capture_slot")
        if any(len(item.slot_id) > 256 for item in self.slots):
            raise ValueError("method_metric_input_capture_slot_id_exceeds_length_limit")
        refs = (
            self.program_graph_ref,
            self.exec_plan_ref,
            self.method_metric_binding_set_ref,
            self.pre_dispatch_state_ref,
        )
        if any(ref.manifest_profile_sha256 is None for ref in refs):
            raise ValueError("method_metric_input_capture_requires_selected_profile_lineage")
        return self


class MethodArtifactOutputPayload(BaseModel):
    """JSON-compatible sidecar payload emitted in ``MethodResult.artifacts``."""

    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.core.MethodArtifactOutputPayload"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"
    ARTIFACT_KIND: ClassVar[Literal["foundry.method_artifact_output"]] = (
        "foundry.method_artifact_output"
    )
    ARTIFACT_MEDIA_TYPE: ClassVar[Literal["application/json"]] = "application/json"

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    occurrence_id: StrictStr = Field(min_length=1)
    invocation_id: StrictStr = Field(min_length=1)
    node_id: StrictStr = Field(min_length=1)
    artifact_key: StrictStr = Field(min_length=1)
    payload: dict[str, Any]


class MethodExecutionOutputSlot(BaseModel):
    """Status and optional selected output ref for one declared method slot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    slot_id: StrictStr = Field(min_length=1, max_length=256)
    status: Literal["captured", "unavailable", "not_emitted"]
    output_ref: MethodOutputRef | None = None
    limitation: StrictStr | None = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def validate_output_slot(self) -> MethodExecutionOutputSlot:
        if self.status == "captured":
            if self.output_ref is None or self.limitation is not None:
                raise ValueError("captured_method_output_requires_ref")
        elif self.output_ref is not None or not self.limitation:
            raise ValueError("uncaptured_method_output_requires_limitation_without_ref")
        return self


class MethodExecutionParameterValue(BaseModel):
    """One resolved method parameter, its source, and exact JSON capture state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: StrictStr = Field(min_length=1, max_length=256)
    source: Literal[
        "requested",
        "signature_default",
        "signature_default_unresolved",
        "requested_unresolved",
    ]
    status: Literal["captured", "unsupported_codec"]
    value: Any = None
    value_sha256: StrictStr | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    limitation: StrictStr | None = None

    @model_validator(mode="after")
    def validate_parameter_capture(self) -> MethodExecutionParameterValue:
        if self.status == "captured":
            if (
                self.value_sha256 is None
                or self.limitation is not None
                or self.source in {"requested_unresolved", "signature_default_unresolved"}
            ):
                raise ValueError("captured_method_parameter_requires_digest")
        elif self.value_sha256 is not None or not self.limitation:
            raise ValueError("unsupported_method_parameter_requires_limitation")
        return self


class MethodExecutionBackendAttempt(BaseModel):
    """One exact dispatcher backend attempt copied from its emitted dispatch trace."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    backend: StrictStr = Field(min_length=1, max_length=128)
    outcome: StrictStr = Field(min_length=1, max_length=128)


class MethodExecutionInputSlot(BaseModel):
    """Bounded content identity for a directly addressable method input slot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    slot_id: StrictStr = Field(min_length=1, max_length=256)
    status: Literal["captured", "not_established"]
    value_sha256: StrictStr | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    runtime_type: StrictStr | None = None
    runtime_shape: tuple[StrictInt, ...] | None = None
    runtime_dtype: StrictStr | None = None
    limitation: StrictStr | None = None

    @model_validator(mode="after")
    def validate_input_identity(self) -> MethodExecutionInputSlot:
        if self.status == "captured":
            if self.value_sha256 is None or self.limitation is not None:
                raise ValueError("captured_method_input_slot_requires_digest")
        elif self.value_sha256 is not None or not self.limitation:
            raise ValueError("unestablished_method_input_slot_requires_limitation")
        return self


class MethodExecutionInputRole(BaseModel):
    """Captured semantic role to actual method ABI input-slot mapping."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role_id: StrictStr = Field(min_length=1, max_length=128)
    slot_id: StrictStr = Field(min_length=1, max_length=256)
    value_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")


class MethodExecutionDispatchRecord(BaseModel):
    """Whole invocation record at the graph-to-method dispatch boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome: Literal["not_run", "succeeded", "failed"]
    started_at: datetime | None = None
    completed_at: datetime | None = None
    dispatch_elapsed_ms: StrictFloat | None = Field(default=None, ge=0)
    runner_wall_time_ms: StrictFloat | None = Field(default=None, ge=0)
    runner_cpu_time_ms: StrictFloat | None = Field(default=None, ge=0)
    runner_compile_time_ms: StrictFloat | None = Field(default=None, ge=0)
    input_state_ref: StateSnapshotRef | None = None
    input_state_relation: Literal["current_visible_state", "origin_only", "not_established"] = (
        "not_established"
    )
    input_state_identity_algorithm: (
        Literal["policyos.method_dispatch_input_map.sha256.v1"] | None
    ) = None
    input_state_identity_sha256: StrictStr | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    input_state_source_ref: StateSnapshotRef | None = None
    method_metric_input_capture_ref: MethodMetricInputCaptureRef | None = None
    method_metric_input_capture_status: Literal[
        "captured", "not_established", "not_required", "not_started"
    ] = "not_required"
    method_metric_input_capture_limitation: StrictStr | None = None
    input_state_status: Literal["captured", "not_established", "not_started"]
    input_state_limitation: StrictStr | None = Field(default=None, max_length=512)
    graph_input_ids: tuple[StrictStr, ...] = Field(default_factory=tuple, max_length=32)
    signature_input_slot_ids: tuple[StrictStr, ...] = Field(default_factory=tuple, max_length=32)
    signature_output_slot_ids: tuple[StrictStr, ...] = Field(default_factory=tuple, max_length=128)
    signature_parameter_names: tuple[StrictStr, ...] = Field(default_factory=tuple, max_length=32)
    signature_input_inventory_observed_count: StrictInt | None = Field(default=None, ge=0)
    signature_input_inventory_limit: StrictInt | None = Field(default=None, ge=1)
    signature_output_inventory_observed_count: StrictInt | None = Field(default=None, ge=0)
    signature_output_inventory_limit: StrictInt | None = Field(default=None, ge=1)
    signature_parameter_inventory_observed_count: StrictInt | None = Field(default=None, ge=0)
    signature_parameter_inventory_limit: StrictInt | None = Field(default=None, ge=1)
    input_slot_values: tuple[MethodExecutionInputSlot, ...] = Field(
        default_factory=tuple, max_length=32
    )
    input_role_values: tuple[MethodExecutionInputRole, ...] = Field(
        default_factory=tuple, max_length=32
    )
    parameter_values: tuple[MethodExecutionParameterValue, ...] = Field(
        default_factory=tuple, max_length=32
    )
    parameter_resolution_status: Literal["captured", "not_established", "not_started"]
    parameter_resolution_limitation: StrictStr | None = Field(default=None, max_length=512)
    parameter_inventory_observed_count: StrictInt | None = Field(default=None, ge=0)
    parameter_inventory_limit: StrictInt | None = Field(default=None, ge=1)
    graph_input_inventory_observed_count: StrictInt | None = Field(default=None, ge=0)
    graph_input_inventory_limit: StrictInt | None = Field(default=None, ge=1)
    root_seed: StrictInt | None = None
    step: StrictInt | None = None
    method_key_words: tuple[StrictInt, ...] = ()
    method_seed: StrictInt | None = None
    reproducibility_seed: StrictInt | None = None
    seed_status: Literal["reconciled", "mismatch", "not_established", "not_started"]
    rng_state_status: Literal["key_captured", "runner_rng_state_not_retained", "not_started"]
    requested_backend: StrictStr | None = None
    selected_backend: StrictStr | None = None
    actual_backend: StrictStr | None = None
    backend_selection_reason: StrictStr | None = None
    backend_identity_status: Literal["reconciled", "mismatch", "not_established", "not_started"]
    backend_attempts: tuple[MethodExecutionBackendAttempt, ...] = ()
    backend_trace_status: Literal["captured", "not_established", "not_started"]
    fallback_status: Literal["fell_back", "not_fell_back", "not_established", "not_started"]
    failure_type: StrictStr | None = Field(default=None, max_length=512)
    failure_message_sha256: StrictStr | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    limitations: tuple[StrictStr, ...] = Field(default_factory=tuple, max_length=32)

    @field_validator("limitations")
    @classmethod
    def validate_dispatch_limitation_lengths(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(len(value) > 512 for value in values):
            raise ValueError("method_execution_dispatch_limitation_exceeds_length_limit")
        return values

    @model_validator(mode="after")
    def validate_dispatch_record(self) -> MethodExecutionDispatchRecord:
        if self.input_state_status == "captured":
            if (
                self.input_state_identity_sha256 is None
                or self.input_state_identity_algorithm
                != "policyos.method_dispatch_input_map.sha256.v1"
                or self.input_state_ref is None
                or self.input_state_relation != "current_visible_state"
                or self.input_state_limitation is not None
            ):
                raise ValueError("captured_method_prestate_requires_selected_content_identity")
        elif (
            self.input_state_identity_sha256 is not None
            or self.input_state_identity_algorithm is not None
        ):
            raise ValueError("unestablished_method_prestate_cannot_have_content_identity")
        if (
            self.input_state_status != "captured"
            and self.input_state_relation == "current_visible_state"
        ):
            raise ValueError("unselected_method_prestate_cannot_claim_current_visible_state")
        if self.input_state_ref is not None and self.input_state_status != "captured":
            raise ValueError("unestablished_method_prestate_cannot_have_selected_ref")
        elif self.input_state_status == "not_established" and not self.input_state_limitation:
            raise ValueError("unestablished_method_prestate_requires_limitation")
        if self.method_metric_input_capture_status == "captured":
            if (
                self.method_metric_input_capture_ref is None
                or self.method_metric_input_capture_limitation is not None
            ):
                raise ValueError("captured_method_metric_input_requires_selected_ref")
        elif self.method_metric_input_capture_ref is not None:
            raise ValueError("uncaptured_method_metric_input_cannot_have_selected_ref")
        elif self.method_metric_input_capture_status == "not_established":
            if not self.method_metric_input_capture_limitation:
                raise ValueError("unestablished_method_metric_input_requires_limitation")
        elif self.method_metric_input_capture_limitation is not None:
            raise ValueError("method_metric_input_limitation_without_unestablished_status")
        if self.outcome == "not_run":
            if self.method_metric_input_capture_status not in {
                "not_started",
                "not_required",
            }:
                raise ValueError("not_run_method_metric_input_capture_has_runtime_status")
        elif self.method_metric_input_capture_status == "not_started":
            raise ValueError("dispatched_method_metric_input_capture_cannot_be_not_started")
        if self.parameter_resolution_status == "not_established":
            if not self.parameter_resolution_limitation:
                raise ValueError("unestablished_method_parameters_require_limitation")
            if (
                self.parameter_inventory_observed_count is not None
                and self.parameter_inventory_limit is None
            ):
                raise ValueError("bounded_parameter_inventory_requires_limit")
        elif self.parameter_resolution_status == "captured":
            if self.parameter_resolution_limitation is not None:
                raise ValueError("captured_method_parameters_cannot_have_limitation")
            if self.parameter_inventory_observed_count != len(self.parameter_values):
                raise ValueError("captured_method_parameter_inventory_count_mismatch")
            if any(
                value.status != "captured"
                or value.source in {"requested_unresolved", "signature_default_unresolved"}
                for value in self.parameter_values
            ):
                raise ValueError("captured_method_parameters_require_captured_values")
        input_slot_ids = [item.slot_id for item in self.input_slot_values]
        role_ids = [item.role_id for item in self.input_role_values]
        role_slot_ids = [item.slot_id for item in self.input_role_values]
        parameter_names = [item.name for item in self.parameter_values]
        if len(set(self.signature_input_slot_ids)) != len(self.signature_input_slot_ids):
            raise ValueError("duplicate_method_execution_signature_input_slot")
        if len(set(self.signature_parameter_names)) != len(self.signature_parameter_names):
            raise ValueError("duplicate_method_execution_signature_parameter")
        if len(set(parameter_names)) != len(parameter_names):
            raise ValueError("duplicate_method_execution_parameter_value")
        if len(input_slot_ids) != len(set(input_slot_ids)):
            raise ValueError("duplicate_method_execution_input_slot_identity")
        if len(set(self.signature_output_slot_ids)) != len(self.signature_output_slot_ids):
            raise ValueError("duplicate_method_execution_signature_output_slot")
        if len(role_ids) != len(set(role_ids)) or len(role_slot_ids) != len(set(role_slot_ids)):
            raise ValueError("duplicate_method_execution_input_role_mapping")
        if not set(input_slot_ids).issubset(set(self.signature_input_slot_ids)):
            raise ValueError("method_execution_input_identity_not_in_signature")
        if any(slot_id not in set(self.signature_input_slot_ids) for slot_id in role_slot_ids):
            raise ValueError("method_execution_input_role_slot_not_in_signature")
        input_digests = {item.slot_id: item.value_sha256 for item in self.input_slot_values}
        if any(
            input_digests.get(item.slot_id) != item.value_sha256 for item in self.input_role_values
        ):
            raise ValueError("method_execution_input_role_digest_mismatch")
        if self.parameter_resolution_status == "captured" and set(parameter_names) != set(
            self.signature_parameter_names
        ):
            raise ValueError("captured_method_parameters_must_cover_signature")
        if self.outcome != "not_run" and set(input_slot_ids) != set(self.signature_input_slot_ids):
            raise ValueError("dispatched_method_input_inventory_must_cover_signature")
        if self.outcome == "not_run":
            if self.started_at is not None or self.completed_at is not None:
                raise ValueError("not_run_method_dispatch_cannot_have_timestamps")
        else:
            if self.started_at is None or self.completed_at is None:
                raise ValueError("started_method_dispatch_requires_timestamps")
            if self.completed_at < self.started_at:
                raise ValueError("method_dispatch_end_precedes_start")
        if self.outcome == "succeeded" and self.failure_type is not None:
            raise ValueError("successful_method_dispatch_cannot_have_failure")
        if self.outcome == "failed" and self.failure_type is None:
            raise ValueError("failed_method_dispatch_requires_failure_type")
        if self.backend_trace_status == "captured" and (
            self.requested_backend is None
            or self.selected_backend is None
            or not self.backend_attempts
        ):
            raise ValueError("captured_method_backend_trace_requires_selection_and_attempts")
        if self.seed_status == "reconciled" and (
            self.method_seed is None or self.reproducibility_seed != self.method_seed
        ):
            raise ValueError("reconciled_method_seed_requires_matching_runner_seed")
        if self.backend_trace_status == "not_started" and self.fallback_status != "not_started":
            raise ValueError("not_started_method_backend_trace_requires_not_started_fallback")
        return self


class MethodExecutionReturnedSlot(BaseModel):
    """Bounded inventory row for every declared or emitted method output slot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    slot_id: StrictStr = Field(min_length=1, max_length=256)
    declared_by_signature: bool
    declared_slot_type: StrictStr | None = Field(default=None, max_length=128)
    declared_shape: tuple[StrictStr, ...] | None = Field(default=None, max_length=4)
    returned: Literal["returned", "not_returned", "not_established"]
    runtime_type: StrictStr | None = Field(default=None, max_length=512)
    runtime_key_type: StrictStr | None = Field(default=None, max_length=512)
    runtime_shape: tuple[StrictInt, ...] | None = None
    runtime_shape_status: Literal["captured", "not_established", "not_returned"]
    runtime_dtype: StrictStr | None = Field(default=None, max_length=128)
    codec_status: Literal[
        "json_scalar_supported", "unsupported_codec", "not_attempted", "not_returned"
    ]
    retention_status: Literal[
        "selected_metric_output", "not_retained", "unsupported_codec", "not_emitted"
    ]
    limitation: StrictStr | None = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def validate_returned_slot(self) -> MethodExecutionReturnedSlot:
        if self.returned == "returned":
            if self.runtime_type is None or self.runtime_shape_status == "not_returned":
                raise ValueError("returned_method_slot_requires_runtime_identity")
            if self.retention_status == "not_emitted":
                raise ValueError("returned_method_slot_cannot_be_not_emitted")
        elif self.returned == "not_returned":
            if (
                self.runtime_type is not None
                or self.runtime_shape is not None
                or self.runtime_dtype is not None
                or self.runtime_shape_status != "not_returned"
                or self.codec_status != "not_returned"
                or self.retention_status != "not_emitted"
            ):
                raise ValueError("unreturned_method_slot_cannot_have_runtime_inventory")
        elif self.runtime_shape_status == "not_returned" or self.codec_status == "not_returned":
            raise ValueError("unestablished_method_slot_requires_unknown_capture_state")
        if self.retention_status in {
            "not_retained",
            "unsupported_codec",
            "not_emitted",
        }:
            if not self.limitation:
                raise ValueError("uncaptured_returned_slot_requires_limitation")
        elif self.limitation is not None:
            raise ValueError("retained_selected_slot_cannot_have_limitation")
        if (
            self.retention_status == "unsupported_codec"
            and self.codec_status != "unsupported_codec"
        ):
            raise ValueError("unsupported_method_slot_retention_requires_codec_failure")
        return self


class MethodExecutionArtifact(BaseModel):
    """Status and optional selected ref for one MethodResult artifact entry."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_key: StrictStr = Field(min_length=1, max_length=256)
    status: Literal["captured", "unavailable"]
    artifact_ref: MethodArtifactOutputRef | None = None
    limitation: StrictStr | None = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def validate_artifact(self) -> MethodExecutionArtifact:
        if self.status == "captured":
            if self.artifact_ref is None or self.limitation is not None:
                raise ValueError("captured_method_artifact_requires_ref")
        elif self.artifact_ref is not None or not self.limitation:
            raise ValueError("uncaptured_method_artifact_requires_limitation_without_ref")
        return self


class RestrictedMethodCallWitness(BaseModel):
    """Bounded actual-call evidence nested in its existing graph occurrence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["verified", "unavailable"]
    limitation: StrictStr | None = Field(default=None, max_length=512)
    profile_id: StrictStr = Field(min_length=1, max_length=128)
    profile_revision_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    method_fqn: StrictStr = Field(min_length=1, max_length=512)
    method_version: StrictStr | None = Field(default=None, max_length=128)
    method_abi_digest: StrictStr | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    method_callable_sha256: StrictStr | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    runner_callable_sha256: StrictStr | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    backend_runtime_fingerprint: StrictStr | None = None
    state_reads: tuple[StrictStr, ...] = Field(default=(), max_length=32)
    parameter_reads: tuple[StrictStr, ...] = Field(default=(), max_length=32)
    parameter_origin: Literal["signature_default", "explicit_parameter", "not_established"]
    poverty_line_value: None = None
    output_slot_id: StrictStr = Field(min_length=1, max_length=256)
    output_value_path: tuple[StrictStr, ...] = Field(min_length=1, max_length=16)
    output_value_sha256: StrictStr | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    occurrence_id: StrictStr = Field(min_length=1, max_length=512)
    invocation_id: StrictStr = Field(min_length=1, max_length=64)
    node_id: StrictStr = Field(min_length=1, max_length=256)
    input_capture_ref: MethodMetricInputCaptureRef | None = None

    @model_validator(mode="after")
    def validate_witness(self) -> RestrictedMethodCallWitness:
        if self.status == "verified":
            if (
                self.limitation is not None
                or self.method_version is None
                or self.method_abi_digest is None
                or self.method_callable_sha256 is None
                or self.runner_callable_sha256 is None
                or self.backend_runtime_fingerprint is None
                or self.state_reads != ("baseline", "scenario")
                or self.parameter_reads != ("poverty_line",)
                or self.parameter_origin not in {"signature_default", "explicit_parameter"}
                or self.input_capture_ref is None
                or self.output_value_sha256 is None
            ):
                raise ValueError("verified_restricted_call_witness_is_incomplete")
        elif not self.limitation:
            raise ValueError("unavailable_restricted_call_witness_requires_limitation")
        return self


class MethodExecutionOccurrence(BaseModel):
    """One planned or actual node occurrence in one graph invocation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    occurrence_id: StrictStr = Field(min_length=1, max_length=512)
    invocation_id: StrictStr = Field(min_length=1, max_length=64)
    plan_index: StrictInt = Field(ge=0)
    node_id: StrictStr = Field(min_length=1, max_length=256)
    node_kind: Literal["method", "mechanism", "op", "unknown"]
    status: Literal["planned", "succeeded", "failed", "skipped"]
    method_fqn: StrictStr | None = Field(default=None, max_length=512)
    method_version: StrictStr | None = Field(default=None, max_length=128)
    method_abi_digest: StrictStr | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    method_abi_digest_algorithm: Literal["blake2b"] | None = None
    method_build_digest: StrictStr | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    method_build_digest_scope: Literal["class_source_only", "unavailable"] | None = None
    output_slots: list[MethodExecutionOutputSlot] = Field(default_factory=list, max_length=128)
    returned_slots: list[MethodExecutionReturnedSlot] = Field(default_factory=list, max_length=128)
    returned_slot_inventory_status: Literal["captured", "not_established", "not_started"] = (
        "not_started"
    )
    returned_slot_inventory_limitation: StrictStr | None = Field(default=None, max_length=512)
    returned_slot_inventory_observed_count: StrictInt | None = Field(default=None, ge=0)
    returned_slot_inventory_limit: StrictInt | None = Field(default=None, ge=1)
    artifact_inventory_status: Literal["captured", "not_established", "not_started"] = "not_started"
    artifact_inventory_limitation: StrictStr | None = None
    artifact_inventory_observed_count: StrictInt | None = Field(default=None, ge=0)
    artifact_inventory_limit: StrictInt | None = Field(default=None, ge=1)
    dispatch: MethodExecutionDispatchRecord | None = None
    restricted_call_witness: RestrictedMethodCallWitness | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    artifacts: list[MethodExecutionArtifact] = Field(default_factory=list, max_length=32)
    limitations: tuple[StrictStr, ...] = Field(default_factory=tuple, max_length=32)

    @field_validator("limitations")
    @classmethod
    def validate_limitation_lengths(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(len(value) > 512 for value in values):
            raise ValueError("method_execution_limitation_exceeds_length_limit")
        return values

    @model_validator(mode="after")
    def validate_occurrence(self) -> MethodExecutionOccurrence:
        expected = f"{self.invocation_id}:{self.plan_index}:{self.node_id}"
        if self.occurrence_id != expected:
            raise ValueError("method_execution_occurrence_id_mismatch")
        if self.node_kind == "method":
            if self.method_fqn is None:
                raise ValueError("method_occurrence_requires_method_fqn")
            if self.dispatch is None:
                raise ValueError("method_occurrence_requires_dispatch_record")
            witness = self.restricted_call_witness
            if witness is not None and (
                witness.occurrence_id != self.occurrence_id
                or witness.invocation_id != self.invocation_id
                or witness.node_id != self.node_id
                or witness.method_fqn != self.method_fqn
                or witness.method_version != self.method_version
                or witness.method_abi_digest != self.method_abi_digest
                or witness.input_capture_ref != self.dispatch.method_metric_input_capture_ref
            ):
                raise ValueError("restricted_call_witness_occurrence_binding_mismatch")
            if (
                witness is not None
                and witness.status == "verified"
                and (
                    self.status != "succeeded"
                    or self.dispatch.method_metric_input_capture_status != "captured"
                )
            ):
                raise ValueError("verified_call_witness_requires_succeeded_bound_input_capture")
            if (
                self.returned_slot_inventory_status == "not_established"
                and not self.returned_slot_inventory_limitation
            ):
                raise ValueError("unestablished_method_slot_inventory_requires_limitation")
            if self.returned_slot_inventory_status == "captured" and (
                self.returned_slot_inventory_limitation is not None
                or self.returned_slot_inventory_observed_count != len(self.returned_slots)
            ):
                raise ValueError("captured_method_slot_inventory_cannot_have_limitation")
            if (
                self.returned_slot_inventory_status == "not_established"
                and self.returned_slot_inventory_observed_count is not None
                and self.returned_slot_inventory_limit is None
            ):
                raise ValueError("bounded_returned_slot_inventory_requires_limit")
            if self.artifact_inventory_status == "not_established":
                if not self.artifact_inventory_limitation:
                    raise ValueError("unestablished_method_artifact_inventory_requires_limitation")
                if (
                    self.artifact_inventory_observed_count is not None
                    and self.artifact_inventory_limit is None
                ):
                    raise ValueError("bounded_method_artifact_inventory_requires_limit")
            elif self.artifact_inventory_status == "captured":
                if (
                    self.artifact_inventory_limitation is not None
                    or self.artifact_inventory_observed_count != len(self.artifacts)
                ):
                    raise ValueError("captured_method_artifact_inventory_count_mismatch")
            if (self.method_abi_digest is None) != (self.method_abi_digest_algorithm is None):
                raise ValueError("method_occurrence_abi_identity_requires_algorithm")
            if (self.method_build_digest is None) != (
                self.method_build_digest_scope != "class_source_only"
            ):
                raise ValueError("method_occurrence_build_identity_scope_mismatch")
        elif (
            self.output_slots
            or self.returned_slots
            or self.returned_slot_inventory_status != "not_started"
            or self.returned_slot_inventory_limitation is not None
            or self.returned_slot_inventory_observed_count is not None
            or self.returned_slot_inventory_limit is not None
            or self.dispatch is not None
            or self.restricted_call_witness is not None
            or self.artifacts
            or self.artifact_inventory_status != "not_started"
            or self.artifact_inventory_limitation is not None
            or self.artifact_inventory_observed_count is not None
            or self.artifact_inventory_limit is not None
        ):
            raise ValueError("non_method_occurrence_cannot_have_method_outputs")
        slot_ids = [item.slot_id for item in self.output_slots]
        returned_slot_ids = [item.slot_id for item in self.returned_slots]
        artifact_keys = [item.artifact_key for item in self.artifacts]
        if len(slot_ids) != len(set(slot_ids)):
            raise ValueError("duplicate_method_execution_output_slot")
        if len(returned_slot_ids) != len(set(returned_slot_ids)):
            raise ValueError("duplicate_method_execution_returned_slot")
        if len(artifact_keys) != len(set(artifact_keys)):
            raise ValueError("duplicate_method_execution_artifact_key")
        return self


class MethodExecutionBundle(BaseModel):
    """Selected actual execution capture with complete occurrence inventory."""

    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.core.MethodExecutionBundle"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.2"
    ARTIFACT_SCHEMA_VERSIONS: ClassVar[tuple[str, ...]] = ("1.1", "1.2")
    ARTIFACT_PAYLOAD_SCHEMA_VERSION_BY_MANIFEST: ClassVar[dict[str, str]] = {
        "1.1": "1.1",
        "1.2": "1.2",
    }
    ARTIFACT_KIND: ClassVar[Literal["foundry.method_execution_bundle"]] = (
        "foundry.method_execution_bundle"
    )
    ARTIFACT_MEDIA_TYPE: ClassVar[Literal["application/json"]] = "application/json"

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.1", "1.2"] = "1.1"
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    program_graph_ref: ProgramGraphRef
    exec_plan_ref: ExecPlanRef
    method_metric_binding_set_ref: MethodMetricBindingSetRef
    environment_manifest_ref: EnvironmentManifestRef | None = None
    occurrences: list[MethodExecutionOccurrence] = Field(default_factory=list, max_length=128)
    limitations: tuple[StrictStr, ...] = Field(default_factory=tuple, max_length=32)

    @field_validator("limitations")
    @classmethod
    def validate_bundle_limitation_lengths(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(len(value) > 512 for value in values):
            raise ValueError("method_execution_bundle_limitation_exceeds_length_limit")
        return values

    @model_validator(mode="after")
    def validate_occurrences(self) -> MethodExecutionBundle:
        ids = [item.occurrence_id for item in self.occurrences]
        positions = [(item.invocation_id, item.plan_index) for item in self.occurrences]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate_method_execution_occurrence_id")
        if len(positions) != len(set(positions)):
            raise ValueError("duplicate_method_execution_plan_position")
        if self.schema_version == "1.1" and any(
            item.restricted_call_witness is not None for item in self.occurrences
        ):
            raise ValueError("legacy_method_execution_bundle_cannot_claim_call_witness")
        if self.schema_version == "1.2" and any(
            item.status == "succeeded"
            and item.method_fqn == "policy.evaluation.ex_ante_simulation@1.0.0"
            and item.restricted_call_witness is None
            for item in self.occurrences
        ):
            raise ValueError("succeeded_exante_occurrence_requires_call_witness_or_refusal")
        return self


class AgentPolicyRef(ArtifactRef):
    """
    Typed reference to an AgentPolicyArtifact in CAS.

    Used in simulation configs to reference trained policies without
    embedding full weights in configuration files.
    """

    kind: str = "foundry.agent_policy"
    media_type: str = "application/octet-stream"

    policy_type: str = Field(description="ActorCritic, MLP, etc.")
    determinism_tier: str = Field(description="strict_cpu, best_effort_gpu, nondeterministic")
    training_steps: int = Field(ge=0, description="Steps when artifact was created")
    env_hash: str = Field(description="16-char environment fingerprint hash")


class StateDeltaRef(ArtifactRef):
    """Artifact reference for the patch set that transforms one state snapshot into the next."""

    kind: str = "foundry.state_delta"
    media_type: str = "application/json"


class MetricsRef(ArtifactRef):
    """Artifact reference for the scalar metrics emitted by a Foundry execution."""

    kind: str = "foundry.metrics"
    media_type: str = "application/json"


class MetricObservationBundleRef(ArtifactRef):
    """Artifact reference for per-example observations required for formal metric validation."""

    kind: str = "foundry.metric_observation_bundle"
    media_type: str = "application/json"


class ConstraintReportRef(ArtifactRef):
    """Constraint report ref data model."""

    kind: str = "foundry.constraint_report"
    media_type: str = "application/json"


class CalibrationReportRef(ArtifactRef):
    """Artifact reference for calibration diagnostics emitted alongside simulation outputs."""

    kind: str = "foundry.calibration_report"
    media_type: str = "application/json"


class ParameterOverrideBundleRef(ArtifactRef):
    """Artifact reference for parameter overrides layered onto a baseline execution config."""

    kind: str = "foundry.parameter_override_bundle"
    media_type: str = "application/json"


class ObservedRangeBundleRef(ArtifactRef):
    """Artifact reference for calibrated numeric envelopes used by decision-sidecar reports."""

    kind: str = "foundry.observed_range_bundle"
    media_type: str = "application/json"


class TraceSliceRef(ArtifactRef):
    """Artifact reference for the structured execution trace slice captured during a run."""

    kind: str = "foundry.trace_slice"
    media_type: str = "application/jsonl"


class SimulationResultRef(ArtifactRef):
    """Artifact reference for the top-level simulation result bundle returned by Foundry."""

    kind: str = "foundry.simulation_result"
    media_type: str = "application/json"


class WelfareBoundReportRef(ArtifactRef):
    """Artifact reference for a mechanism-level welfare-loss certificate."""

    kind: str = "foundry.welfare_bound_report"
    media_type: str = "application/json"


class ProgramNode(BaseModel):
    """One executable node in a program graph, representing a mechanism, op, or method call."""

    model_config = ConfigDict(extra="forbid")

    node_id: str
    node_kind: Literal["mechanism", "op", "method"] = "mechanism"
    mechanism_type: str | None = None
    method_fqn: str | None = None
    method_version: str | None = None
    method_params: dict[str, Any] = Field(default_factory=dict)
    params_ref: ArtifactRef | None = None
    op: ProgramOp | None = None
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_kind(self) -> ProgramNode:
        if self.node_kind == "mechanism" and not self.mechanism_type:
            raise ValueError("mechanism node requires mechanism_type")
        if self.node_kind == "op" and self.op is None:
            raise ValueError("op node requires op")
        if self.node_kind == "method" and not self.method_fqn:
            raise ValueError("method node requires method_fqn")
        return self


class ProgramOp(BaseModel):
    """Program op public type."""

    model_config = ConfigDict(extra="forbid")

    op_kind: Literal[
        "merge_state",
        "check_constraints",
        "read_view",
        "make_mask",
        "apply_mechanism",
        "apply_method",
    ]
    params: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


ProgramNode.model_rebuild()


class ProgramEdge(BaseModel):
    """Program edge public type."""

    model_config = ConfigDict(extra="forbid")

    src: str
    dst: str
    relation: str = "depends_on"


class ProgramGraph(BaseModel):
    """Program graph public type."""

    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.core.ProgramGraph"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "0.2.0"
    ARTIFACT_PAYLOAD_SCHEMA_VERSION_BY_MANIFEST: ClassVar[dict[str, str]] = {"0.2.0": "0.2"}
    ARTIFACT_KIND: ClassVar[Literal["foundry.program_graph"]] = "foundry.program_graph"
    ARTIFACT_MEDIA_TYPE: ClassVar[Literal["application/json"]] = "application/json"

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("0.2", pattern=r"^\d+\.\d+$")
    ir_ref: ArtifactRef
    lowered_ir_ref: LoweredIRRef | None = None
    nodes: list[ProgramNode] = Field(default_factory=list)
    edges: list[ProgramEdge] = Field(default_factory=list)
    entrypoints: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_nodes(self) -> ProgramGraph:
        node_ids = [item.node_id for item in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("duplicate_program_graph_node_id")
        return self


class LoweredMechanism(BaseModel):
    """Lowered mechanism public type."""

    model_config = ConfigDict(extra="forbid")

    binding_id: str
    mechanism_id: str
    intervention_ids: list[str] = Field(default_factory=list)
    effective_params_ref: ArtifactRef | None = None
    effective_schedule: dict[str, Any] | None = None
    selected_fidelity: str | None = None
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    legacy_kind_alias_used: bool = False
    target_selector: dict[str, Any] | None = None
    priority: int | None = None
    notes: list[str] = Field(default_factory=list)


class LoweredConstraint(BaseModel):
    """Lowered constraint public type."""

    model_config = ConfigDict(extra="forbid")

    constraint_id: str
    severity: Literal["hard", "soft"]
    slot_id: str
    operator: Literal["<", "<=", ">", ">=", "==", "!="]
    expected: Any
    unit_id: str | None = None
    penalty: Decimal | None = None
    aggregation: str = "scalar"
    quantile_param: float | None = None
    weights_slot_id: str | None = None
    notes: list[str] = Field(default_factory=list)


class CompositeConstraint(BaseModel):
    """Constraint involving multiple slots combined via arithmetic expression."""

    model_config = ConfigDict(extra="forbid")

    constraint_id: str
    expression: str
    slot_refs: list[str]
    operator: Literal["<", "<=", ">", ">=", "==", "!="]
    expected: str
    severity: Literal["hard", "soft"] = "hard"
    penalty: Decimal | None = None
    notes: list[str] = Field(default_factory=list)


class LoweredIR(BaseModel):
    """Lowered IR public type."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("0.2", pattern=r"^\d+\.\d+$")
    ir_ref: ArtifactRef
    mechanisms: list[LoweredMechanism] = Field(default_factory=list)
    constraints: list[LoweredConstraint] = Field(default_factory=list)
    composite_constraints: list[CompositeConstraint] = Field(default_factory=list)
    parameter_specs: list[dict[str, Any]] = Field(default_factory=list)
    time_semantics: dict[str, Any] | None = None
    environment_config: dict[str, Any] | None = None
    policy_fidelity_level: str | None = None
    constraint_mode: str = "hard_soft_v1"
    notes: list[str] = Field(default_factory=list)


class ExecPlan(BaseModel):
    """Execution-order artifact that pairs a program graph with resolved runtime posture."""

    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.core.ExecPlan"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "0.2.0"
    ARTIFACT_KIND: ClassVar[Literal["foundry.exec_plan"]] = "foundry.exec_plan"
    ARTIFACT_MEDIA_TYPE: ClassVar[Literal["application/json"]] = "application/json"

    model_config = ConfigDict(extra="forbid")

    program_ref: ProgramGraphRef
    order: list[str] = Field(default_factory=list)
    environment_ref: EnvironmentManifestRef | None = Field(
        default=None,
        description="Reference to captured environment at plan creation time",
    )
    environment_fingerprint: str | None = Field(
        default=None,
        description="Fingerprint of critical environment factors",
    )
    determinism_tier: str | None = Field(
        default=None,
        description="Determinism tier for reproducibility expectations",
    )
    random_seed: int | None = Field(
        default=None,
        description="Random seed associated with determinism tier",
    )
    nan_guard_enabled: bool = Field(
        default=False,
        description="Enable NaN/Inf guard checks during execution",
    )
    policy_fidelity_level: str | None = Field(
        default=None,
        description="Resolved policy-level fidelity from Trinity lowering",
    )
    constraint_mode: str = Field(
        default="hard_soft_v1",
        description="Constraint semantics mode used by executor",
    )
    mode: Literal["dev", "perf", "audit"] = "dev"
    jit: bool = True
    max_steps: int | None = None
    notes: list[str] = Field(default_factory=list)


class FoundryValidationFlags(BaseModel):
    """Foundry validation flags public type."""

    model_config = ConfigDict(extra="forbid")

    strict_schema: bool = True
    strict_link: bool = True
    allow_extra_params: bool = False
    strict_conflict_check: bool = True
    allow_legacy_units: bool = False


class FoundryCompileConfig(BaseModel):
    """Compiler options controlling lowering mode, cost budgets, and determinism hints."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")

    mode: Literal["dev", "perf", "audit"] = "dev"
    jit: bool = True
    max_steps: int | None = None
    nan_guard_enabled: bool = False

    determinism_tier: str | None = None
    random_seed: int | None = None

    cost_budget_max_total_ms: int | None = None
    cost_budget_max_memory_mb: int | None = None
    cost_budget_max_compile_ms: int | None = None
    cost_budget_max_per_mechanism_ms: int | None = None

    estimate_n_agents: int | None = None
    estimate_time_steps: int | None = None


class CompileRequest(BaseModel):
    """Input contract for compiling a policy artifact into Foundry execution artifacts."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0", "1.1", "1.2"] = "1.0"

    input_kind: Literal["auto", "trinity"] = "auto"
    policy_ref: ArtifactRef
    method_execution_plan_ref: ExecutionPlanRef | None = None

    registry_bundle_ref: ArtifactRef | None = None
    compile_config: FoundryCompileConfig = Field(
        default_factory=lambda: FoundryCompileConfig(schema_version="1.0")
    )
    validation_flags: FoundryValidationFlags = Field(default_factory=FoundryValidationFlags)
    return_selected_profile: bool = False
    method_metric_bindings: list[MethodMetricBindingRequest] = Field(
        default_factory=list, max_length=METHOD_METRIC_BINDING_LIMIT
    )

    @model_validator(mode="after")
    def validate_method_metric_request_version(self) -> CompileRequest:
        if self.method_metric_bindings and self.schema_version not in {"1.1", "1.2"}:
            raise ValueError("method_metric_bindings_require_compile_request_schema_1_1_or_1_2")
        if self.method_execution_plan_ref is not None:
            if self.schema_version != "1.2":
                raise ValueError("method_execution_plan_ref_requires_compile_request_schema_1_2")
            if (
                self.method_execution_plan_ref.kind != "scientist.execution_plan"
                or self.method_execution_plan_ref.media_type != "application/json"
                or self.method_execution_plan_ref.manifest_profile_sha256 is None
            ):
                raise ValueError("method_execution_plan_ref_must_be_exact_selected_execution_plan")
            if (
                self.policy_ref.kind != "ir.trinity_bundle"
                or self.policy_ref.manifest_profile_sha256 is None
            ):
                raise ValueError("method_execution_plan_ref_requires_exact_trinity_candidate_ref")
        elif self.schema_version == "1.2":
            raise ValueError("compile_request_schema_1_2_requires_method_execution_plan_ref")
        return self

    notes: list[str] = Field(default_factory=list)


class DerivedArtifact(BaseModel):
    """Derived artifact public type."""

    model_config = ConfigDict(extra="forbid")

    role: str
    ref: ArtifactRef


class CompileResult(BaseModel):
    """Compilation outcome pointing to the compile report and any derived Foundry artifacts."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    ok: bool

    exec_plan_ref: ExecPlanRef | None = None
    compile_report_ref: ArtifactRef

    derived_refs: list[DerivedArtifact] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class FoundryExecConfig(BaseModel):
    """Runtime overrides controlling execution mode, seed handling, and env capture."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    seed: int = 0
    mode: Literal["dev", "perf", "audit"] = "dev"
    max_steps: int | None = None
    deterministic: bool = True
    capture_env: bool = False


class FoundryInputBindingTransform(BaseModel):
    """Foundry input binding transform public type."""

    model_config = ConfigDict(extra="forbid")

    op: Literal[
        "identity",
        "to_bool",
        "to_int",
        "to_decimal",
        "fillna",
        "scale",
        "offset",
        "clip",
        "round",
    ] = "identity"
    params: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class FoundryInputBindingRule(BaseModel):
    """Rule mapping one external source path into a Foundry slot through optional transforms."""

    model_config = ConfigDict(extra="forbid")

    binding_id: str
    source_path: str
    target_slot_id: str
    required: bool = True
    default_value: Any = None
    transforms: list[FoundryInputBindingTransform] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class FoundryInputBindings(BaseModel):
    """Foundry input bindings public type."""

    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.core.FoundryInputBindings"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"
    ARTIFACT_SCHEMA_VERSIONS: ClassVar[tuple[str, ...]] = ("1.0", "1.1")
    ARTIFACT_REQUIRED_FIELDS_BY_SCHEMA_VERSION: ClassVar[dict[str, tuple[str, ...]]] = {
        "1.1": ("registered_sql_admission_ref",),
    }
    ARTIFACT_KIND: ClassVar[Literal["foundry.input_bindings"]] = "foundry.input_bindings"
    ARTIFACT_MEDIA_TYPE: ClassVar[Literal["application/json"]] = "application/json"

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    data_snapshot_ref: ArtifactRef
    registry_bundle_ref: ArtifactRef
    rules: list[FoundryInputBindingRule] = Field(default_factory=list)
    bound_state_snapshot_ref: StateSnapshotRef
    quality_report_ref: ArtifactRef | None = None
    registered_sql_admission_ref: ArtifactRef | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_registered_sql_transport(self) -> FoundryInputBindings:
        if (self.registered_sql_admission_ref is not None) != (self.schema_version == "1.1"):
            raise ValueError("foundry_input_bindings_registered_sql_version_mismatch")
        return self


class FeedbackObservationSpec(BaseModel):
    """Scalar observable extracted from post-execution state or metrics."""

    model_config = ConfigDict(extra="forbid")

    source_kind: Literal["state_path", "metric"]
    source_ref: str
    reduction: Literal["identity", "mean", "sum", "min", "max"] = "identity"
    transforms: list[FoundryInputBindingTransform] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class FeedbackVariableSpec(BaseModel):
    """One compact feedback-state component with extraction and injection metadata."""

    model_config = ConfigDict(extra="forbid")

    variable_id: str
    source_kind: Literal["state_path", "metric"]
    source_ref: str
    reduction: Literal["identity", "mean", "sum", "min", "max"] = "identity"
    transforms: list[FoundryInputBindingTransform] = Field(default_factory=list)
    target_kind: Literal["state_path", "parameter_override"] = "state_path"
    target_ref: str
    target_param: str | None = None
    initial_value: float | None = None
    lower_bound: float | None = None
    upper_bound: float | None = None
    scale: float | None = Field(default=None, gt=0.0)
    weight: float = Field(default=1.0, gt=0.0)
    finite_difference_step: float | None = Field(default=None, gt=0.0)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_target(self) -> FeedbackVariableSpec:
        if self.target_kind == "parameter_override" and not self.target_param:
            raise ValueError("Feedback parameter_override targets require target_param")
        if self.target_kind == "state_path" and self.target_param is not None:
            raise ValueError("Feedback state_path targets must not set target_param")
        return self


class FeedbackDiagnosticSpec(BaseModel):
    """Additional scalar diagnostic emitted alongside the solve trace."""

    model_config = ConfigDict(extra="forbid")

    diagnostic_id: str
    source_kind: Literal["state_path", "metric"]
    source_ref: str
    reduction: Literal["identity", "mean", "sum", "min", "max"] = "identity"
    transforms: list[FoundryInputBindingTransform] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class FeedbackSolverConfig(BaseModel):
    """Numerical controls for the fixed-point outer loop."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    mode: Literal["picard", "anderson", "hybrid"] = "hybrid"
    max_iter: int = Field(default=50, ge=1)
    homotopy_grid: list[float] = Field(default_factory=lambda: [0.0, 0.1, 0.25, 0.5, 0.75, 1.0])
    damping_init: float = Field(default=0.5, gt=0.0, le=1.0)
    damping_min: float = Field(default=0.05, gt=0.0, le=1.0)
    anderson_memory: int = Field(default=5, ge=1)
    anderson_start: int = Field(default=3, ge=0)
    anderson_accept_ratio: float = Field(default=0.95, gt=0.0, le=1.0)
    newton_start: int = Field(default=4, ge=0)
    trust_radius_init: float = Field(default=1.0, gt=0.0)
    max_restarts: int = Field(default=3, ge=0)
    stagnation_patience: int = Field(default=4, ge=1)
    divergence_patience: int = Field(default=2, ge=1)
    oscillation_patience: int = Field(default=4, ge=2)
    atol: float = Field(default=1e-6, ge=0.0)
    rtol: float = Field(default=1e-5, ge=0.0)
    xtol: float = Field(default=1e-7, ge=0.0)
    budget_diagnostic_id: str | None = None
    budget_tolerance: float | None = Field(default=None, ge=0.0)
    jacobian_eps: float = Field(default=1e-4, gt=0.0)
    compute_jacobian_diagnostics: bool = True
    multi_start_values: list[list[float]] = Field(default_factory=list)
    fixed_point_merge_tol: float = Field(default=1e-4, gt=0.0)
    store_alternative_fixed_points: bool = True
    detect_multiplicity: bool = False
    multiplicity_mode: Literal["off", "baseline", "continuation"] = "off"
    multiplicity_max_attempts: int = Field(default=256, ge=1)
    multiplicity_sobol_draws: int = Field(default=128, ge=0)
    continuation_parameter: str | None = None
    continuation_grid: list[float] = Field(default_factory=list)
    basin_draws: int = Field(default=0, ge=0)
    basin_seed: int = Field(default=0, ge=0)
    svd_bifurcation_tol: float = Field(default=1e-3, gt=0.0)
    spectral_radius_warn_tol: float = Field(default=5e-2, gt=0.0)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_homotopy_grid(self) -> FeedbackSolverConfig:
        if not self.homotopy_grid:
            raise ValueError("homotopy_grid must not be empty")
        if any(value < 0.0 or value > 1.0 for value in self.homotopy_grid):
            raise ValueError("homotopy_grid values must lie in [0, 1]")
        if list(self.homotopy_grid) != sorted(self.homotopy_grid):
            raise ValueError("homotopy_grid must be sorted in nondecreasing order")
        if self.homotopy_grid[0] != 0.0 or self.homotopy_grid[-1] != 1.0:
            raise ValueError("homotopy_grid must start at 0.0 and end at 1.0")
        return self


class FeedbackConfig(BaseModel):
    """Opt-in fixed-point solve configuration for feedback-consistent execution."""

    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.core.FeedbackConfig"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"
    ARTIFACT_KIND: ClassVar[Literal["foundry.feedback_config"]] = "foundry.feedback_config"
    ARTIFACT_MEDIA_TYPE: ClassVar[Literal["application/json"]] = "application/json"

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    mode: Literal["off", "fixed_point"] = "fixed_point"
    variables: list[FeedbackVariableSpec] = Field(default_factory=list)
    diagnostics: list[FeedbackDiagnosticSpec] = Field(default_factory=list)
    solver: FeedbackSolverConfig = Field(
        default_factory=lambda: FeedbackSolverConfig(schema_version="1.0")
    )
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_variables(self) -> FeedbackConfig:
        if self.mode == "fixed_point" and not self.variables:
            raise ValueError("feedback fixed_point mode requires at least one variable")
        return self


class FeedbackStateSnapshot(BaseModel):
    """Compact feedback vector plus solver scaling metadata."""

    model_config = ConfigDict(extra="forbid")

    variable_ids: list[str]
    values: list[float]
    scales: list[float]
    lower_bounds: list[float | None]
    upper_bounds: list[float | None]
    weights: list[float]
    notes: list[str] = Field(default_factory=list)


class FeedbackIterationRecord(BaseModel):
    """One outer-loop iteration record persisted into the feedback trace."""

    model_config = ConfigDict(extra="forbid")

    stage_alpha: float
    iteration: int
    residual_norm: float
    step_norm: float
    damping: float
    method: str
    accepted: bool
    iterate: list[float]
    residual: list[float]
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class FeedbackFixedPointCandidate(BaseModel):
    """One converged fixed-point candidate returned by a multi-start solve."""

    model_config = ConfigDict(extra="forbid")

    state: FeedbackStateSnapshot
    residual_norm: float | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class FeedbackTrace(BaseModel):
    """Residual and step trace emitted by a feedback solve."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    records: list[FeedbackIterationRecord] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class FeedbackJacobianDiagnostics(BaseModel):
    """Finite-difference Jacobian diagnostics near the solved fixed point."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    dimension: int = Field(ge=1)
    jacobian: list[list[float]] = Field(default_factory=list)
    spectral_radius: float | None = None
    operator_norm_inf: float | None = None
    condition_number: float | None = None
    smallest_singular_value_i_minus_j: float | None = None
    near_fold: bool = False
    near_flip: bool = False
    near_loss_of_stability: bool = False
    near_bifurcation: bool = False
    notes: list[str] = Field(default_factory=list)


class EquilibriumBasinInterval(BaseModel):
    """Confidence interval for a basin-share estimate."""

    model_config = ConfigDict(extra="forbid")

    lower: float = Field(ge=0.0, le=1.0)
    upper: float = Field(ge=0.0, le=1.0)


class EquilibriumSearchProtocol(BaseModel):
    """Protocol metadata for a fixed-point multiplicity search."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["baseline", "research", "continuation"] = "baseline"
    start_domain: dict[str, Any] = Field(default_factory=dict)
    n_attempts: int = Field(ge=1)
    continuation_parameter: str | None = None
    continuation_grid: list[float] = Field(default_factory=list)
    merge_tol: float | None = Field(default=None, gt=0.0)
    residual_tol: float | None = Field(default=None, ge=0.0)
    basin_draws: int = Field(default=0, ge=0)


class EquilibriumCandidateJacobian(BaseModel):
    """Jacobian summaries attached to one equilibrium candidate."""

    model_config = ConfigDict(extra="forbid")

    spectral_radius: float | None = None
    operator_norm_inf: float | None = None
    condition_number: float | None = None
    smallest_singular_value_i_minus_j: float | None = None
    near_fold: bool = False
    near_flip: bool = False
    near_loss_of_stability: bool = False
    near_bifurcation: bool = False


class BasinEstimate(BaseModel):
    """Estimated basin share for one clustered fixed point."""

    model_config = ConfigDict(extra="forbid")

    equilibrium_id: str
    draws: int = Field(ge=0)
    hits: int = Field(ge=0)
    share_hat: float | None = Field(default=None, ge=0.0, le=1.0)
    ci_95: EquilibriumBasinInterval | None = None
    notes: list[str] = Field(default_factory=list)


class EquilibriumCandidate(BaseModel):
    """One clustered fixed-point candidate in a multiplicity report."""

    model_config = ConfigDict(extra="forbid")

    equilibrium_id: str
    state: FeedbackStateSnapshot
    residual_norm: float | None = None
    step_norm: float | None = None
    jacobian: EquilibriumCandidateJacobian | None = None
    local_stability: Literal[
        "attractive",
        "unstable",
        "neutral_or_near_bifurcation",
        "unknown",
    ] = "unknown"
    branch_id: str | None = None
    basin_share_hat: float | None = Field(default=None, ge=0.0, le=1.0)
    basin_ci_95: EquilibriumBasinInterval | None = None
    discovered_from_starts: int = Field(default=1, ge=1)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class EquilibriumBranchPoint(BaseModel):
    """One point on a continuation branch."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    lambda_value: float = Field(alias="lambda")
    equilibrium_id: str


class EquilibriumBranch(BaseModel):
    """A continuation branch through discovered equilibria."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    branch_id: str
    points: list[EquilibriumBranchPoint] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class BifurcationCandidate(BaseModel):
    """Potential bifurcation event detected from local diagnostics."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    kind: Literal["fold", "flip", "loss_of_stability"]
    lambda_value: float | None = Field(default=None, alias="lambda")
    equilibrium_id: str
    confidence: Literal["low", "medium", "high"] = "low"
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class UnresolvedEquilibriumStart(BaseModel):
    """A start point that did not converge or could not be assigned to a cluster."""

    model_config = ConfigDict(extra="forbid")

    start_state: FeedbackStateSnapshot
    status: str
    failure_reason: str | None = None
    residual_norm: float | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class EquilibriumMultiplicityDiagnostics(BaseModel):
    """Search-level diagnostics for a multiplicity report."""

    model_config = ConfigDict(extra="forbid")

    num_attempts: int = Field(ge=0)
    num_converged: int = Field(ge=0)
    num_equilibria: int = Field(ge=0)
    num_unresolved: int = Field(default=0, ge=0)
    two_cycle_failures: int = Field(default=0, ge=0)
    stagnation_failures: int = Field(default=0, ge=0)
    divergence_failures: int = Field(default=0, ge=0)
    unresolved_starts_share: float | None = Field(default=None, ge=0.0, le=1.0)
    max_pairwise_cluster_overlap: float | None = None
    branch_switch_events: int = Field(default=0, ge=0)
    continuation_failures: int = Field(default=0, ge=0)
    false_merge_risk: float | None = Field(default=None, ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list)


class EquilibriumMultiplicityProvenance(BaseModel):
    """Reproducibility metadata for a multiplicity report."""

    model_config = ConfigDict(extra="forbid")

    solver_version: str = "polisyos-foundry-feedback-1.0"
    git_sha: str = "unknown"
    runtime_refs: list[str] = Field(default_factory=list)
    random_seed: int | None = None


class EquilibriumMultiplicityReport(BaseModel):
    """Structured report for discovered fixed-point multiplicity."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    model_id: str
    parameter_hash: str | None = None
    search_protocol: EquilibriumSearchProtocol
    equilibria: list[EquilibriumCandidate] = Field(default_factory=list)
    branches: list[EquilibriumBranch] = Field(default_factory=list)
    bifurcation_candidates: list[BifurcationCandidate] = Field(default_factory=list)
    basin_estimates: list[BasinEstimate] = Field(default_factory=list)
    unresolved_starts: list[UnresolvedEquilibriumStart] = Field(default_factory=list)
    global_diagnostics: EquilibriumMultiplicityDiagnostics
    provenance: EquilibriumMultiplicityProvenance = Field(
        default_factory=EquilibriumMultiplicityProvenance
    )
    notes: list[str] = Field(default_factory=list)


class FeedbackConvergenceCertificate(BaseModel):
    """Certificate summarizing whether and how the feedback solve converged."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    status: Literal[
        "converged",
        "max_iter_exceeded",
        "restarts_exhausted",
        "diverged",
        "oscillating",
        "stagnated",
        "failed",
    ]
    converged: bool
    final_stage_alpha: float | None = None
    final_iteration: int | None = Field(default=None, ge=0)
    final_residual_norm: float | None = None
    final_step_norm: float | None = None
    budget_gap: float | None = None
    budget_tolerance: float | None = None
    multiple_fixed_points: bool = False
    oscillation_detected: bool = False
    divergence_detected: bool = False
    stagnation_detected: bool = False
    near_bifurcation: bool = False
    notes: list[str] = Field(default_factory=list)


class FeedbackSolveResult(BaseModel):
    """Top-level feedback-solver outcome persisted as a CAS artifact."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    status: str = "converged"
    converged: bool
    initial_state: FeedbackStateSnapshot
    final_state: FeedbackStateSnapshot
    trace_ref: FeedbackTraceRef | None = None
    jacobian_diagnostics_ref: FeedbackJacobianDiagnosticsRef | None = None
    convergence_certificate_ref: FeedbackConvergenceCertificateRef | None = None
    final_parameter_override_bundle_ref: ParameterOverrideBundleRef | None = None
    multiplicity_report_ref: EquilibriumMultiplicityReportRef | None = None
    alternative_fixed_points: list[FeedbackFixedPointCandidate] = Field(default_factory=list)
    failure_reason: str | None = None
    final_diagnostics: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class AttractorStateProjection(BaseModel):
    """Reduced observable state on which attractor claims are made."""

    model_config = ConfigDict(extra="forbid")

    variables: list[str] = Field(default_factory=list)
    reduced_dimension: int = Field(ge=0)
    quotient_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dimension(self) -> AttractorStateProjection:
        if self.variables and self.reduced_dimension != len(self.variables):
            raise ValueError("reduced_dimension must match variables length")
        return self


class AttractorParameterPoint(BaseModel):
    """Parameter coordinate associated with an attractor-analysis result."""

    model_config = ConfigDict(extra="forbid")

    names: list[str] = Field(default_factory=list)
    values: list[float] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_shapes(self) -> AttractorParameterPoint:
        if len(self.names) != len(self.values):
            raise ValueError("parameter names and values must have equal length")
        return self


class AttractorSpectralValue(BaseModel):
    """JSON-safe representation of a real or complex spectral value."""

    model_config = ConfigDict(extra="forbid")

    real: float
    imag: float = 0.0


class AttractorStateRepresentation(BaseModel):
    """Compact state, orbit, or invariant-set representation for one attractor."""

    model_config = ConfigDict(extra="forbid")

    equilibrium: dict[str, float] | None = None
    section_definition: str | None = None
    orbit_artifact_ref: ArtifactRef | None = None
    orbit_points: list[dict[str, float]] = Field(default_factory=list)
    invariant_set_artifact_ref: ArtifactRef | None = None
    summary: dict[str, Any] = Field(default_factory=dict)


class AttractorStability(BaseModel):
    """Local or finite-time stability diagnostics for an attractor candidate."""

    model_config = ConfigDict(extra="forbid")

    local_class: Literal[
        "asymptotically_stable",
        "orbitally_stable",
        "neutral",
        "unstable",
        "mixed",
        "unknown",
    ] = "unknown"
    jacobian_eigenvalues: list[AttractorSpectralValue] = Field(default_factory=list)
    spectral_radius: float | None = Field(default=None, ge=0.0)
    floquet_multipliers: list[AttractorSpectralValue] | None = None
    lyapunov_spectrum: list[float] | None = None
    largest_lyapunov_exponent: float | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class AttractorCertificate(BaseModel):
    """Declare the certificate or evidence supporting an attractor claim."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: str = "none"
    status: Literal[
        "not_attempted",
        "not_applicable",
        "numerically_supported",
        "proved_local",
        "proved_global",
        "failed",
    ] = "not_attempted"
    evidence_strength: float | None = Field(default=None, ge=0.0, le=1.0)
    v_description: str | None = Field(default=None, alias="V_description")
    proof_artifact_ref: ArtifactRef | None = None
    notes: list[str] = Field(default_factory=list)


class PeriodicOrbitDiagnostics(BaseModel):
    """Diagnostics for a periodic orbit or Poincare-map fixed point."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    period: float = Field(gt=0.0)
    section_definition: str | None = None
    orbit_artifact_ref: ArtifactRef | None = None
    floquet_multipliers: list[AttractorSpectralValue] = Field(default_factory=list)
    spectral_radius: float | None = Field(default=None, ge=0.0)
    transverse_certificate: AttractorCertificate | None = None
    notes: list[str] = Field(default_factory=list)


class AttractorBasinEstimate(BaseModel):
    """Basin-of-attraction estimate for one attractor."""

    model_config = ConfigDict(extra="forbid")

    estimation_method: str | None = None
    basin_measure_estimate: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence_interval: tuple[float, float] | None = None
    boundary_complexity: str | None = None
    basin_map_ref: BasinMapRef | None = None
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_confidence_interval(self) -> AttractorBasinEstimate:
        if self.confidence_interval is None:
            return self
        lower, upper = self.confidence_interval
        if lower < 0.0 or upper > 1.0 or lower > upper:
            raise ValueError("confidence_interval must be ordered within [0, 1]")
        return self


class AttractorObservableSummary(BaseModel):
    """Human-scale observable properties of one attractor."""

    model_config = ConfigDict(extra="forbid")

    period: float | None = Field(default=None, gt=0.0)
    max_amplitude: float | None = Field(default=None, ge=0.0)
    terminal_residual_norm: float | None = Field(default=None, ge=0.0)
    summary: dict[str, Any] = Field(default_factory=dict)


class AttractorUncertainty(BaseModel):
    """Numerical and stochastic uncertainty attached to one attractor claim."""

    model_config = ConfigDict(extra="forbid")

    seeds_used: int | None = Field(default=None, ge=0)
    numerical_tolerance: float | None = Field(default=None, ge=0.0)
    continuation_step: float | None = Field(default=None, gt=0.0)
    finite_time_horizon: int | None = Field(default=None, ge=0)
    notes: list[str] = Field(default_factory=list)


class AttractorSummary(BaseModel):
    """One attractor, invariant set, or rejected divergent regime."""

    model_config = ConfigDict(extra="forbid")

    attractor_id: str
    kind: Literal[
        "fixed_point",
        "limit_cycle",
        "chaotic",
        "torus",
        "invariant_set",
        "divergent",
    ]
    existence_status: Literal[
        "candidate",
        "numerically_confirmed",
        "analytically_confirmed",
        "rejected",
        "unknown",
    ] = "candidate"
    state_representation: AttractorStateRepresentation = Field(
        default_factory=AttractorStateRepresentation
    )
    stability: AttractorStability = Field(default_factory=AttractorStability)
    certificate: AttractorCertificate = Field(default_factory=AttractorCertificate)
    basin: AttractorBasinEstimate = Field(default_factory=AttractorBasinEstimate)
    observables: AttractorObservableSummary = Field(default_factory=AttractorObservableSummary)
    uncertainty: AttractorUncertainty = Field(default_factory=AttractorUncertainty)
    notes: list[str] = Field(default_factory=list)


class BifurcationEvent(BaseModel):
    """Detected local or global bifurcation event on a branch or sweep."""

    model_config = ConfigDict(extra="forbid")

    bifurcation_id: str
    kind: Literal[
        "saddle_node",
        "hopf",
        "period_doubling",
        "neimark_sacker",
        "torus",
        "branch_point",
        "homoclinic",
        "regime_change",
        "unknown",
    ]
    parameter_values: dict[str, float] = Field(default_factory=dict)
    branch_from: str | None = None
    branch_to: str | None = None
    detection_method: str
    normal_form: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list)


class AttractorUncertaintySummary(BaseModel):
    """Top-level uncertainty summary for an attractor-analysis run."""

    model_config = ConfigDict(extra="forbid")

    stochastic_model: bool = False
    seed_ensemble_size: int | None = Field(default=None, ge=0)
    unresolved_items: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class AttractorAnalysisProvenance(BaseModel):
    """Toolchain and upstream artifacts used to produce an attractor report."""

    model_config = ConfigDict(extra="forbid")

    toolchain: list[str] = Field(default_factory=list)
    derived_from: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class AttractorAnalysisResult(BaseModel):
    """Top-level Foundry artifact for attractors, bifurcations, and certificates."""

    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.core.AttractorAnalysisResult"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"
    ARTIFACT_KIND: ClassVar[Literal["foundry.attractor_analysis_result"]] = (
        "foundry.attractor_analysis_result"
    )
    ARTIFACT_MEDIA_TYPE: ClassVar[Literal["application/json"]] = "application/json"

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    kind: Literal["foundry.attractor_analysis_result"] = "foundry.attractor_analysis_result"
    analysis_id: str
    model_ref: ArtifactRef | None = None
    simulation_result_ref: SimulationResultRef | None = None
    exec_plan_ref: ExecPlanRef | None = None
    feedback_result_ref: FeedbackResultRef | None = None
    state_projection: AttractorStateProjection
    parameter_point: AttractorParameterPoint = Field(default_factory=AttractorParameterPoint)
    attractors: list[AttractorSummary] = Field(default_factory=list)
    bifurcations: list[BifurcationEvent] = Field(default_factory=list)
    uncertainty_summary: AttractorUncertaintySummary = Field(
        default_factory=AttractorUncertaintySummary
    )
    provenance: AttractorAnalysisProvenance = Field(default_factory=AttractorAnalysisProvenance)
    notes: list[str] = Field(default_factory=list)


class BasinMapSample(BaseModel):
    """One initial-condition sample and its assigned attractor label."""

    model_config = ConfigDict(extra="forbid")

    sample_id: str
    initial_state: dict[str, float]
    attractor_id: str | None = None
    seed: int | None = None
    terminal_residual_norm: float | None = Field(default=None, ge=0.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list)


class BasinMap(BaseModel):
    """Dense basin-map sidecar for attractor analysis."""

    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.core.BasinMap"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"
    ARTIFACT_KIND: ClassVar[Literal["foundry.basin_map"]] = "foundry.basin_map"
    ARTIFACT_MEDIA_TYPE: ClassVar[Literal["application/json"]] = "application/json"

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    kind: Literal["foundry.basin_map"] = "foundry.basin_map"
    basin_id: str
    analysis_id: str | None = None
    state_projection: AttractorStateProjection
    sampling_method: str
    samples: list[BasinMapSample] = Field(default_factory=list)
    basin_measure_estimates: dict[str, float] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ContinuationBranchPoint(BaseModel):
    """One continuation branch point with optional stability summaries."""

    model_config = ConfigDict(extra="forbid")

    point_id: str
    parameter_values: dict[str, float] = Field(default_factory=dict)
    state: dict[str, float] = Field(default_factory=dict)
    period: float | None = Field(default=None, gt=0.0)
    stability: AttractorStability = Field(default_factory=AttractorStability)
    bifurcation_id: str | None = None
    notes: list[str] = Field(default_factory=list)


class ContinuationBranch(BaseModel):
    """Continuation sidecar for equilibria, periodic orbits, or bifurcation curves."""

    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.core.ContinuationBranch"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"
    ARTIFACT_KIND: ClassVar[Literal["foundry.continuation_branch"]] = "foundry.continuation_branch"
    ARTIFACT_MEDIA_TYPE: ClassVar[Literal["application/json"]] = "application/json"

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    kind: Literal["foundry.continuation_branch"] = "foundry.continuation_branch"
    branch_id: str
    analysis_id: str | None = None
    branch_kind: Literal["equilibrium", "periodic_orbit", "bifurcation_curve", "parameter_sweep"]
    parameters: list[str] = Field(default_factory=list)
    points: list[ContinuationBranchPoint] = Field(default_factory=list)
    bifurcations: list[BifurcationEvent] = Field(default_factory=list)
    toolchain: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class AttractorAnalysisRequest(BaseModel):
    """Input contract for Foundry attractor-analysis endpoints."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    model_ref: ArtifactRef | None = None
    simulation_result_ref: SimulationResultRef | None = None
    exec_plan_ref: ExecPlanRef | None = None
    feedback_result_ref: FeedbackResultRef | None = None
    feedback_jacobian_diagnostics_ref: FeedbackJacobianDiagnosticsRef | None = None
    state_projection: AttractorStateProjection | None = None
    parameter_point: AttractorParameterPoint = Field(default_factory=AttractorParameterPoint)
    variable_ids: list[str] = Field(default_factory=list)
    trajectory: list[list[float]] | None = None
    trajectories: list[list[list[float]]] = Field(default_factory=list)
    initial_states: list[dict[str, float]] = Field(default_factory=list)
    seeds: list[int] = Field(default_factory=list)
    analysis_modes: list[_AttractorAnalysisMode] = Field(
        default_factory=_default_attractor_analysis_modes
    )
    tolerance: float = Field(default=1.0e-6, ge=0.0)
    rtol: float = Field(default=1.0e-5, ge=0.0)
    window: int = Field(default=32, ge=2)
    max_period: int = Field(default=12, ge=2)
    largest_lyapunov_exponent: float | None = None
    stochastic_model: bool = False
    persist_artifact: bool = True
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_source_ref(self) -> AttractorAnalysisRequest:
        if self.trajectory is not None and self.trajectories:
            raise ValueError("use either trajectory or trajectories, not both")
        trajectory_count = 1 if self.trajectory is not None else len(self.trajectories)
        if self.initial_states and len(self.initial_states) != trajectory_count:
            raise ValueError("initial_states length must match trajectory count")
        if self.seeds and len(self.seeds) != trajectory_count:
            raise ValueError("seeds length must match trajectory count")
        if (
            self.model_ref is None
            and self.simulation_result_ref is None
            and self.exec_plan_ref is None
            and self.feedback_result_ref is None
            and self.trajectory is None
            and not self.trajectories
        ):
            raise ValueError(
                "attractor analysis requires a model/run reference or direct trajectory data"
            )
        if not self.variable_ids and self.state_projection is not None:
            self.variable_ids = list(self.state_projection.variables)
        return self


class AttractorAnalysisResponse(BaseModel):
    """Response contract for Foundry attractor-analysis endpoints."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    ok: bool
    analysis_result: AttractorAnalysisResult | None = None
    analysis_result_ref: AttractorAnalysisResultRef | None = None
    derived_refs: list[DerivedArtifact] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ParameterOverrideBundle(BaseModel):
    """Collection of parameter overrides plus provenance for who supplied each change."""

    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.core.ParameterOverrideBundle"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"
    ARTIFACT_KIND: ClassVar[Literal["foundry.parameter_override_bundle"]] = (
        "foundry.parameter_override_bundle"
    )
    ARTIFACT_MEDIA_TYPE: ClassVar[Literal["application/json"]] = "application/json"

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)
    sources: dict[str, list[str]] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ObservedRange(BaseModel):
    """Numeric lower/upper envelope used by welfare-bound providers."""

    model_config = ConfigDict(extra="forbid")

    lower: float | list[float] | None = None
    upper: float | list[float] | None = None
    notes: list[str] = Field(default_factory=list)


class ObservedRangeBundle(BaseModel):
    """Optional calibrated ranges attached to execution for welfare certification."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    data_snapshot_ref: ArtifactRef | None = None
    ranges: dict[str, ObservedRange] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ExecuteRequest(BaseModel):
    """Input contract for running a compiled Foundry plan against bound evidence."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")

    exec_plan_ref: ExecPlanRef
    input_bindings_ref: FoundryInputBindingsRef

    registry_bundle_ref: ArtifactRef | None = None
    feedback_config_ref: FeedbackConfigRef | None = None
    parameter_override_bundle_ref: ParameterOverrideBundleRef | None = None
    observed_range_bundle_ref: ObservedRangeBundleRef | None = None
    welfare_bound_mode: Literal["ex_ante", "ex_post", "both"] = "ex_ante"
    welfare_bound_required: bool = False
    exec_config: FoundryExecConfig = Field(
        default_factory=lambda: FoundryExecConfig(schema_version="1.0")
    )
    notes: list[str] = Field(default_factory=list)
    return_selected_profile: bool = False


class FoundryExecutionInputBasis(BaseModel):
    """Exact CAS-bound single-step inputs observed at the Foundry executor boundary.

    This artifact identifies producer inputs and effective call arguments only. It
    carries no risk interpretation, refinement, unit, valid-time, or authority claim.
    """

    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.core.FoundryExecutionInputBasis"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"
    ARTIFACT_SCHEMA_VERSIONS: ClassVar[tuple[str, ...]] = ("1.0", "1.1")
    ARTIFACT_REQUIRED_FIELDS_BY_SCHEMA_VERSION: ClassVar[dict[str, tuple[str, ...]]] = {
        "1.1": ("registered_sql_admission_ref",),
    }
    ARTIFACT_KIND: ClassVar[Literal["foundry.execution_input_basis"]] = (
        "foundry.execution_input_basis"
    )
    ARTIFACT_MEDIA_TYPE: ClassVar[Literal["application/json"]] = "application/json"

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0", "1.1"] = "1.0"
    authority_purpose: Literal["execution_input_identity_only"] = "execution_input_identity_only"
    execution_mode: Literal["single_step"] = "single_step"
    request: ExecuteRequest
    request_fields_set: tuple[str, ...] = ()
    request_exec_config_fields_set: tuple[str, ...] = ()
    exec_plan_ref: ExecPlanRef
    program_graph_ref: ProgramGraphRef
    trinity_bundle_ref: ArtifactRef
    candidate_ref: ArtifactRef
    candidate_data_snapshot_ref: ArtifactRef
    candidate_registry_bundle_ref: ArtifactRef
    input_bindings_ref: FoundryInputBindingsRef
    data_snapshot_ref: ArtifactRef
    registered_sql_admission_ref: ArtifactRef | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    bound_state_snapshot_ref: StateSnapshotRef
    binding_registry_ref: ArtifactRef
    compile_registry_ref: ArtifactRef
    runtime_registry_ref: ArtifactRef
    binding_registry_members: RegistryBundlePayload
    compile_registry_members: RegistryBundlePayload
    runtime_registry_members: RegistryBundlePayload
    base_state_snapshot_ref: StateSnapshotRef
    parameter_override_bundle_ref: ParameterOverrideBundleRef | None = None
    observed_range_bundle_ref: ObservedRangeBundleRef | None = None
    parameter_overrides: dict[str, dict[str, Any]] | None = None
    effective_step: int = Field(ge=0, strict=True)
    effective_seed: int = Field(strict=True)
    effective_seed_source: str = Field(min_length=1)
    effective_mode: str = Field(min_length=1)
    effective_max_steps: int | None = None
    effective_determinism_tier: str | None = None
    effective_nan_guard_enabled: bool
    effective_jit: bool
    effective_capture_env: bool

    @model_validator(mode="after")
    def _validate_registered_sql_transport(self) -> FoundryExecutionInputBasis:
        if (self.registered_sql_admission_ref is not None) != (self.schema_version == "1.1"):
            raise ValueError("execution_input_basis_registered_sql_version_mismatch")
        return self


class ExecuteResult(BaseModel):
    """Execution outcome pointing to the simulation result and any additional derived artifacts."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0", "1.1"] = "1.0"
    ok: bool

    simulation_result_ref: SimulationResultRef | None = None
    method_execution_bundle_ref: MethodExecutionBundleRef | None = None
    derived_refs: list[DerivedArtifact] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_method_execution_result_version(self) -> ExecuteResult:
        if self.method_execution_bundle_ref is not None and self.schema_version != "1.1":
            raise ValueError("method_execution_bundle_requires_execute_result_schema_1_1")
        return self


class WelfareBoundReport(BaseModel):
    """Node-level welfare-loss envelope relative to a planner first-best benchmark."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    mechanism_type: str
    node_id: str | None = None
    mode: Literal["ex_ante", "ex_post", "both"] = "ex_ante"
    welfare_loss_lower: float | None = None
    welfare_loss_upper: float | None = None
    first_best_lower: float | None = None
    first_best_upper: float | None = None
    mechanism_value: float | None = None
    required_observables: tuple[str, ...] = Field(default_factory=tuple)
    status: Literal["ok", "warning", "insufficient_observables", "invalid_input"] = "ok"
    notes: list[str] = Field(default_factory=list)


class StateSnapshot(BaseModel):
    """Reference bundle for a persisted Foundry state or method-input capture.

    ``lineage_inputs`` is the ordered manifest input list. Version 2.1 preserves
    its historical bare state-blob edge; versions 2.2 and 2.3 bind the exact
    selected state-blob view. Version 2.3 is reserved for sparse method-input
    slot maps and requires its explicit layout discriminator. Older payloads omit
    that discriminator and retain their historical GlobalState wire bytes.
    """

    SCHEMA_MANIFEST_VERSION_BY_PAYLOAD_VERSION: ClassVar[Mapping[str, str]] = MappingProxyType(
        {
            "2.0": "1.0",
            "2.1": "2.1.0",
            "2.2": "2.2.0",
            "2.3": "2.3.0",
        }
    )
    METHOD_INPUT_SCHEMA_VERSION: ClassVar[str] = "2.3"
    METHOD_INPUT_LAYOUT: ClassVar[Literal["method_input_slots"]] = "method_input_slots"

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("2.1", pattern=r"^\d+\.\d+$")
    state_ref: ArtifactRef
    schema_ref: ArtifactRef | None = None
    step: int | None = None
    format_version: str = "npz-v2"
    checksum_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    entry_count: int | None = Field(default=None, ge=0)
    codec: str = "numpy-npz"
    lineage_inputs: list[InputRef] | None = None
    notes: list[str] = Field(default_factory=list)
    layout: Literal["method_input_slots"] | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )

    @model_validator(mode="after")
    def validate_versioned_layout(self) -> StateSnapshot:
        """Bind the sparse method-input layout to schema 2.3 only."""
        layout_was_supplied = "layout" in self.model_fields_set
        if self.schema_version == self.METHOD_INPUT_SCHEMA_VERSION:
            if not layout_was_supplied or self.layout != self.METHOD_INPUT_LAYOUT:
                raise ValueError("state_snapshot_2_3_requires_explicit_method_input_layout")
        elif layout_was_supplied:
            raise ValueError("state_snapshot_layout_requires_schema_2_3")
        return self


class TreasurySeed(BaseModel):
    """Treasury seed public type."""

    model_config = ConfigDict(extra="forbid")

    seed: int
    streams: dict[str, int] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ExecConfig(BaseModel):
    """Minimal execution overrides accepted by legacy callers at run launch time."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["dev", "perf", "audit"] = "dev"
    max_steps: int | None = None
    deterministic: bool = True
    notes: list[str] = Field(default_factory=list)


class PatchOp(BaseModel):
    """Patch op public type."""

    model_config = ConfigDict(extra="forbid")

    slot_id: str
    op: Literal["add", "set"]
    value_ref: ArtifactRef | None = None
    mask_ref: ArtifactRef | None = None
    mask_scope: Literal["global", "per_agent", "per_firm", "per_entity"] | None = None
    notes: list[str] = Field(default_factory=list)


class UpdateOp(BaseModel):
    """Update op public type."""

    model_config = ConfigDict(extra="forbid")

    slot_id: str
    op: Literal["add", "set", "priority_set", "clamp", "masked"]
    value_ref: ArtifactRef | None = None
    mask_ref: ArtifactRef | None = None
    priority: int | None = None
    min_ref: ArtifactRef | None = None
    max_ref: ArtifactRef | None = None
    notes: list[str] = Field(default_factory=list)


class PatchMeta(BaseModel):
    """Patch meta public type."""

    model_config = ConfigDict(extra="forbid")

    source_node_id: str | None = None
    step: int | None = None
    mode: Literal["dev", "perf", "audit"] | None = None
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class Patch(BaseModel):
    """Patch public type."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    meta: PatchMeta | None = None
    ops: list[UpdateOp] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PatchSet(BaseModel):
    """Patch set public type."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    patches: list[Patch] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class StateDelta(BaseModel):
    """State delta public type."""

    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.core.StateDelta"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "0.1.0"
    ARTIFACT_KIND: ClassVar[Literal["foundry.state_delta"]] = "foundry.state_delta"
    ARTIFACT_MEDIA_TYPE: ClassVar[Literal["application/json"]] = "application/json"

    model_config = ConfigDict(extra="forbid")

    base_ref: StateSnapshotRef | None = None
    patch_ref: ArtifactRef | None = None
    ops: list[PatchOp] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class Metrics(BaseModel):
    """Scalar metrics emitted by a Foundry execution, keyed by metric identifier."""

    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.core.Metrics"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "0.1.0"
    ARTIFACT_KIND: ClassVar[Literal["foundry.metrics"]] = "foundry.metrics"
    ARTIFACT_MEDIA_TYPE: ClassVar[Literal["application/json"]] = "application/json"

    model_config = ConfigDict(extra="forbid")

    values: dict[str, float | int | str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ModelOutputs(BaseModel):
    """Per-model outputs needed to recompute metrics under paired tests and resampling."""

    model_config = ConfigDict(extra="forbid")

    model_id: str
    y_pred: list[bool | int | float | str] | None = None
    y_score: list[float] | list[list[float]] | None = None
    per_example_loss: dict[str, list[float]] | None = None


class MetricObservationBundle(BaseModel):
    """Per-example observations required for paired metric validation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    dataset_id: str
    task: Literal["binary", "multiclass", "multilabel", "regression"]
    sample_ids: list[str] = Field(default_factory=list)
    y_true: list[bool | int | float | str]
    models: dict[str, ModelOutputs] = Field(default_factory=dict)
    sample_weight: list[float] | None = None
    strata: dict[str, list[bool | int | float | str]] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_shapes(self) -> MetricObservationBundle:
        n_samples = len(self.y_true)
        if n_samples == 0:
            raise ValueError("MetricObservationBundle requires at least one observation")
        if self.sample_ids:
            if len(self.sample_ids) != n_samples:
                raise ValueError("sample_ids length must match y_true length")
        else:
            self.sample_ids = [f"row_{index}" for index in range(n_samples)]
        if self.sample_weight is not None and len(self.sample_weight) != n_samples:
            raise ValueError("sample_weight length must match y_true length")
        if self.strata is not None:
            for key, values in self.strata.items():
                if len(values) != n_samples:
                    raise ValueError(f"strata[{key!r}] length must match y_true length")
        if not self.models:
            raise ValueError("MetricObservationBundle requires at least one model output")
        for model_id, outputs in self.models.items():
            if outputs.y_pred is not None and len(outputs.y_pred) != n_samples:
                raise ValueError(f"models[{model_id!r}].y_pred length must match y_true")
            if outputs.y_score is not None and len(outputs.y_score) != n_samples:
                raise ValueError(f"models[{model_id!r}].y_score length must match y_true")
            if outputs.per_example_loss is not None:
                for metric_id, losses in outputs.per_example_loss.items():
                    if len(losses) != n_samples:
                        raise ValueError(
                            f"models[{model_id!r}].per_example_loss[{metric_id!r}] length "
                            "must match y_true"
                        )
        return self


class ConstraintViolation(BaseModel):
    """Constraint violation public type."""

    model_config = ConfigDict(extra="forbid")

    constraint_id: str
    severity: Literal["hard", "soft"]
    slot_id: str
    operator: Literal["<", "<=", ">", ">=", "==", "!="]
    expected: str
    actual: str
    violated: bool
    penalty: Decimal | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)


class ConstraintReport(BaseModel):
    """Constraint-evaluation outcome summarizing hard and soft violations for a run."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    ok: bool
    hard_fail: bool = False
    constraint_mode: str = "hard_soft_v1"
    total_constraints: int = 0
    violations: list[ConstraintViolation] = Field(default_factory=list)
    penalty_total: Decimal | None = None
    notes: list[str] = Field(default_factory=list)


class SimulationResult(BaseModel):
    """Top-level execution artifact tying plans, metrics, traces, and optional reports together."""

    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.core.SimulationResult"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.4"
    ARTIFACT_KIND: ClassVar[Literal["foundry.simulation_result"]] = "foundry.simulation_result"
    ARTIFACT_MEDIA_TYPE: ClassVar[Literal["application/json"]] = "application/json"

    LEGACY_ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.3"

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.3", pattern=r"^\d+\.\d+$")
    exec_plan_ref: ExecPlanRef
    metrics_ref: MetricsRef
    metric_observation_bundle_ref: MetricObservationBundleRef | None = None
    state_snapshot_ref: StateSnapshotRef | None = None
    environment_ref: EnvironmentManifestRef | None = None
    environment_fingerprint: str | None = None
    trace_slice_ref: TraceSliceRef | None = None
    uncertainty_envelopes: Mapping[str, UncertaintyEnvelopeRef] | None = None
    distributional_report_ref: DistributionalReportRef | None = None
    welfare_bundle_ref: WelfareBundleRef | None = None
    welfare_bound_refs: Mapping[str, WelfareBoundReportRef] | None = None
    metric_validation_report_ref: MetricValidationReportRef | None = None
    fairness_audit_report_ref: FairnessAuditReportRef | None = None
    propagation_config_ref: ArtifactRef | None = None
    propagation_report_ref: ArtifactRef | None = None
    feedback_result_ref: FeedbackResultRef | None = None
    identifiability_diagnostic_ref: IdentifiabilityDiagnosticRef | None = None
    execution_input_basis_ref: FoundryExecutionInputBasisRef | None = None
    execution_source_status: Literal["not_recorded", "single_step_basis", "feedback_uncomposed"] = (
        "not_recorded"
    )
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_execution_source_basis(self) -> SimulationResult:
        if self.schema_version == "1.4":
            if self.execution_source_status == "single_step_basis":
                if self.execution_input_basis_ref is None or self.feedback_result_ref is not None:
                    raise ValueError("single_step_source_basis_requires_basis_without_feedback")
            elif self.execution_source_status == "feedback_uncomposed":
                if self.execution_input_basis_ref is not None or self.feedback_result_ref is None:
                    raise ValueError("feedback_source_status_requires_feedback_without_basis")
            elif self.execution_input_basis_ref is not None:
                raise ValueError("execution_basis_ref_requires_single_step_status")
        else:
            if self.execution_input_basis_ref is not None:
                raise ValueError("execution_basis_ref_requires_simulation_result_schema_1_4")
            if self.execution_source_status != "not_recorded":
                raise ValueError("execution_source_status_requires_simulation_result_schema_1_4")
        return self

    def to_artifact_payload(self) -> dict[str, Any]:
        """Project only the fields supported by this result's declared artifact version.

        Schema 1.3 is the frozen historical shape. The execution-basis fields belong
        only to schema 1.4; they are omitted from legacy bytes and are never promoted
        by relabeling a newer result. Unsupported historical versions must be migrated
        through an explicit projection rather than serialized under a guessed schema.
        """
        if self.schema_version == self.LEGACY_ARTIFACT_SCHEMA_VERSION:
            return self.model_dump(
                mode="json",
                exclude={"execution_input_basis_ref", "execution_source_status"},
            )
        if self.schema_version == self.ARTIFACT_SCHEMA_VERSION:
            return self.model_dump(mode="json")
        raise ValueError("unsupported_simulation_result_artifact_schema_version")
