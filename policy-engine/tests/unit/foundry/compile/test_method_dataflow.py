from __future__ import annotations

from dataclasses import replace

import pytest

from polisyos.core.contracts.execution_plan import ExecutionPlan, MethodDagNode
from polisyos.foundry.methods.base import SlotSpec, SlotType, Unit
from polisyos.foundry.methods.catalog.policy.evaluation import ExAnteSimulationEstimator
from polisyos.foundry.methods.selection.registry import MethodRegistry


def _signature(*, name: str, inputs: dict[str, SlotSpec], outputs: dict[str, SlotSpec]):
    template = ExAnteSimulationEstimator.signature
    return replace(
        template,
        namespace="test.method_dataflow",
        name=name,
        input_slots=frozenset(inputs.values()),
        output_slots=frozenset(outputs.values()),
    )


def _register(signature):
    class Method:
        metadata = ExAnteSimulationEstimator.metadata
        pure_step = staticmethod(lambda state, params: {})

    Method.signature = signature
    MethodRegistry.get_instance().register(Method, override=True)
    return signature


def _node(signature, *, node_id, input_ports=None, depends_on=None, state_writes=None):
    fields = {
        "node_id": node_id,
        "method_fqn": signature.fqn,
        "method_version": signature.version,
        "backend": signature.execution_backend.value,
        "reads_slots": sorted(signature.input_slot_names),
        "writes_slots": sorted(signature.output_slot_names),
        "depends_on": list(depends_on or ()),
        "state_writes": state_writes,
    }
    if input_ports is not None:
        fields["input_ports"] = input_ports
    return MethodDagNode(
        **fields,
    )


def _pair(
    *,
    source_unit=None,
    target_unit=None,
    source_shape=(),
    target_shape=(),
    source_type=SlotType.SCALAR,
    target_type=SlotType.SCALAR,
):
    unit_a = source_unit or Unit("currency", "USD")
    unit_b = target_unit or Unit("currency", "USD")
    producer = _register(
        _signature(
            name="producer",
            inputs={"seed": SlotSpec("seed", SlotType.SCALAR, unit_a)},
            outputs={"result": SlotSpec("result", source_type, unit_a, shape=source_shape)},
        )
    )
    consumer = _register(
        _signature(
            name="consumer",
            inputs={
                "renamed_input": SlotSpec("renamed_input", target_type, unit_b, shape=target_shape)
            },
            outputs={"summary": SlotSpec("summary", SlotType.SCALAR, unit_b)},
        )
    )
    return producer, consumer


def _plan(producer, consumer, *, producer_node_id="producer.node", source=None, **producer_kwargs):
    return ExecutionPlan(
        plan_id="method-dataflow-test",
        schema_version="1.2",
        method_dag=[
            _node(producer, node_id=producer_node_id, **producer_kwargs),
            _node(
                consumer,
                node_id="consumer.node",
                input_ports={
                    "renamed_input": {
                        "source_kind": "method_output",
                        "producer_node_id": producer_node_id if source is None else source[0],
                        "output_slot_id": "result" if source is None else source[1],
                    }
                },
            ),
        ],
    )


def test_method_output_binding_resolves_exact_nodes_and_derives_dependency() -> None:
    from polisyos.foundry.compile.method_dataflow import resolve_method_output_input_bindings

    producer, consumer = _pair()
    plan = _plan(
        producer,
        consumer,
        producer_node_id="producer.instance.alpha",
        state_writes=["government.balance"],
    )

    resolution = resolve_method_output_input_bindings(plan, registry=MethodRegistry.get_instance())

    assert len(resolution.bindings) == 1
    binding = resolution.bindings[0]
    assert binding.producer_node_id == "producer.instance.alpha"
    assert binding.producer_output_slot_id == "result"
    assert binding.consumer_node_id == "consumer.node"
    assert binding.consumer_input_slot_id == "renamed_input"
    assert binding.producer_abi_digest == producer.abi_digest()
    assert binding.consumer_abi_digest == consumer.abi_digest()
    assert resolution.dependency_edges == (("producer.instance.alpha", "consumer.node"),)
    assert resolution.execution_order.index("producer.instance.alpha") < (
        resolution.execution_order.index("consumer.node")
    )


