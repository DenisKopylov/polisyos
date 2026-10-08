"""Finite-family completion and query discriminators through the actual engine."""

from __future__ import annotations

from fractions import Fraction
from itertools import combinations, permutations, product

import pytest

from polisyos.foundry.methods.catalog.causal._id_contracts import IdentificationStatus
from polisyos.foundry.methods.catalog.causal._partial_graph_queries import _consistent_extensions
from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.estimand import DistributionRef, EstimandAST, ProductNode, SumNode


def _graph(nodes, edges, **kwargs):
    return CausalGraphModel(graph_type=GraphType.CPDAG, nodes=nodes, edges=edges, **kwargs)


def _undirected(src, dst):
    return CausalEdge(src=src, dst=dst, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.TAIL)


def _arcs(graph):
    return frozenset((edge.src, edge.dst) for edge in graph.edges)


def _evaluate_binary_functional(node, assignment, joint):
    """Exact finite-law sums from raw probabilities, independent of graph code."""
    if isinstance(node, DistributionRef):
        numerator = denominator = Fraction()
        for row, probability in joint:
            if all(row[name] == assignment[name] for name in node.conditioning):
                denominator += probability
                if all(row[name] == assignment[name] for name in node.variables):
                    numerator += probability
        return numerator / denominator
    if isinstance(node, ProductNode):
        result = Fraction(1)
        for factor in node.factors:
            result *= _evaluate_binary_functional(factor, assignment, joint)
        return result
    if isinstance(node, SumNode):
        result = Fraction()
        for values in product((0, 1), repeat=len(node.summation_vars)):
            local = {**assignment, **dict(zip(node.summation_vars, values, strict=True))}
            result += _evaluate_binary_functional(node.operand, local, joint)
        return result
    raise AssertionError(f"unexpected maintained g-formula node: {type(node)}")


def _permutation_oracle(graph):
    """Use topological orders, rather than the implementation's bit assignments."""
    pairs = {frozenset((edge.src, edge.dst)) for edge in graph.edges}
    fixed = set()
    for edge in graph.edges:
        if (edge.mark_src, edge.mark_dst) == (EdgeMark.TAIL, EdgeMark.ARROW):
            fixed.add((edge.src, edge.dst))
        elif (edge.mark_src, edge.mark_dst) == (EdgeMark.ARROW, EdgeMark.TAIL):
            fixed.add((edge.dst, edge.src))

    def colliders(arcs):
        found = set()
        for a, b, c in permutations(graph.nodes, 3):
            if (a, b) in arcs and (c, b) in arcs and frozenset((a, c)) not in pairs:
                found.add((frozenset((a, c)), b))
        return found

    known = colliders(fixed)
    found = set()
    for order in permutations(graph.nodes):
        index = {node: i for i, node in enumerate(order)}
        arcs = frozenset(
            (a, b) if index[a] < index[b] else (b, a)
            for edge in graph.edges
            for a, b in [(edge.src, edge.dst)]
        )
        if fixed <= arcs and colliders(arcs) == known:
            found.add(arcs)
    return found


@pytest.mark.parametrize("n_nodes", [1, 2, 3, 4])
def test_entire_declared_partial_profile_matches_independent_order_oracle(n_nodes):
    nodes = [str(i) for i in range(n_nodes)]
    pairs = list(combinations(nodes, 2))
    # Complete structural denominator: absent, forward, reverse, undirected.
    for choices in product(range(4), repeat=len(pairs)):
        edges = []
        for (src, dst), choice in zip(pairs, choices, strict=True):
            if choice == 1:
                edges.append(CausalEdge(src=src, dst=dst))
            elif choice == 2:
                edges.append(CausalEdge(src=src, dst=dst, mark_src="arrow", mark_dst="tail"))
            elif choice == 3:
                edges.append(_undirected(src, dst))
        graph = _graph(nodes, edges)
        expected = _permutation_oracle(graph)
        if not expected:
            with pytest.raises(ValueError, match="no acyclic extension"):
                _consistent_extensions(graph)
        else:
            extensions, assignments = _consistent_extensions(graph)
            assert {_arcs(extension) for extension in extensions} == expected
            assert assignments == 2 ** choices.count(3)
            assert len(extensions) == len(expected)


def test_different_completion_answers_remain_conditional_not_storage_order_dag():
    graph = _graph(["X", "Y"], [_undirected("X", "Y")])
    result = CausalEngine().identify("X", "Y", graph, dataset_ref="observed-law")
    assert result.status is IdentificationStatus.PAG_AMBIGUOUS
    assert result.estimand_ast is None
    basis = result.metadata["partial_graph_query"]
    assert basis["coverage"] == "exhaustive_for_declared_profile"
    assert basis["admitted_completions"] == 2
    assert basis["disposition"] == "conditional"
    assert basis["authority_eligible"] is False
    assert graph.graph_type is GraphType.CPDAG and graph.edges[0].mark_dst is EdgeMark.TAIL
    # Same observational law: P(X=Y)=4/5, both marginals1/2.
    # X→Y uses P(Y=1|X=1)=4/5; Y→X intervention onX leaves P(Y=1)=1/2.
    forward = Fraction(2, 5) / Fraction(1, 2)
    reverse = Fraction(2, 5) + Fraction(1, 10)
    assert forward == Fraction(4, 5) and reverse == Fraction(1, 2) and forward != reverse
    candidates = {str(candidate["estimand"]["root"]) for candidate in basis["completions"]}
    assert len(candidates) == 2


