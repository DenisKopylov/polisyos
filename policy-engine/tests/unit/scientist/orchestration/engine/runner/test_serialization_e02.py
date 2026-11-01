"""Exact Decimal types on current state/outcome writers and legacy readers."""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import sys
from decimal import Decimal
from itertools import pairwise
from typing import Any

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
from polisyos.scientist.orchestration.engine.state_branching import (
    StateMutation,
    branch_state,
    mutation_journal_for_state,
)


@pytest.fixture(params=["stdlib", "orjson"])
def backend(request, monkeypatch):
    if request.param == "stdlib":
        monkeypatch.setattr(
            wire, "_dumps", lambda obj: json.dumps(obj, separators=(",", ":")).encode()
        )
        monkeypatch.setattr(wire, "_loads", json.loads)
    else:
        orjson = pytest.importorskip("orjson")
        monkeypatch.setattr(wire, "_dumps", orjson.dumps)
        monkeypatch.setattr(wire, "_loads", orjson.loads)
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


@pytest.mark.parametrize("boundary", ["state", "outcome", "safe"])
def test_negative_zero_budget_retains_its_exact_tuple(backend: str, boundary: str) -> None:
    original = Decimal("-0.00")
    state = ExperimentState(run_id="wire-budget-negative-zero", budgets={"run": original})
    if boundary == "state":
        restored = wire.deserialize_state(wire.serialize_state(state))
    elif boundary == "safe":
        payload, _ = wire.serialize_state_safe(state)
        restored = wire.deserialize_state_safe(payload)
    else:
        restored = wire.deserialize_outcome(
            wire.serialize_outcome(NodeOutcome(status="ok", state=state))
        ).state
    assert type(restored.budgets["run"]) is Decimal
    assert restored.budgets["run"].as_tuple() == original.as_tuple()


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
    "unsupported_outcome", [False, True], ids=["typed-result", "codec-refusal"]
)
def test_real_worker_process_consumes_state_and_emits_exact_typed_outcome(
    backend, tmp_path, unsupported_outcome
):
    """Exercise the actual remote worker bridge through a safe outer process."""
    from tests._helpers.worker_transport_wait import reap_worker_process, receive_worker_message
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
        "max_retries": 3,
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
            unsupported_outcome,
        ),
    )
    process.start()
    child.close()
    try:
        kind, actual_bytes = receive_worker_message(parent, process)
        if unsupported_outcome:
            assert kind == "error", actual_bytes
            assert "Unsupported type on runner wire: object" in actual_bytes
        else:
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
        assert len({entry["pid"] for entry in chain}) == len(chain)
        assert chain[-1]["ppid"] == 0
        assert process.pid != os.getpid()
        if sys.platform == "darwin":
            # The untimed generic worker runs inside the fresh outer worker.
            assert attempts[0]["pid"] == process.pid
        else:
            # Linux's timed fork route owns a nested attempt process.
            assert process.pid in [ancestor["pid"] for ancestor in chain[1:]]
            assert attempts[0]["pid"] not in {os.getpid(), process.pid}
    finally:
        try:
            reap_worker_process(process)
        finally:
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


def _nested_wire_value(shape: str, layers: int, *, leaf: Any = Decimal("-0.00")) -> Any:
    value = leaf
    for index in range(layers):
        wrapper = shape if shape != "mixed" else ("plain", "escaped", "list")[index % 3]
        if wrapper == "plain":
            value = {"child": value}
        elif wrapper == "escaped":
            value = {"_type": "ordinary user data", "child": value}
        elif wrapper == "list":
            value = [value]
        else:
            assert wrapper == "model"
            value = StateMutation(path="params.child", operation="set", value=value)
    return value


def _assert_negative_zero_leaf(value: Any) -> None:
    while not isinstance(value, Decimal):
        if isinstance(value, StateMutation):
            value = value.value
        elif isinstance(value, dict):
            value = value["child"]
        else:
            value = value[0]
    assert value.as_tuple() == Decimal("-0.00").as_tuple()


