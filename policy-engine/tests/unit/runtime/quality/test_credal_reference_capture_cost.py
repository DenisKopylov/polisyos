from __future__ import annotations

import json
from collections import UserDict
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


def test_nested_dict_capture_serializes_one_wire_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    assert loads_calls == 0


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
            "duplicate_nan_keys": {
                float("nan"): "first",
                float("nan"): "last",
            }
        },
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

    for invalid_keys in (
        {1: "integer", "1": "string"},
        {None: "null", "null": "string"},
        {True: "boolean", "true": "string"},
        {1: "integer", "mixed": "key"},
    ):
        with pytest.raises(TypeError):
            owner._freeze_reference_payload(invalid_keys)


def test_alias_memo_bounds_stateful_mapping_to_one_snapshot_per_capture() -> None:
    """A Mapping alias shares one fallback sample, while a later capture sees new state."""

    from polisyos.runtime.quality import credal_reference as owner

    class StatefulMapping(UserDict[str, object]):
        def __init__(self) -> None:
            super().__init__({"value": "before"})
            self.calls = 0

        def __str__(self) -> str:
            self.calls += 1
            value = self["value"]
            return f"sample-{self.calls}-{value}"

    source = StatefulMapping()
    frozen = owner._freeze_reference_payload({"left": source, "right": source})

    assert source.calls == 1
    assert frozen["left"] is frozen["right"]
    assert owner._json_ready(frozen) == {
        "left": "sample-1-before",
        "right": "sample-1-before",
    }

    source["value"] = "after"
    next_snapshot = owner._freeze_reference_payload({"only": source})

    assert source.calls == 2
    assert owner._json_ready(next_snapshot) == {"only": "sample-2-after"}


