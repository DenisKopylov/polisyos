from __future__ import annotations

from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
from polisyos.foundry.methods.catalog.causal.id_engine import (
    IdentificationResult,
    IdentificationStatus,
)
from polisyos.foundry.methods.catalog.causal.path_specific_identify import identify_path_specific
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.estimand import DistributionDomain
from polisyos.ir.analytics.interventions import (
    EdgeAssignment,
    EdgeIntervention,
    InterventionQuery,
    PathIntervention,
    QueryTarget,
    QueryTargetKind,
)
from polisyos.ir.analytics.negative_certificate import NegativeCertificate
from polisyos.ir.analytics.path_specific_identification import (
    PathSpecificDecisionMode,
    PathSpecificWitnessKind,
)


def _edge(src: str, dst: str) -> CausalEdge:
    return CausalEdge(src=src, dst=dst, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)


def _bidirected(src: str, dst: str) -> CausalEdge:
    return CausalEdge(src=src, dst=dst, mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW)


def _graph(
    nodes: list[str],
    edges: list[CausalEdge],
    *,
    graph_type: GraphType,
    metadata: dict | None = None,
) -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=graph_type,
        nodes=nodes,
        edges=edges,
        discovery_method="test_fixture",
        metadata=metadata or {},
    )


def test_identify_path_specific_exact_identified_for_simple_dag() -> None:
    graph = _graph(
        ["X", "M", "Y"],
        [_edge("X", "M"), _edge("M", "Y")],
        graph_type=GraphType.DAG,
    )

    report = identify_path_specific(
        graph=graph,
        intervention=PathIntervention(
            active_paths=(("X", "M", "Y"),),
            natural_value_vars=("M",),
        ),
        outcome="Y",
        query_str="distribution:Y <- path(active=X->M->Y)",
    )

    assert report.mode is PathSpecificDecisionMode.EXACT_IDENTIFIED
    assert report.compilation_plan is not None
    assert report.compilation_plan.compiled_estimand_ast is not None
    assert report.compilation_plan.intrinsic_width_bound >= 1
    assert report.required_distributions


def test_identify_path_specific_exact_identified_with_pre_treatment_conditioning() -> None:
    graph = _graph(
        ["Z", "X", "M", "Y"],
        [_edge("Z", "X"), _edge("Z", "Y"), _edge("X", "M"), _edge("M", "Y")],
        graph_type=GraphType.DAG,
    )

    report = identify_path_specific(
        graph=graph,
        intervention=PathIntervention(
            active_paths=(("X", "M", "Y"),),
            natural_value_vars=("M",),
        ),
        outcome="Y",
        query_str="distribution:Y | Z <- path(active=X->M->Y)",
        conditioning=("Z",),
    )

    assert report.mode is PathSpecificDecisionMode.EXACT_IDENTIFIED
    assert report.semantic_query.conditioning == ("Z",)
    assert report.compilation_plan is not None
    compiled = report.compilation_plan.compiled_estimand_ast
    assert compiled is not None
    assert compiled.root.node_type == "conditional_do"
    assert any("ConditionalInterventionNode" in step for step in report.proof_trace)


def test_identify_path_specific_blocks_post_treatment_conditioning() -> None:
    graph = _graph(
        ["X", "M", "Y"],
        [_edge("X", "M"), _edge("M", "Y")],
        graph_type=GraphType.DAG,
    )

    report = identify_path_specific(
        graph=graph,
        intervention=PathIntervention(
            active_paths=(("X", "M", "Y"),),
            natural_value_vars=("M",),
        ),
        outcome="Y",
        query_str="distribution:Y | M <- path(active=X->M->Y)",
        conditioning=("M",),
    )

    assert report.mode is PathSpecificDecisionMode.BLOCKED_WITH_WITNESS
    assert any(
        witness.kind is PathSpecificWitnessKind.UNSUPPORTED_CONDITIONING
        and witness.metadata.get("reason") == "post_treatment_conditioning"
        for witness in report.witnesses
    )


