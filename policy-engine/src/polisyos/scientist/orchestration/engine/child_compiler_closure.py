"""Bounded child closure for actual Trinity compiler and single-step output artifacts.

This extends ``child_output_closure`` with the compiler's existing Core/IR
contracts and producers. It establishes reference closure, not producer
appointment, execution authority, or permission to read another artifact.
Opaque method parameters and nonnumeric mechanism parameters are deliberately
unsupported until their own reference contracts can be established.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import TYPE_CHECKING

from pydantic import BaseModel, TypeAdapter, ValidationError

from polisyos.core.artifacts.canonical_profile import (
    CoreJsonReadBoundsRefusalError,
    CoreJsonReadLimits,
    read_core_input_manifest_profile_bounded,
    read_core_json_artifact_bounded,
    read_core_manifest_profile_bounded,
    validate_core_model_bounded_read,
)
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
)
from polisyos.core.compiler.report import CompileReport
from polisyos.core.contracts.foundry import (
    ConstraintReport,
    ExecPlan,
    FoundryExecutionInputBasis,
    LoweredIR,
    Metrics,
    ProgramGraph,
    SimulationResult,
    StateDelta,
    StateSnapshot,
    WelfareBoundReport,
)
from polisyos.ir.governance.policy_spec import ParameterSpec
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorExpr
from polisyos.ir.kernel.time_semantics import TimeSemantics
from polisyos.ir.linker import LinkReport
from polisyos.ir.model_layer.model_spec import EnvironmentConfig
from polisyos.ir.trinity import TrinityBundle

if TYPE_CHECKING:
    from polisyos.core.artifacts.canonical_profile import (
        CoreJsonArtifactBoundedRead,
        CoreJsonManifestBoundedRead,
    )
    from polisyos.core.artifacts.manifest import ArtifactManifest, InputRef
    from polisyos.core.artifacts.protocol import ArtifactReader


_CONTRACTS = {
    "compiler.compile_report": ("polisyos.core.CompileReport", ("1.0", "1.1")),
    "compiler.link_report": ("polisyos.ir.LinkReport", ("1.0",)),
    "foundry.lowered_ir": ("polisyos.foundry.LoweredIR", ("0.2.0",)),
    "foundry.lowered_mechanism_payload": (
        "polisyos.foundry.LoweredMechanismPayload",
        ("0.2.0",),
    ),
    "foundry.program_graph": (ProgramGraph.ARTIFACT_SCHEMA_NAME, ("0.2.0",)),
    "foundry.exec_plan": (ExecPlan.ARTIFACT_SCHEMA_NAME, ("0.2.0",)),
    "foundry.slot_layout": ("polisyos.foundry.SlotLayout", ("1.0",)),
    "foundry.treasury_plan": ("polisyos.foundry.TreasuryPlan", ("1.0",)),
    "foundry.simulation_result": (SimulationResult.ARTIFACT_SCHEMA_NAME, ("1.4",)),
    "foundry.execution_input_basis": (
        FoundryExecutionInputBasis.ARTIFACT_SCHEMA_NAME,
        ("1.0", "1.1"),
    ),
    "foundry.state_snapshot": ("polisyos.core.StateSnapshot", ("2.2.0",)),
    "foundry.state_delta": (StateDelta.ARTIFACT_SCHEMA_NAME, ("0.1.0",)),
    "foundry.metrics": (Metrics.ARTIFACT_SCHEMA_NAME, ("0.1.0",)),
    "foundry.constraint_report": ("polisyos.core.ConstraintReport", ("1.0",)),
    "foundry.welfare_bound_report": ("polisyos.core.WelfareBoundReport", ("1.0",)),
}
_BINARY_CONTRACTS = {
    "foundry.state_blob": "application/x-npz",
    "foundry.patch_value": "application/x-npy",
}

# A contract extension is reviewed before it can silently add an unwalked field.
_FIELDS = {
    "CompileReport": "schema_version ok policy_ref registry_bundle_ref link_report_ref lowered_ir_ref program_graph_ref exec_plan_ref slot_layout_ref treasury_plan_ref semantic_closure_notes notes candidate_rejection",
    "CompileCandidateRejection": "schema_version kind validation_rule reason_code request_sha256 policy_ref registry_bundle_ref link_report_ref",
    "LinkReport": "schema_version ok issues notes",
    "LinkIssue": "severity code message path ids data",
    "LoweredIR": "schema_version ir_ref mechanisms constraints composite_constraints parameter_specs time_semantics environment_config policy_fidelity_level constraint_mode notes",
    "LoweredMechanism": "binding_id mechanism_id intervention_ids effective_params_ref effective_schedule selected_fidelity inputs outputs legacy_kind_alias_used target_selector priority notes",
    "LoweredConstraint": "constraint_id severity slot_id operator expected unit_id penalty aggregation quantile_param weights_slot_id notes",
    "CompositeConstraint": "constraint_id expression slot_refs operator expected severity penalty notes",
    "ParameterSpec": "param_id intervention_id param_path default_value min_value max_value tunable sensitivity_priority",
    "TimeSemantics": "frequency start_date step_count end_date notes",
    "EnvironmentConfig": "params random_seed stochastic parallel_worlds",
    "ProgramGraph": "schema_version ir_ref lowered_ir_ref nodes edges entrypoints notes",
    "ExecPlan": "program_ref order environment_ref environment_fingerprint determinism_tier random_seed nan_guard_enabled policy_fidelity_level constraint_mode mode jit max_steps notes",
    "SlotLayout": "schema_version layout notes",
    "TreasuryPlan": "schema_version root_seed node_salts stream_salts notes",
    "SimulationResult": "schema_version exec_plan_ref metrics_ref metric_observation_bundle_ref state_snapshot_ref environment_ref environment_fingerprint trace_slice_ref uncertainty_envelopes distributional_report_ref welfare_bundle_ref welfare_bound_refs metric_validation_report_ref fairness_audit_report_ref propagation_config_ref propagation_report_ref feedback_result_ref identifiability_diagnostic_ref execution_input_basis_ref execution_source_status notes",
    "FoundryExecutionInputBasis": "schema_version authority_purpose execution_mode request request_fields_set request_exec_config_fields_set exec_plan_ref program_graph_ref trinity_bundle_ref candidate_ref candidate_data_snapshot_ref candidate_registry_bundle_ref input_bindings_ref data_snapshot_ref registered_sql_admission_ref bound_state_snapshot_ref binding_registry_ref compile_registry_ref runtime_registry_ref binding_registry_members compile_registry_members runtime_registry_members base_state_snapshot_ref parameter_override_bundle_ref observed_range_bundle_ref parameter_overrides effective_step effective_seed effective_seed_source effective_mode effective_max_steps effective_determinism_tier effective_nan_guard_enabled effective_jit effective_capture_env",
    "ExecuteRequest": "schema_version exec_plan_ref input_bindings_ref registry_bundle_ref feedback_config_ref parameter_override_bundle_ref observed_range_bundle_ref welfare_bound_mode welfare_bound_required exec_config notes return_selected_profile",
    "FoundryExecConfig": "schema_version seed mode max_steps deterministic capture_env",
    "StateSnapshot": "schema_version state_ref schema_ref step format_version checksum_sha256 entry_count codec lineage_inputs notes layout",
    "StateDelta": "base_ref patch_ref ops notes",
    "PatchOp": "slot_id op value_ref mask_ref mask_scope notes",
    "Metrics": "values notes",
    "ConstraintReport": "schema_version ok hard_fail constraint_mode total_constraints violations penalty_total notes",
    "ConstraintViolation": "constraint_id severity slot_id operator expected actual violated penalty events",
    "WelfareBoundReport": "schema_version mechanism_type node_id mode welfare_loss_lower welfare_loss_upper first_best_lower first_best_upper mechanism_value required_observables status notes",
}


def _shape(value: BaseModel) -> None:
    expected = _FIELDS.get(type(value).__name__)
    if expected is None or set(type(value).model_fields) != set(expected.split()):
        raise ValueError("child_compiler_owner_schema_changed")
    if value.model_extra:
        raise ValueError("child_compiler_untyped_model_extra")


def _numeric(value: object) -> None:
    """Constrain an Any-valued parameter slot without inferring reference names."""
    if value is None or type(value) in (bool, int):
        return
    if type(value) is Decimal and value.is_finite():
        return
    raise ValueError("child_compiler_opaque_value_unsupported")


def _numeric_parameters(value: object) -> None:
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise ValueError("child_compiler_opaque_value_unsupported")
    for item in value.values():
        _numeric_parameter(item)


def _numeric_parameter(value: object) -> None:
    """Accept the IR writer's numeric string without changing its persisted identity."""
    from polisyos.ir.kernel.numbers import DecimalValue

    if type(value) is str:
        try:
            parsed = TypeAdapter(DecimalValue).validate_python(value)
        except ValidationError:
            pass
        else:
            if parsed.is_finite():
                return
        raise ValueError("child_compiler_opaque_value_unsupported")
    _numeric(value)


