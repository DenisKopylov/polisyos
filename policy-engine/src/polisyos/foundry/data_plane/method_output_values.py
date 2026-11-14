"""Read and reconcile exact method-output values selected for method inputs.

This module provides the data-plane primitives for a later graph-executor
bridge. It does not schedule methods, persist consumption records, or grant
authority to a result. A caller must supply the selected graph and execution
bundle from the same invocation and persist the returned consumption record
through the owning execution-bundle version before claiming durable dataflow.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from polisyos.core.artifacts import (
    CoreJsonReadLimits,
    artifact_ref_identity_key,
    read_core_json_artifact_bounded,
    validate_core_model_bounded_read,
)
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts import (
    MethodExecutionBundle,
    MethodExecutionInputSlot,
    MethodExecutionOccurrence,
    MethodOutputConsumptionRecord,
    MethodOutputInputPortSource,
    MethodOutputPayloadV11,
    MethodOutputRef,
    ProgramGraph,
    ProgramGraphRef,
)
from polisyos.foundry.data_plane.selected_tensors import selected_tensor_value_sha256
from polisyos.foundry.methods.base import MethodSignature


class MethodOutputValueRefusal(ValueError):
    """A selected method-output value failed exact identity reconciliation."""


@dataclass(frozen=True, slots=True)
class SelectedMethodOutputValue:
    """A fresh-read, immutable scalar value and its selected payload identity."""

    output_ref: MethodOutputRef
    payload: MethodOutputPayloadV11
    value: np.ndarray


def prepare_method_output_input_value(
    store: object,
    *,
    bundle: MethodExecutionBundle,
    consumer_occurrence_id: str,
    consumer_input_name: str,
    producer_signature: MethodSignature,
    consumer_signature: MethodSignature,
    limits: CoreJsonReadLimits,
) -> SelectedMethodOutputValue:
    """Resolve one actual succeeded producer into a not-yet-dispatched input.

    The current selected graph is reopened from the bundle's selected graph
    reference. The consumer ABI-local name must map to an explicit
    ``method_output`` source, and the exact producer occurrence must have
    succeeded earlier in the same invocation. Both registered signatures are
    checked by ABI digest and exact slot contracts; no casting or ambient state
    fallback is exposed. The caller still owns dispatch and post-dispatch
    persistence of ``MethodOutputConsumptionRecord``.
    """
    if (
        type(bundle) is not MethodExecutionBundle
        or type(consumer_occurrence_id) is not str
        or not consumer_occurrence_id
        or type(consumer_input_name) is not str
        or not consumer_input_name
        or type(producer_signature) is not MethodSignature
        or type(consumer_signature) is not MethodSignature
        or type(limits) is not CoreJsonReadLimits
    ):
        raise MethodOutputValueRefusal("method_output_prepare_inputs_invalid")
    graph_ref = bundle.program_graph_ref
    if type(graph_ref) is not ProgramGraphRef or not graph_ref.manifest_profile_sha256:
        raise MethodOutputValueRefusal("method_output_graph_selected_profile_required")
    try:
        graph_read = read_core_json_artifact_bounded(
            store, _as_core_artifact_ref(graph_ref), limits=limits
        )
        graph = validate_core_model_bounded_read(ProgramGraph, graph_read)
    except Exception as exc:
        raise MethodOutputValueRefusal("method_output_graph_unavailable") from exc

    consumer = _unique_occurrence(bundle, consumer_occurrence_id)
    if (
        consumer.status != "planned"
        or consumer.node_kind != "method"
        or consumer.dispatch is None
        or consumer.dispatch.outcome != "not_run"
    ):
        raise MethodOutputValueRefusal("method_output_consumer_not_pending")
    consumer_node = _unique_graph_node(graph, consumer.node_id)
    if (
        consumer_node.node_kind != "method"
        or consumer_node.method_fqn != consumer.method_fqn
        or consumer_node.method_version != consumer.method_version
        or consumer.method_fqn != consumer_signature.fqn
        or consumer.method_version != consumer_signature.version
        or consumer.method_abi_digest != consumer_signature.abi_digest()
    ):
        raise MethodOutputValueRefusal("method_output_consumer_abi_mismatch")
    source = (consumer_node.input_ports or {}).get(consumer_input_name)
    if type(source) is not MethodOutputInputPortSource:
        raise MethodOutputValueRefusal("method_output_source_not_declared")
    consumer_slot = consumer_signature.get_input_slot(consumer_input_name)
    if consumer_slot is None:
        raise MethodOutputValueRefusal("method_output_consumer_input_not_in_abi")

    producer_candidates = [
        item
        for item in bundle.occurrences
        if item.node_id == source.producer_node_id and item.invocation_id == consumer.invocation_id
    ]
    if len(producer_candidates) != 1:
        raise MethodOutputValueRefusal("method_output_producer_occurrence_missing_or_ambiguous")
    producer = producer_candidates[0]
    producer_node = _unique_graph_node(graph, producer.node_id)
    if (
        producer.status != "succeeded"
        or producer.node_kind != "method"
        or producer.plan_index >= consumer.plan_index
        or producer.dispatch is None
        or producer.dispatch.outcome != "succeeded"
        or producer.dispatch.step is None
        or consumer.dispatch.step != producer.dispatch.step
        or producer_node.node_kind != "method"
        or producer_node.method_fqn != producer.method_fqn
        or producer_node.method_version != producer.method_version
        or producer.method_fqn != producer_signature.fqn
        or producer.method_version != producer_signature.version
        or producer.method_abi_digest != producer_signature.abi_digest()
    ):
        raise MethodOutputValueRefusal("method_output_producer_order_or_abi_mismatch")
    _require_direct_dependency(graph, producer.node_id, consumer.node_id)

    producer_slot = producer_signature.get_output_slot(source.output_slot_id)
    if producer_slot is None:
        raise MethodOutputValueRefusal("method_output_producer_slot_not_in_abi")
    if (
        producer_slot.slot_type is not consumer_slot.slot_type
        or producer_slot.shape != consumer_slot.shape
        or producer_slot.unit != consumer_slot.unit
        or producer_slot.contract_id != consumer_slot.contract_id
    ):
        raise MethodOutputValueRefusal("method_output_abi_slot_contract_mismatch")
    output_slot = _unique_output_slot(producer, source.output_slot_id)
    if output_slot.status != "captured" or output_slot.output_ref is None:
        raise MethodOutputValueRefusal("method_output_producer_output_unavailable")
    selected = read_selected_method_output_value(store, output_slot.output_ref, limits=limits)
    payload = selected.payload
    expected_unit = producer_slot.unit
    if (
        payload.occurrence_id != producer.occurrence_id
        or payload.invocation_id != producer.invocation_id
        or payload.node_id != producer.node_id
        or payload.method_fqn != producer.method_fqn
        or payload.method_version != producer.method_version
        or payload.method_abi_digest != producer.method_abi_digest
        or payload.output_slot_id != source.output_slot_id
        or payload.value_identity.unit.dimension != expected_unit.dimension
        or payload.value_identity.unit.symbol != expected_unit.symbol
        or payload.value_identity.unit.scale != expected_unit.scale
        or payload.value_identity.shape != producer_slot.shape
        or payload.value_identity.slot_type != producer_slot.slot_type.name
        or payload.value_identity.contract_id != producer_slot.contract_id
    ):
        raise MethodOutputValueRefusal("method_output_payload_abi_contract_mismatch")
    return selected


def read_selected_method_output_value(
    store: object,
    output_ref: MethodOutputRef,
    *,
    limits: CoreJsonReadLimits,
) -> SelectedMethodOutputValue:
    """Fresh-read and verify one selected v1.1 method-output scalar.

    The selected manifest profile, raw-byte digest, finite scalar encoding, and
    shared dispatch value digest are all checked. Legacy v1.0 metric payloads
    remain historical evidence and are not upgraded into transferable values.
    The returned NumPy scalar is backed by immutable bytes and preserves its
    declared byte order and precision without relying on JAX x64 mode.
    """
    if (
        type(output_ref) is not MethodOutputRef
        or not output_ref.manifest_profile_sha256
        or type(limits) is not CoreJsonReadLimits
    ):
        raise MethodOutputValueRefusal("method_output_selected_profile_required")
    try:
        bounded = read_core_json_artifact_bounded(
            store, _as_core_artifact_ref(output_ref), limits=limits
        )
        payload = validate_core_model_bounded_read(MethodOutputPayloadV11, bounded)
    except Exception as exc:
        raise MethodOutputValueRefusal("method_output_selected_payload_unavailable") from exc

    raw = bytes.fromhex(payload.raw_bytes_hex)
    identity = payload.value_identity
    try:
        value_sha256 = selected_tensor_value_sha256(np.dtype(identity.dtype), identity.shape, raw)
    except (TypeError, ValueError, OverflowError) as exc:
        raise MethodOutputValueRefusal("method_output_value_identity_invalid") from exc
    if value_sha256 != payload.value_sha256:
        raise MethodOutputValueRefusal("method_output_value_digest_mismatch")

    value = np.frombuffer(raw, dtype=np.dtype(identity.dtype)).reshape(identity.shape)
    if value.flags.writeable:
        value.setflags(write=False)
    return SelectedMethodOutputValue(output_ref=output_ref, payload=payload, value=value)


def reconcile_method_output_consumption(
    *,
    program_graph_ref: ArtifactRef,
    graph: ProgramGraph,
    bundle: MethodExecutionBundle,
    consumption: MethodOutputConsumptionRecord,
    selected_output: SelectedMethodOutputValue,
) -> np.ndarray:
    """Reconcile a persisted method-output transfer against one actual invocation.

    The graph edge distinguishes the value source from mere execution order.
    Both occurrence identities, the successful producer row, exact selected
    output ref, source mapping, ABI fingerprints, consumer input capture, dtype,
    shape, unit, and content identities must agree. No conversion, broadcast,
    fallback state, or FQN-based producer selection is permitted.

    This is a replay primitive only. A capability exists only after the graph
    executor writes the consumption record from the actual argument bytes and
    a versioned bundle reader exposes that persisted record.
    """
    if (
        not isinstance(program_graph_ref, ArtifactRef)
        or type(graph) is not ProgramGraph
        or type(bundle) is not MethodExecutionBundle
        or type(consumption) is not MethodOutputConsumptionRecord
        or type(selected_output) is not SelectedMethodOutputValue
    ):
        raise MethodOutputValueRefusal("method_output_consumption_inputs_invalid")
    if artifact_ref_identity_key(program_graph_ref) != artifact_ref_identity_key(
        bundle.program_graph_ref
    ):
        raise MethodOutputValueRefusal("method_output_graph_bundle_mismatch")

    producer = _unique_occurrence(bundle, consumption.producer_occurrence_id)
    consumer = _unique_occurrence(bundle, consumption.consumer_occurrence_id)
    if (
        producer.status != "succeeded"
        or producer.node_kind != "method"
        or consumer.node_kind != "method"
        or producer.dispatch is None
        or producer.dispatch.outcome != "succeeded"
        or consumer.dispatch is None
        or consumer.dispatch.outcome != "succeeded"
        or producer.dispatch.step is None
        or consumer.dispatch.step != producer.dispatch.step
        or producer.invocation_id != consumer.invocation_id
        or producer.invocation_id != consumption.producer_invocation_id
        or consumer.invocation_id != consumption.consumer_invocation_id
        or producer.plan_index >= consumer.plan_index
    ):
        raise MethodOutputValueRefusal("method_output_occurrence_order_or_status_mismatch")

    producer_node = _unique_graph_node(graph, producer.node_id)
    consumer_node = _unique_graph_node(graph, consumer.node_id)
    if producer_node.node_kind != "method" or consumer_node.node_kind != "method":
        raise MethodOutputValueRefusal("method_output_graph_endpoint_not_method")
    source = (consumer_node.input_ports or {}).get(consumption.consumer_input_slot_id)
    if (
        type(source) is not MethodOutputInputPortSource
        or source.producer_node_id != producer.node_id
        or source.output_slot_id != consumption.producer_output_slot_id
    ):
        raise MethodOutputValueRefusal("method_output_source_edge_mismatch")
    _require_direct_dependency(graph, producer.node_id, consumer.node_id)

    if (
        producer.method_fqn != producer_node.method_fqn
        or producer.method_version != producer_node.method_version
        or consumer.method_fqn != consumer_node.method_fqn
        or consumer.method_version != consumer_node.method_version
        or producer.method_fqn != consumption.producer_method_fqn
        or producer.method_version != consumption.producer_method_version
        or producer.node_id != consumption.producer_node_id
        or producer.method_abi_digest != consumption.producer_method_abi_digest
        or producer.method_abi_digest_algorithm != consumption.producer_method_abi_digest_algorithm
        or consumer.method_fqn != consumption.consumer_method_fqn
        or consumer.method_version != consumption.consumer_method_version
        or consumer.node_id != consumption.consumer_node_id
        or consumer.method_abi_digest != consumption.consumer_method_abi_digest
        or consumer.method_abi_digest_algorithm != consumption.consumer_method_abi_digest_algorithm
        or producer.occurrence_id != selected_output.payload.occurrence_id
        or producer.invocation_id != selected_output.payload.invocation_id
        or producer.node_id != selected_output.payload.node_id
        or producer.method_fqn != selected_output.payload.method_fqn
        or producer.method_version != selected_output.payload.method_version
        or producer.method_abi_digest != selected_output.payload.method_abi_digest
        or producer.method_abi_digest_algorithm
        != selected_output.payload.method_abi_digest_algorithm
        or consumer.occurrence_id != consumption.consumer_occurrence_id
    ):
        raise MethodOutputValueRefusal("method_output_abi_or_occurrence_mismatch")

    output_slot = _unique_output_slot(producer, consumption.producer_output_slot_id)
    if (
        output_slot.status != "captured"
        or output_slot.output_ref is None
        or artifact_ref_identity_key(output_slot.output_ref)
        != artifact_ref_identity_key(selected_output.output_ref)
        or artifact_ref_identity_key(output_slot.output_ref)
        != artifact_ref_identity_key(consumption.producer_output_ref)
        or selected_output.payload.output_slot_id != output_slot.slot_id
    ):
        raise MethodOutputValueRefusal("method_output_selected_ref_mismatch")

    payload = selected_output.payload
    if (
        payload.value_identity != consumption.producer_value_identity
        or payload.raw_bytes_sha256 != consumption.producer_raw_bytes_sha256
        or payload.value_sha256 != consumption.producer_value_sha256
        or payload.value_sha256_algorithm != consumption.producer_value_sha256_algorithm
        or payload.raw_bytes_sha256 != consumption.consumer_argument_raw_bytes_sha256
        or payload.value_sha256 != consumption.consumer_argument_value_sha256
        or consumption.producer_identity_key != consumption.consumer_identity_key
    ):
        raise MethodOutputValueRefusal("method_output_payload_consumption_mismatch")

    if (
        consumer.status != "succeeded"
        or consumer.dispatch is None
        or consumer.dispatch.outcome != "succeeded"
    ):
        raise MethodOutputValueRefusal("method_output_consumer_dispatch_not_succeeded")
    if consumer.dispatch.signature_input_slot_ids.count(consumption.consumer_input_slot_id) != 1:
        raise MethodOutputValueRefusal("method_output_consumer_input_not_in_abi")
    input_slot = _unique_input_slot(consumer, consumption.consumer_input_slot_id)
    if (
        input_slot.status != "captured"
        or input_slot.runtime_dtype != consumption.consumer_argument_identity.dtype
        or input_slot.runtime_shape != consumption.consumer_argument_identity.shape
        or input_slot.value_sha256 != consumption.consumer_argument_value_sha256
        or selected_output.value.dtype.str != consumption.consumer_argument_identity.dtype
        or selected_output.value.shape != consumption.consumer_argument_identity.shape
    ):
        raise MethodOutputValueRefusal("method_output_consumer_argument_mismatch")
    return selected_output.value


def _as_core_artifact_ref(ref: ArtifactRef) -> ArtifactRef:
    """Project a typed selector subclass to Core's exact base-reference type."""
    try:
        return ArtifactRef.model_validate(ref.model_dump(mode="json"), strict=True)
    except Exception as exc:
        raise MethodOutputValueRefusal("method_output_artifact_ref_invalid") from exc


