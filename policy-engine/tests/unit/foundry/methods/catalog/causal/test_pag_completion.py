"""Tests for pag_completion.py — PAG orientation rules, CPDAG upcast, validity."""

from __future__ import annotations

import pytest

from polisyos.foundry.methods.catalog.causal.pag_completion import (
    apply_pag_orientation_rules,
    cpdag_to_pag,
    extract_unshielded_triples,
    validate_pag,
)
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_edge(
    src: str,
    dst: str,
    mark_src: EdgeMark = EdgeMark.TAIL,
    mark_dst: EdgeMark = EdgeMark.ARROW,
) -> CausalEdge:
    return CausalEdge(src=src, dst=dst, mark_src=mark_src, mark_dst=mark_dst)


def _make_dag(nodes: list[str], edges: list[CausalEdge]) -> CausalGraphModel:
    return CausalGraphModel(graph_type=GraphType.DAG, nodes=nodes, edges=edges)


def _make_cpdag(nodes: list[str], edges: list[CausalEdge]) -> CausalGraphModel:
    return CausalGraphModel(graph_type=GraphType.CPDAG, nodes=nodes, edges=edges)


def _make_pag(nodes: list[str], edges: list[CausalEdge]) -> CausalGraphModel:
    return CausalGraphModel(graph_type=GraphType.PAG, nodes=nodes, edges=edges)


# ---------------------------------------------------------------------------
# Test 1: cpdag_to_pag converts undirected TAIL-TAIL edges to CIRCLE-CIRCLE
# ---------------------------------------------------------------------------


def test_cpdag_to_pag_converts_undirected() -> None:
    undirected_edge = _make_edge("X", "Y", EdgeMark.TAIL, EdgeMark.TAIL)
    cpdag = _make_cpdag(["X", "Y"], [undirected_edge])

    pag = cpdag_to_pag(cpdag)

    assert pag.graph_type is GraphType.PAG
    assert len(pag.edges) == 1
    e = pag.edges[0]
    assert e.mark_src is EdgeMark.CIRCLE
    assert e.mark_dst is EdgeMark.CIRCLE


# ---------------------------------------------------------------------------
# Test 2: cpdag_to_pag preserves directed TAIL-ARROW edges
# ---------------------------------------------------------------------------


def test_cpdag_to_pag_preserves_directed() -> None:
    directed_edge = _make_edge("X", "Y", EdgeMark.TAIL, EdgeMark.ARROW)
    cpdag = _make_cpdag(["X", "Y"], [directed_edge])

    pag = cpdag_to_pag(cpdag)

    assert pag.graph_type is GraphType.PAG
    assert len(pag.edges) == 1
    e = pag.edges[0]
    assert e.mark_src is EdgeMark.TAIL
    assert e.mark_dst is EdgeMark.ARROW


# ---------------------------------------------------------------------------
# Test 3: cpdag_to_pag is identity on PAG input
# ---------------------------------------------------------------------------


def test_cpdag_to_pag_identity_on_pag() -> None:
    edge = _make_edge("X", "Y", EdgeMark.CIRCLE, EdgeMark.ARROW)
    pag_in = _make_pag(["X", "Y"], [edge])

    pag_out = cpdag_to_pag(pag_in)

    assert pag_out is pag_in  # same object returned


def test_pag_consumers_refuse_duplicate_rows_after_schema_bypass() -> None:
    duplicate = CausalGraphModel.model_construct(
        graph_type=GraphType.PAG,
        nodes=["X", "Y"],
        edges=[
            _make_edge("X", "Y", EdgeMark.TAIL, EdgeMark.ARROW),
            _make_edge("Y", "X", EdgeMark.ARROW, EdgeMark.TAIL),
        ],
    )
    with pytest.raises(ValueError, match="PAG requires at most one edge per unordered node pair"):
        apply_pag_orientation_rules(duplicate)
    violations = validate_pag(duplicate)
    assert len(violations) == 1
    assert violations[0].startswith("duplicate_adjacency:")


