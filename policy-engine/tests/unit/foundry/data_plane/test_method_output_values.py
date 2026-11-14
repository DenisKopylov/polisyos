from __future__ import annotations

import hashlib
from dataclasses import replace

import numpy as np
import pytest

from polisyos.core.artifacts.canonical_profile import CoreJsonReadLimits
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.foundry import (
    MethodExecutionBundle,
    MethodExecutionDispatchRecord,
    MethodExecutionInputSlot,
    MethodExecutionOccurrence,
    MethodExecutionOutputSlot,
    MethodOutputConsumptionRecord,
    MethodOutputPayloadV11,
    MethodOutputRef,
    MethodOutputScalarValueIdentity,
    ProgramEdge,
    ProgramGraph,
    ProgramGraphRef,
    ProgramNode,
)
from polisyos.core.contracts.method_input import (
    MethodOutputInputPortSource,
    RegistrySlotInputPortSource,
)
from polisyos.foundry.data_plane.method_output_values import (
    MethodOutputValueRefusal,
    prepare_method_output_input_value,
    read_selected_method_output_value,
    reconcile_method_output_consumption,
)
from polisyos.foundry.data_plane.selected_tensors import selected_tensor_value_sha256
from polisyos.foundry.methods.base import SlotSpec, SlotType, Unit
from polisyos.foundry.methods.catalog.policy.evaluation import ExAnteSimulationEstimator
from polisyos.ir.kernel import MethodMetricSourceUnit


def _put_output(
    store: FileSystemCAS,
    *,
    node_id: str = "producer.a",
    value: float = -6.0e9,
    producer_abi_digest: str = "1" * 64,
):
    scalar_identity = MethodOutputScalarValueIdentity(
        slot_type="SCALAR",
        shape=(),
        dtype="<f8",
        unit=MethodMetricSourceUnit(dimension="currency", symbol="USD", scale=1),
        contract_id="test.period-flow",
    )
    raw = np.asarray(value, dtype=np.dtype("<f8")).tobytes()
    payload = MethodOutputPayloadV11(
        occurrence_id=f"run:0:{node_id}",
        invocation_id="run",
        node_id=node_id,
        method_fqn="test.producer@1.0.0",
        method_version="1.0.0",
        method_abi_digest=producer_abi_digest,
        method_abi_digest_algorithm="blake2b",
        output_slot_id="flow",
        value_identity=scalar_identity,
        value_sha256_algorithm="selected_tensor_value_sha256",
        raw_bytes_hex=raw.hex(),
        raw_bytes_sha256=hashlib.sha256(raw).hexdigest(),
        value_sha256=selected_tensor_value_sha256(np.dtype("<f8"), (), raw),
    )
    ref = store.put_json(
        payload,
        PutOptions(
            kind="foundry.method_output",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.MethodOutputPayload", version="1.1"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    selected_ref = MethodOutputRef.model_validate(ref.model_dump(mode="json"))
    return payload, selected_ref


def _replay_case(store: FileSystemCAS, payload, output_ref):
    identity = payload.value_identity
    consumer_identity = identity.model_copy(deep=True)
    graph_ref = ProgramGraphRef.model_construct(
        artifact_id="sha256:" + "a" * 64,
        kind="foundry.program_graph",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "a" * 64,
    )
    producer = MethodExecutionOccurrence.model_construct(
        occurrence_id=payload.occurrence_id,
        invocation_id="run",
        plan_index=0,
        node_id=payload.node_id,
        node_kind="method",
        status="succeeded",
        method_fqn=payload.method_fqn,
        method_version=payload.method_version,
        method_abi_digest=payload.method_abi_digest,
        method_abi_digest_algorithm="blake2b",
        output_slots=[
            MethodExecutionOutputSlot.model_construct(
                slot_id="flow", status="captured", output_ref=output_ref, limitation=None
            )
        ],
        dispatch=MethodExecutionDispatchRecord.model_construct(
            outcome="succeeded", step=0, signature_output_slot_ids=("flow",)
        ),
    )
    consumer_input = MethodExecutionInputSlot.model_construct(
        slot_id="amount",
        status="captured",
        value_sha256=payload.value_sha256,
        runtime_type="numpy.ndarray",
        runtime_shape=(),
        runtime_dtype="<f8",
        limitation=None,
    )
    consumer = MethodExecutionOccurrence.model_construct(
        occurrence_id="run:1:consumer.node",
        invocation_id="run",
        plan_index=1,
        node_id="consumer.node",
        node_kind="method",
        status="succeeded",
        method_fqn="test.consumer@1.0.0",
        method_version="1.0.0",
        method_abi_digest="2" * 64,
        method_abi_digest_algorithm="blake2b",
        dispatch=MethodExecutionDispatchRecord.model_construct(
            outcome="succeeded",
            step=0,
            signature_input_slot_ids=("amount",),
            input_slot_values=(consumer_input,),
        ),
    )
    graph = ProgramGraph.model_construct(
        schema_version="0.3",
        ir_ref=ArtifactRef.model_construct(
            artifact_id="sha256:" + "b" * 64,
            kind="ir",
            media_type="application/json",
        ),
        nodes=[
            ProgramNode.model_construct(
                node_id=payload.node_id,
                node_kind="method",
                method_fqn=payload.method_fqn,
                method_version=payload.method_version,
                inputs=[],
                outputs=[],
                input_ports={},
            ),
            ProgramNode.model_construct(
                node_id="consumer.node",
                node_kind="method",
                method_fqn="test.consumer@1.0.0",
                method_version="1.0.0",
                inputs=[],
                outputs=[],
                input_ports={
                    "amount": MethodOutputInputPortSource(
                        source_kind="method_output",
                        producer_node_id=payload.node_id,
                        output_slot_id="flow",
                    )
                },
            ),
        ],
        edges=[ProgramEdge(src=payload.node_id, dst="consumer.node")],
        entrypoints=[],
        notes=[],
    )
    bundle = MethodExecutionBundle.model_construct(
        program_graph_ref=graph_ref,
        occurrences=[producer, consumer],
    )
    consumption = MethodOutputConsumptionRecord.model_construct(
        producer_output_ref=output_ref,
        producer_occurrence_id=producer.occurrence_id,
        producer_invocation_id="run",
        producer_node_id=producer.node_id,
        producer_method_fqn=producer.method_fqn,
        producer_method_version=producer.method_version,
        producer_method_abi_digest=producer.method_abi_digest,
        producer_method_abi_digest_algorithm="blake2b",
        producer_output_slot_id="flow",
        producer_value_identity=identity,
        producer_value_sha256_algorithm="selected_tensor_value_sha256",
        producer_raw_bytes_sha256=payload.raw_bytes_sha256,
        producer_value_sha256=payload.value_sha256,
        consumer_occurrence_id=consumer.occurrence_id,
        consumer_invocation_id="run",
        consumer_node_id=consumer.node_id,
        consumer_method_fqn=consumer.method_fqn,
        consumer_method_version=consumer.method_version,
        consumer_method_abi_digest=consumer.method_abi_digest,
        consumer_method_abi_digest_algorithm="blake2b",
        consumer_input_slot_id="amount",
        consumer_argument_identity=consumer_identity,
        consumer_argument_raw_bytes_sha256=payload.raw_bytes_sha256,
        consumer_argument_value_sha256_algorithm="selected_tensor_value_sha256",
        consumer_argument_value_sha256=payload.value_sha256,
    )
    return graph_ref, graph, bundle, consumption


def _signatures():
    template = ExAnteSimulationEstimator.signature
    unit = Unit(dimension="currency", symbol="USD", scale=1)
    producer = replace(
        template,
        namespace="test",
        name="producer",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(
            {
                SlotSpec(
                    name="flow",
                    slot_type=SlotType.SCALAR,
                    unit=unit,
                    contract_id="test.period-flow",
                )
            }
        ),
    )
    consumer = replace(
        template,
        namespace="test",
        name="consumer",
        version="1.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="amount",
                    slot_type=SlotType.SCALAR,
                    unit=unit,
                    contract_id="test.period-flow",
                )
            }
        ),
        output_slots=frozenset(),
    )
    return producer, consumer


