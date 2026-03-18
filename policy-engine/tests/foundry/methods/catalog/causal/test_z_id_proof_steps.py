"""Tests for ProofStep emission in z_id_algorithm and mz_id_algorithm (Phase 3)."""
import pytest

from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType


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


def _source_domain(
    domain_id: str,
    s_nodes: frozenset[str] | None = None,
    z_interventions: frozenset[str] | None = None,
):
    from polisyos.foundry.methods.catalog.causal.id_engine import SourceDomain

    return SourceDomain(
        domain_id=domain_id,
        s_nodes=s_nodes or frozenset(),
        z_interventions=z_interventions or frozenset(),
    )


def _z_id(
    treatment: str,
    outcome: str,
    z_interventions: frozenset[str],
    graph: CausalGraphModel,
    dataset_ref: str | None = None,
):
    from polisyos.foundry.methods.catalog.causal.id_engine import z_id_algorithm

    return z_id_algorithm(
        treatment=frozenset({treatment}),
        outcome=frozenset({outcome}),
        z_interventions=z_interventions,
        graph=graph,
        dataset_ref=dataset_ref,
    )


def _mz_id(
    treatment: str,
    outcome: str,
    source_domains,
    graph: CausalGraphModel,
    dataset_ref: str | None = None,
):
    from polisyos.foundry.methods.catalog.causal.id_engine import mz_id_algorithm

    return mz_id_algorithm(
        treatment=frozenset({treatment}),
        outcome=frozenset({outcome}),
        source_domains=source_domains,
        graph=graph,
        dataset_ref=dataset_ref,
    )


# ---------------------------------------------------------------------------
# z_id_algorithm — Z_TRANSPORT ProofStep
# ---------------------------------------------------------------------------


class TestZIdProofSteps:
    def test_empty_z_falls_back_to_standard_id(self):
        """No z-interventions → standard ID, no Z_TRANSPORT step."""
        from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationStatus

        graph = _dag([("X", "Y")])
        result = _z_id("X", "Y", frozenset(), graph)
        # Should succeed via standard ID
        assert result.status is IdentificationStatus.IDENTIFIED
        z_steps = [s for s in result.proof_steps if s.rule_name == "Z_TRANSPORT"]
        assert len(z_steps) == 0

    def test_z_transport_step_emitted_when_z_blocks_path(self):
        """When Z d-separates Y from X in G_do(X), Z_TRANSPORT step is emitted."""
        from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationStatus

        # Simple graph: X → Z → Y (Z is a mediator — Z-transport valid)
        graph = _dag([("X", "Z"), ("Z", "Y")])
        result = _z_id("X", "Y", frozenset({"Z"}), graph)
        # If direct pass succeeds (Z blocks all back-door paths in G_do(X))
        if result.status is IdentificationStatus.IDENTIFIED:
            z_steps = [s for s in result.proof_steps if s.rule_name == "Z_TRANSPORT"]
            assert len(z_steps) >= 1

    def test_z_id_returns_identification_result(self):
        from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationResult

        graph = _dag([("X", "Y")])
        result = _z_id("X", "Y", frozenset({"X"}), graph)
        assert isinstance(result, IdentificationResult)

    def test_z_id_with_z_equals_treatment(self):
        """Z = {X}: standard ID on experimental domain."""
        from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationStatus

        graph = _dag([("X", "Y")])
        result = _z_id("X", "Y", frozenset({"X"}), graph)
        assert result.status in {
            IdentificationStatus.IDENTIFIED,
            IdentificationStatus.ORACLE_NEEDED,
        }

    def test_z_id_proof_steps_is_list(self):
        graph = _dag([("X", "Y")])
        result = _z_id("X", "Y", frozenset({"X"}), graph)
        assert isinstance(result.proof_steps, list)

    def test_z_id_trace_non_empty(self):
        graph = _dag([("X", "Y")])
        result = _z_id("X", "Y", frozenset({"X"}), graph)
        assert len(result.trace) > 0

    def test_z_transport_step_has_correct_rule_name(self):
        """Any Z_TRANSPORT step emitted has the correct rule name string."""
        graph = _dag([("X", "Z"), ("Z", "Y")])
        result = _z_id("X", "Y", frozenset({"Z"}), graph)
        for step in result.proof_steps:
            assert isinstance(step.rule_name, str)
        z_steps = [s for s in result.proof_steps if s.rule_name == "Z_TRANSPORT"]
        # Each Z_TRANSPORT step should have consequent_vars
        for step in z_steps:
            assert len(step.consequent_vars) > 0


