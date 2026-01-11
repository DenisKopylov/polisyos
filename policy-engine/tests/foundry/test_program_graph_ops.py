from __future__ import annotations

import pytest
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.foundry import (
    PolicySurfaceIRRef,
    ProgramEdge,
    ProgramGraph,
    ProgramNode,
    ProgramOp,
)
from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
from polisyos.foundry.compiler import _build_exec_order, compile_surface_policy
from polisyos.ir.surface import PolicySemantic, PolicySurfaceIR
from polisyos.ir.types import SelectorOperator


def test_program_graph_includes_op_nodes(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store)
    registries = load_registry_bundle_content(store, bundle.bundle_ref)

    policy = PolicySurfaceIR(
        semantic=PolicySemantic(
            context_snapshot_ref="sha256:0000000000000000000000000000000000000000000000000000000000000000",
            interventions=[
                {
                    "intervention_id": "tax_cut",
                    "kind": "income_tax",
                    "target": {
                        "kind": "predicate",
                        "field": "id",
                        "operator": SelectorOperator.EQUALS,
                        "value": "all",
                    },
                    "schedule": {"start_step": 0, "duration_steps": 1},
                    "params": {"rate": "0.1"},
                }
            ],
        )
    )

    artifacts = compile_surface_policy(
        store,
        policy,
        mechanism_registry=registries.mechanism_registry,
        slot_registry=registries.slot_registry,
        merge_registry=registries.merge_registry,
    )

    payload = from_canonical_bytes(store.get_bytes(artifacts.program_ref.artifact_id))
    graph = ProgramGraph.model_validate(payload)
    kinds = {node.op.op_kind for node in graph.nodes if node.node_kind == "op" and node.op}
    assert "merge_state" in kinds
    assert "check_constraints" in kinds


def test_build_exec_order_rejects_cycles() -> None:
    ir_ref = PolicySurfaceIRRef(artifact_id=ArtifactID.from_sha256_hex("0" * 64))
    nodes = [
        ProgramNode(node_id="op_a", node_kind="op", op=ProgramOp(op_kind="apply_mechanism")),
        ProgramNode(node_id="op_b", node_kind="op", op=ProgramOp(op_kind="merge_state")),
    ]
    edges = [
        ProgramEdge(src="op_a", dst="op_b", relation="depends_on"),
        ProgramEdge(src="op_b", dst="op_a", relation="depends_on"),
    ]
    graph = ProgramGraph(ir_ref=ir_ref, nodes=nodes, edges=edges, entrypoints=[])

    with pytest.raises(ValueError):
        _build_exec_order(graph)
