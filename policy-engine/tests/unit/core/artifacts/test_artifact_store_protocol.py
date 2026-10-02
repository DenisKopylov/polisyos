"""Tests for ArtifactStore protocol and FileSystemCAS conformance."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, artifact_ref_identity_key
from polisyos.core.artifacts.ownership import (
    ArtifactOwnershipError,
    ArtifactPublicReadClosureUnavailableError,
)
from polisyos.core.artifacts.protocol import ArtifactStore
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
