"""Public selected execution and cold replay for method-output inputs."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
from dataclasses import replace
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from polisyos.core.artifacts import validate_core_model_json_artifact
from polisyos.core.artifacts.canonical_profile import CoreJsonReadLimits
from polisyos.core.artifacts.manifest import SchemaInfo, input_ref_from_artifact_ref
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.foundry import (
    ExecuteRequest,
    MethodExecutionBundle,
    MethodExecutionBundleRef,
    MethodOutputRef,
    ProgramEdge,
    ProgramGraph,
    SimulationResult,
    SimulationResultRef,
)
from polisyos.core.contracts.method_input import MethodOutputInputPortSource
from polisyos.foundry.data_plane.bindings import load_input_bindings
from polisyos.foundry.data_plane.method_output_values import (
    MethodOutputValueRefusal,
    read_selected_method_output_value,
    reconcile_method_output_consumption,
)
from polisyos.foundry.execute._internal import graph as execute_graph
from polisyos.foundry.execute._internal.graph import prepare_program_graph_method_calls
from polisyos.foundry.execute.api import (
    ExecutionSourceAdmissionRefusal,
    admit_execution_source,
)
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.execute.executor import load_state_snapshot
from polisyos.foundry.methods.base import SlotType, Unit
from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
from polisyos.foundry.methods.registry import MethodRegistry
from tests._helpers.registered_derived_method_input import (
    materialize_registered_method_input_case,
)
from tests._helpers.selected_method_output_input import (
    CONSUMER_INPUT_ID,
    CONSUMER_NODE_ID,
    PRODUCER_NODE_ID,
    PRODUCER_OUTPUT_ID,
    SELECTED_METHOD_OUTPUT_CALLS,
    SelectedMethodOutputConsumer,
    SelectedMethodOutputFailingConsumer,
    SelectedMethodOutputProducer,
    build_selected_method_output_plan,
    persist_and_compile_selected_method_output_plan,
    prepare_selected_method_output_input_case,
)

_READ_LIMITS = CoreJsonReadLimits(
    max_bytes=16384,
    max_depth=24,
    max_elements=512,
    max_manifest_bytes=16384,
)


def _independent_value_sha256(value: Any) -> str:
    """Hash dtype, shape, and contiguous bytes independently of the producer."""
    array = np.asarray(value)
    digest = hashlib.sha256()
    digest.update(array.dtype.str.encode("ascii"))
    digest.update(json.dumps(array.shape, separators=(",", ":")).encode("ascii"))
    digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def _method_occurrence(bundle: MethodExecutionBundle, node_id: str):
    occurrences = [
        item
        for item in bundle.occurrences
        if item.node_kind == "method" and item.node_id == node_id
    ]
    assert len(occurrences) == 1
    return occurrences[0]


def _method_output_ref(occurrence, slot_id: str) -> MethodOutputRef:
    outputs = [item for item in occurrence.output_slots if item.slot_id == slot_id]
    assert len(outputs) == 1
    assert outputs[0].status == "captured"
    assert outputs[0].output_ref is not None
    return outputs[0].output_ref


def _input_capture(occurrence, slot_id: str):
    assert occurrence.dispatch is not None
    rows = [item for item in occurrence.dispatch.input_slot_values if item.slot_id == slot_id]
    assert len(rows) == 1
    assert rows[0].status == "captured"
    return rows[0]


def _execute_request(case, materialized) -> ExecuteRequest:
    return ExecuteRequest(
        exec_plan_ref=case.exec_plan_ref,
        registry_bundle_ref=case.registry_bundle_ref,
        input_bindings_ref=materialized.input_bindings_ref,
        return_selected_profile=True,
    )


def _persist_missing_consumption_replay(case, executed) -> SimulationResultRef:
    """Reprofile a real success with only its required transfer receipt removed."""
    assert executed.simulation_result_ref is not None
    assert executed.method_execution_bundle_ref is not None
    bundle_ref = executed.method_execution_bundle_ref
    bundle = validate_core_model_json_artifact(MethodExecutionBundle, case.store, bundle_ref)
    assert bundle.schema_version == "1.3"
    assert bundle.method_output_consumptions
    partial_payload = bundle.model_dump(mode="python")
    partial_payload["method_output_consumptions"] = None
    partial_bundle = MethodExecutionBundle.model_validate(partial_payload)
    assert partial_bundle.schema_version == "1.3"
    assert partial_bundle.method_output_consumptions is None

    bundle_manifest = case.store.get_manifest(bundle_ref)
    partial_bundle_ref = case.store.put_json(
        partial_bundle,
        PutOptions(
            kind=MethodExecutionBundle.ARTIFACT_KIND,
            media_type=MethodExecutionBundle.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=MethodExecutionBundle.ARTIFACT_SCHEMA_NAME,
                version=partial_bundle.schema_version,
            ),
            inputs=bundle_manifest.inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    selected_bundle_ref = MethodExecutionBundleRef.model_validate(
        partial_bundle_ref.model_dump(mode="python")
    )

    simulation_ref = executed.simulation_result_ref
    simulation = validate_core_model_json_artifact(SimulationResult, case.store, simulation_ref)
    simulation_manifest = case.store.get_manifest(simulation_ref)
    method_edges = [item for item in simulation_manifest.inputs if item.role == "method_execution"]
    assert len(method_edges) == 1
    simulation_inputs = [
        (
            input_ref_from_artifact_ref(selected_bundle_ref, role="method_execution")
            if item.role == "method_execution"
            else item
        )
        for item in simulation_manifest.inputs
    ]
    partial_simulation_ref = case.store.put_json(
        simulation.to_artifact_payload(),
        PutOptions(
            kind=SimulationResult.ARTIFACT_KIND,
            media_type=SimulationResult.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=SimulationResult.ARTIFACT_SCHEMA_NAME,
                version=simulation.schema_version,
            ),
            inputs=simulation_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    selected_simulation_ref = SimulationResultRef.model_validate(
        partial_simulation_ref.model_dump(mode="python")
    )
    assert selected_simulation_ref.artifact_id == simulation_ref.artifact_id
    assert selected_simulation_ref.manifest_profile_sha256 != simulation_ref.manifest_profile_sha256
    reprofiled_manifest = case.store.get_manifest(selected_simulation_ref)
    reprofiled_edges = [
        item for item in reprofiled_manifest.inputs if item.role == "method_execution"
    ]
    assert len(reprofiled_edges) == 1
    assert reprofiled_edges[0].artifact_id == selected_bundle_ref.artifact_id
    assert (
        reprofiled_edges[0].manifest_profile_sha256 == selected_bundle_ref.manifest_profile_sha256
    )
    return selected_simulation_ref


def _close_store(store: FileSystemCAS) -> None:
    close = getattr(store, "close", None)
    if callable(close):
        close()


def _unregister_fixture_methods(extra_class: type[Any] | None = None) -> None:
    registry = MethodRegistry.get_instance()
    registry.unregister(SelectedMethodOutputProducer.signature.fqn)
    registry.unregister(SelectedMethodOutputConsumer.signature.fqn)
    if extra_class is not None:
        registry.unregister(extra_class.signature.fqn)
    registry.register(PeriodFlowToStock, override=True)


def _fresh_process_read(case, result_ref: SimulationResultRef) -> dict[str, Any]:
    """Reopen only persisted selected evidence in a new process and CAS reader."""
    product_root = Path(__file__).resolve().parents[4]
    source_root = product_root / "src"
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(source_root)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    code = r"""
import hashlib
import json
import os
import sys
from io import BytesIO
from pathlib import Path
import numpy as np
from polisyos.core.artifacts import validate_core_model_json_artifact
from polisyos.core.artifacts.canonical_profile import CoreJsonReadLimits
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.foundry import (
    MethodExecutionBundle,
    ProgramEdge,
    ProgramGraph,
    SimulationResultRef,
)
from polisyos.foundry.data_plane.bindings import load_input_bindings
from polisyos.foundry.data_plane.method_output_values import (
    read_selected_method_output_value,
    reconcile_method_output_consumption,
)
from polisyos.foundry.execute import api as execute_api
from polisyos.foundry.data_plane import method_output_values
assert "tests._helpers.selected_method_output_input" not in sys.modules
source_root = Path(sys.argv[3]).resolve()
for module in (execute_api, method_output_values):
    assert Path(module.__file__).resolve().is_relative_to(source_root)