def test_method_output_binding_disambiguates_repeated_fqn_instances() -> None:
    from polisyos.core.contracts.method_input import MethodOutputInputPortSource
    from polisyos.foundry.compile.method_dataflow import resolve_method_output_input_bindings

    producer, consumer = _pair()
    plan = ExecutionPlan(
        plan_id="repeated-method-fqn-dataflow",
        schema_version="1.2",
        method_dag=[
            _node(producer, node_id="producer.first"),
            _node(producer, node_id="producer.second"),
            _node(
                consumer,
                node_id="consumer.node",
                input_ports={
                    "renamed_input": MethodOutputInputPortSource(
                        source_kind="method_output",
                        producer_node_id="producer.second",
                        output_slot_id="result",
                    )
                },
            ),
        ],
    )

    resolution = resolve_method_output_input_bindings(plan, registry=MethodRegistry.get_instance())

    assert [binding.producer_node_id for binding in resolution.bindings] == ["producer.second"]
    assert resolution.dependency_edges == (("producer.second", "consumer.node"),)


@pytest.mark.parametrize(
    ("source_unit", "target_unit", "source_shape", "target_shape", "source_type", "target_type"),
    [
        (
            Unit("currency", "USD"),
            Unit("currency", "EUR"),
            (),
            (),
            SlotType.SCALAR,
            SlotType.SCALAR,
        ),
        (
            Unit("currency", "USD"),
            Unit("currency", "USD", scale=100.0),
            (),
            (),
            SlotType.SCALAR,
            SlotType.SCALAR,
        ),
        (
            Unit("currency", "USD"),
            Unit("currency", "USD"),
            (2,),
            (),
            SlotType.VECTOR,
            SlotType.VECTOR,
        ),
    ],
)
def test_method_output_binding_rejects_implicit_unit_or_shape_adapters(
    source_unit, target_unit, source_shape, target_shape, source_type, target_type
) -> None:
    from polisyos.foundry.compile.method_dataflow import resolve_method_output_input_bindings

    producer, consumer = _pair(
        source_unit=source_unit,
        target_unit=target_unit,
        source_shape=source_shape,
        target_shape=target_shape,
        source_type=source_type,
        target_type=target_type,
    )
    plan = _plan(producer, consumer)

    with pytest.raises(ValueError, match="method_dataflow_abi_slot_contract_mismatch"):
        resolve_method_output_input_bindings(plan, registry=MethodRegistry.get_instance())


def test_method_output_binding_rejects_foreign_or_missing_output() -> None:
    from polisyos.foundry.compile.method_dataflow import resolve_method_output_input_bindings

    producer, consumer = _pair()
    plan = _plan(producer, consumer, source=("unrelated.node", "result"))
    with pytest.raises(ValueError, match="method_dataflow_producer_node_missing"):
        resolve_method_output_input_bindings(plan, registry=MethodRegistry.get_instance())

    plan = _plan(producer, consumer, source=("producer.node", "government.balance"))
    with pytest.raises(ValueError, match="method_dataflow_producer_output_slot_missing"):
        resolve_method_output_input_bindings(plan, registry=MethodRegistry.get_instance())


def test_method_output_binding_rejects_dependency_cycle() -> None:
    from polisyos.foundry.compile.method_dataflow import resolve_method_output_input_bindings

    producer, consumer = _pair()
    plan = _plan(producer, consumer, depends_on=["consumer.node"])

    with pytest.raises(ValueError, match="method_dataflow_dependency_cycle"):
        resolve_method_output_input_bindings(plan, registry=MethodRegistry.get_instance())


def test_method_output_binding_rejects_registry_version_mismatch() -> None:
    from polisyos.foundry.compile.method_dataflow import resolve_method_output_input_bindings

    producer, consumer = _pair()
    plan = _plan(producer, consumer)
    plan.method_dag[0].method_version = "9.9.9"

    with pytest.raises(ValueError, match="method_dataflow_registered_signature_identity_mismatch"):
        resolve_method_output_input_bindings(plan, registry=MethodRegistry.get_instance())