# ---------------------------------------------------------------------------
# Test 4: R1 non-collider orientation — α→β○-γ (unshielded) → β→γ
# Nodes: A, B, C. A→B (TAIL-ARROW), B○-C (CIRCLE at B-end, TAIL at C-end).
# A not adjacent to C. After R1: B→C (TAIL-ARROW).
# ---------------------------------------------------------------------------


def test_r1_noncollider_orientation() -> None:
    # A → B: mark_src=TAIL, mark_dst=ARROW
    ab = _make_edge("A", "B", EdgeMark.TAIL, EdgeMark.ARROW)
    # B o-C: stored as (B, C) with mark_src=CIRCLE (at B-end), mark_dst=TAIL (at C-end)
    bc = _make_edge("B", "C", EdgeMark.CIRCLE, EdgeMark.TAIL)
    pag = _make_pag(["A", "B", "C"], [ab, bc])

    oriented, warnings = apply_pag_orientation_rules(pag, max_iter=5)

    # Find the B-C edge
    bc_result = next((e for e in oriented.edges if e.src == "B" and e.dst == "C"), None)
    # If stored as (B, C): R1 should set mark_src=TAIL, mark_dst=ARROW (B→C)
    assert bc_result is not None, "B-C edge should still be present"
    assert bc_result.mark_src is EdgeMark.TAIL
    assert bc_result.mark_dst is EdgeMark.ARROW


# ---------------------------------------------------------------------------
# Test 5: R2 acyclicity — α→β→γ, α○-γ → α→γ
# ---------------------------------------------------------------------------


def test_r2_acyclicity_orientation() -> None:
    # A → B
    ab = _make_edge("A", "B", EdgeMark.TAIL, EdgeMark.ARROW)
    # B → C
    bc = _make_edge("B", "C", EdgeMark.TAIL, EdgeMark.ARROW)
    # A o- C: stored as (A, C) with mark_src=CIRCLE, mark_dst=TAIL
    ac = _make_edge("A", "C", EdgeMark.CIRCLE, EdgeMark.TAIL)
    pag = _make_pag(["A", "B", "C"], [ab, bc, ac])

    oriented, warnings = apply_pag_orientation_rules(pag, max_iter=5)

    ac_result = next((e for e in oriented.edges if e.src == "A" and e.dst == "C"), None)
    assert ac_result is not None
    # R2: orient A → C
    assert ac_result.mark_src is EdgeMark.TAIL
    assert ac_result.mark_dst is EdgeMark.ARROW


# ---------------------------------------------------------------------------
# Test 6: R3 v-structure extension
# Setup: α→δ, γ→δ (collider at δ), δ○-β, α○-β, γ○-β, α not adj γ → δ→β
# Nodes: alpha=A, beta=B, gamma=C, delta=D
# ---------------------------------------------------------------------------


def test_r3_vstructure_extension() -> None:
    # A → D (TAIL-ARROW)
    ad = _make_edge("A", "D", EdgeMark.TAIL, EdgeMark.ARROW)
    # C → D (TAIL-ARROW)
    cd = _make_edge("C", "D", EdgeMark.TAIL, EdgeMark.ARROW)
    # D o-* B: mark_src=CIRCLE at D-end
    db = _make_edge("D", "B", EdgeMark.CIRCLE, EdgeMark.TAIL)
    # A o-* B: mark_src=CIRCLE at A-end
    ab = _make_edge("A", "B", EdgeMark.CIRCLE, EdgeMark.TAIL)
    # C o-* B: mark_src=CIRCLE at C-end
    cb = _make_edge("C", "B", EdgeMark.CIRCLE, EdgeMark.TAIL)
    # A not adjacent to C — no A-C edge

    pag = _make_pag(["A", "B", "C", "D"], [ad, cd, db, ab, cb])

    oriented, warnings = apply_pag_orientation_rules(pag, max_iter=10)

    db_result = next((e for e in oriented.edges if e.src == "D" and e.dst == "B"), None)
    # R3 should orient D → B
    assert db_result is not None
    assert db_result.mark_src is EdgeMark.TAIL
    assert db_result.mark_dst is EdgeMark.ARROW


