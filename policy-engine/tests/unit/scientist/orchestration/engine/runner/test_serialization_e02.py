"""Exact Decimal types on current state/outcome writers and legacy readers."""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import sys
from decimal import Decimal
from itertools import pairwise

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


def test_real_worker_process_consumes_state_and_emits_exact_typed_outcome(backend, tmp_path):
    """Exercise the actual remote worker bridge through a safe outer process."""
    from tests.unit.scientist.orchestration.engine.runner.decimal_worker_transport import (
        execute_decimal_worker,
    )

    physical_attempts = tmp_path / "attempts.jsonl"
    original = _state()
    payload = {
        "node_id": "scientist.node_decimal_transport@1.0.0",
        "alias": "decimal",
        "state_bytes": wire.serialize_state(original),
        # Generic custom IDs are untimed on macOS: the closed spawn timeout
        # boundary admits only the canonical ResolveParameters node. Linux
        # retains the existing fork-backed timed route.
        "timeout_s": 2.0 if sys.platform == "linux" else None,
        "context_meta": {
            "run_id": original.run_id,
            "store_config": {"backend": "filesystem", "root": str(tmp_path / "store")},
        },
    }
    # The test harness itself must not fork pytest's already multithreaded
    # process on macOS. The Linux child still exercises the production timed
    # fork path for this custom node.
    outer_start_method = "fork" if sys.platform == "linux" else "spawn"
    process_context = multiprocessing.get_context(outer_start_method)
    parent, child = process_context.Pipe()
    process = process_context.Process(
        target=execute_decimal_worker,
        args=(
            payload,
            backend,
            original.budgets,
            str(physical_attempts),
            child,
        ),
    )
    process.start()
    child.close()
    try:
        assert parent.poll(10.0), "actual worker did not emit an outcome"
        kind, actual_bytes = parent.recv()
        assert kind == "result", actual_bytes
        restored = wire.deserialize_outcome(actual_bytes)
        assert restored.status == "ok"
        _assert_budgets(original, restored.state)
        attempts = [json.loads(line) for line in physical_attempts.read_text().splitlines()]
        assert len(attempts) == 1
        assert attempts[0]["run_id"] == original.run_id
        chain = attempts[0]["ancestry"]
        assert chain[0] == {"pid": attempts[0]["pid"], "ppid": attempts[0]["ppid"]}
        assert all(left["ppid"] == right["pid"] for left, right in pairwise(chain))
        assert process.pid != os.getpid()
        if sys.platform == "darwin":
            # The untimed generic worker runs inside the fresh outer worker.
            assert attempts[0]["pid"] == process.pid
        else:
            # Linux's timed fork route owns a nested attempt process.
            assert process.pid in [ancestor["pid"] for ancestor in chain[1:]]
            assert attempts[0]["pid"] not in {os.getpid(), process.pid}
    finally:
        process.join(10.0)
        if process.is_alive():
            process.terminate()
            process.join(5.0)
        parent.close()
    assert process.exitcode == 0


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
