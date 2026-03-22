"""Tests for ArtifactStoreConfig and build_artifact_store factory."""
from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.core.artifacts.backends.config import ArtifactStoreConfig, build_artifact_store
from polisyos.core.artifacts.protocol import ArtifactStore
from polisyos.core.artifacts.store import FileSystemCAS


class TestArtifactStoreConfig:
    def test_default_backend(self):
        cfg = ArtifactStoreConfig()
        assert cfg.backend == "filesystem"

    def test_extra_fields_forbidden(self):
        with pytest.raises(Exception):
            ArtifactStoreConfig(backend="filesystem", unknown_field="x")

    def test_from_env_defaults(self, monkeypatch):
        monkeypatch.delenv("POLISYOS_CAS_BACKEND", raising=False)
        monkeypatch.delenv("POLISYOS_CAS_BUCKET", raising=False)
        cfg = ArtifactStoreConfig.from_env()
        assert cfg.backend == "filesystem"
        assert cfg.bucket is None

    def test_from_env_s3(self, monkeypatch):
        monkeypatch.setenv("POLISYOS_CAS_BACKEND", "s3")
        monkeypatch.setenv("POLISYOS_CAS_BUCKET", "my-bucket")
        monkeypatch.setenv("POLISYOS_CAS_REGION", "eu-west-1")
        cfg = ArtifactStoreConfig.from_env()
        assert cfg.backend == "s3"
        assert cfg.bucket == "my-bucket"
        assert cfg.region == "eu-west-1"


class TestBuildArtifactStore:
    def test_filesystem_backend(self, tmp_path: Path):
        cfg = ArtifactStoreConfig(backend="filesystem", root=str(tmp_path / "cas"))
        store = build_artifact_store(cfg)
        assert isinstance(store, FileSystemCAS)
        assert isinstance(store, ArtifactStore)

    def test_s3_backend_requires_bucket(self):
        cfg = ArtifactStoreConfig(backend="s3")
        with pytest.raises(ValueError, match="bucket"):
            build_artifact_store(cfg)

    def test_gcs_backend_requires_bucket(self):
        cfg = ArtifactStoreConfig(backend="gcs")
        with pytest.raises(ValueError, match="bucket"):
            build_artifact_store(cfg)

    def test_cached_s3_requires_bucket(self):
        cfg = ArtifactStoreConfig(backend="cached_s3")
        with pytest.raises(ValueError, match="bucket"):
            build_artifact_store(cfg)

    def test_unknown_backend_raises(self):
        cfg = ArtifactStoreConfig.__new__(ArtifactStoreConfig)
        object.__setattr__(cfg, "backend", "unknown")
        object.__setattr__(cfg, "root", None)
        object.__setattr__(cfg, "bucket", None)
        object.__setattr__(cfg, "prefix", "x")
        object.__setattr__(cfg, "region", "x")
        object.__setattr__(cfg, "local_cache_dir", None)
        with pytest.raises(ValueError, match="Unknown CAS backend"):
            build_artifact_store(cfg)
