"""Tests for CachingArtifactStore."""

from __future__ import annotations

from datetime import datetime, tzinfo
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from polisyos.core.artifacts._manifest_lifecycle import ManifestLifecycle
from polisyos.core.artifacts.backends.caching_store import CachingArtifactStore
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    ArtifactTenantContextInfo,
    InputRef,
    ProducerInfo,
)
from polisyos.core.artifacts.signing import Ed25519Signer, Ed25519Verifier
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions

_FAKE_ID = "sha256:" + "aa" * 32


def _make_ref(kind: str = "test") -> ArtifactRef:
    return ArtifactRef(artifact_id=_FAKE_ID, kind=kind, media_type="text/plain")


class TestCachingArtifactStore:
    def test_get_bytes_local_hit(self):
        """Local cache hit — remote is never called."""
        local = MagicMock()
        remote = MagicMock()
        local.has.return_value = True
        local.get_bytes.return_value = b"cached"

        store = CachingArtifactStore(remote=remote, local=local)
        result = store.get_bytes(_FAKE_ID)

        assert result == b"cached"
        remote.get_bytes.assert_not_called()

    def test_get_bytes_local_miss_remote_hit(self):
        """Local miss → fetch from remote → populate local cache."""
        local = MagicMock()
        remote = MagicMock()
        local.has.return_value = False
        local.get_bytes.side_effect = KeyError("not found")
        remote.get_bytes.return_value = b"remote-data"
        remote.get_manifest.return_value = MagicMock(kind="test", media_type="text/plain")

        store = CachingArtifactStore(remote=remote, local=local)
        result = store.get_bytes(_FAKE_ID)

        assert result == b"remote-data"
        remote.get_bytes.assert_called_once_with(_FAKE_ID)

    def test_get_bytes_cache_population_failure_can_raise(self):
        """Cache population degradation is explicit when policy is `raise`."""
        local = MagicMock()
        remote = MagicMock()
        local.get_bytes.side_effect = KeyError("not found")
        local.put_bytes.side_effect = OSError("cache disk unavailable")
        remote.get_bytes.return_value = b"remote-data"
        remote.get_manifest.return_value = MagicMock(kind="test", media_type="text/plain")

        store = CachingArtifactStore(
            remote=remote,
            local=local,
            cache_population_failure_policy="raise",
        )

        with pytest.raises(OSError, match="cache disk unavailable"):
            store.get_bytes(_FAKE_ID)

    def test_put_bytes_write_through(self, tmp_path: Path) -> None:
        """Write-through: both owners persist the same typed view and payload."""
        local = FileSystemCAS(tmp_path / "local-write-through")
        remote = FileSystemCAS(tmp_path / "remote-write-through")
        store = CachingArtifactStore(remote=remote, local=local, write_through=True)
        opts = PutOptions(kind="test", media_type="text/plain")
        ref = store.put_bytes(b"data", opts)

        assert local.get_bytes(ref) == b"data"
        assert remote.get_bytes(ref) == b"data"
        assert store.get_manifest(ref).kind == "test"
        assert (
            ManifestLifecycle.profile_sha256(local.get_manifest(ref))
            == ManifestLifecycle.profile_sha256(remote.get_manifest(ref))
        )

    def test_put_bytes_no_write_through(self):
        """write_through=False: only writes to local."""
        local = MagicMock()
        remote = MagicMock()
        local.put_bytes.return_value = _make_ref()

        store = CachingArtifactStore(remote=remote, local=local, write_through=False)
        opts = PutOptions(kind="test", media_type="text/plain")
        store.put_bytes(b"data", opts)

        local.put_bytes.assert_called_once()
        remote.put_bytes.assert_not_called()

    def test_write_through_false_keeps_local_store_as_default_owner(
        self,
        tmp_path: Path,
    ) -> None:
        local = FileSystemCAS(tmp_path / "local-only")
        remote = FileSystemCAS(tmp_path / "unused-remote")
        store = CachingArtifactStore(remote=remote, local=local, write_through=False)
        options = PutOptions(
            kind="cache.local-only",
            media_type="text/plain",
            producer=ProducerInfo(component="tests.cache", version="local-only"),
        )

        ref = store.put_bytes(b"local-only artifact", options)

        assert remote.iter_artifact_ids() == []
        assert store.has(ref) is True
        assert store.iter_artifact_ids() == [ref.artifact_id]
        assert store.get_manifest(ref).producer.version == "local-only"
        assert store.verify(ref).ok is True

    def test_write_through_selectorless_has_uses_remote_default_owner(
        self,
        tmp_path: Path,
    ) -> None:
        local = FileSystemCAS(tmp_path / "cache-only")
        remote = FileSystemCAS(tmp_path / "durable-owner")
        local_ref = local.put_bytes(
            b"local-only orphan",
            PutOptions(
                kind="cache.default-owner",
                media_type="text/plain",
                producer=ProducerInfo(component="tests.cache", version="cache-only"),
            ),
        )
        local_manifest = local.get_manifest(local_ref)
        selected_local_view = ArtifactRef(
            artifact_id=local_ref.artifact_id,
            kind=local_manifest.kind,
            media_type=local_manifest.media_type,
            manifest_profile_sha256=ManifestLifecycle.profile_sha256(local_manifest),
        )
        store = CachingArtifactStore(remote=remote, local=local)

        assert store.has(local_ref.artifact_id) is False
        assert store.has(selected_local_view) is True
        assert store.get_manifest(selected_local_view).producer.version == "cache-only"
        assert store.verify(selected_local_view).ok is True

    def test_write_through_inventory_omits_cache_only_default_orphans(
        self,
        tmp_path: Path,
    ) -> None:
        local = FileSystemCAS(tmp_path / "cache-only-inventory")
        remote = FileSystemCAS(tmp_path / "durable-inventory")
        local.put_bytes(
            b"local-only inventory orphan",
            PutOptions(kind="cache.inventory", media_type="text/plain"),
        )
        remote_ref = remote.put_bytes(
            b"durable inventory artifact",
            PutOptions(kind="cache.inventory", media_type="text/plain"),
        )

        assert CachingArtifactStore(remote=remote, local=local).iter_artifact_ids() == [
            remote_ref.artifact_id
        ]

    def test_has_selector_free_delegates_to_remote_default_owner(self):
        local = MagicMock()
        remote = MagicMock()
        local.has.return_value = True
        remote.has.return_value = False

        store = CachingArtifactStore(remote=remote, local=local)
        assert store.has(_FAKE_ID) is False
        remote.has.assert_called_once_with(_FAKE_ID)
        local.has.assert_not_called()

    def test_has_local_false_remote_true(self):
        local = MagicMock()
        remote = MagicMock()
        local.has.return_value = False
        remote.has.return_value = True

        store = CachingArtifactStore(remote=remote, local=local)
        assert store.has(_FAKE_ID) is True

    def test_verify_selector_free_delegates_to_remote(self):
        local = MagicMock()
        remote = MagicMock()
        local.has.return_value = True
        expected = MagicMock(ok=True)
        remote.verify.return_value = expected

        store = CachingArtifactStore(remote=remote, local=local)
        report = store.verify(_FAKE_ID)
        assert report.ok is True
        remote.verify.assert_called_once_with(_FAKE_ID)
        local.verify.assert_not_called()

    def test_verify_selected_view_uses_local_when_cached(self):
        local = MagicMock()
        remote = MagicMock()
        local.has.return_value = True
        expected = MagicMock(ok=True)
        local.verify.return_value = expected
        selected_ref = ArtifactRef(
            artifact_id=_FAKE_ID,
            kind="test",
            media_type="text/plain",
            manifest_profile_sha256="sha256:" + "bb" * 32,
        )

        report = CachingArtifactStore(remote=remote, local=local).verify(selected_ref)

        assert report is expected
        local.verify.assert_called_once_with(selected_ref)
        remote.verify.assert_not_called()

    def test_remote_population_preserves_the_complete_selected_manifest_profile(
        self,
        tmp_path: Path,
    ) -> None:
        remote = FileSystemCAS(tmp_path / "remote")
        local = FileSystemCAS(tmp_path / "local")
        selected = remote.put_bytes(
            b"cache exact-view bytes",
            PutOptions(
                kind="cache.selected.view",
                media_type="application/octet-stream",
                tenant_context=ArtifactTenantContextInfo(tenant_id="tenant-a"),
            ),
        )
        store = CachingArtifactStore(remote=remote, local=local)

        assert store.get_bytes(selected) == b"cache exact-view bytes"

        assert local.has(selected)
        assert local.get_manifest(selected) == remote.get_manifest(selected)

    def test_selectorless_manifest_read_uses_remote_default_when_cache_defaults_diverge(
        self,
        tmp_path: Path,
    ) -> None:
        """The remote default wins when equal bytes have distinct first-writer profiles."""
        payload = b"same bytes, independent cache defaults"
        local = FileSystemCAS(tmp_path / "local")
        remote = FileSystemCAS(tmp_path / "remote")
        local_ref = local.put_bytes(
            payload,
            PutOptions(
                kind="cache.shared-kind",
                media_type="text/plain",
                producer=ProducerInfo(component="tests.cache", version="local-first"),
            ),
        )
        remote_ref = remote.put_bytes(
            payload,
            PutOptions(
                kind="cache.shared-kind",
                media_type="text/plain",
                producer=ProducerInfo(component="tests.cache", version="remote-first"),
            ),
        )
        assert local_ref.artifact_id == remote_ref.artifact_id
        assert local_ref == remote_ref
        assert (
            local.get_manifest(local_ref).producer.version
            != remote.get_manifest(remote_ref).producer.version
        )

        store = CachingArtifactStore(remote=remote, local=local)

        assert store.get_manifest(remote_ref).producer.version == "remote-first"
        assert store.get_manifest(remote_ref.artifact_id).producer.version == "remote-first"
        assert store.has(remote_ref.artifact_id) is True
        assert store.iter_artifact_ids() == [remote_ref.artifact_id]
        # Payload reads and byte-integrity reports remain valid because the blob ID is shared.
        assert store.get_bytes(remote_ref) == payload
        assert store.verify(remote_ref).ok is True

    def test_selectorless_verification_uses_remote_default_when_cache_defaults_diverge(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        payload = b"verify must follow the composite default owner"
        local = FileSystemCAS(tmp_path / "verify-local")
        remote = FileSystemCAS(tmp_path / "verify-remote")
        local_ref = local.put_bytes(
            payload,
            PutOptions(
                kind="cache.verify-default",
                media_type="text/plain",
                producer=ProducerInfo(component="tests.cache", version="local-first"),
            ),
        )
        remote_ref = remote.put_bytes(
            payload,
            PutOptions(
                kind="cache.verify-default",
                media_type="text/plain",
                producer=ProducerInfo(component="tests.cache", version="remote-first"),
            ),
        )
        assert local_ref == remote_ref
        assert local.get_manifest(local_ref).producer.version == "local-first"
        assert remote.get_manifest(remote_ref).producer.version == "remote-first"
        assert local.has(remote_ref)

        local_verify = MagicMock(
            side_effect=AssertionError("selector-free verification used the cache default")
        )
        monkeypatch.setattr(local, "verify", local_verify)

        report = CachingArtifactStore(remote=remote, local=local).verify(remote_ref)

        assert report.ok is True
        local_verify.assert_not_called()

    @pytest.mark.parametrize("operation", ["put_bytes", "put_json"])
    @pytest.mark.parametrize("seed_local_default", [True, False])
    def test_write_through_accepts_remote_view_when_cache_defaults_diverge(
        self,
        tmp_path: Path,
        operation: str,
        seed_local_default: bool,
    ) -> None:
        local = FileSystemCAS(tmp_path / "write-local")
        remote = FileSystemCAS(tmp_path / "write-remote")
        payload = {"shared": "write-through payload"} if operation == "put_json" else b"shared"
        media_type = "application/json" if operation == "put_json" else "text/plain"

        def options(version: str) -> PutOptions:
            return PutOptions(
                kind="cache.write-through-view",
                media_type=media_type,
                producer=ProducerInfo(component="tests.cache", version=version),
            )

        seeded_store = local if seed_local_default else remote
        if operation == "put_json":
            seeded_store.put_json(payload, options("existing-default"))
        else:
            seeded_store.put_bytes(payload, options("existing-default"))

        store = CachingArtifactStore(remote=remote, local=local)
        if operation == "put_json":
            written_ref = store.put_json(payload, options("new-view"))
        else:
            written_ref = store.put_bytes(payload, options("new-view"))

        remote_manifest = remote.get_manifest(written_ref)
        assert remote_manifest.producer.version == "new-view"
        exact_remote_view = ArtifactRef(
            artifact_id=written_ref.artifact_id,
            kind=remote_manifest.kind,
            media_type=remote_manifest.media_type,
            manifest_profile_sha256=ManifestLifecycle.profile_sha256(remote_manifest),
        )
        assert local.get_manifest(exact_remote_view) == remote_manifest
        assert store.get_manifest(written_ref).producer.version == "new-view"
        assert store.verify(written_ref).ok is True

    def test_remote_child_read_skips_cache_when_input_view_is_not_locally_admitted(
        self,
        tmp_path: Path,
    ) -> None:
        remote = FileSystemCAS(tmp_path / "remote", tenant_id="tenant-a")
        local_root = tmp_path / "local"
        foreign_local = FileSystemCAS(local_root, tenant_id="tenant-b")
        local = FileSystemCAS(local_root, tenant_id="tenant-a")
        parent_options = PutOptions(
            kind="cache.parent",
            media_type="application/octet-stream",
            producer=ProducerInfo(component="tests.cache", version="parent"),
        )
        foreign_parent = foreign_local.put_bytes(b"shared parent bytes", parent_options)
        remote_parent = remote.put_bytes(b"shared parent bytes", parent_options)
        assert foreign_parent.artifact_id == remote_parent.artifact_id

        child_ref = remote.put_bytes(
            b"authorized remote child",
            PutOptions(
                kind="cache.child",
                media_type="application/octet-stream",
                producer=ProducerInfo(component="tests.cache", version="child"),
                inputs=(InputRef(artifact_id=remote_parent.artifact_id, role="parent"),),
            ),
        )
        # The local index admits the child blob for this reader, but has no local ownership
        # of the manifest's upstream view. The remote owner remains the authority for the
        # already-validated child read; cache population must not manufacture parent custody.
        local._ownership_index.record_blob_reader(
            child_ref.artifact_id,
            tenant_id="tenant-a",
        )
        store = CachingArtifactStore(remote=remote, local=local)

        assert store.get_bytes(child_ref) == b"authorized remote child"
        assert not local.has(child_ref)
        assert not local.has(remote_parent.artifact_id)
        with pytest.raises(PermissionError):
            local.get_bytes(remote_parent.artifact_id)

    def test_same_default_profile_remains_readable_through_cache(self, tmp_path: Path) -> None:
        payload = b"same default profile remains usable"
        opts = PutOptions(
            kind="cache.same-default",
            media_type="text/plain",
            producer=ProducerInfo(component="tests.cache", version="same"),
        )
        local = FileSystemCAS(tmp_path / "same-local")
        remote = FileSystemCAS(tmp_path / "same-remote")
        local_ref = local.put_bytes(payload, opts)
        remote_ref = remote.put_bytes(payload, opts)
        assert local_ref == remote_ref

        store = CachingArtifactStore(remote=remote, local=local)

        selected = store.get_manifest(remote_ref)
        assert selected.producer.version == "same"
        assert store.get_bytes(remote_ref) == payload
        assert store.verify(remote_ref).ok is True

    def test_cache_population_preserves_raw_manifest_and_signature_bytes(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        payload = b"historical signed manifest must remain byte exact"
        remote = FileSystemCAS(tmp_path / "signed-remote")
        local = FileSystemCAS(tmp_path / "signed-local")
        key = Ed25519PrivateKey.generate()
        signer = Ed25519Signer(key)
        verifier = Ed25519Verifier()
        verifier.add_trusted_key(key.public_key())
        ref = remote.put_bytes(
            payload,
            PutOptions(kind="cache.signed", media_type="application/octet-stream"),
        )
        remote.sign_artifact(ref, signer, signer_identity="cache-test")
        remote_manifest_bytes = remote.get_manifest_bytes(ref)
        remote_signature_bytes = remote.get_signature_bytes(ref)
        assert remote.verify_signature(ref, verifier).ok is True

        store = CachingArtifactStore(remote=remote, local=local)

        class HistoricalClock:
            @staticmethod
            def now(tz: tzinfo | None = None) -> datetime:
                return datetime(2000, 1, 1, tzinfo=tz)

        monkeypatch.setattr(
            "polisyos.core.artifacts.manifest.datetime",
            HistoricalClock,
        )
        assert store.get_bytes(ref) == payload

        assert local.get_manifest_bytes(ref) == remote_manifest_bytes
        assert local.get_signature_bytes(ref) == remote_signature_bytes
        assert local.verify_signature(ref, verifier).ok is True
