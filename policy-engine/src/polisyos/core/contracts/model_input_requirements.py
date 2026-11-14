"""Exact selected-model inputs carried from preflight to acquisition routing."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactStore,
    InputRef,
    artifact_ref_identity_key,
    ensure_ir_artifact_store,
    input_ref_from_artifact_ref,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.ir.registry import ArtifactRefModel
from polisyos.ir.trinity import load_trinity_bundle_artifact

from .entity_axis import SelectedEntityAxis
from .foundry import (
    ExecPlanRef,
    FoundryInputBindings,
    FoundryInputBindingsRef,
    ParameterOverrideBundleRef,
    ProgramGraph,
    ProgramGraphRef,
    StateSnapshotRef,
)
from .model_input_period_steps import (
    ModelInputPeriodStepProfile,
    ModelInputStepScope,
    derive_model_input_step_scopes,
)
from .variable_binding import (
    MeasurementBindingProfile,
    MeasurementBindingProfileRef,
    ModelInputScope,
    VariableRepresentation,
    VariableRepresentationRef,
    VariableSemanticDefinition,
    VariableSemanticDefinitionRef,
    load_variable_representation,
)


class _ModelInputContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ModelInputContext(_ModelInputContract):
    """Selected candidate and its originating problem/run basis."""

    run_id: str = Field(min_length=1, strict=True)
    candidate_id: str = Field(min_length=1, strict=True)
    candidate_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$", strict=True)
    design_problem_ref: str = Field(min_length=1, strict=True)
    candidate_source_ref: ArtifactRef | None = None
    context_job_ref: ArtifactRef | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @model_validator(mode="after")
    def _selected_source_ref(self) -> ModelInputContext:
        if self.candidate_source_ref is not None and (
            self.candidate_source_ref.media_type != "application/json"
            or self.candidate_source_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("model_input_candidate_source_ref_unselected")
        if self.context_job_ref is not None and (
            self.context_job_ref.kind != "runtime.quality.cycle_substrate_context_job"
            or self.context_job_ref.media_type != "application/json"
            or self.context_job_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("model_input_context_job_ref_unselected")
        return self


class ModelInputPhysicalEncoding(_ModelInputContract):
    """Model-owned physical representation of the required input value."""

    shape: tuple[Annotated[int, Field(gt=0, strict=True)], ...]
    dtype: Literal["float32", "float64"]
    max_absolute_error: Decimal = Field(ge=0, allow_inf_nan=False, strict=True)


class ModelInputPort(_ModelInputContract):
    """The model owner's semantic contract for a concrete external input."""

    port_id: str = Field(min_length=1, strict=True)
    slot_id: str = Field(min_length=1, strict=True)
    carrier: Literal["state_path", "method_input"] = Field(
        default="state_path", exclude_if=lambda value: value == "state_path"
    )
    state_path: str | None = Field(
        default=None, min_length=1, strict=True, exclude_if=lambda v: v is None
    )
    unit_id: str = Field(min_length=1, strict=True)
    purpose: Literal["initial_state", "simulation_input", "calibration", "outcome_validation"]
    semantic_definition_ref: VariableSemanticDefinitionRef
    representation_ref: VariableRepresentationRef
    binding_profile_ref: MeasurementBindingProfileRef
    scope: ModelInputScope
    entity_axis_ref: ArtifactRef | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    period_step_profile: ModelInputPeriodStepProfile | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    physical_encoding: ModelInputPhysicalEncoding | None = None

    @model_validator(mode="after")
    def _executable_encoding(self) -> ModelInputPort:
        if (self.carrier == "state_path") != (self.state_path is not None):
            raise ValueError("model_input_port_carrier_mismatch")
        if self.carrier == "method_input" and self.purpose != "simulation_input":
            raise ValueError("model_input_port_method_purpose_invalid")
        if self.entity_axis_ref is not None and (
            self.carrier != "method_input"
            or self.entity_axis_ref.kind != SelectedEntityAxis.ARTIFACT_KIND
            or self.entity_axis_ref.media_type != "application/json"
            or self.entity_axis_ref.manifest_profile_sha256 is None
            or self.physical_encoding is None
            or len(self.physical_encoding.shape) != 1
        ):
            raise ValueError("model_input_port_entity_axis_invalid")
        if self.period_step_profile is not None and (
            self.carrier != "method_input"
            or self.purpose != "simulation_input"
            or self.scope.period_basis != "calendar_year"
        ):
            raise ValueError("model_input_port_period_step_profile_invalid")
        if self.purpose in {"initial_state", "simulation_input"} and self.physical_encoding is None:
            raise ValueError("model_input_port_physical_encoding_missing")
        return self


