from __future__ import annotations

import hashlib
import json
import os
from dataclasses import replace
from decimal import Decimal
from typing import Annotated, ClassVar, Literal

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts import (
    ArtifactBoundedManifestRead,
    ArtifactBoundedManifestReadError,
    ArtifactGovernanceInfo,
    ArtifactMemberReadBoundsError,
    ArtifactMemberReadIntegrityError,
    ArtifactReadOnlyUnavailableError,
    ArtifactRef,
    CanonInfo,
    CoreJsonArtifactBoundedRead,
    CoreJsonManifestBoundedRead,
    CoreJsonReadBoundsRefusalError,
    CoreJsonReadLimits,
    FileSystemCAS,
    InputRef,
    PutOptions,
    ReadOnlyFileSystemCAS,
    SchemaInfo,
    artifact_ref_for_manifest,
    read_core_input_manifest_profile_bounded,
    read_core_json_artifact_bounded,
    read_core_manifest_profile_bounded,
    validate_core_model_bounded_read,
    validate_core_model_json_artifact,
)
from polisyos.core.canon import CanonSpec, to_canonical_bytes


def _profiled_store(tmp_path, value: object):
    store = FileSystemCAS(tmp_path / "bounded-cas")
    spec = CanonSpec(forbid_floats=False, exclude_none=False, max_depth=32)
    raw = to_canonical_bytes(value, spec)
    ref = store.put_bytes(
        raw,
        PutOptions(
            kind="test.core-json.bounded",
            media_type="application/json",
            canon=CanonInfo.from_spec(spec),
        ),
        return_selected_profile=True,
    )
    return store, ref, raw


def _limits(
    raw: bytes,
    *,
    max_depth: int,
    max_elements: int,
    max_manifest_bytes: int = 4096,
) -> CoreJsonReadLimits:
    return CoreJsonReadLimits(
        max_bytes=len(raw),
        max_depth=max_depth,
        max_elements=max_elements,
        max_manifest_bytes=max_manifest_bytes,
    )


class _DiscriminatedTextPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    kind: Literal["text"]
    value: str


class _DiscriminatedCountPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    kind: Literal["count"]
    value: int


class _DiscriminatedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    item: Annotated[
        _DiscriminatedTextPayload | _DiscriminatedCountPayload,
        Field(discriminator="kind"),
    ]


class _TypedBoundedTuplePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: str
    values: tuple[tuple[str, int], ...] = Field(
        validation_alias="legacy_values",
        serialization_alias="wire_values",
    )

    ARTIFACT_KIND: ClassVar[str] = "test.core-json.bounded-typed"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "test.core-json.BoundedTypedTuplePayload"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"
    ARTIFACT_REQUIRED_FIELDS_BY_SCHEMA_VERSION: ClassVar[dict[str, tuple[str, ...]]] = {
        "1.0": ("values",),
    }


class _WrongTypedBoundedSchemaPayload(_TypedBoundedTuplePayload):
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "test.core-json.WrongBoundedPayload"


def _typed_bounded_store(
    tmp_path,
    payload: object,
    *,
    profile_max_depth: int = 32,
    store: FileSystemCAS | None = None,
):
    if store is None:
        store = FileSystemCAS(tmp_path / "typed-bounded-cas")
    spec = CanonSpec(forbid_floats=False, exclude_none=False, max_depth=profile_max_depth)
    raw = to_canonical_bytes(payload, spec)
    ref = store.put_bytes(
        raw,
        PutOptions(
            kind=_TypedBoundedTuplePayload.ARTIFACT_KIND,
            media_type=_TypedBoundedTuplePayload.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=_TypedBoundedTuplePayload.ARTIFACT_SCHEMA_NAME,
                version="1.0",
            ),
            canon=CanonInfo.from_spec(spec),
        ),
        return_selected_profile=True,
    )
    return store, ref, raw


def test_discriminated_model_fields_work_in_legacy_and_bounded_core_readers(
    tmp_path,
) -> None:
    value = {"item": {"kind": "text", "value": "selected"}}
    store, ref, raw = _profiled_store(tmp_path, value)

    legacy = validate_core_model_json_artifact(_DiscriminatedPayload, store, ref)
    bounded_read = read_core_json_artifact_bounded(
        store,
        ref,
        limits=_limits(raw, max_depth=4, max_elements=8),
    )
    bounded = validate_core_model_bounded_read(_DiscriminatedPayload, bounded_read)

    assert type(legacy.item) is _DiscriminatedTextPayload
    assert type(bounded.item) is _DiscriminatedTextPayload
    assert legacy == bounded

    invalid_store, invalid_ref, invalid_raw = _profiled_store(
        tmp_path,
        {"item": {"kind": "future", "value": "selected"}},
    )
    with pytest.raises(ValidationError):
        validate_core_model_json_artifact(_DiscriminatedPayload, invalid_store, invalid_ref)
    invalid_read = read_core_json_artifact_bounded(
        invalid_store,
        invalid_ref,
        limits=_limits(invalid_raw, max_depth=4, max_elements=8),
    )
    with pytest.raises(ValidationError):
        validate_core_model_bounded_read(_DiscriminatedPayload, invalid_read)


def test_bounded_model_validator_reuses_core_alias_tuple_and_schema_admission(
    tmp_path, monkeypatch
) -> None:
    store, ref, raw = _typed_bounded_store(
        tmp_path,
        {"schema_version": "1.0", "legacy_values": [["alpha", 2], ["beta", 4]]},
    )
    bounded_read = read_core_json_artifact_bounded(
        store,
        ref,
        limits=_limits(raw, max_depth=8, max_elements=32),
    )
    measurements = (
        bounded_read.observed_manifest_bytes,
        bounded_read.observed_bytes,
        bounded_read.observed_depth,
        bounded_read.observed_elements,
    )

    def reject_any_storage_read(*_args, **_kwargs):
        raise AssertionError("bounded model validation must not reread the artifact")

    for name in (
        "get_bytes",
        "get_manifest",
        "get_manifest_by_profile",
        "get_raw_manifest_bytes",
        "get_raw_manifest_bytes_bounded",
        "read_raw_manifest_bytes_bounded",
        "open_member",
        "open_member_bounded",
    ):
        monkeypatch.setattr(store, name, reject_any_storage_read)

    typed = validate_core_model_bounded_read(_TypedBoundedTuplePayload, bounded_read)

    assert typed == _TypedBoundedTuplePayload(
        schema_version="1.0",
        legacy_values=(("alpha", 2), ("beta", 4)),
    )
    assert type(typed.values) is tuple
    assert all(type(row) is tuple for row in typed.values)
    assert (
        bounded_read.observed_manifest_bytes,
        bounded_read.observed_bytes,
        bounded_read.observed_depth,
        bounded_read.observed_elements,
    ) == measurements
    assert bounded_read.effective_ref == ref
    assert bounded_read.manifest.artifact_schema == SchemaInfo(
        name=_TypedBoundedTuplePayload.ARTIFACT_SCHEMA_NAME,
        version="1.0",
    )

    with pytest.raises(CanonicalProfileRefusalError) as wrong_owner:
        validate_core_model_bounded_read(_WrongTypedBoundedSchemaPayload, bounded_read)
    assert wrong_owner.value.code == "canon_profile_typed_artifact_schema_name_mismatch"


def test_mutating_returned_decoded_views_does_not_change_bounded_typed_validation(
    tmp_path,
) -> None:
    payload = {"schema_version": "1.0", "legacy_values": [["alpha", 2]]}
    store, ref, raw = _typed_bounded_store(tmp_path, payload)
    bounded_read = read_core_json_artifact_bounded(
        store,
        ref,
        limits=_limits(raw, max_depth=8, max_elements=32),
    )

    first_value = bounded_read.value
    first_value["legacy_values"][0][1] = 999
    first_profile_value = bounded_read.profile_read.value
    first_profile_value["legacy_values"].append(["injected", 1000])

    typed = validate_core_model_bounded_read(_TypedBoundedTuplePayload, bounded_read)

    assert typed.values == (("alpha", 2),)
    assert bounded_read.value == payload
    assert bounded_read.profile_read.value == payload


