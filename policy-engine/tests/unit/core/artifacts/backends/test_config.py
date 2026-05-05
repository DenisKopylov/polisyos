"""Tests for ArtifactStoreConfig and build_artifact_store factory."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from polisyos.core.artifacts.backends.config import (
    ArtifactStoreConfig,
    build_artifact_store,
    build_async_artifact_store,
    infer_artifact_store_config,
    infer_async_artifact_store_config,
)
from polisyos.core.artifacts.protocol import ArtifactStore, AsyncArtifactStore
from polisyos.core.artifacts.store import FileSystemCAS
from pydantic import ValidationError

if TYPE_CHECKING:
    from pathlib import Path


class _TracerStub:
    pass


class _MetricsStub:
    pass


class TestArtifactStoreConfig:
    def test_default_backend(self):
        cfg = ArtifactStoreConfig()
        assert cfg.backend == "filesystem"

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
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

    def test_from_env_rejects_unknown_backend(self, monkeypatch):
        monkeypatch.setenv("POLISYOS_CAS_BACKEND", "mystery")
        with pytest.raises(ValueError, match="Unknown CAS backend"):
            ArtifactStoreConfig.from_env()


class TestBuildArtifactStore:
    def test_filesystem_backend(self, tmp_path: Path):
        cfg = ArtifactStoreConfig(backend="filesystem", root=str(tmp_path / "cas"))
        store = build_artifact_store(cfg)
        assert isinstance(store, FileSystemCAS)
        assert isinstance(store, ArtifactStore)

    def test_filesystem_backend_receives_injected_providers(self, tmp_path: Path):
        cfg = ArtifactStoreConfig(backend="filesystem", root=str(tmp_path / "cas"))
        metrics = _MetricsStub()
        tracer = _TracerStub()

        store = build_artifact_store(cfg, metrics=metrics, tracer=tracer)

        assert isinstance(store, FileSystemCAS)
        assert store._metrics is metrics
        assert store._tracer is tracer

    def test_filesystem_backend_uses_default_observability_helpers(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        tracer = _TracerStub()
        metrics = _MetricsStub()
        monkeypatch.setattr(
            "polisyos.core.artifacts.store.is_hpc_observability_enabled",
            lambda: True,
        )
        monkeypatch.setattr(
            "polisyos.core.artifacts.store._default_tracer",
            lambda: tracer,
        )
        monkeypatch.setattr(
            "polisyos.core.artifacts.store._default_metrics",
            lambda: metrics,
        )
        monkeypatch.setattr(
            "polisyos.core.artifacts.store.get_tracer",
            lambda: (_ for _ in ()).throw(
                AssertionError("default tracer helper should isolate direct tracer lookup")
            ),
        )
        monkeypatch.setattr(
            "polisyos.core.artifacts.store.get_metrics",
            lambda: (_ for _ in ()).throw(
                AssertionError("default metrics helper should isolate direct metrics lookup")
            ),
        )

        store = FileSystemCAS(tmp_path / "cas")

        assert store._tracer is tracer
        assert store._metrics is metrics

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

    def test_infer_artifact_store_config_for_filesystem(self, tmp_path: Path) -> None:
        store = FileSystemCAS(tmp_path / "cas")

        inferred = infer_artifact_store_config(store)

        assert inferred == ArtifactStoreConfig(
            backend="filesystem",
            root=str(tmp_path / "cas"),
        )

    def test_build_async_artifact_store_for_filesystem(self, tmp_path: Path) -> None:
        cfg = ArtifactStoreConfig(backend="filesystem", root=str(tmp_path / "cas"))

        async_store = build_async_artifact_store(cfg)

        assert isinstance(async_store, AsyncArtifactStore)
        assert infer_async_artifact_store_config(async_store) == cfg