def _verify_unique_ports(ports: tuple[ModelInputPort, ...]) -> None:
    execution_ports = tuple(
        port for port in ports if port.purpose in {"initial_state", "simulation_input"}
    )
    if (
        len({port.port_id for port in ports}) != len(ports)
        or len({port.slot_id for port in execution_ports}) != len(execution_ports)
        or len({port.state_path for port in execution_ports if port.state_path is not None})
        != sum(port.state_path is not None for port in execution_ports)
    ):
        raise ValueError("model_input_interface_duplicate_port")


class ModelInputPortDeclaration(_ModelInputContract):
    """Ports selected by a model before graph and plan compilation."""

    ARTIFACT_KIND: ClassVar[str] = "ir.model_input_port_declaration"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.ir.ModelInputPortDeclaration"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.2"
    ARTIFACT_SCHEMA_VERSIONS: ClassVar[tuple[str, ...]] = ("1.0", "1.1", "1.2")

    schema_version: Literal["1.0", "1.1", "1.2"] = "1.0"
    ports: tuple[ModelInputPort, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_ports(self) -> ModelInputPortDeclaration:
        _verify_unique_ports(self.ports)
        if self.schema_version == "1.0" and any(p.carrier == "method_input" for p in self.ports):
            raise ValueError("model_input_declaration_version_mismatch")
        if self.schema_version != "1.2" and any(
            p.period_step_profile is not None or p.entity_axis_ref is not None for p in self.ports
        ):
            raise ValueError("model_input_declaration_version_mismatch")
        if self.schema_version == "1.2" and any(
            p.carrier == "method_input"
            and p.physical_encoding is not None
            and p.physical_encoding.shape != ()
            and p.entity_axis_ref is None
            for p in self.ports
        ):
            raise ValueError("model_input_declaration_method_vector_axis_missing")
        return self


class ProgramGraphInputInterface(_ModelInputContract):
    """One model-owned semantic port declaration for exact executable refs."""

    ARTIFACT_KIND: ClassVar[str] = "runtime.quality.program_graph_input_interface"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.runtime.quality.ProgramGraphInputInterface"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.2"
    ARTIFACT_SCHEMA_VERSIONS: ClassVar[tuple[str, ...]] = ("1.0", "1.1", "1.2")

    schema_version: Literal["1.0", "1.1", "1.2"] = "1.0"
    program_graph_ref: ProgramGraphRef
    exec_plan_ref: ExecPlanRef
    registry_bundle_ref: ArtifactRef
    ports: tuple[ModelInputPort, ...]

    declaration_ref: ArtifactRef | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    trinity_bundle_ref: ArtifactRef | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @model_validator(mode="after")
    def _unique_ports_and_refs(self) -> ProgramGraphInputInterface:
        _verify_unique_ports(self.ports)
        if self.schema_version == "1.0" and any(p.carrier == "method_input" for p in self.ports):
            raise ValueError("model_input_interface_version_mismatch")
        if self.schema_version != "1.2" and any(
            p.period_step_profile is not None or p.entity_axis_ref is not None for p in self.ports
        ):
            raise ValueError("model_input_interface_version_mismatch")
        if self.schema_version == "1.2" and any(
            p.carrier == "method_input"
            and p.physical_encoding is not None
            and p.physical_encoding.shape != ()
            and p.entity_axis_ref is None
            for p in self.ports
        ):
            raise ValueError("model_input_interface_method_vector_axis_missing")
        if (self.declaration_ref is None) != (self.trinity_bundle_ref is None) or (
            self.declaration_ref is not None
            and (
                self.declaration_ref.kind != ModelInputPortDeclaration.ARTIFACT_KIND
                or self.trinity_bundle_ref is None
                or self.trinity_bundle_ref.kind != "ir.trinity_bundle"
                or any(
                    ref.media_type != "application/json" or ref.manifest_profile_sha256 is None
                    for ref in (self.declaration_ref, self.trinity_bundle_ref)
                )
            )
        ):
            raise ValueError("model_input_interface_declared_origin_invalid")
        if (
            any(
                ref.media_type != "application/json" or ref.manifest_profile_sha256 is None
                for ref in (self.program_graph_ref, self.exec_plan_ref, self.registry_bundle_ref)
            )
            or self.registry_bundle_ref.kind != "core.registry_bundle"
        ):
            raise ValueError("model_input_interface_ref_unselected")
        return self


class ProgramGraphInputDependency(_ModelInputContract):
    """An actual node read or additive merge of the selected prestate."""

    node_id: str = Field(min_length=1, strict=True)
    kind: Literal["mechanism_read", "additive_prestate", "method_read"]
    first_required_step: int = Field(ge=0, strict=True)
    method_abi_digest: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$", strict=True, exclude_if=lambda v: v is None
    )
    required_steps: tuple[Annotated[int, Field(ge=0, strict=True)], ...] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @model_validator(mode="after")
    def _method_digest(self) -> ProgramGraphInputDependency:
        if (self.kind == "method_read") != (self.method_abi_digest is not None):
            raise ValueError("model_input_dependency_method_digest_mismatch")
        if self.required_steps is not None and (
            self.kind != "method_read"
            or not self.required_steps
            or tuple(sorted(set(self.required_steps))) != self.required_steps
            or self.first_required_step != self.required_steps[0]
        ):
            raise ValueError("model_input_dependency_required_steps_invalid")
        return self


