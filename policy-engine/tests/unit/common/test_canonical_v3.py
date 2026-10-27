from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from decimal import Decimal
from types import FrameType, ModuleType

import pytest
from pydantic import BaseModel, ConfigDict, Field, field_serializer

from polisyos.common import canonical as common_codec
from polisyos.common.canonical import (
    CanonSpec,
    from_canonical_bytes,
    to_canonical_bytes,
)
from polisyos.core.canon import canon_json as core_codec
from polisyos.ir.model_layer import canon as ir_codec


@dataclass
class _RawRecord:
    _type: str
    value: str


class _ProjectedModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tag: str = Field(alias="_type")
    value: str
    ignored: str = Field(exclude=True)
    optional: str | None = None

    @field_serializer("value")
    def serialize_value(self, value: str) -> str:
        return f"serialized:{value}"


@pytest.mark.parametrize(
    "codec", [common_codec, core_codec, ir_codec], ids=["common", "core", "ir"]
)
def test_v3_projection_escapes_dataclasses_and_models_at_every_level(
    codec: ModuleType,
) -> None:
    spec = codec.CanonSpec(version="0.3.0")
    value = {
        "records": [
            _RawRecord(_type="decimal", value="1.0"),
            _ProjectedModel(tag="future", value="v", ignored="secret"),
            {"_type": "mapping", "entries": [["_type", "date"]]},
        ],
        "native": Decimal("1.0"),
    }
    expected = {
        "records": [
            {"_type": "decimal", "value": "1.0"},
            {"_type": "future", "value": "serialized:v"},
            {"_type": "mapping", "entries": [["_type", "date"]]},
        ],
        "native": Decimal("1.0"),
    }

    encoded = codec.to_canonical_bytes(value, spec)
    assert codec.from_canonical_bytes(encoded, version=spec.version) == expected
    assert codec.from_canonical_obj(json.loads(encoded), version=spec.version) == expected
    assert codec.to_canonical_bytes(_RawRecord("decimal", "1.0"), spec) != (
        codec.to_canonical_bytes(Decimal("1.0"), spec)
    )


@pytest.mark.parametrize(
    "codec", [common_codec, core_codec, ir_codec], ids=["common", "core", "ir"]
)
@pytest.mark.parametrize(
    ("value", "logical_depth"),
    [
        ({"_type": "future", "value": None}, 1),
        ({"outer": [{"_type": "future"}]}, 3),
        (_RawRecord("decimal", "1.0"), 1),
    ],
)
def test_v3_reader_and_writer_use_the_same_logical_depth(
    codec: ModuleType, value: object, logical_depth: int
) -> None:
    spec = codec.CanonSpec(version="0.3.0", max_depth=logical_depth, exclude_none=False)
    encoded = codec.to_canonical_bytes(value, spec)
    codec.from_canonical_bytes(encoded, version=spec.version, max_depth=logical_depth)
    with pytest.raises(ValueError, match="depth"):
        codec.to_canonical_bytes(
            value,
            codec.CanonSpec(version="0.3.0", max_depth=logical_depth - 1, exclude_none=False),
        )
    with pytest.raises(ValueError, match="depth"):
        codec.from_canonical_bytes(encoded, version=spec.version, max_depth=logical_depth - 1)


@pytest.mark.parametrize(
    "codec", [common_codec, core_codec, ir_codec], ids=["common", "core", "ir"]
)
@pytest.mark.parametrize(
    "payload",
    [
        b'{"_type":"date"}',
        b'{"_type":"date","iso":"2025-01-01","extra":0}',
        b'{"_type":"decimal","value":4}',
        b'{"_type":"bytes","encoding":"base64","data":"!"}',
    ],
)
def test_v3_rejects_malformed_native_envelopes(codec: ModuleType, payload: bytes) -> None:
    with pytest.raises(ValueError, match="malformed_canonical_native_envelope"):
        codec.from_canonical_bytes(payload, version="0.3.0")


