from __future__ import annotations

import copy
import time
from datetime import UTC, datetime
from itertools import combinations
from types import SimpleNamespace
from unittest.mock import patch

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
    TransportabilityCandidateRequestV1,
    transportability_candidate_query_sha256,
)
from polisyos.ir.artifacts.contracts import InputRef
from polisyos.ir.registry.refs import CausalGraphModelRef
from polisyos.scientist.nodes.builtins.causal import resolve_transport as resolver


def _complete_circle_pag() -> CausalGraphModel:
    nodes = ["X0", "X1", "X2"]
    return CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=nodes,
        edges=[
            CausalEdge(src=src, dst=dst, mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.CIRCLE)
            for src, dst in combinations(nodes, 2)
        ],
        discovery_method="FCI",
    )


def test_owner_work_preflight_refuses_before_generation_on_dsep_limit(tmp_path) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    graph = _complete_circle_pag()
    unprofiled_ref = persist_causal_graph_model(store, graph)
    selected_ref = profile_bound_ref(store, unprofiled_ref)
    graph_ref = CausalGraphModelRef.model_validate(selected_ref.model_dump(mode="json"))
    request = TransportabilityCandidateRequestV1(
        profile_id="pag.no_selection.finite_member_sensitivity",
        profile_revision="1",
        selection_identity="transport-candidate.standard.v1",
    )
    source_context = ContextProfile(context_id="source")
    target_context = ContextProfile(context_id="target")
    query_treatment = "X0"
    query_outcome = "X1"
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
        run_id="run-work-preflight",
        attempt_id="attempt-work-preflight",
        attempt_number=1,
        node_alias="run_transportability",
        component_id="scientist.node_run_transportability@1.0.0",
        started_at=datetime.now(UTC),
        dispatch_params_sha256="a" * 64,
        workflow_spec_ref=input_ref("transportability_workflow_spec"),
        input_state_ref=input_ref("transportability_input_state"),
        basis_ref=input_ref("transportability_attempt_basis"),
    )
    inputs: TransportabilityCandidateInputBindingV1 = resolver._candidate_input_binding(
        graph_ref=graph_ref,
        graph=graph,
        source_context=source_context,
        target_context=target_context,
        query_treatment=query_treatment,
        query_outcome=query_outcome,
        query_sha256=query_sha256,
        lineage_refs=(
            attempt_binding.basis_ref,
            attempt_binding.workflow_spec_ref,
            attempt_binding.input_state_ref,
            input_ref("selected_causal_graph"),
            input_ref("causal_effect_report"),
        ),
        requested_profile_id=request.profile_id,
        requested_profile_revision=request.profile_revision,
    )
    policy_snapshot = copy.deepcopy(resolver.causal_full_transport_resource_policy_snapshot())
    policy_snapshot["limits"]["max_estimated_dsep_queries"] = 64
    attempt = SimpleNamespace(
        attempt_binding=attempt_binding,
        hard_deadline_s=120.0,
        effective_worker_timeout_s=120.0,
        supervisor_deadline_monotonic=time.monotonic() + 180.0,
        workflow_params={resolver.CAUSAL_FULL_TRANSPORT_RESOURCE_POLICY_PARAM: policy_snapshot},
    )

    with (
        patch.object(
            resolver,
            "causal_full_transport_resource_policy_snapshot",
            return_value=policy_snapshot,
        ),
        patch.object(
            resolver,
            "evaluate_pag_member_family",
            side_effect=AssertionError("generation must not start after a failed preflight"),
        ) as generate,
    ):
        resource_profile = resolver._resolve_conditional_transport_resource_profile(
            request,
            actual_node_timeout_s=120.0,
            frozen_policy_snapshot=policy_snapshot,
        )
        resource_resolution = resolver.TransportabilityCandidateResourceResolutionV1.model_validate(
            resource_profile
        )
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
                dependency_fingerprint="controlled-work-preflight-test"
            ),
            privacy_context=None,
            resource_profile=resource_profile,
            resource_resolution=resource_resolution,
        )

    assert not generate.called
    assert diagnostic.disposition == "unsupported"
    assert diagnostic.reason is not None
    assert (
        diagnostic.reason.code
        == "conditional_transport_candidate_work_estimate_exceeds_owner_limits"
    )
    assert diagnostic.assignment_space_size == "64"
    assert diagnostic.unattempted_proposals == "64"
    assert diagnostic.proposals == ()
    assert diagnostic.evaluations == ()
    estimate = diagnostic.parameters["work_estimate"]
    assert estimate["d_separation_query_bound"] == {
        "value": 65,
        "ceiling": 64,
        "exceeded_ceiling": True,
    }
    assert estimate["expanded_graph_element_query_bound"]["exceeded_ceiling"] is False
    assert diagnostic.generation_budget.termination == "not_started"
    assert diagnostic.evaluation_budget.termination == "not_started"