class ModelInputObligation(_ModelInputContract):
    """A missing value required by the selected execution, scoped for routing."""

    ARTIFACT_KIND: ClassVar[str] = "runtime.quality.model_input_obligation"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.runtime.quality.ModelInputObligation"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.2"
    ARTIFACT_SCHEMA_VERSIONS: ClassVar[tuple[str, ...]] = ("1.0", "1.1", "1.2")

    schema_version: Literal["1.0", "1.1", "1.2"] = "1.0"
    authority_purpose: Literal["candidate_acquisition_routing_only"] = (
        "candidate_acquisition_routing_only"
    )
    context: ModelInputContext
    interface_ref: ArtifactRef
    program_graph_ref: ProgramGraphRef
    exec_plan_ref: ExecPlanRef
    registry_bundle_ref: ArtifactRef
    input_bindings_ref: FoundryInputBindingsRef
    prestate_ref: StateSnapshotRef
    parameter_override_bundle_ref: ParameterOverrideBundleRef | None = None
    port: ModelInputPort
    dependencies: tuple[ProgramGraphInputDependency, ...] = Field(min_length=1)
    missing_reason: Literal["required_port_input_not_bound"] = "required_port_input_not_bound"

    @model_validator(mode="after")
    def _selected_origin_refs(self) -> ModelInputObligation:
        if self.schema_version == "1.0" and (
            self.port.carrier == "method_input"
            or any(d.kind == "method_read" for d in self.dependencies)
        ):
            raise ValueError("model_input_obligation_version_mismatch")
        has_new_port_semantics = (
            self.port.period_step_profile is not None or self.port.entity_axis_ref is not None
        )
        if self.schema_version != "1.2" and (
            has_new_port_semantics
            or any(dependency.required_steps is not None for dependency in self.dependencies)
        ):
            raise ValueError("model_input_obligation_version_mismatch")
        if self.port.period_step_profile is not None and (
            self.schema_version != "1.2"
            or any(
                dependency.kind != "method_read" or dependency.required_steps is None
                for dependency in self.dependencies
            )
        ):
            raise ValueError("model_input_obligation_step_profile_mismatch")
        if self.port.period_step_profile is None and any(
            dependency.required_steps is not None for dependency in self.dependencies
        ):
            raise ValueError("model_input_obligation_step_profile_mismatch")
        if self.port.carrier == "method_input" and any(
            d.kind != "method_read" for d in self.dependencies
        ):
            raise ValueError("model_input_obligation_method_dependency_mismatch")
        if (
            self.interface_ref.kind != ProgramGraphInputInterface.ARTIFACT_KIND
            or self.registry_bundle_ref.kind != "core.registry_bundle"
            or any(
                ref.media_type != "application/json" or ref.manifest_profile_sha256 is None
                for ref in (
                    self.interface_ref,
                    self.program_graph_ref,
                    self.exec_plan_ref,
                    self.registry_bundle_ref,
                    self.input_bindings_ref,
                    self.prestate_ref,
                )
            )
        ):
            raise ValueError("model_input_obligation_ref_unselected")
        if self.port.purpose not in {"initial_state", "simulation_input"}:
            raise ValueError("model_input_obligation_purpose_not_executable")
        if (
            self.parameter_override_bundle_ref is not None
            and self.parameter_override_bundle_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("model_input_override_ref_unselected")
        if len({(item.node_id, item.kind) for item in self.dependencies}) != len(self.dependencies):
            raise ValueError("model_input_obligation_dependency_duplicate")
        return self


class ProgramGraphInputInvocation(_ModelInputContract):
    """Exact candidate, execution selection and horizon that require input preflight."""

    context: ModelInputContext
    interface_ref: ArtifactRef
    program_graph_ref: ProgramGraphRef
    exec_plan_ref: ExecPlanRef
    registry_bundle_ref: ArtifactRef
    input_bindings_ref: FoundryInputBindingsRef
    steps: tuple[Annotated[int, Field(ge=0, strict=True)], ...] = Field(min_length=1)
    parameter_override_bundle_ref: ParameterOverrideBundleRef | None = None

    @model_validator(mode="after")
    def _selected_inputs(self) -> ProgramGraphInputInvocation:
        if tuple(sorted(set(self.steps))) != self.steps:
            raise ValueError("model_input_execution_steps_invalid")
        if (
            self.interface_ref.kind != ProgramGraphInputInterface.ARTIFACT_KIND
            or self.registry_bundle_ref.kind != "core.registry_bundle"
            or any(
                ref is not None
                and (ref.media_type != "application/json" or ref.manifest_profile_sha256 is None)
                for ref in (
                    self.interface_ref,
                    self.program_graph_ref,
                    self.exec_plan_ref,
                    self.registry_bundle_ref,
                    self.input_bindings_ref,
                    self.parameter_override_bundle_ref,
                )
            )
        ):
            raise ValueError("model_input_invocation_ref_unselected")
        return self


class ModelInputObligationSet(_ModelInputContract):
    """One producer invocation's complete read-scope denominator and missing gaps."""

    ARTIFACT_KIND: ClassVar[str] = "runtime.quality.model_input_obligation_set"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.runtime.quality.ModelInputObligationSet"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.2"
    ARTIFACT_SCHEMA_VERSIONS: ClassVar[tuple[str, ...]] = ("1.0", "1.1", "1.2")

    schema_version: Literal["1.0", "1.1", "1.2"] = "1.0"
    authority_purpose: Literal["candidate_acquisition_routing_only"] = (
        "candidate_acquisition_routing_only"
    )
    invocation: ProgramGraphInputInvocation
    prestate_ref: StateSnapshotRef
    supplied_initial_slots: tuple[str, ...]
    obligation_refs: tuple[ArtifactRef, ...]
    required_step_scopes: tuple[ModelInputStepScope, ...] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @model_validator(mode="after")
    def _selected_obligation_refs(self) -> ModelInputObligationSet:
        if self.prestate_ref.manifest_profile_sha256 is None or any(
            ref.kind != ModelInputObligation.ARTIFACT_KIND
            or ref.media_type != "application/json"
            or ref.manifest_profile_sha256 is None
            for ref in self.obligation_refs
        ):
            raise ValueError("model_input_obligation_set_ref_unselected")
        if tuple(sorted(set(self.supplied_initial_slots))) != self.supplied_initial_slots or len(
            {artifact_ref_identity_key(ref) for ref in self.obligation_refs}
        ) != len(self.obligation_refs):
            raise ValueError("model_input_obligation_set_duplicate")
        if self.schema_version == "1.2":
            if self.required_step_scopes is None:
                raise ValueError("model_input_obligation_set_step_scopes_missing")
            identities = tuple((item.port_id, item.step) for item in self.required_step_scopes)
            if identities != tuple(sorted(set(identities))):
                raise ValueError("model_input_obligation_set_step_scopes_invalid")
        elif self.required_step_scopes is not None or (
            "required_step_scopes" in self.model_fields_set
        ):
            raise ValueError("model_input_obligation_set_version_mismatch")
        return self


type _ModelInputArtifact = (
    ModelInputPortDeclaration
    | ProgramGraphInputInterface
    | ModelInputObligation
    | ModelInputObligationSet
)


def _port_inputs(port: ModelInputPort) -> list[InputRef]:
    inputs = [
        input_ref_from_artifact_ref(
            port.semantic_definition_ref, role=f"{port.port_id}.definition"
        ),
        input_ref_from_artifact_ref(port.representation_ref, role=f"{port.port_id}.representation"),
        input_ref_from_artifact_ref(port.binding_profile_ref, role=f"{port.port_id}.profile"),
    ]
    if port.entity_axis_ref is not None:
        inputs.append(
            input_ref_from_artifact_ref(port.entity_axis_ref, role=f"{port.port_id}.axis")
        )
    return inputs


def _graph_inputs(
    origin: ProgramGraphInputInterface | ProgramGraphInputInvocation | ModelInputObligation,
) -> list[InputRef]:
    return [
        input_ref_from_artifact_ref(origin.program_graph_ref, role="selected_program_graph"),
        input_ref_from_artifact_ref(origin.exec_plan_ref, role="selected_exec_plan"),
        input_ref_from_artifact_ref(origin.registry_bundle_ref, role="selected_registry_bundle"),
    ]


def _artifact_inputs(value: _ModelInputArtifact) -> list[InputRef]:
    if isinstance(value, ModelInputPortDeclaration):
        return [edge for port in value.ports for edge in _port_inputs(port)]
    if isinstance(value, ProgramGraphInputInterface):
        inputs = _graph_inputs(value)
        if value.declaration_ref is not None and value.trinity_bundle_ref is not None:
            inputs.extend(
                (
                    input_ref_from_artifact_ref(
                        value.declaration_ref, role="model_input_declaration"
                    ),
                    input_ref_from_artifact_ref(value.trinity_bundle_ref, role="selected_trinity"),
                )
            )
        for port in value.ports:
            inputs.extend(_port_inputs(port))
        return inputs
    origin = value.invocation if isinstance(value, ModelInputObligationSet) else value
    inputs = _graph_inputs(origin)
    for ref, role in (
        (origin.context.candidate_source_ref, "selected_candidate_source"),
        (origin.context.context_job_ref, "selected_context_job"),
        (origin.parameter_override_bundle_ref, "selected_parameter_overrides"),
        (origin.interface_ref, "model_input_interface"),
        (origin.input_bindings_ref, "selected_input_bindings"),
    ):
        if ref is not None:
            inputs.append(input_ref_from_artifact_ref(ref, role=role))
    inputs.append(input_ref_from_artifact_ref(value.prestate_ref, role="selected_prestate"))
    if isinstance(value, ModelInputObligationSet):
        inputs.extend(
            input_ref_from_artifact_ref(ref, role="model_input_obligation")
            for ref in value.obligation_refs
        )
    else:
        inputs.extend(_port_inputs(value.port))
    return inputs


def _persist(store: ArtifactStore, value: _ModelInputArtifact) -> ArtifactRef:
    ref = store.put_json(
        value,
        PutOptions(
            kind=value.ARTIFACT_KIND,
            media_type=value.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name=value.ARTIFACT_SCHEMA_NAME, version=value.schema_version),
            inputs=_artifact_inputs(value),
        ),
        return_selected_profile=True,
    )
    if ref.manifest_profile_sha256 is None:
        raise ValueError("model_input_artifact_write_unselected")
    return ref