def test_identify_path_specific_detects_recanting_district_and_returns_bounds() -> None:
    graph = _graph(
        ["X", "M1", "M2", "Y"],
        [
            _edge("X", "M1"),
            _edge("X", "M2"),
            _edge("M1", "Y"),
            _edge("M2", "Y"),
            _bidirected("M1", "M2"),
        ],
        graph_type=GraphType.ADMG,
        metadata={"outcome_support": {"Y": (0.0, 1.0)}},
    )

    report = identify_path_specific(
        graph=graph,
        intervention=PathIntervention(
            active_paths=(("X", "M1", "Y"),),
            frozen_paths=(("X", "M2", "Y"),),
            natural_value_vars=("M1", "M2"),
        ),
        outcome="Y",
        query_str="distribution:Y <- path(active=X->M1->Y; frozen=X->M2->Y)",
    )

    assert report.mode is PathSpecificDecisionMode.BOUNDED
    assert report.bounds_bundle is not None
    assert any(
        witness.kind is PathSpecificWitnessKind.RECANTING_DISTRICT for witness in report.witnesses
    )


def test_identify_path_specific_width_budget_overflow_returns_bounded_mode() -> None:
    graph = _graph(
        ["X", "M1", "M2", "Y"],
        [
            _edge("X", "M1"),
            _edge("X", "M2"),
            _edge("M1", "Y"),
            _edge("M2", "Y"),
            _bidirected("M1", "M2"),
        ],
        graph_type=GraphType.ADMG,
        metadata={"outcome_support": {"Y": (0.0, 1.0)}},
    )

    report = identify_path_specific(
        graph=graph,
        intervention=PathIntervention(
            active_paths=(("X", "M1", "Y"), ("X", "M2", "Y")),
            natural_value_vars=("M1", "M2"),
        ),
        outcome="Y",
        query_str="distribution:Y <- path(active=X->M1->Y,X->M2->Y)",
        width_budget=1,
    )

    assert report.mode is PathSpecificDecisionMode.BOUNDED
    assert report.bounds_bundle is not None
    assert any(
        witness.kind is PathSpecificWitnessKind.WIDTH_BUDGET_EXCEEDED
        for witness in report.witnesses
    )


def test_identify_path_specific_exact_with_experiments_when_base_effect_not_observed() -> None:
    graph = _graph(
        ["X", "Y"],
        [_edge("X", "Y"), _bidirected("X", "Y")],
        graph_type=GraphType.ADMG,
    )

    report = identify_path_specific(
        graph=graph,
        intervention=PathIntervention(active_paths=(("X", "Y"),)),
        outcome="Y",
        query_str="distribution:Y <- path(active=X->Y)",
        available_experimental_distributions=("exp:do(X)",),
    )

    assert report.mode is PathSpecificDecisionMode.EXACT_WITH_EXPERIMENTS
    assert report.compilation_plan is not None
    assert report.compilation_plan.compiled_estimand_ast is not None
    assert (
        DistributionDomain.EXPERIMENTAL
        in report.compilation_plan.compiled_estimand_ast.required_domains()
    )
    assert report.required_distributions


def test_causal_engine_path_query_attaches_compilation_metadata() -> None:
    engine = CausalEngine()
    graph = _graph(
        ["X", "M", "Y"],
        [_edge("X", "M"), _edge("M", "Y")],
        graph_type=GraphType.DAG,
    )
    query = InterventionQuery(
        target=QueryTarget(
            target_kind=QueryTargetKind.DECOMPOSITION,
            outcome_variables=("Y",),
        ),
        intervention=PathIntervention(
            active_paths=(("X", "M", "Y"),),
            natural_value_vars=("M",),
        ),
    )

    result = engine.identify("X", "Y", graph, intervention_query=query)

    assert hasattr(result, "status")
    assert result.estimand_ast is not None
    assert result.metadata["path_specific_mode"] == "exact_identified"
    assert "compiled_path_specific_estimand_ast" in result.metadata
    assert result.required_distributions


def test_causal_engine_compile_uses_lowered_path_specific_formula() -> None:
    engine = CausalEngine()
    graph = _graph(
        ["X", "M", "Y"],
        [_edge("X", "M"), _edge("M", "Y")],
        graph_type=GraphType.DAG,
    )
    query = InterventionQuery(
        target=QueryTarget(
            target_kind=QueryTargetKind.DECOMPOSITION,
            outcome_variables=("Y",),
        ),
        intervention=PathIntervention(
            active_paths=(("X", "M", "Y"),),
            natural_value_vars=("M",),
        ),
    )

    result = engine.identify("X", "Y", graph, intervention_query=query)
    executor_graph = engine.compile(result, graph=graph, run_id="path-stage13-3")
    method_fqns = {node.method_fqn for node in executor_graph.nodes}

    assert "causal.compiler.edge_intervention" in method_fqns
    assert "causal.treatment_effects.aipw" not in method_fqns


