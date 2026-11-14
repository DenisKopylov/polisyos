from __future__ import annotations

import hashlib
import json
import struct
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.contracts.foundry import (
    ExecPlanRef,
    MethodExecutionBundle,
    MethodExecutionDispatchRecord,
    MethodExecutionInputSlot,
    MethodExecutionOccurrence,
    MethodExecutionOutputSlot,
    MethodExecutionReturnedSlot,
    MethodMetricBindingSetRef,
    MethodOutputConsumptionRecord,
    MethodOutputRef,
    MethodOutputScalarValueIdentity,
    ProgramGraphRef,
)
from polisyos.ir.kernel import MethodMetricSourceUnit

_CAPTURED_AT = datetime(2026, 1, 1, tzinfo=UTC)
_PROFILE = "sha256:" + "f" * 64
_RAW = struct.pack("<f", -6_000_000_000.0)
_RAW_SHA256 = hashlib.sha256(_RAW).hexdigest()
_VALUE_SHA256 = hashlib.sha256(
    b"<f4" + json.dumps([], separators=(",", ":")).encode("ascii") + _RAW
).hexdigest()
_PRODUCER_ABI = "a" * 64
_CONSUMER_ABI = "c" * 64


def _ref(kind: str, suffix: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + suffix * 64,
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256=_PROFILE,
    )


def _identity() -> MethodOutputScalarValueIdentity:
    return MethodOutputScalarValueIdentity(
        slot_type="SCALAR",
        shape=(),
        dtype="<f4",
        unit=MethodMetricSourceUnit(dimension="currency", symbol="USD", scale=1.0),
        contract_id=None,
    )


def _dispatch(
    *,
    outcome: str,
    input_slots: tuple[MethodExecutionInputSlot, ...] = (),
    input_ids: tuple[str, ...] = (),
    output_ids: tuple[str, ...] = (),
) -> MethodExecutionDispatchRecord:
    return MethodExecutionDispatchRecord(
        outcome=outcome,
        started_at=(_CAPTURED_AT if outcome != "not_run" else None),
        completed_at=(_CAPTURED_AT if outcome != "not_run" else None),
        failure_type=("RuntimeError" if outcome == "failed" else None),
        signature_input_slot_ids=input_ids,
        signature_output_slot_ids=output_ids,
        input_slot_values=input_slots,
        input_state_status="not_started",
        parameter_resolution_status="captured",
        parameter_inventory_observed_count=0,
        parameter_inventory_limit=32,
        seed_status="not_started",
        rng_state_status="not_started",
        backend_identity_status="not_started",
        backend_trace_status="not_started",
        fallback_status="not_started",
    )


def _consumption(
    *,
    producer_output_ref: MethodOutputRef | None = None,
    producer_occurrence_id: str = "run.1:0:producer",
    producer_invocation_id: str = "run.1",
    producer_node_id: str = "producer",
    producer_method_fqn: str = "policy.example.producer@1.0.0",
    producer_method_version: str = "1.0.0",
    producer_method_abi_digest: str = _PRODUCER_ABI,
    consumer_occurrence_id: str = "run.1:1:consumer",
    consumer_invocation_id: str = "run.1",
    consumer_node_id: str = "consumer",
    consumer_method_fqn: str = "policy.example.consumer@1.0.0",
    consumer_method_version: str = "1.0.0",
    consumer_method_abi_digest: str = _CONSUMER_ABI,
    consumer_input_slot_id: str = "incoming_flow",
) -> MethodOutputConsumptionRecord:
    identity = _identity()
    return MethodOutputConsumptionRecord(
        producer_output_ref=producer_output_ref
        or MethodOutputRef.model_validate(
            _ref("foundry.method_output", "b").model_dump(mode="python")
        ),
        producer_occurrence_id=producer_occurrence_id,
        producer_invocation_id=producer_invocation_id,
        producer_node_id=producer_node_id,
        producer_method_fqn=producer_method_fqn,
        producer_method_version=producer_method_version,
        producer_method_abi_digest=producer_method_abi_digest,
        producer_method_abi_digest_algorithm="blake2b",
        producer_output_slot_id="period_flow",
        producer_value_identity=identity,
        producer_value_sha256_algorithm="selected_tensor_value_sha256",
        producer_raw_bytes_sha256=_RAW_SHA256,
        producer_value_sha256=_VALUE_SHA256,
        consumer_occurrence_id=consumer_occurrence_id,
        consumer_invocation_id=consumer_invocation_id,
        consumer_node_id=consumer_node_id,
        consumer_method_fqn=consumer_method_fqn,
        consumer_method_version=consumer_method_version,
        consumer_method_abi_digest=consumer_method_abi_digest,
        consumer_method_abi_digest_algorithm="blake2b",
        consumer_input_slot_id=consumer_input_slot_id,
        consumer_argument_identity=identity,
        consumer_argument_raw_bytes_sha256=_RAW_SHA256,
        consumer_argument_value_sha256_algorithm="selected_tensor_value_sha256",
        consumer_argument_value_sha256=_VALUE_SHA256,
    )


