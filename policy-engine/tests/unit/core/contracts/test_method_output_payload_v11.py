from __future__ import annotations

import hashlib
import json
import struct
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.canonical_profile import (
    CoreJsonReadLimits,
    read_core_json_artifact_bounded,
    validate_core_model_bounded_read,
)
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
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
    MethodOutputPayload,
    MethodOutputPayloadV11,
    MethodOutputRef,
    MethodOutputScalarValueIdentity,
    ProgramGraphRef,
)
from polisyos.ir.kernel import MethodMetricSourceUnit


def _scalar_identity(*, dtype="<f4", unit_symbol="USD", unit_scale=1.0, contract_id=None):
    return MethodOutputScalarValueIdentity(
        slot_type="SCALAR",
        shape=(),
        dtype=dtype,
        unit=MethodMetricSourceUnit(dimension="currency", symbol=unit_symbol, scale=unit_scale),
        contract_id=contract_id,
    )


def _payload(
    *, raw=None, dtype="<f4", raw_digest=None, value_digest=None, unit_scale=1.0, contract_id=None
):
    raw_bytes = struct.pack("<f", -6_000_000_000.0) if raw is None else raw
    return MethodOutputPayloadV11(
        occurrence_id="invocation.1:0:producer.a",
        invocation_id="invocation.1",
        node_id="producer.a",
        method_fqn="policy.example.producer@1.0.0",
        method_version="1.0.0",
        method_abi_digest="a" * 64,
        method_abi_digest_algorithm="blake2b",
        output_slot_id="period_flow",
        value_identity=_scalar_identity(
            dtype=dtype, unit_scale=unit_scale, contract_id=contract_id
        ),
        value_sha256_algorithm="selected_tensor_value_sha256",
        raw_bytes_hex=raw_bytes.hex(),
        raw_bytes_sha256=raw_digest or hashlib.sha256(raw_bytes).hexdigest(),
        value_sha256=value_digest
        or hashlib.sha256(
            dtype.encode("ascii")
            + json.dumps([], separators=(",", ":")).encode("ascii")
            + raw_bytes
        ).hexdigest(),
    )


def _consumption(
    *,
    consumer_digest=None,
    consumer_identity=None,
    producer_unit_scale=1.0,
    include_profile=True,
    contract_id=None,
    producer_output_ref=None,
):
    payload = _payload(unit_scale=producer_unit_scale, contract_id=contract_id)
    return MethodOutputConsumptionRecord(
        producer_output_ref=producer_output_ref
        or MethodOutputRef(
            artifact_id="sha256:" + "b" * 64,
            kind="foundry.method_output",
            media_type="application/json",
            **({"manifest_profile_sha256": "sha256:" + "d" * 64} if include_profile else {}),
        ),
        producer_occurrence_id=payload.occurrence_id,
        producer_invocation_id=payload.invocation_id,
        producer_node_id=payload.node_id,
        producer_method_fqn=payload.method_fqn,
        producer_method_version=payload.method_version,
        producer_method_abi_digest=payload.method_abi_digest,
        producer_method_abi_digest_algorithm=payload.method_abi_digest_algorithm,
        producer_output_slot_id=payload.output_slot_id,
        producer_value_identity=payload.value_identity,
        producer_value_sha256_algorithm=payload.value_sha256_algorithm,
        producer_raw_bytes_sha256=payload.raw_bytes_sha256,
        producer_value_sha256=payload.value_sha256,
        consumer_occurrence_id="invocation.1:1:consumer.b",
        consumer_invocation_id=payload.invocation_id,
        consumer_node_id="consumer.b",
        consumer_method_fqn="policy.example.consumer@1.0.0",
        consumer_method_version="1.0.0",
        consumer_method_abi_digest=consumer_digest or "c" * 64,
        consumer_method_abi_digest_algorithm="blake2b",
        consumer_input_slot_id="incoming_flow",
        consumer_argument_identity=consumer_identity or payload.value_identity,
        consumer_argument_raw_bytes_sha256=payload.raw_bytes_sha256,
        consumer_argument_value_sha256_algorithm="selected_tensor_value_sha256",
        consumer_argument_value_sha256=payload.value_sha256,
    )


def _artifact_ref(kind: str, suffix: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + suffix * 64,
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "f" * 64,
    )