@pytest.mark.parametrize("shape", ["plain", "escaped", "list", "mixed", "model"])
@pytest.mark.parametrize("layers", [1, 40, 64, 80])
@pytest.mark.parametrize("boundary", ["state", "outcome", "safe"])
def test_accepted_writer_depth_roundtrips_every_transport_boundary(
    backend: str, shape: str, layers: int, boundary: str
) -> None:
    """Technical wrappers consume no extra semantic depth on the real backends."""
    value = _nested_wire_value(shape, layers)
    # The dictionary's values are Any. A model directly in params would first
    # be coerced by JsonValue's scalar/list/dict union, before reaching wire.
    state = ExperimentState(run_id="wire-depth", params={"holder": {"nested": value}})
    if boundary == "state":
        restored = wire.deserialize_state(wire.serialize_state(state))
    elif boundary == "safe":
        payload, _ = wire.serialize_state_safe(state)
        restored = wire.deserialize_state_safe(payload)
    else:
        restored = wire.deserialize_outcome(
            wire.serialize_outcome(NodeOutcome(status="ok", state=state))
        ).state
    assert restored.params["holder"]["nested"] == value
    _assert_negative_zero_leaf(restored.params["holder"]["nested"])


@pytest.mark.parametrize("shape", ["plain", "escaped", "list", "mixed", "model"])
def test_semantic_depth_boundary_is_the_same_for_plain_and_tagged_children(shape: str) -> None:
    """Bypass only JSON syntax depth to isolate the shared semantic 128-edge limit."""
    value = _nested_wire_value(shape, wire._WIRE_MAX_DEPTH)
    assert wire._decode_wire_value(wire._encode_wire_value(value)) == value
    with pytest.raises(TypeError, match="Wire serialization depth exceeds"):
        wire._encode_wire_value(_nested_wire_value(shape, wire._WIRE_MAX_DEPTH + 1))
    with pytest.raises(wire.DeserializationError, match="Wire deserialization depth exceeds"):
        wire._decode_wire_value(wire._encode_wire_value(value), depth=1)


def test_root_model_root_is_one_semantic_child_in_both_directions() -> None:
    artifact_id = ArtifactID.from_sha256_hex("a" * 64)
    payload = wire._encode_wire_value(artifact_id, depth=wire._WIRE_MAX_DEPTH - 1)
    assert wire._decode_wire_value(payload, depth=wire._WIRE_MAX_DEPTH - 1) == artifact_id
    with pytest.raises(TypeError, match="Wire serialization depth exceeds"):
        wire._encode_wire_value(artifact_id, depth=wire._WIRE_MAX_DEPTH)
    with pytest.raises(wire.DeserializationError, match="Wire deserialization depth exceeds"):
        wire._decode_wire_value(payload, depth=wire._WIRE_MAX_DEPTH)


@pytest.mark.parametrize("shape", ["plain", "escaped", "list", "mixed", "model"])
@pytest.mark.parametrize("boundary", ["state", "outcome", "safe"])
def test_near_limit_backend_refuses_before_bytes_or_reads_its_entire_accepted_profile(
    backend: str, shape: str, boundary: str, record_property: Any
) -> None:
    """The JSON parser's raw-wrapper limit cannot create an unreadable success."""
    accepted, refused = [], []
    for layers in (81, 82, 83, 84, 85, 86, 124, 125, 126, 127, 128):
        value = _nested_wire_value(shape, layers)
        state = ExperimentState(run_id="wire-parser-limit", params={"holder": {"nested": value}})
        try:
            if boundary == "state":
                payload = wire.serialize_state(state)
            elif boundary == "safe":
                payload, _ = wire.serialize_state_safe(state)
            else:
                payload = wire.serialize_outcome(NodeOutcome(status="ok", state=state))
        except TypeError as error:
            if not str(error).startswith("Wire serialization depth exceeds"):
                assert backend == "orjson"
                assert isinstance(error, wire.orjson.JSONEncodeError)
                assert "recursion" in str(error).lower()
            refused.append(layers)
            continue
        if boundary == "state":
            restored = wire.deserialize_state(payload)
        elif boundary == "safe":
            restored = wire.deserialize_state_safe(payload)
        else:
            restored = wire.deserialize_outcome(payload).state
        assert restored.params["holder"]["nested"] == value
        _assert_negative_zero_leaf(restored.params["holder"]["nested"])
        accepted.append(layers)
    assert 81 in accepted
    assert 128 in refused
    record_property("accepted_semantic_layers", accepted)
    record_property("refused_before_bytes_layers", refused)


