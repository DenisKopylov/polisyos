from __future__ import annotations

import hashlib
import json
import types
from copy import deepcopy
from datetime import UTC, datetime
from typing import Annotated, Union, get_args, get_origin

import pytest
from pydantic import BaseModel, StrictFloat, StrictInt, ValidationError

from polisyos.ir.analytics.causal import CausalEffectReport, CausalMethod, EstimationStatus
from polisyos.ir.analytics.causal_graph import GraphType
from polisyos.ir.analytics.transportability import (
    TransportabilityCandidateAttemptBindingV1,
    TransportabilityCandidateBudgetMeasureV1,
    TransportabilityCandidateDiagnosticV1,
    TransportabilityCandidateInputBindingV1,
    TransportabilityCandidateMemberEvaluationV1,
    TransportabilityCandidatePhaseBudgetV1,
    TransportabilityCandidateProfileV1,
    TransportabilityCandidateProposalV1,
    TransportabilityCandidateRequestV1,
    TransportabilityCandidateResourceResolutionV1,
    TransportabilityCandidateSolverOutcomeV1,
    TransportabilityResult,
    TransportabilityStatus,
    TransportMode,
    transportability_candidate_query_sha256,
)
from polisyos.ir.artifacts import InputRef
from polisyos.ir.registry.refs import CausalGraphModelRef

PROFILE_SHA = "sha256:" + "f" * 64
QUERY = "P*(Y|do(X))"
QUERY_SHA = transportability_candidate_query_sha256("X", "Y")


def _numeric_schema_paths(
    annotation: object, prefix: tuple[str, ...] = ()
) -> tuple[tuple[str, ...], ...]:
    if annotation in {int, float, StrictInt, StrictFloat}:
        return (prefix,)
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is Annotated:
        return _numeric_schema_paths(args[0], prefix)
    if origin in {types.UnionType, Union}:
        return tuple(
            dict.fromkeys(
                path
                for argument in args
                if argument is not type(None)
                for path in _numeric_schema_paths(argument, prefix)
            )
        )
    if origin is dict:
        return tuple(
            dict.fromkeys(path for path in _numeric_schema_paths(args[1], (*prefix, "{}")))
        )
    if origin in {tuple, list}:
        return tuple(
            dict.fromkeys(
                path
                for argument in args
                if argument is not Ellipsis
                for path in _numeric_schema_paths(argument, (*prefix, "[]"))
            )
        )
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return tuple(
            dict.fromkeys(
                path
                for name, field in annotation.model_fields.items()
                for path in _numeric_schema_paths(field.annotation, (*prefix, name))
            )
        )
    return ()


def _replace_numeric_path(payload: object, path: tuple[str, ...], value: object) -> None:
    cursor = payload
    for segment in path[:-1]:
        if segment == "{}":
            cursor = cursor[next(iter(cursor))]
        elif segment == "[]":
            cursor = cursor[0]
        else:
            cursor = cursor[segment]
    final = path[-1]
    if final == "{}":
        cursor[next(iter(cursor))] = value
    elif final == "[]":
        cursor[0] = value
    else:
        cursor[final] = value


def _ref(artifact: str, role: str) -> InputRef:
    return InputRef(
        artifact_id=artifact if artifact.startswith("sha256:") else f"sha256:{artifact}",
        role=role,
        manifest_profile_sha256=PROFILE_SHA,
    )


def _budget(
    phase: str,
    *,
    admission: str = "admitted",
    admission_source: str = "bounded_execution_policy",
    termination: str = "completed",
) -> TransportabilityCandidatePhaseBudgetV1:
    common = {
        "phase": phase,
        "selection_identity": "node-slot:transportability",
        "admission": admission,
        "admission_source": admission_source,
        "termination": termination,
    }
    if admission == "not_required":
        return TransportabilityCandidatePhaseBudgetV1.model_validate(
            {
                **common,
                "admission_source": "not_required",
                "termination": "not_required",
            }
        )
    if admission == "admitted":
        return TransportabilityCandidatePhaseBudgetV1.model_validate(
            {
                **common,
                "admission_policy_id": "generic.transport.resource.policy@1",
                "effective_limits": [{"resource": "solver_calls", "value": 3, "unit": "count"}],
                "consumed": [{"resource": "solver_calls", "value": 2, "unit": "count"}],
            }
        )
    return TransportabilityCandidatePhaseBudgetV1.model_validate(
        {
            **common,
            "admission": admission,
            "admission_source": "not_established",
            "termination": "not_started",
            "reason": {"code": "permit_unavailable"},
        }
    )


