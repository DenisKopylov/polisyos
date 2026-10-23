from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Never

import pytest
from pydantic import ValidationError

from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    EdgeSource,
    GraphType,
)

if TYPE_CHECKING:
    from types import ModuleType

    from pydantic import BaseModel


def _load_candidate() -> ModuleType:
    policy_root = Path(__file__).parents[6]
    source = policy_root / "src/polisyos/foundry/methods/catalog/causal/pag_member_family.py"
    spec = importlib.util.spec_from_file_location(
        "polisyos.foundry.methods.catalog.causal.pag_member_family", source
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _edge(left: str, right: str, left_mark: EdgeMark, right_mark: EdgeMark) -> CausalEdge:
    return CausalEdge(src=left, dst=right, mark_src=left_mark, mark_dst=right_mark)


def _pag(nodes: list[str], edges: list[CausalEdge], *, reverse: bool = False) -> CausalGraphModel:
    if reverse:
        edges = [
            CausalEdge(
                src=edge.dst,
                dst=edge.src,
                mark_src=edge.mark_dst,
                mark_dst=edge.mark_src,
                lag=edge.lag,
                sources=list(edge.sources),
                data_confidence=edge.data_confidence,
                literature_confidence=edge.literature_confidence,
                llm_confidence=edge.llm_confidence,
                expert_confidence=edge.expert_confidence,
                simulation_confidence=edge.simulation_confidence,
                combined_confidence=edge.combined_confidence,
                unsupported_by_evidence=edge.unsupported_by_evidence,
                evidence_refs=list(edge.evidence_refs),
                p_value=edge.p_value,
                metadata=dict(edge.metadata),
            )
            for edge in reversed(edges)
        ]
        nodes = list(reversed(nodes))
    return CausalGraphModel(
        graph_type=GraphType.PAG, nodes=nodes, edges=edges, discovery_method="FCI"
    )


def _budget(
    module: ModuleType,
    *,
    proposals: int = 64,
    members: int = 64,
    oracle: int = 64,
    seconds: float = 30,
    output: int = 262144,
) -> BaseModel:
    return module.PAGMemberBudget(
        max_proposals=proposals,
        max_members=members,
        max_oracle_operations=oracle,
        max_elapsed_seconds=seconds,
        max_output_bytes=output,
    )


def _evaluate(graph: CausalGraphModel, **budget_args: int) -> BaseModel:
    module = _load_candidate()
    return module.evaluate_pag_member_family(
        graph,
        profile_id="pag.no_selection.finite_member_sensitivity",
        profile_revision="1",
        budget=_budget(module, **budget_args),
    )


def _semantic_edges(graph: CausalGraphModel) -> dict[tuple[str, str], tuple[str, str]]:
    output = {}
    for edge in graph.edges:
        pair = tuple(sorted((edge.src, edge.dst)))
        marks = {edge.src: edge.mark_src.value, edge.dst: edge.mark_dst.value}
        output[pair] = (marks[pair[0]], marks[pair[1]])
    return output


def _two_node_circle() -> CausalGraphModel:
    return _pag(["X", "Y"], [_edge("X", "Y", EdgeMark.CIRCLE, EdgeMark.CIRCLE)])


def _latent_pag(*, reverse: bool = False) -> CausalGraphModel:
    return _pag(
        ["X", "Y", "W", "Z"],
        [
            _edge("X", "Y", EdgeMark.CIRCLE, EdgeMark.CIRCLE),
            _edge("X", "Z", EdgeMark.CIRCLE, EdgeMark.CIRCLE),
            _edge("Y", "W", EdgeMark.TAIL, EdgeMark.ARROW),
            _edge("Z", "W", EdgeMark.TAIL, EdgeMark.ARROW),
        ],
        reverse=reverse,
    )


def _r4_pag(*, reverse: bool = False) -> CausalGraphModel:
    return _pag(
        ["A", "B", "C", "D", "E"],
        [
            _edge("A", "C", EdgeMark.CIRCLE, EdgeMark.ARROW),
            _edge("A", "D", EdgeMark.TAIL, EdgeMark.ARROW),
            _edge("A", "E", EdgeMark.CIRCLE, EdgeMark.CIRCLE),
            _edge("B", "C", EdgeMark.CIRCLE, EdgeMark.ARROW),
            _edge("C", "D", EdgeMark.TAIL, EdgeMark.ARROW),
        ],
        reverse=reverse,
    )


def test_two_node_circle_pag_has_three_oracle_verified_members() -> None:
    result = _evaluate(_two_node_circle(), proposals=4, members=4, oracle=4)

    assert result.status == "completed"
    assert result.coverage == "finite_endpoint_assignment_space_complete"
    assert [proposal.disposition.value for proposal in result.proposals] == [
        "admitted",
        "unsupported",
        "admitted",
        "admitted",
    ]
    assert len(result.members) == 3
    assert len({member.member_sha256 for member in result.members}) == 3
    assert result.counts.assignment_space_size == "4"
    assert result.counts.unattempted_proposals == "0"
    assert result.counts.proposals_attempted == 4
    assert result.counts.oracle_operations == 3
    assert result.trace_bytes > 0
    assert all(
        member.graph.graph_type in {GraphType.DAG, GraphType.ADMG} for member in result.members
    )
    assert {next(iter(_semantic_edges(member.graph).values())) for member in result.members} == {
        ("tail", "arrow"),
        ("arrow", "tail"),
        ("arrow", "arrow"),
    }


def test_reversed_member_edge_preserves_nonorientation_evidence_fields() -> None:
    edge = CausalEdge(
        src="X",
        dst="Y",
        mark_src=EdgeMark.CIRCLE,
        mark_dst=EdgeMark.CIRCLE,
        sources=[EdgeSource.DATA],
        data_confidence=0.75,
        evidence_refs=["fixture:evidence"],
        metadata={"basis": "source-edge"},
    )
    graph = CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=["X", "Y"],
        edges=[edge],
        discovery_method="FCI",
    )

    result = _evaluate(graph)
    reverse = next(
        member.graph.edges[0]
        for member in result.members
        if _semantic_edges(member.graph)[("X", "Y")] == ("arrow", "tail")
    )

    assert (reverse.src, reverse.dst) == ("Y", "X")
    assert (reverse.mark_src, reverse.mark_dst) == (EdgeMark.TAIL, EdgeMark.ARROW)
    assert reverse.sources == [EdgeSource.DATA]
    assert reverse.data_confidence == 0.75
    assert reverse.evidence_refs == ["fixture:evidence"]
    assert reverse.metadata == {"basis": "source-edge"}