def test_bounded_typed_validation_rejects_mixed_sibling_carrier_identity(
    tmp_path,
) -> None:
    payload = {"schema_version": "1.0", "legacy_values": [["alpha", 2]]}
    store_a, ref_a, raw_a = _typed_bounded_store(tmp_path, payload, profile_max_depth=32)
    store_b, ref_b, raw_b = _typed_bounded_store(
        tmp_path, payload, profile_max_depth=31, store=store_a
    )
    assert raw_a == raw_b
    assert ref_a.artifact_id == ref_b.artifact_id
    assert ref_a.manifest_profile_sha256 != ref_b.manifest_profile_sha256

    read_a = read_core_json_artifact_bounded(
        store_a,
        ref_a,
        limits=_limits(raw_a, max_depth=8, max_elements=32),
    )
    read_b = read_core_json_artifact_bounded(
        store_b,
        ref_b,
        limits=_limits(raw_b, max_depth=8, max_elements=32),
    )
    profile_a = read_a.profile_read
    profile_b = read_b.profile_read
    assert profile_a.selected_artifact_id == profile_b.selected_artifact_id
    assert profile_a.selected_manifest_profile_sha256 != profile_b.selected_manifest_profile_sha256

    mixed = replace(
        read_a,
        effective_ref=read_b.effective_ref,
        manifest=read_b.manifest,
        raw_manifest_bytes=read_b.raw_manifest_bytes,
        limits=read_b.limits,
        observed_manifest_bytes=read_b.observed_manifest_bytes,
    )
    with pytest.raises(CanonicalProfileRefusalError) as error:
        validate_core_model_bounded_read(_TypedBoundedTuplePayload, mixed)
    assert error.value.code == "canon_profile_bounded_read_carrier_mismatch"

    with pytest.raises(TypeError):
        replace(read_a, profile_read=profile_b)

    unsealed = replace(read_a, _seal=None)
    with pytest.raises(CanonicalProfileRefusalError) as unsealed_error:
        validate_core_model_bounded_read(_TypedBoundedTuplePayload, unsealed)
    assert unsealed_error.value.code == "canon_profile_bounded_read_unverified"


@pytest.mark.parametrize(
    ("field_name", "replacement"),
    [
        pytest.param("effective_ref", "sibling", id="selected-ref"),
        pytest.param("manifest", "sibling", id="typed-manifest"),
        pytest.param("raw_manifest_bytes", "sibling", id="raw-manifest-profile"),
        pytest.param("raw_payload_bytes", b"{}", id="payload-bytes"),
        pytest.param("limits", "different", id="pinned-limits"),
        pytest.param("observed_manifest_bytes", -1, id="manifest-count"),
        pytest.param("observed_bytes", -1, id="payload-byte-count"),
        pytest.param("observed_depth", -1, id="depth-count"),
        pytest.param("observed_elements", -1, id="element-count"),
    ],
)
def test_bounded_typed_validation_rejects_carrier_field_replacement(
    tmp_path,
    field_name: str,
    replacement: object,
) -> None:
    payload = {"schema_version": "1.0", "legacy_values": [["alpha", 2]]}
    store_a, ref_a, raw_a = _typed_bounded_store(tmp_path, payload, profile_max_depth=32)
    store_b, ref_b, raw_b = _typed_bounded_store(
        tmp_path, payload, profile_max_depth=31, store=store_a
    )
    read_a = read_core_json_artifact_bounded(
        store_a,
        ref_a,
        limits=_limits(raw_a, max_depth=8, max_elements=32),
    )
    read_b = read_core_json_artifact_bounded(
        store_b,
        ref_b,
        limits=_limits(raw_b, max_depth=8, max_elements=32),
    )
    replacements: dict[str, object] = {
        "effective_ref": read_b.effective_ref,
        "manifest": read_b.manifest,
        "raw_manifest_bytes": read_b.raw_manifest_bytes,
        "raw_payload_bytes": replacement,
        "limits": CoreJsonReadLimits(
            max_bytes=len(raw_a),
            max_depth=8,
            max_elements=32,
            max_manifest_bytes=4095,
        ),
        "observed_manifest_bytes": replacement,
        "observed_bytes": replacement,
        "observed_depth": replacement,
        "observed_elements": replacement,
    }
    tampered = replace(read_a, **{field_name: replacements[field_name]})

    with pytest.raises(CanonicalProfileRefusalError) as error:
        validate_core_model_bounded_read(_TypedBoundedTuplePayload, tampered)
    assert error.value.code in {
        "canon_profile_bounded_read_carrier_mismatch",
        "canon_profile_bounded_read_measurement_mismatch",
    }


def test_bounded_model_validator_enforces_payload_schema_version_from_same_manifest(
    tmp_path,
) -> None:
    store, ref, raw = _typed_bounded_store(
        tmp_path,
        {"schema_version": "2.0", "legacy_values": [["alpha", 2]]},
    )
    bounded_read = read_core_json_artifact_bounded(
        store,
        ref,
        limits=_limits(raw, max_depth=8, max_elements=32),
    )

    with pytest.raises(CanonicalProfileRefusalError) as error:
        validate_core_model_bounded_read(_TypedBoundedTuplePayload, bounded_read)

    assert error.value.code == "canon_profile_typed_artifact_schema_version_mismatch"


def test_bounded_reader_accepts_exact_observed_limits_and_returns_selected_identity(
    tmp_path,
) -> None:
    store, ref, raw = _profiled_store(tmp_path, {"value": 7})

    result = read_core_json_artifact_bounded(
        store,
        ref,
        limits=_limits(raw, max_depth=1, max_elements=3),
    )

    assert isinstance(result, CoreJsonArtifactBoundedRead)
    assert result.effective_ref == ref
    assert result.profile_read.selected_artifact_id == str(ref.artifact_id)
    assert result.profile_read.selected_manifest_profile_sha256 == ref.manifest_profile_sha256
    assert result.observed_manifest_bytes == len(result.raw_manifest_bytes)
    assert result.observed_manifest_verification_bytes == len(result.raw_manifest_bytes)
    assert result.observed_bytes == len(raw)
    assert result.observed_payload_bytes == len(raw)
    assert result.observed_payload_size == len(raw)
    assert result.payload_integrity_verified is True
    assert result.observed_source_bytes == 2 * len(result.raw_manifest_bytes) + len(raw)
    assert result.observed_depth == 1
    assert result.observed_elements == 3
    assert result.value == {"value": 7}


def test_bounded_reader_retains_raw_manifest_when_typed_governance_uses_default(
    tmp_path, monkeypatch
) -> None:
    backing = FileSystemCAS(tmp_path / "raw-governance-cas")
    spec = CanonSpec(forbid_floats=False, exclude_none=False, max_depth=32)
    raw = to_canonical_bytes({"value": 7}, spec)
    ref = backing.put_bytes(
        raw,
        PutOptions(
            kind="test.core-json.bounded",
            media_type="application/json",
            canon=CanonInfo.from_spec(spec),
            governance=ArtifactGovernanceInfo(column_classification={"value": "public"}),
        ),
        return_selected_profile=True,
    )
    raw_manifest = json.loads(
        backing.get_raw_manifest_bytes(
            ref,
            manifest_profile_sha256=ref.manifest_profile_sha256,
        )
    )
    assert raw_manifest["governance"]["classification"] == "public"
    raw_manifest["governance"].pop("classification")
    selected_raw_manifest_bytes = json.dumps(raw_manifest, separators=(",", ":")).encode()
    selected_manifest = type(backing.get_manifest(ref)).model_validate_json(
        selected_raw_manifest_bytes
    )
    assert artifact_ref_for_manifest(selected_manifest) == ref
    backing._manifest_path_for_ref(ref.artifact_id, ref.manifest_profile_sha256).write_bytes(
        selected_raw_manifest_bytes
    )

    def reject_unbounded_reader(*_args, **_kwargs):
        raise AssertionError("strict path must parse one bounded manifest byte sequence")

    monkeypatch.setattr(backing, "get_manifest", reject_unbounded_reader)
    monkeypatch.setattr(backing, "get_manifest_by_profile", reject_unbounded_reader)
    monkeypatch.setattr(backing, "get_raw_manifest_bytes", reject_unbounded_reader)

    result = read_core_json_artifact_bounded(
        backing,
        ref,
        limits=_limits(raw, max_depth=1, max_elements=3),
    )

    assert result.manifest.governance is not None
    assert result.manifest.governance.classification == "public"
    assert result.raw_manifest_bytes == selected_raw_manifest_bytes
    assert "classification" not in json.loads(result.raw_manifest_bytes)["governance"]
    assert result.value == {"value": 7}
    assert result.observed_manifest_bytes == len(selected_raw_manifest_bytes)

    metadata = read_core_manifest_profile_bounded(
        backing,
        ref,
        max_manifest_bytes=len(selected_raw_manifest_bytes),
    )
    assert isinstance(metadata, CoreJsonManifestBoundedRead)
    assert metadata.effective_ref == ref
    assert metadata.raw_manifest_bytes == selected_raw_manifest_bytes
    assert metadata.observed_manifest_bytes == len(selected_raw_manifest_bytes)