def test_pre_dispatch_resolver_uses_completed_producer_and_current_graph(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    producer_signature, consumer_signature = _signatures()
    payload, output_ref = _put_output(store, producer_abi_digest=producer_signature.abi_digest())
    _, graph, bundle, _ = _replay_case(store, payload, output_ref)
    graph_ref = store.put_json(
        graph,
        PutOptions(
            kind="foundry.program_graph",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.ProgramGraph", version="0.3.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    selected_graph_ref = ProgramGraphRef.model_validate(graph_ref.model_dump(mode="json"))
    pending_consumer = bundle.occurrences[1].model_copy(
        update={
            "status": "planned",
            "method_abi_digest": consumer_signature.abi_digest(),
            "dispatch": bundle.occurrences[1].dispatch.model_copy(update={"outcome": "not_run"}),
        }
    )
    pre_dispatch_bundle = bundle.model_copy(
        update={
            "program_graph_ref": selected_graph_ref,
            "occurrences": [bundle.occurrences[0], pending_consumer],
        }
    )

    value = prepare_method_output_input_value(
        store,
        bundle=pre_dispatch_bundle,
        consumer_occurrence_id=pending_consumer.occurrence_id,
        consumer_input_name="amount",
        producer_signature=producer_signature,
        consumer_signature=consumer_signature,
        limits=CoreJsonReadLimits(
            max_bytes=4096, max_depth=16, max_elements=128, max_manifest_bytes=4096
        ),
    )

    assert value.value.dtype == np.dtype("<f8")
    assert value.value.item() == -6.0e9
    assert value.value.flags.writeable is False


def test_pre_dispatch_resolver_refuses_same_value_after_source_removal(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    producer_signature, consumer_signature = _signatures()
    payload, output_ref = _put_output(store, producer_abi_digest=producer_signature.abi_digest())
    _, graph, bundle, _ = _replay_case(store, payload, output_ref)
    consumer_node = graph.nodes[1].model_copy(
        update={
            "inputs": ["external.input"],
            "input_ports": {
                "amount": RegistrySlotInputPortSource(
                    source_kind="registry_slot", slot_id="external.input"
                )
            },
        }
    )
    graph_without_binding = graph.model_copy(update={"nodes": [graph.nodes[0], consumer_node]})
    graph_ref = store.put_json(
        graph_without_binding,
        PutOptions(
            kind="foundry.program_graph",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.ProgramGraph", version="0.3.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    selected_graph_ref = ProgramGraphRef.model_validate(graph_ref.model_dump(mode="json"))
    pending_consumer = bundle.occurrences[1].model_copy(
        update={
            "status": "planned",
            "method_abi_digest": consumer_signature.abi_digest(),
            "dispatch": bundle.occurrences[1].dispatch.model_copy(update={"outcome": "not_run"}),
        }
    )
    pre_dispatch_bundle = bundle.model_copy(
        update={
            "program_graph_ref": selected_graph_ref,
            "occurrences": [bundle.occurrences[0], pending_consumer],
        }
    )

    with pytest.raises(MethodOutputValueRefusal, match="method_output_source_not_declared"):
        prepare_method_output_input_value(
            store,
            bundle=pre_dispatch_bundle,
            consumer_occurrence_id=pending_consumer.occurrence_id,
            consumer_input_name="amount",
            producer_signature=producer_signature,
            consumer_signature=consumer_signature,
            limits=CoreJsonReadLimits(
                max_bytes=4096, max_depth=16, max_elements=128, max_manifest_bytes=4096
            ),
        )


def test_fresh_cas_output_replay_preserves_float64_and_actual_binding(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    payload, output_ref = _put_output(store)
    selected = read_selected_method_output_value(
        store,
        output_ref,
        limits=CoreJsonReadLimits(
            max_bytes=4096, max_depth=16, max_elements=128, max_manifest_bytes=4096
        ),
    )
    graph_ref, graph, bundle, consumption = _replay_case(store, payload, output_ref)

    resolved = reconcile_method_output_consumption(
        program_graph_ref=graph_ref,
        graph=graph,
        bundle=bundle,
        consumption=consumption,
        selected_output=selected,
    )

    assert resolved.dtype == np.dtype("<f8")
    assert resolved.shape == ()
    assert resolved.item() == -6.0e9
    assert resolved.flags.writeable is False


def test_same_number_from_wrong_graph_source_is_refused(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    payload, output_ref = _put_output(store)
    selected = read_selected_method_output_value(
        store,
        output_ref,
        limits=CoreJsonReadLimits(
            max_bytes=4096, max_depth=16, max_elements=128, max_manifest_bytes=4096
        ),
    )
    graph_ref, graph, bundle, consumption = _replay_case(store, payload, output_ref)
    consumer_node = graph.nodes[1].model_copy(
        update={
            "input_ports": {
                "amount": MethodOutputInputPortSource(
                    source_kind="method_output",
                    producer_node_id="foreign.producer",
                    output_slot_id="flow",
                )
            }
        }
    )
    wrong_source_graph = graph.model_copy(update={"nodes": [graph.nodes[0], consumer_node]})

    with pytest.raises(MethodOutputValueRefusal, match="method_output_source_edge_mismatch"):
        reconcile_method_output_consumption(
            program_graph_ref=graph_ref,
            graph=wrong_source_graph,
            bundle=bundle,
            consumption=consumption,
            selected_output=selected,
        )


def test_historical_replay_requires_direct_order_edge_as_well_as_source_map(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    payload, output_ref = _put_output(store)
    selected = read_selected_method_output_value(
        store,
        output_ref,
        limits=CoreJsonReadLimits(
            max_bytes=4096, max_depth=16, max_elements=128, max_manifest_bytes=4096
        ),
    )
    graph_ref, graph, bundle, consumption = _replay_case(store, payload, output_ref)
    graph_without_order = graph.model_copy(update={"edges": []})

    with pytest.raises(
        MethodOutputValueRefusal,
        match="method_output_direct_dependency_edge_missing_or_ambiguous",
    ):
        reconcile_method_output_consumption(
            program_graph_ref=graph_ref,
            graph=graph_without_order,
            bundle=bundle,
            consumption=consumption,
            selected_output=selected,
        )


def test_unselected_or_missing_output_bytes_refuse_replay(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    _, output_ref = _put_output(store)
    with pytest.raises(MethodOutputValueRefusal, match="selected_profile_required"):
        read_selected_method_output_value(
            store,
            output_ref.model_copy(update={"manifest_profile_sha256": None}),
            limits=CoreJsonReadLimits(
                max_bytes=4096, max_depth=16, max_elements=128, max_manifest_bytes=4096
            ),
        )

    missing = output_ref.model_copy(update={"artifact_id": "sha256:" + "c" * 64})
    with pytest.raises(MethodOutputValueRefusal, match="selected_payload_unavailable"):
        read_selected_method_output_value(
            store,
            missing,
            limits=CoreJsonReadLimits(
                max_bytes=4096, max_depth=16, max_elements=128, max_manifest_bytes=4096
            ),
        )
