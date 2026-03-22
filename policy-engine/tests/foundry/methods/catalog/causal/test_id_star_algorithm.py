from __future__ import annotations

import numpy as np

from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
from polisyos.foundry.methods.catalog.causal.id_engine import (
    CtfQuery,
    IdentificationStatus,
    id_star_algorithm,
    idc_star_algorithm,
)
from polisyos.foundry.methods.catalog.causal.estimand_compiler import compile_estimand
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.estimand import CrossWorldNode, NestedCounterfactualNode, RatioNode


def _edge(src: str, dst: str, *, bidirected: bool = False) -> CausalEdge:
    if bidirected:
        return CausalEdge(src=src, dst=dst, mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW)
    return CausalEdge(src=src, dst=dst, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)


def _graph(nodes: list[str], edges: list[CausalEdge]) -> CausalGraphModel:
    return CausalGraphModel(graph_type=GraphType.ADMG, nodes=nodes, edges=edges)


def test_id_star_simple_backdoor_reduces_to_id() -> None:
    graph = _graph(
        ["X", "Y", "Z"],
        [_edge("Z", "X"), _edge("Z", "Y"), _edge("X", "Y")],
    )
    query = CtfQuery(outcome="Y", intervention=(("X", 1.0),), conditioning=("Z",), kind="single_world")
    result = id_star_algorithm(query, graph)
    assert result.status is IdentificationStatus.IDENTIFIED
    assert any(step.rule_name == "ID_STAR_STEP3" for step in result.proof_steps)


def test_id_star_bow_arc_non_identifiable() -> None:
    graph = _graph(
        ["X", "Y"],
        [_edge("X", "Y"), _edge("X", "Y", bidirected=True)],
    )
    query = CtfQuery(outcome="Y", intervention=(("X", 1.0),), kind="single_world")
    result = id_star_algorithm(query, graph)
    assert result.status is IdentificationStatus.HEDGE_FOUND
    assert result.hedge_certificate is not None


def test_id_star_ett_query() -> None:
    graph = _graph(
        ["X", "Y", "Z"],
        [_edge("Z", "X"), _edge("Z", "Y"), _edge("X", "Y")],
    )
    query = CtfQuery(
        outcome="Y",
        intervention=(("X", 1.0),),
        evidence=(("X", 1.0),),
        kind="ett",
    )
    result = id_star_algorithm(query, graph)
    assert result.status is IdentificationStatus.IDENTIFIED


def test_id_star_pn_query() -> None:
    graph = _graph(["X", "Y"], [_edge("X", "Y")])
    query = CtfQuery(
        outcome="Y",
        intervention=(("X", 1.0),),
        evidence=(("Y", 1.0),),
        kind="pn",
    )
    result = id_star_algorithm(query, graph)
    assert result.status is IdentificationStatus.IDENTIFIED
    assert result.estimand_ast is not None
    assert result.estimand_ast.query_str == "P(Y_{X=0} | X=1, Y=1)"


def test_id_star_pns_query_uses_cross_world_ast() -> None:
    graph = _graph(["X", "Y"], [_edge("X", "Y")])
    query = CtfQuery(
        outcome="Y",
        intervention=(("X", 1.0),),
        reference_intervention=(("X", 0.0),),
        kind="pns",
    )
    result = id_star_algorithm(query, graph)
    assert result.status is IdentificationStatus.IDENTIFIED
    assert result.estimand_ast is not None
    assert result.estimand_ast.query_str == "P(Y_{X=1}, Y_{X=0})"
    assert isinstance(result.estimand_ast.root, CrossWorldNode)
    assert len(result.estimand_ast.root.worlds) == 2
    interventions = [world.intervention for world in result.estimand_ast.root.worlds]
    assert {"X": 1.0} in interventions
    assert {"X": 0.0} in interventions