def test_bounded_input_ref_resolves_full_identity_from_exact_raw_manifest(tmp_path, monkeypatch):
    store, ref, _raw = _profiled_store(tmp_path, {"value": 7})
    edge = InputRef(
        artifact_id=ref.artifact_id,
        role="method_input",
        manifest_profile_sha256=ref.manifest_profile_sha256,
    )
    original_read = store.read_raw_manifest_bytes_bounded_for_input
    calls = 0

    def observe_input_manifest_read(input_ref, *, max_manifest_bytes):
        nonlocal calls
        calls += 1
        assert input_ref == edge
        return original_read(input_ref, max_manifest_bytes=max_manifest_bytes)

    monkeypatch.setattr(
        store, "read_raw_manifest_bytes_bounded_for_input", observe_input_manifest_read
    )
    result = read_core_input_manifest_profile_bounded(
        store,
        edge,
        max_manifest_bytes=4096,
    )

    assert calls == 1
    assert result.effective_ref == ref
    assert result.effective_ref.kind == "test.core-json.bounded"
    assert result.effective_ref.media_type == "application/json"
    assert result.manifest.integrity.sha256 == edge.artifact_id.hex
    assert result.observed_manifest_bytes == len(result.raw_manifest_bytes)


def test_bounded_manifest_carrier_rebuilds_mutable_views_and_rejects_tampering(
    tmp_path,
):
    store, ref, _raw = _profiled_store(tmp_path, {"value": 7})
    metadata = read_core_manifest_profile_bounded(
        store,
        ref,
        max_manifest_bytes=4096,
    )
    metadata.manifest.kind = "test.forged.kind"
    metadata.effective_ref.kind = "test.forged.ref"

    assert metadata.manifest.kind == ref.kind
    assert metadata.effective_ref.kind == ref.kind

    tampered = replace(metadata, observed_manifest_bytes=metadata.observed_manifest_bytes + 1)
    with pytest.raises(CanonicalProfileRefusalError) as error:
        _ = tampered.effective_ref
    assert error.value.code == "canon_profile_bounded_manifest_carrier_mismatch"

    unsealed = replace(metadata, _seal=None)
    with pytest.raises(CanonicalProfileRefusalError) as unsealed_error:
        _ = unsealed.manifest
    assert unsealed_error.value.code == "canon_profile_bounded_manifest_carrier_unverified"


@pytest.mark.parametrize("read_only", [False, True], ids=["filesystem-cas", "readonly-cas"])
def test_bounded_input_ref_reads_actual_selected_profile_through_store_facade(
    tmp_path,
    monkeypatch,
    read_only: bool,
) -> None:
    writer, ref, _raw = _profiled_store(tmp_path, {"value": 7})
    store = FileSystemCAS.open_existing_read_only(writer.root) if read_only else writer
    edge = InputRef(
        artifact_id=ref.artifact_id,
        role="input",
        manifest_profile_sha256=ref.manifest_profile_sha256,
    )
    method = type(store).read_raw_manifest_bytes_bounded_for_input
    calls = 0

    def observe(self, input_ref, *, max_manifest_bytes):
        nonlocal calls
        calls += 1
        assert input_ref == edge
        return method(self, input_ref, max_manifest_bytes=max_manifest_bytes)

    monkeypatch.setattr(type(store), "read_raw_manifest_bytes_bounded_for_input", observe)
    result = read_core_input_manifest_profile_bounded(
        store,
        edge,
        max_manifest_bytes=4096,
    )
    assert calls == 1
    assert result.effective_ref == ref


def test_bounded_input_ref_requires_explicit_valid_profile_without_fallback(tmp_path, monkeypatch):
    store, ref, _raw = _profiled_store(tmp_path, {"value": 7})

    def reject_backend_read(*_args, **_kwargs):
        raise AssertionError("profile absence or malformation must refuse before storage")

    monkeypatch.setattr(store, "read_raw_manifest_bytes_bounded_for_input", reject_backend_read)
    for edge in (
        InputRef(artifact_id=ref.artifact_id, role="input"),
        InputRef.model_construct(
            artifact_id=ref.artifact_id,
            role="input",
            manifest_profile_sha256="sha256:NOT_A_PROFILE",
        ),
    ):
        with pytest.raises(CanonicalProfileRefusalError):
            read_core_input_manifest_profile_bounded(
                store,
                edge,
                max_manifest_bytes=4096,
            )


def test_bounded_input_ref_rejects_wrong_id_profile_manifest_hash_and_truncation(
    tmp_path,
):
    store, ref, _raw = _profiled_store(tmp_path, {"value": 7})
    other_store, other_ref, _other_raw = _profiled_store(tmp_path / "other", {"value": 9})
    del other_store
    edge = InputRef(
        artifact_id=ref.artifact_id,
        role="input",
        manifest_profile_sha256=ref.manifest_profile_sha256,
    )

    wrong_id = edge.model_copy(update={"artifact_id": other_ref.artifact_id})
    with pytest.raises((FileNotFoundError, CanonicalProfileRefusalError)):
        read_core_input_manifest_profile_bounded(
            store,
            wrong_id,
            max_manifest_bytes=4096,
        )

    wrong_profile = edge.model_copy(update={"manifest_profile_sha256": "sha256:" + ("0" * 64)})
    with pytest.raises((FileNotFoundError, CanonicalProfileRefusalError)):
        read_core_input_manifest_profile_bounded(
            store,
            wrong_profile,
            max_manifest_bytes=4096,
        )

    path = store._manifest_path_for_ref(ref.artifact_id, ref.manifest_profile_sha256)
    original_manifest = path.read_bytes()
    path.write_bytes(original_manifest[:-1])
    with pytest.raises(CanonicalProfileRefusalError):
        read_core_input_manifest_profile_bounded(
            store,
            edge,
            max_manifest_bytes=4096,
        )

    parsed = json.loads(original_manifest)
    parsed["integrity"]["sha256"] = other_ref.artifact_id.hex
    path.write_text(json.dumps(parsed, separators=(",", ":")), encoding="utf-8")
    with pytest.raises(CanonicalProfileRefusalError) as wrong_hash:
        read_core_input_manifest_profile_bounded(
            store,
            edge,
            max_manifest_bytes=4096,
        )
    assert wrong_hash.value.code == "canon_profile_selection_unverified"


def test_bounded_input_ref_rejects_sibling_profile_bytes_for_selected_edge(tmp_path):
    store = FileSystemCAS(tmp_path / "input-sibling-cas")
    spec = CanonSpec(forbid_floats=False, exclude_none=False)
    raw = to_canonical_bytes({"value": 7}, spec)
    selected = store.put_bytes(
        raw,
        PutOptions(
            kind="test.core-json.input-selected",
            media_type="application/json",
            canon=CanonInfo.from_spec(spec),
        ),
        return_selected_profile=True,
    )
    sibling = store.put_bytes(
        raw,
        PutOptions(
            kind="test.core-json.input-sibling",
            media_type="application/json",
            canon=CanonInfo.from_spec(spec),
        ),
        return_selected_profile=True,
    )
    assert selected.artifact_id == sibling.artifact_id
    assert selected.manifest_profile_sha256 != sibling.manifest_profile_sha256
    edge = InputRef(
        artifact_id=selected.artifact_id,
        role="input",
        manifest_profile_sha256=selected.manifest_profile_sha256,
    )

    class SiblingManifestReader:
        def read_raw_manifest_bytes_bounded_for_input(
            self,
            _input_ref,
            *,
            max_manifest_bytes: int,
        ) -> ArtifactBoundedManifestRead:
            assert max_manifest_bytes == 4096
            sibling_edge = InputRef(
                artifact_id=sibling.artifact_id,
                role="input",
                manifest_profile_sha256=sibling.manifest_profile_sha256,
            )
            return store.read_raw_manifest_bytes_bounded_for_input(
                sibling_edge,
                max_manifest_bytes=max_manifest_bytes,
            )

    with pytest.raises(CanonicalProfileRefusalError) as error:
        read_core_input_manifest_profile_bounded(
            SiblingManifestReader(),
            edge,
            max_manifest_bytes=4096,
        )
    assert error.value.code == "canon_profile_selection_unverified"


def test_bounded_input_ref_manifest_budget_counts_actual_selected_bytes(tmp_path, monkeypatch):
    store, ref, _raw = _profiled_store(tmp_path, {"value": 7})
    edge = InputRef(
        artifact_id=ref.artifact_id,
        role="input",
        manifest_profile_sha256=ref.manifest_profile_sha256,
    )
    path = store._manifest_path_for_ref(ref.artifact_id, ref.manifest_profile_sha256)
    raw_manifest = path.read_bytes()
    oversized = raw_manifest + (b" " * 64)
    path.write_bytes(oversized)

    with pytest.raises(CoreJsonReadBoundsRefusalError) as error:
        read_core_input_manifest_profile_bounded(
            store,
            edge,
            max_manifest_bytes=len(raw_manifest),
        )
    assert error.value.observed_manifest_bytes == len(oversized)
    assert error.value.limit_name == "max_manifest_bytes"

    original_read = store._read_cas_file_no_follow
    unbounded_materializations: list[int] = []

    def remove_preallocation_bound(
        path,
        *,
        member: str,
        max_bytes: int | None = None,
        raise_read_limit: bool = False,
        _read_attempt=None,
        _usage_field=None,
        _usage_stage: str = "bounded_manifest_transfer",
    ) -> bytes:
        data = original_read(
            path,
            member=member,
            max_bytes=None if member == "manifest" else max_bytes,
            raise_read_limit=False if member == "manifest" else raise_read_limit,
            _read_attempt=_read_attempt,
            _usage_field=_usage_field,
            _usage_stage=_usage_stage,
        )
        if member == "manifest":
            unbounded_materializations.append(len(data))
        return data

    monkeypatch.setattr(store, "_read_cas_file_no_follow", remove_preallocation_bound)
    with pytest.raises(CoreJsonReadBoundsRefusalError):
        read_core_input_manifest_profile_bounded(
            store,
            edge,
            max_manifest_bytes=len(raw_manifest),
        )
    assert unbounded_materializations == [len(oversized)]


