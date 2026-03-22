"""Tests for Phase 4 counterfactual transportability."""

from __future__ import annotations

from polisyos.foundry.methods.catalog.causal.ctf_transport import (
    build_ctf_selection_diagram,
    ctf_transport_bounds,
    ctf_transportability,
)
from polisyos.foundry.methods.catalog.causal.id_engine import (
    CtfQuery,
    IdentificationResult,
    IdentificationStatus,
    SourceDomain,
)
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
)
from polisyos.ir.analytics.estimand import DistributionRef
from polisyos.ir.analytics.negative_certificate import BlockingType, NegativeCertificate
from polisyos.ir.analytics.partial_identification import BoundMethod
from polisyos.ir.analytics.transportability import SNode


def _dag(
    edges: list[tuple[str, str]],
    *,
    extra_nodes: tuple[str, ...] = (),
) -> CausalGraphModel:
    nodes = sorted({node for edge in edges for node in edge} | set(extra_nodes))
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=nodes,
        edges=[
            CausalEdge(src=src, dst=dst, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)
            for src, dst in edges
        ],
    )


def _bow_arc_graph() -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["X", "Y"],
        edges=[
            CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="X", dst="Y", mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW),
        ],
    )


def _snode(variable: str) -> SNode:
    return SNode(
        target_variable=variable,
        context_dimension="mechanism_shift",
        source_value=0.0,
        target_value=1.0,
        delta=1.0,
        severity="medium",
    )


def test_ctf_transport_pn_across_domains() -> None:
    graph = _dag([("X", "Y")])
    query = CtfQuery(
        outcome="Y",
        intervention=(("X", 1.0),),
        evidence=(("Y", 1.0),),
        kind="pn",
    )
    selection_diagram = build_ctf_selection_diagram(graph=graph, s_nodes=[_snode("Y")])

    result = ctf_transportability(query, selection_diagram)

    assert isinstance(result, IdentificationResult)
    assert result.status is IdentificationStatus.IDENTIFIED
    assert any(step.rule_name == "CTF_TRANSPORT_START" for step in result.proof_steps)
    assert result.query_str == "P(Y_{X=0} | Y=1)"


def test_ctf_transport_non_transportable() -> None:
    graph = _bow_arc_graph()
    query = CtfQuery(outcome="Y", intervention=(("X", 1.0),), kind="single_world")
    selection_diagram = build_ctf_selection_diagram(graph=graph, s_nodes=[_snode("Y")])

    result = ctf_transportability(query, selection_diagram)

    assert isinstance(result, NegativeCertificate)
    assert result.blocking_type is BlockingType.S_NODE_UNRESOLVED
    assert result.partial_bounds is not None
    assert result.partial_bounds.method is BoundMethod.TRANSPORT_BOUNDS


def test_ctf_transport_reduces_to_l2() -> None:
    graph = _dag([], extra_nodes=("X", "Y"))
    query = CtfQuery(outcome="Y", intervention=(("X", 1.0),), kind="single_world")
    selection_diagram = build_ctf_selection_diagram(graph=graph, s_nodes=[_snode("Y")])

    result = ctf_transportability(query, selection_diagram)

    assert isinstance(result, IdentificationResult)
    assert result.status is IdentificationStatus.IDENTIFIED
    assert result.estimand_ast is not None
    assert isinstance(result.estimand_ast.root, DistributionRef)
    assert result.estimand_ast.root.intervention_set == ()
    assert any(step.rule_name == "CTF_R3" for step in result.proof_steps)


def test_ctf_transport_bounds() -> None:
    graph = _bow_arc_graph()
    query = CtfQuery(outcome="Y", intervention=(("X", 1.0),), kind="single_world")
    selection_diagram = build_ctf_selection_diagram(graph=graph, s_nodes=[_snode("Y")])

    bounds = ctf_transport_bounds(query, selection_diagram)

    assert bounds.method is BoundMethod.TRANSPORT_BOUNDS
    assert bounds.lower_bound == 0.0
    assert bounds.upper_bound == 1.0
    assert "query_kind=single_world" in bounds.assumptions_used


def test_ctf_transport_multi_domain() -> None:
    graph = _dag([], extra_nodes=("X", "Y"))
    query = CtfQuery(outcome="Y", intervention=(("X", 1.0),), kind="single_world")
    source_domains = [
        SourceDomain(domain_id="source_obs", s_nodes=frozenset({"Y"}), dataset_ref="study_obs"),
        SourceDomain(domain_id="source_rct", z_interventions=frozenset({"X"}), dataset_ref="study_rct"),
    ]
    selection_diagram = build_ctf_selection_diagram(graph=graph, source_domains=source_domains)

    result = ctf_transportability(
        query,
        selection_diagram,
        source_domains=source_domains,
    )

    assert isinstance(result, IdentificationResult)
    assert result.status is IdentificationStatus.IDENTIFIED
    assert any(step.rule_name == "CTF_TRANSPORT_MZ" for step in result.proof_steps)
    assert result.estimand_ast is not None
    refs = result.estimand_ast.collect_distribution_refs()
    assert refs
    assert refs[0].dataset_ref == "study_obs"
