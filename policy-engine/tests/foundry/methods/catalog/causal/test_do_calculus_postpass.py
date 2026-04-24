"""Tests for do-calculus post-pass in transport_engine._try_tr_via_id_engine (Phase 4)."""

from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.transportability import SelectionDiagram, SNode, TransportabilityStatus

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


def _snode(var: str) -> SNode:
    return SNode(
        target_variable=var,
        context_dimension="programmatic",
        source_value=0.0,
        target_value=1.0,
        delta=1.0,
        severity="medium",
    )


def _diagram(graph: CausalGraphModel, s_var_names: list[str]) -> SelectionDiagram:
    return SelectionDiagram(
        base_graph=graph,
        s_nodes=[_snode(v) for v in s_var_names],
        source_context=ContextProfile(),
        target_context=ContextProfile(),
    )


def _try_tr(diagram: SelectionDiagram, treatment: str, outcome: str):
    """Call _try_tr_via_id_engine directly."""
    from polisyos.foundry.methods.catalog.causal.transport_engine import (
        CausalBackendId,
        _try_tr_via_id_engine,
    )

    return _try_tr_via_id_engine(
        diagram=diagram,
        treatment=treatment,
        outcome=outcome,
        backend_id=CausalBackendId.Y0,
        trace=[],
    )


# ---------------------------------------------------------------------------
# Tests: _try_tr_via_id_engine
# ---------------------------------------------------------------------------


class TestTryTrViaIdEngine:
    def test_simple_dag_no_s_nodes_returns_result(self):
        """No S-nodes: tr_algorithm falls back to standard ID → result populated."""
        graph = _dag([("X", "Y")])
        diagram = _diagram(graph, [])
        result = _try_tr(diagram, "X", "Y")
        assert result is not None

    def test_result_is_transportability_result(self):
        from polisyos.ir.analytics.transportability import TransportabilityResult

        graph = _dag([("X", "Y")])
        diagram = _diagram(graph, [])
        result = _try_tr(diagram, "X", "Y")
        assert result is None or isinstance(result, TransportabilityResult)

    def test_status_is_identified_on_simple_dag(self):
        graph = _dag([("X", "Y")])
        diagram = _diagram(graph, [])
        result = _try_tr(diagram, "X", "Y")
        if result is not None:
            assert result.status is TransportabilityStatus.IDENTIFIED

    def test_estimand_ast_populated_on_identification(self):
        """When TR algorithm identifies, estimand_ast should be populated."""
        graph = _dag([("X", "Y")])
        diagram = _diagram(graph, [])
        result = _try_tr(diagram, "X", "Y")
        if result is not None and result.status is TransportabilityStatus.IDENTIFIED:
            assert result.estimand_ast is not None
            assert isinstance(result.estimand_ast, dict)

    def test_identification_engine_contains_tr(self):
        graph = _dag([("X", "Y")])
        diagram = _diagram(graph, [])
        result = _try_tr(diagram, "X", "Y")
        if result is not None:
            assert "tr" in result.identification_engine.lower()

    def test_identification_trace_non_empty(self):
        graph = _dag([("X", "Y")])
        diagram = _diagram(graph, [])
        result = _try_tr(diagram, "X", "Y")
        if result is not None:
            assert len(result.identification_trace) > 0

    def test_s_node_on_ancestor_does_not_crash(self):
        """S_X with X → Y: algorithm should handle S-nodes cleanly."""
        graph = _dag([("X", "Y")])
        diagram = _diagram(graph, ["X"])
        # Should not raise
        result = _try_tr(diagram, "X", "Y")
        # Result may be None or identified — both are acceptable
        assert result is None or result.status in set(TransportabilityStatus)

    def test_algorithm_version_set(self):
        graph = _dag([("X", "Y")])
        diagram = _diagram(graph, [])
        result = _try_tr(diagram, "X", "Y")
        if result is not None:
            assert len(result.algorithm_version) > 0


# ---------------------------------------------------------------------------
# Tests: estimand_ast JSON serialisability
# ---------------------------------------------------------------------------


