"""Internal welfare context implementation helpers."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from decimal import Decimal
from numbers import Real
from typing import Any, Literal

import numpy as np

from polisyos.common import logger as common_logger
from polisyos.core.artifacts import ArtifactRef, resolve_manifest_by_profile
from polisyos.core.artifacts import (
    ensure_ir_artifact_store as _ensure_ir_artifact_store,
)
from polisyos.core.artifacts.manifest import InputRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts import (
    DataSnapshot,
    EquilibriumMultiplicityReport,
    FeedbackSolveResult,
    Metrics,
    SimulationResult,
)
from polisyos.core.contracts.foundry import (
    ExecPlan,
    ProgramGraph,
    SimulationResultRef,
    StateSnapshot,
)
from polisyos.foundry.calibration import CalibrationReport, read_calibration_config_source
from polisyos.foundry.calibration.execution_basis import (
    RUNTIME_REGISTRY_MEMBER_CONTRACT,
    CalibrationExecutionInputBasis,
    CalibrationOrderedBatchBackendUnavailable,
    CalibrationParameterUnitIdentity,
    calibration_report_series_sha256,
    calibration_report_time_axis_sha256,
    canonical_input_sha256,
    load_calibration_execution_input_basis,
    read_calibration_execution_input_basis_source,
    read_calibration_model_source,
    read_calibration_registry_source,
    read_calibration_report_source,
    read_calibration_source,
    reconcile_ordered_batch_report_identity,
    reconcile_selected_runtime_input,
    record_calibration_source_error,
    replay_ordered_batch_report_projection,
)
from polisyos.foundry.execute import (
    ExecutionSourceAdmissionRefusal,
    admit_execution_source,
)
from polisyos.ir import (
    ArtifactRefModel,
    DependenceStructureRef,
    UncertaintyEnvelope,
    UncertaintyEnvelopeRef,
    load_dependence_structure,
    load_uncertainty_envelope,
)
from polisyos.ir.analytics import EquilibriumMultiplicityWelfareAnnotation
from polisyos.ir.kernel import MechanismTypeRegistry, UnitsRegistry
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_CALIBRATION_REPORT_REF,
    INPUT_DATA_SNAPSHOT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.phase3 import (
    ensure_social_weight_manifest_artifact,
)

from .welfare_ge import (
    _coerce_artifact_ref,
    _coerce_dependence_matrix,
    _coerce_str_list,
    _correlation_from_covariance,
    _resolve_ge_context,
    _stabilize_correlation_matrix,
)
from .welfare_types import (
    _ERROR_DEPENDENCE_SPEC_INVALID,
    _ERROR_WELFARE_DIMENSION_MISMATCH,
    _ERROR_WELFARE_MODEL_CLASS_MISMATCH,
    _ERROR_WELFARE_OUTPUT_NONFINITE,
    _WELFARE_LOAD_ERRORS,
    _WELFARE_VALIDATION_ERRORS,
    _CalibrationCovarianceSource,
    _EnvelopeCollection,
    _EnvelopeOrigin,
    _fail_error,
    _load_artifact_json,
    _persist_json_payload,
    _ResolvedDependenceContext,
    _ResolvedWelfareContext,
)

logger = common_logger.get_logger(__name__)


def _artifact_ref_identity(ref: ArtifactRef) -> tuple[str, str, str, str | None]:
    return (str(ref.artifact_id), ref.kind, ref.media_type, ref.manifest_profile_sha256)


def _selected_input_ref(ctx: ExecutionContext, edge: InputRef) -> ArtifactRef:
    """Resolve one exact input with the shared selection/availability classification."""
    return read_calibration_source(
        ctx.store,
        role=edge.role,
        inputs=(edge,),
        expected_media_type=None,
        decoder=lambda selected, _manifest, _payload: selected,
    ).require_value()


def _load_registry_model(
    ctx: ExecutionContext,
    ref: ArtifactRef,
    model_cls: type[Any],
    *,
    expected_kind: str,
    expected_schema: str,
) -> Any:
    """Delegate selected registry reads to the shared availability intake."""
    return read_calibration_model_source(
        ctx.store,
        role=expected_kind,
        ref=ref,
        expected_kind=expected_kind,
        expected_schema=expected_schema,
        model=model_cls,
        decoder=lambda _ref, _manifest, value: value,
    ).require_value()


def _graph_parameter_nodes(
    graph: ProgramGraph,
    plan: ExecPlan,
) -> tuple[tuple[str, str, ArtifactRef | None], ...]:
    """Derive mechanism parameter-source rows from the selected graph and plan."""
    by_id = {node.node_id: node for node in graph.nodes}
    ordered_ids = plan.order or [node.node_id for node in graph.nodes]
    rows: list[tuple[str, str, ArtifactRef | None]] = []
    for node_id in ordered_ids:
        node = by_id.get(node_id)
        if node is None:
            continue
        mechanism_type = node.mechanism_type
        params_ref = node.params_ref
        if node.node_kind == "op" and node.op is not None:
            if node.op.op_kind != "apply_mechanism":
                continue
            mechanism_type = node.op.params.get("mechanism_type") or mechanism_type
            params_ref = node.op.params.get("params_ref") or params_ref
        elif node.node_kind != "mechanism":
            continue
        if mechanism_type is not None:
            rows.append(
                (
                    node_id,
                    mechanism_type,
                    params_ref if isinstance(params_ref, ArtifactRef) else None,
                )
            )
    return tuple(rows)


def _expected_parameter_unit_identities(
    *,
    graph: ProgramGraph,
    plan: ExecPlan,
    mechanism_registry: MechanismTypeRegistry,
    units_registry: UnitsRegistry | None,
    mechanism_source_selected: bool,
    units_source_selected: bool,
) -> tuple[CalibrationParameterUnitIdentity, ...]:
    """Recompute declared parameter and unit identities from registry content."""
    identities: list[CalibrationParameterUnitIdentity] = []
    for node_id, mechanism_type, _params_ref in _graph_parameter_nodes(graph, plan):
        mechanism = mechanism_registry.mechanisms.get(mechanism_type)
        if mechanism is None:
            raise ValueError("selected_graph_mechanism_missing_from_registry")
        for parameter_id, spec in mechanism.params.items():
            unit_id = spec.unit_id
            unit_digest = None
            unit_status = "not_established"
            if unit_id is not None and units_registry is not None:
                if unit_id not in units_registry.units:
                    unit_status = "selected_source_missing"
                else:
                    unit_digest = canonical_input_sha256(units_registry.units[unit_id])
                    unit_status = (
                        "selected_source_content_bound"
                        if units_source_selected
                        else "in_memory_content_bound"
                    )
            identities.append(
                CalibrationParameterUnitIdentity(
                    field_name=f"{node_id}.{parameter_id}",
                    mechanism_type=mechanism_type,
                    parameter_id=parameter_id,
                    value_type=spec.value_type.value,
                    unit_id=unit_id,
                    parameter_spec_sha256=canonical_input_sha256(spec),
                    parameter_spec_status=(
                        "selected_source_content_bound"
                        if mechanism_source_selected
                        else "in_memory_content_bound"
                    ),
                    unit_definition_sha256=unit_digest,
                    unit_definition_status=unit_status,
                    status="parameter_spec_bound",
                )
            )
    return tuple(identities)


def _calibration_execution_source_join(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    report_ref: ArtifactRef,
    report: CalibrationReport,
) -> tuple[Literal["matched", "not_established", "mismatch"], tuple[str, ...], tuple[str, ...]]:
    """Recompute the report→basis→selected simulation source join.

    Missing historical basis or a legacy/profileless execution source is a
    candidate limitation. A basis that is present but contradicts selected
    source bytes is a hard issue and must not fall back to the legacy path.
    """
    limitations: set[str] = set()
    blockers: set[str] = set()
    issues: set[str] = set()
    if report.ordered_batch_execution is not None:
        limitations.add("calibration_batch_curvature_only")
    selected_report = read_calibration_report_source(ctx.store, ref=report_ref)
    if selected_report.status != "matched":
        if selected_report.status == "not_established":
            return (
                "not_established",
                tuple(
                    sorted(limitations | {"source_execution_not_established", selected_report.code})
                ),
                (),
            )
        return "mismatch", tuple(sorted(limitations)), (selected_report.code,)
    actual_report = selected_report.require_value()
    if actual_report.model_dump(mode="json") != report.model_dump(mode="json"):
        return (
            "mismatch",
            tuple(sorted(limitations)),
            ("calibration_selected_report_payload_mismatch",),
        )
    report_manifest = selected_report.manifest
    assert report_manifest is not None
    selected_basis = read_calibration_execution_input_basis_source(
        ctx.store, inputs=report_manifest.inputs
    )
    if selected_basis.status != "matched":
        if selected_basis.status == "not_established":
            return (
                "not_established",
                tuple(
                    sorted(
                        limitations
                        | {
                            "source_execution_not_established",
                            "calibration_execution_input_unavailable",
                            selected_basis.code,
                        }
                    )
                ),
                (),
            )
        return (
            "mismatch",
            tuple(sorted(limitations)),
            ("calibration_execution_basis_invalid", selected_basis.code),
        )
    basis = selected_basis.require_value()
    basis_ref = selected_basis.ref
    assert basis_ref is not None
    if basis.ordered_batch_profile is not None:
        limitations.add("calibration_batch_curvature_only")
    if basis.schema_version == "1.2" or report.ordered_batch_execution is not None:
        try:
            reconcile_ordered_batch_report_identity(basis, report)
        except (TypeError, ValueError, KeyError) as error:
            record_calibration_source_error(
                error,
                role="calibration_ordered_report_input_scope_mismatch",
                limitations=blockers,
                issues=issues,
            )
    if basis.input_capture_status == "limited":
        blockers.add("calibration_execution_input_capture_limited")
    if basis.source_attestation_status == "not_established":
        limitations.add("calibration_external_source_attestation_not_established")
    if basis.unit_status == "not_established":
        limitations.add("calibration_unit_definition_not_established")
    if basis.physical_time_status == "not_established":
        limitations.add("calibration_physical_time_semantics_not_established")
    limitations.update(
        {
            "calibration_noise_law_not_established",
            "calibration_authority_not_established",
        }
    )
    if basis.program_graph_status == "selected_source_mismatch":
        issues.add("calibration_execution_program_graph_source_mismatch")
    elif basis.program_graph_status != "selected_source_matched":
        blockers.add("calibration_program_graph_source_not_established")
    if basis.exec_plan_source_status == "selected_source_mismatch":
        issues.add("calibration_execution_exec_plan_source_mismatch")
    elif basis.exec_plan_source_status != "selected_source_matched":
        blockers.add("calibration_exec_plan_source_not_established")
    if basis.base_state_source_status == "selected_source_mismatch":
        issues.add("calibration_execution_base_state_source_mismatch")
    elif basis.base_state_source_status != "selected_source_matched":
        blockers.add("calibration_base_state_source_not_established")

    config_source = read_calibration_config_source(
        ctx.store, ref=basis.calibration_config_ref, inputs=report_manifest.inputs
    )
    if config_source.status != "matched":
        if config_source.status == "not_established":
            blockers.update(("source_execution_not_established", config_source.code))
        else:
            issues.update(("calibration_execution_config_edge_invalid", config_source.code))

    report_target_order = tuple(report.series_comparison)
    if report_target_order != basis.target_order:
        issues.add("calibration_execution_target_order_mismatch")
    if tuple(item.target_id for item in basis.target_inputs) != basis.target_order:
        issues.add("calibration_execution_target_basis_order_mismatch")
    for target_id in basis.target_order:
        identity = next(
            (item for item in basis.target_inputs if item.target_id == target_id),
            None,
        )
        comparison = report.series_comparison.get(target_id)
        if identity is None or comparison is None:
            issues.add("calibration_execution_target_basis_incomplete")
            continue
        if (
            identity.report_series_sha256
            != calibration_report_series_sha256(real=comparison.real, time=comparison.time)
            or identity.observed_values_sha256 != canonical_input_sha256(comparison.real)
            or identity.report_time_axis_sha256
            != calibration_report_time_axis_sha256(comparison.time)
        ):
            issues.add("calibration_execution_target_bytes_mismatch")

    envelope_digests: dict[str, str] = {}
    try:
        for field_name, envelope in (report.uncertainty_envelopes or {}).items():
            envelope_digests[field_name] = canonical_input_sha256(envelope)
    except (TypeError, ValueError, OverflowError):
        issues.add("calibration_execution_report_envelope_not_serializable")
    if envelope_digests != dict(basis.report_envelope_sha256):
        issues.add("calibration_execution_report_envelope_mismatch")
    try:
        fitted_values_digest = canonical_input_sha256(report.calibrated_params)
    except (TypeError, ValueError, OverflowError):
        issues.add("calibration_execution_fitted_values_not_serializable")
    else:
        if fitted_values_digest != basis.calibrated_parameter_values_sha256:
            issues.add("calibration_execution_fitted_values_mismatch")

    for binding in basis.runtime_input_roster:
        if binding.status == "selected_source_mismatch":
            issues.add(f"calibration_execution_runtime_input_source_mismatch:{binding.input_name}")
        if binding.status == "not_established":
            blockers.add(
                f"calibration_execution_runtime_input_not_established:{binding.input_name}"
            )
        if binding.status != "resolved_output_content_bound":
            continue
        if binding.resolved_by == ("parameter_inputs",):
            resolved_digest = canonical_input_sha256(
                [item.model_dump(mode="json") for item in basis.parameter_inputs]
            )
        elif binding.resolved_by == ("target_inputs",):
            resolved_digest = canonical_input_sha256(
                [item.model_dump(mode="json") for item in basis.target_inputs]
            )
        elif binding.resolved_by == ("report_series_horizon",):
            horizons = {len(item.model) for item in report.series_comparison.values()}
            resolved_digest = (
                canonical_input_sha256({"steps": next(iter(horizons))})
                if len(horizons) == 1
                else None
            )
        else:
            resolved_digest = None
        if resolved_digest is None:
            blockers.add(
                f"calibration_execution_runtime_input_resolution_not_established:{binding.input_name}"
            )
        elif resolved_digest != binding.value_sha256:
            issues.add(
                f"calibration_execution_runtime_input_resolution_mismatch:{binding.input_name}"
            )

    simulation_ref = state.artifacts_index.get(ARTIFACT_SIMULATION_RESULT_REF)
    if simulation_ref is None:
        blockers.add("source_execution_not_established")
    else:
        try:
            selected_simulation_ref = SimulationResultRef.model_validate(
                simulation_ref.model_dump(mode="python")
            )
            read_calibration_model_source(
                ctx.store,
                role="simulation_result",
                ref=selected_simulation_ref,
                expected_kind=selected_simulation_ref.kind,
                decoder=lambda selected, _manifest, _payload: selected,
                model=SimulationResult,
            ).require_value()
            admitted = admit_execution_source(ctx.store, selected_simulation_ref)
        except ExecutionSourceAdmissionRefusal:
            if simulation_ref.manifest_profile_sha256 is None:
                blockers.add("source_execution_not_established")
            else:
                issues.add("selected_simulation_execution_source_invalid")
        except (
            FileNotFoundError,
            PermissionError,
            NotImplementedError,
            TypeError,
            ValueError,
            KeyError,
        ) as error:
            record_calibration_source_error(
                error,
                role="selected_simulation_execution_source_invalid",
                limitations=blockers,
                issues=issues,
            )
        else:
            if admitted.mode != "single_step_basis" or admitted.basis is None:
                blockers.add("source_execution_not_established")
            else:
                source_basis = admitted.basis
                graph = None
                plan = None
                mechanism_registry = None
                units_registry = None
                selected_registry_content = None
                if _artifact_ref_identity(basis.program_graph_ref) != _artifact_ref_identity(
                    source_basis.program_graph_ref
                ):
                    issues.add("calibration_execution_program_graph_mismatch")
                if basis.exec_plan_ref is None:
                    blockers.add("calibration_exec_plan_source_not_established")
                elif _artifact_ref_identity(basis.exec_plan_ref) != _artifact_ref_identity(
                    source_basis.exec_plan_ref
                ):
                    issues.add("calibration_execution_exec_plan_mismatch")
                if _artifact_ref_identity(basis.base_state_snapshot_ref) != _artifact_ref_identity(
                    source_basis.base_state_snapshot_ref
                ):
                    issues.add("calibration_execution_base_state_mismatch")
                if basis.program_graph_status != "selected_source_matched":
                    blockers.add("calibration_program_graph_source_not_established")
                if basis.exec_plan_source_status != "selected_source_matched":
                    blockers.add("calibration_exec_plan_source_not_established")
                try:
                    graph = read_calibration_model_source(
                        ctx.store,
                        role="program_graph",
                        ref=basis.program_graph_ref,
                        expected_kind=basis.program_graph_ref.kind,
                        decoder=lambda _ref, _manifest, payload: payload,
                        model=ProgramGraph,
                    ).require_value()
                    plan = (
                        read_calibration_model_source(
                            ctx.store,
                            role="exec_plan",
                            ref=basis.exec_plan_ref,
                            expected_kind=basis.exec_plan_ref.kind,
                            decoder=lambda _ref, _manifest, payload: payload,
                            model=ExecPlan,
                        ).require_value()
                        if basis.exec_plan_ref is not None
                        else basis.exec_plan
                    )
                    if canonical_input_sha256(graph) != basis.program_graph_sha256:
                        issues.add("calibration_execution_program_graph_digest_mismatch")
                    if canonical_input_sha256(plan) != basis.exec_plan_sha256:
                        issues.add("calibration_execution_exec_plan_digest_mismatch")
                    if basis.exec_plan_ref is not None and plan != basis.exec_plan:
                        issues.add("calibration_execution_exec_plan_object_mismatch")
                    if _artifact_ref_identity(plan.program_ref) != _artifact_ref_identity(
                        basis.program_graph_ref
                    ):
                        issues.add("calibration_execution_plan_graph_mismatch")
                except (
                    FileNotFoundError,
                    PermissionError,
                    NotImplementedError,
                    TypeError,
                    ValueError,
                    KeyError,
                ) as error:
                    record_calibration_source_error(
                        error,
                        role="calibration_execution_source_payload_invalid",
                        limitations=blockers,
                        issues=issues,
                    )
                try:
                    state_manifest = read_calibration_model_source(
                        ctx.store,
                        role="base_state_snapshot",
                        ref=basis.base_state_snapshot_ref,
                        expected_kind="foundry.state_snapshot",
                        decoder=lambda _ref, manifest, _payload: manifest,
                        model=StateSnapshot,
                    ).require_value()
                    state_blob_ref = read_calibration_source(
                        ctx.store,
                        role="state_blob",
                        inputs=state_manifest.inputs,
                        expected_media_type=None,
                        decoder=lambda selected, _manifest, _payload: selected,
                    ).require_value()
                    state_blob = ctx.store.get_bytes(state_blob_ref)
                    raw_sha256 = hashlib.sha256(state_blob).hexdigest()
                    if (
                        raw_sha256 != state_blob_ref.artifact_id.hex
                        or basis.base_state_checksum_sha256 != raw_sha256
                    ):
                        issues.add("calibration_execution_base_state_digest_mismatch")
                except (
                    FileNotFoundError,
                    PermissionError,
                    NotImplementedError,
                    TypeError,
                    ValueError,
                    KeyError,
                ) as error:
                    record_calibration_source_error(
                        error,
                        role="calibration_execution_state_snapshot_invalid",
                        limitations=blockers,
                        issues=issues,
                    )

                source_mechanism_ref = source_basis.runtime_registry_members.mechanism_registry
                source_units_ref = source_basis.runtime_registry_members.units_registry
                try:
                    selected_registry_content = read_calibration_registry_source(
                        ctx.store,
                        source_basis.runtime_registry_ref,
                    ).require_value()
                except (
                    FileNotFoundError,
                    PermissionError,
                    NotImplementedError,
                    TypeError,
                    ValueError,
                    KeyError,
                ) as error:
                    record_calibration_source_error(
                        error,
                        role="calibration_execution_runtime_registry_members_invalid",
                        limitations=blockers,
                        issues=issues,
                    )
                for input_name, ref_field, _kind, _schema_name in RUNTIME_REGISTRY_MEMBER_CONTRACT:
                    binding = next(
                        (
                            item
                            for item in basis.runtime_input_roster
                            if item.input_name == input_name
                        ),
                        None,
                    )
                    if binding is None:
                        issues.add("calibration_execution_runtime_input_roster_incomplete")
                        continue
                    if binding.status == "not_consumed":
                        continue
                    member_ref = getattr(source_basis.runtime_registry_members, ref_field)
                    member_value = (
                        getattr(selected_registry_content, input_name)
                        if selected_registry_content is not None
                        else None
                    )
                    member_status = reconcile_selected_runtime_input(
                        binding,
                        selected_ref=member_ref,
                        selected_value=member_value,
                    )
                    if member_status == "mismatch":
                        issues.add(
                            f"calibration_execution_runtime_input_source_mismatch:{input_name}"
                        )
                    elif member_status == "not_established":
                        blockers.add(
                            f"calibration_execution_runtime_input_source_not_established:{input_name}"
                        )
                if basis.registry_bundle_ref is None:
                    blockers.add("calibration_registry_bundle_source_not_established")
                elif _artifact_ref_identity(basis.registry_bundle_ref) != _artifact_ref_identity(
                    source_basis.runtime_registry_ref
                ):
                    issues.add("calibration_execution_registry_bundle_mismatch")
                elif basis.registry_bundle_status == "selected_source_mismatch":
                    issues.add("calibration_execution_registry_bundle_source_mismatch")
                elif basis.registry_bundle_status != "selected_source_matched":
                    blockers.add("calibration_registry_bundle_source_not_established")
                elif basis.registry_bundle_sha256 != canonical_input_sha256(
                    source_basis.runtime_registry_members
                ):
                    issues.add("calibration_execution_registry_bundle_digest_mismatch")

                mechanism_source_selected = False
                units_source_selected = False
                if basis.mechanism_registry_ref is None:
                    blockers.add("calibration_mechanism_registry_source_not_established")
                elif _artifact_ref_identity(basis.mechanism_registry_ref) != _artifact_ref_identity(
                    source_mechanism_ref
                ):
                    issues.add("calibration_execution_mechanism_registry_mismatch")
                elif basis.mechanism_registry_status == "selected_source_mismatch":
                    issues.add("calibration_execution_mechanism_registry_source_mismatch")
                elif basis.mechanism_registry_status != "selected_source_matched":
                    blockers.add("calibration_mechanism_registry_source_not_established")
                else:
                    try:
                        mechanism_registry = _load_registry_model(
                            ctx,
                            source_mechanism_ref,
                            MechanismTypeRegistry,
                            expected_kind="ir.mechanism_registry",
                            expected_schema="polisyos.ir.kernel.MechanismTypeRegistry",
                        )
                        mechanism_source_selected = True
                        if basis.mechanism_registry_sha256 != canonical_input_sha256(
                            mechanism_registry
                        ):
                            issues.add("calibration_execution_mechanism_registry_digest_mismatch")
                    except (
                        FileNotFoundError,
                        PermissionError,
                        NotImplementedError,
                        TypeError,
                        ValueError,
                        KeyError,
                    ) as error:
                        record_calibration_source_error(
                            error,
                            role="calibration_execution_mechanism_registry_invalid",
                            limitations=blockers,
                            issues=issues,
                        )

                if basis.unit_registry_ref is None:
                    if source_units_ref is not None:
                        blockers.add("calibration_unit_registry_source_not_established")
                elif source_units_ref is None or _artifact_ref_identity(
                    basis.unit_registry_ref
                ) != _artifact_ref_identity(source_units_ref):
                    issues.add("calibration_execution_unit_registry_mismatch")
                elif basis.unit_registry_status == "selected_source_mismatch":
                    issues.add("calibration_execution_unit_registry_source_mismatch")
                elif basis.unit_registry_status != "selected_source_matched":
                    blockers.add("calibration_unit_registry_source_not_established")
                else:
                    try:
                        units_registry = _load_registry_model(
                            ctx,
                            source_units_ref,
                            UnitsRegistry,
                            expected_kind="ir.units_registry",
                            expected_schema="polisyos.ir.kernel.UnitsRegistry",
                        )
                        units_source_selected = True
                        if basis.unit_registry_sha256 != canonical_input_sha256(units_registry):
                            issues.add("calibration_execution_unit_registry_digest_mismatch")
                    except (
                        FileNotFoundError,
                        PermissionError,
                        NotImplementedError,
                        TypeError,
                        ValueError,
                        KeyError,
                    ) as error:
                        record_calibration_source_error(
                            error,
                            role="calibration_execution_unit_registry_invalid",
                            limitations=blockers,
                            issues=issues,
                        )

                if graph is not None and plan is not None:
                    expected_parameter_rows = _graph_parameter_nodes(graph, plan)
                    actual_parameter_rows = tuple(
                        (row.node_id, row.mechanism_type, row.source_ref)
                        for row in basis.parameter_inputs
                    )
                    if actual_parameter_rows != expected_parameter_rows:
                        issues.add("calibration_execution_parameter_sources_mismatch")
                    for parameter_input in basis.parameter_inputs:
                        if parameter_input.source_status == "selected_source_mismatch":
                            issues.add("calibration_execution_parameter_source_mismatch")
                            continue
                        if parameter_input.source_status != "selected_source_matched":
                            blockers.add("calibration_parameter_source_not_established")
                            continue
                        if parameter_input.source_ref is None:
                            issues.add("calibration_execution_parameter_source_missing")
                            continue
                        try:
                            selected_payload = read_calibration_source(
                                ctx.store,
                                role="parameter_source",
                                ref=parameter_input.source_ref,
                                expected_kind=parameter_input.source_ref.kind,
                                decoder=lambda _ref, _manifest, payload: payload,
                            ).require_value()
                            selected_digest = canonical_input_sha256(selected_payload)
                            if (
                                selected_digest != parameter_input.source_payload_sha256
                                or selected_digest != parameter_input.payload_sha256
                            ):
                                issues.add("calibration_execution_parameter_source_digest_mismatch")
                        except (
                            FileNotFoundError,
                            PermissionError,
                            NotImplementedError,
                            TypeError,
                            ValueError,
                            KeyError,
                        ) as error:
                            record_calibration_source_error(
                                error,
                                role="calibration_execution_parameter_source_invalid",
                                limitations=blockers,
                                issues=issues,
                            )
                    if mechanism_registry is not None:
                        try:
                            expected_unit_identities = _expected_parameter_unit_identities(
                                graph=graph,
                                plan=plan,
                                mechanism_registry=mechanism_registry,
                                units_registry=units_registry,
                                mechanism_source_selected=mechanism_source_selected,
                                units_source_selected=units_source_selected,
                            )
                            actual_unit_identities = tuple(
                                item.model_dump(mode="json")
                                for item in basis.parameter_unit_identities
                            )
                            if actual_unit_identities != tuple(
                                item.model_dump(mode="json") for item in expected_unit_identities
                            ):
                                issues.add("calibration_execution_parameter_unit_identity_mismatch")
                        except (TypeError, ValueError, KeyError):
                            issues.add("calibration_execution_parameter_contract_invalid")

                try:
                    expected_overrides: dict[str, dict[str, float]] = {}
                    for field_name, value in report.calibrated_params.items():
                        node_id, separator, parameter_id = field_name.partition(".")
                        if not separator or not node_id or not parameter_id:
                            raise ValueError("calibrated_parameter_field_name_invalid")
                        expected_overrides.setdefault(node_id, {})[parameter_id] = float(value)
                    actual_overrides = {
                        node_id: {
                            parameter_id: float(value) for parameter_id, value in values.items()
                        }
                        for node_id, values in (source_basis.parameter_overrides or {}).items()
                    }
                    if actual_overrides != expected_overrides:
                        issues.add("calibration_execution_parameter_overrides_mismatch")
                except (TypeError, ValueError, OverflowError):
                    issues.add("calibration_execution_parameter_overrides_not_serializable")

    if basis.ordered_batch_profile is not None and not issues and not blockers:
        replay_status, replay_details = replay_ordered_batch_report_projection(
            ctx.store, basis_ref, report_ref
        )
        if replay_status == "mismatch":
            issues.update(replay_details)
        elif replay_status == "not_established":
            blockers.update(replay_details)
        else:
            limitations.update(replay_details)
    if issues:
        return "mismatch", tuple(sorted(limitations | blockers)), tuple(sorted(issues))
    if blockers:
        return "not_established", tuple(sorted(limitations | blockers)), ()
    return "matched", tuple(sorted(limitations)), ()


def _envelope_origin(
    *,
    source_role: str,
    ref: ArtifactRefModel | None,
) -> _EnvelopeOrigin:
    artifact_key = None
    if ref is not None:
        artifact_key = (ref.kind, str(ref.artifact_id))
    return _EnvelopeOrigin(artifact_key=artifact_key, source_role=source_role)


def _load_model(ctx: ExecutionContext, ref: ArtifactRef, model_cls):
    payload = _load_artifact_json(ctx, ref)
    if model_cls is Metrics and isinstance(payload, Mapping):
        # Metrics accepts bool through Pydantic's numeric union coercion; inspect the
        # uncoerced artifact with the same admission boundary before that information is lost.
        _extract_numeric_metrics(payload)
    return model_cls.model_validate(payload)


def _equilibrium_multiplicity_annotation(
    ctx: ExecutionContext,
    sim_result: SimulationResult,
) -> EquilibriumMultiplicityWelfareAnnotation:
    if sim_result.feedback_result_ref is None:
        return EquilibriumMultiplicityWelfareAnnotation(status="not_checked")
    try:
        feedback = _load_model(ctx, sim_result.feedback_result_ref, FeedbackSolveResult)
    except _WELFARE_LOAD_ERRORS:
        return EquilibriumMultiplicityWelfareAnnotation(
            status="unresolved",
            materiality_note="feedback_result_unavailable_for_multiplicity_annotation",
        )
    report_ref = feedback.multiplicity_report_ref
    if report_ref is None:
        return EquilibriumMultiplicityWelfareAnnotation(status="not_checked")
    generic_ref = ArtifactRefModel.model_validate(report_ref.model_dump(mode="python"))
    try:
        report = _load_model(ctx, report_ref, EquilibriumMultiplicityReport)
    except _WELFARE_LOAD_ERRORS:
        return EquilibriumMultiplicityWelfareAnnotation(
            status="unresolved",
            report_ref=generic_ref,
            selection_dependence=True,
            materiality_note="equilibrium_multiplicity_report_unavailable",
        )
    count = int(report.global_diagnostics.num_equilibria)
    unresolved = int(report.global_diagnostics.num_unresolved)
    status: Literal["unique", "multiple", "unresolved", "not_checked"]
    if count > 1:
        status = "multiple"
    elif unresolved > 0:
        status = "unresolved"
    elif count == 1:
        status = "unique"
    else:
        status = "unresolved"
    return EquilibriumMultiplicityWelfareAnnotation(
        status=status,
        report_ref=generic_ref,
        selection_dependence=status in {"multiple", "unresolved"},
        materiality_note=(
            f"equilibria={count}; unresolved_starts={unresolved}; "
            f"bifurcation_candidates={len(report.bifurcation_candidates)}"
        ),
        metadata={
            "num_equilibria": count,
            "num_unresolved": unresolved,
            "bifurcation_candidate_count": len(report.bifurcation_candidates),
        },
    )


def _load_welfare_params(state: ExperimentState) -> dict[str, Any]:
    resolved: dict[str, Any] = {}
    raw_config = state.params.get("welfare_config")
    if isinstance(raw_config, dict):
        resolved.update(raw_config)
    for key, value in state.params.items():
        if key.startswith("welfare_"):
            resolved[key[8:]] = value
    return resolved


def _has_explicit_welfare_request(
    welfare_params: Mapping[str, Any],
    *,
    keys: frozenset[str],
) -> bool:
    for key in keys:
        if welfare_params.get(key) is not None:
            return True
        prefixed_key = f"welfare_{key}"
        if welfare_params.get(prefixed_key) is not None:
            return True
    return False


def _coerce_welfare_numeric_scalar(value: object, *, allow_numeric_string: bool = False) -> float:
    """Convert a supported real scalar without accepting boolean or arbitrary objects."""
    if isinstance(value, (bool, np.bool_)):
        raise TypeError("boolean values are not welfare numeric scalars")
    if not isinstance(value, (Real, Decimal)) and not (
        allow_numeric_string and isinstance(value, str)
    ):
        raise TypeError("value is outside the declared welfare numeric input types")
    try:
        numeric = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("welfare numeric scalar could not be represented as float") from exc
    if not math.isfinite(numeric):
        raise ValueError("welfare numeric scalar must be finite")
    return numeric


def _admit_welfare_numeric_scalar(value: object, *, field_name: str) -> float:
    try:
        return _coerce_welfare_numeric_scalar(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise _fail_error(
            _ERROR_WELFARE_DIMENSION_MISMATCH,
            f"{field_name} values must be finite real numeric scalars",
            details={"field": field_name, "received_type": type(value).__name__},
        ) from exc


def _admit_welfare_numeric_mapping(
    values: Mapping[object, object], *, field_name: str
) -> dict[str, float]:
    admitted: dict[str, float] = {}
    for key, value in values.items():
        if not isinstance(key, str) or not key.strip():
            raise _fail_error(
                _ERROR_WELFARE_DIMENSION_MISMATCH,
                f"{field_name} mapping keys must be non-empty strings",
                details={"field": field_name},
            )
        admitted[key] = _admit_welfare_numeric_scalar(value, field_name=field_name)
    return admitted


def _admit_welfare_numeric_sequence(
    values: list[object] | tuple[object, ...], *, field_name: str
) -> np.ndarray:
    return np.asarray(
        [_admit_welfare_numeric_scalar(value, field_name=field_name) for value in values],
        dtype=np.float64,
    )


def _extract_numeric_metrics(metrics: Metrics | Mapping[str, Any]) -> dict[str, float]:
    values = metrics.values if isinstance(metrics, Metrics) else metrics.get("values", {})
    if not isinstance(values, Mapping):
        return {}
    out: dict[str, float] = {}
    for key, value in values.items():
        try:
            numeric = _coerce_welfare_numeric_scalar(value, allow_numeric_string=True)
        except (TypeError, ValueError, OverflowError) as exc:
            if isinstance(value, (bool, np.bool_)):
                raise _fail_error(
                    _ERROR_WELFARE_DIMENSION_MISMATCH,
                    "Simulation metrics cannot use boolean values as welfare scalars",
                    details={"metric": str(key)},
                ) from exc
            continue
        out[str(key)] = numeric
    return out


def _admit_input_envelope(
    name: str,
    envelope: UncertaintyEnvelope,
    *,
    source_role: str,
    envelopes: dict[str, UncertaintyEnvelope],
    refs: dict[str, UncertaintyEnvelopeRef],
    origins: dict[str, _EnvelopeOrigin],
    calibration_issues: set[str],
    origin_ref: ArtifactRefModel | None = None,
    ref: UncertaintyEnvelopeRef | None = None,
) -> None:
    """Admit one envelope while preserving its source and calibration conflict state."""
    previous = envelopes.get(name)
    previous_origin = origins.get(name)
    current_origin = _envelope_origin(source_role=source_role, ref=origin_ref)
    if previous is not None and previous_origin is not None:
        same_source = (
            current_origin.artifact_key is not None
            and current_origin.artifact_key == previous_origin.artifact_key
        )
        same_content = previous.model_dump(mode="json") == envelope.model_dump(mode="json")
        if same_source and same_content:
            return
        if (
            previous_origin.source_role == "calibration_report"
            or source_role == "calibration_report"
        ):
            calibration_issues.add("calibration_envelope_conflict")
            if previous_origin.source_role == "calibration_report":
                return
    elif previous is not None and (
        previous_origin is None
        or previous_origin.source_role == "calibration_report"
        or source_role == "calibration_report"
    ):
        # Equal values without a shared content-addressed origin are not evidence that
        # two producers admitted the same envelope.
        calibration_issues.add("calibration_envelope_conflict")
        if previous_origin is not None and previous_origin.source_role == "calibration_report":
            return
    envelopes[name] = envelope
    origins[name] = current_origin
    if ref is None:
        refs.pop(name, None)
    else:
        refs[name] = ref


def _load_calibration_report_envelopes(
    ctx: ExecutionContext,
    report: CalibrationReport,
    calibration_ref: ArtifactRefModel,
    *,
    admit: Any,
) -> list[str]:
    """Load report-owned envelopes and admit them with their exact source refs."""
    loaded_names: list[str] = []
    if report.uncertainty_envelope_refs:
        for name, ref in report.uncertainty_envelope_refs.items():
            key = str(name)
            loaded_names.append(key)
            admit(
                key,
                load_uncertainty_envelope(_ensure_ir_artifact_store(ctx.store), ref),
                source_role="calibration_report",
                origin_ref=ref,
                ref=ref,
            )
    elif report.uncertainty_envelopes:
        for name, envelope in report.uncertainty_envelopes.items():
            key = str(name)
            loaded_names.append(key)
            admit(
                key,
                envelope,
                source_role="calibration_report",
                origin_ref=calibration_ref,
            )
    return loaded_names


def _calibration_fields_from_report(
    report: CalibrationReport,
    *,
    loaded_names: list[str],
    projection_present: bool,
    projection_status: str,
    issues: set[str],
) -> tuple[str, ...]:
    """Resolve calibration field order and record unsupported projection states."""
    if report.coordinate_projection is not None:
        fields = report.coordinate_projection.field_order
        if report.uncertainties is not None and not set(fields) <= set(loaded_names):
            issues.add("calibration_covariance_invalid")
    else:
        fields = tuple(loaded_names) or tuple(str(name) for name in report.calibrated_params)
        if report.uncertainties is not None:
            legacy_identity = (
                report.schema_version == "1.0"
                and set(report.uncertainties.params) == set(report.calibrated_params)
                and len(report.uncertainties.params) == len(report.calibrated_params)
            )
            if projection_status == "incomplete":
                issues.add("calibration_projection_incomplete")
            elif projection_status == "unsupported":
                issues.add("calibration_projection_unsupported")
            elif not legacy_identity:
                issues.add("calibration_projection_missing")
    if not loaded_names and report.uncertainties is not None:
        issues.add(
            "calibration_projection_missing"
            if not projection_present
            else "calibration_covariance_invalid"
        )
    return tuple(fields)


def _collect_inline_envelopes(
    ctx: ExecutionContext,
    *,
    welfare_params: Mapping[str, Any],
    calibration_fields: tuple[str, ...],
    calibration_issues: set[str],
    admit: Any,
) -> None:
    """Admit valid inline envelopes and retain conflicts with calibration fields."""
    raw_input_envelopes = welfare_params.get("input_envelopes")
    if not isinstance(raw_input_envelopes, dict):
        return
    for name, value in raw_input_envelopes.items():
        if not isinstance(name, str) or not name.strip():
            continue
        if isinstance(value, dict) and {"artifact_id", "kind", "media_type"} <= set(value):
            ref = UncertaintyEnvelopeRef.model_validate(value)
            admit(
                name,
                load_uncertainty_envelope(_ensure_ir_artifact_store(ctx.store), ref),
                source_role="inline_ref",
                origin_ref=ref,
                ref=ref,
            )
            continue
        try:
            admit(
                name,
                UncertaintyEnvelope.model_validate(value),
                source_role="inline",
            )
        except _WELFARE_VALIDATION_ERRORS:
            logger.debug("Invalid inline welfare input envelope for %s", name, exc_info=True)
            if name in calibration_fields:
                calibration_issues.add("calibration_envelope_conflict")


def _build_calibration_covariance_source(
    calibration_ref: ArtifactRefModel | None,
    report: CalibrationReport | None,
    *,
    fields: tuple[str, ...],
    projection_present: bool,
    projection_status: str,
    issues: set[str],
    source_execution_status: Literal["matched", "not_established", "mismatch"] = (
        "not_established"
    ),
    source_execution_limitations: tuple[str, ...] = (),
) -> _CalibrationCovarianceSource | None:
    """Build the report-bound covariance source only when it carries a relevant field."""
    if calibration_ref is None or report is None or not (fields or issues):
        return None
    coordinate_order = (
        tuple(report.uncertainties.params) if report.uncertainties is not None else ()
    )
    coordinate_covariance = (
        tuple(tuple(float(value) for value in row) for row in report.uncertainties.covariance)
        if report.uncertainties is not None
        else ()
    )
    return _CalibrationCovarianceSource(
        report_ref=calibration_ref,
        report_schema_version=report.schema_version,
        projection_status=projection_status,
        field_order=fields,
        projection_present=projection_present,
        coordinate_projection=report.coordinate_projection,
        coordinate_order=coordinate_order,
        coordinate_covariance=coordinate_covariance,
        issue_codes=tuple(sorted(issues)),
        source_execution_status=source_execution_status,
        source_execution_limitations=source_execution_limitations,
        inference_status=(
            "curvature_only"
            if report.ordered_batch_execution is not None
            or "calibration_batch_curvature_only" in source_execution_limitations
            else "not_established"
        ),
    )


def _collect_input_envelopes(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    welfare_params: Mapping[str, Any],
) -> _EnvelopeCollection:
    calibration_ref = state.inputs.get(INPUT_CALIBRATION_REPORT_REF)
    report = None
    if calibration_ref is not None:
        source = read_calibration_report_source(ctx.store, ref=calibration_ref)
        if source.status != "matched":
            raise _fail_error(
                "welfare.calibration_source_invalid",
                "Selected calibration report cannot supply welfare inputs",
                details={
                    "input": f"inputs.{INPUT_CALIBRATION_REPORT_REF}",
                    "source_status": source.status,
                    "source_code": source.code,
                },
            )
        report = source.require_value()
    envelopes: dict[str, UncertaintyEnvelope] = {}
    refs: dict[str, UncertaintyEnvelopeRef] = {}
    origins: dict[str, _EnvelopeOrigin] = {}
    calibration_issues: set[str] = set()

    def admit(name: str, envelope: UncertaintyEnvelope, **kwargs: Any) -> None:
        _admit_input_envelope(
            name,
            envelope,
            envelopes=envelopes,
            refs=refs,
            origins=origins,
            calibration_issues=calibration_issues,
            **kwargs,
        )

    data_snapshot_ref = state.inputs.get(INPUT_DATA_SNAPSHOT_REF)
    if data_snapshot_ref is not None:
        snapshot = _load_model(ctx, data_snapshot_ref, DataSnapshot)
        if snapshot.uncertainty_envelope_ref is not None:
            envelope_ref = snapshot.uncertainty_envelope_ref
            envelope = load_uncertainty_envelope(_ensure_ir_artifact_store(ctx.store), envelope_ref)
            raw_name = envelope.metadata.get("param_name")
            name = (
                str(raw_name) if isinstance(raw_name, str) and raw_name.strip() else "data_snapshot"
            )
            admit(
                name,
                envelope,
                source_role="data_snapshot",
                origin_ref=envelope_ref,
                ref=envelope_ref,
            )

    projection_present = report is not None and report.coordinate_projection is not None
    projection_status = (
        (report.coordinate_projection_status or "not_established")
        if report is not None
        else "not_established"
    )
    if projection_status == "incomplete":
        calibration_issues.add("calibration_projection_incomplete")
    elif projection_status == "unsupported":
        calibration_issues.add("calibration_projection_unsupported")

    calibration_fields: tuple[str, ...] = ()
    source_execution_status: Literal["matched", "not_established", "mismatch"] = "not_established"
    source_execution_limitations: tuple[str, ...] = ()
    if report is not None and calibration_ref is not None:
        (
            source_execution_status,
            source_execution_limitations,
            source_execution_issues,
        ) = _calibration_execution_source_join(
            ctx,
            state,
            report_ref=calibration_ref,
            report=report,
        )
        calibration_issues.update(source_execution_issues)
        loaded_names = _load_calibration_report_envelopes(ctx, report, calibration_ref, admit=admit)
        calibration_fields = _calibration_fields_from_report(
            report,
            loaded_names=loaded_names,
            projection_present=projection_present,
            projection_status=projection_status,
            issues=calibration_issues,
        )

    _collect_inline_envelopes(
        ctx,
        welfare_params=welfare_params,
        calibration_fields=calibration_fields,
        calibration_issues=calibration_issues,
        admit=admit,
    )
    calibration_source = _build_calibration_covariance_source(
        calibration_ref,
        report,
        fields=calibration_fields,
        projection_present=projection_present,
        projection_status=projection_status,
        issues=calibration_issues,
        source_execution_status=source_execution_status,
        source_execution_limitations=source_execution_limitations,
    )
    return _EnvelopeCollection(
        envelopes=envelopes,
        refs=refs,
        calibration_source=calibration_source,
    )


def _resolve_welfare_context(
    ctx: ExecutionContext,
    *,
    welfare_params: Mapping[str, Any],
    numeric_metrics: Mapping[str, float],
    response_size_hint: int,
    return_selected_profile: bool = False,
) -> _ResolvedWelfareContext:
    labels, base_response = _resolve_base_response(
        welfare_params=welfare_params,
        numeric_metrics=numeric_metrics,
    )
    weights, weights_ref = _resolve_weights(
        ctx,
        welfare_params=welfare_params,
        labels=labels,
        return_selected_profile=return_selected_profile,
    )
    social_weight_ref = ensure_social_weight_manifest_artifact(
        ctx,
        welfare_params=welfare_params,
        return_selected_profile=return_selected_profile,
    )
    policy_ref = _coerce_artifact_ref(welfare_params.get("policy_ref"))
    baseline_ref = _coerce_artifact_ref(welfare_params.get("baseline_ref"))
    pe_model_ref = _coerce_artifact_ref(welfare_params.get("pe_model_ref"))
    dependence_context = _resolve_dependence_context(ctx, welfare_params)
    dependence_structure_ref = dependence_context.ref
    pe_sensitivity = _resolve_pe_sensitivity(
        welfare_params=welfare_params,
        labels=labels,
    )
    ge_multiplier_semantics = _resolve_ge_multiplier_semantics(welfare_params)
    model_class = str(welfare_params.get("model_class") or "linearized_ge_io")
    _validate_model_class(model_class, ge_multiplier_semantics)
    ge_context = _resolve_ge_context(
        ctx,
        welfare_params=welfare_params,
        size=len(labels),
        ge_multiplier_semantics=ge_multiplier_semantics,
    )
    if ge_context.point_multiplier is not None and ge_context.point_multiplier.shape != (
        len(labels),
        len(labels),
    ):
        raise _fail_error(
            _ERROR_WELFARE_DIMENSION_MISMATCH,
            "GE multiplier dimensions do not match welfare response vector",
            details={
                "multiplier_shape": list(ge_context.point_multiplier.shape),
                "response_size": len(labels),
            },
        )
    warnings = list(ge_context.warnings)
    diagnostics = {
        "response_size": len(labels),
        "metric_labels": list(labels),
        "weights_norm": float(np.linalg.norm(weights)),
        "response_size_hint": response_size_hint,
        "dependence_structure": dependence_context.diagnostics,
        **ge_context.diagnostics,
    }
    return _ResolvedWelfareContext(
        welfare_measure=str(welfare_params.get("measure") or "net_social_welfare"),
        model_class=model_class,
        ge_multiplier_semantics=ge_multiplier_semantics,
        labels=labels,
        base_response=base_response,
        weights=weights,
        weights_ref=weights_ref,
        social_weight_ref=social_weight_ref,
        policy_ref=policy_ref,
        baseline_ref=baseline_ref,
        pe_model_ref=pe_model_ref,
        dependence_structure_ref=dependence_structure_ref,
        dependence_context=dependence_context,
        pe_sensitivity=pe_sensitivity,
        ge_context=ge_context,
        warnings=tuple(warnings),
        diagnostics=diagnostics,
    )


def _response_from_mapping(
    raw_response: Mapping[str, Any], metric_order: list[str] | None
) -> tuple[tuple[str, ...], np.ndarray]:
    if not raw_response:
        raise _fail_error(
            _ERROR_WELFARE_DIMENSION_MISMATCH,
            "welfare_pe_response must contain at least one response component",
        )
    admitted_response = _admit_welfare_numeric_mapping(
        raw_response, field_name="welfare_pe_response"
    )
    labels = metric_order or list(admitted_response)
    missing = [label for label in labels if label not in admitted_response]
    if missing:
        raise _fail_error(
            _ERROR_WELFARE_DIMENSION_MISMATCH,
            "welfare_pe_response is missing a requested metric_order label",
            details={"missing_labels": missing},
        )
    vector = np.asarray([admitted_response[label] for label in labels], dtype=np.float64)
    return tuple(labels), vector


def _response_from_sequence(
    raw_response: list[Any] | tuple[Any, ...], metric_order: list[str] | None
) -> tuple[tuple[str, ...], np.ndarray]:
    if not raw_response:
        raise _fail_error(
            _ERROR_WELFARE_DIMENSION_MISMATCH,
            "welfare_pe_response must contain at least one response component",
        )
    vector = _admit_welfare_numeric_sequence(raw_response, field_name="welfare_pe_response")
    if metric_order is not None and len(metric_order) != vector.shape[0]:
        raise _fail_error(
            _ERROR_WELFARE_DIMENSION_MISMATCH,
            "welfare_metric_order length must match welfare_pe_response length",
            details={
                "metric_order": len(metric_order),
                "pe_response": int(vector.shape[0]),
            },
        )
    labels = (
        tuple(f"component_{idx}" for idx in range(vector.shape[0]))
        if metric_order is None
        else tuple(metric_order)
    )
    return labels, vector


def _response_from_metrics(
    labels: list[str], numeric_metrics: Mapping[str, float], *, error_message: str
) -> tuple[tuple[str, ...], np.ndarray]:
    missing = [label for label in labels if label not in numeric_metrics]
    if missing:
        raise _fail_error(
            _ERROR_WELFARE_DIMENSION_MISMATCH,
            error_message,
            details={"missing_metrics": missing},
        )
    vector = np.asarray(
        [
            _admit_welfare_numeric_scalar(numeric_metrics[label], field_name="simulation metrics")
            for label in labels
        ],
        dtype=np.float64,
    )
    return tuple(labels), vector


def _resolve_base_response(
    *,
    welfare_params: Mapping[str, Any],
    numeric_metrics: Mapping[str, float],
) -> tuple[tuple[str, ...], np.ndarray]:
    numeric_metrics = _admit_welfare_numeric_mapping(
        numeric_metrics, field_name="simulation metrics"
    )
    metric_order: list[str] | None = None
    if "metric_order" in welfare_params:
        raw_order = welfare_params["metric_order"]
        if (
            not isinstance(raw_order, (list, tuple))
            or not raw_order
            or any(not isinstance(label, str) or not label.strip() for label in raw_order)
            or len(set(raw_order)) != len(raw_order)
        ):
            raise _fail_error(
                _ERROR_WELFARE_DIMENSION_MISMATCH,
                "welfare_metric_order must contain unique non-empty labels",
            )
        metric_order = list(raw_order)
    if "pe_response" in welfare_params:
        raw_response = welfare_params["pe_response"]
        if isinstance(raw_response, Mapping):
            return _response_from_mapping(raw_response, metric_order)
        if isinstance(raw_response, (list, tuple)):
            return _response_from_sequence(raw_response, metric_order)
        raise _fail_error(
            _ERROR_WELFARE_DIMENSION_MISMATCH,
            "welfare_pe_response must be a mapping or a sequence when provided",
            details={"received_type": type(raw_response).__name__},
        )
    if metric_order is not None:
        return _response_from_metrics(
            metric_order,
            numeric_metrics,
            error_message="Requested welfare_metric_order labels are missing from simulation metrics",
        )
    raw_weights = welfare_params.get("weights")
    if isinstance(raw_weights, Mapping):
        return _response_from_metrics(
            [str(key) for key in raw_weights],
            numeric_metrics,
            error_message=(
                "welfare_weights keys must align with numeric simulation metrics when pe_response is omitted"
            ),
        )
    for candidate in ("net_social_welfare", "welfare", "policy_value", "gdp_change"):
        if candidate in numeric_metrics:
            return (candidate,), np.asarray(
                [
                    _admit_welfare_numeric_scalar(
                        numeric_metrics[candidate], field_name="simulation metrics"
                    )
                ],
                dtype=np.float64,
            )
    if len(numeric_metrics) == 1:
        label, value = next(iter(numeric_metrics.items()))
        return (label,), np.asarray(
            [_admit_welfare_numeric_scalar(value, field_name="simulation metrics")],
            dtype=np.float64,
        )
    raise _fail_error(
        _ERROR_WELFARE_DIMENSION_MISMATCH,
        "No welfare target could be resolved from metrics or welfare_pe_response",
        details={"available_metrics": sorted(numeric_metrics)},
    )


def _resolve_weights(
    ctx: ExecutionContext,
    *,
    welfare_params: Mapping[str, Any],
    labels: tuple[str, ...],
    return_selected_profile: bool = False,
) -> tuple[np.ndarray, ArtifactRefModel | None]:
    if not labels:
        raise _fail_error(
            _ERROR_WELFARE_DIMENSION_MISMATCH,
            "Welfare aggregation requires at least one response label",
        )
    if "weights" not in welfare_params:
        if len(labels) != 1:
            raise _fail_error(
                _ERROR_WELFARE_DIMENSION_MISMATCH,
                "welfare_weights must be provided when aggregating more than one response component",
                details={"labels": list(labels)},
            )
        vector = np.asarray([1.0], dtype=np.float64)
        if not return_selected_profile:
            return vector, None
    else:
        raw_weights = welfare_params["weights"]

        if isinstance(raw_weights, Mapping):
            admitted_weights = _admit_welfare_numeric_mapping(
                raw_weights, field_name="welfare_weights"
            )
            missing = [label for label in labels if label not in raw_weights]
            if missing:
                raise _fail_error(
                    _ERROR_WELFARE_DIMENSION_MISMATCH,
                    "welfare_weights is missing one or more response labels",
                    details={"missing_labels": missing},
                )
            vector = np.asarray([admitted_weights[label] for label in labels], dtype=np.float64)
        elif isinstance(raw_weights, (list, tuple)):
            vector = _admit_welfare_numeric_sequence(raw_weights, field_name="welfare_weights")
            if vector.shape[0] != len(labels):
                raise _fail_error(
                    _ERROR_WELFARE_DIMENSION_MISMATCH,
                    "welfare_weights length must match response vector length",
                    details={"weights": int(vector.shape[0]), "response": len(labels)},
                )
        else:
            raise _fail_error(
                _ERROR_WELFARE_DIMENSION_MISMATCH,
                "welfare_weights must be a dict keyed by labels or a dense list",
            )
    if not np.all(np.isfinite(vector)):
        raise _fail_error(
            _ERROR_WELFARE_OUTPUT_NONFINITE,
            "welfare_weights must be finite",
        )

    weights_ref = _persist_json_payload(
        ctx,
        payload={"labels": list(labels), "weights": vector.tolist()},
        kind="ir.welfare_weights",
        schema_name="ir.welfare_weights",
        return_selected_profile=return_selected_profile,
    )
    return vector, weights_ref


def _source_social_weight_handle(welfare_params: Mapping[str, Any]) -> str | None:
    for key in (
        "welfare_social_weight_ref",
        "social_weight_ref",
    ):
        value = welfare_params.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _resolve_dependence_context(
    ctx: ExecutionContext,
    welfare_params: Mapping[str, Any],
) -> _ResolvedDependenceContext:
    raw = welfare_params.get("dependence_structure_ref")
    if raw is None:
        return _ResolvedDependenceContext(
            ref=None,
            structure=None,
            correlation_matrix=None,
            parameter_order=(),
            strategy="independent",
            warnings=(),
            diagnostics={"present": False, "strategy": "independent"},
        )
    try:
        ref = DependenceStructureRef.model_validate(raw)
        structure = load_dependence_structure(_ensure_ir_artifact_store(ctx.store), ref)
    except _WELFARE_VALIDATION_ERRORS as exc:
        raise _fail_error(
            _ERROR_DEPENDENCE_SPEC_INVALID,
            "Invalid welfare dependence_structure_ref",
            details={"error": str(exc)},
        ) from exc
    warnings = list(structure.warnings)
    if structure.blocking_reasons:
        warnings.extend(f"blocking:{item}" for item in structure.blocking_reasons)

    metadata = dict(structure.metadata)
    parameter_order = (
        _coerce_str_list(metadata.get("parameter_order"))
        or _coerce_str_list(metadata.get("parameter_names"))
        or _coerce_str_list(metadata.get("order"))
        or []
    )
    correlation_matrix = _coerce_dependence_matrix(
        metadata.get("correlation_matrix")
        or metadata.get("gaussian_copula_correlation")
        or metadata.get("gaussian_copula_corr")
    )
    covariance_matrix = _coerce_dependence_matrix(
        metadata.get("covariance_matrix") or metadata.get("gaussian_copula_covariance")
    )
    strategy = "descriptive_only"
    if correlation_matrix is None and covariance_matrix is not None:
        correlation_matrix = _correlation_from_covariance(covariance_matrix)
        strategy = "gaussian_copula_from_covariance"
    elif correlation_matrix is not None:
        strategy = "gaussian_copula"

    if correlation_matrix is not None:
        if not parameter_order or len(parameter_order) != correlation_matrix.shape[0]:
            warnings.append("dependence_parameter_order_mismatch")
            correlation_matrix = None
            strategy = "descriptive_only"
        else:
            correlation_matrix = _stabilize_correlation_matrix(correlation_matrix)

    diagnostics = {
        "present": True,
        "regime": structure.regime,
        "class_label": structure.class_label,
        "recommended_covariance": structure.recommended_covariance,
        "calibrated": bool(structure.calibrated),
        "source_method": structure.source_method,
        "strategy": strategy,
        "parameter_order": list(parameter_order),
        "warnings": list(warnings),
        "blocking_reasons": list(structure.blocking_reasons),
    }
    if correlation_matrix is not None:
        diagnostics["matrix_shape"] = list(correlation_matrix.shape)
    return _ResolvedDependenceContext(
        ref=ref,
        structure=structure,
        correlation_matrix=correlation_matrix,
        parameter_order=tuple(parameter_order),
        strategy=strategy,
        warnings=tuple(warnings),
        diagnostics=diagnostics,
    )


def _resolve_pe_sensitivity(
    *,
    welfare_params: Mapping[str, Any],
    labels: tuple[str, ...],
) -> dict[str, dict[str, float]]:
    if "pe_sensitivity" not in welfare_params:
        return {label: {label: 1.0} for label in labels}
    raw = welfare_params["pe_sensitivity"]
    resolved: dict[str, dict[str, float]] = {}
    if not isinstance(raw, Mapping) or not raw:
        raise _fail_error(
            _ERROR_WELFARE_DIMENSION_MISMATCH,
            "welfare_pe_sensitivity must be a non-empty mapping when provided",
            details={"received_type": type(raw).__name__},
        )

    unknown_labels = [label for label in raw if not isinstance(label, str) or label not in labels]
    if unknown_labels:
        raise _fail_error(
            _ERROR_WELFARE_DIMENSION_MISMATCH,
            "welfare_pe_sensitivity contains labels outside welfare_metric_order",
            details={"unknown_labels": [str(label) for label in unknown_labels]},
        )
    for label, per_label in raw.items():
        if not isinstance(per_label, Mapping) or not per_label:
            raise _fail_error(
                _ERROR_WELFARE_DIMENSION_MISMATCH,
                "welfare_pe_sensitivity entries must be non-empty parameter mappings",
                details={"label": label, "received_type": type(per_label).__name__},
            )
        label_map: dict[str, float] = {}
        for param_name, coef in per_label.items():
            if not isinstance(param_name, str) or not param_name.strip():
                raise _fail_error(
                    _ERROR_WELFARE_DIMENSION_MISMATCH,
                    "welfare_pe_sensitivity parameter names must be non-empty strings",
                    details={"label": label, "parameter": str(param_name)},
                )
            try:
                numeric_coef = _coerce_welfare_numeric_scalar(coef)
            except (TypeError, ValueError, OverflowError) as exc:
                raise _fail_error(
                    _ERROR_WELFARE_DIMENSION_MISMATCH,
                    "welfare_pe_sensitivity coefficients must be finite numbers",
                    details={"label": label, "parameter": param_name},
                ) from exc
            if not math.isfinite(numeric_coef):
                raise _fail_error(
                    _ERROR_WELFARE_DIMENSION_MISMATCH,
                    "welfare_pe_sensitivity coefficients must be finite numbers",
                    details={"label": label, "parameter": param_name},
                )
            label_map[param_name] = numeric_coef
        resolved[label] = label_map
    return resolved


def _resolve_ge_multiplier_semantics(welfare_params: Mapping[str, Any]) -> str:
    explicit = welfare_params.get("ge_multiplier_semantics")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    if welfare_params.get("ge_technical_coefficients") is not None:
        return "leontief_inverse"
    if welfare_params.get("ge_model_ref") is not None:
        return "leontief_inverse"
    return "reduced_form_ge_multiplier"


def _validate_model_class(model_class: str, ge_multiplier_semantics: str) -> None:
    if model_class == "linearized_ge_io" and ge_multiplier_semantics not in {
        "leontief_inverse",
        "reduced_form_ge_multiplier",
    }:
        raise _fail_error(
            _ERROR_WELFARE_MODEL_CLASS_MISMATCH,
            "linearized_ge_io requires leontief or reduced-form GE semantics",
            details={"ge_multiplier_semantics": ge_multiplier_semantics},
        )
    if model_class == "linearized_cge" and ge_multiplier_semantics not in {
        "jacobian_inverse",
        "reduced_form_ge_multiplier",
    }:
        raise _fail_error(
            _ERROR_WELFARE_MODEL_CLASS_MISMATCH,
            "linearized_cge requires jacobian or reduced-form GE semantics",
            details={"ge_multiplier_semantics": ge_multiplier_semantics},
        )
