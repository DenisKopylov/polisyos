from __future__ import annotations

import asyncio
import json

import pytest
from pydantic import BaseModel, ConfigDict

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts import (
    CanonInfo,
    FileSystemCAS,
    PutOptions,
    aload_core_json_artifact,
    load_core_json_artifact,
    load_core_json_frame_records,
    read_core_json_artifact,
    read_core_json_artifact_bytes,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts.async_store import AsyncArtifactStoreAdapter
from polisyos.core.canon import CanonSpec, to_canonical_bytes


class _Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    value: int


def _profiled_json_store(tmp_path, payload: dict[str, object]):
    store = FileSystemCAS(tmp_path / "cas")
    spec = CanonSpec(forbid_floats=False, exclude_none=False)
    raw = to_canonical_bytes(payload, spec)
    ref = store.put_bytes(
        raw,
        PutOptions(
            kind="test.selected_profile.json",
            media_type="application/json",
            canon=CanonInfo.from_spec(spec),
        ),
    )
    return store, ref, raw


def test_core_json_facade_returns_only_profile_conformant_selected_values(tmp_path) -> None:
    store, ref, raw = _profiled_json_store(tmp_path, {"value": 7})

    assert read_core_json_artifact_bytes(store, ref) == raw
    assert load_core_json_artifact(store, ref) == {"value": 7}
    assert validate_core_model_json_artifact(_Payload, store, ref) == _Payload(value=7)


def test_core_json_missing_profile_is_refused_before_selected_semantics(tmp_path, monkeypatch) -> None:
    store, ref, _raw = _profiled_json_store(tmp_path, {"value": 7})
    original_raw_reader = store.get_raw_manifest_bytes
    original_manifest_reader = store.get_manifest
    selected_id = str(ref.artifact_id)

    def absent_profile(selector, *, manifest_profile_sha256=None):
        raw = original_raw_reader(
            selector, manifest_profile_sha256=manifest_profile_sha256
        )
        if str(getattr(selector, "artifact_id", selector)) != selected_id:
            return raw
        payload = json.loads(raw)
        payload.pop("canon", None)
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()

    def typed_absent_profile(selector):
        manifest = original_manifest_reader(selector)
        if str(getattr(selector, "artifact_id", selector)) != selected_id:
            return manifest
        return manifest.model_copy(update={"canon": None})

    monkeypatch.setattr(store, "get_raw_manifest_bytes", absent_profile)
    monkeypatch.setattr(store, "get_manifest", typed_absent_profile)
    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_absent"):
        load_core_json_artifact(store, ref.artifact_id)


def test_core_json_present_malformed_profile_is_not_treated_as_absent(tmp_path, monkeypatch) -> None:
    store, ref, _raw = _profiled_json_store(tmp_path, {"value": 7})
    original_raw_reader = store.get_raw_manifest_bytes
    selected_id = str(ref.artifact_id)

    def malformed_present(selector, *, manifest_profile_sha256=None):
        raw = original_raw_reader(
            selector, manifest_profile_sha256=manifest_profile_sha256
        )
        if str(getattr(selector, "artifact_id", selector)) == selected_id:
            return b'{"canon":null}'
        return raw

    monkeypatch.setattr(store, "get_raw_manifest_bytes", malformed_present)
    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_invalid"):
        read_core_json_artifact_bytes(store, ref)


def test_core_unknown_profile_remains_an_exact_raw_only_candidate(tmp_path) -> None:
    raw = b'{"candidate":true}'
    store = FileSystemCAS(tmp_path / "unknown-profile-cas")
    ref = store.put_bytes(
        raw,
        PutOptions(
            kind="test.unknown-profile",
            media_type="application/json",
            canon=CanonInfo(name="polisyos.canon.future"),
        ),
    )

    read = read_core_json_artifact(store, ref)

    assert read.status == "declared_unknown_candidate"
    assert read.raw_only_candidate_bytes == raw
    assert read.selected_artifact_id == str(ref.artifact_id)
    assert read.selected_manifest_profile_sha256 is not None
    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_not_verified"):
        _ = read.value


def test_core_frame_loader_verifies_manifest_profile_and_each_record(tmp_path, monkeypatch) -> None:
    store = FileSystemCAS(tmp_path / "framed-cas")
    spec = CanonSpec(forbid_floats=False, exclude_none=False)
    records = [to_canonical_bytes({"value": value}, spec) for value in (3, 5)]
    raw = b"".join(len(record).to_bytes(8, "big") + record for record in records)
    ref = store.put_bytes(
        raw,
        PutOptions(
            kind="test.selected_profile.frames",
            media_type="application/vnd.polisyos.test-frames+json",
            canon=CanonInfo.from_spec(spec),
        ),
    )

    assert load_core_json_frame_records(store, ref) == [{"value": 3}, {"value": 5}]

    original_raw_reader = store.get_raw_manifest_bytes
    selected_id = str(ref.artifact_id)

    def absent_frame_profile(selector, *, manifest_profile_sha256=None):
        sidecar = original_raw_reader(
            selector, manifest_profile_sha256=manifest_profile_sha256
        )
        if str(getattr(selector, "artifact_id", selector)) == selected_id:
            payload = json.loads(sidecar)
            payload.pop("canon", None)
            return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return sidecar

    monkeypatch.setattr(store, "get_raw_manifest_bytes", absent_frame_profile)
    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_absent"):
        load_core_json_frame_records(store, ref.artifact_id)


def test_async_core_json_facade_preserves_the_selected_profile_guard(tmp_path) -> None:
    store, ref, _raw = _profiled_json_store(tmp_path, {"value": 11})
    async_store = AsyncArtifactStoreAdapter(store, timeout_seconds=5.0)

    assert asyncio.run(aload_core_json_artifact(async_store, ref)) == {"value": 11}


@pytest.mark.parametrize(
    ("profile_variant", "expected_error"),
    [
        ("incomplete", "canon_profile_incomplete"),
        ("unsupported", "canon_profile_not_verified"),
    ],
)
def test_async_core_refuses_nonreadable_raw_profile_before_typed_or_payload_reads(
    tmp_path, monkeypatch, profile_variant, expected_error
) -> None:
    store, ref, _raw = _profiled_json_store(tmp_path, {"value": 17})
    selected_id = str(ref.artifact_id)
    original_raw_reader = store.get_raw_manifest_bytes
    original_manifest_reader = store.get_manifest
    original_payload_reader = store.get_bytes
    manifest_reads: list[object] = []
    payload_reads: list[object] = []

    def nonreadable_profile(selector, *, manifest_profile_sha256=None):
        raw = original_raw_reader(
            selector, manifest_profile_sha256=manifest_profile_sha256
        )
        if str(getattr(selector, "artifact_id", selector)) != selected_id:
            return raw
        if profile_variant == "incomplete":
            return b'{"canon":{}}'
        manifest = json.loads(raw)
        manifest["canon"]["version"] = "0.3.0"
        return json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()

    def record_manifest(selector):
        manifest_reads.append(selector)
        return original_manifest_reader(selector)

    def record_payload(selector):
        payload_reads.append(selector)
        return original_payload_reader(selector)

    monkeypatch.setattr(store, "get_raw_manifest_bytes", nonreadable_profile)
    monkeypatch.setattr(store, "get_manifest", record_manifest)
    monkeypatch.setattr(store, "get_bytes", record_payload)
    async_store = AsyncArtifactStoreAdapter(store, timeout_seconds=5.0)

    with pytest.raises(CanonicalProfileRefusalError, match=expected_error):
        asyncio.run(aload_core_json_artifact(async_store, ref))

    assert manifest_reads == []
    assert payload_reads == []


def test_typed_core_reader_preserves_the_selected_manifest_view(tmp_path, monkeypatch) -> None:
    from polisyos.core.artifacts import artifact_ref_for_manifest
    from polisyos.scientist.methods.autotune.models import load_json_artifact

    store, ref, _raw = _profiled_json_store(tmp_path, {"value": 13})
    selected_ref = artifact_ref_for_manifest(store.get_manifest(ref))
    observed_selectors = []
    original_raw_reader = store.get_raw_manifest_bytes

    def record_selector(selector, *, manifest_profile_sha256=None):
        observed_selectors.append(selector)
        return original_raw_reader(
            selector, manifest_profile_sha256=manifest_profile_sha256
        )

    monkeypatch.setattr(store, "get_raw_manifest_bytes", record_selector)

    assert load_json_artifact(store, selected_ref) == {"value": 13}
    assert observed_selectors[0] == selected_ref
