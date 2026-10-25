from __future__ import annotations

import hashlib
import time
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store, profile_bound_ref
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.causal_capabilities import CausalCapabilityContract
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
    persist_causal_graph_model,
)
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.transportability import (
    TransportabilityCandidateAttemptBindingV1,
    TransportabilityCandidateInputBindingV1,
    TransportabilityCandidateMemberEvaluationV1,
    TransportabilityCandidateRequestV1,
    TransportabilityCandidateSolverOutcomeV1,
    TransportabilityResult,
    TransportabilityStatus,
    TransportMode,
    transportability_candidate_query_sha256,
)
from polisyos.ir.artifacts.contracts import InputRef
from polisyos.ir.registry.refs import CausalGraphModelRef
from polisyos.scientist.nodes.builtins.causal import resolve_transport as resolver

_resolve_conditional_transport_resource_profile = (
    resolver._resolve_conditional_transport_resource_profile
)


def test_pag_output_cap_keeps_completed_prefix_and_records_oversized_attempt(
    tmp_path,
) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    graph = CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=["X", "Y"],
        edges=[
            CausalEdge(
                src="X",
                dst="Y",
                mark_src=EdgeMark.CIRCLE,
                mark_dst=EdgeMark.CIRCLE,
            )
        ],
        discovery_method="FCI",
    )
    unprofiled_ref = persist_causal_graph_model(store, graph)
    selected_ref = profile_bound_ref(store, unprofiled_ref)
    graph_ref = CausalGraphModelRef.model_validate(selected_ref.model_dump(mode="json"))
    assert graph_ref.manifest_profile_sha256 is not None

    request = TransportabilityCandidateRequestV1(
        profile_id="pag.no_selection.finite_member_sensitivity",
        profile_revision="1",
        selection_identity="transport-candidate.standard.v1",
    )
    resource_profile = _resolve_conditional_transport_resource_profile(request)
    resource_resolution = resolver.TransportabilityCandidateResourceResolutionV1.model_validate(
        resource_profile
    )
    source_context = ContextProfile(context_id="source")
    target_context = ContextProfile(context_id="target")
    query_treatment = "X"
    query_outcome = "Y"
    query_sha256 = transportability_candidate_query_sha256(
        query_treatment,
        query_outcome,
    )

    def input_ref(role: str) -> InputRef:
        return InputRef(
            artifact_id=graph_ref.artifact_id,
            role=role,
            manifest_profile_sha256=graph_ref.manifest_profile_sha256,
        )

    attempt_binding = TransportabilityCandidateAttemptBindingV1(
        run_id="run-output-cap",
        attempt_id="attempt-output-cap",
        attempt_number=1,
        node_alias="run_transportability",
        component_id="scientist.node_run_transportability@1.0.0",
        started_at=datetime.now(UTC),
        dispatch_params_sha256="a" * 64,
        workflow_spec_ref=input_ref("transportability_workflow_spec"),
        input_state_ref=input_ref("transportability_input_state"),
        basis_ref=input_ref("transportability_attempt_basis"),
    )
    lineage_refs = (
        attempt_binding.basis_ref,
        attempt_binding.workflow_spec_ref,
        attempt_binding.input_state_ref,
        input_ref("selected_causal_graph"),
        input_ref("causal_effect_report"),
    )
    inputs: TransportabilityCandidateInputBindingV1 = resolver._candidate_input_binding(
        graph_ref=graph_ref,
        graph=graph,
        source_context=source_context,
        target_context=target_context,
        query_treatment=query_treatment,
        query_outcome=query_outcome,
        query_sha256=query_sha256,
        lineage_refs=lineage_refs,
        requested_profile_id=request.profile_id,
        requested_profile_revision=request.profile_revision,
    )
    attempt = SimpleNamespace(
        attempt_binding=attempt_binding,
        hard_deadline_s=120.0,
        effective_worker_timeout_s=120.0,
        supervisor_deadline_monotonic=time.monotonic() + 180.0,
        workflow_params={
            resolver.CAUSAL_FULL_TRANSPORT_RESOURCE_POLICY_PARAM: resolver.causal_full_transport_resource_policy_snapshot()
        },
    )
    small = TransportabilityResult(
        query="P*(Y|do(X))",
        status=TransportabilityStatus.IDENTIFIED,
        transport_mode=TransportMode.DIRECT,
        algorithm_version="controlled-output-cap-test",
        identification_engine="controlled-output-cap-test",
        identification_trace=["small retained solver result"],
    )
    oversized = small.model_copy(
        update={"identification_trace": ["x" * 300_000]},
    )
    solver_results = [small, oversized, small]

    def evaluate_member(**kwargs):
        result = solver_results.pop(0)
        return TransportabilityCandidateMemberEvaluationV1(
            member_sha256=kwargs["member"].member_sha256,
            member_graph_ref=kwargs["member_graph_ref"],
            disposition="completed",
            outcome=TransportabilityCandidateSolverOutcomeV1.from_result(
                result,
                query_sha256=hashlib.sha256(result.query.encode("utf-8")).hexdigest(),
            ),
        )

    with (
        patch.object(resolver, "_candidate_solver_revision", return_value="sha256:" + "b" * 64),
        patch.object(
            resolver,
            "evaluate_pag_member_candidate",
            side_effect=evaluate_member,
        ) as solve,
    ):
        diagnostic = resolver._conditional_transport_pag_member_diagnostic(
            ctx=SimpleNamespace(store=store),
            request=request,
            attempt=attempt,
            graph_ref=graph_ref,
            graph=graph,
            source_context=source_context,
            target_context=target_context,
            inputs=inputs,
            query_treatment=query_treatment,
            query_outcome=query_outcome,
            query_sha256=query_sha256,
            solver_mode="auto",
            allow_degraded_transport=False,
            capability_contract=CausalCapabilityContract(
                dependency_fingerprint="controlled-output-cap-test"
            ),
            privacy_context=None,
            resource_profile=resource_profile,
            resource_resolution=resource_resolution,
        )

    assert solve.call_count == 2
    assert [row.disposition for row in diagnostic.evaluations] == [
        "completed",
        "error",
        "not_started",
    ]
    assert diagnostic.evaluations[0].outcome is not None
    assert diagnostic.evaluations[0].outcome.result.identification_trace == [
        "small retained solver result"
    ]
    assert diagnostic.evaluations[1].reason is not None
    assert diagnostic.evaluations[1].reason.code == "result_not_retained_due_output_budget"
    assert diagnostic.evaluations[2].reason is not None
    assert diagnostic.disposition == "partial"
    estimate = diagnostic.parameters["work_estimate"]
    assert estimate["d_separation_query_bound"]["value"] == 4
    assert not estimate["d_separation_query_bound"]["exceeded_ceiling"]
    assert estimate["expanded_graph_element_query_bound"]["value"] == 20
    assert not estimate["expanded_graph_element_query_bound"]["exceeded_ceiling"]
    assert diagnostic.evaluation_budget.termination == "budget_exhausted"
    assert diagnostic.evaluation_budget.reason is not None
    assert diagnostic.evaluation_budget.reason.code == "result_not_retained_due_output_budget"
    limits = {item.resource: item.value for item in diagnostic.evaluation_budget.effective_limits}
    consumed = {item.resource: item for item in diagnostic.evaluation_budget.consumed}
    assert consumed["max_diagnostic_bytes"].unit == "bytes"
    assert consumed["max_diagnostic_bytes"].value > limits["max_diagnostic_bytes"]
    assert diagnostic.parameters["evaluation_source_member_count"] == 3
    assert diagnostic.parameters["evaluation_attempted_member_count"] == 2
    assert diagnostic.parameters["evaluation_completed_retained_member_count"] == 1
    assert diagnostic.parameters["evaluation_not_started_member_count"] == 1
    assert diagnostic.parameters["identified_member_fraction_denominator"] == 1
    assert diagnostic.identified_member_fraction == 1.0


