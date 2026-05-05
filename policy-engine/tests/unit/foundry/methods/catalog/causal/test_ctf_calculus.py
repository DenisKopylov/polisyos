"""Tests for the standalone counterfactual calculus module."""

from __future__ import annotations

from polisyos.foundry.methods.catalog.causal.amn import build_amn
from polisyos.foundry.methods.catalog.causal.ctf_calculus import (
    apply_ctf_rule3,
    rewrite_ctf_estimand,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.estimand import (
    CounterfactualNode,
    CrossWorldNode,
    DistributionRef,
    EstimandAST,
)


def _dag(
    directed: list[tuple[str, str]],
    *,
    extra_nodes: tuple[str, ...] = (),
) -> CausalGraphModel:
    nodes = sorted({node for edge in directed for node in edge} | set(extra_nodes))
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=nodes,
        edges=[
            CausalEdge(src=src, dst=dst, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)
            for src, dst in directed
        ],
    )


def _admg_with_latent_confounding() -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["U_ZY", "X", "Y", "Z"],
        edges=[
            CausalEdge(src="U_ZY", dst="Z", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="U_ZY", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        ],
        metadata={"shared_exogenous": ["U_ZY"]},
    )


def _ast(root: object, all_variables: tuple[str, ...]) -> EstimandAST:
    return EstimandAST(
        query_str="ctf-test",
        root=root,
        treatment="X",
        outcome="Y",
        all_variables=all_variables,
        identification_method="ctf_test",
    )


def test_ctf_r1_insertion_deletion() -> None:
    graph = _dag([("X", "Y")], extra_nodes=("W",))
    ast = _ast(
        CounterfactualNode(variable="Y", intervention={"X": 1}, conditioning=("W",)),
        ("W", "X", "Y"),
    )

    result_ast, steps = rewrite_ctf_estimand(ast, graph)

    assert any(step.rule_name == "CTF_R1" for step in steps)
    assert isinstance(result_ast.root, CounterfactualNode)
    assert result_ast.root.conditioning == ()


def test_ctf_r2_exchange() -> None:
    graph = _dag([("X", "Y"), ("Z", "Y")])
    ast = _ast(
        CounterfactualNode(variable="Y", intervention={"X": 1, "Z": 0}),
        ("X", "Y", "Z"),
    )

    result_ast, steps = rewrite_ctf_estimand(ast, graph)

    assert any(step.rule_name == "CTF_R2" for step in steps)
    assert isinstance(result_ast.root, CounterfactualNode)
    assert result_ast.root.intervention == {"X": 1}
    assert result_ast.root.conditioning == ("Z",)


def test_ctf_r3_deletion() -> None:
    graph = _admg_with_latent_confounding()
    node = CounterfactualNode(variable="Y", intervention={"X": 1, "Z": 0})
    amn, _ = build_amn(graph, {"w0": {"X": 1.0, "Z": 0.0}})

    rewritten, step = apply_ctf_rule3(node, amn, frozenset({"Z"}))

    assert step is not None
    assert step.rule_name == "CTF_R3"
    assert rewritten.intervention == {"X": 1}


def test_ctf_fixed_point_accumulates_multiple_rules() -> None:
    graph = _dag([("X", "Y"), ("Z", "Y")], extra_nodes=("W",))
    ast = _ast(
        CounterfactualNode(
            variable="Y",
            intervention={"X": 1, "Z": 0},
            conditioning=("W",),
        ),
        ("W", "X", "Y", "Z"),
    )

    result_ast, steps = rewrite_ctf_estimand(ast, graph)
    step_names = {step.rule_name for step in steps}

    assert "CTF_R1" in step_names
    assert "CTF_R2" in step_names
    assert isinstance(result_ast.root, CounterfactualNode)
    assert result_ast.root.intervention == {"X": 1}
    assert result_ast.root.conditioning == ("Z",)


def test_ctf_rewrite_reduces_to_l2() -> None:
    graph = _dag([], extra_nodes=("X", "Y"))
    ast = _ast(
        CounterfactualNode(variable="Y", intervention={"X": 1}),
        ("X", "Y"),
    )

    result_ast, steps = rewrite_ctf_estimand(ast, graph)

    assert any(step.rule_name == "CTF_R3" for step in steps)
    assert isinstance(result_ast.root, DistributionRef)
    assert result_ast.root.variables == ("Y",)
    assert result_ast.root.intervention_set == ()


def test_ctf_non_identifiable_through_rules() -> None:
    graph = _dag([("X", "Y")])
    ast = _ast(
        CounterfactualNode(variable="Y", intervention={"X": 1}),
        ("X", "Y"),
    )

    result_ast, steps = rewrite_ctf_estimand(ast, graph)

    assert steps == []
    assert isinstance(result_ast.root, CounterfactualNode)
    assert result_ast.root.intervention == {"X": 1}


def test_ctf_proof_steps_formal() -> None:
    graph = _dag([("X", "Y")], extra_nodes=("W",))
    ast = _ast(
        CounterfactualNode(variable="Y", intervention={"X": 1}, conditioning=("W",)),
        ("W", "X", "Y"),
    )

    _, steps = rewrite_ctf_estimand(ast, graph)
    ctf_steps = [step for step in steps if step.rule_name.startswith("CTF_")]

    assert ctf_steps
    assert all(step.rule_formal_name for step in ctf_steps)
    assert all(step.applicable_theorem for step in ctf_steps)


def test_ctf_cross_world_walks_all_worlds() -> None:
    graph = _dag([("X", "Y")], extra_nodes=("W",))
    ast = _ast(
        CrossWorldNode(
            worlds=(
                CounterfactualNode(
                    variable="Y", intervention={"X": 0}, world_index=0, conditioning=("W",)
                ),
                CounterfactualNode(
                    variable="Y", intervention={"X": 1}, world_index=1, conditioning=("W",)
                ),
            ),
            joint=True,
        ),
        ("W", "X", "Y"),
    )

    result_ast, steps = rewrite_ctf_estimand(ast, graph)

    assert any(step.rule_name == "CTF_R1" for step in steps)
    assert isinstance(result_ast.root, CrossWorldNode)
    assert all(world.conditioning == () for world in result_ast.root.worlds)


def test_ctf_cross_world_preserves_reduced_worlds() -> None:
    graph = _dag([("X", "Y")])
    ast = _ast(
        CrossWorldNode(
            worlds=(
                CounterfactualNode(variable="Y", intervention={"X": 1}, world_index=0),
                CounterfactualNode(variable="Y", intervention={}, world_index=1),
            ),
            joint=True,
        ),
        ("X", "Y"),
    )

    result_ast, steps = rewrite_ctf_estimand(ast, graph)

    assert steps == []
    assert isinstance(result_ast.root, CrossWorldNode)
    assert len(result_ast.root.worlds) == 2
    assert isinstance(result_ast.root.worlds[0], CounterfactualNode)
    assert isinstance(result_ast.root.worlds[1], CounterfactualNode)
    assert result_ast.root.worlds[1].intervention == {}
