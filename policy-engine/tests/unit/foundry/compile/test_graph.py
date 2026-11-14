from __future__ import annotations

import hashlib

import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import to_canonical_bytes
from polisyos.core.contracts.foundry import (
    LoweredIRRef,
    LoweredMechanism,
    ProgramGraph,
)
from polisyos.foundry.compile._graph import build_exec_order, build_program_graph


def _artifact_ref(kind: str = "test") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID("sha256:" + "a" * 64),
        kind=kind,
        media_type="application/json",
    )


def _lowered_ir_ref() -> LoweredIRRef:
    return LoweredIRRef(
        artifact_id=ArtifactID("sha256:" + "b" * 64),
    )


def _mechanism(
    binding_id: str,
    mechanism_id: str = "flat_tax",
    inputs: list[str] | None = None,
    outputs: list[str] | None = None,
    intervention_ids: list[str] | None = None,
) -> LoweredMechanism:
    return LoweredMechanism(
        binding_id=binding_id,
        mechanism_id=mechanism_id,
        intervention_ids=intervention_ids or [binding_id],
        inputs=inputs or [],
        outputs=outputs or [],
    )


class TestBuildProgramGraph:
    def test_single_mechanism(self) -> None:
        mech = _mechanism("b1", inputs=["income"], outputs=["tax"])
        graph, refs = build_program_graph(
            None,
            ir_ref=_artifact_ref("ir"),
            lowered_ir_ref=_lowered_ir_ref(),
            mechanisms=[mech],
            constraint_ids=[],
        )
        node_ids = [n.node_id for n in graph.nodes]
        assert "op.mask.b1" in node_ids
        assert "b1" in node_ids
        assert "op.merge_state" in node_ids
        assert "op.check_constraints" in node_ids
        assert any(e.src == "op.mask.b1" and e.dst == "b1" for e in graph.edges)

    def test_two_mechanisms_slot_dep(self) -> None:
        m1 = _mechanism("m1", inputs=["income"], outputs=["tax"])
        m2 = _mechanism("m2", mechanism_id="consumption", inputs=["tax"], outputs=["spending"])
        graph, _ = build_program_graph(
            None,
            ir_ref=_artifact_ref("ir"),
            lowered_ir_ref=_lowered_ir_ref(),
            mechanisms=[m1, m2],
            constraint_ids=[],
        )
        assert any(
            e.src == "m1" and e.dst == "m2" and e.relation == "depends_on" for e in graph.edges
        )

    def test_constraint_ids_in_check_node(self) -> None:
        mech = _mechanism("b1")
        graph, _ = build_program_graph(
            None,
            ir_ref=_artifact_ref("ir"),
            lowered_ir_ref=_lowered_ir_ref(),
            mechanisms=[mech],
            constraint_ids=["c1", "c2"],
        )
        check_node = next(n for n in graph.nodes if n.node_id == "op.check_constraints")
        assert check_node.op.params["constraint_ids"] == ["c1", "c2"]

    def test_entrypoints_are_roots(self) -> None:
        mech = _mechanism("b1")
        graph, _ = build_program_graph(
            None,
            ir_ref=_artifact_ref("ir"),
            lowered_ir_ref=_lowered_ir_ref(),
            mechanisms=[mech],
            constraint_ids=[],
        )
        dst_set = {e.dst for e in graph.edges}
        for ep in graph.entrypoints:
            assert ep not in dst_set


class TestBuildExecOrder:
    def test_topological_order(self) -> None:
        mech = _mechanism("b1")
        graph, _ = build_program_graph(
            None,
            ir_ref=_artifact_ref("ir"),
            lowered_ir_ref=_lowered_ir_ref(),
            mechanisms=[mech],
            constraint_ids=[],
        )
        order = build_exec_order(graph)
        assert order.index("op.mask.b1") < order.index("b1")
        assert order.index("b1") < order.index("op.merge_state")
        assert order.index("op.merge_state") < order.index("op.check_constraints")

    def test_empty_graph(self) -> None:
        graph = ProgramGraph(
            ir_ref=_artifact_ref("ir"),
            nodes=[],
            edges=[],
            entrypoints=[],
        )
        assert build_exec_order(graph) == []