def test_bounded_reader_scans_escaped_strings_without_counting_braces_inside_them(
    tmp_path,
) -> None:
    value = {"text": "quoted " + chr(92) + chr(34) + " brace } and array [ ] plus ☃"}
    store, ref, raw = _profiled_store(tmp_path, value)

    result = read_core_json_artifact_bounded(
        store,
        ref,
        limits=_limits(raw, max_depth=1, max_elements=3),
    )

    assert result.value == value
    assert result.observed_depth == 1
    assert result.observed_elements == 3


def test_bounded_reader_refuses_nested_arrays_before_core_json_materialization(
    tmp_path,
) -> None:
    store, ref, raw = _profiled_store(tmp_path, {"nested": [[[0]]]})

    with pytest.raises(CoreJsonReadBoundsRefusalError) as error:
        read_core_json_artifact_bounded(
            store,
            ref,
            limits=_limits(raw, max_depth=3, max_elements=32),
        )

    assert error.value.code == "canon_profile_bounded_depth_exceeded"
    assert error.value.observed_bytes == len(raw)
    assert error.value.observed_depth == 4


@pytest.mark.parametrize(
    (
        "value",
        "limit_name",
        "max_bytes_delta",
        "max_depth",
        "max_elements",
        "expected_observed",
    ),
    [
        pytest.param({"k": 0}, "max_bytes", -1, 8, 8, -1, id="bytes"),
        pytest.param({"k": [0]}, "max_depth", 0, 1, 8, 2, id="depth"),
        pytest.param({"k": 0}, "max_elements", 0, 1, 2, 3, id="elements"),
    ],
)
def test_each_selected_bound_refuses_before_decode_and_removal_reopens_value(
    tmp_path,
    monkeypatch,
    value: object,
    limit_name: str,
    max_bytes_delta: int,
    max_depth: int,
    max_elements: int,
    expected_observed: int,
) -> None:
    import polisyos.core.artifacts.canonical_profile as owner

    store, ref, raw = _profiled_store(tmp_path, value)
    limits = CoreJsonReadLimits(
        max_bytes=len(raw) + max_bytes_delta,
        max_depth=max_depth,
        max_elements=max_elements,
        max_manifest_bytes=4096,
    )
    original_decode = owner._decode_core_payload_under_declaration
    decode_calls = 0

    def observed_decode(payload: bytes, declaration: object):
        nonlocal decode_calls
        decode_calls += 1
        return original_decode(payload, declaration)

    monkeypatch.setattr(owner, "_decode_core_payload_under_declaration", observed_decode)

    with pytest.raises(CoreJsonReadBoundsRefusalError) as error:
        read_core_json_artifact_bounded(store, ref, limits=limits)

    assert error.value.code == f"canon_profile_bounded_{limit_name.removeprefix('max_')}_exceeded"
    assert error.value.limit_name == limit_name
    observed_name = f"observed_{limit_name.removeprefix('max_')}"
    expected = len(raw) if expected_observed < 0 else expected_observed
    assert getattr(error.value, observed_name) == expected
    assert decode_calls == 0

    # Matched removal: exact manifest/profile selection remains, but deleting
    # the generic bound admits the conformant value for each independent axis.
    def remove_selected_bounds(
        _limits: CoreJsonReadLimits,
        *,
        observed_manifest_bytes: int,
        observed_bytes: int,
        observed_depth: int,
        observed_elements: int,
    ) -> None:
        del observed_manifest_bytes, observed_bytes, observed_depth, observed_elements

    monkeypatch.setattr(owner, "_enforce_core_json_read_bounds", remove_selected_bounds)
    result = read_core_json_artifact_bounded(store, ref, limits=limits)
    assert result.value == value
    assert decode_calls >= 1


def test_bounded_reader_uses_read_only_cas_streaming_facade(
    tmp_path,
    monkeypatch,
) -> None:
    writer, ref, raw = _profiled_store(tmp_path, {"value": 7})
    reader = FileSystemCAS.open_existing_read_only(writer.root)
    assert isinstance(reader, ReadOnlyFileSystemCAS)
    original_open_member_bounded = ReadOnlyFileSystemCAS.open_member_bounded
    original_bounded_manifest_read = ReadOnlyFileSystemCAS.read_raw_manifest_bytes_bounded
    open_member_calls = 0
    bounded_manifest_read_calls = 0

    def observed_open_member_bounded(
        self,
        artifact_id,
        member,
        *,
        max_manifest_bytes,
        expected_manifest_sha256,
        max_member_bytes,
    ):
        nonlocal open_member_calls
        open_member_calls += 1
        assert max_manifest_bytes == 4096
        assert expected_manifest_sha256
        assert max_member_bytes == len(raw)
        return original_open_member_bounded(
            self,
            artifact_id,
            member,
            max_manifest_bytes=max_manifest_bytes,
            expected_manifest_sha256=expected_manifest_sha256,
            max_member_bytes=max_member_bytes,
        )

    def observed_bounded_manifest_read(self, artifact_id, *, max_manifest_bytes):
        nonlocal bounded_manifest_read_calls
        bounded_manifest_read_calls += 1
        assert artifact_id == ref
        return original_bounded_manifest_read(
            self,
            artifact_id,
            max_manifest_bytes=max_manifest_bytes,
        )

    def reject_get_bytes(self, _artifact_id):
        raise AssertionError("bounded reader must use the read-only streaming bridge")

    monkeypatch.setattr(
        ReadOnlyFileSystemCAS,
        "open_member_bounded",
        observed_open_member_bounded,
    )
    monkeypatch.setattr(
        ReadOnlyFileSystemCAS,
        "read_raw_manifest_bytes_bounded",
        observed_bounded_manifest_read,
    )
    monkeypatch.setattr(ReadOnlyFileSystemCAS, "get_bytes", reject_get_bytes)
    monkeypatch.setattr(ReadOnlyFileSystemCAS, "get_manifest", reject_get_bytes)
    monkeypatch.setattr(ReadOnlyFileSystemCAS, "get_manifest_by_profile", reject_get_bytes)
    monkeypatch.setattr(ReadOnlyFileSystemCAS, "get_raw_manifest_bytes", reject_get_bytes)

    result = read_core_json_artifact_bounded(
        reader,
        ref,
        limits=_limits(raw, max_depth=1, max_elements=3),
    )

    assert result.value == {"value": 7}
    assert open_member_calls == 1
    assert bounded_manifest_read_calls == 1
    assert result.observed_manifest_selection_bytes > 0
    assert result.observed_manifest_verification_bytes > 0
    assert result.observed_payload_bytes == len(raw)
    assert result.observed_source_bytes == (
        result.observed_manifest_selection_bytes
        + result.observed_manifest_verification_bytes
        + result.observed_payload_bytes
    )


def test_strict_bounded_reader_refuses_legacy_stream_without_fallback(tmp_path) -> None:
    store, ref, raw = _profiled_store(tmp_path, {"value": 7})
    legacy_open_calls = 0

    class LegacyReader:
        def read_raw_manifest_bytes_bounded(self, artifact_id, *, max_manifest_bytes):
            return store.read_raw_manifest_bytes_bounded(
                artifact_id,
                max_manifest_bytes=max_manifest_bytes,
            )

        def open_member(self, *_args, **_kwargs):
            nonlocal legacy_open_calls
            legacy_open_calls += 1
            return store.open_member(*_args, **_kwargs)

    with pytest.raises(CoreJsonReadBoundsRefusalError) as error:
        read_core_json_artifact_bounded(
            LegacyReader(),
            ref,
            limits=_limits(raw, max_depth=8, max_elements=32),
        )

    assert error.value.code == "canon_profile_bounded_stream_unavailable"
    assert error.value.observed_manifest_selection_bytes > 0
    assert error.value.observed_manifest_verification_bytes == 0
    assert error.value.observed_payload_bytes == 0
    assert error.value.observed_source_bytes == error.value.observed_manifest_selection_bytes
    assert error.value.failure_stage == "bounded_member_open_preflight"
    assert legacy_open_calls == 0


