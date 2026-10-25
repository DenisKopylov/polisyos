from __future__ import annotations

import importlib.util
import json
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


def test_family_result_rejects_json_disposition_counts_that_disagree_with_rows() -> None:
    module = _load_candidate()
    digest = "0" * 64
    payload = {
        "profile_id": "pag.no_selection.finite_member_sensitivity",
        "profile_revision": "1",
        "budget": {
            "max_proposals": 1,
            "max_members": 1,
            "max_oracle_operations": 1,
            "max_elapsed_seconds": 1,
            "max_output_bytes": 1024,
        },
        "status": "budget_exhausted",
        "coverage": "not_established",
        "assumptions": [],
        "elapsed_seconds": 0,
        "proposals": [
            {
                "ordinal": 0,
                "assignment_sha256": digest,
                "disposition": "invalid",
                "reason_code": "directed_cycle",
            }
        ],
        "members": [],
        "counts": {
            "assignment_space_size": "1",
            "proposals_attempted": 1,
            "unattempted_proposals": "0",
            "admitted": 0,
            "duplicate": 1,
            "invalid": 0,
            "unsupported": 0,
            "validation_incomplete": 0,
            "oracle_operations": 0,
        },
        "trace_bytes": 0,
        "trace_sha256": digest,
    }

    with pytest.raises(ValidationError, match="proposal disposition counts"):
        module.PAGMemberFamilyResult.model_validate_json(json.dumps(payload))


def test_family_result_reconciles_every_disposition_bucket_from_proposal_rows() -> None:
    from copy import deepcopy

    module = _load_candidate()
    digest = "0" * 64
    graph = {
        "graph_type": GraphType.DAG.value,
        "nodes": ["X"],
        "edges": [],
        "discovery_method": "fixture",
    }
    proposals = []
    members = []
    reported = {}
    dispositions = tuple(module.PAGProposalDisposition)
    for ordinal, disposition in enumerate(dispositions):
        member_sha = f"{ordinal + 1:064x}"
        row = {
            "ordinal": ordinal,
            "assignment_sha256": f"{ordinal + 11:064x}",
            "disposition": disposition.value,
        }
        if disposition is module.PAGProposalDisposition.ADMITTED:
            row["member_sha256"] = member_sha
            members.append(
                {
                    "proposal_ordinal": ordinal,
                    "assignment_sha256": row["assignment_sha256"],
                    "member_sha256": member_sha,
                    "graph": graph,
                }
            )
        elif disposition is module.PAGProposalDisposition.DUPLICATE:
            row["duplicate_of"] = 0
        else:
            row["reason_code"] = "fixture_disposition"
        proposals.append(row)
        reported[disposition.value] = 1

    payload = {
        "profile_id": "pag.no_selection.finite_member_sensitivity",
        "profile_revision": "1",
        "budget": {
            "max_proposals": len(dispositions),
            "max_members": len(dispositions),
            "max_oracle_operations": len(dispositions),
            "max_elapsed_seconds": 1,
            "max_output_bytes": 4096,
        },
        "status": "budget_exhausted",
        "coverage": "not_established",
        "assumptions": [],
        "elapsed_seconds": 0,
        "proposals": proposals,
        "members": members,
        "counts": {
            "assignment_space_size": str(len(dispositions)),
            "proposals_attempted": len(dispositions),
            "unattempted_proposals": "0",
            **reported,
            "oracle_operations": len(dispositions),
        },
        "trace_bytes": 0,
        "trace_sha256": digest,
    }

    for disposition in dispositions:
        other = next(candidate for candidate in dispositions if candidate is not disposition)
        corrupted = deepcopy(payload)
        corrupted["counts"][disposition.value] -= 1
        corrupted["counts"][other.value] += 1

        with pytest.raises(ValidationError, match="proposal disposition counts"):
            module.PAGMemberFamilyResult.model_validate_json(json.dumps(corrupted))