def test_causal_engine_path_query_keeps_conditioning_and_compiles_conditional_formula() -> None:
    engine = CausalEngine()
    graph = _graph(
        ["Z", "X", "M", "Y"],
        [_edge("Z", "X"), _edge("Z", "Y"), _edge("X", "M"), _edge("M", "Y")],
        graph_type=GraphType.DAG,
    )
    query = InterventionQuery(
        target=QueryTarget(
            target_kind=QueryTargetKind.DECOMPOSITION,
            outcome_variables=("Y",),
            conditioning=("Z",),
        ),
        intervention=PathIntervention(
            active_paths=(("X", "M", "Y"),),
            natural_value_vars=("M",),
        ),
    )

    result = engine.identify("X", "Y", graph, intervention_query=query)

    assert result.estimand_ast is not None
    assert result.estimand_ast.root.node_type == "path_specific"
    assert result.estimand_ast.root.conditioning == ("Z",)
    assert result.metadata["path_specific_mode"] == "exact_identified"
    compiled = result.metadata["compiled_path_specific_estimand_ast"]
    assert compiled["root"]["node_type"] == "conditional_do"


def test_causal_engine_path_query_returns_negative_certificate_with_bounds() -> None:
    engine = CausalEngine()
    graph = _graph(
        ["X", "M1", "M2", "Y"],
        [
            _edge("X", "M1"),
            _edge("X", "M2"),
            _edge("M1", "Y"),
            _edge("M2", "Y"),
            _bidirected("M1", "M2"),
        ],
        graph_type=GraphType.ADMG,
        metadata={"outcome_support": {"Y": (0.0, 1.0)}},
    )
    query = InterventionQuery(
        target=QueryTarget(
            target_kind=QueryTargetKind.DISTRIBUTION,
            outcome_variables=("Y",),
        ),
        intervention=PathIntervention(
            active_paths=(("X", "M1", "Y"),),
            frozen_paths=(("X", "M2", "Y"),),
            natural_value_vars=("M1", "M2"),
        ),
    )

    result = engine.identify("X", "Y", graph, intervention_query=query)

    assert isinstance(result, NegativeCertificate)
    assert result.bounds_bundle is not None
    assert result.quantitative_diagnostics["path_specific_mode"] == "bounded"


def test_causal_engine_path_query_returns_oracle_needed_surrogate_result() -> None:
    engine = CausalEngine()
    graph = _graph(
        ["X", "Y"],
        [_edge("X", "Y"), _bidirected("X", "Y")],
        graph_type=GraphType.ADMG,
    )
    query = InterventionQuery(
        target=QueryTarget(
            target_kind=QueryTargetKind.DISTRIBUTION,
            outcome_variables=("Y",),
        ),
        intervention=PathIntervention(active_paths=(("X", "Y"),)),
        context={"available_data_refs": ("exp:do(X)",)},
    )

    result = engine.identify("X", "Y", graph, intervention_query=query)

    assert isinstance(result, IdentificationResult)
    assert result.status is IdentificationStatus.ORACLE_NEEDED
    assert result.metadata["path_specific_mode"] == "exact_with_experiments"
    assert "compiled_path_specific_estimand_ast" in result.metadata
    assert result.required_distributions


def test_causal_engine_compile_uses_recursive_edge_intervention_formula() -> None:
    engine = CausalEngine()
    graph = _graph(
        ["X", "M", "Y"],
        [_edge("X", "M"), _edge("X", "Y"), _edge("M", "Y")],
        graph_type=GraphType.DAG,
    )
    query = InterventionQuery(
        target=QueryTarget(
            target_kind=QueryTargetKind.DISTRIBUTION,
            outcome_variables=("Y",),
        ),
        intervention=EdgeIntervention(
            assignments=(
                EdgeAssignment(source="X", target="M", value=0),
                EdgeAssignment(source="X", target="Y", value=1),
            ),
            semantics="edge_g_formula",
        ),
    )

    result = engine.identify("X", "Y", graph, intervention_query=query)
    executor_graph = engine.compile(result, graph=graph, run_id="edge-stage13-3")
    method_fqns = {node.method_fqn for node in executor_graph.nodes}

    assert "causal.compiler.edge_intervention" in method_fqns
    assert "causal.treatment_effects.aipw" not in method_fqns