def test_causal_full_policy_keeps_backend_optional_at_workflow_construction() -> None:
    from polisyos.scientist.orchestration.workflows.causal_full import (
        CAUSAL_FULL_TRANSPORT_RESOURCE_POLICY_PARAM,
        causal_full_transport_resource_policy_snapshot,
        causal_full_workflow_spec,
    )

    snapshot = causal_full_transport_resource_policy_snapshot()
    assert snapshot["work_estimator"]["status"] in {"available", "unavailable"}
    workflow = causal_full_workflow_spec()
    invocations = [node for node in workflow.nodes if node.alias == "run_transportability"]
    assert len(invocations) == 1
    assert invocations[0].params[CAUSAL_FULL_TRANSPORT_RESOURCE_POLICY_PARAM] == snapshot


def test_owner_rejects_incomplete_or_shifted_exhausted_pag_family_before_completion(
    tmp_path,
) -> None:
    from polisyos.ir.analytics.causal_graph import CausalEdge
    from polisyos.scientist.nodes.builtins.causal.resolve_transport import PAGMemberBudget

    cases = (("shifted", (1, 2)), ("incomplete", (0, 1)))
    for case_name, proposal_ordinals in cases:
        case_path = tmp_path / f"case-{proposal_ordinals[0]}"
        store = ensure_ir_artifact_store(FileSystemCAS(case_path / "cas"))
        graph = CausalGraphModel(
            graph_type=GraphType.PAG,
            nodes=["X0", "X1"],
            edges=[
                CausalEdge(
                    src="X0",
                    dst="X1",
                    mark_src=EdgeMark.CIRCLE,
                    mark_dst=EdgeMark.ARROW,
                )
            ],
            discovery_method="FCI",
        )
        unprofiled_ref = persist_causal_graph_model(store, graph)
        selected_ref = profile_bound_ref(store, unprofiled_ref)
        graph_ref = CausalGraphModelRef.model_validate(selected_ref.model_dump(mode="json"))
        request = TransportabilityCandidateRequestV1(
            profile_id="pag.no_selection.finite_member_sensitivity",
            profile_revision="1",
            selection_identity="transport-candidate.standard.v1",
        )
        source_context = ContextProfile(context_id="source")
        target_context = ContextProfile(context_id="target")
        query_treatment = "X0"
        query_outcome = "X1"
        query_sha256 = transportability_candidate_query_sha256(
            query_treatment,
            query_outcome,
        )

        def input_ref(role: str, *, selected_ref=graph_ref) -> InputRef:
            return InputRef(
                artifact_id=selected_ref.artifact_id,
                role=role,
                manifest_profile_sha256=selected_ref.manifest_profile_sha256,
            )

        attempt_binding = TransportabilityCandidateAttemptBindingV1(
            run_id=f"run-owner-exhausted-{proposal_ordinals[0]}",
            attempt_id=f"attempt-owner-exhausted-{proposal_ordinals[0]}",
            attempt_number=1,
            node_alias="run_transportability",
            component_id="scientist.node_run_transportability@1.0.0",
            started_at=datetime.now(UTC),
            dispatch_params_sha256="a" * 64,
            workflow_spec_ref=input_ref("transportability_workflow_spec"),
            input_state_ref=input_ref("transportability_input_state"),
            basis_ref=input_ref("transportability_attempt_basis"),
        )
        inputs = resolver._candidate_input_binding(
            graph_ref=graph_ref,
            graph=graph,
            source_context=source_context,
            target_context=target_context,
            query_treatment=query_treatment,
            query_outcome=query_outcome,
            query_sha256=query_sha256,
            lineage_refs=(
                attempt_binding.basis_ref,
                attempt_binding.workflow_spec_ref,
                attempt_binding.input_state_ref,
                input_ref("selected_causal_graph"),
                input_ref("causal_effect_report"),
            ),
            requested_profile_id=request.profile_id,
            requested_profile_revision=request.profile_revision,
        )
        policy_snapshot = resolver.causal_full_transport_resource_policy_snapshot()
        attempt = SimpleNamespace(
            attempt_binding=attempt_binding,
            hard_deadline_s=120.0,
            effective_worker_timeout_s=120.0,
            supervisor_deadline_monotonic=time.monotonic() + 180.0,
            workflow_params={resolver.CAUSAL_FULL_TRANSPORT_RESOURCE_POLICY_PARAM: policy_snapshot},
        )
        resource_profile = resolver._resolve_conditional_transport_resource_profile(
            request,
            actual_node_timeout_s=120.0,
            frozen_policy_snapshot=policy_snapshot,
        )
        resource_resolution = resolver.TransportabilityCandidateResourceResolutionV1.model_validate(
            resource_profile
        )
        limits = resource_profile["effective_limits"]
        budget = PAGMemberBudget(
            max_proposals=limits["max_proposals"],
            max_members=limits["max_members"],
            max_oracle_operations=limits["max_oracle_operations"],
            max_elapsed_seconds=limits["max_elapsed_seconds"],
            max_output_bytes=limits["max_output_bytes"],
        )
        admitted_ordinal, incomplete_ordinal = proposal_ordinals
        admitted_sha = "b" * 64
        incomplete_sha = "c" * 64
        member_graph = CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["X0", "X1"],
            edges=[
                CausalEdge(
                    src="X0",
                    dst="X1",
                    mark_src=EdgeMark.TAIL,
                    mark_dst=EdgeMark.ARROW,
                )
            ],
            discovery_method="FCI",
        )
        member_sha = resolver.graph_content_sha256(member_graph)
        if case_name == "incomplete":
            family_status = resolver.PAGMemberFamilyStatus.COMPLETED
            family_coverage = (
                resolver.PAGMemberFamilyCoverage.FINITE_ENDPOINT_ASSIGNMENT_SPACE_COMPLETE
            )
            family_reason = None
            family_counts = SimpleNamespace(
                proposals_attempted=2,
                unattempted_proposals="0",
                assignment_space_size="2",
                admitted=1,
                duplicate=0,
                invalid=0,
                unsupported=0,
                validation_incomplete=1,
                oracle_operations=1,
            )
            proposal_rows = (
                SimpleNamespace(
                    ordinal=admitted_ordinal,
                    assignment_sha256=admitted_sha,
                    disposition=resolver.PAGProposalDisposition.ADMITTED,
                    member_sha256=member_sha,
                    duplicate_of=None,
                    reason_code=None,
                ),
                SimpleNamespace(
                    ordinal=incomplete_ordinal,
                    assignment_sha256=incomplete_sha,
                    disposition=resolver.PAGProposalDisposition.VALIDATION_INCOMPLETE,
                    member_sha256=None,
                    duplicate_of=None,
                    reason_code="membership_oracle_failed",
                ),
            )
            member_rows = (
                SimpleNamespace(
                    proposal_ordinal=admitted_ordinal,
                    assignment_sha256=admitted_sha,
                    member_sha256=member_sha,
                    graph=member_graph,
                ),
            )
        else:
            family_status = resolver.PAGMemberFamilyStatus.NOT_ESTABLISHED
            family_coverage = resolver.PAGMemberFamilyCoverage.NOT_ESTABLISHED
            family_reason = "zero_admitted_members_not_established"
            family_counts = SimpleNamespace(
                proposals_attempted=2,
                unattempted_proposals="0",
                assignment_space_size="2",
                admitted=0,
                duplicate=0,
                invalid=2,
                unsupported=0,
                validation_incomplete=0,
                oracle_operations=0,
            )
            proposal_rows = tuple(
                SimpleNamespace(
                    ordinal=ordinal,
                    assignment_sha256=("c" if offset else "b") * 64,
                    disposition=resolver.PAGProposalDisposition.INVALID,
                    member_sha256=None,
                    duplicate_of=None,
                    reason_code="structural_invalid",
                )
                for offset, ordinal in enumerate(proposal_ordinals)
            )
            member_rows = ()
        family = SimpleNamespace(
            profile_id=request.profile_id,
            profile_revision=request.profile_revision,
            source_graph_sha256=inputs.graph_sha256,
            budget=budget,
            backend_identity=None,
            status=family_status,
            coverage=family_coverage,
            reason_code=family_reason,
            elapsed_seconds=0.01,
            trace_bytes=0,
            counts=family_counts,
            proposals=proposal_rows,
            members=member_rows,
        )

        with (
            patch.object(resolver, "evaluate_pag_member_family", return_value=family),
            patch.object(
                resolver,
                "persist_causal_graph_model",
                side_effect=AssertionError(
                    "invalid exhausted family reached member result persistence"
                ),
            ) as persist_member,
        ):
            try:
                resolver._conditional_transport_pag_member_diagnostic(
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
                        dependency_fingerprint="owner-exhausted-family-test"
                    ),
                    privacy_context=None,
                    resource_profile=resource_profile,
                    resource_resolution=resource_resolution,
                )
            except ValueError as exc:
                assert str(exc) == (
                    "conditional_transport_candidate_pag_producer_completion_binding_mismatch"
                )
            else:
                raise AssertionError(
                    "owner accepted validation-incomplete/nonexact proposal partition as complete"
                )
            assert not persist_member.called
