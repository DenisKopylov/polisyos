"""Connect a genuine blocked model-input preflight to candidate N7 routing.

An execution *envelope* with ``simulation_blocked`` is not a numerical run.
This owner reuses Generic's historical input/preflight replay and the model
requirement compiler. It neither invents an L1 absence observation nor turns a
candidate source query, derivation graph or acquisition plan into permission.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from polisyos.core import artifacts

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

    from polisyos.core.artifacts import ArtifactStore
    from polisyos.data_requirement import (
        CompiledModelInputRequirement,
        ModelInputCompilationReport,
    )
    from polisyos.runtime.quality.acquisition_planner import (
        AcquisitionGap,
        AcquisitionPlannerReport,
        AcquisitionRequirementGap,
        N7DerivationBundle,
        _N7CandidateReportInputBinding,
        _N7ConfiguredCandidatePortSource,
    )
    from polisyos.runtime.quality.generation_cycle import GenerationCycleRecord, GenerationCycleRun
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationN5InputV1,
        GenericN5ExecutionJoinExpectation,
    )
    from polisyos.runtime.quality.model_input_routing import ModelInputRoutingReport


PRE_NUMERICAL_SOURCE_VERSION = "policyos.runtime.n7_configured_candidate_port_source.v3"
PRE_NUMERICAL_LINEAGE_VERSION = "policyos.runtime.n7_candidate_report_lineage.v2"
MODEL_INPUT_GAP_VERSION = "policyos.runtime.model_input_obligation_gap.v1"


def _same(left: artifacts.ArtifactRef, right: artifacts.ArtifactRef) -> bool:
    return artifacts.artifact_ref_identity_key(left) == artifacts.artifact_ref_identity_key(right)


def _selected(ref: object, kind: str) -> bool:
    return (
        type(ref) is artifacts.ArtifactRef
        and ref.kind == kind
        and ref.media_type == "application/json"
        and ref.manifest_profile_sha256 is not None
    )


def validate_pre_numerical_source_shape(source: _N7ConfiguredCandidatePortSource) -> None:
    """Validate the v3 shape without claiming its parents have been replayed."""
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.generation_cycle import (
        CandidateGroundingObservation,
        ValuePortObservation,
    )

    refs = (
        (source.n4_source_ref, "runtime.generation_source_handoff"),
        (source.context_job_ref, "runtime.quality.cycle_substrate_context_job"),
        (source.n5_input_ref, "runtime.quality.generic_cycle_simulation_n5_input"),
        (source.n5_execution_ref, "runtime.quality.generic_cycle_simulation_n5_execution"),
        (source.model_input_obligation_set_ref, "runtime.quality.model_input_obligation_set"),
        (source.model_input_obligation_ref, "runtime.quality.model_input_obligation"),
        (source.model_input_routing_report_ref, "runtime.quality.model_input_routing_report"),
    )
    if (
        source.numerical_execution_status != "unrun"
        or source.n5_result_ref is not None
        or any(not _selected(ref, kind) for ref, kind in refs)
    ):
        raise ValueError("n7_pre_numerical_source_selected_inputs_invalid")
    if source.derivation_bundle_ref is not None and not _selected(
        source.derivation_bundle_ref, "runtime.quality.n7_derivation_bundle"
    ):
        raise ValueError("n7_pre_numerical_source_bundle_unselected")
    grounding = CandidateGroundingObservation.model_validate(source.grounding_observation)
    value = ValuePortObservation.model_validate(source.value_observation)
    if (
        grounding.candidate_id != source.candidate_id
        or value.candidate_id not in {None, source.candidate_id}
        or value.candidate_n5_l1_routing is not None
        or value.value_ref is not None
        or source.source_gap.requirement_schema_version != MODEL_INPUT_GAP_VERSION
        or source.source_gap.metadata.get("source") != "model_input_obligation"
        or source.source_gap.metadata.get("candidate_binding")
        != {
            "candidate_id": source.candidate_id,
            "candidate_content_hash": source.candidate_content_hash,
            "design_problem_ref": source.design_problem_basis_ref,
        }
    ):
        raise ValueError("n7_pre_numerical_source_subject_mismatch")
    companions = (
        (grounding.acquisition_requirement,)
        if grounding.acquisition_requirement is not None
        else ()
    )
    if source.accompanying_requirement_gaps != companions:
        raise ValueError("n7_pre_numerical_source_companions_mismatch")
    if grounding.report_ref is None:
        if source.grounding_digest_payload is not None:
            raise ValueError("n7_pre_numerical_source_grounding_digest_mismatch")
    elif (
        source.grounding_digest_payload is None
        or gy_content_hash(source.grounding_digest_payload) != grounding.report_ref
        or source.grounding_digest_payload.get("candidate_id") != source.candidate_id
        or source.grounding_digest_payload.get("source") != grounding.grounding_source
    ):
        raise ValueError("n7_pre_numerical_source_grounding_digest_mismatch")


def _selected_model_requirements(
    store: ArtifactStore,
    *,
    obligation_set_ref: artifacts.ArtifactRef,
    routing_report_ref: artifacts.ArtifactRef,
    target_obligation_ref: artifacts.ArtifactRef,
) -> tuple[ModelInputCompilationReport, CompiledModelInputRequirement, ModelInputRoutingReport]:
    """Replay the model compiler and every recorded route against its full set.

    Catalog query outcomes remain historical candidate observations. The
    Generic cycle-owner join separately establishes the preflight's selected
    subject; a constructor or this compiler replay is not that owner proof.
    """
    from polisyos.core.contracts import load_model_input_obligation_set
    from polisyos.data_requirement import verify_model_input_compilation_report
    from polisyos.runtime.quality.model_input_routing import read_model_input_routing_report

    selected_set, members = load_model_input_obligation_set(store, obligation_set_ref)
    report = read_model_input_routing_report(store, routing_report_ref)
    if (
        not _same(report.obligation_set_ref, obligation_set_ref)
        or report.selected_invocation != selected_set.invocation
        or len(members) != len(selected_set.obligation_refs)
    ):
        raise ValueError("n7_pre_numerical_model_input_report_subject_mismatch")
    compilation = verify_model_input_compilation_report(
        store,
        report.compilation_report_ref,
        expected_context=selected_set.invocation.context,
        expected_interface_ref=selected_set.invocation.interface_ref,
        expected_obligation_set_ref=obligation_set_ref,
    )
    expected = tuple(
        (
            item.requirement_id,
            artifacts.artifact_ref_identity_key(item.obligation_ref),
            item.port.port_id,
        )
        for item in compilation.requirements
    )
    actual = tuple(
        (
            route.requirement_id,
            artifacts.artifact_ref_identity_key(route.obligation_ref),
            route.port_id,
        )
        for route in report.routes
    )
    if actual != expected or tuple(
        artifacts.artifact_ref_identity_key(item.obligation_ref)
        for item in compilation.requirements
    ) != tuple(artifacts.artifact_ref_identity_key(ref) for ref in selected_set.obligation_refs):
        raise ValueError("n7_pre_numerical_model_input_denominator_mismatch")
    targets = tuple(
        item
        for item in compilation.requirements
        if _same(item.obligation_ref, target_obligation_ref)
    )
    if len(targets) != 1:
        raise ValueError("n7_pre_numerical_target_not_in_full_obligation_set")
    return compilation, targets[0], report


def _model_input_gap(
    *,
    candidate_id: str,
    candidate_content_hash: str,
    design_problem_basis_ref: str,
    obligation_set_ref: artifacts.ArtifactRef,
    target: CompiledModelInputRequirement,
    routing_report_ref: artifacts.ArtifactRef,
    authority_level: object,
) -> AcquisitionRequirementGap:
    """Name an unbound model port, without claiming catalog/data absence."""
    from polisyos.runtime.quality.acquisition_planner import (
        AcquisitionGapType,
        AcquisitionRequirementGap,
        AuthorityLevel,
        MandatoryGateState,
        RequirementGapFamily,
        _stable_content_hash,
    )

    level = (
        authority_level
        if isinstance(authority_level, AuthorityLevel)
        else AuthorityLevel(authority_level)
    )
    binding = {
        "candidate_id": candidate_id,
        "candidate_content_hash": candidate_content_hash,
        "design_problem_ref": design_problem_basis_ref,
    }
    metadata = {
        "source": "model_input_obligation",
        "schema_version": MODEL_INPUT_GAP_VERSION,
        "authority_purpose": "candidate_acquisition_routing_only",
        "candidate_binding": binding,
        "model_input_obligation_set_ref": obligation_set_ref.model_dump(mode="json"),
        "model_input_obligation_ref": target.obligation_ref.model_dump(mode="json"),
        "model_input_port_id": target.port.port_id,
        "model_input_routing_report_ref": routing_report_ref.model_dump(mode="json"),
        "historical_catalog_absence": "not_established",
        "source_currentness": "not_established",
        "satisfaction_status": "unsatisfied",
    }
    identity = _stable_content_hash(metadata).removeprefix("sha256:")[:16]
    return AcquisitionRequirementGap(
        requirement_gap_id=f"requirement-gap:model-input:{identity}",
        requirement_family=RequirementGapFamily.DATA,
        compiled_requirement_ref=target.requirement_id,
        requirement_schema_version=MODEL_INPUT_GAP_VERSION,
        gap_type=AcquisitionGapType.DATA_SNAPSHOT_RELEASE,
        claim_ref=f"model-input:{candidate_id}:{target.port.port_id}",
        scenario_requirement_refs=(design_problem_basis_ref, str(obligation_set_ref.artifact_id)),
        missing_requirement_fields=(f"bound_model_input:{target.port.port_id}",),
        authority_level=level,
        mandatory_gate_state=(
            MandatoryGateState.NONE
            if level is AuthorityLevel.RESEARCH
            else MandatoryGateState.NON_OVERRIDABLE
        ),
        mandatory_gate_refs=(target.requirement_id,),
        limitation_permitted=False,
        decision_owner_ref="polisyos.runtime.quality.acquisition_planner",
        producer_output_ref=str(target.obligation_ref.artifact_id),
        metadata=metadata,
    )


def replay_pre_numerical_source_inputs(
    store: ArtifactStore, source: _N7ConfiguredCandidatePortSource
) -> tuple[ModelInputCompilationReport, ModelInputRoutingReport, N7DerivationBundle | None]:
    """Reopen the compiler/port/bundle namespace of the exact selected source."""
    from polisyos.runtime.quality.acquisition_planner import _n7_load_derivation_bundle

    validate_pre_numerical_source_shape(source)
    compilation, target, report = _selected_model_requirements(
        store,
        obligation_set_ref=source.model_input_obligation_set_ref,
        routing_report_ref=source.model_input_routing_report_ref,
        target_obligation_ref=source.model_input_obligation_ref,
    )
    context = report.selected_invocation.context
    if (
        context.run_id != source.run_id
        or context.candidate_id != source.candidate_id
        or context.candidate_content_hash != source.candidate_content_hash
        or context.context_job_ref is None
        or not _same(context.context_job_ref, source.context_job_ref)
    ):
        raise ValueError("n7_pre_numerical_source_context_mismatch")
    expected_gap = _model_input_gap(
        candidate_id=source.candidate_id,
        candidate_content_hash=source.candidate_content_hash,
        design_problem_basis_ref=source.design_problem_basis_ref,
        obligation_set_ref=source.model_input_obligation_set_ref,
        target=target,
        routing_report_ref=source.model_input_routing_report_ref,
        authority_level=source.source_gap.authority_level,
    )
    if source.source_gap != expected_gap:
        raise ValueError("n7_pre_numerical_source_gap_replay_mismatch")
    bundle = (
        _n7_load_derivation_bundle(store, source.derivation_bundle_ref)
        if source.derivation_bundle_ref is not None
        else None
    )
    if (
        bundle is not None
        and bundle.schema_version == "policyos.runtime.n7_derivation_bundle.v2"
        and not _same(bundle.model_input_routing_report_ref, source.model_input_routing_report_ref)
    ):
        raise ValueError("n7_pre_numerical_source_bundle_routing_mismatch")
    if bundle is not None and (
        not _same(bundle.obligation_set_ref, source.model_input_obligation_set_ref)
        or not _same(bundle.model_input_obligation_ref, source.model_input_obligation_ref)
        or not _same(
            bundle.target_basis.semantic_definition_ref, target.port.semantic_definition_ref
        )
        or not _same(bundle.target_basis.representation_ref, target.port.representation_ref)
        or not _same(bundle.target_basis.binding_profile_ref, target.port.binding_profile_ref)
    ):
        raise ValueError("n7_pre_numerical_source_bundle_target_mismatch")
    return compilation, report, bundle


def _pre_numerical_planning_gaps(
    store: ArtifactStore,
    source: _N7ConfiguredCandidatePortSource,
    *,
    resolved_inputs: tuple[
        ModelInputCompilationReport, ModelInputRoutingReport, N7DerivationBundle | None
    ]
    | None = None,
) -> tuple[AcquisitionGap, ...]:
    from polisyos.runtime.quality.acquisition_planner import (
        n7_pending_unique_derivation_source_gaps,
    )

    compilation, _report, bundle = (
        replay_pre_numerical_source_inputs(store, source)
        if resolved_inputs is None
        else resolved_inputs
    )
    companions = source.accompanying_requirement_gaps
    leaves = n7_pending_unique_derivation_source_gaps(bundle) if bundle is not None else ()
    source_gaps = (source.source_gap, *companions)
    gaps = (*source_gaps, *leaves)
    # Grounding uses the full cycle basis; model-input leaves use the exact
    # compiler invocation projection. These time/context roles need not hash
    # identically and must not be silently rebound to make a bundle fit.
    model_binding = {
        "candidate_id": compilation.context.candidate_id,
        "candidate_content_hash": compilation.context.candidate_content_hash,
        "design_problem_ref": compilation.context.design_problem_ref,
    }
    if (
        len({gap.requirement_gap_id for gap in gaps}) != len(gaps)
        or any(
            gap.metadata.get("candidate_binding") != source.source_gap.metadata["candidate_binding"]
            for gap in source_gaps
        )
        or any(gap.metadata.get("candidate_binding") != model_binding for gap in leaves)
        or any(gap.authority_level != source.source_gap.authority_level for gap in gaps)
    ):
        raise ValueError("n7_pre_numerical_gap_scope_mismatch")
    return tuple(gap.to_acquisition_gap() for gap in gaps)


def pre_numerical_report_input_bindings(
    report: AcquisitionPlannerReport,
    source: _N7ConfiguredCandidatePortSource,
    *,
    bundle: N7DerivationBundle | None,
) -> tuple[_N7CandidateReportInputBinding, ...]:
    """Classify every report locator using a selected owner or bundle leaf."""
    from polisyos.runtime.quality.acquisition_planner import (
        _N7CandidateReportInputBinding,
        n7_pending_unique_derivation_source_gaps,
    )

    # Source and bundle replay is performed by the surrounding report owner.
    result = []
    leaves = n7_pending_unique_derivation_source_gaps(bundle) if bundle is not None else ()
    for record in report.acquisition_records:
        for role, value in (
            ("voi_ranking", record.voi_ranking_ref),
            ("producer_output", record.producer_output_ref),
            ("calibration_feedback", record.calibration_feedback_ref),
        ):
            if not value:
                continue
            if (
                role == "producer_output"
                and record.requirement_gap_ref == source.source_gap.requirement_gap_id
                and value == source.source_gap.producer_output_ref
            ):
                result.append(
                    _N7CandidateReportInputBinding(
                        acquisition_id=record.acquisition_id,
                        role=role,
                        value=value,
                        source_kind="selected_artifact",
                        selected_artifact_ref=source.model_input_obligation_ref,
                    )
                )
            elif role == "producer_output" and any(
                record.requirement_gap_ref == gap.requirement_gap_id
                and value == gap.producer_output_ref
                for gap in source.accompanying_requirement_gaps
            ):
                result.append(
                    _N7CandidateReportInputBinding(
                        acquisition_id=record.acquisition_id,
                        role=role,
                        value=value,
                        source_kind="grounding_digest",
                    )
                )
            elif role == "producer_output" and any(
                record.requirement_gap_ref == gap.requirement_gap_id
                and value == gap.producer_output_ref
                for gap in leaves
            ):
                result.append(
                    _N7CandidateReportInputBinding(
                        acquisition_id=record.acquisition_id,
                        role=role,
                        value=value,
                        source_kind="n7_derivation_source_request",
                    )
                )
            elif (
                role == "calibration_feedback" and value == f"calibration_feedback:{record.gap_id}"
            ):
                result.append(
                    _N7CandidateReportInputBinding(
                        acquisition_id=record.acquisition_id,
                        role=role,
                        value=value,
                        source_kind="planner_generated_locator",
                    )
                )
            else:
                raise ValueError("n7_pre_numerical_report_input_not_established")
    return tuple(result)


def bind_pre_numerical_candidate_report(
    store: ArtifactStore,
    report: AcquisitionPlannerReport,
    source_ref: artifacts.ArtifactRef,
    source: _N7ConfiguredCandidatePortSource,
) -> AcquisitionPlannerReport:
    """Bind the real model compiler, rather than a fabricated legacy basis."""
    from polisyos.runtime.quality.acquisition_planner import (
        _N7_CONFIGURED_REPORT_SCHEMA,
        AcquisitionPlannerReport,
        _n7_exact_wire,
        _N7CandidateReportLineage,
        plan_evidence_acquisition,
    )

    if report.requirement_basis_binding is not None:
        raise ValueError("n7_pre_numerical_legacy_compiler_basis_forbidden")
    if report.run_id != _pre_numerical_report_run_id(source):
        raise ValueError("n7_pre_numerical_report_scope_mismatch")
    resolved = replay_pre_numerical_source_inputs(store, source)
    _compilation, routing, bundle = resolved
    expected = plan_evidence_acquisition(
        run_id=report.run_id,
        gaps=_pre_numerical_planning_gaps(store, source, resolved_inputs=resolved),
        generated_at=report.generated_at,
    )
    if _n7_exact_wire(
        report.model_dump(mode="json", exclude={"planning_context_hash", "planning_binding_hash"})
    ) != _n7_exact_wire(
        expected.model_dump(mode="json", exclude={"planning_context_hash", "planning_binding_hash"})
    ):
        raise ValueError("n7_pre_numerical_report_planning_replay_mismatch")
    lineage = _N7CandidateReportLineage(
        schema_version=PRE_NUMERICAL_LINEAGE_VERSION,
        port_source_ref=source_ref,
        bindings=pre_numerical_report_input_bindings(report, source, bundle=bundle),
        model_input_compilation_ref=routing.compilation_report_ref,
    )
    return AcquisitionPlannerReport.model_validate(
        {
            **report.model_dump(mode="python"),
            "schema_version": _N7_CONFIGURED_REPORT_SCHEMA,
            "candidate_lineage": lineage,
        }
    )


def validate_pre_numerical_candidate_report(
    store: ArtifactStore, report: AcquisitionPlannerReport, source: _N7ConfiguredCandidatePortSource
) -> None:
    """Replay the actual model compiler, complete gap set and input occurrences."""
    from polisyos.runtime.quality.acquisition_planner import (
        ACQUISITION_PLANNER_SCHEMA_VERSION,
        AcquisitionPlannerReport,
        _n7_exact_wire,
        plan_evidence_acquisition,
    )

    lineage = report.candidate_lineage
    if (
        lineage is None
        or lineage.schema_version != PRE_NUMERICAL_LINEAGE_VERSION
        or report.requirement_basis_binding is not None
    ):
        raise ValueError("n7_pre_numerical_report_compiler_variant_mismatch")
    if report.run_id != _pre_numerical_report_run_id(source):
        raise ValueError("n7_pre_numerical_report_scope_mismatch")
    resolved = replay_pre_numerical_source_inputs(store, source)
    _compilation, routing, bundle = resolved
    if not _same(lineage.model_input_compilation_ref, routing.compilation_report_ref):
        raise ValueError("n7_pre_numerical_report_compiler_selection_mismatch")
    plain = AcquisitionPlannerReport.model_validate(
        {
            **report.model_dump(mode="python", exclude={"candidate_lineage"}),
            "schema_version": ACQUISITION_PLANNER_SCHEMA_VERSION,
        }
    )
    expected = plan_evidence_acquisition(
        run_id=plain.run_id,
        gaps=_pre_numerical_planning_gaps(store, source, resolved_inputs=resolved),
        generated_at=plain.generated_at,
    )
    excluded = {"planning_context_hash", "planning_binding_hash"}
    if _n7_exact_wire(plain.model_dump(mode="json", exclude=excluded)) != _n7_exact_wire(
        expected.model_dump(mode="json", exclude=excluded)
    ) or lineage.bindings != pre_numerical_report_input_bindings(plain, source, bundle=bundle):
        raise ValueError("n7_pre_numerical_report_source_replay_mismatch")


def plan_n7_pre_numerical_candidate_acquisition(
    store: ArtifactStore, *, source_ref: artifacts.ArtifactRef, generated_at: datetime
) -> AcquisitionPlannerReport:
    """Plan target and source-leaf work with the existing N7 planner."""
    from polisyos.runtime.quality.acquisition_planner import (
        _n7_load_configured_candidate_port_source,
        bind_acquisition_planner_report,
        plan_evidence_acquisition,
    )

    source = _n7_load_configured_candidate_port_source(store, source_ref)
    if source.schema_version != PRE_NUMERICAL_SOURCE_VERSION:
        raise ValueError("n7_pre_numerical_source_version_required")
    report = plan_evidence_acquisition(
        run_id=_pre_numerical_report_run_id(source),
        gaps=_pre_numerical_planning_gaps(store, source),
        generated_at=generated_at,
    )
    bound = bind_pre_numerical_candidate_report(store, report, source_ref, source)
    return bind_acquisition_planner_report(
        bound,
        planning_context_hash=pre_numerical_planning_context_hash(
            source_ref, bound.candidate_lineage.model_input_compilation_ref
        ),
    )


def _pre_numerical_report_run_id(source: _N7ConfiguredCandidatePortSource) -> str:
    return (
        f"n7-input:{source.source_generation_run_id}:{source.cycle_index}:"
        f"{source.model_input_obligation_ref.artifact_id}"
    )


def pre_numerical_planning_context_hash(
    source_ref: artifacts.ArtifactRef,
    model_input_compilation_ref: artifacts.ArtifactRef,
) -> str:
    """Bind the actual preflight/route compiler closure, not a legacy spec copy."""
    from polisyos.runtime.quality.acquisition_planner import _stable_content_hash

    if not _selected(
        source_ref, "runtime.quality.n7_configured_candidate_port_source"
    ) or not _selected(model_input_compilation_ref, "data_requirement.model_input_compilation"):
        raise ValueError("n7_pre_numerical_planning_selected_inputs_required")
    return _stable_content_hash(
        {
            "rule_version": "policyos.runtime.n7_model_input_planning_context.v1",
            "configured_source_ref": source_ref.model_dump(mode="json"),
            "model_input_compilation_ref": model_input_compilation_ref.model_dump(mode="json"),
        }
    )


def validate_persisted_pre_numerical_candidate_report(
    store: ArtifactStore,
    ref: artifacts.ArtifactRef,
    report: AcquisitionPlannerReport,
    *,
    expected_design_problem_basis_ref: str,
    expected_compiled_requirement_ref: str,
    expected_obligation_set_ref: artifacts.ArtifactRef | None,
) -> tuple[dict[str, Any], ...]:
    """Shared current/historical report proof against an independently selected set.

    This establishes the model compiler and recorded route. Current permission,
    quote validity, Catalog currentness and the effect lease are separate gates.
    """
    from polisyos.core.artifacts import raise_artifact_read_access_error
    from polisyos.runtime.quality.acquisition_planner import (
        _n7_load_configured_candidate_port_source,
        _validate_persisted_planner_report,
        acquisition_planner_report_matches_context,
    )

    issues = list(_validate_persisted_planner_report(store=store, ref=ref, report=report))
    if issues:
        return tuple(issues)
    if expected_obligation_set_ref is None:
        return ({"code": "n7_pre_numerical_expected_obligation_set_missing"},)
    try:
        lineage = report.candidate_lineage
        if lineage is None or lineage.schema_version != PRE_NUMERICAL_LINEAGE_VERSION:
            raise ValueError("n7_pre_numerical_report_lineage_required")
        source = _n7_load_configured_candidate_port_source(store, lineage.port_source_ref)
        if (
            source.schema_version != PRE_NUMERICAL_SOURCE_VERSION
            or not _same(source.model_input_obligation_set_ref, expected_obligation_set_ref)
            or source.design_problem_basis_ref != expected_design_problem_basis_ref
        ):
            raise ValueError("n7_pre_numerical_report_selected_subject_mismatch")
        validate_pre_numerical_candidate_report(store, report, source)
        if not acquisition_planner_report_matches_context(
            report,
            planning_context_hash=pre_numerical_planning_context_hash(
                lineage.port_source_ref, lineage.model_input_compilation_ref
            ),
        ):
            raise ValueError("n7_pre_numerical_report_context_binding_mismatch")
        if not expected_compiled_requirement_ref or expected_compiled_requirement_ref not in {
            gap.compiled_requirement_ref for gap in _pre_numerical_planning_gaps(store, source)
        }:
            raise ValueError("n7_pre_numerical_compiled_requirement_not_in_basis")
    except (OSError, TypeError, ValueError) as exc:
        raise_artifact_read_access_error(exc)
        return ({"code": "n7_pre_numerical_report_not_established", "reason": str(exc)},)
    if report.status == "blocked":
        return ({"code": "acquisition_planner_report_blocked"},)
    return ()


def verify_pre_numerical_candidate_report_cycle(
    *,
    store: ArtifactStore,
    source: _N7ConfiguredCandidatePortSource,
    report: AcquisitionPlannerReport,
    generation_run: GenerationCycleRun,
    source_cycle: GenerationCycleRecord,
    tenant_id: str,
    cell_id: str,
    run_id: str,
    source_job_id: str,
    design_problem_ref: str,
) -> None:
    """Use Generic's existing historical blocked-input replay for the cycle join."""
    from polisyos.core.artifacts import read_core_json_artifact
    from polisyos.runtime.quality.acquisition_planner import (
        _n7_exact_wire,
    )
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationAdmissionOwner,
        GenericCycleSimulationN5InputV1,
        GenericN5ExecutionJoinExpectation,
    )

    simulation = source_cycle.simulation
    if (
        (source.tenant_id, source.cell_id, source.run_id, source.source_job_id)
        != (tenant_id, cell_id, run_id, source_job_id)
        or source.source_generation_run_id != generation_run.run_id
        or source.cycle_index != source_cycle.cycle_index
        or source.candidate_id != source_cycle.selected_candidate_ref
        or source.candidate_content_hash != source_cycle.selected_candidate_content_hash
        or source.design_problem_basis_ref
        != (source_cycle.design_problem_basis_ref or source_cycle.design_problem_ref)
        or simulation.status != "simulation_blocked"
        or simulation.simulation_result_ref is not None
        or simulation.model_input_obligation_set_ref is None
        or source_cycle.model_input_routing_report_ref is None
        or not _same(
            source.model_input_obligation_set_ref, simulation.model_input_obligation_set_ref
        )
        or not _same(
            source.model_input_routing_report_ref, source_cycle.model_input_routing_report_ref
        )
        or _n7_exact_wire(source.grounding_observation)
        != _n7_exact_wire(source_cycle.grounding.model_dump(mode="json"))
        or _n7_exact_wire(source.value_observation)
        != _n7_exact_wire(source_cycle.value_port.model_dump(mode="json"))
    ):
        raise ValueError("n7_pre_numerical_report_cycle_subject_mismatch")
    for actual, selected in (
        (source.n4_source_ref, simulation.generic_n4_source_ref),
        (source.context_job_ref, simulation.generic_context_job_ref),
        (source.n5_input_ref, simulation.generic_n5_input_ref),
        (source.n5_execution_ref, simulation.generic_n5_execution_ref),
    ):
        if selected is None or not _same(actual, selected):
            raise ValueError("n7_pre_numerical_report_cycle_selected_ref_mismatch")
    # The exact selected cycle report binds the source and its optional one-port
    # bundle. No N8/value acquisition request is invented for a pre-kernel gap.
    # Bundle target/full-set replay happens in the shared source validator.
    # These two value fields are taken from the selected recorded input; the
    # Generic owner replays them from the independently selected N4/context.
    # Actor/job/run/cycle/candidate and selected refs above come from the
    # actual control-owned cycle, not the source artifact being verified.
    recorded_input = GenericCycleSimulationN5InputV1.model_validate(
        read_core_json_artifact(store, source.n5_input_ref).value
    )
    if simulation.k_world_ref_before is not None and (
        simulation.k_world_ref_before
        != recorded_input.profile.context_inputs.world_model_record.content_hash
    ):
        raise ValueError("n7_pre_numerical_report_cycle_world_mismatch")
    expected = GenericN5ExecutionJoinExpectation(
        input_ref=source.n5_input_ref,
        result_ref=None,
        status="simulation_blocked",
        model_input_obligation_set_ref=simulation.model_input_obligation_set_ref,
        n4_source_ref=simulation.generic_n4_source_ref,
        context_job_ref=simulation.generic_context_job_ref,
        profile_ref=simulation.generic_profile_ref,
        child_family_ref=simulation.generic_n4_child_profile_family_ref,
        child_set_ref=simulation.generic_n4_child_profile_set_ref,
        profile_selection_ref=simulation.generic_profile_selection_ref,
        profile=recorded_input.profile,
        child_selection=recorded_input.child_selection,
        design_problem_ref=design_problem_ref,
        outcome_variable=recorded_input.outcome_variable,
        cycle_index=source_cycle.cycle_index,
        candidate_id=source_cycle.selected_candidate_ref,
        candidate_atom_hash=source_cycle.selected_candidate_content_hash,
        world_model_record_content_hash=recorded_input.profile.context_inputs.world_model_record.content_hash,
        job_id=source_job_id,
        run_id=run_id,
        source_run_id=generation_run.run_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
    )
    joined, basis = GenericCycleSimulationAdmissionOwner(
        profiles=(), store=store
    ).resolve_n5_execution_join_with_program_graph_input_basis(
        source.n5_execution_ref, expected=expected
    )
    if joined.status != "resolved" or basis is None or joined.execution.result_ref is not None:
        raise ValueError("n7_pre_numerical_report_generic_owner_join_not_established")
    _verify_pre_numerical_grounding_from_source(store, source, recorded_input)
    validate_pre_numerical_candidate_report(store, report, source)


