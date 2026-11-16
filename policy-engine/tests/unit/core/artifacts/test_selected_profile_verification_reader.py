"""The strict replay reader preserves selected-owner read failures."""

import json
from pathlib import Path

import pytest

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts import (
    ArtifactIntegrityError,
    ArtifactManifest,
    ArtifactOwnershipError,
    ArtifactReadOnlyUnavailableError,
    CanonInfo,
    FileSystemCAS,
    PutOptions,
    SchemaInfo,
    SelectedProfileVerificationReader,
    raise_artifact_read_access_error,
)
from polisyos.core.canon import CanonSpec
from polisyos.core.security.tenant_context import tenant_scope


def test_selected_reader_reopens_owner_and_content_without_using_false_as_access_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FileSystemCAS(tmp_path / "cas").with_ambient_ownership_enforcement()
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        ref = store.put_json(
            {"witness": "selected"},
            PutOptions(
                kind="test.selected",
                media_type="application/json",
                canon=CanonInfo.from_spec(CanonSpec()),
            ),
            canon_spec=CanonSpec(),
            return_selected_profile=True,
        )
        selected = SelectedProfileVerificationReader(store)
        assert selected.verify(ref).ok
        original = store.get_bytes

        def deny_after_manifest(_ref: object) -> bytes:
            raise ArtifactOwnershipError("changed owner during selected read")

        with monkeypatch.context() as fault:
            fault.setattr(store, "get_bytes", deny_after_manifest)
            with pytest.raises(ArtifactOwnershipError):
                selected.verify(ref)
        with monkeypatch.context() as fault:
            fault.setattr(store, "get_bytes", lambda _ref: b"wrong bytes")
            assert selected.verify(ref).ok is False

        def wrapped_cause(cause: Exception):
            def fail(_ref: object) -> bytes:
                raise RuntimeError("selected backend wrapper") from cause

            return fail

        denial = ArtifactOwnershipError("selected owner denied")
        with monkeypatch.context() as fault:
            fault.setattr(store, "get_bytes", wrapped_cause(denial))
            with pytest.raises(ArtifactOwnershipError) as captured:
                selected.verify(ref)
            assert captured.value is denial
        temporarily_unavailable = ArtifactReadOnlyUnavailableError("unavailable")
        with monkeypatch.context() as fault:
            fault.setattr(store, "get_bytes", wrapped_cause(temporarily_unavailable))
            with pytest.raises(RuntimeError) as captured_unavailable:
                selected.verify(ref)
            assert captured_unavailable.value.__cause__ is temporarily_unavailable
        disk_permission = PermissionError("filesystem permission")
        with monkeypatch.context() as fault:
            fault.setattr(store, "get_bytes", wrapped_cause(disk_permission))
            with pytest.raises(PermissionError) as captured_disk:
                selected.verify(ref)
            assert type(captured_disk.value) is PermissionError
            assert captured_disk.value is disk_permission
        assert store.get_bytes(ref) == original(ref)

    with tenant_scope(None, tenant_id="tenant-b", cell_id="cell-b"):
        with pytest.raises(ArtifactOwnershipError):
            selected.verify(ref)


def test_access_error_preserves_only_explicit_cause_and_typed_unavailability() -> None:
    denial = ArtifactOwnershipError("tenant denied")
    try:
        raise ValueError("owner wrapper") from denial
    except ValueError as wrapped:
        with pytest.raises(ArtifactOwnershipError) as seen:
            raise_artifact_read_access_error(wrapped)
    assert seen.value is denial
    unavailable = ArtifactReadOnlyUnavailableError("temporarily unavailable")
    raise_artifact_read_access_error(unavailable)
    nested_owner = ArtifactOwnershipError("nested owner denial")
    unavailable.__cause__ = nested_owner
    with pytest.raises(ArtifactOwnershipError) as nested:
        raise_artifact_read_access_error(unavailable)
    assert nested.value is nested_owner
    nested_permission = PermissionError("nested filesystem permission")
    unavailable.__cause__ = nested_permission
    with pytest.raises(PermissionError) as nested_disk:
        raise_artifact_read_access_error(unavailable)
    assert nested_disk.value is nested_permission
    assert type(nested_disk.value) is PermissionError
    filesystem_error = PermissionError("filesystem refused")
    with pytest.raises(PermissionError) as seen_permission:
        raise_artifact_read_access_error(filesystem_error)
    assert type(seen_permission.value) is PermissionError


