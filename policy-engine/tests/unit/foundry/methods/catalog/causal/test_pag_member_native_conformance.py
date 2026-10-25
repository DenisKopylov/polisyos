"""Native PAG member conformance witness for G06.

Fixture basis: G528 doc path:
policy-engine/docs/research/e02-cloud-test-plan/integration/
architecture-decisions-2026-10-23/06-validated-partial-graph-profile.md @
528ec2576393e8aa9a0239a8e4172336ccf76a057.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    from types import ModuleType

import pytest

from polisyos.foundry.methods.catalog.causal.capabilities import (
    build_causal_capability_contract,
)
from polisyos.foundry.methods.catalog.causal.pag_member_family import (
    PAGMemberBudget,
    evaluate_pag_member_family,
)
from polisyos.foundry.methods.catalog.causal.transport_engine import (
    evaluate_pag_member_candidate,
)
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
    graph_content_sha256,
)
from polisyos.ir.analytics.context import ContextProfile, IncomeLevel
from polisyos.ir.analytics.estimand import (
    DistributionDomain,
    DistributionRef,
    EstimandAST,
    ProductNode,
    SumNode,
)
from polisyos.ir.analytics.transportability import (
    TransportabilityCandidateInputBindingV1,
    TransportabilityCandidateMemberEvaluationV1,
    TransportabilityCandidateModelPlanRelationV1,
    TransportabilityStatus,
    TransportMode,
    build_selection_diagram,
    transportability_candidate_query_sha256,
)
from polisyos.ir.artifacts import InputRef
from polisyos.ir.model_layer.canon import CanonSpec, to_canonical_bytes
from polisyos.ir.registry.refs import CausalGraphModelRef

_PROFILE = "sha256:" + "a" * 64
_CANON = CanonSpec(forbid_floats=False, sort_keys=True, exclude_none=False)
_PROFILE_ID = "pag.no_selection.finite_member_sensitivity"
_PROFILE_REVISION = "1"
_X = "consumption_response"
_M1 = "latent_mediator_left"
_M2 = "latent_mediator_right"
_Y = "corruption_level"


def _sha(value: object) -> str:
    return hashlib.sha256(to_canonical_bytes(value, _CANON)).hexdigest()


def _edge(
    left: str,
    right: str,
    left_mark: EdgeMark,
    right_mark: EdgeMark,
) -> CausalEdge:
    return CausalEdge(
        src=left,
        dst=right,
        mark_src=left_mark,
        mark_dst=right_mark,
    )


def _expected_positive_gformula() -> EstimandAST:
    root = SumNode(
        summation_vars=(_M1, _M2),
        operand=ProductNode(
            factors=(
                DistributionRef(
                    domain=DistributionDomain.SOURCE,
                    variables=(_M1,),
                    conditioning=(_X,),
                ),
                DistributionRef(
                    domain=DistributionDomain.SOURCE,
                    variables=(_M2,),
                    conditioning=(_X,),
                ),
                DistributionRef(
                    domain=DistributionDomain.SOURCE,
                    variables=(_Y,),
                    conditioning=(_M1, _M2),
                ),
            )
        ),
    )
    return EstimandAST(
        query_str="independently specified G06 mediator g-formula",
        root=root,
        treatment=_X,
        outcome=_Y,
        all_variables=(_X, _M1, _M2, _Y),
        identification_method="g_formula",
    )


def _normalized_ast_payload(ast: EstimandAST) -> dict[str, object]:
    return ast.normalize().model_dump(mode="json")


def _assert_positive_gformula(actual: EstimandAST) -> None:
    assert _normalized_ast_payload(actual) == _normalized_ast_payload(_expected_positive_gformula())


def _distribution_leaf_signature(
    ast: EstimandAST,
) -> set[tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...]]]:
    return {
        (ref.domain.value, ref.variables, ref.conditioning, ref.intervention_set)
        for ref in ast.normalize().collect_distribution_refs()
    }


def _latent_compelled_pag() -> CausalGraphModel:
    """Return the independently enumerated G528 latent-confounded PAG fixture.

    The exact expected skeleton and marks are the G528 latent case:
    X o-o M1, X o-o M2, M1 -> Y, M2 -> Y. Its independent finite oracle
    found five MAGs, with both mediator-to-outcome tails compelled.
    """
    return CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=[_X, _M1, _M2, _Y],
        edges=[
            _edge(_X, _M1, EdgeMark.CIRCLE, EdgeMark.CIRCLE),
            _edge(_X, _M2, EdgeMark.CIRCLE, EdgeMark.CIRCLE),
            _edge(_M1, _Y, EdgeMark.TAIL, EdgeMark.ARROW),
            _edge(_M2, _Y, EdgeMark.TAIL, EdgeMark.ARROW),
        ],
        discovery_method="FCI",
    )


def _r4_pag() -> CausalGraphModel:
    """Return the G528 discriminating-path fixture B-C-A-D."""
    return CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=["A", "B", "C", "D", "E"],
        edges=[
            _edge("A", "C", EdgeMark.CIRCLE, EdgeMark.ARROW),
            _edge("A", "D", EdgeMark.TAIL, EdgeMark.ARROW),
            _edge("A", "E", EdgeMark.CIRCLE, EdgeMark.CIRCLE),
            _edge("B", "C", EdgeMark.CIRCLE, EdgeMark.ARROW),
            _edge("C", "D", EdgeMark.TAIL, EdgeMark.ARROW),
        ],
        discovery_method="FCI",
    )


def _semantic_edges(
    graph: CausalGraphModel,
) -> dict[tuple[str, str], tuple[str, str]]:
    result = {}
    for edge in graph.edges:
        pair = tuple(sorted((edge.src, edge.dst)))
        marks = {edge.src: edge.mark_src.value, edge.dst: edge.mark_dst.value}
        result[pair] = (marks[pair[0]], marks[pair[1]])
    return result


def _budget(proposals: int, members: int, oracle: int) -> PAGMemberBudget:
    return PAGMemberBudget(
        max_proposals=proposals,
        max_members=members,
        max_oracle_operations=oracle,
        max_elapsed_seconds=20.0,
        max_output_bytes=262144,
    )


def _contexts() -> tuple[ContextProfile, ContextProfile]:
    return (
        ContextProfile(context_id="source", income_level=IncomeLevel.HIGH),
        ContextProfile(context_id="target", income_level=IncomeLevel.LOW),
    )


def _binding(
    graph: CausalGraphModel,
    source: ContextProfile,
    target: ContextProfile,
    treatment: str,
    outcome: str,
) -> TransportabilityCandidateInputBindingV1:
    graph_ref = CausalGraphModelRef(
        artifact_id="sha256:" + "1" * 64,
        manifest_profile_sha256=_PROFILE,
    )
    roles = (
        ("sha256:" + "2" * 64, "transportability_attempt_basis"),
        ("sha256:" + "3" * 64, "transportability_workflow_spec"),
        ("sha256:" + "4" * 64, "transportability_input_state"),
        (graph_ref.artifact_id, "selected_causal_graph"),
        ("sha256:" + "5" * 64, "causal_effect_report"),
    )
    refs = tuple(
        InputRef(
            artifact_id=artifact_id,
            role=role,
            manifest_profile_sha256=_PROFILE,
        )
        for artifact_id, role in roles
    )
    query_sha = transportability_candidate_query_sha256(treatment, outcome)
    base = {
        "graph_ref": graph_ref.model_dump(mode="json"),
        "graph_type": graph.graph_type.value,
        "graph_sha256": graph_content_sha256(graph),
        "query_treatment": treatment,
        "query_outcome": outcome,
        "query_sha256": query_sha,
        "source_context_id": source.context_id,
        "source_context_sha256": _sha(source.model_dump(mode="json")),
        "target_context_id": target.context_id,
        "target_context_sha256": _sha(target.model_dump(mode="json")),
        "profile_id": _PROFILE_ID,
        "profile_revision": _PROFILE_REVISION,
    }
    relation_id = "transportability.pag.no_selection.member_selection_diagrams"
    relation_revision = "1"
    relation_payload = {
        "relation_id": relation_id,
        "revision": relation_revision,
        **base,
    }
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
        source_context_sha256=base["source_context_sha256"],
        target_context_id=target.context_id,
        target_context_sha256=base["target_context_sha256"],
        lineage_refs=refs,
    )


def _evaluate_member(
    family: object,
    member: object,
    graph: CausalGraphModel,
    source: ContextProfile,
    target: ContextProfile,
    inputs: TransportabilityCandidateInputBindingV1,
) -> TransportabilityCandidateMemberEvaluationV1:
    return evaluate_pag_member_candidate(
        family=family,
        member=member,
        source_graph=graph,
        source_context=source,
        target_context=target,
        selection_diagram=build_selection_diagram(source, target, member.graph),
        member_graph_ref=CausalGraphModelRef(
            artifact_id="sha256:" + member.member_sha256,
            manifest_profile_sha256=_PROFILE,
        ),
        persisted_member_graph=member.graph,
        inputs=inputs,
        solver_mode="simplified",
        allow_degraded_transport=False,
        capability_contract=build_causal_capability_contract(),
    )


def _load_without_membership_equality_gate() -> ModuleType:
    from polisyos.foundry.methods.catalog.causal import pag_member_family as canonical

    source_path = Path(canonical.__file__ or "")
    source = source_path.read_text()
    check = "        if reconstructed != expected:" + chr(10)
    bypass = "        if False and reconstructed != expected:" + chr(10)
    assert source.count(check) == 1
    mutated = source.replace(check, bypass, 1)
    assert "pag_membership_mismatch" in mutated
    module_name = "polisyos.foundry.methods.catalog.causal._native_r4_membership_gate_removal_probe"
    spec = importlib.util.spec_from_file_location(module_name, source_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    exec(compile(mutated, str(source_path), "exec"), module.__dict__)  # noqa: S102 - in-memory property-removal probe
    return module


def test_native_latent_confounded_compelled_pag_routes_members_through_solver() -> None:
    graph = _latent_compelled_pag()
    family = evaluate_pag_member_family(
        graph,
        profile_id=_PROFILE_ID,
        profile_revision=_PROFILE_REVISION,
        budget=_budget(proposals=16, members=8, oracle=16),
    )

    assert family.status.value == "completed"
    assert family.coverage.value == "finite_endpoint_assignment_space_complete"
    assert family.counts.assignment_space_size == "16"
    assert family.counts.proposals_attempted == 16
    assert family.counts.unattempted_proposals == "0"
    assert family.counts.admitted == 5
    assert family.counts.oracle_operations == 9
    assert family.backend_identity is not None
    assert family.backend_identity.backend_id == "causal-learn.FCI.fci+d_separation"
    assert family.backend_identity.backend_version == "0.1.4.4"
    assert family.backend_identity.fci_source_sha256 == (
        "8f0f14f9d31847efa30fa056a162f1f9d21d07595880c1ad2b099ec11e544ead"
    )
    assert family.backend_identity.cit_source_sha256 == (
        "0d3db11083985b7cb0edbaa44662307c28f27bc135053a65751cd52f451ddc8f"
    )

    expected_pag = {
        tuple(sorted((_X, _M1))): ("circle", "circle"),
        tuple(sorted((_X, _M2))): ("circle", "circle"),
        tuple(sorted((_M1, _Y))): ("arrow", "tail"),
        tuple(sorted((_M2, _Y))): ("arrow", "tail"),
    }
    assert _semantic_edges(graph) == expected_pag
    assert all(
        _semantic_edges(member.graph)[tuple(sorted((_M1, _Y)))] == ("arrow", "tail")
        and _semantic_edges(member.graph)[tuple(sorted((_M2, _Y)))] == ("arrow", "tail")
        for member in family.members
    )

    source, target = _contexts()
    inputs = _binding(graph, source, target, _X, _Y)
    rows = [
        _evaluate_member(family, member, graph, source, target, inputs) for member in family.members
    ]
    assert len(rows) == 5
    assert all(
        row.disposition == "completed"
        and row.outcome is not None
        and row.outcome.status is TransportabilityStatus.IDENTIFIED
        and row.outcome.transport_mode is TransportMode.TRANSPORT_FORMULA
        and row.outcome.transport_formula is not None
        and row.outcome.transport_formula.adjustment_type == "s_admissibility_source_law"
        and not row.outcome.transport_formula.target_quantities
        and not row.outcome.result.required_target_data
        for row in rows
    )

    # Independent DAG g-formula expectation for X->M1, X->M2, M1->Y, M2->Y:
    # P_s(M1|X) P_s(M2|X) P_s(Y|M1,M2), under only S_X->X.
    positive_member = next(
        member
        for member in family.members
        if _semantic_edges(member.graph)[tuple(sorted((_X, _M1)))] == ("tail", "arrow")
        and _semantic_edges(member.graph)[tuple(sorted((_X, _M2)))] == ("tail", "arrow")
    )
    row = _evaluate_member(family, positive_member, graph, source, target, inputs)
    assert row.outcome is not None
    ast = EstimandAST.model_validate(row.outcome.result.estimand_ast)
    _assert_positive_gformula(ast)
    refs = ast.collect_distribution_refs()
    assert refs
    assert all(ref.domain is DistributionDomain.SOURCE for ref in refs)
    assert {(ref.variables, ref.conditioning) for ref in refs} == {
        ((_M1,), (_X,)),
        ((_M2,), (_X,)),
        ((_Y,), tuple(sorted((_M1, _M2)))),
    }
    assert len({item.outcome.transport_formula.formula_str for item in rows}) >= 2

    expected_payload = _normalized_ast_payload(_expected_positive_gformula())
    constant_index = next(
        index
        for index, (member, candidate_row) in enumerate(zip(family.members, rows, strict=True))
        if member.member_sha256 != positive_member.member_sha256
        and candidate_row.outcome is not None
        and _normalized_ast_payload(
            EstimandAST.model_validate(candidate_row.outcome.result.estimand_ast)
        )
        != expected_payload
    )
    constant_row = rows[constant_index]
    assert constant_row.outcome is not None
    with patch.object(
        sys.modules[__name__],
        "evaluate_pag_member_candidate",
        return_value=constant_row,
    ):
        constant_replacement_rows = [
            _evaluate_member(family, member, graph, source, target, inputs)
            for member in family.members
        ]
    assert all(replacement is constant_row for replacement in constant_replacement_rows)
    # The same independent formula assertion must reject a constant solver output.
    with pytest.raises(AssertionError):
        _assert_positive_gformula(
            EstimandAST.model_validate(
                constant_replacement_rows[
                    family.members.index(positive_member)
                ].outcome.result.estimand_ast
            )
        )

    # Independent negative transport expectation: institutional_quality changes Y's
    # mechanism directly, so source-only evidence cannot identify the target outcome law.
    shifted_source = ContextProfile(context_id="source-outcome-shift", institutional_quality=0.9)
    shifted_target = ContextProfile(context_id="target-outcome-shift", institutional_quality=0.1)
    shifted_inputs = _binding(graph, shifted_source, shifted_target, _X, _Y)
    shifted_diagram = build_selection_diagram(
        shifted_source, shifted_target, family.members[0].graph
    )
    assert {node.target_variable for node in shifted_diagram.s_nodes} == {_Y}
    negative_rows = [
        _evaluate_member(family, member, graph, shifted_source, shifted_target, shifted_inputs)
        for member in family.members
    ]
    assert all(
        row.disposition == "completed"
        and row.outcome is not None
        and row.outcome.status is TransportabilityStatus.UNSUPPORTED
        and row.outcome.transport_formula is None
        and not row.outcome.result.required_target_data
        for row in negative_rows
    )


def test_full_gformula_comparator_rejects_same_leaves_without_sum() -> None:
    expected = _expected_positive_gformula().normalize()
    assert isinstance(expected.root, SumNode)
    assert isinstance(expected.root.operand, ProductNode)
    wrong_composition = expected.model_copy(update={"root": expected.root.operand}).normalize()

    assert _distribution_leaf_signature(wrong_composition) == (
        _distribution_leaf_signature(expected)
    )
    with pytest.raises(AssertionError):
        _assert_positive_gformula(wrong_composition)


def test_native_r4_discriminating_path_rejects_weakened_a_tail() -> None:
    graph = _r4_pag()
    original = evaluate_pag_member_family(
        graph,
        profile_id=_PROFILE_ID,
        profile_revision=_PROFILE_REVISION,
        budget=_budget(proposals=16, members=16, oracle=16),
    )

    assert original.status.value == "completed"
    assert original.coverage.value == "finite_endpoint_assignment_space_complete"
    assert original.counts.admitted == 8
    assert original.counts.proposals_attempted == 16
    assert all(
        _semantic_edges(member.graph)[("A", "D")] == ("tail", "arrow")
        and _semantic_edges(member.graph)[("C", "D")] == ("tail", "arrow")
        for member in original.members
    )

    # G528's independently checked discriminating path B-C-A-D compels A->D.
    # Weaken only the A endpoint to a circle while preserving the edge and D arrowhead.
    weakened = graph.model_copy(
        update={
            "edges": [
                edge.model_copy(update={"mark_src": EdgeMark.CIRCLE})
                if (edge.src, edge.dst) == ("A", "D")
                else edge
                for edge in graph.edges
            ]
        }
    )
    falsified = evaluate_pag_member_family(
        weakened,
        profile_id=_PROFILE_ID,
        profile_revision=_PROFILE_REVISION,
        budget=_budget(proposals=32, members=16, oracle=32),
    )

    assert falsified.counts.assignment_space_size == "32"
    assert falsified.counts.proposals_attempted == 32
    assert falsified.counts.unattempted_proposals == "0"
    assert falsified.counts.admitted == 0
    assert falsified.members == ()
    assert falsified.proposals[0].reason_code == "pag_membership_mismatch"
    assert any(row.reason_code == "pag_membership_mismatch" for row in falsified.proposals)
    assert falsified.status.value == "not_established"
    assert falsified.coverage.value == "not_established"
    assert falsified.reason_code == "zero_admitted_members_not_established"
    assert falsified.counts.admitted == 0
    assert falsified.members == ()
    assert len(falsified.proposals) == 32
    assert falsified.counts.proposals_attempted == 32
    assert falsified.counts.unattempted_proposals == "0"
    assert falsified.counts.oracle_operations == 18

    # Remove only the equality predicate in-memory, retain the code marker and
    # real pinned FCI backend, and prove the same R4 falsifier escapes.
    bypass_module = _load_without_membership_equality_gate()
    bypassed = bypass_module.evaluate_pag_member_family(
        weakened,
        profile_id=_PROFILE_ID,
        profile_revision=_PROFILE_REVISION,
        budget=bypass_module.PAGMemberBudget(
            max_proposals=32,
            max_members=32,
            max_oracle_operations=32,
            max_elapsed_seconds=20.0,
            max_output_bytes=262144,
        ),
    )
    assert bypassed.counts.admitted > 0
    assert bypassed.members
    from polisyos.foundry.methods.catalog.causal import pag_member_family as canonical

    identity, fci, numpy, networkx = canonical._backend_identity()
    assert identity.backend_id == "causal-learn.FCI.fci+d_separation"
    _, reconstructed = canonical._oracle_pag_endpoint_map(
        bypassed.members[0].graph, fci, numpy, networkx
    )
    assert reconstructed != canonical._source_endpoint_map(weakened)
