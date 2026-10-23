from __future__ import annotations

import pytest

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


def test_build_program_graph_adapts_the_selected_execution_plan_method_dag():
    from polisyos.core.contracts.execution_plan import ExecutionPlan, MethodDagNode
    from polisyos.core.contracts.foundry import LoweredIRRef
    from polisyos.foundry.compile._graph import build_program_graph
    from polisyos.foundry.methods.catalog.policy.evaluation import ExAnteSimulationEstimator
    from polisyos.foundry.methods.registry import MethodRegistry

    MethodRegistry.get_instance().register(ExAnteSimulationEstimator, override=True)
    signature = ExAnteSimulationEstimator.signature
    planned = MethodDagNode(
        node_id="ex_ante_node",
        method_fqn=signature.fqn,
        method_version=signature.version,
        backend=signature.execution_backend.value,
        params={"poverty_line": None},
        reads_slots=["baseline", "scenario"],
        writes_slots=["result"],
    )
    plan = ExecutionPlan(plan_id="selected-ex-ante", method_dag=[planned])
    lowered_ref = LoweredIRRef(
        artifact_id="sha256:" + "b" * 64,
        kind="foundry.lowered_ir",
        media_type="application/json",
    )

    graph, _ = build_program_graph(
        None,
        ir_ref=_dummy_ir_ref(),
        lowered_ir_ref=lowered_ref,
        mechanisms=[],
        constraint_ids=[],
        method_plan=plan,
    )

    method = next(node for node in graph.nodes if node.node_id == "ex_ante_node")
    assert method.node_kind == "method"
    assert method.method_fqn == signature.fqn
    assert method.method_version == signature.version
    assert method.method_params == {"poverty_line": None}
    assert method.inputs == ["baseline", "scenario"]
    assert method.outputs == []


def _plan_for(nodes, edges=()):
    from polisyos.core.contracts.execution_plan import ExecutionPlan

    return ExecutionPlan(plan_id="ad01-test-plan", method_dag=list(nodes), method_edges=list(edges))


def _build_selected_plan(plan, mechanisms=()):
    from polisyos.core.contracts.foundry import LoweredIRRef
    from polisyos.foundry.compile._graph import build_program_graph

    return build_program_graph(
        None,
        ir_ref=_dummy_ir_ref(),
        lowered_ir_ref=LoweredIRRef(
            artifact_id="sha256:" + "b" * 64,
            kind="foundry.lowered_ir",
            media_type="application/json",
        ),
        mechanisms=list(mechanisms),
        constraint_ids=[],
        method_plan=plan,
    )[0]


def _registered_method_signature():
    from polisyos.foundry.methods.catalog.policy.evaluation import ExAnteSimulationEstimator
    from polisyos.foundry.methods.registry import MethodRegistry

    registry = MethodRegistry.get_instance()
    registry.register(ExAnteSimulationEstimator, override=True)
    return ExAnteSimulationEstimator.signature


def _method_dag_node(signature, *, node_id, reads=None, writes=None, depends_on=None):
    from polisyos.core.contracts.execution_plan import MethodDagNode

    return MethodDagNode(
        node_id=node_id,
        method_fqn=signature.fqn,
        method_version=signature.version,
        backend=signature.execution_backend.value,
        params={"poverty_line": None},
        reads_slots=list(
            reads if reads is not None else sorted(s.name for s in signature.input_slots)
        ),
        writes_slots=list(
            writes if writes is not None else sorted(s.name for s in signature.output_slots)
        ),
        depends_on=list(depends_on or []),
    )


def _register_consumer_signature(*, alias):
    from dataclasses import replace

    from polisyos.foundry.methods.catalog.policy.evaluation import ExAnteSimulationEstimator
    from polisyos.foundry.methods.registry import MethodRegistry

    source = ExAnteSimulationEstimator.signature
    scenario = next(slot for slot in source.input_slots if slot.name == "scenario")
    input_name = "result_alias" if alias else "result"
    inputs = frozenset({replace(scenario, name="scenario"), replace(scenario, name=input_name)})
    output = next(iter(source.output_slots))
    signature = replace(
        source,
        namespace="test.ad01",
        name="consumer_alias" if alias else "consumer_result",
        input_slots=inputs,
        output_slots=frozenset({replace(output, name="consumer_out")}),
    )

    class ConsumerMethod:
        metadata = ExAnteSimulationEstimator.metadata
        pure_step = staticmethod(lambda state, params: {"consumer_out": state})

    ConsumerMethod.signature = signature
    MethodRegistry.get_instance().register(ConsumerMethod, override=True)
    return signature