def _verify_pre_numerical_grounding_from_source(
    store: ArtifactStore,
    source: _N7ConfiguredCandidatePortSource,
    recorded_input: GenericCycleSimulationN5InputV1,
) -> None:
    """Replay Generic's retained full N4 grounding, without a current mandate.

    The caller has already joined this exact input to the independent selected
    job/cycle. Unlike the legacy NCM configured-source envelope, the Generic N4
    handoff retains the real disposition and its source/certificate parents.
    """
    from polisyos.runtime.quality.generation_cycle import PolicyGroundingPort, _n7_exact_wire
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository

    retained = GenerationSourceRepository(store).load(
        source.n4_source_ref,
        run_id=source.source_generation_run_id,
        expected_job_id=source.source_job_id,
        expected_run_id=source.run_id,
        expected_tenant_id=source.tenant_id,
        expected_cell_id=source.cell_id,
        context_job_ref=source.context_job_ref,
        profile_ref=recorded_input.profile_ref,
        n4_child_profile_family_ref=recorded_input.n4_child_profile_family_ref,
    )
    candidates = tuple(
        candidate
        for candidate in retained.generation_result.candidates
        if getattr(candidate, "candidate_id", None) == source.candidate_id
        and getattr(getattr(candidate, "atom", None), "content_hash", None)
        == source.candidate_content_hash
    )
    if len(candidates) != 1:
        raise ValueError("n7_pre_numerical_grounding_candidate_not_selected")
    observation = PolicyGroundingPort()(
        candidate=candidates[0],
        problem=retained.problem,
        cycle_index=source.cycle_index,
        generation_result=retained.generation_result,
    )
    if _n7_exact_wire(observation.model_dump(mode="json")) != _n7_exact_wire(
        source.grounding_observation
    ):
        raise ValueError("n7_pre_numerical_grounding_owner_replay_mismatch")