def test_unqualified_replay_pins_initial_manifest_before_body_read(tmp_path: Path) -> None:
    """A same-body default-view switch cannot replace the selected metadata."""
    store = FileSystemCAS(tmp_path / "switching-cas").with_ambient_ownership_enforcement()
    spec = CanonSpec()
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        first = store.put_json(
            {"witness": "same payload"},
            PutOptions(
                kind="test.selected",
                media_type="application/json",
                schema=SchemaInfo(name="test.selected", version="1.0"),
                canon=CanonInfo.from_spec(spec),
            ),
            canon_spec=spec,
            return_selected_profile=True,
        )
        second = store.put_json(
            {"witness": "same payload"},
            PutOptions(
                kind="test.selected",
                media_type="application/json",
                schema=SchemaInfo(name="test.selected", version="2.0"),
                canon=CanonInfo.from_spec(spec),
            ),
            canon_spec=spec,
            return_selected_profile=True,
        )
        assert first.artifact_id == second.artifact_id
        assert first.manifest_profile_sha256 != second.manifest_profile_sha256
        unqualified = first.model_copy(update={"manifest_profile_sha256": None})

        class SwitchingOwner:
            switched = False

            def __init__(self) -> None:
                self.body_selectors: list[object] = []

            def choose(self, selector: object) -> object:
                if getattr(selector, "manifest_profile_sha256", None) is None:
                    return second if self.switched else first
                return selector

            def get_raw_manifest_bytes(self, selector: object) -> bytes:
                return store.get_raw_manifest_bytes(self.choose(selector))  # type: ignore[arg-type]

            def get_manifest(self, selector: object) -> object:
                return store.get_manifest(self.choose(selector))  # type: ignore[arg-type]

            def get_bytes(self, selector: object) -> bytes:
                self.body_selectors.append(selector)
                self.switched = True
                return store.get_bytes(self.choose(selector))  # type: ignore[arg-type]

        switching = SwitchingOwner()
        report = SelectedProfileVerificationReader(switching).verify(unqualified)
        assert report.ok
        assert switching.switched
        assert switching.body_selectors == [first]
        assert switching.get_manifest(unqualified) == store.get_manifest(second)


@pytest.mark.parametrize("media_type", ["text/plain", "application/x-npz"])
def test_selected_raw_media_rechecks_exact_view_and_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, media_type: str
) -> None:
    """The selected raw proof requires both the original view and intact bytes."""
    store = FileSystemCAS(tmp_path / "raw-cas").with_ambient_ownership_enforcement()
    selected = SelectedProfileVerificationReader(store)
    data = b"actual bytes of the selected raw evidence"
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        ref = store.put_bytes(
            data,
            PutOptions(kind="test.raw_evidence", media_type=media_type),
            return_selected_profile=True,
        )
        alternate = store.put_bytes(
            data,
            PutOptions(
                kind=ref.kind,
                media_type=media_type,
                schema=SchemaInfo(name=ref.kind, version="1.0"),
            ),
            return_selected_profile=True,
        )
        assert ref.artifact_id == alternate.artifact_id
        assert ref.manifest_profile_sha256 != alternate.manifest_profile_sha256
        assert store.get_manifest(ref).canon is None
        assert selected.verify(ref).ok
        with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_absent"):
            selected.verify(ref.model_copy(update={"manifest_profile_sha256": None}))
        alternate_manifest = store.get_manifest(alternate)

        def wrong_manifest(selector: object) -> ArtifactManifest:
            assert selector == ref
            return alternate_manifest

        with monkeypatch.context() as fault:
            fault.setattr(store, "get_manifest", wrong_manifest)
            with pytest.raises(
                CanonicalProfileRefusalError, match="canon_profile_selected_manifest_changed"
            ):
                selected.verify(ref)
        with monkeypatch.context() as fault:
            fault.setattr(store, "get_bytes", lambda _selector: b"same-shaped different bytes")
            assert not selected.verify(ref).ok
    with tenant_scope(None, tenant_id="tenant-b", cell_id="cell-b"):
        with pytest.raises(ArtifactOwnershipError):
            selected.verify(ref)