# ---------------------------------------------------------------------------
# Test 7: validate_pag catches almost-directed cycle
# A→B→C and C*→A (arrow at A-end) creates almost-directed cycle.
# ---------------------------------------------------------------------------


def test_validate_pag_catches_almost_directed_cycle() -> None:
    ab = _make_edge("A", "B", EdgeMark.TAIL, EdgeMark.ARROW)
    bc = _make_edge("B", "C", EdgeMark.TAIL, EdgeMark.ARROW)
    # C *→ A: stored as (C, A) with mark_dst=ARROW at A-end
    ca = _make_edge("C", "A", EdgeMark.TAIL, EdgeMark.ARROW)
    pag = _make_pag(["A", "B", "C"], [ab, bc, ca])

    violations = validate_pag(pag)

    assert len(violations) > 0
    assert any("almost_directed_cycle" in v for v in violations)


# ---------------------------------------------------------------------------
# Test 8: validate_pag accepts a valid collider PAG
# A→B←C (collider at B), A not adjacent to C. No cycles.
# ---------------------------------------------------------------------------


def test_validate_pag_accepts_valid_pag() -> None:
    ab = _make_edge("A", "B", EdgeMark.TAIL, EdgeMark.ARROW)
    cb = _make_edge("C", "B", EdgeMark.TAIL, EdgeMark.ARROW)
    pag = _make_pag(["A", "B", "C"], [ab, cb])

    violations = validate_pag(pag)

    # No almost-directed cycles (A and C have no path back to each other)
    cycle_violations = [v for v in violations if "almost_directed_cycle" in v]
    assert len(cycle_violations) == 0


# ---------------------------------------------------------------------------
# Test 9: consensus PAG with mixed CPDAG + PAG input
# ---------------------------------------------------------------------------


def test_consensus_pag_with_mixed_cpdag_and_pag() -> None:
    """PC (CPDAG) and FCI (PAG) reports can be merged into a valid PAG."""
    from polisyos.foundry.methods.catalog.causal.discovery_pipeline import (
        _build_consensus_pag,
    )
    from polisyos.ir.analytics.causal_discovery import CausalDiscoveryReport

    # Report 1: PC → CPDAG with X→Y (directed) and Y-Z (undirected)
    pc_graph = _make_cpdag(
        ["X", "Y", "Z"],
        [
            _make_edge("X", "Y", EdgeMark.TAIL, EdgeMark.ARROW),
            _make_edge("Y", "Z", EdgeMark.TAIL, EdgeMark.TAIL),
        ],
    )
    pc_report = CausalDiscoveryReport(method="pc", graph=pc_graph)

    # Report 2: FCI → PAG with X→Y and Z→Y (same direction for Y-Z)
    fci_graph = _make_pag(
        ["X", "Y", "Z"],
        [
            _make_edge("X", "Y", EdgeMark.TAIL, EdgeMark.ARROW),
            _make_edge("Z", "Y", EdgeMark.TAIL, EdgeMark.ARROW),
        ],
    )
    fci_report = CausalDiscoveryReport(method="fci", graph=fci_graph)

    pag, edge_agreements, skeleton_agreement, violations, orient_warnings, temporal_edges = (
        _build_consensus_pag(
            [pc_report, fci_report],
            {"pc": 0.5, "fci": 0.5},
            ["X", "Y", "Z"],
            min_presence_score=0.3,
        )
    )

    assert pag.graph_type is GraphType.PAG
    # Both algorithms agree X→Y exists
    xy_edges = [e for e in pag.edges if {e.src, e.dst} == {"X", "Y"}]
    assert len(xy_edges) == 1
    # skeleton_agreement should have entries
    assert len(skeleton_agreement) > 0
    for key, score in skeleton_agreement.items():
        assert 0.0 <= score <= 1.0
    # temporal_edges should be empty (no PCMCI)
    assert temporal_edges == []


# ---------------------------------------------------------------------------
# Test 10: temporal edges segregated from PAG
# PCMCI lag>0 edges go to temporal_edges, not the unified_pag.
# ---------------------------------------------------------------------------


