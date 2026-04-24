from __future__ import annotations

from decimal import Decimal

import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.foundry import (
    CompileRequest,
    ProgramEdge,
    ProgramGraph,
    ProgramNode,
    ProgramOp,
)
from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
from polisyos.foundry.compile._graph import build_exec_order
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.types import SelectorOperator


def _put_trinity_bundle(store: FileSystemCAS, registry_bundle_ref: str) -> object:
    bundle = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="problem_1", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="policy_1",
            interventions=[
                InterventionSpec(
                    intervention_id="tax_cut",
                    kind="income_tax",
                    target=SelectorPredicate(
                        field="id",
                        operator=SelectorOperator.EQUALS,
                        value="all",
                    ),
                    schedule=ScheduleSpec(start_step=0, duration_steps=1),
                    params={"rate": Decimal("0.1")},
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="model_1",
            data_snapshot_ref="sha256:0000000000000000000000000000000000000000000000000000000000000000",
            registry_bundle_ref=registry_bundle_ref,
        ),
    )
    return store.put_json(
        bundle,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version=bundle.schema_version),
        ),
    )


def test_program_graph_includes_op_nodes(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store)
    load_registry_bundle_content(store, bundle.bundle_ref)
    policy_ref = _put_trinity_bundle(store, str(bundle.bundle_ref.artifact_id))
    result = compile_foundry(
        store,
        CompileRequest(
            input_kind="trinity",
            policy_ref=policy_ref,
            registry_bundle_ref=bundle.bundle_ref,
        ),
    )
    assert result.ok
    program_ref = next(ref.ref for ref in result.derived_refs if ref.role == "program_graph")
    payload = from_canonical_bytes(store.get_bytes(program_ref.artifact_id))
    graph = ProgramGraph.model_validate(payload)
    assert graph.lowered_ir_ref is not None
    kinds = {node.op.op_kind for node in graph.nodes if node.node_kind == "op" and node.op}
    assert "merge_state" in kinds
    assert "check_constraints" in kinds


def test_build_exec_order_rejects_cycles() -> None:
    ir_ref = ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex("0" * 64),
        kind="ir.trinity_bundle",
        media_type="application/json",
    )
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
        build_exec_order(graph)