def _load[ArtifactT: _ModelInputArtifact](
    store: ArtifactStore, ref: ArtifactRef, model: type[ArtifactT]
) -> ArtifactT:
    if ref.manifest_profile_sha256 is None:
        raise ValueError("model_input_artifact_ref_unselected")
    value = validate_core_model_json_artifact(model, store, ref)
    if store.get_manifest(ref).inputs != _artifact_inputs(value):
        raise ValueError("model_input_artifact_lineage_mismatch")
    return value


def persist_model_input_port_declaration(
    store: ArtifactStore, declaration: ModelInputPortDeclaration
) -> ArtifactRef:
    """Write model-owned port semantics before compiling a graph that uses them."""
    ref = _persist(store, declaration)
    if load_model_input_port_declaration(store, ref) != declaration:
        raise ValueError("model_input_port_declaration_readback_mismatch")
    return ref


def load_model_input_port_declaration(
    store: ArtifactStore, ref: ArtifactRef
) -> ModelInputPortDeclaration:
    """Read the selected model owner's declaration and exact semantic inputs."""
    return _load(store, ref, ModelInputPortDeclaration)


def persist_program_graph_input_interface(
    store: ArtifactStore, interface: ProgramGraphInputInterface
) -> ArtifactRef:
    """Store the exact selected model/interface declaration with its lineage."""
    ref = _persist(store, interface)
    if load_program_graph_input_interface(store, ref) != interface:
        raise ValueError("model_input_interface_readback_mismatch")
    return ref


