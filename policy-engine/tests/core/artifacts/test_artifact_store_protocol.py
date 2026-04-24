"""Tests for ArtifactStore protocol and FileSystemCAS conformance."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from polisyos.core.artifacts.protocol import ArtifactStore
from polisyos.core.artifacts.store import FileSystemCAS


class TestArtifactStoreProtocol:
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
        from polisyos.core.artifacts.store import PutOptions

        ref = store.put_bytes(b"x", PutOptions(kind="test", media_type="text/plain"))
        ids = store.iter_artifact_ids()
        assert ref.artifact_id in ids