def test_nontrivial_latent_confounded_pag_has_five_exact_members() -> None:
    result = _evaluate(_latent_pag())

    assert result.status == "completed"
    assert result.counts.admitted == 5
    assert result.counts.proposals_attempted == 16
    assert result.counts.oracle_operations < result.counts.proposals_attempted
    assert all(
        member.graph.graph_type in {GraphType.DAG, GraphType.ADMG} for member in result.members
    )
    assert {tuple(sorted(_semantic_edges(member.graph).items())) for member in result.members}


def test_r4_discriminating_path_fixture_has_eight_members_and_keeps_compelled_marks() -> None:
    result = _evaluate(_r4_pag())

    assert result.status == "completed"
    assert result.counts.admitted == 8
    assert result.counts.proposals_attempted == 16
    for member in result.members:
        edges = _semantic_edges(member.graph)
        assert edges[("A", "D")] == ("tail", "arrow")
        assert edges[("C", "D")] == ("tail", "arrow")


def test_node_and_edge_permutation_preserve_r4_semantic_family() -> None:
    first = _evaluate(_r4_pag())
    permuted = _evaluate(_r4_pag(reverse=True))

    first_family = {_semantic_edges(member.graph).__repr__() for member in first.members}
    permuted_family = {_semantic_edges(member.graph).__repr__() for member in permuted.members}
    assert first_family == permuted_family
    assert {member.member_sha256 for member in first.members} == {
        member.member_sha256 for member in permuted.members
    }