@pytest.mark.parametrize(
    "codec", [common_codec, core_codec, ir_codec], ids=["common", "core", "ir"]
)
def test_v2_duplicate_member_compatibility_and_v3_refusal(codec: ModuleType) -> None:
    payload = b'{"value":1,"value":2}'
    assert codec.from_canonical_bytes(payload) == {"value": 2}
    with pytest.raises(ValueError, match="duplicate JSON object key"):
        codec.from_canonical_bytes(payload, version="0.3.0")


@pytest.mark.parametrize(
    "codec", [common_codec, core_codec, ir_codec], ids=["common", "core", "ir"]
)
def test_v3_rejects_non_json_number_constants(codec: ModuleType) -> None:
    with pytest.raises(ValueError, match="invalid JSON numeric constant"):
        codec.from_canonical_bytes(b'{"value":NaN}', version="0.3.0")


@pytest.mark.parametrize(
    "codec", [common_codec, core_codec, ir_codec], ids=["common", "core", "ir"]
)
def test_explicit_unknown_version_does_not_fall_back_to_v2(codec: ModuleType) -> None:
    with pytest.raises(ValueError, match="unsupported_canonical_codec_version"):
        codec.to_canonical_bytes({"value": 1}, codec.CanonSpec(version="0.4.0"))
    with pytest.raises(ValueError, match="unsupported_canonical_codec_version"):
        codec.from_canonical_bytes(b'{"value":1}', version="0.4.0")


@pytest.mark.parametrize(
    "codec", [common_codec, core_codec, ir_codec], ids=["common", "core", "ir"]
)
@pytest.mark.parametrize(
    ("name", "version"),
    [
        ("polisyos.core.run.owner-scope", "1.0"),
        ("polisyos.scientist.orchestration.engine.journal-proof", "1.0"),
        ("polisyos.idempotency.canon", "2.0"),
        ("polisyos.test.other-domain", "0.3.0"),
    ],
)
def test_legacy_named_hash_domains_keep_v2_codec_mechanics(
    codec: ModuleType, name: str, version: str
) -> None:
    spec = codec.CanonSpec(name=name, version=version, forbid_floats=False)
    assert codec.to_canonical_bytes({"value": 1.5}, spec) == (
        b'{"value":{"_type":"float","repr":"1.5"}}'
    )
    with pytest.raises(ValueError, match="Unknown canonical _type"):
        codec.to_canonical_bytes({"_type": "future"}, spec)


@pytest.mark.parametrize(
    "codec", [common_codec, core_codec, ir_codec], ids=["common", "core", "ir"]
)
def test_projection_cannot_change_the_selected_codec_version(codec: ModuleType) -> None:
    spec = codec.CanonSpec()

    class _MutatingModel(BaseModel):
        def model_dump(self, *args: object, **kwargs: object) -> dict[str, str]:
            object.__setattr__(spec, "version", "0.3.0")
            return {"_type": "decimal", "value": "1.0"}

    encoded = codec.to_canonical_bytes(_MutatingModel(), spec)
    assert encoded == b'{"_type":"decimal","value":"1.0"}'
    assert codec.from_canonical_bytes(encoded) == Decimal("1.0")


@pytest.mark.parametrize(
    "carrier",
    [
        core_codec.FloatHexRepresentation("0x1.0000000000000p+0"),
        core_codec.FloatHexRepresentation("-0x0.0p+0"),
        core_codec.BytesHexRepresentation("00ff"),
        core_codec.ArrayDigestRepresentation(
            dtype="<f8", shape=(2, 3), digest="sha256:" + "a" * 64
        ),
    ],
)
def test_core_v3_descriptor_carriers_decode_and_reencode_exactly(carrier: object) -> None:
    spec = core_codec.CanonSpec(version="0.3.0", forbid_floats=False)
    encoded = core_codec.to_canonical_bytes(carrier, spec)
    decoded = core_codec.from_canonical_bytes(encoded, version=spec.version)

    assert type(decoded) is type(carrier)
    assert decoded == carrier
    assert core_codec.to_canonical_bytes(decoded, spec) == encoded


