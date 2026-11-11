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
    input_ref_from_artifact_ref,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import PutOptions

from .foundry import (
    ExecPlanRef,
    FoundryInputBindings,
    FoundryInputBindingsRef,
    ParameterOverrideBundleRef,
    ProgramGraph,
    ProgramGraphRef,
    StateSnapshotRef,
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
    state_path: str = Field(min_length=1, strict=True)
    unit_id: str = Field(min_length=1, strict=True)
    purpose: Literal["initial_state", "simulation_input", "calibration", "outcome_validation"]
    semantic_definition_ref: VariableSemanticDefinitionRef
    representation_ref: VariableRepresentationRef
    binding_profile_ref: MeasurementBindingProfileRef
    scope: ModelInputScope
    physical_encoding: ModelInputPhysicalEncoding | None = None

    @model_validator(mode="after")
    def _executable_encoding(self) -> ModelInputPort:
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
        or len({port.state_path for port in execution_ports}) != len(execution_ports)
    ):
        raise ValueError("model_input_interface_duplicate_port")


class ModelInputPortDeclaration(_ModelInputContract):
    """Ports selected by a model before graph and plan compilation."""

    ARTIFACT_KIND: ClassVar[str] = "ir.model_input_port_declaration"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.ir.ModelInputPortDeclaration"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"

    schema_version: Literal["1.0"] = "1.0"
    ports: tuple[ModelInputPort, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_ports(self) -> ModelInputPortDeclaration:
        _verify_unique_ports(self.ports)
        return self


class ProgramGraphInputInterface(_ModelInputContract):
    """One model-owned semantic port declaration for exact executable refs."""

    ARTIFACT_KIND: ClassVar[str] = "runtime.quality.program_graph_input_interface"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.runtime.quality.ProgramGraphInputInterface"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"

    schema_version: Literal["1.0"] = "1.0"
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
    kind: Literal["mechanism_read", "additive_prestate"]
    first_required_step: int = Field(ge=0, strict=True)


class ModelInputObligation(_ModelInputContract):
    """A missing value required by the selected execution, scoped for routing."""

    ARTIFACT_KIND: ClassVar[str] = "runtime.quality.model_input_obligation"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.runtime.quality.ModelInputObligation"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"

    schema_version: Literal["1.0"] = "1.0"
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
    """One producer invocation's complete selected missing-input denominator."""

    ARTIFACT_KIND: ClassVar[str] = "runtime.quality.model_input_obligation_set"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.runtime.quality.ModelInputObligationSet"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"

    schema_version: Literal["1.0"] = "1.0"
    authority_purpose: Literal["candidate_acquisition_routing_only"] = (
        "candidate_acquisition_routing_only"
    )
    invocation: ProgramGraphInputInvocation
    prestate_ref: StateSnapshotRef
    supplied_initial_slots: tuple[str, ...]
    obligation_refs: tuple[ArtifactRef, ...]

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
        return self


type _ModelInputArtifact = (
    ModelInputPortDeclaration
    | ProgramGraphInputInterface
    | ModelInputObligation
    | ModelInputObligationSet
)


def _port_inputs(port: ModelInputPort) -> list[InputRef]:
    return [
        input_ref_from_artifact_ref(
            port.semantic_definition_ref, role=f"{port.port_id}.definition"
        ),
        input_ref_from_artifact_ref(port.representation_ref, role=f"{port.port_id}.representation"),
        input_ref_from_artifact_ref(port.binding_profile_ref, role=f"{port.port_id}.profile"),
    ]


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
            schema=SchemaInfo(
                name=value.ARTIFACT_SCHEMA_NAME, version=value.ARTIFACT_SCHEMA_VERSION
            ),
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
    return _load(store, ref, ProgramGraphInputInterface)


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
        if node is None or node.op is None or node.op.op_kind != "apply_mechanism":
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
    return obligation_set, members


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