def test_full_family_same_functional_positive_keeps_query_and_authority_scope():
    graph = _graph(["X", "Y", "Z"], [_undirected("Y", "Z")])
    result = CausalEngine().identify("X", "Y", graph, dataset_ref="observed-law")
    assert result.status is IdentificationStatus.IDENTIFIED
    assert result.estimand_ast is not None
    basis = result.metadata["partial_graph_query"]
    assert basis["admitted_completions"] == 2
    assert basis["disposition"] == "common_functional"
    assert basis["authority_eligible"] is False
    assert "source" in basis["limitation"].lower()


def test_two_agreeing_chain_samples_do_not_hide_third_completion():
    graph = _graph(["X", "Y", "Z"], [_undirected("X", "Y"), _undirected("Y", "Z")])
    result = CausalEngine().identify("X", "Z", graph, dataset_ref="observed-law")
    assert result.status is IdentificationStatus.PAG_AMBIGUOUS
    basis = result.metadata["partial_graph_query"]
    assert basis["admitted_completions"] == 3
    assert basis["orientation_assignments_checked"] == 4
    # Independent two-transition binary law: two reverse/fork answers1/2,
    # while forward chain is(4/5)^2+(1/5)^2=17/25, so sample agreement is false.
    assert Fraction(4, 5) ** 2 + Fraction(1, 5) ** 2 == Fraction(17, 25)
    assert Fraction(17, 25) != Fraction(1, 2)


def test_every_actual_completion_g_formula_matches_independent_binary_law():
    graph = _graph(["X", "Y", "Z"], [_undirected("X", "Y"), _undirected("Y", "Z")])
    result = CausalEngine().identify("X", "Z", graph, dataset_ref="binary-law")
    joint = []
    for x, y, z in product((0, 1), repeat=3):
        probability = Fraction(1, 2)
        probability *= Fraction(4, 5) if x == y else Fraction(1, 5)
        probability *= Fraction(4, 5) if y == z else Fraction(1, 5)
        joint.append(({"X": x, "Y": y, "Z": z}, probability))
    assert sum(probability for _, probability in joint) == 1
    answers = {}
    for candidate in result.metadata["partial_graph_query"]["completions"]:
        ast = EstimandAST.model_validate(candidate["estimand"])
        assert ast.treatment == "X" and ast.outcome == "Z"
        answer = _evaluate_binary_functional(ast.root, {"X": 1, "Z": 1}, joint)
        answers[frozenset(tuple(arc) for arc in candidate["arcs"])] = answer
    assert answers == {
        frozenset({("X", "Y"), ("Y", "Z")}): Fraction(17, 25),
        frozenset({("Y", "X"), ("Y", "Z")}): Fraction(1, 2),
        frozenset({("Y", "X"), ("Z", "Y")}): Fraction(1, 2),
    }


def test_no_effect_equal_answer_control_evaluates_all_conditional_factors():
    graph = _graph(["X", "Y", "Z"], [_undirected("Y", "Z")])
    result = CausalEngine().identify("X", "Y", graph, dataset_ref="binary-law")
    joint = []
    for x, y, z in product((0, 1), repeat=3):
        probability = Fraction(1, 4) * (Fraction(4, 5) if y == z else Fraction(1, 5))
        joint.append(({"X": x, "Y": y, "Z": z}, probability))
    for candidate in result.metadata["partial_graph_query"]["completions"]:
        ast = EstimandAST.model_validate(candidate["estimand"])
        assert _evaluate_binary_functional(ast.root, {"X": 1, "Y": 1}, joint) == Fraction(1, 2)
    assert _evaluate_binary_functional(
        result.estimand_ast.root, {"X": 1, "Y": 1}, joint
    ) == Fraction(1, 2)


@pytest.mark.parametrize(
    "graph",
    [
        _graph(["X", "Y", "A", "B", "C"], [_undirected("X", "Y")]),
        _graph(["X", "Y"], [CausalEdge(src="X", dst="Y", lag=1)]),
        _graph(["X", "Y"], [CausalEdge(src="X", dst="Y", mark_src="arrow")]),
        _graph(["X", "Y"], [_undirected("X", "Y")], metadata={"mgraph": None}),
        _graph(["X", "Y"], [CausalEdge(src="X", dst="Y"), CausalEdge(src="Y", dst="X")]),
    ],
)
def test_unsupported_family_is_typed_limited_without_fake_coverage(graph):
    result = CausalEngine().identify("X", "Y", graph)
    assert result.status is IdentificationStatus.PAG_AMBIGUOUS
    assert result.estimand_ast is None
    basis = result.metadata["partial_graph_query"]
    assert basis["coverage"] == "not_established"
    assert basis["disposition"] == "unsupported"
    assert basis["limitation"]


def test_conditional_transport_oracle_request_cannot_reuse_unconditional_completion_proof():
    graph = _graph(["X", "Y", "Z"], [_undirected("Y", "Z")])
    for kwargs in ({"conditions": frozenset({"Z"})}, {"oracle": "expert"}):
        result = CausalEngine().identify("X", "Y", graph, **kwargs)
        assert result.status is IdentificationStatus.PAG_AMBIGUOUS
        assert result.metadata["partial_graph_query"]["disposition"] == "unsupported"


def test_triangle_cycles_rejected_and_known_reverse_arrow_preserved():
    triangle = _graph(
        ["X", "Y", "Z"],
        [_undirected("X", "Y"), _undirected("Y", "Z"), _undirected("Z", "X")],
    )
    extensions, checked = _consistent_extensions(triangle)
    assert checked == 8 and len(extensions) == 6
    fixed = _graph(
        ["X", "Y", "Z"],
        [
            CausalEdge(src="Y", dst="X", mark_src="arrow", mark_dst="tail"),
            CausalEdge(src="Y", dst="Z"),
            _undirected("X", "Z"),
        ],
    )
    extensions, _ = _consistent_extensions(fixed)
    assert len(extensions) == 1
    assert _arcs(extensions[0]) == {("X", "Y"), ("Y", "Z"), ("X", "Z")}