def test_selected_pag_must_match_reconstructed_complete_pag_not_merely_admit_one_member() -> None:
    # The source DAG A->B, A->C, A->D, B->D, C->D has compelled A o-> D.
    # The deliberately weakened A o-o D input is not its complete observational PAG.
    weakened = _pag(
        ["A", "B", "C", "D"],
        [
            _edge("A", "B", EdgeMark.CIRCLE, EdgeMark.CIRCLE),
            _edge("A", "C", EdgeMark.CIRCLE, EdgeMark.CIRCLE),
            _edge("A", "D", EdgeMark.CIRCLE, EdgeMark.CIRCLE),
            _edge("B", "D", EdgeMark.CIRCLE, EdgeMark.ARROW),
            _edge("C", "D", EdgeMark.CIRCLE, EdgeMark.ARROW),
        ],
    )

    result = _evaluate(weakened, proposals=1, members=64, oracle=64)

    assert result.status == "budget_exhausted"
    assert result.coverage == "not_established"
    assert result.members == ()
    assert result.counts.admitted == 0
    assert result.counts.proposals_attempted == 1
    assert result.proposals[0].reason_code == "pag_membership_mismatch"
    assert all(row.disposition.value != "admitted" for row in result.proposals)


def test_directed_cycle_is_rejected_before_membership_oracle() -> None:
    graph = _pag(
        ["A", "B", "C"],
        [
            _edge("A", "B", EdgeMark.TAIL, EdgeMark.ARROW),
            _edge("B", "C", EdgeMark.TAIL, EdgeMark.ARROW),
            _edge("C", "A", EdgeMark.TAIL, EdgeMark.ARROW),
        ],
    )

    result = _evaluate(graph, proposals=1, members=64, oracle=64)

    assert result.counts.proposals_attempted == 1
    assert result.proposals[0].disposition.value == "invalid"
    assert result.proposals[0].reason_code == "directed_cycle"
    assert result.counts.oracle_operations == 0
    assert result.members == ()


def test_nonmaximal_inducing_path_is_rejected_even_when_ancestral() -> None:
    graph = _pag(
        ["X", "A", "B", "Y"],
        [
            _edge("X", "A", EdgeMark.ARROW, EdgeMark.ARROW),
            _edge("A", "B", EdgeMark.ARROW, EdgeMark.ARROW),
            _edge("B", "Y", EdgeMark.ARROW, EdgeMark.ARROW),
            _edge("A", "Y", EdgeMark.TAIL, EdgeMark.ARROW),
            _edge("B", "X", EdgeMark.TAIL, EdgeMark.ARROW),
        ],
    )

    result = _evaluate(graph, proposals=1, members=64, oracle=64)

    assert result.counts.proposals_attempted == 1
    assert result.proposals[0].ordinal == 0
    assert result.proposals[0].disposition.value == "invalid"
    assert result.proposals[0].reason_code == "nonmaximal_inducing_path"
    assert result.counts.oracle_operations == 0


def test_profile_refuses_cpdag_and_selection_encoded_source() -> None:
    module = _load_candidate()
    cpdag = CausalGraphModel(graph_type=GraphType.CPDAG, nodes=["X", "Y"], edges=[])
    tail_tail = _pag(["X", "Y"], [_edge("X", "Y", EdgeMark.TAIL, EdgeMark.TAIL)])

    refused_cpdag = module.evaluate_pag_member_family(
        cpdag,
        profile_id="pag.no_selection.finite_member_sensitivity",
        profile_revision="1",
        budget=_budget(module),
    )
    refused_selection = module.evaluate_pag_member_family(
        tail_tail,
        profile_id="pag.no_selection.finite_member_sensitivity",
        profile_revision="1",
        budget=_budget(module),
    )

    assert refused_cpdag.status == "unsupported"
    assert refused_cpdag.reason_code == "input_graph_type_unsupported"
    assert refused_selection.status == "unsupported"
    assert refused_selection.reason_code == "selection_encoded_tail_tail_unsupported"
    assert refused_cpdag.proposals == ()
    assert refused_selection.proposals == ()


def test_wrong_profile_is_typed_unsupported_not_silently_selected() -> None:
    module = _load_candidate()
    result = module.evaluate_pag_member_family(
        _two_node_circle(),
        profile_id="pag.some_other_profile",
        profile_revision="1",
        budget=_budget(module),
    )

    assert result.status == "unsupported"
    assert result.reason_code == "profile_not_registered"
    assert result.counts.proposals_attempted == 0
    assert result.coverage == "not_established"


def test_oracle_failure_is_validation_incomplete_not_a_negative_member_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_candidate()

    def fail_oracle(*_args: object, **_kwargs: object) -> Never:
        raise RuntimeError("fixture oracle failure")

    monkeypatch.setattr(module, "_oracle_pag_endpoint_map", fail_oracle)
    result = module.evaluate_pag_member_family(
        _two_node_circle(),
        profile_id="pag.no_selection.finite_member_sensitivity",
        profile_revision="1",
        budget=_budget(module, proposals=4, members=4, oracle=4),
    )

    assert result.status == "validation_incomplete"
    assert result.coverage == "not_established"
    assert result.counts.validation_incomplete == 1
    assert result.counts.oracle_operations == 1
    assert result.counts.unattempted_proposals == "3"
    assert result.proposals[-1].reason_code == "membership_oracle_failed"


