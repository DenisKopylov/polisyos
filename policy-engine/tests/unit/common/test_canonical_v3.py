from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from types import ModuleType

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
    "payload",
    [
        b'{"_type":"float_hex","value":"0x1.0p+0"}',
        b'{"_type":"bytes_hex","value":"00"}',
        b'{"_type":"array_digest","digest":"sha256:abc"}',
    ],
)
def test_core_v3_refuses_unimplemented_descriptor_carriers(payload: bytes) -> None:
    with pytest.raises(core_codec.CanonViolation, match="canonical_v3_descriptor_unsupported"):
        core_codec.from_canonical_bytes(payload, version="0.3.0")


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
