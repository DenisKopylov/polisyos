from __future__ import annotations

import numpy as np

from polisyos.foundry.methods.catalog.causal.transport_bounds import transport_bounds
from polisyos.foundry.methods.catalog.causal.transport_engine import _run_bounds_only
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.partial_identification import BoundMethod, compute_manski_bounds
from polisyos.ir.analytics.transportability import SelectionDiagram, SNode, SNodeOrigin, SNodeRole


def _make_graph() -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[
            CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        ],
    )


def _make_selection_diagram(
    *, s_count: int = 2, context_distance: float = 0.45
) -> SelectionDiagram:
    graph = _make_graph()
    s_nodes = [
        SNode(
            target_variable="X" if i == 0 else "Y",
            context_dimension=f"dim_{i}",
            source_value=0.0,
            target_value=1.0,
            delta=1.0,
            severity="medium",
            origin=SNodeOrigin.CONTEXT_DELTA,
            role=SNodeRole.PRE_TREATMENT_COVARIATE if i == 0 else SNodeRole.MEDIATOR,
        )
        for i in range(s_count)
    ]
    return SelectionDiagram(
        base_graph=graph,
        s_nodes=s_nodes,
        source_context=ContextProfile(context_id="source"),
        target_context=ContextProfile(context_id="target"),
        context_distance=context_distance,
    )


def _binary_data(seed: int = 5, n: int = 600, *, effect: float = 0.45) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    treatment = rng.integers(0, 2, size=n).astype(float)
    outcome = (rng.random(size=n) < (0.12 + effect * treatment)).astype(float)
    return {"outcome": outcome, "treatment": treatment}


def test_transport_bounds_are_subset_of_target_manski() -> None:
    diagram = _make_selection_diagram()
    source = _binary_data(seed=5, effect=0.35)
    target = _binary_data(seed=9, effect=0.42)

    result = transport_bounds(
        selection_diagram=diagram,
        data_source=source,
        data_target=target,
    )
    treated = target["treatment"] > 0.5
    manski = compute_manski_bounds(
        outcome_conditioned=np.array(
            [
                float(np.mean(target["outcome"][~treated])),
                float(np.mean(target["outcome"][treated])),
            ]
        ),
        treatment_probs=np.array(
            [
                float(np.mean(~treated)),
                float(np.mean(treated)),
            ]
        ),
        outcome_support=(0.0, 1.0),
    )

    assert result.method == BoundMethod.TRANSPORT_BOUNDS
    assert result.lower_bound >= manski.lower_bound - 1e-9
    assert result.upper_bound <= manski.upper_bound + 1e-9
    assert "transport_selection_relaxation" in result.assumptions_used
    assert "target_partial_identification" in result.assumptions_used


def test_transport_bounds_with_partial_s_elimination_tighten_monotonically() -> None:
    diagram = _make_selection_diagram(s_count=3, context_distance=0.6)
    source = _binary_data(seed=13, effect=0.4)
    target = _binary_data(seed=17, effect=0.41)

    unresolved = transport_bounds(selection_diagram=diagram, data_source=source, data_target=target)
    partially_resolved = transport_bounds(
        selection_diagram=diagram,
        data_source=source,
        data_target=target,
        constraints={"resolved_s_nodes": ["X"]},
    )
    fully_resolved = transport_bounds(
        selection_diagram=diagram,
        data_source=source,
        data_target=target,
        constraints={"resolved_s_nodes": ["X", "Y", "Z"]},
    )

    assert partially_resolved.bound_width <= unresolved.bound_width + 1e-9
    assert fully_resolved.bound_width <= partially_resolved.bound_width + 1e-9
    assert "resolved_s_nodes=1/3" in partially_resolved.assumptions_used


def test_transport_bounds_can_report_exact_when_all_components_are_exact() -> None:
    diagram = _make_selection_diagram(s_count=1, context_distance=0.0)
    source = _binary_data(seed=21, effect=0.5)
    target = _binary_data(seed=22, effect=0.5)

    result = transport_bounds(
        selection_diagram=diagram,
        data_source=source,
        data_target=target,
        constraints={"resolved_s_nodes": ["X"]},
    )

    assert result.bounds_type == "sharp_lp"
    assert result.relaxation_gap == 0.0
    assert result.discretization_method is not None


def test_transport_engine_bounds_only_uses_transport_bounds() -> None:
    diagram = _make_selection_diagram(s_count=2, context_distance=0.3)
    result = _run_bounds_only(
        diagram=diagram,
        treatment="X",
        outcome="Y",
        trace=["test"],
    )

    assert result.partial_identification_result is not None
    assert result.partial_identification_result.method == BoundMethod.TRANSPORT_BOUNDS
    assert result.identification_trace[-1] == "family:transport_bounds"