def test_proposal_and_oracle_budgets_reconcile_without_claiming_empty_family() -> None:
    module = _load_candidate()
    graph = _two_node_circle()
    result = module.evaluate_pag_member_family(
        graph,
        profile_id="pag.no_selection.finite_member_sensitivity",
        profile_revision="1",
        budget=_budget(module, proposals=2, members=4, oracle=4),
    )
    zero = module.evaluate_pag_member_family(
        graph,
        profile_id="pag.no_selection.finite_member_sensitivity",
        profile_revision="1",
        budget=_budget(module, proposals=0, members=4, oracle=4),
    )

    assert result.status == zero.status == "budget_exhausted"
    assert result.coverage == zero.coverage == "not_established"
    assert result.counts.proposals_attempted == 2
    assert result.counts.unattempted_proposals == "2"
    assert zero.counts.proposals_attempted == 0
    assert zero.counts.unattempted_proposals == "4"
    assert zero.members == ()


def test_trace_byte_budget_stops_before_claiming_unretained_member() -> None:
    module = _load_candidate()
    result = module.evaluate_pag_member_family(
        _two_node_circle(),
        profile_id="pag.no_selection.finite_member_sensitivity",
        profile_revision="1",
        budget=_budget(module, proposals=4, members=4, oracle=4, output=1024),
    )

    assert result.status == "budget_exhausted"
    assert result.coverage == "not_established"
    assert result.reason_code == "output_budget_exhausted"
    assert result.proposals == ()
    assert result.members == ()
    assert result.counts.unattempted_proposals == "4"
    assert result.trace_bytes <= result.budget.max_output_bytes
    assert result.trace_sha256


@pytest.mark.parametrize(
    ("assignment_space_size", "unattempted_proposals"),
    [("4", "2"), ("4", "4")],
    ids=("universe-undercount", "universe-overcount"),
)
def test_counts_reject_assignment_space_that_does_not_reconcile(
    assignment_space_size: str, unattempted_proposals: str
) -> None:
    module = _load_candidate()

    with pytest.raises(ValidationError, match="assignment_space_size must equal"):
        module.PAGMemberCounts(
            assignment_space_size=assignment_space_size,
            proposals_attempted=1,
            unattempted_proposals=unattempted_proposals,
            admitted=1,
            duplicate=0,
            invalid=0,
            unsupported=0,
            validation_incomplete=0,
            oracle_operations=1,
        )


def test_counts_reconcile_arbitrarily_large_decimal_universe_without_int_conversion() -> None:
    module = _load_candidate()
    universe = "1" + "0" * 5000
    remaining = "9" * 5000

    counts = module.PAGMemberCounts(
        assignment_space_size=universe,
        proposals_attempted=1,
        unattempted_proposals=remaining,
        admitted=1,
        duplicate=0,
        invalid=0,
        unsupported=0,
        validation_incomplete=0,
        oracle_operations=1,
    )

    assert counts.assignment_space_size == universe
    assert counts.unattempted_proposals == remaining


@pytest.mark.parametrize(
    (
        "admitted",
        "invalid",
        "oracle_operations",
        "expected_message",
    ),
    [
        (0, 1, 2, "oracle operations cannot exceed attempted proposals"),
        (1, 0, 0, "admitted proposals cannot exceed oracle operations"),
    ],
    ids=("oracle-attempt-bound", "admitted-oracle-bound"),
)
def test_counts_reject_inconsistent_oracle_aggregates(
    admitted: int,
    invalid: int,
    oracle_operations: int,
    expected_message: str,
) -> None:
    module = _load_candidate()

    with pytest.raises(ValidationError, match=expected_message):
        module.PAGMemberCounts(
            assignment_space_size="4",
            proposals_attempted=1,
            unattempted_proposals="3",
            admitted=admitted,
            duplicate=0,
            invalid=invalid,
            unsupported=0,
            validation_incomplete=0,
            oracle_operations=oracle_operations,
        )