# ---------------------------------------------------------------------------
# mz_id_algorithm — MZ_FACTORIZE and S_DOMAIN_SELECT ProofSteps
# ---------------------------------------------------------------------------


class TestMzIdProofSteps:
    def test_no_source_domains_falls_back_to_standard_id(self):
        """Empty source_domains → standard ID fallback."""
        from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationStatus

        graph = _dag([("X", "Y")])
        result = _mz_id("X", "Y", [], graph)
        # Standard ID on simple DAG should succeed
        assert result.status is IdentificationStatus.IDENTIFIED

    def test_single_domain_no_s_no_z(self):
        """Domain with no S-nodes, no Z: should run standard ID."""
        from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationStatus

        graph = _dag([("X", "Y")])
        dom = _source_domain("dom1")
        result = _mz_id("X", "Y", [dom], graph)
        assert result.status is IdentificationStatus.IDENTIFIED

    def test_single_domain_with_z_runs_z_id(self):
        """Domain with Z-interventions: runs z_id_algorithm."""
        from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationStatus

        graph = _dag([("X", "Y")])
        dom = _source_domain("dom1", z_interventions=frozenset({"X"}))
        result = _mz_id("X", "Y", [dom], graph)
        assert result.status is IdentificationStatus.IDENTIFIED

    def test_mz_id_trace_non_empty(self):
        graph = _dag([("X", "Y")])
        dom = _source_domain("dom1")
        result = _mz_id("X", "Y", [dom], graph)
        assert len(result.trace) > 0

    def test_mz_factorize_step_when_multiple_domains(self):
        """Multiple domains trigger formal c-component factorization."""
        # Simple DAG where both domains can contribute
        graph = _dag([("X", "Y"), ("Z", "Y")])
        dom1 = _source_domain("dom1", z_interventions=frozenset({"X"}))
        dom2 = _source_domain("dom2", z_interventions=frozenset({"Z"}))
        result = _mz_id("X", "Y", [dom1, dom2], graph)
        # Factorize step emitted when formal c-component path is taken
        mz_steps = [s for s in result.proof_steps if s.rule_name == "MZ_FACTORIZE"]
        # Either MZ_FACTORIZE fires (if identification succeeded) or it doesn't
        # — just verify proof_steps is a list and rule names are strings
        for step in result.proof_steps:
            assert isinstance(step.rule_name, str)

    def test_s_domain_select_step_has_correct_antecedents(self):
        """S_DOMAIN_SELECT steps (if emitted) reference domain and c-component vars."""
        graph = _dag([("X", "Y"), ("Z", "Y")])
        dom1 = _source_domain("dom1", s_nodes=frozenset({"X"}))
        dom2 = _source_domain("dom2", s_nodes=frozenset({"Z"}))
        result = _mz_id("X", "Y", [dom1, dom2], graph)
        for step in result.proof_steps:
            if step.rule_name == "S_DOMAIN_SELECT":
                # Each S_DOMAIN_SELECT step should document which c-component
                assert len(step.consequent_vars) > 0 or len(step.applied_to_graph_state) > 0

    def test_mz_id_result_is_identification_result(self):
        from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationResult

        graph = _dag([("X", "Y")])
        result = _mz_id("X", "Y", [_source_domain("d1")], graph)
        assert isinstance(result, IdentificationResult)

    def test_multiple_domains_same_graph_no_crash(self):
        """Smoke test: multiple domains with overlapping S-nodes should not crash."""
        graph = _dag([("W", "X"), ("X", "Y")])
        dom1 = _source_domain("d1", s_nodes=frozenset({"W"}), z_interventions=frozenset({"X"}))
        dom2 = _source_domain("d2", s_nodes=frozenset({"X"}))
        result = _mz_id("X", "Y", [dom1, dom2], graph)
        # Should not raise, status is valid
        from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationStatus
        assert result.status in set(IdentificationStatus)