def test_bounded_reader_keeps_attempted_owner_usage_unknown_without_fallback(
    tmp_path,
) -> None:
    store, ref, raw = _profiled_store(tmp_path, {"value": 7})
    attempted = 0

    class TypeErrorReader:
        def read_raw_manifest_bytes_bounded(self, artifact_id, *, max_manifest_bytes):
            return store.read_raw_manifest_bytes_bounded(
                artifact_id,
                max_manifest_bytes=max_manifest_bytes,
            )

        def open_member_bounded(self, *_args, **_kwargs):
            nonlocal attempted
            attempted += 1
            raise TypeError("backend failed after bounded open was attempted")

        def open_member(self, *_args, **_kwargs):
            raise AssertionError("bounded refusal must not fall back to legacy open")

    with pytest.raises(CoreJsonReadBoundsRefusalError) as error:
        read_core_json_artifact_bounded(
            TypeErrorReader(),
            ref,
            limits=_limits(raw, max_depth=8, max_elements=32),
        )

    refusal = error.value
    assert attempted == 1
    assert refusal.observed_manifest_selection_bytes > 0
    assert refusal.observed_manifest_verification_bytes is None
    assert refusal.observed_payload_bytes is None
    assert refusal.observed_source_bytes is None
    assert refusal.failure_stage == "bounded_member_usage_unknown"
    assert refusal.original_exception_type == "TypeError"
    assert isinstance(refusal.__cause__, TypeError)


@pytest.mark.parametrize("reports_source_counter", [True, False])
def test_bounded_reader_accounts_successful_partial_transfer_before_read_error(
    tmp_path,
    reports_source_counter: bool,
) -> None:
    store, ref, raw = _profiled_store(tmp_path, {"value": "x" * 200})
    selected_manifest = store.get_raw_manifest_bytes_bounded(ref, max_manifest_bytes=4096)

    class PartialReadErrorReader:
        def read_raw_manifest_bytes_bounded(self, artifact_id, *, max_manifest_bytes):
            return store.read_raw_manifest_bytes_bounded(
                artifact_id,
                max_manifest_bytes=max_manifest_bytes,
            )

        def open_member_bounded(self, *args, **kwargs):
            owner_attempt = store.open_member_bounded(*args, **kwargs)

            class PartialStream:
                def __init__(self, owner_stream):
                    self._owner_stream = owner_stream
                    self.member_size_bytes = owner_stream.member_size_bytes
                    self.observed_manifest_verification_bytes = (
                        owner_stream.observed_manifest_verification_bytes
                    )

                def __getattr__(self, name: str) -> object:
                    if name == "observed_payload_bytes" and reports_source_counter:
                        return self._owner_stream.observed_payload_bytes
                    raise AttributeError(name)

                @property
                def payload_integrity_verified(self):
                    return self._owner_stream.payload_integrity_verified

                @property
                def receipt(self):
                    return self._owner_stream.receipt

                def read(self, size: int) -> bytes:
                    if self._owner_stream.observed_payload_bytes:
                        raise OSError("injected failure before the next owner read")
                    return self._owner_stream.read(min(size, 16))

            class PartialAttempt:
                @property
                def usage(self):
                    return owner_attempt.usage

                def __enter__(self):
                    return PartialStream(owner_attempt.__enter__())

                def __exit__(self, exc_type, exc, traceback):
                    return owner_attempt.__exit__(exc_type, exc, traceback)

            return PartialAttempt()

    with pytest.raises(CoreJsonReadBoundsRefusalError) as error:
        read_core_json_artifact_bounded(
            PartialReadErrorReader(),
            ref,
            limits=CoreJsonReadLimits(
                max_bytes=len(raw),
                max_depth=8,
                max_elements=32,
                max_manifest_bytes=4096,
            ),
        )

    refusal = error.value
    assert refusal.observed_manifest_selection_bytes == len(selected_manifest)
    assert refusal.observed_manifest_verification_bytes == len(selected_manifest)
    assert refusal.observed_payload_bytes == 16
    assert refusal.observed_source_bytes == 2 * len(selected_manifest) + 16
    assert refusal.payload_integrity_verified is False
    assert refusal.original_exception_type == "OSError"
    assert isinstance(refusal.__cause__, OSError)


def test_bounded_reader_keeps_payload_unknown_when_wrapper_hides_owner_attempt_receipt(
    tmp_path,
) -> None:
    from contextlib import contextmanager

    store, ref, raw = _profiled_store(tmp_path, {"value": "x" * 200})
    selected_manifest = store.get_raw_manifest_bytes(
        ref, manifest_profile_sha256=ref.manifest_profile_sha256
    )

    class ReceiptHiddenReader:
        def read_raw_manifest_bytes_bounded(self, artifact_id, *, max_manifest_bytes):
            return store.read_raw_manifest_bytes_bounded(
                artifact_id,
                max_manifest_bytes=max_manifest_bytes,
            )

        @contextmanager
        def open_member_bounded(self, *args, **kwargs):
            with store.open_member_bounded(*args, **kwargs) as owner_stream:

                class DelegatingStream:
                    member_size_bytes = owner_stream.member_size_bytes
                    calls = 0

                    def read(self, size: int) -> bytes:
                        self.calls += 1
                        chunk = owner_stream.read(min(size, 16))
                        if self.calls == 2:
                            raise OSError("injected failure after delegated owner read")
                        return chunk

                yield DelegatingStream()

    with pytest.raises(CoreJsonReadBoundsRefusalError) as error:
        read_core_json_artifact_bounded(
            ReceiptHiddenReader(),
            ref,
            limits=CoreJsonReadLimits(
                max_bytes=len(raw),
                max_depth=8,
                max_elements=32,
                max_manifest_bytes=4096,
            ),
        )

    refusal = error.value
    assert refusal.observed_manifest_selection_bytes == len(selected_manifest)
    assert refusal.observed_manifest_verification_bytes is None
    assert refusal.observed_payload_bytes is None
    assert refusal.observed_source_bytes is None
    assert refusal.payload_integrity_verified is False
    assert refusal.original_exception_type == "OSError"
    assert isinstance(refusal.__cause__, OSError)


@pytest.mark.parametrize("reports_exact_bytes", [True, False])
def test_manifest_attempt_preserves_known_usage_and_keeps_unknown_usage_unknown(
    tmp_path,
    reports_exact_bytes: bool,
) -> None:
    store, ref, _raw = _profiled_store(tmp_path, {"value": 7})
    selected_manifest = store.get_raw_manifest_bytes_bounded(ref, max_manifest_bytes=4096)
    original_error: RuntimeError | None = None

    class ManifestAttemptReader:
        def read_raw_manifest_bytes_bounded(self, artifact_id, *, max_manifest_bytes):
            nonlocal original_error
            returned = store.read_raw_manifest_bytes_bounded(
                artifact_id,
                max_manifest_bytes=max_manifest_bytes,
            )
            original_error = RuntimeError("injected error after manifest transfer")
            if reports_exact_bytes:
                raise ArtifactBoundedManifestReadError(
                    "injected_manifest_read_refusal",
                    usage=replace(
                        returned.usage,
                        failure_stage="selected_manifest_reader_refusal",
                    ),
                    original_exception=original_error,
                ) from original_error
            original_error.bytes_read = len(returned.raw_manifest_bytes)  # type: ignore[attr-defined]
            raise original_error

        def open_member_bounded(self, *_args, **_kwargs):
            raise AssertionError("payload open must not follow a manifest refusal")

    with pytest.raises(CoreJsonReadBoundsRefusalError) as error:
        read_core_json_artifact_bounded(
            ManifestAttemptReader(),
            ref,
            limits=_limits(
                _raw,
                max_depth=8,
                max_elements=32,
                max_manifest_bytes=4096,
            ),
        )

    refusal = error.value
    assert original_error is not None
    assert refusal.failure_stage == "selected_manifest_reader_refusal"
    assert refusal.observed_manifest_selection_bytes == (
        len(selected_manifest) if reports_exact_bytes else None
    )
    assert refusal.observed_manifest_verification_bytes == 0
    assert refusal.observed_payload_bytes == 0
    assert refusal.observed_source_bytes == (
        len(selected_manifest) if reports_exact_bytes else None
    )
    assert refusal.original_exception_type == "RuntimeError"
    assert refusal.__cause__ is original_error