def load_program_graph_input_interface(
    store: ArtifactStore, ref: ArtifactRef
) -> ProgramGraphInputInterface:
    """Reopen the selected model owner's interface and check its lineage."""
    interface = _load(store, ref, ProgramGraphInputInterface)
    if interface.schema_version == "1.2" and interface.declaration_ref is not None:
        declaration = load_model_input_port_declaration(store, interface.declaration_ref)
        if declaration.schema_version != "1.2" or interface.ports != declaration.ports:
            raise ValueError("model_input_interface_declaration_mismatch")
    return interface


def persist_model_input_obligation(
    store: ArtifactStore, obligation: ModelInputObligation
) -> ArtifactRef:
    """Store the selected model's missing-input observation and verify readback."""
    ref = _persist(store, obligation)
    if load_model_input_obligation(store, ref) != obligation:
        raise ValueError("model_input_obligation_readback_mismatch")
    return ref


def load_model_input_obligation(store: ArtifactStore, ref: ArtifactRef) -> ModelInputObligation:
    """Reopen the selected obligation and reconcile its interface identity."""
    obligation = _load(store, ref, ModelInputObligation)
    interface = load_program_graph_input_interface(store, obligation.interface_ref)
    if (
        obligation.port not in interface.ports
        or artifact_ref_identity_key(obligation.program_graph_ref)
        != artifact_ref_identity_key(interface.program_graph_ref)
        or artifact_ref_identity_key(obligation.exec_plan_ref)
        != artifact_ref_identity_key(interface.exec_plan_ref)
        or artifact_ref_identity_key(obligation.registry_bundle_ref)
        != artifact_ref_identity_key(interface.registry_bundle_ref)
    ):
        raise ValueError("model_input_obligation_interface_mismatch")
    bindings = validate_core_model_json_artifact(
        FoundryInputBindings, store, obligation.input_bindings_ref
    )
    if artifact_ref_identity_key(bindings.bound_state_snapshot_ref) != artifact_ref_identity_key(
        obligation.prestate_ref
    ) or artifact_ref_identity_key(bindings.registry_bundle_ref) != artifact_ref_identity_key(
        obligation.registry_bundle_ref
    ):
        raise ValueError("model_input_obligation_prestate_mismatch")
    graph = validate_core_model_json_artifact(ProgramGraph, store, obligation.program_graph_ref)
    nodes = {node.node_id: node for node in graph.nodes}
    for dependency in obligation.dependencies:
        node = nodes.get(dependency.node_id)
        if node is None:
            raise ValueError("model_input_obligation_dependency_mismatch")
        if dependency.kind == "method_read":
            if node.node_kind != "method":
                raise ValueError("model_input_obligation_dependency_mismatch")
            referenced_slots = node.inputs
        else:
            if node.op is None or node.op.op_kind != "apply_mechanism":
                raise ValueError("model_input_obligation_dependency_mismatch")
            referenced_slots = node.inputs if dependency.kind == "mechanism_read" else node.outputs
        if obligation.port.slot_id not in referenced_slots:
            raise ValueError("model_input_obligation_dependency_mismatch")
    return obligation


