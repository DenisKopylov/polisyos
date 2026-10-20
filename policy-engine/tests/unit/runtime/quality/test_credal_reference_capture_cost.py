from __future__ import annotations

import json
from collections import UserDict

import pytest


def test_nested_dict_capture_serializes_one_wire_root(monkeypatch: pytest.MonkeyPatch) -> None:
    """A nested mapping snapshot has linear wire work and preserves the legacy projection."""

    from polisyos.runtime.quality import credal_reference as owner

    source: dict[str, object] = {"leaf": {"items": [1, "value", None]}}
    for depth in range(64):
        source = {f"level_{depth:02d}": source}
    expected = json.loads(json.dumps(source, ensure_ascii=False, sort_keys=False, default=str))
    dumps_calls = 0
    loads_calls = 0
    original_dumps = owner.json.dumps
    original_loads = owner.json.loads

    def counted_dumps(*args: object, **kwargs: object) -> str:
        nonlocal dumps_calls
        dumps_calls += 1
        return original_dumps(*args, **kwargs)

    def counted_loads(*args: object, **kwargs: object) -> object:
        nonlocal loads_calls
        loads_calls += 1
        return original_loads(*args, **kwargs)

    monkeypatch.setattr(owner.json, "dumps", counted_dumps)
    monkeypatch.setattr(owner.json, "loads", counted_loads)
    captured = owner._freeze_reference_payload(source)

    assert dumps_calls == 1
    assert loads_calls == 0
    assert owner._json_ready(captured) == expected
    assert dumps_calls == 1
    assert loads_calls == 1


def test_shared_mapping_dag_is_captured_once_and_keeps_repeated_wire_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Memoization follows unique containers without changing JSON's unfolded result."""

    from polisyos.runtime.quality import credal_reference as owner

    depth = 9
    source: dict[str, object] = {"leaf": [1, "payload"]}
    for _ in range(depth):
        source = {"left": source, "right": source}
    expected = json.loads(json.dumps(source, ensure_ascii=False, sort_keys=False, default=str))
    key_capture_calls = 0
    original_freeze_key = owner._freeze_reference_mapping_key

    def counted_freeze_key(key: object) -> object:
        nonlocal key_capture_calls
        key_capture_calls += 1
        return original_freeze_key(key)

    monkeypatch.setattr(owner, "_freeze_reference_mapping_key", counted_freeze_key)
    captured = owner._freeze_reference_payload(source)

    assert key_capture_calls == 1 + 2 * depth
    assert owner._json_ready(captured) == expected
    assert captured["left"] is captured["right"]


def test_hidden_mapping_children_keep_standard_json_integer_limit() -> None:
    """A non-dict Mapping remains a string wire value without hiding invalid children."""

    from polisyos.runtime.quality import credal_reference as owner

    class HiddenLargeValueMapping(UserDict):
        def __str__(self) -> str:
            return "hidden-map"

    too_many_digits = 10**5000
    wrapped = HiddenLargeValueMapping({"child": {"value": too_many_digits}})
    with pytest.raises(ValueError, match="Exceeds the limit"):
        owner._freeze_reference_payload(wrapped)


def test_generic_mapping_wire_fallback_and_lookup_snapshot_remain_distinct() -> None:
    """A generic Mapping keeps its str wire while its captured lookup remains immutable."""

    from polisyos.runtime.quality import credal_reference as owner

    mapping_data = {"owner": "before", "nested": {"count": 2}}
    generic_mapping = UserDict(mapping_data)
    source = {"generic": generic_mapping, "regular": {"ready": True}}
    expected = json.loads(json.dumps(source, ensure_ascii=False, sort_keys=False, default=str))

    captured = owner._freeze_reference_payload(source)
    mapping_data["owner"] = "after"

    assert captured["generic"]["owner"] == "before"
    assert owner._json_ready(captured) == expected


