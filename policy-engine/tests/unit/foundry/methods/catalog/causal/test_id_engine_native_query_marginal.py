"""Actual finite observed-DAG query AST against independent joint-table arithmetic."""

from fractions import Fraction
from itertools import product

import pytest

from polisyos.foundry.methods.catalog.causal.id_engine import id_algorithm, idc_algorithm
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.estimand import DistributionRef, ProductNode, RatioNode, SumNode


def _evaluate(node, assignment, joint):
    if isinstance(node, DistributionRef):
        rows = [
            (row, p) for row, p in joint if all(row[v] == assignment[v] for v in node.conditioning)
        ]
        return sum(
            (p for row, p in rows if all(row[v] == assignment[v] for v in node.variables)),
            Fraction(),
        ) / sum((p for _, p in rows), Fraction())
    if isinstance(node, RatioNode):
        return _evaluate(node.numerator, assignment, joint) / _evaluate(
            node.denominator, assignment, joint
        )
    if isinstance(node, ProductNode):
        answer = Fraction(1)
        for factor in node.factors:
            answer *= _evaluate(factor, assignment, joint)
        return answer
    if isinstance(node, SumNode):
        return sum(
            (
                _evaluate(
                    node.operand,
                    {**assignment, **dict(zip(node.summation_vars, values, strict=True))},
                    joint,
                )
                for values in product((0, 1), repeat=len(node.summation_vars))
            ),
            Fraction(),
        )
    raise AssertionError(type(node))


@pytest.mark.parametrize(
    "z_one,expected", [(Fraction(3, 4), Fraction(7, 10)), (Fraction(1, 4), Fraction(3, 10))]
)
def test_isolated_treatment_keeps_original_query_and_marginalizes_outcome_parent(z_one, expected):
    graph = CausalGraphModel(
        graph_type=GraphType.DAG, nodes=["X", "Z", "Y"], edges=[CausalEdge(src="Z", dst="Y")]
    )
    result = id_algorithm(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        graph=graph,
        dataset_ref="finite-joint",
    )
    ast = result.estimand_ast
    assert ast is not None and ast.treatment == "X" and ast.query_str == "P(Y|do(X))"
    assert set(ast.all_variables) == set(graph.nodes)
    joint = []
    for x, z, y in product((0, 1), repeat=3):
        py = Fraction(9, 10) if z else Fraction(1, 10)
        p = Fraction(1, 2) * (z_one if z else 1 - z_one) * (py if y else 1 - py)
        joint.append(({"X": x, "Z": z, "Y": y}, p))
    assert sum(p for _, p in joint) == 1 and all(p > 0 for _, p in joint)
    assert sum(p for row, p in joint if row["Y"] == 1) == expected
    answers = [_evaluate(ast.root, {"X": x, "Y": 1}, joint) for x in (0, 1)]
    assert answers == [expected, expected]
    assert answers[1] - answers[0] == 0


def test_actual_idc_ratio_matches_independent_interventional_conditional_table():
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["Z", "X", "Y"],
        edges=[
            CausalEdge(src="Z", dst="X"),
            CausalEdge(src="Z", dst="Y"),
            CausalEdge(src="X", dst="Y"),
        ],
    )
    joint = []
    for z, x, y in product((0, 1), repeat=3):
        pz = Fraction(1, 3) if z else Fraction(2, 3)
        px_one = Fraction(4, 5) if z else Fraction(1, 5)
        py_one = Fraction(1 + 2 * x + 3 * z, 8)
        joint.append(
            (
                {"Z": z, "X": x, "Y": y},
                pz * (px_one if x else 1 - px_one) * (py_one if y else 1 - py_one),
            )
        )
    result = idc_algorithm(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        conditions=frozenset({"Z"}),
        graph=graph,
    )
    assert result.estimand_ast is not None and result.estimand_ast.treatment == "X"
    # Independent DGP intervention removes only P(X|Z); conditional denominator
    # sums Y in P(Z)P(Y|X,Z), rather than consulting the emitted AST.
    for x, z in product((0, 1), repeat=2):
        pz = Fraction(1, 3) if z else Fraction(2, 3)
        interventional_y = [
            pz * (Fraction(1 + 2 * x + 3 * z, 8) if y else 1 - Fraction(1 + 2 * x + 3 * z, 8))
            for y in (0, 1)
        ]
        expected = interventional_y[1] / sum(interventional_y)
        assert expected == Fraction(1 + 2 * x + 3 * z, 8)
        assert _evaluate(result.estimand_ast.root, {"X": x, "Z": z, "Y": 1}, joint) == expected