@pytest.mark.parametrize("boundary", ["state", "outcome", "safe"])
def test_cycles_are_refused_before_the_backend_or_publication(
    backend: str, boundary: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    cycle: list[Any] = []
    cycle.append(cycle)
    state = ExperimentState(run_id="wire-cycle", params={"nested": cycle})
    dumped = []
    actual_dumps = wire._dumps

    def observed_dumps(value: Any) -> bytes:
        dumped.append(True)
        return actual_dumps(value)

    monkeypatch.setattr(wire, "_dumps", observed_dumps)
    if boundary == "state":
        writer, value = wire.serialize_state, state
    elif boundary == "safe":
        writer, value = wire.serialize_state_safe, state
    else:
        writer, value = wire.serialize_outcome, NodeOutcome(status="ok", state=state)
    with pytest.raises(TypeError, match="Cycle detected"):
        writer(value)
    assert dumped == []


def test_literal_legacy_v0_and_integrity_v1_budgets_remain_readable(backend: str) -> None:
    legacy = b'{"run_id":"wire-historical-literal","budgets":{"run":"1.2300"}}'
    framed = b"\x01" + legacy + hashlib.sha256(legacy).digest()
    for payload in (legacy, framed):
        restored = wire.deserialize_state(payload)
        assert restored.run_id == "wire-historical-literal"
        assert restored.budgets["run"].as_tuple() == Decimal("1.2300").as_tuple()


def test_mapping_at_journal_profile_limit_survives_actual_sidecar(backend: str) -> None:
    state = branch_state(
        ExperimentState(run_id="wire-depth-journal"),
        write_paths=["params"],
    ).state
    # The canonical journal's dictionary edge costs two levels; its actual
    # admitted 128-level attachment profile accepts these 62 wrappers.
    value = _nested_wire_value("plain", 62, leaf="journal-leaf")
    state.params["nested"] = value
    restored = wire.deserialize_outcome(
        wire.serialize_outcome(NodeOutcome(status="ok", state=state))
    )
    assert restored.state.params["nested"] == value
    journal = mutation_journal_for_state(restored.state)
    assert journal is not None
    assert len(journal.operations) == 1
    assert journal.operations[0].path == "params.nested"
    assert journal.operations[0].value == value


@pytest.mark.parametrize("type_name", ["decimal", "ordinary user data"])
def test_journal_reserved_mapping_uses_its_actual_canonical_profile_before_publication(
    backend: str, type_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = branch_state(
        ExperimentState(run_id="wire-journal-canonical-profile"), write_paths=["params"]
    ).state
    value = {"_type": type_name, "value": "1.20"}
    state.params["nested"] = value
    outcome = NodeOutcome(status="ok", state=state)
    if type_name == "decimal":
        # A raw mapping admitted by Canon.2 remains a mapping on the wire, not
        # an implicitly decoded Decimal. No canonical journal upgrade occurs.
        restored = wire.deserialize_outcome(wire.serialize_outcome(outcome))
        assert restored.state.params["nested"] == value
        assert mutation_journal_for_state(restored.state).operations[0].value == value
        return
    dumped = []
    actual_dumps = wire._dumps

    def observed_dumps(value: Any) -> bytes:
        dumped.append(True)
        return actual_dumps(value)

    monkeypatch.setattr(wire, "_dumps", observed_dumps)
    with pytest.raises(ValueError, match="Unknown canonical _type"):
        wire.serialize_outcome(outcome)
    assert dumped == []


def test_writer_rejects_a_foreign_journal_path_before_returning_bytes(backend: str) -> None:
    state = branch_state(ExperimentState(run_id="wire-journal-path"), write_paths=["params"]).state
    journal = mutation_journal_for_state(state)
    assert journal is not None
    journal.operations.append(StateMutation(path="not_an_experiment_field.child", operation="set"))
    with pytest.raises(ValueError, match="State mutation path is not rooted"):
        wire.serialize_outcome(NodeOutcome(status="ok", state=state))


def test_writer_admits_actual_sidecar_not_an_original_model_dump_override(backend: str) -> None:
    state = branch_state(
        ExperimentState(run_id="wire-journal-shadow"), write_paths=["params"]
    ).state
    state.params["nested"] = {"_type": "outside the canonical journal profile"}
    journal = mutation_journal_for_state(state)
    assert journal is not None
    callbacks = []

    def forged_projection(**_kwargs: Any) -> dict[str, Any]:
        callbacks.append(True)
        return {"path": "params.nested", "operation": "set", "value": "unrelated allowed value"}

    object.__setattr__(journal.operations[0], "model_dump", forged_projection)
    with pytest.raises(ValueError, match="Unknown canonical _type"):
        wire.serialize_outcome(NodeOutcome(status="ok", state=state))
    assert callbacks == []


@pytest.mark.parametrize("shape", ["plain", "escaped", "list", "mixed", "model"])
@pytest.mark.parametrize("boundary", ["state", "outcome", "safe"])
def test_public_writer_refuses_values_past_its_semantic_depth_before_returning_bytes(
    backend: str, shape: str, boundary: str
) -> None:
    state = ExperimentState(
        run_id="wire-too-deep", params={"nested": _nested_wire_value(shape, wire._WIRE_MAX_DEPTH)}
    )
    if boundary == "state":
        writer, value = wire.serialize_state, state
    elif boundary == "safe":
        writer, value = wire.serialize_state_safe, state
    else:
        writer, value = wire.serialize_outcome, NodeOutcome(status="ok", state=state)
    with pytest.raises(TypeError, match="Wire serialization depth exceeds"):
        writer(value)


@pytest.mark.parametrize(
    "invalid",
    [
        {"_type": "unknown"},
        {"_type": "model", "module": "foreign", "qualname": "Forged", "value": {}},
        {"_type": "mapping", "entries": [["same", 1], ["same", 2]]},
        {"_type": "mapping", "entries": [[1, "not a string key"]]},
        {"_type": "bytes", "encoding": "base64", "data": "@malformed@"},
        {"_type": "decimal", "value": "NaN"},
    ],
)
def test_malformed_tag_corpus_never_becomes_a_typed_state(backend: str, invalid: Any) -> None:
    payload = json.loads(wire.serialize_state(_state()))
    payload["value"]["params"] = {"invalid": invalid}
    with pytest.raises(wire.DeserializationError):
        wire.deserialize_state(wire._dumps(payload))


def test_declared_any_normalizations_remain_compatible(backend: str) -> None:
    state = ExperimentState(
        run_id="wire-normalized-types",
        params={
            "holder": {
                "tuple": (1, Decimal("1.20")),
                "bytearray": bytearray(b"x"),
                "view": memoryview(b"y"),
            }
        },
    )
    restored = wire.deserialize_state(wire.serialize_state(state))
    holder = restored.params["holder"]
    assert type(holder["tuple"]) is list
    assert holder["tuple"] == [1, Decimal("1.20")]
    assert type(holder["bytearray"]) is bytes
    assert holder["bytearray"] == b"x"
    assert type(holder["view"]) is bytes
    assert holder["view"] == b"y"