def test_frozen_payloads_remain_unhashable_and_cycles_are_refused() -> None:
    """The cost optimization preserves identity-free immutable and cycle behavior."""

    from polisyos.runtime.quality import credal_reference as owner

    source: dict[str, object] = {"shared": {"value": ["x"]}}
    frozen = owner._freeze_reference_payload(source)
    assert type(frozen).__hash__ is None
    with pytest.raises(TypeError, match="unhashable type"):
        hash(frozen)

    cycle: dict[str, object] = {}
    cycle["self"] = cycle
    with pytest.raises(ValueError, match="Circular reference detected"):
        owner._freeze_reference_payload(cycle)


def test_legacy_wire_matrix_matches_existing_snapshot_rules() -> None:
    """The optimized snapshot retains deterministic legacy wires across supported values."""

    import math

    from polisyos.runtime.quality import credal_reference as owner

    class DictSubclass(dict[str, object]):
        pass

    class StringSubclass(str):
        pass

    class IntegerSubclass(int):
        pass

    class FloatSubclass(float):
        pass

    def legacy_key(key: object) -> str | int | float | bool | None:
        if key is None or type(key) is bool:
            return key
        if isinstance(key, str):
            return str.__str__(key)
        if isinstance(key, int):
            return int.__int__(key)
        if isinstance(key, float):
            return float.__float__(key)
        raise TypeError("credal_reference_mapping_key_not_json_scalar")

    def legacy_capture(value: object) -> object:
        if isinstance(value, dict):
            return {legacy_key(key): legacy_capture(item) for key, item in sorted(value.items())}
        if isinstance(value, UserDict):
            fallback_text = str(value)
            for item in value.values():
                legacy_capture(item)
            return fallback_text
        if isinstance(value, list | tuple):
            return [legacy_capture(item) for item in value]
        if type(value) is bytes:
            return str(value)
        if type(value) in (bool, type(None), str, int, float):
            return value
        if isinstance(value, str):
            return str.__str__(value)
        if isinstance(value, int):
            return int.__int__(value)
        if isinstance(value, float):
            return float.__float__(value)
        if isinstance(value, bytes):
            return str(value)
        return str(value)

    wire_cases: tuple[object, ...] = (
        {"z": 2, "a": {"nested": [1, "unicode —", None]}},
        DictSubclass({"z": 2, "a": {"nested": [1, "value", None]}}),
        {"generic": UserDict({"z": 2, "a": [True, "value"]})},
        {"bytes": b"\x00\xff", "tuple": (1, "two")},
        {"float": [float("inf"), float("-inf"), float("nan"), -0.0]},
        {
            "subclasses": [
                StringSubclass("text"),
                IntegerSubclass(7),
                FloatSubclass(1.5),
            ]
        },
        {False: "false", 1: "integer", 2.5: "fraction"},
        None,
        True,
        "root text",
        17,
        -0.0,
        b"root bytes",
    )
    for source in wire_cases:
        captured = owner._freeze_reference_payload(source)
        actual = owner._json_ready(captured)
        expected = json.loads(
            json.dumps(
                legacy_capture(source),
                ensure_ascii=False,
                sort_keys=False,
                default=str,
            )
        )
        assert json.dumps(actual, ensure_ascii=False, sort_keys=False, default=str) == json.dumps(
            expected, ensure_ascii=False, sort_keys=False, default=str
        )

    assert math.copysign(1.0, owner._json_ready(owner._freeze_reference_payload(-0.0))) == -1.0

    with pytest.raises(TypeError):
        owner._freeze_reference_payload({1: "integer", "mixed": "key"})


def test_alias_memo_bounds_volatile_fallback_to_one_source_snapshot() -> None:
    """Stateful fallback text is sampled once per unique aliased container snapshot."""

    from polisyos.runtime.quality import credal_reference as owner

    class VolatileText:
        def __init__(self) -> None:
            self.calls = 0

        def __str__(self) -> str:
            self.calls += 1
            return f"sample-{self.calls}"

    fallback = VolatileText()
    shared = {"fallback": fallback}
    frozen = owner._freeze_reference_payload({"left": shared, "right": shared})

    assert fallback.calls == 1
    assert owner._json_ready(frozen) == {
        "left": {"fallback": "sample-1"},
        "right": {"fallback": "sample-1"},
    }