def test_core_v3_descriptor_shape_cannot_be_manufactured_by_mapping() -> None:
    spec = core_codec.CanonSpec(version="0.3.0", forbid_floats=False)
    shaped = {"_type": "bytes_hex", "value": "00ff"}
    encoded = core_codec.to_canonical_bytes(shaped, spec)

    assert core_codec.from_canonical_bytes(encoded, version=spec.version) == shaped
    assert b'"_type":"mapping"' in encoded


def test_ir_v3_refuses_unescaped_core_descriptor() -> None:
    payload = b'{"_type":"bytes_hex","value":"00ff"}'
    with pytest.raises(ir_codec.CanonViolation, match="Unknown canonical _type"):
        ir_codec.from_canonical_bytes(payload, version="0.3.0")


def test_bounded_core_codec_checks_exact_wire_limit_and_one_over() -> None:
    spec = core_codec.CanonSpec(version="0.3.0", exclude_none=False)
    value = {"_type": "future", "value": "x"}
    expected = core_codec.to_canonical_bytes(value, spec)
    exact = core_codec.CanonicalResourceLimits(
        policy_id="test.core-json@1",
        max_wire_bytes=len(expected),
        max_wire_depth=8,
        max_elements=11,
    )

    assert core_codec.to_bounded_canonical_bytes(value, spec, exact) == expected
    with pytest.raises(core_codec.CanonViolation, match="canonical_wire_bytes_exceeded"):
        core_codec.to_bounded_canonical_bytes(
            value,
            spec,
            core_codec.CanonicalResourceLimits(
                policy_id=exact.policy_id,
                max_wire_bytes=len(expected) - 1,
                max_wire_depth=exact.max_wire_depth,
                max_elements=exact.max_elements,
            ),
        )

    with pytest.raises(core_codec.CanonViolation, match="canonical_wire_elements_exceeded"):
        core_codec.to_bounded_canonical_bytes(
            value,
            spec,
            core_codec.CanonicalResourceLimits(
                policy_id=exact.policy_id,
                max_wire_bytes=len(expected),
                max_wire_depth=exact.max_wire_depth,
                max_elements=10,
            ),
        )


def test_bounded_core_codec_uses_wire_wrapper_depth() -> None:
    value = {"_type": "future"}
    spec = core_codec.CanonSpec(version="0.3.0")
    with pytest.raises(core_codec.CanonViolation, match="canonical_wire_depth_exceeded"):
        core_codec.to_bounded_canonical_bytes(
            value,
            spec,
            core_codec.CanonicalResourceLimits(
                policy_id="test.core-json@1",
                max_wire_bytes=100,
                max_wire_depth=2,
                max_elements=20,
            ),
        )


def test_bounded_core_codec_retains_profile_conformance_gate() -> None:
    shaped = {"_type": "decimal", "value": "1.0", "extra": "x"}
    with pytest.raises(core_codec.CanonViolation, match="canon_profile_payload_nonconformant"):
        core_codec.to_bounded_canonical_bytes(
            shaped,
            core_codec.CanonSpec(),
            core_codec.CanonicalResourceLimits(
                policy_id="test.core-json@1",
                max_wire_bytes=200,
                max_wire_depth=8,
                max_elements=20,
            ),
        )


@pytest.mark.parametrize(
    "constructor",
    [
        lambda: core_codec.BytesHexRepresentation("00  11"),
        lambda: core_codec.ArrayDigestRepresentation(
            dtype="<f8", shape=(1,), digest="sha256:" + "a" * 62 + "  "
        ),
        lambda: core_codec.FloatHexRepresentation("0x1p+9999"),
    ],
)
def test_core_descriptor_carriers_reject_noncanonical_or_nonfinite_input(
    constructor: object,
) -> None:
    with pytest.raises(ValueError):
        constructor()