def test_family_result_rejects_duplicate_member_links_and_missing_admitted_member() -> None:
    module = _load_candidate()
    digest_a = "1" * 64
    digest_b = "2" * 64
    graph = {
        "graph_type": GraphType.DAG.value,
        "nodes": ["X"],
        "edges": [],
        "discovery_method": "fixture",
    }
    proposals = [
        {
            "ordinal": 0,
            "assignment_sha256": "3" * 64,
            "disposition": "admitted",
            "member_sha256": digest_a,
        },
        {
            "ordinal": 1,
            "assignment_sha256": "4" * 64,
            "disposition": "admitted",
            "member_sha256": digest_b,
        },
    ]
    base = {
        "profile_id": "pag.no_selection.finite_member_sensitivity",
        "profile_revision": "1",
        "budget": {
            "max_proposals": 2,
            "max_members": 2,
            "max_oracle_operations": 2,
            "max_elapsed_seconds": 1,
            "max_output_bytes": 4096,
        },
        "status": "budget_exhausted",
        "coverage": "not_established",
        "assumptions": [],
        "elapsed_seconds": 0,
        "proposals": proposals,
        "counts": {
            "assignment_space_size": "2",
            "proposals_attempted": 2,
            "unattempted_proposals": "0",
            "admitted": 2,
            "duplicate": 0,
            "invalid": 0,
            "unsupported": 0,
            "validation_incomplete": 0,
            "oracle_operations": 2,
        },
        "trace_bytes": 0,
        "trace_sha256": "0" * 64,
    }
    first_member = {
        "proposal_ordinal": 0,
        "assignment_sha256": proposals[0]["assignment_sha256"],
        "member_sha256": digest_a,
        "graph": graph,
    }
    duplicate_link_payload = {
        **base,
        "members": [first_member, dict(first_member)],
    }

    with pytest.raises(ValidationError, match="member rows"):
        module.PAGMemberFamilyResult.model_validate_json(json.dumps(duplicate_link_payload))

    missing_member_payload = {**base, "members": [first_member]}
    with pytest.raises(ValidationError, match="member"):
        module.PAGMemberFamilyResult.model_validate_json(json.dumps(missing_member_payload))

    second_member = {
        "proposal_ordinal": 1,
        "assignment_sha256": proposals[1]["assignment_sha256"],
        "member_sha256": digest_b,
        "graph": graph,
    }
    duplicate_proposal_payload = {
        **base,
        "proposals": [proposals[0], {**proposals[1], "ordinal": 0}],
        "members": [first_member, second_member],
    }
    with pytest.raises(ValidationError, match="unique ordinals"):
        module.PAGMemberFamilyResult.model_validate_json(json.dumps(duplicate_proposal_payload))


def test_family_result_rejects_member_link_with_foreign_assignment_digest() -> None:
    module = _load_candidate()
    digest = "1" * 64
    payload = {
        "profile_id": "pag.no_selection.finite_member_sensitivity",
        "profile_revision": "1",
        "budget": {
            "max_proposals": 1,
            "max_members": 1,
            "max_oracle_operations": 1,
            "max_elapsed_seconds": 1,
            "max_output_bytes": 2048,
        },
        "status": "budget_exhausted",
        "coverage": "not_established",
        "assumptions": [],
        "elapsed_seconds": 0,
        "proposals": [
            {
                "ordinal": 0,
                "assignment_sha256": digest,
                "disposition": "admitted",
                "member_sha256": "2" * 64,
            }
        ],
        "members": [
            {
                "proposal_ordinal": 0,
                "assignment_sha256": "3" * 64,
                "member_sha256": "2" * 64,
                "graph": {
                    "graph_type": GraphType.DAG.value,
                    "nodes": ["X"],
                    "edges": [],
                    "discovery_method": "fixture",
                },
            }
        ],
        "counts": {
            "assignment_space_size": "1",
            "proposals_attempted": 1,
            "unattempted_proposals": "0",
            "admitted": 1,
            "duplicate": 0,
            "invalid": 0,
            "unsupported": 0,
            "validation_incomplete": 0,
            "oracle_operations": 1,
        },
        "trace_bytes": 0,
        "trace_sha256": "0" * 64,
    }

    with pytest.raises(ValidationError, match="member rows"):
        module.PAGMemberFamilyResult.model_validate_json(json.dumps(payload))


def _estimate_work(
    graph: CausalGraphModel,
    *,
    module: ModuleType | None = None,
    dsep_limit: int = 64,
    expanded_limit: int = 524288,
    proposals: int = 64,
    members: int = 64,
    oracle: int = 64,
) -> BaseModel:
    candidate = module or _load_candidate()
    return candidate.estimate_pag_member_work(
        graph,
        profile_id="pag.no_selection.finite_member_sensitivity",
        profile_revision="1",
        budget=_budget(candidate, proposals=proposals, members=members, oracle=oracle),
        max_estimated_dsep_queries=dsep_limit,
        max_estimated_expanded_graph_element_query_units=expanded_limit,
    )