def test_selected_pure_method_return_is_not_a_program_state_patch() -> None:
    from polisyos.core.contracts.execution_plan import ExecutionPlan
    from polisyos.foundry.methods.base import MethodKind
    from polisyos.foundry.methods.catalog.policy.evaluation import ExAnteSimulationEstimator
    from polisyos.foundry.methods.registry import MethodRegistry

    signature = ExAnteSimulationEstimator.signature
    MethodRegistry.get_instance().register(ExAnteSimulationEstimator, override=True)
    assert signature.kind is MethodKind.PURE
    plan = ExecutionPlan(
        plan_id="ad01-pure-return",
        method_dag=[_method_dag_node(signature, node_id="producer")],
    )
    graph = _build_selected_plan(plan)
    method = next(node for node in graph.nodes if node.node_id == "producer")
    assert method.outputs == []
    assert sorted(method.inputs) == ["baseline", "scenario"]


def test_selected_method_plan_rejects_registered_return_slot_mismatch() -> None:
    signature = _registered_method_signature()
    plan = _plan_for(
        [
            _method_dag_node(signature, node_id="producer", writes=["not_the_registered_result"]),
        ]
    )
    with pytest.raises(ValueError, match="execution_plan_method_slots_mismatch"):
        _build_selected_plan(plan)


def test_selected_method_plan_rejects_return_slot_consumer_even_with_wrong_dependency() -> None:
    from polisyos.core.contracts.execution_plan import MethodDagEdge

    producer_sig = _registered_method_signature()
    consumer_sig = _register_consumer_signature(alias=False)
    producer = _method_dag_node(producer_sig, node_id="producer")
    consumer = _method_dag_node(consumer_sig, node_id="consumer", reads=["result", "scenario"])
    plan = _plan_for([producer, consumer], [MethodDagEdge(src="consumer", dst="producer")])
    with pytest.raises(ValueError, match="execution_plan_method_return_slot_consumer_unsupported"):
        _build_selected_plan(plan)


def test_selected_method_plan_rejects_return_slot_alias_through_declared_dependency() -> None:
    from polisyos.core.contracts.execution_plan import MethodDagEdge

    producer_sig = _registered_method_signature()
    consumer_sig = _register_consumer_signature(alias=True)
    producer = _method_dag_node(producer_sig, node_id="producer")
    consumer = _method_dag_node(
        consumer_sig,
        node_id="consumer",
        reads=["result_alias", "scenario"],
        depends_on=["producer"],
    )
    plan = _plan_for([producer, consumer], [MethodDagEdge(src="producer", dst="consumer")])
    with pytest.raises(ValueError, match="execution_plan_method_return_slot_consumer_unsupported"):
        _build_selected_plan(plan)


def test_selected_method_plan_rejects_non_pure_method_before_graph_creation() -> None:
    from dataclasses import replace

    from polisyos.core.contracts.execution_plan import ExecutionPlan
    from polisyos.foundry.methods.base import MethodKind
    from polisyos.foundry.methods.catalog.policy.evaluation import ExAnteSimulationEstimator
    from polisyos.foundry.methods.registry import MethodRegistry

    source = ExAnteSimulationEstimator.signature
    signature = replace(
        source, namespace="test.ad01", name="non_pure_method", kind=MethodKind.MECHANISM
    )

    class NonPureMethod:
        metadata = ExAnteSimulationEstimator.metadata
        pure_step = staticmethod(lambda state, params: {"result": state})

    NonPureMethod.signature = signature
    MethodRegistry.get_instance().register(NonPureMethod, override=True)
    plan = ExecutionPlan(
        plan_id="ad01-non-pure",
        method_dag=[_method_dag_node(signature, node_id="mechanism")],
    )
    with pytest.raises(ValueError, match="execution_plan_method_kind_unsupported"):
        _build_selected_plan(plan)


def test_selected_method_plan_refuses_lowered_mechanism_consuming_return_slot() -> None:
    from polisyos.core.contracts.execution_plan import ExecutionPlan
    from polisyos.core.contracts.foundry import LoweredMechanism

    signature = _registered_method_signature()
    plan = ExecutionPlan(
        plan_id="ad01-cross-plane-consumer",
        method_dag=[_method_dag_node(signature, node_id="producer")],
    )
    mechanism = LoweredMechanism(
        binding_id="consume-result",
        mechanism_id="test_mechanism",
        inputs=["result"],
        outputs=["tax"],
    )
    with pytest.raises(ValueError, match="execution_plan_method_return_slot_consumer_unsupported"):
        _build_selected_plan(plan, mechanisms=[mechanism])