def test_resource_snapshot_uses_verified_hard_deadline_and_refuses_unbounded_or_incompatible() -> (
    None
):
    request = TransportabilityCandidateRequestV1(
        profile_id="transport.conditional.resolved_graph",
        profile_revision="1",
        selection_identity="transport-candidate.standard.v1",
    )

    selected = _resolve_conditional_transport_resource_profile(
        request,
        actual_node_timeout_s=90.0,
    )
    assert selected["status"] == "selected"
    assert selected["effective_limits"]["node_timeout_s"] == 90.0
    assert selected["effective_limits"]["max_elapsed_seconds"] < 90.0

    for timeout, expected_reason in (
        (None, "conditional_transport_node_timeout_not_configured"),
        (60.0, "conditional_transport_node_timeout_incompatible_with_phase_budget"),
        (121.0, "conditional_transport_node_timeout_exceeds_owner_profile"),
    ):
        refused = _resolve_conditional_transport_resource_profile(
            request,
            actual_node_timeout_s=timeout,
        )
        assert refused["status"] == "refused"
        assert refused["reason_code"] == expected_reason
        assert refused["effective_limits"] is None
        assert refused["effective_limit_units"] is None


def test_resource_policy_snapshot_refuses_stale_or_forged_limits() -> None:
    from polisyos.scientist.orchestration.workflows.causal_full import (
        causal_full_transport_resource_policy_snapshot,
    )

    request = TransportabilityCandidateRequestV1(
        profile_id="transport.conditional.resolved_graph",
        profile_revision="1",
        selection_identity="transport-candidate.standard.v1",
    )
    current = causal_full_transport_resource_policy_snapshot()
    selected = _resolve_conditional_transport_resource_profile(
        request,
        actual_node_timeout_s=90.0,
        frozen_policy_snapshot=current,
    )
    assert selected["status"] == "selected"

    stale_snapshot = {
        **current,
        "limits": {**current["limits"], "max_evaluations": 63},
    }
    refused = _resolve_conditional_transport_resource_profile(
        request,
        actual_node_timeout_s=90.0,
        frozen_policy_snapshot=stale_snapshot,
    )
    assert refused["status"] == "refused"
    assert refused["reason_code"] == ("conditional_transport_resource_policy_snapshot_mismatch")
    assert refused["effective_limits"] is None