@dataclass(frozen=True)
class _View:
    read: CoreJsonArtifactBoundedRead
    inputs: dict[str, ArtifactRef]
    edges: tuple[tuple[str, ArtifactRef], ...]


class _Reader:
    def __init__(self, store: ArtifactReader, limits: CoreJsonReadLimits) -> None:
        self.store = store
        self.limits = limits
        self.views: dict[tuple[str, str, str, str | None], _View] = {}
        self.manifest_bytes = 0
        self.payload_bytes = 0
        self.usage_established = True

    def account(self, *, manifest_bytes: int = 0, payload_bytes: int = 0) -> None:
        self.manifest_bytes += manifest_bytes
        self.payload_bytes += payload_bytes

    def manifest_limit(self) -> int:
        return self.limits.max_manifest_bytes

    def json_limits(self, selected: CoreJsonManifestBoundedRead) -> CoreJsonReadLimits:
        return self.limits

    def account_refusal(self, error: CoreJsonReadBoundsRefusalError, *, selection: bool) -> None:
        counts = (
            error.observed_manifest_selection_bytes if selection else 0,
            error.observed_manifest_verification_bytes,
            error.observed_payload_bytes,
        )
        if any(type(count) is not int or count < 0 for count in counts):
            self.usage_established = False
            return
        self.account(manifest_bytes=counts[0] + counts[1], payload_bytes=counts[2])

    def selected_manifest(
        self, ref: ArtifactRef, *, allow_profile_absent: bool = False
    ) -> CoreJsonManifestBoundedRead:
        try:
            return read_core_manifest_profile_bounded(
                self.store,
                ref,
                max_manifest_bytes=self.manifest_limit(),
                allow_profile_absent=allow_profile_absent,
            )
        except CoreJsonReadBoundsRefusalError as exc:
            self.account_refusal(exc, selection=True)
            raise

    def input_manifest(
        self, parent_ref: ArtifactRef, edge: InputRef
    ) -> CoreJsonManifestBoundedRead:
        binary_kind = {
            ("foundry.state_snapshot", "state_blob"): "foundry.state_blob",
            ("foundry.state_delta", "patch_value"): "foundry.patch_value",
            ("foundry.metrics", "patch_value"): "foundry.patch_value",
            ("foundry.constraint_report", "patch_value"): "foundry.patch_value",
        }.get((parent_ref.kind, edge.role))
        if binary_kind is not None:
            if edge.manifest_profile_sha256 is None:
                raise ValueError("child_compiler_selected_profile_required")
            return self.selected_manifest(
                ArtifactRef(
                    artifact_id=edge.artifact_id,
                    kind=binary_kind,
                    media_type=_BINARY_CONTRACTS[binary_kind],
                    manifest_profile_sha256=edge.manifest_profile_sha256,
                ),
                allow_profile_absent=True,
            )
        try:
            return read_core_input_manifest_profile_bounded(
                self.store, edge, max_manifest_bytes=self.manifest_limit()
            )
        except CoreJsonReadBoundsRefusalError as exc:
            self.account_refusal(exc, selection=True)
            raise

    def view(self, ref: ArtifactRef) -> _View:
        from polisyos.core.run.child_custody import _snapshot_selected_ref

        try:
            ref = _snapshot_selected_ref(ref)
        except (PermissionError, ValueError) as exc:
            raise ValueError("child_compiler_selected_profile_required") from exc
        key = artifact_ref_identity_key(ref)
        if key in self.views:
            return self.views[key]
        selected = self.selected_manifest(ref)
        self.account(manifest_bytes=selected.observed_source_bytes)
        contract = _CONTRACTS.get(ref.kind)
        if contract is not None:
            schema = selected.manifest.artifact_schema
            if (
                ref.media_type != "application/json"
                or schema is None
                or schema.name != contract[0]
                or schema.version not in contract[1]
            ):
                raise ValueError("child_compiler_artifact_contract_mismatch")
        try:
            read = read_core_json_artifact_bounded(
                self.store, ref, limits=self.json_limits(selected), manifest_read=selected
            )
        except CoreJsonReadBoundsRefusalError as exc:
            self.account_refusal(exc, selection=False)
            raise
        self.account(
            manifest_bytes=read.observed_manifest_verification_bytes,
            payload_bytes=read.observed_payload_bytes,
        )
        inputs: dict[str, ArtifactRef] = {}
        edges: list[tuple[str, ArtifactRef]] = []
        # Basis aliases are resolved from the canonical typed source enumeration
        # below, including its parents' exact binary-role contracts.
        edges_to_resolve = (
            () if ref.kind == "foundry.execution_input_basis" else selected.manifest.inputs
        )
        for edge in edges_to_resolve:
            repeated_patch = (
                ref.kind in {"foundry.state_delta", "foundry.metrics", "foundry.constraint_report"}
                and edge.role == "patch_value"
            )
            if (edge.role in inputs and not repeated_patch) or not edge.manifest_profile_sha256:
                raise ValueError("child_compiler_input_ambiguous")
            source = self.input_manifest(ref, edge)
            self.account(manifest_bytes=source.observed_source_bytes)
            inputs.setdefault(edge.role, source.effective_ref)
            edges.append((edge.role, source.effective_ref))
        view = _View(read=read, inputs=inputs, edges=tuple(edges))
        self.views[key] = view
        return view

    def typed[ModelT: BaseModel](self, ref: ArtifactRef, model: type[ModelT]) -> ModelT:
        value = validate_core_model_bounded_read(model, self.view(ref).read)
        if model is not TrinityBundle:
            _shape(value)
        return value


