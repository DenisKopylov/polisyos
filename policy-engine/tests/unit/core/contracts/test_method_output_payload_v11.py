from __future__ import annotations

import hashlib
import json
import struct

import pytest
from pydantic import ValidationError

from polisyos.core.contracts.foundry import (
    MethodOutputConsumptionRecord,
    MethodOutputPayload,
    MethodOutputPayloadV11,
    MethodOutputRef,
    MethodOutputScalarValueIdentity,
)
from polisyos.ir.kernel import MethodMetricSourceUnit


def _scalar_identity(*, dtype="<f4", unit_symbol="USD", unit_scale=1.0):
    return MethodOutputScalarValueIdentity(
        slot_type="SCALAR",
        shape=(),
        dtype=dtype,
        unit=MethodMetricSourceUnit(dimension="currency", symbol=unit_symbol, scale=unit_scale),
        contract_id=None,
    )


def _payload(*, raw=None, dtype="<f4", raw_digest=None, value_digest=None, unit_scale=1.0):
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
        value_identity=_scalar_identity(dtype=dtype, unit_scale=unit_scale),
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
):
    payload = _payload(unit_scale=producer_unit_scale)
    return MethodOutputConsumptionRecord(
        producer_output_ref=MethodOutputRef(
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