def test_bounded_reader_preserves_usage_after_full_transfer_decode_refusal(
    tmp_path,
) -> None:
    raw = b'{"value": 7,}'
    store = FileSystemCAS(tmp_path / "malformed-profiled-cas")
    ref = store.put_bytes(
        raw,
        PutOptions(
            kind="test.core-json.bounded",
            media_type="application/json",
            canon=CanonInfo(),
        ),
        return_selected_profile=True,
    )
    assert isinstance(ref, ArtifactRef)

    with pytest.raises(CoreJsonReadBoundsRefusalError) as error:
        read_core_json_artifact_bounded(
            store,
            ref,
            limits=CoreJsonReadLimits(
                max_bytes=len(raw),
                max_depth=8,
                max_elements=32,
                max_manifest_bytes=4096,
            ),
        )

    refusal = error.value
    assert refusal.code != "canon_profile_absent"
    assert refusal.observed_payload_bytes == len(raw)
    assert refusal.observed_payload_size == len(raw)
    assert refusal.payload_integrity_verified is True
    assert refusal.observed_source_bytes == (
        refusal.observed_manifest_selection_bytes
        + refusal.observed_manifest_verification_bytes
        + len(raw)
    )
    assert refusal.original_exception_type is not None
    assert refusal.__cause__ is not None


def test_bounded_manifest_integrity_refusal_retains_bytes_read_before_postread_stat_error(
    tmp_path,
    monkeypatch,
) -> None:
    import polisyos.core.artifacts.store as store_module

    store, ref, _raw = _profiled_store(tmp_path, {"value": 7})
    manifest_path = store._manifest_path_for_ref(ref.artifact_id, ref.manifest_profile_sha256)
    expected_bytes = manifest_path.stat().st_size
    real_fstat = os.fstat
    fstat_calls = 0

    def fail_after_read(descriptor: int) -> os.stat_result:
        nonlocal fstat_calls
        fstat_calls += 1
        if fstat_calls == 2:
            raise OSError("injected post-read stat failure")
        return real_fstat(descriptor)

    monkeypatch.setattr(store_module.os, "fstat", fail_after_read)

    with pytest.raises(OSError) as error:
        store._read_cas_file_no_follow(
            manifest_path,
            member="manifest",
            max_bytes=4096,
            raise_read_limit=True,
        )

    assert fstat_calls == 2
    assert error.value.bytes_read == expected_bytes  # type: ignore[attr-defined]


def test_core_open_context_entry_keeps_exact_verification_bytes_before_fstat_refusal(
    tmp_path,
    monkeypatch,
) -> None:
    import polisyos.core.artifacts.store as store_module

    store, ref, raw = _profiled_store(tmp_path, {"value": 7})
    manifest_bytes = store.get_raw_manifest_bytes(
        ref, manifest_profile_sha256=ref.manifest_profile_sha256
    )
    real_fstat = os.fstat
    fstat_calls = 0

    def fail_verification_postread(descriptor: int) -> os.stat_result:
        nonlocal fstat_calls
        fstat_calls += 1
        if fstat_calls == 4:
            raise OSError("injected verification post-read fstat failure")
        return real_fstat(descriptor)

    monkeypatch.setattr(store_module.os, "fstat", fail_verification_postread)
    with pytest.raises(CoreJsonReadBoundsRefusalError) as error:
        read_core_json_artifact_bounded(
            store,
            ref,
            limits=_limits(raw, max_depth=8, max_elements=32),
        )

    refusal = error.value
    assert fstat_calls == 4
    assert refusal.observed_manifest_selection_bytes == len(manifest_bytes)
    assert refusal.observed_manifest_verification_bytes == len(manifest_bytes)
    assert refusal.observed_payload_bytes == 0
    assert refusal.observed_source_bytes == 2 * len(manifest_bytes)
    assert refusal.payload_integrity_verified is False
    assert refusal.failure_stage == "manifest_verification_postread_validation"
    assert refusal.original_exception_type == "OSError"
    assert isinstance(refusal.__cause__, OSError)


def test_read_only_facade_preserves_usage_before_verification_refusal(
    tmp_path,
    monkeypatch,
) -> None:
    import polisyos.core.artifacts.store as store_module

    writer, ref, raw = _profiled_store(tmp_path, {"value": 7})
    manifest_bytes = writer.get_raw_manifest_bytes(
        ref,
        manifest_profile_sha256=ref.manifest_profile_sha256,
    )
    reader = FileSystemCAS.open_existing_read_only(writer.root)
    real_fstat = os.fstat
    fstat_calls = 0

    def fail_verification_postread(descriptor: int) -> os.stat_result:
        nonlocal fstat_calls
        fstat_calls += 1
        if fstat_calls == 4:
            raise OSError("injected read-only verification post-read fstat failure")
        return real_fstat(descriptor)

    monkeypatch.setattr(store_module.os, "fstat", fail_verification_postread)
    with pytest.raises(CoreJsonReadBoundsRefusalError) as error:
        read_core_json_artifact_bounded(
            reader,
            ref,
            limits=_limits(raw, max_depth=8, max_elements=32),
        )

    refusal = error.value
    assert fstat_calls == 4
    assert refusal.observed_manifest_selection_bytes == len(manifest_bytes)
    assert refusal.observed_manifest_verification_bytes == len(manifest_bytes)
    assert refusal.observed_payload_bytes == 0
    assert refusal.observed_source_bytes == 2 * len(manifest_bytes)
    assert refusal.failure_stage == "manifest_verification_postread_validation"
    assert isinstance(refusal.__cause__, ArtifactReadOnlyUnavailableError)
    assert isinstance(refusal.__cause__.__cause__, OSError)


def test_core_finish_validation_fstat_refusal_keeps_exact_payload_usage_and_phase(
    tmp_path,
    monkeypatch,
) -> None:
    import polisyos.core.artifacts.store as store_module

    store, ref, raw = _profiled_store(tmp_path, {"value": 7})
    manifest_bytes = store.get_raw_manifest_bytes(
        ref, manifest_profile_sha256=ref.manifest_profile_sha256
    )
    real_fstat = os.fstat
    fstat_calls = 0

    def fail_finish_validation(descriptor: int) -> os.stat_result:
        nonlocal fstat_calls
        fstat_calls += 1
        if fstat_calls == 6:
            raise OSError("injected member finish-validation fstat failure")
        return real_fstat(descriptor)

    monkeypatch.setattr(store_module.os, "fstat", fail_finish_validation)
    with pytest.raises(CoreJsonReadBoundsRefusalError) as error:
        read_core_json_artifact_bounded(
            store,
            ref,
            limits=_limits(raw, max_depth=8, max_elements=32),
        )

    refusal = error.value
    assert fstat_calls == 6
    assert refusal.observed_manifest_selection_bytes == len(manifest_bytes)
    assert refusal.observed_manifest_verification_bytes == len(manifest_bytes)
    assert refusal.observed_payload_bytes == len(raw)
    assert refusal.observed_source_bytes == 2 * len(manifest_bytes) + len(raw)
    assert refusal.payload_integrity_verified is False
    assert refusal.failure_stage == "bounded_payload_finish_validation"
    assert refusal.original_exception_type == "OSError"
    assert isinstance(refusal.__cause__, OSError)


@pytest.mark.parametrize(
    ("cleanup_code", "expected_cleanup_code"),
    [("core_cleanup_code", "core_cleanup_code"), (17, None)],
)
def test_payload_close_failure_after_verified_read_refuses_core_admission(
    tmp_path,
    monkeypatch,
    cleanup_code: object,
    expected_cleanup_code: str | None,
) -> None:
    import polisyos.core.artifacts.store as store_module

    store, ref, raw = _profiled_store(tmp_path, {"value": 7})
    real_fdopen = os.fdopen
    fdopen_calls = 0

    class CloseError(OSError):
        code: object

    close_error = CloseError("injected payload close failure after verification")
    close_error.code = cleanup_code

    class CloseThenRaise:
        def __init__(self, wrapped) -> None:
            self._wrapped = wrapped

        def fileno(self) -> int:
            return self._wrapped.fileno()

        def read(self, size: int = -1) -> bytes:
            return self._wrapped.read(size)

        def close(self) -> None:
            self._wrapped.close()
            raise close_error

    def fail_payload_close(descriptor: int, *args, **kwargs):
        nonlocal fdopen_calls
        fdopen_calls += 1
        wrapped = real_fdopen(descriptor, *args, **kwargs)
        return CloseThenRaise(wrapped) if fdopen_calls == 3 else wrapped

    monkeypatch.setattr(store_module.os, "fdopen", fail_payload_close)
    with pytest.raises(CoreJsonReadBoundsRefusalError) as error:
        read_core_json_artifact_bounded(
            store,
            ref,
            limits=_limits(raw, max_depth=8, max_elements=32),
        )

    refusal = error.value
    assert fdopen_calls == 3
    assert refusal.observed_payload_bytes == len(raw)
    assert refusal.payload_integrity_verified is True
    assert refusal.observed_source_bytes == (
        refusal.observed_manifest_selection_bytes
        + refusal.observed_manifest_verification_bytes
        + len(raw)
    )
    assert refusal.failure_stage == "bounded_member_close"
    assert refusal.cleanup_failure_stage == "bounded_member_close"
    assert refusal.cleanup_exception_type == "CloseError"
    assert refusal.cleanup_exception_code == expected_cleanup_code
    assert refusal.__cause__ is close_error