class _ExecutionReader(_Reader):
    """Adapt existing bounded Core reads to Foundry's source-admission reader."""

    def __init__(self, store: ArtifactReader, limits: CoreJsonReadLimits) -> None:
        super().__init__(store, limits)
        self.blobs: dict[tuple[str, str, str, str | None], tuple[ArtifactManifest, bytes]] = {}

    def account(self, *, manifest_bytes: int = 0, payload_bytes: int = 0) -> None:
        from polisyos.foundry.execute.api import ExecutionSourceBoundedReadRefusal

        super().account(manifest_bytes=manifest_bytes, payload_bytes=payload_bytes)
        observed = self.manifest_bytes + self.payload_bytes
        if observed > self.limits.max_bytes:
            raise ExecutionSourceBoundedReadRefusal(
                "child_compiler_execution_read_budget_exhausted",
                observed_bytes=observed,
                limit_bytes=self.limits.max_bytes,
            )

    def refuse_budget(self) -> None:
        from polisyos.foundry.execute.api import ExecutionSourceBoundedReadRefusal

        raise ExecutionSourceBoundedReadRefusal(
            "child_compiler_execution_read_budget_exhausted",
            observed_bytes=self.manifest_bytes + self.payload_bytes,
            limit_bytes=self.limits.max_bytes,
        )

    def remaining(self) -> int:
        if not self.usage_established:
            raise ValueError("child_compiler_execution_read_usage_unavailable")
        return self.limits.max_bytes - self.manifest_bytes - self.payload_bytes

    def manifest_limit(self) -> int:
        remaining = self.remaining()
        if remaining < 1:
            self.refuse_budget()
        return min(self.limits.max_manifest_bytes, remaining)

    def json_limits(self, selected: CoreJsonManifestBoundedRead) -> CoreJsonReadLimits:
        reopen_bytes = len(selected.raw_manifest_bytes)
        available_payload = self.remaining() - reopen_bytes
        if available_payload < 1 or selected.manifest.byte_size > available_payload:
            self.refuse_budget()
        return CoreJsonReadLimits(
            max_bytes=min(self.limits.max_bytes, available_payload),
            max_depth=self.limits.max_depth,
            max_elements=self.limits.max_elements,
            max_manifest_bytes=reopen_bytes,
        )

    def blob(self, ref: ArtifactRef) -> tuple[ArtifactManifest, bytes]:
        from polisyos.core.artifacts._integrity_ops import _is_artifact_store_read_usage
        from polisyos.core.run.child_custody import _ManagedStore, _snapshot_selected_ref

        ref = _snapshot_selected_ref(ref)
        key = artifact_ref_identity_key(ref)
        if key in self.blobs:
            return self.blobs[key]
        selected = self.selected_manifest(ref, allow_profile_absent=True)
        self.account(manifest_bytes=selected.observed_source_bytes)
        reopen_bytes = len(selected.raw_manifest_bytes)
        remaining = self.remaining() - reopen_bytes
        if selected.manifest.byte_size > remaining or remaining < 1:
            self.refuse_budget()
        attempt = None
        try:
            if type(self.store) is _ManagedStore:
                method = getattr(self.store, "_read_owned_blob_bounded", None)
                if not callable(method):
                    raise ValueError("child_compiler_guarded_binary_reader_unavailable")
                result = method(ref, manifest_read=selected, max_member_bytes=remaining)
                if type(result) is not tuple or len(result) != 2:
                    raise ValueError("child_compiler_binary_read_usage_unavailable")
                data, usage = result
            else:
                attempt = self.store.open_member_bounded(
                    ref,
                    "blob",
                    max_manifest_bytes=reopen_bytes,
                    expected_manifest_sha256=hashlib.sha256(
                        selected.raw_manifest_bytes
                    ).hexdigest(),
                    max_member_bytes=remaining,
                )
                parts = bytearray()
                with attempt as member:
                    if member.member_size_bytes != selected.manifest.byte_size:
                        raise ValueError("child_compiler_binary_size_mismatch")
                    while len(parts) < member.member_size_bytes:
                        chunk = member.read(min(65_536, member.member_size_bytes - len(parts)))
                        if type(chunk) is not bytes or not chunk:
                            raise ValueError("child_compiler_binary_size_mismatch")
                        parts.extend(chunk)
                    if member.read(1):
                        raise ValueError("child_compiler_binary_size_mismatch")
                data = bytes(parts)
                usage = attempt.usage
        except BaseException:
            refused_usage = getattr(attempt, "usage", None)
            if (
                _is_artifact_store_read_usage(refused_usage)
                and type(refused_usage.observed_source_bytes) is int
                and type(refused_usage.observed_payload_bytes) is int
            ):
                self.account(
                    manifest_bytes=(
                        refused_usage.observed_source_bytes - refused_usage.observed_payload_bytes
                    ),
                    payload_bytes=refused_usage.observed_payload_bytes,
                )
            else:
                self.usage_established = False
            raise
        if (
            type(data) is not bytes
            or not _is_artifact_store_read_usage(usage)
            or usage.observed_source_bytes is None
            or usage.observed_payload_bytes != len(data)
            or usage.payload_integrity_verified is not True
            or len(data) != selected.manifest.byte_size
            or hashlib.sha256(data).hexdigest() != ref.artifact_id.hex
        ):
            raise ValueError("child_compiler_binary_read_integrity_unavailable")
        self.account(
            manifest_bytes=usage.observed_source_bytes - len(data), payload_bytes=len(data)
        )
        self.blobs[key] = (selected.manifest, data)
        return self.blobs[key]

    def read_selected_manifest(self, ref: ArtifactRef) -> tuple[ArtifactManifest, int]:
        before = self.manifest_bytes + self.payload_bytes
        manifest = (
            self.view(ref).read.manifest
            if ref.media_type == "application/json"
            else self.blob(ref)[0]
        )
        return manifest, self.manifest_bytes + self.payload_bytes - before

    def read_edge_manifest(
        self, parent_ref: ArtifactRef, edge: InputRef
    ) -> tuple[ArtifactRef, ArtifactManifest, int]:
        before = self.manifest_bytes + self.payload_bytes
        if edge not in self.view(parent_ref).read.manifest.inputs:
            raise ValueError("child_compiler_source_edge_not_owned")
        selected = self.input_manifest(parent_ref, edge)
        self.account(manifest_bytes=selected.observed_source_bytes)
        manifest, _ = self.read_selected_manifest(selected.effective_ref)
        return selected.effective_ref, manifest, self.manifest_bytes + self.payload_bytes - before

    def read_typed_model(
        self, model: type[BaseModel], ref: ArtifactRef
    ) -> tuple[ArtifactManifest, BaseModel, int, int]:
        before_manifest, before_payload = self.manifest_bytes, self.payload_bytes
        view = self.view(ref)
        value = validate_core_model_bounded_read(model, view.read)
        if type(value).__name__ in _FIELDS:
            _shape(value)
        return (
            view.read.manifest,
            value,
            self.manifest_bytes - before_manifest,
            self.payload_bytes - before_payload,
        )


