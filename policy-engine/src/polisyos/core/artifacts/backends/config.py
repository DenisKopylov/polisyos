"""Backend configuration and factory for ArtifactStore."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from ..protocol import ArtifactStore


class ArtifactStoreConfig(BaseModel):
    """Declarative CAS backend configuration."""

    model_config = ConfigDict(extra="forbid")

    backend: Literal["filesystem", "s3", "gcs", "cached_s3", "cached_gcs"] = "filesystem"
    root: str | None = None
    bucket: str | None = None
    prefix: str = "polisyos-cas"
    region: str = "us-east-1"
    local_cache_dir: str | None = None

    @classmethod
    def from_env(cls) -> ArtifactStoreConfig:
        return cls(
            backend=os.environ.get("POLISYOS_CAS_BACKEND", "filesystem"),
            root=os.environ.get("POLISYOS_CAS_ROOT"),
            bucket=os.environ.get("POLISYOS_CAS_BUCKET"),
            prefix=os.environ.get("POLISYOS_CAS_PREFIX", "polisyos-cas"),
            region=os.environ.get("POLISYOS_CAS_REGION", "us-east-1"),
            local_cache_dir=os.environ.get("POLISYOS_CAS_LOCAL_CACHE_DIR"),
        )


def build_artifact_store(config: ArtifactStoreConfig) -> ArtifactStore:
    """Construct an ``ArtifactStore`` from declarative config."""
    if config.backend == "filesystem":
        from ..store import FileSystemCAS

        root = Path(config.root) if config.root else Path.cwd() / ".polisyos" / "cas"
        return FileSystemCAS(root)

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
        )

    if config.backend in ("cached_s3", "cached_gcs"):
        from ..store import FileSystemCAS

        from .caching_store import CachingArtifactStore

        cache_root = Path(config.local_cache_dir) if config.local_cache_dir else Path.cwd() / ".polisyos" / "cas_cache"
        local = FileSystemCAS(cache_root)

        if config.backend == "cached_s3":
            from .s3_store import S3ArtifactStore

            if not config.bucket:
                raise ValueError("ArtifactStoreConfig.bucket is required for cached_s3 backend")
            remote: ArtifactStore = S3ArtifactStore(
                bucket=config.bucket,
                prefix=config.prefix,
                region=config.region,
            )
        else:
            from .gcs_store import GCSArtifactStore

            if not config.bucket:
                raise ValueError("ArtifactStoreConfig.bucket is required for cached_gcs backend")
            remote = GCSArtifactStore(
                bucket=config.bucket,
                prefix=config.prefix,
            )

        return CachingArtifactStore(remote=remote, local=local)

    raise ValueError(f"Unknown CAS backend: {config.backend!r}")