def test_selected_raw_json_without_declared_codec_rechecks_exact_view_and_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A selected raw JSON storage view gets byte checks without a codec claim."""
    store = FileSystemCAS(tmp_path / "raw-json-cas").with_ambient_ownership_enforcement()
    selected = SelectedProfileVerificationReader(store)
    data = b'{"evidence":"selected raw JSON"}'
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        ref = store.put_bytes(
            data,
            PutOptions(kind="test.raw_json", media_type="application/json"),
            return_selected_profile=True,
        )
        manifest = store.get_manifest(ref)
        assert manifest.artifact_schema is None
        assert manifest.canon is None
        report = selected.verify(ref)
        assert report.ok
        assert report.byte_size == len(data)

        wrong_profile = ref.model_copy(update={"manifest_profile_sha256": "sha256:" + "0" * 64})
        with pytest.raises(ArtifactOwnershipError):
            selected.verify(wrong_profile)
        with pytest.raises(
            ArtifactIntegrityError,
            match="Artifact reference type does not match selected manifest",
        ):
            selected.verify(ref.model_copy(update={"kind": "test.other_raw_json"}))
        with pytest.raises(
            ArtifactIntegrityError,
            match="Artifact reference type does not match selected manifest",
        ):
            selected.verify(ref.model_copy(update={"media_type": "application/octet-stream"}))

        with monkeypatch.context() as fault:
            fault.setattr(store, "get_bytes", lambda _selector: b'{"evidence":"changed"}')
            corrupt_report = selected.verify(ref)
            assert not corrupt_report.ok
            assert corrupt_report.error == "sha256 mismatch"

    with tenant_scope(None, tenant_id="tenant-b", cell_id="cell-b"):
        with pytest.raises(ArtifactOwnershipError):
            selected.verify(ref)


@pytest.mark.parametrize(("field", "value"), [("kind", ""), ("media_type", "application")])
def test_selected_raw_json_malformed_reference_does_not_opt_in_to_absent_profile(
    tmp_path: Path, field: str, value: str
) -> None:
    """Malformed selected metadata cannot enable the absent-profile path."""
    store = FileSystemCAS(tmp_path / "malformed-ref-cas")
    ref = store.put_bytes(
        b'{"evidence":"selected raw JSON"}',
        PutOptions(kind="test.raw_json", media_type="application/json"),
        return_selected_profile=True,
    )
    malformed_ref = ref.model_copy(update={field: value})

    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_absent"):
        SelectedProfileVerificationReader(store).verify(malformed_ref)


@pytest.mark.parametrize("media_type", ["text/plain", "application/x-npz"])
def test_selected_non_json_schema_view_still_verifies_without_canonical_profile(
    tmp_path: Path, media_type: str
) -> None:
    """A binary schema does not require the separate Core JSON canonical codec."""
    store = FileSystemCAS(tmp_path / "binary-schema-cas")
    data = b"selected binary payload"
    ref = store.put_bytes(
        data,
        PutOptions(
            kind="test.typed_binary",
            media_type=media_type,
            schema=SchemaInfo(name="test.typed_binary", version="1.0"),
        ),
        return_selected_profile=True,
    )
    manifest = store.get_manifest(ref)
    assert manifest.artifact_schema is not None
    assert manifest.canon is None

    report = SelectedProfileVerificationReader(store).verify(ref)

    assert report.ok
    assert report.byte_size == len(data)


@pytest.mark.parametrize(
    "media_type", ["application/json", "Application/JSON; charset=utf-8", "application/test+JSON"]
)
def test_typed_json_without_canonical_profile_still_refuses(
    tmp_path: Path,
    media_type: str,
) -> None:
    """A typed JSON schema cannot pass as raw storage when its codec is absent."""
    store = FileSystemCAS(tmp_path / "json-cas")
    ref = store.put_bytes(
        b'{"evidence":"raw transport"}',
        PutOptions(
            kind="test.typed_json",
            media_type=media_type,
            schema=SchemaInfo(name="test.typed_json", version="1.0"),
        ),
        return_selected_profile=True,
    )
    manifest = store.get_manifest(ref)
    assert manifest.artifact_schema is not None
    assert manifest.canon is None
    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_absent"):
        SelectedProfileVerificationReader(store).verify(ref)


def test_typed_json_malformed_canonical_profile_still_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An explicit malformed codec never becomes eligible for raw fallback."""
    store = FileSystemCAS(tmp_path / "invalid-json-cas")
    ref = store.put_bytes(
        b'{"evidence":"typed transport"}',
        PutOptions(
            kind="test.typed_json",
            media_type="application/json",
            schema=SchemaInfo(name="test.typed_json", version="1.0"),
        ),
        return_selected_profile=True,
    )
    raw_manifest = json.loads(store.get_raw_manifest_bytes(ref))
    raw_manifest["canon"] = None
    malformed_manifest = json.dumps(raw_manifest).encode()

    with monkeypatch.context() as fault:
        fault.setattr(
            store,
            "get_raw_manifest_bytes",
            lambda _selector, **_kwargs: malformed_manifest,
        )
        with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_invalid"):
            SelectedProfileVerificationReader(store).verify(ref)