def _occurrences(
    *,
    producer_status: str = "succeeded",
    producer_plan_index: int = 0,
    consumer_input: MethodExecutionInputSlot | None = None,
    producer_output_ref: MethodOutputRef | None = None,
    mixed_metric_output: bool = False,
    consumer_status: str = "succeeded",
    dataflow_capture: bool = True,
) -> list[MethodExecutionOccurrence]:
    producer_id = f"run.1:{producer_plan_index}:producer"
    producer_ref = producer_output_ref or MethodOutputRef.model_validate(
        _ref("foundry.method_output", "b").model_dump(mode="python")
    )
    producer = MethodExecutionOccurrence(
        occurrence_id=producer_id,
        invocation_id="run.1",
        plan_index=producer_plan_index,
        node_id="producer",
        node_kind="method",
        status=producer_status,
        method_fqn="policy.example.producer@1.0.0",
        method_version="1.0.0",
        method_abi_digest=_PRODUCER_ABI,
        method_abi_digest_algorithm="blake2b",
        output_slots=[
            MethodExecutionOutputSlot(
                slot_id="period_flow",
                status="captured",
                output_ref=producer_ref,
            ),
            *(
                [
                    MethodExecutionOutputSlot(
                        slot_id="metric_flow",
                        status="captured",
                        output_ref=MethodOutputRef.model_validate(
                            _ref("foundry.method_output", "d").model_dump(mode="python")
                        ),
                    )
                ]
                if mixed_metric_output
                else []
            ),
        ],
        returned_slots=[
            *(
                [
                    MethodExecutionReturnedSlot(
                        slot_id="period_flow",
                        declared_by_signature=True,
                        declared_slot_type="SCALAR",
                        declared_shape=(),
                        returned="returned",
                        runtime_type="numpy.ndarray",
                        runtime_shape=(),
                        runtime_shape_status="captured",
                        runtime_dtype="<f4",
                        codec_status="typed_scalar_supported",
                        retention_status="selected_dataflow_output",
                    )
                ]
                if dataflow_capture
                else []
            ),
            *(
                [
                    MethodExecutionReturnedSlot(
                        slot_id="metric_flow",
                        declared_by_signature=True,
                        declared_slot_type="SCALAR",
                        declared_shape=(),
                        returned="returned",
                        runtime_type="numpy.ndarray",
                        runtime_shape=(),
                        runtime_shape_status="captured",
                        runtime_dtype="<f4",
                        codec_status="json_scalar_supported",
                        retention_status="selected_metric_output",
                    )
                ]
                if mixed_metric_output
                else []
            ),
        ],
        returned_slot_inventory_status="captured",
        returned_slot_inventory_observed_count=(int(dataflow_capture) + int(mixed_metric_output)),
        dispatch=_dispatch(
            outcome=producer_status,
            output_ids=("period_flow", "metric_flow")
            if mixed_metric_output
            else ("period_flow",)
            if dataflow_capture
            else (),
        ),
    )
    value = consumer_input or MethodExecutionInputSlot(
        slot_id="incoming_flow",
        status="captured",
        value_sha256=_VALUE_SHA256,
        runtime_type="numpy.ndarray",
        runtime_shape=(),
        runtime_dtype="<f4",
    )
    consumer = MethodExecutionOccurrence(
        occurrence_id="run.1:1:consumer",
        invocation_id="run.1",
        plan_index=1,
        node_id="consumer",
        node_kind="method",
        status=consumer_status,
        method_fqn="policy.example.consumer@1.0.0",
        method_version="1.0.0",
        method_abi_digest=_CONSUMER_ABI,
        method_abi_digest_algorithm="blake2b",
        dispatch=_dispatch(
            outcome=consumer_status if consumer_status != "planned" else "not_run",
            input_slots=(value,) if consumer_status != "planned" else (),
            input_ids=("incoming_flow",),
        ),
    )
    return [producer, consumer]