def test_id_star_frontdoor_ctf() -> None:
    graph = _graph(
        ["X", "M", "Y"],
        [_edge("X", "M"), _edge("M", "Y"), _edge("X", "Y", bidirected=True)],
    )
    query = CtfQuery(outcome="Y", intervention=(("X", 1.0),), mediators=("M",), kind="frontdoor")
    result = id_star_algorithm(query, graph)
    assert result.status is IdentificationStatus.IDENTIFIED


def test_id_star_napkin_graph() -> None:
    graph = _graph(
        ["X", "M", "Y", "U"],
        [_edge("X", "M"), _edge("M", "Y"), _edge("U", "X"), _edge("U", "Y")],
    )
    query = CtfQuery(outcome="Y", intervention=(("X", 1.0),), mediators=("M",), kind="napkin")
    result = id_star_algorithm(query, graph)
    assert result.status is IdentificationStatus.IDENTIFIED


def test_id_star_proof_steps_complete() -> None:
    graph = _graph(["X", "Y"], [_edge("X", "Y")])
    query = CtfQuery(outcome="Y", intervention=(("X", 1.0),), kind="proof")
    result = id_star_algorithm(query, graph)
    rule_names = {step.rule_name for step in result.proof_steps}
    assert {"ID_STAR_STEP1", "ID_STAR_STEP2", "ID_STAR_STEP3", "ID_STAR_STEP5"} <= rule_names


def test_id_star_nested_ctf() -> None:
    graph = _graph(["X", "Y"], [_edge("X", "Y")])
    query = CtfQuery(outcome="Y", intervention=(("X", 1.0),), kind="nested")
    result = id_star_algorithm(query, graph)
    assert result.status is IdentificationStatus.IDENTIFIED
    assert result.estimand_ast is not None
    assert isinstance(result.estimand_ast.root, NestedCounterfactualNode)


def test_idc_star_ratio_of_two_calls() -> None:
    graph = _graph(["X", "Y", "Z"], [_edge("Z", "X"), _edge("Z", "Y"), _edge("X", "Y")])
    query = CtfQuery(
        outcome="Y",
        intervention=(("X", 1.0),),
        conditioning=("Z",),
        evidence=(("X", 1.0),),
        kind="ett",
    )
    result = idc_star_algorithm(query, graph)
    assert result.status is IdentificationStatus.IDENTIFIED
    assert result.estimand_ast is not None
    assert isinstance(result.estimand_ast.root, RatioNode)
    assert result.query_str == "P(Y_{X=1} | X=1, Z)"


def test_counterfactual_identification_compiles_to_counterfactual_executor() -> None:
    graph = _graph(["X", "Y"], [_edge("X", "Y")])
    engine = CausalEngine()
    query = CtfQuery(outcome="Y", intervention=(("X", 1.0),), kind="single_world")
    result = engine.identify("X", "Y", graph, counterfactual_query=query)
    assert not isinstance(result, dict)
    assert result.status is IdentificationStatus.IDENTIFIED
    _, executor_graph = compile_estimand(  # type: ignore[arg-type]
        result.estimand_ast,
        run_id="test-id-star",
    )
    assert any("twin_network_query" in node.method_fqn for node in executor_graph.nodes)


def test_counterfactual_run_executes_twin_network_pipeline() -> None:
    graph = _graph(["X", "Y"], [_edge("X", "Y")])
    engine = CausalEngine(registry=MethodRegistry.get_instance())
    rng = np.random.default_rng(7)
    x = rng.binomial(1, 0.5, 300).astype(float)
    y = 0.5 + 1.75 * x + 0.1 * rng.standard_normal(300)
    query = CtfQuery(
        outcome="Y",
        intervention=(("X", 1.0),),
        evidence=(("X", 0.0),),
        kind="ett",
    )
    report, bundle, cert = engine.run(
        "X",
        "Y",
        graph,
        data_dict={"X": x, "Y": y},
        counterfactual_query=query,
        run_id="ctf-run",
    )
    assert cert is None
    assert report is not None
    assert getattr(report, "ite_mean", 0.0) > 0.5
    assert "X=1" in bundle.query_str