def test_manifest_fdopen_close_failure_retains_exact_verification_usage(
    tmp_path,
    monkeypatch,
) -> None:
    import polisyos.core.artifacts.store as store_module

    store, ref, raw = _profiled_store(tmp_path, {"value": 7})
    manifest_bytes = store.get_raw_manifest_bytes(
        ref,
        manifest_profile_sha256=ref.manifest_profile_sha256,
    )
    real_fdopen = os.fdopen
    fdopen_calls = 0
    close_error = OSError("injected manifest close failure after exact transfer")

    class CloseThenRaise:
        def __init__(self, wrapped) -> None:
            self._wrapped = wrapped

        def fileno(self) -> int:
            return self._wrapped.fileno()

        def read(self, size: int = -1) -> bytes:
            return self._wrapped.read(size)

        def close(self) -> None:
            self._wrapped.close()
            raise close_error

    def fail_verification_close(descriptor: int, *args, **kwargs):
        nonlocal fdopen_calls
        fdopen_calls += 1
        wrapped = real_fdopen(descriptor, *args, **kwargs)
        return CloseThenRaise(wrapped) if fdopen_calls == 2 else wrapped

    monkeypatch.setattr(store_module.os, "fdopen", fail_verification_close)
    with pytest.raises(CoreJsonReadBoundsRefusalError) as error:
        read_core_json_artifact_bounded(
            store,
            ref,
            limits=_limits(raw, max_depth=8, max_elements=32),
        )

    refusal = error.value
    assert fdopen_calls == 2
    assert refusal.observed_manifest_selection_bytes == len(manifest_bytes)
    assert refusal.observed_manifest_verification_bytes == len(manifest_bytes)
    assert refusal.observed_payload_bytes == 0
    assert refusal.observed_source_bytes == 2 * len(manifest_bytes)
    assert refusal.failure_stage == "manifest_verification_close"
    assert refusal.cleanup_failure_stage == "manifest_verification_close"
    assert refusal.cleanup_exception_type == "OSError"
    assert refusal.cleanup_exception_code is None
    assert refusal.__cause__ is close_error


def test_nonbytes_stream_result_does_not_claim_an_exact_payload_total(tmp_path) -> None:
    from contextlib import contextmanager

    store, ref, raw = _profiled_store(tmp_path, {"value": "x" * 200})

    class InvalidChunkReader:
        def read_raw_manifest_bytes_bounded(self, artifact_id, *, max_manifest_bytes):
            return store.read_raw_manifest_bytes_bounded(
                artifact_id,
                max_manifest_bytes=max_manifest_bytes,
            )

        @contextmanager
        def open_member_bounded(self, *args, **kwargs):
            with store.open_member_bounded(*args, **kwargs) as owner:

                class InvalidChunkStream:
                    member_size_bytes = owner.member_size_bytes
                    observed_manifest_verification_bytes = (
                        owner.observed_manifest_verification_bytes
                    )
                    payload_integrity_verified = owner.payload_integrity_verified

                    def read(self, size: int) -> bytearray:
                        return bytearray(owner.read(size))

                yield InvalidChunkStream()

    with pytest.raises(CoreJsonReadBoundsRefusalError) as error:
        read_core_json_artifact_bounded(
            InvalidChunkReader(),
            ref,
            limits=CoreJsonReadLimits(
                max_bytes=len(raw),
                max_depth=8,
                max_elements=32,
                max_manifest_bytes=4096,
            ),
        )

    refusal = error.value
    assert refusal.code == "canon_profile_bounded_stream_invalid"
    assert refusal.observed_manifest_selection_bytes is not None
    assert refusal.observed_manifest_verification_bytes is None
    assert refusal.observed_payload_bytes is None
    assert refusal.observed_source_bytes is None
    assert refusal.payload_integrity_verified is False
    assert refusal.original_exception_type == "TypeError"
    assert isinstance(refusal.__cause__, TypeError)


def test_bounded_reader_preserves_core_tagged_decimal_values(tmp_path) -> None:
    value = {"number": Decimal("12.50")}
    store, ref, raw = _profiled_store(tmp_path, value)

    result = read_core_json_artifact_bounded(
        store,
        ref,
        limits=_limits(raw, max_depth=8, max_elements=32),
    )

    assert result.value == value
    assert type(result.value["number"]) is Decimal
    assert result.value["number"] == Decimal("12.50")
    assert result.raw_payload_bytes == raw
    assert result.effective_ref == ref
    assert result.observed_bytes == len(raw)


def test_bounded_owner_preflights_manifest_size_before_payload_read(tmp_path) -> None:
    store, ref, raw = _profiled_store(tmp_path, {"large": "x" * 128})
    selected_manifest = store.get_raw_manifest_bytes_bounded(ref, max_manifest_bytes=4096)

    attempt = store.open_member_bounded(
        ref,
        "blob",
        max_manifest_bytes=4096,
        expected_manifest_sha256=hashlib.sha256(selected_manifest).hexdigest(),
        max_member_bytes=32,
    )
    with pytest.raises(ArtifactMemberReadBoundsError) as error:
        with attempt:
            raise AssertionError("over-cap member must refuse before yielding a stream")

    assert attempt.usage.failure_stage == "bounded_member_bounds_validation"
    assert attempt.usage.observed_payload_bytes == 0
    assert error.value.observed_member_size == len(raw)
    assert error.value.max_member_bytes == 32
    assert error.value.observed_manifest_verification_bytes == len(selected_manifest)
    assert error.value.observed_payload_bytes == 0
    assert error.value.payload_integrity_verified is False


def test_bounded_reader_rejects_actual_payload_stream_over_selected_byte_limit(
    tmp_path,
) -> None:
    payload = b'{"input":"' + (b"x" * 200) + b'"}'
    backing = FileSystemCAS(tmp_path / "oversize-cas")
    base_ref = backing.put_bytes(
        payload,
        PutOptions(
            kind="test.core-json.bounded",
            media_type="application/json",
            canon=CanonInfo(),
        ),
        return_selected_profile=True,
    )
    limits = CoreJsonReadLimits(
        max_bytes=64,
        max_depth=8,
        max_elements=32,
        max_manifest_bytes=4096,
    )
    with pytest.raises(CoreJsonReadBoundsRefusalError) as error:
        read_core_json_artifact_bounded(
            backing,
            base_ref,
            limits=limits,
        )

    assert error.value.code == "canon_profile_bounded_bytes_exceeded"
    assert error.value.observed_bytes == 0
    assert error.value.observed_payload_size == len(payload)
    assert error.value.payload_integrity_verified is False
    assert error.value.observed_manifest_verification_bytes > 0
    assert error.value.observed_source_bytes == (
        error.value.observed_manifest_selection_bytes
        + error.value.observed_manifest_verification_bytes
    )
    assert error.value.limits.max_bytes == 64


def test_structural_refusal_aborts_stream_without_drain_and_owner_normal_exit_is_the_control(
    tmp_path,
) -> None:
    payload = b'{"nested":[[[0]]],"trailing":"' + (b"x" * (2 * 1024 * 1024)) + b'"}'
    store, ref, _raw = _profiled_store(tmp_path, json.loads(payload))
    # Store canonicalization produces the same valid value bytes under the selected profile.
    stored_payload = store.get_bytes(ref)
    assert len(stored_payload) > 1024 * 1024
    limits = CoreJsonReadLimits(
        max_bytes=len(stored_payload),
        max_depth=2,
        max_elements=100,
        max_manifest_bytes=4096,
    )

    with pytest.raises(CoreJsonReadBoundsRefusalError) as error:
        read_core_json_artifact_bounded(store, ref, limits=limits)

    refusal = error.value
    assert refusal.code == "canon_profile_bounded_depth_exceeded"
    assert 0 < refusal.observed_payload_bytes < len(stored_payload)
    assert refusal.observed_payload_size == len(stored_payload)
    assert refusal.payload_integrity_verified is False
    assert refusal.observed_source_bytes == (
        refusal.observed_manifest_selection_bytes
        + refusal.observed_manifest_verification_bytes
        + refusal.observed_payload_bytes
    )

    # Removal control: normal owner context exit intentionally drains and verifies.
    with store.open_member_bounded(
        ref,
        "blob",
        max_manifest_bytes=4096,
        expected_manifest_sha256=hashlib.sha256(
            store.get_raw_manifest_bytes_bounded(ref, max_manifest_bytes=4096)
        ).hexdigest(),
        max_member_bytes=len(stored_payload),
    ) as source:
        source.read(64 * 1024)
    assert source.payload_integrity_verified is True
    assert source.observed_payload_bytes == len(stored_payload)