def publish_n7_pre_numerical_candidate_source(
    store: ArtifactStore,
    *,
    expected: GenericN5ExecutionJoinExpectation,
    execution_ref: artifacts.ArtifactRef,
    routing_report_ref: artifacts.ArtifactRef,
    target_obligation_ref: artifacts.ArtifactRef,
    derivation_bundle_ref: artifacts.ArtifactRef | None,
    design_problem_basis_ref: str,
    grounding_observation: Mapping[str, Any],
    value_observation: Mapping[str, Any],
    grounding_digest_payload: dict[str, Any] | None,
    authority_level: object,
) -> artifacts.ArtifactRef:
    """Publish only after Generic reopens its genuine blocked preflight envelope.

    The controller supplies the independently selected expected job/cycle
    scope and must retain its current-owner fence around this call. This
    historical replay does not grant current fetch or protected-use rights.
    """
    from polisyos.runtime.quality.acquisition_planner import (
        _n7_put_configured_candidate_port_source,
        _N7ConfiguredCandidatePortSource,
    )
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationAdmissionOwner,
    )

    if (
        expected.status != "simulation_blocked"
        or expected.result_ref is not None
        or expected.model_input_obligation_set_ref is None
    ):
        raise ValueError("n7_pre_numerical_blocked_expectation_required")
    joined, basis = GenericCycleSimulationAdmissionOwner(
        profiles=(), store=store
    ).resolve_n5_execution_join_with_program_graph_input_basis(execution_ref, expected=expected)
    if joined.status != "resolved" or basis is None or joined.execution.result_ref is not None:
        raise ValueError("n7_pre_numerical_blocked_owner_not_established")
    _compilation, target, _routing = _selected_model_requirements(
        store,
        obligation_set_ref=expected.model_input_obligation_set_ref,
        routing_report_ref=routing_report_ref,
        target_obligation_ref=target_obligation_ref,
    )
    gap = _model_input_gap(
        candidate_id=expected.candidate_id,
        candidate_content_hash=expected.candidate_atom_hash,
        design_problem_basis_ref=design_problem_basis_ref,
        obligation_set_ref=expected.model_input_obligation_set_ref,
        target=target,
        routing_report_ref=routing_report_ref,
        authority_level=authority_level,
    )
    from polisyos.runtime.quality.generation_cycle import CandidateGroundingObservation

    grounding = CandidateGroundingObservation.model_validate(dict(grounding_observation))
    source = _N7ConfiguredCandidatePortSource(
        schema_version=PRE_NUMERICAL_SOURCE_VERSION,
        tenant_id=expected.tenant_id,
        cell_id=expected.cell_id,
        run_id=expected.run_id,
        source_job_id=expected.job_id,
        source_generation_run_id=expected.source_run_id,
        cycle_index=expected.cycle_index,
        candidate_id=expected.candidate_id,
        candidate_content_hash=expected.candidate_atom_hash,
        design_problem_basis_ref=design_problem_basis_ref,
        n4_source_ref=expected.n4_source_ref,
        context_job_ref=expected.context_job_ref,
        n5_input_ref=expected.input_ref,
        n5_execution_ref=execution_ref,
        numerical_execution_status="unrun",
        model_input_obligation_set_ref=expected.model_input_obligation_set_ref,
        model_input_obligation_ref=target_obligation_ref,
        model_input_routing_report_ref=routing_report_ref,
        grounding_observation=dict(grounding_observation),
        value_observation=dict(value_observation),
        grounding_digest_payload=grounding_digest_payload,
        source_gap=gap,
        accompanying_requirement_gaps=(
            (grounding.acquisition_requirement,)
            if grounding.acquisition_requirement is not None
            else ()
        ),
        derivation_bundle_ref=derivation_bundle_ref,
    )
    replay_pre_numerical_source_inputs(store, source)
    return _n7_put_configured_candidate_port_source(store, source)


