"""Atomic snapshot commit contracts."""

from __future__ import annotations

from pydantic import Field

import polisyos.data_forge.kernel.artifacts as artifact_contracts
from polisyos.data_forge.kernel._base import DataForgeModel, utc_now

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


__all__ = ["AtomicCommitResult", "CommitPlan"]
