"""Behavioral owner witness for validated partial PAG member evaluation.

This follows G06 §§4–5 and G04 §§34–42: membership is per proposal, while
generation coverage remains not established for an early-stopped family.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.causal.capabilities import (
    build_causal_capability_contract,
)
from polisyos.foundry.methods.catalog.causal.pag_member_family import (
    PAGAdmittedMember,
    PAGMemberBudget,
    PAGMemberFamilyCoverage,
    PAGMemberFamilyResult,
    PAGMemberFamilyStatus,
    PAGProposalDisposition,
    evaluate_pag_member_family,
)
from polisyos.foundry.methods.catalog.causal.transport_engine import (
    TransportCandidateMemberBindingError,
    evaluate_pag_member_candidate,
)
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
    graph_content_sha256,
    load_causal_graph_model,
    persist_causal_graph_model,
)
from polisyos.ir.analytics.context import ContextProfile, IncomeLevel
from polisyos.ir.analytics.transportability import (
    TransportabilityCandidateInputBindingV1,
    TransportabilityCandidateMemberEvaluationV1,
    TransportabilityCandidateModelPlanRelationV1,
    build_selection_diagram,
    transportability_candidate_query_sha256,
)
from polisyos.ir.artifacts import InputRef
from polisyos.ir.model_layer.canon import CanonSpec, to_canonical_bytes
from polisyos.ir.registry.refs import CausalGraphModelRef

_PROFILE_ID = "pag.no_selection.finite_member_sensitivity"
_PROFILE_REVISION = "1"
_PROFILE_HASH = "sha256:" + "a" * 64
_CANON = CanonSpec(forbid_floats=False, sort_keys=True, exclude_none=False)
_TREATMENT = "consumption_response"
_OUTCOME = "gdp_growth"


def _sha(value: object) -> str:
    return hashlib.sha256(to_canonical_bytes(value, _CANON)).hexdigest()


def _route_pag() -> CausalGraphModel:
    """Match the route witness: four nodes, 12 circles, and 4,096 assignments."""
    nodes = [_TREATMENT, _OUTCOME, "education", "employment"]
    return CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=nodes,
        edges=[
            CausalEdge(
                src=nodes[left],
                dst=nodes[right],
                mark_src=EdgeMark.CIRCLE,
                mark_dst=EdgeMark.CIRCLE,
            )
            for left in range(len(nodes))
            for right in range(left + 1, len(nodes))
        ],
        discovery_method="FCI",
    )


def _two_node_pag() -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=[_TREATMENT, _OUTCOME],
        edges=[
            CausalEdge(
                src=_TREATMENT,
                dst=_OUTCOME,
                mark_src=EdgeMark.CIRCLE,
                mark_dst=EdgeMark.CIRCLE,
            )
        ],
        discovery_method="FCI",
    )


def _zero_member_pag() -> CausalGraphModel:
    """Use the G06 discriminating-path counterexample after weakening A-D."""
    return CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=["A", "B", "C", "D", "E"],
        edges=[
            CausalEdge(src="A", dst="C", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="A", dst="D", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="A", dst="E", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.CIRCLE),
            CausalEdge(src="B", dst="C", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="C", dst="D", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        ],
        discovery_method="FCI",
    )


def _budget(*, proposals: int, members: int, oracle: int) -> PAGMemberBudget:
    return PAGMemberBudget(
        max_proposals=proposals,
        max_members=members,
        max_oracle_operations=oracle,
        max_elapsed_seconds=75.0,
        max_output_bytes=1_000_000,
    )


def _persist_and_reload(
    cas_root: Path, graph: CausalGraphModel
) -> tuple[CausalGraphModelRef, CausalGraphModel]:
    writer = ensure_ir_artifact_store(FileSystemCAS(cas_root))
    selected_ref = persist_causal_graph_model(
        writer,
        graph,
        schema_version="1.1",
        return_selected_profile=True,
    )
    reader = ensure_ir_artifact_store(FileSystemCAS(cas_root))
    loaded = load_causal_graph_model(reader, selected_ref)
    assert loaded.model_dump(mode="json") == graph.model_dump(mode="json")
    assert selected_ref.manifest_profile_sha256 is not None
    return selected_ref, loaded


def _binding(
    graph: CausalGraphModel,
    graph_ref: CausalGraphModelRef,
    source: ContextProfile,
    target: ContextProfile,
    treatment: str,
    outcome: str,
) -> TransportabilityCandidateInputBindingV1:
    query_sha = transportability_candidate_query_sha256(treatment, outcome)
    source_sha = _sha(source.model_dump(mode="json"))
    target_sha = _sha(target.model_dump(mode="json"))
    base = {
        "graph_ref": graph_ref.model_dump(mode="json"),
        "graph_type": graph.graph_type.value,
        "graph_sha256": graph_content_sha256(graph),
        "query_treatment": treatment,
        "query_outcome": outcome,
        "query_sha256": query_sha,
        "source_context_id": source.context_id,
        "source_context_sha256": source_sha,
        "target_context_id": target.context_id,
        "target_context_sha256": target_sha,
        "profile_id": _PROFILE_ID,
        "profile_revision": _PROFILE_REVISION,
    }
    relation_id = "transportability.pag.no_selection.member_selection_diagrams"
    relation_revision = "1"
    relation_payload = {"relation_id": relation_id, "revision": relation_revision, **base}
    lineage = (
        InputRef(
            artifact_id="sha256:" + "2" * 64,
            role="transportability_attempt_basis",
            manifest_profile_sha256=_PROFILE_HASH,
        ),
        InputRef(
            artifact_id="sha256:" + "3" * 64,
            role="transportability_workflow_spec",
            manifest_profile_sha256=_PROFILE_HASH,
        ),
        InputRef(
            artifact_id="sha256:" + "4" * 64,
            role="transportability_input_state",
            manifest_profile_sha256=_PROFILE_HASH,
        ),
        InputRef(
            artifact_id=graph_ref.artifact_id,
            role="selected_causal_graph",
            manifest_profile_sha256=graph_ref.manifest_profile_sha256,
        ),
        InputRef(
            artifact_id="sha256:" + "5" * 64,
            role="causal_effect_report",
            manifest_profile_sha256=_PROFILE_HASH,
        ),
    )
    return TransportabilityCandidateInputBindingV1(
        graph_ref=graph_ref,
        graph_type=graph.graph_type,
        graph_sha256=base["graph_sha256"],
        model_plan_relation=TransportabilityCandidateModelPlanRelationV1(
            relation_id=relation_id,
            revision=relation_revision,
            content_sha256=_sha(relation_payload),
        ),
        query_treatment=treatment,
        query_outcome=outcome,
        query_sha256=query_sha,
        source_context_id=source.context_id,
        source_context_sha256=source_sha,
        target_context_id=target.context_id,
        target_context_sha256=target_sha,
        lineage_refs=lineage,
    )


def _evaluate(
    family: PAGMemberFamilyResult,
    member: PAGAdmittedMember,
    graph: CausalGraphModel,
    graph_ref: CausalGraphModelRef,
    persisted_member: CausalGraphModel,
    member_ref: CausalGraphModelRef,
    source: ContextProfile,
    target: ContextProfile,
    treatment: str = _TREATMENT,
    outcome: str = _OUTCOME,
) -> TransportabilityCandidateMemberEvaluationV1:
    return evaluate_pag_member_candidate(
        family=family,
        member=member,
        source_graph=graph,
        source_context=source,
        target_context=target,
        selection_diagram=build_selection_diagram(source, target, persisted_member),
        member_graph_ref=member_ref,
        persisted_member_graph=persisted_member,
        inputs=_binding(graph, graph_ref, source, target, treatment, outcome),
        solver_mode="simplified",
        allow_degraded_transport=False,
        capability_contract=build_causal_capability_contract(),
    )


def test_real_partial_prefix_member_reaches_solver_and_refusals_remain_bound(
    tmp_path: Path,
) -> None:
    source, target = (
        ContextProfile(context_id="source", income_level=IncomeLevel.HIGH),
        ContextProfile(context_id="target", income_level=IncomeLevel.LOW),
    )
    cas_root = tmp_path / "cas"

    # Real CAS writer, fresh typed reader, and the actual pinned PAG generator.
    graph = _route_pag()
    graph_ref, reloaded_graph = _persist_and_reload(cas_root, graph)
    family = evaluate_pag_member_family(
        reloaded_graph,
        profile_id=_PROFILE_ID,
        profile_revision=_PROFILE_REVISION,
        budget=_budget(proposals=64, members=64, oracle=64),
    )
    assert family.status is PAGMemberFamilyStatus.BUDGET_EXHAUSTED
    assert family.coverage is PAGMemberFamilyCoverage.NOT_ESTABLISHED
    assert family.counts.assignment_space_size == "4096"
    assert family.counts.proposals_attempted <= 64
    assert int(family.counts.unattempted_proposals) > 0
    assert family.counts.admitted == len(family.members) > 0
    assert family.backend_identity is not None
    assert family.backend_identity.backend_id == "causal-learn.FCI.fci+d_separation"
    assert family.backend_identity.backend_version == "0.1.4.4"
    assert family.proposals[-1].ordinal == len(family.proposals) - 1

    member = family.members[0]
    member_ref, persisted_member = _persist_and_reload(cas_root, member.graph)
    partial_evaluation = _evaluate(
        family,
        member,
        reloaded_graph,
        graph_ref,
        persisted_member,
        member_ref,
        source,
        target,
    )
    assert partial_evaluation.disposition == "completed"
    assert partial_evaluation.outcome is not None

    # A complete family remains admissible through this owner path.
    two_node = _two_node_pag()
    two_ref, two_reloaded = _persist_and_reload(cas_root, two_node)
    full_two_node = evaluate_pag_member_family(
        two_reloaded,
        profile_id=_PROFILE_ID,
        profile_revision=_PROFILE_REVISION,
        budget=_budget(proposals=4, members=4, oracle=4),
    )
    assert full_two_node.status is PAGMemberFamilyStatus.COMPLETED
    assert (
        full_two_node.coverage is PAGMemberFamilyCoverage.FINITE_ENDPOINT_ASSIGNMENT_SPACE_COMPLETE
    )
    complete_member = full_two_node.members[0]
    complete_member_ref, complete_member_graph = _persist_and_reload(
        cas_root, complete_member.graph
    )
    complete_evaluation = _evaluate(
        full_two_node,
        complete_member,
        two_reloaded,
        two_ref,
        complete_member_graph,
        complete_member_ref,
        source,
        target,
    )
    assert complete_evaluation.disposition == "completed"
    assert complete_evaluation.outcome is not None

    # An admitted prefix remains usable when a later proposal's membership
    # oracle is incomplete; that unvalidated proposal is never evaluated.
    prefix_two_node = evaluate_pag_member_family(
        two_reloaded,
        profile_id=_PROFILE_ID,
        profile_revision=_PROFILE_REVISION,
        budget=_budget(proposals=4, members=1, oracle=4),
    )
    assert prefix_two_node.status is PAGMemberFamilyStatus.VALIDATION_INCOMPLETE
    assert prefix_two_node.coverage is PAGMemberFamilyCoverage.NOT_ESTABLISHED
    assert prefix_two_node.members
    incomplete_rows = [
        row
        for row in prefix_two_node.proposals
        if row.disposition is PAGProposalDisposition.VALIDATION_INCOMPLETE
    ]
    assert len(incomplete_rows) == 1
    incomplete_row = incomplete_rows[0]
    assert incomplete_row.reason_code == prefix_two_node.reason_code
    valid_prefix_member = prefix_two_node.members[0]
    prefix_ref, prefix_graph = _persist_and_reload(cas_root, valid_prefix_member.graph)
    prefix_evaluation = _evaluate(
        prefix_two_node,
        valid_prefix_member,
        two_reloaded,
        two_ref,
        prefix_graph,
        prefix_ref,
        source,
        target,
    )
    assert prefix_evaluation.disposition == "completed"
    assert prefix_evaluation.outcome is not None

    unvalidated_member = next(
        candidate
        for candidate in full_two_node.members
        if candidate.proposal_ordinal == incomplete_row.ordinal
    )
    unvalidated_ref, unvalidated_graph = _persist_and_reload(cas_root, unvalidated_member.graph)
    with pytest.raises(TransportCandidateMemberBindingError) as exc:
        _evaluate(
            prefix_two_node,
            unvalidated_member,
            two_reloaded,
            two_ref,
            unvalidated_graph,
            unvalidated_ref,
            source,
            target,
        )
    assert exc.value.reason_code == "candidate_member_not_in_validated_family"

    # Keep source/member markers but swap in a member from another genuine family.
    with pytest.raises(TransportCandidateMemberBindingError) as exc:
        _evaluate(
            family,
            complete_member,
            reloaded_graph,
            graph_ref,
            complete_member_graph,
            complete_member_ref,
            source,
            target,
        )
    assert exc.value.reason_code == "candidate_member_not_in_validated_family"

    # Unknown and unsupported family identities are still refused.
    unknown = family.model_copy(update={"status": "future_status"})
    with pytest.raises(TransportCandidateMemberBindingError) as exc:
        _evaluate(
            unknown,
            member,
            reloaded_graph,
            graph_ref,
            persisted_member,
            member_ref,
            source,
            target,
        )
    assert exc.value.reason_code == "candidate_member_family_not_canonical"
    unsupported = evaluate_pag_member_family(
        reloaded_graph,
        profile_id="unregistered.partial.profile",
        profile_revision=_PROFILE_REVISION,
        budget=_budget(proposals=64, members=64, oracle=64),
    )
    assert unsupported.status is PAGMemberFamilyStatus.UNSUPPORTED
    with pytest.raises(TransportCandidateMemberBindingError) as exc:
        _evaluate(
            unsupported,
            member,
            reloaded_graph,
            graph_ref,
            persisted_member,
            member_ref,
            source,
            target,
        )
    assert exc.value.reason_code == "candidate_member_family_not_complete"

    # An exhausted zero-admission family has no member or solver denominator.
    zero_graph = _zero_member_pag()
    zero_ref, zero_reloaded = _persist_and_reload(cas_root, zero_graph)
    zero_family = evaluate_pag_member_family(
        zero_reloaded,
        profile_id=_PROFILE_ID,
        profile_revision=_PROFILE_REVISION,
        budget=_budget(proposals=32, members=32, oracle=32),
    )
    assert zero_family.status is PAGMemberFamilyStatus.NOT_ESTABLISHED
    assert zero_family.coverage is PAGMemberFamilyCoverage.NOT_ESTABLISHED
    assert zero_family.counts.admitted == 0
    assert zero_family.members == ()
    with pytest.raises(TransportCandidateMemberBindingError) as exc:
        _evaluate(
            zero_family,
            member,
            zero_reloaded,
            zero_ref,
            persisted_member,
            member_ref,
            source,
            target,
            treatment="A",
            outcome="D",
        )
    assert exc.value.reason_code == "candidate_member_family_not_complete"