def persist_n7_pre_numerical_candidate_acquisition(
    store: ArtifactStore,
    *,
    expected: GenericN5ExecutionJoinExpectation,
    execution_ref: artifacts.ArtifactRef,
    routing_report_ref: artifacts.ArtifactRef,
    design_problem_basis_ref: str,
    grounding_observation: Mapping[str, Any],
    value_observation: Mapping[str, Any],
    grounding_digest_payload: dict[str, Any] | None,
    authority_level: object,
    acquisition_request: Mapping[str, Any] | None,
    generated_at: datetime,
    configured_derivation_bundle_ref: artifacts.ArtifactRef | None = None,
) -> artifacts.ArtifactRef:
    """Publish a target-scoped plan after genuine blocked model-input routing.

    A missing bundle exposes only an unbound target; it cannot become a leaf
    acquisition plan. The complete selected set remains in the source. An
    explicit bundle must select one actual member and cannot close other ports.
    """
    from polisyos.runtime.quality.acquisition_planner import (
        _N7_CANDIDATE_INPUT_OBLIGATIONS_RULE,
        _n7_derivation_bundle_from_request,
        _n7_load_derivation_bundle,
        persist_and_verify_acquisition_planner_report,
    )
    from polisyos.runtime.quality.model_input_routing import read_model_input_routing_report

    routing = read_model_input_routing_report(store, routing_report_ref)
    if (
        expected.model_input_obligation_set_ref is None
        or not _same(routing.obligation_set_ref, expected.model_input_obligation_set_ref)
        or not routing.routes
    ):
        raise ValueError("n7_pre_numerical_routing_target_missing")
    target_ref = routing.routes[0].obligation_ref
    bundle_ref = configured_derivation_bundle_ref
    if bundle_ref is not None:
        bundle = _n7_load_derivation_bundle(store, bundle_ref)
        if not _same(bundle.obligation_set_ref, expected.model_input_obligation_set_ref):
            raise ValueError("n7_pre_numerical_configured_bundle_full_set_mismatch")
        target_ref = bundle.model_input_obligation_ref
    if acquisition_request is not None and {
        "n7_derivation_bundle_ref",
        "n7_derivation_bundle",
    }.intersection(acquisition_request):
        if acquisition_request.get("n7_source_join_rule") != _N7_CANDIDATE_INPUT_OBLIGATIONS_RULE:
            raise ValueError("n7_pre_numerical_bundle_source_rule_mismatch")
        requested_bundle_ref, bundle = _n7_derivation_bundle_from_request(
            store, acquisition_request
        )
        if bundle_ref is not None and (
            requested_bundle_ref is None or not _same(bundle_ref, requested_bundle_ref)
        ):
            raise ValueError("n7_pre_numerical_configured_request_bundle_mismatch")
        bundle_ref = requested_bundle_ref
        if (
            bundle_ref is None
            or bundle is None
            or not _same(bundle.obligation_set_ref, expected.model_input_obligation_set_ref)
        ):
            raise ValueError("n7_pre_numerical_bundle_full_set_mismatch")
        target_ref = bundle.model_input_obligation_ref
    source_ref = publish_n7_pre_numerical_candidate_source(
        store,
        expected=expected,
        execution_ref=execution_ref,
        routing_report_ref=routing_report_ref,
        target_obligation_ref=target_ref,
        derivation_bundle_ref=bundle_ref,
        design_problem_basis_ref=design_problem_basis_ref,
        grounding_observation=grounding_observation,
        value_observation=value_observation,
        grounding_digest_payload=grounding_digest_payload,
        authority_level=authority_level,
    )
    report = plan_n7_pre_numerical_candidate_acquisition(
        store, source_ref=source_ref, generated_at=generated_at
    )
    return persist_and_verify_acquisition_planner_report(store, report)