def test_manifest_byte_limit_refuses_before_parse_and_removal_exposes_allocation(
    tmp_path,
    monkeypatch,
) -> None:
    store, ref, _payload = _profiled_store(tmp_path, {"value": 7})
    raw_manifest = store.get_raw_manifest_bytes(
        ref,
        manifest_profile_sha256=ref.manifest_profile_sha256,
    )
    max_manifest_bytes = len(raw_manifest)
    oversized_manifest = raw_manifest + (b" " * (256 * 1024))
    manifest_path = store._manifest_path_for_ref(ref.artifact_id, ref.manifest_profile_sha256)
    manifest_path.write_bytes(oversized_manifest)

    with pytest.raises(CoreJsonReadBoundsRefusalError) as error:
        read_core_manifest_profile_bounded(
            store,
            ref,
            max_manifest_bytes=max_manifest_bytes,
        )

    assert error.value.code == "canon_profile_bounded_manifest_bytes_exceeded"
    assert error.value.limit_name == "max_manifest_bytes"
    assert error.value.limit_value == max_manifest_bytes
    assert error.value.observed_manifest_bytes == len(oversized_manifest)

    original_read = store._read_cas_file_no_follow
    materialized_oversize_reads: list[tuple[int | None, int]] = []

    def remove_manifest_preallocation_bound(
        path,
        *,
        member: str,
        max_bytes: int | None = None,
        raise_read_limit: bool = False,
    ) -> bytes:
        data = original_read(
            path,
            member=member,
            max_bytes=None if member == "manifest" else max_bytes,
            raise_read_limit=False if member == "manifest" else raise_read_limit,
        )
        if member == "manifest":
            materialized_oversize_reads.append((max_bytes, len(data)))
        return data

    monkeypatch.setattr(store, "_read_cas_file_no_follow", remove_manifest_preallocation_bound)
    with pytest.raises(CoreJsonReadBoundsRefusalError):
        read_core_manifest_profile_bounded(
            store,
            ref,
            max_manifest_bytes=max_manifest_bytes,
        )

    assert materialized_oversize_reads == [(max_manifest_bytes, len(oversized_manifest))]


def test_malformed_present_manifest_refuses_without_defaulting_to_absence(
    tmp_path,
) -> None:
    store, ref, _payload = _profiled_store(tmp_path, {"value": 7})
    store._manifest_path_for_ref(ref.artifact_id, ref.manifest_profile_sha256).write_bytes(b"{")

    with pytest.raises(CanonicalProfileRefusalError) as error:
        read_core_manifest_profile_bounded(
            store,
            ref,
            max_manifest_bytes=4096,
        )

    assert error.value.code == "canon_profile_bounded_manifest_invalid"


def test_bounded_blob_open_rejects_manifest_drift_after_prepost_metadata_read(
    tmp_path,
    monkeypatch,
) -> None:
    store, ref, raw_payload = _profiled_store(tmp_path, {"value": 7})
    raw_manifest = store.get_raw_manifest_bytes(
        ref,
        manifest_profile_sha256=ref.manifest_profile_sha256,
    )
    manifest_path = store._manifest_path_for_ref(ref.artifact_id, ref.manifest_profile_sha256)
    original_open_member = store.open_member
    open_attempts = 0

    def drift_manifest_before_open(
        artifact_id,
        member,
        *,
        max_manifest_bytes=None,
        expected_manifest_sha256=None,
        max_member_bytes=None,
    ):
        nonlocal open_attempts
        open_attempts += 1
        manifest_path.write_bytes(raw_manifest + b" ")
        return original_open_member(
            artifact_id,
            member,
            max_manifest_bytes=max_manifest_bytes,
            expected_manifest_sha256=expected_manifest_sha256,
            max_member_bytes=max_member_bytes,
        )

    monkeypatch.setattr(store, "open_member", drift_manifest_before_open)
    with pytest.raises(ArtifactMemberReadIntegrityError) as error:
        read_core_json_artifact_bounded(
            store,
            ref,
            limits=_limits(raw_payload, max_depth=1, max_elements=3),
        )

    assert error.value.code == "cas_member_manifest_changed"
    assert error.value.observed_manifest_verification_bytes == len(raw_manifest) + 1
    assert error.value.observed_payload_bytes == 0
    assert open_attempts == 1


def test_bounded_reader_counts_manifest_verification_preflight_without_payload_read(
    tmp_path,
    monkeypatch,
) -> None:
    store, ref, raw_payload = _profiled_store(tmp_path, {"value": 7})
    raw_manifest = store.get_raw_manifest_bytes(
        ref,
        manifest_profile_sha256=ref.manifest_profile_sha256,
    )
    max_manifest_bytes = len(raw_manifest) + 8
    manifest_path = store._manifest_path_for_ref(ref.artifact_id, ref.manifest_profile_sha256)
    original_open_member = store.open_member
    verification_manifest_size: list[int] = []

    def grow_manifest_before_owner_verification(
        artifact_id,
        member,
        *,
        max_manifest_bytes=None,
        expected_manifest_sha256=None,
        max_member_bytes=None,
    ):
        changed = raw_manifest + (b" " * (max_manifest_bytes + 1))
        manifest_path.write_bytes(changed)
        verification_manifest_size.append(len(changed))
        return original_open_member(
            artifact_id,
            member,
            max_manifest_bytes=max_manifest_bytes,
            expected_manifest_sha256=expected_manifest_sha256,
            max_member_bytes=max_member_bytes,
        )

    monkeypatch.setattr(store, "open_member", grow_manifest_before_owner_verification)
    with pytest.raises(CoreJsonReadBoundsRefusalError) as error:
        read_core_json_artifact_bounded(
            store,
            ref,
            limits=CoreJsonReadLimits(
                max_bytes=len(raw_payload),
                max_depth=8,
                max_elements=32,
                max_manifest_bytes=max_manifest_bytes,
            ),
        )

    refusal = error.value
    assert refusal.code == "canon_profile_bounded_manifest_bytes_exceeded"
    assert verification_manifest_size == [len(raw_manifest) + max_manifest_bytes + 1]
    assert refusal.observed_manifest_bytes == verification_manifest_size[0]
    assert refusal.observed_manifest_selection_bytes == len(raw_manifest)
    assert refusal.observed_manifest_verification_bytes == 0
    assert refusal.observed_payload_bytes == 0
    assert refusal.observed_payload_size is None
    assert refusal.payload_integrity_verified is False
    assert refusal.observed_source_bytes == len(raw_manifest)


def test_legacy_member_open_keeps_its_unbounded_default(tmp_path) -> None:
    store, ref, raw = _profiled_store(tmp_path, {"value": 7})

    with store.open_member(ref, "blob") as source:
        payload = b"".join(iter(lambda: source.read(64), b""))

    assert payload == raw


def test_bounded_reader_rejects_profile_bound_to_a_different_manifest_view(
    tmp_path, monkeypatch
) -> None:
    store = FileSystemCAS(tmp_path / "wrong-view-cas")
    spec = CanonSpec(forbid_floats=False, exclude_none=False)
    raw = to_canonical_bytes({"value": 7}, spec)
    first = store.put_bytes(
        raw,
        PutOptions(
            kind="test.core-json.view-a",
            media_type="application/json",
            canon=CanonInfo.from_spec(spec),
        ),
        return_selected_profile=True,
    )
    second = store.put_bytes(
        raw,
        PutOptions(
            kind="test.core-json.view-b",
            media_type="application/json",
            canon=CanonInfo.from_spec(spec),
        ),
        return_selected_profile=True,
    )
    assert first.artifact_id == second.artifact_id
    assert first.manifest_profile_sha256 != second.manifest_profile_sha256
    stream_calls = 0
    open_member = store.open_member

    def observed_open_member(*args, **kwargs):
        nonlocal stream_calls
        stream_calls += 1
        return open_member(*args, **kwargs)

    monkeypatch.setattr(store, "open_member", observed_open_member)
    wrong_ref = first.model_copy(update={"manifest_profile_sha256": second.manifest_profile_sha256})

    with pytest.raises((FileNotFoundError, CanonicalProfileRefusalError)):
        read_core_json_artifact_bounded(
            store,
            wrong_ref,
            limits=_limits(raw, max_depth=8, max_elements=32),
        )

    assert stream_calls == 0


def test_bounded_reader_rejects_malformed_selected_payload(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "malformed-cas")
    raw = b'{"value":'
    ref = store.put_bytes(
        raw,
        PutOptions(
            kind="test.core-json.bounded",
            media_type="application/json",
            canon=CanonInfo(),
        ),
        return_selected_profile=True,
    )

    with pytest.raises(CanonicalProfileRefusalError) as error:
        read_core_json_artifact_bounded(
            store,
            ref,
            limits=_limits(raw, max_depth=4, max_elements=16),
        )

    assert error.value.code == "canon_profile_payload_nonconformant"
