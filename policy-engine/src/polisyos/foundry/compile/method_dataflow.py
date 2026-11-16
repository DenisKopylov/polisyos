"""Resolve typed method-input sources for compiled method DAGs.

This module validates compile-time bindings only. Runtime value transfer and
durable output/input capture remain owned by the graph executor.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from graphlib import CycleError, TopologicalSorter
from types import MappingProxyType

from polisyos.core.contracts import (
    ExecutionPlan,
    MethodDagNode,
    MethodInputPortSource,
    MethodOutputInputPortSource,
    ProgramGraph,
    RegistrySlotInputPortSource,
)
from polisyos.core.registry import RegistryBundleContent
from polisyos.foundry.methods import MethodRegistry, resolve_selected_method_entry
from polisyos.foundry.methods.base import (
    ComputeBackend,
    MethodKind,
    MethodSignature,
    SideEffectProfile,
)
from polisyos.foundry.methods.types.checker import (
    check_slot_compatibility,
    validate_registered_method_input,
)


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
    """Resolved input source maps, dependencies, and deterministic method order."""

    bindings: tuple[MethodOutputInputBinding, ...]
    dependency_edges: tuple[tuple[str, str], ...]
    execution_order: tuple[str, ...]
    input_sources: Mapping[str, Mapping[str, MethodInputPortSource]]
    registry_inputs: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class _MethodNode:
    """One method node joined to its exact registered signature and sources."""

    node_id: str
    method_fqn: str
    method_version: str
    signature: MethodSignature
    metadata: object
    input_sources: Mapping[str, MethodInputPortSource]
    registry_inputs: tuple[str, ...]
    declared_output_slots: frozenset[str]
    state_outputs: tuple[str, ...]


def resolve_method_output_input_bindings(
    plan: ExecutionPlan,
    *,
    registry: MethodRegistry,
    registry_content: RegistryBundleContent | None = None,
    allow_method_output: bool = False,
) -> MethodDataflowResolution:
    """Resolve every plan input source against exact registered method ABIs.

    Missing maps in a mixed mapped plan are normalized to explicit identity
    registry-slot sources. The compiler must pass the selected registry bundle
    so those sources are checked against the same model registry used by
    execution. A legacy plan with no maps is represented as identity sources in
    this result, but callers preserve its Graph 0.2 wire bytes.

    A method-output source is an explicit binding to one method node occurrence,
    not a name-based slot alias. The producer is required to precede the
    consumer in the declared plan order, and the binding adds a dependency edge.

    Args:
        plan: Versioned execution plan with exact method node identifiers.
        registry: Canonical selected method registry for the executable methods.
        registry_content: Exact selected registry bundle for registry-slot arms.

    Returns:
        Immutable normalized source maps, their registry-only projections,
        validated method-output bindings, dependency edges, and topological order.

    Raises:
        ValueError: If a node, source, ABI contract, dependency, or DAG invariant
            is invalid.
    """
    if type(plan) is not ExecutionPlan or type(registry) is not MethodRegistry:
        raise ValueError("method_dataflow_inputs_invalid")
    nodes = tuple(plan.method_dag)
    nodes_by_id = {node.node_id: node for node in nodes}
    if len(nodes_by_id) != len(nodes):
        raise ValueError("method_dataflow_node_ids_not_unique")

    resolved_nodes: dict[str, _MethodNode] = {}
    for node in nodes:
        try:
            entry = resolve_selected_method_entry(
                node.method_fqn, version=node.method_version, registry=registry
            )
        except ValueError as exc:
            raise ValueError("method_dataflow_registered_signature_identity_mismatch") from exc
        if entry is None:
            raise ValueError("method_dataflow_registered_signature_missing")
        signature = entry.signature
        if (
            node.method_version != signature.version
            or signature.kind is not MethodKind.PURE
            or node.backend != signature.execution_backend.value
        ):
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
        input_sources, registry_inputs = _normalize_input_sources(
            node_id=node.node_id,
            signature=signature,
            declared_sources=node.input_ports,
            require_explicit=node.input_ports is not None,
            registry_content=registry_content,
        )
        resolved_nodes[node.node_id] = _MethodNode(
            node_id=node.node_id,
            method_fqn=signature.fqn,
            method_version=signature.version,
            signature=signature,
            metadata=entry.metadata,
            input_sources=input_sources,
            registry_inputs=registry_inputs,
            declared_output_slots=frozenset(node.writes_slots),
            state_outputs=tuple(node.state_writes or ()),
        )

    dependencies = _plan_dependencies(nodes, plan)
    plan_order = {node.node_id: index for index, node in enumerate(nodes)}
    bindings = _resolve_output_bindings(
        resolved_nodes,
        registry=registry,
        dependencies=dependencies,
        order=tuple(node.node_id for node in nodes),
        persisted_edges=None,
        require_selected_registry=registry_content is not None,
        allow_method_output=allow_method_output,
    )
    for binding in bindings:
        if plan_order[binding.producer_node_id] >= plan_order[binding.consumer_node_id]:
            raise ValueError("method_dataflow_producer_forward_reference")
    execution_order = _topological_method_order(nodes_by_id, dependencies)
    return _resolution(
        resolved_nodes=resolved_nodes,
        bindings=bindings,
        dependencies=dependencies,
        execution_order=execution_order,
    )


def resolve_program_graph_method_input_sources(
    graph: ProgramGraph,
    *,
    registry: MethodRegistry,
    registry_content: RegistryBundleContent,
    order: Sequence[str],
    allow_method_output: bool = False,
) -> MethodDataflowResolution:
    """Reconcile persisted graph source maps against actual registries and order.

    Unlike the plan resolver, this reader never repairs or synthesizes a
    persisted Graph 0.3 map. It checks the graph's exact map, registry-only
    ``ProgramNode.inputs`` projection, selected method ABIs, direct persisted
    producer edges, and the actual full graph order supplied by the caller.
    Graph 0.2 remains an identity join and cannot carry method-output sources.

    Args:
        graph: Selected persisted program graph.
        registry: Actual method registry used to dispatch this graph.
        registry_content: Actual selected model registry bundle.
        order: Full graph node order used by the current execution plan.

    Returns:
        Immutable local-ABI source maps, registry-only projections, validated
        output bindings, persisted method dependency edges, and method order.

    Raises:
        ValueError: If the graph, source map, ABI, selected registry, or order is
            missing, ambiguous, stale, or incompatible.
    """
    if (
        type(graph) is not ProgramGraph
        or type(registry) is not MethodRegistry
        or type(registry_content) is not RegistryBundleContent
    ):
        raise ValueError("method_dataflow_graph_inputs_invalid")
    if graph.schema_version not in {"0.2", "0.3"}:
        raise ValueError("method_dataflow_graph_schema_unsupported")
    node_ids = [node.node_id for node in graph.nodes]
    if len(node_ids) != len(set(node_ids)):
        raise ValueError("method_dataflow_graph_node_ids_not_unique")
    order_tuple = tuple(order)
    if len(order_tuple) != len(set(order_tuple)) or set(order_tuple) != set(node_ids):
        raise ValueError("method_dataflow_graph_order_not_exact")
    order_index = {node_id: index for index, node_id in enumerate(order_tuple)}
    node_by_id = {node.node_id: node for node in graph.nodes}
    method_nodes = tuple(node for node in graph.nodes if node.node_kind == "method")
    if graph.schema_version == "0.2":
        method_fqns = [node.method_fqn for node in method_nodes]
        if len(method_fqns) != len(set(method_fqns)):
            raise ValueError("method_dataflow_legacy_method_instance_duplicate")

    edge_keys: set[tuple[str, str, str]] = set()
    persisted_method_edges: set[tuple[str, str]] = set()
    for edge in graph.edges:
        if edge.src not in node_by_id or edge.dst not in node_by_id:
            raise ValueError("method_dataflow_graph_edge_endpoint_missing")
        edge_key = (edge.src, edge.dst, edge.relation)
        if edge_key in edge_keys:
            raise ValueError("method_dataflow_graph_edges_not_unique")
        edge_keys.add(edge_key)
        if order_index[edge.src] >= order_index[edge.dst]:
            raise ValueError("method_dataflow_graph_order_not_topological")
        if (
            node_by_id[edge.src].node_kind == "method"
            and node_by_id[edge.dst].node_kind == "method"
        ):
            if edge.relation != "depends_on":
                raise ValueError("method_dataflow_graph_method_edge_relation_unsupported")
            persisted_method_edges.add((edge.src, edge.dst))

    resolved_nodes: dict[str, _MethodNode] = {}
    for node in method_nodes:
        if node.method_fqn is None or node.method_version is None:
            raise ValueError("method_dataflow_graph_method_identity_missing")
        try:
            entry = resolve_selected_method_entry(
                node.method_fqn, version=node.method_version, registry=registry
            )
        except ValueError as exc:
            raise ValueError("method_dataflow_registered_signature_identity_mismatch") from exc
        if entry is None:
            raise ValueError("method_dataflow_registered_signature_missing")
        signature = entry.signature
        if signature.version != node.method_version or signature.kind is not MethodKind.PURE:
            raise ValueError("method_dataflow_registered_signature_identity_mismatch")
        if graph.schema_version == "0.3":
            if node.input_ports is None:
                raise ValueError("method_dataflow_graph_input_map_missing")
            input_sources, registry_inputs = _normalize_input_sources(
                node_id=node.node_id,
                signature=signature,
                declared_sources=node.input_ports,
                require_explicit=True,
                registry_content=registry_content,
            )
            if node.inputs != list(registry_inputs):
                raise ValueError("method_dataflow_graph_registry_projection_mismatch")
        else:
            if node.input_ports is not None:
                raise ValueError("method_dataflow_graph_input_map_version_mismatch")
            input_sources, registry_inputs = _normalize_input_sources(
                node_id=node.node_id,
                signature=signature,
                declared_sources=None,
                require_explicit=False,
                # Graph 0.2's identity join predates the selected scalar-money
                # input profile. Keep its historical acceptance surface; the
                # actual execute preflight retains its existing registry checks.
                registry_content=None,
            )
            if len(node.inputs) != len(set(node.inputs)) or set(node.inputs) != set(
                registry_inputs
            ):
                raise ValueError("method_dataflow_graph_legacy_registry_inputs_mismatch")
        resolved_nodes[node.node_id] = _MethodNode(
            node_id=node.node_id,
            method_fqn=signature.fqn,
            method_version=signature.version,
            signature=signature,
            metadata=entry.metadata,
            input_sources=input_sources,
            registry_inputs=registry_inputs,
            # ProgramNode.outputs is the patch channel, not the method-return ABI.
            declared_output_slots=signature.output_slot_names,
            state_outputs=tuple(node.outputs),
        )

    dependencies = set(persisted_method_edges)
    bindings = _resolve_output_bindings(
        resolved_nodes,
        registry=registry,
        dependencies=dependencies,
        order=order_tuple,
        persisted_edges=persisted_method_edges,
        require_selected_registry=True,
        allow_method_output=allow_method_output,
    )
    return _resolution(
        resolved_nodes=resolved_nodes,
        bindings=bindings,
        dependencies=dependencies,
        execution_order=tuple(node_id for node_id in order_tuple if node_id in resolved_nodes),
    )


def _normalize_input_sources(
    *,
    node_id: str,
    signature: MethodSignature,
    declared_sources: Mapping[str, MethodInputPortSource] | None,
    require_explicit: bool,
    registry_content: RegistryBundleContent | None,
) -> tuple[Mapping[str, MethodInputPortSource], tuple[str, ...]]:
    """Validate one exact ABI-local source map and its registry projection."""
    input_names = {slot.name for slot in signature.input_slots}
    if declared_sources is None:
        if require_explicit:
            raise ValueError("method_dataflow_input_map_missing")
        sources: dict[str, MethodInputPortSource] = {
            name: RegistrySlotInputPortSource(source_kind="registry_slot", slot_id=name)
            for name in sorted(input_names)
        }
    else:
        if set(declared_sources) != input_names:
            raise ValueError("method_dataflow_input_map_abi_mismatch")
        sources = dict(declared_sources)

    for input_name in sorted(input_names):
        source = sources.get(input_name)
        if isinstance(source, RegistrySlotInputPortSource):
            if registry_content is not None:
                try:
                    validate_registered_method_input(
                        signature,
                        input_slot_id=input_name,
                        registered_slot_id=source.slot_id,
                        registry=registry_content,
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError(
                        f"method_dataflow_registry_input_source_invalid:{exc}"
                    ) from exc
        elif isinstance(source, MethodOutputInputPortSource):
            continue
        else:
            raise ValueError("method_dataflow_input_source_type_invalid")

    registry_inputs = tuple(
        sorted(
            {
                source.slot_id
                for source in sources.values()
                if isinstance(source, RegistrySlotInputPortSource)
            }
        )
    )
    return MappingProxyType(dict(sorted(sources.items()))), registry_inputs


def _resolve_output_bindings(
    resolved_nodes: Mapping[str, _MethodNode],
    *,
    registry: MethodRegistry,
    dependencies: set[tuple[str, str]],
    order: Sequence[str],
    persisted_edges: set[tuple[str, str]] | None,
    require_selected_registry: bool,
    allow_method_output: bool,
) -> tuple[MethodOutputInputBinding, ...]:
    """Validate internal edges and add their dependencies to the supplied set."""
    positions = {node_id: index for index, node_id in enumerate(order)}
    bindings: list[MethodOutputInputBinding] = []
    for consumer in resolved_nodes.values():
        for input_name, source in consumer.input_sources.items():
            if not isinstance(source, MethodOutputInputPortSource):
                continue
            if not allow_method_output:
                raise ValueError("method_dataflow_method_output_not_supported")
            producer = resolved_nodes.get(source.producer_node_id)
            if producer is None:
                raise ValueError("method_dataflow_producer_node_missing")
            if producer.node_id == consumer.node_id:
                raise ValueError("method_dataflow_self_dependency")
            if positions[producer.node_id] >= positions[consumer.node_id]:
                raise ValueError("method_dataflow_producer_forward_reference")

            producer_slot = producer.signature.get_output_slot(source.output_slot_id)
            consumer_slot = consumer.signature.get_input_slot(input_name)
            if producer_slot is None or source.output_slot_id not in producer.declared_output_slots:
                raise ValueError("method_dataflow_producer_output_slot_missing")
            if consumer_slot is None:
                raise ValueError("method_dataflow_consumer_input_slot_missing")
            if (
                require_selected_registry
                and resolve_selected_method_entry(
                    producer.method_fqn, version=producer.method_version, registry=registry
                )
                is None
            ):
                raise ValueError("method_dataflow_registered_signature_missing")
            _validate_transfer_profile(producer, consumer)
            compatibility = check_slot_compatibility(
                producer_slot,
                consumer_slot,
                strict_shape=True,
                allow_unsafe_shapes=False,
            )
            if (
                not compatibility.compatible
                or compatibility.adapter_plan.as_tuple()
                or producer_slot.unit != consumer_slot.unit
                or producer_slot.slot_type is not consumer_slot.slot_type
                or producer_slot.slot_type.name != "SCALAR"
                or consumer_slot.slot_type.name != "SCALAR"
                or producer_slot.shape != consumer_slot.shape
                or producer_slot.shape != ()
                or producer_slot.contract_id != consumer_slot.contract_id
            ):
                raise ValueError("method_dataflow_abi_slot_contract_mismatch")

            dependency = (producer.node_id, consumer.node_id)
            if persisted_edges is not None and dependency not in persisted_edges:
                raise ValueError("method_dataflow_persisted_output_edge_missing")
            dependencies.add(dependency)
            bindings.append(
                MethodOutputInputBinding(
                    producer_node_id=producer.node_id,
                    producer_method_fqn=producer.method_fqn,
                    producer_method_version=producer.method_version,
                    producer_abi_digest=producer.signature.abi_digest(),
                    producer_output_slot_id=producer_slot.name,
                    consumer_node_id=consumer.node_id,
                    consumer_method_fqn=consumer.method_fqn,
                    consumer_method_version=consumer.method_version,
                    consumer_abi_digest=consumer.signature.abi_digest(),
                    consumer_input_slot_id=consumer_slot.name,
                )
            )
    return tuple(
        sorted(
            bindings,
            key=lambda binding: (
                binding.consumer_node_id,
                binding.consumer_input_slot_id,
                binding.producer_node_id,
                binding.producer_output_slot_id,
            ),
        )
    )


def _validate_transfer_profile(producer: _MethodNode, consumer: _MethodNode) -> None:
    """Limit the first runtime bridge to actual held pure NumPy calls."""
    if (
        producer.signature.kind is not MethodKind.PURE
        or consumer.signature.kind is not MethodKind.PURE
        or producer.signature.execution_backend is not ComputeBackend.NUMPY
        or consumer.signature.execution_backend is not ComputeBackend.NUMPY
        or producer.signature.representation_profiles
        or consumer.signature.representation_profiles
        or getattr(producer.metadata, "side_effect_profile", None) is not SideEffectProfile.NONE
        or getattr(consumer.metadata, "side_effect_profile", None) is not SideEffectProfile.NONE
    ):
        raise ValueError("method_dataflow_method_profile_unsupported")
    if (
        producer.signature.patch_targets
        or consumer.signature.patch_targets
        or producer.state_outputs
        or consumer.state_outputs
    ):
        raise ValueError("method_dataflow_patch_transfer_not_supported")


def _plan_dependencies(nodes: Sequence[MethodDagNode], plan: ExecutionPlan) -> set[tuple[str, str]]:
    """Validate and collect the selected plan's explicit dependency edges."""
    node_ids = {node.node_id for node in nodes}
    dependencies: set[tuple[str, str]] = set()
    for node in nodes:
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
    if any(source not in node_ids or target not in node_ids for source, target in dependencies):
        raise ValueError("method_dataflow_dependency_endpoint_missing")
    return dependencies