def test_temporal_edges_segregated_from_pag() -> None:
    from polisyos.foundry.methods.catalog.causal.discovery_pipeline import (
        _build_consensus_pag,
    )
    from polisyos.ir.analytics.causal_discovery import CausalDiscoveryReport

    lag1_edge = CausalEdge(
        src="X",
        dst="Y",
        mark_src=EdgeMark.TAIL,
        mark_dst=EdgeMark.ARROW,
        lag=1,
    )
    lag2_edge = CausalEdge(
        src="Y",
        dst="Z",
        mark_src=EdgeMark.TAIL,
        mark_dst=EdgeMark.ARROW,
        lag=2,
    )
    pcmci_graph = _make_pag(["X", "Y", "Z"], [lag1_edge, lag2_edge])
    pcmci_report = CausalDiscoveryReport(method="pcmci+", graph=pcmci_graph)

    pag, edge_agreements, skeleton_agreement, violations, orient_warnings, temporal_edges = (
        _build_consensus_pag(
            [pcmci_report],
            {"pcmci+": 1.0},
            ["X", "Y", "Z"],
            min_presence_score=0.3,
        )
    )

    # All edges were lagged → PAG should be empty
    assert pag.edges == []
    # temporal_edges should contain both lag edges
    assert len(temporal_edges) == 2
    lags = {e.lag for e in temporal_edges}
    assert 1 in lags
    assert 2 in lags


# ---------------------------------------------------------------------------
# Test 11: extract_unshielded_triples basic case
# ---------------------------------------------------------------------------


def test_extract_unshielded_triples_basic() -> None:
    # A-B-C chain, no A-C edge → unshielded triple (A,B,C) and (C,B,A)
    ab = _make_edge("A", "B", EdgeMark.CIRCLE, EdgeMark.CIRCLE)
    bc = _make_edge("B", "C", EdgeMark.CIRCLE, EdgeMark.CIRCLE)
    pag = _make_pag(["A", "B", "C"], [ab, bc])

    triples = extract_unshielded_triples(pag)
    triple_set = set(triples)

    assert ("A", "B", "C") in triple_set or ("C", "B", "A") in triple_set


def test_extract_unshielded_triples_shielded_returns_empty() -> None:
    # A-B-C with A-C also present → shielded, no unshielded triples
    ab = _make_edge("A", "B", EdgeMark.CIRCLE, EdgeMark.CIRCLE)
    bc = _make_edge("B", "C", EdgeMark.CIRCLE, EdgeMark.CIRCLE)
    ac = _make_edge("A", "C", EdgeMark.CIRCLE, EdgeMark.CIRCLE)
    pag = _make_pag(["A", "B", "C"], [ab, bc, ac])

    triples = extract_unshielded_triples(pag)

    assert triples == []


# ---------------------------------------------------------------------------
# Test 12: apply_pag_orientation_rules does not modify a PAG with no circles
# ---------------------------------------------------------------------------


def test_apply_rules_no_change_on_fully_oriented() -> None:
    ab = _make_edge("A", "B", EdgeMark.TAIL, EdgeMark.ARROW)
    bc = _make_edge("B", "C", EdgeMark.TAIL, EdgeMark.ARROW)
    pag = _make_pag(["A", "B", "C"], [ab, bc])

    oriented, warnings = apply_pag_orientation_rules(pag, max_iter=5)

    # No circles → no changes → output should match input
    assert len(oriented.edges) == len(pag.edges)
    assert warnings == []
    for e_in, e_out in zip(pag.edges, oriented.edges):
        assert e_out.mark_src is e_in.mark_src
        assert e_out.mark_dst is e_in.mark_dst


# ---------------------------------------------------------------------------
# Scalar identification admission for PAG/CPDAG remains unresolved.


