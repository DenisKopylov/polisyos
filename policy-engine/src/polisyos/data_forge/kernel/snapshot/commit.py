"""Atomic snapshot commit contracts."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

import polisyos.data_forge.kernel.artifacts as artifact_contracts
from polisyos.data_forge.kernel._base import DataForgeModel, utc_now
from polisyos.data_forge.kernel.io import atomic_commit_path

ArtifactRef = artifact_contracts.ArtifactRef


class CommitPlan(DataForgeModel):
    """Write-then-rename commit plan for a snapshot publication."""

    staging_path: str = Field(min_length=1)
    final_path: str = Field(min_length=1)
    artifacts: tuple[ArtifactRef, ...] = Field(default_factory=tuple)


class AtomicCommitResult(DataForgeModel):
    """Result of a successful atomic commit."""

    final_path: str = Field(min_length=1)
    artifact_count: int = Field(ge=0)
    committed_at: str = Field(default_factory=lambda: utc_now().isoformat())


def commit_staged_path(plan: CommitPlan) -> AtomicCommitResult:
    """Atomically replace a final path with the plan staging path."""
    final_path = atomic_commit_path(Path(plan.staging_path), Path(plan.final_path))
    return AtomicCommitResult(
        final_path=str(final_path),
        artifact_count=len(plan.artifacts),
    )


__all__ = ["AtomicCommitResult", "CommitPlan", "commit_staged_path"]