store = FileSystemCAS(sys.argv[1])
result_ref = SimulationResultRef.model_validate_json(sys.argv[2])
admitted = execute_api.admit_execution_source(store, result_ref)
manifest = store.get_manifest(result_ref)
edge = next(item for item in manifest.inputs if item.role == "method_execution")
bundle_ref = ArtifactRef(
    artifact_id=edge.artifact_id,
    manifest_profile_sha256=edge.manifest_profile_sha256,
    kind=MethodExecutionBundle.ARTIFACT_KIND,
    media_type="application/json",
)
bundle = validate_core_model_json_artifact(MethodExecutionBundle, store, bundle_ref)
graph = validate_core_model_json_artifact(
    ProgramGraph, store, admitted.basis.program_graph_ref
)
assert graph.schema_version == "0.3"
assert bundle.schema_version == "1.3"
producer, consumer = (
    next(item for item in bundle.occurrences if item.node_id == node_id)
    for node_id in ("flow.producer", "flow.consumer")
)
assert producer.status == consumer.status == "succeeded"
assert producer.dispatch is not None and consumer.dispatch is not None
assert producer.invocation_id == consumer.invocation_id
assert len(bundle.method_output_consumptions or ()) == 1
consumption, = bundle.method_output_consumptions
assert consumption.producer_invocation_id == producer.invocation_id
assert consumption.consumer_invocation_id == consumer.invocation_id
consumer_node = next(item for item in graph.nodes if item.node_id == "flow.consumer")
source = consumer_node.input_ports["incoming_flow"]
assert source.source_kind == "method_output"
assert source.producer_node_id == "flow.producer" and source.output_slot_id == "result"
selected_output = next(
    item for item in producer.output_slots if item.slot_id == "result"
)
summary_output = next(
    item for item in consumer.output_slots if item.slot_id == "summary"
)
assert selected_output.output_ref is not None and summary_output.output_ref is not None
limits = CoreJsonReadLimits(
    max_bytes=16384, max_depth=24, max_elements=512, max_manifest_bytes=16384
)
producer_value = read_selected_method_output_value(
    store, selected_output.output_ref, limits=limits
)
summary_value = read_selected_method_output_value(
    store, summary_output.output_ref, limits=limits
)
resolved = reconcile_method_output_consumption(
    program_graph_ref=admitted.basis.program_graph_ref,
    graph=graph,
    bundle=bundle,
    consumption=consumption,
    selected_output=producer_value,
)
bindings = load_input_bindings(store, admitted.basis.input_bindings_ref)
selected, = bindings.selected_method_inputs
npy_value = np.load(BytesIO(store.get_bytes(selected.npy_value_ref)), allow_pickle=False)
def digest(value):
    array = np.asarray(value)
    result = hashlib.sha256()
    result.update(array.dtype.str.encode("ascii"))
    result.update(json.dumps(array.shape, separators=(",", ":")).encode("ascii"))
    result.update(array.tobytes(order="C"))
    return result.hexdigest()
