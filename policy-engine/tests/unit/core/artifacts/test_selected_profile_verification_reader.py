"""The strict replay reader preserves selected-owner read failures."""

from pathlib import Path

import pytest

from polisyos.core.artifacts import (
    ArtifactOwnershipError,
    ArtifactReadOnlyUnavailableError,
    CanonInfo,
    FileSystemCAS,
    PutOptions,
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
    from polisyos.core.artifacts import SchemaInfo

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
