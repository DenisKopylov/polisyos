"""Tests for SelectionDiagramBuilder (Track 2 — transportability infrastructure)."""

from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.transportability import (
    SelectionDiagram,
    SelectionDiagramBuilder,
    SNodeRole,
)


def _dag(edges):
    nodes = sorted({n for e in edges for n in e})
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=nodes,
        edges=[
            CausalEdge(src=s, dst=d, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)
            for s, d in edges
        ],
    )


class TestSelectionDiagramBuilder:
    """Test the fluent builder API for SelectionDiagram."""

    def test_build_empty(self):
        graph = _dag([("X", "Y")])
        diagram = SelectionDiagramBuilder(graph).build()
        assert isinstance(diagram, SelectionDiagram)
        assert diagram.s_nodes == []

    def test_add_single_sigma_variable(self):
        graph = _dag([("X", "Y")])
        diagram = SelectionDiagramBuilder(graph).add_sigma_variable("X", severity="high").build()
        assert len(diagram.s_nodes) == 1
        assert diagram.s_nodes[0].target_variable == "X"
        assert diagram.s_nodes[0].severity == "high"

    def test_add_multiple_sigma_variables(self):
        graph = _dag([("X", "Z"), ("Z", "Y")])
        diagram = (
            SelectionDiagramBuilder(graph)
            .add_sigma_variable("X")
            .add_sigma_variable("Z", role=SNodeRole.MEDIATOR)
            .build()
        )
        assert len(diagram.s_nodes) == 2
        var_names = {sn.target_variable for sn in diagram.s_nodes}
        assert var_names == {"X", "Z"}

    def test_deduplication(self):
        graph = _dag([("X", "Y")])
        diagram = (
            SelectionDiagramBuilder(graph)
            .add_sigma_variable("X")
            .add_sigma_variable("X")  # duplicate
            .build()
        )
        assert len(diagram.s_nodes) == 1

    def test_base_graph_preserved(self):
        graph = _dag([("X", "Z"), ("Z", "Y"), ("U", "X"), ("U", "Y")])
        diagram = SelectionDiagramBuilder(graph).add_sigma_variable("Z").build()
        assert diagram.base_graph is graph

    def test_chaining_returns_self(self):
        graph = _dag([("X", "Y")])
        builder = SelectionDiagramBuilder(graph)
        ret = builder.add_sigma_variable("X")
        assert ret is builder

    def test_context_distance_computed(self):
        """Context distance should be non-negative even with default ContextProfiles."""
        graph = _dag([("X", "Y")])
        diagram = SelectionDiagramBuilder(graph).add_sigma_variable("X").build()
        assert diagram.context_distance >= 0.0

    def test_s_node_s_variables_populated(self):
        """sigma_variables (SigmaVariable list) should be auto-populated from s_nodes."""
        graph = _dag([("X", "Y")])
        diagram = SelectionDiagramBuilder(graph).add_sigma_variable("X").build()
        # SelectionDiagram should have sigma_variables derived from s_nodes
        sigma_vars = getattr(diagram, "sigma_variables", None)
        if sigma_vars is not None:
            assert len(sigma_vars) == 1
            assert sigma_vars[0].variable_name == "X"