def test_program_graph_v02_keeps_legacy_wire_and_rejects_input_port_maps() -> None:
    node = {
        "node_id": "method-a",
        "node_kind": "method",
        "method_fqn": "policy.example@1.0.0",
        "inputs": ["ledger.flow"],
    }
    graph = ProgramGraph(ir_ref=_artifact_ref("ir"), nodes=[node])

    assert graph.schema_version == "0.2"
    assert graph.artifact_schema_version == "0.2.0"
    legacy_node = graph.to_artifact_payload()["nodes"][0]
    assert legacy_node["node_id"] == node["node_id"]
    assert legacy_node["method_fqn"] == node["method_fqn"]
    assert legacy_node["inputs"] == node["inputs"]
    assert "input_ports" not in legacy_node
    assert hashlib.sha256(to_canonical_bytes(graph)).hexdigest() == (
        "8db5fffa2aee868a86db50d291af9f1503474a82812b8476a7a757835efbcdfc"
    )
    with pytest.raises(ValueError, match="program_graph_input_ports_version_mismatch"):
        ProgramGraph(
            ir_ref=_artifact_ref("ir"),
            nodes=[
                {
                    **node,
                    "input_ports": {
                        "period_flow": {"source_kind": "registry_slot", "slot_id": "ledger.flow"}
                    },
                }
            ],
        )


def test_program_graph_v03_requires_complete_maps_and_projects_registry_slots() -> None:
    source = {"source_kind": "registry_slot", "slot_id": "ledger.flow"}
    node = {
        "node_id": "method-a",
        "node_kind": "method",
        "method_fqn": "policy.example@1.0.0",
        "inputs": ["ledger.flow"],
        "input_ports": {"period_flow": source, "baseline_flow": source},
    }
    graph = ProgramGraph(
        ir_ref=_artifact_ref("ir"),
        schema_version="0.3",
        nodes=[node],
    )

    assert graph.artifact_schema_version == "0.3.0"
    assert graph.ARTIFACT_PAYLOAD_SCHEMA_VERSION_BY_MANIFEST[graph.artifact_schema_version] == "0.3"
    assert graph.to_artifact_payload()["nodes"][0]["input_ports"] == node["input_ports"]

    with pytest.raises(ValueError, match="program_graph_input_ports_missing"):
        ProgramGraph(
            ir_ref=_artifact_ref("ir"),
            schema_version="0.3",
            nodes=[
                node,
                {
                    "node_id": "method-b",
                    "node_kind": "method",
                    "method_fqn": "policy.other@1.0.0",
                    "inputs": [],
                },
            ],
        )
    with pytest.raises(
        ValueError,
        match="program_graph_input_ports_registry_projection_mismatch",
    ):
        ProgramGraph(
            ir_ref=_artifact_ref("ir"),
            schema_version="0.3",
            nodes=[{**node, "inputs": ["wrong.slot"]}],
        )


def test_program_graph_v03_represents_method_output_source_structurally() -> None:
    graph = ProgramGraph(
        ir_ref=_artifact_ref("ir"),
        schema_version="0.3",
        nodes=[
            {
                "node_id": "consumer",
                "node_kind": "method",
                "method_fqn": "policy.example@1.0.0",
                "input_ports": {
                    "period_flow": {
                        "source_kind": "method_output",
                        "producer_node_id": "producer",
                        "output_slot_id": "derived.flow",
                    }
                },
                "inputs": [],
            }
        ],
    )

    assert graph.to_artifact_payload()["nodes"][0]["input_ports"]["period_flow"] == {
        "source_kind": "method_output",
        "producer_node_id": "producer",
        "output_slot_id": "derived.flow",
    }


def test_program_graph_v03_projection_is_canonical_order_independent() -> None:
    from polisyos.core.canon import to_canonical_bytes

    source_by_port = {
        "z_port": {"source_kind": "registry_slot", "slot_id": "slot.a"},
        "a_port": {"source_kind": "registry_slot", "slot_id": "slot.z"},
        "alias_port": {"source_kind": "registry_slot", "slot_id": "slot.a"},
    }

    def graph_for(ports: dict[str, dict[str, str]]) -> ProgramGraph:
        return ProgramGraph(
            ir_ref=_artifact_ref("ir"),
            schema_version="0.3",
            nodes=[
                {
                    "node_id": "method-a",
                    "node_kind": "method",
                    "method_fqn": "policy.example@1.0.0",
                    "inputs": ["slot.a", "slot.z"],
                    "input_ports": ports,
                }
            ],
        )

    first = graph_for(source_by_port)
    second = graph_for(dict(reversed(tuple(source_by_port.items()))))
    first_bytes = to_canonical_bytes(first)
    second_bytes = to_canonical_bytes(second)

    assert first.nodes[0].inputs == ["slot.a", "slot.z"]
    assert second.nodes[0].inputs == ["slot.a", "slot.z"]
    assert first_bytes == second_bytes
    assert ProgramGraph.model_validate_json(first_bytes) == first
    assert ProgramGraph.model_validate_json(second_bytes) == second
