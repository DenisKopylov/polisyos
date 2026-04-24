"""Tests for S-trimming and ProofStep emission in tr_algorithm (Phase 3)."""

from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.transportability import SelectionDiagram, SNode

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


def _snode(var: str, severity: str = "medium") -> SNode:
    return SNode(
        target_variable=var,
        context_dimension="programmatic",
        source_value=0.0,
        target_value=1.0,
        delta=1.0,
        severity=severity,
    )


def _diagram(graph: CausalGraphModel, s_var_names: list[str]) -> SelectionDiagram:
    return SelectionDiagram(
        base_graph=graph,
        s_nodes=[_snode(v) for v in s_var_names],
        source_context=ContextProfile(),
        target_context=ContextProfile(),
    )


def _tr(treatment: str, outcome: str, diagram: SelectionDiagram):
    from polisyos.foundry.methods.catalog.causal.id_engine import tr_algorithm

    return tr_algorithm(
        treatment=frozenset({treatment}),
        outcome=frozenset({outcome}),
        selection_diagram=diagram,
    )


# ---------------------------------------------------------------------------
# Tests: S-node not an ancestor → trimmed
# ---------------------------------------------------------------------------


class TestSTrimLemma:
    def test_s_node_not_ancestor_is_pruned(self):
        """S_Z where Z is not an ancestor of Y: should be pruned."""
        # Graph: X → Y, Z → X (but Z is not on any path to Y that matters for S_Z)
        # Actually Z → X → Y means Z IS an ancestor of Y — let's use isolated Z
        # Graph: X → Y, W (disconnected from Y)
        graph = _dag([("X", "Y"), ("W", "X")])
        # S_V where V has no path to Y: use a node disconnected from Y's ancestors
        # We need a node that is NOT an ancestor of Y
        # Add node Q with Q → W (but W → X → Y, so W IS ancestor of Y)
        # Let's use a totally isolated node — we can't with _dag since it requires edges
        # Use: X → Y, S_node on Z where Z is in the graph but Z → X not present
        # Build manually:
        nodes = ["X", "Y", "Z"]
        edges = [CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)]
        graph2 = CausalGraphModel(graph_type=GraphType.DAG, nodes=nodes, edges=edges)
        # Z is a node but has no path to Y → S_Z should be trimmed
        diagram = _diagram(graph2, ["Z"])
        result = _tr("X", "Y", diagram)
        # Trimming means the algorithm still runs (no crash) and emits S_TRIM
        trim_steps = [s for s in result.proof_steps if s.rule_name == "S_TRIM"]
        assert len(trim_steps) >= 1, "Expected S_TRIM ProofStep for non-ancestor S-node"

    def test_s_node_ancestor_not_pruned(self):
        """S_Z where Z IS an ancestor of Y: should not be trimmed."""
        # Z → X → Y: Z is ancestor of Y
        graph = _dag([("Z", "X"), ("X", "Y")])
        diagram = _diagram(graph, ["Z"])
        result = _tr("X", "Y", diagram)
        trim_steps = [s for s in result.proof_steps if s.rule_name == "S_TRIM"]
        # Z is ancestor of Y (Z→X→Y), so it should NOT be trimmed
        assert len(trim_steps) == 0, "S_Z (ancestor of Y) should not be trimmed"

    def test_direct_s_node_not_trimmed(self):
        """S_X where X→Y: X is direct ancestor, should not be trimmed."""
        graph = _dag([("X", "Y")])
        diagram = _diagram(graph, ["X"])
        result = _tr("X", "Y", diagram)
        trim_steps = [s for s in result.proof_steps if s.rule_name == "S_TRIM"]
        assert len(trim_steps) == 0

    def test_mix_ancestor_and_non_ancestor(self):
        """Two S-nodes: one ancestor (X), one non-ancestor (W)."""
        nodes = ["X", "Y", "W"]
        edges = [CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)]
        graph = CausalGraphModel(graph_type=GraphType.DAG, nodes=nodes, edges=edges)
        diagram = _diagram(graph, ["X", "W"])
        result = _tr("X", "Y", diagram)
        trim_steps = [s for s in result.proof_steps if s.rule_name == "S_TRIM"]
        # W is not ancestor of Y → trimmed; X is → not trimmed
        # At least one S_TRIM step expected
        assert len(trim_steps) >= 1

    def test_no_s_nodes_no_trim_step(self):
        """No S-nodes → no S_TRIM steps."""
        graph = _dag([("X", "Y")])
        diagram = _diagram(graph, [])  # no S-nodes
        result = _tr("X", "Y", diagram)
        trim_steps = [s for s in result.proof_steps if s.rule_name == "S_TRIM"]
        assert len(trim_steps) == 0