class TestPAGIDPolicies:
    """Graph-kind tags remain load-bearing even when endpoints look resolved."""

    def _run_pag_id(self, graph: CausalGraphModel, treatment: str, outcome: str):
        from polisyos.foundry.methods.catalog.causal.id_engine import (
            DistributionDomain,
            _pag_id_algorithm,
        )

        return _pag_id_algorithm(
            treatment=frozenset({treatment}),
            outcome=frozenset({outcome}),
            graph=graph,
            available_vars=frozenset(graph.nodes),
            dataset_ref=None,
            domain=DistributionDomain.SOURCE,
            _depth=0,
            _trace=[],
        )

    def _run_public_id(self, graph: CausalGraphModel, treatment: str, outcome: str):
        from polisyos.foundry.methods.catalog.causal.id_engine import id_algorithm

        return id_algorithm(
            treatment=frozenset({treatment}),
            outcome=frozenset({outcome}),
            graph=graph,
            available_vars=frozenset(graph.nodes),
        )

    @pytest.mark.parametrize("graph_type", [GraphType.PAG, GraphType.CPDAG])
    def test_resolved_endpoint_marks_do_not_authorize_partial_graph_id(self, graph_type):
        """A typed partial profile cannot be relabeled by its endpoint pattern."""
        from polisyos.foundry.methods.catalog.causal.admg_ops import (
            PartialGraphCompletionSemanticsError,
        )

        graph = CausalGraphModel(
            graph_type=graph_type,
            nodes=["X", "Y"],
            edges=[_make_edge("X", "Y", EdgeMark.TAIL, EdgeMark.ARROW)],
        )
        with pytest.raises(PartialGraphCompletionSemanticsError):
            self._run_public_id(graph, "X", "Y")
        with pytest.raises(PartialGraphCompletionSemanticsError):
            self._run_pag_id(graph, "X", "Y")

    @pytest.mark.parametrize("policy", ["conservative", "optimistic", "probabilistic"])
    def test_pag_policy_labels_do_not_authorize_completion(self, policy):
        """A policy name cannot select an extension for a residual circle."""
        from polisyos.foundry.methods.catalog.causal.admg_ops import (
            PartialGraphCompletionSemanticsError,
        )
        from polisyos.ir.analytics.causal_graph import PAGIdentificationPolicy

        graph = CausalGraphModel(
            graph_type=GraphType.PAG,
            nodes=["X", "Y"],
            edges=[_make_edge("X", "Y", EdgeMark.CIRCLE, EdgeMark.ARROW)],
            pag_identification_policy=PAGIdentificationPolicy(policy),
        )
        with pytest.raises(PartialGraphCompletionSemanticsError):
            self._run_public_id(graph, "X", "Y")

    def test_pag_orientation_rules_remain_structural_not_identification_authority(self):
        """Orientation helpers may refine marks without changing the PAG tag."""
        pag = _make_pag(
            ["A", "B", "C"],
            [
                _make_edge("A", "B"),
                _make_edge("B", "C", EdgeMark.CIRCLE, EdgeMark.TAIL),
            ],
        )
        oriented, _warnings = apply_pag_orientation_rules(pag, max_iter=5)
        assert oriented.graph_type is GraphType.PAG
        assert oriented.graph_type is not GraphType.ADMG

    def test_static_admg_controls_remain_identified_or_hedged(self):
        """The native resolved ADMG owner retains its actual positive controls."""
        from polisyos.foundry.methods.catalog.causal.id_engine import (
            IdentificationStatus,
        )

        directed = CausalGraphModel(
            graph_type=GraphType.ADMG,
            nodes=["X", "Y"],
            edges=[_make_edge("X", "Y")],
        )
        identified = self._run_public_id(directed, "X", "Y")
        assert identified.status is IdentificationStatus.IDENTIFIED
        assert identified.estimand_ast is not None

        bow = CausalGraphModel(
            graph_type=GraphType.ADMG,
            nodes=["X", "Y"],
            edges=[_make_edge("X", "Y"), _make_edge("X", "Y", EdgeMark.ARROW, EdgeMark.ARROW)],
        )
        hedged = self._run_public_id(bow, "X", "Y")
        assert hedged.status is IdentificationStatus.HEDGE_FOUND
        assert hedged.hedge_certificate is not None