def test_bounded_core_codec_refuses_bytes_before_base64_materialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> bytes:
        raise AssertionError("base64 materializer called")

    monkeypatch.setattr(common_codec.base64, "b64encode", forbidden)
    with pytest.raises(core_codec.CanonViolation, match="canonical_wire_bytes_exceeded"):
        core_codec.to_bounded_canonical_bytes(
            b"x" * 1_000,
            core_codec.CanonSpec(version="0.3.0"),
            core_codec.CanonicalResourceLimits(
                policy_id="test.core-json@1",
                max_wire_bytes=64,
                max_wire_depth=8,
                max_elements=20,
            ),
        )


def test_bounded_core_codec_refuses_before_model_serializer_callback() -> None:
    events: list[str] = []

    class CallbackModel(BaseModel):
        value: str

        @field_serializer("value")
        def serialize_value(self, value: str) -> str:
            events.append(value)
            return value

    with pytest.raises(core_codec.CanonViolation, match="canonical_bounded_projection_required"):
        core_codec.to_bounded_canonical_bytes(
            CallbackModel(value="secret"),
            core_codec.CanonSpec(version="0.3.0"),
            core_codec.CanonicalResourceLimits(
                policy_id="test.core-json@1",
                max_wire_bytes=100,
                max_wire_depth=8,
                max_elements=8,
            ),
        )
    assert events == []


@pytest.mark.parametrize("codec", [common_codec, core_codec], ids=["common", "core"])
def test_bounded_codec_snapshots_spec_before_caller_field_access(codec: ModuleType) -> None:
    accessed: list[str] = []

    class TrapSpec(common_codec.CanonSpec):
        def __getattribute__(self, name: str) -> object:
            if name in {"separators", "ensure_ascii", "version", "name"}:
                accessed.append(name)
                raise AssertionError("caller spec getter ran")
            return super().__getattribute__(name)

    spec = TrapSpec(version="0.3.0")
    limits = common_codec.CanonicalResourceLimits("test@1", 20, 2, 3)
    assert codec.to_bounded_canonical_bytes({"x": 1}, spec, limits) == b'{"x":1}'
    assert accessed == []


@pytest.mark.parametrize(
    ("limits", "reason"),
    [
        (common_codec.CanonicalResourceLimits("test@1", 100_000, 8, 1), "elements"),
        (common_codec.CanonicalResourceLimits("test@1", 1, 8, 10_000), "bytes"),
        (common_codec.CanonicalResourceLimits("test@1", 100_000, 0, 10_000), "depth"),
    ],
)
def test_bounded_codec_refuses_large_mapping_before_sort(
    limits: common_codec.CanonicalResourceLimits, reason: str
) -> None:
    value = {"_type": "future", **{f"key-{index}": index for index in range(1024)}}
    events: list[int] = []
    previous = sys.getprofile()

    def trace(frame: FrameType, event: str, arg: object) -> None:
        if (
            event == "c_call"
            and frame.f_globals.get("__name__") == common_codec.__name__
            and getattr(arg, "__name__", None) == "sort"
        ):
            events.append(1)

    sys.setprofile(trace)
    try:
        with pytest.raises(common_codec.CanonicalError, match=f"canonical_wire_{reason}_exceeded"):
            common_codec.to_bounded_canonical_bytes(
                value, common_codec.CanonSpec(version="0.3.0"), limits
            )
    finally:
        sys.setprofile(previous)
    assert events == []


def test_bounded_codec_refuses_large_string_before_materialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> str:
        raise AssertionError("full JSON materialization was reached")

    monkeypatch.setattr(common_codec.json, "dumps", forbidden)
    with pytest.raises(common_codec.CanonicalError, match="canonical_wire_bytes_exceeded"):
        common_codec.to_bounded_canonical_bytes(
            "x" * 100_000,
            common_codec.CanonSpec(version="0.3.0"),
            common_codec.CanonicalResourceLimits("test@1", 64, 1, 1),
        )