def _bundle(
    *,
    schema_version: str,
    consumptions: tuple[MethodOutputConsumptionRecord, ...] | None = None,
    occurrences: list[MethodExecutionOccurrence] | None = None,
) -> MethodExecutionBundle:
    return MethodExecutionBundle(
        schema_version=schema_version,
        captured_at=_CAPTURED_AT,
        program_graph_ref=ProgramGraphRef.model_validate(
            _ref("foundry.program_graph", "1").model_dump(mode="python")
        ),
        exec_plan_ref=ExecPlanRef.model_validate(
            _ref("foundry.exec_plan", "2").model_dump(mode="python")
        ),
        method_metric_binding_set_ref=MethodMetricBindingSetRef.model_validate(
            _ref("foundry.method_metric_binding_set", "3").model_dump(mode="python")
        ),
        occurrences=[] if occurrences is None else occurrences,
        method_output_consumptions=consumptions,
    )


@pytest.mark.parametrize("schema_version", ["1.1", "1.2"])
def test_legacy_method_execution_bundle_wire_is_golden_and_omits_dataflow(
    schema_version: str,
) -> None:
    bundle = _bundle(schema_version=schema_version)
    payload = bundle.model_dump(mode="json")
    canonical = to_canonical_bytes(payload, CanonSpec())

    assert "method_output_consumptions" not in payload
    assert canonical == _LEGACY_BUNDLE_WIRE[schema_version]


def test_v13_bundle_records_joined_actual_output_consumption() -> None:
    row = _consumption()
    bundle = _bundle(
        schema_version="1.3",
        consumptions=(row,),
        occurrences=_occurrences(),
    )

    dumped = bundle.model_dump(mode="json")
    assert dumped["schema_version"] == "1.3"
    assert dumped["method_output_consumptions"][0]["consumer_input_slot_id"] == "incoming_flow"


@pytest.mark.parametrize("schema_version", ["1.1", "1.2"])
def test_legacy_bundle_rejects_nonempty_output_consumption_rows(schema_version: str) -> None:
    with pytest.raises(ValidationError, match="method_execution_bundle_output_consumption_version"):
        _bundle(schema_version=schema_version, consumptions=(_consumption(),))


def test_v13_rejects_empty_unbacked_dataflow_capture() -> None:
    with pytest.raises(
        ValidationError, match="method_execution_bundle_v13_requires_dataflow_output_capture"
    ):
        _bundle(schema_version="1.3")


def test_v13_preserves_producer_only_dataflow_capture_with_metric_output() -> None:
    bundle = _bundle(
        schema_version="1.3",
        occurrences=_occurrences(mixed_metric_output=True),
    )

    assert bundle.method_output_consumptions is None
    assert "method_output_consumptions" not in bundle.model_dump(mode="json")
    producer = bundle.occurrences[0]
    assert [item.retention_status for item in producer.returned_slots] == [
        "selected_dataflow_output",
        "selected_metric_output",
    ]


def test_legacy_bundle_rejects_new_dataflow_capture_labels() -> None:
    with pytest.raises(
        ValidationError,
        match="legacy_method_execution_bundle_cannot_claim_dataflow_output",
    ):
        _bundle(schema_version="1.2", occurrences=_occurrences())


@pytest.mark.parametrize(
    ("field", "value"),
    [("runtime_dtype", "float32"), ("runtime_shape", (1,))],
)
def test_v13_rejects_inconsistent_typed_dataflow_returned_identity(field, value) -> None:
    occurrences = _occurrences()
    returned = occurrences[0].returned_slots[0].model_copy(update={field: value})
    producer = occurrences[0].model_copy(update={"returned_slots": [returned]})
    occurrences[0] = producer

    with pytest.raises(
        ValidationError,
        match="method_execution_bundle_dataflow_output_capture_mismatch",
    ):
        _bundle(schema_version="1.3", occurrences=occurrences)


def test_v13_rejects_duplicate_consumer_input_and_wrong_actual_hash() -> None:
    row = _consumption()
    with pytest.raises(
        ValidationError,
        match="method_execution_bundle_duplicate_output_consumption_input",
    ):
        _bundle(schema_version="1.3", consumptions=(row, row), occurrences=_occurrences())

    wrong_input = MethodExecutionInputSlot(
        slot_id="incoming_flow",
        status="captured",
        value_sha256="0" * 64,
        runtime_type="numpy.ndarray",
        runtime_shape=(),
        runtime_dtype="<f4",
    )
    with pytest.raises(
        ValidationError,
        match="method_execution_bundle_output_consumption_input_mismatch",
    ):
        _bundle(
            schema_version="1.3",
            consumptions=(row,),
            occurrences=_occurrences(consumer_input=wrong_input),
        )


