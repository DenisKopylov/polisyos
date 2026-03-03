from __future__ import annotations

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