@pytest.mark.parametrize("codec", [common_codec, core_codec], ids=["common", "core"])
def test_bounded_codec_exact_native_bytes_wire_vector(codec: ModuleType) -> None:
    spec = codec.CanonSpec(version="0.3.0")
    expected = b'{"_type":"bytes","data":"eA==","encoding":"base64"}'
    assert (
        codec.to_bounded_canonical_bytes(
            b"x", spec, common_codec.CanonicalResourceLimits("test@1", 51, 1, 7)
        )
        == expected
    )
    for limits in (
        common_codec.CanonicalResourceLimits("test@1", 50, 1, 7),
        common_codec.CanonicalResourceLimits("test@1", 51, 0, 7),
        common_codec.CanonicalResourceLimits("test@1", 51, 1, 6),
    ):
        with pytest.raises(ValueError):
            codec.to_bounded_canonical_bytes(b"x", spec, limits)


@pytest.mark.parametrize("codec", [common_codec, core_codec], ids=["common", "core"])
def test_bounded_codec_counts_native_bytes_before_later_sibling(codec: ModuleType) -> None:
    value = [b"x", 0]
    spec = codec.CanonSpec(version="0.3.0")
    expected = b'[{"_type":"bytes","data":"eA==","encoding":"base64"},0]'
    assert (
        codec.to_bounded_canonical_bytes(
            value, spec, common_codec.CanonicalResourceLimits("test@1", 55, 2, 9)
        )
        == expected
    )
    error = common_codec.CanonicalError if codec is common_codec else core_codec.CanonViolation
    with pytest.raises(error, match="canonical_wire_elements_exceeded"):
        codec.to_bounded_canonical_bytes(
            value, spec, common_codec.CanonicalResourceLimits("test@1", 55, 2, 8)
        )


def test_bounded_codec_exact_escaped_mapping_wire_vector() -> None:
    value = {"_type": "future"}
    spec = common_codec.CanonSpec(version="0.3.0")
    assert (
        common_codec.to_bounded_canonical_bytes(
            value, spec, common_codec.CanonicalResourceLimits("test@1", 50, 3, 8)
        )
        == b'{"_type":"mapping","entries":[["_type","future"]]}'
    )
    for limits in (
        common_codec.CanonicalResourceLimits("test@1", 49, 3, 8),
        common_codec.CanonicalResourceLimits("test@1", 50, 2, 8),
        common_codec.CanonicalResourceLimits("test@1", 50, 3, 7),
    ):
        with pytest.raises(common_codec.CanonicalError):
            common_codec.to_bounded_canonical_bytes(value, spec, limits)


def test_bounded_codec_counts_each_shared_occurrence_and_rejects_cycle() -> None:
    shared = ["x"]
    value = [shared, shared]
    spec = common_codec.CanonSpec(version="0.3.0")
    assert (
        common_codec.to_bounded_canonical_bytes(
            value, spec, common_codec.CanonicalResourceLimits("test@1", 13, 2, 5)
        )
        == b'[["x"],["x"]]'
    )
    with pytest.raises(common_codec.CanonicalError, match="canonical_wire_elements_exceeded"):
        common_codec.to_bounded_canonical_bytes(
            value, spec, common_codec.CanonicalResourceLimits("test@1", 13, 2, 4)
        )
    cyclic: list[object] = []
    cyclic.append(cyclic)
    with pytest.raises(common_codec.CanonicalError, match="canonical_bounded_cycle"):
        common_codec.to_bounded_canonical_bytes(
            cyclic, spec, common_codec.CanonicalResourceLimits("test@1", 100, 8, 20)
        )


def test_bounded_codec_serializes_counted_snapshot_after_input_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = {"x": "a"}
    original = common_codec._canonicalize_obj
    events: list[str] = []

    def mutate_source(obj: object, *args: object, **kwargs: object) -> object:
        if not events:
            value["x"] = "b" * 100_000
            events.append("mutated")
        return original(obj, *args, **kwargs)

    monkeypatch.setattr(common_codec, "_canonicalize_obj", mutate_source)
    assert (
        common_codec.to_bounded_canonical_bytes(
            value,
            common_codec.CanonSpec(version="0.3.0"),
            common_codec.CanonicalResourceLimits("test@1", 9, 1, 3),
        )
        == b'{"x":"a"}'
    )
    assert events == ["mutated"]


