from __future__ import annotations

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
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