def model_input_obligation_set_inputs(obligation_set: ModelInputObligationSet) -> list[InputRef]:
    """Derive the complete ordered writer lineage for a selected obligation set."""
    return _artifact_inputs(obligation_set)


def persist_model_input_obligation_set(
    store: ArtifactStore, obligation_set: ModelInputObligationSet
) -> ArtifactRef:
    """Write and reopen the producer's complete set with exact member edges."""
    ref = _persist(store, obligation_set)
    if _load(store, ref, ModelInputObligationSet) != obligation_set:
        raise ValueError("model_input_obligation_set_readback_mismatch")
    return ref


def load_model_input_obligation_set(
    store: ArtifactStore, ref: ArtifactRef
) -> tuple[ModelInputObligationSet, tuple[ModelInputObligation, ...]]:
    """Reopen and reconcile membership; Runtime separately replays the dependencies."""
    obligation_set = _load(store, ref, ModelInputObligationSet)
    members = tuple(
        load_model_input_obligation(store, member_ref)
        for member_ref in obligation_set.obligation_refs
    )
    verify_model_input_obligation_set_members(obligation_set, members)
    _verify_required_step_scope_denominator(store, obligation_set, members)
    return obligation_set, members


def _verify_required_step_scope_denominator(
    store: ArtifactStore,
    obligation_set: ModelInputObligationSet,
    members: tuple[ModelInputObligation, ...],
) -> None:
    """Recompute every selected method port×step read and missing-step gap."""
    interface = load_program_graph_input_interface(store, obligation_set.invocation.interface_ref)
    graph = validate_core_model_json_artifact(
        ProgramGraph, store, obligation_set.invocation.program_graph_ref
    )
    method_ports = tuple(
        port
        for port in interface.ports
        if port.carrier == "method_input"
        and any(node.node_kind == "method" and port.slot_id in node.inputs for node in graph.nodes)
    )
    temporal_ports = tuple(port for port in method_ports if port.period_step_profile is not None)
    advanced_port_semantics = any(
        port.period_step_profile is not None or port.entity_axis_ref is not None
        for port in method_ports
    )
    bindings = validate_core_model_json_artifact(
        FoundryInputBindings, store, obligation_set.invocation.input_bindings_ref
    )
    versioned_step_bindings = bindings.schema_version == "1.5"

    if (
        method_ports
        and len(obligation_set.invocation.steps) != 1
        and len(temporal_ports) != len(method_ports)
    ):
        raise ValueError("model_input_method_temporal_profile_missing")
    if temporal_ports and (
        interface.schema_version != "1.2"
        or obligation_set.schema_version != "1.2"
        or interface.trinity_bundle_ref is None
        or interface.declaration_ref is None
    ):
        raise ValueError("model_input_temporal_profile_version_mismatch")
    if advanced_port_semantics and (
        interface.schema_version != "1.2" or obligation_set.schema_version != "1.2"
    ):
        raise ValueError("model_input_port_12_semantics_version_mismatch")
    if not (advanced_port_semantics or versioned_step_bindings):
        if obligation_set.schema_version == "1.2" and obligation_set.required_step_scopes:
            raise ValueError("model_input_obligation_set_step_scope_denominator_mismatch")
        return
    if obligation_set.schema_version != "1.2":
        raise ValueError("model_input_obligation_set_step_scopes_missing")

    time_semantics = None
    if temporal_ports:
        trinity_ref = ArtifactRefModel.model_validate(
            interface.trinity_bundle_ref.model_dump(mode="python")
        )
        bundle = load_trinity_bundle_artifact(ensure_ir_artifact_store(store), trinity_ref)
        time_semantics = bundle.model_spec.time_semantics
        selected_declaration_ref = bundle.model_spec.model_input_port_declaration_ref
        if time_semantics is None:
            raise ValueError("model_input_temporal_profile_time_semantics_missing")
        if (
            artifact_ref_identity_key(graph.ir_ref) != artifact_ref_identity_key(trinity_ref)
            or selected_declaration_ref is None
            or artifact_ref_identity_key(selected_declaration_ref)
            != artifact_ref_identity_key(interface.declaration_ref)
        ):
            raise ValueError("model_input_temporal_profile_selected_model_mismatch")

    expected: list[ModelInputStepScope] = []
    expected_by_identity: dict[tuple[str, int], ModelInputStepScope] = {}
    for port in method_ports:
        if port.period_step_profile is not None:
            if time_semantics is None:
                raise ValueError("model_input_temporal_profile_time_semantics_missing")
            scopes = derive_model_input_step_scopes(
                port.period_step_profile,
                port_id=port.port_id,
                scope_envelope=port.scope,
                time_semantics=time_semantics,
                steps=obligation_set.invocation.steps,
            )
        else:
            if len(obligation_set.invocation.steps) != 1:
                raise ValueError("model_input_method_temporal_profile_missing")
            scopes = (
                ModelInputStepScope(
                    port_id=port.port_id,
                    step=obligation_set.invocation.steps[0],
                    scope=port.scope,
                ),
            )
        expected.extend(scopes)
        expected_by_identity.update({(scope.port_id, scope.step): scope for scope in scopes})
    expected_rows = tuple(sorted(expected, key=lambda item: (item.port_id, item.step)))
    if obligation_set.required_step_scopes != expected_rows:
        raise ValueError("model_input_obligation_set_step_scope_denominator_mismatch")

    required_port_ids = {port.port_id for port in method_ports}
    supplied_by_port: dict[str, set[int]] = {port_id: set() for port_id in required_port_ids}
    selected_step_inputs = bindings.selected_method_input_steps or ()
    temporal_port_ids = {port.port_id for port in temporal_ports}
    axis_port_ids = {port.port_id for port in method_ports if port.entity_axis_ref is not None}
    if bindings.schema_version == "1.4" and any(
        item.port_id in temporal_port_ids or item.port_id in axis_port_ids
        for item in (bindings.selected_method_inputs or ())
    ):
        raise ValueError("model_input_method_input_step_scope_missing")
    for selected in selected_step_inputs:
        identity = (selected.input.port_id, selected.step_scope.step)
        expected_scope = expected_by_identity.get(identity)
        if expected_scope is None:
            raise ValueError("model_input_method_input_step_scope_unexpected")
        if selected.step_scope != expected_scope:
            raise ValueError("model_input_method_input_step_scope_mismatch")
        supplied_by_port[selected.input.port_id].add(selected.step_scope.step)

    for member in members:
        required_scopes = tuple(
            scope for scope in expected_rows if scope.port_id == member.port.port_id
        )
        if member.port.period_step_profile is None:
            if any(dependency.required_steps is not None for dependency in member.dependencies):
                raise ValueError("model_input_obligation_step_scope_mismatch")
            continue
        if member.schema_version != "1.2" or not required_scopes:
            raise ValueError("model_input_obligation_step_scope_mismatch")
        missing_steps = tuple(
            scope.step
            for scope in required_scopes
            if scope.step not in supplied_by_port[member.port.port_id]
        )
        if not missing_steps or any(
            dependency.required_steps != missing_steps for dependency in member.dependencies
        ):
            raise ValueError("model_input_obligation_step_scope_mismatch")

    member_port_ids = {member.port.port_id for member in members}
    for port_id, supplied_steps in supplied_by_port.items():
        required_steps = {scope.step for scope in expected_rows if scope.port_id == port_id}
        missing_steps = required_steps - supplied_steps
        if bool(missing_steps) != (port_id in member_port_ids):
            raise ValueError("model_input_obligation_step_scope_mismatch")