def test_v13_rejects_missing_or_later_or_failed_producer() -> None:
    row = _consumption()
    with pytest.raises(
        ValidationError,
        match="method_execution_bundle_output_consumption_occurrence_missing",
    ):
        _bundle(
            schema_version="1.3",
            consumptions=(row.model_copy(update={"producer_occurrence_id": "missing"}),),
            occurrences=_occurrences(),
        )

    later_occurrences = _occurrences(producer_plan_index=2)
    later_row = _consumption(
        producer_occurrence_id="run.1:2:producer",
    )
    with pytest.raises(
        ValidationError,
        match="method_execution_bundle_output_consumption_occurrence_mismatch",
    ):
        _bundle(schema_version="1.3", consumptions=(later_row,), occurrences=later_occurrences)

    with pytest.raises(
        ValidationError,
        match="method_execution_bundle_output_consumption_occurrence_mismatch",
    ):
        _bundle(
            schema_version="1.3",
            consumptions=(row,),
            occurrences=_occurrences(producer_status="failed", dataflow_capture=False),
        )


def test_v13_rejects_grafted_output_reference_and_abi_identity() -> None:
    wrong_ref = MethodOutputRef.model_validate(
        _ref("foundry.method_output", "e").model_dump(mode="python")
    )
    with pytest.raises(
        ValidationError,
        match="method_execution_bundle_output_consumption_output_ref_mismatch",
    ):
        _bundle(
            schema_version="1.3",
            consumptions=(_consumption(),),
            occurrences=_occurrences(producer_output_ref=wrong_ref),
        )

    with pytest.raises(
        ValidationError,
        match="method_execution_bundle_output_consumption_occurrence_mismatch",
    ):
        _bundle(
            schema_version="1.3",
            consumptions=(_consumption(consumer_method_abi_digest="e" * 64),),
            occurrences=_occurrences(),
        )


def test_v13_keeps_ex_ante_call_witness_requirement() -> None:
    occurrences = _occurrences()
    producer = occurrences[0].model_copy(
        update={"method_fqn": "policy.evaluation.ex_ante_simulation@1.0.0"}
    )
    row = _consumption(producer_method_fqn="policy.evaluation.ex_ante_simulation@1.0.0")

    with pytest.raises(
        ValidationError,
        match="succeeded_exante_occurrence_requires_call_witness_or_refusal",
    ):
        _bundle(schema_version="1.3", consumptions=(row,), occurrences=[producer, occurrences[1]])


_LEGACY_BUNDLE_WIRE: dict[str, bytes] = {
    "1.1": (
        b'{"captured_at":"2026-01-01T00:00:00Z","environment_manifest_ref":null,'
        b'"exec_plan_ref":{"artifact_id":"sha256:2222222222222222222222222222222222222222222222222222222222222222",'
        b'"kind":"foundry.exec_plan","manifest_profile_sha256":"sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",'
        b'"media_type":"application/json"},"limitations":[],"method_metric_binding_set_ref":'
        b'{"artifact_id":"sha256:3333333333333333333333333333333333333333333333333333333333333333",'
        b'"kind":"foundry.method_metric_binding_set","manifest_profile_sha256":"sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",'
        b'"media_type":"application/json"},"occurrences":[],"program_graph_ref":{"artifact_id":'
        b'"sha256:1111111111111111111111111111111111111111111111111111111111111111",'
        b'"kind":"foundry.program_graph","manifest_profile_sha256":"sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",'
        b'"media_type":"application/json"},"schema_version":"1.1"}'
    ),
    "1.2": (
        b'{"captured_at":"2026-01-01T00:00:00Z","environment_manifest_ref":null,'
        b'"exec_plan_ref":{"artifact_id":"sha256:2222222222222222222222222222222222222222222222222222222222222222",'
        b'"kind":"foundry.exec_plan","manifest_profile_sha256":"sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",'
        b'"media_type":"application/json"},"limitations":[],"method_metric_binding_set_ref":'
        b'{"artifact_id":"sha256:3333333333333333333333333333333333333333333333333333333333333333",'
        b'"kind":"foundry.method_metric_binding_set","manifest_profile_sha256":"sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",'
        b'"media_type":"application/json"},"occurrences":[],"program_graph_ref":{"artifact_id":'
        b'"sha256:1111111111111111111111111111111111111111111111111111111111111111",'
        b'"kind":"foundry.program_graph","manifest_profile_sha256":"sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",'
        b'"media_type":"application/json"},"schema_version":"1.2"}'
    ),
}
