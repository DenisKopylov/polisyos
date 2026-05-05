from __future__ import annotations

import pytest
from polisyos.common import serialization
from polisyos.core.canon import to_canonical_bytes


def test_fast_json_roundtrip_matches_payload() -> None:
    payload = {
        "alpha": 1,
        "beta": [1, 2, {"nested": True}],
        "gamma": {"x": 1.5, "y": "text"},
    }

    encoded = serialization.fast_json_dumps(payload, sort_keys=True)
    decoded = serialization.fast_json_loads(encoded)

    assert decoded == payload


def test_fast_json_fallback_works_without_orjson(monkeypatch) -> None:
    monkeypatch.setattr(serialization, "orjson", None)
    payload = {"k": "v", "n": 3}

    encoded_bytes = serialization.fast_json_dumps_bytes(payload, sort_keys=True)
    decoded = serialization.fast_json_loads(encoded_bytes)

    assert isinstance(encoded_bytes, bytes)
    assert decoded == payload


def test_canonical_path_is_unchanged_by_fast_json_helpers() -> None:
    payload = {"b": 2, "a": [3, 1]}
    baseline = to_canonical_bytes(payload)
    _ = serialization.fast_json_dumps(payload, sort_keys=False)
    after = to_canonical_bytes(payload)

    assert baseline == after


def test_failed_array_coercion_is_logged(monkeypatch) -> None:
    messages: list[str] = []

    class BrokenArray:
        def tolist(self):
            raise RuntimeError("coercion exploded")

    monkeypatch.setattr(
        serialization.logger,
        "warning",
        lambda message, *args, **kwargs: messages.append(message % args),
    )

    result = serialization.to_python_data(BrokenArray())

    assert isinstance(result, BrokenArray)
    assert messages
    assert "Serialization tolist() coercion failed" in messages[0]


def test_fast_json_rejects_cycles_without_recursion_error() -> None:
    payload: dict[str, object] = {}
    payload["self"] = payload

    with pytest.raises(serialization.SerializationCycleError):
        serialization.fast_json_dumps(payload)


def test_to_python_data_enforces_depth_budget() -> None:
    payload: object = {"leaf": True}
    for _ in range(4):
        payload = {"nested": payload}

    with pytest.raises(serialization.SerializationDepthError):
        serialization.to_python_data(payload, max_depth=2)


def test_fast_json_rejects_unsupported_objects_explicitly() -> None:
    class NotJson:
        pass

    with pytest.raises(serialization.UnsupportedSerializationError):
        serialization.fast_json_dumps({"value": NotJson()})