def verify_model_input_obligation_set_members(
    obligation_set: ModelInputObligationSet, members: tuple[ModelInputObligation, ...]
) -> None:
    """Check consistency of members already reopened at the set's exact refs."""
    invocation = obligation_set.invocation
    slots = tuple(member.port.slot_id for member in members)
    if (
        len(members) != len(obligation_set.obligation_refs)
        or slots != tuple(sorted(set(slots)))
        or set(slots).intersection(obligation_set.supplied_initial_slots)
    ):
        raise ValueError("model_input_obligation_set_membership_mismatch")
    for member in members:
        if obligation_set.schema_version == "1.0" and member.schema_version != "1.0":
            raise ValueError("model_input_obligation_set_version_mismatch")
        if (
            member.context != invocation.context
            or member.parameter_override_bundle_ref != invocation.parameter_override_bundle_ref
            or any(item.first_required_step not in invocation.steps for item in member.dependencies)
            or any(
                artifact_ref_identity_key(actual) != artifact_ref_identity_key(expected)
                for actual, expected in (
                    (member.interface_ref, invocation.interface_ref),
                    (member.program_graph_ref, invocation.program_graph_ref),
                    (member.exec_plan_ref, invocation.exec_plan_ref),
                    (member.registry_bundle_ref, invocation.registry_bundle_ref),
                    (member.input_bindings_ref, invocation.input_bindings_ref),
                    (member.prestate_ref, obligation_set.prestate_ref),
                )
            )
        ):
            raise ValueError("model_input_obligation_set_origin_mismatch")


