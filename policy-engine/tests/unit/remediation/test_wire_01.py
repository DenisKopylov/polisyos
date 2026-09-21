"""Distinguishing tests for the typed runner wire contract (B94)."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.orchestration.engine.protocol import (
    NodeOutcome,
    NodeOutputDisposition,
    OutputAwareNodeOutcome,
)
from polisyos.scientist.orchestration.engine.runner import serialization as serialization_module
from polisyos.scientist.orchestration.engine.runner.serialization import (
    DeserializationError,
    deserialize_outcome,
    deserialize_state,
    deserialize_state_safe,
    serialize_outcome,
    serialize_state,
    serialize_state_safe,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState


def _stdlib_dumps(value: Any) -> bytes:
    """Emulate the supported stdlib backend, including its permissive NaN default."""
    return json.dumps(value, separators=(",", ":"), allow_nan=True).encode()


def _stdlib_loads(data: bytes) -> Any:
    return json.loads(data)


@pytest.fixture(params=("native", "stdlib"), ids=("native", "stdlib"))
def _wire_backend(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> str:
    """Exercise the import-selected backend and the stdlib fallback explicitly."""
    if request.param == "stdlib":
        monkeypatch.setattr(serialization_module, "_dumps", _stdlib_dumps)
        monkeypatch.setattr(serialization_module, "_loads", _stdlib_loads)
    return str(request.param)


def _artifact_ref() -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="test.wire_01",
        media_type="application/json",
    )


def _typed_state() -> ExperimentState:
    return ExperimentState(
        run_id="wire-01-typed",
        params={
            "direct_decimal": Decimal("12.3400"),
            "nested": {
                "decimal": Decimal("0.1250"),
                "blob": b"\x00\xff",
            },
        },
        budgets={"compute": Decimal("7.5000")},
        causal_method_params={
            "nested": [{"decimal": Decimal("1.2300"), "blob": b"\x01\x02"}]
        },
    )


def _assert_typed_state(state: ExperimentState) -> None:
    budget = state.budgets["compute"]
    assert isinstance(budget, Decimal)
    assert budget.as_tuple() == Decimal("7.5000").as_tuple()

    direct = state.params["direct_decimal"]
    assert isinstance(direct, Decimal)
    assert direct.as_tuple() == Decimal("12.3400").as_tuple()

    nested = state.params["nested"]
    assert isinstance(nested, dict)
    assert isinstance(nested["decimal"], Decimal)
    assert nested["decimal"].as_tuple() == Decimal("0.1250").as_tuple()
    assert nested["blob"] == b"\x00\xff"

    method_nested = state.causal_method_params["nested"]
    assert isinstance(method_nested, list)
    assert isinstance(method_nested[0], dict)
    assert isinstance(method_nested[0]["decimal"], Decimal)
    assert method_nested[0]["decimal"].as_tuple() == Decimal("1.2300").as_tuple()
    assert method_nested[0]["blob"] == b"\x01\x02"


def _encode_state(state: ExperimentState, wire_kind: str) -> bytes:
    if wire_kind == "plain":
        return serialize_state(state)
    if wire_kind == "safe":
        return serialize_state_safe(state)[0]
    if wire_kind == "outcome":
        return serialize_outcome(NodeOutcome(status="ok", state=state))
    raise AssertionError(f"unknown wire kind: {wire_kind}")


@pytest.mark.parametrize("wire_kind", ("plain", "safe", "outcome"))
def test_typed_state_round_trip_preserves_decimal_and_bytes(
    _wire_backend: str, wire_kind: str
) -> None:
    """Decimal and bytes retain their exact typed values on every state boundary."""
    state = _typed_state()
    payload = _encode_state(state, wire_kind)

    if wire_kind == "outcome":
        restored = deserialize_outcome(payload).state
    elif wire_kind == "safe":
        restored = deserialize_state_safe(payload)
    else:
        restored = deserialize_state(payload)

    assert restored.run_id == state.run_id
    _assert_typed_state(restored)


@pytest.mark.parametrize("value", (float("nan"), float("inf"), float("-inf")))
@pytest.mark.parametrize("wire_kind", ("plain", "safe", "outcome"))
def test_nested_non_finite_values_are_rejected(
    _wire_backend: str, wire_kind: str, value: float
) -> None:
    state = ExperimentState(run_id="wire-01-non-finite", params={"nested": [value]})

    with pytest.raises((TypeError, ValueError)):
        _encode_state(state, wire_kind)


@pytest.mark.parametrize("wire_kind", ("plain", "safe", "outcome"))
def test_nested_unsupported_values_are_rejected(_wire_backend: str, wire_kind: str) -> None:
    state = ExperimentState(
        run_id="wire-01-unsupported",
        params={"nested": {"unsupported": object()}},
    )

    with pytest.raises((TypeError, ValueError)):
        _encode_state(state, wire_kind)


def test_safe_digest_binds_the_exact_typed_wire_bytes(_wire_backend: str) -> None:
    payload, hex_digest = serialize_state_safe(_typed_state())
    body = payload[1:-32]

    assert payload[:1] == b"\x01"
    assert hashlib.sha256(body).hexdigest() == hex_digest
    assert hashlib.sha256(body).digest() == payload[-32:]
    _assert_typed_state(deserialize_state_safe(payload))

    corrupted = payload[:5] + bytes([payload[5] ^ 0x01]) + payload[6:]
    with pytest.raises(DeserializationError, match="Integrity check failed"):
        deserialize_state_safe(corrupted)


def test_legacy_v0_and_v1_readers_remain_compatible() -> None:
    legacy = deserialize_state(b'{"run_id":"wire-01-legacy-v0"}')
    assert legacy.run_id == "wire-01-legacy-v0"

    versioned, _ = serialize_state_safe(ExperimentState(run_id="wire-01-v1"))
    assert deserialize_state(versioned).run_id == "wire-01-v1"


def test_real_artifact_ref_and_output_aware_outcome_round_trip(_wire_backend: str) -> None:
    ref = _artifact_ref()
    outcome = OutputAwareNodeOutcome(
        status="ok",
        state=_typed_state(),
        artifacts=[ref],
        output_dispositions=(
            NodeOutputDisposition(
                output_key="transport_ref",
                disposition="produced",
                artifact_ref=ref,
            ),
        ),
        supporting_artifacts={"actual_source": ref},
    )

    restored = deserialize_outcome(serialize_outcome(outcome))

    assert type(restored) is OutputAwareNodeOutcome
    assert restored.artifacts == [ref]
    assert restored.output_dispositions[0].artifact_ref == ref
    assert restored.supporting_artifacts["actual_source"] == ref
    _assert_typed_state(restored.state)