def test_exact_scalars_skip_mapping_abc_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exact scalar leaves avoid ABC mapping checks while container dispatch stays intact."""

    from polisyos.runtime.quality import credal_reference as owner

    original_mapping = owner.Mapping
    scalar_types = {bool, type(None), str, int, float, bytes}
    scalar_checks: list[type[object]] = []

    class MappingProbeMeta(type):
        def __instancecheck__(cls, instance: object) -> bool:
            if type(instance) in scalar_types:
                scalar_checks.append(type(instance))
            return isinstance(instance, original_mapping)

    class MappingProbe(metaclass=MappingProbeMeta):
        pass

    monkeypatch.setattr(owner, "Mapping", MappingProbe)
    values: tuple[object, ...] = (False, None, "text", 17, -0.0, b"bytes")
    for value in values:
        assert owner._capture_reference_payload(value) == value

    assert scalar_checks == []


def test_cached_wire_projection_preserves_key_coercion_order_and_edge_hash() -> None:
    """The direct projection equals json.loads of the legacy wire and keeps hashes."""

    from polisyos.runtime.quality import credal_reference as owner

    first_nan = float("nan")
    second_nan = float("nan")
    provenance = {
        "selected_source_profile": {
            "source_read_prepared_at_utc": "2026-06-29T00:00:00Z",
            "details": {
                "integer_key": {1: "one"},
                "duplicate_nan_keys": {first_nan: "first", second_nan: "last"},
                "sequence": (1, "two"),
            },
        },
        "owner": "L2",
    }
    expected_wire_projection = json.loads(
        json.dumps(provenance, ensure_ascii=False, sort_keys=True, default=str)
    )
    edge = owner.CredalReferenceEdge(
        modality="L2_VARIABLE",
        edge_id="variable:profile",
        status="confirmed",
        admissible_completions=(),
        provenance=provenance,
    )
    actual = edge.with_content_hash()

    assert json.dumps(
        owner._json_ready(actual.provenance),
        ensure_ascii=False,
        sort_keys=False,
        default=str,
    ) == json.dumps(
        expected_wire_projection,
        ensure_ascii=False,
        sort_keys=False,
        default=str,
    )
    expected_semantic_provenance = json.loads(
        json.dumps(expected_wire_projection, ensure_ascii=False, sort_keys=False, default=str)
    )
    expected_semantic_provenance["selected_source_profile"].pop("source_read_prepared_at_utc")
    expected_hash = owner.gy_content_hash(
        {
            "admissible_completions": [],
            "edge_id": "variable:profile",
            "modality": "L2_VARIABLE",
            "provenance": expected_semantic_provenance,
            "scale": None,
            "status": "confirmed",
            "unit": None,
        }
    )

    assert actual.content_hash == expected_hash
    assert json.dumps(
        actual.to_payload(), ensure_ascii=False, sort_keys=False, default=str
    ) == json.dumps(
        {
            "admissible_completions": [],
            "edge_id": "variable:profile",
            "modality": "L2_VARIABLE",
            "provenance": expected_wire_projection,
            "scale": None,
            "status": "confirmed",
            "unit": None,
            "content_hash": expected_hash,
        },
        ensure_ascii=False,
        sort_keys=False,
        default=str,
    )


def test_selected_l2_edges_reuse_one_immutable_profile_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The selected profile is dumped once and each edge keeps its legacy hash."""

    from polisyos.runtime.quality import credal_reference as owner

    profile_payload = {
        "source_snapshot_ref": "snapshot-ref-1",
        "source_snapshot_sha256": "a" * 64,
        "source_read_prepared_at_utc": "2026-06-29T00:00:00Z",
        "nested": {"items": [1, "two", None]},
    }

    class Profile:
        source_snapshot_ref = "snapshot-ref-1"
        source_snapshot_sha256 = "a" * 64

        def __init__(self) -> None:
            self.dump_calls = 0

        def model_dump(self, *, mode: str) -> dict[str, object]:
            assert mode == "json"
            self.dump_calls += 1
            return {
                **profile_payload,
                "nested": {"items": [1, "two", None]},
            }

    profile = Profile()
    rows = SimpleNamespace(
        source_snapshot_ref=profile.source_snapshot_ref,
        source_snapshot_sha256=profile.source_snapshot_sha256,
        version_id="version-1",
        synthetic_values=(),
    )
    selected = owner._PreparedL2Source(
        prepared_read=SimpleNamespace(read_credal_source_rows=lambda: rows),
        profile=profile,
        version="version-1",
    )
    source_edges = tuple(
        owner.CredalReferenceEdge(
            modality="L2_VARIABLE",
            edge_id=f"edge-{index}",
            status="confirmed",
            admissible_completions=(),
            provenance={"owner": "L2", "base": index},
        )
        for index in range(2)
    )
    monkeypatch.setattr(owner, "_iter_l2_source_edges", lambda *args, **kwargs: iter(source_edges))
    actual_edges = tuple(owner._iter_selected_l2_edges(tmp_path, selected, catalog_source=object()))

    assert profile.dump_calls == 1
    assert (
        actual_edges[0].provenance["selected_source_profile"]
        is actual_edges[1].provenance["selected_source_profile"]
    )
    for index, (source_edge, actual_edge) in enumerate(
        zip(source_edges, actual_edges, strict=True)
    ):
        expected_provenance = json.loads(
            json.dumps(
                {
                    "owner": "L2",
                    "base": index,
                    "selected_source_profile": profile_payload,
                },
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
        )
        expected_hash_provenance = json.loads(
            json.dumps(expected_provenance, ensure_ascii=False, sort_keys=False, default=str)
        )
        expected_hash_provenance["selected_source_profile"].pop("source_read_prepared_at_utc")
        expected_hash = owner.gy_content_hash(
            {
                "admissible_completions": [],
                "edge_id": source_edge.edge_id,
                "modality": source_edge.modality,
                "provenance": expected_hash_provenance,
                "scale": source_edge.scale,
                "status": source_edge.status,
                "unit": source_edge.unit,
            }
        )

        assert owner._json_ready(actual_edge.provenance) == expected_provenance
        assert actual_edge.content_hash == expected_hash
