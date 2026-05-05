"""Tests for CachingArtifactStore."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from polisyos.core.artifacts.backends.caching_store import CachingArtifactStore
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import PutOptions

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
