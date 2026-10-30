"""Tests for ArtifactStore protocol and FileSystemCAS conformance."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol
from unittest.mock import MagicMock

import pytest

from polisyos.core.artifacts import (
    ArtifactIntegrityError,
    ArtifactReadOnlyUnavailableError,
    artifact_manifest_profile_sha256,
    ensure_ir_artifact_store,
)
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.ir_adapter import CoreToIRArtifactStoreAdapter
from polisyos.core.artifacts.manifest import ArtifactRef, artifact_ref_identity_key
from polisyos.core.artifacts.ownership import (
    ArtifactOwnershipError,
    ArtifactPublicReadClosureUnavailableError,
    ArtifactTransactionPendingError,
)
from polisyos.core.artifacts.protocol import (
    ArtifactReader,
    ArtifactStore,
    CoreJSONArtifactStore,
    RootedArtifactStore,
    matches_runtime_protocol,
    matches_runtime_protocol_definition,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.security.tenant_context import tenant_scope

if TYPE_CHECKING:

    class NeverRuntimeProtocolAnnotation: ...


class _RootedCoreJSONArtifactStore(RootedArtifactStore, CoreJSONArtifactStore, Protocol):
    """Composite structural surface used by protected selected-profile readers."""


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

    def test_core_artifacts_facade_reexports_exact_intake_owners(self) -> None:
        from polisyos.core import artifacts
        from polisyos.core.artifacts import canonical_profile, ir_adapter, manifest, protocol
        from polisyos.core.artifacts.backends import config

        assert artifacts.require_return_selected_profile_writer is (
            protocol._require_return_selected_profile_writer
        )
        assert artifacts.require_return_selected_profile_writer is (
            protocol.require_return_selected_profile_writer
        )
        assert artifacts.validate_return_selected_profile is (
            protocol._validate_return_selected_profile
        )
        assert (
            artifacts.validate_return_selected_profile is protocol.validate_return_selected_profile
        )
        assert artifacts.matches_runtime_protocol is protocol.matches_runtime_protocol
        assert artifacts.matches_runtime_protocol_definition is (
            protocol.matches_runtime_protocol_definition
        )
        assert artifacts.CoreToIRArtifactStoreAdapter is ir_adapter.CoreToIRArtifactStoreAdapter
        assert (
            artifacts.matches_artifact_store_protocol is ir_adapter.matches_artifact_store_protocol
        )
        assert artifacts.decode_core_json_payload is canonical_profile.decode_core_json_payload
        assert artifacts.artifact_reference_parts is manifest.artifact_reference_parts
        assert (
            artifacts.with_ambient_ownership_enforcement_if_supported
            is config.with_ambient_ownership_enforcement_if_supported
        )
        assert {
            "require_return_selected_profile_writer",
            "validate_return_selected_profile",
            "matches_runtime_protocol",
            "matches_runtime_protocol_definition",
            "matches_artifact_store_protocol",
            "CoreToIRArtifactStoreAdapter",
            "decode_core_json_payload",
            "artifact_reference_parts",
            "with_ambient_ownership_enforcement_if_supported",
        } <= set(artifacts.__all__)
        assert artifacts.validate_return_selected_profile(False) is False
        with pytest.raises(TypeError, match="return_selected_profile must be a bool"):
            artifacts.validate_return_selected_profile(1)  # type: ignore[arg-type]

    def test_core_artifacts_facade_exports_read_only_surface(self) -> None:
        from polisyos.core import artifacts
        from polisyos.core.artifacts.ownership import ArtifactReadOnlyUnavailableError
        from polisyos.core.artifacts.protocol import ArtifactReader
        from polisyos.core.artifacts.store import ReadOnlyFileSystemCAS

        assert artifacts.ArtifactReadOnlyUnavailableError is ArtifactReadOnlyUnavailableError
        assert artifacts.ArtifactReader is ArtifactReader
        from polisyos.core.artifacts.protocol import VerifiableArtifactReader

        assert artifacts.VerifiableArtifactReader is VerifiableArtifactReader
        assert "VerifiableArtifactReader" in artifacts.__all__
        assert artifacts.ReadOnlyFileSystemCAS is ReadOnlyFileSystemCAS
        assert {
            "ArtifactReadOnlyUnavailableError",
            "ArtifactReader",
            "ReadOnlyFileSystemCAS",
        } <= set(artifacts.__all__)
        assert callable(artifacts.FileSystemCAS.open_existing_read_only)

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

    class ConcreteSurface(CompleteSurface):
        root = Path("/concrete/root")
        revision = 1

        @property
        def ready(self) -> bool:
            return True

        def read(self) -> bytes:
            return b"payload"

        def write(self, data: bytes) -> None:
            return None

    class MarkerSpoof:
        _is_protocol = True

        def read(self) -> bytes:
            return b"payload"

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
    assert matches_runtime_protocol_definition(handle, CompleteSurface)
    assert not matches_runtime_protocol_definition(MarkerSpoof(), MarkerSpoof)
    assert not matches_runtime_protocol(MarkerSpoof(), MarkerSpoof)
    assert not matches_runtime_protocol_definition(ConcreteSurface(), ConcreteSurface)
    assert not matches_runtime_protocol_definition(handle, ConcreteSurface)
    handle.read()
    assert handle.calls == ["read"]
    assert not matches_runtime_protocol(MissingInheritedMember(), CompleteSurface)
    assert not matches_runtime_protocol_definition(MissingInheritedMember(), CompleteSurface)
    assert not matches_runtime_protocol(NonCallableMethod(), CompleteSurface)
    assert not matches_runtime_protocol_definition(NonCallableMethod(), CompleteSurface)
    assert not matches_runtime_protocol_definition(handle, object())
    assert not matches_runtime_protocol_definition(handle, DynamicHandle)

    class AccessDenied(DynamicHandle):
        def __getattr__(self, name: str):
            if name == "read":
                raise PermissionError("read is denied")
            return super().__getattr__(name)

    with pytest.raises(PermissionError, match="read is denied"):
        matches_runtime_protocol_definition(AccessDenied(), CompleteSurface)

    class DynamicCoreStore:
        def __getattr__(self, name: str):
            if name == "root":
                return Path("/guarded/cas")
            if name in {
                "has",
                "get_bytes",
                "get_manifest",
                "put_bytes",
                "put_json",
                "verify",
                "iter_artifact_ids",
                "get_raw_manifest_bytes",
            }:
                return lambda *_args, **_kwargs: None
            raise AttributeError(name)

    class RootedWithoutRawManifest(DynamicCoreStore):
        def __getattr__(self, name: str):
            if name == "get_raw_manifest_bytes":
                raise AttributeError(name)
            return super().__getattr__(name)

    class CoreJSONWithoutRoot(DynamicCoreStore):
        def __getattr__(self, name: str):
            if name == "root":
                raise AttributeError(name)
            return super().__getattr__(name)

    assert matches_runtime_protocol_definition(DynamicCoreStore(), _RootedCoreJSONArtifactStore)
    assert not matches_runtime_protocol_definition(
        RootedWithoutRawManifest(), _RootedCoreJSONArtifactStore
    )
    assert not matches_runtime_protocol_definition(
        CoreJSONWithoutRoot(), _RootedCoreJSONArtifactStore
    )


def test_runtime_protocol_matcher_requires_inherited_deferred_data_members() -> None:
    class ParentSurface(Protocol):
        source_root: NeverRuntimeProtocolAnnotation

        def read(self) -> bytes: ...

    class CompositeSurface(ParentSurface, Protocol):
        revision: NeverRuntimeProtocolAnnotation

        def write(self, data: bytes) -> None: ...

    class MissingInheritedData:
        revision = 7

        def read(self) -> bytes:
            return b"payload"

        def write(self, data: bytes) -> None:
            return None

    class MissingDirectData:
        source_root = Path("/source/root")

        def read(self) -> bytes:
            return b"payload"

        def write(self, data: bytes) -> None:
            return None

    class CompleteHandle:
        source_root = Path("/source/root")
        revision = 7

        def read(self) -> bytes:
            return b"payload"

        def write(self, data: bytes) -> None:
            return None

    assert not matches_runtime_protocol_definition(MissingInheritedData(), CompositeSurface)
    assert not matches_runtime_protocol(MissingInheritedData(), CompositeSurface)
    assert not matches_runtime_protocol_definition(MissingDirectData(), CompositeSurface)
    assert matches_runtime_protocol_definition(CompleteHandle(), CompositeSurface)
    assert matches_runtime_protocol(CompleteHandle(), CompositeSurface)


def test_protocol_member_fallback_reads_stored_annotation_names_without_evaluation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import typing

    legacy_surface = type(
        "LegacyStoredSurface",
        (Protocol,),
        {
            "__annotations__": {"required_root": "UnknownForwardReference"},
            "read": lambda _self: b"payload",
        },
    )
    monkeypatch.delattr(typing, "get_protocol_members")

    class MissingRoot:
        def read(self) -> bytes:
            return b"payload"

    class CompleteHandle:
        required_root = Path("/legacy/root")

        def read(self) -> bytes:
            return b"payload"

    assert not matches_runtime_protocol_definition(MissingRoot(), legacy_surface)
    assert matches_runtime_protocol_definition(CompleteHandle(), legacy_surface)


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


def test_core_adapter_accepts_explicit_positional_or_keyword_profile_parameter(
    tmp_path: Path,
) -> None:
    class PositionalOrKeywordStore:
        def __init__(self, delegate: FileSystemCAS) -> None:
            self.delegate = delegate
            self.selected_profile_calls: list[bool] = []

        def put_bytes(
            self,
            data: bytes,
            opts: PutOptions,
            return_selected_profile: bool = False,
        ) -> ArtifactRef:
            self.selected_profile_calls.append(return_selected_profile)
            return self.delegate.put_bytes(
                data,
                opts,
                return_selected_profile=return_selected_profile,
            )

        def __getattr__(self, name: str) -> Any:
            return getattr(self.delegate, name)

    payload = b"selected"
    store = PositionalOrKeywordStore(FileSystemCAS(tmp_path / "cas"))
    ref = CoreToIRArtifactStoreAdapter(store).put_bytes(
        payload,
        PutOptions(kind="test.profile.pos_or_kw", media_type="application/octet-stream"),
        return_selected_profile=True,
    )

    assert store.selected_profile_calls == [True]
    assert ref.artifact_id == ArtifactID.from_sha256_hex(hashlib.sha256(payload).hexdigest())
    manifest = store.get_manifest(ref)
    assert ref.manifest_profile_sha256 == artifact_manifest_profile_sha256(manifest)
    assert store.get_bytes(ref) == payload


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


def _cas_tree_state(root: Path) -> dict[str, tuple[int, int, int, int, int, str | None]]:
    """Capture path type, mode, inode, link count, mtime, size and bytes digest."""
    state: dict[str, tuple[int, int, int, int, int, str | None]] = {}
    if not root.exists():
        return state
    for path in [root, *sorted(root.rglob("*"))]:
        info = path.lstat()
        digest = (
            hashlib.sha256(path.read_bytes()).hexdigest() if stat.S_ISREG(info.st_mode) else None
        )
        relative_path = "." if path == root else path.relative_to(root).as_posix()
        state[relative_path] = (
            stat.S_IFMT(info.st_mode),
            stat.S_IMODE(info.st_mode),
            info.st_ino,
            info.st_nlink,
            info.st_mtime_ns,
            digest,
        )
    return state


def test_existing_read_only_cas_uses_reader_protocol_without_filesystem_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "cas"
    writer = FileSystemCAS(root)
    ref = writer.put_bytes(
        b"immutable-read-only-payload",
        PutOptions(kind="test.read_only", media_type="application/octet-stream"),
    )
    before = _cas_tree_state(root)
    original_os_open = os.open
    original_path_open = Path.open
    original_modes = {path: stat.S_IMODE(path.stat().st_mode) for path in [root, *root.rglob("*")]}

    def read_only_os_open(
        path: str | bytes | os.PathLike[str],
        flags: int,
        *args: object,
        **kwargs: object,
    ) -> int:
        write_flags = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
        assert flags & write_flags == 0, "read-only CAS attempted a write-capable open"
        return original_os_open(path, flags, *args, **kwargs)

    def read_only_path_open(
        path: Path,
        mode: str = "r",
        *args: object,
        **kwargs: object,
    ) -> Any:
        assert not any(flag in mode for flag in "wax+"), "read-only CAS opened a writable path"
        return original_path_open(path, mode, *args, **kwargs)

    def deny_mkdir(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("read-only CAS attempted to create a directory")

    monkeypatch.setattr(os, "open", read_only_os_open)
    monkeypatch.setattr(Path, "open", read_only_path_open)
    monkeypatch.setattr(Path, "mkdir", deny_mkdir)
    for path, mode in original_modes.items():
        path.chmod(mode & ~0o222)
    read_only_before = _cas_tree_state(root)
    try:
        reader = FileSystemCAS.open_existing_read_only(root)
        assert isinstance(reader, ArtifactReader)
        from polisyos.core.artifacts import VerifiableArtifactReader

        assert isinstance(reader, VerifiableArtifactReader)
        assert reader.has(ref)
        assert reader.get_manifest(ref).kind == ref.kind
        assert reader.get_bytes(ref.artifact_id) == b"immutable-read-only-payload"
        ir_reader = ensure_ir_artifact_store(reader)
        selector = ref.model_dump(mode="python")
        assert ir_reader.get_bytes(selector) == b"immutable-read-only-payload"
        assert ir_reader.get_manifest_bytes(selector) == reader.get_raw_manifest_bytes(ref)
        assert not hasattr(ir_reader, "put_bytes")
        assert not hasattr(ir_reader, "put_json")
        assert not hasattr(reader, "put_bytes")
        with pytest.raises(AttributeError):
            reader.put_bytes(b"forbidden", PutOptions(kind="test.write", media_type="text/plain"))
        assert _cas_tree_state(root) == read_only_before
    finally:
        for path, mode in original_modes.items():
            path.chmod(mode)
    assert _cas_tree_state(root) == before


def test_read_only_cas_refuses_existing_pending_transaction_without_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "cas"
    writer = FileSystemCAS(root)
    payload = b"a pending transaction must block every read surface"
    artifact_id = ArtifactID.from_sha256_hex(hashlib.sha256(payload).hexdigest())

    def interrupt_before_first_final(
        stage_path: Path | None,
        final_path: Path,
        *,
        expected_sha256: str,
    ) -> bool:
        raise RuntimeError("simulated interruption after durable transaction intent")

    monkeypatch.setattr(writer, "_publish_transaction_member", interrupt_before_first_final)
    with pytest.raises(
        RuntimeError, match="simulated interruption after durable transaction intent"
    ):
        writer.put_bytes(
            payload,
            PutOptions(kind="test.read_only_pending", media_type="application/octet-stream"),
        )

    intent_path = writer._ownership_index._transaction_intent_path(artifact_id)
    assert intent_path.is_file()
    intent = json.loads(intent_path.read_text(encoding="utf-8"))
    assert intent["status"] == "pending"

    reader = FileSystemCAS.open_existing_read_only(root)
    attempts = (
        ("writer.has", lambda: writer.has(artifact_id)),
        ("writer.get_manifest", lambda: writer.get_manifest(artifact_id)),
        ("writer.get_bytes", lambda: writer.get_bytes(artifact_id)),
        ("reader.has", lambda: reader.has(artifact_id)),
        ("reader.get_manifest", lambda: reader.get_manifest(artifact_id)),
        ("reader.get_bytes", lambda: reader.get_bytes(artifact_id)),
    )
    before_reads = _cas_tree_state(root)
    for name, attempt in attempts:
        with pytest.raises(ArtifactTransactionPendingError) as error:
            attempt()
        assert error.value.code == ArtifactTransactionPendingError.code, name
        assert _cas_tree_state(root) == before_reads, name


def test_read_only_cas_refuses_missing_root_without_creating_it(tmp_path: Path) -> None:
    root = tmp_path / "missing-cas"
    assert not root.exists()

    with pytest.raises(ArtifactReadOnlyUnavailableError):
        FileSystemCAS.open_existing_read_only(root)

    assert not root.exists()


def test_read_only_cas_refuses_missing_root_lock_without_recreating_it(tmp_path: Path) -> None:
    root = tmp_path / "cas"
    writer = FileSystemCAS(root)
    writer.put_bytes(
        b"root-lock-payload",
        PutOptions(kind="test.read_only", media_type="application/octet-stream"),
    )
    root_lock = root / "artifacts/ownership/transactions/root.lock"
    root_lock.unlink()
    before = _cas_tree_state(root)

    with pytest.raises(ArtifactReadOnlyUnavailableError):
        FileSystemCAS.open_existing_read_only(root)

    assert _cas_tree_state(root) == before


def test_read_only_cas_reports_missing_artifact_without_materializing_state(
    tmp_path: Path,
) -> None:
    root = tmp_path / "cas"
    writer = FileSystemCAS(root)
    existing_ref = writer.put_bytes(
        b"existing-stripe-payload",
        PutOptions(kind="test.read_only", media_type="application/octet-stream"),
    )
    existing_stripe = int(existing_ref.artifact_id.hex, 16) % 64
    absent_id = next(
        candidate
        for suffix in range(256)
        if (
            candidate := ArtifactID.from_sha256_hex(
                existing_ref.artifact_id.hex[:-2] + f"{suffix:02x}"
            )
        )
        != existing_ref.artifact_id
        and int(candidate.hex, 16) % 64 == existing_stripe
    )
    before = _cas_tree_state(root)
    reader = FileSystemCAS.open_existing_read_only(root)

    assert not reader.has(absent_id)
    with pytest.raises(FileNotFoundError):
        reader.get_bytes(absent_id)

    assert _cas_tree_state(root) == before


def test_read_only_cas_refuses_missing_stripe_lock_without_recreating_it(tmp_path: Path) -> None:
    root = tmp_path / "cas"
    writer = FileSystemCAS(root)
    ref = writer.put_bytes(
        b"stripe-lock-payload",
        PutOptions(kind="test.read_only", media_type="application/octet-stream"),
    )
    stripe = int(ref.artifact_id.hex, 16) % 64
    stripe_lock = root / "artifacts/ownership/transactions/locks" / f"stripe-{stripe:02d}.lock"
    stripe_lock.unlink()
    before = _cas_tree_state(root)

    reader = FileSystemCAS.open_existing_read_only(root)
    with pytest.raises(ArtifactReadOnlyUnavailableError):
        reader.get_bytes(ref.artifact_id)

    assert _cas_tree_state(root) == before


@pytest.mark.parametrize(
    ("corruption", "expected_error"),
    [
        ("blob", ArtifactIntegrityError),
        ("malformed_manifest", ValueError),
        ("manifest_identity", ArtifactIntegrityError),
        ("blob_symlink", ArtifactIntegrityError),
        ("dangling_blob_symlink", ArtifactIntegrityError),
        ("dangling_manifest_symlink", ArtifactIntegrityError),
        ("blob_directory", ArtifactIntegrityError),
        ("manifest_directory", ArtifactIntegrityError),
    ],
)
def test_read_only_cas_refuses_present_invalid_artifacts_without_repair(
    tmp_path: Path,
    corruption: str,
    expected_error: type[Exception],
) -> None:
    root = tmp_path / "cas"
    writer = FileSystemCAS(root)
    ref = writer.put_bytes(
        b"integrity-bound-payload",
        PutOptions(kind="test.read_only", media_type="application/octet-stream"),
    )
    artifact_dir = root / "artifacts/sha256" / ref.artifact_id.hex[:2] / ref.artifact_id.hex[2:4]
    blob_path = artifact_dir / f"{ref.artifact_id.hex}.blob"
    manifest_path = artifact_dir / f"{ref.artifact_id.hex}.manifest.json"
    external_blob = tmp_path / "outside-cas.bin"
    if corruption == "blob":
        blob_path.write_bytes(b"forged-present-payload")
    elif corruption in {"blob_symlink", "dangling_blob_symlink"}:
        target = external_blob
        if corruption == "blob_symlink":
            external_blob.write_bytes(b"integrity-bound-payload")
        else:
            target = tmp_path / "missing-blob-target"
        blob_path.unlink()
        blob_path.symlink_to(target)
    elif corruption == "dangling_manifest_symlink":
        manifest_path.unlink()
        manifest_path.symlink_to(tmp_path / "missing-manifest-target")
    elif corruption == "blob_directory":
        blob_path.unlink()
        blob_path.mkdir()
    elif corruption == "manifest_directory":
        manifest_path.unlink()
        manifest_path.mkdir()
    elif corruption == "malformed_manifest":
        manifest_path.write_bytes(b"{")
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["artifact_id"] = "sha256:" + ("0" * 64)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    before = _cas_tree_state(root)

    reader = FileSystemCAS.open_existing_read_only(root)
    with pytest.raises(expected_error):
        reader.has(ref)
    with pytest.raises(expected_error):
        reader.get_bytes(ref.artifact_id)

    assert _cas_tree_state(root) == before
    if corruption == "blob_symlink":
        assert external_blob.read_bytes() == b"integrity-bound-payload"


def test_read_only_cas_refuses_manifest_without_blob_without_repair(tmp_path: Path) -> None:
    root = tmp_path / "cas"
    writer = FileSystemCAS(root)
    ref = writer.put_bytes(
        b"partial-member-payload",
        PutOptions(kind="test.read_only", media_type="application/octet-stream"),
    )
    blob_dir = root / "artifacts/sha256" / ref.artifact_id.hex[:2] / ref.artifact_id.hex[2:4]
    (blob_dir / f"{ref.artifact_id.hex}.blob").unlink()
    before = _cas_tree_state(root)

    reader = FileSystemCAS.open_existing_read_only(root)
    with pytest.raises(ArtifactIntegrityError, match="manifest exists without its blob"):
        reader.has(ref)

    assert _cas_tree_state(root) == before


def test_read_only_cas_does_not_fall_back_from_missing_selected_profile(
    tmp_path: Path,
) -> None:
    root = tmp_path / "cas"
    writer = FileSystemCAS(root)
    default_ref = writer.put_bytes(
        b"default-only-payload",
        PutOptions(kind="test.read_only", media_type="application/octet-stream"),
    )
    selected_ref = ArtifactRef(
        artifact_id=default_ref.artifact_id,
        kind=default_ref.kind,
        media_type=default_ref.media_type,
        manifest_profile_sha256="sha256:" + "0" * 64,
    )
    before = _cas_tree_state(root)

    reader = FileSystemCAS.open_existing_read_only(root)
    assert reader.has(default_ref)
    assert not reader.has(selected_ref)
    with pytest.raises(FileNotFoundError):
        reader.get_manifest(selected_ref)

    assert _cas_tree_state(root) == before


@pytest.mark.parametrize(
    ("failure_stage", "member"),
    [
        ("status", "blob"),
        ("status", "manifest"),
        ("read", "blob"),
        ("read", "manifest"),
    ],
)
def test_read_only_cas_refuses_os_errors_without_claiming_absence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_stage: str,
    member: str,
) -> None:
    root = tmp_path / "cas"
    writer = FileSystemCAS(root)
    ref = writer.put_bytes(
        b"unreadable-member-payload",
        PutOptions(kind="test.read_only", media_type="application/octet-stream"),
    )
    blob_dir = root / "artifacts/sha256" / ref.artifact_id.hex[:2] / ref.artifact_id.hex[2:4]
    blob_path = blob_dir / f"{ref.artifact_id.hex}.blob"
    manifest_path = blob_dir / f"{ref.artifact_id.hex}.manifest.json"
    member_path = blob_path if member == "blob" else manifest_path
    before = _cas_tree_state(root)
    reader = FileSystemCAS.open_existing_read_only(root)
    original_lstat = os.lstat
    original_open = os.open

    def denied_lstat(path: str | bytes | os.PathLike[str]) -> os.stat_result:
        if Path(path) == member_path:
            raise PermissionError("controlled CAS member status denial")
        return original_lstat(path)

    def denied_open(
        path: str | bytes | os.PathLike[str],
        flags: int,
        *args: object,
        **kwargs: object,
    ) -> int:
        if Path(path) == member_path:
            raise PermissionError("controlled CAS member read denial")
        return original_open(path, flags, *args, **kwargs)

    with monkeypatch.context() as patcher:
        if failure_stage == "status":
            patcher.setattr(os, "lstat", denied_lstat)
        else:
            patcher.setattr(os, "open", denied_open)
        with pytest.raises(ArtifactReadOnlyUnavailableError):
            reader.has(ref)

    assert _cas_tree_state(root) == before


def test_read_only_cas_refuses_symlinked_member_parent_without_repair(tmp_path: Path) -> None:
    root = tmp_path / "cas"
    writer = FileSystemCAS(root)
    ref = writer.put_bytes(
        b"symlinked-parent-payload",
        PutOptions(kind="test.read_only", media_type="application/octet-stream"),
    )
    artifact_dir = root / "artifacts/sha256" / ref.artifact_id.hex[:2] / ref.artifact_id.hex[2:4]
    external_dir = tmp_path / "external-artifact-dir"
    artifact_dir.rename(external_dir)
    artifact_dir.symlink_to(external_dir, target_is_directory=True)
    before_root = _cas_tree_state(root)
    before_external = _cas_tree_state(external_dir)

    reader = FileSystemCAS.open_existing_read_only(root)
    with pytest.raises(ArtifactIntegrityError, match="path crosses a symlink"):
        reader.has(ref)

    assert _cas_tree_state(root) == before_root
    assert _cas_tree_state(external_dir) == before_external