def _numeric_array_elements(data: bytes, *, limits: CoreJsonReadLimits) -> int:
    """Use NumPy's header reader, then admit only bounded primitive array bytes."""
    import numpy as np

    stream = BytesIO(data)
    try:
        version = np.lib.format.read_magic(stream)
        if version == (1, 0):
            shape, _fortran, dtype = np.lib.format.read_array_header_1_0(
                stream, max_header_size=min(10_000, limits.max_bytes)
            )
        elif version == (2, 0):
            shape, _fortran, dtype = np.lib.format.read_array_header_2_0(
                stream, max_header_size=min(10_000, limits.max_bytes)
            )
        else:
            raise ValueError("child_compiler_array_format_unsupported")
    except (EOFError, ValueError, TypeError) as exc:
        raise ValueError("child_compiler_array_format_unsupported") from exc
    elements = math.prod(shape) if shape else 1
    if (
        len(shape) > limits.max_depth
        or any(type(size) is not int or size < 0 for size in shape)
        or dtype.hasobject
        or dtype.fields is not None
        or dtype.kind not in {"b", "i", "u", "f"}
        or elements > limits.max_elements
        or stream.tell() + elements * dtype.itemsize != len(data)
    ):
        raise ValueError("child_compiler_array_reference_contract_unsupported")
    return elements


def _binary_children(reader: _ExecutionReader, ref: ArtifactRef) -> tuple[ArtifactRef, ...]:
    from zipfile import ZipFile

    from polisyos.foundry.execute._internal.snapshots import _read_npz_entry_count

    manifest, data = reader.blob(ref)
    if (
        ref.media_type != _BINARY_CONTRACTS[ref.kind]
        or manifest.artifact_schema is not None
        or manifest.inputs
    ):
        raise ValueError("child_compiler_binary_contract_mismatch")
    if ref.kind == "foundry.patch_value":
        _numeric_array_elements(data, limits=reader.limits)
    else:
        _read_npz_entry_count(data, max_entries=reader.limits.max_elements)
        elements = 0
        with ZipFile(BytesIO(data)) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or not names:
                raise ValueError("child_compiler_array_format_unsupported")
            for info in archive.infolist():
                if not info.filename.endswith(".npy") or info.file_size > reader.limits.max_bytes:
                    raise ValueError("child_compiler_array_format_unsupported")
                with archive.open(info) as entry:
                    member = entry.read(info.file_size + 1)
                if len(member) != info.file_size:
                    raise ValueError("child_compiler_array_format_unsupported")
                elements += _numeric_array_elements(member, limits=reader.limits)
                if elements > reader.limits.max_elements:
                    raise ValueError("child_compiler_array_reference_contract_unsupported")
    return ()


def _basis_children(reader: _ExecutionReader, ref: ArtifactRef) -> tuple[ArtifactRef, ...]:
    from polisyos.foundry.execute.api import execution_input_basis_sources

    basis = reader.typed(ref, FoundryExecutionInputBasis)
    _shape(basis.request)
    _shape(basis.request.exec_config)
    for actual, expected_ref in (
        (basis.request.exec_plan_ref, basis.exec_plan_ref),
        (basis.request.input_bindings_ref, basis.input_bindings_ref),
        (basis.request.registry_bundle_ref, basis.runtime_registry_ref),
        (basis.request.parameter_override_bundle_ref, basis.parameter_override_bundle_ref),
        (basis.request.observed_range_bundle_ref, basis.observed_range_bundle_ref),
    ):
        if (actual is None) != (expected_ref is None) or (
            actual is not None
            and expected_ref is not None
            and artifact_ref_identity_key(actual) != artifact_ref_identity_key(expected_ref)
        ):
            raise ValueError("child_compiler_execution_source_mismatch")
    if basis.parameter_overrides is not None:
        for values in basis.parameter_overrides.values():
            _numeric_parameters(values)
    expected: list[InputRef] = []
    children: list[ArtifactRef] = []
    for role, source in execution_input_basis_sources(basis):
        manifest, _ = reader.read_selected_manifest(source)
        expected.append(input_ref_from_artifact_ref(source, role=f"basis.source.{role}"))
        children.append(source)
        for edge in manifest.inputs:
            child, _, _ = reader.read_edge_manifest(source, edge)
            children.append(child)
            expected.append(edge.model_copy(update={"role": f"basis.edge.{role}.{edge.role}"}))
    view = reader.view(ref)
    if view.read.manifest.inputs != expected:
        raise ValueError("child_compiler_execution_basis_input_mismatch")
    return tuple(child.model_copy(deep=True) for child in children)


