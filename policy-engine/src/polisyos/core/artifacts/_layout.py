"""Stable filesystem CAS path layout helpers."""

from __future__ import annotations

import re
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

    def view_manifest_path(self, artifact_id: ArtifactID, profile_sha256: str) -> Path:
        """Return the immutable manifest path for a selected profile view."""
        profile_hex = self._profile_hex(profile_sha256)
        hex64 = artifact_id.hex
        return (
            self.base
            / hex64[:2]
            / hex64[2:4]
            / f"{hex64}.view.{profile_hex}.manifest.json"
        )

    def view_sig_path(self, artifact_id: ArtifactID, profile_sha256: str) -> Path:
        """Return the detached-signature path for one selected profile view."""
        profile_hex = self._profile_hex(profile_sha256)
        hex64 = artifact_id.hex
        return self.base / hex64[:2] / hex64[2:4] / f"{hex64}.view.{profile_hex}.sig"

    @staticmethod
    def _profile_hex(profile_sha256: str) -> str:
        prefix, separator, digest = profile_sha256.partition(":")
        if (
            prefix != "sha256"
            or not separator
            or len(digest) != 64
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
        ):
            raise ValueError("manifest profile selector must be sha256:<64 lowercase hex>")
        return digest


__all__ = ["CASPathLayout"]
