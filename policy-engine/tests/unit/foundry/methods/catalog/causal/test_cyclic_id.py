"""Tests for the Phase-5 cyclic identification path."""

from __future__ import annotations

import numpy as np

from polisyos.foundry.methods.catalog.causal.admg_ops import (
    condense_graph,
    has_directed_cycle,
    tarjan_scc,
    topological_order,
)
from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
from polisyos.foundry.methods.catalog.causal.cyclic_id import (
    build_sigma_connection_graph,
    cyclic_id_algorithm,
    sigma_separation,
    well_posedness_check,
)
from polisyos.foundry.methods.catalog.causal.estimand_compiler import (
    CyclicExecutionBlock,
    EstimandShape,
    EstimationStrategy,
    classify_estimand,
    compile_estimand,
    recommend_estimator,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.estimand import make_backdoor_estimand
from polisyos.ir.analytics.negative_certificate import NegativeCertificate


def _cyclic_graph(
    directed: list[tuple[str, str]],
    *,
    metadata: dict | None = None,
) -> CausalGraphModel:
    nodes = sorted({n for edge in directed for n in edge})
    return CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=nodes,
        edges=[
            CausalEdge(src=src, dst=dst, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)
            for src, dst in directed
        ],
        metadata=metadata or {},
    )


def test_tarjan_scc_and_condense_graph_produce_dag() -> None:
    graph = _cyclic_graph([("A", "B"), ("B", "A"), ("B", "C")])
    sccs = tarjan_scc(graph)
    assert any(comp == frozenset({"A", "B"}) for comp in sccs)
    condensed = condense_graph(graph, sccs)
    assert not has_directed_cycle(condensed)
    assert topological_order(condensed)


def test_sigma_separation_matches_m_separation_outside_cycle() -> None:
    graph = _cyclic_graph(
        [("A", "B"), ("B", "A"), ("C", "M"), ("M", "D")],
    )
    sigma_graph = build_sigma_connection_graph(graph)
    assert sigma_separation(sigma_graph, frozenset({"C"}), frozenset({"D"}), frozenset({"M"}))


def test_sigma_separation_inside_scc_is_false() -> None:
    graph = _cyclic_graph([("A", "B"), ("B", "A"), ("C", "D")])
    sigma_graph = build_sigma_connection_graph(graph)
    assert not sigma_separation(sigma_graph, frozenset({"A"}), frozenset({"B"}), frozenset())


def test_well_posedness_exact_linear() -> None:
    graph = _cyclic_graph([("A", "B"), ("B", "A")])
    result = well_posedness_check(
        graph,
        {"linear_system_matrix": np.array([[0.2, 0.1], [0.1, 0.2]])},
    )
    assert result.well_posed is True
    assert result.method == "exact_linear"
    assert result.confidence == "exact"


def test_well_posedness_detects_multiple_fixed_points() -> None:
    graph = _cyclic_graph([("A", "B"), ("B", "A")])

    def update_fn(x: float | np.ndarray) -> float:
        value = float(np.asarray(x).reshape(-1)[0])
        return float(np.tanh(2.0 * value))

    result = well_posedness_check(graph, {"update_fn": update_fn})
    assert result.well_posed is False
    assert result.method in {"numerical_sampling", "lipschitz_heuristic"}
    assert result.confidence == "approximate"


def test_cyclic_algorithm_identifies_well_posed_feedback_loop() -> None:
    graph = _cyclic_graph(
        [("X", "A"), ("A", "B"), ("B", "A"), ("Y", "B")],
        metadata={
            "well_posedness_spec": {"linear_system_matrix": np.array([[0.1, 0.1], [0.1, 0.1]])}
        },
    )
    result = cyclic_id_algorithm(frozenset({"X"}), frozenset({"Y"}), graph)
    assert result.status.name == "IDENTIFIED"
    assert result.algorithm_version == "cyclic_id_scoped_v1"
    assert result.estimand_ast is not None
    assert "cyclic_id" in result.estimand_ast.identification_method
    dynamic_semantics = result.metadata.get("dynamic_semantics")
    assert isinstance(dynamic_semantics, dict)
    assert dynamic_semantics["semantics_family"] == "ioSCM"
    assert dynamic_semantics["reduction_status"] == "validated_reduction"
    assert dynamic_semantics["markov_criterion_certificate"]["graphical_oracle"] == "sigma"


def test_engine_routes_supported_cycle_to_validated_dynamic_reduction() -> None:
    graph = _cyclic_graph(
        [("X", "A"), ("A", "B"), ("B", "A"), ("Y", "B")],
        metadata={
            "well_posedness_spec": {"linear_system_matrix": np.array([[0.1, 0.1], [0.1, 0.1]])}
        },
    )
    engine = CausalEngine(registry=None, knowledge_base=None)
    result = engine.identify("X", "Y", graph)
    assert not isinstance(result, NegativeCertificate)
    assert result.status.name == "IDENTIFIED"
    assert result.algorithm_version == "dynamic_acyclic_reduction_v1"

    eg = engine.compile(result)
    assert not any(isinstance(node, CyclicExecutionBlock) for node in eg.nodes)


def test_cyclic_algorithm_returns_oracle_needed_when_validated_reduction_is_unavailable() -> None:
    graph = _cyclic_graph(
        [("A", "B"), ("B", "A")],
        metadata={
            "well_posedness_spec": {
                "update_fn": lambda x: 0.2 * float(np.asarray(x).reshape(-1)[0]),
                "lipschitz_constant": 0.2,
            }
        },
    )

    result = cyclic_id_algorithm(frozenset({"A"}), frozenset({"B"}), graph)

    assert result.status.name == "ORACLE_NEEDED"
    assert result.estimand_ast is None
    assert result.algorithm_version == "cyclic_id_scoped_v1"
    assert result.metadata["dynamic_semantics"]["reduction_status"] == "blocked"
    assert result.metadata["frontier_sketch"]["stage_id"] == "4.4"
    assert (
        result.metadata["frontier_sketch"]["typed_integration_target"]
        == "ProofBundle.dynamic_semantics"
    )


def test_compiler_classifies_cyclic_marker() -> None:
    ast = make_backdoor_estimand(
        treatment="A",
        outcome="B",
        adjustment_set=("C",),
        dataset_ref="ds1",
    ).model_copy(update={"identification_method": "cyclic_id|scc=A,B"})
    assert classify_estimand(ast) is EstimandShape.CYCLIC
    rec = recommend_estimator(ast, n_obs=250)
    assert rec.strategy is EstimationStrategy.FIXED_POINT_SOLVER
    _, eg = compile_estimand(ast, run_id="cyclic-test", n_obs=250)
    assert any(isinstance(node, CyclicExecutionBlock) for node in eg.nodes)


def test_cyclic_algorithm_returns_negative_certificate_when_not_well_posed() -> None:
    graph = _cyclic_graph(
        [("A", "B"), ("B", "A")],
        metadata={
            "well_posedness_spec": {
                "update_fn": lambda x: float(np.tanh(2.0 * float(np.asarray(x).reshape(-1)[0])))
            }
        },
    )
    engine = CausalEngine(registry=None, knowledge_base=None)
    result = engine.identify("A", "B", graph)
    assert isinstance(result, NegativeCertificate)
    assert result.blocking_type.value == "semantics_not_well_defined"
    assert "dynamic_semantics" in result.quantitative_diagnostics
    assert result.quantitative_diagnostics["dynamic_semantics"]["reduction_status"] == "blocked"
