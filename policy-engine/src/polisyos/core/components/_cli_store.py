"""Shared CLI helpers for constructing local artifact stores."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from polisyos.core.artifacts.backends.config import ArtifactStoreConfig, build_artifact_store

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.core.artifacts.store import FileSystemCAS


def _normalize_root(root: str | Path) -> Path:
    return Path(root).expanduser()


def build_cli_artifact_store(root: str | Path) -> ArtifactStore:
    """Construct the default CLI artifact store through the declarative backend factory."""

    return cast(
        "ArtifactStore",
        build_artifact_store(
            ArtifactStoreConfig(
                backend="filesystem",
                root=str(_normalize_root(root)),
            )
        ),
    )


def build_cli_filesystem_cas(root: str | Path) -> FileSystemCAS:
    """Construct the local filesystem CAS used by CLI commands that need local-only helpers."""

    return cast("FileSystemCAS", build_cli_artifact_store(root))


__all__ = ["build_cli_artifact_store", "build_cli_filesystem_cas"]
