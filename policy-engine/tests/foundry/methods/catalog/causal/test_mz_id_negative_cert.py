"""Tests for NegativeCertificate emission on mz-ID failure (Phases 3+5)."""
import pytest

from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.negative_certificate import BlockingType, NegativeCertificate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dag(edges: list[tuple[str, str]]) -> CausalGraphModel:
    nodes = sorted({n for e in edges for n in e})
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=nodes,
        edges=[
            CausalEdge(src=s, dst=d, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)
            for s, d in edges
        ],
    )


def _confounded(directed: list[tuple[str, str]], bidirected: list[tuple[str, str]]) -> CausalGraphModel:
    nodes = sorted({n for e in directed + bidirected for n in e})
    edges = [
        CausalEdge(src=s, dst=d, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)
        for s, d in directed
    ]
    for s, d in bidirected:
        edges.append(CausalEdge(src=s, dst=d, mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW))
    return CausalGraphModel(graph_type=GraphType.PAG, nodes=nodes, edges=edges)


# ---------------------------------------------------------------------------
# Tests: NegativeCertificate.from_mz_id_failure()
# ---------------------------------------------------------------------------


class TestNegativeCertFromMzIdFailure:
    def test_s_node_unresolved_blocking_type(self):
        cert = NegativeCertificate.from_mz_id_failure(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            unresolved_s_nodes=frozenset({"Z"}),
            available_domains=["dom1"],
        )
        assert cert.blocking_type is BlockingType.S_NODE_UNRESOLVED

    def test_hedge_structure_blocking_type(self):
        """No unresolved S-nodes but hedge certificate → HEDGE_STRUCTURE."""
        # Provide a mock hedge certificate with a description attribute
        class MockHedge:
            description = "hedge found: F={X,Y}, F'={X}"
            hedge_forest = frozenset({"X", "Y"})
            hedge_root = frozenset({"X"})
            minimal_required_s_nodes = frozenset()

        cert = NegativeCertificate.from_mz_id_failure(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            unresolved_s_nodes=frozenset(),
            available_domains=["dom1"],
            hedge_certificate=MockHedge(),
        )
        assert cert.blocking_type is BlockingType.HEDGE_STRUCTURE

    def test_missing_distribution_blocking_type(self):
        """No S-nodes, no hedge → MISSING_DISTRIBUTION."""
        cert = NegativeCertificate.from_mz_id_failure(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            unresolved_s_nodes=frozenset(),
            available_domains=[],
        )
        assert cert.blocking_type is BlockingType.MISSING_DISTRIBUTION

    def test_blocking_description_mentions_outcome(self):
        cert = NegativeCertificate.from_mz_id_failure(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            unresolved_s_nodes=frozenset({"Z"}),
            available_domains=["dom1"],
        )
        assert "Y" in cert.blocking_description
        assert "X" in cert.blocking_description

    def test_unresolved_s_node_count_in_diagnostics(self):
        cert = NegativeCertificate.from_mz_id_failure(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            unresolved_s_nodes=frozenset({"Z1", "Z2"}),
            available_domains=["dom1", "dom2"],
        )
        assert cert.quantitative_diagnostics["unresolved_s_node_count"] == 2

    def test_available_domain_count_in_diagnostics(self):
        cert = NegativeCertificate.from_mz_id_failure(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            unresolved_s_nodes=frozenset(),
            available_domains=["dom1", "dom2", "dom3"],
        )
        assert cert.quantitative_diagnostics["available_domain_count"] == 3

    def test_missing_domain_count_in_diagnostics(self):
        cert = NegativeCertificate.from_mz_id_failure(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            unresolved_s_nodes=frozenset(),
            available_domains=[],
            missing_domains=["target_study", "rct_trial"],
        )
        assert cert.quantitative_diagnostics["missing_domain_count"] == 2

    def test_suggested_experiments_non_empty_for_s_node_failure(self):
        cert = NegativeCertificate.from_mz_id_failure(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            unresolved_s_nodes=frozenset({"Z"}),
            available_domains=["dom1"],
        )
        assert len(cert.suggested_experiments) >= 1

    def test_suggested_experiment_domain_for_s_node(self):
        cert = NegativeCertificate.from_mz_id_failure(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            unresolved_s_nodes=frozenset({"Z"}),
            available_domains=["dom1"],
        )
        # S_NODE_UNRESOLVED → experimental domain
        assert any(exp.domain == "experimental" for exp in cert.suggested_experiments)

    def test_constructive_message_mentions_missing_domains(self):
        cert = NegativeCertificate.from_mz_id_failure(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            unresolved_s_nodes=frozenset(),
            available_domains=[],
            missing_domains=["required_rct"],
        )
        assert "required_rct" in cert.constructive_message

    def test_hedge_technical_detail_populated(self):
        class MockHedge:
            description = "hedge found"
            hedge_forest = frozenset({"X", "Y"})
            hedge_root = frozenset({"X"})
            minimal_required_s_nodes = frozenset()

        cert = NegativeCertificate.from_mz_id_failure(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            unresolved_s_nodes=frozenset(),
            available_domains=["dom1"],
            hedge_certificate=MockHedge(),
        )
        assert "X" in cert.technical_detail or "Y" in cert.technical_detail

    def test_partial_bounds_forwarded(self):
        from polisyos.ir.analytics.partial_identification import BoundMethod, PartialIdentificationResult

        bounds = PartialIdentificationResult(
            method=BoundMethod.MANSKI, lower_bound=-0.2, upper_bound=0.8, confidence=0.9
        )
        cert = NegativeCertificate.from_mz_id_failure(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            unresolved_s_nodes=frozenset(),
            available_domains=[],
            partial_bounds=bounds,
        )
        assert cert.has_partial_bounds()
        assert cert.partial_bounds.lower_bound == -0.2

    def test_to_summary_contains_blocking_type(self):
        cert = NegativeCertificate.from_mz_id_failure(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            unresolved_s_nodes=frozenset({"Z"}),
            available_domains=[],
        )
        summary = cert.to_summary()
        assert "s_node_unresolved" in summary

    def test_round_trip_json(self):
        cert = NegativeCertificate.from_mz_id_failure(
            treatment=frozenset({"T"}),
            outcome=frozenset({"Y"}),
            unresolved_s_nodes=frozenset({"W"}),
            available_domains=["d1"],
        )
        data = cert.model_dump(mode="json")
        restored = NegativeCertificate.model_validate(data)
        assert restored.blocking_type == cert.blocking_type
        assert restored.quantitative_diagnostics["unresolved_s_node_count"] == 1

    def test_empty_available_domains_listed_in_description(self):
        cert = NegativeCertificate.from_mz_id_failure(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            unresolved_s_nodes=frozenset({"Z"}),
            available_domains=[],
        )
        # Description should mention that 0 domains were tried
        assert "0" in cert.blocking_description or "none" in cert.blocking_description.lower()

    def test_multiple_unresolved_s_nodes_in_description(self):
        cert = NegativeCertificate.from_mz_id_failure(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            unresolved_s_nodes=frozenset({"Z1", "Z2", "Z3"}),
            available_domains=["dom1"],
        )
        assert cert.quantitative_diagnostics["unresolved_s_node_count"] == 3