def verify_model_input_port_semantics(
    store: ArtifactStore, port: ModelInputPort
) -> VariableRepresentation:
    """Reopen the selected target definition, representation and binding profile."""
    validate_core_model_json_artifact(
        VariableSemanticDefinition, store, port.semantic_definition_ref
    )
    representation = load_variable_representation(store, port.representation_ref)
    profile = validate_core_model_json_artifact(
        MeasurementBindingProfile, store, port.binding_profile_ref
    )
    if port.entity_axis_ref is not None:
        axis = validate_core_model_json_artifact(SelectedEntityAxis, store, port.entity_axis_ref)
        if (
            port.physical_encoding is None
            or len(port.physical_encoding.shape) != 1
            or axis.cardinality != port.physical_encoding.shape[0]
        ):
            raise ValueError("model_input_port_entity_axis_cardinality_mismatch")
    if (
        artifact_ref_identity_key(representation.semantic_definition_ref)
        != artifact_ref_identity_key(port.semantic_definition_ref)
        or representation.unit_id != port.unit_id
        or (
            representation.population_ref is not None
            and representation.population_ref != port.scope.population_ref
        )
        or any(getattr(representation, axis.value) is None for axis in profile.required_axes)
    ):
        raise ValueError("model_input_port_semantics_mismatch")
    return representation