def test_method_owned_work_estimate_uses_graph_dimensions_and_bounded_queries() -> None:
    module = _load_candidate()
    two = _estimate_work(_two_node_circle(), module=module)
    three_graph = _pag(
        ["X", "M", "Y"],
        [
            _edge("X", "M", EdgeMark.CIRCLE, EdgeMark.CIRCLE),
            _edge("X", "Y", EdgeMark.CIRCLE, EdgeMark.CIRCLE),
            _edge("M", "Y", EdgeMark.CIRCLE, EdgeMark.CIRCLE),
        ],
    )
    three = _estimate_work(three_graph, module=module)
    three_limited = _estimate_work(three_graph, module=module, proposals=10, oracle=10)

    assert two.assignment_space.model_dump(mode="json") == {"base": 2, "exponent": 2}
    assert two.observed_node_count == 2
    assert two.observed_edge_count == 1
    assert two.circle_endpoint_count == 2
    assert two.bidirected_edge_upper_bound == 1
    assert two.expanded_node_upper_bound == 3
    assert two.expanded_edge_upper_bound == 2
    assert two.proposal_bound.model_dump(mode="json") == {
        "value": 4,
        "ceiling": 64,
        "exceeded_ceiling": False,
    }
    assert two.fci_membership_call_bound.value == 4
    assert two.d_separation_queries_per_fci_call_bound.value == 1
    assert two.d_separation_query_bound.value == 4
    assert two.expanded_graph_element_query_bound.value == 20

    assert three.assignment_space.exponent == 6
    assert three.observed_node_count == 3
    assert three.observed_edge_count == 3
    assert three.circle_endpoint_count == 6
    assert three.bidirected_edge_upper_bound == 3
    assert three.expanded_node_upper_bound == 6
    assert three.expanded_edge_upper_bound == 6
    assert three.fci_membership_call_bound.value == 64
    assert three.d_separation_queries_per_fci_call_bound.value == 6
    assert three.d_separation_query_bound.model_dump(mode="json") == {
        "value": 65,
        "ceiling": 64,
        "exceeded_ceiling": True,
    }
    assert three.expanded_graph_element_query_bound.value == 4608

    # Same graph dimension with fewer permitted full FCI calls must lower the bound.
    # This falsifies a dimension-only/hardcoded n=3 estimator.
    assert three_limited.fci_membership_call_bound.value == 10
    assert three_limited.d_separation_query_bound.value == 60
    assert three_limited.expanded_graph_element_query_bound.value == 720
    assert not three_limited.d_separation_query_bound.exceeded_ceiling


def test_work_estimate_keeps_assignment_power_factored_for_large_circle_spaces() -> None:
    module = _load_candidate()
    node_count = 1000
    graph = _pag(
        [f"X{index}" for index in range(node_count)],
        [
            _edge(f"X{index}", f"X{index + 1}", EdgeMark.CIRCLE, EdgeMark.CIRCLE)
            for index in range(node_count - 1)
        ],
    )

    estimate = _estimate_work(graph, module=module)

    assert estimate.assignment_space.model_dump(mode="json") == {
        "base": 2,
        "exponent": 2 * (node_count - 1),
    }
    assert estimate.proposal_bound.exceeded_ceiling
    assert estimate.proposal_bound.value == estimate.proposal_bound.ceiling + 1
    assert estimate.d_separation_query_bound.exceeded_ceiling


def test_work_estimator_refuses_unpinned_backend_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_candidate()
    original = module.importlib.metadata.version

    def wrong_causal_learn_version(name: str) -> str:
        if name == "causal-learn":
            return "unexpected"
        return original(name)

    monkeypatch.setattr(module.importlib.metadata, "version", wrong_causal_learn_version)

    with pytest.raises(module.PAGWorkEstimateError) as error:
        module.pag_member_work_algorithm_identity()

    assert error.value.code == "pinned_backend_identity_unavailable"


