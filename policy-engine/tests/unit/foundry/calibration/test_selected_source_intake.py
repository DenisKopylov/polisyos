"""Actual Core selected-byte availability and contradiction classification."""

from __future__ import annotations

from typing import Literal

import pytest
from pydantic import BaseModel, ConfigDict

from polisyos.core.artifacts import FileSystemCAS, InputRef, PutOptions, SchemaInfo
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.foundry.calibration import read_calibration_model_source, read_calibration_source


class _SourceValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    value: int
    coordinates: tuple[int, ...] = (1, 2)


class _DeniedBytesCAS(FileSystemCAS):
    def get_bytes(self, selector):
        raise PermissionError("test owner does not grant access to selected bytes")


class _DefaultOnlyReader:
    """Expose the real owner without its optional non-default selector capability."""

    get_manifest_by_profile = None

    def __init__(self, owner):
        self.owner = owner

    def __getattr__(self, name):
        return getattr(self.owner, name)


class _MissingCapabilityReader:
    def __init__(self, owner, absent):
        self.owner, self.absent = owner, absent

    def __getattr__(self, name):
        return None if name == self.absent else getattr(self.owner, name)


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("selected", "matched"),
        ("absent_ref", "not_established"),
        ("absent_edge", "not_established"),
        ("profileless_ref", "not_established"),
        ("profileless_edge", "not_established"),
        ("missing_view", "not_established"),
        ("missing_blob", "not_established"),
        ("denied_bytes", "not_established"),
        ("unavailable_view_reader", "not_established"),
        ("canonical_profile_absent", "not_established"),
        ("missing_capability:get_bytes", "not_established"),
        ("missing_capability:get_manifest", "not_established"),
        ("missing_capability:get_raw_manifest_bytes", "not_established"),
        ("duplicate_edges", "mismatch"),
        ("conflicting_edge", "mismatch"),
        ("reference_kind", "mismatch"),
        ("manifest_kind", "mismatch"),
        ("manifest_schema", "mismatch"),
        ("manifest_version", "mismatch"),
        ("malformed_present", "mismatch"),
        ("numeric_string", "mismatch"),
        ("corrupt_blob", "mismatch"),
    ],
)
def test_shared_selected_source_intake_uses_actual_core_bytes(tmp_path, case, expected):
    """A readable default is not a selector; known contradictory bytes are not absent."""
    root = tmp_path / "fresh_source_case"
    store = FileSystemCAS(root)
    options = PutOptions(
        kind="tests.calibration_source",
        media_type="application/json",
        schema=SchemaInfo(name="tests.CalibrationSource", version="1.0"),
    )
    payload = {"schema_version": "1.0", "value": 7, "coordinates": [1, 2]}
    selected = store.put_json(payload, options, return_selected_profile=True)
    assert selected.manifest_profile_sha256 is not None
    assert FileSystemCAS(root).get_bytes(selected) == to_canonical_bytes(payload)
    assert FileSystemCAS(root).verify(selected).ok
    ref, inputs, reader = selected, None, FileSystemCAS(root)
    if case == "absent_ref":
        ref = None
    elif case == "absent_edge":
        inputs = []
    elif case == "profileless_ref":
        ref = selected.model_copy(update={"manifest_profile_sha256": None})
        assert reader.get_bytes(ref) == reader.get_bytes(selected)
    elif case == "profileless_edge":
        inputs = [InputRef(role="source", artifact_id=selected.artifact_id)]
        assert reader.get_manifest(selected).artifact_id == selected.artifact_id
    elif case == "missing_view":
        ref = selected.model_copy(update={"manifest_profile_sha256": "sha256:" + "f" * 64})
        assert not reader.has_manifest_view(ref.artifact_id, ref.manifest_profile_sha256)
        assert reader.get_bytes(selected)
    elif case in {"missing_blob", "corrupt_blob"}:
        # Damage only this fresh disposable test CAS. The real selected sidecar
        # remains present, so this distinguishes missing payload from bad bytes.
        blob, _ = store._paths(selected.artifact_id)
        assert store.has_manifest_view(selected.artifact_id, selected.manifest_profile_sha256)
        if case == "missing_blob":
            blob.unlink()
            assert store._layout.view_manifest_path(
                selected.artifact_id, selected.manifest_profile_sha256
            ).is_file()
            with pytest.raises(FileNotFoundError):
                FileSystemCAS(root).get_bytes(selected)
        else:
            blob.write_bytes(b"!" * len(blob.read_bytes()))
            assert not FileSystemCAS(root).verify(selected).ok
    elif case == "denied_bytes":
        reader = _DeniedBytesCAS(root)
    elif case == "unavailable_view_reader":
        # Same bytes and known schema, but another real selected manifest view.
        alternate = store.put_json(
            payload,
            PutOptions(
                kind=options.kind,
                media_type=options.media_type,
                schema=options.schema,
                inputs=[InputRef(role="retained_parent", artifact_id=selected.artifact_id)],
            ),
            return_selected_profile=True,
        )
        assert alternate.artifact_id == selected.artifact_id
        assert alternate.manifest_profile_sha256 != selected.manifest_profile_sha256
        ref, reader = alternate, _DefaultOnlyReader(FileSystemCAS(root))
    elif case.startswith("missing_capability:"):
        reader = _MissingCapabilityReader(FileSystemCAS(root), case.partition(":")[2])
    elif case == "canonical_profile_absent":
        ref = store.put_bytes(
            to_canonical_bytes({"schema_version": "1.0", "value": 8}),
            options,
            return_selected_profile=True,
        )
        assert store.get_manifest(ref).canon is None
    elif case == "duplicate_edges":
        edge = InputRef(
            role="source",
            artifact_id=selected.artifact_id,
            manifest_profile_sha256=selected.manifest_profile_sha256,
        )
        inputs = [edge, edge]
    elif case == "conflicting_edge":
        other = store.put_json(
            {"schema_version": "1.0", "value": 9}, options, return_selected_profile=True
        )
        inputs = [
            InputRef(
                role="source",
                artifact_id=other.artifact_id,
                manifest_profile_sha256=other.manifest_profile_sha256,
            )
        ]
    elif case == "reference_kind":
        ref = selected.model_copy(update={"kind": "tests.foreign"})
    elif case in {
        "manifest_kind",
        "manifest_schema",
        "manifest_version",
        "malformed_present",
        "numeric_string",
    }:
        ref = store.put_json(
            {**payload, "value": "contradictory" if case == "malformed_present" else "7"}
            if case in {"malformed_present", "numeric_string"}
            else payload,
            PutOptions(
                kind="tests.foreign" if case == "manifest_kind" else options.kind,
                media_type=options.media_type,
                schema=SchemaInfo(
                    name="tests.Foreign" if case == "manifest_schema" else options.schema.name,
                    version="9.9" if case == "manifest_version" else "1.0",
                ),
            ),
            canon_spec=CanonSpec(),
            return_selected_profile=True,
        )
    result = read_calibration_model_source(
        reader,
        role="source",
        ref=ref,
        inputs=inputs,
        expected_kind=options.kind,
        expected_schema=options.schema.name,
        expected_versions=("1.0",),
        model=_SourceValue,
        decoder=lambda _ref, _manifest, value: value,
    )
    assert result.status == expected, (case, result)
    if expected == "matched":
        assert result.require_value().value == 7
        assert result.require_value().coordinates == (1, 2)
        assert result.ref == selected
    else:
        assert result.value is None
        with pytest.raises((ValueError, FileNotFoundError, PermissionError)):
            result.require_value()


