from __future__ import annotations

import json

import pytest

from polisyos.common.canonical_profile import (
    CanonicalProfileRefusalError,
    read_canonical_profiled_bytes,
    require_declared_profile,
)
from polisyos.core.artifacts.manifest import CanonInfo as CoreCanonInfo
from polisyos.core.canon import (
    CanonSpec as CoreCanonSpec,
)
from polisyos.core.canon import (
    CanonViolation as CoreCanonViolation,
)
from polisyos.core.canon import (
    from_canonical_bytes as core_from_canonical_bytes,
)
from polisyos.core.canon import (
    to_canonical_bytes as core_to_canonical_bytes,
)
from polisyos.ir.artifacts.contracts import CanonInfo as IRCanonInfo
from polisyos.ir.model_layer.canon import (
    CanonViolation as IRCanonViolation,
)
from polisyos.ir.model_layer.canon import (
    from_canonical_bytes as ir_from_canonical_bytes,
)
from polisyos.ir.model_layer.canon import (
    to_canonical_bytes as ir_to_canonical_bytes,
)


def _profiled_read(raw_payload: bytes, profile: CoreCanonInfo):
    raw_manifest = json.dumps({"canon": profile.model_dump(mode="json")}).encode()
    return read_canonical_profiled_bytes(
        raw_manifest,
        raw_payload,
        profile_model=CoreCanonInfo,
        make_spec=lambda item: CoreCanonSpec(**item.model_dump()),
        decode=lambda data, max_depth: core_from_canonical_bytes(data, max_depth=max_depth),
        encode=lambda value, spec: core_to_canonical_bytes(value, spec),
        allow_profile_absent=False,
    )


def test_shared_reader_round_trips_declared_profile_and_marks_absence() -> None:
    profile = CoreCanonInfo(forbid_floats=False)
    raw = core_to_canonical_bytes({"value": 1.5}, CoreCanonSpec(forbid_floats=False))

    read = _profiled_read(raw, profile)

    assert read.value == {"value": 1.5}
    assert read.raw_payload_bytes == raw
    assert read.status == "declared_bytes_conformant"
    absent = read_canonical_profiled_bytes(
        b"{}",
        core_to_canonical_bytes({"value": 2}),
        profile_model=CoreCanonInfo,
        make_spec=lambda item: CoreCanonSpec(**item.model_dump()),
        decode=lambda data, max_depth: core_from_canonical_bytes(data, max_depth=max_depth),
        encode=lambda value, spec: core_to_canonical_bytes(value, spec),
        allow_profile_absent=True,
    )
    assert absent.status == "profile_absent_unqualified_candidate"
    assert absent.unqualified_candidate_value == {"value": 2}
    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_not_verified"):
        _ = absent.value
    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_not_verified"):
        require_declared_profile(absent)


def test_canonical_profile_read_cannot_self_attest_by_construction() -> None:
    from polisyos.common.canonical_profile import CanonicalProfileRead, require_declared_profile

    forged = CanonicalProfileRead(
        value={"authority": "unverified"},
        raw_payload_bytes=b"{}",
        status="declared_bytes_conformant",
    )
    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_not_verified"):
        _ = forged.value
    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_not_verified"):
        require_declared_profile(forged)


def test_present_malformed_and_incomplete_profiles_do_not_become_absent() -> None:
    raw = core_to_canonical_bytes({"value": 1})
    callbacks = {
        "profile_model": CoreCanonInfo,
        "make_spec": lambda item: CoreCanonSpec(**item.model_dump()),
        "decode": lambda data, max_depth: core_from_canonical_bytes(data, max_depth=max_depth),
        "encode": lambda value, spec: core_to_canonical_bytes(value, spec),
        "allow_profile_absent": True,
    }
    for manifest in (b'{"canon":null}', b'{"canon":{}}', b'{"canon":{},"canon":{}}'):
        with pytest.raises(CanonicalProfileRefusalError):
            read_canonical_profiled_bytes(manifest, raw, **callbacks)


def test_declared_float_policy_is_checked_by_encode_decode_round_trip() -> None:
    raw = core_to_canonical_bytes({"value": 1.5}, CoreCanonSpec(forbid_floats=False))
    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_payload_nonconformant"):
        _profiled_read(raw, CoreCanonInfo(forbid_floats=True))


def test_codec_facades_keep_distinct_tag_laws_and_exception_identity() -> None:
    core_only = b'{"_type":"bytes_hex","value":"78"}'
    assert core_from_canonical_bytes(core_only) == b"x"
    with pytest.raises(IRCanonViolation, match="Unknown canonical _type"):
        ir_from_canonical_bytes(core_only)
    assert CoreCanonViolation is not IRCanonViolation

    ir_raw = ir_to_canonical_bytes({"x": 1})
    assert ir_from_canonical_bytes(ir_raw) == {"x": 1}
    assert IRCanonInfo().version == CoreCanonInfo().version


def test_core_selected_profile_is_refused_before_payload_io() -> None:
    from polisyos.core.artifacts.canonical_profile import read_core_json_artifact

    class Store:
        payload_read = False
        manifest_read = False

        def get_raw_manifest_bytes(self, _selector):
            return b'{"canon":{}}'

        def get_manifest(self, _selector):
            self.manifest_read = True
            raise AssertionError("typed manifest must wait for raw profile validation")

        def get_bytes(self, _selector):
            self.payload_read = True
            return b'{"value":1}'

    store = Store()
    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_incomplete"):
        read_core_json_artifact(store, "selected-view")
    assert store.manifest_read is False
    assert store.payload_read is False


def test_valid_unsupported_profile_is_raw_only_and_never_uses_a_codec_default() -> None:
    from polisyos.common.canonical_profile import (
        decode_profiled_canonical_bytes,
        parse_canonical_profile,
    )

    payload = b'{"candidate":true}'
    profile = CoreCanonInfo().model_dump(mode="json")
    profile["version"] = f"{profile['version']}-future"
    declaration = parse_canonical_profile(
        json.dumps({"canon": profile}).encode(),
        profile_model=CoreCanonInfo,
        allow_profile_absent=False,
    )
    assert declaration.status == "declared_unknown_candidate"
    calls: list[str] = []
    read = decode_profiled_canonical_bytes(
        payload,
        declaration,
        profile_model=CoreCanonInfo,
        make_spec=lambda item: CoreCanonSpec(**item.model_dump()),
        decode=lambda data, max_depth: calls.append("decode")
        or core_from_canonical_bytes(data, max_depth=max_depth),
        encode=lambda value, spec: calls.append("encode") or core_to_canonical_bytes(value, spec),
    )
    assert read.status == "declared_unknown_candidate"
    assert read.raw_only_candidate_bytes == payload
    assert calls == []
    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_not_verified"):
        _ = read.value
    with pytest.raises(
        CanonicalProfileRefusalError, match="canon_profile_candidate_read_not_unqualified"
    ):
        _ = read.unqualified_candidate_value
    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_not_verified"):
        require_declared_profile(read)


def test_profile_refusal_keeps_existing_value_error_boundary_compatibility() -> None:
    """Typed profile refusal remains distinguishable and compatible with callers."""
    from polisyos.common.canonical_profile import CanonicalProfileRefusalError

    assert issubclass(CanonicalProfileRefusalError, ValueError)