def _execution_graph_inputs(
    reader: _ExecutionReader,
    ref: ArtifactRef,
    *,
    patch_refs: list[ArtifactRef] | None = None,
) -> tuple[tuple[ArtifactRef, ...], FoundryExecutionInputBasis]:
    view = reader.view(ref)
    plan_ref = _edge(view, "exec_plan", kind="foundry.exec_plan")
    plan = reader.typed(plan_ref, ExecPlan)
    graph_ref = _edge(
        view, "program_graph", expected=plan.program_ref, kind="foundry.program_graph"
    )
    graph = reader.typed(graph_ref, ProgramGraph)
    if graph.lowered_ir_ref is None:
        raise ValueError("child_compiler_required_payload_ref_missing")
    lowered = _edge(view, "lowered_ir", expected=graph.lowered_ir_ref, kind="foundry.lowered_ir")
    basis_ref = _edge(view, "execution_input_basis", kind="foundry.execution_input_basis")
    basis = reader.typed(basis_ref, FoundryExecutionInputBasis)
    if (
        artifact_ref_identity_key(basis.exec_plan_ref) != artifact_ref_identity_key(plan_ref)
        or artifact_ref_identity_key(basis.program_graph_ref)
        != artifact_ref_identity_key(graph_ref)
        or basis.parameter_override_bundle_ref is not None
    ):
        raise ValueError("child_compiler_execution_source_mismatch")
    declared_patches = [child for role, child in view.edges if role == "patch_value"]
    if patch_refs is not None and [
        artifact_ref_identity_key(child) for child in declared_patches
    ] != [artifact_ref_identity_key(child) for child in patch_refs]:
        raise ValueError("child_compiler_patch_input_mismatch")
    expected = [
        input_ref_from_artifact_ref(graph_ref, role="program_graph"),
        input_ref_from_artifact_ref(plan_ref, role="exec_plan"),
        input_ref_from_artifact_ref(lowered, role="lowered_ir"),
        input_ref_from_artifact_ref(basis_ref, role="execution_input_basis"),
        *(input_ref_from_artifact_ref(child, role="patch_value") for child in declared_patches),
    ]
    if view.read.manifest.inputs != expected:
        raise ValueError("child_compiler_execution_input_set_mismatch")
    if any(child.kind != "foundry.patch_value" for child in declared_patches):
        raise ValueError("child_compiler_input_kind_mismatch")
    return tuple(child.model_copy(deep=True) for _, child in view.edges), basis


def _delta_children(reader: _ExecutionReader, ref: ArtifactRef) -> tuple[ArtifactRef, ...]:
    delta = reader.typed(ref, StateDelta)
    if delta.base_ref is None or delta.patch_ref is not None:
        raise ValueError("child_compiler_state_delta_contract_unsupported")
    values: list[ArtifactRef] = []
    for op in delta.ops:
        _shape(op)
        if op.value_ref is None or op.mask_ref is not None or op.mask_scope is not None:
            raise ValueError("child_compiler_patch_reference_contract_unsupported")
        values.append(op.value_ref)
    children, basis = _execution_graph_inputs(reader, ref, patch_refs=values)
    if artifact_ref_identity_key(delta.base_ref) != artifact_ref_identity_key(
        basis.base_state_snapshot_ref
    ):
        raise ValueError("child_compiler_execution_source_mismatch")
    return (*children, delta.base_ref.model_copy(deep=True))


def _metrics_children(reader: _ExecutionReader, ref: ArtifactRef) -> tuple[ArtifactRef, ...]:
    metrics = reader.typed(ref, Metrics)
    counters = {
        "applied_nodes",
        "skipped_nodes",
        "op_nodes",
        "checked_constraints",
        "patch_ops",
        "step",
        "step_latency_ms",
        "constraint_hard_fail",
        "failure_cards_recorded",
        "failure_cards_dropped",
    }
    if set(metrics.values) != counters or any(
        type(value) is not int or value < 0 for value in metrics.values.values()
    ):
        raise ValueError("child_compiler_metrics_reference_contract_unsupported")
    children, basis = _execution_graph_inputs(reader, ref)
    patches = [child for role, child in reader.view(ref).edges if role == "patch_value"]
    if (
        len(patches) != metrics.values["patch_ops"]
        or metrics.values["step"] != basis.effective_step
    ):
        raise ValueError("child_compiler_patch_input_mismatch")
    return children


def _snapshot_children(reader: _ExecutionReader, ref: ArtifactRef) -> tuple[ArtifactRef, ...]:
    snapshot = reader.typed(ref, StateSnapshot)
    view = reader.view(ref)
    if (
        snapshot.schema_version != "2.2"
        or snapshot.schema_ref is not None
        or snapshot.layout is not None
        or snapshot.codec != "numpy-npz"
        or snapshot.format_version != "npz-v2"
        or snapshot.lineage_inputs != view.read.manifest.inputs
        or snapshot.checksum_sha256 != snapshot.state_ref.artifact_id.hex
    ):
        raise ValueError("child_compiler_snapshot_reference_contract_unsupported")
    blob = _edge(view, "state_blob", expected=snapshot.state_ref, kind="foundry.state_blob")
    if blob.media_type != "application/x-npz":
        raise ValueError("child_compiler_input_kind_mismatch")
    roles = {"state_blob"}
    if "state_delta" in view.inputs:
        delta_ref = _edge(view, "state_delta", kind="foundry.state_delta")
        delta = reader.typed(delta_ref, StateDelta)
        if delta.base_ref is None:
            raise ValueError("child_compiler_required_payload_ref_missing")
        _edge(view, "base_state", expected=delta.base_ref, kind="foundry.state_snapshot")
        roles.update({"state_delta", "base_state"})
    if not snapshot.lineage_inputs or snapshot.lineage_inputs[-1].role != "state_blob":
        raise ValueError("child_compiler_snapshot_reference_contract_unsupported")
    _binary_children(reader, blob)
    from polisyos.foundry.execute._internal.snapshots import _read_npz_entry_count

    count = _read_npz_entry_count(reader.blob(blob)[1], max_entries=reader.limits.max_elements)
    if snapshot.entry_count != count:
        raise ValueError("child_compiler_snapshot_entry_count_mismatch")
    return _complete(view, roles)


