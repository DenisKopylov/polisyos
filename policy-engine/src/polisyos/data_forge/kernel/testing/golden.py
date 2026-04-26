"""Golden artifact helpers for freeze-safe Data Forge migration tests."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from polisyos.data_forge.kernel._base import DataForgeModel
from polisyos.data_forge.kernel.io import sha256_file


class GoldenArtifact(DataForgeModel):
    """Checksum contract for one golden artifact."""

    name: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class GoldenCase(DataForgeModel):
    """Named collection of golden artifacts captured for a migration step."""

    case_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$")
    artifacts: tuple[GoldenArtifact, ...] = Field(default_factory=tuple)


def capture_golden_file(root: str | Path, relative_path: str, *, name: str) -> GoldenArtifact:
    """Capture a golden artifact checksum without mutating the source file."""
    root_path = Path(root)
    artifact_path = root_path / relative_path
    return GoldenArtifact(
        name=name,
        relative_path=relative_path,
        sha256=sha256_file(artifact_path),
    )


def verify_golden_file(root: str | Path, artifact: GoldenArtifact) -> bool:
    """Return whether the current file still matches the golden checksum."""
    return sha256_file(Path(root) / artifact.relative_path) == artifact.sha256


__all__ = [
    "GoldenArtifact",
    "GoldenCase",
    "capture_golden_file",
    "verify_golden_file",
]
