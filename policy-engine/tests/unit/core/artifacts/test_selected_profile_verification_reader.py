"""The strict replay reader preserves selected-owner read failures."""

from pathlib import Path

import pytest

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts import (
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


@pytest.mark.parametrize(
    "media_type", ["application/json", "Application/JSON; charset=utf-8", "application/test+JSON"]
)
def test_exact_json_view_still_requires_a_canonical_profile(
    tmp_path: Path, media_type: str
) -> None:
    """A selected JSON view alone supplies no canonical declaration."""
    store = FileSystemCAS(tmp_path / "json-cas")
    ref = store.put_bytes(
        b'{"evidence":"raw transport"}',
        PutOptions(kind="test.raw_json", media_type=media_type),
        return_selected_profile=True,
    )
    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_absent"):
        SelectedProfileVerificationReader(store).verify(ref)