def _unique_occurrence(
    bundle: MethodExecutionBundle, occurrence_id: str
) -> MethodExecutionOccurrence:
    matches = [item for item in bundle.occurrences if item.occurrence_id == occurrence_id]
    if len(matches) != 1:
        raise MethodOutputValueRefusal("method_output_occurrence_missing_or_ambiguous")
    return matches[0]


def _require_direct_dependency(
    graph: ProgramGraph, producer_node_id: str, consumer_node_id: str
) -> None:
    """Require exactly one persisted ordering edge apart from the value binding."""
    matches = [
        edge
        for edge in graph.edges
        if edge.src == producer_node_id
        and edge.dst == consumer_node_id
        and edge.relation == "depends_on"
    ]
    if len(matches) != 1:
        raise MethodOutputValueRefusal("method_output_direct_dependency_edge_missing_or_ambiguous")


def _unique_graph_node(graph: ProgramGraph, node_id: str):
    matches = [item for item in graph.nodes if item.node_id == node_id]
    if len(matches) != 1:
        raise MethodOutputValueRefusal("method_output_graph_node_missing_or_ambiguous")
    return matches[0]


def _unique_output_slot(occurrence: MethodExecutionOccurrence, slot_id: str):
    matches = [item for item in occurrence.output_slots if item.slot_id == slot_id]
    if len(matches) != 1:
        raise MethodOutputValueRefusal("method_output_slot_missing_or_ambiguous")
    return matches[0]


def _unique_input_slot(
    occurrence: MethodExecutionOccurrence, slot_id: str
) -> MethodExecutionInputSlot:
    assert occurrence.dispatch is not None
    matches = [item for item in occurrence.dispatch.input_slot_values if item.slot_id == slot_id]
    if len(matches) != 1:
        raise MethodOutputValueRefusal("method_output_input_slot_missing_or_ambiguous")
    return matches[0]
