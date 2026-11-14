"""Resolve typed method-output input bindings for the compiled method DAG.

This module validates compile-time bindings only. Runtime value transfer and
durable output/input capture remain owned by the graph executor.
"""

from __future__ import annotations

from dataclasses import dataclass
from graphlib import CycleError, TopologicalSorter

from polisyos.core.contracts import ExecutionPlan, MethodOutputInputPortSource
from polisyos.foundry.methods.base import MethodSignature
from polisyos.foundry.methods.selection.registry import MethodRegistry
from polisyos.foundry.methods.types.checker import check_slot_compatibility


@dataclass(frozen=True, slots=True)
class MethodOutputInputBinding:
    """One explicit output-to-input edge resolved against registered method ABIs."""

    producer_node_id: str
    producer_method_fqn: str
    producer_method_version: str
    producer_abi_digest: str
    producer_output_slot_id: str
    consumer_node_id: str
    consumer_method_fqn: str
    consumer_method_version: str
    consumer_abi_digest: str
    consumer_input_slot_id: str


@dataclass(frozen=True, slots=True)
class MethodDataflowResolution:
    """Resolved method-output bindings, dependency edges, and deterministic order."""

    bindings: tuple[MethodOutputInputBinding, ...]
    dependency_edges: tuple[tuple[str, str], ...]
    execution_order: tuple[str, ...]


def resolve_method_output_input_bindings(
    plan: ExecutionPlan,
    *,
    registry: MethodRegistry,
) -> MethodDataflowResolution:
    """Resolve every declared method-output source to exact registered ABI slots.

    The method DAG is the source for returned ABI slot names. ``state_writes``
    describes a separate patch channel and is never treated as a returned slot.
    Program graph node ``outputs`` likewise describes state patches, not method
    return values.

    Compatible transfers must already have identical unit, slot type, and shape.
    The existing slot compatibility checker is reused with strict shape matching;
    any required unit, shape, or type adapter is refused rather than applied.

    Args:
        plan: Versioned execution plan containing method nodes and explicit sources.
        registry: Selected canonical method registry for the plan's exact ABIs.

    Returns:
        Immutable output-to-input bindings and their combined DAG ordering.

    Raises:
        ValueError: If a node, source, ABI slot, type contract, dependency, or DAG
            invariant is invalid.
    """
    nodes_by_id = {node.node_id: node for node in plan.method_dag}
    if len(nodes_by_id) != len(plan.method_dag):
        raise ValueError("method_dataflow_node_ids_not_unique")

    signatures_by_node: dict[str, MethodSignature] = {}
    for node in plan.method_dag:
        signature = registry.get_signature(node.method_fqn)
        if signature is None:
            raise ValueError("method_dataflow_registered_signature_missing")
        if signature.fqn != node.method_fqn or node.method_version != signature.version:
            raise ValueError("method_dataflow_registered_signature_identity_mismatch")
        input_names = {slot.name for slot in signature.input_slots}
        output_names = {slot.name for slot in signature.output_slots}
        if (
            len(node.reads_slots) != len(set(node.reads_slots))
            or set(node.reads_slots) != input_names
            or len(node.writes_slots) != len(set(node.writes_slots))
            or set(node.writes_slots) != output_names
        ):
            raise ValueError("method_dataflow_plan_abi_slots_mismatch")
        signatures_by_node[node.node_id] = signature

    dependencies: set[tuple[str, str]] = set()
    for node in plan.method_dag:
        if len(node.depends_on) != len(set(node.depends_on)):
            raise ValueError("method_dataflow_dependencies_not_unique")
        dependencies.update((dependency, node.node_id) for dependency in node.depends_on)

    explicit_edges: set[tuple[str, str]] = set()
    for edge in plan.method_edges:
        if edge.relation != "depends_on":
            raise ValueError("method_dataflow_edge_relation_unsupported")
        edge_key = (edge.src, edge.dst)
        if edge_key in explicit_edges:
            raise ValueError("method_dataflow_edges_not_unique")
        explicit_edges.add(edge_key)
    dependencies.update(explicit_edges)
    if any(
        source not in nodes_by_id or target not in nodes_by_id for source, target in dependencies
    ):
        raise ValueError("method_dataflow_dependency_endpoint_missing")

    bindings: list[MethodOutputInputBinding] = []
    for consumer in plan.method_dag:
        if consumer.input_ports is None:
            continue
        consumer_signature = signatures_by_node[consumer.node_id]
        for input_name, source in consumer.input_ports.items():
            if not isinstance(source, MethodOutputInputPortSource):
                continue
            producer = nodes_by_id.get(source.producer_node_id)
            if producer is None:
                raise ValueError("method_dataflow_producer_node_missing")
            if producer.node_id == consumer.node_id:
                raise ValueError("method_dataflow_self_dependency")
            producer_signature = signatures_by_node[producer.node_id]
            output_slot = producer_signature.get_output_slot(source.output_slot_id)
            input_slot = consumer_signature.get_input_slot(input_name)
            if output_slot is None or source.output_slot_id not in producer.writes_slots:
                raise ValueError("method_dataflow_producer_output_slot_missing")
            if input_slot is None or input_name not in consumer.reads_slots:
                raise ValueError("method_dataflow_consumer_input_slot_missing")

            compatibility = check_slot_compatibility(
                output_slot,
                input_slot,
                strict_shape=True,
                allow_unsafe_shapes=False,
            )
            if (
                not compatibility.compatible
                or compatibility.adapter_plan.as_tuple()
                or output_slot.unit != input_slot.unit
                or output_slot.slot_type is not input_slot.slot_type
                or output_slot.shape != input_slot.shape
                or (
                    input_slot.contract_id is not None
                    and output_slot.contract_id != input_slot.contract_id
                )
            ):
                raise ValueError("method_dataflow_abi_slot_contract_mismatch")

            dependencies.add((producer.node_id, consumer.node_id))
            bindings.append(
                MethodOutputInputBinding(
                    producer_node_id=producer.node_id,
                    producer_method_fqn=producer_signature.fqn,
                    producer_method_version=producer_signature.version,
                    producer_abi_digest=producer_signature.abi_digest(),
                    producer_output_slot_id=output_slot.name,
                    consumer_node_id=consumer.node_id,
                    consumer_method_fqn=consumer_signature.fqn,
                    consumer_method_version=consumer_signature.version,
                    consumer_abi_digest=consumer_signature.abi_digest(),
                    consumer_input_slot_id=input_slot.name,
                )
            )

    sorter = TopologicalSorter()
    for node_id in sorted(nodes_by_id):
        sorter.add(node_id)
    for source, target in sorted(dependencies):
        sorter.add(target, source)
    try:
        execution_order = tuple(sorter.static_order())
    except CycleError as exc:
        raise ValueError("method_dataflow_dependency_cycle") from exc

    return MethodDataflowResolution(
        bindings=tuple(
            sorted(
                bindings,
                key=lambda binding: (
                    binding.consumer_node_id,
                    binding.consumer_input_slot_id,
                    binding.producer_node_id,
                    binding.producer_output_slot_id,
                ),
            )
        ),
        dependency_edges=tuple(sorted(dependencies)),
        execution_order=execution_order,
    )