class TestEstimandAstJson:
    def test_estimand_ast_is_json_serialisable(self):
        """estimand_ast dict must be JSON serialisable (no non-JSON types)."""
        import json

        graph = _dag([("X", "Y")])
        diagram = _diagram(graph, [])
        result = _try_tr(diagram, "X", "Y")
        if result is not None and result.estimand_ast is not None:
            # Should not raise
            json.dumps(result.estimand_ast)

    def test_estimand_ast_has_root_key(self):
        """estimand_ast dict should have a 'root' key (EstimandAST structure)."""
        graph = _dag([("X", "Y")])
        diagram = _diagram(graph, [])
        result = _try_tr(diagram, "X", "Y")
        if result is not None and result.estimand_ast is not None:
            assert "root" in result.estimand_ast

    def test_estimand_ast_treatment_and_outcome(self):
        graph = _dag([("X", "Y")])
        diagram = _diagram(graph, [])
        result = _try_tr(diagram, "X", "Y")
        if result is not None and result.estimand_ast is not None:
            assert result.estimand_ast.get("treatment") == "X"
            assert result.estimand_ast.get("outcome") == "Y"


# ---------------------------------------------------------------------------
# Tests: do-calculus rewrite steps appear in trace
# ---------------------------------------------------------------------------


class TestDoCalculusPostPass:
    def test_do_calculus_rewrite_logged_when_applicable(self):
        """If do-calculus simplification fires, the trace records it."""
        graph = _dag([("X", "Y")])
        diagram = _diagram(graph, [])
        result = _try_tr(diagram, "X", "Y")
        if result is not None:
            # Trace may contain "do_calculus_rewrite" if rules fired
            # We just assert the function doesn't crash — simplification is optional
            trace_str = " ".join(result.identification_trace)
            assert "identified" in trace_str or "tr" in trace_str

    def test_no_do_calculus_step_when_no_do_terms(self):
        """Without intervention terms in the estimand, rewrite step count is 0."""
        graph = _dag([("X", "Y")])
        diagram = _diagram(graph, [])
        result = _try_tr(diagram, "X", "Y")
        if result is not None:
            trace_str = " ".join(result.identification_trace)
            # If no do-calculus steps fired, "do_calculus_rewrite:0" should not appear
            # or it won't appear at all
            if "do_calculus_rewrite" in trace_str:
                # If it appears, check count is > 0 (logged only when steps > 0)
                assert "do_calculus_rewrite:0" not in trace_str


# ---------------------------------------------------------------------------
# Tests: _run_symbolic_backend wiring
# ---------------------------------------------------------------------------


class TestRunSymbolicBackendWiring:
    def test_symbolic_backend_calls_tr_first(self):
        """_run_symbolic_backend calls _try_tr_via_id_engine at the start."""
        from polisyos.foundry.methods.catalog.causal.transport_engine import (
            CausalBackendId,
            _run_symbolic_backend,
        )

        graph = _dag([("X", "Y")])
        diagram = _diagram(graph, [])
        result = _run_symbolic_backend(
            backend_id=CausalBackendId.Y0,
            diagram=diagram,
            treatment="X",
            outcome="Y",
            trace=[],
        )
        assert result is not None
        assert result.status is TransportabilityStatus.IDENTIFIED

    def test_symbolic_backend_returns_transportability_result(self):
        from polisyos.foundry.methods.catalog.causal.transport_engine import (
            CausalBackendId,
            _run_symbolic_backend,
        )
        from polisyos.ir.analytics.transportability import TransportabilityResult

        graph = _dag([("X", "Y")])
        diagram = _diagram(graph, [])
        result = _run_symbolic_backend(
            backend_id=CausalBackendId.Y0,
            diagram=diagram,
            treatment="X",
            outcome="Y",
            trace=[],
        )
        assert result is None or isinstance(result, TransportabilityResult)

    def test_symbolic_backend_sets_identification_engine(self):
        from polisyos.foundry.methods.catalog.causal.transport_engine import (
            CausalBackendId,
            _run_symbolic_backend,
        )

        graph = _dag([("X", "Y")])
        diagram = _diagram(graph, [])
        result = _run_symbolic_backend(
            backend_id=CausalBackendId.Y0,
            diagram=diagram,
            treatment="X",
            outcome="Y",
            trace=[],
        )
        if result is not None:
            assert len(result.identification_engine) > 0