def _dispatch(
    *,
    output_ids=(),
    input_ids=(),
    input_slots=(),
) -> MethodExecutionDispatchRecord:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    return MethodExecutionDispatchRecord(
        outcome="succeeded",
        started_at=timestamp,
        completed_at=timestamp,
        step=0,
        signature_output_slot_ids=output_ids,
        signature_input_slot_ids=input_ids,
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


def test_legacy_method_output_payload_wire_stays_1_0() -> None:
    payload = MethodOutputPayload(
        occurrence_id="invocation.1:0:producer.a",
        invocation_id="invocation.1",
        node_id="producer.a",
        slot_id="result",
        value=2**53 + 1,
    )

    assert payload.model_dump(mode="json") == {
        "schema_version": "1.0",
        "occurrence_id": "invocation.1:0:producer.a",
        "invocation_id": "invocation.1",
        "node_id": "producer.a",
        "slot_id": "result",
        "value_path": [],
        "value": 2**53 + 1,
    }


def test_v11_captures_typed_actual_scalar_bytes() -> None:
    payload = _payload()

    assert payload.model_dump(mode="json")["schema_version"] == "1.1"
    assert payload.value_identity.shape == ()
    assert payload.value_identity.dtype == "<f4"
    assert (
        payload.raw_bytes_sha256 == hashlib.sha256(bytes.fromhex(payload.raw_bytes_hex)).hexdigest()
    )


@pytest.mark.parametrize("contract_id", [None, "test.period-flow.v1"])
def test_method_output_identity_and_nested_consumption_round_trip_through_core_cas(
    tmp_path, contract_id
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    canon_spec = CanonSpec(forbid_floats=False)
    limits = CoreJsonReadLimits(
        max_bytes=64 * 1024,
        max_depth=32,
        max_elements=4096,
        max_manifest_bytes=64 * 1024,
    )
    payload = _payload(contract_id=contract_id)
    output_ref = store.put_json(
        payload,
        PutOptions(
            kind=MethodOutputPayloadV11.ARTIFACT_KIND,
            media_type=MethodOutputPayloadV11.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=MethodOutputPayloadV11.ARTIFACT_SCHEMA_NAME,
                version=MethodOutputPayloadV11.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
        canon_spec=canon_spec,
        return_selected_profile=True,
    )
    selected_output_ref = MethodOutputRef.model_validate(output_ref.model_dump(mode="json"))
    payload_bytes = store.get_bytes(output_ref.artifact_id)
    if contract_id is None:
        assert b'"contract_id"' not in payload_bytes
    else:
        assert b'"contract_id":"test.period-flow.v1"' in payload_bytes
    reread_payload = validate_core_model_bounded_read(
        MethodOutputPayloadV11,
        read_core_json_artifact_bounded(
            store,
            ArtifactRef.model_validate(selected_output_ref.model_dump(mode="json")),
            limits=limits,
        ),
    )
    assert reread_payload.value_identity.contract_id == contract_id

    consumption = _consumption(
        contract_id=contract_id,
        producer_output_ref=selected_output_ref,
    )
    producer = MethodExecutionOccurrence(
        occurrence_id=payload.occurrence_id,
        invocation_id=payload.invocation_id,
        plan_index=0,
        node_id=payload.node_id,
        node_kind="method",
        status="succeeded",
        method_fqn=payload.method_fqn,
        method_version=payload.method_version,
        method_abi_digest=payload.method_abi_digest,
        method_abi_digest_algorithm=payload.method_abi_digest_algorithm,
        output_slots=[
            MethodExecutionOutputSlot(
                slot_id=payload.output_slot_id,
                status="captured",
                output_ref=selected_output_ref,
            )
        ],
        returned_slots=[
            MethodExecutionReturnedSlot(
                slot_id=payload.output_slot_id,
                declared_by_signature=True,
                declared_slot_type="SCALAR",
                declared_shape=(),
                returned="returned",
                runtime_type="numpy.ndarray",
                runtime_shape=(),
                runtime_shape_status="captured",
                runtime_dtype=payload.value_identity.dtype,
                codec_status="typed_scalar_supported",
                retention_status="selected_dataflow_output",
            )
        ],
        returned_slot_inventory_status="captured",
        returned_slot_inventory_observed_count=1,
        dispatch=_dispatch(output_ids=(payload.output_slot_id,)),
    )
    consumer_input = MethodExecutionInputSlot(
        slot_id=consumption.consumer_input_slot_id,
        status="captured",
        value_sha256=payload.value_sha256,
        runtime_type="numpy.ndarray",
        runtime_shape=(),
        runtime_dtype=payload.value_identity.dtype,
    )
    consumer = MethodExecutionOccurrence(
        occurrence_id=consumption.consumer_occurrence_id,
        invocation_id=consumption.consumer_invocation_id,
        plan_index=1,
        node_id=consumption.consumer_node_id,
        node_kind="method",
        status="succeeded",
        method_fqn=consumption.consumer_method_fqn,
        method_version=consumption.consumer_method_version,
        method_abi_digest=consumption.consumer_method_abi_digest,
        method_abi_digest_algorithm=consumption.consumer_method_abi_digest_algorithm,
        dispatch=_dispatch(
            input_ids=(consumption.consumer_input_slot_id,),
            input_slots=(consumer_input,),
        ),
    )
    bundle = MethodExecutionBundle(
        schema_version="1.3",
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
        program_graph_ref=ProgramGraphRef.model_validate(
            _artifact_ref("foundry.program_graph", "1").model_dump(mode="python")
        ),
        exec_plan_ref=ExecPlanRef.model_validate(
            _artifact_ref("foundry.exec_plan", "2").model_dump(mode="python")
        ),
        method_metric_binding_set_ref=MethodMetricBindingSetRef.model_validate(
            _artifact_ref("foundry.method_metric_binding_set", "3").model_dump(mode="python")
        ),
        occurrences=[producer, consumer],
        method_output_consumptions=(consumption,),
    )
    bundle_ref = store.put_json(
        bundle,
        PutOptions(
            kind=MethodExecutionBundle.ARTIFACT_KIND,
            media_type=MethodExecutionBundle.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=MethodExecutionBundle.ARTIFACT_SCHEMA_NAME,
                version="1.3",
            ),
        ),
        canon_spec=canon_spec,
        return_selected_profile=True,
    )
    nested_bundle_bytes = store.get_bytes(bundle_ref.artifact_id)
    if contract_id is None:
        assert b'"contract_id"' not in nested_bundle_bytes
    else:
        assert nested_bundle_bytes.count(b'"contract_id":"test.period-flow.v1"') == 2
    reread_bundle = validate_core_model_bounded_read(
        MethodExecutionBundle,
        read_core_json_artifact_bounded(store, bundle_ref, limits=limits),
    )
    nested = reread_bundle.method_output_consumptions[0]
    assert nested.producer_value_identity.contract_id == contract_id
    assert nested.consumer_argument_identity.contract_id == contract_id


def test_v11_rejects_raw_digest_mismatch_and_nonfinite_float() -> None:
    raw = struct.pack("<f", -6_000_000_000.0)
    with pytest.raises(ValidationError, match="method_output_scalar_raw_bytes_digest_mismatch"):
        _payload(raw=raw, raw_digest="0" * 64)

    nan_bytes = struct.pack("<f", float("nan"))
    with pytest.raises(ValidationError, match="method_output_scalar_raw_value_not_finite"):
        _payload(raw=nan_bytes)


@pytest.mark.parametrize(
    ("dtype", "raw"),
    [
        ("float32", struct.pack("<f", 1.0)),
        ("<f8", struct.pack("<f", 1.0)),
    ],
)
def test_v11_rejects_noncanonical_or_wrong_width_scalar_codecs(dtype, raw) -> None:
    with pytest.raises(ValidationError):
        _payload(dtype=dtype, raw=raw)


def test_nested_consumption_binds_exact_producer_ref_and_consumer_argument() -> None:
    record = _consumption()

    assert record.producer_output_ref.kind == "foundry.method_output"
    assert record.producer_output_slot_id == "period_flow"
    assert record.consumer_input_slot_id == "incoming_flow"
    assert record.producer_value_sha256 == record.consumer_argument_value_sha256


def test_nested_consumption_rejects_changed_unit_or_actual_argument_digest() -> None:
    with pytest.raises(ValidationError, match="method_output_consumption_value_identity_mismatch"):
        _consumption(consumer_identity=_scalar_identity(unit_symbol="EUR"))

    values = _consumption().model_dump(mode="python")
    values["consumer_argument_value_sha256"] = "0" * 64
    with pytest.raises(ValidationError, match="method_output_consumption_value_digest_mismatch"):
        MethodOutputConsumptionRecord.model_validate(values)


def test_nested_consumption_preserves_large_integer_unit_scale_exactly() -> None:
    with pytest.raises(ValidationError, match="method_output_consumption_value_identity_mismatch"):
        _consumption(
            producer_unit_scale=2**53,
            consumer_identity=_scalar_identity(unit_scale=2**53 + 1),
        )

    huge = 10**1000
    record = _consumption(
        producer_unit_scale=huge,
        consumer_identity=_scalar_identity(unit_scale=huge),
    )
    assert record.producer_identity_key == record.consumer_identity_key


def test_nested_consumption_requires_exact_selected_producer_profile() -> None:
    with pytest.raises(
        ValidationError,
        match="method_output_consumption_requires_selected_profile",
    ):
        _consumption(include_profile=False)