def _welfare_children(reader: _ExecutionReader, ref: ArtifactRef) -> tuple[ArtifactRef, ...]:
    report = reader.typed(ref, WelfareBoundReport)
    if report.schema_version != "1.0" or report.node_id is None:
        raise ValueError("child_compiler_welfare_reference_contract_unsupported")
    view = reader.view(ref)
    plan = reader.typed(_edge(view, "exec_plan", kind="foundry.exec_plan"), ExecPlan)
    graph = reader.typed(plan.program_ref, ProgramGraph)
    nodes = [node for node in graph.nodes if node.node_id == report.node_id]
    if len(nodes) != 1 or nodes[0].mechanism_type != report.mechanism_type:
        raise ValueError("child_compiler_welfare_source_mismatch")
    _edge(view, "base_state_snapshot", kind="foundry.state_snapshot")
    if nodes[0].params_ref is None:
        raise ValueError("child_compiler_required_payload_ref_missing")
    _edge(
        view,
        "mechanism_params",
        expected=nodes[0].params_ref,
        kind="foundry.lowered_mechanism_payload",
    )
    return _complete(view, {"exec_plan", "base_state_snapshot", "mechanism_params"})


def _simulation_children(reader: _ExecutionReader, ref: ArtifactRef) -> tuple[ArtifactRef, ...]:
    from polisyos.foundry.execute.api import admit_execution_source_bounded

    admission = admit_execution_source_bounded(reader.store, ref, reader=reader)
    if admission.mode != "single_step_basis" or admission.basis is None:
        raise ValueError("child_compiler_simulation_source_mode_unsupported")
    simulation = admission.simulation_result
    _shape(simulation)
    permitted = {
        "schema_version",
        "exec_plan_ref",
        "metrics_ref",
        "state_snapshot_ref",
        "environment_fingerprint",
        "welfare_bound_refs",
        "execution_input_basis_ref",
        "execution_source_status",
        "notes",
    }
    if any(
        getattr(simulation, name) is not None
        for name in type(simulation).model_fields
        if name not in permitted
    ):
        raise ValueError("child_compiler_simulation_reference_contract_unsupported")
    view = reader.view(ref)
    delta_ref = _edge(view, "state_delta", kind="foundry.state_delta")
    _delta_children(reader, delta_ref)
    _metrics_children(reader, simulation.metrics_ref)
    if (
        reader.view(delta_ref).read.manifest.inputs
        != reader.view(simulation.metrics_ref).read.manifest.inputs
    ):
        raise ValueError("child_compiler_execution_companion_input_mismatch")
    if simulation.state_snapshot_ref is None:
        raise ValueError("child_compiler_required_payload_ref_missing")
    _snapshot_children(reader, simulation.state_snapshot_ref)
    snapshot_view = reader.view(simulation.state_snapshot_ref)
    _edge(snapshot_view, "state_delta", expected=delta_ref)
    _edge(snapshot_view, "base_state", expected=admission.basis.base_state_snapshot_ref)
    roles = {
        "exec_plan",
        "metrics",
        "state_delta",
        "state_snapshot",
        "input.input_bindings_ref",
        "input.data_snapshot_ref",
        "input.bound_state_snapshot_ref",
        "execution_input_basis",
    }
    children = _complete(view, roles)
    welfare: list[ArtifactRef] = []
    for node_id, report_ref in (simulation.welfare_bound_refs or {}).items():
        if (
            report_ref.kind != "foundry.welfare_bound_report"
            or not report_ref.manifest_profile_sha256
        ):
            raise ValueError("child_compiler_welfare_reference_contract_unsupported")
        report = reader.typed(report_ref, WelfareBoundReport)
        if report.node_id != node_id:
            raise ValueError("child_compiler_welfare_source_mismatch")
        _welfare_children(reader, report_ref)
        _edge(reader.view(report_ref), "exec_plan", expected=simulation.exec_plan_ref)
        _edge(
            reader.view(report_ref),
            "base_state_snapshot",
            expected=admission.basis.base_state_snapshot_ref,
        )
        welfare.append(report_ref.model_copy(deep=True))
    return (*children, *welfare)


def _edge(
    view: _View,
    role: str,
    *,
    expected: ArtifactRef | None = None,
    kind: str | None = None,
) -> ArtifactRef:
    actual = view.inputs.get(role)
    if actual is None:
        raise ValueError("child_compiler_required_input_missing")
    if kind is not None and (
        actual.kind != kind or actual.media_type != _BINARY_CONTRACTS.get(kind, "application/json")
    ):
        raise ValueError("child_compiler_input_kind_mismatch")
    if expected is not None and (
        not expected.manifest_profile_sha256
        or artifact_ref_identity_key(actual) != artifact_ref_identity_key(expected)
    ):
        raise ValueError("child_compiler_payload_input_mismatch")
    return actual


def _complete(view: _View, roles: set[str]) -> tuple[ArtifactRef, ...]:
    if set(view.inputs) != roles:
        raise ValueError("child_compiler_input_set_mismatch")
    return tuple(ref.model_copy(deep=True) for ref in view.inputs.values())


def _compile_children(reader: _Reader, ref: ArtifactRef) -> tuple[ArtifactRef, ...]:
    report = reader.typed(ref, CompileReport)
    schema = reader.view(ref).read.manifest.artifact_schema
    if schema is None or report.schema_version != schema.version:
        raise ValueError("child_compiler_payload_version_mismatch")
    if report.candidate_rejection is not None:
        _shape(report.candidate_rejection)
    roles: set[str] = set()
    for role, child, kind in (
        ("ir", report.policy_ref, "ir.trinity_bundle"),
        ("registry_bundle", report.registry_bundle_ref, "core.registry_bundle"),
        ("link_report", report.link_report_ref, "compiler.link_report"),
        ("lowered_ir", report.lowered_ir_ref, "foundry.lowered_ir"),
        ("program_graph", report.program_graph_ref, "foundry.program_graph"),
        ("exec_plan", report.exec_plan_ref, "foundry.exec_plan"),
        ("slot_layout", report.slot_layout_ref, "foundry.slot_layout"),
        ("treasury_plan", report.treasury_plan_ref, "foundry.treasury_plan"),
    ):
        if child is not None:
            roles.add(role)
            _edge(reader.view(ref), role, expected=child, kind=kind)
        elif report.ok or role == "ir":
            raise ValueError("child_compiler_required_payload_ref_missing")
    return _complete(reader.view(ref), roles)