def test_bounded_codec_counts_unicode_and_nondefault_separators() -> None:
    value = {"a": "é", "b": [0]}
    spec = common_codec.CanonSpec(
        version="0.3.0", sort_keys=False, separators=(", ", ": "), ensure_ascii=False
    )
    assert (
        common_codec.to_bounded_canonical_bytes(
            value, spec, common_codec.CanonicalResourceLimits("test@1", 21, 2, 6)
        )
        == '{"a": "é", "b": [0]}'.encode()
    )
    ascii_spec = common_codec.CanonSpec(version="0.3.0", ensure_ascii=True)
    assert (
        common_codec.to_bounded_canonical_bytes(
            "\x7fé😀", ascii_spec, common_codec.CanonicalResourceLimits("test@1", 26, 0, 1)
        )
        == b'"\\u007f\\u00e9\\ud83d\\ude00"'
    )


@pytest.mark.parametrize("codec", [common_codec, core_codec], ids=["common", "core"])
@pytest.mark.parametrize(
    ("carrier", "expected", "wire_depth", "elements"),
    [
        (
            common_codec.BytesHexRepresentation("00ff"),
            b'{"_type":"bytes_hex","value":"00ff"}',
            1,
            5,
        ),
        (
            common_codec.FloatHexRepresentation("-0x0.0p+0"),
            b'{"_type":"float_hex","value":"-0x0.0p+0"}',
            1,
            5,
        ),
        (
            common_codec.ArrayDigestRepresentation(
                dtype="<f8", shape=(2, 3), digest="sha256:" + "a" * 64
            ),
            b'{"_type":"array_digest","digest":"sha256:'
            + b"a" * 64
            + b'","dtype":"<f8","shape":[2,3]}',
            2,
            11,
        ),
    ],
)
def test_bounded_carriers_obey_exact_wire_vector(
    codec: ModuleType, carrier: object, expected: bytes, wire_depth: int, elements: int
) -> None:
    spec = codec.CanonSpec(version="0.3.0", forbid_floats=False)
    limits = common_codec.CanonicalResourceLimits("test@1", len(expected), wire_depth, elements)
    encoded = codec.to_bounded_canonical_bytes(carrier, spec, limits)
    assert encoded == expected
    decoded = codec.from_canonical_bytes(encoded, version="0.3.0")
    assert type(decoded) is type(carrier)
    assert decoded == carrier
    assert codec.to_bounded_canonical_bytes(decoded, spec, limits) == encoded
    error = common_codec.CanonicalError if codec is common_codec else core_codec.CanonViolation
    for smaller, reason in (
        (
            common_codec.CanonicalResourceLimits("test@1", len(expected) - 1, wire_depth, elements),
            "bytes",
        ),
        (
            common_codec.CanonicalResourceLimits("test@1", len(expected), wire_depth - 1, elements),
            "depth",
        ),
        (
            common_codec.CanonicalResourceLimits("test@1", len(expected), wire_depth, elements - 1),
            "elements",
        ),
    ):
        with pytest.raises(error, match=f"canonical_wire_{reason}_exceeded"):
            codec.to_bounded_canonical_bytes(carrier, spec, smaller)