def _resource_resolution(
    profile_id: str,
    profile_revision: str = "1",
    *,
    status: str = "selected",
) -> TransportabilityCandidateResourceResolutionV1:
    payload = {
        "schema_version": "1.1",
        "policy_id": "generic.transport.resource.policy",
        "policy_revision": "1",
        "profile_id": profile_id,
        "profile_revision": profile_revision,
        "selection_identity": "node-slot:transportability",
        "status": status,
        "reason_code": None if status == "selected" else "profile_unsupported",
        "effective_limits": {"solver_calls": 3, "max_proposals": 64}
        if status == "selected"
        else None,
        "effective_limit_units": (
            {"solver_calls": "count", "max_proposals": "count"} if status == "selected" else None
        ),
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return TransportabilityCandidateResourceResolutionV1(
        **payload, sha256=hashlib.sha256(canonical).hexdigest()
    )


def _solver_outcome(
    status: TransportabilityStatus,
    *,
    reason: str | None = None,
) -> TransportabilityCandidateSolverOutcomeV1:
    kwargs: dict[str, object] = {
        "query": QUERY,
        "status": status,
        "identification_engine": "validated_test_solver",
        "identification_trace": ["solver:completed"],
    }
    if status is TransportabilityStatus.PARTIALLY_IDENTIFIED:
        kwargs.update(
            transport_mode=TransportMode.DIRECT,
            identified_region={"lower": 0.0, "upper": 1.0},
        )
    elif status is TransportabilityStatus.BOUNDED_NON_IDENTIFIED:
        pytest.fail("this fixture does not create a bounds-only member")
    elif status is TransportabilityStatus.UNSUPPORTED:
        kwargs.update(
            transport_mode=TransportMode.NONE,
            feasible=False,
            unsupported_reason=reason or "member_solver_refused",
        )
    else:
        kwargs["transport_mode"] = TransportMode.DIRECT
    result = TransportabilityResult.model_validate(kwargs)
    return TransportabilityCandidateSolverOutcomeV1.from_result(
        result,
        query_sha256=QUERY_SHA,
    )


def _diagnostic(
    *,
    graph_type: GraphType = GraphType.DAG,
    statuses: tuple[TransportabilityStatus, ...] = (TransportabilityStatus.IDENTIFIED,),
) -> TransportabilityCandidateDiagnosticV1:
    graph_id = "1" * 64
    graph_artifact_id = "sha256:" + "a" * 64
    graph_ref = CausalGraphModelRef(
        artifact_id=graph_artifact_id,
        kind="ir.causal_graph_model",
        media_type="application/json",
        manifest_profile_sha256=PROFILE_SHA,
    )
    basis = _ref("b" * 64, "transportability_attempt_basis")
    workflow = _ref("c" * 64, "transportability_workflow_spec")
    state = _ref("d" * 64, "transportability_input_state")
    graph_lineage = _ref(graph_artifact_id, "selected_causal_graph")
    report = _ref("e" * 64, "causal_effect_report")
    attempt = TransportabilityCandidateAttemptBindingV1(
        run_id="run-1",
        attempt_id="attempt-1",
        attempt_number=1,
        node_alias="run_transportability",
        component_id="scientist.node_run_transportability@1.0.0",
        started_at=datetime(2026, 10, 23, 12, tzinfo=UTC),
        dispatch_params_sha256="1" * 64,
        workflow_spec_ref=workflow,
        input_state_ref=state,
        basis_ref=basis,
    )
    inputs = TransportabilityCandidateInputBindingV1(
        graph_ref=graph_ref,
        graph_type=graph_type,
        graph_sha256=graph_id,
        selection_diagram_sha256="2" * 64,
        query_treatment="X",
        query_outcome="Y",
        query_sha256=QUERY_SHA,
        source_context_id="source",
        source_context_sha256="3" * 64,
        target_context_id="target",
        target_context_sha256="4" * 64,
        lineage_refs=(basis, workflow, state, graph_lineage, report),
    )
    pag = graph_type is GraphType.PAG
    proposals: tuple[TransportabilityCandidateProposalV1, ...] = ()
    member_ids = [graph_id]
    generation_budget = _budget(
        "generation",
        admission="admitted" if pag else "not_required",
        admission_source="bounded_execution_policy" if pag else "not_required",
        termination="completed" if pag else "not_required",
    )
    if pag:
        member_ids = [f"{index:x}" * 64 for index in range(5, 5 + len(statuses))]
        proposal_rows = []
        for ordinal, member_id in enumerate(member_ids):
            assignment = f"{ordinal + 10:x}" * 64
            proposal_rows.append(
                TransportabilityCandidateProposalV1(
                    ordinal=ordinal,
                    assignment_sha256=assignment,
                    disposition="admitted",
                    member_sha256=member_id,
                )
            )
        proposals = tuple(proposal_rows)
        generation_budget = TransportabilityCandidatePhaseBudgetV1(
            phase="generation",
            selection_identity="node-slot:transportability",
            admission="admitted",
            admission_source="bounded_execution_policy",
            admission_policy_id="generic.transport.resource.policy@1",
            effective_limits=({"resource": "max_proposals", "value": 64, "unit": "count"},),
            consumed=({"resource": "max_proposals", "value": len(proposals), "unit": "count"},),
            termination="completed",
        )
    evaluation_rows = tuple(
        TransportabilityCandidateMemberEvaluationV1(
            member_sha256=member_id,
            member_graph_ref=(
                graph_ref
                if not pag
                else CausalGraphModelRef(
                    artifact_id="sha256:"
                    + hashlib.sha256(("cas:" + member_id).encode()).hexdigest(),
                    kind="ir.causal_graph_model",
                    media_type="application/json",
                    manifest_profile_sha256=PROFILE_SHA,
                )
            ),
            disposition="completed",
            outcome=_solver_outcome(status),
        )
        for member_id, status in zip(member_ids, statuses, strict=True)
    )
    return TransportabilityCandidateDiagnosticV1(
        candidate_request=TransportabilityCandidateRequestV1(
            profile_id=(
                "pag.no_selection.finite_member_sensitivity" if pag else "unseen.transport.profile"
            ),
            profile_revision="1",
            selection_identity="node-slot:transportability",
        ),
        effective_profile=TransportabilityCandidateProfileV1(
            profile_id=(
                "pag.no_selection.finite_member_sensitivity" if pag else "unseen.transport.profile"
            ),
            profile_revision="1",
        ),
        resource_resolution=_resource_resolution(
            "pag.no_selection.finite_member_sensitivity" if pag else "unseen.transport.profile"
        ),
        disposition="completed",
        attempt=attempt,
        inputs=inputs,
        graph_provenance="manual",
        algorithm_id="transport.solver",
        algorithm_revision="solver-v1",
        implementation_revision="source-tree-sha",
        backend_id="native",
        backend_revision="1.0",
        assumptions=("graph_member_validated_for_conditional_query",),
        unresolved_predicates=("legal_relation_unverified",),
        generation_budget=generation_budget,
        evaluation_budget=_budget("evaluation"),
        proposals=proposals,
        evaluations=evaluation_rows,
        assignment_space_size=str(len(proposals)) if pag else None,
        unattempted_proposals="0" if pag else None,
        generation_coverage=(
            "finite_endpoint_assignment_space_complete" if pag else "not_established"
        ),
        evaluated_at=datetime(2026, 10, 23, 12, 1, tzinfo=UTC),
    )


def _outer(diagnostic: TransportabilityCandidateDiagnosticV1) -> TransportabilityResult:
    return TransportabilityResult.model_validate(
        {
            "schema_version": "2.2",
            "query": QUERY,
            "status": "unsupported",
            "transport_mode": "none",
            "base_confidence": 0.0,
            "final_confidence": 0.0,
            "feasible": False,
            "source_graph_type": diagnostic.inputs.graph_type.value,
            "source_graph_sha256": diagnostic.inputs.graph_sha256,
            "source_context_id": diagnostic.inputs.source_context_id,
            "target_context_id": diagnostic.inputs.target_context_id,
            "unsupported_reason": "legal_source_relation_verification_missing",
            "requires_expert_review": True,
            "expert_review_reasons": ["legal_source_relation_verification_missing"],
            "candidate_diagnostics": diagnostic.model_dump(mode="python"),
        }
    )


def test_candidate_diagnostic_roundtrips_under_explicit_outer_refusal() -> None:
    result = _outer(_diagnostic())
    payload = result.model_dump(mode="json")

    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.transport_mode is TransportMode.NONE
    assert result.feasible is False
    assert result.id_confidence_under_pag is None
    assert result.pag_dag_sample_size is None
    assert result.pag_transportable_count is None
    assert result.candidate_diagnostics is not None
    assert payload["candidate_diagnostics"]["source_currentness"] == "unknown"
    assert payload["candidate_diagnostics"]["identified_member_fraction"] == 1.0


def test_selected_family_fraction_counts_all_completed_statuses() -> None:
    diagnostic = _diagnostic(
        graph_type=GraphType.PAG,
        statuses=(
            TransportabilityStatus.IDENTIFIED,
            TransportabilityStatus.PARTIALLY_IDENTIFIED,
            TransportabilityStatus.UNSUPPORTED,
        ),
    )

    assert diagnostic.identified_member_fraction == pytest.approx(1 / 3)
    assert diagnostic.evaluation_counts["completed"] == 3
    assert diagnostic.evaluation_counts["identified"] == 1
    assert diagnostic.evaluation_counts["partially_identified"] == 1
    assert diagnostic.evaluation_counts["unsupported"] == 1


def test_unseen_profile_is_admitted_by_the_generic_dto() -> None:
    request = TransportabilityCandidateRequestV1(
        profile_id="future.owner.profile.for.unseen.resources",
        profile_revision="9",
        selection_identity="permit:transport-compute",
    )

    assert request.profile_id == "future.owner.profile.for.unseen.resources"


def test_explicit_null_and_extra_request_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        TransportabilityCandidateRequestV1.model_validate(
            {
                "profile_id": "transport.conditional.resolved_graph",
                "profile_revision": "1",
                "selection_identity": None,
            }
        )
    with pytest.raises(ValidationError):
        TransportabilityCandidateRequestV1.model_validate(
            {
                "profile_id": "transport.conditional.resolved_graph",
                "profile_revision": "1",
                "selection_identity": "permit",
                "caller_can_run": True,
            }
        )


def test_incomplete_budget_and_wrong_lineage_do_not_validate() -> None:
    diagnostic = _diagnostic()
    payload = diagnostic.model_dump(mode="python")
    payload["evaluation_budget"] = _budget(
        "evaluation",
        admission="not_established",
        admission_source="not_established",
        termination="not_started",
    ).model_dump(mode="python")
    with pytest.raises(ValidationError):
        TransportabilityCandidateDiagnosticV1.model_validate(payload)

    payload = diagnostic.model_dump(mode="python")
    payload["inputs"]["lineage_refs"][0]["artifact_id"] = "sha256:" + "9" * 64
    with pytest.raises(ValidationError):
        TransportabilityCandidateDiagnosticV1.model_validate(payload)


def test_report_1_0_refuses_new_nested_result_and_1_1_accepts_it() -> None:
    result = _outer(_diagnostic())
    report_fields: dict[str, object] = {
        "method": CausalMethod.G_COMPUTATION,
        "status": EstimationStatus.SUCCESS,
        "estimand": "P*(Y|do(X))",
        "inference_method": "asymptotic",
        "point_estimate": 0.2,
        "confidence_interval": (0.1, 0.3),
        "sample_size": 100,
        "n_treated": 50,
        "n_control": 50,
        "pre_periods": 1,
        "post_periods": 1,
        "transport_result": result,
    }
    with pytest.raises(ValidationError):
        CausalEffectReport.model_validate({**report_fields, "schema_version": "1.0"})

    without_diagnostic = TransportabilityResult.model_validate({"schema_version": "2.2"})
    with pytest.raises(ValidationError):
        CausalEffectReport.model_validate(
            {
                **report_fields,
                "schema_version": "1.0",
                "transport_result": without_diagnostic,
            }
        )

    report = CausalEffectReport.model_validate({**report_fields, "schema_version": "1.1"})
    assert report.transport_result is not None
    assert report.transport_result.candidate_diagnostics is not None


def test_fraction_excludes_interrupted_and_error_member_rows() -> None:
    diagnostic = _diagnostic(
        graph_type=GraphType.PAG,
        statuses=(
            TransportabilityStatus.IDENTIFIED,
            TransportabilityStatus.PARTIALLY_IDENTIFIED,
            TransportabilityStatus.UNSUPPORTED,
            TransportabilityStatus.UNSUPPORTED,
        ),
    )
    member_ids = [row.member_sha256 for row in diagnostic.evaluations]
    assert all(member_ids)
    payload = diagnostic.model_dump(mode="python")
    payload.pop("identified_member_fraction")
    payload["disposition"] = "partial"
    payload["reason"] = {"code": "member_evaluation_incomplete"}
    payload["evaluation_budget"]["termination"] = "error"
    payload["evaluation_budget"]["reason"] = {"code": "solver_error"}
    payload["evaluations"] = [
        {
            "member_sha256": member_ids[0],
            "member_graph_ref": payload["evaluations"][0]["member_graph_ref"],
            "disposition": "completed",
            "outcome": _solver_outcome(TransportabilityStatus.IDENTIFIED).model_dump(mode="python"),
        },
        {
            "member_sha256": member_ids[1],
            "member_graph_ref": payload["evaluations"][1]["member_graph_ref"],
            "disposition": "completed",
            "outcome": _solver_outcome(TransportabilityStatus.PARTIALLY_IDENTIFIED).model_dump(
                mode="python"
            ),
        },
        {
            "member_sha256": member_ids[2],
            "member_graph_ref": payload["evaluations"][2]["member_graph_ref"],
            "disposition": "interrupted",
            "reason": {"code": "execution_cancelled"},
        },
        {
            "member_sha256": member_ids[3],
            "member_graph_ref": payload["evaluations"][3]["member_graph_ref"],
            "disposition": "error",
            "reason": {"code": "solver_error"},
        },
    ]

    result = TransportabilityCandidateDiagnosticV1.model_validate(payload)

    assert result.identified_member_fraction == pytest.approx(0.5)
    assert result.evaluation_counts["completed"] == 2
    assert result.evaluation_counts["interrupted"] == 1
    assert result.evaluation_counts["error"] == 1
    assert result.evaluation_counts["identified"] == 1
    assert result.evaluation_counts["partially_identified"] == 1


def test_zero_completed_rows_have_no_fraction_and_reject_fabricated_fraction() -> None:
    diagnostic = _diagnostic(
        graph_type=GraphType.PAG, statuses=(TransportabilityStatus.IDENTIFIED,)
    )
    payload = diagnostic.model_dump(mode="python")
    member_id = payload["evaluations"][0]["member_sha256"]
    payload["evaluations"] = [
        {
            "member_sha256": member_id,
            "member_graph_ref": payload["evaluations"][0]["member_graph_ref"],
            "disposition": "not_started",
            "reason": {"code": "evaluation_not_started"},
        }
    ]
    payload.pop("identified_member_fraction")
    payload["disposition"] = "partial"
    payload["reason"] = {"code": "evaluation_budget_exhausted"}
    payload["evaluation_budget"]["termination"] = "budget_exhausted"
    payload["evaluation_budget"]["reason"] = {"code": "evaluation_budget_exhausted"}

    result = TransportabilityCandidateDiagnosticV1.model_validate(payload)
    assert result.identified_member_fraction is None
    assert result.evaluation_counts["not_started"] == 1

    payload["identified_member_fraction"] = 1.0
    with pytest.raises(ValidationError):
        TransportabilityCandidateDiagnosticV1.model_validate(payload)


def test_unknown_requested_profile_is_a_typed_pre_admission_refusal() -> None:
    diagnostic = _diagnostic(graph_type=GraphType.DAG)
    payload = diagnostic.model_dump(mode="python")
    payload["effective_profile"] = None
    payload["resource_resolution"] = _resource_resolution(
        "unseen.transport.profile", status="refused"
    ).model_dump(mode="python")
    payload["disposition"] = "unsupported"
    payload["reason"] = {"code": "unknown_requested_profile"}
    payload["evaluations"] = []
    payload.pop("identified_member_fraction")
    payload["evaluation_budget"] = _budget(
        "evaluation",
        admission="not_established",
        admission_source="not_established",
        termination="not_started",
    )

    result = TransportabilityCandidateDiagnosticV1.model_validate(payload)

    assert result.candidate_request.profile_id == "unseen.transport.profile"
    assert result.effective_profile is None
    assert result.disposition == "unsupported"
    assert result.reason is not None
    assert result.evaluation_budget.admission == "not_established"


def test_unknown_effective_profile_cannot_accompany_execution_or_admission() -> None:
    diagnostic = _diagnostic(graph_type=GraphType.DAG)
    payload = diagnostic.model_dump(mode="python")
    payload["effective_profile"] = None
    payload["disposition"] = "unsupported"
    payload["reason"] = {"code": "unknown_requested_profile"}
    payload.pop("identified_member_fraction")

    with pytest.raises(ValidationError):
        TransportabilityCandidateDiagnosticV1.model_validate(payload)


def test_candidate_formula_or_confidence_cannot_escape_outer_refusal() -> None:
    result = _outer(_diagnostic())
    payload = result.model_dump(mode="python")
    payload["final_confidence"] = 0.8
    with pytest.raises(ValidationError):
        TransportabilityResult.model_validate(payload)

    payload = result.model_dump(mode="python")
    payload["transport_formula"] = {"formula_str": "P*(Y|do(X))"}
    with pytest.raises(ValidationError):
        TransportabilityResult.model_validate(payload)


def test_historical_result_version_keeps_absent_diagnostic_absent() -> None:
    historical = TransportabilityResult.model_validate({"schema_version": "2.1"})

    assert historical.candidate_diagnostics is None
    assert "candidate_diagnostics" not in historical.model_fields_set
    assert "candidate_diagnostics" not in historical.model_dump(mode="json")

    with pytest.raises(ValidationError):
        TransportabilityResult.model_validate(
            {
                "schema_version": "2.1",
                "candidate_diagnostics": None,
            }
        )


def test_proposal_counts_are_derived_and_all_invalid_is_a_partial_result() -> None:
    diagnostic = _diagnostic(
        graph_type=GraphType.PAG,
        statuses=(TransportabilityStatus.IDENTIFIED,),
    )
    payload = diagnostic.model_dump(mode="python")
    payload["disposition"] = "partial"
    payload["generation_coverage"] = "not_established"
    payload["reason"] = {"code": "zero_admitted_members_not_established"}
    payload["proposals"] = [
        {
            **row,
            "disposition": "invalid",
            "member_sha256": None,
            "duplicate_of": None,
            "reason": {"code": "member_validation_failed"},
        }
        for row in payload["proposals"]
    ]
    payload["evaluations"] = []
    payload["evaluation_budget"] = _budget("evaluation", admission="not_required")
    payload.pop("identified_member_fraction")

    result = TransportabilityCandidateDiagnosticV1.model_validate(payload)

    assert result.proposal_counts == {
        "admitted": 0,
        "duplicate": 0,
        "invalid": 1,
        "unsupported": 0,
        "validation_incomplete": 0,
    }
    assert result.generation_coverage == "not_established"
    assert result.reason is not None
    assert result.reason.code == "zero_admitted_members_not_established"
    assert result.identified_member_fraction is None


def test_duplicate_proposal_targets_prior_matching_admitted_assignment() -> None:
    diagnostic = _diagnostic(
        graph_type=GraphType.PAG,
        statuses=(
            TransportabilityStatus.IDENTIFIED,
            TransportabilityStatus.IDENTIFIED,
        ),
    )
    payload = diagnostic.model_dump(mode="python")
    first, second = payload["proposals"]
    second["disposition"] = "duplicate"
    second["assignment_sha256"] = first["assignment_sha256"]
    second["member_sha256"] = None
    second["duplicate_of"] = 0
    second["reason"] = None
    payload["proposals"] = [first, second]
    payload["evaluations"] = [payload["evaluations"][0]]
    payload.pop("identified_member_fraction")

    result = TransportabilityCandidateDiagnosticV1.model_validate(payload)
    assert result.proposal_counts["admitted"] == 1
    assert result.proposal_counts["duplicate"] == 1
    assert len(result.evaluations) == 1

    bad_payload = result.model_dump(mode="python")
    bad_payload["proposals"][1]["assignment_sha256"] = "0" * 64
    with pytest.raises(ValidationError):
        TransportabilityCandidateDiagnosticV1.model_validate(bad_payload)


def test_pre_admission_not_started_evaluations_and_generation_coverage_are_truthful() -> None:
    diagnostic = _diagnostic(
        graph_type=GraphType.PAG,
        statuses=(TransportabilityStatus.IDENTIFIED,),
    )
    payload = diagnostic.model_dump(mode="python")
    member_id = payload["evaluations"][0]["member_sha256"]
    payload["disposition"] = "partial"
    payload["reason"] = {"code": "evaluation_not_started"}
    payload["evaluations"] = [
        {
            "member_sha256": member_id,
            "member_graph_ref": payload["evaluations"][0]["member_graph_ref"],
            "disposition": "not_started",
            "reason": {"code": "evaluation_permit_not_admitted"},
        }
    ]
    payload["evaluation_budget"] = _budget(
        "evaluation",
        admission="not_established",
        admission_source="not_established",
        termination="not_started",
    )
    payload.pop("identified_member_fraction")

    result = TransportabilityCandidateDiagnosticV1.model_validate(payload)
    assert result.evaluation_counts["not_started"] == 1

    early_payload = diagnostic.model_dump(mode="python")
    early_payload["disposition"] = "partial"
    early_payload["generation_budget"]["termination"] = "budget_exhausted"
    early_payload["generation_budget"]["reason"] = {"code": "generation_budget_exhausted"}
    early_payload["disposition"] = "partial"
    early_payload["reason"] = {"code": "generation_budget_exhausted"}
    early_payload["generation_coverage"] = "finite_endpoint_assignment_space_complete"
    with pytest.raises(ValidationError):
        TransportabilityCandidateDiagnosticV1.model_validate(early_payload)

    early_payload["generation_coverage"] = "not_established"
    early_result = TransportabilityCandidateDiagnosticV1.model_validate(early_payload)
    assert early_result.generation_coverage == "not_established"


def test_budget_numeric_inputs_reject_nonfinite_and_coercive_values_by_schema() -> None:
    fixtures = (
        (
            TransportabilityCandidateResourceResolutionV1,
            _resource_resolution("future.owner.profile").model_dump(mode="python"),
        ),
        (
            TransportabilityCandidateBudgetMeasureV1,
            {"resource": "solver_calls", "value": 2, "unit": "count"},
        ),
        (
            TransportabilityCandidatePhaseBudgetV1,
            _budget("evaluation").model_dump(mode="python"),
        ),
    )
    invalid_values = (True, "1", float("nan"), float("inf"), float("-inf"))
    checked_paths = 0
    for model, fixture in fixtures:
        paths = tuple(
            dict.fromkeys(
                path
                for name, field in model.model_fields.items()
                for path in _numeric_schema_paths(field.annotation, (name,))
            )
        )
        for path in paths:
            checked_paths += 1
            for invalid in invalid_values:
                payload = deepcopy(fixture)
                _replace_numeric_path(payload, path, invalid)
                if "sha256" in model.model_fields:
                    try:
                        canonical = json.dumps(
                            {key: value for key, value in payload.items() if key != "sha256"},
                            sort_keys=True,
                            separators=(",", ":"),
                            ensure_ascii=False,
                            allow_nan=False,
                        ).encode("utf-8")
                    except ValueError:
                        payload["sha256"] = "0" * 64
                    else:
                        payload["sha256"] = hashlib.sha256(canonical).hexdigest()
                with pytest.raises(ValidationError) as error:
                    model.model_validate(payload)
                errors = error.value.errors()
                assert errors
                assert any(path[0] in item["loc"] or not item["loc"] for item in errors)
    assert checked_paths > 0


def test_budget_consumption_is_unique_and_reconciles_with_limits() -> None:
    diagnostic = _diagnostic()
    payload = diagnostic.model_dump(mode="python")
    payload["evaluation_budget"]["consumed"] = [
        {"resource": "solver_calls", "value": 2, "unit": "count"},
        {"resource": "solver_calls", "value": 1, "unit": "count"},
    ]
    with pytest.raises(ValidationError):
        TransportabilityCandidateDiagnosticV1.model_validate(payload)

    payload = diagnostic.model_dump(mode="python")
    payload["evaluation_budget"]["consumed"][0]["value"] = 999
    with pytest.raises(ValidationError):
        TransportabilityCandidateDiagnosticV1.model_validate(payload)

    payload = diagnostic.model_dump(mode="python")
    payload["evaluation_budget"]["consumed"][0]["value"] = True
    with pytest.raises(ValidationError):
        TransportabilityCandidateDiagnosticV1.model_validate(payload)

    payload = diagnostic.model_dump(mode="python")
    payload["evaluation_budget"]["consumed"][0]["value"] = 999
    payload["disposition"] = "partial"
    payload["reason"] = {"code": "solver_budget_exhausted"}
    payload["evaluation_budget"]["termination"] = "budget_exhausted"
    payload["evaluation_budget"]["reason"] = {"code": "solver_budget_exhausted"}
    partial = TransportabilityCandidateDiagnosticV1.model_validate(payload)
    assert partial.evaluation_budget.consumed[0].value == 999
    assert partial.evaluation_budget.termination == "budget_exhausted"


def test_phase_limits_must_come_from_the_typed_owner_snapshot() -> None:
    diagnostic = _diagnostic()
    payload = diagnostic.model_dump(mode="python")
    payload["evaluation_budget"]["effective_limits"][0]["value"] = 4
    with pytest.raises(ValidationError):
        TransportabilityCandidateDiagnosticV1.model_validate(payload)

    payload = diagnostic.model_dump(mode="python")
    payload["resource_resolution"]["sha256"] = "0" * 64
    with pytest.raises(ValidationError):
        TransportabilityCandidateDiagnosticV1.model_validate(payload)

    payload = diagnostic.model_dump(mode="python")
    payload["evaluation_budget"]["effective_limits"][0]["unit"] = "seconds"
    payload["evaluation_budget"]["consumed"][0]["unit"] = "seconds"
    with pytest.raises(ValidationError):
        TransportabilityCandidateDiagnosticV1.model_validate(payload)


def test_solver_source_is_full_typed_result_and_projection_is_recomputed() -> None:
    outcome = _solver_outcome(TransportabilityStatus.IDENTIFIED)
    assert outcome.result.status is TransportabilityStatus.IDENTIFIED
    payload = outcome.model_dump(mode="python")
    payload["result_sha256"] = "0" * 64
    with pytest.raises(ValidationError):
        TransportabilityCandidateSolverOutcomeV1.model_validate(payload)

    payload = outcome.model_dump(mode="python")
    payload["algorithm_version"] = "caller-selected-version"
    with pytest.raises(ValidationError):
        TransportabilityCandidateSolverOutcomeV1.model_validate(payload)

    payload = outcome.model_dump(mode="python")
    payload["result"]["candidate_diagnostics"] = _diagnostic().model_dump(mode="python")
    with pytest.raises((ValidationError, ValueError)):
        TransportabilityCandidateSolverOutcomeV1.model_validate(payload)


def test_resolved_graph_evaluation_ref_must_equal_selected_graph_ref() -> None:
    diagnostic = _diagnostic()
    payload = diagnostic.model_dump(mode="python")
    payload["evaluations"][0]["member_graph_ref"]["artifact_id"] = "sha256:" + "9" * 64
    with pytest.raises(ValidationError):
        TransportabilityCandidateDiagnosticV1.model_validate(payload)


def test_pag_complete_coverage_requires_zero_unattempted_and_completed_generation() -> None:
    diagnostic = _diagnostic(graph_type=GraphType.PAG)
    payload = diagnostic.model_dump(mode="python")
    payload["unattempted_proposals"] = "1"
    payload["assignment_space_size"] = str(len(payload["proposals"]) + 1)
    with pytest.raises(ValidationError):
        TransportabilityCandidateDiagnosticV1.model_validate(payload)

    payload = diagnostic.model_dump(mode="python")
    payload["generation_budget"]["termination"] = "budget_exhausted"
    payload["disposition"] = "partial"
    payload["reason"] = {"code": "generation_budget_exhausted"}
    with pytest.raises(ValidationError):
        TransportabilityCandidateDiagnosticV1.model_validate(payload)

    payload = diagnostic.model_dump(mode="python")
    payload["unattempted_proposals"] = "1"
    payload["assignment_space_size"] = str(len(payload["proposals"]) + 1)
    payload["generation_coverage"] = "declared_attempt_budget"
    result = TransportabilityCandidateDiagnosticV1.model_validate(payload)
    assert result.generation_coverage == "declared_attempt_budget"
    assert result.unattempted_proposals == "1"


def test_request_and_owner_resource_resolution_remain_bound_without_allowlist() -> None:
    diagnostic = _diagnostic()
    assert diagnostic.candidate_request.profile_id == "unseen.transport.profile"
    assert diagnostic.resource_resolution.status == "selected"

    payload = diagnostic.model_dump(mode="python")
    payload["candidate_request"]["selection_identity"] = "attacker-chosen"
    payload["generation_budget"]["selection_identity"] = "attacker-chosen"
    payload["evaluation_budget"]["selection_identity"] = "attacker-chosen"
    with pytest.raises(ValidationError):
        TransportabilityCandidateDiagnosticV1.model_validate(payload)


def test_pag_assignment_accounting_is_decimal_safe_and_rows_match_attempts() -> None:
    diagnostic = _diagnostic(graph_type=GraphType.PAG)
    payload = diagnostic.model_dump(mode="python")
    payload["generation_budget"]["consumed"][0]["value"] = 0
    with pytest.raises(ValidationError):
        TransportabilityCandidateDiagnosticV1.model_validate(payload)

    payload = diagnostic.model_dump(mode="python")
    unattempted = "9" * 5000
    payload["unattempted_proposals"] = unattempted
    payload["assignment_space_size"] = "1" + "0" * 5000
    payload["generation_coverage"] = "declared_attempt_budget"
    result = TransportabilityCandidateDiagnosticV1.model_validate(payload)
    assert result.unattempted_proposals == unattempted


def test_owner_snapshot_must_match_request_profile_identity() -> None:
    diagnostic = _diagnostic()
    payload = diagnostic.model_dump(mode="python")
    payload["candidate_request"]["profile_id"] = "other.resource.profile"
    with pytest.raises(ValidationError):
        TransportabilityCandidateDiagnosticV1.model_validate(payload)


def test_owner_resource_units_are_generic_and_bound_to_every_phase() -> None:
    diagnostic = _diagnostic()
    payload = diagnostic.model_dump(mode="python")
    resolution = payload["resource_resolution"]
    resolution["effective_limits"]["future_owner_resource"] = 7
    resolution["effective_limit_units"]["future_owner_resource"] = "widgets"
    canonical = json.dumps(
        {key: value for key, value in resolution.items() if key != "sha256"},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    resolution["sha256"] = hashlib.sha256(canonical).hexdigest()
    payload["evaluation_budget"]["effective_limits"] += (
        {"resource": "future_owner_resource", "value": 7, "unit": "widgets"},
    )
    payload["evaluation_budget"]["consumed"] += (
        {"resource": "future_owner_resource", "value": 2, "unit": "widgets"},
    )
    result = TransportabilityCandidateDiagnosticV1.model_validate(payload)
    assert result.resource_resolution.effective_limit_units is not None
    assert result.resource_resolution.effective_limit_units["future_owner_resource"] == "widgets"


def test_old_owner_resource_snapshot_version_is_not_reinterpreted() -> None:
    payload = _resource_resolution("transport.conditional.resolved_graph").model_dump(mode="python")
    payload["schema_version"] = "1.0"
    canonical = json.dumps(
        {key: value for key, value in payload.items() if key != "sha256"},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    payload["sha256"] = hashlib.sha256(canonical).hexdigest()
    with pytest.raises(ValidationError):
        TransportabilityCandidateResourceResolutionV1.model_validate(payload)


def test_completed_candidate_rejects_budget_failure_with_result_markers_retained() -> None:
    diagnostic = _diagnostic()
    payload = diagnostic.model_dump(mode="python")
    payload["evaluation_budget"]["consumed"][0]["value"] = 999
    payload["evaluation_budget"]["termination"] = "budget_exhausted"
    payload["evaluation_budget"]["reason"] = {"code": "solver_budget_exhausted"}
    # Keep the completed solver row, outer completed marker, and no outer reason.
    with pytest.raises(ValidationError):
        TransportabilityCandidateDiagnosticV1.model_validate(payload)

    payload["disposition"] = "partial"
    payload["reason"] = {"code": "solver_budget_exhausted"}
    result = TransportabilityCandidateDiagnosticV1.model_validate(payload)
    assert result.disposition == "partial"
    assert result.evaluations[0].disposition == "completed"


def test_outer_partial_reconciles_generation_exhaustion_with_completed_evaluation() -> None:
    diagnostic = _diagnostic(graph_type=GraphType.PAG)
    payload = diagnostic.model_dump(mode="python")
    payload["disposition"] = "partial"
    payload["reason"] = {"code": "generation_budget_exhausted"}
    payload["generation_budget"]["termination"] = "budget_exhausted"
    payload["generation_budget"]["reason"] = {"code": "generation_budget_exhausted"}
    payload["assignment_space_size"] = str(len(payload["proposals"]) + 1)
    payload["unattempted_proposals"] = "1"
    payload["generation_coverage"] = "not_established"

    result = TransportabilityCandidateDiagnosticV1.model_validate(payload)
    assert result.generation_budget.termination == "budget_exhausted"
    assert result.evaluation_budget.termination == "completed"
    assert result.disposition == "partial"


def test_outer_partial_reconciles_completed_and_error_member_rows() -> None:
    diagnostic = _diagnostic(
        graph_type=GraphType.PAG,
        statuses=(
            TransportabilityStatus.IDENTIFIED,
            TransportabilityStatus.PARTIALLY_IDENTIFIED,
        ),
    )
    payload = diagnostic.model_dump(mode="python")
    payload["disposition"] = "partial"
    payload["reason"] = {"code": "solver_member_error"}
    payload["evaluations"][1]["disposition"] = "error"
    payload["evaluations"][1]["outcome"] = None
    payload["evaluations"][1]["reason"] = {"code": "solver_member_error"}
    payload.pop("identified_member_fraction")
    payload["evaluation_budget"]["termination"] = "error"
    payload["evaluation_budget"]["reason"] = {"code": "solver_member_error"}

    result = TransportabilityCandidateDiagnosticV1.model_validate(payload)
    assert result.evaluation_counts["completed"] == 1
    assert result.evaluation_counts["error"] == 1
    assert result.disposition == "partial"


def test_outer_partial_reconciles_cancelled_phase_with_interrupted_member() -> None:
    diagnostic = _diagnostic(graph_type=GraphType.PAG)
    payload = diagnostic.model_dump(mode="python")
    member = payload["evaluations"][0]
    payload["evaluations"] = [
        {
            "member_sha256": member["member_sha256"],
            "member_graph_ref": member["member_graph_ref"],
            "disposition": "interrupted",
            "reason": {"code": "execution_cancelled"},
        }
    ]
    payload.pop("identified_member_fraction")
    payload["evaluation_budget"]["termination"] = "cancelled"
    payload["evaluation_budget"]["reason"] = {"code": "execution_cancelled"}
    payload["disposition"] = "partial"
    payload["reason"] = {"code": "execution_cancelled"}

    result = TransportabilityCandidateDiagnosticV1.model_validate(payload)
    assert result.evaluation_budget.termination == "cancelled"
    assert result.evaluation_counts["interrupted"] == 1


def test_outer_not_run_requires_no_phase_admission_or_attempt_rows() -> None:
    diagnostic = _diagnostic()
    payload = diagnostic.model_dump(mode="python")
    payload["evaluations"] = []
    payload.pop("identified_member_fraction")
    payload["evaluation_budget"] = _budget(
        "evaluation",
        admission="not_established",
        admission_source="not_established",
        termination="not_started",
    ).model_dump(mode="python")
    payload["disposition"] = "not_run"
    payload["reason"] = {"code": "execution_not_started"}

    result = TransportabilityCandidateDiagnosticV1.model_validate(payload)
    assert result.disposition == "not_run"

    payload["evaluation_budget"] = _budget("evaluation").model_dump(mode="python")
    with pytest.raises(ValidationError):
        TransportabilityCandidateDiagnosticV1.model_validate(payload)


def test_outer_status_reconciles_phase_success_refusal_and_failure() -> None:
    diagnostic = _diagnostic(graph_type=GraphType.DAG)
    base = diagnostic.model_dump(mode="python")
    base["evaluations"] = []
    base.pop("identified_member_fraction")

    for termination in ("budget_exhausted", "cancelled", "error"):
        payload = deepcopy(base)
        phase = payload["evaluation_budget"]
        phase["consumed"] = []
        phase["termination"] = termination
        phase["reason"] = {"code": f"evaluation_{termination}"}
        payload["disposition"] = "error"
        payload["reason"] = {"code": f"evaluation_{termination}"}
        result = TransportabilityCandidateDiagnosticV1.model_validate(payload)
        assert result.disposition == "error"
        assert result.evaluation_budget.termination == termination

        payload["disposition"] = "completed"
        payload["reason"] = None
        with pytest.raises(ValidationError):
            TransportabilityCandidateDiagnosticV1.model_validate(payload)

        payload["disposition"] = "not_run"
        payload["reason"] = {"code": f"evaluation_{termination}"}
        with pytest.raises(ValidationError):
            TransportabilityCandidateDiagnosticV1.model_validate(payload)

    payload = deepcopy(base)
    phase = payload["evaluation_budget"]
    phase["consumed"] = []
    phase["termination"] = "unsupported"
    phase["reason"] = {"code": "solver_unsupported"}
    payload["disposition"] = "unsupported"
    payload["reason"] = {"code": "solver_unsupported"}
    result = TransportabilityCandidateDiagnosticV1.model_validate(payload)
    assert result.disposition == "unsupported"

    payload["disposition"] = "error"
    payload["reason"] = {"code": "solver_unsupported"}
    with pytest.raises(ValidationError):
        TransportabilityCandidateDiagnosticV1.model_validate(payload)


def test_phase_completion_requires_completed_member_rows_and_declared_pag_scope() -> None:
    diagnostic = _diagnostic(
        graph_type=GraphType.PAG,
        statuses=(
            TransportabilityStatus.IDENTIFIED,
            TransportabilityStatus.PARTIALLY_IDENTIFIED,
        ),
    )
    payload = diagnostic.model_dump(mode="python")
    payload["disposition"] = "partial"
    payload["reason"] = {"code": "member_evaluation_incomplete"}
    payload["evaluations"][1]["disposition"] = "error"
    payload["evaluations"][1]["outcome"] = None
    payload["evaluations"][1]["reason"] = {"code": "solver_member_error"}
    payload.pop("identified_member_fraction")
    payload["evaluation_budget"]["termination"] = "completed"
    payload["evaluation_budget"]["reason"] = None
    with pytest.raises(ValidationError):
        TransportabilityCandidateDiagnosticV1.model_validate(payload)

    payload = diagnostic.model_dump(mode="python")
    payload["generation_coverage"] = "not_established"
    with pytest.raises(ValidationError):
        TransportabilityCandidateDiagnosticV1.model_validate(payload)

    payload = diagnostic.model_dump(mode="python")
    payload["evaluation_budget"]["termination"] = "not_required"
    payload["evaluation_budget"]["admission"] = "not_required"
    payload["evaluation_budget"]["admission_source"] = "not_required"
    payload["evaluation_budget"]["effective_limits"] = []
    payload["evaluation_budget"]["consumed"] = []
    with pytest.raises(ValidationError):
        TransportabilityCandidateDiagnosticV1.model_validate(payload)


def test_elapsed_overrun_keeps_full_solver_result_and_marks_outer_partial() -> None:
    diagnostic = _diagnostic()
    payload = diagnostic.model_dump(mode="python")
    resolution = payload["resource_resolution"]
    resolution["effective_limits"]["max_elapsed_seconds"] = 75
    resolution["effective_limit_units"]["max_elapsed_seconds"] = "seconds"
    canonical = json.dumps(
        {key: value for key, value in resolution.items() if key != "sha256"},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    resolution["sha256"] = hashlib.sha256(canonical).hexdigest()
    budget = payload["evaluation_budget"]
    budget["effective_limits"] += (
        {"resource": "max_elapsed_seconds", "value": 75, "unit": "seconds"},
    )
    budget["elapsed_seconds"] = 80.0

    with pytest.raises(ValidationError):
        TransportabilityCandidateDiagnosticV1.model_validate(payload)

    payload["evaluation_budget"]["termination"] = "budget_exhausted"
    payload["evaluation_budget"]["reason"] = {"code": "elapsed_budget_overrun"}
    payload["disposition"] = "partial"
    payload["reason"] = {"code": "elapsed_budget_overrun"}
    result = TransportabilityCandidateDiagnosticV1.model_validate(payload)
    assert result.evaluation_budget.elapsed_seconds == 80.0
    assert result.evaluation_budget.termination == "budget_exhausted"
    assert result.evaluations[0].disposition == "completed"
    assert result.evaluations[0].outcome is not None
    assert result.evaluations[0].outcome.result.status is TransportabilityStatus.IDENTIFIED


def test_outer_partial_cannot_downgrade_a_fully_successful_dag_execution() -> None:
    payload = _diagnostic(graph_type=GraphType.DAG).model_dump(mode="python")
    payload["disposition"] = "partial"
    payload["reason"] = {"code": "self_asserted_partial"}

    with pytest.raises(ValidationError):
        TransportabilityCandidateDiagnosticV1.model_validate(payload)


def test_declared_pag_attempt_scope_can_complete_without_population_coverage() -> None:
    payload = _diagnostic(
        graph_type=GraphType.PAG,
        statuses=(TransportabilityStatus.IDENTIFIED,),
    ).model_dump(mode="python")
    payload["assignment_space_size"] = str(len(payload["proposals"]) + 3)
    payload["unattempted_proposals"] = "3"
    payload["generation_coverage"] = "declared_attempt_budget"

    diagnostic = TransportabilityCandidateDiagnosticV1.model_validate(payload)

    assert diagnostic.disposition == "completed"
    assert diagnostic.generation_coverage == "declared_attempt_budget"
    assert diagnostic.unattempted_proposals == "3"
    assert len(diagnostic.evaluations) == 1
    assert diagnostic.evaluations[0].outcome is not None


def test_completed_zero_member_pag_search_is_partial_and_not_established() -> None:
    diagnostic = _diagnostic(graph_type=GraphType.PAG)
    payload = diagnostic.model_dump(mode="python")
    payload["proposals"] = tuple(
        {
            "ordinal": index,
            "assignment_sha256": f"{index + 1:x}" * 64,
            "disposition": "invalid",
            "reason": {"code": "pag_membership_mismatch"},
        }
        for index in range(4)
    )
    payload["evaluations"] = ()
    payload["identified_member_fraction"] = None
    payload["assignment_space_size"] = "4"
    payload["unattempted_proposals"] = "0"
    payload["generation_coverage"] = "not_established"
    payload["disposition"] = "partial"
    payload["reason"] = {"code": "zero_admitted_members_not_established"}
    payload["generation_budget"]["consumed"] = (
        {"resource": "max_proposals", "value": 4, "unit": "count"},
    )
    payload["evaluation_budget"] = _budget(
        "evaluation",
        admission="not_required",
        admission_source="not_required",
        termination="not_required",
    ).model_dump(mode="python")

    result = TransportabilityCandidateDiagnosticV1.model_validate(payload)

    assert result.disposition == "partial"
    assert result.reason is not None
    assert result.reason.code == "zero_admitted_members_not_established"
    assert result.generation_budget.termination == "completed"
    assert result.generation_coverage == "not_established"
    assert result.proposals and all(row.disposition == "invalid" for row in result.proposals)
    assert not result.evaluations
    assert result.identified_member_fraction is None
    assert result.unattempted_proposals == "0"


def test_completed_unknown_pag_coverage_rejects_nonzero_members() -> None:
    diagnostic = _diagnostic(graph_type=GraphType.PAG)
    payload = diagnostic.model_dump(mode="python")
    payload["generation_coverage"] = "not_established"
    payload["disposition"] = "partial"
    payload["reason"] = {"code": "zero_admitted_members_not_established"}

    with pytest.raises(ValidationError):
        TransportabilityCandidateDiagnosticV1.model_validate(payload)


def test_completed_pag_exhaustion_rejects_validation_incomplete_proposal() -> None:
    diagnostic = _diagnostic(graph_type=GraphType.PAG)
    payload = diagnostic.model_dump(mode="python")
    proposal = payload["proposals"][0]
    proposal.update(
        disposition="validation_incomplete",
        member_sha256=None,
        duplicate_of=None,
        reason={"code": "candidate_validation_incomplete"},
    )
    payload["evaluations"] = ()
    payload["identified_member_fraction"] = None
    payload["evaluation_budget"] = _budget(
        "evaluation",
        admission="not_required",
        admission_source="not_required",
        termination="not_required",
    ).model_dump(mode="python")
    payload["disposition"] = "partial"
    payload["reason"] = {"code": "generation_validation_incomplete"}

    with pytest.raises(
        ValidationError,
        match="completed_pag_exhaustion_cannot_include_validation_incomplete",
    ):
        TransportabilityCandidateDiagnosticV1.model_validate(payload)


def test_completed_pag_finite_coverage_requires_positive_admission() -> None:
    diagnostic = _diagnostic(graph_type=GraphType.PAG)
    payload = diagnostic.model_dump(mode="python")
    proposal = payload["proposals"][0]
    proposal.update(
        disposition="invalid",
        member_sha256=None,
        duplicate_of=None,
        reason={"code": "pag_membership_mismatch"},
    )
    payload["evaluations"] = ()
    payload["identified_member_fraction"] = None
    payload["evaluation_budget"] = _budget(
        "evaluation",
        admission="not_required",
        admission_source="not_required",
        termination="not_required",
    ).model_dump(mode="python")
    payload["disposition"] = "partial"
    payload["reason"] = {"code": "zero_admitted_members_not_established"}

    with pytest.raises(
        ValidationError,
        match="complete_pag_coverage_requires_positive_admission",
    ):
        TransportabilityCandidateDiagnosticV1.model_validate(payload)