def test_raw_selected_intake_cannot_emit_a_coerced_domain_model(tmp_path):
    store = FileSystemCAS(tmp_path)
    selected = store.put_json(
        {"schema_version": "1.0", "value": "7", "coordinates": [1, 2]},
        PutOptions(
            kind="tests.calibration_source",
            media_type="application/json",
            schema=SchemaInfo(name="tests.CalibrationSource", version="1.0"),
        ),
        return_selected_profile=True,
    )
    raw = read_calibration_source(
        FileSystemCAS(tmp_path),
        role="source",
        ref=selected,
        decoder=lambda _ref, _manifest, value: value,
    )
    typed = read_calibration_model_source(
        FileSystemCAS(tmp_path),
        role="source",
        ref=selected,
        model=_SourceValue,
        decoder=lambda _ref, _manifest, value: value,
    )
    coerced = read_calibration_source(
        FileSystemCAS(tmp_path),
        role="source",
        ref=selected,
        decoder=lambda _ref, _manifest, value: _SourceValue.model_validate(value),
    )
    assert raw.status == "matched"  # Canonical bytes only, no model admission.
    assert isinstance(raw.require_value()["value"], str)
    assert typed.status == "mismatch"
    assert coerced.status == "mismatch"
    assert coerced.value is None
    with pytest.raises(TypeError, match="requires_a_model_owner"):
        read_calibration_model_source(
            store,
            role="source",
            ref=selected,
            model=None,
            decoder=lambda _ref, _manifest, value: value,
        )


def test_raw_intake_reuses_core_native_values_and_binds_the_selected_payload(tmp_path):
    from datetime import date
    from decimal import Decimal

    payload = {"as_of": date(2026, 10, 28), "amount": Decimal("1.25"), "raw": b"native"}
    store = FileSystemCAS(tmp_path)
    selected = store.put_json(
        payload,
        PutOptions(kind="tests.native_source", media_type="application/json"),
        return_selected_profile=True,
    )
    positive = read_calibration_source(
        FileSystemCAS(tmp_path),
        role="source",
        ref=selected,
        decoder=lambda _ref, _manifest, value: value,
    )
    changed = read_calibration_source(
        FileSystemCAS(tmp_path),
        role="source",
        ref=selected,
        decoder=lambda _ref, _manifest, value: {**value, "amount": Decimal("2.50")},
    )
    nested = read_calibration_source(
        FileSystemCAS(tmp_path),
        role="source",
        ref=selected,
        decoder=lambda _ref, _manifest, value: {**value, "amount": _SourceValue(value=7)},
    )
    assert positive.status == "matched"
    assert positive.require_value() == payload
    assert changed.status == nested.status == "mismatch"
    assert changed.value is nested.value is None
