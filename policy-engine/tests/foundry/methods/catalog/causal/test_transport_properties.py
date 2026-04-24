from __future__ import annotations

import pytest

try:
    from hypothesis import HealthCheck, given, settings
    from hypothesis import strategies as st

    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False

from polisyos.foundry.methods.catalog.causal.admg_ops import ancestors
from polisyos.foundry.methods.catalog.causal.id_engine import (
    IdentificationStatus,
    id_algorithm,
    tr_algorithm,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.transportability import SelectionDiagram, SelectionDiagramBuilder, SNode

pytestmark = pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")

NODE_ORDER = ("X", "A", "B", "Y", "W", "Z")
NON_ANCESTOR_CANDIDATES = ("W", "Z")
OPTIONAL_EDGES = tuple(
    (src, dst)
    for i, src in enumerate(NODE_ORDER)
    for dst in NODE_ORDER[i + 1 :]
    if (src, dst) != ("X", "Y")
)


def _edge(src: str, dst: str) -> CausalEdge:
    return CausalEdge(src=src, dst=dst, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)


def _graph_from_optional_edges(optional_edges: list[tuple[str, str]]) -> CausalGraphModel:
    edges = [("X", "Y"), *sorted(optional_edges)]
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=list(NODE_ORDER),
        edges=[_edge(src, dst) for src, dst in edges],
    )


@st.composite
def _transport_graph_spec(draw):
    optional_edges = draw(
        st.lists(
            st.sampled_from(OPTIONAL_EDGES),
            unique=True,
            max_size=len(OPTIONAL_EDGES),
        )
    )
    graph = _graph_from_optional_edges(optional_edges)
    ancestor_candidates = sorted(ancestors(graph, frozenset({"Y"})) & {"X", "A", "B"})
    ancestor_s_vars = draw(
        st.lists(
            st.sampled_from(ancestor_candidates),
            unique=True,
            min_size=1,
            max_size=len(ancestor_candidates),
        )
    )
    irrelevant_s_vars = draw(
        st.lists(
            st.sampled_from(NON_ANCESTOR_CANDIDATES),
            unique=True,
            min_size=1,
            max_size=len(NON_ANCESTOR_CANDIDATES),
        )
    )
    duplicate_sigma_vars = draw(
        st.lists(
            st.sampled_from(tuple(ancestor_s_vars) + NON_ANCESTOR_CANDIDATES),
            min_size=1,
            max_size=8,
        )
    )
    return {
        "graph": graph,
        "ancestor_s_vars": ancestor_s_vars,
        "irrelevant_s_vars": irrelevant_s_vars,
        "duplicate_sigma_vars": duplicate_sigma_vars,
    }


def _selection_diagram(graph: CausalGraphModel, s_vars: list[str]) -> SelectionDiagram:
    return SelectionDiagram(
        base_graph=graph,
        s_nodes=[
            SNode(
                target_variable=var,
                context_dimension="programmatic",
                source_value=0.0,
                target_value=1.0,
                delta=1.0,
                severity="medium",
            )
            for var in s_vars
        ],
        source_context=ContextProfile(context_id="source"),
        target_context=ContextProfile(context_id="target"),
    )


def _canonical_latex(result) -> str | None:
    if result.estimand_ast is None:
        return None
    return result.estimand_ast.to_latex().replace(" ", "").replace(".0", "")


def _rule_names(result) -> list[str]:
    return [step.rule_name for step in result.proof_steps]


def _dedupe_in_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


@given(spec=_transport_graph_spec())
@settings(
    max_examples=40,
    deadline=15000,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_non_ancestor_s_nodes_trim_to_base_identification(spec) -> None:
    graph = spec["graph"]
    base_result = id_algorithm(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        graph=graph,
    )
    tr_result = tr_algorithm(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        selection_diagram=_selection_diagram(graph, spec["irrelevant_s_vars"]),
    )

    assert base_result.status is IdentificationStatus.IDENTIFIED
    assert tr_result.status is IdentificationStatus.IDENTIFIED
    assert _canonical_latex(tr_result) == _canonical_latex(base_result)
    assert _rule_names(tr_result).count("S_TRIM") == len(spec["irrelevant_s_vars"])
    assert "S_AUGMENT" not in _rule_names(tr_result)


@given(spec=_transport_graph_spec())
@settings(
    max_examples=40,
    deadline=15000,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_ancestor_s_nodes_are_retained_by_transport_augmentation(spec) -> None:
    tr_result = tr_algorithm(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        selection_diagram=_selection_diagram(spec["graph"], spec["ancestor_s_vars"]),
    )

    rules = _rule_names(tr_result)
    assert tr_result.status is IdentificationStatus.IDENTIFIED
    assert rules.count("S_TRIM") == 0
    assert "S_AUGMENT" in rules
    augment_step = next(step for step in tr_result.proof_steps if step.rule_name == "S_AUGMENT")
    assert set(augment_step.antecedent_vars) == {f"S_{var}" for var in spec["ancestor_s_vars"]}


@given(spec=_transport_graph_spec())
@settings(
    max_examples=40,
    deadline=15000,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_irrelevant_s_nodes_do_not_change_transport_estimand(spec) -> None:
    graph = spec["graph"]
    base_transport = tr_algorithm(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        selection_diagram=_selection_diagram(graph, spec["ancestor_s_vars"]),
    )
    mixed_transport = tr_algorithm(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        selection_diagram=_selection_diagram(
            graph,
            [*spec["ancestor_s_vars"], *spec["irrelevant_s_vars"]],
        ),
    )

    assert base_transport.status is IdentificationStatus.IDENTIFIED
    assert mixed_transport.status is IdentificationStatus.IDENTIFIED
    assert _canonical_latex(mixed_transport) == _canonical_latex(base_transport)
    assert _rule_names(mixed_transport).count("S_TRIM") == len(spec["irrelevant_s_vars"])
    assert "S_AUGMENT" in _rule_names(mixed_transport)


@given(spec=_transport_graph_spec())
@settings(
    max_examples=40,
    deadline=15000,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_selection_diagram_builder_deduplicates_sigma_variables(spec) -> None:
    builder = SelectionDiagramBuilder(spec["graph"])
    for variable_name in spec["duplicate_sigma_vars"]:
        builder.add_sigma_variable(variable_name)
    built = builder.build(
        source_context=ContextProfile(context_id="source"),
        target_context=ContextProfile(context_id="target"),
    )
    expected_unique = _dedupe_in_order(spec["duplicate_sigma_vars"])

    assert [s_node.target_variable for s_node in built.s_nodes] == expected_unique

    manual = _selection_diagram(spec["graph"], expected_unique)
    built_result = tr_algorithm(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        selection_diagram=built,
    )
    manual_result = tr_algorithm(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        selection_diagram=manual,
    )

    assert built_result.status is manual_result.status
    assert _canonical_latex(built_result) == _canonical_latex(manual_result)
