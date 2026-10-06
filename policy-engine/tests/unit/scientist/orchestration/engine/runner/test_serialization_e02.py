"""Exact Decimal types on current state/outcome writers and legacy readers."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal

import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.orchestration.engine.protocol import (
    NodeError,
    NodeOutcome,
    OutputAwareNodeOutcome,
)
from polisyos.scientist.orchestration.engine.runner import serialization as wire
from polisyos.scientist.orchestration.engine.state import ExperimentState


@pytest.fixture(params=["stdlib", "orjson"])
def backend(request, monkeypatch):
    if request.param == "stdlib":
        monkeypatch.setattr(
            wire, "_dumps", lambda obj: json.dumps(obj, separators=(",", ":")).encode()
        )
        monkeypatch.setattr(wire, "_loads", json.loads)
    elif wire.orjson is None:
        pytest.skip("orjson tool input is not installed")
    wire._WIRE_MODEL_TYPES = None
    return request.param


def _state() -> ExperimentState:
    return ExperimentState(
        run_id="wire-current",
        budgets={
            "run": Decimal("123456789123456789.00000000000000000000001"),
            "scale": Decimal("1.2300"),
        },
    )


def _assert_budgets(before: ExperimentState, after: ExperimentState) -> None:
    for key, value in before.budgets.items():
        assert type(after.budgets[key]) is Decimal
        assert after.budgets[key].as_tuple() == value.as_tuple()


@pytest.mark.parametrize("safe", [False, True])
def test_actual_state_roundtrip_cold_and_warm_preserves_decimal_type(backend, safe) -> None:
    state = _state()
    for _ in range(2):
        if safe:
            payload, _ = wire.serialize_state_safe(state)
            restored = wire.deserialize_state_safe(payload)
        else:
            restored = wire.deserialize_state(wire.serialize_state(state))
        _assert_budgets(state, restored)


def test_any_nested_decimal_and_typed_artifact_ref_survive_actual_outcome(backend) -> None:
    ref = ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex(hashlib.sha256(b"e02-ref").hexdigest()),
        kind="test.e02",
        media_type="application/json",
    )
    outcome = NodeOutcome(
        status="fail",
        state=_state(),
        error=NodeError(
            code="expected",
            message="typed payload",
            details={
                "nested": [{"amount": Decimal("0.0000000000000000000001"), "ref": ref}],
                "user_mapping": {"_type": "decimal", "value": "ordinary user text"},
            },
        ),
    )
    restored = wire.deserialize_outcome(wire.serialize_outcome(outcome))
    _assert_budgets(outcome.state, restored.state)
    value = restored.error.details["nested"][0]
    assert type(value["amount"]) is Decimal
    assert value["amount"] == Decimal("0.0000000000000000000001")
    assert type(value["ref"]) is ArtifactRef
    assert value["ref"] == ref
    assert restored.error.details["user_mapping"] == outcome.error.details["user_mapping"]


def test_output_aware_outcome_remains_typed(backend) -> None:
    outcome = OutputAwareNodeOutcome(status="ok", state=_state(), output_dispositions=())
    restored = wire.deserialize_outcome(wire.serialize_outcome(outcome))
    assert type(restored) is OutputAwareNodeOutcome
    _assert_budgets(outcome.state, restored.state)


@pytest.mark.parametrize(
    "replacement", ["0.1", 0.1, True, None, {"_type": "decimal", "value": 0.1}]
)
def test_current_version_rejects_untyped_decimal_budget(backend, replacement) -> None:
    payload = json.loads(wire.serialize_state(_state()))
    assert payload["wire_schema"] == "polisyos.scientist.state_wire.v2"
    payload["value"]["budgets"]["run"] = replacement
    with pytest.raises(wire.DeserializationError):
        wire.deserialize_state(json.dumps(payload).encode())


def test_current_outcome_rejects_untyped_nested_budget(backend) -> None:
    payload = json.loads(wire.serialize_outcome(NodeOutcome(status="ok", state=_state())))
    assert payload["wire_schema"] == "polisyos.scientist.outcome_wire.v2"
    payload["value"]["state"]["budgets"]["run"] = "0.1"
    with pytest.raises(wire.DeserializationError):
        wire.deserialize_outcome(json.dumps(payload).encode())


def test_legacy_numeric_budget_read_remains_explicitly_compatible(backend) -> None:
    restored = wire.deserialize_state(b'{"run_id":"legacy", "budgets":{"run":0.1}}')
    assert restored.budgets["run"] == Decimal("0.1")


@pytest.mark.parametrize("bad", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_nonfinite_decimal_writer_refuses(backend, bad) -> None:
    state = ExperimentState.model_construct(run_id="bad", budgets={"run": bad})
    with pytest.raises((TypeError, ValueError)):
        wire.serialize_state(state)


def test_safe_hash_tamper_refuses_before_typed_decode(backend) -> None:
    payload, _ = wire.serialize_state_safe(_state())
    changed = bytearray(payload)
    changed[10] ^= 1
    with pytest.raises(wire.DeserializationError, match="Integrity"):
        wire.deserialize_state_safe(bytes(changed))