producer_argument, = (
    item for item in producer.dispatch.input_slot_values if item.slot_id == "period_flow"
)
consumer_argument, = (
    item for item in consumer.dispatch.input_slot_values if item.slot_id == "incoming_flow"
)
assert digest(npy_value) == selected.value_sha256 == producer_argument.value_sha256
assert digest(producer_value.value) == consumer_argument.value_sha256
assert consumption.consumer_argument_raw_bytes_sha256 == producer_value.payload.raw_bytes_sha256
assert consumption.producer_value_sha256 == producer_value.payload.value_sha256
assert resolved.dtype == np.dtype(np.float64) and resolved.shape == ()
assert float(producer_value.value) == -12000000000.0
assert float(summary_value.value) == -36000000000.0
assert graph.edges.count(
    ProgramEdge(src="flow.producer", dst="flow.consumer", relation="depends_on")
) == 1
print(json.dumps({
    "graph_version": graph.schema_version,
    "consumptions": len(bundle.method_output_consumptions),
    "producer_input_sha256": digest(npy_value),
    "consumer_input_sha256": digest(producer_value.value),
    "producer_value": float(producer_value.value),
    "consumer_value": float(summary_value.value),
}))
"""
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            code,
            str(case.store_root),
            result_ref.model_dump_json(),
            str(source_root),
        ],
        cwd=product_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    return json.loads(result.stdout)


def _changed_consumer(*, change: str) -> type[Any]:
    """Build a real incompatible registered consumer signature for compiler refusal."""
    base = SelectedMethodOutputConsumer.signature.get_input_slot(CONSUMER_INPUT_ID)
    assert base is not None
    if change == "unit":
        changed_slot = replace(base, unit=Unit("currency", "EUR"))
    elif change == "shape":
        changed_slot = replace(base, slot_type=SlotType.VECTOR, shape=(1,))
    else:  # pragma: no cover - test parameter invariant
        raise ValueError("selected_method_output_bad_abi_change_invalid")
    signature = replace(
        SelectedMethodOutputConsumer.signature,
        name=f"consumer_bad_{change}",
        input_slots=frozenset({changed_slot}),
    )
    return type(
        f"SelectedMethodOutputConsumerBad{change.title()}",
        (SelectedMethodOutputConsumer,),
        {"signature": signature},
    )


@pytest.mark.parametrize(
    ("producer_node_id", "output_slot_id"),
    [("missing.producer", PRODUCER_OUTPUT_ID), (PRODUCER_NODE_ID, "missing.output")],
)
def test_selected_compiler_refuses_missing_method_output_source(
    tmp_path, producer_node_id: str, output_slot_id: str
) -> None:
    case, _ = prepare_selected_method_output_input_case(tmp_path)
    try:
        plan = build_selected_method_output_plan(
            consumer_source=MethodOutputInputPortSource(
                source_kind="method_output",
                producer_node_id=producer_node_id,
                output_slot_id=output_slot_id,
            ),
            plan_id="selected-method-output-invalid-source",
        )
        compiled = persist_and_compile_selected_method_output_plan(case, plan)
        assert not compiled.ok
        assert compiled.exec_plan_ref is None
        assert not any(item.role == "program_graph" for item in compiled.derived_refs)
    finally:
        _unregister_fixture_methods()
        case.close()


@pytest.mark.parametrize("change", ["unit", "shape"])
def test_selected_compiler_refuses_method_output_abi_mismatch(tmp_path, change: str) -> None:
    case, _ = prepare_selected_method_output_input_case(tmp_path)
    registry = MethodRegistry.get_instance()
    changed_consumer = _changed_consumer(change=change)
    registry.register(changed_consumer, override=True)
    try:
        plan = build_selected_method_output_plan(
            consumer_class=changed_consumer,
            plan_id=f"selected-method-output-invalid-{change}",
        )
        compiled = persist_and_compile_selected_method_output_plan(case, plan)
        assert not compiled.ok
        assert compiled.exec_plan_ref is None
        assert not any(item.role == "program_graph" for item in compiled.derived_refs)
    finally:
        _unregister_fixture_methods(changed_consumer)
        case.close()


def test_selected_method_output_reaches_consumer_and_cold_reader(tmp_path, monkeypatch) -> None:
    SELECTED_METHOD_OUTPUT_CALLS.clear()
    case, metadata = prepare_selected_method_output_input_case(tmp_path)
    try:
        materialized = materialize_registered_method_input_case(
            case,
            metadata,
            ratio_value=Decimal("-0.03"),
            denominator_value=Decimal("200000000000"),
        )
        bindings = load_input_bindings(case.store, materialized.input_bindings_ref)
        assert bindings.schema_version == "1.4"
        (selected,) = bindings.selected_method_inputs
        selected_bytes = case.store.get_bytes(selected.npy_value_ref)
        source_array = np.load(BytesIO(selected_bytes), allow_pickle=False)
        assert source_array.dtype == np.dtype(np.float64) and source_array.shape == ()
        assert float(source_array) == -6_000_000_000.0
        source_digest = _independent_value_sha256(source_array)
        assert source_digest == selected.value_sha256

        assert bindings.bound_state_snapshot_ref is not None
        base_state = load_state_snapshot(
            case.store,
            snapshot_ref=bindings.bound_state_snapshot_ref,
        )
        held_preparations: list[str] = []

        def unexpected_held_preparation(*, node, **kwargs):
            held_preparations.append(node.node_id)
            raise AssertionError("prospective method-output intent prepared a held call")

        with monkeypatch.context() as patch:
            patch.setattr(
                execute_graph,
                "_prepare_method_call_observation",
                unexpected_held_preparation,
            )
            with pytest.raises(
                ValueError,
                match=r"^program_graph_method_output_intent_not_established$",
            ):
                prepare_program_graph_method_calls(
                    case.store,
                    program_ref=case.program_graph_ref,
                    exec_plan_ref=case.exec_plan_ref,
                    registry_bundle_ref=case.registry_bundle_ref,
                    input_bindings_ref=materialized.input_bindings_ref,
                    base_state=base_state,
                    steps=(0,),
                )
        assert held_preparations == []
        assert SELECTED_METHOD_OUTPUT_CALLS == []

        graph = validate_core_model_json_artifact(ProgramGraph, case.store, case.program_graph_ref)
        assert graph.schema_version == "0.3"
        producer_node = next(item for item in graph.nodes if item.node_id == PRODUCER_NODE_ID)
        consumer_node = next(item for item in graph.nodes if item.node_id == CONSUMER_NODE_ID)
        assert producer_node.inputs == ["period_flow"] and producer_node.outputs == []
        assert consumer_node.inputs == [] and consumer_node.outputs == []
        assert consumer_node.input_ports is not None
        assert consumer_node.input_ports[CONSUMER_INPUT_ID] == MethodOutputInputPortSource(
            source_kind="method_output",
            producer_node_id=PRODUCER_NODE_ID,
            output_slot_id=PRODUCER_OUTPUT_ID,
        )
        assert (
            graph.edges.count(
                ProgramEdge(src=PRODUCER_NODE_ID, dst=CONSUMER_NODE_ID, relation="depends_on")
            )
            == 1
        )

        executed = execute_foundry(case.store, _execute_request(case, materialized))
        assert executed.ok and executed.simulation_result_ref is not None, executed.notes
        assert executed.method_execution_bundle_ref is not None
        bundle = validate_core_model_json_artifact(
            MethodExecutionBundle,
            case.store,
            executed.method_execution_bundle_ref,
        )
        assert bundle.schema_version == "1.3"
        assert bundle.method_output_consumptions is not None
        (consumption,) = bundle.method_output_consumptions
        assert consumption.producer_node_id == PRODUCER_NODE_ID
        assert consumption.consumer_node_id == CONSUMER_NODE_ID
        assert consumption.consumer_input_slot_id == CONSUMER_INPUT_ID
        producer = _method_occurrence(bundle, PRODUCER_NODE_ID)
        consumer = _method_occurrence(bundle, CONSUMER_NODE_ID)
        assert producer.status == consumer.status == "succeeded"
        assert producer.invocation_id == consumer.invocation_id
        assert producer.dispatch is not None and consumer.dispatch is not None
        assert producer.dispatch.step == consumer.dispatch.step
        assert consumption.producer_invocation_id == producer.invocation_id
        assert consumption.consumer_invocation_id == consumer.invocation_id

        producer_argument = _input_capture(producer, "period_flow")
        consumer_argument = _input_capture(consumer, CONSUMER_INPUT_ID)
        assert producer_argument.value_sha256 == source_digest
        assert producer_argument.runtime_dtype == np.dtype(np.float64).str
        assert producer_argument.runtime_shape == ()

        producer_output = read_selected_method_output_value(
            case.store,
            _method_output_ref(producer, PRODUCER_OUTPUT_ID),
            limits=_READ_LIMITS,
        )
        summary_output = read_selected_method_output_value(
            case.store,
            _method_output_ref(consumer, "summary"),
            limits=_READ_LIMITS,
        )
        producer_digest = _independent_value_sha256(producer_output.value)
        summary_digest = _independent_value_sha256(summary_output.value)
        assert producer_output.value.dtype == np.dtype(np.float64)
        assert producer_output.value.shape == ()
        assert float(producer_output.value) == -12_000_000_000.0
        assert float(summary_output.value) == -36_000_000_000.0
        assert consumer_argument.value_sha256 == producer_digest
        assert consumer_argument.runtime_dtype == np.dtype(np.float64).str
        assert consumer_argument.runtime_shape == ()
        assert consumption.producer_value_sha256 == producer_digest
        assert consumption.consumer_argument_value_sha256 == producer_digest
        assert (
            consumption.producer_raw_bytes_sha256
            == hashlib.sha256(bytes.fromhex(producer_output.payload.raw_bytes_hex)).hexdigest()
        )
        assert consumption.consumer_argument_raw_bytes_sha256 == (
            consumption.producer_raw_bytes_sha256
        )
        assert summary_output.payload.value_sha256 == summary_digest
        assert SELECTED_METHOD_OUTPUT_CALLS == [
            ("producer", -6_000_000_000.0),
            ("consumer", -12_000_000_000.0),
        ]

        fresh = FileSystemCAS(case.store_root)
        try:
            admitted = admit_execution_source(fresh, executed.simulation_result_ref)
            cold_bundle = validate_core_model_json_artifact(
                MethodExecutionBundle,
                fresh,
                executed.method_execution_bundle_ref,
            )
            cold_graph = validate_core_model_json_artifact(
                ProgramGraph,
                fresh,
                admitted.basis.program_graph_ref,
            )
            (cold_consumption,) = cold_bundle.method_output_consumptions or ()
            cold_producer = _method_occurrence(cold_bundle, PRODUCER_NODE_ID)
            cold_output = read_selected_method_output_value(
                fresh,
                _method_output_ref(cold_producer, PRODUCER_OUTPUT_ID),
                limits=_READ_LIMITS,
            )
            resolved = reconcile_method_output_consumption(
                program_graph_ref=admitted.basis.program_graph_ref,
                graph=cold_graph,
                bundle=cold_bundle,
                consumption=cold_consumption,
                selected_output=cold_output,
            )
            assert _independent_value_sha256(resolved) == producer_digest
        finally:
            _close_store(fresh)

        fresh_summary = _fresh_process_read(case, executed.simulation_result_ref)
        assert fresh_summary == {
            "graph_version": "0.3",
            "consumptions": 1,
            "producer_input_sha256": source_digest,
            "consumer_input_sha256": producer_digest,
            "producer_value": -12_000_000_000.0,
            "consumer_value": -36_000_000_000.0,
        }

        calls_before_partial = tuple(SELECTED_METHOD_OUTPUT_CALLS)
        partial_result_ref = _persist_missing_consumption_replay(case, executed)
        partial_reader = FileSystemCAS(case.store_root)
        try:
            with pytest.raises(ExecutionSourceAdmissionRefusal) as partial_refusal:
                admit_execution_source(partial_reader, partial_result_ref)
            assert (
                partial_refusal.value.reason
                == "execution_source_method_dataflow_consumption_inventory_mismatch"
            )
        finally:
            _close_store(partial_reader)
        assert tuple(SELECTED_METHOD_OUTPUT_CALLS) == calls_before_partial

        # Remove only the actual output blob, then restore it without rerunning either method.
        calls_before_removal = tuple(SELECTED_METHOD_OUTPUT_CALLS)
        output_ref = _method_output_ref(producer, PRODUCER_OUTPUT_ID)
        blob_path, _ = case.store._paths(output_ref.artifact_id)
        original_mode = stat.S_IMODE(blob_path.stat().st_mode)
        original_blob = blob_path.read_bytes()
        blob_path.unlink()
        missing_reader = None
        try:
            missing_reader = FileSystemCAS(case.store_root)
            with pytest.raises(MethodOutputValueRefusal, match="selected_payload_unavailable"):
                read_selected_method_output_value(
                    missing_reader,
                    output_ref,
                    limits=_READ_LIMITS,
                )
            with pytest.raises(
                FileNotFoundError, match=str(output_ref.artifact_id).removeprefix("sha256:")
            ):
                admit_execution_source(missing_reader, executed.simulation_result_ref)
        finally:
            if missing_reader is not None:
                _close_store(missing_reader)
            blob_path.write_bytes(original_blob)
            blob_path.chmod(original_mode)

        restored_reader = FileSystemCAS(case.store_root)
        try:
            restored = read_selected_method_output_value(
                restored_reader,
                output_ref,
                limits=_READ_LIMITS,
            )
            assert _independent_value_sha256(restored.value) == producer_digest
            restored_admission = admit_execution_source(
                restored_reader,
                executed.simulation_result_ref,
            )
            assert restored_admission.basis == admitted.basis
        finally:
            _close_store(restored_reader)
        assert tuple(SELECTED_METHOD_OUTPUT_CALLS) == calls_before_removal
    finally:
        _unregister_fixture_methods()
        case.close()


def test_failed_consumer_retains_actual_method_output_attempt(tmp_path) -> None:
    SELECTED_METHOD_OUTPUT_CALLS.clear()
    case, metadata = prepare_selected_method_output_input_case(
        tmp_path,
        consumer_class=SelectedMethodOutputFailingConsumer,
    )
    try:
        materialized = materialize_registered_method_input_case(
            case,
            metadata,
            ratio_value=Decimal("-0.03"),
            denominator_value=Decimal("200000000000"),
        )
        executed = execute_foundry(case.store, _execute_request(case, materialized))
        assert not executed.ok
        assert executed.simulation_result_ref is None
        assert executed.method_execution_bundle_ref is not None

        bundle = validate_core_model_json_artifact(
            MethodExecutionBundle,
            case.store,
            executed.method_execution_bundle_ref,
        )
        assert bundle.schema_version == "1.3"
        producer = _method_occurrence(bundle, PRODUCER_NODE_ID)
        consumer = _method_occurrence(bundle, CONSUMER_NODE_ID)
        assert producer.status == "succeeded"
        assert producer.dispatch is not None and producer.dispatch.outcome == "succeeded"
        assert consumer.status == "failed"
        assert consumer.dispatch is not None and consumer.dispatch.outcome == "failed"
        assert consumer.invocation_id == producer.invocation_id
        assert consumer.plan_index > producer.plan_index
        assert producer.dispatch.step == consumer.dispatch.step

        output = read_selected_method_output_value(
            case.store,
            _method_output_ref(producer, PRODUCER_OUTPUT_ID),
            limits=_READ_LIMITS,
        )
        output_digest = _independent_value_sha256(output.value)
        assert output.value.dtype == np.dtype(np.float64)
        assert output.value.shape == ()
        assert float(output.value) == -12_000_000_000.0
        argument = _input_capture(consumer, CONSUMER_INPUT_ID)
        assert argument.runtime_dtype == np.dtype(np.float64).str
        assert argument.runtime_shape == ()
        assert argument.value_sha256 == output_digest

        assert bundle.method_output_consumptions is not None
        (attempt,) = bundle.method_output_consumptions
        assert attempt.producer_occurrence_id == producer.occurrence_id
        assert attempt.consumer_occurrence_id == consumer.occurrence_id
        assert attempt.producer_output_slot_id == PRODUCER_OUTPUT_ID
        assert attempt.consumer_input_slot_id == CONSUMER_INPUT_ID
        assert attempt.producer_value_sha256 == output_digest
        assert attempt.consumer_argument_value_sha256 == output_digest
        assert attempt.producer_raw_bytes_sha256 == output.payload.raw_bytes_sha256
        assert attempt.consumer_argument_raw_bytes_sha256 == output.payload.raw_bytes_sha256
        assert SELECTED_METHOD_OUTPUT_CALLS == [
            ("producer", -6_000_000_000.0),
            ("consumer_failed", -12_000_000_000.0),
        ]
    finally:
        _unregister_fixture_methods(SelectedMethodOutputFailingConsumer)
        case.close()
