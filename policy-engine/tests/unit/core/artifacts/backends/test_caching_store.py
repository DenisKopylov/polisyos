"""Tests for CachingArtifactStore."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from polisyos.core.artifacts.backends.caching_store import CachingArtifactStore
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    ArtifactTenantContextInfo,
    ProducerInfo,
)
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

    def test_put_bytes_write_through(self):
        """Write-through: writes to both local and remote."""
        local = MagicMock()
        remote = MagicMock()
        local.put_bytes.return_value = _make_ref()
        remote.put_bytes.return_value = _make_ref()

        store = CachingArtifactStore(remote=remote, local=local, write_through=True)
        opts = PutOptions(kind="test", media_type="text/plain")
        store.put_bytes(b"data", opts)

        local.put_bytes.assert_called_once()
        remote.put_bytes.assert_called_once()

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

    def test_has_local_true(self):
        local = MagicMock()
        remote = MagicMock()
        local.has.return_value = True

        store = CachingArtifactStore(remote=remote, local=local)
        assert store.has(_FAKE_ID) is True
        remote.has.assert_not_called()

    def test_has_local_false_remote_true(self):
        local = MagicMock()
        remote = MagicMock()
        local.has.return_value = False
        remote.has.return_value = True

        store = CachingArtifactStore(remote=remote, local=local)
        assert store.has(_FAKE_ID) is True

    def test_verify_delegates_to_local(self):
        local = MagicMock()
        remote = MagicMock()
        local.has.return_value = True
        expected = MagicMock(ok=True)
        local.verify.return_value = expected

        store = CachingArtifactStore(remote=remote, local=local)
        report = store.verify(_FAKE_ID)
        assert report.ok is True
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
        # Payload reads and byte-integrity reports remain valid because the blob ID is shared.
        assert store.get_bytes(remote_ref) == payload
        assert store.verify(remote_ref).ok is True