# ---------------------------------------------------------------------------
# Tests: S_AUGMENT ProofStep emission
# ---------------------------------------------------------------------------


class TestSAugmentProofStep:
    def test_s_augment_emitted_when_s_nodes_remain(self):
        """S_AUGMENT step emitted for non-pruned S-nodes."""
        graph = _dag([("X", "Y")])
        diagram = _diagram(graph, ["X"])
        result = _tr("X", "Y", diagram)
        aug_steps = [s for s in result.proof_steps if s.rule_name == "S_AUGMENT"]
        assert len(aug_steps) >= 1

    def test_s_augment_not_emitted_when_all_trimmed(self):
        """If all S-nodes are trimmed, S_AUGMENT step is NOT emitted."""
        nodes = ["X", "Y", "W"]
        edges = [CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)]
        graph = CausalGraphModel(graph_type=GraphType.DAG, nodes=nodes, edges=edges)
        diagram = _diagram(graph, ["W"])
        result = _tr("X", "Y", diagram)
        aug_steps = [s for s in result.proof_steps if s.rule_name == "S_AUGMENT"]
        assert len(aug_steps) == 0, "S_AUGMENT should not fire when all S-nodes were trimmed"

    def test_s_augment_step_lists_remaining_s_nodes(self):
        graph = _dag([("X", "Y")])
        diagram = _diagram(graph, ["X"])
        result = _tr("X", "Y", diagram)
        aug = next((s for s in result.proof_steps if s.rule_name == "S_AUGMENT"), None)
        assert aug is not None
        # antecedent_vars should contain "S_X"
        assert "S_X" in aug.antecedent_vars


# ---------------------------------------------------------------------------
# Tests: Identification correctness
# ---------------------------------------------------------------------------


class TestTrAlgorithmIdentification:
    def test_no_s_nodes_identifies_simple_dag(self):
        """Without S-nodes, tr_algorithm falls through to standard ID."""
        from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationStatus

        graph = _dag([("X", "Y")])
        diagram = _diagram(graph, [])
        result = _tr("X", "Y", diagram)
        assert result.status is IdentificationStatus.IDENTIFIED

    def test_invalid_selection_diagram_type_returns_oracle_needed(self):
        from polisyos.foundry.methods.catalog.causal.id_engine import (
            IdentificationStatus,
            tr_algorithm,
        )

        result = tr_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            selection_diagram="not_a_diagram",
        )
        assert result.status is IdentificationStatus.ORACLE_NEEDED

    def test_tr_returns_identification_result(self):
        from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationResult

        graph = _dag([("X", "Y")])
        diagram = _diagram(graph, [])
        result = _tr("X", "Y", diagram)
        assert isinstance(result, IdentificationResult)

    def test_proof_steps_is_list(self):
        graph = _dag([("X", "Y")])
        diagram = _diagram(graph, ["X"])
        result = _tr("X", "Y", diagram)
        assert isinstance(result.proof_steps, list)

    def test_trace_is_non_empty(self):
        graph = _dag([("X", "Y")])
        diagram = _diagram(graph, [])
        result = _tr("X", "Y", diagram)
        assert len(result.trace) > 0
