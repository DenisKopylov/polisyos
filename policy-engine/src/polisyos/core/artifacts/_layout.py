"""Stable filesystem CAS path layout helpers."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from .ids import ArtifactID


class CASPathLayout:
    """Own the stable filesystem CAS path ABI."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.base = root / "artifacts" / "sha256"

    def paths(self, artifact_id: ArtifactID) -> tuple[Path, Path]:
        hex64 = artifact_id.hex
        dirp = self.base / hex64[:2] / hex64[2:4]
        return dirp / f"{hex64}.blob", dirp / f"{hex64}.manifest.json"

    def sig_path(self, artifact_id: ArtifactID) -> Path:
        hex64 = artifact_id.hex
        return self.base / hex64[:2] / hex64[2:4] / f"{hex64}.sig"


__all__ = ["CASPathLayout"]