def test_full_zero_member_search_is_not_established_and_cannot_claim_empty_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_candidate()

    def reject_membership(
        *_args: object, **_kwargs: object
    ) -> tuple[tuple[str, ...], dict[tuple[str, str], tuple[EdgeMark, EdgeMark]]]:
        return ("X", "Y"), {}

    monkeypatch.setattr(module, "_oracle_pag_endpoint_map", reject_membership)
    result = module.evaluate_pag_member_family(
        _two_node_circle(),
        profile_id="pag.no_selection.finite_member_sensitivity",
        profile_revision="1",
        budget=_budget(module, proposals=4, members=4, oracle=4),
    )

    assert result.status.value == "not_established"
    assert result.coverage.value == "not_established"
    assert result.reason_code == "zero_admitted_members_not_established"
    assert result.counts.admitted == 0
    assert result.members == ()
    assert result.counts.proposals_attempted == 4
    assert result.counts.unattempted_proposals == "0"

    admitted = _evaluate(_two_node_circle()).model_dump(mode="python")
    admitted.update(
        status="not_established",
        coverage="not_established",
        reason_code="zero_admitted_members_not_established",
    )
    with pytest.raises(ValidationError, match="zero-admitted proposal family"):
        module.PAGMemberFamilyResult.model_validate(admitted)


@pytest.mark.parametrize(
    ("zero_members", "falsifier", "expected_error"),
    [
        (False, "shifted_ordinals", "exhausted_proposal_ordinals"),
        (False, "validation_incomplete", "exhausted_proposal_partition_cannot_include"),
        (True, "shifted_ordinals", "exhausted_proposal_ordinals"),
        (True, "validation_incomplete", "exhausted_proposal_partition_cannot_include"),
    ],
)
def test_exhausted_family_rejects_shifted_or_incomplete_terminal_partition(
    monkeypatch: pytest.MonkeyPatch,
    zero_members: bool,
    falsifier: str,
    expected_error: str,
) -> None:
    module = _load_candidate()
    if zero_members:

        def reject_membership(
            *_args: object, **_kwargs: object
        ) -> tuple[tuple[str, ...], dict[tuple[str, str], tuple[EdgeMark, EdgeMark]]]:
            return ("X", "Y"), {}

        monkeypatch.setattr(module, "_oracle_pag_endpoint_map", reject_membership)

    result = module.evaluate_pag_member_family(
        _two_node_circle(),
        profile_id="pag.no_selection.finite_member_sensitivity",
        profile_revision="1",
        budget=_budget(module, proposals=4, members=4, oracle=4),
    )
    assert result.status.value == ("not_established" if zero_members else "completed")

    payload = result.model_dump(mode="python")
    if falsifier == "shifted_ordinals":
        for proposal in payload["proposals"]:
            proposal["ordinal"] += 1
        for member in payload["members"]:
            member["proposal_ordinal"] += 1
    else:
        proposal_index = next(
            index
            for index, proposal in enumerate(payload["proposals"])
            if proposal["disposition"] != "admitted"
        )
        proposal = payload["proposals"][proposal_index]
        previous_disposition = proposal["disposition"]
        proposal.update(
            disposition="validation_incomplete",
            member_sha256=None,
            duplicate_of=None,
            reason_code="candidate_validation_incomplete",
        )
        payload["counts"][previous_disposition] -= 1
        payload["counts"]["validation_incomplete"] += 1

    with pytest.raises(ValidationError, match=expected_error):
        module.PAGMemberFamilyResult.model_validate(payload)


def test_completed_finite_coverage_requires_positive_member_admission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_candidate()

    def reject_membership(
        *_args: object, **_kwargs: object
    ) -> tuple[tuple[str, ...], dict[tuple[str, str], tuple[EdgeMark, EdgeMark]]]:
        return ("X", "Y"), {}

    monkeypatch.setattr(module, "_oracle_pag_endpoint_map", reject_membership)
    result = module.evaluate_pag_member_family(
        _two_node_circle(),
        profile_id="pag.no_selection.finite_member_sensitivity",
        profile_revision="1",
        budget=_budget(module, proposals=4, members=4, oracle=4),
    )
    payload = result.model_dump(mode="python")
    payload.update(
        status="completed",
        coverage="finite_endpoint_assignment_space_complete",
        reason_code=None,
    )

    with pytest.raises(ValidationError, match="complete finite coverage"):
        module.PAGMemberFamilyResult.model_validate(payload)