def test_new_carrier_emission_obeys_selected_version_and_tag_policy() -> None:
    carrier = core_codec.BytesHexRepresentation("00")
    limits = common_codec.CanonicalResourceLimits("test@1", 100, 4, 20)
    for codec in (common_codec, core_codec):
        with pytest.raises(ValueError, match="canonical_carrier_profile_unsupported"):
            codec.to_canonical_bytes(carrier, codec.CanonSpec())
        with pytest.raises(ValueError, match="canonical_carrier_profile_unsupported"):
            codec.to_bounded_canonical_bytes(carrier, codec.CanonSpec(), limits)
    with pytest.raises(common_codec.CanonicalError, match="canonical_carrier_profile_unsupported"):
        common_codec.to_canonical_bytes(
            carrier,
            common_codec.CanonSpec(version="0.3.0"),
            canonical_types=frozenset({"bytes"}),
        )
    with pytest.raises(common_codec.CanonicalError, match="canonical_bounded_type_policy_invalid"):
        common_codec.to_bounded_canonical_bytes(
            carrier,
            common_codec.CanonSpec(version="0.3.0"),
            limits,
            canonical_types=frozenset({"bytes"}),
        )
    with pytest.raises(ir_codec.CanonViolation, match="canonical_carrier_profile_unsupported"):
        ir_codec.to_canonical_bytes(carrier, ir_codec.CanonSpec(version="0.3.0"))

    # Historical .2 wire data keeps its existing primitive/dict interpretation.
    assert core_codec.from_canonical_bytes(b'{"_type":"bytes_hex","value":"00"}') == b"\x00"
    decoded = core_codec.from_canonical_bytes(
        b'{"_type":"array_digest","dtype":"<f8","shape":[1],"digest":"sha256:opaque"}'
    )
    assert type(decoded) is dict
    assert decoded["digest"] == "sha256:opaque"


def test_bounded_codec_refuses_oversized_unregistered_tag_policy() -> None:
    unsupported = frozenset(f"future-{index}" for index in range(64))
    with pytest.raises(common_codec.CanonicalError, match="canonical_bounded_type_policy_invalid"):
        common_codec.to_bounded_canonical_bytes(
            0,
            common_codec.CanonSpec(version="0.3.0"),
            common_codec.CanonicalResourceLimits("test@1", 1, 0, 1),
            canonical_types=unsupported,
        )


@pytest.mark.parametrize(
    "raw",
    [
        {"_type": "future", "value": None},
        {"_type": None},
        {"_type": 7},
        {"_type": "mapping", "entries": [["_type", "date"]]},
        {"outer": [{"_type": "future", "nested": {"_type": None}}]},
    ],
)
def test_v3_losslessly_escapes_every_ordinary_type_mapping(raw: object) -> None:
    spec = CanonSpec(version="0.3.0", exclude_none=False)

    encoded = to_canonical_bytes(raw, spec)

    assert from_canonical_bytes(encoded, version=spec.version) == raw
    assert to_canonical_bytes(raw, spec) == encoded


def test_v3_keeps_native_envelope_distinct_from_raw_mapping() -> None:
    spec = CanonSpec(version="0.3.0")
    native = to_canonical_bytes({"value": b"x"}, spec)
    raw = to_canonical_bytes(
        {"value": {"_type": "bytes", "encoding": "base64", "data": "eA=="}}, spec
    )

    assert native != raw
    assert from_canonical_bytes(native, version=spec.version) == {"value": b"x"}
    assert from_canonical_bytes(raw, version=spec.version) == {
        "value": {"_type": "bytes", "encoding": "base64", "data": "eA=="}
    }


@pytest.mark.parametrize(
    "payload",
    [
        b'{"_type":"mapping","entries":[],"extra":0}',
        b'{"_type":"mapping","entries":[]}',
        b'{"_type":"mapping","entries":[["x",1],["_type",2]]}',
        b'{"_type":"mapping","entries":[["_type",1],["_type",2]]}',
        b'{"_type":"mapping","entries":[[1,2]]}',
        b'{"_type":"mapping","entries":{"_type":1}}',
        b'{"_type":"mapping","_type":"mapping","entries":[]}',
    ],
)
def test_v3_strictly_rejects_malformed_mapping_wrappers(payload: bytes) -> None:
    with pytest.raises(ValueError):
        from_canonical_bytes(payload, version="0.3.0")


def test_v2_default_behavior_is_unchanged() -> None:
    with pytest.raises(ValueError, match="Unknown canonical _type"):
        to_canonical_bytes({"_type": "future"})

    with pytest.raises(ValueError, match="Unknown canonical _type"):
        from_canonical_bytes(b'{"_type":"mapping","entries":[]}')