def graph_ref_for_test() -> CausalGraphModelRef:
    return CausalGraphModelRef(
        artifact_id="sha256:" + "b" * 64,
        manifest_profile_sha256="sha256:" + "a" * 64,
    )


def test_complete_transport_result_is_capped_before_persistence(tmp_path) -> None:
    diagnostic_request = TransportabilityCandidateRequestV1(
        profile_id="transport.conditional.resolved_graph",
        profile_revision="1",
        selection_identity="transport-candidate.standard.v1",
    )
    resolved = _resolve_conditional_transport_resource_profile(diagnostic_request)
    resource_resolution = resolver.TransportabilityCandidateResourceResolutionV1.model_validate(
        resolved
    )
    diagnostic = resolver.TransportabilityCandidateDiagnosticV1(
        candidate_request=diagnostic_request,
        effective_profile=resolver.TransportabilityCandidateProfileV1(
            profile_id=diagnostic_request.profile_id,
            profile_revision=diagnostic_request.profile_revision,
        ),
        resource_resolution=resource_resolution,
        disposition="unsupported",
        reason=resolver.TransportabilityCandidateReasonV1(
            code="candidate_input_not_supported",
            detail="Test-only bounded refusal.",
        ),
        attempt=resolver.TransportabilityCandidateAttemptBindingV1(
            run_id="run-result-cap",
            attempt_id="attempt-result-cap",
            attempt_number=1,
            node_alias="run_transportability",
            component_id="scientist.node_run_transportability@1.0.0",
            started_at=datetime.now(UTC),
            dispatch_params_sha256="c" * 64,
            workflow_spec_ref=InputRef(
                artifact_id=graph_ref_for_test().artifact_id,
                role="transportability_workflow_spec",
                manifest_profile_sha256="sha256:" + "a" * 64,
            ),
            input_state_ref=InputRef(
                artifact_id=graph_ref_for_test().artifact_id,
                role="transportability_input_state",
                manifest_profile_sha256="sha256:" + "a" * 64,
            ),
            basis_ref=InputRef(
                artifact_id=graph_ref_for_test().artifact_id,
                role="transportability_attempt_basis",
                manifest_profile_sha256="sha256:" + "a" * 64,
            ),
        ),
        inputs=resolver.TransportabilityCandidateInputBindingV1(
            graph_ref=graph_ref_for_test(),
            graph_type=GraphType.DAG,
            graph_sha256="d" * 64,
            selection_diagram_sha256="e" * 64,
            query_treatment="X",
            query_outcome="Y",
            query_sha256=transportability_candidate_query_sha256("X", "Y"),
            source_context_id="source",
            source_context_sha256="f" * 64,
            target_context_id="target",
            target_context_sha256="1" * 64,
            lineage_refs=(
                InputRef(
                    artifact_id=graph_ref_for_test().artifact_id,
                    role="transportability_attempt_basis",
                    manifest_profile_sha256="sha256:" + "a" * 64,
                ),
                InputRef(
                    artifact_id=graph_ref_for_test().artifact_id,
                    role="transportability_workflow_spec",
                    manifest_profile_sha256="sha256:" + "a" * 64,
                ),
                InputRef(
                    artifact_id=graph_ref_for_test().artifact_id,
                    role="transportability_input_state",
                    manifest_profile_sha256="sha256:" + "a" * 64,
                ),
                InputRef(
                    artifact_id=graph_ref_for_test().artifact_id,
                    role="selected_causal_graph",
                    manifest_profile_sha256="sha256:" + "a" * 64,
                ),
                InputRef(
                    artifact_id=graph_ref_for_test().artifact_id,
                    role="causal_effect_report",
                    manifest_profile_sha256="sha256:" + "a" * 64,
                ),
            ),
        ),
        graph_provenance="unknown",
        algorithm_id="test",
        algorithm_revision="1",
        implementation_revision="test",
        backend_id="not_established",
        backend_revision="not_established",
        parameters={},
        generation_budget=resolver._candidate_budget_phase(
            phase="generation",
            selection_identity=diagnostic_request.selection_identity,
            admission="not_required",
            termination="not_required",
        ),
        evaluation_budget=resolver._candidate_budget_phase(
            phase="evaluation",
            selection_identity=diagnostic_request.selection_identity,
            admission="refused",
            reason=resolver.TransportabilityCandidateReasonV1(
                code="candidate_budget_not_admitted",
                detail="Test-only owner refusal.",
            ),
            termination="not_started",
        ),
        generation_coverage="not_established",
        evaluated_at=datetime.now(UTC),
    )
    refusal_code = "candidate_input_not_supported"
    minimal = TransportabilityResult(
        query="P*(Y|do(X))",
        schema_version="2.2",
        status=TransportabilityStatus.UNSUPPORTED,
        transport_mode=TransportMode.NONE,
        feasible=False,
        unsupported_reason=refusal_code,
        requires_expert_review=True,
        expert_review_reasons=[refusal_code],
        source_graph_type=GraphType.DAG,
        source_graph_sha256="d" * 64,
        source_context_id="source",
        target_context_id="target",
        base_confidence=0.0,
        final_confidence=0.0,
        candidate_diagnostics=diagnostic,
    )
    small_result = minimal.model_copy(
        update={
            "candidate_diagnostics": diagnostic,
            "identification_trace": ["café"],
        },
    )
    resolver._require_candidate_transport_result_within_output_budget(small_result)
    cas_root = tmp_path / "result-cap"
    store = ensure_ir_artifact_store(FileSystemCAS(cas_root))
    ref = resolver.persist_transportability_result(
        store,
        small_result,
        schema_version="2.2",
        return_selected_profile=True,
    )
    persisted = store.get_bytes(ref)
    assert persisted == resolver._candidate_persisted_result_bytes(small_result)
    assert b"caf\xc3\xa9" in persisted

    limit = int(resource_resolution.effective_limits["max_diagnostic_bytes"])
    empty_trace_result = small_result.model_copy(update={"identification_trace": []})
    empty_size = len(resolver._candidate_persisted_result_bytes(empty_trace_result))
    exact_trace_size = limit - empty_size - 2
    one_below = empty_trace_result.model_copy(
        update={"identification_trace": ["x" * (exact_trace_size - 1)]}
    )
    exact_limit = empty_trace_result.model_copy(
        update={"identification_trace": ["x" * exact_trace_size]}
    )
    one_over = empty_trace_result.model_copy(
        update={"identification_trace": ["x" * (exact_trace_size + 1)]}
    )
    warning_over = exact_limit.model_copy(
        update={"warnings": ["normalization warning added after candidate handling"]}
    )
    assert len(resolver._candidate_persisted_result_bytes(one_below)) == limit - 1
    assert len(resolver._candidate_persisted_result_bytes(exact_limit)) == limit
    assert len(resolver._candidate_persisted_result_bytes(one_over)) == limit + 1
    assert len(resolver._candidate_persisted_result_bytes(warning_over)) > limit
    resolver._require_candidate_transport_result_within_output_budget(one_below)
    resolver._require_candidate_transport_result_within_output_budget(exact_limit)
    cas_files_before_refusal = {
        path.relative_to(cas_root) for path in cas_root.rglob("*") if path.is_file()
    }
    with pytest.raises(
        resolver.InvalidTransportInput,
        match="complete_result_exceeds_output_budget",
    ):
        resolver._require_candidate_transport_result_within_output_budget(one_over)
    with pytest.raises(
        resolver.InvalidTransportInput,
        match="complete_result_exceeds_output_budget",
    ):
        resolver._require_candidate_transport_result_within_output_budget(warning_over)
    assert {
        path.relative_to(cas_root) for path in cas_root.rglob("*") if path.is_file()
    } == cas_files_before_refusal

    oversized_result = minimal.model_copy(
        update={
            "candidate_diagnostics": diagnostic,
            "identification_trace": ["x" * 300_000],
        },
    )
    with pytest.raises(
        resolver.InvalidTransportInput,
        match="complete_result_exceeds_output_budget",
    ):
        resolver._require_candidate_transport_result_within_output_budget(oversized_result)
