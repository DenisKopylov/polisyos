"""Backend configuration and factory helpers for ``ArtifactStore``."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from polisyos.core.observability import MetricsRegistry, PolicyOSTracer

    from ..protocol import ArtifactStore, AsyncArtifactStore

ArtifactBackend = Literal["filesystem", "s3", "gcs", "cached_s3", "cached_gcs"]
_VALID_BACKENDS = frozenset({"filesystem", "s3", "gcs", "cached_s3", "cached_gcs"})


def _coerce_backend(value: str) -> ArtifactBackend:
    normalized = value.strip()
    if normalized not in _VALID_BACKENDS:
        raise ValueError(f"Unknown CAS backend: {normalized!r}")
    return cast("ArtifactBackend", normalized)


class ArtifactStoreConfig(BaseModel):
    """Declarative CAS backend configuration."""

    model_config = ConfigDict(extra="forbid")

    backend: ArtifactBackend = "filesystem"
    root: str | None = None
    bucket: str | None = None
    prefix: str = "polisyos-cas"
    region: str = "us-east-1"
    local_cache_dir: str | None = None

    @classmethod
    def from_env(cls) -> ArtifactStoreConfig:
        return cls(
            backend=_coerce_backend(os.environ.get("POLISYOS_CAS_BACKEND", "filesystem")),
            root=os.environ.get("POLISYOS_CAS_ROOT"),
            bucket=os.environ.get("POLISYOS_CAS_BUCKET"),
            prefix=os.environ.get("POLISYOS_CAS_PREFIX", "polisyos-cas"),
            region=os.environ.get("POLISYOS_CAS_REGION", "us-east-1"),
            local_cache_dir=os.environ.get("POLISYOS_CAS_LOCAL_CACHE_DIR"),
        )


def build_artifact_store(
    config: ArtifactStoreConfig,
    *,
    metrics: MetricsRegistry | None = None,
    tracer: PolicyOSTracer | None = None,
) -> ArtifactStore:
    """Construct an ``ArtifactStore`` from declarative config."""
    if config.backend == "filesystem":
        from ..store import FileSystemCAS

        root = Path(config.root) if config.root else Path.cwd() / ".polisyos" / "cas"
        return FileSystemCAS(root, metrics=metrics, tracer=tracer)

    if config.backend == "s3":
        from .s3_store import S3ArtifactStore

        if not config.bucket:
            raise ValueError("ArtifactStoreConfig.bucket is required for s3 backend")
        cache_dir = Path(config.local_cache_dir) if config.local_cache_dir else None
        return S3ArtifactStore(
            bucket=config.bucket,
            prefix=config.prefix,
            region=config.region,
            local_cache_dir=cache_dir,
            metrics=metrics,
        )

    if config.backend == "gcs":
        from .gcs_store import GCSArtifactStore

        if not config.bucket:
            raise ValueError("ArtifactStoreConfig.bucket is required for gcs backend")
        cache_dir = Path(config.local_cache_dir) if config.local_cache_dir else None
        return GCSArtifactStore(
            bucket=config.bucket,
            prefix=config.prefix,
            local_cache_dir=cache_dir,
            metrics=metrics,
        )

    if config.backend in ("cached_s3", "cached_gcs"):
        from ..store import FileSystemCAS
        from .caching_store import CachingArtifactStore

        cache_root = (
            Path(config.local_cache_dir)
            if config.local_cache_dir
            else Path.cwd() / ".polisyos" / "cas" / "_cache"
        )
        local = FileSystemCAS(cache_root, metrics=metrics, tracer=tracer)

        if config.backend == "cached_s3":
            from .s3_store import S3ArtifactStore

            if not config.bucket:
                raise ValueError("ArtifactStoreConfig.bucket is required for cached_s3 backend")
            remote: ArtifactStore = S3ArtifactStore(
                bucket=config.bucket,
                prefix=config.prefix,
                region=config.region,
                metrics=metrics,
            )
        else:
            from .gcs_store import GCSArtifactStore

            if not config.bucket:
                raise ValueError("ArtifactStoreConfig.bucket is required for cached_gcs backend")
            remote = GCSArtifactStore(
                bucket=config.bucket,
                prefix=config.prefix,
                metrics=metrics,
            )

        return CachingArtifactStore(remote=remote, local=local)

    raise ValueError(f"Unknown CAS backend: {config.backend!r}")


def build_async_artifact_store(
    config: ArtifactStoreConfig,
    *,
    metrics: MetricsRegistry | None = None,
    tracer: PolicyOSTracer | None = None,
    timeout_seconds: float | None = None,
    sync_store: ArtifactStore | None = None,
) -> AsyncArtifactStore:
    """Construct an async CAS contract from declarative config plus an optional sync peer."""
    from ..async_store import AsyncArtifactStoreAdapter, AsyncFileSystemArtifactStore
    from ..store import FileSystemCAS

    if config.backend == "filesystem":
        if isinstance(sync_store, FileSystemCAS):
            return AsyncFileSystemArtifactStore(sync_store, timeout_seconds=timeout_seconds)
        root = Path(config.root) if config.root else Path.cwd() / ".polisyos" / "cas"
        return AsyncFileSystemArtifactStore(
            FileSystemCAS(root, metrics=metrics, tracer=tracer),
            timeout_seconds=timeout_seconds,
        )

    paired_store = sync_store or build_artifact_store(config, metrics=metrics, tracer=tracer)
    return AsyncArtifactStoreAdapter(paired_store, timeout_seconds=timeout_seconds)


def infer_artifact_store_config(store: ArtifactStore) -> ArtifactStoreConfig | None:
    """Best-effort reconstruction of declarative config from a live store.

    This is intentionally conservative: it only returns configurations that can
    be losslessly reconstructed from the store instance and that our bootstrap
    factory knows how to rebuild.
    """
    exporter = getattr(store, "artifact_store_config", None)
    if not callable(exporter):
        return None
    config = exporter()
    if config is None:
        return None
    if isinstance(config, ArtifactStoreConfig):
        return config
    if isinstance(config, dict):
        return ArtifactStoreConfig.model_validate(config)
    return None


def infer_async_artifact_store_config(
    store: AsyncArtifactStore | ArtifactStore,
) -> ArtifactStoreConfig | None:
    """Best-effort reconstruction of declarative config from an async or sync store."""
    exporter = getattr(store, "artifact_store_config", None)
    if callable(exporter):
        config = exporter()
        if isinstance(config, ArtifactStoreConfig):
            return config
        if isinstance(config, dict):
            return ArtifactStoreConfig.model_validate(config)
    sync_store = getattr(store, "store", None)
    if sync_store is not None:
        return infer_artifact_store_config(sync_store)
    return None
