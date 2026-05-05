"""Standalone tests for the extracted σ-calculus module."""

from __future__ import annotations

from polisyos.foundry.methods.catalog.causal.sigma_calculus import (
    rewrite_estimand_with_selection,
    sigma_identify,
    sigma_z_identify,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.estimand import (
    CounterfactualNode,
    DistributionDomain,
    DistributionRef,
    EstimandAST,
    ProductNode,
)


def _dag(
    directed: list[tuple[str, str]],
    *,
    extra_nodes: tuple[str, ...] = (),
) -> CausalGraphModel:
    nodes = sorted({n for edge in directed for n in edge} | set(extra_nodes))
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=nodes,
        edges=[
            CausalEdge(src=src, dst=dst, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)
            for src, dst in directed
        ],
    )


def _dist_ref(
    variables: tuple[str, ...],
    intervention_set: tuple[str, ...] = (),
    conditioning: tuple[str, ...] = (),
) -> DistributionRef:
    return DistributionRef(
        domain=DistributionDomain.SOURCE,
        variables=variables,
        intervention_set=intervention_set,
        conditioning=conditioning,
    )


def _ast(root: object) -> EstimandAST:
    vars_seen: set[str] = set()
    if isinstance(root, DistributionRef):
        vars_seen |= set(root.variables) | set(root.intervention_set) | set(root.conditioning)
    return EstimandAST(
        query_str="sigma-test",
        root=root,
        treatment="X",
        outcome="Y",
        all_variables=tuple(sorted(vars_seen or {"X", "Y"})),
        identification_method="sigma_test",
    )


def test_sigma_identify_full_pipeline() -> None:
    """Full pipeline: do-calculus first, then σ-calculus."""
    graph = _dag([("Z", "X"), ("X", "Y")], extra_nodes=("W",))
    ast = _ast(_dist_ref(variables=("Y",), intervention_set=("X", "Z"), conditioning=("W",)))

    result_ast, steps = sigma_identify(
        ast, graph, selection_vars=frozenset({"W"}), max_iterations=5
    )

    assert isinstance(result_ast, EstimandAST)
    assert any(step.rule_name == "RULE2" for step in steps)
    assert isinstance(result_ast.root, DistributionRef)
    assert result_ast.root.conditioning


def test_sigma_z_combined_helper() -> None:
    """Combined helper accepts z_interventions and still rewrites via σ-calculus."""
    graph = _dag([("X", "Y")], extra_nodes=("W",))
    ast = _ast(_dist_ref(variables=("Y",), intervention_set=("X",), conditioning=("W",)))

    result_ast, steps = sigma_z_identify(
        ast,
        graph,
        selection_vars=frozenset(),
        z_interventions=frozenset({"W"}),
        max_iterations=5,
    )

    assert isinstance(result_ast, EstimandAST)
    assert isinstance(result_ast.root, DistributionRef)
    assert isinstance(steps, list)


def test_sigma_ctf_builtin_postpass() -> None:
    """The extracted σ-calculus triggers the real ctf-calculus post-pass."""

    graph = _dag([("X", "Y")], extra_nodes=("W",))
    counterfactual = CounterfactualNode(
        variable="Y",
        intervention={"X": 1},
        world_index=0,
        conditioning=("W",),
    )
    root = ProductNode(
        factors=(
            _dist_ref(variables=("Y",), intervention_set=(), conditioning=("W",)),
            counterfactual,
        )
    )
    ast = _ast(root)

    result_ast, steps = rewrite_estimand_with_selection(
        ast,
        graph,
        frozenset({"W"}),
        max_iterations=5,
    )

    assert isinstance(result_ast, EstimandAST)
    assert any(step.rule_name == "CTF_R1" for step in steps)
    assert isinstance(result_ast.root, ProductNode)
    assert isinstance(result_ast.root.factors[1], CounterfactualNode)
    assert result_ast.root.factors[1].conditioning == ()