def _link_children(reader: _Reader, ref: ArtifactRef) -> tuple[ArtifactRef, ...]:
    report = reader.typed(ref, LinkReport)
    if report.schema_version != "1.0":
        raise ValueError("child_compiler_payload_version_mismatch")
    # These are diagnostic values, not an open artifact selector namespace.
    scalar_data = {
        "registry",
        "metric_id",
        "unit_id",
        "constraint_id",
        "slot_id",
        "field_id",
        "rule_id",
        "where",
        "expected",
        "actual",
        "param_path",
        "max_depth",
    }
    sequence_data = {
        "mechanism_ids",
        "slot_ids",
        "constraint_ids",
        "scopes",
        "intervention_ids",
        "missing",
    }
    for issue in report.issues:
        _shape(issue)
        if set(issue.data) - scalar_data - sequence_data:
            raise ValueError("child_compiler_opaque_value_unsupported")
        for name, value in issue.data.items():
            if name in sequence_data:
                if type(value) is not list or any(type(item) is not str for item in value):
                    raise ValueError("child_compiler_opaque_value_unsupported")
            elif type(value) not in (str, int, bool, Decimal) and value is not None:
                raise ValueError("child_compiler_opaque_value_unsupported")
    view = reader.view(ref)
    policy = _edge(view, "ir", kind="ir.trinity_bundle")
    registry = _edge(view, "registry_bundle", kind="core.registry_bundle")
    bundle = reader.typed(policy, TrinityBundle)
    if bundle.model_spec.registry_bundle_ref is not None and (
        bundle.model_spec.registry_bundle_ref != str(registry.artifact_id)
    ):
        raise ValueError("child_compiler_payload_input_mismatch")
    return _complete(view, {"ir", "registry_bundle"})


def _lowered_children(reader: _Reader, ref: ArtifactRef) -> tuple[ArtifactRef, ...]:
    lowered = reader.typed(ref, LoweredIR)
    if lowered.schema_version != "0.2":
        raise ValueError("child_compiler_payload_version_mismatch")
    view = reader.view(ref)
    policy = _edge(view, "ir", expected=lowered.ir_ref, kind="ir.trinity_bundle")
    registry = _edge(view, "registry_bundle", kind="core.registry_bundle")
    bundle = reader.typed(policy, TrinityBundle)
    if bundle.model_spec.registry_bundle_ref is not None and (
        bundle.model_spec.registry_bundle_ref != str(registry.artifact_id)
    ):
        raise ValueError("child_compiler_payload_input_mismatch")
    roles = {"ir", "registry_bundle"}
    for mechanism in lowered.mechanisms:
        _shape(mechanism)
        if len(mechanism.intervention_ids) != 1 or mechanism.effective_params_ref is None:
            raise ValueError("child_compiler_mechanism_contract_unsupported")
        role = f"effective_params:{mechanism.intervention_ids[0]}"
        if role in roles:
            raise ValueError("child_compiler_input_ambiguous")
        roles.add(role)
        _edge(
            view,
            role,
            expected=mechanism.effective_params_ref,
            kind="foundry.lowered_mechanism_payload",
        )
        if mechanism.effective_schedule is not None:
            ScheduleSpec.model_validate(mechanism.effective_schedule)
        if mechanism.target_selector is not None:
            TypeAdapter(SelectorExpr).validate_python(mechanism.target_selector)
    for constraint in lowered.constraints:
        _shape(constraint)
        _numeric(constraint.expected)
    for constraint in lowered.composite_constraints:
        _shape(constraint)
        # The composite RHS is an expression, not an artifact selector.
        try:
            numeric = Decimal(constraint.expected)
        except InvalidOperation as exc:
            raise ValueError("child_compiler_opaque_value_unsupported") from exc
        if not numeric.is_finite():
            raise ValueError("child_compiler_opaque_value_unsupported")
    for raw in lowered.parameter_specs:
        parameter = ParameterSpec.model_validate(raw)
        _shape(parameter)
        for value in (parameter.default_value, parameter.min_value, parameter.max_value):
            _numeric_parameter(value)
    if lowered.time_semantics is not None:
        _shape(TimeSemantics.model_validate(lowered.time_semantics))
    if lowered.environment_config is not None:
        environment = EnvironmentConfig.model_validate(lowered.environment_config)
        _shape(environment)
        if environment.params:
            raise ValueError("child_compiler_environment_reference_contract_unsupported")
    return _complete(view, roles)


def _parameter_children(reader: _Reader, ref: ArtifactRef) -> tuple[ArtifactRef, ...]:
    from polisyos.core.canon import to_canonical_bytes
    from polisyos.foundry.compile._lowering import _merge_effective_params, _resolve_bindings
    from polisyos.foundry.methods.catalog.mechanism.runtime_registry import (
        resolve_runtime_fidelity,
    )
    from polisyos.ir.kernel.mechanisms import ParamSpec

    view = reader.view(ref)
    value = view.read.value
    fields = {
        "binding_id",
        "mechanism_id",
        "intervention_ids",
        "priority",
        "params",
        "schedule",
        "selector",
        "selected_fidelity",
        "legacy_kind_alias_used",
        "notes",
    }
    if type(value) is not dict or set(value) != fields:
        raise ValueError("child_compiler_parameter_contract_mismatch")
    _numeric_parameters(value["params"])
    policy = _edge(view, "ir", kind="ir.trinity_bundle")
    bundle = reader.typed(policy, TrinityBundle)
    interventions = [item for item in bundle.policy_spec.interventions if item.enabled]
    matches = [
        item for item in interventions if [item.intervention_id] == value["intervention_ids"]
    ]
    if len(matches) != 1:
        raise ValueError("child_compiler_parameter_source_mismatch")
    # Current ParamSpec has no default-value field. A later defaults contract
    # cannot silently make the no-default replay below incomplete.
    if {"default", "default_value"}.intersection(ParamSpec.model_fields):
        raise ValueError("child_compiler_owner_schema_changed")
    intervention = matches[0]
    bindings, _ = _resolve_bindings(
        enabled_interventions=interventions,
        explicit_bindings=list(bundle.policy_spec.mechanism_bindings),
    )
    binding, synthetic = bindings[intervention.intervention_id]
    schedule = bundle.policy_spec.global_schedule or intervention.schedule
    expected = {
        "binding_id": binding.binding_id,
        "mechanism_id": binding.mechanism_id,
        "intervention_ids": [intervention.intervention_id],
        "priority": intervention.priority,
        "params": _merge_effective_params(
            mechanism_spec=None, binding=binding, intervention=intervention
        ),
        "schedule": schedule.model_dump(mode="json"),
        "selector": intervention.target.model_dump(mode="json"),
        "selected_fidelity": resolve_runtime_fidelity(
            binding.mechanism_id, bundle.model_spec.fidelity_level
        ).value,
        "legacy_kind_alias_used": synthetic,
        "notes": ["synthetic_mechanism_binding_from_kind"]
        if synthetic
        else list(intervention.notes),
    }
    if to_canonical_bytes(value) != to_canonical_bytes(expected):
        raise ValueError("child_compiler_parameter_source_mismatch")
    return _complete(view, {"ir"})