def _topological_method_order(
    nodes_by_id: Mapping[str, object], dependencies: set[tuple[str, str]]
) -> tuple[str, ...]:
    """Return a deterministic topological method-node order."""
    sorter = TopologicalSorter()
    for node_id in sorted(nodes_by_id):
        sorter.add(node_id)
    for source, target in sorted(dependencies):
        sorter.add(target, source)
    try:
        return tuple(sorter.static_order())
    except CycleError as exc:
        raise ValueError("method_dataflow_dependency_cycle") from exc


def _resolution(
    *,
    resolved_nodes: Mapping[str, _MethodNode],
    bindings: tuple[MethodOutputInputBinding, ...],
    dependencies: set[tuple[str, str]],
    execution_order: tuple[str, ...],
) -> MethodDataflowResolution:
    """Create one immutable result for compiler and persisted-graph readers."""
    source_maps = {node_id: node.input_sources for node_id, node in sorted(resolved_nodes.items())}
    registry_inputs = {
        node_id: node.registry_inputs for node_id, node in sorted(resolved_nodes.items())
    }
    return MethodDataflowResolution(
        bindings=bindings,
        dependency_edges=tuple(sorted(dependencies)),
        execution_order=execution_order,
        input_sources=MappingProxyType(source_maps),
        registry_inputs=MappingProxyType(registry_inputs),
    )
