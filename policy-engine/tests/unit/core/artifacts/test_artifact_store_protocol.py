"""Tests for ArtifactStore protocol and FileSystemCAS conformance."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol
from unittest.mock import MagicMock

import pytest

from polisyos.core.artifacts import artifact_manifest_profile_sha256
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.ir_adapter import CoreToIRArtifactStoreAdapter
from polisyos.core.artifacts.manifest import ArtifactRef, artifact_ref_identity_key
from polisyos.core.artifacts.ownership import (
    ArtifactOwnershipError,
    ArtifactPublicReadClosureUnavailableError,
)
from polisyos.core.artifacts.protocol import ArtifactStore, matches_runtime_protocol
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.security.tenant_context import tenant_scope


class TestArtifactStoreProtocol:
    def test_core_artifacts_facade_exports_backend_factory(self):
        """The facade re-exports the canonical backend owner, not a duplicate."""
        from polisyos.core import artifacts
        from polisyos.core.artifacts.backends.config import (
            ArtifactStoreConfig,
            build_artifact_store,
        )

        assert artifacts.ArtifactStoreConfig is ArtifactStoreConfig
        assert artifacts.build_artifact_store is build_artifact_store
        assert {"ArtifactStoreConfig", "build_artifact_store"} <= set(artifacts.__all__)

    def test_filesystem_cas_satisfies_protocol(self, tmp_path: Path):
        """FileSystemCAS must be a structural match for ArtifactStore."""
        store = FileSystemCAS(tmp_path / "cas")
        assert isinstance(store, ArtifactStore)

    def test_protocol_is_runtime_checkable(self):
        """The protocol decorator allows isinstance checks."""
        mock = MagicMock(spec=ArtifactStore)
        assert isinstance(mock, ArtifactStore)

    def test_plain_object_does_not_satisfy(self):
        """An arbitrary object should not satisfy the protocol."""
        assert not isinstance(object(), ArtifactStore)

    def test_protocol_required_methods(self):
        """Verify the protocol declares exactly the expected methods."""
        expected = {
            "has",
            "get_bytes",
            "get_manifest",
            "put_bytes",
            "put_json",
            "verify",
            "iter_artifact_ids",
        }
        # Protocol members (exclude dunder / internal)
        members = {name for name in dir(ArtifactStore) if not name.startswith("_")}
        assert expected.issubset(members)


def test_runtime_protocol_matcher_uses_inherited_members_on_the_same_dynamic_handle() -> None:
    class ParentSurface(Protocol):
        root: Path

        @property
        def ready(self) -> bool: ...

        def read(self) -> bytes: ...

    class CompleteSurface(ParentSurface, Protocol):
        revision: int

        def write(self, data: bytes) -> None: ...

    class DynamicHandle:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def __getattr__(self, name: str):
            if name == "root":
                return Path("/guarded/root")
            if name == "ready":
                return True
            if name == "revision":
                return 3
            if name in {"read", "write"}:

                def call(*_args: object) -> object:
                    self.calls.append(name)
                    return b"payload" if name == "read" else None

                return call
            raise AttributeError(name)

    class MissingInheritedMember(DynamicHandle):
        def __getattr__(self, name: str):
            if name == "ready":
                raise AttributeError(name)
            return super().__getattr__(name)

    class NonCallableMethod(DynamicHandle):
        def __getattr__(self, name: str):
            if name == "write":
                return "present but not callable"
            return super().__getattr__(name)

    handle = DynamicHandle()
    assert matches_runtime_protocol(handle, CompleteSurface)
    handle.read()
    assert handle.calls == ["read"]
    assert not matches_runtime_protocol(MissingInheritedMember(), CompleteSurface)
    assert not matches_runtime_protocol(NonCallableMethod(), CompleteSurface)


class _NoopSpan:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def set_attribute(self, *_args):
        return None


class _NoopTracer:
    def start_as_current_span(self, *_args, **_kwargs):
        return _NoopSpan()


@pytest.mark.parametrize("instrumented", [False, True])
def test_put_bytes_can_return_the_exact_write_selected_profile(
    tmp_path: Path,
    instrumented: bool,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    if instrumented:
        store._hpc_enabled = True
        store._tracer = _NoopTracer()

    first_options = PutOptions(kind="test.profile.default", media_type="application/json")
    legacy = store.put_bytes(b"shared", first_options)
    assert legacy.manifest_profile_sha256 is None

    selected_options = PutOptions(kind="test.profile.sibling", media_type="text/plain")
    selected = store.put_bytes(b"shared", selected_options, return_selected_profile=True)
    selected_manifest = store.get_manifest(selected)
    assert selected.artifact_id == legacy.artifact_id
    assert selected.manifest_profile_sha256 == artifact_manifest_profile_sha256(selected_manifest)
    assert selected_manifest.kind == selected_options.kind
    assert store.get_manifest(legacy).kind == first_options.kind

    first_selected = store.put_bytes(
        b"new first-write blob",
        PutOptions(kind="test.profile.first", media_type="application/octet-stream"),
        return_selected_profile=True,
    )
    assert first_selected.manifest_profile_sha256 == artifact_manifest_profile_sha256(
        store.get_manifest(first_selected)
    )

    selected_json = store.put_json(
        {"value": "profile from json write"},
        PutOptions(kind="test.profile.json", media_type="application/json"),
        return_selected_profile=True,
    )
    assert selected_json.manifest_profile_sha256 == artifact_manifest_profile_sha256(
        store.get_manifest(selected_json)
    )

    before_ids = {str(artifact_id) for artifact_id in store.iter_artifact_ids()}
    with pytest.raises(TypeError, match="return_selected_profile must be a bool"):
        store.put_bytes(
            b"invalid option must not write",
            PutOptions(kind="test.profile.invalid", media_type="application/json"),
            return_selected_profile=1,  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError, match="return_selected_profile must be a bool"):
        store.put_json(
            {"value": "invalid option must not write"},
            PutOptions(kind="test.profile.invalid_json", media_type="application/json"),
            return_selected_profile=1,  # type: ignore[arg-type]
        )
    assert {str(artifact_id) for artifact_id in store.iter_artifact_ids()} == before_ids


def test_core_adapter_accepts_explicit_positional_or_keyword_profile_parameter() -> None:
    class PositionalOrKeywordStore:
        called = False

        def put_bytes(self, data, opts, return_selected_profile=False):
            self.called = True
            assert return_selected_profile is True
            return ArtifactRef(
                artifact_id=ArtifactID.from_sha256_hex("0" * 64),
                kind=opts.kind,
                media_type=opts.media_type,
                manifest_profile_sha256="sha256:" + "1" * 64,
            )

    store = PositionalOrKeywordStore()
    ref = CoreToIRArtifactStoreAdapter(store).put_bytes(
        b"selected",
        PutOptions(kind="test.profile.pos_or_kw", media_type="application/json"),
        return_selected_profile=True,
    )

    assert store.called is True
    assert ref.manifest_profile_sha256 == "sha256:" + "1" * 64


@pytest.mark.parametrize(
    "signature_kind",
    ["positional_only", "variadic_positional", "variadic_keyword"],
)
def test_core_adapter_refuses_non_keyword_profile_parameters_before_writer_call(
    signature_kind: str,
) -> None:
    class PositionalOnlyStore:
        called = False

        def put_bytes(self, data, opts, return_selected_profile=False, /):
            self.called = True

    class VariadicPositionalStore:
        called = False

        def put_bytes(self, data, opts, *return_selected_profile):
            self.called = True

    class VariadicKeywordStore:
        called = False

        def put_bytes(self, data, opts, **return_selected_profile):
            self.called = True

    store_type = {
        "positional_only": PositionalOnlyStore,
        "variadic_positional": VariadicPositionalStore,
        "variadic_keyword": VariadicKeywordStore,
    }[signature_kind]
    store = store_type()

    with pytest.raises(
        NotImplementedError,
        match="artifact_store_return_selected_profile_unsupported",
    ):
        CoreToIRArtifactStoreAdapter(store).put_bytes(
            b"must not reach writer",
            object(),  # type: ignore[arg-type]
            return_selected_profile=True,
        )

    assert store.called is False


class TestFileSystemCASRoundTrip:
    """Smoke test: put + get through the protocol interface."""

    def test_put_get_bytes(self, tmp_path: Path):
        store: ArtifactStore = FileSystemCAS(tmp_path / "cas")
        from polisyos.core.artifacts.store import PutOptions

        ref = store.put_bytes(b"hello world", PutOptions(kind="test", media_type="text/plain"))
        assert store.has(ref.artifact_id)
        assert store.get_bytes(ref.artifact_id) == b"hello world"

    def test_put_get_json(self, tmp_path: Path):
        store: ArtifactStore = FileSystemCAS(tmp_path / "cas")
        from polisyos.core.artifacts.store import PutOptions

        data = {"key": "value", "n": 42}
        ref = store.put_json(data, PutOptions(kind="test", media_type="application/json"))
        assert store.has(ref.artifact_id)
        manifest = store.get_manifest(ref.artifact_id)
        assert manifest.kind == "test"

    def test_verify(self, tmp_path: Path):
        store: ArtifactStore = FileSystemCAS(tmp_path / "cas")
        from polisyos.core.artifacts.store import PutOptions

        ref = store.put_bytes(b"data", PutOptions(kind="test", media_type="text/plain"))
        report = store.verify(ref.artifact_id)
        assert report.ok is True

    def test_iter_artifact_ids(self, tmp_path: Path):
        store: ArtifactStore = FileSystemCAS(tmp_path / "cas")

        ref = store.put_bytes(b"x", PutOptions(kind="test", media_type="text/plain"))
        ids = store.iter_artifact_ids()
        assert ids == [ref.artifact_id]

    def test_governed_public_read_closure_is_exact_and_does_not_override_tenant_owner(
        self, tmp_path: Path
    ) -> None:
        """A closure permits one captured full ref operation and preserves ordinary ACLs."""
        store = FileSystemCAS(
            tmp_path / "cas",
            ownership_enforced=True,
            ownership_requires_scope=False,
        )
        owner_token = store._register_governed_public_read_owner()
        raw = b"synthetic governed public member"
        with tenant_scope(None, tenant_id="tenant-a"):
            default_ref = store.put_bytes(
                raw,
                PutOptions(kind="test.public_member", media_type="application/json"),
            )
            selected_ref = store.put_bytes(
                raw,
                PutOptions(kind="test.public_member.selected", media_type="text/plain"),
            )
        assert selected_ref.artifact_id == default_ref.artifact_id
        assert selected_ref.manifest_profile_sha256 is not None

        record_id = "gpr_" + "p" * 32
        with tenant_scope(None, tenant_id="tenant-a"):
            with store._capture_public_read_set() as observed:
                assert store.get_bytes(default_ref) == raw
                assert store.get_manifest(default_ref).kind == "test.public_member"
            closure = store._record_governed_public_read_closure(
                record_id,
                observed,
                owner_token=owner_token,
            )
            assert closure["status"] == "active"
            assert closure["operation_refs"] == observed.serialized_operation_refs()
            assert (
                store._record_governed_public_read_closure(
                    record_id,
                    observed,
                    owner_token=owner_token,
                )
                == closure
            )

        with store._authorize_governed_public_read(
            record_id,
            owner_token=owner_token,
        ):
            assert store.get_bytes(default_ref) == raw
            with pytest.raises(ArtifactPublicReadClosureUnavailableError):
                store.get_bytes(selected_ref)
            assert store.get_manifest(default_ref).kind == "test.public_member"
            with pytest.raises(ArtifactPublicReadClosureUnavailableError):
                store.get_manifest_bytes(default_ref)

        with (
            store._authorize_governed_public_read(
                record_id,
                owner_token=owner_token,
            ),
            tenant_scope(None, tenant_id="tenant-b"),
            pytest.raises(ArtifactOwnershipError),
        ):
            store.get_bytes(default_ref)

        assert (
            store._revoke_governed_public_read_closure(
                record_id,
                owner_token=owner_token,
            )
            is True
        )
        with (
            pytest.raises(ArtifactPublicReadClosureUnavailableError),
            store._authorize_governed_public_read(
                record_id,
                owner_token=owner_token,
            ),
        ):
            store.get_bytes(default_ref)

        candidate = store.put_bytes(
            b"ordinary unclaimed candidate",
            PutOptions(kind="test.candidate", media_type="text/plain"),
        )
        assert store.get_bytes(candidate) == b"ordinary unclaimed candidate"

    def test_inventory_preserves_views_but_iter_returns_sorted_unique_blob_ids(
        self, tmp_path: Path
    ) -> None:
        store = FileSystemCAS(tmp_path / "cas")
        default_view = store.put_bytes(
            b"shared blob",
            PutOptions(kind="test.default", media_type="text/plain"),
        )
        selected_view = store.put_bytes(
            b"shared blob",
            PutOptions(kind="test.selected", media_type="application/octet-stream"),
        )
        other_blob = store.put_bytes(
            b"another blob",
            PutOptions(kind="test.other", media_type="text/plain"),
        )

        inventory = store.inventory_snapshot()

        assert inventory.verdict == "pass"
        assert len(inventory.entries) == 5
        default_entries = [
            entry for entry in inventory.entries if isinstance(entry.artifact_ref, ArtifactID)
        ]
        selected_entries = [
            entry for entry in inventory.entries if isinstance(entry.artifact_ref, ArtifactRef)
        ]
        assert len(default_entries) == 2
        assert len(selected_entries) == 3
        expected_default_members = {
            (str(default_view.artifact_id), "test.default"),
            (str(other_blob.artifact_id), "test.other"),
        }
        actual_default_members = {
            (str(entry.artifact_ref), entry.manifest.kind)
            for entry in default_entries
            if isinstance(entry.artifact_ref, ArtifactID)
        }
        assert actual_default_members == expected_default_members

        def selected_view_ref(ref: ArtifactRef) -> ArtifactRef:
            manifest = store.get_manifest(ref)
            return ArtifactRef(
                artifact_id=ref.artifact_id,
                kind=manifest.kind,
                media_type=manifest.media_type,
                manifest_profile_sha256=store._manifests.profile_sha256(manifest),
            )

        expected_views = {
            artifact_ref_identity_key(selected_view_ref(ref))
            for ref in (default_view, selected_view, other_blob)
        }
        actual_views = {
            artifact_ref_identity_key(entry.artifact_ref)
            for entry in selected_entries
            if isinstance(entry.artifact_ref, ArtifactRef)
        }
        assert len(actual_views) == len(selected_entries)
        assert actual_views == expected_views
        assert default_view.artifact_id == selected_view.artifact_id

        ids = store.iter_artifact_ids()

        expected = sorted(
            (default_view.artifact_id, other_blob.artifact_id),
            key=lambda artifact_id: artifact_id.hex,
        )
        assert ids == expected
        assert len({str(artifact_id) for artifact_id in ids}) == 2
        assert store.iter_artifact_ids() == expected

    def test_inventory_snapshot_scopes_view_verification_to_selected_artifact_id(
        self, tmp_path: Path
    ) -> None:
        store = FileSystemCAS(tmp_path / "cas")
        default_view = store.put_bytes(
            b"same selected inventory blob",
            PutOptions(kind="inventory.default", media_type="text/plain"),
        )
        selected_view = store.put_bytes(
            b"same selected inventory blob",
            PutOptions(kind="inventory.selected", media_type="application/octet-stream"),
        )
        other_blob = store.put_bytes(
            b"excluded inventory blob",
            PutOptions(kind="inventory.other", media_type="text/plain"),
        )

        snapshot = store.inventory_snapshot(artifact_id=selected_view.artifact_id)

        assert snapshot.verdict == "pass"
        assert selected_view.artifact_id == default_view.artifact_id
        assert len(snapshot.entries) == 3
        entry_ids = {
            str(entry.artifact_ref.artifact_id)
            if isinstance(entry.artifact_ref, ArtifactRef)
            else str(entry.artifact_ref)
            for entry in snapshot.entries
        }
        assert entry_ids == {str(selected_view.artifact_id)}
        assert str(other_blob.artifact_id) not in entry_ids
        default_entries = [
            entry for entry in snapshot.entries if isinstance(entry.artifact_ref, ArtifactID)
        ]
        profile_entries = [
            entry for entry in snapshot.entries if isinstance(entry.artifact_ref, ArtifactRef)
        ]
        assert len(default_entries) == 1
        assert default_entries[0].manifest.kind == "inventory.default"
        assert len(profile_entries) == 2
        expected_profiles = {
            store._manifests.profile_sha256(store.get_manifest(ref))
            for ref in (default_view, selected_view)
        }
        assert {entry.artifact_ref.manifest_profile_sha256 for entry in profile_entries} == (
            expected_profiles
        )
        assert "canonical CAS root member names" in snapshot.inputs
        assert any(str(selected_view.artifact_id) in item for item in snapshot.inputs)

    def test_inventory_snapshot_hides_foreign_tenant_members_without_losing_owned_views(
        self, tmp_path: Path
    ) -> None:
        store = FileSystemCAS(
            tmp_path / "cas",
            ownership_enforced=True,
            ownership_requires_scope=False,
        )
        with tenant_scope(None, tenant_id="tenant-b"):
            foreign_first = store.put_bytes(
                b"foreign payload",
                PutOptions(kind="inventory.foreign", media_type="text/plain"),
            )
            foreign_same_blob = store.put_bytes(
                b"tenant-owned payload",
                PutOptions(kind="inventory.foreign.same_blob", media_type="text/plain"),
            )
            foreign_same_profile = store._manifests.profile_sha256(
                store.get_manifest(foreign_same_blob)
            )
        with tenant_scope(None, tenant_id="tenant-a"):
            owner_default = store.put_bytes(
                b"tenant-owned payload",
                PutOptions(kind="inventory.owner.default", media_type="text/plain"),
            )
            owner_default_profile = store._manifests.profile_sha256(
                store.get_manifest(owner_default)
            )
            owner_selected = store.put_bytes(
                b"tenant-owned payload",
                PutOptions(kind="inventory.owner.selected", media_type="application/octet-stream"),
            )
            owner_selected_profile = store._manifests.profile_sha256(
                store.get_manifest(owner_selected)
            )

        assert foreign_first.artifact_id.hex < owner_default.artifact_id.hex
        assert foreign_same_blob.artifact_id == owner_default.artifact_id
        assert owner_default.artifact_id == owner_selected.artifact_id

        tenant_store = store.for_tenant("tenant-a")
        with tenant_scope(None, tenant_id="tenant-a"):
            snapshot = tenant_store.inventory_snapshot()

        assert snapshot.verdict == "pass"
        assert snapshot.owner_generation_sha256 is not None
        assert "other tenant views hidden by the active tenant scope" in (
            snapshot.unresolved_by_construction
        )
        entry_ids = {
            str(entry.artifact_ref.artifact_id)
            if isinstance(entry.artifact_ref, ArtifactRef)
            else str(entry.artifact_ref)
            for entry in snapshot.entries
        }
        assert entry_ids == {str(owner_default.artifact_id)}
        assert str(foreign_first.artifact_id) not in entry_ids
        default_entries = [
            entry for entry in snapshot.entries if isinstance(entry.artifact_ref, ArtifactID)
        ]
        profile_entries = [
            entry for entry in snapshot.entries if isinstance(entry.artifact_ref, ArtifactRef)
        ]
        assert default_entries == []
        assert len(profile_entries) == 2
        observed_profiles = {
            entry.artifact_ref.manifest_profile_sha256 for entry in profile_entries
        }
        assert observed_profiles == {owner_default_profile, owner_selected_profile}
        assert foreign_same_profile not in observed_profiles