def _program_children(reader: _Reader, ref: ArtifactRef) -> tuple[ArtifactRef, ...]:
    from polisyos.core.canon import to_canonical_bytes
    from polisyos.foundry.compile._graph import build_program_graph

    program = reader.typed(ref, ProgramGraph)
    if any(node.node_kind == "method" for node in program.nodes):
        raise ValueError("child_compiler_method_reference_contract_unsupported")
    if program.lowered_ir_ref is None:
        raise ValueError("child_compiler_required_payload_ref_missing")
    view = reader.view(ref)
    _edge(view, "ir", expected=program.ir_ref, kind="ir.trinity_bundle")
    lowered_ref = _edge(
        view, "lowered_ir", expected=program.lowered_ir_ref, kind="foundry.lowered_ir"
    )
    lowered = reader.typed(lowered_ref, LoweredIR)
    _lowered_children(reader, lowered_ref)
    _edge(reader.view(lowered_ref), "ir", expected=program.ir_ref)
    registry = _edge(reader.view(lowered_ref), "registry_bundle")
    _edge(view, "registry_bundle", expected=registry, kind="core.registry_bundle")
    link = _edge(view, "link_report", kind="compiler.link_report")
    _link_children(reader, link)
    _edge(reader.view(link), "ir", expected=program.ir_ref)
    _edge(reader.view(link), "registry_bundle", expected=registry)
    expected, params = build_program_graph(
        reader.store,
        ir_ref=program.ir_ref,
        lowered_ir_ref=program.lowered_ir_ref,
        mechanisms=lowered.mechanisms,
        constraint_ids=[item.constraint_id for item in lowered.constraints],
    )
    if to_canonical_bytes(program) != to_canonical_bytes(expected):
        raise ValueError("child_compiler_program_source_mismatch")
    roles = {"ir", "registry_bundle", "link_report", "lowered_ir"}
    for node_id, child in params.items():
        role = f"params:{node_id}"
        roles.add(role)
        _edge(view, role, expected=child, kind="foundry.lowered_mechanism_payload")
    return _complete(view, roles)


def _compiler_children(reader: _Reader, ref: ArtifactRef) -> tuple[ArtifactRef, ...]:
    if ref.kind == "compiler.compile_report":
        return _compile_children(reader, ref)
    if ref.kind == "compiler.link_report":
        return _link_children(reader, ref)
    if ref.kind == "foundry.lowered_ir":
        return _lowered_children(reader, ref)
    if ref.kind == "foundry.lowered_mechanism_payload":
        return _parameter_children(reader, ref)
    if ref.kind == "foundry.program_graph":
        return _program_children(reader, ref)
    view = reader.view(ref)
    if ref.kind == "foundry.exec_plan":
        plan = reader.typed(ref, ExecPlan)
        if plan.environment_ref is not None:
            raise ValueError("child_compiler_environment_reference_contract_unsupported")
        program = _edge(
            view, "program_graph", expected=plan.program_ref, kind="foundry.program_graph"
        )
        treasury = _edge(view, "treasury_plan", kind="foundry.treasury_plan")
        _edge(reader.view(treasury), "program_graph", expected=program)
        return _complete(view, {"program_graph", "treasury_plan"})
    if ref.kind == "foundry.slot_layout":
        from polisyos.ir.kernel.slots import SlotLayout

        model = reader.typed(ref, SlotLayout)
    else:
        from polisyos.foundry.compile.randomization import TreasuryPlan

        model = reader.typed(ref, TreasuryPlan)
    if model.schema_version != "1.0":
        raise ValueError("child_compiler_payload_version_mismatch")
    _edge(view, "program_graph", kind="foundry.program_graph")
    return _complete(view, {"program_graph"})


def _artifact_children(
    store: ArtifactReader, ref: ArtifactRef, *, limits: CoreJsonReadLimits
) -> tuple[ArtifactRef, ...] | None:
    """Dispatch actual owner contracts before the parent attempts JSON decoding."""
    from zipfile import BadZipFile

    if ref.kind not in _CONTRACTS and ref.kind not in _BINARY_CONTRACTS:
        return None
    try:
        if ref.kind in _BINARY_CONTRACTS:
            return _binary_children(_ExecutionReader(store, limits), ref)
        execution_reader = _ExecutionReader(store, limits)
        if ref.kind == "foundry.simulation_result":
            return _simulation_children(execution_reader, ref)
        if ref.kind == "foundry.execution_input_basis":
            return _basis_children(execution_reader, ref)
        if ref.kind == "foundry.state_delta":
            return _delta_children(execution_reader, ref)
        if ref.kind == "foundry.metrics":
            return _metrics_children(execution_reader, ref)
        if ref.kind == "foundry.state_snapshot":
            return _snapshot_children(execution_reader, ref)
        if ref.kind == "foundry.welfare_bound_report":
            return _welfare_children(execution_reader, ref)
        if ref.kind == "foundry.constraint_report":
            report = execution_reader.typed(ref, ConstraintReport)
            if report.schema_version != "1.0":
                raise ValueError("child_compiler_payload_version_mismatch")
            for violation in report.violations:
                _shape(violation)
                if violation.events:
                    raise ValueError("child_compiler_opaque_value_unsupported")
            return _execution_graph_inputs(execution_reader, ref)[0]
        return _compiler_children(_Reader(store, limits), ref)
    except ValidationError as exc:
        raise ValueError("child_compiler_payload_invalid") from exc
    except BadZipFile as exc:
        raise ValueError("child_compiler_array_format_unsupported") from exc


def compiler_artifact_children(
    store: ArtifactReader, ref: ArtifactRef, *, limits: CoreJsonReadLimits
) -> tuple[ArtifactRef, ...] | None:
    """Derive complete immediate children for supported Foundry output artifacts.

    Args:
        store: The already scoped reader; this function never expands its grant.
        ref: Full selected artifact reference.
        limits: Bounds applied to every manifest and payload read. Execution
            source admission additionally shares max_bytes across its actual reads.

    Returns:
        Detached full selected Core references, preserving role multiplicity,
        or None for an unknown artifact family.

    Raises:
        ValueError: A supported artifact has mismatched, incomplete, or unsupported
            source/reference semantics. Existing reader permission/integrity errors
            propagate and do not become successful closure.
    """
    from polisyos.core.run.child_custody import _snapshot_selected_ref

    children = _artifact_children(store, ref, limits=limits)
    if children is None:
        return None
    return tuple(_snapshot_selected_ref(child) for child in children)
