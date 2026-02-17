from __future__ import annotations

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.foundry import ProgramEdge, ProgramGraph, ProgramNode
from polisyos.foundry.compile._graph import _slot_dependency_edges, build_exec_order


def _dummy_ir_ref() -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="ir.trinity_bundle",
        media_type="application/json",
    )


def test_build_exec_order_accepts_method_nodes_in_unified_graph() -> None:
    graph = ProgramGraph(
        ir_ref=_dummy_ir_ref(),
        nodes=[
            ProgramNode(
                node_id="method.1",
                node_kind="method",
                method_fqn="causal.inference.synthetic_control@1.0.0",
                outputs=["slot.outcome"],
            ),
            ProgramNode(
                node_id="mechanism.1",
                node_kind="mechanism",
                mechanism_type="income_tax",
                inputs=["slot.outcome"],
                outputs=["slot.tax"],
            ),
        ],
        edges=[ProgramEdge(src="method.1", dst="mechanism.1", relation="depends_on")],
    )
    order = build_exec_order(graph)
    assert order.index("method.1") < order.index("mechanism.1")


def test_slot_dependency_edges_link_method_and_mechanism_nodes() -> None:
    nodes = [
        ProgramNode(
            node_id="method.1",
            node_kind="method",
            method_fqn="causal.inference.synthetic_control@1.0.0",
            outputs=["slot.x"],
        ),
        ProgramNode(
            node_id="mechanism.1",
            node_kind="mechanism",
            mechanism_type="income_tax",
            inputs=["slot.x"],
            outputs=["slot.y"],
        ),
    ]
    edges = _slot_dependency_edges(nodes)
    assert any(edge.src == "method.1" and edge.dst == "mechanism.1" for edge in edges)
